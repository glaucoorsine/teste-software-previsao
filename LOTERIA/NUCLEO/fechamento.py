# -*- coding: utf-8 -*-
"""
FECHAMENTO — garantir prêmio por construção, não por sorte.

O QUE ELE DISSE
───────────────
    "todos os jogos, na verdade escolhe ali e tal, jogar com números fixos"

Jogar com um conjunto fixo de dezenas é exatamente o terreno do fechamento, e é
onde este software pode fazer algo REAL — verificável antes do sorteio, sem
depender de prever nada.

A PERGUNTA QUE ISTO RESPONDE
────────────────────────────
    "Escolhi 12 dezenas. Se 5 delas saírem, quantas apostas eu preciso fazer
     para GARANTIR pelo menos uma quadra?"

Repare no que a pergunta não é. Não é "quais dezenas vão sair" — isso ninguém
sabe e eu não vou fingir que sei. É: dado que eu já escolhi as dezenas, como
distribuo o dinheiro entre as apostas para converter acerto parcial em prêmio
com CERTEZA.

E "certeza" aqui é literal. Não é 95%, não é "quase sempre": ou toda combinação
possível de 5 entre as 12 é coberta por alguma aposta com 4 acertos, ou a
garantia não existe. Um único caso descoberto derruba a garantia inteira — e é
por isso que `conferir()` testa TODOS, não uma amostra.

POR QUE ISTO É HONESTO E PREVISÃO NÃO SERIA
───────────────────────────────────────────
O fechamento não aumenta a chance de as suas dezenas saírem. Ele reorganiza as
apostas para que, quando saírem, o prêmio venha. É ganho de EFICIÊNCIA sobre o
dinheiro apostado, e é demonstrável: dá para verificar a garantia antes de gastar
um real, sem sorteio nenhum.

Comparar com o alternativo mostra o tamanho da coisa. Com 12 dezenas na
Mega-Sena, apostar todas as combinações são 924 jogos. Um fechamento com garantia
de quadra para 5 acertos custa uma fração disso — e a garantia é a mesma. A
diferença é dinheiro, e é grande.

O QUE EU NÃO VOU FINGIR
───────────────────────
Achar o MENOR fechamento possível é um problema em aberto da matemática
(covering designs); para vários tamanhos ninguém conhece o mínimo. O que este
arquivo faz é construir um fechamento válido por um método guloso e PROVAR a
garantia dele. "Válido e provado" é diferente de "o menor que existe", e o
software diz qual dos dois está entregando.
"""
from __future__ import annotations

import random
import time
from itertools import combinations
from math import comb
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# quantos casos a verificação exaustiva aceita antes de recusar.
#
# C(20,6) = 38.760 e C(25,7) = 480.700 -- tudo isso é rápido. Acima de alguns
# milhões a verificação levaria minutos e travaria a tela, e uma garantia que
# ninguém espera conferir não serve para nada. Então há teto, e ele é dito.
MAX_CASOS = 3_000_000

# quantas partidas do guloso disputam entre si, e o teto de tempo delas.
#
# ISTO NASCEU DE UM DEFEITO QUE SÓ APARECEU NA TELA
# ─────────────────────────────────────────────────
# A primeira versão montava UMA partida, e as candidatas dela saíam de
# `list(casos)[:60]` — a ordem de iteração de um `set`. Essa ordem depende dos
# VALORES das dezenas, não da estrutura do problema. O resultado: as mesmas 12
# dezenas fechavam em 15 apostas quando eram 1 a 12, e em 20 ou 21 quando eram
# espalhadas. O problema é o mesmo, renomeado — e ele pagaria 5 apostas a mais
# por causa da ordem interna de uma estrutura de dados.
#
# Agora as candidatas saem em ordem definida, e várias partidas com
# embaralhamentos semeados disputam a menor. Os três conjuntos equivalentes
# passaram a fechar nas mesmas 15, e o de 14 dezenas caiu de 43 para 39.
# As sementes são fixas: rodar duas vezes dá o mesmo conjunto de apostas.
PARTIDAS = 12
SEGUNDOS_ALVO = 20.0


def _milhar(n: int) -> str:
    """1234567 -> "1.234.567". Só o número, nunca a frase inteira."""
    return f"{n:,}".replace(",", ".")


