# -*- coding: utf-8 -*-
"""
AS 44 LEITURAS DO TRATADO — F01 a F44, uma função por família dele.

REGRA DESTE ARQUIVO
───────────────────
Toda função aqui implementa UMA família publicada, e o nome dela é o número da
família. A fórmula dele está no topo de cada uma, copiada do livro, para
conferência linha a linha.

O que NÃO existe aqui: heurística minha. Se uma ideia não tem número de
família, ela não entra. Foi exatamente isso que ele mandou consertar --
"ficou muito misturado".

O QUE UMA LEITURA DEVOLVE
─────────────────────────
    (peso_por_classe, fala)

`peso` vazio significa que ela se calou, e `fala` diz por quê. Silêncio com
motivo vale mais que palpite inventado -- e várias famílias dele se calam com
frequência de propósito, porque medem condições que raramente ocorrem.

O ESTADO DE CADA FAMÍLIA
────────────────────────
Nem todas as 44 são executáveis com o dado que a API entrega. Em vez de fingir
que executo, cada família declara seu estado:

    EXECUTA     está implementada e roda
    SEM_DADO    a fórmula pede variável que a mesa não fornece
    PENDENTE    ainda não implementei

`PENDENTE` é dívida minha declarada, não omissão. O painel mostra a conta, e
ele vê exatamente quanto do livro dele já está no ar.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}

ALPHA = 0.5          # suavização de Dirichlet, o alpha das fórmulas dele


def _ints(seq) -> List[int]:
    out = []
    for x in seq or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _norm(peso: Dict[Any, float]) -> Dict[str, float]:
    """Chaves viram texto, o maior vira 1,0 — para as 44 somarem na mesma escala."""
    p = {}
    for k, v in (peso or {}).items():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f > 0 and math.isfinite(f):
            p[str(k)] = f
    if not p:
        return {}
    teto = max(p.values()) or 1.0
    return {k: v / teto for k, v in p.items()}


def _tem_roda(n_classes) -> bool:
    """Só as roletas têm geometria física; 0..7 do Crazy Time não são casas."""
    return int(n_classes) >= 37


_CORTES: Dict[Tuple[int, int], float] = {}


def _corte_setor(N: int, W: int, alfa: float = 0.05,
                 ensaios: int = 4000) -> float:
    """O corte em desvios para "este setor da roda está quente".

    A janela desliza pelas N posições e a leitura fica com a MAIOR. Ficar com
    a maior de N não é o mesmo que olhar uma: no corte de 1,5 desvio a roda
    honesta acusava vício em ~4 de cada 10 leituras, e a correção de Šidák
    sobre janelas efetivas ainda deixava 16%. Janelas vizinhas enxergam quase
    o mesmo pedaço da roda, então a fórmula fechada superestima a
    independência delas.

    A ficha 001 do compêndio dele diz o que fazer nesse caso: trocar a
    aproximação assintótica por Monte Carlo sob probabilidades iguais. É o que
    está aqui -- o percentil 95 da estatística do máximo, medido, não deduzido.
    Roda uma vez por (N, W) e fica guardado.
    """
    chave = (int(N), int(W))
    if chave in _CORTES:
        return _CORTES[chave]
    import random as _r
    rnd = _r.Random(20260816)               # semente fixa: corte reproduzível
    n = 200                                 # tamanho típico de leitura aqui
    p = W / N
    esp = n * p
    dp = math.sqrt(n * p * (1 - p)) or 1.0
    maximos = []
    for _ in range(ensaios):
        c = Counter(rnd.randrange(N) for _ in range(n))
        maximos.append(max(
            (sum(c.get((i + d) % N, 0) for d in range(W)) - esp) / dp
            for i in range(N)))
    maximos.sort()
    corte = maximos[min(len(maximos) - 1, int((1 - alfa) * len(maximos)))]
    _CORTES[chave] = corte
    return corte


def _atrasos(s: List[int], n_classes: int) -> Dict[int, int]:
    """D_t de cada classe. A lista vem RECENTE-PRIMEIRO, então o índice é o atraso."""
    visto: Dict[int, int] = {}
    for i, x in enumerate(s):
        visto.setdefault(x, i)
    return {x: visto.get(x, len(s)) for x in range(int(n_classes))}


def _intervalos(s: List[int]) -> Dict[int, List[int]]:
    """Os intervalos entre aparições sucessivas de cada classe."""
    ultimo: Dict[int, int] = {}
    inter: Dict[int, List[int]] = defaultdict(list)
    for i, x in enumerate(s):
        if x in ultimo:
            inter[x].append(i - ultimo[x])
        ultimo[x] = i
    return inter


# ═══════════════════════════════════════════════ IA01 · tempo e intervalos

def f01(s, k, ctx):
    """F01 · Intervalo contextual desde a última ocorrência.

        D_t = t - max{i<t : Y_i=1}

    A regra que ele confirmou por conta própria em outro lugar: "sinal é
    somente o que tá muito tempo sem vir".
    """
    if len(s) < 30:
        return {}, "amostra curta para intervalo (30+)"
    return _norm(_atrasos(s, k)), f"D_t nas {k} classes"


def f02(s, k, ctx):
    """F02 · Contração e expansão dos intervalos.

        A_t = log((D_(t-1)+1)/(D_(t-2)+1))

    Não é o intervalo, é a TRAJETÓRIA dele: os intervalos daquela classe estão
    encurtando ou alongando? A_t > 0 quer dizer que estão se abrindo.
    """
    if len(s) < 80:
        return {}, "amostra curta para trajetória de intervalos (80+)"
    peso = {}
    for x, D in _intervalos(s).items():
        if len(D) < 3:
            continue
        a = math.log((D[0] + 1) / (D[1] + 1))     # D[0] é o mais recente
        if a > 0:                                  # intervalos se abrindo
            peso[x] = a
    return _norm(peso), (f"{len(peso)} com intervalos em expansão"
                         if peso else "nenhum intervalo em expansão")


def f03(s, k, ctx):
    """F03 · Periodicidade imperfeita.

        I(f) = |Σ_t (Y_t - ȳ)·exp(-2πift)|² / n

    Periodograma da série indicadora de cada classe. Procura ritmo que não é
    exato -- por isso "imperfeita": um pico largo conta.
    """
    if len(s) < 120:
        return {}, "amostra curta para periodograma (120+)"
    n = len(s)
    peso = {}
    for x in range(int(k)):
        y = [1.0 if v == x else 0.0 for v in s]
        m = sum(y) / n
        if sum(y) < 6:
            continue
        melhor = 0.0
        # períodos plausíveis: de 3 giros até um quinto da amostra
        for periodo in range(3, max(4, n // 5)):
            f = 1.0 / periodo
            re = sum((y[t] - m) * math.cos(-2 * math.pi * f * t) for t in range(n))
            im = sum((y[t] - m) * math.sin(-2 * math.pi * f * t) for t in range(n))
            melhor = max(melhor, (re * re + im * im) / n)
        # referência: a potência média que a própria série teria sem ritmo
        base = sum((v - m) ** 2 for v in y) / n
        if base > 0 and melhor / base > 2.5:
            peso[x] = melhor / base
    return _norm(peso), (f"{len(peso)} com pico espectral acima de 2,5x"
                         if peso else "nenhum ritmo acima do ruído")


def f04(s, k, ctx):
    """F04 · Memória de duração.

        h(d) = (κ/λ)·(d/λ)^(κ-1)

    Risco de Weibull sobre o intervalo. κ>1 quer dizer que a chance de vir
    AUMENTA conforme a espera cresce -- é o que separa "está atrasado" de
    "está atrasado e a espera pesa".
    """
    if len(s) < 100:
        return {}, "amostra curta para risco de duração (100+)"
    at = _atrasos(s, k)
    peso = {}
    for x, D in _intervalos(s).items():
        if len(D) < 5:
            continue
        # κ por regressão de momentos: cv = sd/média decresce com κ
        m = sum(D) / len(D)
        if m <= 0:
            continue
        sd = math.sqrt(sum((d - m) ** 2 for d in D) / len(D))
        cv = sd / m
        if cv <= 0 or cv >= 1.0:
            continue                               # κ<=1: espera não pesa
        kappa = cv ** -1.086                       # aproximação usual
        lam = m
        d = max(1, at.get(x, 0))
        h = (kappa / lam) * ((d / lam) ** (kappa - 1))
        if kappa > 1.0 and h > 0:
            peso[x] = h * (kappa - 1.0)
    return _norm(peso), (f"{len(peso)} com risco crescente (κ>1)"
                         if peso else "nenhuma classe com espera que pesa")


# ═══════════════════════════════════════════ IA02 · recência multiescala

def _densidade(s, k, w):
    """p(t) = (α + Σ Y_i) / (α + β + w) — a posterior beta-binomial da janela."""
    c = Counter(s[:w])
    beta = (k - 1) * ALPHA
    return {x: (ALPHA + c.get(x, 0)) / (ALPHA + beta + w) for x in range(int(k))}


def f05(s, k, ctx):
    """F05 · Densidade curta.

        p_s(t) = (α + Σ_(i=t-w_s)^(t-1) Y_i) / (α + β + w_s)
    """
    if len(s) < 40:
        return {}, "amostra curta para densidade curta (40+)"
    w = min(30, len(s))
    base = 1.0 / k
    p = _densidade(s, k, w)
    return _norm({x: v / base for x, v in p.items() if v > base}), \
        f"janela curta de {w} giros"


def f06(s, k, ctx):
    """F06 · Densidade intermediária.

        p_m(t) = λ·Y_(t-1) + (1-λ)·p_m(t-1)

    Suavização exponencial: o passado pesa, mas decai. É a memória média entre
    a janela curta (que reage a tudo) e a longa (que não reage a nada).
    """
    if len(s) < 60:
        return {}, "amostra curta para densidade intermediária (60+)"
    lam = 0.06
    p = {x: 1.0 / k for x in range(int(k))}
    for v in reversed(s):                          # do mais antigo ao mais novo
        for x in p:
            p[x] = lam * (1.0 if v == x else 0.0) + (1 - lam) * p[x]
    base = 1.0 / k
    return _norm({x: v / base for x, v in p.items() if v > base}), \
        f"suavização exponencial λ={lam}"


def f07(s, k, ctx):
    """F07 · Densidade longa.

        p_l(t) = (α + Σ_(i<t) Y_i) / (α + β + t - 1)
    """
    if len(s) < 100:
        return {}, "amostra curta para densidade longa (100+)"
    base = 1.0 / k
    p = _densidade(s, k, len(s))
    return _norm({x: v / base for x, v in p.items() if v > base}), \
        f"histórico inteiro ({len(s)} giros)"


def f08(s, k, ctx):
    """F08 · Alinhamento e conflito entre escalas.

        Z_t = [p_s(t), p_m(t), p_l(t)] ;  C_t = var(Z_t)

    A pergunta dele: "qual escala está descrevendo a cena e qual apenas reage
    ao ruído?". Quem ALINHA nas três é cena. Variância alta é conflito, e
    conflito não é sinal -- por isso o peso cai com C_t.
    """
    if len(s) < 100:
        return {}, "amostra curta para comparar escalas (100+)"
    base = 1.0 / k
    ps = _densidade(s, k, min(30, len(s)))
    pl = _densidade(s, k, len(s))
    pm = _densidade(s, k, min(120, len(s)))
    peso = {}
    for x in range(int(k)):
        Z = [ps[x] / base, pm[x] / base, pl[x] / base]
        if min(Z) <= 1.0:
            continue                               # não sobe nas três
        mu = sum(Z) / 3
        C = sum((z - mu) ** 2 for z in Z) / 3
        peso[x] = mu / (1.0 + C)                   # alinhamento premiado
    return _norm(peso), (f"{len(peso)} alinhados nas três escalas"
                         if peso else "nenhuma classe sobe nas três escalas")


# ═══════════════════════════════════════════ IA03 · sequências e motivos

def f09(s, k, ctx):
    """F09 · Motivos mínimos.

        PMI(a,b) = log( P(a,b) / (P(a)·P(b)) )
    """
    if len(s) < 80:
        return {}, "amostra curta para motivos (80+)"
    n = len(s) - 1
    solo = Counter(s)
    atual = s[0]
    if solo.get(atual, 0) < 3:
        return {}, f"o {atual} só apareceu {solo.get(atual,0)}x — sem base"
    par = Counter((s[i + 1], s[i]) for i in range(n))
    peso = {}
    for (a, b), q in par.items():
        if a != atual or q < 2:
            continue
        p_ab, p_a, p_b = q / n, solo[a] / len(s), solo[b] / len(s)
        if p_a > 0 and p_b > 0:
            pmi = math.log(p_ab / (p_a * p_b))
            if pmi > 0:
                peso[b] = pmi
    return _norm(peso), f"PMI a partir do {atual} ({solo[atual]}x)"


def f10(s, k, ctx):
    """F10 · Motivos extensos.

        L(m) = Σ_t -log P(X_t | X_(t-m:t-1))

    Contexto de comprimento m, não de 1. Onde o contexto atual já apareceu
    antes, o que veio depois volta a ser candidato.
    """
    if len(s) < 150:
        return {}, "amostra curta para motivo extenso (150+)"
    for m in (3, 2):
        ctx_atual = tuple(s[:m])
        peso = Counter()
        vistos = 0
        for i in range(1, len(s) - m):
            if tuple(s[i:i + m]) == ctx_atual:
                peso[s[i - 1]] += 1
                vistos += 1
        if vistos >= 3:
            return _norm(peso), f"contexto de {m} repetiu {vistos}x"
    return {}, "o contexto atual nunca repetiu — sem base"


def f11(s, k, ctx):
    """F11 · Ruptura de sequência.

        R_t = -log P(X_t | X_(t-k:t-1))

    Surpresa do que ACABOU de sair. R_t alto quer dizer que a sequência
    quebrou -- e depois de quebra o modelo curto vale menos que o longo.
    Devolve o longo quando detecta ruptura, e se cala quando não há.
    """
    if len(s) < 120:
        return {}, "amostra curta para ruptura (120+)"
    solo = Counter(s[1:])
    p = (solo.get(s[0], 0) + ALPHA) / (len(s) - 1 + k * ALPHA)
    R = -math.log(p) if p > 0 else 0.0
    esperado = math.log(k)
    if R <= esperado * 1.15:
        return {}, f"sem ruptura (R_t={R:.2f}, esperado {esperado:.2f})"
    base = 1.0 / k
    pl = _densidade(s, k, len(s))
    return _norm({x: v / base for x, v in pl.items() if v > base}), \
        f"ruptura detectada (R_t={R:.2f}) — lendo pela escala longa"


def f12(s, k, ctx):
    """F12 · Retorno parcial de motivo.

        Sim(A,B) = 1 - dist(A,B)/max(|A|,|B|)

    O motivo não precisa voltar idêntico. Compara o trecho recente com todos
    os trechos passados por distância de Hamming e usa os mais parecidos.
    """
    if len(s) < 150:
        return {}, "amostra curta para motivo parcial (150+)"
    m = 5
    A = s[:m]
    achados = []
    for i in range(1, len(s) - m - 1):
        B = s[i:i + m]
        d = sum(1 for a, b in zip(A, B) if a != b)
        sim = 1.0 - d / m
        if sim >= 0.6:                             # 3 de 5 iguais
            achados.append((sim, s[i - 1]))
    if len(achados) < 3:
        return {}, f"só {len(achados)} trechos parecidos — sem base"
    peso = defaultdict(float)
    for sim, prox in achados:
        peso[prox] += sim
    return _norm(peso), f"{len(achados)} trechos com 60%+ de semelhança"


# ═══════════════════════════════════════ IA04 · transições contextuais

def f13(s, k, ctx):
    """F13 · Transição de primeira ordem.

        P_ab = (N_ab + α) / (N_a + K·α)
    """
    if len(s) < 60:
        return {}, "amostra curta para transição (60+)"
    atual = s[0]
    seg = Counter()
    n_a = 0
    for i in range(1, len(s)):
        if s[i] == atual:
            n_a += 1
            seg[s[i - 1]] += 1
    if n_a < 4:
        return {}, f"o {atual} só apareceu {n_a}x antes — sem base"
    K = int(k)
    piso = ALPHA / (n_a + K * ALPHA)
    peso = {b: (seg.get(b, 0) + ALPHA) / (n_a + K * ALPHA) for b in range(K)}
    return _norm({b: v for b, v in peso.items() if v > piso * 1.5}), \
        f"P_ab a partir do {atual}, em {n_a} passagens"


def f14(s, k, ctx):
    """F14 · Transição de ordem ampliada.

        P(X_t | X_(t-1), …, X_(t-k))

    Mesma ideia da F13 com contexto maior. Cai para ordem menor quando a
    amostra não sustenta a maior -- é o recuo que evita transformar
    coincidência única em certeza.
    """
    if len(s) < 120:
        return {}, "amostra curta para ordem ampliada (120+)"
    for ordem in (3, 2):
        ctx_atual = tuple(s[:ordem])
        seg = Counter()
        n_c = 0
        for i in range(1, len(s) - ordem):
            if tuple(s[i:i + ordem]) == ctx_atual:
                n_c += 1
                seg[s[i - 1]] += 1
        if n_c >= 4:
            K = int(k)
            peso = {b: (seg.get(b, 0) + ALPHA) / (n_c + K * ALPHA)
                    for b in seg}
            return _norm(peso), f"contexto de ordem {ordem}, {n_c} ocorrências"
    return {}, "nem a ordem 2 tem ocorrências suficientes"


def f15(s, k, ctx):
    """F15 · Contexto posterior à presença.

        Δ_k = P(Y_(t+k)=1 | Y_t=1, C_t) - P(Y=1 | C_t)

    O que muda DEPOIS que a classe apareceu, comparado ao normal dela. Δ>0 é
    eco; Δ<0 é exaustão. Só o eco vira palpite.
    """
    if len(s) < 120:
        return {}, "amostra curta para eco (120+)"
    peso = {}
    for x in range(int(k)):
        idx = [i for i, v in enumerate(s) if v == x]
        if len(idx) < 5:
            continue
        base = len(idx) / len(s)
        melhor = 0.0
        for lag in (1, 2, 3):
            depois = sum(1 for i in idx if i - lag >= 0 and s[i - lag] == x)
            tent = sum(1 for i in idx if i - lag >= 0)
            if tent >= 5:
                melhor = max(melhor, depois / tent - base)
        if melhor > 0:
            peso[x] = melhor
    return _norm(peso), (f"{len(peso)} com eco após a própria presença"
                         if peso else "nenhum eco acima da base")


def f16(s, k, ctx):
    """F16 · Contexto posterior à ausência.

        logit P(Y_t=1) = b0 + s(D_t) + γ·C_t

    A chance cresce com a ausência? Aqui `s(D_t)` é medido: para cada classe,
    compara a taxa de retorno quando o atraso está acima do típico com a taxa
    geral. É a versão medida do "está muito tempo sem vir".
    """
    if len(s) < 120:
        return {}, "amostra curta para efeito da ausência (120+)"
    at = _atrasos(s, k)
    peso = {}
    for x, D in _intervalos(s).items():
        if len(D) < 5:
            continue
        m = sum(D) / len(D)
        d = at.get(x, 0)
        if d <= m:
            continue
        # quantos intervalos passados chegaram a ser tão longos quanto este?
        tao_longos = sum(1 for v in D if v >= d)
        if tao_longos == 0:
            peso[x] = d / m * 1.5                  # inédito: espera recorde
        else:
            peso[x] = d / m
    return _norm(peso), (f"{len(peso)} acima do próprio intervalo típico"
                         if peso else "ninguém acima do próprio típico")


# ══════════════════════════════════════════ IA05 · redes e vizinhanças

def f17(s, k, ctx):
    """F17 · Pares recorrentes.

        w_ab = N_ab / E0[N_ab]

    O par observado dividido pelo par esperado se não houvesse estrutura.
    """
    if len(s) < 100:
        return {}, "amostra curta para pares (100+)"
    n = len(s) - 1
    solo = Counter(s)
    atual = s[0]
    par = Counter((s[i + 1], s[i]) for i in range(n))
    peso = {}
    for (a, b), q in par.items():
        if a != atual or q < 2:
            continue
        esperado = solo[a] * solo[b] / len(s)
        if esperado > 0 and q / esperado > 1.0:
            peso[b] = q / esperado
    return _norm(peso), f"w_ab a partir do {atual}"


def f18(s, k, ctx):
    """F18 · Tríades contextuais.

        I_3(A;B;C) = I(A;B) - I(A;B|C)

    O que a vizinhança acrescenta DEPOIS de descontar o que a contagem
    isolada já explicava.
    """
    if len(s) < 100:
        return {}, "amostra curta para tríade (100+)"
    if not _tem_roda(k):
        return {}, "esta mesa não tem vizinhança física na roda"
    n = len(s) - 1
    c = Counter(s)
    viz = Counter()
    for i in range(n):
        a, b = s[i + 1], s[i]
        if a in POS and b in POS:
            d = abs(POS[a] - POS[b])
            if min(d, len(RODA) - d) <= 3:
                viz[b] += 1
    if sum(viz.values()) < 10:
        return {}, "poucos saltos curtos para medir estrutura"
    tot = sum(viz.values())
    peso = {}
    for x, q in viz.items():
        obs, esp = q / tot, c.get(x, 0) / len(s)
        if esp > 0 and obs > esp:
            peso[x] = math.log(obs / esp)
    return _norm(peso), f"{len(peso)} acrescentam além da contagem"


def f19(s, k, ctx):
    """F19 · Comunidades de proximidade.

        Q = Σ_c (e_cc - a_c²)

    Modularidade: os setores da roda formam comunidade de verdade ou a
    divisão é arbitrária? Só devolve quando Q indica agrupamento real.
    """
    if len(s) < 150:
        return {}, "amostra curta para modularidade (150+)"
    if not _tem_roda(k):
        return {}, "esta mesa não tem comunidades na roda"
    def com(x):
        return POS[x] // 5 if x in POS else -1
    n = len(s) - 1
    e = Counter()
    grau = Counter()
    for i in range(n):
        a, b = com(s[i + 1]), com(s[i])
        if a < 0 or b < 0:
            continue
        if a == b:
            e[a] += 1
        grau[a] += 1
        grau[b] += 1
    if not grau:
        return {}, "sem arestas para medir"
    m2 = sum(grau.values())
    Q = sum(e[c] / max(1, n) - (grau[c] / m2) ** 2 for c in grau)
    if Q <= 0.02:
        return {}, f"Q={Q:.3f} — setores não formam comunidade"
    forte = max(e, key=lambda c: e[c])
    peso = {RODA[j]: 1.0 for j in range(forte * 5, min((forte + 1) * 5, len(RODA)))}
    return _norm(peso), f"Q={Q:.3f} — setor {forte} fecha em si"


def f20(s, k, ctx):
    """F20 · Exclusão e anticoocorrência.

        NPMI(a,b) = log(P_ab/(P_a·P_b)) / -log(P_ab)

    O que NÃO vem junto. NPMI muito negativo marca exclusão; a leitura é o
    complemento -- se o atual exclui um conjunto, o resto ganha.
    """
    if len(s) < 120:
        return {}, "amostra curta para exclusão (120+)"
    n = len(s) - 1
    solo = Counter(s)
    atual = s[0]
    if solo.get(atual, 0) < 5:
        return {}, f"o {atual} só apareceu {solo.get(atual,0)}x — sem base"
    par = Counter((s[i + 1], s[i]) for i in range(n))
    excluidos = set()
    for b in range(int(k)):
        q = par.get((atual, b), 0)
        p_ab = (q + 0.5) / n
        p_a, p_b = solo[atual] / len(s), (solo.get(b, 0) + 0.5) / len(s)
        if p_ab <= 0 or p_a <= 0 or p_b <= 0:
            continue
        npmi = math.log(p_ab / (p_a * p_b)) / -math.log(p_ab)
        if npmi < -0.25:
            excluidos.add(b)
    if not excluidos or len(excluidos) >= k - 2:
        return {}, f"{len(excluidos)} exclusões — sem contraste útil"
    return _norm({x: 1.0 for x in range(int(k)) if x not in excluidos}), \
        f"{len(excluidos)} classes excluídas depois do {atual}"


# ═════════════════════════════════════ IA06 · agrupamento e dispersão

def f21(s, k, ctx):
    """F21 · Rajadas.

        B = (sd(D) - mean(D)) / (sd(D) + mean(D))

    B>0: a classe vem em grupo e depois some. Quem tem B alto e está em seca
    longa ainda não teve a rajada dela.
    """
    if len(s) < 100:
        return {}, "amostra curta para rajada (100+)"
    at = _atrasos(s, k)
    peso = {}
    for x, D in _intervalos(s).items():
        if len(D) < 4:
            continue
        m = sum(D) / len(D)
        sd = math.sqrt(sum((d - m) ** 2 for d in D) / len(D))
        if sd + m <= 0:
            continue
        B = (sd - m) / (sd + m)
        if B > 0 and at.get(x, 0) > m:
            peso[x] = B * (at[x] / m)
    return _norm(peso), (f"{len(peso)} em rajada (B>0) e em seca"
                         if peso else "nenhuma classe em rajada e seca")


def f22(s, k, ctx):
    """F22 · Desertos.

        L_max = max_j run_length_j(Y=0)

    A maior seca histórica de cada classe. Quem está perto do próprio recorde
    de ausência é o que a fórmula aponta.
    """
    if len(s) < 100:
        return {}, "amostra curta para deserto (100+)"
    at = _atrasos(s, k)
    peso = {}
    for x in range(int(k)):
        D = _intervalos(s).get(x) or []
        if not D:
            peso[x] = 1.5                          # nunca veio: deserto total
            continue
        Lmax = max(D)
        if at.get(x, 0) >= Lmax * 0.9:
            peso[x] = at[x] / max(1, Lmax)
    return _norm(peso), (f"{len(peso)} perto do próprio recorde de ausência"
                         if peso else "ninguém perto do recorde de seca")


def f23(s, k, ctx):
    """F23 · Forma e extensão dos agrupamentos.

        S = max_W (O_W - E_W)/√E_W

    Varre janelas de vários tamanhos e fica com o maior excesso padronizado.
    Varrer muitas janelas e ficar com a maior INFLA o resultado; por isso o
    corte sai de Šidák sobre o número de janelas efetivamente testadas.
    """
    if len(s) < 150:
        return {}, "amostra curta para agrupamento (150+)"
    peso = {}
    larguras = [w for w in (20, 40, 80) if w <= len(s)]
    n_testes = max(1, len(larguras) * max(1, len(s) // 20))
    try:
        from statistics import NormalDist
        corte = NormalDist().inv_cdf((1 - 0.05) ** (1.0 / n_testes))
    except Exception:
        corte = 3.0
    for x in range(int(k)):
        idx = [i for i, v in enumerate(s) if v == x]
        if len(idx) < 5:
            continue
        p = len(idx) / len(s)
        melhor = 0.0
        for w in larguras:
            E = w * p
            if E < 3:
                continue
            for ini in range(0, len(s) - w, max(1, w // 2)):
                O = sum(1 for i in idx if ini <= i < ini + w)
                melhor = max(melhor, (O - E) / math.sqrt(E))
        if melhor > corte:
            peso[x] = melhor
    return _norm(peso), (f"{len(peso)} acima de {corte:.1f} desvios "
                         f"(corte já descontando {n_testes} janelas)")


def f24(s, k, ctx):
    """F24 · Dissolução e retorno do agrupamento.

        R_ij = 1[dist(v_i,v_j) ≤ ε]

    Matriz de recorrência: quando o estado de agora reencontra um estado
    passado, o que veio depois daquele volta a ser candidato.
    """
    if len(s) < 150:
        return {}, "amostra curta para recorrência (150+)"
    m = 3
    def v(i):
        return tuple(s[i:i + m])
    atual = v(0)
    peso = Counter()
    achados = 0
    for i in range(1, len(s) - m - 1):
        d = sum(1 for a, b in zip(atual, v(i)) if a != b)
        if d <= 1:                                  # ε = 1 diferença
            peso[s[i - 1]] += 1
            achados += 1
    if achados < 3:
        return {}, f"o estado atual só reencontrou {achados}x"
    return _norm(peso), f"{achados} reencontros do estado atual"


# ══════════════════════════════════════ IA07 · regimes e mudanças de fase

def f25(s, k, ctx):
    """F25 · Consenso entre detectores de mudança.

        K_t = Σ_j 1[detector_j marca t ± δ]

    Um detector sozinho marca ruído. A fórmula exige que vários concordem no
    mesmo ponto, e só então o trecho recente vale mais que a média de tudo.
    """
    if len(s) < 120:
        return {}, "amostra curta para detectar regime (120+)"
    N = len(s)
    marcas = Counter()
    for c in range(40, N - 40, 10):
        novo, velho = s[:c], s[c:]
        cn, cv = Counter(novo), Counter(velho)
        t1 = set(x for x, _ in cn.most_common(5)) != set(
            x for x, _ in cv.most_common(5))
        d1 = sum((cn.get(x, 0) / len(novo) - 1 / k) ** 2 for x in range(int(k)))
        d2 = sum((cv.get(x, 0) / len(velho) - 1 / k) ** 2 for x in range(int(k)))
        t2 = d1 > d2 * 1.4 or d2 > d1 * 1.4
        r1 = sum(1 for i in range(1, len(novo)) if novo[i] == novo[i - 1])
        r2 = sum(1 for i in range(1, len(velho)) if velho[i] == velho[i - 1])
        t3 = abs(r1 / max(1, len(novo)) - r2 / max(1, len(velho))) > 0.03
        j = int(t1) + int(t2) + int(t3)
        if j >= 2:
            marcas[c] = j
    if not marcas:
        return {}, "nenhum ponto marcado por 2+ detectores"
    corte = min(marcas, key=lambda c: (-marcas[c], c))
    c = Counter(s[:corte])
    esp = corte / k
    return _norm({x: (q - esp) / esp for x, q in c.items() if q > esp}), \
        f"regime mudou há ~{corte} giros ({marcas[corte]} detectores)"


def f26(s, k, ctx):
    """F26 · Regime semi-Markov com duração explícita.

        P(S_t=j, D=d | S_prev=i) = A_ij · g_j(d)

    O regime tem duração própria: não basta saber que mudou, importa há quanto
    tempo está no atual. Aqui o estado é grosso (qual terço da mesa domina) e
    g_j(d) sai das durações passadas do mesmo estado.
    """
    if len(s) < 200:
        return {}, "amostra curta para regime com duração (200+)"
    def estado(janela):
        c = Counter(janela)
        if not c:
            return -1
        return c.most_common(1)[0][0] % 3           # terço dominante
    W = 25
    seq_est = [estado(s[i:i + W]) for i in range(0, len(s) - W, W)]
    if len(seq_est) < 5:
        return {}, "poucos blocos para medir duração de regime"
    duracoes = defaultdict(list)
    atual, conta = seq_est[0], 1
    for e in seq_est[1:]:
        if e == atual:
            conta += 1
        else:
            duracoes[atual].append(conta)
            atual, conta = e, 1
    d_atual = conta
    hist = duracoes.get(seq_est[0]) or []
    if len(hist) < 2:
        return {}, "o estado atual não tem histórico de duração"
    media = sum(hist) / len(hist)
    if d_atual < media:
        return {}, (f"regime atual com {d_atual} blocos, típico {media:.1f} "
                    f"— ainda dentro da duração dele")
    c = Counter(s[:W * 2])
    esp = (W * 2) / k
    return _norm({x: (q - esp) / esp for x, q in c.items() if q > esp}), \
        f"regime atual já passou da duração típica ({d_atual} vs {media:.1f})"


def f27(s, k, ctx):
    """F27 · Deriva suave do regime.

        logit P(Y_t=1) = b0 + s(t)

    Não é quebra, é ladeira. Ajusta tendência linear no logito de cada classe
    e devolve as que estão subindo de forma consistente.
    """
    if len(s) < 200:
        return {}, "amostra curta para deriva (200+)"
    B = 5
    blocos = [s[i:i + len(s) // B] for i in range(0, len(s), max(1, len(s) // B))][:B]
    if len(blocos) < B:
        return {}, "não deu para dividir em blocos"
    peso = {}
    for x in range(int(k)):
        ys = []
        for b in blocos:
            q = sum(1 for v in b if v == x)
            p = (q + ALPHA) / (len(b) + k * ALPHA)
            ys.append(math.log(p / (1 - p)))
        # blocos vêm do mais recente ao mais antigo: subir = ys decrescente
        n = len(ys)
        mx = (n - 1) / 2
        my = sum(ys) / n
        num = sum((i - mx) * (ys[i] - my) for i in range(n))
        den = sum((i - mx) ** 2 for i in range(n)) or 1.0
        incl = -num / den                           # positivo = crescendo agora
        if incl > 0 and all(ys[i] >= ys[i + 1] - 0.35 for i in range(n - 1)):
            peso[x] = incl
    return _norm(peso), (f"{len(peso)} em deriva de subida"
                         if peso else "nenhuma deriva consistente")


def f28(s, k, ctx):
    """F28 · Retorno e transporte de regimes.

        T_reg = min_(r≠q) Skill(train_r, test_q)

    A leitura de um trecho vale em outro? Mede se o topo de frequência de um
    bloco se sustenta no bloco seguinte -- e só devolve o que TRANSPORTA.
    """
    if len(s) < 240:
        return {}, "amostra curta para transporte (240+)"
    B = 4
    tam = len(s) // B
    blocos = [s[i * tam:(i + 1) * tam] for i in range(B)]
    topos = [set(x for x, _ in Counter(b).most_common(max(3, k // 6)))
             for b in blocos]
    persistentes = set.intersection(*topos) if topos else set()
    if not persistentes:
        return {}, "nenhuma classe permanece no topo dos quatro blocos"
    return _norm({x: 1.0 for x in persistentes}), \
        f"{len(persistentes)} no topo dos {B} blocos — leitura transportável"


# ═════════════════════════════════════════ IA08 · simetria e geometria

def f29(s, k, ctx):
    """F29 · Imersão temporal de estados.

        v_t = [X_t, X_(t-τ), …, X_(t-(m-1)τ)]
    """
    if len(s) < 120:
        return {}, "amostra curta para imersão (120+)"
    if not _tem_roda(k):
        return {}, "esta mesa não tem geometria de roda"
    m = 2
    def setor(x):
        return POS[x] // 5 if x in POS else -1
    atual = tuple(setor(s[i]) for i in range(m))
    peso = Counter()
    achados = 0
    for i in range(1, len(s) - m - 1):
        if tuple(setor(s[i + j]) for j in range(m)) == atual:
            peso[s[i - 1]] += 1
            achados += 1
    if achados < 3:
        return {}, f"o estado atual só repetiu {achados}x"
    return _norm(peso), f"vetor de {m} setores repetiu {achados}x"


def f30(s, k, ctx):
    """F30 · Topologia persistente das familiaridades.

        Pers = Σ_i (death_i - birth_i)

    Homologia persistente sobre a nuvem de estados. Precisa de biblioteca de
    topologia computacional que este pacote não carrega, e implementar
    persistência à mão daria resultado que eu não saberia validar.
    """
    return {}, "PENDENTE — precisa de homologia persistente"


def f31(s, k, ctx):
    """F31 · Quebra e restauração de simetria.

        Z_c = (n_c - w·π_c) / √(w·π_c·(1-π_c))

    Assimetria por SETOR CONTÍGUO da roda -- a assinatura observável de vício
    físico. A janela desliza e dá a volta no cilindro; o corte de desvio já
    desconta o número de janelas testadas, senão a roda honesta "acusa vício"
    em quatro leituras de cada dez.
    """
    if len(s) < 120:
        return {}, "amostra curta para simetria (120+)"
    if not _tem_roda(k):
        return {}, "esta mesa não tem roda física"
    pos = [POS[x] for x in s if x in POS]
    if not pos:
        return {}, "sem posição na roda"
    N, W = len(RODA), 5
    n = len(pos)
    conta = Counter(pos)
    pi_c = W / N
    dp = math.sqrt(n * pi_c * (1 - pi_c)) or 1.0
    esp = n * pi_c
    melhor, z_max = None, -9.9
    for ini in range(N):
        jan = [(ini + d) % N for d in range(W)]
        z = (sum(conta.get(j, 0) for j in jan) - esp) / dp
        if z > z_max:
            melhor, z_max = jan, z
    corte = _corte_setor(N, W)
    if z_max <= corte:
        return {}, (f"maior setor a {z_max:.1f} desvios, abaixo do corte "
                    f"{corte:.1f} — roda simétrica")
    return _norm({RODA[j]: z_max for j in melhor}), \
        f"setor a {z_max:.1f} desvios (corte {corte:.2f} por Monte Carlo, {N} janelas)"


def f32(s, k, ctx):
    """F32 · Espectro e comunidades do grafo.

        L = D - A ;  gap = λ_(k+1) - λ_k

    Laplaciano do grafo de transições. O gap espectral diz se o grafo se
    parte em comunidades. Precisa de decomposição de autovalores de matriz
    37x37, e sem numpy no pacote isso sai caro e mal condicionado.
    """
    return {}, "PENDENTE — precisa de decomposição espectral"


# ═══════════════════════════════════════ IA09 · anomalias e resíduos

def f33(s, k, ctx):
    """F33 · Surpresa bayesiana contextual.

        S_B = KL( P(θ|D_new) ‖ P(θ|D_old) )
    """
    if len(s) < 120:
        return {}, "amostra curta para surpresa (120+)"
    meio = len(s) // 3
    novo, velho = s[:meio], s[meio:]
    cn, cv = Counter(novo), Counter(velho)
    K = int(k)
    peso = {}
    for x in range(K):
        a1, b1 = ALPHA + cn.get(x, 0), ALPHA * (K - 1) + len(novo) - cn.get(x, 0)
        a0, b0 = ALPHA + cv.get(x, 0), ALPHA * (K - 1) + len(velho) - cv.get(x, 0)
        p1, p0 = a1 / (a1 + b1), a0 / (a0 + b0)
        if not (0 < p1 < 1 and 0 < p0 < 1):
            continue
        kl = p1 * math.log(p1 / p0) + (1 - p1) * math.log((1 - p1) / (1 - p0))
        if kl > 0 and p1 > p0:
            peso[x] = kl
    return _norm(peso), f"{len(peso)} com crença revisada para cima"


def f34(s, k, ctx):
    """F34 · Estrutura residual após modelos principais.

        e_t = Y_t - p_t ;  Q = n(n+2)·Σ_k ρ_k(e)²/(n-k)

    O que sobra depois de descontar a frequência. Ljung-Box sobre o resíduo:
    se Q é grande, restou estrutura que a contagem não pegou.
    """
    if len(s) < 150:
        return {}, "amostra curta para resíduo (150+)"
    n = len(s)
    peso = {}
    for x in range(int(k)):
        y = [1.0 if v == x else 0.0 for v in s]
        p = sum(y) / n
        if sum(y) < 8:
            continue
        e = [v - p for v in y]
        var = sum(v * v for v in e) / n
        if var <= 0:
            continue
        Q = 0.0
        for lag in range(1, 6):
            num = sum(e[t] * e[t + lag] for t in range(n - lag)) / (n - lag)
            rho = num / var
            Q += rho * rho / (n - lag)
        Q *= n * (n + 2)
        if Q > 11.07:                              # qui-quadrado 5 gl, 5%
            peso[x] = Q
    return _norm(peso), (f"{len(peso)} com estrutura residual (Q>11,1)"
                         if peso else "nenhum resíduo estruturado")


def f35(s, k, ctx):
    """F35 · Controles negativos e placebos temporais.

        Δ_neg = Skill(X_legit) - max_j Skill(X_placebo_j)

    Esta família NÃO aponta classe: ela mede se as outras estão lendo sinal ou
    ruído. Embaralha a série e compara a força do achado com a do embaralhado.
    O resultado entra como fator de confiança do painel.
    """
    return {}, "não aponta classe — mede a confiança das outras (ver painel)"


def f36(s, k, ctx):
    """F36 · Vazamento, duplicação e erro de observação.

        LeakGap = S_illegal - S_legal ;  DupGap = θ_all - θ_dedup

    Também não aponta classe. Denuncia giro duplicado, que é o erro de captura
    mais comum aqui -- e o que mais infla taxa de acerto sem ninguém perceber.
    """
    if len(s) < 40:
        return {}, "amostra curta para checar duplicação"
    rep = sum(1 for i in range(1, len(s)) if s[i] == s[i - 1])
    esperado = (len(s) - 1) / k
    if esperado > 0 and rep > esperado * 2.5:
        return {}, (f"⚠ {rep} repetições imediatas onde o esperado é "
                    f"{esperado:.0f} — suspeita de giro duplicado na captura")
    return {}, f"sem sinal de duplicação ({rep} repetições, esperado {esperado:.0f})"


# ═════════════════════════════════════ IA10 · intensidade e saliência

def f37(s, k, ctx):
    """F37 · Modelo hurdle de existência e intensidade.

        P(M=0) = 1-p ;  log(M)|M>0 ~ F(θ)

    Existência e magnitude são processos SEPARADOS. Tratá-los como um só foi
    erro meu que o segundo estudo dele já apontava: a mesa pode ganhar em
    ocorrência e perder em magnitude ao mesmo tempo.
    """
    mults = (ctx or {}).get("mults") or []
    if not mults:
        return {}, "esta mesa não entrega marca de multiplicador"
    pares = [(x, m) for x, m in zip(s, mults) if m]
    if len(pares) < 8:
        return {}, f"só {len(pares)} marcas — sem base"
    c_tot = Counter(s[:len(mults)])
    c_mult = Counter(x for x, _ in pares)
    p_base = len(pares) / max(1, len(mults))
    existe = {}
    for x, q in c_mult.items():
        n_x = c_tot.get(x, 0)
        if n_x >= 3 and q / n_x > p_base:
            existe[x] = (q / n_x) / p_base
    porv = defaultdict(list)
    for x, m in pares:
        try:
            v = float(m)
        except (TypeError, ValueError):
            continue
        if v > 0:
            porv[x].append(math.log(v))
    if not porv:
        return _norm(existe), "hurdle: só a metade de existência tem dado"
    todos = [v for vs in porv.values() for v in vs]
    media = sum(todos) / len(todos)
    magn = {x: math.exp(sum(vs) / len(vs) - media)
            for x, vs in porv.items() if len(vs) >= 2}
    peso = {x: existe.get(x, 1.0) * magn.get(x, 1.0)
            for x in set(existe) | set(magn)}
    return _norm(peso), (f"hurdle em {len(pares)} marcas: {len(existe)} por "
                         f"existência, {len(magn)} por magnitude")


def f38(s, k, ctx):
    """F38 · Inclinação robusta e quantis da intensidade.

        β_TS = median_(i<j)( (log M_j - log M_i)/(j - i) )

    Theil-Sen sobre o log do multiplicador: a magnitude está subindo ou
    descendo ao longo do tempo? Robusto a um único valor extremo, que é o que
    quebra a regressão comum.
    """
    mults = (ctx or {}).get("mults") or []
    vals = [(i, float(m)) for i, m in enumerate(mults)
            if m and str(m).replace(".", "").isdigit()]
    if len(vals) < 6:
        return {}, f"só {len(vals)} marcas para medir inclinação"
    incl = []
    for a in range(len(vals)):
        for b in range(a + 1, len(vals)):
            (i, mi), (j, mj) = vals[a], vals[b]
            if j != i and mi > 0 and mj > 0:
                incl.append((math.log(mj) - math.log(mi)) / (j - i))
    if not incl:
        return {}, "sem pares para Theil-Sen"
    incl.sort()
    beta = incl[len(incl) // 2]
    # a lista é recente-primeiro: beta<0 quer dizer magnitude crescendo agora
    if beta >= 0:
        return {}, f"β_TS={beta:+.4f} — magnitude não está subindo"
    pares = [(x, float(m)) for x, m in zip(s, mults)
             if m and str(m).replace(".", "").isdigit()]
    peso = defaultdict(float)
    for x, m in pares:
        if m > 0:
            peso[x] += math.log(m)
    return _norm(peso), f"β_TS={beta:+.4f} — magnitude em alta"


def f39(s, k, ctx):
    """F39 · Cauda extrema estabilizada.

        P(M > u+x | M > u) = (1 + ξx/σ)^(-1/ξ)

    Pareto generalizada sobre os multiplicadores acima do limiar u. ξ>0 marca
    cauda pesada -- o extremo é possível, não anomalia.
    """
    mults = [float(m) for m in ((ctx or {}).get("mults") or [])
             if m and str(m).replace(".", "").isdigit()]
    if len(mults) < 12:
        return {}, f"só {len(mults)} marcas para estimar cauda"
    mults.sort()
    # O limiar u tem que deixar excedentes ACIMA dele. Com valores repetidos
    # (50, 100, 500 e nada entre), o quantil 70% caía em cima do maior valor e
    # a cauda ficava vazia -- a fórmula não tinha o que estimar. Aqui u desce
    # até sobrar amostra de verdade.
    u = None
    for q in (0.70, 0.60, 0.50, 0.40, 0.30):
        cand = mults[int(len(mults) * q)]
        if sum(1 for m in mults if m > cand) >= 5:
            u = cand
            break
    if u is None:
        return {}, (f"os multiplicadores não têm cauda para medir "
                    f"({len(set(mults))} valores distintos em {len(mults)} marcas)")
    exc = [m - u for m in mults if m > u]
    m1 = sum(exc) / len(exc)
    m2 = sum(e * e for e in exc) / len(exc)
    if m2 <= m1 * m1:
        return {}, "momentos degenerados"
    # estimador de momentos da GPD
    xi = 0.5 * (1 - m1 * m1 / (m2 - m1 * m1))
    return {}, (f"ξ={xi:+.2f} sobre {len(exc)} excedentes (u={u:.0f}) — "
                + ("cauda pesada: extremo é esperado, não anomalia"
                   if xi > 0 else "cauda leve: extremo é raro de verdade"))


def f40(s, k, ctx):
    """F40 · Processo pontual marcado e cópula.

        λ(t,m|H) = λ0(t|H)·f(m|t,H) ;  F_DM = C(F_D, F_M)

    Precisa de ajuste de cópula entre a duração e a marca, com amostra que
    essas mesas não fornecem: as bases dele têm dezenas de marcas, não
    milhares.
    """
    return {}, "PENDENTE — cópula precisa de amostra que a mesa não dá"


# ═══════════════════════════════ IA11 · familiaridades contextuais

def f41(s, k, ctx):
    """F41 · Resíduo de interferência probabilística.

        I_q = P(Y) - Σ_c P(Y|c)·P(c)

    Se a mesa fosse a soma limpa dos seus contextos, I_q seria zero. O que
    sobra é o que a decomposição por contexto não explica -- a assinatura que
    dá nome ao livro dele.
    """
    if len(s) < 120:
        return {}, "amostra curta para interferência (120+)"
    def ctx_de(x):
        return POS[x] // 5 if x in POS and _tem_roda(k) else (x % 4)
    K = int(k)
    total = Counter(s)
    n = len(s)
    porc = defaultdict(Counter)
    nc = Counter()
    for i in range(n - 1):
        c = ctx_de(s[i + 1])
        porc[c][s[i]] += 1
        nc[c] += 1
    if len(nc) < 2:
        return {}, "um contexto só — sem interferência a medir"
    peso = {}
    for y in range(K):
        p_y = total.get(y, 0) / n
        soma = sum((porc[c].get(y, 0) / nc[c]) * (nc[c] / max(1, n - 1))
                   for c in nc if nc[c] > 0)
        if p_y - soma > 0:
            peso[y] = p_y - soma
    return _norm(peso), f"I_q>0 em {len(peso)} classes sobre {len(nc)} contextos"


def f42(s, k, ctx):
    """F42 · Contextualidade por conteúdo e contexto.

        X_q^c ≠ X_q^c'  — testar acoplamento multimaximal

    A mesma classe se comporta diferente em contextos diferentes? Mede a
    dispersão da taxa condicional entre contextos; dispersão alta é
    contextualidade.
    """
    if len(s) < 150:
        return {}, "amostra curta para contextualidade (150+)"
    def ctx_de(x):
        return POS[x] // 5 if x in POS and _tem_roda(k) else (x % 4)
    porc = defaultdict(Counter)
    nc = Counter()
    for i in range(len(s) - 1):
        c = ctx_de(s[i + 1])
        porc[c][s[i]] += 1
        nc[c] += 1
    ctxs = [c for c in nc if nc[c] >= 20]
    if len(ctxs) < 2:
        return {}, "poucos contextos com amostra suficiente"
    peso = {}
    for y in range(int(k)):
        taxas = [porc[c].get(y, 0) / nc[c] for c in ctxs]
        mu = sum(taxas) / len(taxas)
        if mu <= 0:
            continue
        var = sum((t - mu) ** 2 for t in taxas) / len(taxas)
        # dispersão esperada só por amostragem
        esp = mu * (1 - mu) / (sum(nc[c] for c in ctxs) / len(ctxs))
        if esp > 0 and var / esp > 2.0:
            peso[y] = max(taxas) / mu
    return _norm(peso), (f"{len(peso)} com comportamento dependente de contexto"
                         if peso else "nenhuma classe muda com o contexto")


def f43(s, k, ctx):
    """F43 · Não comutatividade da ordem contextual.

        Δ_order = ‖A·B - B·A‖

    A ordem em que dois contextos aparecem importa? Compara o que vem depois
    de (a→b) com o que vem depois de (b→a). Se a diferença é grande, a ordem
    carrega informação que a contagem de pares joga fora.
    """
    if len(s) < 200:
        return {}, "amostra curta para ordem contextual (200+)"
    def g(x):
        return POS[x] // 9 if x in POS and _tem_roda(k) else (x % 4)
    ab = Counter()
    ba = Counter()
    n_ab = n_ba = 0
    for i in range(len(s) - 3):
        g1, g2 = g(s[i + 2]), g(s[i + 1])
        if g1 == g2:
            continue
        if g1 < g2:
            ab[s[i]] += 1
            n_ab += 1
        else:
            ba[s[i]] += 1
            n_ba += 1
    if n_ab < 20 or n_ba < 20:
        return {}, f"poucas ordens observadas ({n_ab}/{n_ba})"
    peso = {}
    for x in range(int(k)):
        d = ab.get(x, 0) / n_ab - ba.get(x, 0) / n_ba
        if d > 0:
            peso[x] = d
    delta = sum(abs(ab.get(x, 0) / n_ab - ba.get(x, 0) / n_ba)
                for x in range(int(k)))
    if delta < 0.10:
        return {}, f"Δ_order={delta:.3f} — a ordem não muda o resultado"
    return _norm(peso), f"Δ_order={delta:.3f} — a ordem carrega informação"


def f44(s, k, ctx):
    """F44 · Estado de densidade das hipóteses.

        ρ = Σ_k w_k |ψ_k⟩⟨ψ_k| ;  S = -Tr(ρ log ρ)

    Precisa das outras leituras como estados, e da entropia de von Neumann da
    mistura. Como ela opera sobre o painel e não sobre a mesa, vive na
    agregação -- aqui ficaria sem o que ler.
    """
    return {}, "opera sobre o painel, não sobre a mesa (ver agregação)"


# ═══════════════════════════════════════════════════════ o painel das 44
LEITURAS: Tuple = (
    ("F01", f01), ("F02", f02), ("F03", f03), ("F04", f04),
    ("F05", f05), ("F06", f06), ("F07", f07), ("F08", f08),
    ("F09", f09), ("F10", f10), ("F11", f11), ("F12", f12),
    ("F13", f13), ("F14", f14), ("F15", f15), ("F16", f16),
    ("F17", f17), ("F18", f18), ("F19", f19), ("F20", f20),
    ("F21", f21), ("F22", f22), ("F23", f23), ("F24", f24),
    ("F25", f25), ("F26", f26), ("F27", f27), ("F28", f28),
    ("F29", f29), ("F30", f30), ("F31", f31), ("F32", f32),
    ("F33", f33), ("F34", f34), ("F35", f35), ("F36", f36),
    ("F37", f37), ("F38", f38), ("F39", f39), ("F40", f40),
    ("F41", f41), ("F42", f42), ("F43", f43), ("F44", f44),
)

# As que declaradamente ainda não executam, e por quê. Dívida assumida, não
# omissão: o painel mostra a conta e ele vê quanto do livro já está no ar.
PENDENTES = {
    "F30": "homologia persistente",
    "F32": "decomposição espectral",
    "F40": "cópula sem amostra suficiente",
}
# As que não apontam classe por natureza -- medem a confiança das outras.
NAO_APONTAM = {"F35", "F36", "F39", "F44"}


def executar(seq, n_classes: int = 37, ctx: Optional[Dict[str, Any]] = None,
             k: int = 12) -> Dict[str, Any]:
    """As 44 leituras. Devolve palpite, peso e fala de cada uma."""
    s = _ints(seq)
    ctx = ctx or {}
    palpites: Dict[str, List[str]] = {}
    pesos: Dict[str, Dict[str, float]] = {}
    falas: Dict[str, str] = {}
    for nome, fn in LEITURAS:
        try:
            peso, fala = fn(s, int(n_classes), ctx)
        except Exception as e:
            peso, fala = {}, f"erro: {type(e).__name__}"
        falas[nome] = fala
        if peso:
            pesos[nome] = peso
            ranking = sorted(peso.items(), key=lambda t: (-t[1], str(t[0])))
            palpites[nome] = [str(c) for c, v in ranking if v > 0][:k]
    return {
        "palpites": palpites, "pesos": pesos, "falas": falas,
        "apontaram": len(palpites), "total": len(LEITURAS),
        "pendentes": sorted(PENDENTES), "nao_apontam": sorted(NAO_APONTAM),
    }
