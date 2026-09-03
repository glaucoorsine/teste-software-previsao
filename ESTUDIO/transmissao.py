# -*- coding: utf-8 -*-
"""
TRANSMISSÃO — do software para o YouTube, sem OBS no meio.

O QUE ELE PEDIU
───────────────
    "te pedi pro software nao ter a necessidade de passar pelo obs tambem"

O QUE "SEM OBS" SIGNIFICA AQUI, E O QUE NÃO SIGNIFICA
─────────────────────────────────────────────────────
Significa: o software abre a webcam, processa, e ENTREGA ao YouTube. Ele não
manda a imagem para outro programa capturar. Não tem câmera virtual, não tem
janela para o OBS "pegar", não tem cena para montar. Ele aperta TRANSMITIR
aqui e a live começa.

NÃO significa que eu escrevi um codificador H.264. Isso eu não fiz e não devo
fazer: comprimir vídeo em tempo real é trabalho para código que existe há
vinte anos, está otimizado em assembly, e usa o chip de vídeo da máquina dele.
Esse código é o `ffmpeg`, e ele é UM PROGRAMA, não um estúdio -- não tem
janela, não tem cena, não tem interface. É a mesma peça que o OBS usa por
baixo. A diferença é que aqui ela é chamada diretamente por este software, e
não por outro que ele teria de abrir, configurar e manter aberto.

Se ele preferir que não haja nem isso, a resposta honesta é que não dá em
Python com qualidade de live.

COMO OS DOIS FLUXOS CHEGAM NO FFMPEG AO MESMO TEMPO
───────────────────────────────────────────────────
Um processo tem uma entrada padrão só, e eu preciso mandar duas coisas: vídeo
cru e som cru. As saídas possíveis eram:

  · gravar em arquivo e o ffmpeg ler          -> atraso e disco à toa
  · fifo/named pipe                           -> não funciona igual no Windows
  · SOCKET TCP local                          -> funciona nos dois, é o que uso

Então: vídeo vai pela entrada padrão (`pipe:0`) e o som por um socket TCP em
127.0.0.1 numa porta que o sistema escolhe. O ffmpeg conecta nele como
cliente. Nada disso sai da máquina dele.

`-use_wallclock_as_timestamps 1` nas duas entradas: o relógio de parede é o
que sincroniza voz e imagem. Sem isso, um travamento de meio segundo na
câmera desloca a boca do som para sempre.

A CHAVE
───────
A chave nunca é impressa. `comando_visivel()` existe para a tela e para o log
e devolve a linha com a chave trocada por `•••`. O comando de verdade só é
montado dentro de `iniciar()` e não é guardado em lugar nenhum.
"""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent
JANELA = platform.system() == "Windows"

# Codificadores por ordem de preferência. Placa de vídeo primeiro: ela
# codifica sem tirar CPU do processamento de imagem, que é onde a CPU faz
# falta neste software.
PREFERENCIA = ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox",
               "libx264")

NOMES = {
    "h264_nvenc": "placa NVIDIA (NVENC)",
    "h264_qsv": "vídeo integrado Intel (QuickSync)",
    "h264_amf": "placa AMD (AMF)",
    "h264_videotoolbox": "Apple VideoToolbox",
    "libx264": "processador (libx264)",
}


