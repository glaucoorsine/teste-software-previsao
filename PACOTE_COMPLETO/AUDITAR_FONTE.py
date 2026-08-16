# -*- coding: utf-8 -*-
"""
AUDITAR FONTE — quanto do que decide o número vem dos estudos dele.

    python AUDITAR_FONTE.py

A PERGUNTA
──────────
    "Mas os 3 pdfs estão como base para funcionamento do software?"

É uma pergunta de auditoria, e merece resposta de auditoria: não a minha
opinião, e sim a CONTA. Toda voz que entra no consenso tem um peso; este
arquivo soma esses pesos separando o que saiu dos estudos dele do que eu
inventei sozinho.

Se a resposta fosse "sim" por educação e a conta dissesse 20%, ele estaria
tomando decisão sobre um software que não é o que eu disse que era.

COMO A CONTA É FEITA
────────────────────
Cada voz é classificada em três categorias, pela origem REAL do código:

    DELE        implementa fórmula ou prática publicada num dos três estudos,
                e consegue citar de onde
    MISTA       nasceu de heurística minha mas foi corrigida por uma ficha
                dele -- o crivo, o N efetivo, os controles negativos
    MINHA       eu inventei; não tem respaldo em estudo nenhum

O peso é o que a voz leva para `Critico.consenso()`. Somar peso é o certo aqui
porque é literalmente o que decide o número na tela: quem pesa mais, decide
mais.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

# ─────────────────────────────────────────────────────────────────────────────
# A classificação. Cada entrada: (nome, peso, categoria, de onde saiu)
#
# Os pesos vêm de `grep hips.append ia_modulos.py`. Onde o peso é variável
# (peso*_wa, por exemplo) está o valor nominal.
VOZES = [
    # ── as que executam matemática publicada por ele ────────────────────────
    ("IA01_TEMPO", 2.4, "DELE", "Tratado, 16 formulações por mesa · D_t"),
    ("IA02_RECENCIA", 2.4, "DELE", "Tratado · p_s(t) beta-binomial multiescala"),
    ("IA03_MOTIVOS", 2.4, "DELE", "Tratado · PMI"),
    ("IA04_TRANSICAO", 2.4, "DELE", "Tratado · P_ab com Dirichlet"),
    ("IA05_VIZINHANCA", 2.4, "DELE", "Tratado · I_3 informação de interação"),
    ("IA06_RAJADA", 2.4, "DELE", "Tratado · coeficiente de rajada B"),
    ("IA07_REGIME", 2.4, "DELE", "Tratado · K_t consenso de detectores"),
    ("IA08_GEOMETRIA", 2.4, "DELE", "Tratado · imersão temporal v_t"),
    ("IA09_SURPRESA", 2.4, "DELE", "Tratado · S_B divergência KL"),
    ("IA10_INTENSIDADE", 2.4, "DELE", "Tratado · modelo hurdle"),
    ("IA11_FAMILIARIDADE", 2.4, "DELE", "Tratado · I_q resíduo de interferência"),

    ("E01_FREQUENCIA", 1.7, "DELE", "Compêndio, fichas 001-015"),
    ("E02_DEPENDENCIA", 1.7, "DELE", "Compêndio, fichas 016-025"),
    ("E03_REGIME", 1.7, "DELE", "Compêndio, fichas 026-030"),
    ("E04_MEMORIA", 1.7, "DELE", "Compêndio, fichas 031-040"),
    ("E05_RARIDADE", 1.7, "DELE", "Compêndio, fichas 041-050"),
    ("E06_CICLO", 1.7, "DELE", "Compêndio, fichas 051-060"),
    ("E07_BORDA", 1.7, "DELE", "Compêndio, fichas 061-080"),
    ("E08_CALIBRACAO", 1.7, "DELE", "Compêndio, fichas 081-100"),
    ("E09_INFORMACAO", 1.7, "DELE", "Compêndio, fichas 101-120"),
    ("E10_COMPLEXIDADE", 1.7, "DELE", "Compêndio, fichas 121-135"),
    ("E11_CAUSALIDADE", 1.7, "DELE", "Compêndio, fichas 136-160"),
    ("E12_DINAMICA", 1.7, "DELE", "Compêndio, fichas 161-185"),
    ("E13_MEDICAO", 1.7, "DELE", "Compêndio, fichas 186-200"),
    ("E14_MULT_OCORRENCIA", 1.7, "DELE", "Estudo multiplicadores, lente ocorrência"),
    ("E15_MULT_MAGNITUDE", 1.7, "DELE", "Estudo multiplicadores, lente magnitude"),
    ("E16_VIESES", 1.7, "DELE", "Compêndio, fichas 201-300"),
    ("E17_FISICA", 1.7, "DELE", "Compêndio, fichas 301-400"),

    ("C006_SOBREDISPERSAO", 1.5, "DELE", "Compêndio, ficha 006"),
    ("C011_SUBDISPERSAO", 1.5, "DELE", "Compêndio, ficha 011"),
    ("C016_AUTOCORRELACAO", 1.5, "DELE", "Compêndio, ficha 016"),
    ("C026_REGIME", 1.5, "DELE", "Compêndio, ficha 026"),
    ("C031_MEMORIA_LONGA", 1.5, "DELE", "Compêndio, ficha 031"),
    ("C036_REVERSAO", 1.5, "DELE", "Compêndio, ficha 036"),
    ("C041_RARIDADES", 1.5, "DELE", "Compêndio, ficha 041"),
    ("C046_RENOVACAO", 1.5, "DELE", "Compêndio, ficha 046"),
    ("C051_PERIODICIDADE", 1.5, "DELE", "Compêndio, ficha 051"),
    ("C111_INFO_MUTUA", 1.5, "DELE", "Compêndio, ficha 111"),
    ("C176_RECORRENCIA", 1.5, "DELE", "Compêndio, ficha 176"),

    ("MULT_* (7 por mesa)", 2.6, "DELE", "Estudo multiplicadores, 416 fichas"),

    # ── minhas, corrigidas por ficha dele ───────────────────────────────────
    ("ANOMALIA", 1.5, "MISTA", "minha; ficha 226 corrigiu o falso positivo"),
    ("SETOR", 2.0, "MISTA", "minha; corte de desvio veio das fichas 301-400"),
    ("FINAIS", 1.4, "MISTA", "família de finais foi teoria DELE, código meu"),
    ("GAP_CICLO", 2.2, "MISTA", "minha; critério de atraso é regra dele"),

    # ── minhas, sem respaldo em estudo nenhum ───────────────────────────────
    ("ESTAT", 1.3, "MINHA", "contagem simples que eu escrevi"),
    ("LSTM", 2.6, "MINHA", "rede que eu montei"),
    ("HEURISTICA", 1.0, "MINHA", "regra minha"),
    ("DESCOBERTA", 2.4, "MINHA", "fabricante de teorias que eu escrevi"),
    ("APLICADORES", 2.2, "MINHA", "meu"),
    ("REGRA_OPERADOR", 1.6, "MINHA", "minha"),
    ("REGRA_OPERADOR_ESTREITA", 1.6, "MINHA", "minha"),
    ("REGRA_TRANSICAO", 1.6, "MINHA", "minha"),
    ("REGRA_FAMILIA_QUENTE", 1.6, "MINHA", "minha"),
    ("ACADEMIA_* (teorias)", 1.4, "MINHA", "academia autônoma, invenção minha"),
    ("CT_FREQUENTE", 1.8, "MINHA", "minha"),
    ("CT_TRANSICAO", 1.6, "MINHA", "minha"),
    ("ANTI_12", 1.4, "MINHA", "minha"),
]

CORES = {"DELE": "estudos dele", "MISTA": "minha, corrigida por ficha dele",
         "MINHA": "invenção minha"}


def confere_pesos() -> list:
    """Lê os pesos que estão MESMO no código, para a tabela não mentir."""
    arq = RAIZ / "ia_modulos.py"
    if not arq.is_file():
        return []
    txt = arq.read_text(encoding="utf-8", errors="ignore")
    achados = re.findall(r'"nome"\s*:\s*"?([A-Za-z_0-9{}]+)"?.*?"peso"\s*:\s*'
                         r'([0-9.]+)', txt, re.S)
    return achados


def main() -> int:
    print("\n  Os três estudos dele são a base do software?")
    print("  A conta, por peso de voto no consenso.\n")

    tot = {}
    n = {}
    for _nome, peso, cat, _fonte in VOZES:
        tot[cat] = tot.get(cat, 0.0) + peso
        n[cat] = n.get(cat, 0) + 1
    soma = sum(tot.values()) or 1.0

    for cat in ("DELE", "MISTA", "MINHA"):
        if cat in tot:
            print(f"  {CORES[cat]:<34} {n[cat]:3d} vozes   "
                  f"peso {tot[cat]:6.1f}   {100 * tot[cat] / soma:5.1f}%")
    print(f"  {'':<34} {sum(n.values()):3d} vozes   peso {soma:6.1f}   100.0%")

    dele = 100 * tot.get("DELE", 0) / soma
    mista = 100 * tot.get("MISTA", 0) / soma
    print(f"\n  Executando estudo dele:            {dele:5.1f}% do peso")
    print(f"  Com correção vinda de ficha dele:  {dele + mista:5.1f}% do peso")

    print("\n  ── as que executam matemática publicada por ele ──")
    for nome, peso, cat, fonte in VOZES:
        if cat == "DELE":
            print(f"     {nome:<24} {peso:4.1f}   {fonte}")

    print("\n  ── as que eu inventei, sem respaldo em estudo ──")
    for nome, peso, cat, fonte in VOZES:
        if cat == "MINHA":
            print(f"     {nome:<24} {peso:4.1f}   {fonte}")

    print("\n  Observação sobre o que esta conta NÃO diz: peso alto não é")
    print("  acerto. A medição de acertividade é outra conta, em")
    print("  MEDIR_TRATADO.py, e lá as inteligências dele estão em 0,98x.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
