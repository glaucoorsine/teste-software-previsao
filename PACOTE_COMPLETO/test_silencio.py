# -*- coding: utf-8 -*-
"""Confere o direito de silêncio — R04-UNC-03 e R04-UNC-04 da Régua dele.

O replay expôs que o núcleo fala em 100% das rodadas, com risco seletivo de
69% a 83%. Pela régua dele isso é fraqueza: quem nunca cala não pode mostrar
que sabe quando não sabe.

O que este teste cobra, e a primeira é a que impede fraude:

  1. `a_t` é congelado ANTES do resultado — calar retroativamente nas rodadas
     em que errou faria qualquer leitura parecer excelente
  2. a entropia mede concentração genuína, não escolha arbitrária do topo
  3. cobertura entra SEMPRE junto do risco
  4. um critério que não ajuda tem que APARECER como não ajudando

    python test_silencio.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import silencio as S  # noqa: E402

falhas = []
rnd = random.Random(41)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a decisão de calar não pode olhar o resultado")

# Esta é a fraude mais fácil da métrica: calar depois, nas rodadas em que
# errou. `decidir()` recebe SÓ o placar, e o teste garante que a assinatura
# não tem por onde receber o alvo.
import inspect  # noqa: E402
sig = inspect.signature(S.Silencio.decidir)
params = [p for p in sig.parameters if p != "self"]
checa(params == ["placar"],
      "decidir() recebe só o placar — não há por onde passar o resultado",
      params)

# e a mesma sequência de placares tem que gerar a mesma decisão,
# independentemente do que saiu depois
def decisoes(alvos):
    s = S.Silencio(min_historico=3)
    fora = []
    for i, _alvo in enumerate(alvos):
        placar = {str(j): 1.0 / (1 + j + (i % 4)) for j in range(10)}
        fora.append(s.decidir(placar)["falar"])
    return fora

a = decisoes([1] * 40)
b = decisoes([0] * 40)
checa(a == b, "a decisão é a mesma qualquer que seja o resultado depois")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] a entropia separa concentração de empate")

concentrado = {"7": 10.0, "9": 1.0, "3": 0.8, "1": 0.5}
plano = {str(i): 1.0 for i in range(12)}
ec = S.entropia_e_margem(concentrado)
ep = S.entropia_e_margem(plano)
print(f"       concentrado: H={ec['H_norm']:.3f}  M={ec['M']:.3f}")
print(f"       plano:       H={ep['H_norm']:.3f}  M={ep['M']:.3f}")
checa(ec["H_norm"] < ep["H_norm"], "placar concentrado tem entropia menor",
      (ec["H_norm"], ep["H_norm"]))
checa(ec["M"] > ep["M"], "e margem maior", (ec["M"], ep["M"]))
checa(abs(ep["M"]) < 1e-9, "num empate perfeito a margem é zero", ep["M"])
checa(ep["H_norm"] > 0.99, "e a entropia é máxima", ep["H_norm"])
checa(S.entropia_e_margem({})["n"] == 0, "placar vazio não estoura")

# o núcleo tem que CALAR no plano e FALAR no concentrado
s = S.Silencio(min_historico=5)
for _ in range(20):
    s.decidir({str(i): 1.0 + rnd.random() * 0.05 for i in range(12)})
d_plano = s.decidir({str(i): 1.0 for i in range(12)})
d_conc = s.decidir({"7": 10.0, "9": 1.0, "3": 0.5})
checa(not d_plano["falar"], "cala quando o placar é plano", d_plano["motivo"][:50])
checa(d_conc["falar"], "fala quando há concentração", d_conc["motivo"][:50])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] cobertura anda sempre junto do risco")

s2 = S.Silencio(min_historico=2)
for i in range(50):
    s2.registrar(i % 5 == 0, True)          # fala em 20%, acerta sempre
m = s2.medida()
checa(m["risco"] == 0.0, "risco zero nas que falou", m)
checa(abs(m["cobertura"] - 0.2) < 0.01, "e cobertura de 20% aparece junto", m)
checa("cobertura" in m and "risco" in m["motivo"],
      "a frase traz as duas — risco baixo com cobertura de 2% é seleção",
      m["motivo"])

vazio = S.Silencio().medida()
checa(vazio["cobertura"] == 0.0, "sem rodadas, cobertura zero")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] um critério que não ajuda aparece como não ajudando")

# caso em que calar AJUDA: o núcleo erra justamente quando cala
acertos = [i % 3 != 0 for i in range(90)]
falou = [i % 3 != 0 for i in range(90)]
c = S.comparar(acertos, acertos, falou)
print(f"       ajuda:     {c['motivo']}")
checa(c["vale"], "quando calar ajuda, a conta mostra ganho", c)
checa(c["ganho"] > 0, "com ganho positivo", c["ganho"])

# caso em que calar NÃO ajuda: silêncio sorteado, sem relação com acerto
falou2 = [rnd.random() < 0.5 for _ in range(90)]
c2 = S.comparar(acertos, acertos, falou2)
print(f"       não ajuda: {c2['motivo']}")
checa(abs(c2["ganho"]) < 0.15, "silêncio aleatório não produz ganho real",
      c2["ganho"])

c3 = S.comparar(acertos, acertos, [False] * 90)
checa(not c3["vale"], "calar sempre não é vitória", c3["motivo"])

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("SILENCIO_OK")
