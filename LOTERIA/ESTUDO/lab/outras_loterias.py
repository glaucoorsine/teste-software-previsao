# -*- coding: utf-8 -*-
"""
OUTRAS LOTERIAS — o teste que decide se o desvio da Lotofácil é físico.

O RACIOCÍNIO
────────────
O capítulo 7 encontrou um desvio de frequência na Lotofácil que se repete em
janelas independentes. Restam duas explicações e elas fazem previsões
diferentes:

    FÍSICA        alguma coisa no equipamento — bola, globo, carregamento.
                  Então as OUTRAS loterias da Caixa, que usam globos e bolas de
                  fabricação parecida, deveriam mostrar algo análogo.

    COINCIDÊNCIA  o desvio é o extremo esperado de uma busca grande. Então as
                  outras loterias não vão mostrar nada, e a Lotofácil vira o
                  extremo de uma amostra de nove.

Este arquivo faz esse teste. Ele roda EXATAMENTE a mesma medida — χ² de
uniformidade com a variância binomial correta, mais a replicação entre janelas
cronológicas — em todas as modalidades que cabem no molde "escolher k de N".

E ele tem um segundo uso, mais importante que o primeiro: as nove modalidades
formam uma amostra. Se a Lotofácil for a única com desvio entre nove testes
independentes, o p-valor dela precisa ser multiplicado por nove. Nove testes é
uma busca pequena, mas é uma busca — e o capítulo 2 vale para mim também.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from base import RESULTADOS

FONTE = Path("/home/user/guilhermeasn/loteria.json/data")

# chave: (arquivo, nome, N, k, primeiro_numero, quantos_usar_da_linha, sorteios_por_linha)
MODALIDADES = [
    ("lotofacil",      "Lotofácil",     25, 15, 1, 15, 1),
    ("megasena",       "Mega-Sena",     60,  6, 1,  6, 1),
    ("quina",          "Quina",         80,  5, 1,  5, 1),
    ("lotomania",      "Lotomania",    100, 20, 0, 20, 1),
    ("duplasena",      "Dupla Sena",    50,  6, 1, 12, 2),
    ("timemania",      "Timemania",     80,  7, 1,  7, 1),
    ("diadesorte",     "Dia de Sorte",  31,  7, 1,  7, 1),
    ("maismilionaria", "+Milionária",   50,  6, 1,  6, 1),
]


def carregar(chave: str, N: int, k: int, primeiro: int, usar: int,
             por_linha: int) -> np.ndarray:
    """Devolve matriz (T, N) de 0/1. Dupla Sena vira dois sorteios por concurso."""
    cru = json.loads((FONTE / f"{chave}.json").read_text(encoding="utf-8"))
    ks = sorted(int(x) for x in cru)
    linhas: List[List[int]] = []
    for c in ks:
        v = cru[str(c)][:usar]
        try:
            nums = [int(x) for x in v]
        except ValueError:
            continue
        for s in range(por_linha):
            bloco = nums[s * k:(s + 1) * k]
            if len(bloco) == k and len(set(bloco)) == k:
                linhas.append(bloco)
    M = np.zeros((len(linhas), N), dtype=np.int8)
    for i, b in enumerate(linhas):
        for x in b:
            M[i, x - primeiro] = 1
    return M


def z_freq(M: np.ndarray, p: float) -> np.ndarray:
    T = len(M)
    return (M.sum(axis=0) - T * p) / np.sqrt(T * p * (1 - p))


def medir(M: np.ndarray, N: int, k: int) -> Dict[str, float]:
    p = k / N
    T = len(M)
    a, b = int(T * 0.6), int(T * 0.8)
    zs = [z_freq(M[:a], p), z_freq(M[a:b], p), z_freq(M[b:], p)]
    rs = [float(np.corrcoef(zs[i], zs[j])[0, 1]) for i, j in ((0, 1), (0, 2), (1, 2))]
    return {"chi2": float((z_freq(M, p) ** 2).sum()), "df": N - 1,
            "r_media": float(np.mean(rs)), "T": T}


def sorteios_falsos(N: int, k: int, T: int, rng) -> np.ndarray:
    """T sorteios uniformes de k em N, de uma vez só.

    Vetorizar isto é o que permite 2.000 réplicas por modalidade em vez de 400:
    ordenar T×N números ao acaso e pegar os k menores de cada linha é
    matematicamente idêntico a sortear sem reposição, e roda em uma chamada.
    """
    R = rng.random((T, N))
    idx = np.argpartition(R, k, axis=1)[:, :k]
    M = np.zeros((T, N), dtype=np.int8)
    np.put_along_axis(M, idx, 1, axis=1)
    return M


def controle(N: int, k: int, T: int, n: int, rng) -> Tuple[np.ndarray, np.ndarray]:
    chi, rm = np.empty(n), np.empty(n)
    for i in range(n):
        r = medir(sorteios_falsos(N, k, T, rng), N, k)
        chi[i], rm[i] = r["chi2"], r["r_media"]
    return chi, rm


def super_sete(n: int, rng) -> Dict[str, float]:
    """Sete colunas de 0 a 9 — não é 'escolher k de N', então tem molde próprio."""
    cru = json.loads((FONTE / "supersete.json").read_text(encoding="utf-8"))
    ks = sorted(int(x) for x in cru)
    A = np.array([[int(d) for d in cru[str(c)]] for c in ks])
    T = len(A)
    chi = 0.0
    for col in range(7):
        cont = np.bincount(A[:, col], minlength=10)
        chi += float(((cont - T / 10) ** 2 / (T / 10)).sum())
    df = 7 * 9
    sim = np.empty(n)
    for i in range(n):
        B = rng.integers(0, 10, size=(T, 7))
        s = 0.0
        for col in range(7):
            cont = np.bincount(B[:, col], minlength=10)
            s += float(((cont - T / 10) ** 2 / (T / 10)).sum())
        sim[i] = s
    return {"nome": "Super Sete", "T": T, "chi2": chi, "df": df,
            "p_chi2": float((sim >= chi).mean()),
            "nota": "7 colunas independentes de 0 a 9; 70 células, 63 graus"}


def rodar(n_falsas: int = 2000, semente: int = 20260903) -> dict:
    rng = np.random.default_rng(semente)
    out = []
    for chave, nome, N, k, prim, usar, por in MODALIDADES:
        M = carregar(chave, N, k, prim, usar, por)
        r = medir(M, N, k)
        chi_n, rm_n = controle(N, k, r["T"], n_falsas, rng)
        out.append({
            "chave": chave, "nome": nome, "N": N, "k": k,
            "p": k / N, "T_sorteios": r["T"],
            "chi2": r["chi2"], "df": r["df"],
            "chi2_nulo_medio": float(chi_n.mean()),
            "chi2_nulo_p95": float(np.percentile(chi_n, 95)),
            "p_chi2": float((chi_n >= r["chi2"]).mean()),
            "r_media": r["r_media"],
            "r_nulo_medio": float(rm_n.mean()),
            "r_nulo_p95": float(np.percentile(rm_n, 95)),
            "p_r": float((rm_n >= r["r_media"]).mean()),
        })
    # resolução: menor desvio RELATIVO por dezena que cada modalidade consegue
    # enxergar. É o que separa "não há efeito" de "não haveria como ver".
    for m in out:
        pp, T = m["p"], m["T_sorteios"]
        m["resolucao_relativa"] = float(np.sqrt((1 - pp) / (T * pp)))
    ref = [m for m in out if m["chave"] == "lotofacil"][0]["resolucao_relativa"]
    for m in out:
        m["quantas_vezes_menos_sensivel_que_a_lotofacil"] = m["resolucao_relativa"] / ref

    def fisher(chaves, campo):
        ps = [max(m[campo], 1.0 / n_falsas) for m in out if m["chave"] in chaves]
        X = -2 * sum(np.log(x) for x in ps)
        gl = 2 * len(ps)
        # sobrevivência do χ² com gl graus, sem scipy
        from math import exp, lgamma
        k = gl // 2
        s_ = sum(exp(-X / 2 + i * np.log(X / 2) - lgamma(i + 1)) for i in range(k))
        return {"X2": float(X), "df": gl, "p": float(min(1.0, s_)), "n": len(ps)}

    todas = {m["chave"] for m in out}
    sem_lf = todas - {"lotofacil"}
    return {"n_falsas": n_falsas, "modalidades": out,
            "super_sete": super_sete(n_falsas, rng),
            "fisher": {
                "todas_persistencia": fisher(todas, "p_r"),
                "todas_uniformidade": fisher(todas, "p_chi2"),
                "sem_lotofacil_persistencia": fisher(sem_lf, "p_r"),
                "sem_lotofacil_uniformidade": fisher(sem_lf, "p_chi2"),
            }}


if __name__ == "__main__":
    r = rodar()
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "outras_loterias.json").write_text(
        json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{'modalidade':<15}{'N/k':>8}{'sorteios':>10}{'chi2':>9}{'df':>5}"
          f"{'p(chi2)':>9}{'r':>8}{'p(r)':>8}")
    for m in r["modalidades"]:
        print(f"{m['nome']:<15}{f'{m[chr(78)]}/{m[chr(107)]}':>8}{m['T_sorteios']:>10}"
              f"{m['chi2']:>9.1f}{m['df']:>5}{m['p_chi2']:>9.4f}"
              f"{m['r_media']:>+8.3f}{m['p_r']:>8.4f}")
    s = r["super_sete"]
    print(f"{s['nome']:<15}{'7x10':>8}{s['T']:>10}{s['chi2']:>9.1f}{s['df']:>5}{s['p_chi2']:>9.4f}")
