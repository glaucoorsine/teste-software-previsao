# -*- coding: utf-8 -*-
"""
PROTOCOLO — a ordem em que as perguntas são feitas, decidida antes de olhar.

O CORTE CRONOLÓGICO
───────────────────
    DESCOBERTA   concursos    1 – 1948   (60%)   onde eu posso garimpar à vontade
    VALIDAÇÃO    concursos 1949 – 2597   (20%)   primeira confirmação
    TESTE        concursos 2598 – 3246   (20%)   a última, e só uma vez

O corte é cronológico e não aleatório porque a pergunta é sobre o FUTURO. Um
corte aleatório deixaria o modelo ver 2024 para prever 2015, e isso infla
qualquer resultado — é o vazamento temporal, o erro que mais produz "IA que
acerta loteria" na internet.

O CONTROLE NEGATIVO, QUE É O CORAÇÃO
────────────────────────────────────
Rodo a bateria inteira — os 689 testes — sobre 1.000 históricos que eu gerei
por acaso uniforme. Para cada um guardo o MAIOR |z| que a bateria produziu.
Isso me dá a distribuição do melhor achado possível num mundo sem padrão.

Daí saem dois p-valores para cada teste real, e a diferença entre eles é a lição
inteira deste estudo:

    p_isolado   com que frequência ESTE teste específico dá um |z| assim no
                acaso. É o p-valor que todo mundo publica.

    p_familia   com que frequência a bateria INTEIRA produz um |z| assim em
                ALGUM de seus 689 testes, no acaso. É o p-valor honesto de quem
                procurou em 689 lugares.

Um achado com p_isolado = 0,004 parece ouro. Se o p_familia dele for 0,93,
ele é o que se esperava encontrar procurando tanto — e reportá-lo como
descoberta seria fraude estatística, mesmo sem má-fé.
"""
from __future__ import annotations

import json
import time
from typing import Dict, List, Tuple

import numpy as np

from base import RESULTADOS, Historico, carregar, conferir_integridade, historia_falsa
from bateria import apenas_testes, bateria_completa, bateria_ranking

CORTES = {"descoberta": (0, 1948), "validacao": (1948, 2597), "teste": (2597, 3246)}
CONCURSOS_SUSPEITOS = (2425,)      # veio ordenado da fonte: sem ordem real de sorteio
N_FALSAS = 1000
SEMENTE = 20260903


def rodar(n_falsas: int = N_FALSAS, semente: int = SEMENTE) -> dict:
    rng = np.random.default_rng(semente)
    h = carregar()
    integridade = conferir_integridade(h)

    ini_t, fim_t = CORTES["teste"]
    real = bateria_completa(h, ini_t, fim_t, np.random.default_rng(semente),
                            excluir=CONCURSOS_SUSPEITOS)
    # o ranking também nas outras duas janelas, para o funil de três etapas
    ranking_por_janela = {}
    for nome, (a, b) in CORTES.items():
        ranking_por_janela[nome] = bateria_ranking(h, a, b,
                                                   np.random.default_rng(semente))

    chaves = sorted(apenas_testes(real))
    acum = {k: [] for k in chaves}
    maximos: List[float] = []
    t0 = time.time()
    for s in range(n_falsas):
        r_ = np.random.default_rng(semente + 1 + s)
        f = historia_falsa(h.T, r_)
        rf = apenas_testes(bateria_completa(f, ini_t, fim_t, r_))
        vals = []
        for k in chaves:
            v = abs(float(rf.get(k, 0.0)))
            acum[k].append(v)
            vals.append(v)
        maximos.append(max(vals))
    dur = time.time() - t0

    maximos_arr = np.array(maximos)
    veredicto = {}
    for k in chaves:
        z = float(real[k])
        a = np.array(acum[k])
        p_iso = float((a >= abs(z)).mean())
        p_fam = float((maximos_arr >= abs(z)).mean())
        veredicto[k] = {
            "z": z, "p_isolado": p_iso, "p_familia": p_fam,
            "nulo_p95": float(np.percentile(a, 95)),
            "sobrevive": bool(p_fam < 0.05),
        }

    return {
        "integridade": integridade,
        "protocolo": {
            "cortes": {k: [int(a), int(b)] for k, (a, b) in CORTES.items()},
            "n_testes_na_bateria": len(chaves),
            "n_historias_falsas": n_falsas,
            "segundos_controle_negativo": round(dur, 1),
            "concursos_excluidos_da_bateria_posicional": list(CONCURSOS_SUSPEITOS),
            "semente": semente,
        },
        "controle_negativo": {
            "max_z_media": float(maximos_arr.mean()),
            "max_z_p50": float(np.percentile(maximos_arr, 50)),
            "max_z_p95": float(np.percentile(maximos_arr, 95)),
            "max_z_p99": float(np.percentile(maximos_arr, 99)),
            "max_z_maximo": float(maximos_arr.max()),
            "amostra": [round(float(x), 3) for x in maximos_arr[:200]],
        },
        "real": {k: float(v) for k, v in real.items()},
        "veredicto": veredicto,
        "ranking_por_janela": {a: {k: float(v) for k, v in b.items()}
                               for a, b in ranking_por_janela.items()},
    }


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else N_FALSAS
    res = rodar(n)
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "protocolo.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    cn = res["controle_negativo"]
    print(f"controle negativo: max|z| mediano {cn['max_z_p50']:.2f} | "
          f"p95 {cn['max_z_p95']:.2f} | p99 {cn['max_z_p99']:.2f}")
    vivos = [k for k, v in res["veredicto"].items() if v["sobrevive"]]
    print(f"testes que sobrevivem ao controle negativo: {len(vivos)}")
    for k in vivos:
        v = res["veredicto"][k]
        print(f"   {k}: z={v['z']:+.2f} p_iso={v['p_isolado']:.4f} p_fam={v['p_familia']:.4f}")
