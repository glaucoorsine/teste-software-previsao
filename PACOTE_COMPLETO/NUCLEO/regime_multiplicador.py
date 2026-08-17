# -*- coding: utf-8 -*-
"""
REGIME DE MULTIPLICADOR — as observações dele, medidas, com número e limiar.

O QUE ELE DESCREVEU, E EU NÃO TINHA USADO
─────────────────────────────────────────
    "no Mega Fire diz, nas últimas quinhentas rodadas saíram x números
     multiplicados. E eu percebi que quando está acima de quarenta e cinco
     costumam ficar vindo multiplicadores de uma maneira mais fácil"

    "os multiplicadores que vieram recente são valores altos ou baixos? Normalmente
     quando são valores baixos, após um tempo começa a vir multiplicadores altos
     e vice-versa"

    "tem um tempo que não saiu um número multiplicado"

Meu semáforo estava decidindo com quatro checagens minhas -- ele chamou de
superficial e tem razão. Estas três são observações DELE, com número e direção,
e são exatamente o tipo de coisa que se mede.

AS TRÊS PERGUNTAS, E COMO CADA UMA É RESPONDIDA
───────────────────────────────────────────────
1. DENSIDADE — quantos pagaram nas últimas 500? O limiar 45 é dele, declarado, e
   fica citado como tal. Mas o software também MEDE o próprio limiar: divide o
   histórico em janelas de 500, e vê se acima de 45 a taxa de prêmio realmente
   sobe. Se subir, o limiar dele está confirmado com número. Se não subir nesta
   mesa, isso é dito -- sem apagar a observação, que pode valer noutra.

2. CICLO DE MAGNITUDE — depois de um período de multiplicadores BAIXOS vêm os
   altos? Isto é testável: separa os momentos em que a média recente estava
   baixa e olha se o próximo alto veio mais cedo do que o normal. É a mesma
   pergunta que ele faz, escrita como medida.

3. SECA — quantos giros desde o último que pagou, e quanto isso é ALTO para esta
   mesa (em quantil, não em número absoluto: 12 giros de seca é muito no Crazy
   Time e pouco no Mega Fire).

O QUE NÃO FAÇO AQUI
───────────────────
Não decido nada. Este arquivo mede e devolve com o `n` de cada medida. Quem usa
é o semáforo, e ele só transforma em motivo o que veio com base.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

# a janela que ELE usa para contar, e o limiar que ELE observou
JANELA_DELE = 500
LIMIAR_DELE = 45

MIN_PARA_MEDIR_LIMIAR = 3        # janelas de 500 necessárias para testar o 45
MIN_PREMIOS_MAGNITUDE = 20       # prêmios necessários para falar de magnitude


def _pagos(linhas: Sequence[dict], pagou_de) -> List[float]:
    """O valor pago em cada giro, 0 quando não pagou. Recente-primeiro."""
    return [float(pagou_de(l)[0] or 0.0) for l in linhas]


# ─────────────────────────────────────── o corte que separa achado de ruído
#
# POR QUE UMA RAZÃO NÃO BASTA, E COMO EU SOUBE
# ────────────────────────────────────────────
# Estas medidas confirmavam por RAZÃO: se a taxa de um lado passasse 15% da do
# outro, a observação dele estava "confirmada". O controle honesto -- mesa gerada
# sem nenhuma inversão -- devolveu 0,582 contra 0,492, razão 1,183x, e passou. Não
# havia inversão nenhuma naquela mesa; com cinquenta observações de cada lado,
# uma diferença de nove pontos é sorteio.
#
# Uma razão sem o `n` atrás dela dispara com ruído, e disparar com ruído aqui é
# grave: é o semáforo dando verde porque a moeda caiu de um jeito. Então o
# `confirma` passa a exigir as duas coisas -- tamanho de efeito E que o efeito
# esteja além do ruído do próprio tamanho da amostra.
Z_MINIMO = 2.0          # ~95% de dois lados


def _z_proporcoes(k1: int, n1: int, k2: int, n2: int) -> Optional[float]:
    """Quantos desvios separam duas proporções. Sinal: positivo se a 1ª é maior."""
    if n1 < 2 or n2 < 2:
        return None
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se <= 1e-12:
        return None
    return (p1 - p2) / se


def _welch_t(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Idem para duas listas de medidas contínuas, sem supor variância igual.

    Aqui as unidades são BLOCOS de 500 giros, não giros. Usar o `n` de giros
    trataria 500 giros do mesmo bloco como 500 provas independentes -- é o erro
    da ficha 226, o N efetivo, e inflaria a certeza por um fator enorme.
    """
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    se = math.sqrt(va / na + vb / nb)
    if se <= 1e-12:
        return None
    return (ma - mb) / se


