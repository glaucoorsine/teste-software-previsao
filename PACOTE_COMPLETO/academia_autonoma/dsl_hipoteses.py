# -*- coding: utf-8 -*-
"""
DSL de hipóteses — JSON/AST.
Agentes combinam operadores; não executam Python arbitrário.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence

# Operadores permitidos na DSL
OPS = {
    "lag", "count_in_window", "gap_since", "run_length", "transition",
    "subseq", "cooccur", "window_diff", "regime_flag", "similar_state",
    "and", "or", "not", "threshold", "in_set", "last_is", "final_in",
}

def sha_expr(expr: dict) -> str:
    raw = json.dumps(expr, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def expr_id(expr: dict, dominio: str, horizonte: int, janela: int) -> str:
    payload = {"expr": expr, "dom": dominio, "h": horizonte, "w": janela}
    return sha_expr(payload)[:24]

def legivel(expr: dict) -> str:
    if not expr:
        return "(vazio)"
    op = expr.get("op")
    if op == "last_is":
        return f"último={expr.get('valor')}"
    if op == "transition":
        return f"após {expr.get('a')} → tende {expr.get('b')}"
    if op == "count_in_window":
        return f"contagem({expr.get('valor')})≥{expr.get('k')} em w={expr.get('w')}"
    if op == "gap_since":
        return f"gap({expr.get('valor')})≥{expr.get('min_gap')}"
    if op == "run_length":
        return f"corrida de {expr.get('valor')} ≥{expr.get('min_run')}"
    if op == "subseq":
        return f"subseq {expr.get('seq')}"
    if op == "cooccur":
        return f"coocorrência {expr.get('set')} em w={expr.get('w')}"
    if op == "and":
        return " E ".join(legivel(x) for x in expr.get("args") or [])
    if op == "or":
        return " OU ".join(legivel(x) for x in expr.get("args") or [])
    if op == "not":
        return f"NÃO({legivel(expr.get('arg') or {})})"
    if op == "window_diff":
        return f"freq_curta>freq_longa ({expr.get('valor')})"
    if op == "in_set":
        return f"em {{{','.join(map(str, expr.get('set') or []))}}}"
    if op == "final_in":
        return f"finais {{{','.join(map(str, expr.get('finais') or []))}}}"
    return json.dumps(expr, ensure_ascii=False)

def _vals(eventos: Sequence) -> List[str]:
    out = []
    for e in eventos:
        if hasattr(e, "valor"):
            out.append(str(e.valor))
        else:
            out.append(str(e))
    return out

def _int(v, default: int) -> int:
    """Conversão defensiva: expr vindo de fonte externa/corrompida não deve
    derrubar o avaliador inteiro por causa de um campo numérico não-numérico."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def eval_cond(expr: dict, hist_recent_first: List[str]) -> bool:
    """Avalia condição no histórico (index 0 = mais recente)."""
    h = hist_recent_first
    if not expr or not h:
        return False
    op = expr.get("op")
    if op == "last_is":
        return h[0] == str(expr.get("valor"))
    if op == "in_set":
        return h[0] in set(map(str, expr.get("set") or []))
    if op == "final_in":
        fins = {str(x) for x in (expr.get("finais") or [])}
        try:
            return str(h[0])[-1] in fins
        except Exception:
            return False
    if op == "transition":
        # Convenção: h[0] = evento mais recente (gatilho "a").
        # O avaliador monta past_recent incluindo o passo atual em h[0]
        # e compara pred_candidatos contra chrono[t+horizonte].
        # Usar h[1] deslocava a avaliação em um passo (taxa → 0 no prospectivo).
        if not h:
            return False
        return h[0] == str(expr.get("a"))
    if op == "count_in_window":
        w = _int(expr.get("w"), 10)
        k = _int(expr.get("k"), 2)
        v = str(expr.get("valor"))
        return h[:w].count(v) >= k
    if op == "gap_since":
        v = str(expr.get("valor"))
        min_gap = _int(expr.get("min_gap"), 10)
        try:
            gap = h.index(v)
        except ValueError:
            gap = len(h)
        return gap >= min_gap
    if op == "run_length":
        v = str(expr.get("valor"))
        min_run = _int(expr.get("min_run"), 2)
        run = 0
        for x in h:
            if x == v:
                run += 1
            else:
                break
        return run >= min_run
    if op == "subseq":
        seq = [str(x) for x in (expr.get("seq") or [])]
        if len(seq) < 2 or len(h) < len(seq):
            return False
        # seq no passado recente invertido: h[len-1]... corresponde ordem temporal antiga→nova
        # verificamos se h[1:1+len] matches seq reversed (seq é antiga→nova)
        trecho = list(reversed(h[1:1+len(seq)]))
        return trecho == seq
    if op == "cooccur":
        w = _int(expr.get("w"), 8)
        sset = set(map(str, expr.get("set") or []))
        return len(sset & set(h[:w])) >= max(2, len(sset) - 1)
    if op == "window_diff":
        v = str(expr.get("valor"))
        wc = _int(expr.get("w_curta"), 12)
        wl = _int(expr.get("w_longa"), 40)
        if len(h) < wl:
            return False
        fc = h[:wc].count(v) / max(wc, 1)
        fl = h[:wl].count(v) / max(wl, 1)
        try:
            margem = float(expr.get("margem") or 0.05)
        except (TypeError, ValueError):
            margem = 0.05
        return fc > fl + margem
    if op == "and":
        return all(eval_cond(a, h) for a in (expr.get("args") or []))
    if op == "or":
        return any(eval_cond(a, h) for a in (expr.get("args") or []))
    if op == "not":
        return not eval_cond(expr.get("arg") or {}, h)
    if op == "threshold":
        # genérico: count_in_window embutido
        return eval_cond(expr.get("arg") or {}, h)
    return False

