# -*- coding: utf-8 -*-
"""
TEORIAS DO OPERADOR — Crazy Time e multiplicadores.

Ditadas em 14/08/2026, palavras dele:

  1. "quando demora pra vir o 10 e de repente vem, logo depois ele sai de novo"
  2. "quando vem dois 10 ou dois bônus juntos, logo depois sai mais"
  3. "vem muito CashHunt junto, logo vem Crazy Time"
  4. "quando fica saindo muito um número, normalmente ele vem multiplicado"

POR QUE ISTO É UM ARQUIVO E NÃO UMA MEDIÇÃO
-------------------------------------------
Nos 203 giros limpos de Crazy Time que existiam quando ele ditou:
    dois 10 seguidos ....... 1 ocorrência
    dois bônus seguidos .... 1 ocorrência
    CrazyBonus ............. 1 aparição inteira
    seca >= 15 do 10 ....... 3 casos

Não há como decidir nada com isso. Estas teorias falam de eventos RAROS, e
evento raro não se testa com uma noite de mesa. A conta, para detectar 1,5x
com 80% de poder:

    dois bônus juntos puxam mais ......   66 horas de mesa
    10 volta depois de seca ...........  258 horas
    dois 10 juntos puxam mais .........  845 horas
    CashHunt puxa CrazyBonus .......... 1088 horas

Só a primeira é alcançável em prazo humano. As outras ficam aqui mesmo assim,
acumulando sozinhas: a mesa roda todo dia, e o contador não esquece. O erro
seria descartá-las por serem lentas — lento não é falso.

CADA TEORIA MEDE CONTRA A RODA REAL
-----------------------------------
54 fatias: 1=21, 2=13, 5=7, 10=4, CoinFlip=4, CashHunt=2, Pachinko=2,
CrazyBonus=1. A régua é essa, nunca "1 em 8".
"""
from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Dict, List, Optional

from .paths_dados import subdir

CT_FATIAS = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2, "CrazyBonus": 1}
CT_TOTAL = 54
CT_BONUS = {"CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"}

SECA_LONGA = 15      # "demora pra vir" — travado, não se ajusta depois
JANELA_DEPOIS = 6    # "logo depois" — travado


def _p_ge(h: int, n: int, p: float) -> float:
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1)
                        + k * math.log(p) + (n - k) * math.log(1 - p))
               for k in range(min(h, n), n + 1))


def _janela_tem(seq: List[str], i: int, alvo: set, j: int = JANELA_DEPOIS) -> bool:
    return any(x in alvo for x in seq[i + 1:i + 1 + j])


def _base_janela(p: float, j: int = JANELA_DEPOIS) -> float:
    """chance de o alvo aparecer em pelo menos um de j giros"""
    return 1 - (1 - p) ** j


# ------------------------------------------------------------------ teorias
def T1_dez_depois_da_seca(seq: List[str]) -> Dict[str, Any]:
    """O 10 sai depois de longa ausência — vem outro 10 logo em seguida?"""
    p = CT_FATIAS["10"] / CT_TOTAL
    alvo = {"10"}
    h = n = 0
    seca = 0
    for i, x in enumerate(seq):
        if x == "10":
            if seca >= SECA_LONGA:
                n += 1
                if _janela_tem(seq, i, alvo):
                    h += 1
            seca = 0
        else:
            seca += 1
    base = _base_janela(p)
    return {"id": "T1", "nome": f"10 volta em {JANELA_DEPOIS} giros, "
                                f"depois de seca >= {SECA_LONGA}",
            "hits": h, "n": n, "base": base,
            "razao": (h / n) / base if n else None,
            "p": _p_ge(h, n, base) if n else None}


def T2_par_puxa_mais(seq: List[str], quais: str = "10") -> Dict[str, Any]:
    """Vieram dois seguidos — vem mais logo depois?"""
    if quais == "10":
        alvo = {"10"}
        p = CT_FATIAS["10"] / CT_TOTAL
        rot = "dois 10 seguidos"
    else:
        alvo = set(CT_BONUS)
        p = sum(CT_FATIAS[s] for s in CT_BONUS) / CT_TOTAL
        rot = "dois bônus seguidos"
    h = n = 0
    for i in range(len(seq) - 1):
        if seq[i] in alvo and seq[i + 1] in alvo:
            n += 1
            if _janela_tem(seq, i + 1, alvo):
                h += 1
    base = _base_janela(p)
    return {"id": f"T2_{quais}", "nome": f"{rot} puxam mais em {JANELA_DEPOIS} giros",
            "hits": h, "n": n, "base": base,
            "razao": (h / n) / base if n else None,
            "p": _p_ge(h, n, base) if n else None}


