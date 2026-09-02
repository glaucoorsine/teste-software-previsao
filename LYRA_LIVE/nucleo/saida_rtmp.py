# -*- coding: utf-8 -*-
"""
O encoder: empurra a Lyra já filtrada para o YouTube por RTMP.

COMO A LIVE COMEÇA
------------------
O software abre um ffmpeg que lê quadros BGR crus pela entrada padrão, codifica
em H.264 + AAC e publica em `rtmp://a.rtmp.youtube.com/live2/SUA-CHAVE`. Do
lado do YouTube Studio aparece "recebendo dados" e o botão de transmitir
libera. É assim que todo software de live funciona, OBS incluído.

TRÊS DECISÕES QUE VALEM EXPLICAÇÃO
----------------------------------
`-progress pipe:1`: o ffmpeg escreve estatística estruturada na saída padrão,
separada do stderr. Sem isso a única forma de saber a taxa real seria raspar
texto de log — que muda de formato entre versões. Com isso, a IA supervisora lê
velocidade, taxa e quadros perdidos direto da fonte.

FAIXA DE ÁUDIO SEMPRE: o YouTube recusa transmissão sem áudio. Quando não há
microfone escolhido, o encoder gera silêncio com `anullsrc`. É melhor uma live
muda que uma live recusada, e a mensagem no painel diz qual dos dois está
acontecendo.

`-bufsize` igual ao dobro da taxa: dá ao codificador margem para gastar bits num
movimento brusco sem estourar o teto. Buffer curto demais faz a imagem
"respirar" (piorar e melhorar em ciclo) toda vez que a cena se mexe.

A CHAVE NUNCA APARECE
---------------------
`comando_para_log()` devolve a linha de comando com a chave trocada por
asteriscos. Quem depurar um problema vai colar essa linha em algum lugar, e a
chave de transmissão é a senha da live.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List, Optional

import numpy as np

from . import youtube as YT
from .metricas import analisar_progresso

_cache_encoders: Optional[List[str]] = None


def ffmpeg_existe(binario: str = "ffmpeg") -> bool:
    return shutil.which(binario) is not None


def encoders_disponiveis(binario: str = "ffmpeg") -> List[str]:
    """Quais codificadores H.264 este ffmpeg tem. Consultado uma vez só."""
    global _cache_encoders
    if _cache_encoders is not None:
        return _cache_encoders
    achados: List[str] = []
    try:
        saida = subprocess.run([binario, "-hide_banner", "-encoders"],
                               capture_output=True, text=True, timeout=15)
        texto = (saida.stdout or "") + (saida.stderr or "")
        for nome in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox", "libx264"):
            if nome in texto:
                achados.append(nome)
    except Exception:
        achados = ["libx264"]
    _cache_encoders = achados or ["libx264"]
    return _cache_encoders


def escolher_encoder(preferencia: str = "auto", binario: str = "ffmpeg") -> str:
    """Placa de vídeo codifica de graça; o processador cobra caro.

    Em 1080p, o libx264 come um núcleo inteiro e é a causa mais comum de live
    que engasga em máquina modesta. Se houver NVENC, QuickSync ou AMF, usa.
    """
    disponiveis = encoders_disponiveis(binario)
    mapa = {"nvidia": "h264_nvenc", "intel": "h264_qsv", "amd": "h264_amf",
            "apple": "h264_videotoolbox", "cpu": "libx264"}
    if preferencia in mapa:
        alvo = mapa[preferencia]
        return alvo if alvo in disponiveis else "libx264"
    for nome in ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox", "libx264"):
        if nome in disponiveis:
            return nome
    return "libx264"


@dataclass
class ConfigSaida:
    chave: str = ""
    largura: int = 1280
    altura: int = 720
    fps: int = 30
    video_kbps: int = 0                # 0 = usa a recomendação do YouTube
    audio_kbps: int = 128
    audio_dispositivo: str = ""        # vazio = silêncio gerado
    audio_backend: str = "auto"        # auto | dshow | pulse | alsa | avfoundation
    codificador: str = "auto"          # auto | cpu | nvidia | intel | amd | apple
    backup: bool = False
    ingestao: str = ""                 # vazio = ingestão padrão do YouTube
    ffmpeg: str = "ffmpeg"

    def como_dicionario(self) -> Dict:
        d = asdict(self)
        d.pop("chave", None)           # a chave não entra em arquivo de perfil por aqui
        return d

    @staticmethod
    def de_dicionario(d: Optional[Dict]) -> "ConfigSaida":
        base = ConfigSaida()
        for k, v in dict(d or {}).items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base


def entrada_de_audio(cfg: ConfigSaida) -> List[str]:
    """Os argumentos de entrada de áudio — microfone real ou silêncio."""
    if not cfg.audio_dispositivo:
        return ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    backend = cfg.audio_backend
    if backend == "auto":
        import platform
        sistema = platform.system()
        backend = {"Windows": "dshow", "Darwin": "avfoundation"}.get(sistema, "pulse")

    # thread_queue_size grande: sem isso o ffmpeg descarta amostra de áudio
    # quando o vídeo atrasa um instante, e o áudio dessincroniza para sempre
    comum = ["-thread_queue_size", "1024"]
    if backend == "dshow":
        alvo = cfg.audio_dispositivo
        if not alvo.lower().startswith("audio="):
            alvo = f"audio={alvo}"
        return comum + ["-f", "dshow", "-i", alvo]
    if backend == "avfoundation":
        return comum + ["-f", "avfoundation", "-i", f":{cfg.audio_dispositivo}"]
    if backend == "alsa":
        return comum + ["-f", "alsa", "-i", cfg.audio_dispositivo]
    return comum + ["-f", "pulse", "-i", cfg.audio_dispositivo]


def montar_comando(cfg: ConfigSaida) -> List[str]:
    """A linha de comando completa do ffmpeg. Função pura — dá para testar."""
    taxas = YT.preset(cfg.altura, cfg.fps)
    kbps = int(cfg.video_kbps) if cfg.video_kbps else taxas["video_kbps"]
    gop = max(1, int(cfg.fps) * taxas["intervalo_quadro_chave"])
    codec = escolher_encoder(cfg.codificador, cfg.ffmpeg)

    cmd = [cfg.ffmpeg, "-hide_banner", "-loglevel", "warning",
           "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{cfg.largura}x{cfg.altura}", "-r", str(cfg.fps),
           "-thread_queue_size", "512", "-i", "pipe:0"]
    cmd += entrada_de_audio(cfg)

    cmd += ["-c:v", codec, "-pix_fmt", "yuv420p",
            "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k", "-bufsize", f"{kbps * 2}k",
            # quadro-chave a cada 2 s e nenhum extra por corte de cena: o
            # YouTube exige cadência fixa, e -sc_threshold 0 garante isso
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0"]
    if codec == "libx264":
        cmd += ["-preset", "veryfast", "-profile:v", "high"]
    elif codec == "h264_nvenc":
        cmd += ["-preset", "p4", "-rc", "cbr", "-profile:v", "high"]
    elif codec == "h264_qsv":
        cmd += ["-preset", "veryfast"]

    cmd += ["-c:a", "aac", "-b:a", f"{int(cfg.audio_kbps)}k", "-ar", "44100", "-ac", "2",
            # anullsrc gera silêncio para sempre; -shortest faz o ffmpeg encerrar
            # quando o cano de vídeo fechar, em vez de seguir transmitindo mudo
            "-shortest", "-max_muxing_queue_size", "1024",
            "-f", "flv", YT.montar_url(cfg.chave, cfg.backup, cfg.ingestao or None),
            "-progress", "pipe:1", "-nostdin"]
    return cmd


def comando_para_log(cfg: ConfigSaida) -> str:
    """A mesma linha, com a chave mascarada. Use SEMPRE esta para mostrar."""
    return YT.mascarar_chave(" ".join(montar_comando(cfg)))


class EncoderRTMP:
    """O processo de transmissão, com reinício automático.

    Se o ffmpeg morrer no meio da live (queda de rede, servidor derrubando a
    conexão), o software reabre sozinho com espera crescente em vez de encerrar
    a transmissão. Cada reinício é contado e vai para as métricas.
    """

    def __init__(self, cfg: ConfigSaida,
                 ao_medir: Optional[Callable[[Dict], None]] = None,
                 ao_avisar: Optional[Callable[[str], None]] = None):
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None
        self._ao_medir = ao_medir or (lambda _: None)
        self._ao_avisar = ao_avisar or (lambda _: None)
        self._threads: List[threading.Thread] = []
        self._parando = threading.Event()
        self.reinicios = 0
        self.ultimo_erro = ""
        self._falhas = 0
        self._proxima_tentativa = 0.0
        self.bytes_escritos = 0

    # -- ciclo de vida ------------------------------------------------------
    def iniciar(self) -> None:
        if not ffmpeg_existe(self.cfg.ffmpeg):
            raise RuntimeError(
                "ffmpeg não encontrado. Ele é obrigatório para transmitir: "
                "instale e deixe no PATH (no Windows, winget install Gyan.FFmpeg).")
        vale, motivo = YT.validar_chave(self.cfg.chave)
        if not vale:
            raise RuntimeError(motivo)
        self._parando.clear()
        self._abrir()

    def _abrir(self) -> None:
        self._proc = subprocess.Popen(
            montar_comando(self.cfg), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self._threads = [
            threading.Thread(target=self._ler_progresso, args=(self._proc,), daemon=True),
            threading.Thread(target=self._ler_erros, args=(self._proc,), daemon=True),
        ]
        for t in self._threads:
            t.start()

    def _ler_progresso(self, proc: subprocess.Popen) -> None:
        """Consome o `-progress` do ffmpeg. Precisa rodar SEMPRE.

        Não é só para ter métrica: se ninguém ler este cano, ele enche, e o
        ffmpeg trava esperando espaço para escrever. A live congelaria.
        """
        try:
            for linha in iter(proc.stdout.readline, b""):
                if self._parando.is_set():
                    break
                dados = analisar_progresso(linha.decode("utf-8", "ignore"))
                if dados:
                    self._ao_medir(dados)
        except Exception:
            pass

    def _ler_erros(self, proc: subprocess.Popen) -> None:
        try:
            for linha in iter(proc.stderr.readline, b""):
                if self._parando.is_set():
                    break
                texto = YT.mascarar_chave(linha.decode("utf-8", "ignore").strip())
                if texto:
                    self.ultimo_erro = texto
                    self._ao_avisar(texto)
        except Exception:
            pass

    def vivo(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def escrever(self, quadro: np.ndarray) -> bool:
        """Manda um quadro. Devolve False quando o quadro não foi transmitido."""
        if self._parando.is_set():
            return False
        if not self.vivo():
            self._tentar_reabrir()
            return False
        try:
            dados = quadro.tobytes() if quadro.flags["C_CONTIGUOUS"] else \
                np.ascontiguousarray(quadro).tobytes()
            self._proc.stdin.write(dados)
            self.bytes_escritos += len(dados)
            return True
        except (BrokenPipeError, OSError, ValueError) as e:
            # cano quebrado é o ffmpeg tendo morrido: o motivo real está no
            # stderr que a outra thread já capturou
            self.ultimo_erro = self.ultimo_erro or str(e)
            self._tentar_reabrir()
            return False

    def _tentar_reabrir(self) -> None:
        agora = time.time()
        if agora < self._proxima_tentativa:
            return
        self._falhas += 1
        self._proxima_tentativa = agora + min(10.0, 0.5 * (2 ** min(self._falhas, 4)))
        conselho = YT.diagnostico_conexao(self.ultimo_erro)
        self._ao_avisar(conselho or f"Reiniciando a transmissão ({self._falhas}ª tentativa).")
        try:
            self._encerrar_processo()
            self._abrir()
            self.reinicios += 1
        except Exception as e:
            self.ultimo_erro = str(e)

    def _encerrar_processo(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        for fechar in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if fechar:
                    fechar.close()
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def parar(self) -> None:
        self._parando.set()
        self._encerrar_processo()
