# -*- coding: utf-8 -*-
"""O Caçador escolhe sozinho, sem régua — e a Immersive saiu.

    "remover o Immersive e deixar somente o Caçador de Multiplicador
     escolhendo os números para todos os jogos, sem régua para ele"

Decisão dele, e este teste existe para que ela não seja desfeita sem querer:
qualquer gate meu que volte a segurar o número do Caçador quebra aqui.

  1. a Immersive saiu de todos os mapas do software
  2. o Caçador decide nas quatro mesas restantes
  3. NENHUMA régua segura: nem sombra, nem mínimo de vozes, nem corte por apoio
  4. sem palpite do Caçador, a tela fica vazia — não cai para outra fonte
  5. o palpite não vaza de uma volta para a outra

    python test_cacador_decide.py
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

import ia_modulos as M  # noqa: E402

falhas = []
SETOR = [5, 24, 16, 33, 1, 20, 14]


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


def linhas_de(jogo, giros=240, semente=7):
    rnd = random.Random(semente)
    out = []
    ct = str(jogo).startswith("crazy_time")
    for i in range(giros):
        if ct:
            simb = list(M.CT_SETORES)
            v = rnd.choice(simb)
            tags = [{"top": {"simbolo": rnd.choice(simb),
                             "x": rnd.choice([2, 5, 10])}}]
        else:
            v = rnd.choice(SETOR) if rnd.random() < 0.3 else rnd.randrange(37)
            lk = [{"n": (rnd.choice(SETOR) if rnd.random() < 0.3
                         else rnd.randrange(37)),
                   "x": rnd.choice([50, 100, 500])}
                  for _ in range(rnd.randint(1, 5))]
            tags = [{"lucky": lk}]
        out.append({"n": v, "settled": f"2026-08-17T{i//60:02d}:{i%60:02d}:00Z",
                    "tags": tags})
    return out


def rodar(jogo, linhas):
    return M.PipelinePerceptivo(jogo).processar(
        [l["n"] for l in linhas], 0, 0,
        settled=[l["settled"] for l in linhas], linhas=linhas)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a Immersive saiu do software")

from hist_buffer import DOMAIN  # noqa: E402
import coletor_sites as C  # noqa: E402
import descobridor_endereco as D  # noqa: E402
import fluxo_captura as F  # noqa: E402

for nome, mapa in (("DOMAIN", DOMAIN), ("API", F.API_BY_GAME),
                   ("coletor", C.SEQUENCIA), ("descobridor", D.NOMES)):
    checa("immersive" not in mapa, f"{nome} não tem mais immersive",
          sorted(mapa))
    checa(len(mapa) >= 4, f"{nome} mantém as quatro mesas", sorted(mapa))

checa(not (RAIZ / "immersive_combo.py").exists(),
      "o módulo da mesa foi removido")
central = (RAIZ / "CENTRAL.py").read_text(encoding="utf-8")
import re  # noqa: E402
jogos = re.search(r"JOGOS = \[(.*?)\]", central, re.S).group(1)
checa("immersive" not in jogos, "e não aparece nas abas da tela", jogos[:80])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] o Caçador decide nas quatro mesas")

checa(M.CACADOR_DECIDE, "a chave está ligada", M.CACADOR_DECIDE)

resultados = {}
for jogo in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
    r = rodar(jogo, linhas_de(jogo)) or {}
    resultados[jogo] = r
    pad = r.get("pad5") or []
    diz = [m for m in (r.get("msgs") or []) if "açador" in m]
    print(f"       {jogo:<14} {str(pad)[:52]}")
    checa(bool(pad), f"{jogo}: a tela recebe número", pad)
    checa(bool(diz), f"{jogo}: e o log diz que foi o Caçador", diz[:1])
    checa(any("sem régua" in m for m in diz),
          f"{jogo}: declarado sem régua", diz[:1])

# Crazy Time entrega símbolo, não número de roleta
pct = resultados["crazy_time"].get("pad5") or []
checa(all(str(x) in M.CT_SETORES for x in pct),
      "Crazy Time entrega símbolo válido da mesa", pct)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] nenhuma régua segura o Caçador")

# O caso que motivou: o Caçador tinha palpite e a tela ficava VAZIA porque o
# modo era SOMBRA. Sombra é régua, e ele mandou tirar.
sombra = [j for j, r in resultados.items() if r.get("modo") == "SOMBRA"]
com_num = [j for j in sombra if resultados[j].get("pad5")]
checa(len(com_num) == len(sombra),
      "em modo SOMBRA a tela continua mostrando o número do Caçador",
      (sombra, com_num))

# e os números da tela têm de ser os do Caçador, não outra lista
for jogo, r in resultados.items():
    diz = [m for m in (r.get("msgs") or []) if "açador decide" in m]
    if not diz:
        continue
    do_cacador = diz[0].split("]", 1)[1].split("—")[0].split()
    pad = [str(x) for x in (r.get("pad5") or [])]
    checa(pad and pad[0] in do_cacador,
          f"{jogo}: o primeiro da tela é do Caçador", (pad[:3], do_cacador[:3]))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] sem palpite do Caçador, a tela fica vazia")

# Sem `linhas` não há rodada de multiplicador, então o Caçador não fala. A tela
# NÃO pode cair para outra fonte -- ele pediu somente o Caçador.
l = linhas_de("lightning")
r_sem = M.PipelinePerceptivo("lightning").processar(
    [x["n"] for x in l], 0, 0, settled=[x["settled"] for x in l]) or {}
checa(not (r_sem.get("pad5") or []),
      "sem o Caçador a tela fica sem número", r_sem.get("pad5"))
avisou = [m for m in (r_sem.get("msgs") or []) if "sem palpite do Caçador" in m]
checa(bool(avisou), "e o log explica por quê", avisou[:1])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] o palpite não vaza de uma volta para a outra")

p = M.PipelinePerceptivo("lightning")
p.processar([x["n"] for x in l], 0, 0,
            settled=[x["settled"] for x in l], linhas=l)
guardado = list(getattr(p, "_cacador_consenso", []))
checa(bool(guardado), "a primeira volta guarda o palpite", guardado[:3])
r2 = p.processar([x["n"] for x in l], 0, 0,
                 settled=[x["settled"] for x in l]) or {}
checa(not (getattr(p, "_cacador_consenso", []) or []),
      "a volta sem linhas zera o palpite (não repete o velho)",
      getattr(p, "_cacador_consenso", []))
checa(not (r2.get("pad5") or []),
      "e a tela não mostra número velho como se fosse novo", r2.get("pad5"))

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("CACADOR_DECIDE_OK")
