# -*- coding: utf-8 -*-
"""
TESTE DOS CACADORES DE OCORRENCIA

Duas perguntas, e as duas precisam de resposta certa:

  1. Em roleta LIMPA eles ficam calados?
     (se acharem padrao onde nao ha, sao uma maquina de alucinar)

  2. Em roleta com vicio PLANTADO eles acham?
     (se ficarem calados quando ha sinal, sao inuteis)

    python teste_ocorrencia.py
"""
import sys, os, random
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

from academia_autonoma.agentes_ocorrencia import cacar, resumo, RODA, POS, _final

falhas = []
def ck(c, t, d=""):
    print(f"  [{'OK  ' if c else 'FALHA'}] {t}")
    if not c:
        if d: print(f"          {d}")
        falhas.append(t)

N_MUNDOS = 25
GIROS = 300

print("=" * 70)
print("1 — ROLETA LIMPA: eles ficam calados?")
print("=" * 70)
rng = random.Random(4)
com_achado = 0
achados_tot = 0
for i in range(N_MUNDOS):
    seq = [rng.randrange(37) for _ in range(GIROS)]
    r = cacar(seq, n_regua=200)
    if r["achados"]:
        com_achado += 1
        achados_tot += len(r["achados"])
print(f"  {N_MUNDOS} roletas honestas de {GIROS} giros")
print(f"  mundos com ALGUM achado: {com_achado}  ({100*com_achado/N_MUNDOS:.0f}%)")
print(f"  achados no total: {achados_tot}")
ck(com_achado / N_MUNDOS <= 0.20,
   f"falso positivo <= 20% (deu {100*com_achado/N_MUNDOS:.0f}%)",
   "estao inventando padrao em ruido")

print("\n" + "=" * 70)
print("2 — VICIO PLANTADO: eles acham?")
print("=" * 70)

def com_vicio_final(n, forca, seed):
    """Depois de final 4/5/9, o proximo tambem tem final 4/5/9 com prob `forca`."""
    rng = random.Random(seed)
    grupo = [x for x in range(37) if _final(x) in (4, 5, 9)]
    c = [rng.randrange(37)]
    while len(c) < n:
        if _final(c[-1]) in (4, 5, 9) and rng.random() < forca:
            c.append(rng.choice(grupo))
        else:
            c.append(rng.randrange(37))
    return c

achou = 0
exemplos = []
for i in range(N_MUNDOS):
    seq = com_vicio_final(GIROS, 0.55, 100 + i)
    r = cacar(seq, n_regua=200)
    pegou = any(a["agente"] == "O02_FINAIS" and a["atributo"].split("@")[0] in ("4","5","9")
                for a in r["achados"])
    if pegou:
        achou += 1
        if len(exemplos) < 2:
            exemplos.append(resumo(r))
print(f"  {N_MUNDOS} roletas com finais 4/5/9 puxando finais 4/5/9 (55%)")
print(f"  o agente O02_FINAIS pegou em: {achou}  ({100*achou/N_MUNDOS:.0f}%)")
ck(achou / N_MUNDOS >= 0.70,
   f"detecta o vicio em >= 70% dos mundos (deu {100*achou/N_MUNDOS:.0f}%)")
if exemplos:
    print("\n  exemplo do que ele reporta:")
    for l in exemplos[0].split("\n")[:5]:
        print("   " + l)

print("\n" + "=" * 70)
print("3 — VICIO DE SETOR: eles acham na roda fisica?")
print("=" * 70)
def com_vicio_setor(n, forca, seed):
    rng = random.Random(seed)
    setor = [x for x in RODA[10:15]]
    return [rng.choice(setor) if rng.random() < forca else rng.randrange(37)
            for _ in range(n)]
achou = 0
for i in range(N_MUNDOS):
    r = cacar(com_vicio_setor(GIROS, 0.30, 200 + i), n_regua=200)
    # vicio de roda e MARGINAL: quem pega e o O14, nao o O07 (sequencia)
    if any(a["agente"] in ("O14_VIES_SETOR","O13_VIES_NUMERO") for a in r["achados"]):
        achou += 1
print(f"  setor da roda saindo 30% mais: pegou em {achou}/{N_MUNDOS} "
      f"({100*achou/N_MUNDOS:.0f}%)")
ck(achou / N_MUNDOS >= 0.60, f"detecta vicio de setor (deu {100*achou/N_MUNDOS:.0f}%)")

print("\n" + "=" * 70)
print("4 — nao quebra com entrada estranha")
print("=" * 70)
for nome, entrada in (("vazio", []), ("curto", [1, 2, 3]),
                      ("texto", ["CoinFlip", "1", "2"] * 30),
                      ("misto", [1, "2", None, 3.0, "x"] * 40)):
    try:
        r = cacar(entrada, n_regua=20)
        ck(isinstance(r, dict), f"{nome}: devolveu resultado sem quebrar")
    except Exception as e:
        ck(False, f"{nome}: quebrou", f"{type(e).__name__}: {e}")

print("\n" + ("TODOS OS TESTES PASSARAM" if not falhas else f"FALHAS: {len(falhas)}"))
for f in falhas:
    print("  - " + f)
sys.exit(1 if falhas else 0)
