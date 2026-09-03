# -*- coding: utf-8 -*-
"""
ASSERTIVIDADE — onde existe taxa de acerto alta, e por que ela não é vantagem.

O PEDIDO QUE ORIGINOU ESTE ARQUIVO
──────────────────────────────────
    "não quero o padrão que ganha, mas o que tiver uma taxa de assertividade
     boa, pra acrescentar na teoria do projeto científico"

O pedido é bom e tem resposta — mas a resposta tem duas metades, e separá-las é
o achado principal do estudo todo:

    ASSERTIVIDADE   com que frequência a regra acerta.
    GANHO (lift)    quanto ela acerta acima do que o seu próprio tamanho já
                    garantiria.

E existe um teorema que amarra as duas na Lotofácil, que eu demonstro aqui por
ENUMERAÇÃO COMPLETA, não por simulação:

    Se os sorteios são uniformes sobre as 3.268.760 combinações, então para
    QUALQUER regra estrutural R:

              assertividade(R) = fração do espaço que R ocupa
              ganho(R) = 1,000 exatamente

Uma regra que acerta 95% dos concursos acerta porque ocupa 95% do espaço. Não
há regra estrutural com assertividade alta E espaço pequeno — a não ser que os
sorteios NÃO sejam uniformes, e é exatamente isso que este arquivo mede.

POR QUE ENUMERAR TUDO EM VEZ DE SIMULAR
───────────────────────────────────────
C(25,15) = 3.268.760. Cabe na memória. Então eu não preciso estimar a
probabilidade de "soma entre 166 e 224": eu CONTO quantas das 3.268.760
combinações satisfazem, e divido. O resultado é exato, reproduzível e não tem
barra de erro. Nenhuma loteria maior permite isso — na Mega-Sena seriam 50
milhões de combinações por faixa e o mesmo truque fica caro. A Lotofácil é
pequena o bastante para ser resolvida, e grande o bastante para ser
interessante. É a loteria certa para um estudo assim.
"""
from __future__ import annotations

import itertools
import json
from typing import Callable, Dict, List, Tuple

import numpy as np

from base import (FIBONACCI, MIOLO, MOLDURA, PRIMOS, RESULTADOS, SORTEADAS,
                  UNIVERSO, Historico, carregar, coluna, linha)

TOTAL = 3268760          # C(25,15)


def enumerar() -> np.ndarray:
    it = itertools.chain.from_iterable(
        itertools.combinations(range(1, UNIVERSO + 1), SORTEADAS))
    return np.fromiter(it, dtype=np.int8, count=TOTAL * SORTEADAS
                       ).reshape(TOTAL, SORTEADAS)