# ────────────────────────────────────────────────────────────── 1. densidade
def densidade(linhas: Sequence[dict], pagou_de,
              janela: int = JANELA_DELE) -> Dict[str, Any]:
    """Quantos números multiplicados nas últimas `janela` rodadas.

    É a conta que a própria tela do Mega Fire mostra a ele, e por isso a unidade
    é a mesma: CONTAGEM na janela, não taxa. Ele raciocina em "45 em 500".
    """
    p = _pagos(linhas, pagou_de)
    usados = p[:janela]
    quantos = sum(1 for x in usados if x > 0)
    # extrapola quando ainda não há 500 giros, e DIZ que extrapolou
    proj = (quantos * janela / len(usados)) if usados else 0.0
    return {
        "janela": janela, "giros_lidos": len(usados),
        "quantos": quantos,
        "projetado_500": round(proj, 1),
        "completa": len(usados) >= janela,
        "limiar_dele": LIMIAR_DELE,
        "acima_do_limiar": (proj if not usados or len(usados) < janela
                            else quantos) > LIMIAR_DELE,
    }


def limiar_confirmado(linhas: Sequence[dict], pagou_de,
                      janela: int = JANELA_DELE,
                      limiar: int = LIMIAR_DELE) -> Dict[str, Any]:
    """O limiar 45 DELE se confirma nesta mesa?

    Divide o histórico em blocos de `janela`, separa os que tinham mais de
    `limiar` prêmios dos que tinham menos, e compara a taxa de prêmio do bloco
    SEGUINTE. Se acima de 45 o bloco seguinte paga mais, a observação dele tem
    número. Se não, isso é dito -- a observação não é apagada, fica sem
    confirmação NESTA mesa.
    """
    p = _pagos(linhas, pagou_de)
    blocos = [p[i:i + janela] for i in range(0, len(p) - janela + 1, janela)]
    if len(blocos) < MIN_PARA_MEDIR_LIMIAR:
        return {"mediu": False,
                "nota": f"preciso de {MIN_PARA_MEDIR_LIMIAR} blocos de {janela} "
                        f"giros; tenho {len(blocos)}"}
    # recente-primeiro: o bloco SEGUINTE no tempo é o de índice MENOR
    acima, abaixo = [], []
    for i in range(1, len(blocos)):
        anterior = blocos[i]                 # mais antigo
        seguinte = blocos[i - 1]             # o que veio depois dele
        n_ant = sum(1 for x in anterior if x > 0)
        taxa_seg = sum(1 for x in seguinte if x > 0) / max(1, len(seguinte))
        (acima if n_ant > limiar else abaixo).append(taxa_seg)
    if not acima or not abaixo:
        return {"mediu": False,
                "nota": f"todos os blocos ficaram do mesmo lado de {limiar} — "
                        f"sem contraste para medir"}
    ma = sum(acima) / len(acima)
    mb = sum(abaixo) / len(abaixo)
    t = _welch_t(acima, abaixo)
    return {"mediu": True, "limiar": limiar,
            "taxa_depois_de_acima": round(ma, 4),
            "taxa_depois_de_abaixo": round(mb, 4),
            "n_acima": len(acima), "n_abaixo": len(abaixo),
            "razao": round(ma / mb, 3) if mb > 0 else None,
            "t": round(t, 2) if t is not None else None,
            # tamanho E significância: razão sozinha confirma ruído
            "confirma": bool(ma > mb * 1.1 and t is not None and t >= Z_MINIMO)}


# ─────────────────────────────────────────────────────── 2. ciclo de magnitude
def _postos(premios: Sequence[float]):
    """Devolve a função que dá o POSTO de um prêmio nesta mesa, entre 0 e 1.

    POR QUE POSTO E NÃO MEDIANA
    ───────────────────────────
    Eu tinha escrito isto contra a mediana da mesa, para ser livre de escala --
    ×50 é baixo no Lightning e enorme no Crazy Time. A intenção estava certa e a
    conta estava errada, e o teste plantado mostrou onde: os prêmios da mesa dele
    não se espalham suavemente, eles vêm em dois grupos, os miúdos e os graúdos.
    Numa mesa assim a mediana cai DENTRO do grupo alto, e então ×400 é
    classificado como baixo e quase nenhuma janela passa de mediana×1,25. Na
    medida, isso deu 442 janelas de um lado contra 6 do outro -- sem contraste
    não há o que comparar.

    O posto não tem esse problema: é uniforme por construção, seja a mesa de um
    grupo, de dois ou de dez. Empates ficam no meio do empate (`+0.5*iguais`), o
    que dá o efeito certo no caso limite: mesa em que todo prêmio é igual tem
    todos os postos em 0,5 -- nada é alto nem baixo, e é exatamente o que se deve
    dizer de uma mesa sem variação.
    """
    ord_ = sorted(premios)
    n = len(ord_)

    def posto(v: float) -> float:
        import bisect
        menores = bisect.bisect_left(ord_, v)
        iguais = bisect.bisect_right(ord_, v) - menores
        return (menores + 0.5 * iguais) / n

    return posto


