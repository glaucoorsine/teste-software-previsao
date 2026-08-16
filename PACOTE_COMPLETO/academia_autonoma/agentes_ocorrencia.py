# -*- coding: utf-8 -*-
"""
CAÇADORES DE OCORRÊNCIA — doze agentes de análise condicional.

O que eles fazem, em uma frase: olham o histórico REAL e perguntam "dado que
aconteceu X, a chance de Y muda?". É o que em estatística se chama *estudo de
evento* — marcar as ocorrências de uma coisa e olhar a janela em volta.

Diferente dos 12 agentes de familiaridade (que escrevem regras na DSL), estes
não propõem teoria: eles varrem ATRIBUTOS do resultado (final, dúzia, coluna,
cor, setor da roda, salto, espelho…) procurando aglomeração, persistência ou
alternância — e entregam números candidatos.

    O01 SUCESSOR    o que historicamente vem depois do número que acabou de sair
    O02 FINAIS      finais que puxam finais (a percepção do usuário)
    O03 DUZIA       dúzia persiste ou alterna
    O04 COLUNA      idem para colunas
    O05 COR         vermelho/preto em blocos
    O06 PARIDADE    par/ímpar em blocos
    O07 SETOR       setor da roda FÍSICA aglomerando
    O08 SALTO       distância na roda entre giros se repetindo (assinatura)
    O09 ESPELHO     12/21, 13/31 — números espelhados se chamando
    O10 RETORNO     intervalo com que um número volta
    O11 PAR_ORDENADO segunda ordem: depois de (X,Y) tende a vir Z
    O12 VIZINHOS    vizinhos físicos do último número

A RÉGUA DO ACASO
----------------
Toda medição é feita nos SEUS resultados reais. A régua serve só para julgar:
os mesmos números são reordenados numa cópia à parte, muitas vezes, para
responder "se não houvesse ordem nenhuma, quanto isso daria?".

O palpite sai sempre do dado real. A cópia reordenada nunca produz número —
ela só decide se o achado fica ou é descartado como coincidência.

Isso é o que separa achado de alucinação. Sem essa régua, qualquer varredura
de 12 atributos em 300 giros devolve meia dúzia de "padrões" que somem no dia
seguinte.

E como são muitos testes ao mesmo tempo (12 agentes × vários atributos cada),
no fim entra o controle de Benjamini-Hochberg — o mesmo que a academia já usa —
para que a quantidade de perguntas não fabrique respostas.
"""
from __future__ import annotations
import random
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Tuple

# Fundo da régua. Precisa ser grande: o menor p possível é 1/(N+1), e o FDR
# sobre ~50 perguntas exige p<=alpha/50. Com N=200 o piso era 0,005 e a barra
# 0,0019 — nada podia passar NUNCA (o mesmo bug do piso de permutação que já
# tinha aparecido no crítico). Triagem barata primeiro, fundo só em quem sobra.
N_REGUA = 300          # triagem
N_REGUA_FINA = 4000    # só para quem passa da triagem
MIN_OCORRENCIAS = 8    # abaixo disso não se mede nada
FDR_ALPHA = 0.10
JANELA = 5             # giros à frente considerados "logo depois"

VERMELHOS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
RODA = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,
        5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
POS = {n: i for i, n in enumerate(RODA)}


# ---------------------------------------------------------------- utilidades
def _ints(seq) -> List[int]:
    out = []
    for x in seq:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out


def _duzia(n): return -1 if n == 0 else (n - 1) // 12
def _coluna(n): return -1 if n == 0 else (n - 1) % 3
def _cor(n): return "V" if n in VERMELHOS else ("P" if n else "Z")
def _par(n): return "Z" if n == 0 else ("P" if n % 2 == 0 else "I")
def _setor(n): return POS.get(n, -1) // 5
def _final(n): return n % 10


def _espelho(n: int) -> Optional[int]:
    """12<->21, 13<->31… só para dois dígitos com dígitos diferentes."""
    if n < 10 or n % 10 == n // 10:
        return None
    e = (n % 10) * 10 + n // 10
    return e if 0 <= e <= 36 else None


def _taxa_condicional(seq: List[int], marca: Callable[[int], Any],
                      alvo: Any, lag: int = 1) -> Tuple[int, int]:
    """
    Taxa no giro a `lag` distâncias depois de cada ocorrência de `alvo`.

    Mede UMA distância por vez, de propósito. Antes eu somava os 5 giros
    seguintes num número só — e um efeito que age apenas no giro imediatamente
    posterior ficava dividido por cinco, encolhendo até sumir. Medido: o
    detector pegava um vício plantado de 55% em apenas 16% dos mundos.
    Separando por distância, cada lag é uma pergunta limpa (e o FDR no fim
    cobra pelas perguntas a mais).
    """
    h = t = 0
    for i, x in enumerate(seq[:-lag]):
        if marca(x) != alvo:
            continue
        y = seq[i + lag]
        t += 1
        if marca(y) == alvo:
            h += 1
    return h, t


# ---------------------------------------------------------------- os doze
def _agente_atributo(nome: str, desc: str, marca: Callable[[int], Any],
                     nums_do_grupo: Callable[[Any], List[int]]):
    """Fábrica: agentes que medem aglomeração de um atributo qualquer."""
    def rodar(seq: List[int]) -> List[dict]:
        achados = []
        grupos = Counter(marca(x) for x in seq)
        base_total = len(seq)
        for g, q in grupos.items():
            if q < MIN_OCORRENCIAS or g in (-1, "Z"):
                continue
            base = q / base_total
            for lag in range(1, JANELA + 1):
                h, t = _taxa_condicional(seq, marca, g, lag=lag)
                if t < MIN_OCORRENCIAS:
                    continue
                achados.append({
                    "agente": nome, "atributo": f"{g}@{lag}",
                    "descricao": f"{desc} {g} — {lag} giro(s) depois",
                    "medida": h / t, "base": base,
                    "n": t, "alvos": nums_do_grupo(g), "lag": lag,
                })
        return achados
    rodar.__name__ = f"rodar_{nome}"
    return rodar


