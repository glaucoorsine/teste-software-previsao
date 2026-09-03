# -*- coding: utf-8 -*-
"""
PERSISTÊNCIA — o único achado do estudo que sobreviveu, e o tamanho dele.

O QUE APARECEU
──────────────
As 25 dezenas NÃO saem com a mesma frequência em 3.246 concursos: χ² = 56,38
com 24 graus de liberdade. E — o que importa muito mais — o desvio SE REPETE em
janelas cronológicas que não se tocam. As dezenas que estavam acima da média
entre 2003 e 2015 continuaram acima entre 2016 e 2020, e de novo entre 2021 e
2024.

Repetição fora da amostra é a única coisa que separa achado de coincidência, e é
por isso que este arquivo existe separado dos outros. Aqui eu não procuro mais
nada: eu pego a única coisa que sobreviveu e tento matá-la de todas as formas
que eu conheço.

O QUE ISTO NÃO É
────────────────
Não é uma vantagem de aposta, e o número que prova isso está calculado aqui
embaixo: apostar as 15 dezenas historicamente mais frequentes rende 9,07
acertos por jogo contra 9,00 do acaso. São sete centésimos de acerto. A faixa
de prêmio mais baixa da Lotofácil começa em 11 acertos, e nenhum arredondamento
de 9,07 chega perto disso. O efeito é REAL e é IRRELEVANTE para apostar —
as duas coisas ao mesmo tempo, e é exatamente esse par que interessa a um
projeto científico.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

import numpy as np

from base import DP_INTER, RESULTADOS, SORTEADAS, UNIVERSO, carregar, historia_falsa

P = SORTEADAS / UNIVERSO
JANELAS = {"descoberta": (0, 1948), "validacao": (1948, 2597), "teste": (2597, 3246)}


def z_frequencia(M: np.ndarray) -> np.ndarray:
    T = len(M)
    return (M.sum(axis=0) - T * P) / np.sqrt(T * P * (1 - P))


def estatisticas(M_por_janela: Dict[str, np.ndarray]) -> Dict[str, float]:
    """As três medidas que definem o achado. Idênticas no real e no falso."""
    zs = {k: z_frequencia(v) for k, v in M_por_janela.items()}
    todo = np.vstack(list(M_por_janela.values()))
    out = {"chi2_total": float((z_frequencia(todo) ** 2).sum())}
    for k, v in zs.items():
        out[f"chi2_{k}"] = float((v ** 2).sum())
    pares = [("descoberta", "validacao"), ("descoberta", "teste"), ("validacao", "teste")]
    rs = [float(np.corrcoef(zs[a], zs[b])[0, 1]) for a, b in pares]
    for (a, b), r in zip(pares, rs):
        out[f"r_{a}_x_{b}"] = r
    out["r_media"] = float(np.mean(rs))
    # a medida que interessa na prática: apostar o topo/base da descoberta
    topo = np.argsort(-M_por_janela["descoberta"].sum(axis=0))[:SORTEADAS]
    base_ = np.argsort(M_por_janela["descoberta"].sum(axis=0))[:SORTEADAS]
    fora = np.vstack([M_por_janela["validacao"], M_por_janela["teste"]])
    n = len(fora)
    a_topo = fora[:, topo].sum(axis=1).mean()
    a_base = fora[:, base_].sum(axis=1).mean()
    out["acertos_quentes_fora_da_amostra"] = float(a_topo)
    out["acertos_frios_fora_da_amostra"] = float(a_base)
    out["z_quentes"] = float((a_topo - 9.0) * np.sqrt(n) / DP_INTER)
    out["z_frios"] = float((a_base - 9.0) * np.sqrt(n) / DP_INTER)
    out["separacao_quente_menos_frio"] = float(a_topo - a_base)
    return out


def hipotese_da_tinta(M: np.ndarray) -> Dict[str, float]:
    """A bola com mais tinta é mais pesada? — a única explicação física testável.

    Se houvesse viés mecânico, a causa mais citada na literatura de loterias
    físicas é massa: bolas com mais tinta impressa pesam um pouco mais e tendem
    a ficar no fundo. Na Lotofácil isso tem uma forma testável e barata: as
    dezenas 1 a 9 têm UM algarismo e as 10 a 25 têm DOIS. Se a tinta importasse,
    o grupo de dois algarismos sairia menos (mais pesadas, afundam) ou mais,
    conforme o mecanismo — mas sairia DIFERENTE, e de forma consistente.

    Uso também a soma dos algarismos como medida contínua de "quantidade de
    tinta", que separa o 11 (dois traços finos) do 28 (dois algarismos cheios).
    """
    z = z_frequencia(M)
    dois = np.array([n >= 10 for n in range(1, 26)])
    tinta = np.array([sum(int(c) for c in str(n)) for n in range(1, 26)], dtype=float)
    n1, n2 = int((~dois).sum()), int(dois.sum())
    dif = float(z[dois].mean() - z[~dois].mean())
    # sob o nulo os 25 z são ~N(0,1) com soma zero; a diferença de médias tem
    # variância 1/n1 + 1/n2 corrigida pela restrição de soma
    dp = float(np.sqrt(1 / n1 + 1 / n2))
    return {
        "z_medio_um_algarismo": float(z[~dois].mean()),
        "z_medio_dois_algarismos": float(z[dois].mean()),
        "diferenca": dif, "z_da_diferenca": dif / dp,
        "correlacao_z_com_soma_dos_algarismos": float(np.corrcoef(z, tinta)[0, 1]),
        "correlacao_z_com_o_proprio_numero": float(np.corrcoef(z, np.arange(1, 26))[0, 1]),
    }


def rodar(n_falsas: int = 4000, semente: int = 20260903) -> dict:
    h = carregar()
    reais = {k: h.matriz[a:b] for k, (a, b) in JANELAS.items()}
    obs = estatisticas(reais)
    obs_tinta = hipotese_da_tinta(h.matriz)

    rng = np.random.default_rng(semente)
    acum: Dict[str, List[float]] = {k: [] for k in obs}
    tam = [b - a for a, b in JANELAS.values()]
    for _ in range(n_falsas):
        f = historia_falsa(h.T, rng)
        fj = {k: f.matriz[a:b] for k, (a, b) in JANELAS.items()}
        e = estatisticas(fj)
        for k in obs:
            acum[k].append(e[k])

    ver = {}
    for k, v in obs.items():
        a = np.array(acum[k])
        maior = float((a >= v).mean())
        menor = float((a <= v).mean())
        ver[k] = {
            "observado": v, "nulo_media": float(a.mean()), "nulo_dp": float(a.std(ddof=1)),
            "nulo_p95": float(np.percentile(a, 95)), "nulo_p05": float(np.percentile(a, 5)),
            "p_unilateral_maior": maior, "p_unilateral_menor": menor,
            "p_bilateral": float(min(1.0, 2 * min(maior, menor))),
        }
    return {"n_historias_falsas": n_falsas, "janelas": {k: list(v) for k, v in JANELAS.items()},
            "veredicto": ver, "hipotese_da_tinta": obs_tinta,
            "frequencias": {str(i + 1): int(h.matriz[:, i].sum()) for i in range(UNIVERSO)},
            "z_por_dezena": {k: z_frequencia(v).tolist() for k, v in reais.items()},
            "z_total": z_frequencia(h.matriz).tolist()}


if __name__ == "__main__":
    r = rodar()
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "persistencia.json").write_text(
        json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{'estatistica':<38}{'obs':>9}{'nulo':>9}{'p95':>9}{'p':>10}")
    for k, v in r["veredicto"].items():
        p = min(v["p_unilateral_maior"], v["p_unilateral_menor"])
        print(f"{k:<38}{v['observado']:>9.3f}{v['nulo_media']:>9.3f}"
              f"{v['nulo_p95']:>9.3f}{p:>10.4f}")
    print("\nhipotese da tinta (1 vs 2 algarismos):")
    for k, v in r["hipotese_da_tinta"].items():
        print(f"   {k:<42}{v:+.4f}")
