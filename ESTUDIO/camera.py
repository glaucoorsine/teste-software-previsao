# -*- coding: utf-8 -*-
"""
CÂMERA — abrir a Hollyland Lyra e manter o quadro mais novo sempre à mão.

O DETALHE QUE DECIDE SE DÁ 30 QUADROS OU 5
──────────────────────────────────────────
Uma webcam USB pode entregar quadro de dois jeitos: cru (YUY2) ou comprimido
(MJPG). A 1280x720 e 30 quadros, o cru precisa de 442 Mbit/s. O USB 2.0 dá
480 Mbit/s teóricos e uns 300 na prática. Não cabe -- e a câmera não avisa:
ela silenciosamente entrega 10, 7, 5 quadros por segundo.

É a explicação de quase todo "minha webcam é ruim" que existe. Por isso eu
peço MJPG antes de pedir a resolução, e confiro depois se ela obedeceu.

E POR QUE A LEITURA FICA NUMA THREAD SÓ DELA
────────────────────────────────────────────
`cap.read()` bloqueia até o próximo quadro chegar. Se a leitura estivesse
junto do processamento, cada milissegundo gasto processando seria um
milissegundo esperando depois, e o buffer interno da câmera encheria de
quadro velho -- a imagem "atrasa" progressivamente, defeito clássico.

A thread lê sem parar e guarda só o ÚLTIMO. Quem processa pega o mais novo e
descarta o resto. Numa live, quadro velho não serve para nada.
"""
from __future__ import annotations

import platform
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

JANELA = platform.system() == "Windows"


@dataclass
class EstadoCamera:
    aberta: bool = False
    largura: int = 0
    altura: int = 0
    fps_pedido: int = 0
    fps_real: float = 0.0
    formato: str = ""
    lidos: int = 0
    descartados: int = 0     # quadros que chegaram e ninguém buscou
    falhas: int = 0
    aviso: str = ""


class Camera:
    def __init__(self, indice: int = 0, largura: int = 1280, altura: int = 720,
                 fps: int = 30):
        self.indice = int(indice)
        self.largura = int(largura)
        self.altura = int(altura)
        self.fps = int(fps)
        self.estado = EstadoCamera(fps_pedido=self.fps)
        self._cap = None
        self._quadro: Optional[np.ndarray] = None
        self._novo = False
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._marcas: list = []

    def _backend(self) -> int:
        if not TEM_CV:
            return 0
        if JANELA:
            # DirectShow aceita MJPG e troca de resolução melhor que o MSMF,
            # que é o padrão do OpenCV no Windows e engasga com webcam USB
            return getattr(cv2, "CAP_DSHOW", 0)
        return getattr(cv2, "CAP_V4L2", 0)

    def abrir(self) -> Tuple[bool, str]:
        if not TEM_CV:
            return False, "OpenCV não instalado — rode 0_INSTALAR.bat"
        try:
            cap = cv2.VideoCapture(self.indice, self._backend())
            if not cap or not cap.isOpened():
                cap = cv2.VideoCapture(self.indice)      # sem backend fixo
            if not cap or not cap.isOpened():
                return False, f"não consegui abrir a câmera {self.indice}"

            # MJPG ANTES da resolução: em várias câmeras trocar o formato
            # depois reinicia a negociação e desfaz a resolução escolhida
            try:
                cap.set(cv2.CAP_PROP_FOURCC,
                        cv2.VideoWriter_fourcc(*"MJPG"))
            except Exception:
                pass
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.largura)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.altura)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
            try:
                # buffer de 1: sempre o quadro mais novo. Nem todo driver
                # obedece, e por isso a thread também descarta.
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            ok, quadro = cap.read()
            if not ok or quadro is None:
                cap.release()
                return False, ("a câmera abriu mas não entregou quadro — "
                               "outro programa pode estar usando ela")
        except Exception as e:
            return False, f"erro ao abrir a câmera: {e}"

        self._cap = cap
        e = self.estado
        e.aberta = True
        e.altura, e.largura = quadro.shape[:2]
        try:
            cod = int(cap.get(cv2.CAP_PROP_FOURCC))
            e.formato = "".join(chr((cod >> (8 * i)) & 0xFF) for i in range(4)) \
                .strip() or "?"
        except Exception:
            e.formato = "?"
        if e.formato.upper() not in ("MJPG", "H264", "MJPB"):
            e.aviso = (f"a câmera ficou em {e.formato}, não MJPG — em USB 2.0 "
                       f"isso costuma travar a taxa de quadros")
        if (e.largura, e.altura) != (self.largura, self.altura):
            e.aviso = (f"{e.aviso + '; ' if e.aviso else ''}pedi "
                       f"{self.largura}x{self.altura} e ela deu "
                       f"{e.largura}x{e.altura}")

        with self._trava:
            self._quadro, self._novo = quadro, True
        self._parar.clear()
        self._thread = threading.Thread(target=self._ler, daemon=True,
                                        name="camera")
        self._thread.start()
        return True, (f"câmera {self.indice} aberta: {e.largura}x{e.altura} "
                      f"{e.formato}")

    def _ler(self) -> None:
        while not self._parar.is_set():
            cap = self._cap
            if cap is None:
                break
            try:
                ok, quadro = cap.read()
            except Exception:
                ok, quadro = False, None
            if not ok or quadro is None:
                self.estado.falhas += 1
                if self.estado.falhas > 60:
                    self.estado.aviso = "a câmera parou de responder"
                    break
                time.sleep(0.02)
                continue
            self.estado.falhas = 0
            agora = time.perf_counter()
            self._marcas.append(agora)
            if len(self._marcas) > 30:
                self._marcas.pop(0)
                d = self._marcas[-1] - self._marcas[0]
                if d > 0:
                    self.estado.fps_real = (len(self._marcas) - 1) / d
            with self._trava:
                if self._novo:
                    self.estado.descartados += 1
                self._quadro, self._novo = quadro, True
                self.estado.lidos += 1

    def pegar(self) -> Optional[np.ndarray]:
        """O quadro mais novo, ou None se não chegou nenhum desde a última vez."""
        with self._trava:
            if not self._novo or self._quadro is None:
                return None
            self._novo = False
            return self._quadro

    def fechar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self.estado.aberta = False