# limites de posto para chamar uma janela de baixa ou alta. Simétricos em torno
# de 0,5 -- assimetria aqui criaria contraste onde não há.
POSTO_BAIXO, POSTO_ALTO = 0.40, 0.60


def magnitude(linhas: Sequence[dict], pagou_de,
              recentes: int = 8) -> Dict[str, Any]:
    """Os multiplicadores recentes são altos ou baixos, para ESTA mesa?"""
    p = _pagos(linhas, pagou_de)
    premios = [x for x in p if x > 0]
    if len(premios) < MIN_PREMIOS_MAGNITUDE:
        return {"mediu": False,
                "nota": f"só {len(premios)} prêmios no histórico; preciso de "
                        f"{MIN_PREMIOS_MAGNITUDE}"}
    posto = _postos(premios)
    ordenados = sorted(premios)
    mediana = ordenados[len(ordenados) // 2]
    ult = premios[:recentes]
    if not ult:
        return {"mediu": False, "nota": "nenhum prêmio recente"}
    media_recente = sum(ult) / len(ult)
    posto_recente = sum(posto(x) for x in ult) / len(ult)
    return {"mediu": True, "mediana_da_mesa": mediana,
            "media_recente": round(media_recente, 1),
            "posto_recente": round(posto_recente, 3),
            "n_recentes": len(ult),
            "faixa": ("baixos" if posto_recente < POSTO_BAIXO else
                      "altos" if posto_recente > POSTO_ALTO else "normais")}


def ciclo_magnitude(linhas: Sequence[dict], pagou_de,
                    recentes: int = 8) -> Dict[str, Any]:
    """Depois de multiplicadores BAIXOS vêm os altos? A observação dele, medida.

    Para cada prêmio do histórico, olha a média dos `recentes` prêmios ANTERIORES
    a ele e pergunta: quando essa média estava baixa, o prêmio seguinte foi alto
    mais vezes do que o normal?

    Nada do futuro entra: a média é sempre dos prêmios que vieram ANTES.
    """
    p = _pagos(linhas, pagou_de)
    # posições dos prêmios, do mais recente ao mais antigo
    pos = [i for i, x in enumerate(p) if x > 0]
    if len(pos) < MIN_PREMIOS_MAGNITUDE + recentes:
        return {"mediu": False,
                "nota": f"preciso de ~{MIN_PREMIOS_MAGNITUDE + recentes} "
                        f"prêmios; tenho {len(pos)}"}
    vals = [p[i] for i in pos]
    posto = _postos(vals)
    r = [posto(v) for v in vals]
    ordenados = sorted(vals)
    mediana = ordenados[len(ordenados) // 2]
    # recente-primeiro: os ANTERIORES a pos[k] são pos[k+1:]
    depois_de_baixo, depois_de_alto = [], []
    for k in range(0, len(pos) - recentes):
        anteriores = r[k + 1:k + 1 + recentes]
        if len(anteriores) < recentes:
            break
        m = sum(anteriores) / len(anteriores)
        alto_agora = 1 if r[k] > 0.5 else 0
        if m < POSTO_BAIXO:
            depois_de_baixo.append(alto_agora)
        elif m > POSTO_ALTO:
            depois_de_alto.append(alto_agora)
    if len(depois_de_baixo) < 8 or len(depois_de_alto) < 8:
        return {"mediu": False,
                "nota": f"contraste insuficiente (baixo={len(depois_de_baixo)}, "
                        f"alto={len(depois_de_alto)}; preciso de 8 de cada)"}
    pb = sum(depois_de_baixo) / len(depois_de_baixo)
    pa = sum(depois_de_alto) / len(depois_de_alto)
    z = _z_proporcoes(sum(depois_de_baixo), len(depois_de_baixo),
                      sum(depois_de_alto), len(depois_de_alto))
    return {"mediu": True, "mediana": mediana,
            "alto_depois_de_baixo": round(pb, 3),
            "alto_depois_de_alto": round(pa, 3),
            "n_baixo": len(depois_de_baixo), "n_alto": len(depois_de_alto),
            "razao": round(pb / pa, 3) if pa > 0 else None,
            "z": round(z, 2) if z is not None else None,
            # a observação dele: depois de baixos vêm altos -- e além do ruído
            "confirma": bool(pb > pa * 1.15 and z is not None and z >= Z_MINIMO)}


# ─────────────────────────────────────────────────────────────────── 3. seca
def seca(linhas: Sequence[dict], pagou_de) -> Dict[str, Any]:
    """Quantos giros desde o último que pagou — e quão longo isso é AQUI.

    Em quantil, não em número absoluto: 12 giros de seca é muito no Crazy Time e
    pouco no Mega Fire, e comparar o número cru entre mesas não diz nada.
    """
    p = _pagos(linhas, pagou_de)
    agora = 0
    for x in p:
        if x > 0:
            break
        agora += 1
    # todas as secas do histórico, para saber onde esta se encaixa
    secas, corrida = [], 0
    for x in p:
        if x > 0:
            secas.append(corrida)
            corrida = 0
        else:
            corrida += 1
    if len(secas) < 10:
        return {"mediu": False, "agora": agora,
                "nota": f"só {len(secas)} secas no histórico"}
    ordenadas = sorted(secas)
    quantil = sum(1 for s in ordenadas if s <= agora) / len(ordenadas)
    return {"mediu": True, "agora": agora,
            "mediana": ordenadas[len(ordenadas) // 2],
            "maior_do_historico": ordenadas[-1],
            "quantil": round(quantil, 3),
            "n_secas": len(secas),
            "longa": quantil >= 0.85}


# ────────────────────────────────────────────────────────────────── a leitura
def ler(linhas: Sequence[dict], pagou_de) -> Dict[str, Any]:
    """As três observações dele, medidas de uma vez."""
    return {
        "densidade": densidade(linhas, pagou_de),
        "limiar": limiar_confirmado(linhas, pagou_de),
        "magnitude": magnitude(linhas, pagou_de),
        "ciclo": ciclo_magnitude(linhas, pagou_de),
        "seca": seca(linhas, pagou_de),
    }


def resumo(r: Dict[str, Any]) -> List[str]:
    """Em português, com o número e o `n` de cada afirmação."""
    L: List[str] = []
    d = r.get("densidade") or {}
    if d:
        alvo = d["quantos"] if d.get("completa") else d.get("projetado_500")
        marca = "" if d.get("completa") else " (projetado — ainda não há 500)"
        L.append(f"[Multiplicadores] {d['quantos']} pagaram nos últimos "
                 f"{d['giros_lidos']} giros → {alvo} em 500{marca}. "
                 f"O ponto dele é {d['limiar_dele']}: "
                 f"{'ACIMA' if d.get('acima_do_limiar') else 'abaixo'}")
    lim = r.get("limiar") or {}
    if lim.get("mediu"):
        L.append(f"[Multiplicadores] o limiar {lim['limiar']} dele "
                 f"{'CONFIRMA' if lim.get('confirma') else 'não confirma'} "
                 f"nesta mesa: depois de blocos acima, "
                 f"{lim['taxa_depois_de_acima']:.1%} pagaram; abaixo, "
                 f"{lim['taxa_depois_de_abaixo']:.1%} "
                 f"({lim.get('razao')}x, n={lim['n_acima']}/{lim['n_abaixo']} "
                 f"blocos, t={lim.get('t')})")
    elif lim.get("nota"):
        L.append(f"[Multiplicadores] limiar {LIMIAR_DELE} ainda não testável — "
                 f"{lim['nota']}")
    mg = r.get("magnitude") or {}
    if mg.get("mediu"):
        L.append(f"[Magnitude] os {mg['n_recentes']} últimos prêmios são "
                 f"{mg['faixa'].upper()}: média {mg['media_recente']} contra "
                 f"mediana {mg['mediana_da_mesa']} da mesa")
    c = r.get("ciclo") or {}
    if c.get("mediu"):
        L.append(f"[Magnitude] a inversão que ele descreveu "
                 f"{'CONFIRMA' if c.get('confirma') else 'não confirma'}: "
                 f"depois de baixos, {c['alto_depois_de_baixo']:.0%} vieram "
                 f"altos; depois de altos, {c['alto_depois_de_alto']:.0%} "
                 f"(n={c['n_baixo']}/{c['n_alto']}, z={c.get('z')})")
    elif c.get("nota"):
        L.append(f"[Magnitude] inversão ainda não testável — {c['nota']}")
    s = r.get("seca") or {}
    if s.get("mediu"):
        L.append(f"[Seca] {s['agora']} giros sem prêmio — mediana desta mesa é "
                 f"{s['mediana']}, maior já vista {s['maior_do_historico']}; "
                 f"esta está no quantil {s['quantil']:.0%}"
                 + ("  ← seca longa" if s.get("longa") else ""))
    elif s:
        L.append(f"[Seca] {s.get('agora', 0)} giros sem prêmio "
                 f"({s.get('nota') or ''})")
    return L
