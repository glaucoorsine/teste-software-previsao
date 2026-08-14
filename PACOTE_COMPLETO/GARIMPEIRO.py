# -*- coding: utf-8 -*-
"""
GARIMPEIRO — procura sozinho o que prevê melhor.

    python GARIMPEIRO.py                 (usa os buffers de coleta)
    python GARIMPEIRO.py --jogo lightning --k 7

O que ele faz: monta dezenas de previsores a partir de peças simples, mede
todos, cruza os melhores entre si, e reporta o que rendeu — sempre num pedaço
do histórico que não participou da escolha.

POR QUE O PEDAÇO SEPARADO NÃO É FRESCURA
----------------------------------------
Garimpar é olhar muita coisa e ficar com a melhor. Quanto mais se olha, melhor
a melhor parece — mesmo quando não há ouro nenhum. Com 40 candidatos, o
primeiro colocado bate o acaso por sorte quase sempre.

Então o garimpo acontece nos primeiros 60% do histórico e a conferência nos
40% finais, que ficam lacrados. O número que sai é o que a mesa vai pagar, não
o que ficou bonito na peneira. Sem isso, este arquivo seria uma máquina de
fabricar esperança.

O QUE ELE CRUZA
---------------
Peças de percepção (faixa quente, recência, família do final, vizinhos na roda,
setor, atraso) combinadas por votação: cada peça vota nos seus números, os mais
votados viram a aposta. É a mesma ideia do consenso do motor, só que aqui ela é
testada em muitas combinações de uma vez, para descobrir QUAIS peças valem a
pena estar lá dentro.
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List, Tuple

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}
FAIXAS = [range(0, 10), range(10, 20), range(20, 30), range(30, 37)]


# --------------------------------------------------------------- as peças
# Cada peça devolve números com peso. Olham só o passado.
def p_recencia(h: List[int]) -> Dict[int, float]:
    c = Counter(h[-40:])
    return {n: v for n, v in c.items()}


def p_atraso(h: List[int]) -> Dict[int, float]:
    ult = {}
    for i, x in enumerate(h):
        ult[x] = i
    n = len(h)
    return {x: (n - ult.get(x, -60)) / 37.0 for x in range(37)}


def p_faixa_quente(h: List[int]) -> Dict[int, float]:
    c = Counter()
    for x in h[-12:]:
        for k, f in enumerate(FAIXAS):
            if x in f:
                c[k] += 1
    if not c:
        return {}
    q = [k for k, _ in c.most_common(2)]
    return {x: 1.0 for k in q for x in FAIXAS[k]}


def p_familia_final(h: List[int]) -> Dict[int, float]:
    if not h:
        return {}
    f = h[-1] % 10
    for g in ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9)):
        if f in g:
            return {y: 1.0 for y in range(37) if y % 10 in g}
    return {}


def p_vizinhos(h: List[int]) -> Dict[int, float]:
    if not h or h[-1] not in POS:
        return {}
    i = POS[h[-1]]
    return {RODA[(i + d) % 37]: 1.0 for d in (-3, -2, -1, 0, 1, 2, 3)}


def p_setor_quente(h: List[int]) -> Dict[int, float]:
    c = Counter()
    for x in h[-15:]:
        if x in POS:
            for d in range(-3, 4):
                c[RODA[(POS[x] + d) % 37]] += 1
    return dict(c)


def p_repetidos(h: List[int]) -> Dict[int, float]:
    c = Counter(h[-25:])
    return {n: v for n, v in c.items() if v >= 2}


def p_frios(h: List[int]) -> Dict[int, float]:
    c = Counter(h[-60:])
    return {x: 1.0 for x in range(37) if c.get(x, 0) == 0}


PECAS: Dict[str, Callable[[List[int]], Dict[int, float]]] = {
    "recência": p_recencia,
    "atraso": p_atraso,
    "faixa quente": p_faixa_quente,
    "família do final": p_familia_final,
    "vizinhos na roda": p_vizinhos,
    "setor quente": p_setor_quente,
    "repetidos": p_repetidos,
    "frios": p_frios,
}


def _normaliza(d: Dict[int, float]) -> Dict[int, float]:
    if not d:
        return {}
    m = max(d.values()) or 1.0
    return {k: v / m for k, v in d.items()}


def prever(h: List[int], nomes: Tuple[str, ...], k: int) -> List[int]:
    score: Counter = Counter()
    for nome in nomes:
        for n, v in _normaliza(PECAS[nome](h)).items():
            score[n] += v
    if not score:
        return []
    return [n for n, _ in score.most_common(k)]


def mede(seq: List[int], nomes: Tuple[str, ...], k: int,
         janela: int, ini: int, fim: int) -> Tuple[int, int, float]:
    h = n = 0
    for i in range(ini, fim):
        pick = prever(seq[:i + 1], nomes, k)
        if len(pick) < k:
            continue
        n += 1
        if any(x in set(pick) for x in seq[i + 1:i + 1 + janela]):
            h += 1
    acaso = 1 - (1 - k / 37.0) ** janela
    return h, n, acaso


def carregar(jogo: str) -> List[int]:
    from fluxo_captura import buffer_path, _purge_invalid
    d = json.loads(Path(buffer_path(jogo)).read_text(encoding="utf-8"))
    ev = sorted(_purge_invalid(d.get("events") or [], jogo),
                key=lambda e: e.get("settled") or "")
    return [int(e["valor"]) for e in ev
            if str(e.get("valor", "")).lstrip("-").isdigit()]


def garimpar(seq: List[int], k: int = 7, janela: int = 1,
             max_pecas: int = 3, top: int = 8) -> Dict:
    n_tot = len(seq)
    if n_tot < 250:
        return {"erro": f"histórico curto ({n_tot} giros) — precisa de 250+"}
    corte = 60 + int((n_tot - 60) * 0.60)

    combos = []
    for r in range(1, max_pecas + 1):
        combos.extend(itertools.combinations(PECAS.keys(), r))

    achados = []
    for c in combos:
        h, n, acaso = mede(seq, c, k, janela, 60, corte)
        if n < 40:
            continue
        achados.append({"pecas": c, "hits": h, "n": n,
                        "taxa": h / n, "acaso": acaso,
                        "razao": (h / n) / acaso})
    if not achados:
        return {"erro": "nenhuma combinação com ativação suficiente"}
    achados.sort(key=lambda d: -d["razao"])

    # conferência dos melhores, na parte lacrada
    conf = []
    for a in achados[:top]:
        h, n, acaso = mede(seq, a["pecas"], k, janela, corte, n_tot - janela)
        conf.append({**a, "c_hits": h, "c_n": n,
                     "c_taxa": (h / n) if n else 0.0,
                     "c_razao": ((h / n) / acaso) if n else 0.0})
    return {"corte": corte, "n_tot": n_tot, "k": k, "janela": janela,
            "n_combos": len(achados), "melhores": conf,
            "acaso": achados[0]["acaso"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jogo", default="lightning")
    ap.add_argument("--k", type=int, default=7)
    ap.add_argument("--janela", type=int, default=1)
    ap.add_argument("--pecas", type=int, default=3)
    a = ap.parse_args()

    seq = carregar(a.jogo)
    print(f"\n{'='*74}")
    print(f" GARIMPEIRO — {a.jogo}  ({len(seq)} giros)  "
          f"{a.k} números, janela {a.janela}")
    print(f"{'='*74}")
    r = garimpar(seq, a.k, a.janela, a.pecas)
    if r.get("erro"):
        print(f" {r['erro']}")
        return 1
    print(f" garimpo nos primeiros {r['corte']} giros, conferência nos "
          f"{r['n_tot'] - r['corte']} finais")
    print(f" {r['n_combos']} combinações testadas   ·   acaso = {r['acaso']:.1%}")
    print()
    print(f" {'peças':<44} {'garimpo':>14} {'conferência':>16}")
    print(" " + "-" * 72)
    for m in r["melhores"]:
        nomes = " + ".join(m["pecas"])
        if len(nomes) > 42:
            nomes = nomes[:41] + "…"
        print(f" {nomes:<44} {m['taxa']:>6.1%} {m['razao']:>5.2f}x "
              f"{m['c_taxa']:>7.1%} {m['c_razao']:>5.2f}x")
    print()
    melhor_conf = max(r["melhores"], key=lambda d: d["c_razao"])
    print(f" MELHOR NA CONFERÊNCIA (o que vale):")
    print(f"   {' + '.join(melhor_conf['pecas'])}")
    print(f"   {melhor_conf['c_hits']}/{melhor_conf['c_n']} = "
          f"{melhor_conf['c_taxa']:.1%}  contra {r['acaso']:.1%} de acaso  "
          f"= {melhor_conf['c_razao']:.2f}x")
    if melhor_conf["c_n"] < 40:
        print(f"   AVISO: só {melhor_conf['c_n']} ativações na conferência — "
              f"ainda não decide nada.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
