# -*- coding: utf-8 -*-
"""
7 reformuladores inteligentes.

Quando o crítico manda 'reavaliar_variante', estas unidades
NÃO descartam a ideia — tentam variantes concretas:

R1 horizonte 1→2→3
R2 expandir/encolher conjunto de finais (ex.: 4,5,9)
R3 vizinhos de roleta do último alvo
R4 inverter direção da transição A→B vira B→A
R5 janela curta vs média (últimos 15 / 40)
R6 misturar com residual (números fora do consenso quente)
R7 limitar sempre a 5–7 candidatos e retestar

Toda variante nasce como nova hipótese em_observacao_viva,
preservando a teoria-mãe no catálogo.
"""
from __future__ import annotations
from typing import Dict, List, Any
import copy
import time
from .dsl_hipoteses import pred_candidatos

K_MIN, K_MAX = 5, 7

# ordem europeia simplificada para vizinhos
RODA = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26,
]
_IDX = {str(n): i for i, n in enumerate(RODA)}


def _vizinhos(n: str, raio: int = 2) -> List[str]:
    if n not in _IDX:
        return []
    i = _IDX[n]
    out = []
    for d in range(-raio, raio + 1):
        if d == 0:
            continue
        out.append(str(RODA[(i + d) % len(RODA)]))
    return out


def _finais_de(nums: List[str]) -> List[str]:
    fs = sorted({str(x)[-1] for x in nums if str(x).isdigit()})
    return fs


def _clone(teoria: dict, tag: str, expr: dict) -> dict:
    t = copy.deepcopy(teoria)
    t["id"] = f"{teoria.get('id', 't')[:20]}_{tag}_{int(time.time()) % 100000}"
    t["expr"] = expr
    t["origem"] = f"reformulador:{tag}"
    t["teoria_mae"] = teoria.get("id")
    t["destino_critico"] = "em_observacao_viva"
    t["critica_ok"] = False
    t["estado"] = "em_observacao_viva"
    t["primeira_observacao_ts"] = time.time()
    t["preservar_catalogo"] = True
    return t


def R1_horizonte(teoria, hist, dominio):
    h0 = int(teoria.get("horizonte") or 1)
    out = []
    for h in (1, 2, 3):
        if h == h0:
            continue
        t = _clone(teoria, f"R1h{h}", teoria.get("expr") or {})
        t["horizonte"] = h
        out.append(t)
    return out


def R2_finais(teoria, hist, dominio):
    expr = teoria.get("expr") or {}
    cands = pred_candidatos(expr, hist, dominio, k=K_MAX) or []
    fins = _finais_de([str(x) for x in cands] + [str(x) for x in hist[:5] if str(x).isdigit()])
    if not fins:
        fins = list("459")  # grupo que o usuário validou ao vivo
    # expandir
    exp = {
        "op": "final_in",
        "finais": sorted(set(fins + list("459"))),
        "k": K_MAX,
    }
    # encolher ao núcleo 4/5/9 se houver interseção
    nuc = sorted(set(fins) & set("459")) or list("459")
    shr = {"op": "final_in", "finais": nuc, "k": K_MIN}
    return [_clone(teoria, "R2exp", exp), _clone(teoria, "R2shr", shr)]


def R3_vizinhos(teoria, hist, dominio):
    if not hist:
        return []
    ult = str(hist[0])
    viz = _vizinhos(ult, 2)
    if not viz:
        return []
    expr = {"op": "in_set", "set": viz[:K_MAX]}
    return [_clone(teoria, "R3viz", expr)]


def R4_inverte_transicao(teoria, hist, dominio):
    expr = teoria.get("expr") or {}
    if (expr.get("op") or "") != "transition":
        return []
    inv = dict(expr)
    inv["a"], inv["b"] = expr.get("b"), expr.get("a")
    return [_clone(teoria, "R4inv", inv)]


def R5_janela(teoria, hist, dominio):
    expr = dict(teoria.get("expr") or {})
    out = []
    for w, tag in ((15, "curta"), (40, "media")):
        e = dict(expr)
        e["janela"] = w
        out.append(_clone(teoria, f"R5{tag}", e))
    return out


def R6_residual(teoria, hist, dominio):
    """Números que o consenso quente ignora — anti-óbvio limitado a 5–7."""
    from collections import Counter
    c = Counter(hist[:40])
    quentes = {x for x, _ in c.most_common(10)}
    frios = [x for x in dominio if x not in quentes][:K_MAX]
    if len(frios) < K_MIN:
        return []
    expr = {"op": "in_set", "set": frios[:K_MAX]}
    return [_clone(teoria, "R6res", expr)]


def R7_cap_5_7(teoria, hist, dominio):
    expr = teoria.get("expr") or {}
    cands = pred_candidatos(expr, hist, dominio, k=12) or list(expr.get("set") or [])
    cands = [str(x) for x in cands][:K_MAX]
    if len(cands) < K_MIN:
        # completa com finais do histórico recente
        extra = []
        for h in hist[:20]:
            if str(h) not in cands and str(h) in dominio:
                extra.append(str(h))
            if len(cands) + len(extra) >= K_MIN:
                break
        cands = (cands + extra)[:K_MAX]
    if not cands:
        return []
    return [_clone(teoria, "R7cap", {"op": "in_set", "set": cands[:K_MAX]})]


REFORMULADORES = [
    ("R1", R1_horizonte),
    ("R2", R2_finais),
    ("R3", R3_vizinhos),
    ("R4", R4_inverte_transicao),
    ("R5", R5_janela),
    ("R6", R6_residual),
    ("R7", R7_cap_5_7),
]


def reformular(teoria: dict, hist: List[str], dominio: List[str], max_var: int = 8) -> List[dict]:
    """Gera variantes; nunca apaga a mãe."""
    hist = [str(x) for x in (hist or [])]
    dominio = [str(x) for x in (dominio or [])]
    variantes = []
    for nome, fn in REFORMULADORES:
        try:
            vs = fn(teoria, hist, dominio) or []
            for v in vs:
                v["reformulador"] = nome
                variantes.append(v)
                if len(variantes) >= max_var:
                    return variantes
        except Exception:
            continue
    return variantes