def caracteristicas(C: np.ndarray) -> Dict[str, np.ndarray]:
    """As mesmas medidas do histórico, agora sobre TODO o espaço possível."""
    Ci = C.astype(np.int16)
    ehpar = (Ci % 2 == 0)
    tab_primo = np.zeros(26, dtype=bool); tab_primo[list(PRIMOS)] = True
    tab_fib = np.zeros(26, dtype=bool); tab_fib[list(FIBONACCI)] = True
    tab_mold = np.zeros(26, dtype=bool); tab_mold[list(MOLDURA)] = True
    dif = np.diff(Ci, axis=1)
    lin = np.zeros((len(C), 5), dtype=np.int8)
    col = np.zeros((len(C), 5), dtype=np.int8)
    for k in range(5):
        lin[:, k] = ((Ci >= 5 * k + 1) & (Ci <= 5 * k + 5)).sum(axis=1)
        col[:, k] = ((Ci % 5) == ((k + 1) % 5)).sum(axis=1)
    tab_m3 = np.zeros(26, dtype=bool); tab_m3[[n for n in range(1,26) if n % 3 == 0]] = True
    tab_m5 = np.zeros(26, dtype=bool); tab_m5[[n for n in range(1,26) if n % 5 == 0]] = True
    seq = np.ones(len(C), dtype=np.int8); atual = np.ones(len(C), dtype=np.int8)
    for j in range(dif.shape[1]):
        atual = np.where(dif[:, j] == 1, atual + 1, 1)
        seq = np.maximum(seq, atual)
    finais = np.zeros(len(C), dtype=np.int8)
    for d in range(10):
        finais += ((Ci % 10) == d).any(axis=1)
    return {
        "soma": Ci.sum(axis=1).astype(np.int16),
        "mult3": tab_m3[Ci].sum(axis=1).astype(np.int8),
        "mult5": tab_m5[Ci].sum(axis=1).astype(np.int8),
        "seq_max": seq,
        "finais": finais,
        "altas": (Ci > 13).sum(axis=1).astype(np.int8),
        "um_digito": (Ci <= 9).sum(axis=1).astype(np.int8),
        "pares": ehpar.sum(axis=1).astype(np.int8),
        "primos": tab_primo[Ci].sum(axis=1).astype(np.int8),
        "fibonacci": tab_fib[Ci].sum(axis=1).astype(np.int8),
        "moldura": tab_mold[Ci].sum(axis=1).astype(np.int8),
        "consecutivos": (dif == 1).sum(axis=1).astype(np.int8),
        "amplitude": (Ci[:, -1] - Ci[:, 0]).astype(np.int8),
        "linha_max": lin.max(axis=1), "linha_min": lin.min(axis=1),
        "coluna_max": col.max(axis=1), "coluna_min": col.min(axis=1),
        "tem_1": (Ci[:, 0] == 1), "tem_25": (Ci[:, -1] == 25),
    }


