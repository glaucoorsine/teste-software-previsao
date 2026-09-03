# -*- coding: utf-8 -*-
"""
FUNDO — o desfoque de fundo que ele pediu depois.

    "coloque desfoque de fundo tambem"

O QUE SEPARA UM DESFOQUE BOM DE UM RUIM
───────────────────────────────────────
Não é o borrão. Borrar é fácil e barato. O que decide é a MÁSCARA -- saber
onde ele termina e o fundo começa. Máscara ruim aparece de três jeitos, e
todos são piores que não ter desfoque nenhum:

  · o ombro entra e sai do foco quando ele se mexe (máscara sem memória)
  · fica um halo borrado em volta da cabeça (máscara larga demais)
  · a orelha e o cabelo somem (máscara apertada demais)

Contra o primeiro: média no tempo, a máscara de hoje puxada pela de ontem.
Contra os outros dois: a borda é suavizada e o recorte é levemente FOLGADO,
porque errar para dentro (deixar um fio de fundo nítido junto do cabelo) é
menos visível que errar para fora (comer a orelha).

TRÊS NÍVEIS, COMO NO DETECTOR DE ROSTO
──────────────────────────────────────
 1. mediapipe — segmentação de pessoa de verdade, por pixel. Se ele instalar
    (`pip install mediapipe`), é o melhor e roda em ~5 ms.
 2. um .onnx de segmentação ao lado do software, lido pelo `cv2.dnn`.
 3. GEOMÉTRICO, sempre disponível: elipse na cabeça a partir da caixa do
    rosto + tronco que desce dos ombros, reforçado pela máscara de pele.

O nível 3 não é segmentação de verdade e eu não vou dizer que é. Ele funciona
para o caso dele -- uma pessoa sentada de frente para a webcam, que é a live
que ele vai fazer -- e erra se alguém passar atrás ou se ele levantar o braço.
A tela mostra qual nível está em uso, para ele saber o que está olhando.

O BORRÃO É EM 1/4 E DEVOLVIDO
─────────────────────────────
Desfoque de fundo grande em resolução cheia é caro e não precisa: o resultado
é liso por definição. Reduzo para 1/4, borro lá, devolvo. Fica igual e custa
16 vezes menos. E somo um pouco de brilho nas altas do fundo antes de borrar,
que é o que faz luz virar aquele círculo suave de lente aberta.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

from ia_visual import Rosto, mascara_pele
from visual import misturar

RAIZ = Path(__file__).resolve().parent
LARGURA_MASCARA = 256


def mascara_geometrica(h: int, w: int, rosto: Optional[Rosto],
                       img: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """Cabeça + tronco a partir da caixa do rosto. Float32 0..1, (h,w).

    As proporções não são inventadas: são as da figura humana sentada, que é
    o enquadramento de qualquer live de webcam. A cabeça ocupa a caixa com uma
    folga; o pescoço sai do queixo; os ombros abrem para cerca de 3x a largura
    do rosto e descem até o fim do quadro.
    """
    if rosto is None or not rosto.valido:
        return None
    cx, cy = rosto.centro()
    rw2 = rosto.w * 0.62
    rh2 = rosto.h * 0.72

    yy = np.arange(h, dtype=np.float32)[:, None]
    xx = np.arange(w, dtype=np.float32)[None, :]

    d = np.sqrt(((xx - cx) / rw2) ** 2 + ((yy - cy) / rh2) ** 2)
    cabeca = np.clip((1.18 - d) / 0.30, 0.0, 1.0)

    # tronco: começa no queixo e alarga descendo
    y_queixo = rosto.y + rosto.h * 0.86
    desce = np.clip((yy - y_queixo) / max(1.0, rosto.h * 0.55), 0.0, 1.0)
    meia_largura = rosto.w * (0.42 + 1.15 * desce)
    dist_x = np.abs(xx - cx) / np.maximum(meia_largura, 1.0)
    tronco = (np.clip((1.05 - dist_x) / 0.22, 0.0, 1.0)
              * np.clip(desce * 3.0, 0.0, 1.0))

    m = np.maximum(cabeca, tronco).astype(np.float32)

    if img is not None:
        # reforço por pele: mão levantada, ombro nu, pescoço -- coisas que a
        # geometria não prevê mas a cor entrega
        m = np.maximum(m, np.clip(mascara_pele(img) * 1.2, 0.0, 1.0) * 0.9)
    return m


class Fundo:
    """Desfoque de fundo com máscara estável no tempo."""

    def __init__(self) -> None:
        self.nivel = "geometrico"
        self._mp = None
        self._onnx = None
        self._anterior: Optional[np.ndarray] = None
        self._preparar()

    def _preparar(self) -> None:
        try:
            import mediapipe as mp                    # noqa: F401
            self._mp = mp.solutions.selfie_segmentation \
                .SelfieSegmentation(model_selection=1)
            self.nivel = "mediapipe"
            return
        except Exception:
            self._mp = None
        if TEM_CV:
            for nome in ("selfie_segmenter.onnx", "modnet.onnx",
                         "segmentacao_pessoa.onnx"):
                arq = RAIZ / nome
                if arq.is_file():
                    try:
                        self._onnx = cv2.dnn.readNet(str(arq))
                        self.nivel = f"onnx:{nome}"
                        return
                    except Exception:
                        self._onnx = None
        self.nivel = "geometrico"

    def _bruta(self, peq: np.ndarray, rosto_peq: Optional[Rosto]
               ) -> Optional[np.ndarray]:
        if self._mp is not None:
            try:
                rgb = cv2.cvtColor(peq, cv2.COLOR_BGR2RGB)
                r = self._mp.process(rgb)
                if r is not None and r.segmentation_mask is not None:
                    return np.asarray(r.segmentation_mask, dtype=np.float32)
            except Exception:
                pass
        if self._onnx is not None:
            try:
                blob = cv2.dnn.blobFromImage(peq, 1 / 255.0, (256, 256),
                                             swapRB=True)
                self._onnx.setInput(blob)
                saida = self._onnx.forward()
                m = np.asarray(saida).squeeze()
                if m.ndim == 3:
                    m = m[-1]
                m = cv2.resize(m.astype(np.float32),
                               (peq.shape[1], peq.shape[0]))
                if m.max() > 1.5:                     # veio em logits
                    m = 1.0 / (1.0 + np.exp(-m))
                return m
            except Exception:
                pass
        return mascara_geometrica(peq.shape[0], peq.shape[1], rosto_peq, peq)

    def mascara(self, img: np.ndarray, rosto: Optional[Rosto],
                suavizar: float = 0.35) -> Optional[np.ndarray]:
        """A máscara da pessoa, em baixa resolução, já média no tempo."""
        h, w = img.shape[:2]
        k = LARGURA_MASCARA / float(max(1, w))
        if TEM_CV and k < 1.0:
            peq = cv2.resize(img, (LARGURA_MASCARA, max(2, int(h * k))),
                             interpolation=cv2.INTER_AREA)
            rp = rosto.escalar(k) if rosto else None
        else:
            peq, rp = img, rosto

        m = self._bruta(peq, rp)
        if m is None:
            self._anterior = None
            return None
        m = cv2.GaussianBlur(m, (0, 0), 2.0) if TEM_CV else m

        if self._anterior is not None and self._anterior.shape == m.shape:
            a = float(np.clip(suavizar, 0.05, 1.0))
            m = self._anterior * (1.0 - a) + m * a
        self._anterior = m
        return np.clip(m, 0.0, 1.0).astype(np.float32)

    def aplicar(self, img: np.ndarray, rosto: Optional[Rosto] = None,
                forca: float = 0.6, brilho_fundo: float = 0.25
                ) -> Tuple[np.ndarray, str]:
        """Devolve (imagem, motivo). O motivo vai para a tela."""
        if not TEM_CV or img is None or img.size == 0:
            return img, "sem OpenCV"
        f = float(np.clip(forca, 0.0, 1.0))
        if f <= 0.001:
            return img, "desligado"

        m = self.mascara(img, rosto)
        if m is None:
            return img, "sem pessoa detectada — fundo intacto"

        h, w = img.shape[:2]
        # borrão em 1/4: o fundo é liso por definição, ninguém vê a diferença
        pq = cv2.resize(img, (max(16, w // 4), max(16, h // 4)),
                        interpolation=cv2.INTER_AREA)
        if brilho_fundo > 0.001:
            # as altas do fundo incham antes de borrar: é o que transforma
            # uma lâmpada num círculo suave em vez de num borrão cinza
            luz = pq.max(axis=2).astype(np.float32)
            alta = np.clip((luz - 180.0) / 60.0, 0, 1)[..., None]
            pq = np.clip(pq.astype(np.float32)
                         * (1.0 + alta * float(brilho_fundo) * 1.6),
                         0, 255).astype(np.uint8)
        sigma = 1.5 + 9.0 * f
        borrado = cv2.resize(cv2.GaussianBlur(pq, (0, 0), sigma), (w, h),
                             interpolation=cv2.INTER_LINEAR)

        # a máscara vira 8 bits AINDA PEQUENA e é ampliada como 8 bits: subir
        # float de 256 para 1280 e só então converter custava o dobro
        m8 = np.clip(m * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return misturar(img, borrado, m8), self.nivel
