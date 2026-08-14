# -*- coding: utf-8 -*-
"""
Fontes adicionais de histórico (além de casino.org / api-cs).

1) bases_estudo/ — prints reais do usuário (sempre disponíveis offline)
2) Tracksino API — opcional, token em TRACKSINO_TOKEN ou llm_config.json
3) CasinoTrackpot / GamblingCounting — tentativa HTTP pública (pode falhar por anti-bot)

Uso:
  from fontes_externas import carregar_base_estudo, capturar_multi_fonte
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parent
BASES = ROOT / "bases_estudo"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json,text/html,*/*",
}

# URLs públicas de referência (documentação / fallback)
URLS = {
    "crazy_time": [
        "https://www.tracksino.com/crazytime",
        "https://www.casinotrackpot.com/ph/crazy-time/",
        "https://gamblingcounting.com/crazy-time",
    ],
    "lightning": [
        "https://www.tracksino.com/lightning-roulette",
        "https://www.casinotrackpot.com/ph/lightning-roulette/",
        "https://gamblingcounting.com/lightning-roulette",
    ],
    "immersive": [
        "https://www.casinotrackpot.com/ph/immersive-roulette-live/",
        "https://gamblingcounting.com/immersive-roulette",
        "https://gamblingcounting.com/roulette",
    ],
    "mega_fire": [
        "https://gamblingcounting.com/roulette",
    ],
}

TRACKSINO_HISTORY = {
    "crazy_time": "https://api.tracksino.com/crazytime_history",
    "lightning": "https://api.tracksino.com/lightningroulette_history",
}


def _token_tracksino() -> Optional[str]:
    t = os.environ.get("TRACKSINO_TOKEN") or os.environ.get("TRACKSINO_API_KEY")
    if t:
        return t.strip()
    cfg = ROOT / "llm_config.json"
    if cfg.is_file():
        try:
            d = json.loads(cfg.read_text(encoding="utf-8"))
            return (d.get("tracksino_token") or d.get("TRACKSINO_TOKEN") or "").strip() or None
        except Exception:
            return None
    return None


def listar_bases(jogo: Optional[str] = None) -> List[Path]:
    if not BASES.is_dir():
        return []
    out = []
    for p in sorted(BASES.glob("*.json")):
        if p.name == "INDICE.json":
            continue
        if jogo and jogo not in p.name and not _jogo_no_arquivo(p, jogo):
            continue
        out.append(p)
    return out


def _jogo_no_arquivo(p: Path, jogo: str) -> bool:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("jogo") == jogo
    except Exception:
        return False


def carregar_base_estudo(jogo: str, max_eventos: int = 400) -> List[dict]:
    """Carrega e mescla bases reais do usuário (mais recente primeiro).

    Status de "timestamp_sintetico": a flag é gerada aqui e repassada por
    fluxo_captura.capturar() até `rows`. O lado CONSUMIDOR já existe e está
    correto: academia_autonoma/qualidade_dados.py::validar() ignora
    "ordem_temporal_quebrada" para eventos com Evento.attrs["timestamp_sintetico"].
    O lado PRODUTOR ainda não está ligado: nada hoje popula
    Evento.attrs["timestamp_sintetico"] — nem schema_eventos.eventos_de_historico()
    nem a construção de Evento em ciclo_academia.py recebem esse dado, porque
    "rows" (nível fluxo_captura, com a flag por linha) e "historico"/"settled"
    (nível ciclo_academia.ciclo(), sem canal pra flag) ainda são mundos
    separados — falta um parâmetro novo (opcional, retrocompatível) em
    eventos_de_historico()/ciclo() pra fechar esse elo. Ainda não fiz essa
    mudança porque toca a assinatura usada pelos 74 testes e por
    academia_servico.py — prefiro fazer isso numa rodada dedicada, testada,
    em vez de embutir junto de outra entrega. Enquanto isso, o risco prático
    é baixo: os JSONs de bases_estudo/ têm relógio sintético único e
    globalmente monotônico por jogo (sem colisão nem quebra de ordem entre
    arquivos), então "ordem_temporal_quebrada" não deveria disparar por causa
    deles mesmo sem a flag chegar até aqui.
    """
    rows: List[dict] = []
    seen = set()
    for p in listar_bases(jogo):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for ev in d.get("events") or []:
            n = ev.get("n")
            if n is None:
                continue
            key = (str(n), str(ev.get("settled") or ""), str(ev.get("origem") or p.name))
            if key in seen:
                continue
            seen.add(key)
            row = {
                "n": n if not isinstance(n, str) or not n.isdigit() else int(n),
                "settled": ev.get("settled"),
                "tags": ev.get("tags") or ([] if not ev.get("mult") else [{"x": ev["mult"]}]),
                "origem": ev.get("origem") or p.name,
                "event_id": f"estudo|{p.stem}|{n}|{ev.get('settled')}",
                "timestamp_sintetico": bool(
                    ev.get("timestamp_sintetico", d.get("timestamp_sintetico", True))
                ),
            }
            rows.append(row)
            if len(rows) >= max_eventos:
                return rows
    return rows


def fetch_tracksino(jogo: str, per_page: int = 50) -> Tuple[List[dict], Optional[str]]:
    """Tenta API Tracksino (requer token)."""
    url = TRACKSINO_HISTORY.get(jogo)
    if not url:
        return [], "jogo sem endpoint tracksino"
    token = _token_tracksino()
    if not token:
        return [], "TRACKSINO_TOKEN ausente (opcional)"
    try:
        r = requests.get(
            url,
            params={"page_num": 1, "per_page": per_page, "period": "24hours"},
            headers={**HEADERS, "Authorization": f"Bearer {token}", "token": token},
            timeout=20,
        )
        if r.status_code != 200:
            return [], f"tracksino HTTP {r.status_code}: {r.text[:120]}"
        data = r.json()
        items = data if isinstance(data, list) else (data.get("data") or data.get("results") or data.get("history") or [])
        rows = []
        for it in items:
            if not isinstance(it, dict):
                continue
            # formatos possíveis
            n = it.get("result") or it.get("number") or it.get("slot_result") or it.get("segment")
            if n is None and isinstance(it.get("raw"), dict):
                n = it["raw"].get("result") or it["raw"].get("slot_result")
            if n is None:
                continue
            settled = it.get("finalized_at") or it.get("time") or it.get("created_at") or it.get("settledAt")
            rows.append({"n": n, "settled": settled, "tags": [], "origem": "tracksino"})
        return rows, None
    except Exception as e:
        return [], f"tracksino erro: {e}"


def fetch_html_numeros(url: str, max_n: int = 80) -> Tuple[List[dict], Optional[str]]:
    """Extrai sequências de números 0–36 de HTML público (melhor esforço)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        text = r.text
        # números isolados em células / JSON embutido
        found = re.findall(r'(?:["\']number["\']\s*:\s*|["\']result["\']\s*:\s*|>(\d{1,2})<)', text)
        nums = []
        for m in re.finditer(r'\b([0-9]|[12][0-9]|3[0-6])\b', text):
            # filtro muito solto — só usa se contexto próximo parece resultado
            start = max(0, m.start() - 40)
            ctx = text[start:m.end()+40].lower()
            if any(k in ctx for k in ("result", "spin", "number", "outcome", "roulette", "history")):
                nums.append(int(m.group(1)))
            if len(nums) >= max_n:
                break
        rows = [{"n": n, "settled": None, "tags": [], "origem": url} for n in nums[:max_n]]
        return rows, None if rows else "nenhum número confiável no HTML"
    except Exception as e:
        return [], str(e)


