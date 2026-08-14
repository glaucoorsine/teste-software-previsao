# -*- coding: utf-8 -*-
"""Detecção de mudança de regime em sequência categórica.

Limiar de distância L1 é calibrado por Monte Carlo sob H0, com a janela curta
contida na longa (mesma convenção do detector operacional). Um limiar fixo 0.35
gera ~98% de falso positivo em roleta (37 categorias).
"""
from __future__ import annotations
from collections import Counter
from typing import Dict, List, Any, Tuple
import math
import random

# cache: (n_cats, curto, longo, pct) -> limiar
_LIMIAR_CACHE: Dict[Tuple[int, int, int, float], float] = {}


def _freq(hist: List[str], n: int) -> Counter:
    return Counter(hist[:n])


def _dist_l1(hist: List[str], curto: int, longo: int) -> float:
    c = _freq(hist, curto)
    l = _freq(hist, min(longo, len(hist)))
    keys = set(c) | set(l)
    sc = sum(c.values()) or 1
    sl = sum(l.values()) or 1
    dist = 0.0
    for k in keys:
        dist += abs(c.get(k, 0) / sc - l.get(k, 0) / sl)
    return dist / 2.0


def _estimar_n_cats(hist: List[str], dominio_hint: int = 0) -> int:
    if dominio_hint and dominio_hint > 0:
        return int(dominio_hint)
    uniques = len(set(hist[:200]))
    # roleta ~37; CT ~8; se poucos únicos ainda, usa max observado
    if uniques >= 20:
        return 37
    if uniques <= 12:
        return max(uniques, 8)
    return max(uniques, 16)


def calibrar_limiar(
    n_cats: int,
    curto: int = 20,
    longo: int = 80,
    pct: float = 99.0,
    trials: int = 2500,
    seed: int = 1,
) -> float:
    """Percentil da distância L1 sob H0 IID com janela curta ⊆ longa."""
    key = (int(n_cats), int(curto), int(longo), float(pct))
    if key in _LIMIAR_CACHE:
        return _LIMIAR_CACHE[key]
    rng = random.Random(seed)
    dists = []
    n_len = longo + 5
    for _ in range(trials):
        hist = [str(rng.randrange(n_cats)) for _ in range(n_len)]
        dists.append(_dist_l1(hist, curto, longo))
    dists.sort()
    idx = min(len(dists) - 1, max(0, int(round((pct / 100.0) * (len(dists) - 1)))))
    lim = float(dists[idx])
    # piso mínimo para não disparar em amostras minúsculas
    lim = max(lim, 0.18)
    _LIMIAR_CACHE[key] = lim
    return lim


def _chi2_nested(hist: List[str], curto: int, longo: int) -> Tuple[float, float]:
    """
    Compara contagens da janela curta com as da porção complementar da janela longa
    (longo \\ curto), evitando tratar curta e longa como amostras independentes.
    Retorna (estatística, p-valor aproximado cauda direita).
    """
    if len(hist) < longo or longo <= curto + 2:
        return 0.0, 1.0
    c = _freq(hist, curto)
    # complemento: hist[curto:longo]
    comp = Counter(hist[curto:longo])
    keys = set(c) | set(comp)
    if len(keys) < 2:
        return 0.0, 1.0
    n1 = sum(c.values()) or 1
    n2 = sum(comp.values()) or 1
    chi = 0.0
    df = 0
    for k in keys:
        o1 = c.get(k, 0)
        o2 = comp.get(k, 0)
        e1 = n1 * ((o1 + o2) / (n1 + n2))
        e2 = n2 * ((o1 + o2) / (n1 + n2))
        if e1 > 0:
            chi += (o1 - e1) ** 2 / e1
        if e2 > 0:
            chi += (o2 - e2) ** 2 / e2
        df += 1
    df = max(df - 1, 1)
    # p-valor via aproximação de Wilson-Hilferty / sobrevida chi2
    # (sem scipy): usa cauda superior com transformação normal
    try:
        z = ((chi / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
        # 1 - Phi(z) aproximado
        p = 0.5 * math.erfc(z / math.sqrt(2))
        p = max(0.0, min(1.0, p))
    except Exception:
        p = 1.0
    return chi, p


def detectar(
    hist: List[str],
    curto: int = 20,
    longo: int = 80,
    n_cats: int = 0,
    pct_h0: float = 99.0,
    p_chi: float = 0.01,
) -> Dict[str, Any]:
    if len(hist) < curto + 5:
        return {"regime": "INSUFICIENTE", "mudanca": False, "js": 0.0, "detalhe": "n baixo"}

    n_est = _estimar_n_cats(hist, n_cats)
    limiar = calibrar_limiar(n_est, curto, longo, pct=pct_h0)
    dist = _dist_l1(hist, curto, longo)
    chi, pval = _chi2_nested(hist, curto, min(longo, len(hist)))

    # mudança se L1 acima do percentil H0 OU qui-quadrado significativo
    mudanca_l1 = dist >= limiar
    mudanca_chi = pval <= p_chi and chi > 0
    mudanca = bool(mudanca_l1 or mudanca_chi)

    c = _freq(hist, curto)
    sc = sum(c.values()) or 1
    reps = 0
    for i in range(min(15, len(hist) - 1)):
        if hist[i] == hist[i + 1]:
            reps += 1

    regime = "ESTAVEL"
    if mudanca:
        regime = "TRANSICAO"
    if reps >= 4:
        regime = "ALTA_REPETICAO"
    if c:
        top, cnt = c.most_common(1)[0]
        if cnt / sc >= 0.35:
            regime = f"DOMINANTE:{top}"

    return {
        "regime": regime,
        "mudanca": mudanca,
        "js": round(dist, 4),
        "limiar": round(limiar, 4),
        "n_cats": n_est,
        "chi2": round(chi, 4),
        "p_chi": round(pval, 6),
        "reps_curto": reps,
        "top_curto": c.most_common(5),
        "detalhe": (
            f"dist={dist:.3f} limiar={limiar:.3f}(p{pct_h0:.0f}|cats={n_est}) "
            f"chi2={chi:.2f} p={pval:.4f} curto={curto} longo={min(longo, len(hist))}"
        ),
    }


def taxa_falso_positivo_iid(
    n_cats: int = 37,
    curto: int = 20,
    longo: int = 80,
    trials: int = 500,
    seed: int = 1,
) -> float:
    """Utilitário de diagnóstico: fração de mudanca=True sob IID."""
    rng = random.Random(seed)
    hits = 0
    for _ in range(trials):
        hist = [str(rng.randrange(n_cats)) for _ in range(longo + 10)]
        if detectar(hist, curto=curto, longo=longo, n_cats=n_cats)["mudanca"]:
            hits += 1
    return hits / trials
