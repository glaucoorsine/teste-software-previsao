# -*- coding: utf-8 -*-
"""
A6 — o aplicador com raciocínio de linguagem.

Consulta o LLM configurado em `llm_config.json` (Grok/xAI, OpenAI ou Ollama
local) e pede uma leitura do que está acontecendo AGORA na mesa: quais teorias
cabíveis fazem sentido neste contexto e em que números elas convergem.

POR QUE ELE NÃO TEM STATUS ESPECIAL
-----------------------------------
Um LLM é excelente em construir explicação plausível — inclusive quando não há
o que explicar. Dado um punhado de giros aleatórios, ele acha o padrão, narra
com segurança e soa convincente. É exatamente o modo de falha que a sombra
prospectiva, o FDR e a comparação com a régua existem para pegar.

Por isso A6 vota como as outras cinco lentes e é medido do mesmo jeito. Ele não
decide sozinho, não tem poder de veto, e o voto dele só vale se sobreviver à
mesma régua de frequência que todo mundo enfrenta.

`teste_a6_ruido.py` alimenta esta lente com sequência aleatória e mede quantas
vezes ela AFIRMA ver padrão. Uma lente que enxerga sinal em ruído tem o voto
descontado por construção.

SEGURANÇA DE FUNCIONAMENTO
--------------------------
Sem chave de API, sem rede, timeout, resposta malformada ou número fora do
domínio: a lente simplesmente NÃO VOTA. Nunca derruba o ciclo, nunca inventa
número que não existe na mesa.
"""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Optional

TIMEOUT_S = 12
MAX_TEORIAS_NO_PROMPT = 25
MAX_GIROS_NO_PROMPT = 30

INSTRUCAO = """Você analisa uma mesa de cassino ao vivo. Responda SÓ com JSON.

Recebe: os últimos giros (o primeiro é o mais recente) e as teorias que se
aplicam a este momento, cada uma com o desempenho recente dela ao vivo.

Sua tarefa: dizer em quais números as teorias que fazem sentido AGORA convergem.

REGRAS:
- Se você não enxergar nada claro, devolva "numeros": []. Lista vazia é uma
  resposta legítima e frequentemente a correta. Sequência aleatória não tem
  padrão, e afirmar que tem é erro grave.
- No máximo 7 números, e apenas valores que existam no domínio informado.
- "confianca" de 0 a 1: quanto você realmente acredita, não quanto quer acertar.
- "motivo": uma frase curta e concreta.

Formato exato:
{"numeros": ["12","5"], "confianca": 0.4, "motivo": "..."}"""


def _cfg():
    try:
        from ia_chat_llm import load_cfg
        return load_cfg(apply_env=True)
    except Exception:
        return {}


def disponivel() -> bool:
    c = _cfg()
    if (c.get("provider") or "").lower() == "ollama":
        return bool(c.get("ollama_url"))
    return bool(c.get("api_key"))


def _resumo_teoria(t: dict, nums: List[str]) -> Optional[dict]:
    p = t.get("prospectivo") or {}
    h = [e for e in (p.get("hist") or []) if isinstance(e, dict)]
    rec = h[-10:]
    if not nums:
        return None
    d = {
        "aposta_em": nums[:7],
        "descricao": str(t.get("descricao") or "")[:70],
        "vida_toda": f"{p.get('hits', 0)}/{p.get('n', 0)}",
    }
    if rec:
        acertos = sum(1 for e in rec if e.get("hit"))
        d["ultimas"] = f"{acertos}/{len(rec)}"
        marc = [e for e in rec if "baseline_hit" in e]
        if marc:
            reg = sum(1 for e in marc if e.get("baseline_hit"))
            d["regua_nas_mesmas"] = f"{reg}/{len(marc)}"
    return d


def _extrai_json(txt: str) -> Optional[dict]:
    if not txt:
        return None
    m = re.search(r"\{[^{}]*\"numeros\"[^{}]*\}", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def opinar(hist: List[str], dominio: List[str], cabiveis: List[dict],
           pred_fn, k: int = 7) -> Dict[str, Any]:
    """
    Devolve {"numeros": [...], "confianca": float, "motivo": str, "erro": str|None}.
    Em qualquer problema, devolve numeros=[] — nunca levanta exceção.
    """
    vazio = {"numeros": [], "confianca": 0.0, "motivo": "", "erro": None}
    if not disponivel():
        return {**vazio, "erro": "sem chave de API configurada"}
    if not hist or not cabiveis:
        return {**vazio, "erro": "nada para analisar"}

    dom = [str(x) for x in dominio]
    resumos = []
    for t in cabiveis[:MAX_TEORIAS_NO_PROMPT]:
        try:
            nums = [str(x) for x in (pred_fn(t.get("expr") or {}, hist, dom, k=k) or [])]
        except Exception:
            continue
        r = _resumo_teoria(t, nums)
        if r:
            resumos.append(r)
    if not resumos:
        return {**vazio, "erro": "nenhuma teoria com alvo"}

    payload = {
        "ultimos_giros": [str(x) for x in hist[:MAX_GIROS_NO_PROMPT]],
        "dominio": dom,
        "teorias_aplicaveis_agora": resumos,
    }

    try:
        from ia_chat_llm import chamar_llm  # type: ignore
        txt = chamar_llm(INSTRUCAO, json.dumps(payload, ensure_ascii=False),
                         timeout=TIMEOUT_S)
    except ImportError:
        txt = _chamada_direta(INSTRUCAO, json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        return {**vazio, "erro": f"{type(e).__name__}: {str(e)[:60]}"}

    if not txt:
        return {**vazio, "erro": "resposta vazia"}
    d = _extrai_json(txt if isinstance(txt, str) else str(txt))
    if not isinstance(d, dict):
        return {**vazio, "erro": "resposta sem JSON válido"}

    nums, vistos = [], set()
    for x in (d.get("numeros") or [])[:k]:
        s = str(x).strip()
        if s in dom and s not in vistos:      # fora do domínio é descartado
            vistos.add(s)
            nums.append(s)
    try:
        conf = max(0.0, min(1.0, float(d.get("confianca", 0))))
    except Exception:
        conf = 0.0
    return {"numeros": nums, "confianca": conf,
            "motivo": str(d.get("motivo") or "")[:160], "erro": None}


def _chamada_direta(sistema: str, usuario: str) -> Optional[str]:
    """Fallback: fala com o provedor sem depender de helper do ia_chat_llm."""
    try:
        import requests
    except Exception:
        return None
    c = _cfg()
    prov = (c.get("provider") or "xai").lower()
    msgs = [{"role": "system", "content": sistema},
            {"role": "user", "content": usuario}]
    try:
        if prov == "ollama":
            r = requests.post(f"{c.get('ollama_url')}/api/chat",
                              json={"model": c.get("ollama_model"), "messages": msgs,
                                    "stream": False},
                              timeout=TIMEOUT_S)
            r.raise_for_status()
            return (r.json().get("message") or {}).get("content")
        base = c.get("openai_base_url") if prov == "openai" else c.get("base_url")
        r = requests.post(f"{base}/chat/completions",
                          headers={"Authorization": f"Bearer {c.get('api_key')}",
                                   "Content-Type": "application/json"},
                          json={"model": c.get("model"), "messages": msgs,
                                "temperature": float(c.get("temperature", 0.4))},
                          timeout=TIMEOUT_S)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
