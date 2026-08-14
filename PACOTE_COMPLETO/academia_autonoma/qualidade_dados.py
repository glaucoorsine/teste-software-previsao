# -*- coding: utf-8 -*-
"""Camada independente de qualidade dos dados."""
from __future__ import annotations
from typing import List, Dict, Any
from .schema_eventos import Evento, DOMAIN_BY_DATASET, normalizar_valor, ROULETTE_DOMAIN, eventos_de_historico

def validar(eventos: List[Evento], dataset_id: str, invalidos=None) -> Dict[str, Any]:
    from .schema_eventos import ROULETTE_DOMAIN
    dom = DOMAIN_BY_DATASET.get(dataset_id, ROULETTE_DOMAIN)
    problemas = []
    if not eventos:
        return {"ok": False, "problemas": ["vazio"], "n": 0, "ordem_ok": True, "duplicatas_id": 0}

    # domínio: valores já filtrados + inválidos reportados na normalização
    bad_in = [e.valor for e in eventos if e.valor not in dom]
    if bad_in:
        problemas.append(f"fora_dominio:{bad_in[:5]}")
    if invalidos:
        problemas.append(f"entrada_invalida:{list(invalidos)[:5]}")

    # ids
    ids = [e.event_id for e in eventos if e.event_id]
    dup = len(ids) - len(set(ids))
    if dup > 0:
        problemas.append(f"duplicatas_id:{dup}")

    # ordem temporal se timestamps — ignora eventos com timestamp_sintetico
    genuinos = [
        e for e in eventos
        if e.ts and not (isinstance(e.attrs, dict) and e.attrs.get("timestamp_sintetico"))
    ]
    ts = [e.ts for e in genuinos]
    n_sint = sum(
        1 for e in eventos
        if isinstance(e.attrs, dict) and e.attrs.get("timestamp_sintetico")
    )
    ordem_ok = True
    if len(ts) >= 2:
        def _key(x):
            try:
                return float(x)
            except Exception:
                return str(x)
        keys = [_key(x) for x in ts]
        asc = all(keys[i] <= keys[i+1] for i in range(len(keys)-1))
        desc = all(keys[i] >= keys[i+1] for i in range(len(keys)-1))
        ordem_ok = asc or desc
        if not ordem_ok:
            problemas.append("ordem_temporal_quebrada")
    elif n_sint and len(ts) < 2:
        # só sintéticos: não acusar quebra temporal
        ordem_ok = True

    return {
        "ok": len(problemas) == 0,
        "problemas": problemas,
        "n": len(eventos),
        "ordem_ok": ordem_ok,
        "duplicatas_id": dup,
        "com_timestamp": len(ts),
        "timestamp_sintetico_n": n_sint,
        "dominio": dataset_id,
    }
