# -*- coding: utf-8 -*-
"""Confere que os dois compendios dele viraram conhecimento usavel.

Nao basta o texto estar guardado. O teste cobra as tres coisas que separam
biblioteca de enfeite:

  1. o conteudo esta INTEIRO -- 80 conceitos, 416 fichas de multiplicador
  2. a ficha 226 (consenso ilusorio) MEDE de verdade: fontes que dizem a mesma
     coisa tem que valer menos que fontes que dizem coisas diferentes
  3. a separacao ocorrencia/magnitude muda o peso do voto na mesa certa

    python test_biblioteca.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import biblioteca_teorias as B  # noqa: E402
from academia_autonoma import previsores_multiplicador as M  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


print("\n[1] o compendio inteiro, nao um resumo")
cs = B.conceitos()
checa(len(cs) == 80, "os 80 conceitos estao la", len(cs))
eixos = {c["eixo"] for c in cs}
checa(len(eixos) == 4, "os quatro eixos", eixos)
checa(all(c.get("tese") for c in cs), "todo conceito tem tese")
com_medida = sum(1 for c in cs if c.get("medida"))
checa(com_medida >= 75, "e quase todos trazem como medir", com_medida)
checa(B.ficha(226) and "onsenso" in B.ficha(226)["conceito"],
      "a ficha 226 e o consenso ilusorio",
      B.ficha(226) and B.ficha(226)["conceito"])
checa(bool(B.buscar("apofenia")), "da para buscar por termo")

print("\n[2] o estudo dos multiplicadores, com os 416 veredictos")
em = B.estudo_multiplicador()
checa(em.get("n_fichas") == 416, "416 fichas", em.get("n_fichas"))
v = em.get("veredictos") or {}
checa(sum(v.values()) == 416, "e a soma dos veredictos fecha", sum(v.values()))
checa(v.get("CANDIDATO EXPLORATÓRIO") == 52,
      "52 candidatos exploratorios", v.get("CANDIDATO EXPLORATÓRIO"))

print("\n[3] FICHA 226 -- fonte repetida nao vale por duas")
iguais = {"A": ["1", "2", "3"], "B": ["1", "2", "3"], "C": ["1", "2", "3"]}
d_ig = B.n_efetivo(iguais)
print(f"       3 fontes identicas  -> efetivo {d_ig['efetivo']}")
checa(d_ig["efetivo"] <= 1.2,
      "tres fontes identicas valem por UMA", d_ig)
diferentes = {"A": ["1"], "B": ["2"], "C": ["3"]}
d_di = B.n_efetivo(diferentes)
print(f"       3 fontes distintas  -> efetivo {d_di['efetivo']}")
checa(d_di["efetivo"] >= 2.9, "tres fontes distintas valem por tres", d_di)
checa(d_ig["efetivo"] < d_di["efetivo"],
      "e o efetivo separa os dois casos -- e disso que se trata")

meio = {"A": ["1", "2", "3"], "B": ["1", "2", "9"], "C": ["7", "8", "9"]}
d_m = B.n_efetivo(meio)
print(f"       3 fontes com sobreposicao parcial -> efetivo {d_m['efetivo']}")
checa(1.0 < d_m["efetivo"] < 3.0, "caso intermediario fica no meio", d_m)
checa(d_m["pares"], "e o par mais parecido e apontado", d_m["pares"])

print("\n[4] o texto explica, nao so numera")
t = B.texto_n_efetivo(d_ig)
print("       " + t)
checa("226" in t, "cita a ficha de onde veio a regra", t)
checa(B.texto_n_efetivo({}) == "", "sem fonte nenhuma, nao inventa frase")

print("\n[5] casos que nao podem quebrar")
checa(B.n_efetivo({})["nominal"] == 0, "dicionario vazio")
checa(B.n_efetivo({"A": []})["nominal"] == 0, "fonte sem voto nao conta")
checa(B.n_efetivo({"A": ["1"]})["efetivo"] == 1.0, "uma fonte vale uma")

print("\n[6] ocorrencia e magnitude: a lente certa por mesa")
for jogo, esperado in (("lightning", "ocorrencia"),
                       ("crazy_time", "magnitude"),
                       ("crazy_time_a", "magnitude")):
    lu = B.lente_util(jogo)
    print(f"       {jogo:<14} ocorrencia {lu['ocorrencia']:+6.1f}%  "
          f"magnitude {lu['magnitude']:+6.1f}%  -> {lu['melhor']}")
    checa(lu["melhor"] == esperado,
          f"{jogo}: a lente boa e {esperado}", lu["melhor"])
lu_mf = B.lente_util("mega_fire")
checa(lu_mf["melhor"] is None,
      "mega fire: negativo nas duas, entao nenhuma lente e favorecida", lu_mf)

print("\n[7] e isso chega no peso do voto das sete IAs")
checa(M.peso_da_lente("lightning", "QUENTE")
      > M.peso_da_lente("lightning", "INTENSIDADE"),
      "no lightning quem mede ocorrencia vota mais alto")
checa(M.peso_da_lente("crazy_time", "INTENSIDADE")
      > M.peso_da_lente("crazy_time", "QUENTE"),
      "no crazy time e o contrario -- e essa inversao e o achado do estudo")
checa(M.peso_da_lente("mega_fire", "QUENTE")
      == M.peso_da_lente("mega_fire", "INTENSIDADE"),
      "no mega fire, sem ganho medido, ninguem e favorecido")
checa(min(M.peso_da_lente("lightning", n) for n in M.LENTE) > 0,
      "e ninguem e zerado: a lente fraca vota mais baixo, nao fica de fora")

print("\n[8] mesa desconhecida nao quebra nem inventa")
lu = B.lente_util("mesa_que_nao_existe")
checa(lu["melhor"] is None, "sem estudo, sem preferencia", lu)
checa(M.peso_da_lente("mesa_que_nao_existe", "QUENTE") == 1.0,
      "e o peso volta a ser igual para todas")

print("\n[9] o resumo cabe na tela")
txt = B.resumo("lightning")
print("       " + txt.replace("\n", "\n       "))
checa("80 conceitos" in txt, "diz o tamanho da biblioteca")
checa("prova" in txt, "e avisa que nada disso e prova")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("BIBLIOTECA_OK")