# ---- regiões FÍSICAS da roda -------------------------------------------
# As três famílias clássicas: setores contíguos do cilindro. É onde jogador
# procura roda viciada há um século, e é onde um defeito físico se manifesta.
VOISINS = {22,18,29,7,28,12,35,3,26,0,32,15,19,4,21,2,25}   # 17
TIERS   = {27,13,36,11,30,8,23,10,5,24,16,33}               # 12
ORPHELINS = {17,34,6,1,20,14,31,9}                          # 8

def _familia_roda(n):
    if n in VOISINS: return "VOISINS"
    if n in TIERS: return "TIERS"
    if n in ORPHELINS: return "ORPHELINS"
    return "?"

def _alto_baixo(n): return "Z" if n == 0 else ("BAIXO" if n <= 18 else "ALTO")
def _sexto(n): return -1 if n == 0 else (n - 1) // 6
def _quadra(n):
    """Carré da mesa: blocos de 4 na grade 3x12."""
    if n == 0: return -1
    l, c = (n - 1) // 3, (n - 1) % 3
    return (l // 2) * 2 + (0 if c < 2 else 1)

# ---- CANÁRIOS ------------------------------------------------------------
# Atributos SEM mecanismo físico possível: a roda não sabe o que é um número
# primo. Eles não existem para achar vício — existem para denunciar quando o
# detector está produzindo falso positivo. Se um canário "aglomera", a leitura
# daquele ciclo inteira é suspeita.
PRIMOS = {2,3,5,7,11,13,17,19,23,29,31}
def _primo(n): return "PRIMO" if n in PRIMOS else "NAO"
def _soma_digitos(n): return sum(int(d) for d in str(n))
def _mult3(n): return "M3" if n and n % 3 == 0 else "NAO"

CANARIOS = {"C90_PRIMO", "C91_SOMA_DIG", "C92_MULT3"}


O02 = _agente_atributo("O02_FINAIS", "final", _final,
                       lambda g: [n for n in range(37) if _final(n) == g])
O03 = _agente_atributo("O03_DUZIA", "dúzia", _duzia,
                       lambda g: [n for n in range(1, 37) if _duzia(n) == g])
O04 = _agente_atributo("O04_COLUNA", "coluna", _coluna,
                       lambda g: [n for n in range(1, 37) if _coluna(n) == g])
O05 = _agente_atributo("O05_COR", "cor", _cor,
                       lambda g: [n for n in range(1, 37) if _cor(n) == g])
O06 = _agente_atributo("O06_PARIDADE", "paridade", _par,
                       lambda g: [n for n in range(1, 37) if _par(n) == g])
O07 = _agente_atributo("O07_SETOR", "setor da roda", _setor,
                       lambda g: [n for n in range(37) if _setor(n) == g])
O15 = _agente_atributo("O15_FAMILIA_RODA", "família da roda", _familia_roda,
                       lambda g: [n for n in range(37) if _familia_roda(n) == g])
O16 = _agente_atributo("O16_ALTO_BAIXO", "metade", _alto_baixo,
                       lambda g: [n for n in range(1,37) if _alto_baixo(n) == g])
O17 = _agente_atributo("O17_SEXTO", "sexto", _sexto,
                       lambda g: [n for n in range(1,37) if _sexto(n) == g])
O18 = _agente_atributo("O18_QUADRA", "quadra da mesa", _quadra,
                       lambda g: [n for n in range(1,37) if _quadra(n) == g])
C90 = _agente_atributo("C90_PRIMO", "[canário] primo", _primo,
                       lambda g: [n for n in range(1,37) if _primo(n) == g])
C91 = _agente_atributo("C91_SOMA_DIG", "[canário] soma dos dígitos", _soma_digitos,
                       lambda g: [n for n in range(37) if _soma_digitos(n) == g])
C92 = _agente_atributo("C92_MULT3", "[canário] múltiplo de 3", _mult3,
                       lambda g: [n for n in range(1,37) if _mult3(n) == g])


def O01_sucessor(seq: List[int]) -> List[dict]:
    """O que historicamente vem depois de cada número."""
    achados = []
    depois = defaultdict(Counter)
    ocor = Counter()
    for a, b in zip(seq, seq[1:]):
        depois[a][b] += 1
        ocor[a] += 1
    for x, cnt in depois.items():
        if ocor[x] < MIN_OCORRENCIAS:
            continue
        top = cnt.most_common(3)
        alvos = [n for n, _ in top]
        h = sum(q for _, q in top)
        achados.append({
            "agente": "O01_SUCESSOR", "atributo": str(x),
            "descricao": f"depois do {x} costuma vir {alvos}",
            "medida": h / ocor[x], "base": 3 / 37,
            "n": ocor[x], "alvos": alvos, "gatilho": x,
        })
    return achados


def O08_salto(seq: List[int]) -> List[dict]:
    """Distância na roda entre giros consecutivos — assinatura de lançamento."""
    saltos = []
    for a, b in zip(seq, seq[1:]):
        if a in POS and b in POS:
            saltos.append((POS[b] - POS[a]) % 37)
    if len(saltos) < MIN_OCORRENCIAS:
        return []
    c = Counter(saltos)
    achados = []
    for d, q in c.most_common(4):
        if q < MIN_OCORRENCIAS:
            continue
        ult = seq[0] if seq else None
        alvos = []
        if ult in POS:
            alvos = [RODA[(POS[ult] + d) % 37]]
        achados.append({
            "agente": "O08_SALTO", "atributo": str(d),
            "descricao": f"salto de {d} casas na roda",
            "medida": q / len(saltos), "base": 1 / 37,
            "n": len(saltos), "alvos": alvos,
        })
    return achados


def O09_espelho(seq: List[int]) -> List[dict]:
    """Números espelhados (12/21) se chamando dentro da janela."""
    h = t = 0
    for i, x in enumerate(seq[:-1]):
        e = _espelho(x)
        if e is None:
            continue
        t += 1
        if e in seq[i+1:i+1+JANELA]:
            h += 1
    if t < MIN_OCORRENCIAS:
        return []
    ult = seq[0] if seq else None
    alvos = [e for e in [_espelho(ult)] if e is not None]
    return [{
        "agente": "O09_ESPELHO", "atributo": "espelho",
        "descricao": "número espelhado volta em até 5 giros",
        "medida": h / t, "base": 1 - (1 - 1/37) ** JANELA,
        "n": t, "alvos": alvos,
    }]


def O10_retorno(seq: List[int]) -> List[dict]:
    """Com que frequência um número repete dentro da janela."""
    h = t = 0
    for i, x in enumerate(seq[:-1]):
        t += 1
        if x in seq[i+1:i+1+JANELA]:
            h += 1
    if t < MIN_OCORRENCIAS:
        return []
    return [{
        "agente": "O10_RETORNO", "atributo": "repete",
        "descricao": "número repete em até 5 giros",
        "medida": h / t, "base": 1 - (1 - 1/37) ** JANELA,
        "n": t, "alvos": list(dict.fromkeys(seq[:3])),
    }]


def O11_par_ordenado(seq: List[int]) -> List[dict]:
    """Segunda ordem: depois do par (X,Y) tende a vir Z."""
    seg = defaultdict(Counter)
    ocor = Counter()
    for a, b, c in zip(seq, seq[1:], seq[2:]):
        seg[(a, b)][c] += 1
        ocor[(a, b)] += 1
    achados = []
    for par, cnt in seg.items():
        if ocor[par] < MIN_OCORRENCIAS:
            continue
        top = cnt.most_common(2)
        achados.append({
            "agente": "O11_PAR_ORDENADO", "atributo": f"{par[0]},{par[1]}",
            "descricao": f"depois de ({par[0]},{par[1]}) vem {[n for n,_ in top]}",
            "medida": sum(q for _, q in top) / ocor[par], "base": 2 / 37,
            "n": ocor[par], "alvos": [n for n, _ in top], "gatilho_par": par,
        })
    return achados


def O12_vizinhos(seq: List[int]) -> List[dict]:
    """O próximo cai perto do anterior na roda física?"""
    h = t = 0
    for a, b in zip(seq, seq[1:]):
        if a in POS and b in POS:
            t += 1
            d = (POS[b] - POS[a]) % 37
            if min(d, 37 - d) <= 2:
                h += 1
    if t < MIN_OCORRENCIAS:
        return []
    ult = seq[0] if seq else None
    alvos = []
    if ult in POS:
        p = POS[ult]
        alvos = [RODA[(p + d) % 37] for d in (-2, -1, 1, 2)]
    return [{
        "agente": "O12_VIZINHOS", "atributo": "vizinhanca",
        "descricao": "próximo cai a até 2 casas do anterior",
        "medida": h / t, "base": 5 / 37,
        "n": t, "alvos": alvos,
    }]


def _marginais(seq: List[int]) -> List[dict]:
    """
    Viés de roda: números/setores que saem mais NO TOTAL, não em sequência.

    Este é o vício fisicamente mais plausível — roda desnivelada, fret gasto —
    e a régua do embaralhamento é CEGA para ele: reordenar preserva quantas
    vezes cada número saiu. Aqui a régua certa é a uniforme (1/37), avaliada
    por binomial exata; não usa reordenação nenhuma.
    """
    from math import comb, lgamma, exp, log
    n = len(seq)
    if n < 60:
        return []

    def p_ge(h, tot, p):
        if p <= 0 or p >= 1:
            return 1.0
        return sum(exp(lgamma(tot+1)-lgamma(k+1)-lgamma(tot-k+1)
                       + k*log(p) + (tot-k)*log(1-p))
                   for k in range(h, tot+1))

    out = []
    # números individuais
    c = Counter(seq)
    for num, q in c.most_common(6):
        out.append({
            "agente": "O13_VIES_NUMERO", "atributo": str(num),
            "descricao": f"número {num} sai mais que o normal",
            "medida": q / n, "base": 1/37, "n": n,
            "alvos": [num], "p_direto": p_ge(q, n, 1/37),
        })
    # famílias da roda — onde um defeito físico realmente aparece
    fam = Counter(_familia_roda(x) for x in seq)
    for f_, q in fam.items():
        if f_ == "?":
            continue
        nums = [x for x in range(37) if _familia_roda(x) == f_]
        base = len(nums) / 37
        out.append({
            "agente": "O19_VIES_FAMILIA", "atributo": f_,
            "descricao": f"{f_} sai mais que o normal",
            "medida": q / n, "base": base, "n": n,
            "alvos": nums, "p_direto": p_ge(q, n, base),
        })
    # setores da roda
    sec = Counter(_setor(x) for x in seq if x in POS)
    for s_, q in sec.most_common(3):
        if s_ < 0:
            continue
        nums = [x for x in range(37) if _setor(x) == s_]
        base = len(nums) / 37
        out.append({
            "agente": "O14_VIES_SETOR", "atributo": str(s_),
            "descricao": f"setor {s_} da roda sai mais que o normal",
            "medida": q / n, "base": base, "n": n,
            "alvos": nums, "p_direto": p_ge(q, n, base),
        })
    return out



# ---------------------------------------------------------------- O20
def O20_rajada(seq: List[int]) -> List[dict]:
    """
    RAJADA — a percepção de "bate duas vezes no mesmo lugar, passa duas
    rodadas, e aí bate cinco vezes seguidas ali".

    Isso NÃO é viés de média: no total o lugar pode sair a taxa normal. O que
    muda é a DISTRIBUIÇÃO no tempo — os acertos vêm em rajadas em vez de
    espalhados. A estatística disso chama-se sobredispersão: a variância das
    contagens por janela fica acima do que o acaso produziria.

    Nenhum dos outros agentes enxerga isso. Eles olham a taxa; este olha o
    agrupamento dela no tempo.
    """
    if len(seq) < 60:
        return []
    JAN = 12
    achados = []
    for nome, marca, nums_de in (
        ("família da roda", _familia_roda,
         lambda g: [n for n in range(37) if _familia_roda(n) == g]),
        ("setor", _setor, lambda g: [n for n in range(37) if _setor(n) == g]),
        ("dúzia", _duzia, lambda g: [n for n in range(1, 37) if _duzia(n) == g]),
    ):
        grupos = Counter(marca(x) for x in seq)
        for g, q in grupos.items():
            if g in (-1, "?", "Z") or q < MIN_OCORRENCIAS:
                continue
            janelas = [seq[i:i+JAN] for i in range(0, len(seq) - JAN + 1, JAN)]
            if len(janelas) < 5:
                continue
            cont = [sum(1 for x in j if marca(x) == g) for j in janelas]
            media = sum(cont) / len(cont)
            if media <= 0:
                continue
            var = sum((c - media) ** 2 for c in cont) / len(cont)
            # sob acaso, contagem por janela ~ binomial: var = m*(1 - p)
            p = q / len(seq)
            var_esperada = media * (1 - p)
            if var_esperada <= 0:
                continue
            achados.append({
                "agente": "O20_RAJADA", "atributo": f"{nome}:{g}",
                "descricao": f"{nome} {g} sai em rajadas, não espalhado",
                "medida": var / var_esperada, "base": 1.0,
                "n": len(janelas), "alvos": nums_de(g),
            })
    return achados


# ---------------------------------------------------------------- O21
def _p_alguma_recorrencia(n: int, N: int, q: int) -> float:
    """P(ALGUM dos N padrões possíveis aparecer >= q vezes em n amostras).

    ESTA CONTA JÁ ESTEVE ERRADA, E O ERRO CUSTAVA CARO
    --------------------------------------------------
    Aqui morava um falso positivo de 62% em roleta limpa — os caçadores
    "achavam" vício em três de cada cinco roletas honestas. O motivo é o
    paradoxo do aniversário, e ele é traiçoeiro porque a conta antiga PARECIA
    corrigida: ela pegava P(esta trinca específica sair 2x) e multiplicava
    pelas ~298 trincas vistas, dando 0,005 — abaixo de qualquer limiar.

    Mas a pergunta certa nunca foi "qual a chance desta trinca repetir". Foi
    "qual a chance de ALGUMA das 298 repetir", e o que conta aí não são as 298
    trincas: são os 44.253 PARES delas que poderiam colidir. Em 300 giros isso
    dá 58% — quase exatamente os 62% que o teste media.

    Uma trinca repetida em 300 giros é o esperado, não a descoberta. Três
    repetições da mesma trinca (λ cai para 0,0017) é que seria notícia.
    """
    from math import exp, lgamma, log
    if q < 2 or n < q or N < 2:
        return 1.0
    try:
        # esperado de padrões distintos que aparecem >= q vezes:
        #   λ = N · C(n, q) · (1/N)^q
        log_comb = lgamma(n + 1) - lgamma(q + 1) - lgamma(n - q + 1)
        log_lam = log(N) + log_comb - q * log(N)
        if log_lam > 700:
            return 1.0
        lam = exp(log_lam)
    except ValueError:
        return 1.0
    return 1.0 - exp(-lam)


def O21_anomalia_recorrente(seq: List[int]) -> List[dict]:
    """
    O ABSURDO QUE VOLTA.

    A ideia do usuário: às vezes acontece algo que "não tem sentido nenhum" —
    e o que interessa não é a esquisitice em si, é ela REAPARECER.

    Uma coisa rara acontecer uma vez não diz nada; o improvável acontece o
    tempo todo, é só ter eventos suficientes. Mas uma configuração cuja chance
    é 1 em 500 aparecer três vezes em 300 giros é outra história.

    Aqui as configurações são trincas exatas (X,Y,Z) e saltos repetidos na
    roda. Cada uma tem probabilidade minúscula; o agente conta as recorrências
    e cobra contra essa probabilidade.
    """
    if len(seq) < 80:
        return []
    from math import exp, lgamma, log
    achados = []

    trincas = Counter(tuple(seq[i:i+3]) for i in range(len(seq) - 2))
    n_tri = len(seq) - 2
    p_tri = 1 / (37 ** 3)
    for tr, q in trincas.most_common(3):
        if q < 2:
            continue
        # P(ALGUMA trinca repetir q vezes) — não P(esta trinca repetir.
        # A diferença entre as duas é o falso positivo de 62% documentado em
        # `_p_alguma_recorrencia`.
        esperado = n_tri * p_tri
        p_bruto = _p_alguma_recorrencia(n_tri, 37 ** 3, q)
        achados.append({
            "agente": "O21_ANOMALIA", "atributo": f"trinca_{tr[0]}_{tr[1]}_{tr[2]}",
            "descricao": f"a trinca exata {tr} apareceu {q}x",
            "medida": q / max(esperado, 1e-9), "base": 1.0,
            "n": n_tri, "alvos": [tr[2]], "p_direto": p_bruto,
        })

    saltos = [(POS[b] - POS[a]) % 37
              for a, b in zip(seq, seq[1:]) if a in POS and b in POS]
    trios_salto = Counter(tuple(saltos[i:i+2]) for i in range(len(saltos) - 1))
    for par, q in trios_salto.most_common(2):
        if q < 4:
            continue
        esperado = len(saltos) / (37 ** 2)
        ult = seq[-1] if seq else None
        alvos = [RODA[(POS[ult] + par[0]) % 37]] if ult in POS else []
        achados.append({
            "agente": "O21_ANOMALIA", "atributo": f"saltos_{par[0]}_{par[1]}",
            "descricao": f"a dupla de saltos {par} repetiu {q}x",
            "medida": q / max(esperado, 1e-9), "base": 1.0,
            "n": len(saltos), "alvos": alvos,
            # mesma correção das trincas: o que interessa é ALGUMA dupla
            # repetir, e são 1369 duplas possíveis
            "p_direto": _p_alguma_recorrencia(len(saltos), 37 ** 2, q),
        })
    return achados

# ------------------------------------------------- O02F: as famílias DELE
# A TEORIA DELE ESTAVA FALTANDO NA VARREDURA.
#
# O O02 mede um final de cada vez: depois do final 4, vem final 4? Mas o que ele
# ensinou não é isso — é FAMÍLIA: 0-1-3-6, 0-2-7-8, 4-5-9. "Veio 16 e logo
# depois 14", "veio 20 e logo depois o 2", "veio 1 e logo depois 21".
#
# A diferença não é de nome, é de potência. Um vício de família espalhado em
# três dígitos chega ao O02 partido em três, com um terço das ocorrências em
# cada — e três medições fracas morrem no controle de múltiplos testes, onde uma
# medição forte sobreviveria. Medido no teste com vício plantado de 55%: o O02
# sozinho pegava em 8% dos mundos.
#
# Este agente pergunta a coisa inteira. É a hipótese dele, escrita como
# hipótese, entrando na varredura em igualdade com as outras — e passando pela
# mesma régua de permutação e pelo mesmo FDR que todas.
FAMILIAS_FINAL = ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9))