def custo_de_cobrir_tudo(d: int, k: int) -> int:
    """Quantas apostas de `k` cobrem TODAS as combinações de `d` dezenas."""
    return comb(d, k)


def montar(dezenas: Sequence[int], k: int, acertos_previstos: int,
           garantir: int, limite_apostas: int = 5000,
           partidas: int = PARTIDAS,
           segundos: float = SEGUNDOS_ALVO) -> Dict[str, Any]:
    """Monta apostas de `k` dezenas que garantem `garantir` acertos.

    A garantia: SE `acertos_previstos` das `dezenas` forem sorteadas, ALGUMA das
    apostas devolvidas terá pelo menos `garantir` acertos.

    COMO, E POR QUE ASSIM
    ─────────────────────
    É o problema clássico de cobertura. Cada subconjunto de `acertos_previstos`
    dezenas é um "caso" que precisa estar coberto; cada aposta de `k` dezenas
    cobre todos os casos dos quais ela contém pelo menos `garantir` elementos.

    O método é guloso: a cada passo, escolhe a aposta que cobre mais casos ainda
    descobertos. Guloso não dá o mínimo -- este é um problema em aberto -- mas dá
    um conjunto válido, e a validade é o que se pode PROVAR.

    Várias partidas disputam a menor (ver PARTIDAS acima). Isso é honesto porque
    a garantia é conferida à parte, exaustivamente: escolher a menor entre
    conjuntos todos válidos não afrouxa nada, só gasta menos dinheiro dele.
    """
    dez = sorted(set(int(x) for x in dezenas))
    d = len(dez)
    erro = _conferir_pedido(d, k, acertos_previstos, garantir)
    if erro:
        return {"ok": False, "nota": erro}

    total_casos = comb(d, acertos_previstos)
    if total_casos > MAX_CASOS:
        return {"ok": False,
                "nota": f"seriam {_milhar(total_casos)} casos a cobrir — acima "
                        f"do teto de {_milhar(MAX_CASOS)}. Uma garantia que não "
                        f"dá para conferir não é garantia."}

    inicio = time.monotonic()
    melhor: Optional[List[Tuple[int, ...]]] = None
    incompleta: Optional[Tuple[List[Tuple[int, ...]], int]] = None
    tamanhos: List[int] = []
    jogadas = 0
    for i in range(partidas + 1):
        # a partida 0 é a determinística; as outras embaralham com semente fixa
        semente = None if i == 0 else 20260817 + i
        apostas, sobraram = _uma_partida(dez, k, acertos_previstos, garantir,
                                         limite_apostas, semente)
        jogadas += 1
        if sobraram == 0:
            tamanhos.append(len(apostas))
            if melhor is None or len(apostas) < len(melhor):
                melhor = apostas
        elif incompleta is None or sobraram < incompleta[1]:
            incompleta = (apostas, sobraram)
        if time.monotonic() - inicio > segundos:
            break

    if melhor is None:
        faltam = incompleta[1] if incompleta else total_casos
        return {"ok": False, "apostas": [list(a) for a in (incompleta[0] if incompleta else [])],
                "n_apostas": len(incompleta[0]) if incompleta else 0,
                "dezenas": dez, "k": k,
                "acertos_previstos": acertos_previstos, "garantir": garantir,
                "casos_totais": total_casos, "casos_descobertos": faltam,
                "custo_de_cobrir_tudo": custo_de_cobrir_tudo(d, k),
                "economia": None, "otimo": False,
                "nota": f"NÃO fechou: {faltam} caso(s) sem cobertura em "
                        f"{jogadas} partida(s). Isto não é garantia nenhuma; "
                        f"ou aumente o limite de apostas, ou peça menos."}

    return {
        "ok": True,
        "apostas": [list(a) for a in melhor],
        "n_apostas": len(melhor),
        "dezenas": dez, "k": k,
        "acertos_previstos": acertos_previstos, "garantir": garantir,
        "casos_totais": total_casos,
        "casos_descobertos": 0,
        "custo_de_cobrir_tudo": custo_de_cobrir_tudo(d, k),
        "economia": custo_de_cobrir_tudo(d, k) - len(melhor),
        "partidas": jogadas,
        "pior_partida": max(tamanhos) if tamanhos else None,
        "segundos": round(time.monotonic() - inicio, 2),
        "nota": "garantia completa — falta conferir com conferir()",
        # ver o cabeçalho: válido e provado ≠ o menor possível. Nem a menor de
        # doze partidas é o mínimo; é só a menor que eu achei.
        "otimo": False,
    }


