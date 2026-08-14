# -*- coding: utf-8 -*-
"""Contrato único de familiaridade — cópia somente leitura para outras IAs."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import copy

def para_contrato(teoria: dict) -> dict:
    """Objeto padronizado enviado às outras IAs (cópia)."""
    prosp = teoria.get("prospectivo") or {}
    ev = teoria.get("evidencia") or {}
    neg = teoria.get("teste_negativo") or {}
    ret = teoria.get("retrospectivo") or {}
    ganho = ev.get("ganho")
    if ganho is None:
        ganho = (ret.get("ganho") if isinstance(ret, dict) else None)
    return {
        "familiaridade_id": teoria.get("id"),
        "versao": teoria.get("versao", 1),
        "dataset_id": teoria.get("dataset_id"),
        "dominio": teoria.get("dominio"),
        "agente_autor": teoria.get("autor"),
        "expressao_dsl": copy.deepcopy(teoria.get("expr") or {}),
        "descricao": teoria.get("descricao"),
        "janela_descoberta": teoria.get("janela"),
        "horizonte_avaliacao": teoria.get("horizonte", 1),
        "estado_historico": teoria.get("estado"),
        "estado_ativacao": teoria.get("ativacao"),
        "score_ativacao": float(ev.get("taxa") or prosp.get("taxa") or 0) if (ev.get("taxa") or prosp.get("taxa")) else None,
        "amostra_retrospectiva": (ret.get("replay") or {}).get("n") if isinstance(ret, dict) else None,
        "amostra_prospectiva": int(prosp.get("n") or 0),
        "efeito_vs_baseline": ganho,
        "intervalo_confianca": None,  # preenchido quando houver
        "p_valor": neg.get("p_valor_emp"),
        "q_valor": teoria.get("q_valor"),
        "shadow_n": prosp.get("n"),
        "shadow_hits": prosp.get("hits"),
        "regime_atual": teoria.get("regime_atual"),
        "criada_em": teoria.get("criado_em"),
        "atualizada_em": teoria.get("atualizado_em"),
    }

def somente_leitura(contrato: dict) -> dict:
    return copy.deepcopy(contrato)
