# -*- coding: utf-8 -*-
"""Schema de eventos categóricos e domínios."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set

ROULETTE_DOMAIN: Set[str] = {str(i) for i in range(37)}
CT_DOMAIN: Set[str] = {
    "1", "2", "5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"
}
DOMAIN_BY_DATASET = {
    "mega_fire": ROULETTE_DOMAIN,
    "lightning": ROULETTE_DOMAIN,
    "immersive": ROULETTE_DOMAIN,
    "crazy_time": CT_DOMAIN,
}

@dataclass
class Evento:
    valor: str
    ts: Optional[str] = None
    event_id: Optional[str] = None
    attrs: dict = field(default_factory=dict)

    def as_dict(self):
        return {"valor": self.valor, "ts": self.ts, "event_id": self.event_id, "attrs": self.attrs}

def normalizar_valor(raw: Any, dominio: Set[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if s in dominio:
        return s
    # CT aliases
    low = s.lower().replace(" ", "")
    aliases = {
        "coinflip": "CoinFlip", "cashhunt": "CashHunt", "pachinko": "Pachinko",
        "crazybonus": "CrazyBonus", "bonus": "CrazyBonus",
    }
    if low in aliases and aliases[low] in dominio:
        return aliases[low]
    if s.isdigit() and s in dominio:
        return s
    return None

def eventos_de_historico(hist, dataset_id: str, settled=None, mults=None, invalidos_out=None):
    """Normalização pura em memória — NÃO grava em disco."""
    dom = DOMAIN_BY_DATASET.get(dataset_id, ROULETTE_DOMAIN)
    out = []
    settled = settled or []
    mults = mults or []
    mult_by_n = {}
    for m in mults:
        try:
            mult_by_n[str(int(m.get("n")))] = float(m.get("x") or 1)
        except (TypeError, ValueError):
            pass
    invalidos = []
    for i, raw in enumerate(hist or []):
        v = normalizar_valor(raw, dom)
        if v is None:
            invalidos.append(str(raw))
            continue
        ts = settled[i] if i < len(settled) else None
        attrs = {}
        if v in mult_by_n:
            attrs["mult"] = mult_by_n[v]
        out.append(Evento(valor=v, ts=ts, event_id=f"{dataset_id}:{v}:mem{i}", attrs=attrs))
    if invalidos_out is not None:
        invalidos_out.extend(invalidos)
    return out

