# -*- coding: utf-8 -*-
"""Confere que as cinco auditorias dele viraram material de trabalho.

Nao basta o catalogo existir: ele so serve se responder a pergunta pratica do
cacador -- "isso que eu achei ja foi olhado, e com que resultado?".

E tem o teste que importa mais que todos: o CONTROLE NEGATIVO. A grade de 9
colunas do site e so o jeito de caber na tela. Se a maquina acha padrao ali,
ela esta inventando variavel a partir do layout, e nada do que ela diz vale.

    python test_base_auditoria.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import base_auditoria as B  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


print("\n[1] as cinco mesas tem retrato medido")
for m in ("mega_fire", "lightning", "crazy_time", "crazy_time_a"):
    r = B.RETRATO.get(m) or {}
    checa(bool(r.get("n")), f"{m} tem n de resultados", r.get("n"))
checa(B.RETRATO["lightning"]["impar"] == 60
      and B.RETRATO["lightning"]["par"] == 97,
      "o desequilibrio do lightning esta guardado como ele veio")
checa(B.RETRATO["crazy_time"]["categorias"]["1"] == 30,
      "a composicao do crazy time esta guardada")

print("\n[2] o limiar e o que o proprio estudo exige, nao 0,05")
checa(abs(B.ALFA_MULTIPLO - 0.05 / 56) < 1e-5,
      "0,05 dividido pelas 56 familias", B.ALFA_MULTIPLO)
checa(B.limiar("lightning", "H16") < B.ALFA_MULTIPLO,
      "familia de alto risco de ajuste exige ainda mais",
      B.limiar("lightning", "H16"))

print("\n[3] o catalogo responde o que o cacador pergunta")
casos = [
    ("lightning", "o numero par aparece mais que o impar", "H07", "SINAL"),
    ("lightning", "a linha da grade influencia o resultado", "H43",
     "CONTROLE_NEGATIVO"),
    ("mega_fire", "os finais 0 1 3 6 andam juntos", "H11", "SEM_EVIDENCIA"),
    ("mega_fire", "o vermelho domina blocos inteiros", "H05", "SEM_EVIDENCIA"),
    ("crazy_time", "depois de muitos giros sem bonus vem o bonus", "H15",
     "EXPLORATORIA"),
    ("crazy_time", "o multiplicador alto vem em grupo", "H39", "PRE_REGISTRO"),
]
for mesa, texto, cod, est in casos:
    v = B.veredito(mesa, texto)
    checa(v.get("familia") == cod and v.get("estado") == est,
          f"{mesa}: '{texto[:34]}' -> {cod}",
          (v.get("familia"), v.get("estado")))

print("\n[4] terreno nao coberto nao vira acusacao")
v = B.veredito("mega_fire", "o giro numero 7 do crupie loiro rende mais")
checa(not v.get("conhecida"), "ideia fora do catalogo passa como cacada livre")
checa(v["limiar"] == B.ALFA_MULTIPLO, "mas ja nasce com o limiar duro")

print("\n[5] a base diz ONDE ainda vale cavar")
cav = B.onde_cavar("lightning")
checa(len(cav) >= 10, "sobram familias em aberto", len(cav))
checa(all(x[3] in ("EXPLORATORIA", "SINAL", "PRE_REGISTRO") for x in cav),
      "e nenhuma delas e 'ja deu nada'")
checa(not any(x[0] in B.controles_negativos('lightning') for x in cav),
      "controle negativo nunca entra como lugar para cavar")

print("\n[6] os dois sinais abertos estao congelados com horizonte")
for s in B.SINAIS_ABERTOS:
    checa(bool(s.get("horizonte")) and bool(s.get("criterio")),
          f"{s['mesa']} {s['familia']}: horizonte e criterio escritos ANTES")
    checa(s["sobrevive_correcao"] is False,
          f"{s['mesa']} {s['familia']}: registrado que NAO sobrevive a correcao",
          s["p"])

print("\n[7] CONTROLE NEGATIVO — a grade nao pode prever nada")
rnd = random.Random(11)
limpa = [rnd.randint(0, 36) for _ in range(360)]
r = B.controle_negativo_grade(limpa)
print("       sequencia limpa:", r["p_coluna"], r["p_linha"], "-", r["leitura"])
checa(r["limpo"], "numero sorteado nao acusa efeito de coluna nem de linha", r)

print("\n[8] e o controle tem que ter forca — senao passar nao significa nada")
plantada = []
for i in range(360):
    if i % 9 == 3:                 # a coluna 4 da grade puxada para cima
        plantada.append(rnd.randint(30, 36))
    else:
        plantada.append(rnd.randint(0, 20))
r2 = B.controle_negativo_grade(plantada)
print("       coluna plantada:", r2["p_coluna"], r2["p_linha"], "-", r2["leitura"])
checa(not r2["limpo"], "efeito de coluna plantado de proposito e PEGO", r2)
checa(r2["p_coluna"] <= r2["limiar"], "e pego pelo lado da coluna", r2["p_coluna"])

print("\n[9] amostra curta nao inventa veredito")
r3 = B.controle_negativo_grade([1, 2, 3])
checa(r3["p_coluna"] is None, "com 3 numeros o controle se cala", r3)

print("\n[10] o resumo cabe na tela e diz o essencial")
for m in ("lightning", "crazy_time"):
    txt = B.resumo(m)
    print("       " + txt.replace("\n", "\n       "))
    checa("limiar exigido" in txt, f"{m}: mostra o limiar do proprio estudo")
    checa("onde ainda vale cavar" in txt, f"{m}: aponta onde cavar")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("BASE_AUDITORIA_OK")
