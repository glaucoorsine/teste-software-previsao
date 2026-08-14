# -*- coding: utf-8 -*-
from __future__ import annotations
"""Opiniões de modelos. SEQ_MARKOV até LSTM/torch real. Não validam hipóteses."""
from collections import Counter
from typing import Dict, List, Any
from .contrato_familiaridade import somente_leitura
from .dsl_hipoteses import eval_cond, pred_candidatos

def _hist_vals(hist) -> List[str]:
    return [str(x) for x in (hist or [])]

def opiniao_estatistico(hist: List[str], contrato: dict, dominio: List[str]) -> dict:
    c = Counter(hist[:40])
    top = [x for x, _ in c.most_common(5)]
    cands = contrato.get("expressao_dsl") and pred_candidatos(
        contrato.get("expressao_dsl") or {}, hist, dominio, k=5
    ) or []
    inter = len(set(top) & set(map(str, cands)))
    compat = inter / max(len(cands), 1) if cands else 0.0
    return {
        "modelo": "ESTATISTICO",
        "dataset_id": contrato.get("dataset_id"),
        "familiaridade_id": contrato.get("familiaridade_id"),
        "compatibilidade_contextual": round(compat, 3),
        "divergencia": round(1 - compat, 3),
        "amostra_modelo": min(40, len(hist)),
        "calibracao": None,
        "observacao": f"top_freq={top[:3]} inter={inter}",
        "familia_metodologica": "FREQUENCIA",
    }

def opiniao_anomalia(hist: List[str], contrato: dict, dominio: List[str]) -> dict:
    if len(hist) < 20:
        return {
            "modelo": "ANOMALIA", "dataset_id": contrato.get("dataset_id"),
            "familiaridade_id": contrato.get("familiaridade_id"),
            "compatibilidade_contextual": 0.0, "divergencia": 1.0,
            "amostra_modelo": len(hist), "calibracao": None,
            "observacao": "hist curto", "familia_metodologica": "ANOMALIA",
        }
    # ruptura: último valor raro no longo
    longo = Counter(hist[5:40])
    raro = longo.get(hist[0], 0) == 0
    return {
        "modelo": "ANOMALIA",
        "dataset_id": contrato.get("dataset_id"),
        "familiaridade_id": contrato.get("familiaridade_id"),
        "compatibilidade_contextual": 0.3 if raro else 0.6,
        "divergencia": 0.7 if raro else 0.4,
        "amostra_modelo": len(hist[:40]),
        "calibracao": None,
        "observacao": "ruptura no topo" if raro else "sem ruptura forte",
        "familia_metodologica": "ANOMALIA",
    }

def opiniao_regime(hist: List[str], contrato: dict, dominio: List[str]) -> dict:
    if len(hist) < 30:
        return {
            "modelo": "REGIME", "dataset_id": contrato.get("dataset_id"),
            "familiaridade_id": contrato.get("familiaridade_id"),
            "compatibilidade_contextual": 0.0, "divergencia": 1.0,
            "amostra_modelo": len(hist), "calibracao": None,
            "observacao": "insuficiente", "familia_metodologica": "REGIME",
        }
    m1 = Counter(hist[:12]).most_common(1)[0][0]
    m2 = Counter(hist[12:36]).most_common(1)[0][0]
    mudou = m1 != m2
    return {
        "modelo": "REGIME",
        "dataset_id": contrato.get("dataset_id"),
        "familiaridade_id": contrato.get("familiaridade_id"),
        "compatibilidade_contextual": 0.55 if not mudou else 0.35,
        "divergencia": 0.45 if not mudou else 0.65,
        "amostra_modelo": 36,
        "calibracao": None,
        "observacao": f"moda_curta={m1} moda_media={m2} mudou={mudou}",
        "familia_metodologica": "REGIME",
        "regime_label": f"R_{m1}",
    }

def opiniao_lstm_heuristica(hist: List[str], contrato: dict, dominio: List[str]) -> dict:
    """
    Análise sequencial independente (heurística de transição).
    Não confirma lista pronta — mede se o contexto da familiaridade
    alinha com transições observadas pelo próprio modelo.
    """
    if len(hist) < 15:
        return {
            "modelo": "SEQ_MARKOV", "dataset_id": contrato.get("dataset_id"),
            "familiaridade_id": contrato.get("familiaridade_id"),
            "compatibilidade_contextual": 0.0, "divergencia": 1.0,
            "amostra_modelo": len(hist), "calibracao": None,
            "observacao": "hist curto", "familia_metodologica": "SEQUENCIAL",
        }
    # modelo próprio: top transição a partir de hist[1]
    pares = Counter()
    for i in range(len(hist) - 1):
        pares[(hist[i + 1], hist[i])] += 1
    ancora = hist[1] if len(hist) > 1 else hist[0]
    candidatos_modelo = [b for (a, b), n in pares.most_common(20) if a == ancora][:5]
    if not candidatos_modelo:
        candidatos_modelo = [x for x, _ in Counter(hist[:20]).most_common(3)]
    expr = contrato.get("expressao_dsl") or {}
    cands_f = pred_candidatos(expr, hist, dominio, k=5)
    inter = len(set(map(str, candidatos_modelo)) & set(map(str, cands_f)))
    compat = inter / max(len(cands_f), 1) if cands_f else 0.0
    return {
        "modelo": "SEQ_MARKOV",
        "dataset_id": contrato.get("dataset_id"),
        "familiaridade_id": contrato.get("familiaridade_id"),
        "compatibilidade_contextual": round(compat, 3),
        "divergencia": round(1 - compat, 3),
        "amostra_modelo": len(hist),
        "calibracao": None,
        "observacao": f"seq_top={candidatos_modelo[:3]} fam_cands={cands_f[:3]}",
        "familia_metodologica": "SEQUENCIAL",
        "candidatos_proprios": candidatos_modelo,
    }

def coletar_opinioes(hist: List[str], contrato: dict, dominio: List[str]) -> List[dict]:
    c = somente_leitura(contrato)
    return [
        opiniao_estatistico(hist, c, dominio),
        opiniao_anomalia(hist, c, dominio),
        opiniao_regime(hist, c, dominio),
        opiniao_lstm_heuristica(hist, c, dominio),
    ]


def lstm_disponivel() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False