def capturar_multi_fonte(jogo: str, max_total: int = 200) -> Dict[str, Any]:
    """
    Combina: base de estudo (prints reais) + tracksino + HTML público.
    Retorna rows normalizados (mais recente primeiro quando possível).
    """
    rows: List[dict] = []
    fontes_ok = []
    erros = []

    base = carregar_base_estudo(jogo, max_eventos=max_total)
    if base:
        rows.extend(base)
        fontes_ok.append(f"bases_estudo:{len(base)}")

    tr, err = fetch_tracksino(jogo)
    if tr:
        rows.extend(tr)
        fontes_ok.append(f"tracksino:{len(tr)}")
    elif err:
        erros.append(err)

    for url in URLS.get(jogo, [])[:2]:
        hr, herr = fetch_html_numeros(url, max_n=40)
        if hr:
            rows.extend(hr)
            fontes_ok.append(f"html:{url.split('/')[2]}:{len(hr)}")
        elif herr:
            erros.append(f"{url}: {herr}")

    # dedupe simples por (n, settled)
    seen = set()
    uniq = []
    for r in rows:
        k = (str(r.get("n")), str(r.get("settled")))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
        if len(uniq) >= max_total:
            break

    return {
        "rows": uniq,
        "fontes_ok": fontes_ok,
        "erros": erros,
        "n": len(uniq),
    }
