# -*- coding: utf-8 -*-
"""Avaliação prequential sem vazamento: prevê em t, avalia em t+1."""
from __future__ import annotations
from typing import Callable, Dict, List, Any
from .dsl_hipoteses import eval_cond, pred_candidatos

def replay_prospectivo(
    hist_recent_first: List[str],
    expr: dict,
    dominio: List[str],
    horizonte: int = 1,
    max_steps: int = 80,
) -> Dict[str, Any]:
    """
    hist[0] = mais recente. Para não vazar, em cada passo i (do antigo ao novo)
    usamos apenas o passado disponível naquele instante.
    Convert to chronological for walk.
    """
    if len(hist_recent_first) < 10:
        return {"n": 0, "hits": 0, "taxa": None, "ativacoes": 0}
    chrono = list(reversed(hist_recent_first))  # antigo → recente
    hits = n = ativ = 0
    steps = 0
    for t in range(5, len(chrono) - horizonte):
        if steps >= max_steps:
            break
        past_chrono = chrono[: t + 1]
        past_recent = list(reversed(past_chrono))
        if not eval_cond(expr, past_recent):
            continue
        ativ += 1
        cands = pred_candidatos(expr, past_recent, dominio, k=5)
        if not cands:
            continue
        future = chrono[t + horizonte]
        n += 1
        steps += 1
        if future in cands:
            hits += 1
    taxa = hits / n if n else None
    return {"n": n, "hits": hits, "taxa": taxa, "ativacoes": ativ}

def baseline_freq(hist_recent_first: List[str], k: int, dominio: List[str]) -> List[str]:
    from collections import Counter
    c = Counter(hist_recent_first[:40])
    return [x for x, _ in c.most_common(k) if x in dominio]

def replay_baseline(hist_recent_first, k, dominio, max_steps=80):
    chrono = list(reversed(hist_recent_first))
    hits = n = 0
    for t in range(5, min(len(chrono) - 1, 5 + max_steps)):
        past = list(reversed(chrono[: t + 1]))
        pred = baseline_freq(past, k, dominio)
        y = chrono[t + 1]
        n += 1
        if y in pred:
            hits += 1
    return {"n": n, "hits": hits, "taxa": hits / n if n else None}