def _uma_partida(dez: Sequence[int], k: int, acertos_previstos: int,
                 garantir: int, limite_apostas: int,
                 semente: Optional[int]) -> Tuple[List[Tuple[int, ...]], int]:
    """Uma corrida do guloso. Devolve (apostas, quantos casos ficaram de fora)."""
    casos: Set[Tuple[int, ...]] = set(combinations(dez, acertos_previstos))
    rnd = random.Random(semente) if semente is not None else None
    apostas: List[Tuple[int, ...]] = []
    while casos and len(apostas) < limite_apostas:
        melhor, cobertos_pela_melhor = None, -1
        for cand in _candidatas(casos, dez, k, garantir, rnd=rnd):
            n = _quantos_cobre(cand, casos, garantir)
            if n > cobertos_pela_melhor:
                melhor, cobertos_pela_melhor = cand, n
        if not melhor or cobertos_pela_melhor <= 0:
            break
        apostas.append(melhor)
        casos -= {c for c in casos if len(set(c) & set(melhor)) >= garantir}
    return apostas, len(casos)


def _conferir_pedido(d: int, k: int, acertos: int, garantir: int) -> str:
    """O pedido faz sentido? Recusar cedo evita garantia impossível."""
    if d < k:
        return f"pedir aposta de {k} dezenas entre {d} escolhidas não fecha"
    if garantir > k:
        return f"impossível garantir {garantir} acertos numa aposta de {k}"
    if garantir > acertos:
        return (f"impossível garantir {garantir} acertos se só "
                f"{acertos} das suas dezenas saírem — a garantia não pode "
                f"prometer mais acerto do que existe")
    if acertos > d:
        return f"não dá para {acertos} saírem de apenas {d} dezenas"
    if acertos < 1 or garantir < 1 or k < 1:
        return "os números têm de ser positivos"
    return ""


def _candidatas(casos: Set[Tuple[int, ...]], dez: Sequence[int],
                k: int, garantir: int, quantas: int = 60,
                rnd: Optional[random.Random] = None) -> List[Tuple[int, ...]]:
    """Apostas plausíveis para o próximo passo do guloso.

    Varrer todas as C(d,k) apostas seria correto e lento: com 18 dezenas e
    aposta de 6 são 18.564 candidatas em cada passo, vezes dezenas de passos.
    Estas candidatas nascem dos casos ainda DESCOBERTOS -- que é onde a aposta
    útil tem de estar -- completados com as dezenas mais frequentes entre eles.

    A ORDEM AQUI NÃO PODE VIR DO `set`
    ──────────────────────────────────
    Ela vinha, e era um defeito de verdade: a ordem de iteração de um conjunto
    depende dos valores guardados nele, então o mesmo problema com dezenas
    renomeadas dava fechamento maior ou menor por acaso. Ou os casos saem
    ordenados, ou saem sorteados com semente -- as duas dependem da estrutura do
    problema, e nenhuma depende de qual número ele escolheu.
    """
    faltando = sorted(casos)
    if rnd is not None and len(faltando) > quantas:
        faltando = rnd.sample(faltando, quantas)
    else:
        faltando = faltando[:quantas]
    peso: Dict[int, int] = {}
    for c in casos:
        for x in c:
            peso[x] = peso.get(x, 0) + 1
    ordem = sorted(dez, key=lambda x: (-peso.get(x, 0), x))
    saida: List[Tuple[int, ...]] = []
    vistas: Set[Tuple[int, ...]] = set()
    for caso in faltando:
        base = list(caso)[:k]
        for x in ordem:
            if len(base) >= k:
                break
            if x not in base:
                base.append(x)
        t = tuple(sorted(base))
        if len(t) == k and t not in vistas:
            vistas.add(t)
            saida.append(t)
    return saida or [tuple(sorted(ordem[:k]))]


