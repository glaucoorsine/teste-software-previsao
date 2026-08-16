# -*- coding: utf-8 -*-
"""Confere os especialistas nos dois PDFs dele.

Ele pediu quinze IAs especialistas nos PDFs opinando sobre os numeros, "com
todo o PDF como base de consulta". Sao dezessete no fim -- quinze deixavam 40
conceitos sem dono (os eixos de IA/validacao e de fisica).

O teste cobra as cinco coisas que separam especialista de enfeite:

  1. TODA ficha tem dono. Se sobrou conceito orfao, o PDF nao foi lido inteiro.
  2. Cada um consulta a faixa DELE -- e as faixas nao se pisam.
  3. Quem nao tem o que dizer se CALA. Especialista que fala sempre e um que
     nao sabe do que fala; e o silencio dele tambem informa.
  4. O auditor (E16) roda por ULTIMO, porque a opiniao dele e sobre a dos
     outros -- se rodasse antes, auditaria o vazio.
  5. Achado plantado tem que ser achado. Vies de setor na roda, numero
     dominante, atraso longo: quem e dono do assunto tem que apontar.

    python test_especialistas.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import biblioteca_teorias as B  # noqa: E402
from academia_autonoma import especialistas_pdf as E  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] o PDF inteiro tem dono -- nenhum conceito orfao")

cs = B.conceitos()
TOTAL_FICHAS = len(cs) * E.FICHAS_POR_CONCEITO      # 80 blocos x 5 = 400
donos = {}
for nome, _fn, (a, b), _d in E.ESPECIALISTAS:
    if not b:
        continue
    for c in cs:
        if a <= int(c["n"]) <= b:
            donos.setdefault(int(c["n"]), []).append(nome)

checa(len(donos) == len(cs),
      f"os {len(cs)} conceitos tem dono", f"{len(donos)} de {len(cs)}")
duplos = {k: v for k, v in donos.items() if len(v) > 1}
checa(not duplos, "e nenhum tem dois donos (faixas nao se pisam)",
      list(duplos.items())[:3])

# a faixa nao pode cortar um bloco ao meio: se E01 vai ate a ficha 015, o
# bloco que comeca na 011 tem que caber inteiro dentro dela (011-015).
cortados = [int(c["n"]) for c in cs
            for _n, _f, (a, b), _d in E.ESPECIALISTAS
            if b and a <= int(c["n"]) <= b
            and int(c["n"]) + E.FICHAS_POR_CONCEITO - 1 > b]
checa(not cortados, "nenhuma faixa corta um bloco de fichas ao meio",
      cortados[:5])

fichas_cobertas = sum(E.quantas_fichas(n) for n, _f, _fx, d in E.ESPECIALISTAS
                      if _fx[1])
checa(fichas_cobertas == TOTAL_FICHAS,
      f"a soma das faixas fecha em {TOTAL_FICHAS} fichas", fichas_cobertas)
checa(len(E.ESPECIALISTAS) >= 15,
      "sao pelo menos os quinze que ele pediu", len(E.ESPECIALISTAS))
checa(all(E.especialidade(n) for n, _f, _x, _d in E.ESPECIALISTAS),
      "cada um diz de que e especialista")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] eles consultam a ficha, nao inventam")

for nome, _fn, (a, b), _d in E.ESPECIALISTAS:
    if not b:
        continue
    fs = E.fichas_de(a, b)
    if not fs:
        checa(False, f"{nome} acha as fichas {a:03d}-{b:03d}", "faixa vazia")
        break
    if not all(a <= int(f["n"]) <= b for f in fs):
        checa(False, f"{nome} so pega as fichas dele", "vazou da faixa")
        break
else:
    checa(True, "toda faixa devolve ficha, e so a da faixa")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] quem nao tem o que dizer, se cala")

rnd = random.Random(7)
ruido = [rnd.randrange(37) for _ in range(400)]
r = E.consultar(ruido, 37, {"jogo": "lightning"})
checa(r["total"] == len(E.ESPECIALISTAS), "todos foram consultados")
checa(r["opinaram"] < r["total"],
      "em roda honesta nem todos apontam numero",
      f"{r['opinaram']} de {r['total']}")
checa(all(r["falas"].get(n) for n, _f, _x, _d in E.ESPECIALISTAS),
      "e o silencio vem com motivo escrito")
sem_palpite = [n for n in r["falas"] if n not in r["palpites"]]
checa(sem_palpite, "existe silencio de verdade", sem_palpite[:4])

# nada de palpite vazio ou com numero fora da mesa
for n, nums in r["palpites"].items():
    if not nums or any(not str(x).lstrip("-").isdigit() or
                       not (0 <= int(x) <= 36) for x in nums):
        checa(False, f"{n} devolve numero valido da roleta", nums)
        break
else:
    checa(True, "todo palpite e numero real da mesa")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] o auditor opina depois dos outros, nao antes")

visto = {}


def _espiao(seq, n_classes, ctx):
    visto["viu"] = dict(ctx.get("palpites_ate_agora") or {})
    return {}, "espiao"


orig = E.ESPECIALISTAS
E.ESPECIALISTAS = tuple(
    (n, _espiao, fx, d) if n == "E16_VIESES" else (n, f, fx, d)
    for n, f, fx, d in orig)
try:
    E.consultar(ruido, 37, {"jogo": "lightning"})
finally:
    E.ESPECIALISTAS = orig
checa("viu" in visto, "o auditor recebeu o painel")
checa(visto.get("viu"), "e ele ja estava preenchido quando o auditor falou",
      "chegou vazio -- rodou antes dos outros")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] achado plantado tem que ser achado")

# 5a. um numero dominante -- quem cuida de frequencia tem que ver
viciada = [rnd.randrange(37) for _ in range(400)]
for i in range(0, 400, 4):
    viciada[i] = 17
r2 = E.consultar(viciada, 37, {"jogo": "lightning"})
freq = r2["palpites"].get("E01_FREQUENCIA") or []
checa("17" in freq, "E01 ve o numero que aparece 4x demais", freq)

# 5b. um setor contiguo da roda quente -- e a assinatura de vicio FISICO,
#     a unica que da para enxergar com o dado que ele tem
SETOR = [5, 24, 16, 33, 1, 20, 14]
setorial = [rnd.randrange(37) for _ in range(500)]
for i in range(0, 500, 3):
    setorial[i] = rnd.choice(SETOR)
r3 = E.consultar(setorial, 37, {"jogo": "lightning"})
fis = r3["palpites"].get("E17_FISICA") or []
checa(fis, "E17 aponta quando um setor da roda esta quente", r3["falas"].get("E17_FISICA"))
checa(sum(1 for x in fis if int(x) in SETOR) >= max(1, len(fis) // 2),
      "e o que ele aponta esta mesmo no setor plantado", fis)

# ... e o outro lado, que e o que importa de verdade: em roda HONESTA ele
# tem que ficar quieto. Varrer 37 janelas e ficar com a maior nao e o mesmo
# que olhar uma: no corte de 1,5 desvio isto aqui acusava vicio fisico em
# ~4 de cada 10 rodas limpas. Alarme falso e pior que silencio.
alarmes = 0
for semente in range(120):
    rr = random.Random(1000 + semente)
    limpa = [rr.randrange(37) for _ in range(250)]
    if E.consultar(limpa, 37, {"jogo": "lightning"})["palpites"].get("E17_FISICA"):
        alarmes += 1
taxa = alarmes / 120
print(f"       alarme falso de vicio fisico em roda honesta: {taxa:.1%} (120 rodas)")
checa(taxa <= 0.10, "E17 nao inventa vicio fisico em roda honesta", f"{taxa:.1%}")

# 5c. numero em atraso longo -- quem cuida de raridade/renovacao tem que ver
atrasado = [rnd.choice([x for x in range(37) if x != 8]) for _ in range(300)]
r4 = E.consultar(atrasado, 37, {"jogo": "lightning"})
rar = r4["palpites"].get("E05_RARIDADE") or []
checa("8" in rar, "E05 ve o numero que nao vem ha 300 giros", rar)

# 5d. A DIRECAO do atraso. O historico vem recente-primeiro; se a leitura se
#     inverte, o numero que ACABOU de sair vira "o mais atrasado da mesa" --
#     exatamente o avesso do criterio dele ("so o que ta muito tempo sem vir").
#     O 21 sai no giro mais recente e de 3 em 3; o 8 sumiu ha 150 giros.
direcao = []
for i in range(300):
    if i < 150 and i % 3 == 0:
        direcao.append(21)
    elif i >= 150 and i % 7 == 0:
        direcao.append(8)
    else:
        direcao.append(rnd.choice([x for x in range(2, 37)
                                   if x not in (8, 21)]))
direcao[0] = 21
r5 = E.consultar(direcao, 37, {"jogo": "lightning"})
rar5 = r5["palpites"].get("E05_RARIDADE") or []
checa("21" not in rar5,
      "E05 nao chama de atrasado quem acabou de sair", rar5)
checa("8" in rar5, "e ve o 8, que nao vem ha 150 giros", rar5)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] nao quebra com pouco dado nem com dado torto")

for seq in ([], [1], [1, 2, 3], [None, "", "x", 5, 5], list(range(37))):
    try:
        rr = E.consultar(seq, 37, {"jogo": "lightning"})
    except Exception as e:
        checa(False, "aguenta historico curto/sujo", f"{type(e).__name__} em {seq[:5]}")
        break
    if any("erro:" in (rr["falas"].get(n) or "")
           for n, _f, _x, _d in E.ESPECIALISTAS):
        quem = [n for n in rr["falas"] if "erro:" in (rr["falas"][n] or "")]
        checa(False, "aguenta historico curto/sujo", f"{quem} em {seq[:5]}")
        break
else:
    checa(True, "aguenta historico curto, vazio e com lixo dentro")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] o painel cabe na tela")
txt = E.resumo(setorial, 37, {"jogo": "lightning"})
print("       " + txt.replace("\n", "\n       "))
checa("Especialistas" in txt, "o resumo se identifica")
checa("fichas" in txt, "e diz de que faixa do PDF cada um fala")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("ESPECIALISTAS_OK")