def _fam_final(n):
    """A que família de final este número pertence. O zero pertence a duas."""
    f = _final(n)
    return tuple(i for i, fam in enumerate(FAMILIAS_FINAL) if f in fam)


def O02F_familia_final(seq: List[int]) -> List[dict]:
    achados = []
    if len(seq) < 40:
        return achados
    for i, fam in enumerate(FAMILIAS_FINAL):
        nums = [n for n in range(37) if _final(n) in fam]
        alvo = set(nums)
        na_fam = [x in alvo for x in seq]
        q = sum(na_fam)
        if q < MIN_OCORRENCIAS:
            continue
        base = q / len(seq)
        rotulo = "-".join(str(d) for d in fam)
        for lag in range(1, JANELA + 1):
            h = t = 0
            for j in range(len(seq) - lag):
                if na_fam[j]:
                    t += 1
                    if na_fam[j + lag]:
                        h += 1
            if t < MIN_OCORRENCIAS:
                continue
            achados.append({
                "agente": "O02F_FAMILIA_FINAL", "atributo": f"{rotulo}@{lag}",
                "descricao": f"família de final {rotulo} — {lag} giro(s) depois",
                "medida": h / t, "base": base,
                "n": t, "alvos": nums, "lag": lag,
            })
    return achados


AGENTES: List[Callable[[List[int]], List[dict]]] = [
    O02F_familia_final,          # as famílias de final que ele ensinou
    O01_sucessor, O02, O03, O04, O05, O06, O07,
    O08_salto, O09_espelho, O10_retorno, O11_par_ordenado, O12_vizinhos,
    O15, O16, O17, O18,          # regiões da roda e agrupamentos de mesa
    C90, C91, C92,               # canários — ver comentário em CANARIOS
    O20_rajada,                  # concentração no tempo (sobredispersão)
    O21_anomalia_recorrente,     # o improvável que volta
]