# ── a biblioteca de regras, cada uma uma afirmação sobre o próximo concurso ──
def biblioteca_de_regras() -> List[Tuple[str, str, Callable]]:
    """O catálogo. Cada linha é uma afirmação sobre o próximo concurso.

    Este é o "livro de padrões" propriamente dito: reuni aqui tudo que circula
    como teoria de Lotofácil — soma, paridade, primos, moldura, miolo,
    vizinhança, linhas, colunas, terminações, altas e baixas, Fibonacci,
    múltiplos — e calculei a probabilidade EXATA de cada uma percorrendo as
    3.268.760 combinações. Nenhum número aqui é estimado.

    O valor do catálogo não está em nenhuma regra individual: está em ele ser
    completo o bastante para que a Figura 5 tenha o que mostrar. Cinquenta
    pontos em cima da reta ganho = 1 dizem mais do que cinco.
    """
    def faixa(ch, a, b):
        return lambda f: (f[ch] >= a) & (f[ch] <= b)
    def exato(ch, v):
        return lambda f: f[ch] == v

    R: List[Tuple[str, str, Callable]] = []
    # ── soma ──────────────────────────────────────────────────────────────
    R += [("soma_larga", "a soma das 15 dezenas fica entre 150 e 240", faixa("soma", 150, 240)),
          ("soma_central", "a soma fica entre 166 e 224", faixa("soma", 166, 224)),
          ("soma_estreita", "a soma fica entre 180 e 210", faixa("soma", 180, 210)),
          ("soma_muito_estreita", "a soma fica entre 188 e 202", faixa("soma", 188, 202)),
          ("soma_acima_da_media", "a soma passa de 195", lambda f: f["soma"] > 195),
          ("soma_nao_extrema", "a soma não é menor que 140 nem maior que 250", faixa("soma", 140, 250))]
    # ── paridade ──────────────────────────────────────────────────────────
    R += [("pares_5a10", "saem de 5 a 10 dezenas pares", faixa("pares", 5, 10)),
          ("pares_6a9", "saem de 6 a 9 dezenas pares", faixa("pares", 6, 9)),
          ("pares_7ou8", "saem 7 ou 8 dezenas pares", faixa("pares", 7, 8)),
          ("pares_exato_7", "saem exatamente 7 dezenas pares", exato("pares", 7)),
          ("pares_exato_8", "saem exatamente 8 dezenas pares", exato("pares", 8)),
          ("nunca_10_pares", "NÃO saem 10 ou mais dezenas pares", lambda f: f["pares"] <= 9),
          ("impares_maioria", "saem mais ímpares do que pares", lambda f: f["pares"] < 8)]
    # ── primos, Fibonacci, múltiplos ──────────────────────────────────────
    R += [("primos_4a7", "saem de 4 a 7 primos", faixa("primos", 4, 7)),
          ("primos_5ou6", "saem 5 ou 6 primos", faixa("primos", 5, 6)),
          ("primos_ao_menos_3", "saem ao menos 3 primos", lambda f: f["primos"] >= 3),
          ("fib_3a6", "saem de 3 a 6 dezenas de Fibonacci", faixa("fibonacci", 3, 6)),
          ("fib_ao_menos_2", "saem ao menos 2 dezenas de Fibonacci", lambda f: f["fibonacci"] >= 2),
          ("mult3_3a6", "saem de 3 a 6 múltiplos de 3", faixa("mult3", 3, 6)),
          ("mult5_2a4", "saem de 2 a 4 múltiplos de 5", faixa("mult5", 2, 4))]
    # ── geometria do volante ──────────────────────────────────────────────
    R += [("moldura_8a11", "de 8 a 11 dezenas caem na moldura do volante", faixa("moldura", 8, 11)),
          ("moldura_9ou10", "9 ou 10 dezenas caem na moldura", faixa("moldura", 9, 10)),
          ("miolo_ao_menos_4", "ao menos 4 dezenas do miolo", lambda f: (SORTEADAS - f["moldura"]) >= 4),
          ("miolo_5a7", "de 5 a 7 dezenas do miolo", lambda f: ((SORTEADAS - f["moldura"]) >= 5) & ((SORTEADAS - f["moldura"]) <= 7)),
          ("nenhuma_linha_vazia", "nenhuma das 5 linhas fica sem dezena", lambda f: f["linha_min"] >= 1),
          ("linha_min_2", "toda linha tem ao menos 2 dezenas", lambda f: f["linha_min"] >= 2),
          ("nenhuma_linha_cheia", "nenhuma linha sai inteira (5 de 5)", lambda f: f["linha_max"] <= 4),
          ("linha_max_4", "a linha mais cheia tem no máximo 4", lambda f: f["linha_max"] <= 4),
          ("coluna_min_1", "nenhuma coluna fica vazia", lambda f: f["coluna_min"] >= 1),
          ("coluna_min_2", "toda coluna tem ao menos 2 dezenas", lambda f: f["coluna_min"] >= 2),
          ("coluna_max_4", "nenhuma coluna sai inteira", lambda f: f["coluna_max"] <= 4),
          ("linhas_equilibradas", "toda linha tem 2, 3 ou 4 dezenas", lambda f: (f["linha_min"] >= 2) & (f["linha_max"] <= 4))]
    # ── vizinhança e sequências ───────────────────────────────────────────
    R += [("consec_ao_menos_4", "há ao menos 4 pares de dezenas vizinhas", lambda f: f["consecutivos"] >= 4),
          ("consec_ao_menos_5", "há ao menos 5 pares de dezenas vizinhas", lambda f: f["consecutivos"] >= 5),
          ("consec_5a10", "há de 5 a 10 pares de dezenas vizinhas", faixa("consecutivos", 5, 10)),
          ("consec_6a9", "há de 6 a 9 pares de dezenas vizinhas", faixa("consecutivos", 6, 9)),
          ("consec_no_maximo_11", "há no máximo 11 pares de vizinhas", lambda f: f["consecutivos"] <= 11),
          ("seq_max_ate_5", "a maior sequência corrida tem no máximo 5 dezenas", lambda f: f["seq_max"] <= 5),
          ("seq_max_ate_6", "a maior sequência corrida tem no máximo 6 dezenas", lambda f: f["seq_max"] <= 6),
          ("seq_max_ao_menos_3", "há alguma sequência corrida de 3 ou mais", lambda f: f["seq_max"] >= 3)]
    # ── altas, baixas, extremos, terminações ──────────────────────────────
    R += [("altas_6a9", "de 6 a 9 dezenas são maiores que 13", faixa("altas", 6, 9)),
          ("altas_7ou8", "7 ou 8 dezenas são maiores que 13", faixa("altas", 7, 8)),
          ("amplitude_total", "a menor é 1 ou a maior é 25", lambda f: f["tem_1"] | f["tem_25"]),
          ("ambos_extremos", "saem o 1 e o 25 no mesmo concurso", lambda f: f["tem_1"] & f["tem_25"]),
          ("nem_1_nem_25", "não sai nem o 1 nem o 25", lambda f: (~f["tem_1"]) & (~f["tem_25"])),
          ("finais_ao_menos_8", "aparecem ao menos 8 terminações diferentes (0 a 9)", lambda f: f["finais"] >= 8),
          ("finais_9ou10", "aparecem 9 ou 10 terminações diferentes", faixa("finais", 9, 10)),
          ("um_digito_5a7", "de 5 a 7 dezenas têm um só algarismo (1 a 9)", faixa("um_digito", 5, 7))]
    return R


