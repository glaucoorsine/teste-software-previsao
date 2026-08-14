# -*- coding: utf-8 -*-
"""Ativação atual ≠ validade histórica. Regime participa da decisão."""
from __future__ import annotations
from typing import List
from .dsl_hipoteses import eval_cond

MIN_SOMBRA_ATIVA = 8
MIN_TAXA_ATIVA = 0.18


def ativar(teoria: dict, hist: List[str], dominio: List[str], regime=None) -> dict:
    estado = teoria.get("estado")
    expr = teoria.get("expr") or {}
    ativa_ctx = eval_cond(expr, hist)
    regime = regime or {}
    teoria["_regime"] = regime.get("regime")
    teoria["_regime_mudanca"] = bool(regime.get("mudanca"))
    prosp = teoria.get("prospectivo") or {}
    n = int(prosp.get("n") or 0)
    taxa = prosp.get("taxa")
    mudanca = bool(regime.get("mudanca"))
    reg_nome = str(regime.get("regime") or "")

    if estado in ("rejeitada", "arquivada"):
        teoria["ativacao"] = "SEM_EVIDÊNCIA"
        return teoria

    if estado in ("candidata", "em_teste"):
        if ativa_ctx and not mudanca:
            teoria["ativacao"] = "QUARENTENA_SOMBRA"
        elif ativa_ctx and mudanca:
            # em transição: ainda permite sombra, mas marca
            teoria["ativacao"] = "QUARENTENA_SOMBRA"
            teoria.setdefault("episodios_ativacao", []).append(
                {"tipo": "quarentena_em_transicao", "regime": reg_nome}
            )
        else:
            teoria["ativacao"] = "SEM_EVIDÊNCIA"
        return teoria

    if estado == "degradada":
        teoria["ativacao"] = "DEGRADADA"
        if ativa_ctx and n >= MIN_SOMBRA_ATIVA and (taxa or 0) >= MIN_TAXA_ATIVA and not mudanca:
            teoria["ativacao"] = "REATIVAÇÃO_EM_TESTE"
        elif ativa_ctx:
            teoria["ativacao"] = "QUARENTENA_SOMBRA"
        return teoria

    if n >= MIN_SOMBRA_ATIVA and taxa is not None and taxa < 0.12:
        teoria["estado"] = "degradada"
        teoria["ativacao"] = "DEGRADADA"
        return teoria

    if n < MIN_SOMBRA_ATIVA:
        if estado == "validada_ativa":
            teoria["estado"] = "validada_dormente"
        if ativa_ctx:
            teoria["ativacao"] = "QUARENTENA_SOMBRA"
        else:
            teoria["ativacao"] = "DORMENTE" if str(estado).startswith("validada") else "SEM_EVIDÊNCIA"
        return teoria

    # n >= MIN — regime bloqueia ATIVA plena em transição
    if mudanca:
        teoria["ativacao"] = "REATIVAÇÃO_EM_TESTE"
        teoria.setdefault("episodios_ativacao", []).append(
            {"tipo": "bloqueio_regime", "regime": reg_nome, "n_prosp": n}
        )
        if teoria.get("estado") == "validada_ativa":
            teoria["estado"] = "validada_dormente"
        return teoria

    if reg_nome.startswith("DOMINANTE:") and taxa is not None and taxa < 0.25:
        # regime dominante de outro valor: exige taxa maior
        teoria["ativacao"] = "DORMENTE"
        teoria.setdefault("episodios_ativacao", []).append(
            {"tipo": "dominante_alheio", "regime": reg_nome, "taxa": taxa}
        )
        return teoria

    if ativa_ctx and (taxa is None or taxa >= MIN_TAXA_ATIVA):
        if teoria.get("estado") == "validada_dormente":
            teoria["estado"] = "validada_ativa"
            teoria.setdefault("episodios_ativacao", []).append(
                {"tipo": "ativou", "n_prosp": n, "taxa": taxa, "regime": reg_nome}
            )
        teoria["ativacao"] = "ATIVA"
    elif ativa_ctx:
        teoria["ativacao"] = "DORMENTE"
        if teoria.get("estado") == "validada_ativa":
            teoria["estado"] = "validada_dormente"
    else:
        if teoria.get("estado") == "validada_ativa":
            teoria["estado"] = "validada_dormente"
            teoria.setdefault("episodios_ativacao", []).append({"tipo": "dormiu", "n_prosp": n})
        teoria["ativacao"] = "DORMENTE"
    return teoria