def T3_cash_puxa_crazy(seq: List[str], min_cash: int = 2,
                       janela_antes: int = 10,
                       n_regua: int = 1500) -> Dict[str, Any]:
    """
    Muito CashHunt junto — vem CrazyBonus logo depois?

    A RÉGUA AQUI É REORDENAÇÃO, NÃO BINOMIAL.
    -----------------------------------------
    O gatilho desta teoria é "2+ CashHunt nos últimos 10 giros", que fica
    ligado por vários giros seguidos: um mesmo par de CashHunt dispara o
    gatilho dez vezes, e as dez janelas seguintes se sobrepõem quase inteiras.
    Tratar isso como dez ensaios independentes é o que quebra o teste
    binomial — medido: 10% de confirmação falsa em mesas honestas, contra os
    1,25% que a barra promete.

    Reordenar preserva quantos CashHunt e quantos CrazyBonus saíram e desfaz
    só a ordem. Se a proximidade entre eles for real, o embaralhado perde.
    """
    import random as _r
    h = n = 0

    def conta(s):
        a = b = 0
        for i in range(janela_antes, len(s) - JANELA_DEPOIS):
            if sum(1 for x in s[i - janela_antes:i + 1] if x == "CashHunt") >= min_cash:
                b += 1
                if any(y == "CrazyBonus" for y in s[i + 1:i + 1 + JANELA_DEPOIS]):
                    a += 1
        return a, b

    h, n = conta(seq)
    base = _base_janela(CT_FATIAS["CrazyBonus"] / CT_TOTAL)
    p = None
    if n:
        real = h / n
        rng = _r.Random(9091)
        copia = list(seq)
        piores = 0
        for _ in range(n_regua):
            rng.shuffle(copia)
            a2, b2 = conta(copia)
            if b2 and a2 / b2 >= real:
                piores += 1
        p = (piores + 1) / (n_regua + 1)
    return {"id": "T3", "nome": f"{min_cash}+ CashHunt em {janela_antes} giros "
                                f"puxa CrazyBonus",
            "hits": h, "n": n, "base": base,
            "razao": (h / n) / base if (n and base) else None,
            "p": p}


def T4_quente_vem_multiplicado(nums: List[int], teve_mult: List[bool],
                               limiar: int = 3, janela: int = 40) -> Dict[str, Any]:
    """
    ROLETA — número que vinha saindo muito tende a sair com multiplicador?

    A régua aqui não é a roda: é a taxa de multiplicador dos OUTROS giros da
    mesma sessão. Se o Lightning sorteia multiplicador sem olhar o histórico,
    as duas taxas têm que empatar.
    """
    a = na = b = nb = 0
    for i in range(janela, min(len(nums), len(teve_mult))):
        rec = Counter(nums[i - janela:i])
        if rec.get(nums[i], 0) >= limiar:
            na += 1
            a += 1 if teve_mult[i] else 0
        else:
            nb += 1
            b += 1 if teve_mult[i] else 0
    base = (b / nb) if nb else 0.0
    return {"id": "T4", "nome": f"número repetido ({limiar}+ em {janela}) "
                                f"vem com multiplicador",
            "hits": a, "n": na, "base": base,
            "razao": ((a / na) / base) if (na and base) else None,
            "p": _p_ge(a, na, base) if (na and base) else None}


# ------------------------------------------------------------- acumulação
def _arq(jogo: str):
    return subdir("teorias_operador") / f"{jogo}.json"


def _load(jogo: str) -> Dict[str, Any]:
    p = _arq(jogo)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(jogo: str, d) -> None:
    try:
        _arq(jogo).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                              encoding="utf-8")
    except Exception:
        pass


def avaliar_ct(seq: List[str]) -> List[Dict[str, Any]]:
    sim = [str(x) for x in (seq or []) if str(x) in CT_FATIAS]
    if len(sim) < 40:
        return []
    return [T1_dez_depois_da_seca(sim),
            T2_par_puxa_mais(sim, "10"),
            T2_par_puxa_mais(sim, "bonus"),
            T3_cash_puxa_crazy(sim)]


def resumo_ct(res: List[Dict[str, Any]]) -> str:
    if not res:
        return ""
    L = ["[Teorias do operador — Crazy Time]"]
    for r in res:
        if not r["n"]:
            L.append(f"   {r['nome']}: nenhuma ocorrência ainda")
            continue
        raz = f"{r['razao']:.2f}x" if r["razao"] is not None else "-"
        pt = f"p={r['p']:.3f}" if r["p"] is not None else "p=-"
        aviso = "  (amostra pequena)" if r["n"] < 25 else ""
        L.append(f"   {r['nome']}: {r['hits']}/{r['n']} "
                 f"(esperado {r['base']:.0%}) {raz} {pt}{aviso}")
    return "\n".join(L)
