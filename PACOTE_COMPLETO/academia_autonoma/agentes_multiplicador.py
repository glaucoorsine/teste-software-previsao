# -*- coding: utf-8 -*-
"""
QUINZE AGENTES DE MULTIPLICADOR — Lightning e Mega Fire Blaze.

Ditados pelo operador em 14/08/2026:

    "normalmente fica muito tempo sem ver multiplicador, aparece um no
     limite até 200x, e tendem a vir mais multiplicadores"
    "quando vem dois números iguais, tipo 30, 30, logo em seguida vem
     um multiplicador"
    "lá atrás o software tinha indicadores do que poderia vir multiplicado,
     só que a métrica era completamente errada"

POR QUE A MÉTRICA ANTIGA ERRAVA
-------------------------------
Não era escolha de fórmula. Era falta de dado, e por um defeito de captura: o
Lightning sorteia de 1 a 5 lucky numbers em TODA rodada, cada um com seu
multiplicador, e o coletor só registrava quando o lucky calhava de ser o número
que saiu. Em 205 giros reais isso deixou 10 registros de umas 600 premiações
que aconteceram. Qualquer estudo em cima disso enxergava 2% do fenômeno — e
uma métrica cega a 98% do dado acerta de vez em quando, por acaso, que é
exatamente o que o operador descreveu.

Corrigido na captura (`fluxo_captura.parse_items_roulette`), o histórico passa
a trazer a rodada inteira. Estes agentes trabalham em cima disso.

A PERGUNTA QUE NINGUÉM TINHA FEITO
----------------------------------
M07. O número premiado com multiplicador sai mais que os outros?

O multiplicador é sorteado por um gerador; a bola é física. Se as duas coisas
forem independentes — como devem ser — um lucky number sai exatamente 1/37 das
vezes, como qualquer outro. Se sair mais, isso não é vício de roleta: é sinal
de que os dois sorteios se conhecem, e seria o achado mais sério que este
estudo poderia produzir.

Se sair MENOS, também é achado, e do tipo que interessa a quem aposta.

Este agente é o motivo de valer a pena coletar multiplicador.

RÉGUAS
------
Cada agente diz contra o quê está medindo. Onde os gatilhos se sobrepõem
(janelas deslizantes), a régua é reordenação, não binomial — pares sobrepostos
não são ensaios independentes, e tratá-los como se fossem infla a força.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

SELO_CONFIRMADO = "confirmado"
SELO_OBSERVACAO = "em_observacao"
SELO_FRACO = "indicio"

JANELA_DEPOIS = 5      # "logo em seguida" — travado
SECA_LONGA = 12        # "muito tempo sem ver" — travado
ALTO = 100             # "no limite até 200x" — travado
N_REGUA = 1200


def _p_ge(h: int, n: int, p: float) -> float:
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1)
                        + k * math.log(p) + (n - k) * math.log(1 - p))
               for k in range(min(h, n), n + 1))


def _selo(p: Optional[float], m: int = 1) -> str:
    if p is None:
        return SELO_FRACO
    if p <= 0.05 / max(1, m):
        return SELO_CONFIRMADO
    if p <= 0.10:
        return SELO_OBSERVACAO
    return SELO_FRACO


def _achado(aid, nome, h, n, base, p, alvos=None, nota=""):
    return {"agente": aid, "achado": nome, "hits": h, "n": n, "base": base,
            "razao": ((h / n) / base) if (n and base) else None,
            "p": p, "alvos": alvos or [], "nota": nota}


# --------------------------------------------------------------- extração
def extrair(eventos: List[dict]) -> Tuple[List[int], List[int], List[List[dict]]]:
    """
    (números sorteados, multiplicador que BATEU ou 0, rodada de lucky completa)

    `eventos` vem do buffer, em ordem cronológica.
    """
    nums, batido, rodada = [], [], []
    for e in eventos:
        v = str(e.get("valor"))
        if not v.lstrip("-").isdigit():
            continue
        nums.append(int(v))
        x = 0
        luck: List[dict] = []
        for t in (e.get("tags") or []):
            if "x" in t:
                try:
                    x = int(t["x"])
                except (TypeError, ValueError):
                    pass
            if "lucky" in t and isinstance(t["lucky"], list):
                luck = [d for d in t["lucky"] if isinstance(d, dict)]
        batido.append(x)
        rodada.append(luck)
    return nums, batido, rodada


# ------------------------------------------------------------- os quinze
def M01_seca_quebrada(nums, bat, rod):
    """Depois de muitos giros sem multiplicador batido, vem um?"""
    p = sum(1 for x in bat if x) / max(1, len(bat))
    if p <= 0:
        return []
    h = n = 0
    seca = 0
    for i, x in enumerate(bat):
        if seca >= SECA_LONGA and i < len(bat):
            n += 1
            if x:
                h += 1
        seca = 0 if x else seca + 1
    if n < 10:
        return []
    return [_achado("M01_SECA_QUEBRADA",
                    f"após {SECA_LONGA}+ giros sem multiplicador, veio um",
                    h, n, p, _p_ge(h, n, p),
                    nota="a régua é a própria taxa de multiplicador da mesa")]


def M02_apos_alto(nums, bat, rod):
    """Depois de um multiplicador ALTO bater, vêm mais multiplicadores?"""
    p_jan = 1 - (1 - sum(1 for x in bat if x) / max(1, len(bat))) ** JANELA_DEPOIS
    h = n = 0
    for i, x in enumerate(bat[:-JANELA_DEPOIS]):
        if x >= ALTO:
            n += 1
            if any(bat[i + 1:i + 1 + JANELA_DEPOIS]):
                h += 1
    if n < 8:
        return []
    return [_achado("M02_APOS_ALTO",
                    f"após multiplicador ≥{ALTO}x, veio outro em {JANELA_DEPOIS} giros",
                    h, n, p_jan, _p_ge(h, n, p_jan))]


def M03_par_igual(nums, bat, rod):
    """A regra do operador: dois números iguais seguidos → multiplicador."""
    p = sum(1 for x in bat if x) / max(1, len(bat))
    h = n = 0
    for i in range(1, len(nums) - 1):
        if nums[i] == nums[i - 1]:
            n += 1
            if bat[i + 1]:
                h += 1
    if n < 5:
        return [_achado("M03_PAR_IGUAL",
                        "dois números iguais → multiplicador no giro seguinte",
                        h, n, p, None,
                        nota=f"só {n} ocorrência(s) — sem amostra para decidir")]
    return [_achado("M03_PAR_IGUAL",
                    "dois números iguais → multiplicador no giro seguinte",
                    h, n, p, _p_ge(h, n, p))]


def M04_repeticao_janela(nums, bat, rod):
    """Número que repetiu dentro de 5 giros → multiplicador logo depois?"""
    p = sum(1 for x in bat if x) / max(1, len(bat))
    h = n = 0
    for i in range(5, len(nums) - 1):
        if nums[i] in nums[i - 5:i]:
            n += 1
            if bat[i + 1]:
                h += 1
    if n < 15:
        return []
    return [_achado("M04_REPETICAO_JANELA",
                    "número repetido em 5 giros → multiplicador no seguinte",
                    h, n, p, _p_ge(h, n, p))]


def M07_lucky_sai_mais(nums, bat, rod):
    """
    O NÚMERO PREMIADO SAI MAIS QUE OS OUTROS?

    O multiplicador é sorteado por gerador; a bola é física. Se forem
    independentes, um lucky sai 1/37 das vezes como qualquer outro. Sair mais
    (ou menos) significa que os dois sorteios se conhecem.
    """
    h = n = 0
    esp = 0.0
    for i, luck in enumerate(rod):
        if not luck:
            continue
        alvo = {d.get("n") for d in luck}
        n += 1
        esp += len(alvo) / 37.0
        if nums[i] in alvo:
            h += 1
    if n < 30:
        return []
    base = esp / n
    return [_achado("M07_LUCKY_SAI_MAIS",
                    "o número premiado saiu",
                    h, n, base, _p_ge(h, n, base),
                    nota="se sair mais ou menos que a chance, os dois "
                         "sorteios não são independentes")]


def M05_lucky_viciado(nums, bat, rod):
    """Algum número é escolhido lucky com frequência fora do esperado?"""
    c: Counter = Counter()
    tot = 0
    for luck in rod:
        for d in luck:
            c[d.get("n")] += 1
            tot += 1
    if tot < 200:
        return []
    base = 1 / 37
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, tot, base) * 37)      # corrige as 37 perguntas
    return [_achado("M05_LUCKY_VICIADO",
                    f"o número {top} foi escolhido lucky",
                    q, tot, base, p, alvos=[top])]


def M06_lucky_repete(nums, bat, rod):
    """Um número escolhido lucky é escolhido de novo no giro seguinte?"""
    h = n = 0
    esp = 0.0
    for i in range(len(rod) - 1):
        a = {d.get("n") for d in rod[i]}
        b = {d.get("n") for d in rod[i + 1]}
        if not a or not b:
            continue
        n += len(a)
        esp += len(a) * (len(b) / 37.0)
        h += len(a & b)
    if n < 100:
        return []
    base = esp / n
    return [_achado("M06_LUCKY_REPETE", "um lucky voltou a ser lucky",
                    h, n, base, _p_ge(h, n, base))]


def M08_alto_agrupa(nums, bat, rod):
    """Multiplicadores altos vêm em grupo? Régua: reordenação."""
    altos = [1 if any(d.get("x", 0) >= ALTO for d in luck) else 0 for luck in rod]
    if sum(altos) < 12:
        return []
    def juntos(s):
        return sum(1 for i in range(len(s) - 1) if s[i] and s[i + 1])
    real = juntos(altos)
    rng = random.Random(777)
    c = list(altos)
    piores = 0
    for _ in range(N_REGUA):
        rng.shuffle(c)
        if juntos(c) >= real:
            piores += 1
    esperado = (sum(altos) / len(altos)) ** 2 * (len(altos) - 1)
    return [_achado("M08_ALTO_AGRUPA",
                    f"multiplicadores ≥{ALTO}x em giros vizinhos",
                    real, len(altos) - 1,
                    esperado / max(1, len(altos) - 1),
                    (piores + 1) / (N_REGUA + 1),
                    nota="régua de reordenação")]


def M09_quantos_lucky(nums, bat, rod):
    """A quantidade de lucky por rodada varia mais do que deveria?"""
    qs = [len(l) for l in rod if l]
    if len(qs) < 60:
        return []
    c = Counter(qs)
    return [_achado("M09_QUANTOS_LUCKY",
                    f"lucky por rodada: {dict(sorted(c.items()))}",
                    0, len(qs), None, None,
                    nota="descritivo — sem teste, serve de contexto")]


def M10_lucky_setor(nums, bat, rod):
    """Os lucky se concentram num setor da roda?"""
    RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
            10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
    POS = {n: i for i, n in enumerate(RODA)}
    dists = []
    for luck in rod:
        ns = [d.get("n") for d in luck if d.get("n") in POS]
        for a, b in zip(ns, ns[1:]):
            d = abs(POS[a] - POS[b]) % 37
            dists.append(min(d, 37 - d))
    if len(dists) < 150:
        return []
    perto = sum(1 for d in dists if d <= 3)
    base = 7 / 37.0
    return [_achado("M10_LUCKY_SETOR", "dois lucky da mesma rodada vizinhos na roda",
                    perto, len(dists), base, _p_ge(perto, len(dists), base))]


def M11_apos_zero(nums, bat, rod):
    """Depois do zero, vem multiplicador?"""
    p = sum(1 for x in bat if x) / max(1, len(bat))
    h = n = 0
    for i in range(len(nums) - 1):
        if nums[i] == 0:
            n += 1
            if bat[i + 1]:
                h += 1
    if n < 8:
        return []
    return [_achado("M11_APOS_ZERO", "multiplicador no giro após o zero",
                    h, n, p, _p_ge(h, n, p))]


def M12_intervalo_hits(nums, bat, rod):
    """Os intervalos entre multiplicadores batidos são geométricos?"""
    pos = [i for i, x in enumerate(bat) if x]
    if len(pos) < 15:
        return []
    gaps = [b - a for a, b in zip(pos, pos[1:])]
    med = sum(gaps) / len(gaps)
    var = sum((g - med) ** 2 for g in gaps) / len(gaps)
    # numa sequência sem memória a variância é ~med²
    disp = var / (med ** 2) if med else 0
    return [_achado("M12_INTERVALO_HITS",
                    f"intervalo entre multiplicadores: média {med:.1f}, "
                    f"dispersão {disp:.2f}",
                    len(pos), len(bat), None, None,
                    nota="dispersão ~1,0 = sem memória; >1,3 = vem em rajada")]


def M13_lucky_apos_hit(nums, bat, rod):
    """Depois que um lucky bate, ele volta a ser lucky logo?"""
    h = n = 0
    esp = 0.0
    for i in range(len(rod) - JANELA_DEPOIS):
        if not bat[i]:
            continue
        alvo = nums[i]
        n += 1
        for k in range(1, JANELA_DEPOIS + 1):
            if i + k < len(rod) and rod[i + k]:
                esp += len(rod[i + k]) / 37.0
        if any(alvo in {d.get("n") for d in rod[i + k]}
               for k in range(1, JANELA_DEPOIS + 1) if i + k < len(rod)):
            h += 1
    if n < 10:
        return []
    base = min(0.99, esp / n)
    return [_achado("M13_LUCKY_APOS_HIT",
                    f"o número que bateu voltou a ser lucky em {JANELA_DEPOIS} giros",
                    h, n, base, _p_ge(h, n, base))]


def M14_alto_depois_de_alto(nums, bat, rod):
    """Um multiplicador alto puxa outro alto (não só qualquer um)?"""
    altos = [i for i, luck in enumerate(rod)
             if any(d.get("x", 0) >= ALTO for d in luck)]
    if len(altos) < 12:
        return []
    tot_alto = len(altos)
    p = tot_alto / max(1, len(rod))
    p_jan = 1 - (1 - p) ** JANELA_DEPOIS
    s = set(altos)
    h = n = 0
    for i in altos:
        if i + JANELA_DEPOIS >= len(rod):
            continue
        n += 1
        if any((i + k) in s for k in range(1, JANELA_DEPOIS + 1)):
            h += 1
    if n < 8:
        return []
    return [_achado("M14_ALTO_PUXA_ALTO",
                    f"após um ≥{ALTO}x, veio outro ≥{ALTO}x em {JANELA_DEPOIS} giros",
                    h, n, p_jan, _p_ge(h, n, p_jan))]


def M15_valor_medio_desloca(nums, bat, rod):
    """O valor médio do multiplicador sobe antes de um hit?"""
    medias = []
    for luck in rod:
        vs = [d.get("x", 0) for d in luck if d.get("x")]
        medias.append(sum(vs) / len(vs) if vs else 0)
    pares = [(medias[i], bool(bat[i + 1]))
             for i in range(len(medias) - 1) if medias[i]]
    if len(pares) < 60:
        return []
    com = [m for m, ok in pares if ok]
    sem = [m for m, ok in pares if not ok]
    if len(com) < 8:
        return []
    mc = sum(com) / len(com)
    ms = sum(sem) / len(sem)
    rng = random.Random(31)
    vals = [m for m, _ in pares]
    flags = [ok for _, ok in pares]
    real = mc - ms
    piores = 0
    for _ in range(N_REGUA):
        rng.shuffle(vals)
        c = [v for v, f in zip(vals, flags) if f]
        s_ = [v for v, f in zip(vals, flags) if not f]
        if (sum(c) / len(c)) - (sum(s_) / len(s_)) >= real:
            piores += 1
    return [_achado("M15_VALOR_ANTES_DO_HIT",
                    f"multiplicador médio antes de bater {mc:.0f}x, "
                    f"nos demais {ms:.0f}x",
                    len(com), len(pares), None,
                    (piores + 1) / (N_REGUA + 1),
                    nota="régua de reordenação")]


AGENTES_M = [M01_seca_quebrada, M02_apos_alto, M03_par_igual,
             M04_repeticao_janela, M05_lucky_viciado, M06_lucky_repete,
             M07_lucky_sai_mais, M08_alto_agrupa, M09_quantos_lucky,
             M10_lucky_setor, M11_apos_zero, M12_intervalo_hits,
             M13_lucky_apos_hit, M14_alto_depois_de_alto,
             M15_valor_medio_desloca]


def cacar_multiplicadores(eventos: List[dict]) -> Dict[str, Any]:
    """Roda os quinze. Nada é descartado — cada achado sai com selo."""
    nums, bat, rod = extrair(eventos or [])
    if len(nums) < 60:
        return {"achados": [], "erro": "histórico curto", "n_giros": len(nums)}
    achados: List[dict] = []
    for ag in AGENTES_M:
        try:
            achados.extend(ag(nums, bat, rod) or [])
        except Exception as e:
            achados.append({"agente": getattr(ag, "__name__", "?"),
                            "achado": f"[erro: {type(e).__name__}]",
                            "hits": 0, "n": 0, "base": None, "razao": None,
                            "p": None, "alvos": [], "nota": ""})
    m = sum(1 for a in achados if a.get("p") is not None)
    for a in achados:
        a["selo"] = _selo(a.get("p"), m or 1)
    por = Counter(a["selo"] for a in achados)
    com_lucky = sum(1 for r in rod if r)
    return {"achados": achados,
            "confirmados": por[SELO_CONFIRMADO],
            "em_observacao": por[SELO_OBSERVACAO],
            "indicios": por[SELO_FRACO],
            "n_giros": len(nums),
            "n_hits": sum(1 for x in bat if x),
            "n_rodadas_com_lucky": com_lucky,
            "n_premiacoes": sum(len(r) for r in rod)}


def resumo_multiplicadores(r: Dict[str, Any]) -> str:
    if r.get("erro"):
        return f"[Multiplicadores] {r['erro']} ({r.get('n_giros', 0)} giros)"
    L = [f"[Multiplicadores] {r['confirmados']} confirmado(s), "
         f"{r['em_observacao']} em observação, {r['indicios']} indício(s) — "
         f"{r['n_premiacoes']} premiações em {r['n_giros']} giros "
         f"({r['n_hits']} bateram)"]
    if not r["n_premiacoes"]:
        L.append("   AVISO: nenhuma rodada de lucky no histórico. O dado completo")
        L.append("   só passa a ser gravado a partir desta versão — os agentes que")
        L.append("   dependem dele ficam mudos até a coleta acumular.")
    for a in r["achados"]:
        if a["selo"] == SELO_FRACO and a.get("p") is not None:
            continue
        marca = "✓" if a["selo"] == SELO_CONFIRMADO else "·"
        raz = f" {a['razao']:.2f}x" if a.get("razao") else ""
        pt = f" p={a['p']:.3f}" if a.get("p") is not None else ""
        L.append(f"   {marca} {a['achado']}: {a['hits']}/{a['n']}{raz}{pt}")
        if a.get("nota"):
            L.append(f"       {a['nota']}")
    return "\n".join(L)
