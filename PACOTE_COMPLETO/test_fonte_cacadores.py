# -*- coding: utf-8 -*-
"""Confere que cada caçador declara a teoria dele que está testando.

    "todas ias devem aprender tudo que eu ditos nestes 3 pdfs"

A auditoria mostrou que os 25 caçadores -- justamente os que procuram vício --
decidiam sem consultar estudo nenhum. Agora cada um declara de qual formulação
do Tratado e de qual faixa do Compêndio ele saiu.

O teste cobra as cinco coisas que separam procedência de etiqueta:

  1. todo caçador de verdade tem teoria; os CANÁRIOS não têm, de propósito
  2. a citação é da mesa certa -- e mesa com sufixo não pode cair na errada
  3. mesas diferentes citam formulações diferentes
  4. o mapa não cita agente que não existe, nem esquece agente que existe
  5. sem o índice na pasta, degrada para silêncio em vez de estourar

    python test_fonte_cacadores.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import fonte_cacadores as F  # noqa: E402
from academia_autonoma import agentes_ocorrencia as A  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] todo caçador declara a teoria dele — menos os canários")

c = F.cobertura()
checa(c["com_teoria"] >= 25, "pelo menos os 25 caçadores têm teoria dele",
      c)
sem = [k for k, (ia, fx, _m) in F.MAPA.items() if not ia and not fx]
checa(set(sem) == set(A.CANARIOS),
      "e os únicos sem teoria são os canários", (sem, sorted(A.CANARIOS)))

# o canário existe para disparar em roda honesta e denunciar crivo frouxo.
# Amarrá-lo a uma teoria dele seria dar respaldo a um detector feito para errar.
for canario in A.CANARIOS:
    if F.texto_teoria(canario, "lightning"):
        checa(False, "canário não recebe respaldo de teoria dele", canario)
        break
else:
    checa(True, "nenhum canário recebe respaldo de teoria dele")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] a citação é da mesa certa")

for jogo, esperado in (("mega_fire", "MEGA FIRE"), ("lightning", "LIGHTING"),
                       ("crazy_time", "CRAZY TIME"),
                       ("crazy_time_a", "CRAZY TIME A")):
    checa(F.mesa_do(jogo) == esperado, f"{jogo} → {esperado}", F.mesa_do(jogo))

# A Immersive saiu do software por decisão dele. Um teste que continua
# cobrando a citação dela mantém a mesa viva no código só para o teste passar
# -- e foi assim que ela sobreviveu em 54 arquivos depois de "removida".
checa(F.mesa_do("immersive") == "",
      "a Immersive não cita mais mesa nenhuma", F.mesa_do("immersive"))

# O caso que quebraria em silêncio: `crazy_time_a` começa com `crazy_time`.
# Sem prefixo mais longo, a mesa A citaria a formulação da mesa comum -- e
# citar a fonte errada é pior que não citar.
checa(F.mesa_do("crazy_time_a_casino") == "CRAZY TIME A",
      "sufixo não faz crazy_time_a cair em crazy_time",
      F.mesa_do("crazy_time_a_casino"))
checa(F.mesa_do("lightning_br") == "LIGHTING", "sufixo comum é tolerado")
checa(F.mesa_do("mesa_que_nao_existe") == "",
      "mesa desconhecida não vira citação inventada")
checa(F.texto_teoria("O07_SETOR", "mesa_que_nao_existe").startswith("compêndio"),
      "e nesse caso sobra só a faixa do compêndio, que não depende de mesa")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] cada mesa cita as formulações dela")

ns = {}
for jogo in ("mega_fire", "lightning", "crazy_time", "crazy_time_a"):
    t = F.teoria_de("O07_SETOR", jogo)
    ns[jogo] = t.get("formulacao")
checa(len(set(ns.values())) == 4,
      "as quatro mesas citam formulações distintas", ns)
checa(all(v for v in ns.values()), "e nenhuma ficou sem citação", ns)

t = F.teoria_de("O10_RETORNO", "mega_fire")
checa(t.get("ia") == "IA01", "O10_RETORNO sai da IA01 (tempo e intervalos)", t.get("ia"))
checa(t.get("formula"), "e traz a fórmula publicada dele junto", t.get("formula"))
checa("fichas" in t, "e a faixa do compêndio", t.get("fichas"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] o mapa e os agentes falam do mesmo conjunto")

import re  # noqa: E402
txt = (RAIZ / "academia_autonoma" / "agentes_ocorrencia.py").read_text(
    encoding="utf-8")
reais = set(re.findall(r'"((?:O\d+[A-Z]?|C9\d)_[A-Z_0-9]+)"', txt))
mapeados = set(F.MAPA)
orfaos = sorted(reais - mapeados)
fantasmas = sorted(mapeados - reais)
checa(not orfaos, "nenhum caçador ficou sem entrada no mapa", orfaos)
checa(not fantasmas, "e o mapa não cita caçador que não existe", fantasmas)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] degrada sem estourar")

guardado = F.ARQ_INDICE
try:
    F.ARQ_INDICE = RAIZ / "nao_existe_este_arquivo.json"
    F._IDX = None
    r = F.texto_teoria("O07_SETOR", "lightning")
    checa(isinstance(r, str), "sem índice na pasta, devolve texto e não estoura", r)
    checa("formulação" not in r,
          "e não inventa número de formulação que não pôde ler", r)
finally:
    F.ARQ_INDICE = guardado
    F._IDX = None

checa(F.texto_teoria("AGENTE_QUE_NAO_EXISTE", "lightning") == "",
      "agente desconhecido não recebe teoria")
checa(F.contraditorio_de("C90_PRIMO", "lightning") == "",
      "canário não tem contraditório dele para buscar")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] o painel cabe na tela")
print("       " + F.resumo("mega_fire").replace("\n", "\n       ")[:1500])

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("FONTE_CACADORES_OK")
