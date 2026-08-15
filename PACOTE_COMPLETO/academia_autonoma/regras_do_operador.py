# -*- coding: utf-8 -*-
"""
REGRAS DO OPERADOR — o conhecimento de mesa, testado.

Estas transições foram ditadas de cabeça pelo usuário, a partir de anos
olhando as mesas. Elas NÃO estão aqui como verdade: estão como conjunto
PRÉ-DECLARADO de hipóteses, para serem medidas contra a régua igual a
qualquer outra coisa.

POR QUE ISSO VALE MAIS QUE VARRER TUDO
--------------------------------------
Varrer as 37×37 = 1369 transições possíveis e ficar com a melhor é garantia de
achar algo por acaso: com 1369 perguntas, a barra do controle de volume fica
~45x mais dura. Um conjunto declarado ANTES de olhar o dado custa apenas as
perguntas que ele contém.

Ou seja: o conhecimento do operador não é "achismo que o software tolera" — é
o que torna a busca estatisticamente viável. Esse é o papel científico de uma
hipótese formada por experiência.

GRUPOS POR FINAL
----------------
Além das transições, o usuário observa famílias de finais que se chamam:
0-1-3-6, 4-5-9, 0-2-7-8. Estas entram como conjuntos que reaparecem juntos —
não necessariamente em sequência colada, o que os outros agentes não pegavam.
"""
from __future__ import annotations
import math
import random
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------- transições
# "quando vem X, costuma vir Y" — ditado por ele.
#
# SEGUNDA DITADA, 15/08. Ele repassou a tabela inteira e corrigiu a primeira
# versão. O que mudou, para não se perder de novo:
#
#   0    NÃO EXISTIA na tabela antiga.   "quando vem o zero, vem o oito"
#   12   era [17]                      → [14, 16, 17]
#   14   era [16, 18, 12]              → [16]
#   17   era [20, 12]                  → [12, 20, 22]
#   20   NÃO EXISTIA                   → [17, 20, 22]
#   21   NÃO EXISTIA                   → igual ao 19
#   22   era [20, 17]                  → [17, 20, 22]
#   27   NÃO EXISTIA                   → igual ao 19
#   28   NÃO EXISTIA                   → [26, 28]
#   29   era [30]                      → [24, 29]     ← muda o alvo inteiro
#   30   era todos os 30               → igual ao 19
#   31   era [33, 30, ...]             → [33]
#   33   era [31, 30, ...]             → [31]
#
# A mudança do 29 é a mais séria: na tabela antiga, `29→30` foi o achado mais
# forte de toda a investigação (3,52x, p=0,0020 em 3367 giros). Na tabela
# corrigida essa regra não existe — o 29 aponta para o 24. As duas ficam
# medidas separadas, porque uma coisa é a regra dele e outra é o que a minha
# transcrição errada calhou de encontrar.
#
# Ele também frisou o vice-versa: "é sempre vice-versa, né?" — 2↔4, 24↔29,
# 26↔28, 31↔33, 34↔36, 14↔16.
_G19 = [19, 21, 23, 25, 27, 32]          # "mesma coisa do dezenove"
_G10 = [10, 11, 13, 15]                  # "dez onze treze quinze"
_G6 = [6, 8, 18]                         # "seis, oito e dezoito"
_G20 = [17, 20, 22]                      # "o dezessete, o vinte e o vinte e dois"
_G30 = [30, 31, 32, 33, 34, 35, 36]      # "são todos os trinta"

TRANSICOES: Dict[int, List[int]] = {
    0:  [8],
    1:  [1, 2, 3, 7],
    2:  [4],
    3:  [1, 2, 3, 7],
    4:  [2],
    5:  [9],
    6:  list(_G6),
    7:  [1, 7],
    8:  [0] + list(_G6),
    9:  [5],
    10: list(_G10),
    11: list(_G10),
    12: [14, 16, 17],
    13: list(_G10),
    14: [16],
    15: list(_G10),
    16: [14],
    17: [12] + list(_G20),
    18: list(_G6),
    19: list(_G19),
    20: list(_G20),
    21: list(_G19),
    22: list(_G20),
    23: list(_G19),
    24: [29],
    25: list(_G19),
    26: [28],
    27: list(_G19),
    28: [26],
    29: [24],
    30: list(_G19),
    31: [33],
    32: list(_G19),
    33: [31],
    34: [36],
    35: list(_G30),
    36: [34],
}

