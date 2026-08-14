# -*- coding: utf-8 -*-
"""
Seleção de 0–7 familiaridades auditáveis para a interface.
Nunca completa artificialmente até 7.
Nunca apresenta resultado futuro como certeza de aposta.
"""
from __future__ import annotations
from typing import Any, Dict, List
from .dsl_hipoteses import pred_candidatos, legivel

def _diversidade(selecionadas: List[dict], candidata: dict) -> bool:
    """No máx 2 mesma família metodológica (agente prefix), 2 mesmo horizonte, DSL quase igual."""
    autor = (candidata.get("agente_autor") or candidata.get("autor") or "")[:3]
    hor = candidata.get("horizonte_avaliacao") or candidata.get("horizonte") or 1
    desc = candidata.get("descricao") or ""
    n_autor = sum(1 for s in selecionadas if ((s.get("agente_autor") or s.get("autor") or "")[:3] == autor))
    n_hor = sum(1 for s in selecionadas if (s.get("horizonte_avaliacao") or s.get("horizonte") or 1) == hor)
    n_desc = sum(1 for s in selecionadas if (s.get("descricao") or "")[:30] == desc[:30])
    if n_autor >= 2:
        return False
    if n_hor >= 2:
        return False
    if n_desc >= 1:
        return False
    return True

def ordenar_familiaridades(contratos: List[dict]) -> List[dict]:
    def key(c):
        estado = c.get("estado_historico") or ""
        ativ = c.get("estado_ativacao") or ""
        rank_estado = 0
        if estado == "validada_ativa" or (estado.startswith("validada") and ativ == "ATIVA"):
            rank_estado = 3
        elif ativ == "REATIVAÇÃO_EM_TESTE":
            rank_estado = 2
        elif estado.startswith("validada"):
            rank_estado = 1
        n = int(c.get("amostra_prospectiva") or 0)
        ganho = float(c.get("efeito_vs_baseline") or -1)
        p = c.get("p_valor")
        p_score = 0 if p is None else (1 - min(1.0, float(p)))
        return (rank_estado, n, ganho, p_score)

    return sorted(contratos, key=key, reverse=True)

def selecionar_cartoes(contratos: List[dict], max_n: int = 7) -> List[dict]:
    """0–7 cartões. Não preenche com lixo."""
    ordenados = ordenar_familiaridades(contratos)
    # só ativas / reativação / validadas relevantes
    filtrados = [
        c for c in ordenados
        if (c.get("estado_ativacao") in ("ATIVA", "REATIVAÇÃO_EM_TESTE")
            or (c.get("estado_historico") or "").startswith("validada"))
    ]
    out = []
    for c in filtrados:
        if not _diversidade(out, c):
            continue
        out.append(c)
        if len(out) >= max_n:
            break
    return out

def cartao_texto(c: dict, opinioes: List[dict] = None, conv: dict = None) -> str:
    opinioes = opinioes or []
    conv = conv or {}
    conc = ",".join(conv.get("concordantes") or []) or "—"
    div = ",".join(conv.get("divergentes") or []) or "—"
    return (
        f"FAMILIARIDADE {str(c.get('familiaridade_id') or '')[:8]}\n"
        f"  {c.get('descricao')}\n"
        f"  Estado: {c.get('estado_historico')} | Ativação: {c.get('estado_ativacao')}\n"
        f"  Autor: {c.get('agente_autor')} | Janela: {c.get('janela_descoberta')} | "
        f"Horizonte: {c.get('horizonte_avaliacao')}\n"
        f"  Sombra: {c.get('shadow_hits')}/{c.get('shadow_n')} | "
        f"Ganho vs baseline: {c.get('efeito_vs_baseline')}\n"
        f"  p={c.get('p_valor')} | q={c.get('q_valor')}\n"
        f"  Concordâncias: {conc} | Divergências: {div}\n"
        f"  Integrador: {conv.get('status')} ({conv.get('indice')})"
    )

def candidatos_pesquisa(
    cartoes: List[dict],
    hist: List[str],
    dominio: List[str],
    max_n: int = 7,
) -> List[str]:
    """
    Até 7 símbolos experimentais derivados das familiaridades selecionadas.
    Não completa artificialmente. Uso: pesquisa/sombra — não tip de aposta.
    """
    out = []
    for c in cartoes:
        expr = c.get("expressao_dsl") or {}
        for x in pred_candidatos(expr, hist, dominio, k=3):
            if x not in out:
                out.append(x)
            if len(out) >= max_n:
                return out
    return out
