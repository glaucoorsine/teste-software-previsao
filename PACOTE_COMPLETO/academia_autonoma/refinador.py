# -*- coding: utf-8 -*-
"""
REFINADOR — pega uma teoria e a torna melhor.

A academia tinha só um movimento: julgar. Uma teoria chegava, era medida, e
saía carimbada de boa ou fraca. Faltava o movimento que importa para quem quer
subir a taxa de acerto — pegar uma teoria mediana e AFINAR até ela render.

Uma regra quase nunca funciona em todo lugar. Ela funciona quando a mesa está
de um certo jeito. "Família do final puxa família do final" pode render 19% em
geral e 31% quando a faixa está concentrada — e aí a teoria não é fraca, é uma
teoria boa sendo usada na hora errada. Encontrar essa hora é refinar.

COMO REFINA
-----------
Para cada condição candidata, mede a teoria SÓ nos giros em que a condição
vale. Se o acerto sobe e sobra ativação suficiente, a condição entra.

O QUE IMPEDE DE VIRAR FANTASIA
------------------------------
Procurar a condição que mais ajuda é procurar entre muitas — e a que mais
ajuda sempre parece ótima no dado onde foi encontrada. Por isso o refinamento
é feito numa metade e o ganho é reportado na OUTRA, que não participou da
busca. O número que sai é o que se espera na mesa ao vivo, não o que ficou
bonito no ajuste.

Isso não é ceticismo: é a diferença entre entregar 31% que se repete e 31%
que vira 19% quando a mesa liga.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}
FAIXAS = [range(0, 10), range(10, 20), range(20, 30), range(30, 37)]
VERMELHOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}

MIN_ATIVACOES = 25          # abaixo disto uma condição não se avalia


# ------------------------------------------------------- condições candidatas
# Cada uma responde: "a mesa está deste jeito agora?" olhando só o passado.
def _c_faixa_concentrada(h: List[int]) -> bool:
    """as últimas 12 rodadas estão concentradas em poucas faixas"""
    if len(h) < 12:
        return False
    c = Counter()
    for x in h[-12:]:
        for k, f in enumerate(FAIXAS):
            if x in f:
                c[k] += 1
    return c.most_common(1)[0][1] >= 6


def _c_faixa_espalhada(h: List[int]) -> bool:
    if len(h) < 12:
        return False
    c = Counter()
    for x in h[-12:]:
        for k, f in enumerate(FAIXAS):
            if x in f:
                c[k] += 1
    return c.most_common(1)[0][1] <= 4


def _c_repetiu_recente(h: List[int]) -> bool:
    """algum número saiu duas vezes nos últimos 10"""
    return len(h) >= 10 and max(Counter(h[-10:]).values()) >= 2


def _c_sem_repeticao(h: List[int]) -> bool:
    return len(h) >= 10 and max(Counter(h[-10:]).values()) == 1


def _c_setor_quente(h: List[int]) -> bool:
    """metade da roda concentrou as últimas 10"""
    if len(h) < 10:
        return False
    lados = Counter(1 if POS.get(x, 0) < 18 else 2 for x in h[-10:])
    return lados.most_common(1)[0][1] >= 7


def _c_zero_recente(h: List[int]) -> bool:
    return 0 in h[-12:]


def _c_sem_zero(h: List[int]) -> bool:
    return 0 not in h[-25:]


def _c_cor_desbalanceada(h: List[int]) -> bool:
    if len(h) < 12:
        return False
    v = sum(1 for x in h[-12:] if x in VERMELHOS)
    return v >= 9 or v <= 3


def _c_muitos_altos(h: List[int]) -> bool:
    return len(h) >= 10 and sum(1 for x in h[-10:] if x >= 19) >= 7


def _c_muitos_baixos(h: List[int]) -> bool:
    return len(h) >= 10 and sum(1 for x in h[-10:] if 1 <= x <= 18) >= 7


CONDICOES: Dict[str, Callable[[List[int]], bool]] = {
    "faixa concentrada": _c_faixa_concentrada,
    "faixa espalhada": _c_faixa_espalhada,
    "houve repetição recente": _c_repetiu_recente,
    "sem repetição recente": _c_sem_repeticao,
    "setor da roda quente": _c_setor_quente,
    "zero saiu há pouco": _c_zero_recente,
    "zero ausente há 25": _c_sem_zero,
    "cor desbalanceada": _c_cor_desbalanceada,
    "dominam os altos": _c_muitos_altos,
    "dominam os baixos": _c_muitos_baixos,
}


def _mede(seq: List[int], prever: Callable[[List[int]], List[int]],
          cond: Optional[Callable[[List[int]], bool]],
          janela: int = 1, ini: int = 60,
          fim: Optional[int] = None) -> Tuple[int, int, float]:
    """(acertos, ativações, acaso) da teoria, opcionalmente sob a condição."""
    fim = fim if fim is not None else len(seq) - janela
    h = n = 0
    esp = 0.0
    for i in range(ini, fim):
        hist = seq[:i + 1]
        if cond is not None and not cond(hist):
            continue
        pick = prever(hist)
        if not pick:
            continue
        n += 1
        alvo = set(pick)
        esp += 1 - (1 - len(alvo) / 37.0) ** janela
        if any(x in alvo for x in seq[i + 1:i + 1 + janela]):
            h += 1
    return h, n, (esp / n if n else 0.0)


def refinar(seq: List[int], prever: Callable[[List[int]], List[int]],
            janela: int = 1, nome: str = "teoria") -> Dict[str, Any]:
    """
    Procura a condição que melhora a teoria, e diz quanto ela melhora FORA
    do pedaço onde foi procurada.

    A busca acontece na primeira metade; a conferência, na segunda.
    """
    n_tot = len(seq)
    if n_tot < 200:
        return {"nome": nome, "erro": f"histórico curto ({n_tot} giros)"}
    corte = 60 + (n_tot - 60) // 2

    h0, n0, a0 = _mede(seq, prever, None, janela, 60, n_tot - janela)
    base_geral = (h0 / n0) if n0 else 0.0

    # --- busca: só na primeira metade
    achados = []
    for nome_c, cond in CONDICOES.items():
        hf, nf, af = _mede(seq, prever, cond, janela, 60, corte)
        if nf < MIN_ATIVACOES:
            continue
        achados.append({"condicao": nome_c, "cond": cond,
                        "hits": hf, "n": nf, "taxa": hf / nf, "acaso": af,
                        "razao": (hf / nf) / af if af else 0.0})
    if not achados:
        return {"nome": nome, "erro": "nenhuma condição com ativação suficiente",
                "geral": {"hits": h0, "n": n0, "taxa": base_geral, "acaso": a0}}

    achados.sort(key=lambda d: -d["razao"])
    melhor = achados[0]

    # --- conferência: na metade que não participou da busca
    hv, nv, av = _mede(seq, prever, melhor["cond"], janela, corte, n_tot - janela)
    hg, ng, ag = _mede(seq, prever, None, janela, corte, n_tot - janela)

    return {
        "nome": nome,
        "geral": {"hits": h0, "n": n0, "taxa": base_geral, "acaso": a0,
                  "razao": base_geral / a0 if a0 else 0.0},
        "condicao": melhor["condicao"],
        "no_ajuste": {"hits": melhor["hits"], "n": melhor["n"],
                      "taxa": melhor["taxa"], "acaso": melhor["acaso"],
                      "razao": melhor["razao"]},
        "na_conferencia": {"hits": hv, "n": nv,
                           "taxa": (hv / nv) if nv else 0.0, "acaso": av,
                           "razao": ((hv / nv) / av) if (nv and av) else 0.0},
        "sem_condicao_na_conferencia": {
            "hits": hg, "n": ng, "taxa": (hg / ng) if ng else 0.0,
            "acaso": ag, "razao": ((hg / ng) / ag) if (ng and ag) else 0.0},
        "todas": [{k: v for k, v in a.items() if k != "cond"} for a in achados],
    }


def resumo(r: Dict[str, Any]) -> str:
    if r.get("erro") and not r.get("geral"):
        return f"[Refinador] {r['nome']}: {r['erro']}"
    L = [f"[Refinador] {r['nome']}"]
    g = r["geral"]
    L.append(f"   sem condição: {g['hits']}/{g['n']} = {g['taxa']:.1%} "
             f"(acaso {g['acaso']:.1%}) {g['razao']:.2f}x")
    if r.get("erro"):
        L.append(f"   {r['erro']}")
        return "\n".join(L)
    a, v = r["no_ajuste"], r["na_conferencia"]
    s = r["sem_condicao_na_conferencia"]
    L.append(f"   melhor condição: {r['condicao']}")
    L.append(f"      no ajuste     {a['hits']}/{a['n']} = {a['taxa']:.1%} "
             f"{a['razao']:.2f}x")
    L.append(f"      na conferência {v['hits']}/{v['n']} = {v['taxa']:.1%} "
             f"{v['razao']:.2f}x   <- o que vale")
    L.append(f"      (sem condição, mesma metade: {s['taxa']:.1%} {s['razao']:.2f}x)")
    ganho = v["razao"] - s["razao"]
    if v["n"] < MIN_ATIVACOES:
        L.append(f"      ainda sem ativação suficiente na conferência ({v['n']})")
    elif ganho > 0.05:
        L.append(f"      GANHO CONFIRMADO: +{ganho:.2f}x sobre a teoria solta")
    else:
        L.append(f"      a condição não segurou fora do ajuste ({ganho:+.2f}x)")
    return "\n".join(L)