# ---------------------------------------------------------------- a régua
# ACHADOS QUE SÃO "O MAIS EXTREMO DE UMA FAMÍLIA GRANDE".
#
# O O21 não testa uma hipótese: ele varre 298 trincas e reporta a que mais
# repetiu. Isso muda o que a régua tem que perguntar.
#
# Comparando pela chave específica — `trinca_11_0_0` — a régua pergunta "nos
# embaralhamentos, ESTA trinca repete tanto assim?". Quase nunca repete, o p sai
# 0,005 e o achado passa. Só que em TODO embaralhamento alguma trinca repete;
# a que foi escolhida no dado real foi escolhida DEPOIS de olhar, e comparar uma
# escolha posterior contra uma fixa é comparar coisas diferentes.
#
# Medido: 62% de falso positivo em roleta limpa — três de cada cinco roletas
# honestas ganhavam "achado". Agrupando a família, a régua passa a comparar o
# máximo do dado real contra o MÁXIMO de cada embaralhamento, que é a pergunta
# certa, e o acaso volta a ser o que é.
FAMILIA_MAXIMO = {"O21_ANOMALIA"}


def _chave(a: dict) -> str:
    ag = a.get("agente")
    if ag in FAMILIA_MAXIMO:
        # só o TIPO (trinca / saltos), não o valor sorteado
        tipo = str(a.get("atributo", "")).split("_")[0]
        return f"{ag}|{tipo}"
    return f"{ag}|{a['atributo']}"



