# -*- coding: utf-8 -*-
"""
MEDIR AS DOZE INTELIGÊNCIAS CONTRA O ACASO, NOS DADOS REAIS DELE.

    python MEDIR_TRATADO.py

POR QUE ESTE ARQUIVO EXISTE
───────────────────────────
Implementar a fórmula não prova nada. A pergunta dele é sempre a mesma, e é a
certa: "como está a assertividade?".

A COMPARAÇÃO HONESTA
────────────────────
Comparar aposta de tamanhos diferentes é fraude. Uma lista de 12 números acerta
mais que uma de 3 por construção -- não por ser mais inteligente.

Então tudo aqui é medido contra o ACASO DO MESMO TAMANHO:

    acaso = k / N          (k números apontados, N classes na mesa)
    razão = taxa / acaso   (1,00 = está no acaso. 1,20 = 20% acima)

E o p-valor é binomial exato contra esse mesmo acaso -- não contra zero.

FORA DA AMOSTRA
───────────────
Cada previsão usa SÓ o que veio antes dela. O giro que está sendo previsto
nunca entra no histórico que a produziu. Sem isso, qualquer método "acerta"
100% e a medição não vale nada -- é o vazamento temporal que o compêndio dele
descreve nas fichas 201-300.
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from academia_autonoma import inteligencias_livro as T  # noqa: E402

K = 12                  # o teto que ele fixou: "Mas 20 números é demais, deixe até 12"
MIN_HIST = 90           # histórico mínimo antes de deixar qualquer uma opinar
#
# 100 é um compromisso, e vale dizer qual. As bases dele têm de 110 a 194
# giros; com 150 sobravam duas de sete e 86 pontos de medição. Com 100 entram
# as sete e ~300 pontos. O preço é que as fórmulas que pedem 120+ (IA07, IA08,
# IA09, IA11) só falam nas bases maiores -- e por isso a tabela mostra o `n` de
# cada uma separado, em vez de um número só que esconderia isso.


def binom_cauda(k: int, n: int, p: float) -> float:
    """P(X >= k) sob Binomial(n, p). Exato, sem aproximação normal."""
    if n <= 0 or k <= 0:
        return 1.0
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(1.0, total)


def carregar():
    """As bases reais dele. Devolve (nome, jogo, lista recente-primeiro, mults)."""
    for arq in sorted(glob.glob(str(RAIZ / "bases_estudo" / "*.json"))):
        nome = Path(arq).name
        if nome == "INDICE.json":
            continue
        try:
            d = json.load(open(arq, encoding="utf-8"))
        except Exception:
            continue
        ev = d.get("events") or []
        if not isinstance(ev, list) or len(ev) < MIN_HIST + 15:
            continue
        nums, mults = [], []
        for e in ev:
            if not isinstance(e, dict):
                continue
            v = e.get("result", e.get("numero", e.get("n")))
            try:
                nums.append(int(v))
            except (TypeError, ValueError):
                continue
            m = e.get("multiplier", e.get("mult", 0))
            try:
                mults.append(float(m or 0))
            except (TypeError, ValueError):
                mults.append(0.0)
        if len(nums) >= MIN_HIST + 15:
            yield nome, d.get("jogo", "?"), nums, mults


def medir(nums, mults, n_classes=37):
    """Anda para trás no tempo prevendo cada giro só com o passado dele.

    Acumula, junto dos acertos, o ACASO ESPERADO de cada previsão -- porque
    cada inteligência aponta o tanto de número que a fórmula dela produziu.
    IA11 costuma apontar 1; IA01 aponta os 12. Cobrar as duas contra o mesmo
    acaso de 12/37 seria a fraude que o compêndio dele descreve, e foi
    exatamente o que a primeira versão deste arquivo fez.
    """
    acertos = defaultdict(int)
    tentou = defaultdict(int)
    esperado = defaultdict(float)          # Σ m_i / N, o acaso do tamanho certo
    a12 = n12 = 0
    e12 = 0.0

    # a lista vem recente-primeiro: o giro i é previsto pelo histórico i+1 em diante
    for i in range(0, len(nums) - MIN_HIST):
        alvo = nums[i]
        passado = nums[i + 1:]
        passado_m = mults[i + 1:] if mults else []
        r = T.consultar(passado, n_classes, {"mults": passado_m}, k=K)
        for ia, palpite in (r.get("palpites") or {}).items():
            p = palpite[:K]
            if not p:
                continue
            tentou[ia] += 1
            esperado[ia] += len(set(p)) / n_classes
            if str(alvo) in p:
                acertos[ia] += 1
        ag = T.consenso_ia12(r.get("pesos") or {}, None, k=K)
        if ag["ordem"]:
            o = ag["ordem"][:K]
            n12 += 1
            e12 += len(set(o)) / n_classes
            if str(alvo) in o:
                a12 += 1
    return acertos, tentou, esperado, a12, n12, e12


def linha(nome, a, n, esp):
    """`esp` é a soma dos acasos de cada previsão — o tamanho real apostado."""
    if not n:
        return f"  {nome:<20}      — não opinou"
    acaso = esp / n                     # acaso médio do tamanho que ela aposta
    taxa = a / n
    razao = taxa / acaso if acaso else 0
    p = binom_cauda(a, n, acaso)
    marca = "  <<<" if (p < 0.05 and razao > 1) else ""
    med = esp / n * 37                  # quantos números ela aponta, em média
    return (f"  {nome:<20} {a:4d}/{n:<4d}  {taxa:6.1%}  "
            f"acaso {acaso:5.1%} ({med:4.1f} núm)  {razao:5.2f}x  "
            f"p={p:6.4f}{marca}")


def main() -> int:
    print("\n  Medindo as doze inteligências do Tratado dele.")
    print(f"  k={K} números por previsão, fora da amostra, "
          f"contra o acaso do MESMO tamanho.\n")

    geral_a = defaultdict(int)
    geral_n = defaultdict(int)
    geral_e = defaultdict(float)
    g12_a = g12_n = 0
    g12_e = 0.0
    n_classes_por_base = {}
    por_jogo = {}

    bases = list(carregar())
    if not bases:
        print("  Nenhuma base real encontrada em bases_estudo/.")
        print("  (o container foi apagado, ou os arquivos ainda não chegaram)")
        return 0

    for nome, jogo, nums, mults in bases:
        n_classes = 37
        n_classes_por_base[nome] = n_classes
        print(f"  ── {nome}   ({jogo}, {len(nums)} giros, "
              f"{sum(1 for m in mults if m)} com multiplicador)")
        a, n, e, a12, n12, e12 = medir(nums, mults, n_classes)
        for ia, _f, _d, _x in T.INTELIGENCIAS:
            if n.get(ia):
                geral_a[ia] += a.get(ia, 0)
                geral_n[ia] += n[ia]
                geral_e[ia] += e[ia]
        g12_a += a12
        g12_n += n12
        g12_e += e12
        J = por_jogo.setdefault(jogo, [defaultdict(int), defaultdict(int),
                                       defaultdict(float), 0, 0, 0.0])
        for ia in n:
            J[0][ia] += a.get(ia, 0); J[1][ia] += n[ia]; J[2][ia] += e[ia]
        J[3] += a12; J[4] += n12; J[5] += e12
        print()

    for jogo in sorted(por_jogo):
        A, N, E, A2, N2, E2 = por_jogo[jogo]
        print(f"  ══ {jogo.upper()} ══")
        for ia, _f, _d, _x in T.INTELIGENCIAS:
            if N.get(ia):
                print(linha(ia, A[ia], N[ia], E[ia]))
        print(linha("IA12 (consenso)", A2, N2, E2))
        print()

    print("  ══ TODAS AS MESAS JUNTAS ══")
    for ia, _f, _d, _x in T.INTELIGENCIAS:
        if geral_n.get(ia):
            print(linha(ia, geral_a[ia], geral_n[ia], geral_e[ia]))
    print(linha("IA12 (consenso)", g12_a, g12_n, g12_e))

    print("\n  Leitura: 1,00x = está no acaso. p<0,05 marcado com <<<.")
    print("  Nada aqui autoriza extrapolar para o próximo giro — é medição")
    print("  retrospectiva, que é o que o próprio Tratado dele determina.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