# A primeira transcrição, guardada para comparação. `29→30` saiu daqui e foi
# o achado mais forte da investigação; se ele estiver certo e eu tiver ouvido
# errado, foi sorte minha — e vale saber disso.
TRANSICOES_PRIMEIRA_DITADA: Dict[int, List[int]] = {
    1: [3, 7, 1], 2: [4], 3: [1, 2, 3], 4: [2], 5: [9], 6: [6, 8, 18],
    7: [1], 8: [6, 8, 18, 0], 9: [5], 10: [10, 11, 13, 15],
    11: [10, 11, 13, 15], 12: [17], 13: [10, 11, 13, 15], 14: [16, 18, 12],
    15: [10, 11, 13, 15], 16: [14], 17: [20, 12], 18: [6, 8, 18],
    19: [19, 21, 23, 32, 27, 30, 25], 22: [20, 17],
    23: [19, 21, 23, 32, 27, 30, 25], 24: [29],
    25: [19, 21, 23, 32, 27, 30, 25], 26: [28], 29: [30],
    30: [30, 31, 32, 33, 34, 35, 36], 31: [33, 30, 32, 34, 35, 36],
    32: [19, 21, 23, 32, 27, 30, 25], 33: [31, 30, 32, 34, 35, 36],
    34: [36], 35: [30, 31, 32, 33, 34, 35, 36], 36: [34],
}

# ---------------------------------------------------------------- finais
GRUPOS_FINAL: Dict[str, List[int]] = {
    "0-1-3-6": [0, 1, 3, 6],
    "4-5-9":   [4, 5, 9],
    "0-2-7-8": [0, 2, 7, 8],
}

JANELA_GRUPO = 6      # "aparecem juntos" = dentro desta janela
N_REGUA = 2000


def _p_ge(h: int, n: int, p: float) -> float:
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)
                        + k*math.log(p) + (n-k)*math.log(1-p))
               for k in range(min(h, n), n+1))


JANELA_TRANSICAO = 5     # "vem depois" = dentro de tantos giros


def testar_transicoes(seq: List[int], transicoes=None,
                      janela: int = JANELA_TRANSICAO) -> List[dict]:
    """
    Cada regra declarada, medida contra a chance de acertar por acaso.

    "QUANDO VEM X, VEM Y" NÃO É O GIRO SEGUINTE.
    ---------------------------------------------
    A primeira versão disto media só `zip(seq, seq[1:])` — o giro imediatamente
    posterior. O operador corrigiu: "não vem na hora, às vezes vem três, quatro
    depois". Medir só o lag 1 responde a pergunta errada e enterra a regra.

    Aqui cada regra é medida em duas leituras:
      - por DISTÂNCIA (lag 1..janela), uma pergunta por distância, para
        descobrir se o efeito tem um atraso característico
      - por JANELA (aconteceu em algum dos próximos `janela` giros), que é
        como a pessoa percebe na mesa

    A base de comparação muda junto: para janela, a chance de o alvo aparecer
    em pelo menos um de `janela` giros é 1-(1-k/37)^janela, não k/37.
    """
    T = transicoes or TRANSICOES
    out = []
    N = len(seq) or 1
    for gat, alvos in T.items():
        alvo = set(alvos)
        k = len(alvo)
        # A BASE E' A TAXA REAL DO ALVO NESTA MESA, nao a teorica k/37.
        # Se a mesa andou soltando muito 4-5-9, TODA regra que aponte pra
        # 4-5-9 parece forte sem o gatilho ter nada a ver. Caso real,
        # mega_fire, 272 giros: 4-5-9 saiu em 37,9% (teoria diz 29,7%). Com a
        # base teorica a regra marcava 1,10x, "achado". Com a base real da
        # propria mesa: 1,00x -- nada.
        p_alvo = max(sum(1 for x in seq if x in alvo) / N, 1e-9)

        # --- leitura por JANELA (como se percebe na mesa)
        n = h = 0
        for i, a in enumerate(seq[:-1]):
            if a != gat:
                continue
            n += 1
            if alvo & set(seq[i+1:i+1+janela]):
                h += 1
        if n >= 5:
            base = 1 - (1 - p_alvo) ** janela
            out.append({
                "regra": f"{gat} → {alvos} em até {janela} giros",
                "gatilho": gat, "alvos": list(alvos), "lag": None,
                "n": n, "hits": h, "taxa": h/n, "base": base,
                "razao": (h/n)/base if base else None,
                "p": _p_ge(h, n, base),
            })

        # --- leitura por DISTÂNCIA (revela o atraso característico)
        for lag in range(1, janela + 1):
            n2 = h2 = 0
            for i, a in enumerate(seq[:-lag]):
                if a != gat:
                    continue
                n2 += 1
                if seq[i+lag] in alvo:
                    h2 += 1
            if n2 < 5:
                continue
            base2 = p_alvo
            out.append({
                "regra": f"{gat} → {alvos} exatamente {lag} giro(s) depois",
                "gatilho": gat, "alvos": list(alvos), "lag": lag,
                "n": n2, "hits": h2, "taxa": h2/n2, "base": base2,
                "razao": (h2/n2)/base2 if base2 else None,
                "p": _p_ge(h2, n2, base2),
            })
    return out


