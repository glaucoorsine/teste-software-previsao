# -*- coding: utf-8 -*-
"""
CRÍTICO ATIVO — não é só observador.

Papel:
1. Testa a teoria no HISTÓRICO real (replay prospectivo).
2. Mede acertos quando a condição estava ativa.
3. Decide de forma operativa:
   - APROVA (≥30% com amostra mínima) → sobe para META / sombra / uso
   - REPROVA (<30% com amostra completa) → vai ao Tribunal ou descarte reavaliável
   - REFORMULAR (estrutura ok mas fraca/instável) → R1–R7
   - ESTRUTURA INVÁLIDA → rejeição dura

NÃO descarta só porque shuffle/p-valor foi alto.
NÃO fica parado “observando” sem veredito quando já há amostra.

Limite operacional: 5 a 7 números.
"""
from __future__ import annotations
import random
import time
from typing import Dict, List, Any
from .avaliador_prequential import replay_prospectivo, replay_baseline
from .dsl_hipoteses import pred_candidatos, eval_cond

K_MIN, K_MAX = 5, 7
# mesma régua do tribunal (pedido do usuário)
JANELA_MIN = 10
ACERTOS_MIN = 3          # 3/10 = 30%
TAXA_APROVA = 0.30
TAXA_REPROVA = 0.30      # abaixo de 30% com janela cheia → reprova
N_PERM_SINAL = 20        # p-valor só como sinal auxiliar


def _p_valor_emp(obs: float, nula: List[float], maior_melhor: bool = True) -> float:
    if not nula:
        return 1.0
    if maior_melhor:
        extreme = sum(1 for x in nula if x >= obs - 1e-12)
    else:
        extreme = sum(1 for x in nula if x <= obs + 1e-12)
    return (extreme + 1) / (len(nula) + 1)


