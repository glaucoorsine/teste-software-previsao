# -*- coding: utf-8 -*-
"""
TEORIAS — cada uma com o que afirma e o que a mataria.

AS TRÊS FAMÍLIAS, E POR QUE A DISTINÇÃO ENTRE ELAS É O ACHADO PRINCIPAL
──────────────────────────────────────────────────────────────────────
Passei a bateria inteira dividida em três famílias, e a divisão não é
organizacional: é a conclusão do estudo, adiantada.

ESTRUTURAL   Não prevê nada. Pergunta se a FORMA dos sorteios bate com a forma
             que a combinatória exige. "Quantas dezenas repetem do concurso
             anterior?" tem resposta exata — hipergeométrica, média 9 — e a
             pergunta científica é se o real bate com o exato. Aqui a taxa de
             acerto pode ser altíssima (80%, 90%) e isso NÃO é vantagem: é
             aritmética que qualquer um pode conferir antes do sorteio.

RANKING      Prevê QUAIS dezenas. Cada teoria devolve as 15 que ela escolheria,
             e eu conto quantas acertou. A linha de base é cruel e exata: sob
             acaso, QUALQUER escolha de 15 acerta 9,0 em média — as quentes, as
             frias, as atrasadas, as do aniversário da avó, todas. Uma teoria
             só existe se passar de 9,0 de forma que o controle negativo não
             reproduza.

DEPENDÊNCIA  Não aposta. Procura MEMÓRIA: o concurso de hoje sabe alguma coisa
             sobre o de ontem? Se existir previsão possível na Lotofácil, ela
             tem de aparecer aqui primeiro. Se não há memória, nenhuma teoria
             de ranking pode funcionar, e as que parecerem funcionar são ruído.

A ORDEM IMPORTA: dependência é a condição de possibilidade do ranking. Por isso
eu meço dependência com muito mais testes do que ranking.

O QUE EU ACRESCENTEI DE MINHA CABEÇA
────────────────────────────────────
As teorias marcadas MINHA não vieram do folclore de loteria nem de livro. São
tentativas de olhar para onde ninguém olha:

  COMPLEMENTO      todo mundo estuda as 15 que saíram; eu estudo as 10 que não
                   saíram. É um objeto menor, com estrutura mais rica, e
                   qualquer viés aparece mais concentrado nele.

  ECO POSICIONAL   a ordem em que as bolas saem do globo é publicada e quase
                   ninguém usa. Se houvesse física — desgaste, peso, posição —
                   ela apareceria na ordem e sumiria no conjunto ordenado.

  ATRITO DE PARES  a rede de coocorrência das 300 duplas: ela tem comunidades
                   mais fortes do que uma rede aleatória teria?

  NÚCLEO           existe um conjunto de dezenas que "vive junto" por janelas
                   longas, além do que a sobreposição forçada de 60% já
                   explica?

  MARÉ             a frequência das dezenas anda devagar ao longo de 21 anos
                   (troca de globo, de lote de bolas, de máquina)?

  ESPELHO          a simetria n ↔ 26-n do volante deixa marca?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from base import (AUSENTES, DEZENAS, DP_INTER, FIBONACCI, MEDIA_INTER, MIOLO,
                  MOLDURA, PMF_INTER, PRIMOS, SORTEADAS, UNIVERSO, Historico,
                  coluna, linha)

MATEMATICA, CRENCA, MINHA = "MATEMATICA", "CRENCA_COMUM", "MINHA"


@dataclass
class Teoria:
    """Uma afirmação que pode morrer. Sem `derruba`, não entra na bateria."""
    chave: str
    nome: str
    familia: str
    origem: str
    afirma: str
    derruba: str


# ═══════════════════════════════════════════ estatísticas estruturais
def _consecutivos(s: np.ndarray) -> int:
    """Quantos pares de dezenas vizinhas (n, n+1) o sorteio contém."""
    return int(np.sum(np.diff(s) == 1))

def _maior_sequencia(s: np.ndarray) -> int:
    maior = atual = 1
    for i in range(1, len(s)):
        atual = atual + 1 if s[i] - s[i - 1] == 1 else 1
        maior = max(maior, atual)
    return maior

def _n_aps(conj: frozenset) -> int:
    """Progressões aritméticas de 3 termos dentro do sorteio.

    Ideia minha: se houvesse qualquer estrutura aritmética residual no
    mecanismo, a contagem de PAs seria um detector sensível — ela é uma
    estatística de terceira ordem, e quase nenhum estudo de loteria passa da
    primeira (frequência) ou da segunda (pares).
    """
    n = 0
    for a in conj:
        for r in range(1, (UNIVERSO - a) // 2 + 1):
            if (a + r) in conj and (a + 2 * r) in conj:
                n += 1
    return n


def estatisticas_estruturais(h: Historico) -> Dict[str, np.ndarray]:
    """Todas as formas medidas de uma vez, concurso a concurso."""
    M, S = h.matriz, h.ordenados
    T = h.T
    pares = M[:, ::2].sum(axis=1) if False else np.array(
        [int(sum(1 for x in row if x % 2 == 0)) for row in S])
    primos = np.array([int(sum(1 for x in row if int(x) in PRIMOS)) for row in S])
    fib = np.array([int(sum(1 for x in row if int(x) in FIBONACCI)) for row in S])
    soma = S.astype(int).sum(axis=1)
    moldura = np.array([int(sum(1 for x in row if int(x) in MOLDURA)) for row in S])
    consec = np.array([_consecutivos(row.astype(int)) for row in S])
    maiorseq = np.array([_maior_sequencia(row.astype(int)) for row in S])
    aps = np.array([_n_aps(c) for c in h.conjuntos])
    # perfil do volante 5x5
    linhas = np.zeros((T, 5), dtype=int)
    colunas = np.zeros((T, 5), dtype=int)
    for i, row in enumerate(S):
        for x in row:
            linhas[i, linha(int(x))] += 1
            colunas[i, coluna(int(x))] += 1
    # repetições em relação ao concurso anterior (indefinido no primeiro)
    rep = np.full(T, -1, dtype=int)
    for i in range(1, T):
        rep[i] = int(np.dot(M[i], M[i - 1]))
    # espelho: quantas dezenas do sorteio têm o par 26-n também dentro
    espelho = np.array([int(sum(1 for x in c if (26 - x) in c)) for c in h.conjuntos])
    return {
        "pares": pares, "primos": primos, "fibonacci": fib, "soma": soma,
        "moldura": moldura, "consecutivos": consec, "maior_sequencia": maiorseq,
        "progressoes_aritmeticas": aps, "linhas": linhas, "colunas": colunas,
        "repeticoes": rep, "espelho": espelho,
        "amplitude": S[:, -1].astype(int) - S[:, 0].astype(int),
        "desvio_linhas": linhas.std(axis=1), "desvio_colunas": colunas.std(axis=1),
    }


# ═══════════════════════════════════════════ nulos exatos
def pmf_hipergeometrica(K: int) -> np.ndarray:
    """P(k dos K especiais entre as 15 sorteadas). Exata, sem simulação."""
    p = np.zeros(SORTEADAS + 1)
    tot = comb(UNIVERSO, SORTEADAS)
    for k in range(SORTEADAS + 1):
        if k > K or (SORTEADAS - k) > (UNIVERSO - K):
            continue
        p[k] = comb(K, k) * comb(UNIVERSO - K, SORTEADAS - k) / tot
    return p


NULOS_EXATOS: Dict[str, np.ndarray] = {
    "pares": pmf_hipergeometrica(12),        # 12 pares em 1..25
    "primos": pmf_hipergeometrica(9),        # 9 primos
    "fibonacci": pmf_hipergeometrica(7),
    "moldura": pmf_hipergeometrica(16),
    "repeticoes": PMF_INTER,
}


def qui_quadrado(obs_contagens: np.ndarray, pmf: np.ndarray, n: int,
                 minimo_esperado: float = 5.0) -> Tuple[float, int]:
    """Qui-quadrado agrupando as caudas raras — sem isso o teste mente.

    Categoria com esperado abaixo de 5 infla o χ² e produz "descoberta" onde
    só há amostra pequena. É o erro mais comum das análises de loteria que
    circulam por aí.
    """
    esp = pmf * n
    idx = np.where(esp >= minimo_esperado)[0]
    if len(idx) < 2:
        return 0.0, 0
    lo, hi = idx[0], idx[-1]
    o = np.concatenate([[obs_contagens[:lo].sum()], obs_contagens[lo:hi + 1],
                        [obs_contagens[hi + 1:].sum()]])
    e = np.concatenate([[esp[:lo].sum()], esp[lo:hi + 1], [esp[hi + 1:].sum()]])
    manter = e > 0
    o, e = o[manter], e[manter]
    chi = float(np.sum((o - e) ** 2 / e))
    return chi, len(o) - 1
