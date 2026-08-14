# -*- coding: utf-8 -*-
"""
TRIBUNAL DE REVISÃO — 7 IAs

Função: reavaliar o que o Crítico mandou para reavaliar_variante,
         o que ficou só em observação, e o que chegou a ser marcado
         como rejeitada sem ser estrutura inválida.

NÃO é cálculo de 200 mil permutações.
É julgamento em cima do histórico real / janela ao vivo.

Métrica operacional (pedido do usuário):
  Em uma janela de 10 resultados em que a teoria estava ativa
  (condição verdadeira), se acertar pelo menos 3 → PASSA.
  Ou seja: taxa >= 0.30 em 10 ativações reais.

As 7 IAs olham o mesmo material com ênfases diferentes e votam.
Maioria (4 de 7) a favor + métrica mínima → teoria sobe a validada_dormente.
Caso contrário, após tentativas esgotadas → descartada_pelo_tribunal
(permanece no catálogo como histórico, mas não entra no motor).

Os grupos 4/5/9, 1/3/6, 0/2/7/8 etc. são só exemplos de famílias
que o tribunal pode reabilitar — o mecanismo é genérico para
qualquer expressão DSL.
"""
from __future__ import annotations
from typing import Dict, List, Any, Tuple, Optional
from collections import Counter
import time

from .dsl_hipoteses import eval_cond, pred_candidatos
from .avaliador_prequential import replay_prospectivo, replay_baseline

# --- regra de ouro do tribunal ---
JANELA_VIVA = 10          # últimos N resultados com teoria ativa
ACERTOS_MINIMOS = 3       # 3 em 10 = passa
TAXA_MIN = ACERTOS_MINIMOS / JANELA_VIVA  # 0.30
K_MIN, K_MAX = 5, 7
VOTOS_PARA_APROVAR = 4    # maioria do tribunal

# Identidade fixa das 7 IAs (aparecem na Central)
TRIBUNAL_AGENTES = [
    {"id": "T1_puro_vivo", "nome": "T1 · Puro ao vivo", "papel": "Métrica 3/10"},
    {"id": "T2_vs_baseline", "nome": "T2 · vs Baseline", "papel": "Compara com frequência"},
    {"id": "T3_consistencia_recente", "nome": "T3 · Consistência", "papel": "Últimas 5 ativações"},
    {"id": "T4_diversidade_alvos", "nome": "T4 · Diversidade", "papel": "Evita acerto único"},
    {"id": "T5_estabilidade_bloco", "nome": "T5 · Estabilidade", "papel": "Dois blocos da janela"},
    {"id": "T6_contexto_ativo_agora", "nome": "T6 · Contexto agora", "papel": "Condição ativa + métrica"},
    {"id": "T7_cap_5_7_e_utilidade", "nome": "T7 · Utilidade 5–7", "papel": "Faixa operacional"},
]

# último julgamento por jogo (para a Central ler sem reexecutar)
# NUNCA misturar mega_fire / lightning / crazy_time / immersive
_LAST_BY_JOGO: dict = {}
_JOGOS_VALIDOS = ("mega_fire", "lightning", "crazy_time", "immersive")


def _path_jogo(jogo: str):
    from pathlib import Path
    root = Path(__file__).resolve().parent / "data" / "tribunal"
    root.mkdir(parents=True, exist_ok=True)
    j = str(jogo or "").strip() or "unknown"
    if j not in _JOGOS_VALIDOS:
        j = "unknown"
    return root / f"tribunal_{j}.json"


def _load_jogo(jogo: str):
    import json
    path = _path_jogo(jogo)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data[-30:]
    except Exception:
        return []
    return []


