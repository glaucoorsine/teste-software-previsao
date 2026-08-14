# -*- coding: utf-8 -*-
"""
COLETOR DOS SITES — histórico profundo, direto das fontes que o operador usa.

De onde saiu cada endereço deste arquivo: da sonda TESTAR_FONTES, rodada na
máquina do operador, e da leitura do JavaScript das próprias páginas. Nada aqui
foi adivinhado.

O QUE CADA FONTE ENTREGA (medido, não suposto)
---------------------------------------------
casinotrackpot  -> a API que a página dele chama, aberta, com a SEQUÊNCIA:
                   até 1000 rodadas em 72 h, cada uma com o número sorteado e
                   os lucky numbers com multiplicador. É a fonte que importa.
tracksino       -> a página traz um bloco JSON com AGREGADOS (quantas vezes
                   cada número saiu, quantas vezes foi lucky, multiplicador
                   médio, há quantos giros não aparece). Não traz a sequência:
                   a tabela do site é preenchida por JavaScript chamando uma
                   API que responde 403 sem token.
gamblingcounting-> respondeu 403 (Cloudflare) nas quatro páginas. Fica
                   registrado como indisponível, não como erro do software.

POR QUE OS AGREGADOS VALEM MESMO SEM A ORDEM
--------------------------------------------
Eles não servem para transição nem janela — isso exige sequência. Mas trazem
4.746 premiações medidas em 1.766 giros, amostra que a coleta ao vivo levaria
semanas para juntar, e respondem duas perguntas sozinhas: se algum número é
escolhido lucky mais do que devia, e se o multiplicador médio varia entre
números. Ambas são sobre o gerador, não sobre a bola.

REGRA QUE NÃO SE QUEBRA
-----------------------
Giro sem horário não entra na sequência. Todo o estudo mede ordem; um número
sem carimbo de tempo é jogado numa posição indefinida e embaralha justamente o
que se está medindo. Quando a fonte não datar o giro, ele fica de fora.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:                                    # pragma: no cover
    requests = None

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
TIMEOUT = 25

# --- a sequência (o que interessa de verdade)
SEQUENCIA = {
    "lightning": "https://api.trackpotapi.com/api/trackersino/lightningroulette/history",
    "immersive": "https://api.trackpotapi.com/api/trackersino/immersive-roulette/history",
}
PARAMS_SEQ = {"window": "72h", "limit": 1000}

# --- os agregados de multiplicador
AGREGADOS = {
    "lightning": "https://www.tracksino.com/lightning-roulette",
    "crazy_time": "https://www.tracksino.com/crazytime",
}

CAMPOS_TEMPO = ("finalized_at", "observed_at", "time_spin_stop", "timestamp",
                "occured_at", "occurred_at", "created_at", "settled_at")


def _num(row: dict) -> Optional[int]:
    """O número sorteado. A cascata é a mesma que o site usa no getNumber()."""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    raw2 = raw.get("raw") if isinstance(raw.get("raw"), dict) else {}
    for fonte in (row, raw, raw2):
        for c in ("result", "number", "random_number", "slot_result"):
            v = fonte.get(c)
            if v is None:
                continue
            try:
                n = int(str(v).strip())
            except (TypeError, ValueError):
                continue
            if 0 <= n <= 36:
                return n
    return None


def _quando(row: dict) -> Optional[str]:
    """Carimbo ISO em UTC. Sem isto o giro não entra."""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    for fonte in (row, raw):
        for c in CAMPOS_TEMPO:
            v = fonte.get(c)
            if v in (None, ""):
                continue
            # epoch em segundos ou milissegundos
            if isinstance(v, (int, float)) or str(v).isdigit():
                try:
                    t = float(v)
                except (TypeError, ValueError):
                    continue
                if t > 1e11:
                    t /= 1000.0
                if t < 1e9:
                    continue
                return datetime.fromtimestamp(t, timezone.utc).isoformat()
            s = str(v).strip().replace("Z", "+00:00")
            try:
                d = datetime.fromisoformat(s)
            except ValueError:
                continue
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc).isoformat()
    return None


def _luckies(row: dict) -> List[dict]:
    """A rodada de multiplicadores: [{'n': 17, 'x': 150}, ...]"""
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    lista = (row.get("lightning_numbers") or raw.get("lightning_numbers")
             or row.get("lucky_numbers") or raw.get("lucky_numbers") or [])
    out = []
    for it in lista if isinstance(lista, list) else []:
        if not isinstance(it, dict):
            continue
        try:
            n = int(it.get("num", it.get("number")))
            x = it.get("multi", it.get("multiplier"))
            out.append({"n": n, "x": int(x) if x else None})
        except (TypeError, ValueError):
            continue
    return out


def buscar_sequencia(jogo: str) -> Tuple[List[dict], Optional[str]]:
    """Giros com horário e multiplicadores, prontos para o buffer."""
    url = SEQUENCIA.get(jogo)
    if not url:
        return [], "sem endpoint de sequência para este jogo"
    if requests is None:
        return [], "biblioteca requests ausente"
    try:
        r = requests.get(url, params=PARAMS_SEQ, headers=CABECALHO, timeout=TIMEOUT)
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:70]}"
    if r.status_code != 200:
        return [], f"HTTP {r.status_code}"
    try:
        d = r.json()
    except ValueError:
        return [], "resposta não é JSON"

    itens = d
    if isinstance(d, dict):
        for c in ("data", "rounds", "results", "history", "items", "rows"):
            if isinstance(d.get(c), list):
                itens = d[c]
                break
        else:
            itens = []
    if not isinstance(itens, list):
        return [], "formato inesperado"

    linhas, sem_hora = [], 0
    for it in itens:
        if not isinstance(it, dict):
            continue
        n = _num(it)
        q = _quando(it)
        if n is None:
            continue
        if not q:
            sem_hora += 1          # não entra: embaralharia a sequência
            continue
        tags: List[dict] = []
        lk = _luckies(it)
        if lk:
            tags.append({"lucky": lk})
            for L in lk:
                if L["n"] == n and L["x"]:
                    tags.append({"x": L["x"]})
        linhas.append({"n": n, "settled": q, "tags": tags, "origem": "trackpotapi"})
    aviso = f"{sem_hora} giros sem horário descartados" if sem_hora else None
    return linhas, aviso


def buscar_agregados(jogo: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Estatística de multiplicador por número, do bloco JSON da página tracksino.

    O bloco vem no formato "devalue" do Nuxt: uma lista onde números são
    referências para outras posições da mesma lista. Por isso o `puxa()`.
    """
    url = AGREGADOS.get(jogo)
    if not url:
        return {}, "sem página de agregados para este jogo"
    if requests is None:
        return {}, "biblioteca requests ausente"
    try:
        r = requests.get(url, headers=CABECALHO, timeout=TIMEOUT)
    except Exception as e:
        return {}, f"{type(e).__name__}: {str(e)[:70]}"
    if r.status_code != 200:
        return {}, f"HTTP {r.status_code}"
    m = re.search(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
                  r.text, re.S)
    if not m:
        return {}, "sem bloco JSON na página"
    try:
        arr = json.loads(m.group(1))
    except ValueError:
        return {}, "bloco JSON ilegível"
    if not isinstance(arr, list):
        return {}, "bloco JSON em formato inesperado"

    def puxa(v):
        return arr[v] if isinstance(v, int) and 0 <= v < len(arr) else v

    # As duas páginas guardam coisas diferentes, e a do Crazy Time guarda mais.
    #   roleta:     total_spins, spin_results, spin_luckies
    #   crazy time: total_wheel_spins, wheel_results, top_slot_results,
    #               top_slot_multipliers, coinflip_results
    # O top_slot é o achado: ele diz quantas vezes o multiplicador do topo caiu
    # sobre o símbolo que a roda parou (num_matches) — a mesma pergunta que o
    # M07 faz na roleta, só que aqui o próprio site já contou.
    raiz_ct = next((x for x in arr
                    if isinstance(x, dict) and "total_wheel_spins" in x), None)
    if raiz_ct is not None:
        out: Dict[str, Any] = {
            "de": puxa(raiz_ct.get("from_ts")),
            "ate": puxa(raiz_ct.get("to_ts")),
            "total_giros": puxa(raiz_ct.get("total_wheel_spins")),
            "por_simbolo": {}, "top_slot": {}, "top_slot_multi": {},
            "coinflip": {},
        }
        roda = puxa(raiz_ct.get("wheel_results")) or {}
        for chave in (roda if isinstance(roda, dict) else {}):
            reg = puxa(roda[chave]) or {}
            out["por_simbolo"][str(chave).lstrip("n")] = {
                "saiu": puxa(reg.get("num_spins")),
                "giros_sem_sair": puxa(reg.get("spins_since")),
                "multiplicador_medio": puxa(reg.get("avg_multiplier")),
            }
        ts = puxa(raiz_ct.get("top_slot_results")) or {}
        for chave in (ts if isinstance(ts, dict) else {}):
            reg = puxa(ts[chave]) or {}
            out["top_slot"][str(chave).lstrip("n")] = {
                "sorteado": puxa(reg.get("num_spins")),
                "bateu": puxa(reg.get("num_matches")),
            }
        tm = puxa(raiz_ct.get("top_slot_multipliers")) or {}
        for chave in (tm if isinstance(tm, dict) else {}):
            reg = puxa(tm[chave]) or {}
            out["top_slot_multi"][str(chave)] = {
                "sorteado": puxa(reg.get("num_spins")),
                "bateu": puxa(reg.get("num_matches")),
            }
        cf = puxa(raiz_ct.get("coinflip_results")) or {}
        for chave in (cf if isinstance(cf, dict) else {}):
            out["coinflip"][str(chave)] = puxa(cf[chave])
        return out, None

    raiz = next((x for x in arr
                 if isinstance(x, dict) and "total_spins" in x), None)
    if raiz is None:
        return {}, "página sem o resumo de giros"

    out: Dict[str, Any] = {
        "de": puxa(raiz.get("from_ts")),
        "ate": puxa(raiz.get("to_ts")),
        "total_giros": puxa(raiz.get("total_spins")),
        "total_premiacoes": puxa(raiz.get("total_luckies")),
        "por_numero": {},
    }
    saidas = puxa(raiz.get("spin_results")) or {}
    luckies = puxa(raiz.get("spin_luckies")) or {}
    for chave in (saidas if isinstance(saidas, dict) else {}):
        reg = puxa(saidas[chave]) or {}
        alvo = out["por_numero"].setdefault(str(chave), {})
        alvo["saiu"] = puxa(reg.get("num_spins"))
        alvo["giros_sem_sair"] = puxa(reg.get("spins_since"))
    for chave in (luckies if isinstance(luckies, dict) else {}):
        reg = puxa(luckies[chave]) or {}
        alvo = out["por_numero"].setdefault(str(chave), {})
        alvo["foi_lucky"] = puxa(reg.get("num_spins"))
        alvo["multiplicador_medio"] = puxa(reg.get("avg_multi"))
        alvo["giros_sem_ser_lucky"] = puxa(reg.get("spins_since"))
    return out, None


def coletar(jogo: str) -> Dict[str, Any]:
    """Tudo que os sites têm para este jogo, num pacote só."""
    seq, aviso_seq = buscar_sequencia(jogo)
    agg, aviso_agg = buscar_agregados(jogo)
    return {"jogo": jogo, "sequencia": seq, "agregados": agg,
            "avisos": [a for a in (aviso_seq, aviso_agg) if a]}


def resumo(r: Dict[str, Any]) -> str:
    L = [f"[Sites] {r['jogo']}: {len(r['sequencia'])} giros com horário"]
    a = r.get("agregados") or {}
    if a.get("total_giros"):
        L.append(f"   agregados: {a['total_premiacoes']} premiações em "
                 f"{a['total_giros']} giros")
    com_mult = sum(1 for x in r["sequencia"] if any("lucky" in t for t in x["tags"]))
    if com_mult:
        L.append(f"   {com_mult} giros trazem a rodada de multiplicadores")
    for av in r.get("avisos") or []:
        L.append(f"   aviso: {av}")
    return "\n".join(L)