def fdr_bh(p_values: List[float], alpha: float = 0.10) -> List[float]:
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    q = [1.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i, p = indexed[rank - 1]
        val = min(prev, p * m / rank)
        prev = val
        q[i] = min(1.0, val)
    return q


def _estrutura_ok(expr: dict, dominio: List[str]):
    if not isinstance(expr, dict) or not expr:
        return False, "expr_vazia"
    if not (expr.get("op") or expr.get("tipo")):
        return False, "sem_operador"
    if not dominio:
        return False, "dominio_vazio"
    return True, "ok"


def _k_operacional(expr, hist, dominio) -> int:
    try:
        c = pred_candidatos(expr, hist, dominio, k=K_MAX) or []
    except Exception:
        c = []
    n = len(c)
    if n <= 0:
        return 0
    return max(K_MIN, min(K_MAX, n)) if n >= K_MIN else n


def _janela_viva(hist, expr, dominio, horizonte=1, max_n=JANELA_MIN):
    """Últimas ativações reais no histórico (mesmo critério do tribunal)."""
    if len(hist) < 8:
        return {"n": 0, "hits": 0, "taxa": None}
    chrono = list(reversed(hist))
    det = []
    for t in range(2, len(chrono) - horizonte):
        past = list(reversed(chrono[: t + 1]))
        if not eval_cond(expr, past):
            continue
        cands = pred_candidatos(expr, past, dominio, k=K_MAX) or []
        if not cands:
            continue
        fut = chrono[t + horizonte]
        det.append(fut in cands)
    det = det[-max_n:]
    n = len(det)
    hits = sum(1 for x in det if x)
    return {"n": n, "hits": hits, "taxa": (hits / n if n else None)}


def revisar(teoria: dict, hist: List[str], dominio: List[str], n_perm: int = N_PERM_SINAL) -> dict:
    """
    Veredito ATIVO do crítico.
    """
    out = dict(teoria)
    expr = out.get("expr") or {}
    hist = [str(x) for x in (hist or [])]
    dominio = [str(x) for x in (dominio or [])]

    ok_est, mot_est = _estrutura_ok(expr, dominio)
    if not ok_est:
        out.update({
            "critica_ok": False,
            "destino_critico": "estrutura_invalida",
            "veredito_critico": "REPROVA_ESTRUTURA",
            "motivo_critica": mot_est,
            "rejeicao_dura": True,
        })
        return out

    horizonte = int(out.get("horizonte") or 1)
    # 1) teste histórico forte
    rep = replay_prospectivo(hist, expr, dominio, horizonte=horizonte, max_steps=100)
    k = _k_operacional(expr, hist, dominio)
    base = replay_baseline(hist, max(k, K_MIN) if k else K_MIN, dominio, max_steps=80) if k else {"taxa": None, "n": 0}
    taxa = rep.get("taxa")
    taxa_b = base.get("taxa")
    ganho = (taxa - taxa_b) if (taxa is not None and taxa_b is not None) else None

    # 2) janela viva 10 (mesma régua 3/10)
    jan = _janela_viva(hist, expr, dominio, horizonte=horizonte, max_n=JANELA_MIN)

    # 3) p-valor só como sinal
    seed = abs(hash(str(out.get("id") or expr))) & 0xFFFFFFFF
    rng = random.Random(seed)
    nulas = []
    for _ in range(max(5, n_perm)):
        hs = hist[:]
        rng.shuffle(hs)
        r = replay_prospectivo(hs, expr, dominio, horizonte=horizonte, max_steps=40)
        nulas.append(r.get("taxa") if r.get("taxa") is not None else 0.0)
    p = _p_valor_emp(taxa if taxa is not None else 0.0, nulas, maior_melhor=True)

    n_rep = int(rep.get("n") or 0)
    n_jan = int(jan.get("n") or 0)
    hits_jan = int(jan.get("hits") or 0)
    taxa_jan = jan.get("taxa")

    sinais = []
    sinais.append(f"replay n={n_rep} taxa={None if taxa is None else round(taxa, 3)}")
    sinais.append(f"janela {hits_jan}/{n_jan}")
    if ganho is not None:
        sinais.append(f"ganho_vs_base={ganho:+.3f}")
    sinais.append(f"p_nulo={p:.3f} (sinal)")

    # utilidade: precisa gerar 5–7 candidatos quando ativa
    cands_agora = []
    try:
        if eval_cond(expr, hist):
            cands_agora = pred_candidatos(expr, hist, dominio, k=K_MAX) or []
    except Exception:
        cands_agora = []
    if cands_agora:
        sinais.append(f"k_agora={len(cands_agora)}")

    # ---- VEREDITO ATIVO ----
    critica_ok = False
    rejeicao_dura = False
    destino = "reavaliar_variante"
    veredito = "REFORMULAR"

    # A) amostra completa na janela viva → decide por 30%
    if n_jan >= JANELA_MIN:
        if hits_jan >= ACERTOS_MIN:
            critica_ok = True
            destino = "promissora"
            veredito = "APROVA"
            sinais.append(f"APROVA: {hits_jan}/{n_jan} >= {ACERTOS_MIN}/{JANELA_MIN} (30%)")
        else:
            critica_ok = False
            destino = "reprovar_enviar_tribunal"
            veredito = "REPROVA"
            sinais.append(
                f"REPROVA: {hits_jan}/{n_jan} < 30% — envia ao Tribunal/descarte reavaliável"
            )
    # B) replay histórico já tem amostra e taxa clara
    elif n_rep >= JANELA_MIN and taxa is not None:
        if taxa >= TAXA_APROVA and (ganho is None or ganho >= -0.02):
            critica_ok = True
            destino = "promissora"
            veredito = "APROVA"
            sinais.append(f"APROVA por replay histórico taxa={taxa:.2f}")
        elif taxa < TAXA_REPROVA:
            critica_ok = False
            destino = "reprovar_enviar_tribunal"
            veredito = "REPROVA"
            sinais.append(f"REPROVA por replay histórico taxa={taxa:.2f}")
        else:
            destino = "reavaliar_variante"
            veredito = "REFORMULAR"
            sinais.append("zona intermediária → reformular")
    # C) amostra ainda curta: se já mostra ganho forte, aprova provisório; senão reformula
    else:
        if n_rep >= 5 and taxa is not None and taxa >= 0.40 and ganho is not None and ganho > 0.05:
            critica_ok = True
            destino = "promissora"
            veredito = "APROVA_PROVISORIA"
            sinais.append("APROVA provisória (amostra curta mas forte)")
        elif k == 0:
            destino = "reavaliar_variante"
            veredito = "REFORMULAR"
            sinais.append("sem candidatos operacionais (k=0)")
        else:
            destino = "em_teste_ativo"
            veredito = "TESTAR_AGORA"
            sinais.append(
                f"amostra insuficiente ({n_jan}/{JANELA_MIN}) — manda para teste ativo/sombra, não fica parado"
            )
            # crítico ATIVO: empurra para teste, não para limbo eterno
            critica_ok = False

    out["critica_ok"] = critica_ok
    out["rejeicao_dura"] = rejeicao_dura
    out["destino_critico"] = destino
    out["veredito_critico"] = veredito
    out["motivo_critica"] = "; ".join(sinais)
    out["teste_negativo"] = {
        "p_valor_emp": round(p, 4),
        "n_perm": n_perm,
        "papel": "sinal_auxiliar",
        "nao_e_veredito_sozinho": True,
    }
    out["retrospectivo"] = {
        "replay": rep,
        "baseline": base,
        "ganho": ganho,
        "k_operacional": k,
        "janela_viva": jan,
    }
    out["candidatos_agora"] = cands_agora[:K_MAX]
    out["preservar_catalogo"] = True
    if not out.get("primeira_observacao_ts"):
        out["primeira_observacao_ts"] = time.time()
    return out


def aplicar_fdr_batch(teorias: List[dict]) -> List[dict]:
    """FDR anota lote; NÃO derruba APROVA do crítico sozinho."""
    ps = []
    for t in teorias:
        tn = t.get("teste_negativo") or {}
        ps.append(float(tn.get("p_valor_emp") if tn.get("p_valor_emp") is not None else 1.0))
    qs = fdr_bh(ps, alpha=0.15)
    out = []
    for t, q in zip(teorias, qs):
        t2 = dict(t)
        t2["q_valor"] = round(q, 4)
        out.append(t2)
    return out