def combos_de_regras() -> List[Tuple[str, str, List[str]]]:
    """Cinturões: regras empilhadas. A probabilidade do conjunto NÃO é o produto.

    Este é o ponto técnico que quase todo filtro de loteria erra. "Soma central"
    e "pares 6 a 9" não são independentes — somas centrais tendem a ter paridade
    equilibrada. Multiplicar as duas probabilidades dá um número errado e
    sistematicamente pequeno demais, o que faz o filtro parecer muito mais
    seletivo do que é. Enumerando, eu conto a interseção de verdade.
    """
    return [
        ("cinturao_leve", "soma central + paridade 6-9",
         ["soma_central", "pares_6a9"]),
        ("cinturao_medio", "soma central + paridade 6-9 + moldura 8-11 + nenhuma linha vazia",
         ["soma_central", "pares_6a9", "moldura_8a11", "nenhuma_linha_vazia"]),
        ("cinturao_pesado", "os seis filtros populares ao mesmo tempo",
         ["soma_central", "pares_6a9", "moldura_8a11", "nenhuma_linha_vazia",
          "primos_4a7", "consec_ao_menos_4"]),
    ]


def rodar() -> dict:
    C = enumerar()
    f = caracteristicas(C)
    h = carregar()
    hist = {
        "soma": None,
    }
    # as mesmas features, agora no histórico real
    from teorias import estatisticas_estruturais
    e = estatisticas_estruturais(h)
    lin_h = e["linhas"]; col_h = e["colunas"]
    fh = {
        "soma": e["soma"], "pares": e["pares"], "primos": e["primos"],
        "fibonacci": e["fibonacci"], "moldura": e["moldura"],
        "consecutivos": e["consecutivos"], "amplitude": e["amplitude"],
        "linha_max": lin_h.max(axis=1), "linha_min": lin_h.min(axis=1),
        "coluna_max": col_h.max(axis=1), "coluna_min": col_h.min(axis=1),
        "tem_1": h.matriz[:, 0] == 1, "tem_25": h.matriz[:, 24] == 1,
        "seq_max": e["maior_sequencia"],
        "mult3": np.array([sum(1 for x in c if x % 3 == 0) for c in h.conjuntos]),
        "mult5": np.array([sum(1 for x in c if x % 5 == 0) for c in h.conjuntos]),
        "finais": np.array([len({x % 10 for x in c}) for c in h.conjuntos]),
        "altas": np.array([sum(1 for x in c if x > 13) for c in h.conjuntos]),
        "um_digito": np.array([sum(1 for x in c if x <= 9) for c in h.conjuntos]),
    }

    regras = biblioteca_de_regras()
    mascaras_espaco: Dict[str, np.ndarray] = {}
    linhas: List[dict] = []
    ini_teste = 2597

    for chave, texto, teste in regras:
        m_esp = teste(f)
        m_hist = teste(fh)
        mascaras_espaco[chave] = m_esp
        n_esp = int(m_esp.sum())
        p_exato = n_esp / TOTAL
        for janela, sl in (("historico_todo", slice(None)),
                           ("apenas_teste", slice(ini_teste, None))):
            mh = m_hist[sl]
            n = int(len(mh)); acertos = int(mh.sum())
            taxa = acertos / n
            dp = (p_exato * (1 - p_exato) / n) ** 0.5
            linhas.append({
                "regra": chave, "afirma": texto, "janela": janela,
                "combinacoes_no_espaco": n_esp,
                "assertividade_exata": p_exato,
                "assertividade_medida": taxa,
                "n_concursos": n, "acertos": acertos,
                "ganho": taxa / p_exato if p_exato > 0 else float("nan"),
                "z": (taxa - p_exato) / dp if dp > 0 else 0.0,
            })

    for chave, texto, partes in combos_de_regras():
        m_esp = np.ones(TOTAL, dtype=bool)
        m_hist = np.ones(h.T, dtype=bool)
        for p in partes:
            m_esp &= mascaras_espaco[p]
            m_hist &= dict((k, t(fh)) for k, _, t in regras if k == p)[p]
        n_esp = int(m_esp.sum()); p_exato = n_esp / TOTAL
        produto = 1.0
        for p in partes:
            produto *= float(mascaras_espaco[p].sum()) / TOTAL
        for janela, sl in (("historico_todo", slice(None)),
                           ("apenas_teste", slice(ini_teste, None))):
            mh = m_hist[sl]; n = int(len(mh)); acertos = int(mh.sum())
            taxa = acertos / n
            dp = (p_exato * (1 - p_exato) / n) ** 0.5
            linhas.append({
                "regra": chave, "afirma": texto, "janela": janela,
                "combinacoes_no_espaco": n_esp,
                "assertividade_exata": p_exato,
                "assertividade_se_fossem_independentes": produto,
                "assertividade_medida": taxa,
                "n_concursos": n, "acertos": acertos,
                "ganho": taxa / p_exato if p_exato > 0 else float("nan"),
                "z": (taxa - p_exato) / dp if dp > 0 else 0.0,
            })

    # distribuições exatas completas, para as tabelas do relatório
    distribuicoes = {}
    for chave in ("soma", "pares", "primos", "moldura", "consecutivos", "fibonacci",
                  "altas", "seq_max", "finais", "mult3"):
        v = f[chave].astype(int)
        cont = np.bincount(v, minlength=int(v.max()) + 1)
        vh = np.asarray(fh[chave]).astype(int)
        conth = np.bincount(vh, minlength=len(cont))[: len(cont)]
        distribuicoes[chave] = {
            "valores": list(range(len(cont))),
            "exato": (cont / TOTAL).tolist(),
            "medido": (conth / h.T).tolist(),
            "n_concursos": h.T,
        }

    return {"total_combinacoes": TOTAL, "regras": linhas,
            "distribuicoes_exatas": distribuicoes}


if __name__ == "__main__":
    res = rodar()
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "assertividade.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{'regra':26s} {'espaço':>9s} {'exata':>8s} {'medida':>8s} {'ganho':>7s} {'z':>7s}")
    for r in res["regras"]:
        if r["janela"] != "historico_todo":
            continue
        print(f"{r['regra']:26s} {r['assertividade_exata']*100:8.3f}% "
              f"{r['assertividade_exata']*100:7.2f}% {r['assertividade_medida']*100:7.2f}% "
              f"{r['ganho']:7.3f} {r['z']:+7.2f}")
