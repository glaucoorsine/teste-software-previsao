# -*- coding: utf-8 -*-
"""
GAMBLINGCOUNTING — quantas pessoas estão na mesa, e os últimos resultados.

POR QUE ESTA FONTE
------------------
Ele mandou os cinco endereços e disse o que quer deles:

    "para saber quantas pessoas tem e pegar os últimos 200 resultados para
     análise rápida"

E junto veio uma percepção que nenhuma outra fonte permitia testar:

    "normalmente quando o volume maior de pessoas online, mega acima de 800
     por exemplo, crazy acima de 13 mil, mais fácil a previsão e os
     multiplicadores"

Isso é uma hipótese com mecanismo plausível: mais gente na mesa é horário de
pico, e horário de pico muda o ritmo do crupiê, a frequência de giro e o
comportamento da casa. Se for verdade, o software deve prever mais quando a
mesa está cheia e ficar quieto quando está vazia — e isso é medível.

Sem este número, essa teoria não tinha como ser testada. É a razão principal
desta fonte existir.

ATENÇÃO AO QUE JÁ FALHOU AQUI
-----------------------------
Numa sondagem anterior este site respondeu 403 em todos os endereços — é um
Cloudflare que barra cliente que não parece navegador. Por isso: cabeçalho de
navegador de verdade, e falha silenciosa que não derruba nada. Se voltar 403
na máquina dele, o aviso diz exatamente isso, em vez de um erro cru.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:      # pragma: no cover - ambiente sem a biblioteca
    requests = None

RAIZ = Path(__file__).resolve().parent
TIMEOUT = 20

PAGINAS = {
    "lightning": "https://gamblingcounting.com/lightning-roulette",
    "mega_fire": "https://gamblingcounting.com/roulette",
    "crazy_time": "https://gamblingcounting.com/crazy-time",
    "crazy_time_a": "https://gamblingcounting.com/crazy-time-a",
}

# O limiar em que ele diz que a mesa "fica boa". Guardado por mesa porque a
# escala é完全 diferente: 800 pessoas no Mega Fire é cheio, no Crazy Time é vazio.
PICO = {
    "mega_fire": 800,
    "lightning": 800,
    "crazy_time": 13000,
    "crazy_time_a": 13000,
}

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _numero(txt: str) -> Optional[int]:
    """'13,482' e '13.482' e '13 482' viram 13482."""
    t = re.sub(r"[^\d]", "", str(txt or ""))
    try:
        return int(t) if t else None
    except ValueError:
        return None


def extrair_jogadores(html: str) -> Optional[int]:
    """Quantas pessoas estão na mesa agora.

    O site pode escrever isso de várias formas conforme o layout muda, então
    as tentativas vão da mais específica para a mais genérica. Melhor devolver
    None do que devolver um número de outra coisa.
    """
    padroes = [
        r'"players"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'"onlinePlayers"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'"playersOnline"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'([\d.,\s]{2,})\s*(?:players|jogadores)\s*(?:online)?',
        r'(?:players|jogadores)\s*(?:online)?\s*[:\-]?\s*([\d.,\s]{2,})',
    ]
    for p in padroes:
        m = re.search(p, html or "", re.I)
        if m:
            n = _numero(m.group(1))
            if n and 0 < n < 10_000_000:
                return n
    return None


def extrair_resultados(html: str, jogo: str, limite: int = 200) -> List[str]:
    """Os últimos resultados, do mais novo para o mais velho."""
    if not html:
        return []
    # o caminho bom: um bloco JSON na página
    for chave in ("results", "history", "spins", "lastResults", "data"):
        m = re.search(rf'"{chave}"\s*:\s*(\[.*?\])', html, re.S)
        if not m:
            continue
        try:
            arr = json.loads(m.group(1))
        except ValueError:
            continue
        saida = []
        for it in arr:
            v = it
            if isinstance(it, dict):
                for c in ("result", "value", "number", "outcome", "sector"):
                    if it.get(c) is not None:
                        v = it[c]
                        break
            v = str(v).strip()
            if v:
                saida.append(v)
        if saida:
            return saida[:limite]
    return []


def coletar(jogo: str) -> Dict[str, Any]:
    """Jogadores online e últimos resultados desta mesa."""
    url = PAGINAS.get(jogo)
    if not url:
        return {"jogo": jogo, "erro": "mesa sem página neste site"}
    if requests is None:
        return {"jogo": jogo, "erro": "biblioteca requests ausente"}
    try:
        r = requests.get(url, headers=CABECALHO, timeout=TIMEOUT)
    except Exception as e:
        return {"jogo": jogo, "erro": f"{type(e).__name__}: {str(e)[:60]}"}
    if r.status_code == 403:
        return {"jogo": jogo,
                "erro": "403 — o site bloqueia quem não parece navegador "
                        "(Cloudflare). Já aconteceu antes nesta fonte."}
    if r.status_code != 200:
        return {"jogo": jogo, "erro": f"HTTP {r.status_code}"}

    html = r.text or ""
    jogadores = extrair_jogadores(html)
    resultados = extrair_resultados(html, jogo)
    pico = PICO.get(jogo)
    return {
        "jogo": jogo, "jogadores": jogadores, "resultados": resultados,
        "n_resultados": len(resultados),
        "pico": pico,
        "mesa_cheia": (jogadores >= pico) if (jogadores and pico) else None,
        "erro": None,
    }


def resumo(d: Dict[str, Any]) -> str:
    if d.get("erro"):
        return f"[GC] {d['jogo']}: {d['erro']}"
    j = d.get("jogadores")
    L = [f"[GC] {d['jogo']}: "
         + (f"{j} pessoas na mesa" if j else "não achou o número de pessoas")
         + f" · {d.get('n_resultados', 0)} resultados"]
    if d.get("mesa_cheia") is True:
        L.append(f"     mesa CHEIA (acima de {d.get('pico')}) — "
                 f"é o momento que ele diz ser melhor para prever")
    elif d.get("mesa_cheia") is False:
        L.append(f"     mesa vazia (abaixo de {d.get('pico')})")
    return "\n".join(L)
