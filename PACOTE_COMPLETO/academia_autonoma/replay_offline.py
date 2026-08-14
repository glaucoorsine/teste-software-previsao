# -*- coding: utf-8 -*-
"""Replay prequential: avança do passado para o presente, mesmo dataset_id."""
from __future__ import annotations
from typing import Callable, Dict, List, Any


def replay(
    historico_completo: List[str],
    fn_ciclo: Callable,
    dataset_id: str,
    passo_min: int = 30,
    max_passos: int = 40,
) -> Dict[str, Any]:
    """
    historico_completo: índice 0 = mais RECENTE (convenção do projeto).

    Replay prequential:
      - começa com os passo_min eventos mais antigos
      - a cada passo adiciona o próximo evento mais novo
      - sempre mesmo dataset_id (catálogo/sombra persistem entre passos)
      - em cada passo, fn_ciclo só vê o passado até aquele instante
    """
    h = [str(x) for x in historico_completo]
    n = len(h)
    if n < passo_min + 2:
        return {"passos": 0, "logs": [], "erro": "historico curto"}

    # ordem cronológica antiga → nova
    chrono = list(reversed(h))  # chrono[0] = mais antigo
    logs = []
    n_passos = 0
    # t = número de eventos já conhecidos (do mais antigo)
    start = passo_min
    end = min(n, start + max_passos)
    for t in range(start, end):
        # passado: chrono[0:t]  → converter de volta para recente-primeiro
        past_chrono = chrono[:t]
        past = list(reversed(past_chrono))  # hist[0] = mais recente conhecido
        try:
            out = fn_ciclo(dataset_id, past)
            logs.append({
                "t": t,
                "n_conhecido": t,
                "head": past[0] if past else None,
                "operavel": (out or {}).get("operavel"),
                "n_cartoes": len((out or {}).get("cartoes") or []),
            })
        except Exception as e:
            logs.append({"t": t, "erro": str(e)})
        n_passos += 1
    return {"passos": n_passos, "logs": logs, "dataset_id": dataset_id}
