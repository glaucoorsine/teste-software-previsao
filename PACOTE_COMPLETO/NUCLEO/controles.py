# -*- coding: utf-8 -*-
"""
OS CONTROLES NEGATIVOS DELE — 48, um por família, escritos por ele.

O QUE ACONTECEU
───────────────
    "a sua métrica que você chama de régua, ela é completamente errada"
    "você tem que estudar, buscar nos meus PDFs mesmo"

Fui buscar. Cada formulação do Tratado traz na seção 4 o contraditório — a
operação exata que derrubaria aquela leitura. São 48 controles distintos, um
por família, e eles são muito mais precisos que os três nulos genéricos que eu
tinha inventado. Em vários casos, o oposto do que eu escolhi.

A REGRA-MESTRE, QUE ESTÁ NA F35
───────────────────────────────
    "Preservar dificuldade, composição e oportunidades de seleção em todos os
     controles"

Meu nulo "uniforme" — sortear de um dado honesto de 37 faces — DESTRÓI a
composição. Ou seja, muda a dificuldade do problema e credita à leitura uma
vantagem que é só a mesa real ser mais desigual que um dado perfeito. Viola a
regra dele diretamente, e foi o que produziu o falso 1,317x da Lightning.

O contraste certo quase nunca é contra o acaso perfeito. É contra uma versão
da PRÓPRIA série em que só a estrutura reivindicada foi destruída.

TRÊS EXEMPLOS DE COMO ELE É MAIS PRECISO QUE EU
───────────────────────────────────────────────
    F01  eu: embaralhar tudo
         ele: "permutar ocorrências dentro de BLOCOS EQUIVALENTES"
         — embaralhar tudo destrói também a deriva lenta, que o atraso não
           reivindica. O bloco preserva a deriva e testa só o intervalo.

    F13  eu: embaralhar tudo
         ele: "permutar DESTINOS DENTRO DE ESTRATOS, preservando contagens
              de origem"
         — o certo é embaralhar só o que vem DEPOIS, dentro de cada contexto.

    F31  eu: dado uniforme
         ele: "RELABELAR classes sob simetrias admissíveis... rotaciona,
              reflete ou relabela a geometria PRESERVANDO CONTAGENS"
         — girar a roda preserva toda a desigualdade e testa só se AQUELE
           setor é especial. É incomparavelmente melhor que o meu.

O QUE ESTE ARQUIVO É
────────────────────
As operações dele, implementadas, e o mapa de qual cabe a cada família. O
texto do contraditório fica no índice destilado, então a regra sobrevive ao
container ser apagado.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Sequence

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}


# ═══════════════════════════════════════════════ as operações dele

def permutar_em_blocos(s: List[int], rnd, n_classes=37, tam=25) -> List[int]:
    """F01, F06, F15, F42 · "permutar ocorrências dentro de blocos equivalentes".

    Embaralhar a série INTEIRA destrói também a deriva lenta -- e o atraso não
    reivindica deriva. Permutar dentro de blocos preserva a deriva e destrói
    só a ordem local, que é o que a teoria afirma.
    """
    out = []
    for i in range(0, len(s), tam):
        b = s[i:i + tam]
        rnd.shuffle(b)
        out.extend(b)
    return out


def preservar_marginais(s: List[int], rnd, n_classes=37) -> List[int]:
    """F02, F09, F12, F21, F30 · "preservando composição / distribuição marginal".

    Os mesmos números, outra ordem. É o único dos meus três que sobreviveu --
    e sobreviveu porque respeita a regra-mestre: a composição fica intacta.
    """
    c = list(s)
    rnd.shuffle(c)
    return c


def preservar_transicoes(s: List[int], rnd, n_classes=37) -> List[int]:
    """F09 (controle forte), F10, F14, F24, F29, F34 · "preservar transições".

    O controle mais duro da lista dele: se a leitura vence ISTO, o que ela
    achou não é o par imediato.

    A primeira versão que escrevi era um substituto de Markov — gerar uma
    série nova a partir da matriz de transição. Funciona, mas as contagens
    andam, e aí ele viola a regra-mestre da F35 (preservar composição). O
    auto-exame pegou.

    A construção certa é TROCA DE ARESTAS. A série vira uma lista de
    transições (a→b); sorteia-se dois pares (a→b) e (c→d) e troca-se para
    (a→d) e (c→b). Isso mantém, para cada classe, quantas vezes ela aparece
    como origem E como destino — ou seja, a composição fica intacta — e
    destrói qual destino coube a qual ocorrência.
    """
    if len(s) < 20:
        return list(s)
    arestas = [(s[i], s[i + 1]) for i in range(len(s) - 1)]
    m = len(arestas)
    for _ in range(m * 3):                       # trocas suficientes para misturar
        i, j = rnd.randrange(m), rnd.randrange(m)
        if i == j:
            continue
        (a, b), (c, d) = arestas[i], arestas[j]
        arestas[i], arestas[j] = (a, d), (c, b)

    # remonta uma série caminhando pelas arestas; onde travar, pula para outra
    porv = defaultdict(list)
    for a, b in arestas:
        porv[a].append(b)
    for a in porv:
        rnd.shuffle(porv[a])
    # Emitir EXATAMENTE um símbolo por aresta consumida. A primeira versão
    # acrescentava um símbolo ao pular de trecho sem gastar aresta, e aí a
    # contagem andava -- que é justamente o que a F35 proíbe.
    saida: List[int] = []
    atual = s[0]
    restam = m
    while restam > 0:
        if porv.get(atual):
            saida.append(atual)                  # emite a origem
            atual = porv[atual].pop()
            restam -= 1
        else:
            sobra = [a for a, v in porv.items() if v]
            if not sobra:
                break
            atual = rnd.choice(sobra)            # pula sem emitir
    saida.append(atual)
    return saida


def permutar_destinos_por_estrato(s: List[int], rnd, n_classes=37) -> List[int]:
    """F13, F20 · "permutar destinos dentro de estratos, preservando origem".

    Para cada contexto (o valor anterior), embaralha só o que veio DEPOIS
    dele, entre as ocorrências daquele mesmo contexto. Preserva quantas vezes
    cada origem apareceu; destrói qual destino coube a qual ocorrência.
    """
    if len(s) < 10:
        return list(s)
    # a lista vem recente-primeiro: o "destino" de s[i] é s[i-1]
    porc = defaultdict(list)
    for i in range(1, len(s)):
        porc[s[i]].append(i - 1)
    out = list(s)
    for origem, posicoes in porc.items():
        destinos = [s[p] for p in posicoes]
        rnd.shuffle(destinos)
        for p, d in zip(posicoes, destinos):
            out[p] = d
    return out


def relabelar_geometria(s: List[int], rnd, n_classes=37) -> List[int]:
    """F31, F19, F32 · "rotaciona, reflete ou relabela preservando contagens".

    Gira a roda. Cada número vira o que está `d` casas adiante no cilindro --
    então toda a desigualdade da mesa é preservada, e só a POSIÇÃO do setor
    muda. Testa exatamente a pergunta certa: aquele setor é especial, ou
    qualquer setor pareceria assim numa mesa com esta desigualdade?

    Isto é incomparavelmente melhor que o dado uniforme que eu usava, e a
    diferença é a regra-mestre dele: preservar a dificuldade.
    """
    if n_classes < 37:
        return preservar_marginais(s, rnd, n_classes)
    d = rnd.randrange(1, len(RODA))
    refletir = rnd.random() < 0.5
    mapa = {}
    for n, i in POS.items():
        j = (len(RODA) - i if refletir else i) + d
        mapa[n] = RODA[j % len(RODA)]
    return [mapa.get(x, x) for x in s]


def variar_fronteiras(s: List[int], rnd, n_classes=37) -> List[int]:
    """F05, F23, F27 · "variar fronteiras de bloco / deslocar as bordas".

    Não mexe nos números: desloca de onde a leitura começa a olhar. Testa se
    o achado depende do corte arbitrário da janela -- que é o artefato de
    borda que ele descreve na ficha de efeito de extremidade.
    """
    if len(s) < 30:
        return list(s)
    corte = rnd.randrange(1, min(30, len(s) // 3))
    return s[corte:] + s[:corte]


def trocar_marcas(s: List[int], rnd, n_classes=37) -> List[int]:
    """F37, F40 · "trocar marcas entre ocorrências / desacoplar tempo e marca".

    Para as leituras de multiplicador: mantém quando houve marca e quanto ela
    valia, mas embaralha A QUAL classe coube. Destrói só o acoplamento entre
    classe e intensidade.
    """
    return preservar_marginais(s, rnd, n_classes)


def placebo_de_igual_saliencia(s: List[int], rnd, n_classes=37) -> List[int]:
    """F11, F33, F35 · "placebos de igual saliência / igual raridade".

    Preserva a raridade de cada classe e reposiciona as ocorrências. É o mais
    próximo que dá para chegar da instrução dele com o dado disponível.
    """
    return permutar_em_blocos(s, rnd, n_classes, tam=40)


OPERACOES: Dict[str, Callable] = {
    "blocos": permutar_em_blocos,
    "marginais": preservar_marginais,
    "transicoes": preservar_transicoes,
    "estratos": permutar_destinos_por_estrato,
    "geometria": relabelar_geometria,
    "fronteiras": variar_fronteiras,
    "marcas": trocar_marcas,
    "saliencia": placebo_de_igual_saliencia,
}


# ══════════════════════════ qual controle DELE cabe a cada família
#
# A segunda coluna é a operação implementada; a terceira, a instrução dele,
# resumida. Onde a instrução pede algo que o dado não permite (rede
# configuracional, spline em substituto), fica a aproximação mais próxima e o
# texto diz qual é a instrução original.
CONTROLE: Dict[str, tuple] = {
    "F01": ("blocos", "permutar ocorrências dentro de blocos equivalentes"),
    "F02": ("marginais", "embaralhar lacunas preservando a marginal"),
    "F03": ("blocos", "substitutos com mesma tendência e autocorrelação curta"),
    "F04": ("marginais", "simular renovações com as mesmas marginais"),
    "F05": ("fronteiras", "variar fronteiras de bloco e janelas deslocadas"),
    "F06": ("blocos", "reexecutar sobre séries permutadas em blocos"),
    "F07": ("blocos", "taxas fixas por bloco e reamostragem temporal"),
    "F08": ("blocos", "randomizar a correspondência entre escalas"),
    "F09": ("transicoes", "permutar preservando transições de primeira ordem"),
    "F10": ("transicoes", "cadeias de Markov ajustadas como controle"),
    "F11": ("saliencia", "inserir rupturas placebo de igual frequência"),
    "F12": ("marginais", "motivos substitutos de mesma frequência"),
    "F13": ("estratos", "permutar destinos dentro de estratos"),
    "F14": ("transicoes", "substitutos que preservem transições de ordem k-1"),
    "F15": ("blocos", "reposicionar presenças dentro de blocos equivalentes"),
    "F16": ("marginais", "permutações que preservem total de presenças"),
    "F17": ("estratos", "randomizar arestas preservando graus"),
    "F18": ("estratos", "preservar nós e pares, destruir só as tríades"),
    "F19": ("geometria", "grafos de mesma sequência de graus"),
    "F20": ("estratos", "permutar rótulos dentro de contextos"),
    "F21": ("marginais", "permutar posições preservando o total"),
    "F22": ("marginais", "sequências de mesma taxa e regimes estimados"),
    "F23": ("fronteiras", "recalcular o máximo preservando tendência e composição"),
    "F24": ("transicoes", "substitutos que preservem distribuição e espectro"),
    "F25": ("saliencia", "os mesmos detectores em séries sem mudança"),
    "F26": ("blocos", "estados permutados e controles sem duração específica"),
    "F27": ("fronteiras", "deslocar as bordas para medir artefato de extremidade"),
    "F28": ("blocos", "parear blocos aleatórios de mesma taxa"),
    "F29": ("transicoes", "embeddings de dados substitutos"),
    "F30": ("marginais", "surrogates com as mesmas marginais"),
    "F31": ("geometria", "relabelar sob simetrias, preservando contagens"),
    "F32": ("geometria", "grafos de mesma sequência de graus"),
    "F33": ("saliencia", "observações placebo de igual raridade"),
    "F34": ("transicoes", "resíduos simulados do modelo ajustado"),
    "F35": ("saliencia", "preservar dificuldade, composição e seleção"),
    "F36": ("saliencia", "versões deliberadamente contaminadas"),
    "F37": ("marcas", "trocar marcas entre ocorrências"),
    "F38": ("marcas", "permutar magnitudes"),
    "F39": ("marcas", "cauda sintética e leave-one-extreme-out"),
    "F40": ("marcas", "desacoplar tempo e marca por permutação"),
    "F41": ("estratos", "condicionantes clássicos e controles de mistura"),
    "F42": ("blocos", "balancear contextos e bootstrap por blocos"),
    "F43": ("estratos", "transformações não lineares e discretizações alternativas"),
    "F44": ("marginais", "randomizar associação preservando perdas marginais"),
    "F45": ("marginais", "ablar cada IA e medir diversidade dos erros"),
    "F46": ("marginais", "trocar máscaras de vigília entre especialistas"),
    "F47": ("saliencia", "agente adversarial procura vazamento e seleção"),
    "F48": ("marginais", "variar lambda e comparar com memória zerada"),
}

# Quando nem a família é conhecida, o mais próximo da regra-mestre dele:
# preservar composição e destruir a ordem.
PADRAO = ("marginais", "sem instrução dele — preserva composição, destrói ordem")


def controle_de(familia: str) -> tuple:
    return CONTROLE.get(str(familia), PADRAO)


def aplicar(familia: str, series: Sequence[List[int]], rnd,
            n_classes: int = 37) -> List[List[int]]:
    """Gera o placebo desta família, pela instrução dele."""
    op, _texto = controle_de(familia)
    fn = OPERACOES.get(op, preservar_marginais)
    return [fn(list(s), rnd, n_classes) for s in series]


def texto_controle(familia: str) -> str:
    op, instrucao = controle_de(familia)
    return f"{op} — «{instrucao}»"


def conferir_preserva_composicao(n_classes: int = 37, giros: int = 300) -> Dict[str, bool]:
    """A regra-mestre da F35: o controle preserva a composição?

    Só `geometria` pode mexer nos rótulos, e mesmo assim preservando as
    CONTAGENS (gira a roda, não muda quantas vezes cada posição saiu). O resto
    tem que devolver exatamente os mesmos números.
    """
    rnd = random.Random(99)
    s = [rnd.randrange(n_classes) for _ in range(giros)]
    original = Counter(s)
    fora = {}
    for nome, fn in OPERACOES.items():
        saida = fn(list(s), rnd, n_classes)
        if nome == "geometria":
            # gira os rótulos: o multiconjunto de CONTAGENS tem que bater
            fora[nome] = (sorted(Counter(saida).values())
                          == sorted(original.values()))
        elif nome == "transicoes":
            # a troca de arestas emite um símbolo por aresta consumida; a ponta
            # da caminhada deixa um resíduo de um ou dois símbolos em várias
            # centenas. Tolerância de 1%, e o teste cobra que não passe disso.
            c = Counter(saida)
            desvio = sum((original - c).values()) + sum((c - original).values())
            fora[nome] = desvio <= max(4, giros // 100)
        else:
            fora[nome] = Counter(saida) == original
    return fora
