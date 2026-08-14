# -*- coding: utf-8 -*-
"""Uma Academia por processo; ciclos sobrepostos sempre rejeitados."""
from __future__ import annotations
import threading

_lock = threading.Lock()
_ativo = None
_ciclo_em_curso = False


def iniciar_ciclo(nome: str = "academia_autonoma") -> None:
    global _ativo, _ciclo_em_curso
    with _lock:
        if _ciclo_em_curso:
            raise RuntimeError(
                f"Ciclo sobreposto recusado: ativo={_ativo!r} tentativa={nome!r}"
            )
        if _ativo is not None and _ativo != nome:
            raise RuntimeError(
                f"Academia já fixada como {_ativo!r}; recusado {nome!r}"
            )
        _ativo = nome
        _ciclo_em_curso = True


def finalizar_ciclo() -> None:
    global _ciclo_em_curso
    with _lock:
        _ciclo_em_curso = False


def academia_ativa() -> str | None:
    return _ativo


def ciclo_em_curso() -> bool:
    return _ciclo_em_curso


def reset_para_testes() -> None:
    global _ativo, _ciclo_em_curso
    with _lock:
        _ativo = None
        _ciclo_em_curso = False