def achar_ffmpeg() -> str:
    """Onde está o ffmpeg. Procura ao lado do software antes do sistema.

    Ao lado primeiro porque é onde ele vai colocar se baixar avulso, e porque
    uma versão que eu sei que funciona vale mais que a que estiver no PATH.
    """
    for nome in ("ffmpeg.exe", "ffmpeg"):
        p = RAIZ / nome
        if p.is_file():
            return str(p)
        p = RAIZ / "ffmpeg" / "bin" / nome
        if p.is_file():
            return str(p)
    achado = shutil.which("ffmpeg")
    if achado:
        return achado
    if JANELA:
        for base in (r"C:\ffmpeg\bin\ffmpeg.exe",
                     r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"):
            if Path(base).is_file():
                return base
    return ""


def encoders_disponiveis(ffmpeg: str = "") -> List[str]:
    """Quais codificadores H.264 esta máquina tem. Listar é barato, errar não."""
    exe = ffmpeg or achar_ffmpeg()
    if not exe:
        return []
    try:
        p = subprocess.run([exe, "-hide_banner", "-encoders"],
                           capture_output=True, text=True, timeout=20,
                           errors="replace")
        texto = (p.stdout or "") + (p.stderr or "")
    except Exception:
        return []
    return [e for e in PREFERENCIA if e in texto]


def escolher_encoder(preferido: str, disponiveis: List[str]) -> Tuple[str, str]:
    """Devolve (encoder, motivo). O motivo vai para a tela."""
    if not disponiveis:
        return "libx264", "não consegui listar os codificadores; tentando libx264"
    if preferido and preferido != "auto":
        if preferido in disponiveis:
            return preferido, f"escolhido por você: {NOMES.get(preferido, preferido)}"
        return (disponiveis[0],
                f"'{preferido}' não existe nesta máquina; usei "
                f"{NOMES.get(disponiveis[0], disponiveis[0])}")
    return disponiveis[0], f"automático: {NOMES.get(disponiveis[0], disponiveis[0])}"


def opcoes_qualidade(encoder: str, kbps: int, fps: int) -> List[str]:
    """Os parâmetros de cada codificador, com o que o YouTube exige.

    O YouTube pede quadro-chave a cada 2 segundos. Sem isso o espectador que
    entra no meio espera até o próximo, e o YouTube reclama de "configuração
    de codificação" na página da live. `-g = 2*fps` é essa regra.

    `zerolatency` no libx264 desliga o buffer de quadros futuros. Custa um
    pouco de qualidade por bit e devolve um segundo de atraso -- numa live com
    chat, um segundo é muito.
    """
    g = str(max(2, int(fps) * 2))
    taxa = f"{int(kbps)}k"
    comum = ["-b:v", taxa, "-maxrate", taxa, "-bufsize", f"{int(kbps) * 2}k",
             "-g", g, "-keyint_min", g, "-pix_fmt", "yuv420p"]
    if encoder == "libx264":
        return ["-c:v", "libx264", "-preset", "veryfast", "-tune",
                "zerolatency", "-profile:v", "high"] + comum
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "ll",
                "-rc", "cbr", "-profile:v", "high"] + comum
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "veryfast",
                "-profile:v", "high"] + comum
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-usage", "lowlatency",
                "-profile:v", "high"] + comum
    return ["-c:v", encoder] + comum


def montar_comando(ffmpeg: str, largura: int, altura: int, fps: int,
                   porta_audio: int, destino: str, encoder: str = "libx264",
                   kbps_video: int = 4500, kbps_audio: int = 160,
                   taxa_audio: int = 48000, canais_audio: int = 1,
                   gravar_em: str = "") -> List[str]:
    """A linha de comando inteira. Separada para o teste poder conferi-la.

    Isto é função pura de propósito: transmitir de verdade exige internet,
    chave e webcam, mas ERRAR A LINHA DE COMANDO é o defeito mais provável e
    o mais caro (ele descobre no ar). O teste confere a linha sem transmitir
    nada.
    """
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "warning", "-nostdin",
           # vídeo cru pela entrada padrão
           "-use_wallclock_as_timestamps", "1",
           "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{int(largura)}x{int(altura)}", "-r", str(int(fps)),
           "-i", "pipe:0",
           # som cru pelo socket local
           "-use_wallclock_as_timestamps", "1",
           "-f", "s16le", "-ar", str(int(taxa_audio)),
           "-ac", str(int(canais_audio)),
           "-i", f"tcp://127.0.0.1:{int(porta_audio)}",
           "-map", "0:v:0", "-map", "1:a:0"]
    cmd += opcoes_qualidade(encoder, kbps_video, fps)
    cmd += ["-c:a", "aac", "-b:a", f"{int(kbps_audio)}k", "-ar", "48000",
            "-ac", "2"]          # o YouTube quer estéreo; mono vira duplicado

    if gravar_em:
        # A CÓPIA LOCAL, E POR QUE ELA VEM ANTES DA REDE NA LISTA
        # ──────────────────────────────────────────────────────
        # Se a internet dele cair no meio, a live acaba e o conteúdo some. O
        # arquivo local não depende da rede e sobrevive. Custa disco e quase
        # nada de CPU, porque é o MESMO vídeo já codificado sendo escrito
        # duas vezes.
        cmd += ["-f", "flv", str(destino), "-c", "copy", "-f", "mp4",
                "-movflags", "+faststart", str(gravar_em)]
    else:
        cmd += ["-f", "flv", str(destino)]
    return cmd


