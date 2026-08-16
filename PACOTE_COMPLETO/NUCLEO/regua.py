# -*- coding: utf-8 -*-
"""
A RÉGUA — o nulo certo é o placebo dele, não a conta k/N.

O QUE ACONTECEU
───────────────
Medi a família F07 (densidade longa) nas bases reais dele e deu 1,238x acima
do acaso, com p=0,0028. Sobreviveu até à correção de Benjamini-Hochberg sobre
as 23 famílias com amostra. Parecia achado.

Antes de anunciar, rodei a F35 do Tratado dele -- "controles negativos e
placebos temporais":

    Δ_neg = Skill(X_legit) - max_j Skill(X_placebo_j)

Embaralhar a ordem dos MESMOS números destrói toda estrutura temporal. Se a
leitura estivesse lendo tempo, o embaralhado tinha que cair para 1,00x.

    dado real                1,238x
    mediana dos 12 placebos  1,102x     ← devia ser 1,000x

O placebo dá 10% de "vantagem" com o tempo destruído. Ou seja: a régua k/N
estava inflada, e parte do que eu chamaria de descoberta era artefato da
própria medição.

POR QUE ISSO ACONTECE
─────────────────────
A leitura escolhe as 12 classes mais frequentes do passado, e o alvo vem do
MESMO arquivo finito. Num arquivo finito a distribuição empírica é desigual
por acaso, e o alvo compartilha essa desigualdade -- porque é o mesmo arquivo
que a produziu. Apostar nas mais frequentes de uma amostra finita bate 12/37
para prever outros sorteios DAQUELA amostra, sem que exista viés nenhum na
roda.

Não é vazamento temporal: o alvo nunca entra no histórico que o previu. É a
composição finita da amostra, e a conta fechada k/N não enxerga isso.

A CORREÇÃO
──────────
O nulo passa a ser o placebo, medido, não deduzido:

    razão_honesta = razão_observada / razão_mediana_dos_placebos
    p             = (quantos placebos alcançaram o real + 1) / (placebos + 1)

O p pela contagem de placebos é o teste de permutação -- exato, sem supor
distribuição nenhuma, e é o que o compêndio dele manda usar quando a
aproximação não serve.

Este arquivo existe porque a alternativa era eu te contar uma descoberta que
não existe. Já fiz isso uma vez neste projeto com os caçadores (68% de falso
positivo) e uma segunda com o vício físico (4 em 10 rodas honestas). A régua
dele pegou a terceira antes de sair da minha máquina.
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Sequence

PLACEBOS = 20          # 20 dá p mínimo de 1/21 ≈ 0,048, que cobre o corte de 5%


def binom_cauda(k: int, n: int, p: float) -> float:
    """P(X >= k) sob Binomial(n, p). Serve de referência, não de veredito."""
    if n <= 0 or k <= 0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
                        for i in range(k, n + 1)))


def razao(acertos: int, tentativas: int, esperado: float) -> float:
    if not tentativas or esperado <= 0:
        return 0.0
    return (acertos / tentativas) / (esperado / tentativas)


def medir_com_placebo(series: Sequence[List[int]],
                      avaliar: Callable[[Sequence[List[int]]], Any],
                      placebos: int = PLACEBOS,
                      semente: int = 20260816) -> Dict[str, Any]:
    """Mede de verdade: o real contra o embaralhado dos mesmos números.

    `avaliar` recebe a lista de séries e devolve (acertos, tentativas,
    esperado). É chamada uma vez no real e `placebos` vezes no embaralhado.

    O embaralhamento preserva a COMPOSIÇÃO (quais números, quantas vezes) e
    destrói só a ORDEM. É o contraste certo: separa "esta mesa tem números
    mais frequentes" -- que amostra finita sempre tem -- de "esta mesa tem
    estrutura no tempo", que é o que interessa.
    """
    a, n, e = avaliar(series)
    r_real = razao(a, n, e)

    rnd = random.Random(semente)
    rs: List[float] = []
    for _ in range(placebos):
        emb = []
        for s in series:
            c = list(s)
            rnd.shuffle(c)
            emb.append(c)
        a2, n2, e2 = avaliar(emb)
        if n2:
            rs.append(razao(a2, n2, e2))
    if not rs:
        return {"razao": r_real, "acertos": a, "tentativas": n,
                "placebos": 0, "motivo": "nenhum placebo pôde ser medido"}

    rs_ord = sorted(rs)
    mediana = rs_ord[len(rs_ord) // 2]
    alcancaram = sum(1 for x in rs if x >= r_real)
    # teste de permutação: o +1 impede p=0, que seria mentira com 20 placebos
    p_perm = (alcancaram + 1) / (len(rs) + 1)
    return {
        "acertos": a, "tentativas": n,
        "razao_bruta": r_real,
        "razao_placebo": mediana,
        "razao": (r_real / mediana) if mediana else 0.0,
        "delta_neg": r_real - mediana,
        "p": p_perm,
        "placebos": len(rs),
        "alcancaram": alcancaram,
        "p_ingenuo": binom_cauda(a, n, e / n) if n else 1.0,
        "motivo": (f"{a}/{n} = {r_real:.3f}x bruto; placebo {mediana:.3f}x; "
                   f"honesto {(r_real / mediana if mediana else 0):.3f}x; "
                   f"p={p_perm:.3f} ({alcancaram}/{len(rs)} placebos alcançaram)"),
    }


def benjamini_hochberg(ps: Dict[str, float], fdr: float = 0.05) -> List[str]:
    """Quais sobrevivem testando muitos ao mesmo tempo.

    Com 44 famílias, a melhor passa de 0,05 por sorte em ~90% das vezes. Sem
    esta correção, "a melhor de 44" é sempre uma descoberta -- e nunca é.
    """
    if not ps:
        return []
    ordem = sorted(ps.items(), key=lambda t: t[1])
    m = len(ordem)
    corte = 0
    for i, (_nome, p) in enumerate(ordem, 1):
        if p <= i / m * fdr:
            corte = i
    return [nome for nome, _p in ordem[:corte]]
