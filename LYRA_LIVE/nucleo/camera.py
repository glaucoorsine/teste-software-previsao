# -*- coding: utf-8 -*-
"""
A captura da Lyra — por USB, por Wi-Fi, ou nenhuma das duas.

QUAL É A SUA LYRA
-----------------
"Câmera Lyra" pode chegar ao computador de dois jeitos, e o software aceita os
dois sem você precisar saber qual é:

* Por CABO, aparecendo como webcam comum (UVC). Aí ela tem um número —
  `--camera 0`, `--camera 1` — e `listar_cameras()` diz quais existem.
* Por REDE, publicando um endereço RTSP ou HTTP. Aí a origem é a URL inteira:
  `--camera rtsp://192.168.0.50:554/live`.

`abrir_fonte` olha o que você passou e escolhe sozinho. Número vira webcam,
texto com "://" vira stream de rede, caminho de arquivo vira vídeo (útil para
testar tudo sem câmera nenhuma).

DOIS MOTORES DE CAPTURA
-----------------------
`FonteOpenCV` é o caminho normal: rápido, baixa latência, enumera dispositivo.

`FonteFFmpeg` existe porque o ffmpeg já é dependência obrigatória (é ele quem
transmite para o YouTube), e porque ele abre RTSP com muito mais teimosia que o
OpenCV. Se o OpenCV não estiver instalado, ou se a câmera de rede se recusar a
abrir por ele, a captura continua existindo pelo ffmpeg. Um software de live que
morre porque uma biblioteca de visão computacional faltou não é um software de
live.

RECONEXÃO
---------
Câmera USB cai. Wi-Fi oscila. `FonteResiliente` reabre sozinha com espera
crescente e CONTA quantas vezes fez isso — esse número vai para as métricas, e é
daí que a IA supervisora descobre que o problema é o cabo, não a internet.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Union

import numpy as np

from . import imagem as IMG

try:
    import cv2
except Exception:  # pragma: no cover - depende da máquina
    cv2 = None

SISTEMA = platform.system()      # "Windows", "Linux", "Darwin"


@dataclass
class ConfigCamera:
    origem: Union[int, str] = 0
    largura: int = 1280
    altura: int = 720
    fps: int = 30
    backend: str = "auto"            # auto | opencv | ffmpeg
    formato: str = "auto"            # auto | mjpeg | yuyv — dica para o driver

    def como_dicionario(self) -> Dict:
        return asdict(self)

    @staticmethod
    def de_dicionario(d: Optional[Dict]) -> "ConfigCamera":
        base = ConfigCamera()
        for k, v in dict(d or {}).items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base


def normalizar_origem(origem) -> Union[int, str]:
    """"0" vira 0; "rtsp://..." e caminhos ficam texto."""
    if isinstance(origem, int):
        return origem
    texto = str(origem).strip()
    if texto.isdigit():
        return int(texto)
    return texto


def e_stream(origem) -> bool:
    return isinstance(origem, str) and "://" in origem


# ----------------------------------------------------------------------------
# fontes
# ----------------------------------------------------------------------------
class Fonte:
    """Contrato de captura: `iniciar`, `ler`, `parar`. `ler` devolve BGR uint8."""

    nome = "base"

    def __init__(self, cfg: ConfigCamera):
        self.cfg = cfg
        self.largura = cfg.largura
        self.altura = cfg.altura
        self.aberta = False

    def iniciar(self) -> None:  # pragma: no cover - abstrato
        raise NotImplementedError

    def ler(self) -> Optional[np.ndarray]:  # pragma: no cover - abstrato
        raise NotImplementedError

    def parar(self) -> None:  # pragma: no cover - abstrato
        raise NotImplementedError

    def __enter__(self):
        self.iniciar()
        return self

    def __exit__(self, *_):
        self.parar()


class FonteOpenCV(Fonte):
    """Captura por OpenCV — o caminho normal."""

    nome = "opencv"

    def __init__(self, cfg: ConfigCamera):
        super().__init__(cfg)
        self._cap = None

    def _backend_nativo(self) -> int:
        """O backend que menos atrapalha em cada sistema.

        No Windows o padrão (MSMF) demora segundos para abrir webcam e às vezes
        ignora a resolução pedida; DSHOW abre na hora. Para stream de rede, o
        FFMPEG é o backend certo em qualquer sistema.
        """
        if cv2 is None:
            return 0
        if e_stream(self.cfg.origem):
            return cv2.CAP_FFMPEG
        if SISTEMA == "Windows":
            return cv2.CAP_DSHOW
        if SISTEMA == "Linux":
            return cv2.CAP_V4L2
        if SISTEMA == "Darwin":
            return cv2.CAP_AVFOUNDATION
        return cv2.CAP_ANY

    def iniciar(self) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV não está instalado — use o motor ffmpeg.")
        origem = normalizar_origem(self.cfg.origem)
        if e_stream(origem):
            # TCP em vez de UDP: pacote de vídeo perdido em UDP vira macrobloco
            # verde na live, e o YouTube grava esse borrão para sempre.
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS",
                                  "rtsp_transport;tcp|max_delay;500000")
        cap = cv2.VideoCapture(origem, self._backend_nativo())
        if not cap.isOpened():
            cap = cv2.VideoCapture(origem)          # última tentativa, sem backend fixo
        if not cap.isOpened():
            raise RuntimeError(f"Não consegui abrir a câmera {origem!r}.")

        if not e_stream(origem):
            if self.cfg.formato in ("auto", "mjpeg"):
                # MJPEG é o que permite 720p/1080p a 30 fps num cabo USB 2.0;
                # sem isso a maioria das webcams cai para 5-10 fps em 1080p.
                try:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                except Exception:
                    pass
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.cfg.largura))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.cfg.altura))
            cap.set(cv2.CAP_PROP_FPS, float(self.cfg.fps))
        try:
            # buffer de 1: sempre o quadro mais novo. Buffer maior acumula atraso
            # que só cresce, e live atrasada não tem conserto depois.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._cap = cap
        self.largura = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or self.cfg.largura
        self.altura = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self.cfg.altura
        self.aberta = True

    def ler(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ok, quadro = self._cap.read()
        if not ok or quadro is None:
            return None
        return quadro

    def parar(self) -> None:
        self.aberta = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None


class FonteFFmpeg(Fonte):
    """Captura por ffmpeg, lendo BGR cru do pipe. Não depende de OpenCV."""

    nome = "ffmpeg"

    def __init__(self, cfg: ConfigCamera, ffmpeg: str = "ffmpeg"):
        super().__init__(cfg)
        self._proc: Optional[subprocess.Popen] = None
        self._ffmpeg = ffmpeg
        self._bytes_por_quadro = 0

    def comando(self) -> List[str]:
        origem = normalizar_origem(self.cfg.origem)
        cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error"]

        if e_stream(origem):
            cmd += ["-rtsp_transport", "tcp", "-i", str(origem)]
        elif isinstance(origem, str) and os.path.exists(origem):
            cmd += ["-re", "-i", origem]
        else:
            tam = f"{self.cfg.largura}x{self.cfg.altura}"
            if SISTEMA == "Windows":
                # No Windows o dshow quer o NOME do dispositivo, não o índice.
                # Um número puro não abre nada — daí `listar_cameras` devolver
                # também o nome, e o painel oferecer o nome.
                alvo = origem if isinstance(origem, str) else f"video={origem}"
                if not str(alvo).lower().startswith("video="):
                    alvo = f"video={alvo}"
                cmd += ["-f", "dshow", "-video_size", tam,
                        "-framerate", str(self.cfg.fps), "-i", str(alvo)]
            elif SISTEMA == "Darwin":
                cmd += ["-f", "avfoundation", "-video_size", tam,
                        "-framerate", str(self.cfg.fps), "-i", f"{origem}:none"]
            else:
                disp = origem if isinstance(origem, str) else f"/dev/video{origem}"
                cmd += ["-f", "v4l2", "-video_size", tam,
                        "-framerate", str(self.cfg.fps), "-i", str(disp)]

        cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24",
                "-vf", f"scale={self.cfg.largura}:{self.cfg.altura}",
                "-an", "-sn", "-"]
        return cmd

    def iniciar(self) -> None:
        if shutil.which(self._ffmpeg) is None:
            raise RuntimeError("ffmpeg não encontrado no PATH.")
        self.largura, self.altura = self.cfg.largura, self.cfg.altura
        self._bytes_por_quadro = self.largura * self.altura * 3
        self._proc = subprocess.Popen(
            self.comando(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=self._bytes_por_quadro * 2)
        self.aberta = True

    def ler(self) -> Optional[np.ndarray]:
        if self._proc is None or self._proc.stdout is None:
            return None
        cru = self._proc.stdout.read(self._bytes_por_quadro)
        if not cru or len(cru) < self._bytes_por_quadro:
            return None
        return np.frombuffer(cru, np.uint8).reshape(self.altura, self.largura, 3)

    def parar(self) -> None:
        self.aberta = False
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


class FonteSintetica(Fonte):
    """Uma "câmera" gerada por código: fundo em movimento e uma figura no meio.

    Serve para dois usos reais: rodar a suíte de testes numa máquina sem câmera,
    e o modo demonstração do painel, onde dá para ver os filtros funcionando
    antes de ligar a Lyra.
    """

    nome = "sintetica"

    def __init__(self, cfg: Optional[ConfigCamera] = None):
        super().__init__(cfg or ConfigCamera())
        self._n = 0

    def iniciar(self) -> None:
        self.largura, self.altura = self.cfg.largura, self.cfg.altura
        self._n = 0
        self.aberta = True

    def ler(self) -> Optional[np.ndarray]:
        if not self.aberta:
            return None
        alt, larg = self.altura, self.largura
        t = self._n * 0.05
        self._n += 1

        x = np.linspace(0, 6.28, larg, dtype=np.float32)[None, :]
        y = np.linspace(0, 6.28, alt, dtype=np.float32)[:, None]
        fundo = (np.sin(x + t) * 0.25 + np.cos(y * 1.3 - t) * 0.25 + 0.5)
        quadro = np.repeat(fundo[:, :, None], 3, axis=2)
        quadro *= np.array([1.05, 0.9, 0.8], np.float32)

        # uma "pessoa": elipse em tom de pele, para o embelezamento ter alvo
        yy = (np.arange(alt, dtype=np.float32)[:, None] - alt * 0.55) / (alt * 0.42)
        xx = (np.arange(larg, dtype=np.float32)[None, :] - larg * 0.5) / (larg * 0.22)
        dentro = np.clip(1.6 - np.sqrt(xx * xx + yy * yy) * 1.6, 0.0, 1.0)[:, :, None]
        pele = np.array([0.52, 0.66, 0.84], np.float32)
        quadro = quadro * (1 - dentro) + pele * dentro

        return np.clip(quadro * 255.0, 0, 255).astype(np.uint8)

    def parar(self) -> None:
        self.aberta = False


class FonteResiliente(Fonte):
    """Embrulha uma fonte e a reabre sozinha quando ela cai."""

    nome = "resiliente"

    def __init__(self, interna: Fonte, max_espera: float = 8.0):
        super().__init__(interna.cfg)
        self.interna = interna
        self.reconexoes = 0
        self.ultimo_erro = ""
        self._max_espera = float(max_espera)
        self._falhas = 0
        self._proxima_tentativa = 0.0

    @property
    def nome_interno(self) -> str:
        return self.interna.nome

    def iniciar(self) -> None:
        self.interna.iniciar()
        self.largura, self.altura = self.interna.largura, self.interna.altura
        self.aberta = True
        self._falhas = 0

    def ler(self) -> Optional[np.ndarray]:
        quadro = None
        try:
            quadro = self.interna.ler()
        except Exception as e:
            self.ultimo_erro = str(e)
        if quadro is not None:
            # o erro só é esquecido quando a câmera VOLTA A ENTREGAR imagem.
            # Limpar ao reabrir apagava o motivo da queda antes de alguém poder
            # lê-lo: reabrir dá certo mesmo quando a leitura continua falhando.
            self._falhas = 0
            self.ultimo_erro = ""
            return quadro

        # Espera crescente: reabrir em laço apertado uma câmera que foi
        # desconectada fisicamente só queima CPU e enche o log.
        self._falhas += 1
        agora = time.time()
        if agora < self._proxima_tentativa:
            return None
        espera = min(self._max_espera, 0.25 * (2 ** min(self._falhas, 5)))
        self._proxima_tentativa = agora + espera
        try:
            self.interna.parar()
            self.interna.iniciar()
            self.largura, self.altura = self.interna.largura, self.interna.altura
            self.reconexoes += 1
        except Exception as e:
            self.ultimo_erro = str(e)
        return None

    def parar(self) -> None:
        self.aberta = False
        self.interna.parar()


# ----------------------------------------------------------------------------
# descoberta e fábrica
# ----------------------------------------------------------------------------
def listar_cameras(maximo: int = 8) -> List[Dict]:
    """Sonda os índices e devolve os que abrem, com a resolução que entregam.

    Não existe jeito portátil de perguntar ao sistema "quais câmeras existem"
    pelo OpenCV: sondar e ver o que responde é o método. Cada índice que abre é
    testado com uma leitura de verdade, porque abrir e não entregar quadro é um
    estado comum de webcam já em uso por outro programa.
    """
    achadas: List[Dict] = []
    if cv2 is None:
        return achadas

    # Sondar índice que não existe faz o OpenCV despejar linha vermelha no
    # terminal — que é o resultado ESPERADO da sondagem, não um problema.
    with IMG.silenciar_opencv():
        return _sondar_indices(int(maximo))


def _sondar_indices(maximo: int) -> List[Dict]:
    achadas: List[Dict] = []
    for i in range(max(1, int(maximo))):
        cap = None
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if SISTEMA == "Windows" else cv2.CAP_ANY)
            if not cap.isOpened():
                continue
            ok, quadro = cap.read()
            if not ok or quadro is None:
                continue
            achadas.append({
                "indice": i,
                "largura": int(quadro.shape[1]),
                "altura": int(quadro.shape[0]),
                "descricao": f"Câmera {i} — {quadro.shape[1]}x{quadro.shape[0]}",
            })
        except Exception:
            continue
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    return achadas


def abrir_fonte(cfg: ConfigCamera, resiliente: bool = True) -> Fonte:
    """Escolhe o motor de captura e devolve a fonte já pronta para `iniciar`."""
    origem = normalizar_origem(cfg.origem)
    if isinstance(origem, str) and origem.lower() in ("sintetica", "demo", "teste"):
        base: Fonte = FonteSintetica(cfg)
    elif cfg.backend == "ffmpeg":
        base = FonteFFmpeg(cfg)
    elif cfg.backend == "opencv":
        base = FonteOpenCV(cfg)
    elif cv2 is not None:
        base = FonteOpenCV(cfg)
    else:
        base = FonteFFmpeg(cfg)
    return FonteResiliente(base) if resiliente else base