def pred_candidatos(expr: dict, hist_recent_first: List[str], dominio: List[str], k: int = 5) -> List[str]:
    """Dado contexto ativo, devolve candidatos experimentais."""
    if not expr:
        return []
    op = expr.get("op")
    h = hist_recent_first or []
    if op == "transition":
        b = str(expr.get("b"))
        return [b] if b in dominio else []
    if op == "run_length":
        v = str(expr.get("valor"))
        return [v] if v in dominio else []
    if op == "subseq":
        seq = [str(x) for x in (expr.get("seq") or [])]
        return [seq[-1]] if seq and seq[-1] in dominio else []
    if op == "cooccur":
        s = [x for x in (expr.get("set") or []) if str(x) in dominio]
        recent = set(h[:3])
        return [x for x in s if x not in recent][:k] or s[:k]
    if op == "in_set":
        s = [x for x in (expr.get("set") or []) if str(x) in dominio]
        return s[:k]
    if op == "final_in":
        fins = {str(x) for x in (expr.get("finais") or [])}
        kk = int(expr.get("k") or k)
        kk = max(5, min(7, kk))
        out = []
        for x in list(h[:40]) + list(dominio):
            xs = str(x)
            if xs in dominio and xs[-1] in fins and xs not in out:
                out.append(xs)
            if len(out) >= kk:
                break
        return out[:kk]
    if op == "count_in_window":
        v = str(expr.get("valor"))
        return [v] if v in dominio else []
    if op == "gap_since":
        v = str(expr.get("valor"))
        return [v] if v in dominio else []
    if op == "window_diff":
        v = str(expr.get("valor"))
        return [v] if v in dominio else []
    if op == "and":
        # união dos candidatos dos args
        out = []
        for a in expr.get("args") or []:
            for c in pred_candidatos(a, h, dominio, k):
                if c not in out:
                    out.append(c)
        return out[:k]
    if op == "or":
        out = []
        for a in expr.get("args") or []:
            for c in pred_candidatos(a, h, dominio, k):
                if c not in out:
                    out.append(c)
        return out[:k]
    # fallback: não prevê
    return []

def make_hipotese(expr: dict, agente: str, dataset_id: str, dominio: str,
                  janela: int, horizonte: int = 1, descricao: str = "") -> dict:
    eid = expr_id(expr, dominio, horizonte, janela)
    return {
        "id": eid,
        "versao": 1,
        "autor": agente,
        "dataset_id": dataset_id,
        "dominio": dominio,
        "expr": expr,
        "descricao": descricao or legivel(expr),
        "janela": janela,
        "horizonte": horizonte,
        "estado": "candidata",
        "ativacao": "SEM_EVIDÊNCIA",
        "evidencia": {},
        "baseline": {},
        "retrospectivo": {},
        "prospectivo": {"n": 0, "hits": 0, "misses": 0, "taxa": None, "hist": []},
        "teste_negativo": {},
        "criado_em": None,
        "atualizado_em": None,
        "episodios_ativacao": [],
        "versoes_anteriores": [],
    }
