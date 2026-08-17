# -*- coding: utf-8 -*-
"""Confere a entrega: os números ANTES do giro, e o placar honesto.

    "é a previsão que importa, é a entrega de cinco a dez [números]...
     acertividade. E mostrar a previsão antes da próxima rodada."

Tudo o mais no núcleo existe para que duas linhas sejam verdadeiras: os
números saem antes do giro, e o placar é medido em vez de declarado. É isso
que este teste cobra.

  1. sai de 5 a 10 números, do tamanho pedido, sem repetir
  2. o CARIMBO impede creditar acerto de giro que já existia
  3. o placar compara com o acaso do MESMO tamanho, com intervalo
  4. a perda alimenta a agregação dele: quem erra encolhe (F45/F46/F48)
  5. com vício plantado o placar sobe; em mesa honesta fica no acaso

    python test_prever.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import PREVER as P  # noqa: E402

falhas = []
rnd = random.Random(23)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


SETOR = [5, 24, 16, 33, 1, 20, 14]


def historico(n=300, vies=0.0):
    h = []
    for i in range(n):
        x = rnd.choice(SETOR) if rnd.random() < vies else rnd.randrange(37)
        lucky = [{"n": (rnd.choice(SETOR) if rnd.random() < vies
                        else rnd.randrange(37)), "x": 50}
                 for _ in range(rnd.randint(1, 5))]
        h.append({"n": x, "event_id": f"e{n - i}", "tags": [{"lucky": lucky}]})
    return h


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a entrega: de 5 a 10 números, antes do giro")

h = historico(300, vies=0.32)
for k in (5, 8, 10):
    p = P.prever(h, "lightning", k)
    checa(len(p["numeros"]) == k, f"entrega exatamente {k} números",
          len(p["numeros"]))
    checa(len(set(p["numeros"])) == k, f"sem repetir ({k})", p["numeros"])
    checa(all(str(x).isdigit() and 0 <= int(x) <= 36 for x in p["numeros"]),
          f"todos são casas da roleta ({k})", p["numeros"])
    # QUEM ENTREGA O NÚMERO É O CAÇADOR — inclusive aqui.
    #
    # Este teste cobrava `p["quem"]`, que é o mapa das famílias dos PDFs. Era
    # o contrato antigo, de quando este arquivo decidia sozinho. Ele mandou
    # deixar "somente o Caçador de Multiplicador escolhendo os números para
    # todos os jogos", então o contrato mudou: os PDFs continuam calculando
    # tudo (e o `numeros_pdfs` prova que continuam), mas o entregue é o dele.
    checa(bool(p.get("cacador")), f"e diz de onde veio o número ({k})",
          p.get("cacador"))
    checa(len(p.get("numeros_pdfs") or []) == k,
          f"os PDFs continuam calculando a lista deles ({k})",
          p.get("numeros_pdfs"))

# Crazy Time SEM tags: não há rodada de multiplicador, então o Caçador não
# fala -- e sem ele não sai número. Cair para a lista dos PDFs seria régua
# reserva, que é o que ele mandou tirar.
pct = P.prever([{"n": rnd.randrange(8), "event_id": f"c{i}"} for i in range(300)],
               "crazy_time", 3)
checa(pct["numeros"] == [],
      "sem rodada de multiplicador, o Crazy Time não entrega número",
      pct["numeros"])
checa(bool(pct.get("numeros_pdfs")),
      "mas os PDFs seguem apontando (só não decidem)", pct.get("numeros_pdfs"))

# com o sorteio do top slot presente, ele fala
_ct = [{"n": str(rnd.randrange(8)), "event_id": f"d{i}",
        "tags": [{"top": {"simbolo": str(rnd.randrange(8)), "x": 5}}]}
       for i in range(300)]
pct2 = P.prever(_ct, "crazy_time", 3)
checa(len(pct2["numeros"]) <= 3 and bool(pct2["numeros"]),
      "com rodada de sorteio, o Caçador entrega até 3", pct2["numeros"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] o carimbo impede creditar giro que já existia")

pl = P.Placar(37)
prev = ["1", "2", "3", "4", "5"]

# caso legítimo: o carimbo está no histórico, DEPOIS do alvo
ids_ok = ["novo", "carimbo", "velho"]
checa("carimbo" in ids_ok[1:],
      "carimbo presente depois do topo = giro é posterior")

# caso de vazamento: o carimbo É o topo, então nada de novo aconteceu
ids_leak = ["carimbo", "velho"]
checa("carimbo" not in ids_leak[1:],
      "carimbo no topo = nenhum giro novo, não pode contar")

# o placar só conta o que foi registrado
pl.registrar(prev, "3", {"F01": ["3", "9"]})
pl.registrar(prev, "30", {"F01": ["9"]})
checa(pl.rodadas == 2 and pl.acertos == 1, "conta acerto e erro",
      (pl.acertos, pl.rodadas))
pl.descartadas += 1
checa("descartadas" in pl.linha(),
      "e mostra as descartadas na tela em vez de esconder", pl.linha())

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] o placar compara com o acaso do mesmo tamanho")

p5 = P.Placar(37)
p10 = P.Placar(37)
for _ in range(200):
    alvo = str(rnd.randrange(37))
    p5.registrar([str(i) for i in range(5)], alvo, {})
    p10.registrar([str(i) for i in range(10)], alvo, {})
checa(abs(p5.acaso - 5 / 37) < 1e-9, "5 números → acaso 5/37", p5.acaso)
checa(abs(p10.acaso - 10 / 37) < 1e-9, "10 números → acaso 10/37", p10.acaso)
# a razão é o que compara os dois: apostar mais acerta mais por construção
checa(abs(p5.razao - 1) < 0.6 and abs(p10.razao - 1) < 0.6,
      "e as duas razões ficam perto de 1 em mesa honesta",
      (round(p5.razao, 2), round(p10.razao, 2)))

lo, hi = p10.intervalo()
checa(lo < p10.taxa < hi, "o intervalo contém a taxa", (lo, p10.taxa, hi))
curto = P.Placar(37)
curto.registrar(["1"] * 1, "1", {})
lo2, hi2 = curto.intervalo()
checa(hi2 - lo2 > 0.5,
      "com 1 rodada o intervalo é largo — taxa sozinha não diz nada",
      (lo2, hi2))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] a perda alimenta a agregação dele")

pl2 = P.Placar(37)
for _ in range(30):
    alvo = "7"
    pl2.registrar(["7"], alvo, {"BOA": ["7"], "RUIM": ["19"]})
checa(pl2.perdas["RUIM"] > pl2.perdas["BOA"],
      "quem erra acumula perda", dict(pl2.perdas))
checa(pl2.vigilia["BOA"] == pl2.vigilia["RUIM"] == 30,
      "a vigília conta os giros em que cada uma falou (F46)",
      dict(pl2.vigilia))
checa(pl2.memoria["BOA"] > 0 > pl2.memoria["RUIM"],
      "e a memória epistemológica separa as duas (F48)", pl2.memoria)

# a família prudente, que fala pouco, não pode ser punida pelo silêncio
pl3 = P.Placar(37)
for i in range(40):
    quem = {"FALADEIRA": ["9"]}
    if i % 10 == 0:
        quem["PRUDENTE"] = ["9"]
    pl3.registrar(["1"], "1", quem)
from NUCLEO import agregacao as A  # noqa: E402
w = A.f45_pesos(dict(pl3.perdas), dict(pl3.vigilia))
checa(abs(w["PRUDENTE"] - w["FALADEIRA"]) < 1e-9,
      "erra igual quando fala → pesa igual, mesmo falando 10x menos",
      {k: round(v, 4) for k, v in w.items()})

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] o placar sobe com vício e fica no acaso sem ele")


def rodar(semente, vies, rodadas=45, k=10):
    """Uma sessão inteira: prevê, o giro sai, o placar conta, a perda realimenta."""
    r = random.Random(semente)

    def giro():
        return r.choice(SETOR) if r.random() < vies else r.randrange(37)

    def linha_hist(x, i):
        return {"n": x, "event_id": f"e{i}",
                "tags": [{"lucky": [{"n": giro(), "x": 50}
                                    for _ in range(r.randint(1, 5))]}]}

    h = [linha_hist(giro(), 900 - i) for i in range(240)]
    pl = P.Placar(37)
    for i in range(rodadas):
        p = P.prever(h, "lightning", k, pl)
        x = giro()
        pl.registrar(p["numeros"], str(x), p["palpites"])
        h.insert(0, linha_hist(x, 1000 + i))
    return pl


# UMA SESSÃO SÓ NÃO SERVE DE TESTE.
#
# A primeira versão disto rodava uma sessão honesta e cobrava razão < 1,25.
# Ela deu 1,54x e eu fui atrás achando que era vazamento. Havia um bug real
# (o mapa família/classe invertido), mas mesmo depois de corrigido uma sessão
# de 60 rodadas varia entre 0,93x e 1,25x só por acaso -- o desvio-padrão da
# razão com 60 rodadas e k=10 é ~0,20.
#
# Cobrar uma sessão isolada é cobrar sorte. O teste passa a rodar várias
# sementes independentes e conferir a MÉDIA, que é o que tem que valer 1,00.
honestas = [rodar(s, 0.0) for s in (101, 202, 303, 404)]
viciadas = [rodar(s, 0.34) for s in (101, 202, 303)]
mh = sum(p.razao for p in honestas) / len(honestas)
mv = sum(p.razao for p in viciadas) / len(viciadas)
print(f"       honestas: " + "  ".join(f"{p.razao:.2f}x" for p in honestas)
      + f"   média {mh:.3f}x")
print(f"       viciadas: " + "  ".join(f"{p.razao:.2f}x" for p in viciadas)
      + f"   média {mv:.3f}x")
checa(0.85 <= mh <= 1.15,
      "em mesa honesta a média das sessões fica no acaso", f"{mh:.3f}x")
checa(mv > 1.30, "com vício plantado o placar sobe", f"{mv:.3f}x")
checa(mv > mh * 1.25, "e as duas se separam com folga", (round(mv, 2), round(mh, 2)))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] a tela diz o que o número SIGNIFICA, não só o número")

# Ele avisou: "cuidado com essas suas métricas aí que já atrapalhou antes".
# O risco não é só a conta errada -- é "1,20x" na tela PARECER resultado
# quando o intervalo cobre o acaso inteiro. O veredito fecha essa porta.

curto = P.Placar(37)
for _ in range(10):
    curto.registrar([str(i) for i in range(10)], "5", {})
checa("AINDA NÃO" in curto.veredito(),
      "com menos de 20 rodadas se recusa a concluir", curto.veredito())

# taxa alta mas intervalo cobrindo o acaso: NÃO pode parecer vitória
morno = P.Placar(37)
for i in range(30):
    morno.registrar([str(j) for j in range(10)], "5" if i % 3 == 0 else "30", {})
print("       " + f"{morno.razao:.2f}x" + " → " + morno.veredito())
checa(morno.razao > 1.05, "(cenário) a razão parece boa", f"{morno.razao:.2f}x")
checa("INDISTINGUÍVEL" in morno.veredito(),
      "mas o veredito avisa que o intervalo cobre o acaso", morno.veredito())

# vantagem real e grande: aí sim pode afirmar
forte = P.Placar(37)
for i in range(60):
    forte.registrar([str(j) for j in range(10)], "5" if i % 2 == 0 else "30", {})
print("       " + f"{forte.razao:.2f}x" + " → " + forte.veredito())
checa("ACIMA DO ACASO" in forte.veredito(),
      "com vantagem larga o veredito confirma", forte.veredito())

# e o veredito aparece na linha que vai para a tela
checa("INDISTINGUÍVEL" in morno.linha() or "ACIMA" in morno.linha()
      or "AINDA" in morno.linha(),
      "o veredito vai junto do placar na tela")

# nas sessões honestas de verdade, o veredito não pode afirmar vantagem
afirmou = [p for p in honestas if "ACIMA DO ACASO" in p.veredito()]
checa(not afirmou,
      "e em mesa honesta nenhuma sessão afirma vantagem",
      [p.linha() for p in afirmou][:1])

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("PREVER_OK")