def _quantos_cobre(aposta: Sequence[int], casos: Set[Tuple[int, ...]],
                   garantir: int) -> int:
    a = set(aposta)
    return sum(1 for c in casos if len(a & set(c)) >= garantir)


# ══════════════════════════════════════════════════ a prova, exaustiva
def conferir(apostas: Sequence[Sequence[int]], dezenas: Sequence[int],
             acertos_previstos: int, garantir: int) -> Dict[str, Any]:
    """A garantia É verdadeira? Testa TODOS os casos, não uma amostra.

    POR QUE EXAUSTIVO E NÃO POR AMOSTRAGEM
    ──────────────────────────────────────
    Uma garantia vale por ser universal. Testar mil casos ao acaso e não achar
    falha diria "provavelmente cobre" -- e "provavelmente" é justamente o que o
    fechamento existe para eliminar. Um único subconjunto descoberto derruba a
    promessa inteira, então ou se testa tudo, ou não se promete.

    Quando não dá para testar tudo dentro do teto, isto RECUSA em vez de dizer
    que está tudo bem. Garantia não conferida entregue como conferida seria a
    pior coisa que este software poderia fazer: ele gastaria dinheiro dele
    confiando numa promessa que ninguém verificou.
    """
    dez = sorted(set(int(x) for x in dezenas))
    total = comb(len(dez), acertos_previstos)
    if total > MAX_CASOS:
        return {"provado": False,
                "nota": f"{_milhar(total)} casos — acima do teto; não afirmo "
                        f"garantia que não conferi"}
    conjuntos = [set(a) for a in apostas]
    falhas: List[Tuple[int, ...]] = []
    for caso in combinations(dez, acertos_previstos):
        alvo = set(caso)
        if not any(len(alvo & a) >= garantir for a in conjuntos):
            falhas.append(caso)
            if len(falhas) >= 5:
                break
    return {
        "provado": not falhas,
        "casos_testados": total,
        "falhas": [list(f) for f in falhas],
        # o `replace` do separador de milhar tem de ficar SÓ no número: aplicado
        # na frase inteira ele comia a vírgula da oração e saía "252 casos de 5
        # acertos. alguma aposta faz 4"
        "nota": (f"PROVADO: em todos os {_milhar(total)} casos de "
                 f"{acertos_previstos} acertos, alguma aposta faz {garantir}"
                 if not falhas else
                 f"NÃO PROVADO: {len(falhas)}+ caso(s) sem cobertura, "
                 f"o primeiro é {list(falhas[0])}"),
    }


def resumo(r: Dict[str, Any], prova: Optional[Dict[str, Any]] = None) -> List[str]:
    """O fechamento em português, com o que ele economiza e o que garante."""
    if not r.get("ok"):
        return [f"[Fechamento] não fechou — {r.get('nota')}"]
    L = [f"[Fechamento] {len(r['dezenas'])} dezenas em {r['n_apostas']} apostas "
         f"de {r['k']}:",
         f"[Fechamento]   garantia: se {r['acertos_previstos']} das suas "
         f"dezenas saírem, alguma aposta faz {r['garantir']}",
         f"[Fechamento]   cobrir tudo custaria {r['custo_de_cobrir_tudo']} "
         f"apostas; estas são {r['n_apostas']} — economia de "
         f"{r.get('economia')} apostas com a MESMA garantia"]
    if r.get("partidas"):
        L.append(f"[Fechamento]   menor de {r['partidas']} partidas do guloso "
                 f"(a pior deu {r.get('pior_partida')}), em "
                 f"{r.get('segundos')}s — e nenhuma delas é o mínimo provado "
                 f"da matemática, que ninguém conhece para todo tamanho")
    if prova is not None:
        L.append(f"[Fechamento]   {prova.get('nota')}")
        if not prova.get("provado"):
            L.append("[Fechamento]   ATENÇÃO: sem prova, não use isto como "
                     "garantia — é só um conjunto de apostas")
    else:
        L.append("[Fechamento]   (ainda não conferido — chame conferir() antes "
                 "de confiar na garantia)")
    L.append("[Fechamento]   isto NÃO aumenta a chance das suas dezenas saírem; "
             "converte acerto parcial em prêmio com certeza")
    return L