# ================================================================= CRAZY TIME
# A roda do Crazy Time nao e uma roleta: sao 54 fatias com 8 simbolos de
# frequencias MUITO desiguais (o "1" ocupa 21 fatias; o CrazyBonus, 1). Setor,
# Voisins, final, duzia — nada disso existe aqui.
#
# Antes, `_ints()` descartava CoinFlip/CashHunt/Pachinko/CrazyBonus e sobrava
# uma sequencia mutilada de 1/2/5/10 que os agentes de roleta interpretavam
# como numeros. Resultado medido: 48 "achados" em 179 perguntas — lixo puro.
CT_FATIAS = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2, "CrazyBonus": 1}
CT_TOTAL = 54
CT_BONUS = {"CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"}


def _ct_simbolos(seq) -> List[str]:
    return [str(x) for x in (seq or []) if str(x) in CT_FATIAS]



# ---------------------------------------------------------------- O22
def O22_fora_do_padrao(seq: List[int], previsoes: Optional[List[dict]] = None) -> List[dict]:
    """
    O QUE VEM QUANDO TUDO APONTAVA PARA OUTRO LUGAR.

    A observação do usuário: às vezes todos os padrões apontam para 30, 24, e
    sai um 1 — um número que ninguém cogitaria. Ele suspeita de direcionamento;
    seja qual for a causa, o que interessa aqui é se ESSAS saídas têm estrutura.

    Medido nos dados reais do usuário, a implicação mais direta da hipótese de
    direcionamento NÃO se confirmou: o resultado cai nos números previstos um
    pouco MAIS que o acaso (18,6% vs 13,8% no mega_fire), não menos. Se houvesse
    fuga sistemática do previsível, a taxa ficaria abaixo do acaso.

    Mas resta a pergunta que ninguém estava guardando: quando o palpite falha,
    o que vem no lugar tem padrão? Três coisas são medidas aqui:

      1. os "surpresas" se repetem? (poucos números concentrando as falhas)
      2. eles ficam LONGE na roda do que foi previsto? (deslocamento sistemático)
      3. eles são justamente os mais frios? (o que ninguém aposta)

    `previsoes` é a lista de {alvos, saiu} registrada pelo motor. Sem ela o
    agente não tem o que medir e fica calado — ele depende de o software estar
    guardando as previsões, não só os giros.
    """
    if not previsoes:
        return []
    erros = [p for p in previsoes
             if p.get("alvos") and str(p.get("saiu")) not in [str(a) for a in p["alvos"]]]
    if len(erros) < 15:
        return []

    achados = []
    n_err = len(erros)

    # 1) as surpresas se concentram em poucos números?
    #
    # Limiar chutado ("q >= 3") canta em ruído: com 49 erros, ver um número 5x
    # é comum. Aqui vai binomial exata, corrigida por termos olhado os 37
    # candidatos e escolhido o maior — sem isso o agente vira gerador de
    # falso positivo, que é o oposto do que ele existe para fazer.
    from math import exp, lgamma, log
    def _p_ge(h, tot, pr):
        if pr <= 0 or pr >= 1 or tot <= 0:
            return 1.0
        return sum(exp(lgamma(tot+1)-lgamma(k+1)-lgamma(tot-k+1)
                       + k*log(pr) + (tot-k)*log(1-pr)) for k in range(h, tot+1))

    quem = Counter(int(p["saiu"]) for p in erros if str(p["saiu"]).lstrip("-").isdigit())
    if quem:
        top, q = quem.most_common(1)[0]
        p_um = _p_ge(q, n_err, 1/37)
        p_corr = min(1.0, p_um * 37)          # olhamos 37 e pegamos o maior
        achados.append({
            "agente": "O22_SURPRESA", "atributo": f"num_{top}",
            "descricao": f"o {top} é quem mais aparece quando o palpite falha ({q}x)",
            "medida": q / n_err, "base": 1 / 37, "n": n_err, "alvos": [top],
            "p_direto": p_corr,
        })

    # 2) distância na roda entre o previsto e o que veio
    dists = []
    for p in erros:
        try:
            saiu = int(p["saiu"])
        except (TypeError, ValueError):
            continue
        if saiu not in POS:
            continue
        ds = [min((POS[saiu] - POS[int(a)]) % 37, (POS[int(a)] - POS[saiu]) % 37)
              for a in p["alvos"] if int(a) in POS]
        if ds:
            dists.append(min(ds))
    if len(dists) >= 15:
        media = sum(dists) / len(dists)
        # sob acaso, a menor distância a k alvos espalhados fica em torno de 37/(2(k+1))
        k_med = sum(len(p["alvos"]) for p in erros) / n_err
        esperada = 37 / (2 * (k_med + 1))
        achados.append({
            "agente": "O22_DISTANCIA", "atributo": "afastamento",
            "descricao": (f"quando erra, o número sai a {media:.1f} casas do "
                          f"previsto (esperado {esperada:.1f})"),
            "medida": media, "base": esperada, "n": len(dists),
            "alvos": [],
        })

    # 3) as surpresas são os números mais frios?
    freq_geral = Counter(seq)
    frios = {n for n, _ in sorted(freq_geral.items(), key=lambda kv: kv[1])[:12]}
    q_frio = sum(1 for p in erros
                 if str(p["saiu"]).lstrip("-").isdigit() and int(p["saiu"]) in frios)
    if n_err >= 20:
        achados.append({
            "agente": "O22_FRIOS", "atributo": "frios",
            "descricao": f"{q_frio} de {n_err} surpresas caíram nos 12 números mais frios",
            "medida": q_frio / n_err, "base": 12 / 37, "n": n_err,
            "alvos": sorted(frios),
            "p_direto": _p_ge(q_frio, n_err, 12/37),
        })
    return achados