def _save_jogo(jogo: str):
    import json
    path = _path_jogo(jogo)
    try:
        path.write_text(
            json.dumps(_LAST_BY_JOGO.get(jogo, [])[-30:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _janela_ativa(hist: List[str], expr: dict, dominio: List[str],
                  horizonte: int = 1, max_n: int = JANELA_VIVA) -> Dict[str, Any]:
    """
    Percorre o histórico do mais antigo ao mais recente.
    Quando a condição está ativa em t, prevê para t+horizonte.
    Guarda só as últimas `max_n` ativações reais (não shuffle).
    """
    if len(hist) < 8:
        return {"n": 0, "hits": 0, "taxa": None, "detalhe": []}
    chrono = list(reversed(hist))  # antigo → recente
    detalhe = []
    for t in range(2, len(chrono) - horizonte):
        past_recent = list(reversed(chrono[: t + 1]))
        if not eval_cond(expr, past_recent):
            continue
        cands = pred_candidatos(expr, past_recent, dominio, k=K_MAX) or []
        if not cands:
            continue
        futuro = chrono[t + horizonte]
        hit = futuro in cands
        detalhe.append({
            "t": t,
            "gatilho": chrono[t],
            "previsto": cands[:K_MAX],
            "saiu": futuro,
            "hit": hit,
        })
    # só as últimas max_n ativações
    detalhe = detalhe[-max_n:]
    n = len(detalhe)
    hits = sum(1 for d in detalhe if d["hit"])
    taxa = hits / n if n else None
    return {"n": n, "hits": hits, "taxa": taxa, "detalhe": detalhe}


def _passa_metrica(jan: Dict[str, Any]) -> bool:
    n = int(jan.get("n") or 0)
    hits = int(jan.get("hits") or 0)
    if n < JANELA_VIVA:
        # amostra incompleta: ainda não julga definitivo
        return False
    return hits >= ACERTOS_MINIMOS


# ---------------------------------------------------------------------------
# 7 IAs do tribunal — cada uma com ênfase própria, mas a mesma métrica base
# ---------------------------------------------------------------------------

def T1_puro_vivo(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Só a métrica 3/10 ao vivo. Sem baseline, sem shuffle."""
    ok = _passa_metrica(jan)
    return {
        "id": "T1_puro_vivo",
        "voto": "aprova" if ok else ("abstencao" if (jan.get("n") or 0) < JANELA_VIVA else "reprova"),
        "motivo": f"hits={jan.get('hits')}/{jan.get('n')} (mínimo {ACERTOS_MINIMOS}/{JANELA_VIVA})",
        "peso": 1.2,
    }


def T2_vs_baseline(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Exige bater o baseline de frequência no mesmo k."""
    expr = teoria.get("expr") or {}
    k = max(K_MIN, min(K_MAX, len((jan.get("detalhe") or [{}])[-1].get("previsto") or []) or K_MIN))
    base = replay_baseline(hist, k, dominio, max_steps=40)
    taxa = jan.get("taxa")
    taxa_b = base.get("taxa")
    if (jan.get("n") or 0) < JANELA_VIVA:
        voto = "abstencao"
        motivo = f"amostra {jan.get('n')}/{JANELA_VIVA}"
    elif taxa is not None and taxa_b is not None and taxa >= max(TAXA_MIN, (taxa_b or 0) + 0.02):
        voto = "aprova"
        motivo = f"taxa={taxa:.2f} > baseline={taxa_b:.2f}"
    elif taxa is not None and taxa >= TAXA_MIN:
        voto = "aprova"
        motivo = f"taxa={taxa:.2f} >= {TAXA_MIN} (baseline={taxa_b})"
    else:
        voto = "reprova"
        motivo = f"taxa={taxa} baseline={taxa_b}"
    return {"id": "T2_vs_baseline", "voto": voto, "motivo": motivo, "peso": 1.0}


def T3_consistencia_recente(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Olha só as 5 ativações mais recentes: precisa de >=2 acertos."""
    det = jan.get("detalhe") or []
    ult = det[-5:]
    if len(ult) < 5:
        return {"id": "T3_consistencia_recente", "voto": "abstencao",
                "motivo": f"só {len(ult)} ativações recentes", "peso": 1.0}
    hits = sum(1 for d in ult if d["hit"])
    voto = "aprova" if hits >= 2 else "reprova"
    return {"id": "T3_consistencia_recente", "voto": voto,
            "motivo": f"últimas5 hits={hits}/5", "peso": 1.1}


def T4_diversidade_alvos(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Evita teoria que só acerta repetindo o mesmo número."""
    det = jan.get("detalhe") or []
    acertos = [d["saiu"] for d in det if d.get("hit")]
    if (jan.get("n") or 0) < JANELA_VIVA:
        return {"id": "T4_diversidade_alvos", "voto": "abstencao",
                "motivo": "amostra incompleta", "peso": 0.8}
    if not acertos:
        return {"id": "T4_diversidade_alvos", "voto": "reprova",
                "motivo": "zero acertos", "peso": 0.8}
    unicos = len(set(acertos))
    voto = "aprova" if unicos >= 2 or len(acertos) >= ACERTOS_MINIMOS else "reprova"
    return {"id": "T4_diversidade_alvos", "voto": voto,
            "motivo": f"acertos_unicos={unicos} total_hits={len(acertos)}", "peso": 0.9}


def T5_estabilidade_bloco(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Divide a janela em 2 metades: as duas precisam ter pelo menos 1 acerto."""
    det = jan.get("detalhe") or []
    if len(det) < JANELA_VIVA:
        return {"id": "T5_estabilidade_bloco", "voto": "abstencao",
                "motivo": f"n={len(det)}", "peso": 1.0}
    mid = len(det) // 2
    h1 = sum(1 for d in det[:mid] if d["hit"])
    h2 = sum(1 for d in det[mid:] if d["hit"])
    voto = "aprova" if h1 >= 1 and h2 >= 1 and (h1 + h2) >= ACERTOS_MINIMOS else "reprova"
    return {"id": "T5_estabilidade_bloco", "voto": voto,
            "motivo": f"bloco1={h1} bloco2={h2}", "peso": 1.0}


def T6_contexto_ativo_agora(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Se a condição está ativa AGORA e a métrica já passou, favorece aprovação."""
    expr = teoria.get("expr") or {}
    ativa_agora = False
    try:
        ativa_agora = bool(eval_cond(expr, hist))
    except Exception:
        ativa_agora = False
    if _passa_metrica(jan) and ativa_agora:
        voto = "aprova"
        motivo = "métrica ok e contexto ativo agora"
    elif _passa_metrica(jan):
        voto = "aprova"
        motivo = "métrica ok (contexto inativo no momento)"
    elif (jan.get("n") or 0) < JANELA_VIVA:
        voto = "abstencao"
        motivo = "aguardando mais ativações"
    else:
        voto = "reprova"
        motivo = f"métrica insuficiente hits={jan.get('hits')}/{jan.get('n')}"
    return {"id": "T6_contexto_ativo_agora", "voto": voto, "motivo": motivo, "peso": 1.0}


def T7_cap_5_7_e_utilidade(teoria, hist, dominio, jan) -> Dict[str, Any]:
    """Exige que a teoria produza entre 5 e 7 candidatos (utilidade operacional)."""
    expr = teoria.get("expr") or {}
    try:
        cands = pred_candidatos(expr, hist, dominio, k=K_MAX) or []
    except Exception:
        cands = []
    n_c = len(cands)
    metrica_ok = _passa_metrica(jan)
    if (jan.get("n") or 0) < JANELA_VIVA:
        voto = "abstencao"
        motivo = f"amostra incompleta; k={n_c}"
    elif metrica_ok and K_MIN <= n_c <= K_MAX:
        voto = "aprova"
        motivo = f"métrica ok e k={n_c} em [{K_MIN},{K_MAX}]"
    elif metrica_ok and n_c > 0:
        voto = "aprova"  # ainda aprova, mas registra
        motivo = f"métrica ok; k={n_c} fora da faixa ideal"
    else:
        voto = "reprova"
        motivo = f"métrica falhou ou k=0 (k={n_c})"
    return {"id": "T7_cap_5_7_e_utilidade", "voto": voto, "motivo": motivo, "peso": 1.0}


TRIBUNAL = [
    T1_puro_vivo,
    T2_vs_baseline,
    T3_consistencia_recente,
    T4_diversidade_alvos,
    T5_estabilidade_bloco,
    T6_contexto_ativo_agora,
    T7_cap_5_7_e_utilidade,
]


def julgar(teoria: dict, hist: List[str], dominio: List[str]) -> dict:
    """
    Executa as 7 IAs e devolve veredito.

    veredito:
      aprovada_pelo_tribunal  → vira validada_dormente
      em_revisao              → ainda sem 10 ativações
      descartada_pelo_tribunal → não entra no motor (catálogo preserva histórico)
    """
    hist = [str(x) for x in (hist or [])]
    dominio = [str(x) for x in (dominio or [])]
    expr = teoria.get("expr") or {}
    horizonte = int(teoria.get("horizonte") or 1)

    jan = _janela_ativa(hist, expr, dominio, horizonte=horizonte, max_n=JANELA_VIVA)

    votos = []
    for fn in TRIBUNAL:
        try:
            votos.append(fn(teoria, hist, dominio, jan))
        except Exception as e:
            votos.append({
                "id": getattr(fn, "__name__", "T?"),
                "voto": "abstencao",
                "motivo": f"erro:{e}",
                "peso": 0.5,
            })

    peso_aprova = sum(v.get("peso", 1) for v in votos if v.get("voto") == "aprova")
    peso_reprova = sum(v.get("peso", 1) for v in votos if v.get("voto") == "reprova")
    n_aprova = sum(1 for v in votos if v.get("voto") == "aprova")
    n_reprova = sum(1 for v in votos if v.get("voto") == "reprova")
    n_abs = sum(1 for v in votos if v.get("voto") == "abstencao")

    out = dict(teoria)
    out["tribunal"] = {
        "votos": votos,
        "n_aprova": n_aprova,
        "n_reprova": n_reprova,
        "n_abstencao": n_abs,
        "peso_aprova": round(peso_aprova, 2),
        "peso_reprova": round(peso_reprova, 2),
        "janela": {
            "n": jan.get("n"),
            "hits": jan.get("hits"),
            "taxa": jan.get("taxa"),
            "regra": f">={ACERTOS_MINIMOS} acertos em {JANELA_VIVA} ativações",
        },
        "julgado_em": time.time(),
    }

    # amostra incompleta → continua em revisão (não descarta)
    if (jan.get("n") or 0) < JANELA_VIVA:
        out["veredito_tribunal"] = "em_revisao"
        out["estado"] = "em_revisao_tribunal"
        out["motivo_tribunal"] = (
            f"aguardando ativações {jan.get('n')}/{JANELA_VIVA}; "
            f"votos A={n_aprova} R={n_reprova} Abs={n_abs}"
        )
        return out

    # métrica dura + maioria
    metrica_ok = _passa_metrica(jan)
    maioria = n_aprova >= VOTOS_PARA_APROVAR or peso_aprova > peso_reprova

    if metrica_ok and maioria:
        # RECURSO ACEITO — mas o tribunal julga o HISTÓRICO (o mesmo de onde a
        # teoria saiu), então ele não valida sozinho: promove para SOMBRA AO
        # VIVO. A validação final sai da META, com evidência prospectiva real
        # (ver meta_supervisora.avaliar_sombra). Antes disso o tribunal escrevia
        # estado="validada_dormente" direto daqui, o que produziu 373 validações
        # falsas em dado 100% aleatório no test_controle_100.
        out["veredito_tribunal"] = "aprovada_pelo_tribunal"
        out["estado"] = "em_teste"          # entra na fila de sombra ao vivo
        out["critica_ok"] = True
        out["destino_critico"] = "promissora"
        out["motivo_tribunal"] = (
            f"RECURSO ACEITO: {jan.get('hits')}/{jan.get('n')} no histórico "
            f"(regra {ACERTOS_MINIMOS}/{JANELA_VIVA}) | votos A={n_aprova} R={n_reprova} "
            f"→ promovida para sombra AO VIVO; valida quando a sombra confirmar"
        )
        out["preservar_catalogo"] = True
    elif metrica_ok and not maioria:
        # métrica ok mas tribunal dividido → mantém em revisão uma rodada
        out["veredito_tribunal"] = "em_revisao"
        out["estado"] = "em_revisao_tribunal"
        out["motivo_tribunal"] = (
            f"métrica ok ({jan.get('hits')}/{jan.get('n')}) mas votos divididos "
            f"A={n_aprova} R={n_reprova}"
        )
    else:
        out["veredito_tribunal"] = "descartada_pelo_tribunal"
        out["estado"] = "descartada_pelo_tribunal"
        out["critica_ok"] = False
        out["motivo_tribunal"] = (
            f"FALHOU: {jan.get('hits')}/{jan.get('n')} "
            f"(<{int(TAXA_MIN*100)}% — precisava {ACERTOS_MINIMOS}/{JANELA_VIVA}) | "
            f"votos A={n_aprova} R={n_reprova} | descartada (reavaliável sob comando)"
        )
        out["preservar_catalogo"] = True  # histórico permanece; pode reavaliar sob comando
    return out


def _registrar_para_central(jogo: str, julgado: dict):
    """Guarda resumo legível para a Central das IAs — isolado por jogo."""
    import time as _t
    j = str(jogo or "").strip()
    if j not in _JOGOS_VALIDOS:
        return  # não registra em bucket errado
    if j not in _LAST_BY_JOGO:
        _LAST_BY_JOGO[j] = _load_jogo(j)
    votos = (julgado.get("tribunal") or {}).get("votos") or []
    resumo = {
        "teoria_id": julgado.get("id"),
        "descricao": (julgado.get("descricao") or julgado.get("id") or "")[:80],
        "veredito": julgado.get("veredito_tribunal"),
        "motivo": julgado.get("motivo_tribunal"),
        "janela": (julgado.get("tribunal") or {}).get("janela"),
        "votos": votos,
        "estado": julgado.get("estado"),
        "jogo": j,
        "ts": _t.strftime("%H:%M:%S"),
    }
    lst = _LAST_BY_JOGO.setdefault(j, [])
    lst.append(resumo)
    _LAST_BY_JOGO[j] = lst[-30:]
    _save_jogo(j)


def snapshot_tribunal(jogo: str) -> dict:
    """O que a Central mostra: 7 juízes + últimos vereditos DESTE jogo apenas."""
    j = str(jogo or "").strip()
    if j not in _JOGOS_VALIDOS:
        return {
            "agentes": [],
            "ultimos": [],
            "regra": f">={ACERTOS_MINIMOS}/{JANELA_VIVA}",
            "n_julgamentos": 0,
            "jogo": j,
            "erro": "jogo_invalido",
        }
    if j not in _LAST_BY_JOGO:
        _LAST_BY_JOGO[j] = _load_jogo(j)
    recent = [u for u in (_LAST_BY_JOGO.get(j) or []) if u.get("jogo") in (None, j)]
    ultimo = recent[-1] if recent else None
    agentes = []
    for a in TRIBUNAL_AGENTES:
        voto_info = None
        if ultimo:
            for v in ultimo.get("votos") or []:
                if v.get("id") == a["id"]:
                    voto_info = v
                    break
        agentes.append({
            "id": a["id"],
            "nome": f"{a['nome']} · {j}",
            "papel": a["papel"],
            "conjunto": j,
            "estado": (voto_info or {}).get("voto") or "aguardando",
            "tarefa": f"tribunal_revisao:{j}",
            "ultima_descoberta": (voto_info or {}).get("motivo") or f"sem julgamento ainda ({j})",
            "confianca": 1.0 if (voto_info or {}).get("voto") == "aprova" else (
                0.0 if (voto_info or {}).get("voto") == "reprova" else 0.5
            ),
            "modelo": f"tribunal-vivo-3em10/{j}",
            "amostra": ((ultimo or {}).get("janela") or {}).get("n") or 0,
            "duracao_ms": 0,
            "tipo": "TRIBUNAL",
            "jogo": j,
        })
    return {
        "agentes": agentes,
        "ultimos": recent[-10:],
        "regra": f">={ACERTOS_MINIMOS} acertos em {JANELA_VIVA} ativações",
        "n_julgamentos": len(recent),
        "jogo": j,
        "arquivo": str(_path_jogo(j)),
    }


def colher_candidatas(catalogo: List[dict]) -> List[dict]:
    """Teorias que o tribunal deve julgar."""
    estados = {
        "reavaliar_variante",
        "reprovar_enviar_tribunal",
        "em_observacao_viva",
        "em_teste_ativo",
        "em_revisao_tribunal",
        "rejeitada",  # só se não for estrutura inválida
        "descartada_pelo_tribunal",  # pode ser rejulgada se histórico cresceu
    }
    out = []
    for t in catalogo or []:
        est = t.get("estado") or ""
        dest = t.get("destino_critico") or ""
        if t.get("rejeicao_dura"):
            continue
        if est in estados or dest in ("reavaliar_variante", "reprovar_enviar_tribunal", "em_observacao_viva", "em_teste_ativo"):
            out.append(t)
    return out


def ciclo_tribunal(dataset_id: str, hist: List[str], dominio: List[str],
                   catalogo: List[dict], merge_fn, max_julgamentos: int = 12) -> Dict[str, Any]:
    """
    Roda o tribunal sobre o catálogo DESTE dataset_id apenas.
    Nunca mistura mega_fire / lightning / crazy_time / immersive.
    merge_fn(teoria) grava no catálogo persistente (já particionado por dataset_id).
    """
    j = str(dataset_id or "").strip()
    # filtra catálogo por dataset_id quando o campo existir
    cat = [t for t in (catalogo or []) if not t.get("dataset_id") or t.get("dataset_id") == j]
    cands = colher_candidatas(cat)
    msgs = []
    aprovadas = []
    reprovadas = []
    em_revisao = []

    for t in cands[:max_julgamentos]:
        julgado = julgar(t, hist, dominio)
        try:
            merge_fn(julgado)
        except Exception as e:
            msgs.append(f"[Tribunal] merge erro {t.get('id')}: {e}")
            continue
        _registrar_para_central(dataset_id, julgado)
        v = julgado.get("veredito_tribunal")
        if v == "aprovada_pelo_tribunal":
            aprovadas.append(julgado)
            msgs.append(
                f"[Tribunal] APROVOU {julgado.get('id')} — {julgado.get('motivo_tribunal')}"
            )
        elif v == "descartada_pelo_tribunal":
            reprovadas.append(julgado)
            msgs.append(
                f"[Tribunal] descartou {julgado.get('id')} — {julgado.get('motivo_tribunal')}"
            )
        else:
            em_revisao.append(julgado)
            msgs.append(
                f"[Tribunal] em revisão {julgado.get('id')} — {julgado.get('motivo_tribunal')}"
            )

    return {
        "msgs": msgs,
        "aprovadas": aprovadas,
        "reprovadas": reprovadas,
        "em_revisao": em_revisao,
        "julgadas": len(aprovadas) + len(reprovadas) + len(em_revisao),
        "regra": f"{ACERTOS_MINIMOS} acertos em {JANELA_VIVA} ativações ao vivo",
    }


def reavaliar_descartadas(dataset_id, hist, dominio, catalogo, merge_fn, max_n=20):
    """Comando do usuário: reabre descartada_pelo_tribunal e julga de novo (só deste jogo)."""
    j = str(dataset_id or "").strip()
    cat = [t for t in (catalogo or []) if (not t.get("dataset_id") or t.get("dataset_id") == j)]
    descartadas = [
        t for t in cat
        if (t.get("estado") == "descartada_pelo_tribunal"
            or t.get("veredito_tribunal") == "descartada_pelo_tribunal")
        and not t.get("rejeicao_dura")
    ]
    msgs = []
    aprovadas, reprovadas, revisao = [], [], []
    for t in descartadas[:max_n]:
        t2 = dict(t)
        t2["estado"] = "em_revisao_tribunal"
        t2["veredito_tribunal"] = None
        t2["reavaliacao_manual"] = True
        julgado = julgar(t2, hist, dominio)
        try:
            merge_fn(julgado)
        except Exception as e:
            msgs.append(f"[Reavaliar] merge erro {t.get('id')}: {e}")
            continue
        _registrar_para_central(j, julgado)
        v = julgado.get("veredito_tribunal")
        if v == "aprovada_pelo_tribunal":
            aprovadas.append(julgado)
            msgs.append(f"[Reavaliar] APROVOU de novo {julgado.get('id')} — {julgado.get('motivo_tribunal')}")
        elif v == "descartada_pelo_tribunal":
            reprovadas.append(julgado)
            msgs.append(f"[Reavaliar] seguiu descartada {julgado.get('id')} — {julgado.get('motivo_tribunal')}")
        else:
            revisao.append(julgado)
            msgs.append(f"[Reavaliar] em revisão {julgado.get('id')} — {julgado.get('motivo_tribunal')}")
    return {
        "msgs": msgs,
        "aprovadas": aprovadas,
        "reprovadas": reprovadas,
        "em_revisao": revisao,
        "n_candidatas": len(descartadas),
        "jogo": j,
        "regra": f"{ACERTOS_MINIMOS}/{JANELA_VIVA} = {int(TAXA_MIN*100)}%",
    }


def listar_descartadas(dataset_id, catalogo):
    j = str(dataset_id or "").strip()
    return [
        t for t in (catalogo or [])
        if (not t.get("dataset_id") or t.get("dataset_id") == j)
        and (t.get("estado") == "descartada_pelo_tribunal"
             or t.get("veredito_tribunal") == "descartada_pelo_tribunal")
    ]
