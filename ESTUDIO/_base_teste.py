# -*- coding: utf-8 -*-
"""Base comum dos testes: a função `checa` e o resumo, no formato do projeto."""
from __future__ import annotations
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

falhas: list = []


def checa(cond, nome, detalhe=""):
    print(("  ok    " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)
    return bool(cond)


def resumo(titulo: str) -> int:
    print(f"\n{titulo}: {'TUDO OK' if not falhas else str(len(falhas)) + ' FALHA(S)'}")
    for f in falhas:
        print("   - " + f)
    return 1 if falhas else 0
