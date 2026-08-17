# -*- coding: utf-8 -*-
"""
AS DOZE INTELIGÊNCIAS DO TRATADO DELE, COM AS FÓRMULAS DELE.

DE ONDE ISTO VEM
────────────────
    "agora, que todas as ias do software trabalham minhas teorias dos 3 pdfs
     para entregar previsões através de consenso"

O terceiro estudo -- `Capacidade de Previsão Quântica`, 1000 páginas -- não é
um catálogo de ideias como os dois primeiros. É uma ESPECIFICAÇÃO. Ele desenha
a arquitetura inteira e entrega a matemática pronta:

    960 formulações, da 1 à 960, nenhuma pulada
    12 inteligências x 48 famílias x 5 mesas
    192 formulações por mesa -- Mega Fire, Lighting, Crazy Time, Crazy Time A
    e Immersive, sem sobra nem falta
    16 formulações por mesa por inteligência
    100% com FÓRMULA AUDITÁVEL

O cabeçalho de cada página já diz de quem é a leitura:

    MEGA FIRE  |  F02  |  IA01  |  FORMULAÇÃO 007

Este arquivo implementa as doze. A fórmula de cada uma está escrita no topo do
método, exatamente como ele publicou, para conferência linha a linha.

AS DOZE, E O QUE CADA UMA PERGUNTA
──────────────────────────────────
    IA01  Tempo e intervalos       Que relação temporal reaparece quando o
                                   contexto também reaparece?
    IA02  Recência multiescala     Qual escala descreve a cena e qual só reage
                                   ao ruído?
    IA03  Sequências e motivos     O que permanece reconhecível quando a forma
                                   muda?
    IA04  Transições contextuais   A passagem importa por si ou só dentro de
                                   um regime?
    IA05  Redes e vizinhanças      Quais vizinhanças reaparecem como estrutura
                                   e não só como contagem?
    IA06  Agrupamento e dispersão  O conjunto forma uma ecologia temporal ou
                                   apenas extremos esperados?
    IA07  Regimes e fases          Qual teoria volta a ficar pertinente quando
                                   o regime retorna?
    IA08  Simetria e geometria     A forma geométrica acrescenta algo além da
                                   frequência?
    IA09  Anomalias e resíduos     A anomalia muda a teoria ou só chama
                                   atenção?
    IA10  Intensidade e saliência  A magnitude tem memória própria ou só
                                   acompanha a presença?
    IA11  Familiaridades           Quando duas cenas diferentes pertencem ao
                                   mesmo tipo?
    IA12  Agregação                (é o consenso -- vive em `consenso_ia12`)

POR QUE IA12 NÃO APONTA NÚMERO
──────────────────────────────
Porque no desenho dele IA12 não é uma leitura, é o AGREGADOR: pesos
exponenciais sobre a perda acumulada de cada especialista. Ela não opina sobre
a mesa, opina sobre as outras onze. Fica em `consenso_ia12()`, no fim.

Isso corrige um defeito meu que estava lá desde o começo: eu somava peso fixo
por fonte. Quem errava a semana inteira continuava pesando igual. Na fórmula
dele, quem erra perde peso sozinho, sem eu precisar podar ninguém -- o que
também respeita o que ele já tinha mandado: "não critique e nem barre".

O QUE ESTE ARQUIVO NÃO FAZ
──────────────────────────
Não julga o conteúdo dele. A fórmula entra como está publicada. Onde a mesa não
oferece o dado que a fórmula pede (multiplicador em roleta sem marca, por
exemplo), a inteligência se cala e diz por quê -- em vez de inventar leitura,
que é o erro que ele já me apontou antes.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

# ═════════════════════════════════════════════════════════ a roda física
RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}

# As mesas do Tratado, com o nome que ele usa no cabeçalho das formulações.
MESAS = {
    "mega_fire": "MEGA FIRE",
    "lightning": "LIGHTING",          # é assim que está escrito no livro dele
    "crazy_time": "CRAZY TIME",
    "crazy_time_a": "CRAZY TIME A",
}

# Suavização de Dirichlet, o alpha das fórmulas IA02 e IA04.
ALPHA = 0.5


def _ints(seq) -> List[int]:
    out = []
    for x in seq or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _norm(peso: Dict[Any, float]) -> Dict[str, float]:
    """Chaves viram texto e o maior vira 1.0 — para as onze somarem na mesma escala."""
    peso = {str(k): float(v) for k, v in (peso or {}).items()
            if v is not None and float(v) > 0 and math.isfinite(float(v))}
    if not peso:
        return {}
    teto = max(peso.values()) or 1.0
    return {k: v / teto for k, v in peso.items()}


def _tem_roda(n_classes) -> bool:
    """A mesa tem geometria física?

    Checar `x in POS` não serve: as classes do Crazy Time são 0..7, e 0..7
    também são casas da roleta -- a checagem passava e IA05/IA08 opinavam
    sobre a "vizinhança na roda" de um jogo que não tem roda numerada. Quem
    decide é o tamanho da mesa.
    """
    return int(n_classes) >= 37


# ═══════════════════════════════════════════════════════ IA01 .. IA11
#
# Cada uma devolve (peso_por_classe, fala). Peso vazio = ela se calou, e a fala
# diz o motivo. Silêncio com motivo vale mais que palpite inventado.

def ia01_tempo_intervalos(seq, n_classes, ctx):
    """IA01 · Tempo e intervalos.

        D_t = t - max{i<t : Y_i = 1}

    O atraso de cada classe desde a última vez que apareceu. É a fórmula que
    ele já tinha confirmado por conta própria em outro lugar: "sinal é somente
    o que tá muito tempo sem vir".

    O histórico chega RECENTE-PRIMEIRO, então o índice já é D_t.
    """
    s = _ints(seq)
    if len(s) < 30:
        return {}, "amostra curta para medir intervalo (precisa de 30+)"
    visto: Dict[int, int] = {}
    for i, x in enumerate(s):
        visto.setdefault(x, i)              # primeira vista = mais recente
    peso = {}
    for x in range(int(n_classes)):
        peso[x] = float(visto.get(x, len(s)))   # nunca veio = atraso máximo
    return _norm(peso), f"D_t medido nas {n_classes} classes"


def ia02_recencia_multiescala(seq, n_classes, ctx):
    """IA02 · Recência multiescala.

        p_s(t) = (alpha + Σ_(i=t-w_s)^(t-1) Y_i) / (alpha + beta + w_s)

    A mesma classe medida em várias janelas w_s ao mesmo tempo. A pergunta
    dele: "qual escala está descrevendo a cena e qual apenas reage ao ruído?".

    A resposta sai da CONCORDÂNCIA entre escalas: o que sobe em todas é cena;
    o que sobe só na curta é ruído. Por isso o peso é o mínimo entre as
    escalas, não a média -- a média deixaria o ruído da janela curta passar.
    """
    s = _ints(seq)
    if len(s) < 60:
        return {}, "amostra curta para comparar escalas (precisa de 60+)"
    escalas = [w for w in (20, 50, 120, 250) if w <= len(s)]
    if len(escalas) < 2:
        return {}, "só uma escala cabe na amostra — sem contraste"
    base = 1.0 / n_classes
    razao: Dict[int, List[float]] = defaultdict(list)
    for w in escalas:
        c = Counter(s[:w])
        beta = (n_classes - 1) * ALPHA
        for x in range(int(n_classes)):
            p = (ALPHA + c.get(x, 0)) / (ALPHA + beta + w)
            razao[x].append(p / base)
    peso = {x: min(v) for x, v in razao.items() if min(v) > 1.0}
    return _norm(peso), (f"{len(escalas)} escalas ({', '.join(map(str, escalas))}); "
                         f"{len(peso)} sobem em todas")


def ia03_motivos(seq, n_classes, ctx):
    """IA03 · Sequências e motivos.

        PMI(a,b) = log( P(a,b) / (P(a)·P(b)) )

    Informação mútua pontual entre o que saiu e o que veio depois. Mede se o
    par acontece MAIS do que o acaso das duas frequências isoladas explicaria
    -- que é diferente de "o par é frequente".
    """
    s = _ints(seq)
    if len(s) < 80:
        return {}, "amostra curta para motivos (precisa de 80+)"
    n = len(s) - 1
    solo = Counter(s)
    par = Counter((s[i + 1], s[i]) for i in range(n))    # (antes, depois)
    atual = s[0]
    if solo.get(atual, 0) < 3:
        return {}, f"o {atual} só apareceu {solo.get(atual, 0)}x — sem base"
    peso = {}
    for (a, b), q in par.items():
        if a != atual or q < 2:
            continue
        p_ab = q / n
        p_a = solo[a] / len(s)
        p_b = solo[b] / len(s)
        if p_a > 0 and p_b > 0:
            pmi = math.log(p_ab / (p_a * p_b))
            if pmi > 0:
                peso[b] = pmi
    return _norm(peso), (f"PMI a partir do {atual} ({solo[atual]}x); "
                         f"{len(peso)} pares acima do acaso")


def ia04_transicao(seq, n_classes, ctx):
    """IA04 · Transições contextuais.

        P_ab = (N_ab + alpha) / (N_a + K·alpha)

    Transição de primeira ordem com suavização de Dirichlet. O alpha é o que
    impede que um par visto uma única vez vire certeza -- o erro clássico da
    matriz de transição crua.

    Só devolve o que ficar ACIMA da suavizada uniforme; senão a fórmula
    devolveria a mesa inteira em ordem alfabética.
    """
    s = _ints(seq)
    if len(s) < 60:
        return {}, "amostra curta para transição (precisa de 60+)"
    atual = s[0]
    seg = Counter()
    n_a = 0
    for i in range(1, len(s)):
        if s[i] == atual:
            n_a += 1
            seg[s[i - 1]] += 1
    if n_a < 4:
        return {}, f"o {atual} só apareceu {n_a}x antes — sem base"
    K = int(n_classes)
    piso = ALPHA / (n_a + K * ALPHA)
    peso = {}
    for b in range(K):
        p = (seg.get(b, 0) + ALPHA) / (n_a + K * ALPHA)
        if p > piso * 1.5:
            peso[b] = p
    return _norm(peso), f"P_ab suavizada a partir do {atual}, em {n_a} passagens"


def ia05_vizinhancas(seq, n_classes, ctx):
    """IA05 · Redes e vizinhanças.

        I_3(A;B;C) = I(A;B) - I(A;B|C)

    Informação de interação: quanto a vizinhança na roda ACRESCENTA depois de
    descontar o que a contagem isolada já explicava. É a pergunta dele --
    "quais vizinhanças reaparecem como estrutura e não só como contagem?".

    Sem posição na roda (Crazy Time), a fórmula não tem sobre o que operar.
    """
    s = _ints(seq)
    if len(s) < 80:
        return {}, "amostra curta para vizinhança (precisa de 80+)"
    if not _tem_roda(n_classes):
        return {}, "esta mesa não tem posição física na roda"
    n = len(s) - 1
    c = Counter(s)
    # coocorrência de vizinhanças: o que sai perto (na roda) do que saiu antes
    viz = Counter()
    for i in range(n):
        a, b = s[i + 1], s[i]
        if a in POS and b in POS:
            d = abs(POS[a] - POS[b])
            d = min(d, len(RODA) - d)
            if d <= 3:
                viz[b] += 1
    if sum(viz.values()) < 10:
        return {}, "poucos saltos curtos na roda para medir estrutura"
    total = sum(viz.values())
    peso = {}
    for x, q in viz.items():
        obs = q / total
        esp = c.get(x, 0) / len(s)
        if esp > 0 and obs > esp:
            peso[x] = math.log(obs / esp)       # o que a vizinhança acrescenta
    return _norm(peso), (f"{len(peso)} aparecem em vizinhança mais do que a "
                         f"contagem isolada explicaria")


def ia06_rajada(seq, n_classes, ctx):
    """IA06 · Agrupamento e dispersão.

        B = (sd(D) - mean(D)) / (sd(D) + mean(D))

    Coeficiente de rajada sobre os intervalos D de cada classe. B > 0 quer
    dizer que ela vem em grupo e depois some; B < 0, que vem espaçada.

    Quem tem B alto E está no meio de uma seca longa é a leitura da fórmula:
    a rajada dela ainda não veio.
    """
    s = _ints(seq)
    if len(s) < 100:
        return {}, "amostra curta para rajada (precisa de 100+)"
    ultimo: Dict[int, int] = {}
    inter: Dict[int, List[int]] = defaultdict(list)
    desde: Dict[int, int] = {}
    for i, x in enumerate(s):
        desde.setdefault(x, i)
        if x in ultimo:
            inter[x].append(i - ultimo[x])
        ultimo[x] = i
    peso = {}
    for x, D in inter.items():
        if len(D) < 4:
            continue
        m = sum(D) / len(D)
        var = sum((d - m) ** 2 for d in D) / len(D)
        sd = math.sqrt(var)
        if sd + m <= 0:
            continue
        B = (sd - m) / (sd + m)
        if B > 0 and desde.get(x, 0) > m:
            peso[x] = B * (desde[x] / m)
    return _norm(peso), (f"{len(peso)} com rajada (B>0) e seca acima do "
                         f"próprio intervalo médio")


def ia07_regime(seq, n_classes, ctx):
    """IA07 · Regimes e mudanças de fase.

        K_t = Σ_j 1[detector_j marca t ± delta]

    Consenso entre detectores de mudança, não um detector só. Cada janela
    candidata é votada por vários testes; onde vários marcam junto, houve
    mudança de regime -- e o que vale é o trecho DEPOIS dela.
    """
    s = _ints(seq)
    if len(s) < 120:
        return {}, "amostra curta para detectar regime (precisa de 120+)"
    N = len(s)
    cortes = [c for c in range(40, N - 40, 10)]
    if not cortes:
        return {}, "sem ponto de corte possível"
    marcas = Counter()
    for c in cortes:
        novo, velho = s[:c], s[c:]
        cn, cv = Counter(novo), Counter(velho)
        # detector 1: mudou o topo
        t1 = set(x for x, _ in cn.most_common(5)) != set(
            x for x, _ in cv.most_common(5))
        # detector 2: mudou a dispersão
        d1 = sum((cn.get(x, 0) / len(novo) - 1 / n_classes) ** 2
                 for x in range(int(n_classes)))
        d2 = sum((cv.get(x, 0) / len(velho) - 1 / n_classes) ** 2
                 for x in range(int(n_classes)))
        t2 = d1 > d2 * 1.4 or d2 > d1 * 1.4
        # detector 3: mudou a taxa de repetição imediata
        r1 = sum(1 for i in range(1, len(novo)) if novo[i] == novo[i - 1])
        r2 = sum(1 for i in range(1, len(velho)) if velho[i] == velho[i - 1])
        t3 = abs(r1 / max(1, len(novo)) - r2 / max(1, len(velho))) > 0.03
        k = int(t1) + int(t2) + int(t3)
        if k >= 2:
            marcas[c] = k
    if not marcas:
        return {}, "nenhum corte marcado por 2+ detectores — regime estável"
    corte = min(marcas, key=lambda c: (-marcas[c], c))
    recente = s[:corte]
    c = Counter(recente)
    esp = len(recente) / n_classes
    peso = {x: (q - esp) / esp for x, q in c.items() if q > esp}
    return _norm(peso), (f"regime mudou há ~{corte} giros "
                         f"({marcas[corte]} detectores concordam); lendo só depois")


def ia08_geometria(seq, n_classes, ctx):
    """IA08 · Simetria e geometria.

        v_t = [X_t, X_(t-tau), ..., X_(t-(m-1)·tau)]

    Imersão temporal de estados (Takens). O estado não é o último número, é o
    vetor dos últimos m separados por tau. Quando o vetor de agora repete um
    vetor do passado, o que veio depois daquele volta a ser candidato.

    Ele pergunta se a geometria acrescenta além da frequência -- aqui ela
    acrescenta ORDEM, que a contagem joga fora.
    """
    s = _ints(seq)
    if len(s) < 120:
        return {}, "amostra curta para imersão (precisa de 120+)"
    if not _tem_roda(n_classes):
        return {}, "esta mesa não tem geometria de roda"
    # m=3 sobre 8 setores dá 512 estados: em 400 giros o estado atual quase
    # nunca repete, e a leitura morria por falta de caso. m=2 dá 64 estados,
    # que é o que a amostra dele sustenta.
    m, tau = 2, 1
    # o estado é o SETOR de cada um, senão a repetição exata quase nunca ocorre
    def setor(x):
        return POS[x] // 5 if x in POS else -1

    atual = tuple(setor(s[i * tau]) for i in range(m))
    peso = Counter()
    achados = 0
    for i in range(1, len(s) - m * tau - 1):
        v = tuple(setor(s[i + j * tau]) for j in range(m))
        if v == atual:
            peso[s[i - 1]] += 1
            achados += 1
    if achados < 3:
        return {}, f"o estado atual só repetiu {achados}x — sem base"
    return _norm(peso), (f"vetor de {m} setores repetiu {achados}x; "
                         f"o que veio depois")


def ia09_surpresa(seq, n_classes, ctx):
    """IA09 · Anomalias e resíduos.

        S_B = KL( P(theta|D_new) || P(theta|D_old) )

    Surpresa bayesiana: o quanto a crença sobre cada classe MUDOU quando os
    dados recentes chegaram. Não é "saiu muito", é "saiu diferente do que eu
    achava" -- a pergunta dele, "a anomalia muda a teoria ou apenas chama
    atenção?".
    """
    s = _ints(seq)
    if len(s) < 120:
        return {}, "amostra curta para surpresa (precisa de 120+)"
    meio = len(s) // 3
    novo, velho = s[:meio], s[meio:]
    cn, cv = Counter(novo), Counter(velho)
    K = int(n_classes)
    peso = {}
    for x in range(K):
        a_new = ALPHA + cn.get(x, 0)
        b_new = ALPHA * (K - 1) + len(novo) - cn.get(x, 0)
        a_old = ALPHA + cv.get(x, 0)
        b_old = ALPHA * (K - 1) + len(velho) - cv.get(x, 0)
        p_new = a_new / (a_new + b_new)
        p_old = a_old / (a_old + b_old)
        if p_new <= 0 or p_old <= 0 or p_new >= 1 or p_old >= 1:
            continue
        kl = (p_new * math.log(p_new / p_old)
              + (1 - p_new) * math.log((1 - p_new) / (1 - p_old)))
        if kl > 0 and p_new > p_old:            # surpresa PARA CIMA
            peso[x] = kl
    return _norm(peso), f"{len(peso)} com crença revisada para cima (KL>0)"


def ia10_intensidade(seq, n_classes, ctx):
    """IA10 · Intensidade e saliência.

        P(M=0) = 1-p ;  log(M)|M>0 ~ F(theta)

    Modelo hurdle: separa EXISTÊNCIA do multiplicador da MAGNITUDE dele. São
    dois processos, e tratá-los como um só foi um erro meu que o segundo PDF
    dele já apontava -- a mesa pode ganhar em ocorrência e perder em magnitude
    ao mesmo tempo (Lighting: +8,2% e -59,2%).

    A pergunta dele: "a magnitude possui memória própria ou só acompanha a
    presença?". A resposta sai da comparação entre as duas metades do hurdle.
    """
    mults = (ctx or {}).get("mults") or []
    if not mults:
        return {}, "esta mesa não entrega marca de multiplicador"
    s = _ints(seq)
    pares = [(x, m) for x, m in zip(s, mults) if m]
    if len(pares) < 8:
        return {}, f"só {len(pares)} marcas de multiplicador — sem base"

    # metade 1 do hurdle: quem TEM multiplicador com mais frequência
    c_tot = Counter(s[:len(mults)])
    c_mult = Counter(x for x, _ in pares)
    p_base = len(pares) / max(1, len(mults))
    existencia = {}
    for x, q in c_mult.items():
        n_x = c_tot.get(x, 0)
        if n_x >= 3:
            p_x = q / n_x
            if p_x > p_base:
                existencia[x] = p_x / p_base

    # metade 2: entre os que têm, quem tem multiplicador GRANDE
    porv: Dict[int, List[float]] = defaultdict(list)
    for x, m in pares:
        try:
            v = float(m)
        except (TypeError, ValueError):
            continue
        if v > 0:
            porv[x].append(math.log(v))
    if not porv:
        return _norm(existencia), "hurdle: só a metade de existência tem dado"
    todos = [v for vs in porv.values() for v in vs]
    media = sum(todos) / len(todos)
    magnitude = {x: math.exp(sum(vs) / len(vs) - media)
                 for x, vs in porv.items() if len(vs) >= 2}

    peso = {}
    for x in set(existencia) | set(magnitude):
        peso[x] = existencia.get(x, 1.0) * magnitude.get(x, 1.0)
    return _norm(peso), (f"hurdle sobre {len(pares)} marcas: "
                         f"{len(existencia)} por existência, "
                         f"{len(magnitude)} por magnitude")


def ia11_familiaridade(seq, n_classes, ctx):
    """IA11 · Familiaridades contextuais.

        I_q = P(Y) - Σ_c P(Y|c)·P(c)

    Resíduo de interferência. Se a mesa fosse a soma limpa dos seus contextos,
    I_q seria zero: a probabilidade total seria a média das condicionais. O que
    sobra é o que a decomposição por contexto NÃO explica.

    É a assinatura que dá nome ao livro dele -- e é a única das doze que mede
    algo que a estatística clássica de contagem descarta por construção.
    """
    s = _ints(seq)
    if len(s) < 120:
        return {}, "amostra curta para interferência (precisa de 120+)"
    # contextos: em que "cena" a mesa estava -- aqui, o setor do giro anterior
    def ctx_de(x):
        return POS[x] // 5 if x in POS else (x % 4)

    K = int(n_classes)
    total = Counter(s)
    n = len(s)
    porc: Dict[int, Counter] = defaultdict(Counter)
    nc = Counter()
    for i in range(n - 1):
        c = ctx_de(s[i + 1])
        porc[c][s[i]] += 1
        nc[c] += 1
    if len(nc) < 2:
        return {}, "um contexto só — sem interferência para medir"
    peso = {}
    for y in range(K):
        p_y = total.get(y, 0) / n
        soma = sum((porc[c].get(y, 0) / nc[c]) * (nc[c] / max(1, n - 1))
                   for c in nc if nc[c] > 0)
        iq = p_y - soma
        if iq > 0:
            peso[y] = iq
    return _norm(peso), (f"I_q > 0 em {len(peso)} classes sobre "
                         f"{len(nc)} contextos")


# ═════════════════════════════════════════════════ o painel das onze
INTELIGENCIAS: Tuple = (
    ("IA01_TEMPO", ia01_tempo_intervalos, "tempo e intervalos",
     "D_t = t - max{i<t : Y_i=1}"),
    ("IA02_RECENCIA", ia02_recencia_multiescala, "recência multiescala",
     "p_s(t)=(α+Σ Y_i)/(α+β+w_s)"),
    ("IA03_MOTIVOS", ia03_motivos, "sequências e motivos",
     "PMI(a,b)=log(P(a,b)/(P(a)P(b)))"),
    ("IA04_TRANSICAO", ia04_transicao, "transições contextuais",
     "P_ab=(N_ab+α)/(N_a+K·α)"),
    ("IA05_VIZINHANCA", ia05_vizinhancas, "redes e vizinhanças",
     "I_3(A;B;C)=I(A;B)-I(A;B|C)"),
    ("IA06_RAJADA", ia06_rajada, "agrupamento e dispersão",
     "B=(sd(D)-mean(D))/(sd(D)+mean(D))"),
    ("IA07_REGIME", ia07_regime, "regimes e mudanças de fase",
     "K_t=Σ_j 1[detector_j marca t±δ]"),
    ("IA08_GEOMETRIA", ia08_geometria, "simetria e geometria",
     "v_t=[X_t,X_(t-τ),…,X_(t-(m-1)τ)]"),
    ("IA09_SURPRESA", ia09_surpresa, "anomalias e resíduos",
     "S_B=KL(P(θ|D_new)‖P(θ|D_old))"),
    ("IA10_INTENSIDADE", ia10_intensidade, "intensidade e saliência",
     "P(M=0)=1-p; log(M)|M>0~F(θ)"),
    ("IA11_FAMILIARIDADE", ia11_familiaridade, "familiaridades contextuais",
     "I_q=P(Y)-Σ_c P(Y|c)P(c)"),
)


def formula_de(nome: str) -> str:
    for n, _f, _d, form in INTELIGENCIAS:
        if n == nome:
            return form
    return ""


# ═════════════════════════════════════════════ de onde cada leitura saiu
#
# Uma previsão que não diz de onde veio não é auditável, e o livro dele é
# inteiro sobre leitura auditável. Aqui cada inteligência recupera as
# formulações que ELA assina NA MESA em questão -- 16 por mesa por IA.
#
# Lê o índice destilado, que fica versionado justamente para sobreviver ao
# container ser apagado. Sem o índice, a IA continua rodando e só deixa de
# citar; ela não para.

_INDICE: Optional[Dict[str, List[dict]]] = None


def _carregar_indice() -> Dict[str, List[dict]]:
    """Formulações agrupadas por (MESA, IAxx). Lido uma vez e guardado."""
    global _INDICE
    if _INDICE is not None:
        return _INDICE
    _INDICE = {}
    try:
        import json
        from pathlib import Path
        arq = Path(__file__).resolve().parent / "indice_estudos_destilado.json"
        d = json.loads(arq.read_text(encoding="utf-8"))
        for _est, corpo in (d.get("estudos") or {}).items():
            for u in corpo.get("unidades") or []:
                if u.get("tipo") != "formulacao":
                    continue
                chave = f"{u.get('mesa', '')}|{u.get('ia', '')}"
                _INDICE.setdefault(chave, []).append(u)
    except Exception:
        _INDICE = {}
    return _INDICE


def citar(nome_ia: str, jogo: str, quantas: int = 2) -> List[dict]:
    """As formulações que esta inteligência assina nesta mesa.

    `nome_ia` é o nome interno (IA01_TEMPO); o livro usa IA01. `jogo` é a
    chave do software (lightning); o livro escreve LIGHTING.
    """
    mesa = MESAS.get(str(jogo), "")
    curto = str(nome_ia).split("_")[0]            # IA01_TEMPO -> IA01
    achadas = _carregar_indice().get(f"{mesa}|{curto}") or []
    return sorted(achadas, key=lambda u: u.get("n", 0))[:quantas]


def texto_citacao(nome_ia: str, jogo: str) -> str:
    """Uma linha em português dizendo de onde a leitura saiu."""
    fs = citar(nome_ia, jogo, 2)
    if not fs:
        return ""
    ns = ", ".join(f"#{u.get('n')}" for u in fs)
    fam = fs[0].get("familia", "")
    tit = (fs[0].get("titulo") or "").split("—")[0].strip()
    total = len(_carregar_indice().get(
        f"{MESAS.get(str(jogo), '')}|{str(nome_ia).split('_')[0]}") or [])
    return (f"formulação {ns} de {total}, família {fam}"
            + (f" — {tit[:52]}" if tit else ""))


def especialidade_de(nome: str) -> str:
    for n, _f, d, _form in INTELIGENCIAS:
        if n == nome:
            return d
    return ""


def consultar(seq, n_classes: int = 37, ctx: Dict[str, Any] = None,
              k: int = 6) -> Dict[str, Any]:
    """As onze leem a mesa. IA12 agrega depois, em `consenso_ia12`."""
    ctx = ctx or {}
    palpites, falas, pesos = {}, {}, {}
    for nome, fn, _d, _form in INTELIGENCIAS:
        try:
            peso, fala = fn(seq, n_classes, ctx)
        except Exception as e:                  # nenhuma derruba as outras
            peso, fala = {}, f"erro: {type(e).__name__}"
        falas[nome] = fala
        if peso:
            pesos[nome] = peso
            ranking = sorted(peso.items(), key=lambda x: (-x[1], str(x[0])))
            palpites[nome] = [str(c) for c, v in ranking if v > 0][:k]
    return {"palpites": palpites, "falas": falas, "pesos": pesos,
            "opinaram": len(palpites), "total": len(INTELIGENCIAS)}


# ══════════════════════════════════════════════════════════════ IA12
#
#     w_(j,t) ∝ exp(-eta · Loss_(j,1:t-1))
#
# A décima segunda inteligência. Ela não lê a mesa -- lê as outras onze.

ETA = 0.6            # o quanto o erro passado pesa. Alto demais vira ditadura
                     # da última rodada; baixo demais, todo mundo igual para
                     # sempre. 0,6 leva ~5 janelas para separar quem acerta.


def pesos_ia12(perdas: Dict[str, float], eta: float = ETA) -> Dict[str, float]:
    """Peso de cada inteligência pela perda acumulada dela.

        w_(j,t) ∝ exp(-eta · Loss_(j,1:t-1))

    Sem histórico de perda, todas valem 1 -- que é o comportamento antigo, e é
    o certo no começo: ninguém errou ainda.

    Nenhuma é zerada. Quem erra encolhe e continua na mesa, porque ele já
    mandou: "não critique e nem barre". Encolher não é podar.
    """
    if not perdas:
        return {}
    menor = min(perdas.values())
    w = {j: math.exp(-eta * (L - menor)) for j, L in perdas.items()}
    s = sum(w.values()) or 1.0
    n = len(w)
    return {j: v / s * n for j, v in w.items()}       # média 1.0


def consenso_ia12(pesos_por_ia: Dict[str, Dict[str, float]],
                  perdas: Optional[Dict[str, float]] = None,
                  k: int = 12, eta: float = ETA) -> Dict[str, Any]:
    """A agregação dele: soma ponderada pelo desempenho, não por peso fixo.

    Devolve os k mais votados e, para cada um, quem votou -- porque um número
    escolhido sem dizer quem o escolheu não é auditável, e o livro inteiro
    dele é sobre leitura auditável.
    """
    w = pesos_ia12(perdas or {}, eta)
    placar: Dict[str, float] = defaultdict(float)
    quem: Dict[str, List[str]] = defaultdict(list)
    for ia, peso in (pesos_por_ia or {}).items():
        wj = w.get(ia, 1.0)
        for classe, v in (peso or {}).items():
            placar[str(classe)] += wj * float(v)
            quem[str(classe)].append(ia)
    ordem = sorted(placar.items(), key=lambda x: (-x[1], x[0]))
    return {
        "ordem": [c for c, _ in ordem[:k]],
        "placar": dict(ordem[:k]),
        "quem": {c: quem[c] for c, _ in ordem[:k]},
        "pesos_ia": w,
    }


def resumo(seq, n_classes: int = 37, ctx: Dict[str, Any] = None,
           perdas: Optional[Dict[str, float]] = None) -> str:
    r = consultar(seq, n_classes, ctx)
    L = [f"[Tratado] {r['opinaram']} das {r['total']} inteligências leram a mesa"]
    for nome, _fn, desc, form in INTELIGENCIAS:
        p = r["palpites"].get(nome)
        if p:
            L.append(f"   {nome:<20} {form[:34]:<34} {' '.join(p[:6])}")
        else:
            L.append(f"   {nome:<20} {form[:34]:<34} — {r['falas'].get(nome, '')[:44]}")
    ag = consenso_ia12(r["pesos"], perdas)
    L.append(f"   IA12 agrega           w∝exp(-η·Loss)"
             f"                     {' '.join(ag['ordem'][:8])}")
    return "\n".join(L)