def _cacar_ct(simbolos: List[str], n_regua: int, alpha: float, seed: int) -> Dict[str, Any]:
    """Caçadores do Crazy Time. Mesma disciplina, vocabulário próprio."""
    from math import exp, lgamma, log
    n = len(simbolos)
    if n < 40:
        return {"achados": [], "candidatos": [], "erro": "histórico curto",
                "n_perguntas": 0}

    def p_ge(h, tot, p):
        if p <= 0 or p >= 1 or tot <= 0:
            return 1.0
        return sum(exp(lgamma(tot+1)-lgamma(k+1)-lgamma(tot-k+1)
                       + k*log(p) + (tot-k)*log(1-p)) for k in range(h, tot+1))

    def marca_bonus(x): return "BONUS" if x in CT_BONUS else "NUMERO"

    reais: Dict[str, dict] = {}

    # 1) sequência: símbolo puxa símbolo, por distância
    for alvo in CT_FATIAS:
        base = simbolos.count(alvo) / n
        if base <= 0:
            continue
        for lag in range(1, JANELA + 1):
            h = t = 0
            for i, x in enumerate(simbolos[:-lag]):
                if x != alvo:
                    continue
                t += 1
                if simbolos[i + lag] == alvo:
                    h += 1
            if t < MIN_OCORRENCIAS:
                continue
            reais[f"CT_SIMBOLO|{alvo}@{lag}"] = {
                "agente": "CT01_SIMBOLO", "atributo": f"{alvo}@{lag}",
                "descricao": f"{alvo} puxa {alvo} — {lag} giro(s) depois",
                "medida": h / t, "base": base, "n": t, "alvos": [alvo], "lag": lag,
            }

    # 2) bônus chamando bônus (o que o jogador sente como "veio a rodada boa")
    base_b = sum(1 for x in simbolos if marca_bonus(x) == "BONUS") / n
    for lag in range(1, JANELA + 1):
        h = t = 0
        for i, x in enumerate(simbolos[:-lag]):
            if marca_bonus(x) != "BONUS":
                continue
            t += 1
            if marca_bonus(simbolos[i + lag]) == "BONUS":
                h += 1
        if t >= MIN_OCORRENCIAS and base_b > 0:
            reais[f"CT_BONUS|@{lag}"] = {
                "agente": "CT02_BONUS", "atributo": f"bonus@{lag}",
                "descricao": f"bônus puxa bônus — {lag} giro(s) depois",
                "medida": h / t, "base": base_b, "n": t,
                "alvos": sorted(CT_BONUS), "lag": lag,
            }

    # régua de sequência: reordenar
    piores = {k: 0 for k in reais}
    rng = random.Random(seed)
    copia = simbolos[:]
    for _ in range(n_regua):
        rng.shuffle(copia)
        for k, a in reais.items():
            lag = a["lag"]
            if a["agente"] == "CT01_SIMBOLO":
                alvo = a["atributo"].split("@")[0]
                h = t = 0
                for i, x in enumerate(copia[:-lag]):
                    if x != alvo:
                        continue
                    t += 1
                    if copia[i + lag] == alvo:
                        h += 1
            else:
                h = t = 0
                for i, x in enumerate(copia[:-lag]):
                    if marca_bonus(x) != "BONUS":
                        continue
                    t += 1
                    if marca_bonus(copia[i + lag]) == "BONUS":
                        h += 1
            if t and (h / t) >= a["medida"]:
                piores[k] += 1
    for k, a in reais.items():
        a["p"] = (piores[k] + 1) / (n_regua + 1)
        a["razao"] = a["medida"] / a["base"] if a["base"] else None

    # 3) viés de roda: símbolo saindo mais que as fatias dele permitem
    for simb, fatias in CT_FATIAS.items():
        q = simbolos.count(simb)
        base = fatias / CT_TOTAL
        if q < MIN_OCORRENCIAS:
            continue
        reais[f"CT_VIES|{simb}"] = {
            "agente": "CT03_VIES", "atributo": simb,
            "descricao": f"{simb} sai mais do que as {fatias} fatias dele preveem",
            "medida": q / n, "base": base, "n": n, "alvos": [simb],
            "p": p_ge(q, n, base), "razao": (q / n) / base,
        }

    itens = sorted(reais.values(), key=lambda a: a["p"])
    m = len(itens)
    prev = 1.0
    for i in range(m, 0, -1):
        a = itens[i-1]
        a["q"] = round(min(prev, a["p"] * m / i), 5)
        prev = a["q"]
    sobrev = [a for a in itens if a["q"] <= alpha and (a.get("razao") or 0) > 1.0]

    cand: Dict[str, float] = defaultdict(float)
    for a in sobrev:
        for x in a["alvos"]:
            cand[x] += (a["razao"] - 1.0) * (1.0 - a["q"])
    return {
        "achados": sobrev,
        "candidatos": [x for x, _ in sorted(cand.items(), key=lambda kv: -kv[1])][:5],
        "n_perguntas": m, "n_sobreviventes": len(sobrev), "n_giros": n,
    }


