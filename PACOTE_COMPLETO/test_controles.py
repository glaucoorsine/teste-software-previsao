# -*- coding: utf-8 -*-
"""Confere que a régua usa OS CONTROLES DELE, e que eles são honestos.

    "a sua métrica que você chama de régua, ela é completamente errada, não
     funciona, e torna quase tudo inválido"
    "você tem que estudar, buscar nos meus PDFs mesmo"

Ele estava certo. Cada formulação do Tratado traz na seção 4 a operação exata
que derrubaria aquela leitura -- 48 controles escritos por ele, muito mais
precisos que os três nulos genéricos que eu tinha inventado.

O teste cobra as seis coisas que separam régua honesta de régua que mente:

  1. a regra-mestre da F35: todo controle preserva dificuldade e composição
  2. cada família recebe o controle DELE, não um genérico meu
  3. cada operação destrói o que promete destruir, e só isso
  4. em mesa honesta a régua dá 1,00x -- se der 1,10x, ela credita à leitura
     uma vantagem que veio da medição
  5. com vício plantado a régua ENXERGA, senão ela seria só conservadora
  6. o contraditório dele sobrevive ao container ser apagado

    python test_controles.py
"""
from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import base as B  # noqa: E402
from NUCLEO import controles as C  # noqa: E402
from NUCLEO import regua as R  # noqa: E402

falhas = []
rnd = random.Random(17)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a regra-mestre da F35: preservar dificuldade e composição")

# "Preservar dificuldade, composição e oportunidades de seleção em todos os
#  controles" -- meu nulo uniforme destruía a composição e por isso inflava.
for nome, ok in C.conferir_preserva_composicao().items():
    checa(ok, f"o controle '{nome}' preserva a composição")

# o contraexemplo: um nulo uniforme NÃO preservaria, e é o que eu usava
uni = [rnd.randrange(37) for _ in range(300)]
orig = [rnd.randrange(37) for _ in range(300)]
checa(Counter(uni) != Counter(orig),
      "(contraste) sortear de dado honesto muda a composição — era o meu erro")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] cada família recebe o controle dele")

fams = [f["familia"] for f in B.familias()]
checa(len(fams) == 48, "as 48 famílias", len(fams))
sem = [f for f in fams if f not in C.CONTROLE]
checa(not sem, "todas têm controle declarado", sem)
fantasma = [f for f in C.CONTROLE if f not in fams]
checa(not fantasma, "e o mapa não inventa família", fantasma)
checa(all(C.controle_de(f)[1] for f in fams),
      "cada controle carrega a instrução dele por extenso")
checa(all(C.controle_de(f)[0] in C.OPERACOES for f in fams),
      "e aponta para uma operação implementada")

# a régua tem que delegar para ele, não usar tabela minha
checa(R.nulo_de("F31")[0] == "geometria",
      "a régua usa o controle dele (F31 → relabelar geometria)",
      R.nulo_de("F31"))
checa(R.nulo_de("F13")[0] == "estratos",
      "F13 → permutar destinos dentro de estratos", R.nulo_de("F13"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] cada operação destrói o que promete, e só isso")

s = [rnd.randrange(37) for _ in range(400)]

# blocos: preserva a deriva lenta, destrói a ordem local
com_deriva = [0] * 100 + [rnd.randrange(37) for _ in range(300)]
b = C.permutar_em_blocos(list(com_deriva), rnd, 37)
zeros_inicio = sum(1 for x in b[:100] if x == 0)
checa(zeros_inicio >= 80,
      "'blocos' preserva a deriva lenta (o que o atraso não reivindica)",
      zeros_inicio)

# geometria: gira a roda -- as CONTAGENS ficam, os rótulos mudam
g = C.relabelar_geometria(list(s), rnd, 37)
checa(sorted(Counter(g).values()) == sorted(Counter(s).values()),
      "'geometria' preserva o perfil de contagens")
checa(Counter(g) != Counter(s), "e mesmo assim move os rótulos")

# estratos: preserva quantas vezes cada origem apareceu
e = C.permutar_destinos_por_estrato(list(s), rnd, 37)
checa(Counter(e) == Counter(s), "'estratos' preserva a composição")

# transicoes: quebra o pareamento sem mexer em quem apareceu
t = C.preservar_transicoes(list(s), rnd, 37)
p0 = Counter((s[i], s[i + 1]) for i in range(len(s) - 1))
p1 = Counter((t[i], t[i + 1]) for i in range(len(t) - 1))
mantidos = sum((p0 & p1).values()) / max(1, sum(p0.values()))
checa(mantidos < 0.45, "'transicoes' quebra o pareamento", f"{mantidos:.0%}")

# fronteiras: não muda número nenhum, só de onde se começa a olhar
f = C.variar_fronteiras(list(s), rnd, 37)
checa(Counter(f) == Counter(s), "'fronteiras' não mexe nos números")
checa(f != s, "mas desloca a borda")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] em mesa honesta a régua dá 1,00x")

