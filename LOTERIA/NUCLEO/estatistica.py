# -*- coding: utf-8 -*-
"""
ESTATÍSTICA — a régua que decide se uma medida achou algo ou achou ruído.

POR QUE ESTE ARQUIVO EXISTE SEPARADO
────────────────────────────────────
No outro software a régua ficou espalhada dentro dos medidores, e eu descobri
tarde que dois deles usavam critérios diferentes para dizer a mesma coisa. Aqui
a régua é uma só, mora num lugar, e é testada sozinha — contra valores que dão
para conferir na mão.

E ela é escrita à mão de propósito: este ambiente não instala pacote (nem scipy
nem statsmodels), e eu preferi assim mesmo. Um p-valor errado é PIOR que nenhum
p-valor: nenhum deixa a pessoa sem conclusão, e o errado a deixa com a conclusão
trocada e a impressão de que mediu.

O QUE ESTA RÉGUA MEDE, E O QUE NÃO
──────────────────────────────────
Ela responde "isto que eu vi cabe no acaso?". Ela NÃO responde "isto vai
acontecer de novo". A diferença é a que separa este software de um vendedor de
palpite: eu consigo dizer com números que uma coisa não se explica pelo acaso;
não consigo dizer que ela continua valendo no próximo concurso. Onde eu só tiver
a primeira resposta, é a primeira que eu escrevo na tela.
"""
from __future__ import annotations

import random
from math import comb, exp, lgamma, log, sqrt
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 1,96 desvios = 95%. Fica como padrão e aparece em todo resultado, porque
# "significativo" sem dizer a que nível não quer dizer nada.
Z95 = 1.959963984540054


# ══════════════════════════════════════════════ a taxa observada, com margem
def wilson(sucessos: int, n: int, z: float = Z95) -> Tuple[float, float]:
    """Intervalo de confiança da taxa `sucessos/n` pelo método de Wilson.

    POR QUE WILSON E NÃO O DA FÓRMULA DE ESCOLA
    ───────────────────────────────────────────
    O intervalo normal (`p ± z·√(p(1-p)/n)`) mente exatamente onde este software
    vive: taxas pequenas (0,10 na Mega-Sena é a chance de uma dezena sair) e n
    modesto. Ele chega a descer abaixo de zero — e um intervalo que inclui taxa
    negativa não está medindo nada. Wilson não faz isso e é igualmente simples.
    """
    if n <= 0:
        return (0.0, 1.0)
    p = sucessos / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centro = (p + z2 / (2 * n)) / denom
    margem = (z * sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, centro - margem), min(1.0, centro + margem))


def poder_basta(n: int, p0: float, efeito_relativo: float = 0.10,
                z: float = Z95) -> Dict[str, Any]:
    """Este `n` daria para NOTAR um efeito, se ele existisse?

    A PERGUNTA QUE FALTAVA NO OUTRO SOFTWARE
    ────────────────────────────────────────
    Lá eu escrevia "não se sustentou" com n pequeno, e isso é uma armadilha: com
    n pequeno o intervalo é largo, ele contém o acaso quase sempre, e o software
    "derruba" tudo o que olha. Não medir e não achar são a mesma tela, e não são
    a mesma coisa.

    Então antes de derrubar item nenhum eu pergunto: SE a taxa verdadeira fosse
    `p0 × (1 + efeito)`, uma observação exatamente nela já excluiria `p0` do
    intervalo? Se nem nesse caso favorável excluiria, o n não dá para concluir —
    e a resposta honesta é "sem base", não "derrubado".

    Isto é um teste de poder a 50%, e eu digo qual é para ninguém o ler como
    mais do que é: ele não garante que o efeito seria pego, garante que ele
    CABERIA na medida. É o piso, e o piso é o que impede a conclusão falsa.
    """
    if n <= 0 or not (0 < p0 < 1):
        return {"basta": False, "n": n, "n_mínimo_estimado": None,
                "nota": "n ou taxa de base inválidos"}
    p1 = min(1.0, p0 * (1.0 + efeito_relativo))
    lo, _hi = wilson(int(round(p1 * n)), n, z)
    basta = lo > p0
    # quantos concursos faltariam: cresce como 1/n, então a busca é rápida e
    # feita direto, sem fórmula aproximada que eu teria de justificar depois.
    n_min = None
    if not basta:
        m = max(n, 10)
        while m < 10_000_000:
            m = int(m * 1.35) + 1
            if wilson(int(round(p1 * m)), m, z)[0] > p0:
                n_min = m
                break
    return {"basta": basta, "n": n, "n_mínimo_estimado": n_min,
            "efeito_relativo": efeito_relativo,
            "nota": ("o n dá para notar um efeito deste tamanho"
                     if basta else
                     f"o n NÃO dá para notar nem um efeito de "
                     f"{efeito_relativo:+.0%}; seriam ~{n_min} observações. "
                     f"Não concluir nada é o resultado correto aqui.")}


