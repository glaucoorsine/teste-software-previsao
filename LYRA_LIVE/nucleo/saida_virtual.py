# -*- coding: utf-8 -*-
"""
A câmera virtual: a Lyra filtrada aparecendo como um dispositivo do sistema.

PARA QUE SERVE
--------------
Com isto ligado, "Lyra Live" aparece na lista de câmeras de qualquer programa —
inclusive na opção "Webcam" do YouTube Studio no navegador, e também no Meet, no
Zoom e no Teams. O que sai por ali é a Lyra COM os filtros, o embelezamento e o
fundo desfocado já aplicados.

É o segundo caminho para o YouTube reconhecer este software; o primeiro é o
RTMP. Os dois podem ficar ligados ao mesmo tempo.

O QUE PRECISA ESTAR INSTALADO
-----------------------------
O dispositivo virtual é do sistema operacional, não deste programa:

* Windows — o driver que vem com o OBS Studio. Basta ter o OBS instalado (não
  precisa estar aberto); ele registra a "OBS Virtual Camera" no sistema.
* Linux — o módulo v4l2loopback.
* macOS — o driver do OBS também.

Sem isso, `pyvirtualcam` não tem onde publicar. Aqui isso não é um erro fatal:
a mensagem explica o que instalar e a transmissão RTMP segue funcionando.
"""
from __future__ import annotations

import platform
from typing import Optional

import numpy as np


class CameraVirtual:
    """Publica quadros num dispositivo de câmera do sistema."""

    def __init__(self, largura: int = 1280, altura: int = 720, fps: int = 30,
                 nome: str = "Lyra Live"):
        self.largura = int(largura)
        self.altura = int(altura)
        self.fps = int(fps)
        self.nome = nome
        self._cam = None
        self.dispositivo = ""
        self.ativa = False

    @staticmethod
    def instrucao_de_instalacao() -> str:
        sistema = platform.system()
        if sistema == "Windows":
            return ("Para a câmera virtual, instale o OBS Studio — ele registra o "
                    "dispositivo no Windows. Não precisa abrir o OBS depois.")
        if sistema == "Darwin":
            return "Para a câmera virtual no macOS, instale o OBS Studio."
        return ("Para a câmera virtual no Linux, carregue o v4l2loopback:\n"
                "  sudo modprobe v4l2loopback devices=1 card_label='Lyra Live' "
                "exclusive_caps=1")

    def iniciar(self) -> None:
        try:
            import pyvirtualcam
        except ImportError as e:
            raise RuntimeError(
                "O pacote pyvirtualcam não está instalado (pip install pyvirtualcam).\n"
                + self.instrucao_de_instalacao()) from e
        try:
            # BGR direto: sem isto o pyvirtualcam receberia RGB e a live sairia
            # com a pessoa azul — o erro clássico de quem troca a ordem de canal
            self._cam = pyvirtualcam.Camera(width=self.largura, height=self.altura,
                                            fps=self.fps, fmt=pyvirtualcam.PixelFormat.BGR,
                                            print_fps=False)
        except Exception as e:
            raise RuntimeError(f"Não consegui abrir a câmera virtual: {e}\n"
                               + self.instrucao_de_instalacao()) from e
        self.dispositivo = getattr(self._cam, "device", "") or ""
        self.ativa = True

    def escrever(self, quadro: np.ndarray) -> bool:
        if not self.ativa or self._cam is None:
            return False
        try:
            if quadro.shape[0] != self.altura or quadro.shape[1] != self.largura:
                return False
            self._cam.send(np.ascontiguousarray(quadro))
            return True
        except Exception:
            return False

    def parar(self) -> None:
        self.ativa = False
        cam, self._cam = self._cam, None
        if cam is not None:
            try:
                cam.close()
            except Exception:
                pass


def abrir_camera_virtual(largura: int, altura: int, fps: int) -> tuple[Optional[CameraVirtual], str]:
    """Tenta abrir e devolve (câmera ou None, mensagem para a tela).

    Falhar aqui não pode derrubar a live: quem transmite por RTMP não precisa da
    câmera virtual, e quem precisa dela merece uma frase que diga o que instalar.
    """
    cam = CameraVirtual(largura, altura, fps)
    try:
        cam.iniciar()
        return cam, f"Câmera virtual ativa: {cam.dispositivo or cam.nome}"
    except Exception as e:
        return None, str(e)
