# -*- coding: utf-8 -*-
"""Confere as tres faixas de publico e a recalibragem.

    python test_publico.py
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
import publico_mesa as P

P.HISTORICO = Path(tempfile.mkdtemp()) / "publico.json"
falhas = []
def checa(c, n, d=""):
    print(("  ok   " if c else "  FALHA ") + n + ("" if c else f"   [{d}]"))
    if not c: falhas.append(n)

print("\n[1] as tres faixas, com as ancoras dele")
checa(P.classificar("mega_fire", 900)["faixa"] == "cheia",
      "900 no Mega Fire e cheia — a ancora dele e 800")
checa(P.classificar("mega_fire", 500)["faixa"] == "media", "500 e media")
checa(P.classificar("mega_fire", 100)["faixa"] == "vazia", "100 e vazia")
checa(P.classificar("crazy_time", 14000)["faixa"] == "cheia",
      "14 mil no Crazy Time e cheia — ancora de 13 mil")
checa(P.classificar("crazy_time", 900)["faixa"] == "vazia",
      "900 no Crazy Time e VAZIA, apesar de ser cheia na roleta — "
      "a escala e outra")

print("\n[2] cada faixa diz o que fazer")
checa(P.classificar("mega_fire", 900)["conselho"] == "bom para jogar", "cheia")
checa(P.classificar("mega_fire", 500)["conselho"] == "talvez jogar", "media")
checa(P.classificar("mega_fire", 100)["conselho"] == "não vale jogar", "vazia")
checa(P.classificar("mega_fire", None)["faixa"] is None,
      "sem leitura nao inventa faixa")

print("\n[3] toda leitura e guardada")
for n in (100, 200, 300):
    P.observar("teste_g", n)
checa(P.limiares("teste_g")["n_obs"] == 3, "guardou as tres",
      P.limiares("teste_g")["n_obs"])
P.observar("teste_g", 0)
checa(P.limiares("teste_g")["n_obs"] == 3, "zero nao e leitura valida")

print("\n[4] com pouca leitura, mantem as ancoras dele")
lim = P.limiares("teste_g")
checa("âncoras" in lim["origem"], "com 3 leituras ainda usa as ancoras", lim)

print("\n[5] com leitura suficiente, a mesa define as proprias faixas")
for i in range(60):
    P.observar("teste_c", 1000 + i * 100)       # de 1000 a 6900
lim = P.limiares("teste_c")
print("       ", lim)
checa("tercis" in lim["origem"], "passou a usar os tercis da mesa", lim["origem"])
checa(lim["medio"] < lim["alto"], "e as fronteiras ficam em ordem")
checa(2000 < lim["medio"] < 4000 and 4000 < lim["alto"] < 6500,
      "os tercis caem onde deviam para essa distribuicao", lim)
checa(P.classificar("teste_c", 6500)["faixa"] == "cheia",
      "e a classificacao passa a seguir a mesa, nao a ancora")

print("\n[6] mesa sem variacao nao inventa fronteira")
for _ in range(60):
    P.observar("teste_p", 500)
lim = P.limiares("teste_p")
checa("sem variação" in lim["origem"], "volta para a ancora", lim["origem"])

print()
if falhas:
    print("FALHAS:", falhas); sys.exit(1)
print("PUBLICO_OK")
