# -*- coding: utf-8 -*-
"""Confere as doze inteligências do Tratado dele.

O terceiro estudo é uma ESPECIFICAÇÃO, não um catálogo: 960 formulações, 12
inteligências, fórmula auditável em todas. Este teste cobra que a
implementação faça o que a fórmula diz -- e, principalmente, que ela SE CALE
onde a mesa não oferece o dado que a fórmula pede.

  1. as doze existem, cada uma com a fórmula publicada dele
  2. cada fórmula faz o que promete, num caso plantado onde a resposta é sabida
  3. quem não tem dado se cala -- e diz por quê
  4. IA12 agrega pela perda acumulada: quem erra encolhe, e ninguém é zerado
  5. nada quebra com histórico curto, vazio ou sujo

    python test_inteligencias.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import inteligencias_livro as T  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


rnd = random.Random(11)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] as doze do livro, com a fórmula dele")

checa(len(T.INTELIGENCIAS) == 11,
      "onze leem a mesa (a décima segunda é o agregador)", len(T.INTELIGENCIAS))
checa(all(T.formula_de(n) for n, _f, _d, _x in T.INTELIGENCIAS),
      "cada uma carrega a fórmula publicada")
checa(all(T.especialidade_de(n) for n, _f, _d, _x in T.INTELIGENCIAS),
      "e a especialidade que ele deu a ela")
nomes = [n for n, _f, _d, _x in T.INTELIGENCIAS]
checa(nomes == sorted(nomes), "estão na ordem IA01..IA11", nomes[:3])
checa(callable(T.consenso_ia12), "IA12 existe como agregador, não como leitura")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] cada fórmula faz o que promete")

# IA01  D_t = t - max{i<t : Y_i=1}   -- atraso desde a última
#       o 8 sumiu; o 21 acabou de sair. A fórmula tem que ordenar assim.
h = [rnd.choice([x for x in range(37) if x != 8]) for _ in range(300)]
h[0] = 21
p1, f1 = T.ia01_tempo_intervalos(h, 37, {})
ord1 = sorted(p1, key=lambda k: -p1[k])
checa(ord1[0] == "8", "IA01 põe em primeiro quem nunca veio", ord1[:4])
checa(p1.get("21", 0.0) < 0.05,
      "e tira do placar quem acabou de sair (D_t = 0)", p1.get("21"))

# IA02  concordância entre escalas: o que sobe em TODAS, não só na curta.
#       o 30 é plantado em toda a série; o 12 só nos 15 giros mais recentes.
h2 = [rnd.randrange(37) for _ in range(300)]
for i in range(0, 300, 6):
    h2[i] = 30
for i in range(0, 15, 2):
    h2[i] = 12
p2, f2 = T.ia02_recencia_multiescala(h2, 37, {})
checa("30" in p2, "IA02 vê o que sobe em todas as escalas", sorted(p2)[:6])
checa(p2.get("30", 0) > p2.get("12", 0),
      "e não se deixa levar pela janela curta sozinha",
      f"30={p2.get('30')} 12={p2.get('12')}")

# IA03  PMI: par que acontece mais do que as frequências isoladas explicam.
#       depois do 5 vem o 19 -- mas o 19 é raro no resto da série.
h3 = []
for i in range(400):
    if h3 and h3[-1] == 5 and rnd.random() < 0.75:
        h3.append(19)
    else:
        h3.append(rnd.choice([x for x in range(37) if x != 19]))
h3 = h3[::-1]                                   # recente-primeiro
h3[0] = 5
p3, f3 = T.ia03_motivos(h3, 37, {})
checa(p3 and max(p3, key=p3.get) == "19",
      "IA03 acha o motivo 5→19 pelo PMI", sorted(p3, key=p3.get, reverse=True)[:4])

# IA04  transição suavizada: um par visto 1x não pode virar certeza
h4 = [rnd.randrange(37) for _ in range(300)]
h4[0] = 7
p4, f4 = T.ia04_transicao(h4, 37, {})
checa(not p4 or max(p4.values()) <= 1.0, "IA04 normaliza o placar", p4 and max(p4.values()))
raro = [rnd.randrange(37) for _ in range(80)]
raro[0] = 7
_p, f4b = T.ia04_transicao(raro, 37, {})
checa("sem base" in f4b or not _p,
      "e não opina quando o contexto atual quase não ocorreu", f4b)

# IA06  rajada: B>0 quer dizer vem em grupo. Série em grupo tem que dar B>0.
grupo = []
for _ in range(40):
    grupo += [13] * 4 + [rnd.choice([x for x in range(37) if x != 13])] * 26
p6, f6 = T.ia06_rajada(grupo[:400], 37, {})
checa("13" in p6 or "rajada" in f6, "IA06 mede rajada", f6[:60])

# IA10  hurdle: existência e magnitude são dois processos separados.
#       o 4 tem multiplicador SEMPRE, mas pequeno. o 9, raramente, mas enorme.
h10, m10 = [], []
for i in range(400):
    x = rnd.randrange(37)
    h10.append(x)
    if x == 4:
        m10.append(50)
    elif x == 9 and rnd.random() < 0.3:
        m10.append(5000)
    else:
        m10.append(0)
p10, f10 = T.ia10_intensidade(h10, 37, {"mults": m10})
checa(p10, "IA10 lê o hurdle quando há marca de multiplicador", f10[:60])
checa("4" in p10 and "9" in p10,
      "e enxerga os dois lados: existência (4) e magnitude (9)", sorted(p10)[:8])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] quem não tem o dado, se cala -- e diz por quê")

ct = [rnd.randrange(8) for _ in range(300)]
r_ct = T.consultar(ct, 8, {})
for quem in ("IA05_VIZINHANCA", "IA08_GEOMETRIA"):
    checa(quem not in r_ct["palpites"],
          f"{quem} não opina em mesa sem roda física",
          r_ct["palpites"].get(quem))
    checa("roda" in (r_ct["falas"].get(quem) or ""),
          "  e explica que é por causa da roda", r_ct["falas"].get(quem))
checa("IA10_INTENSIDADE" not in r_ct["palpites"],
      "IA10 não opina sem marca de multiplicador")
checa(r_ct["opinaram"] >= 5, "mas as demais leem o Crazy Time normalmente",
      r_ct["opinaram"])

r_rol = T.consultar([rnd.randrange(37) for _ in range(400)], 37, {})
checa(r_rol["opinaram"] >= 8, "na roleta quase todas leem", r_rol["opinaram"])
checa(all(r_rol["falas"].get(n) for n, _f, _d, _x in T.INTELIGENCIAS),
      "e toda inteligência deixa uma fala, falando ou calando")
erros = [n for n in r_rol["falas"] if "erro:" in (r_rol["falas"][n] or "")]
checa(not erros, "nenhuma estourou", erros)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] IA12 agrega pela perda, e não zera ninguém")

w0 = T.pesos_ia12({})
checa(w0 == {}, "sem histórico de perda, ninguém é penalizado", w0)

perdas = {"IA01_TEMPO": 0.2, "IA02_RECENCIA": 0.9, "IA03_MOTIVOS": 0.5}
w = T.pesos_ia12(perdas)
checa(w["IA01_TEMPO"] > w["IA03_MOTIVOS"] > w["IA02_RECENCIA"],
      "quem erra menos pesa mais", {k: round(v, 3) for k, v in w.items()})
checa(all(v > 0 for v in w.values()),
      "e ninguém é zerado -- encolher não é podar", w)
checa(abs(sum(w.values()) - len(w)) < 1e-6,
      "a média do peso continua 1.0 (a escala não infla)", sum(w.values()))

# a perda tem que efetivamente mudar o resultado, senão o peso é enfeite
pesos_ia = {"IA01_TEMPO": {"7": 1.0}, "IA02_RECENCIA": {"22": 0.95}}
sem = T.consenso_ia12(pesos_ia, {})
com = T.consenso_ia12(pesos_ia, {"IA01_TEMPO": 3.0, "IA02_RECENCIA": 0.0})
checa(sem["ordem"][0] == "7", "sem perda, vence quem tem mais peso bruto", sem["ordem"])
checa(com["ordem"][0] == "22",
      "com perda acumulada, o que erra muito perde a ponta", com["ordem"])
checa(com["quem"].get("22") == ["IA02_RECENCIA"],
      "e o placar diz QUEM votou em cada número", com["quem"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] não quebra com pouco dado nem com dado torto")

for seq, nc in (([], 37), ([1], 37), ([1, 2, 3], 37),
                ([None, "", "x", 5, 5], 37), (list(range(37)), 37),
                ([0] * 300, 8), ([rnd.randrange(8) for _ in range(9)], 8)):
    try:
        rr = T.consultar(seq, nc, {"mults": [0, 0]})
    except Exception as e:
        checa(False, "aguenta histórico curto/sujo", f"{type(e).__name__} em {seq[:4]}")
        break
    ruins = [n for n in rr["falas"] if "erro:" in (rr["falas"][n] or "")]
    if ruins:
        checa(False, "aguenta histórico curto/sujo", f"{ruins} em {seq[:4]}")
        break
else:
    checa(True, "aguenta histórico curto, vazio, sujo e constante")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] o painel cabe na tela")
SET = [5, 24, 16, 33, 1, 20, 14]
viciada = [rnd.randrange(37) for _ in range(400)]
for i in range(0, 400, 3):
    viciada[i] = rnd.choice(SET)
txt = T.resumo(viciada, 37, {"mults": [rnd.choice([0, 0, 50]) for _ in range(400)]})
print("       " + txt.replace("\n", "\n       "))
checa("Tratado" in txt, "o resumo se identifica")
checa("IA12" in txt, "e mostra a agregação dele no fim")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("INTELIGENCIAS_OK")