def cacar(historico, n_regua: int = N_REGUA, alpha: float = FDR_ALPHA,
          seed: int = 20260813) -> Dict[str, Any]:
    """
    Roda os doze nos SEUS resultados e julga cada achado contra a régua do acaso.

    Devolve os achados que sobrevivem, os números candidatos e um relatório de
    quantas perguntas foram feitas — porque isso importa para julgar as
    respostas.
    """
    # Crazy Time tem vocabulário próprio — mandar símbolo para agente de roleta
    # produz lixo (medido: 48 "achados" em 179 perguntas).
    brutos = [str(x) for x in (historico or [])]
    if brutos and sum(1 for x in brutos if x in CT_BONUS) >= 2:
        return _cacar_ct(_ct_simbolos(brutos), n_regua, alpha, seed)

    seq = _ints(historico)
    if len(seq) < 40:
        return {"achados": [], "candidatos": [], "erro": "histórico curto",
                "n_perguntas": 0}

    # 1) medição no dado REAL — duas famílias, duas réguas
    reais: Dict[str, dict] = {}
    for ag in AGENTES:
        try:
            for a in ag(seq):
                reais[_chave(a)] = a
        except Exception:
            continue
    # viés marginal: régua uniforme, p já sai calculado (sem reordenação)
    marginais: Dict[str, dict] = {}
    try:
        for a in _marginais(seq):
            marginais[_chave(a)] = a
    except Exception:
        pass
    if not reais:
        return {"achados": [], "candidatos": [], "n_perguntas": 0}

    # 2) a régua: mesmos números, ordem desfeita, muitas vezes.
    #    Nada daqui vira palpite — serve só para saber o que o acaso produz.
    piores = {k: 0 for k in reais}
    rng = random.Random(seed)
    copia = seq[:]
    for _ in range(n_regua):
        rng.shuffle(copia)
        for ag in AGENTES:
            try:
                for a in ag(copia):
                    k = _chave(a)
                    if k in reais and a["medida"] >= reais[k]["medida"]:
                        piores[k] += 1
            except Exception:
                continue

    for k, a in reais.items():
        a["p"] = (piores[k] + 1) / (n_regua + 1)
        a["razao"] = (a["medida"] / a["base"]) if a["base"] else None

    # refino: quem passou da triagem recebe régua funda, para o p ter resolução
    # suficiente de sobreviver ao FDR (ver comentário em N_REGUA)
    promissores = [k for k, a in reais.items()
                   if a["p"] <= 0.10 and (a.get("razao") or 0) > 1.0]
    if promissores:
        piores2 = {k: 0 for k in promissores}
        copia = seq[:]
        for _ in range(N_REGUA_FINA):
            rng.shuffle(copia)
            for ag in AGENTES:
                try:
                    for a in ag(copia):
                        k = _chave(a)
                        if k in piores2 and a["medida"] >= reais[k]["medida"]:
                            piores2[k] += 1
                except Exception:
                    continue
        for k in promissores:
            reais[k]["p"] = (piores2[k] + 1) / (N_REGUA_FINA + 1)

    for k, a in marginais.items():
        a["p"] = a.pop("p_direto")
        a["razao"] = (a["medida"] / a["base"]) if a["base"] else None
    reais.update(marginais)

    # 3) Benjamini-Hochberg — foram muitas perguntas de uma vez
    itens = sorted(reais.values(), key=lambda a: a["p"])
    m = len(itens)
    sobreviventes, prev = [], 1.0
    for i in range(m, 0, -1):
        a = itens[i-1]
        q = min(prev, a["p"] * m / i)
        prev = q
        a["q"] = round(q, 5)
    for a in itens:
        if a["q"] <= alpha and (a.get("razao") or 0) > 1.0:
            sobreviventes.append(a)

    candidatos: Dict[int, float] = defaultdict(float)
    for a in sobreviventes:
        peso = (a["razao"] - 1.0) * (1.0 - a["q"])
        for n in (a.get("alvos") or []):
            candidatos[int(n)] += peso

    ordenados = [n for n, _ in sorted(candidatos.items(), key=lambda kv: -kv[1])]
    return {
        "achados": sobreviventes,
        "candidatos": ordenados[:7],
        "pesos": {str(k): round(v, 4) for k, v in candidatos.items()},
        "n_perguntas": m,
        "n_sobreviventes": len(sobreviventes),
        "n_giros": len(seq),
    }


