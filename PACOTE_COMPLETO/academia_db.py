# -*- coding: utf-8 -*-
"""ADAPTADOR DB completo → academia_autonoma."""
from __future__ import annotations
from typing import List, Optional
from academia_autonoma.catalogo_persistente import get, listar, merge, count, registrar_prospectivo


def get_monitor(conjunto: str) -> dict:
    return {"cpu": "—", "ram": "—", "conjunto": conjunto, "fonte": "academia_autonoma"}


def list_hipoteses(conjunto: str, estado: Optional[str] = None) -> List[dict]:
    teor = listar(conjunto)
    if estado:
        return [t for t in teor if t.get("estado") == estado]
    return teor


def get_meta(conjunto: str) -> dict:
    teor = listar(conjunto)
    por = {}
    for t in teor:
        e = t.get("estado") or "?"
        por[e] = por.get(e, 0) + 1
    return {
        "conjunto": conjunto,
        "validadas": por.get("validada_ativa", 0) + por.get("validada_dormente", 0),
        "em_teste": por.get("em_teste", 0),
        "rejeitadas": por.get("rejeitada", 0),
        "total": len(teor),
        "fonte": "academia_autonoma",
    }


def conhecimento_validado_para_motor(conjunto: str) -> List[dict]:
    return [
        {
            "id": t.get("id"),
            "descricao": t.get("descricao"),
            "expr": t.get("expr"),
            "estado": t.get("estado"),
            "ativacao": t.get("ativacao"),
            "n_prosp": (t.get("prospectivo") or {}).get("n"),
            "taxa": (t.get("prospectivo") or {}).get("taxa"),
        }
        for t in listar(conjunto)
        if str(t.get("estado", "")).startswith("validada")
    ]
