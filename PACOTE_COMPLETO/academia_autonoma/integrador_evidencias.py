# -*- coding: utf-8 -*-
"""Integrador: convergência. Sem evidência prospectiva → SEM_EVIDÊNCIA."""
from __future__ import annotations
from typing import Any, Dict, List


def _familia(op: dict) -> str:
    return op.get("familia_metodologica") or op.get("modelo") or "?"


def convergencia(contrato: dict, opinioes: List[dict], qualidade_ok: bool) -> dict:
    if not qualidade_ok:
        return {
            "indice": 0.0,
            "status": "SEM_EVIDÊNCIA",
            "motivo": "qualidade_dados",
            "concordantes": [],
            "divergentes": [o.get("modelo") for o in opinioes],
        }

    estado = contrato.get("estado_historico") or ""
    ativ = contrato.get("estado_ativacao") or ""
    n_prosp = int(contrato.get("amostra_prospectiva") or contrato.get("shadow_n") or 0)
    ganho = contrato.get("efeito_vs_baseline")
    p = contrato.get("p_valor")

    # fator prospectivo: ZERO se não há sombra — não inventar 0.15
    if n_prosp <= 0:
        return {
            "indice": 0.0,
            "status": "SEM_EVIDÊNCIA",
            "motivo": "shadow_n=0",
            "concordantes": [],
            "divergentes": [o.get("modelo") for o in opinioes],
        }

    if not estado.startswith("validada") and estado not in ("em_teste", "reativada"):
        return {
            "indice": 0.0, "status": "SEM_EVIDÊNCIA",
            "motivo": f"estado_historico={estado}",
            "concordantes": [], "divergentes": [],
        }

    if ativ not in ("ATIVA", "REATIVAÇÃO_EM_TESTE"):
        return {
            "indice": 0.0, "status": "SEM_EVIDÊNCIA",
            "motivo": f"ativacao={ativ}",
            "concordantes": [], "divergentes": [],
        }

    f_prosp = min(1.0, n_prosp / 20.0)
    f_ganho = 0.0 if ganho is None else max(0.0, min(1.0, 0.5 + float(ganho) * 5))
    f_ativ = 1.0 if ativ == "ATIVA" else 0.6
    f_p = 1.0 if (p is not None and p <= 0.1) else 0.4

    concordantes, divergentes = [], []
    familias_ok = set()
    for o in opinioes:
        if float(o.get("compatibilidade_contextual") or 0) >= 0.45:
            concordantes.append(o.get("modelo"))
            familias_ok.add(_familia(o))
        else:
            divergentes.append(o.get("modelo"))

    f_repro = min(1.0, len(familias_ok) / 2.0)
    indice = f_prosp * f_ganho * f_ativ * f_repro * f_p
    if f_repro < 0.5 or f_ganho <= 0:
        status = "SEM_EVIDÊNCIA"
    elif indice >= 0.25:
        status = "CONVERGENTE"
    else:
        status = "FRACO"

    return {
        "indice": round(indice, 4),
        "status": status,
        "motivo": f"prosp={f_prosp:.2f} ganho={f_ganho:.2f} ativ={f_ativ} repro={f_repro:.2f} p={f_p}",
        "concordantes": concordantes,
        "divergentes": divergentes,
        "familias_independentes": sorted(familias_ok),
    }