# ═══════════════════════════════ o p-valor do qui-quadrado, sem aproximação
#
# Q(a,x), a gama incompleta superior regularizada. É o mesmo algoritmo do
# Numerical Recipes (série quando x < a+1, fração continuada quando x ≥ a+1),
# porque é o que converge nos dois lados. Escrevi à mão e o teste confere contra
# valores de tabela — implementação de estatística sem conferência é chute com
# casas decimais.
def _gama_serie(a: float, x: float, iteracoes: int = 500) -> float:
    """P(a,x) pela série. Vale para x < a+1."""
    if x <= 0:
        return 0.0
    ap, soma, termo = a, 1.0 / a, 1.0 / a
    for _ in range(iteracoes):
        ap += 1.0
        termo *= x / ap
        soma += termo
        if abs(termo) < abs(soma) * 1e-15:
            break
    return soma * exp(-x + a * log(x) - lgamma(a))


def _gama_fracao(a: float, x: float, iteracoes: int = 500) -> float:
    """Q(a,x) pela fração continuada (Lentz). Vale para x ≥ a+1."""
    minusculo = 1e-300
    b, c, d = x + 1.0 - a, 1e300, 1.0 / (x + 1.0 - a)
    h = d
    for i in range(1, iteracoes + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < minusculo:
            d = minusculo
        c = b + an / c
        if abs(c) < minusculo:
            c = minusculo
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h * exp(-x + a * log(x) - lgamma(a))


def gama_q(a: float, x: float) -> float:
    """Q(a,x) — a cauda superior. É daqui que sai o p-valor do qui-quadrado."""
    if x < 0 or a <= 0:
        return float("nan")
    if x == 0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gama_serie(a, x)
    return _gama_fracao(a, x)


def p_qui2(estatistica: float, graus: int) -> float:
    """Chance de ver um qui-quadrado ao menos tão grande, se o esperado é o certo."""
    if graus <= 0:
        return 1.0
    return max(0.0, min(1.0, gama_q(graus / 2.0, estatistica / 2.0)))


def qui2(observado: Sequence[float], esperado: Sequence[float],
         minimo_por_caixa: float = 5.0) -> Dict[str, Any]:
    """Compara o que se viu com o que a teoria manda, caixa por caixa.

    JUNTAR AS CAIXAS MAGRAS NÃO É DETALHE
    ─────────────────────────────────────
    O qui-quadrado só vale onde o esperado por caixa não é minúsculo. As somas da
    Mega-Sena vão de 21 a 345: as pontas têm esperado de fração de concurso, e
    deixá-las soltas infla a estatística e fabrica significância. Então caixas
    magras são juntadas com a vizinha — mantendo a ordem, porque soma é ordenada
    — e o resultado diz quantas caixas sobraram.

    Os graus de liberdade são `caixas − 1`: o esperado vem da combinatória, não
    foi ajustado nos dados. Se algum dia ele vier de parâmetro estimado aqui,
    tem de descontar, e este comentário é o lembrete.
    """
    ob = [float(x) for x in observado]
    es = [float(x) for x in esperado]
    if len(ob) != len(es) or not ob:
        return {"ok": False, "nota": "observado e esperado de tamanhos diferentes"}
    if sum(es) <= 0:
        return {"ok": False, "nota": "esperado soma zero"}

    caixas: List[Tuple[float, float]] = []
    ac_ob = ac_es = 0.0
    for o, e in zip(ob, es):
        ac_ob += o
        ac_es += e
        if ac_es >= minimo_por_caixa:
            caixas.append((ac_ob, ac_es))
            ac_ob = ac_es = 0.0
    if ac_es > 0:                      # a última ponta magra vai na vizinha
        if caixas:
            o0, e0 = caixas[-1]
            caixas[-1] = (o0 + ac_ob, e0 + ac_es)
        else:
            caixas.append((ac_ob, ac_es))
    if len(caixas) < 2:
        return {"ok": False, "caixas": len(caixas),
                "nota": "sobrou menos de 2 caixas com esperado suficiente — "
                        "não há o que comparar; é falta de dados, não resultado"}

    estat = sum((o - e) ** 2 / e for o, e in caixas if e > 0)
    graus = len(caixas) - 1
    return {"ok": True, "estatistica": estat, "graus": graus,
            "p": p_qui2(estat, graus), "caixas": len(caixas),
            "caixas_originais": len(ob)}


# ═════════════════════════════════ as distribuições exatas de referência
#
# Isto é o que impede a armadilha que a própria base de conhecimento aponta em
# C03: existem MUITO mais combinações com soma média, então elas saem mais em
# número absoluto sem que nenhuma seja mais provável. Comparar a soma observada
# com "o meio da faixa" acusaria padrão em qualquer sorteio honesto. O
# comparativo certo é a distribuição combinatória — e ela é exata, não amostrada.
def distribuicao_soma(universo: int, sorteadas: int,
                      primeiro: int = 1) -> Dict[int, int]:
    """Quantas combinações de `sorteadas` dezenas somam cada valor. Exato.

    Por programação dinâmica, não por enumeração: C(60,6) são 50 milhões de
    combinações e a tabela resolve isso em alguns milhares de passos. O total
    devolvido bate com C(universo, sorteadas) — o teste confere, e é o que prova
    que a tabela não perdeu nem duplicou caminho.
    """
    dezenas = list(range(primeiro, primeiro + universo))
    # tabela[j] = {soma: quantas} com j dezenas usadas
    tabela: List[Dict[int, int]] = [{0: 1}] + [{} for _ in range(sorteadas)]
    for d in dezenas:
        for j in range(sorteadas - 1, -1, -1):
            if not tabela[j]:
                continue
            destino = tabela[j + 1]
            for s, q in tabela[j].items():
                destino[s + d] = destino.get(s + d, 0) + q
    return dict(sorted(tabela[sorteadas].items()))


def distribuicao_impares(universo: int, sorteadas: int,
                         primeiro: int = 1) -> Dict[int, int]:
    """Quantas combinações têm cada quantidade de dezenas ímpares. Exato.

    É hipergeométrica pura: escolher `i` das ímpares e o resto das pares.
    """
    dezenas = range(primeiro, primeiro + universo)
    impares = sum(1 for d in dezenas if d % 2 == 1)
    pares = universo - impares
    saida: Dict[int, int] = {}
    for i in range(0, sorteadas + 1):
        if i <= impares and (sorteadas - i) <= pares:
            saida[i] = comb(impares, i) * comb(pares, sorteadas - i)
    return saida


# ════════════════════════════════════════════════ comparar dois grupos
def teste_permutacao(grupo_a: Sequence[float], grupo_b: Sequence[float],
                     repeticoes: int = 20_000,
                     semente: int = 20260817) -> Dict[str, Any]:
    """As médias dos dois grupos diferem mais do que o embaralhamento explica?

    POR QUE PERMUTAÇÃO E NÃO UM TESTE t
    ───────────────────────────────────
    O uso disto é a partilha do prêmio (P01), e "número de ganhadores" tem cauda
    longa e feia: a maioria dos concursos com poucos, alguns com milhares. O
    teste t supõe uma forma que esses dados não têm. A permutação não supõe nada
    sobre a forma — ela pergunta direto: se o rótulo dos grupos não importasse,
    com que frequência o embaralhamento produziria uma diferença desta?

    A semente é fixa para o resultado ser reproduzível. Sem isso, rodar duas
    vezes daria p-valores diferentes e não haveria como ele conferir o meu.
    """
    a = [float(x) for x in grupo_a]
    b = [float(x) for x in grupo_b]
    if len(a) < 2 or len(b) < 2:
        return {"ok": False, "n_a": len(a), "n_b": len(b),
                "nota": "cada grupo precisa de ao menos 2 observações"}
    dif = sum(a) / len(a) - sum(b) / len(b)
    junto = a + b
    corte = len(a)
    rnd = random.Random(semente)
    extremos = 0
    for _ in range(repeticoes):
        rnd.shuffle(junto)
        d = (sum(junto[:corte]) / corte
             - sum(junto[corte:]) / (len(junto) - corte))
        if abs(d) >= abs(dif) - 1e-12:
            extremos += 1
    # +1 no numerador e no denominador: o p-valor nunca é 0. Com 20 mil sorteios
    # o mínimo honesto é ~1/20001, e escrever 0 afirmaria certeza que não existe.
    p = (extremos + 1) / (repeticoes + 1)
    return {"ok": True, "media_a": sum(a) / len(a), "media_b": sum(b) / len(b),
            "diferenca": dif, "p": p, "repeticoes": repeticoes,
            "n_a": len(a), "n_b": len(b)}
