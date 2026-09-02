# -*- coding: utf-8 -*-
"""Utilidades comuns aos testes."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent


def garantir_caminho() -> Path:
    """Põe a raiz do LYRA LIVE no sys.path e devolve onde ela está.

    Necessário para rodar um arquivo de teste direto (`python tests/test_x.py`),
    quando quem entra no sys.path é a pasta `tests/` e não a raiz. Rodando pelo
    `unittest` a partir da raiz isso já estaria resolvido — mas as duas formas
    precisam funcionar, senão a suíte só passa do jeito de quem a escreveu.
    """
    if str(RAIZ) not in sys.path:
        sys.path.insert(0, str(RAIZ))
    return RAIZ


garantir_caminho()


def quadro_ruido(alt=90, larg=160, semente=7) -> np.ndarray:
    """Ruído reprodutível — teste que muda de resultado a cada execução não vale."""
    r = np.random.RandomState(semente)
    return (r.rand(alt, larg, 3) * 255).astype(np.uint8)


def quadro_cena(alt=120, larg=200) -> np.ndarray:
    """Uma cena com fundo liso e uma figura em tom de pele no meio."""
    q = np.zeros((alt, larg, 3), np.uint8)
    q[:, :] = (120, 110, 100)
    y0, y1 = int(alt * 0.25), int(alt * 0.85)
    x0, x1 = int(larg * 0.3), int(larg * 0.7)
    q[y0:y1, x0:x1] = (140, 170, 215)      # BGR aproximado de pele
    return q
