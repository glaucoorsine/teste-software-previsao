# -*- coding: utf-8 -*-
"""Confere que a autopsia separa CEGUEIRA de VOTACAO.

Sao diagnosticos opostos e a correcao de cada um e diferente: se o numero
estava na mesa e perdeu a vaga, o problema e peso; se ninguem tinha, e teoria
que falta. Confundir os dois manda o trabalho para o lado errado.

    python test_autopsia.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import autopsia as A  # noqa: E402

A.PASTA = Path(tempfile.mkdtemp())

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


print("\n[1] os tres tipos de laudo")
# ninguem tinha o 30: cegueira
l = A.registrar("t1", ["4", "5", "9"], 30, False,
                candidatos_por_fonte={"ESTAT": ["1", "2"],
                                      "REGRA_OPERADOR": ["4", "5", "9"]})
checa(l["tipo"] == "cegueira", "ninguem tinha o numero → CEGUEIRA", l["tipo"])
checa(l["quem_tinha"] == [], "e ninguem e apontado")

# a transicao TINHA o 30, mas ele ficou fora das vagas: votacao
l = A.registrar("t1", ["4", "5", "9"], 30, False,
                candidatos_por_fonte={"ESTAT": ["1", "2"],
                                      "REGRA_TRANSICAO": ["30", "31"]})
checa(l["tipo"] == "votacao", "alguem tinha e perdeu a vaga → VOTACAO", l["tipo"])
checa(l["quem_tinha"] == ["REGRA_TRANSICAO"], "e diz QUEM tinha", l["quem_tinha"])

l = A.registrar("t1", ["4", "5", "9"], 5, True,
                candidatos_por_fonte={"REGRA_OPERADOR": ["4", "5"],
                                      "ESTAT": ["9"]})
checa(l["tipo"] == "acerto", "acerto e marcado como acerto")
checa(l["quem_tinha"] == ["REGRA_OPERADOR"],
      "e diz quem tinha o numero que saiu", l["quem_tinha"])

print("\n[2] o numero e comparado por valor, nao por tipo")
l = A.registrar("t2", [4, 5], 29, False,
                candidatos_por_fonte={"X": [29, 30]})
checa(l["tipo"] == "votacao",
      "inteiro na fonte e inteiro no resultado casam", l["tipo"])
l = A.registrar("t2", ["4"], 29, False,
                candidatos_por_fonte={"X": ["29"]})
checa(l["tipo"] == "votacao", "texto tambem casa")
l = A.registrar("t2", ["4"], 29, False, candidatos_por_fonte={"X": [29]})
checa(l["tipo"] == "votacao",
      "int na fonte com int no resultado -- o erro de tipo nao volta aqui")

print("\n[3] o diagnostico soma os laudos")
for _ in range(6):
    A.registrar("t3", ["1"], 30, False, candidatos_por_fonte={"A": ["9"]})
for _ in range(4):
    A.registrar("t3", ["1"], 30, False, candidatos_por_fonte={"B": ["30"]})
for _ in range(3):
    A.registrar("t3", ["30"], 30, True, candidatos_por_fonte={"B": ["30"]})
d = A.diagnostico("t3")
checa(d["n"] == 13, "conta todas as janelas", d["n"])
checa(d["erros"] == 10 and d["acertos"] == 3, "separa acerto de erro",
      (d["acertos"], d["erros"]))
checa(d["cegueira"] == 6 and d["votacao"] == 4,
      "seis cegueiras e quatro de votacao", (d["cegueira"], d["votacao"]))
checa(abs(d["p_cegueira"] - 0.6) < 1e-9, "e a proporcao sai certa")
checa(d["puxando"] and d["puxando"][0][0] == "B",
      "diz quem estava puxando os acertos", d["puxando"])
checa(d["ignorados"] and d["ignorados"][0][0] == "B",
      "e quem tinha o numero nos erros e foi ignorado", d["ignorados"])

print("\n[4] o resumo aponta para onde trabalhar")
txt = A.resumo("t3")
print("       " + txt.replace("\n", "\n       "))
checa("NÃO VIMOS" in txt and "VIMOS e descartamos" in txt,
      "mostra os dois tipos, em portugues simples", txt)
checa("cedo para concluir" in txt, "com 13 janelas, avisa que e cedo")

for _ in range(20):
    A.registrar("t4", ["1"], 30, False, candidatos_por_fonte={"B": ["30"]})
t4 = A.resumo("t4")
print("       " + t4.replace("\n", "\n       "))
checa("VOTAÇÃO" in t4 and "pesos" in t4,
      "com erro de votacao dominante, manda mexer nos pesos", t4)

for _ in range(20):
    A.registrar("t5", ["1"], 30, False, candidatos_por_fonte={"B": ["7"]})
t5 = A.resumo("t5")
checa("captador" in t5,
      "com cegueira dominante, manda buscar teoria nova", t5)

print("\n[5] sem laudo nenhum nao quebra")
checa(A.diagnostico("vazio") == {"n": 0}, "mesa sem janela devolve vazio")
checa("nenhuma janela dissecada" in A.resumo("vazio"), "e o resumo avisa")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("AUTOPSIA_OK")
