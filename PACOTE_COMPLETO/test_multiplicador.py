# -*- coding: utf-8 -*-
"""Confere as sete IAs de multiplicador -- uma a uma, e o conjunto.

O teste que importa nao e "roda sem quebrar": e se cada IA PEGA o mecanismo que
ela diz pegar. Por isso cada uma tem um historico plantado com o seu proprio
padrao, e ela tem que achar o numero plantado. Uma IA que passa em tudo
igualmente nao esta medindo nada.

E o contrario tambem e testado: em historico sorteado, ninguem pode aparecer
com vantagem. Se aparecer, a IA esta lendo ruido.

    python test_multiplicador.py
"""
from __future__ import annotations

# Os testes constroem o pipeline direto, com historico sintetico. Sem isto
# eles gravam decisoes, acertos e calibragem nos MESMOS arquivos que o
# software usa ao vivo -- e essas decisoes falsas entram no placar real.
import os, tempfile
os.environ.setdefault("LAB_MEMORIA_DIR",
                      tempfile.mkdtemp(prefix="lab_memoria_teste_"))


import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import previsores_multiplicador as M  # noqa: E402
from progresso_teste import Progresso  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


def giro(saiu, premiados, valores=None, jogo="lightning"):
    """Monta uma linha de historico como a captura entrega."""
    valores = valores or {}
    if jogo in M.CRAZY:
        s = premiados[0] if premiados else None
        tags = [{"top": {"simbolo": s, "x": valores.get(s, 5)}}] if s else []
    else:
        tags = [{"lucky": [{"n": n, "x": valores.get(n, 50)}
                           for n in premiados]}] if premiados else []
    return {"n": saiu, "tags": tags}


print("\n[1] a Immersive nao tem multiplicador, e o software nao finge que tem")
checa(not M.tem_multiplicador("immersive"), "immersive fica de fora")
for j in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
    checa(M.tem_multiplicador(j), f"{j} tem multiplicador")
p = M.prever("immersive", [giro(5, [5])])
checa(p["consenso"] == [] and p["tem"] is False,
      "e a previsao devolve vazio, com o motivo escrito", p.get("nota"))
checa("não tem multiplicador" in M.resumo("immersive", []),
      "o resumo diz por que esta vazio")

print("\n[2] a rodada INTEIRA e lida, saindo ou nao o numero")
h = [giro(7, [12, 19, 30], {12: 100, 19: 50, 30: 200})]
r = M.rodadas(h, "lightning")
checa(r[0]["premiados"] == [12, 19, 30],
      "os tres sorteados entram, mesmo com o giro tendo dado 7", r[0])
checa(r[0]["x"][30] == 200, "e o multiplicador de cada um vem junto")
h2 = [{"n": 7, "tags": [{"fire_nums": [{"n": 4, "x": 20}, {"n": 9, "x": None}]}]}]
r2 = M.rodadas(h2, "mega_fire")
checa([x for x in r2[0]["premiados"]] == [4, 9],
      "mega fire: fire_nums tambem e lido", r2[0])

print("\n[3] cada IA pega o mecanismo que ela diz pegar")
rnd = random.Random(3)

# QUENTE: o 17 sorteado em quase todo giro
hq = [giro(rnd.randint(0, 36), [17] + [rnd.randint(0, 36)]) for _ in range(60)]
checa(17 in M._topo(M._ia_quente(M.rodadas(hq, "lightning"), "lightning"), 6),
      "QUENTE acha o numero que mais foi sorteado")

# ATRASO: o 5 sai no comeco e nunca mais (historico e recente->antigo)
ha = [giro(rnd.randint(0, 36), [rnd.choice([11, 12, 13])]) for _ in range(60)]
ha.append(giro(5, [5]))
checa(5 in M._topo(M._ia_atraso(M.rodadas(ha, "lightning"), "lightning"), 6),
      "ATRASO acha quem sumiu ha mais tempo")

# VIZINHOS: sorteia sempre o 0, e o teste cobra os vizinhos dele na roda
hv = [giro(rnd.randint(0, 36), [0]) for _ in range(10)]
viz = M._topo(M._ia_vizinhos(M.rodadas(hv, "lightning"), "lightning"), 6)
checa(32 in viz and 26 in viz,
      "VIZINHOS traz os dois lados do 0 na roda fisica (32 e 26)", viz)