cal = R.conferir_calibragem()
for desenho, v in cal.items():
    print(f"       {desenho:<18} {v:.3f}x")
    checa(0.90 <= v <= 1.10,
          f"o desenho '{desenho}' calibra em mesa honesta", f"{v:.3f}x")


def ler_topo(velho, k=12):
    return [str(c) for c, _q in Counter(velho).most_common(k)]


# a régua inteira, com o controle dele, sobre mesa honesta
honestas = [[rnd.randrange(37) for _ in range(400)] for _ in range(3)]
r = R.medir_limpo(honestas, ler_topo, familia="F07", placebos=20)
print(f"       régua completa em mesa honesta: {r['razao']:.3f}x  p={r['p']:.3f}")
checa(0.85 <= r["razao"] <= 1.15,
      "a régua completa não credita vantagem à mesa honesta", f"{r['razao']:.3f}x")
checa(r["p"] > 0.05, "e não acha significância onde não há", r["p"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] com vício plantado, a régua enxerga")

# uma mesa realmente viciada: sete números saem o dobro
VICIADOS = [5, 24, 16, 33, 1, 20, 14]
viciadas = []
for _ in range(3):
    v = []
    for _ in range(400):
        v.append(rnd.choice(VICIADOS) if rnd.random() < 0.34
                 else rnd.randrange(37))
    viciadas.append(v)
# ATENÇÃO À DISTINÇÃO, que é a raiz de tudo que eu errei:
#
#   "esta roda é desigual?"        -> aderência ao uniforme (mesa_e_justa)
#   "a leitura acrescenta algo?"   -> permutação que preserva composição
#
# Os 48 controles dele preservam a composição de propósito (F35). Testar viés
# de roda com um deles é cego por construção: o controle carrega o próprio
# viés que se quer detectar. Por isso a pergunta do vício vai para a aderência.
jv = R.mesa_e_justa(viciadas)
jh = R.mesa_e_justa(honestas)
print(f"       viciada: {jv['motivo']}")
print(f"       honesta: {jh['motivo']}")
checa(jv["justa"] is False, "a aderência acusa a roda viciada", jv["motivo"])
checa(jh["justa"] is True, "e absolve a honesta", jh["motivo"])
checa(jv["qui2"] > jh["qui2"] * 3, "com folga larga", (jv["qui2"], jh["qui2"]))

# e o controle DELE, aplicado à mesma mesa viciada, tem que ficar perto de 1:
# ele não erra, ele responde outra pergunta -- se a leitura acrescenta algo
# ALÉM da desigualdade que a mesa já tem.
rv = R.medir_limpo(viciadas, ler_topo, familia="F07", placebos=20)
print(f"       controle dele na mesa viciada: {rv['razao']:.3f}x  (esperado ~1)")
checa(0.85 <= rv["razao"] <= 1.15,
      "o controle dele não credita à leitura a desigualdade da mesa",
      f"{rv['razao']:.3f}x")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] o contraditório dele sobrevive ao container")

import json  # noqa: E402
idx = json.loads((RAIZ / "academia_autonoma"
                  / "indice_estudos_destilado.json").read_text(encoding="utf-8"))
F = [u for e in idx["estudos"].values() for u in e["unidades"]
     if u.get("tipo") == "formulacao"]
com = sum(1 for u in F if u.get("contraditorio"))
checa(com == len(F), "todas as 960 formulações trazem o contraditório",
      f"{com} de {len(F)}")
checa(all(len(u.get("contraditorio", "")) <= 160 for u in F),
      "e entra só a operação, não o parágrafo inteiro")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("CONTROLES_OK")
