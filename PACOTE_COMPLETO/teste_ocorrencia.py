# -*- coding: utf-8 -*-
"""
TESTE DOS CACADORES DE OCORRENCIA

Duas perguntas, e as duas precisam de resposta certa:

  1. Em roleta LIMPA eles ficam calados?
     (se acharem padrao onde nao ha, sao uma maquina de alucinar)

  2. Em roleta com vicio PLANTADO eles acham?
     (se ficarem calados quando ha sinal, sao inuteis)

E o mais pesado da suite: 75 roletas de 300 giros, cada uma passando pela
regua de permutacao de 200 embaralhamentos. Em serie isso levava quarenta
minutos calado, e quarenta minutos calado nao dao para distinguir de um
travamento -- por isso as cacadas foram divididas pelos nucleos da maquina e
por isso a barra mostra o andamento.

A divisao nao muda numero nenhum: `cacar` tem semente propria e fixa, entao o
resultado de cada sequencia e o mesmo sozinho ou em paralelo.

    python teste_ocorrencia.py
"""
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from academia_autonoma.agentes_ocorrencia import (  # noqa: E402
    cacar, resumo, RODA, POS, _final)
from progresso_teste import Progresso  # noqa: E402

N_MUNDOS = 25
GIROS = 300


def _cacar1(seq):
    """Uma cacada. Fica no topo do arquivo porque o Pool precisa importa-la."""
    return cacar(seq, n_regua=200)


def _todas(seqs, rotulo):
    """As N cacadas, uma por nucleo quando da, mostrando o andamento."""
    prog = Progresso(len(seqs), titulo=rotulo)
    prog.mostrar(rotulo)
    saida = []
    try:
        import multiprocessing as mp
        n = min(len(seqs), max(1, os.cpu_count() or 1))
        if n > 1:
            with mp.Pool(n) as pool:
                for i, r in enumerate(pool.imap(_cacar1, seqs), 1):
                    saida.append(r)
                    prog.feito = i
                    prog.duracoes.append(0)      # so para a conta de ritmo
                    prog.mostrar(f"{rotulo} {i}/{len(seqs)}")
            print(prog.fim(f"{n} nucleos"))
            return saida
    except Exception as e:
        # NAO ENGOLIR EM SILENCIO. Cair para o modo serie e legitimo -- em
        # maquina de um nucleo, por exemplo -- mas cair sem dizer por que
        # transforma "quatro vezes mais lento" em misterio.
        print(f"\n  (sem paralelo: {type(e).__name__}: {str(e)[:70]} "
              f"-- seguindo em serie)")
        saida = []
    for i, s in enumerate(seqs, 1):
        saida.append(_cacar1(s))
        prog.feito = i
        prog.duracoes.append(0)
        prog.mostrar(f"{rotulo} {i}/{len(seqs)}")
    print(prog.fim())
    return saida


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


def com_vicio_setor(n, forca, seed):
    rng = random.Random(seed)
    setor = list(RODA[10:15])
    return [rng.choice(setor) if rng.random() < forca else rng.randrange(37)
            for _ in range(n)]


def main() -> int:
    falhas = []

    def ck(c, t, d=""):
        print(f"  [{'OK  ' if c else 'FALHA'}] {t}")
        if not c:
            if d:
                print(f"          {d}")
            falhas.append(t)

    print("=" * 70)
    print("1 — ROLETA LIMPA: eles ficam calados?")
    print("=" * 70)
    rng = random.Random(4)
    seqs = [[rng.randrange(37) for _ in range(GIROS)] for _ in range(N_MUNDOS)]
    com_achado = achados_tot = 0
    for r in _todas(seqs, "roletas limpas"):
        if r["achados"]:
            com_achado += 1
            achados_tot += len(r["achados"])
    print(f"  {N_MUNDOS} roletas honestas de {GIROS} giros")
    print(f"  mundos com ALGUM achado: {com_achado}  "
          f"({100 * com_achado / N_MUNDOS:.0f}%)")
    print(f"  achados no total: {achados_tot}")
    ck(com_achado / N_MUNDOS <= 0.20,
       f"falso positivo <= 20% (deu {100 * com_achado / N_MUNDOS:.0f}%)",
       "estao inventando padrao em ruido")

    print("\n" + "=" * 70)
    print("2 — VICIO PLANTADO: eles acham?")
    print("=" * 70)
    seqs2 = [com_vicio_final(GIROS, 0.55, 100 + i) for i in range(N_MUNDOS)]
    achou, exemplos = 0, []
    for r in _todas(seqs2, "vicio de final"):
        # O vicio plantado e de FAMILIA: final 4/5/9 puxa final 4/5/9. Entao
        # vale a deteccao por qualquer um dos dois caminhos -- o agente de
        # familia (a hipotese dele) ou o de digito solto.
        #
        # Isto ja foi so o digito, e o teste cobrava 70% de um agente que
        # matematicamente nao podia entregar: um efeito espalhado em tres
        # digitos chega partido em tres, e tres medidas fracas morrem no
        # controle de multiplos testes. Medido: 12% pelo digito, 100% pela
        # familia. Nao e o teste que estava exigente demais -- era a varredura
        # que nao tinha a hipotese certa.
        pegou = any(
            (a["agente"] == "O02F_FAMILIA_FINAL"
             and a["atributo"].startswith("4-5-9"))
            or (a["agente"] == "O02_FINAIS"
                and a["atributo"].split("@")[0] in ("4", "5", "9"))
            for a in r["achados"])
        if pegou:
            achou += 1
            if len(exemplos) < 2:
                exemplos.append(resumo(r))
    print(f"  {N_MUNDOS} roletas com finais 4/5/9 puxando finais 4/5/9 (55%)")
    print(f"  o agente O02_FINAIS pegou em: {achou}  "
          f"({100 * achou / N_MUNDOS:.0f}%)")
    ck(achou / N_MUNDOS >= 0.70,
       f"detecta o vicio em >= 70% dos mundos (deu {100 * achou / N_MUNDOS:.0f}%)")
    if exemplos:
        print("\n  exemplo do que ele reporta:")
        for l in exemplos[0].split("\n")[:5]:
            print("   " + l)

    print("\n" + "=" * 70)
    print("3 — VICIO DE SETOR: eles acham na roda fisica?")
    print("=" * 70)
    seqs3 = [com_vicio_setor(GIROS, 0.30, 200 + i) for i in range(N_MUNDOS)]
    achou = 0
    for r in _todas(seqs3, "vicio de setor"):
        # vicio de roda e MARGINAL: quem pega e o O14, nao o O07 (sequencia)
        if any(a["agente"] in ("O14_VIES_SETOR", "O13_VIES_NUMERO")
               for a in r["achados"]):
            achou += 1
    print(f"  setor da roda saindo 30% mais: pegou em {achou}/{N_MUNDOS} "
          f"({100 * achou / N_MUNDOS:.0f}%)")
    ck(achou / N_MUNDOS >= 0.60,
       f"detecta vicio de setor (deu {100 * achou / N_MUNDOS:.0f}%)")

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

    print("\n" + ("TODOS OS TESTES PASSARAM" if not falhas
                  else f"FALHAS: {len(falhas)}"))
    for f in falhas:
        print("  - " + f)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