# FAMILIA: sorteados terminam em 1 -> familia (0,1,3,6)
hf = [giro(rnd.randint(0, 36), [21]) for _ in range(8)]
fam = M._ia_familia(M.rodadas(hf, "lightning"), "lightning")
checa(all(n % 10 in (0, 1, 3, 6) for n in fam),
      "FAMILIA levanta so a familia do final ensinado por ele")
checa(len(fam) > 10, "e levanta a familia inteira, nao um numero", len(fam))

# REPETE: o 8 aparece em rodadas consecutivas
hr = [giro(rnd.randint(0, 36), [8, rnd.randint(0, 36)]) for _ in range(20)]
checa(8 in M._topo(M._ia_repete(M.rodadas(hr, "lightning"), "lightning"), 6),
      "REPETE acha quem volta em rodadas seguidas")

# INTENSIDADE: o 3 vale pouco em presenca e muito em tamanho
hi = ([giro(rnd.randint(0, 36), [3], {3: 500})]
      + [giro(rnd.randint(0, 36), [22], {22: 50}) for _ in range(6)])
checa(3 in M._topo(M._ia_intensidade(M.rodadas(hi, "lightning"), "lightning"), 3),
      "INTENSIDADE pesa o tamanho, nao so a presenca")

print("\n[4] as sete do crazy time olham o top slot")
hc = [giro("1", ["CoinFlip"], {"CoinFlip": 50}, jogo="crazy_time")
      for _ in range(30)]
rc = M.rodadas(hc, "crazy_time")
checa(rc[0]["premiados"] == ["CoinFlip"], "le o simbolo do top slot", rc[0])
checa("CoinFlip" in M._topo(M._ia_quente(rc, "crazy_time"), 3),
      "QUENTE acha o simbolo mais sorteado no top slot")
hp = [giro("CoinFlip", ["CoinFlip"], jogo="crazy_time") for _ in range(20)]
checa("CoinFlip" in M._topo(M._ct_pagou(M.rodadas(hp, "crazy_time"), "crazy_time"), 3),
      "PAGOU acha o simbolo em que o top slot casou com a roda")
checa(M._ct_pagou(M.rodadas(hc, "crazy_time"), "crazy_time") == {},
      "e nao conta como pago quando o top slot NAO casou", "hc nunca casa")

print("\n[5] as sete sao sete mesmo -- nao sete copias")
hm = [giro(rnd.randint(0, 36), [rnd.randint(0, 36) for _ in range(3)],
           {i: rnd.choice([50, 100, 500]) for i in range(37)})
      for _ in range(200)]
pv = M.prever("lightning", hm)
listas = {nome: tuple(v) for nome, v in pv["por_ia"].items()}
checa(len(pv["por_ia"]) == 7, "sete IAs responderam", len(pv["por_ia"]))
checa(len(set(listas.values())) >= 5,
      "e ao menos cinco delas deram listas diferentes", len(set(listas.values())))
checa(len(pv["consenso"]) <= M.K_PALPITE, "o consenso respeita o tamanho pedido")
checa(all(pv["quantas_ias"][n] >= 1 for n in pv["consenso"]),
      "todo numero do consenso tem ao menos uma IA por tras")

print("\n[6] em historico sorteado ninguem pode ter vantagem")
print("      (backtest de verdade -- e a parte demorada)")
rnd2 = random.Random(99)
limpo = []
for _ in range(140):
    prem = rnd2.sample(range(37), 3)
    limpo.append(giro(rnd2.randint(0, 36), prem,
                      {n: rnd2.choice([50, 100, 200]) for n in prem}))
prog = Progresso(3, titulo="backtest")
prog.comecou("medindo lightning no ruido")
med = M.medir("lightning", limpo)
prog.terminou("ruido")
checa(med.get("suficiente"), "o backtest rodou", med.get("nota"))
if med.get("suficiente"):
    for nome, v in med["por_ia"].items():
        if v.get("razao"):
            print(f"       {nome:<12} {v['razao']:.2f}x  n={v['n']}")
    razoes = [v["razao"] for v in med["por_ia"].values() if v.get("razao")]
    checa(razoes and max(razoes) < 1.45,
          "nenhuma IA 'acha' vantagem em numero sorteado", max(razoes or [0]))