def testar_grupos(seq: List[int], grupos=None, janela: int = JANELA_GRUPO,
                  n_regua: int = N_REGUA, seed: int = 4242) -> List[dict]:
    """
    Os números do grupo reaparecem JUNTOS numa janela, mesmo espalhados?

    Isto é o que faltava: O11 e X05 só pegam trinca colada e na ordem. Aqui a
    pergunta é outra — em quantas janelas de `janela` giros o grupo inteiro
    aparece, em qualquer ordem, com outros números no meio.

    A régua é reordenação: preserva quantas vezes cada número saiu e desfaz a
    ordem. Se o grupo se junta mais na sequência real do que nas reordenadas,
    o agrupamento é da ordem, não da composição.
    """
    G = grupos or GRUPOS_FINAL
    if len(seq) < 60:
        return []

    def conta_juntos(s, alvos):
        alvo = set(alvos)
        c = 0
        for i in range(len(s) - janela + 1):
            if alvo.issubset(set(s[i:i+janela])):
                c += 1
        return c

    rng = random.Random(seed)
    out = []
    copia = seq[:]
    reais = {nome: conta_juntos(seq, alvos) for nome, alvos in G.items()}
    piores = {nome: 0 for nome in G}
    for _ in range(n_regua):
        rng.shuffle(copia)
        for nome, alvos in G.items():
            if conta_juntos(copia, alvos) >= reais[nome]:
                piores[nome] += 1
    for nome, alvos in G.items():
        out.append({
            "regra": f"grupo {nome} aparece junto em {janela} giros",
            "gatilho": None, "alvos": list(alvos),
            "n": len(seq) - janela + 1, "hits": reais[nome],
            "taxa": None, "base": None,
            "razao": None,
            "p": (piores[nome] + 1) / (n_regua + 1),
        })
    return out


def avaliar(seq, alpha: float = 0.10) -> Dict[str, Any]:
    """
    Roda tudo e aplica Benjamini-Hochberg sobre o conjunto declarado.

    Nada é descartado: cada regra sai com o veredito dela, inclusive as que
    não passaram. Regra fraca hoje pode estar só esperando giros.
    """
    limpa = []
    for x in (seq or []):
        try:
            limpa.append(int(x))
        except (TypeError, ValueError):
            pass
    if len(limpa) < 60:
        return {"regras": [], "candidatos": [], "erro": "histórico curto"}

    itens = testar_transicoes(limpa) + testar_grupos(limpa)
    itens = [i for i in itens if i.get("p") is not None]
    if not itens:
        return {"regras": [], "candidatos": []}

    itens.sort(key=lambda i: i["p"])
    m = len(itens)
    prev = 1.0
    for k in range(m, 0, -1):
        it = itens[k-1]
        it["q"] = round(min(prev, it["p"] * m / k), 5)
        prev = it["q"]
    for it in itens:
        it["veredito"] = ("confirmada" if it["q"] <= alpha
                          else ("em_observacao" if it["p"] <= 0.10 else "sem_forca"))

    ultimo = limpa[-1] if limpa else None
    cand: Dict[int, float] = defaultdict(float)
    for it in itens:
        if it["veredito"] == "sem_forca":
            continue
        peso = 1.0 if it["veredito"] == "confirmada" else 0.4
        # a regra só vale AGORA se o gatilho dela for o giro atual
        if it["gatilho"] is not None and it["gatilho"] != ultimo:
            continue
        for a in it["alvos"]:
            cand[int(a)] += peso * max(1.0, it.get("razao") or 1.0)

    conf = sum(1 for i in itens if i["veredito"] == "confirmada")
    obs = sum(1 for i in itens if i["veredito"] == "em_observacao")
    return {
        "regras": itens,
        "candidatos": [n for n, _ in sorted(cand.items(), key=lambda kv: -kv[1])][:7],
        "confirmadas": conf, "em_observacao": obs,
        "sem_forca": m - conf - obs, "n_testadas": m, "n_giros": len(limpa),
    }


def resumo(r: Dict[str, Any]) -> str:
    if r.get("erro"):
        return f"[Regras do operador] {r['erro']}"
    if not r.get("regras"):
        return "[Regras do operador] nada a medir"
    L = [f"[Regras do operador] {r['confirmadas']} confirmada(s), "
         f"{r['em_observacao']} em observação, de {r['n_testadas']} testadas "
         f"({r['n_giros']} giros)"]
    for it in r["regras"]:
        if it["veredito"] == "sem_forca":
            continue
        marca = "✓" if it["veredito"] == "confirmada" else "·"
        raz = f" {it['razao']:.2f}x" if it.get("razao") else ""
        L.append(f"   {marca} {it['regra']}: {it['hits']}/{it['n']}{raz} q={it['q']:.3f}")
    if r.get("candidatos"):
        L.append(f"   candidatos agora: {r['candidatos']}")
    return "\n".join(L)
