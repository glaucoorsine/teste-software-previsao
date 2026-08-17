# -*- coding: utf-8 -*-
"""A página que ele mandou passa a ser fonte — em vez de eu chutar o endereço.

    "troque a api do crazy time a pois continua dando 404, coloque
     https://www.casino.org/casinoscores/pt-br/crazy-time-a/"
    "voce nao consertou o que pedi"        (print: Crazy Time A, HTTP 404)
    "use este https://www.casino.org/casinoscores/pt-br/crazy-time-a/"

Ele pediu três vezes. O que eu vinha fazendo era DEDUZIR o nome da mesa no
endereço da API — crazytimea, crazytime-a, crazytimeA, crazytime2,
crazytimeatable, crazy-time-a — e todos deram 404. E eu não consigo testar
nenhum: o proxy deste ambiente nega CONNECT para casino.org (403 confirmado).

Então cada palpite chegava na máquina dele sem nunca ter sido verificado.

A correção é de método: a página EXIBE os resultados, logo ela sabe de onde os
tira. O software passa a ler a página e (a) pegar os giros dali se estiverem
embutidos, ou (b) extrair o endereço de API que ela própria referencia. Nos dois
casos é evidência, não adivinhação.

  1. a página dele é a primeira fonte da Crazy Time A
  2. os giros são lidos mesmo quando o JSON está bem aninhado (Next.js)
  3. e recusados quando não são daquela mesa
  4. o endereço de API é extraído do que a página cita, com qualquer nome
  5. lixo de analytics não é confundido com fonte
  6. com fonte já gravada, o atalho não roda (a API é melhor: traz multiplicador)

    python test_pagina_da_mesa.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("LAB_MEMORIA_DIR", tempfile.mkdtemp())

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


import fluxo_captura as F  # noqa: E402
from descobridor_pela_pagina import enderecos_citados  # noqa: E402
from fonte_gamblingcounting import extrair_resultados as ler  # noqa: E402

PAGINA_DELE = "https://www.casino.org/casinoscores/pt-br/crazy-time-a/"

# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a página dele é a primeira fonte da Crazy Time A")

ends = F.enderecos_html("crazy_time_a")
checa(ends and ends[0] == PAGINA_DELE,
      "o endereço que ele mandou é o primeiro da lista", ends[:2])
for mesa in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
    e = F.enderecos_html(mesa)
    checa(len(e) >= 2, f"{mesa}: tem mais de uma página", e)
    checa("casino.org/casinoscores" in e[0],
          f"{mesa}: a página do provedor vem antes do agregador", e[0])

fonte = (RAIZ / "fluxo_captura.py").read_text(encoding="utf-8")
checa("if not fonte_lembrada(dataset_id):" in fonte,
      "mesa sem fonte conhecida consulta a página ANTES de tentar as grafias")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] os giros são lidos mesmo bem aninhados")

CT = ["CoinFlip", "1", "5", "Pachinko", "2", "10"]
casos = {
    "Next.js: props→pageProps→initialData→table→latestResults":
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"initialData":{"table":{"latestResults":'
        '[{"result":"CoinFlip"},{"result":"1"},{"result":"5"},'
        '{"result":"Pachinko"},{"result":"2"},{"result":"10"}]}}}}}</script>',
    "chave que eu não conheço, quatro níveis fundo":
        '<script>window.__S={"a":{"b":{"c":{"seja_o_que_for":'
        '[{"wheelSector":"CoinFlip"},{"wheelSector":"1"},{"wheelSector":"5"},'
        '{"wheelSector":"Pachinko"},{"wheelSector":"2"},'
        '{"wheelSector":"10"}]}}}}</script>',
    "raso, como o formato antigo (não regride)":
        '<script>{"history":["CoinFlip","1","5","Pachinko","2","10"]}</script>',
}
for nome, html in casos.items():
    r = ler(html, "crazy_time_a")
    checa(r == CT, nome[:58], r)

# a roleta, e o zero — que uma cadeia de `or` já engoliu antes
rol = ('<script>{"props":{"x":{"spins":[{"number":17},{"number":0},'
       '{"number":36},{"number":5},{"number":22},{"number":9}]}}}</script>')
checa(ler(rol, "lightning") == ["17", "0", "36", "5", "22", "9"],
      "roleta aninhada, com o zero", ler(rol, "lightning"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] e o que não é daquela mesa é recusado")

checa(ler(casos["Next.js: props→pageProps→initialData→table→latestResults"],
          "lightning") == [],
      "símbolo de Crazy Time não entra como roleta")
ids = '<script>{"data":[10231,88123,40021,99110,70233,11002,55001]}</script>'
checa(ler(ids, "lightning") == [], "array de ids não vira histórico", ler(ids, "lightning"))
checa(ler("<html>sem json nenhum</html>", "crazy_time_a") == [],
      "página sem dado devolve vazio, não invenção")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] o endereço de API sai do que a página cita — com QUALQUER nome")

# o ponto: eu não sei como o provedor chama a mesa. Não preciso.
pag = ('<script src="/_next/static/chunk.js"></script>'
       '<script>{"apiBase":"https://api-cs.casino.org/'
       'svc-evolution-game-events/api/UmNomeQueEuNaoAdivinharia"}</script>')
achados = enderecos_citados(pag, PAGINA_DELE)
checa(achados and achados[0].endswith("UmNomeQueEuNaoAdivinharia"),
      "extrai o endereço mesmo com nome que eu jamais chutaria", achados[:1])

rel = '<script>{"path":"/svc-evolution-game-events/api/outraCoisa"}</script>'
r2 = enderecos_citados(rel, PAGINA_DELE)
checa(r2 and r2[0].startswith("https://www.casino.org/svc-"),
      "caminho relativo vira absoluto", r2[:1])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] lixo de analytics não é confundido com fonte")

sujo = ('<script>{"a":"https://api-cs.casino.org/analytics/collect",'
        '"b":"https://api-cs.casino.org/svc-evolution-game-events/api/crazytimeZ",'
        '"c":"https://www.google-analytics.com/g/collect"}</script>')
r3 = enderecos_citados(sujo, PAGINA_DELE)
checa(not any("analytics" in u for u in r3), "analytics fora", r3)
checa(r3 and "game-events" in r3[0],
      "e quem tem pista de histórico vem primeiro", r3[:1])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] com fonte já gravada, o atalho não roda")

# A API conhecida é melhor que a página: ela traz o anúncio de multiplicador,
# que a página não traz. O atalho existe para destravar mesa nova.
checa("fonte_lembrada" in fonte and "_lembrar_fonte(dataset_id, _r[\"api\"])" in fonte,
      "o endereço achado é GRAVADO, então a procura acontece uma vez")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("PAGINA_MESA_OK")