print("\n[7] com padrao plantado, o backtest TEM que ver")
prog.comecou("medindo com padrao plantado")
plantado = []
for i in range(140):
    prem = [13, 26] + [rnd2.randint(0, 36)]      # 13 e 26 quase sempre
    plantado.append(giro(rnd2.randint(0, 36), prem, {n: 100 for n in prem}))
med2 = M.medir("lightning", plantado)
prog.terminou("plantado")
q = (med2.get("por_ia") or {}).get("QUENTE") or {}
# O VICIO FOI PLANTADO NO ANUNCIO, E A RODA E ALEATORIA.
#
# `prem = [13, 26] + aleatorio` vicia quem e ANUNCIADO; o numero sorteado
# continua sendo `randint(0,36)`. Sao dois alvos, e ate a v121 o medidor
# tinha um so -- media contra o anuncio e essa razao virava peso no consenso,
# que a tela cobra contra a RODA. Uma IA podia sair com 100% aqui e 0% la.
#
# Agora `razao` e contra a roda e `razao_anuncio` contra o anuncio. Neste
# cenario o certo e: pega o vicio do anuncio, e NAO acha vantagem na roda.
print(f"       QUENTE no plantado: roda={q.get('razao')}x  "
      f"anuncio={q.get('razao_anuncio')}x  n={q.get('n')}")
checa(q.get("razao_anuncio") and q["razao_anuncio"] > 1.2,
      "QUENTE pega o padrao plantado NO ANUNCIO -- o medidor tem forca",
      q.get("razao_anuncio"))
checa(q.get("razao") is None or q["razao"] < 1.45,
      "e NAO inventa vantagem na roda, que aqui e aleatoria",
      q.get("razao"))

print("\n[8] historico curto nao inventa taxa")
prog.comecou("historico curto")
m3 = M.medir("lightning", limpo[:10])
prog.terminou("curto")
print(prog.fim("backtests"))
checa(not m3.get("suficiente"), "com 10 rodadas, se cala", m3)
checa("precisa de" in (m3.get("nota") or ""), "e diz quantas faltam", m3.get("nota"))

print("\n[9] marcar ordena DENTRO da aposta, e nao inventa nada fora")
esc = ["13", "26", "4", "9", "17"]
marcados = M.marcar("lightning", esc, plantado)
print("       escolhidos:", esc, "-> fogo:", marcados)
checa(all(x in esc for x in marcados),
      "nao inventa numero fora da aposta", marcados)
checa("13" in marcados and "26" in marcados,
      "os dois plantados como sorteados sao os marcados", marcados)
checa(len(marcados) <= 3, "marca no maximo tres", marcados)
checa(len(marcados) <= (len(esc) + 1) // 2,
      "e nunca mais que metade da aposta -- marcar tudo nao separa nada",
      (len(marcados), len(esc)))
# no crazy time, com tres opcoes, o teto cai para duas
hct = [giro("1", ["CoinFlip"], {"CoinFlip": 50}, jogo="crazy_time")
       for _ in range(40)]
mct = M.marcar("crazy_time", ["1", "2", "CoinFlip"], hct)
checa(len(mct) <= 2, "crazy time marca no maximo 2 das 3 opcoes", mct)
checa(M.marcar("immersive", esc, plantado) == [],
      "e na immersive nao marca nada")
pts = M.pontuar("lightning", esc, plantado)
checa(pts and pts[0][0] in ("13", "26"),
      "a pontuacao poe o mais apoiado na frente", pts[:2])
checa(all(q >= 2 for _n, q, _v in [x for x in pts if x[0] in marcados]),
      "e so marca quem tem ao menos duas das sete atras", pts[:3])
checa(M.pontuar("lightning", [], plantado) == [],
      "sem aposta nao ha o que pontuar")
checa(M.pontuar("lightning", esc, []) == [],
      "sem historico tambem nao")

print("\n[10] o resumo cabe na tela")
txt = M.resumo("lightning", plantado)
print("       " + txt.replace("\n", "\n       "))
checa("as 7 IAs apontam" in txt, "diz o que as sete apontam")
checa("medida" in txt, "e mostra a medida, ou por que ainda nao ha")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("MULTIPLICADOR_OK")
