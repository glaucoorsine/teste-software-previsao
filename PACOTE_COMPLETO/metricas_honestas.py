# -*- coding: utf-8 -*-
"""
Métricas honestas: cobertura de janela vs acaso (não é EV financeiro).

P_hit = 1 - (1 - p)^J  sob independência.
Δ agregado correto: (Σ y_i / n) - (Σ p_esperado_i / n)  (Poisson-binomial).
"""
from __future__ import annotations
import math
from typing import Sequence, Optional, List

CT_WEIGHTS = {
    "1": 21 / 54, "2": 13 / 54, "5": 7 / 54, "10": 4 / 54,
    "CoinFlip": 4 / 54, "CashHunt": 2 / 54, "Pachinko": 2 / 54, "CrazyBonus": 1 / 54,
}
ROULETTE_P = 1.0 / 37.0


def p_alvos_roleta(alvos: Sequence) -> float:
    nums = set()
    for a in alvos or []:
        try:
            n = int(a)
            if 0 <= n <= 36:
                nums.add(n)
        except (TypeError, ValueError):
            continue
    return len(nums) * ROULETTE_P


def p_alvos_ct(alvos: Sequence) -> float:
    p = 0.0
    seen = set()
    for a in alvos or []:
        s = str(a)
        if s in seen:
            continue
        seen.add(s)
        p += float(CT_WEIGHTS.get(s, 0.0))
    return min(p, 1.0)


def p_hit_janela(p_single: float, janela: int) -> float:
    j = max(0, int(janela or 0))
    p = max(0.0, min(1.0, float(p_single or 0.0)))
    if j <= 0:
        return 0.0
    return 1.0 - (1.0 - p) ** j


def p_esperado_para(alvos: Sequence, janela: int, *, is_ct: bool) -> float:
    p1 = p_alvos_ct(alvos) if is_ct else p_alvos_roleta(alvos)
    return p_hit_janela(p1, janela)


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple:
    """IC95 Wilson para proporção."""
    if n <= 0:
        return (0.0, 1.0)
    # k fora de [0,n] não deveria acontecer (é uma contagem de acertos em n
    # tentativas), mas se acontecer por algum bug upstream, phat fora de [0,1]
    # derruba math.sqrt() com "math domain error" — melhor saturar que crashar.
    phat = max(0.0, min(1.0, k / n))
    z2 = z * z
    den = 1 + z2 / n
    centre = (phat + z2 / (2 * n)) / den
    margin = (z / den) * math.sqrt(phat * (1 - phat) / n + z2 / (4 * n * n))
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def ganho_significativo(
    acertos: int,
    n: int,
    p_esperado_medio: float,
    *,
    z: float = 1.96,
) -> dict:
    """
    Compara taxa observada com p_esperado médio acumulado.
    Exige IC95 da taxa completamente acima de p_esperado (teste conservador).
    """
    if n <= 0:
        return {"ok": False, "motivo": "n=0", "taxa": None, "lo": None, "hi": None, "p_exp": p_esperado_medio}
    lo, hi = wilson_interval(int(acertos), int(n), z=z)
    taxa = acertos / n
    # significativo se limite inferior do IC > p_esperado
    sig = lo > float(p_esperado_medio) + 1e-9
    return {
        "ok": sig,
        "motivo": "IC95_lo>p_exp" if sig else "IC95_cruza_ou_abaixo_p_exp",
        "taxa": taxa,
        "lo": lo,
        "hi": hi,
        "p_exp": float(p_esperado_medio),
        "ganho": taxa - float(p_esperado_medio),
    }


def resumo_acumulado(
    soma_y: float,
    soma_p: float,
    n: int,
    *,
    alvos_ultima: Sequence = (),
    janela_ultima: int = 0,
    is_ct: bool = False,
) -> dict:
    """Δ = taxa_obs - p_exp médio (ambos sobre as mesmas n janelas)."""
    if n <= 0:
        pe_last = p_esperado_para(alvos_ultima, janela_ultima, is_ct=is_ct) if alvos_ultima else 0.0
        return {
            "n_janelas": 0,
            "taxa_obs": None,
            "p_esperado_medio": None,
            "p_esperado_ultima": round(pe_last, 4),
            "ganho_vs_acaso": None,
            "aviso": "Sem janelas fechadas ainda.",
        }
    taxa = float(soma_y) / n
    pe = float(soma_p) / n
    pe_last = p_esperado_para(alvos_ultima, janela_ultima, is_ct=is_ct) if alvos_ultima else pe
    return {
        "n_janelas": n,
        "taxa_obs": round(taxa, 4),
        "p_esperado_medio": round(pe, 4),
        "p_esperado_ultima": round(pe_last, 4),
        "ganho_vs_acaso": round(taxa - pe, 4),
        "aviso": (
            f"Δ vs acaso acumulado (Σp/n={pe:.1%}). "
            f"Última janela sozinha esperaria {pe_last:.1%} — não use só a última no Δ."
        ),
    }


def texto_placar_acumulado(
    acertos: int,
    erros: int,
    soma_p_esperado: float,
    *,
    alvos_ultima: Sequence = (),
    janela_ultima: int = 0,
    is_ct: bool = False,
    exp_acertos: int = 0,
    exp_erros: int = 0,
) -> str:
    n = int(acertos or 0) + int(erros or 0)
    r = resumo_acumulado(
        float(acertos or 0), float(soma_p_esperado or 0.0), n,
        alvos_ultima=alvos_ultima, janela_ultima=janela_ultima, is_ct=is_ct,
    )
    if n <= 0:
        pe = r.get("p_esperado_ultima") or 0.0
        return f"Janelas 0|0  acaso_última≈{pe*100:.0f}%  (cobertura ≠ edge)"
    pe = r["p_esperado_medio"] or 0.0
    taxa = r["taxa_obs"] or 0.0
    g = r["ganho_vs_acaso"] or 0.0
    base = f"Janelas {acertos}|{erros}  taxa={taxa*100:.0f}%  acaso≈{pe*100:.0f}%  Δ={g:+.0%}"
    if exp_acertos or exp_erros:
        # "exp_acertos"/"exp_erros" sao 2 contadores independentes (nao uma
        # fracao) -- "N/M" aqui induzia a leitura errada de "N de M".
        base += f"  · esperado(mod.) acertos={exp_acertos} erros={exp_erros}"
    return base
