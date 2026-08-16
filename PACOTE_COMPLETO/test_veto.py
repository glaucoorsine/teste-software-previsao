# -*- coding: utf-8 -*-
"""Confere a família 12 da Régua dele — a que IMPEDE, não a que mede.

    "cuidado com essas suas métricas aí que já atrapalhou antes"

Depois desse aviso ele mandou `A Régua da Capacidade de Previsão Quântica`:
60 teorias sobre exatamente o problema que eu não resolvia sozinho. A carta de
abertura tem o diagnóstico dos meus três erros numa frase:

    "Uma afirmação pode coincidir com o resultado e ainda assim ser
     epistemicamente falsa se usou certeza maior do que seus dados permitiam."

Este teste cobra que a família 12 esteja de pé:

  1. R12-VET-01 é PRODUTO — uma porta fechada veta, e média não levanta
  2. R12-VET-02 mede o suporte efetivo, e pega o meu caso real
  3. R12-VET-03 trata controle ausente como veto, não como aprovação
  4. R12-VET-05 decide na ordem certa: integridade, contradição, suporte
  5. o placar ao vivo obedece o veto mesmo com taxa ótima

    python test_veto.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import PREVER as P  # noqa: E402
from NUCLEO import veto as V  # noqa: E402

falhas = []
rnd = random.Random(31)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] R12-VET-01 · a porta fatal é produto, não média")

g = V.porta_de_integridade({"a": True, "b": True, "c": True})
checa(g["G"] == 1 and g["integro"], "todas abertas → G=1", g)
g2 = V.porta_de_integridade({"a": True, "b": False, "c": True})
checa(g2["G"] == 0 and not g2["integro"], "uma fechada → G=0", g2)
checa("b" in g2["reprovadas"], "e diz qual fechou", g2["reprovadas"])
# a diferença que importa: numa MÉDIA, 2 de 3 daria 0,67 e passaria
checa(g2["G"] == 0,
      "duas de três não é 'quase íntegro' — é vetado")
checa(V.porta_de_integridade({})["integro"], "sem portas declaradas, não veta")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] R12-VET-02 · suporte efetivo")

indep = [1.0 if rnd.random() < 0.3 else 0.0 for _ in range(300)]
r = V.tamanho_efetivo(indep)
checa(r["n_eff"] > 200, "série independente mantém quase todo o n",
      round(r["n_eff"]))
grud = []
for _ in range(60):
    v = 1.0 if rnd.random() < 0.3 else 0.0
    grud.extend([v] * 5)
r2 = V.tamanho_efetivo(grud)
checa(r2["n_eff"] < r2["n"] / 2, "série grudada perde a maior parte",
      (r2["n"], round(r2["n_eff"])))

# a variante que pegou o MEU erro: previsões quase iguais
iguais = [[str(j) for j in range(10)] for _ in range(60)]
pe = V.previsoes_efetivas(iguais)
checa(pe["distintas"] == 1, "60 previsões idênticas = 1 teste", pe["distintas"])
checa(pe["sobreposicao"] > 0.95, "e a sobreposição denuncia", pe["sobreposicao"])
variadas = [[str((j + i * 3) % 37) for j in range(10)] for i in range(60)]
pv = V.previsoes_efetivas(variadas)
checa(pv["distintas"] > 30, "previsões variadas contam de verdade",
      pv["distintas"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] R12-VET-03 · controle ausente é veto, não aprovação")

c0 = V.controle_negativo_obrigatorio(1.5, [])
checa(not c0["passa"], "sem envelope não passa", c0["motivo"])
c1 = V.controle_negativo_obrigatorio(1.5, [1.0 + rnd.random() * 0.1
                                           for _ in range(200)])
checa(c1["passa"], "observado fora do envelope passa", c1["motivo"])
c2 = V.controle_negativo_obrigatorio(1.02, [1.0 + rnd.random() * 0.3
                                            for _ in range(200)])
checa(not c2["passa"], "observado dentro do envelope não passa", c2["motivo"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] R12-VET-05 · decide na ordem certa")

bom_ctrl = V.controle_negativo_obrigatorio(2.0, [1.0] * 50)
muito = {"n_eff": 200.0, "motivo": "farto"}
pouco = {"n_eff": 6.0, "motivo": "escasso"}
aberto = V.porta_de_integridade({"ok": True})
fechado = V.porta_de_integridade({"vazamento": False})

d = V.decisao(fechado, bom_ctrl, muito)
checa(d["decisao"] == V.VETADO, "integridade vem primeiro", d)
d = V.decisao(aberto, bom_ctrl, pouco)
checa(d["decisao"] == V.NAO_CONCLUIR, "suporte fraco não conclui", d)
d = V.decisao(aberto, V.controle_negativo_obrigatorio(1.0, [1.2] * 50), muito)
checa(d["decisao"] == V.NAO_CONCLUIR, "controle que não separa não conclui", d)
d = V.decisao(aberto, bom_ctrl, muito,
              contradicao={"contr": 5.0, "motivo": "objeção forte"},
              estabilidade=1.0)
checa(d["decisao"] == V.DORMENTE, "contradição dominante adormece", d)
d = V.decisao(aberto, bom_ctrl, muito)
checa(d["decisao"] == V.PODE_AFIRMAR, "tudo em ordem pode afirmar", d)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] o placar ao vivo obedece o veto — mesmo com taxa ótima")

# ESTE É O MEU ERRO, REPRODUZIDO. A previsão foi a mesma lista 60 vezes e a
# taxa deu 1,85x com o intervalo inteiro acima do acaso. O veredito do
# intervalo diz "ACIMA DO ACASO"; a régua dele veta, porque 60 rodadas de uma
# previsão só não são 60 testes.
constante = P.Placar(37)
for i in range(60):
    constante.registrar([str(j) for j in range(10)],
                        "5" if i % 2 == 0 else "30", {})
c = constante.constituicao()
print(f"       taxa {constante.razao:.2f}x · {constante.veredito()[:34]}")
print(f"       régua: {c['decisao']['decisao']} — {c['decisao']['porque'][:56]}")
checa(constante.razao > 1.5, "(cenário) a taxa parece ótima",
      f"{constante.razao:.2f}x")
checa("ACIMA DO ACASO" in constante.veredito(),
      "(cenário) e o intervalo confirma")
checa(c["decisao"]["decisao"] == V.VETADO,
      "mas a régua dele VETA a previsão constante",
      c["decisao"])
checa("VETADO" in constante.linha(),
      "e o veto aparece na tela junto do placar")

variado = P.Placar(37)
for i in range(60):
    prev = [str((j + i * 3) % 37) for j in range(10)]
    variado.registrar(prev, prev[0] if i % 2 == 0 else str((i * 7 + 5) % 37), {})
cv = variado.constituicao()
print(f"       variado: {variado.razao:.2f}x · "
      f"{cv['decisao']['decisao']}")
checa(cv["decisao"]["decisao"] == V.PODE_AFIRMAR,
      "com previsões variadas e vantagem real, deixa afirmar", cv["decisao"])

curto = P.Placar(37)
for i in range(10):
    curto.registrar([str(j) for j in range(10)], "5", {})
cc = curto.constituicao()
checa(cc["decisao"]["decisao"] != V.PODE_AFIRMAR,
      "com 10 rodadas não deixa afirmar de jeito nenhum", cc["decisao"])

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("VETO_OK")