def resumo(r: Dict[str, Any], jogo: str = "lightning") -> str:
    if r.get("erro"):
        return f"[Ocorrências] {r['erro']}"
    if not r.get("achados"):
        return (f"[Ocorrências] {r.get('n_perguntas',0)} perguntas, nenhuma "
                f"sobreviveu à régua do acaso — nada a sugerir")
    cantou = [a for a in r["achados"] if a["agente"] in CANARIOS]
    linhas = [f"[Ocorrências] {r['n_sobreviventes']} de {r['n_perguntas']} "
              f"achados sobreviveram (em {r['n_giros']} giros)"]
    if cantou:
        linhas.append(f"   ⚠ CANÁRIO CANTOU ({len(cantou)}): "
                      f"{cantou[0]['descricao']} — atributo sem mecanismo físico "
                      f"apareceu como padrão. Trate esta leitura como suspeita.")
    for a in r["achados"][:6]:
        linhas.append(f"   {a['agente']}: {a['descricao']} — "
                      f"{a['razao']:.2f}x o acaso, q={a['q']:.3f}, n={a['n']}")
        # de qual teoria DELE este cacador saiu. Sem isto, o achado e uma
        # afirmacao sem procedencia -- e ele cobrou exatamente isso:
        # "todas ias devem aprender tudo que eu ditos nestes 3 pdfs".
        try:
            from .fonte_cacadores import texto_teoria
            t = texto_teoria(a["agente"], jogo)
            if t:
                linhas.append(f"      ↳ teoria dele: {t[:88]}")
        except Exception:
            pass
    if r.get("candidatos"):
        linhas.append(f"   candidatos: {r['candidatos']}")
    return "\n".join(linhas)
