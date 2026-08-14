# -*- coding: utf-8 -*-
"""
TESTAR FONTES — descobre o que cada site realmente responde.

    python TESTAR_FONTES.py        (ou TESTAR_FONTES.bat)

Por que existe: o raspador das fontes alternativas foi escrito no chute — uma
expressão regular procurando qualquer número de 0 a 36 perto das palavras
"result" ou "spin". Nunca ninguém conferiu o que as páginas devolvem, e o
resultado é que em 765 giros coletados, ZERO vieram delas.

Esta sonda não tenta adivinhar. Ela bate em cada endereço, guarda a resposta
crua em `amostras_fontes/`, e imprime um resumo do que encontrou: se veio
JSON, quais campos tem; se veio HTML, se há tabela de resultados; se bloqueou,
qual foi o código.

Com essas amostras dá para escrever o coletor certo de cada fonte, em vez de
uma regex torcendo para dar certo.

NADA É ENVIADO PARA LUGAR NENHUM. Os arquivos ficam na sua pasta.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "amostras_fontes"

FONTES = [
    ("tracksino API  lightning", "https://api.tracksino.com/lightningroulette_history",
     {"page_num": 1, "per_page": 50, "period": "24hours"}),
    ("tracksino API  crazy_time", "https://api.tracksino.com/crazytime_history",
     {"page_num": 1, "per_page": 50, "period": "24hours"}),
    ("tracksino HTML lightning", "https://www.tracksino.com/lightning-roulette", None),
    ("tracksino HTML crazy_time", "https://www.tracksino.com/crazytime", None),
    ("casinotrackpot lightning", "https://www.casinotrackpot.com/ph/lightning-roulette/", None),
    ("casinotrackpot crazy_time", "https://www.casinotrackpot.com/ph/crazy-time/", None),
    ("casinotrackpot immersive", "https://www.casinotrackpot.com/ph/immersive-roulette-live/", None),
    ("gamblingcounting lightning", "https://gamblingcounting.com/lightning-roulette", None),
    ("gamblingcounting crazy_time", "https://gamblingcounting.com/crazy-time", None),
    ("gamblingcounting immersive", "https://gamblingcounting.com/immersive-roulette", None),
    ("gamblingcounting roleta", "https://gamblingcounting.com/roulette", None),
]

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def olhar_json(d):
    """O que tem dentro? Devolve linhas legíveis."""
    L = []
    if isinstance(d, list):
        L.append(f"lista com {len(d)} itens")
        if d and isinstance(d[0], dict):
            L.append(f"campos do 1o item: {sorted(d[0].keys())[:14]}")
            L.append(f"1o item: {json.dumps(d[0], ensure_ascii=False)[:220]}")
    elif isinstance(d, dict):
        L.append(f"objeto com campos: {sorted(d.keys())[:14]}")
        for k in ("data", "results", "history", "items", "rows"):
            v = d.get(k)
            if isinstance(v, list) and v:
                L.append(f"  '{k}' e' lista com {len(v)} itens")
                if isinstance(v[0], dict):
                    L.append(f"  campos: {sorted(v[0].keys())[:14]}")
                    L.append(f"  1o: {json.dumps(v[0], ensure_ascii=False)[:220]}")
                break
    return L


def olhar_html(t):
    """Tem tabela de resultado? Tem horário? Tem multiplicador?"""
    L = [f"HTML com {len(t)} caracteres"]
    tem = lambda p: bool(re.search(p, t, re.I))
    marcas = {
        "tabela <table>": r"<table",
        "palavra 'result'": r"result",
        "palavra 'spin'": r"spin",
        "palavra 'multiplier'": r"multiplier",
        "horário (hh:mm)": r"\b\d{1,2}:\d{2}\b",
        "data ISO": r"\d{4}-\d{2}-\d{2}",
        "JSON embutido": r"application/json|__NEXT_DATA__|window\.__",
    }
    achou = [k for k, p in marcas.items() if tem(p)]
    L.append("encontrado: " + (", ".join(achou) if achou else "nada reconhecível"))
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.{0,300})', t, re.I | re.S)
    if m:
        L.append("tem __NEXT_DATA__ (dado da pagina em JSON) — otimo sinal")
    if re.search(r"cloudflare|captcha|just a moment|access denied", t, re.I):
        L.append("!! parece bloqueio anti-robo")
    return L


def main():
    try:
        import requests
    except ImportError:
        print("Falta a biblioteca requests. Rode 0_INSTALAR_DEPENDENCIAS.bat")
        return 1

    SAIDA.mkdir(exist_ok=True)
    print()
    print("=" * 72)
    print(" SONDA DAS FONTES — o que cada site responde de verdade")
    print("=" * 72)
    print(f" as respostas cruas ficam em: {SAIDA}")
    print()

    resumo = []
    for nome, url, params in FONTES:
        print("-" * 72)
        print(f" {nome}")
        print(f"   {url}")
        try:
            r = requests.get(url, params=params, headers=CABECALHO, timeout=25)
        except Exception as e:
            print(f"   FALHOU: {type(e).__name__}: {str(e)[:90]}")
            resumo.append((nome, "erro de conexao"))
            continue

        print(f"   HTTP {r.status_code}   {len(r.content)} bytes   "
              f"{r.headers.get('content-type', '?')[:40]}")
        if r.status_code != 200:
            print(f"   corpo: {r.text[:140]}")
            resumo.append((nome, f"HTTP {r.status_code}"))
            continue

        arq = SAIDA / f"{_slug(nome)}"
        try:
            d = r.json()
            (arq.with_suffix(".json")).write_text(
                json.dumps(d, ensure_ascii=False, indent=1)[:400000], encoding="utf-8")
            for l in olhar_json(d):
                print(f"   {l}")
            resumo.append((nome, "JSON OK"))
        except ValueError:
            (arq.with_suffix(".html")).write_text(r.text[:400000], encoding="utf-8")
            for l in olhar_html(r.text):
                print(f"   {l}")
            resumo.append((nome, "HTML"))

    print()
    print("=" * 72)
    print(" RESUMO")
    print("=" * 72)
    for nome, st in resumo:
        print(f"   {st:<18} {nome}")
    print()
    print(f" Os arquivos em {SAIDA.name}/ mostram o formato exato de cada fonte.")
    print(" Zipe essa pasta e me mande — com ela dá para escrever o coletor")
    print(" certo de cada site, em vez de adivinhar com expressao regular.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
