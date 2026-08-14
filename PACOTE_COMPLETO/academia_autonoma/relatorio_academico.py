# -*- coding: utf-8 -*-
"""Relatório acadêmico auditável."""
from __future__ import annotations
from typing import Dict, Any, List
from .catalogo_persistente import listar, count
from .detector_regimes import detectar
from .stream_seq import peek_seq
from .paths_dados import subdir
from .memoria_agentes import carregar


def gerar(dataset_id: str, hist: List[str] = None) -> Dict[str, Any]:
    teor = listar(dataset_id)
    por_estado = {}
    por_autor = {}
    trilha = []
    for t in teor:
        e = t.get("estado") or "?"
        por_estado[e] = por_estado.get(e, 0) + 1
        a = t.get("autor") or "?"
        por_autor[a] = por_autor.get(a, 0) + 1
        p = t.get("prospectivo") or {}
        trilha.append({
            "id": t.get("id"),
            "autor": a,
            "descricao": t.get("descricao"),
            "estado": e,
            "ativacao": t.get("ativacao"),
            "n_prosp": p.get("n"),
            "hits": p.get("hits"),
            "taxa": p.get("taxa"),
            "baseline_hits": sum(1 for x in (p.get("hist") or []) if x.get("baseline_hit")),
            "ganho_prosp": (t.get("evidencia") or {}).get("ganho_prosp"),
            "ic90_low_ganho": (t.get("evidencia") or {}).get("ic90_low_ganho_prosp"),
            "q_valor": t.get("q_valor"),
            "p_valor": (t.get("teste_negativo") or {}).get("p_valor_emp"),
            "motivo_meta": t.get("motivo_meta"),
            "motivo_critica": t.get("motivo_critica"),
            "regime_ultima": t.get("_regime"),
            "episodios_n": len(t.get("episodios_ativacao") or []),
        })
    sombras = [x for x in trilha if (x.get("n_prosp") or 0) > 0]
    mem_ag = {}
    for a in sorted(por_autor.keys()):
        mem_ag[a] = carregar(dataset_id, a)
    reg = detectar(hist or []) if hist else {}
    return {
        "dataset_id": dataset_id,
        "stream_seq": peek_seq(dataset_id),
        "total_teorias": count(dataset_id),
        "por_estado": por_estado,
        "por_autor": por_autor,
        "com_sombra": len(sombras),
        "top_sombra": sorted(sombras, key=lambda x: -(x.get("n_prosp") or 0))[:20],
        "trilha_estatistica": trilha[:200],
        "regime": reg,
        "memoria_agentes": {k: {
            "ciclos": v.get("ciclos"),
            "stats": v.get("stats"),
            "regioes": (v.get("regioes_exploradas") or [])[:20],
            "rejeicoes_recentes": (v.get("ultimas_rejeicoes") or [])[-5:],
        } for k, v in mem_ag.items()},
        "data_dir": str(subdir(".").parent),
        "aviso": "Relatório descritivo; não constitui tip de aposta.",
    }