def comando_visivel(cmd: List[str]) -> str:
    """O comando para a tela e para o log, SEM a chave.

    A chave é o último trecho do endereço rtmp. Trocar por `•••` aqui é o que
    permite mostrar o comando inteiro para ele conferir sem que uma gravação
    de tela entregue a live dele para qualquer um.
    """
    partes = []
    for a in cmd:
        s = str(a)
        if s.startswith("rtmp://"):
            base, _, chave = s.rpartition("/")
            fim = chave[-4:] if len(chave) > 4 else ""
            s = f"{base}/•••{fim}"
        partes.append(s)
    return " ".join(partes)


@dataclass
class Estado:
    rodando: bool = False
    encoder: str = ""
    motivo_encoder: str = ""
    destino_visivel: str = ""
    erro: str = ""
    ultimas_linhas: Deque[str] = field(default_factory=lambda: deque(maxlen=25))
    quadros_enviados: int = 0
    quadros_perdidos: int = 0
    inicio: float = 0.0

    @property
    def segundos_no_ar(self) -> float:
        return (time.time() - self.inicio) if self.rodando and self.inicio else 0.0


class Transmissao:
    """Um processo ffmpeg vivo, com vídeo pela entrada padrão e som por socket."""

    def __init__(self) -> None:
        self.estado = Estado()
        self.ffmpeg = achar_ffmpeg()
        self._proc: Optional[subprocess.Popen] = None
        self._srv: Optional[socket.socket] = None
        self._sock_audio: Optional[socket.socket] = None
        self._aceitar: Optional[threading.Thread] = None
        self._ler: Optional[threading.Thread] = None
        self._trava = threading.Lock()

    # ── ciclo de vida ─────────────────────────────────────────────────────
    def iniciar(self, destino: str, largura: int, altura: int, fps: int,
                encoder: str = "auto", kbps_video: int = 4500,
                kbps_audio: int = 160, canais_audio: int = 1,
                gravar_em: str = "") -> Tuple[bool, str]:
        if self.estado.rodando:
            return False, "já está transmitindo"
        if not self.ffmpeg:
            return False, ("ffmpeg não encontrado. Coloque o ffmpeg.exe na "
                           "pasta do software ou instale-o — o LEIA_PRIMEIRO "
                           "explica em três linhas.")
        if not destino or not str(destino).startswith(("rtmp://", "rtmps://")):
            return False, "endereço de transmissão inválido"

        esc, motivo = escolher_encoder(encoder, encoders_disponiveis(self.ffmpeg))

        # porta efêmera: o sistema escolhe uma livre, ninguém precisa configurar
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind(("127.0.0.1", 0))
        self._srv.listen(1)
        self._srv.settimeout(15.0)
        porta = self._srv.getsockname()[1]

        cmd = montar_comando(self.ffmpeg, largura, altura, fps, porta, destino,
                             esc, kbps_video, kbps_audio, 48000, canais_audio,
                             gravar_em)
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=(subprocess.CREATE_NO_WINDOW if JANELA else 0))
        except Exception as e:
            self._fechar_socket()
            return False, f"não consegui iniciar o ffmpeg: {e}"

        self.estado = Estado(rodando=True, encoder=esc, motivo_encoder=motivo,
                             destino_visivel=comando_visivel([destino]),
                             inicio=time.time())
        self._aceitar = threading.Thread(target=self._aceitar_audio, daemon=True,
                                         name="tx-audio")
        self._aceitar.start()
        self._ler = threading.Thread(target=self._ler_erros, daemon=True,
                                     name="tx-log")
        self._ler.start()
        return True, f"transmitindo — {motivo}"

    def _aceitar_audio(self) -> None:
        try:
            s, _ = self._srv.accept()
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock_audio = s
        except Exception as e:
            self.estado.erro = f"o ffmpeg não conectou no canal de áudio: {e}"

    def _ler_erros(self) -> None:
        """Guarda o que o ffmpeg reclama. É a única forma de saber o motivo.

        Sem isto, "a live não subiu" chega até ele como uma tela parada. Com
        isto, chega como "Server returned 403 Forbidden" e ele troca a chave.
        """
        p = self._proc
        if p is None or p.stderr is None:
            return
        for linha in iter(p.stderr.readline, b""):
            try:
                txt = linha.decode("utf-8", "replace").strip()
            except Exception:
                continue
            if not txt:
                continue
            self.estado.ultimas_linhas.append(txt)
            baixo = txt.lower()
            if any(k in baixo for k in ("error", "failed", "invalid",
                                        "forbidden", "unable", "refused",
                                        "connection reset")):
                self.estado.erro = txt

    # ── envio ─────────────────────────────────────────────────────────────
    def enviar_video(self, quadro) -> bool:
        """Um quadro BGR. Devolve False quando a transmissão morreu."""
        p = self._proc
        if not self.estado.rodando or p is None or p.stdin is None:
            return False
        try:
            p.stdin.write(quadro.tobytes())
            self.estado.quadros_enviados += 1
            return True
        except (BrokenPipeError, ValueError, OSError):
            self.estado.quadros_perdidos += 1
            self.estado.rodando = False
            if not self.estado.erro:
                self.estado.erro = ("o ffmpeg fechou a entrada de vídeo — veja "
                                    "as últimas linhas dele")
            return False

    def enviar_audio(self, pcm: bytes) -> bool:
        s = self._sock_audio
        if not self.estado.rodando or s is None:
            return False
        try:
            s.sendall(pcm)
            return True
        except OSError:
            self._sock_audio = None
            return False

    def parar(self, esperar: float = 6.0) -> None:
        """Fecha na ordem certa: entrada primeiro, e só então o processo.

        Fechar a entrada faz o ffmpeg terminar o arquivo e encerrar a conexão
        com o YouTube direito. Matar o processo antes disso deixa a gravação
        local sem o índice -- um .mp4 que não abre. Por isso o `terminate` só
        vem depois da espera.
        """
        with self._trava:
            self.estado.rodando = False
            p = self._proc
            if p is not None:
                try:
                    if p.stdin:
                        p.stdin.close()
                except Exception:
                    pass
                if self._sock_audio is not None:
                    try:
                        self._sock_audio.close()
                    except Exception:
                        pass
                    self._sock_audio = None
                try:
                    p.wait(timeout=esperar)
                except Exception:
                    try:
                        p.terminate()
                        p.wait(timeout=2.0)
                    except Exception:
                        try:
                            p.kill()
                        except Exception:
                            pass
                self._proc = None
            self._fechar_socket()

    def _fechar_socket(self) -> None:
        if self._srv is not None:
            try:
                self._srv.close()
            except Exception:
                pass
            self._srv = None

    @property
    def viva(self) -> bool:
        p = self._proc
        return bool(self.estado.rodando and p is not None and p.poll() is None)
