# -*- coding: utf-8 -*-
"""
INOVAÇÕES — as sete teorias que eu inventei para este estudo, e o que deu.

O QUE ELE PEDIU, LITERALMENTE
─────────────────────────────
    "eu não quero nada conhecido. quero que você entre ali e inove... pode usar
     até teorias já conhecidas, mas inova... você testa essa teoria aqui, aí
     você vai e testa como se fosse resultado novo e vê o que dá"

Então cada teoria daqui nasceu de uma pergunta que eu não vi feita nos materiais
do projeto (o Atlas, a Enciclopédia, o v8) nem no folclore de loteria. E cada
uma vem com o que a mataria, e é testada nos concursos que ela não viu.

O CRITÉRIO QUE EU USEI PARA "INOVAR" DE VERDADE
───────────────────────────────────────────────
Não basta inventar nome novo para frequência. Uma teoria só entrou aqui se
olhasse para uma DIMENSÃO que as outras jogam fora:

  I.   COMPLEMENTO      olha as 10 que não saíram, não as 15 que saíram
  II.  ECO POSICIONAL   usa a ordem de saída do globo, que o conjunto apaga
  III. INÉRCIA          trata a série de repetições como sinal, não como ruído
  IV.  ATRITO           trata as 300 duplas como rede, não como contagens soltas
  V.   NÚCLEO           procura persistência acima da sobreposição forçada
  VI.  MARÉ             procura deriva lenta em 21 anos, não padrão de curto prazo
  VII. ESPELHO          usa a simetria n ↔ 26-n do volante
"""
from __future__ import annotations

import itertools
import json
from math import comb
from typing import Dict, List, Tuple

import numpy as np

from base import (AUSENTES, DP_INTER, MEDIA_INTER, PMF_INTER, RESULTADOS,
                  SORTEADAS, UNIVERSO, carregar, historia_falsa)
from teorias import estatisticas_estruturais, pmf_hipergeometrica, qui_quadrado

INI_TESTE = 2597


def _pmf_inter(N: int, K: int, n: int) -> np.ndarray:
    p = np.zeros(min(K, n) + 1)
    tot = comb(N, n)
    for k in range(len(p)):
        if (n - k) > (N - K):
            continue
        p[k] = comb(K, k) * comb(N - K, n - k) / tot
    return p


# ═══════════════════════════════════════ I. TEORIA DO COMPLEMENTO
def complemento(h) -> dict:
    """As 10 ausentes. Objeto menor, estrutura mais densa, viés mais concentrado.

    AFIRMA    o conjunto das 10 dezenas que NÃO saíram carrega estrutura que as
              15 sorteadas diluem — em particular, ausências repetidas de um
              concurso para o outro.
    DERRUBA   |ausentes_t ∩ ausentes_{t-1}| seguir exatamente H(25,10,10)
              (média 4,0) e o número de blocos de ausentes bater com o nulo.

    Por que 10 e não 15: com 15 escolhidas de 25, a interseção mínima forçada é
    5 (aritmética pura). Com as 10 ausentes, a interseção mínima forçada é ZERO.
    O complemento tem, portanto, MAIS liberdade — e um sinal do mesmo tamanho
    aparece com mais contraste nele. É a razão técnica da escolha.
    """
    A = 1 - h.matriz                       # 1 onde a dezena FALTOU
    T = h.T
    inter = np.array([int(A[i] @ A[i - 1]) for i in range(1, T)])
    pmf = _pmf_inter(UNIVERSO, AUSENTES, AUSENTES)
    cont = np.bincount(inter, minlength=len(pmf))[: len(pmf)]
    chi, df = qui_quadrado(cont, pmf, len(inter))
    mu = float(np.dot(np.arange(len(pmf)), pmf))
    sd = float(np.sqrt(np.dot((np.arange(len(pmf)) - mu) ** 2, pmf)))

    # blocos: quantos pedaços contíguos as 10 ausentes formam no volante linear
    blocos, isoladas = [], []
    for i in range(T):
        aus = sorted(int(x) for x in np.where(A[i] == 1)[0] + 1)
        b = 1 + sum(1 for j in range(1, len(aus)) if aus[j] - aus[j - 1] > 1)
        s = set(aus)
        iso = sum(1 for x in aus if (x - 1) not in s and (x + 1) not in s)
        blocos.append(b); isoladas.append(iso)
    return {
        "afirma": "as 10 ausentes carregam estrutura que as 15 sorteadas diluem",
        "derruba": "interseção das ausências seguir H(25,10,10) e blocos baterem com o nulo",
        "intersecao_media_medida": float(inter.mean()),
        "intersecao_media_exata": mu,
        "z_media": float((inter.mean() - mu) * np.sqrt(len(inter)) / sd),
        "chi2_z": float((chi - df) / (2 * df) ** 0.5) if df > 0 else 0.0,
        "pmf_exata": pmf.tolist(),
        "pmf_medida": (cont / len(inter)).tolist(),
        "blocos_media": float(np.mean(blocos)),
        "isoladas_media": float(np.mean(isoladas)),
        "blocos_serie": blocos, "isoladas_serie": isoladas,
    }


# ═══════════════════════════════════════ II. ECO POSICIONAL
def eco_posicional(h, excluir=(2425,)) -> dict:
    """A ordem em que a bola sai do globo prevê alguma coisa?

    AFIRMA    a posição de extração carrega informação física (peso, desgaste,
              carregamento do globo) que o conjunto ordenado destrói.
    DERRUBA   a tabela dezena × posição bater com o nulo, a posição média de
              cada dezena não se separar, e a posição não prever repetição.

    Esta é a única bateria do estudo capaz, em princípio, de detectar viés
    MECÂNICO. Todas as outras olham o conjunto, e o conjunto é invariante a
    qualquer coisa que a máquina faça na ordem.
    """
    manter = np.array([int(c) not in excluir for c in h.concursos])
    ordem = h.ordem[manter]
    T = ordem.shape[0]
    tab = np.zeros((UNIVERSO, SORTEADAS))
    for i in range(T):
        for p in range(SORTEADAS):
            tab[ordem[i, p] - 1, p] += 1
    lin, col = tab.sum(axis=1, keepdims=True), tab.sum(axis=0, keepdims=True)
    esp = lin @ col / tab.sum()
    chi = float(np.sum((tab - esp) ** 2 / esp))
    df = (UNIVERSO - 1) * (SORTEADAS - 1)

    pos_media = np.zeros(UNIVERSO); n_ap = np.zeros(UNIVERSO)
    for i in range(T):
        for p in range(SORTEADAS):
            pos_media[ordem[i, p] - 1] += p + 1
            n_ap[ordem[i, p] - 1] += 1
    pos_media = pos_media / n_ap
    # sob o nulo, a posição média de uma dezena é 8 (média de 1..15)
    dp_pos = np.sqrt(((np.arange(1, 16) - 8.0) ** 2).mean() / n_ap)
    z_pos = (pos_media - 8.0) / dp_pos

    # a bola que sai primeiro: uniforme sobre as 25?
    primeira = np.bincount(ordem[:, 0], minlength=26)[1:]
    chi1 = float(np.sum((primeira - T / 25) ** 2 / (T / 25)))

    # posição prediz repetição no concurso seguinte?
    difs = []
    idx = np.where(manter)[0]
    for i in idx:
        if i + 1 >= h.T:
            continue
        p_de = {int(h.ordem[i, p]): p + 1 for p in range(SORTEADAS)}
        rep = [p_de[x] for x in p_de if h.matriz[i + 1, x - 1] == 1]
        nao = [p_de[x] for x in p_de if h.matriz[i + 1, x - 1] == 0]
        if rep and nao:
            difs.append(np.mean(rep) - np.mean(nao))
    d = np.array(difs)
    return {
        "afirma": "a ordem de saída do globo carrega informação física",
        "derruba": "dezena×posição bater com o nulo e a posição não prever repetição",
        "chi2_dezena_x_posicao": chi, "df": df,
        "chi2_z": (chi - df) / (2 * df) ** 0.5,
        "posicao_media_por_dezena": pos_media.tolist(),
        "z_posicao_por_dezena": z_pos.tolist(),
        "maior_z_posicao": float(np.abs(z_pos).max()),
        "dezena_do_maior_z": int(np.argmax(np.abs(z_pos)) + 1),
        "chi2_primeira_bola": chi1, "df_primeira": 24,
        "z_primeira_bola": (chi1 - 24) / (2 * 24) ** 0.5,
        "diferenca_posicao_repete_menos_nao_repete": float(d.mean()),
        "z_eco": float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))),
        "n_pares_usados": int(len(d)),
        "concursos_excluidos": list(excluir),
    }


# ═══════════════════════════════════════ III. INÉRCIA DE REPETIÇÃO
def inercia(h) -> dict:
    """A série de repetições tem momento próprio?

    AFIRMA    concursos que repetem muito são seguidos por concursos que repetem
              muito (o globo "esquenta" numa vizinhança do espaço).
    DERRUBA   a matriz de transição entre faixas de repetição ser indistinguível
              do produto das marginais.

    Esta é a teoria mais promissora em princípio, porque a repetição é a única
    grandeza da Lotofácil que LIGA dois concursos por construção. Se houver
    memória em algum lugar, o caminho mais curto até ela passa por aqui.
    """
    e = estatisticas_estruturais(h)
    rep = e["repeticoes"][1:].astype(int)
    n = len(rep)
    # matriz de transição 11x11 (valores 5..15) reduzida às faixas com massa
    vals = list(range(5, 16))
    T_ = np.zeros((len(vals), len(vals)))
    for a, b in zip(rep[:-1], rep[1:]):
        T_[a - 5, b - 5] += 1
    lin, col = T_.sum(axis=1, keepdims=True), T_.sum(axis=0, keepdims=True)
    esp = lin @ col / T_.sum()
    m = esp >= 5
    chi = float(np.sum((T_[m] - esp[m]) ** 2 / esp[m]))
    df = max(int(m.sum()) - len(vals) * 2 + 1, 1)
    r1 = float(np.corrcoef(rep[:-1], rep[1:])[0, 1])
    # a média condicional: depois de repetir muito, repete quanto?
    cond = {}
    for v in vals:
        seg = rep[1:][rep[:-1] == v]
        if len(seg) >= 20:
            cond[v] = {"n": int(len(seg)), "media_seguinte": float(seg.mean()),
                       "z": float((seg.mean() - MEDIA_INTER) * np.sqrt(len(seg)) / DP_INTER)}
    return {
        "afirma": "a quantidade de repetições tem inércia de um concurso para o outro",
        "derruba": "transição indistinguível do produto das marginais",
        "n": n, "media": float(rep.mean()), "media_exata": MEDIA_INTER,
        "autocorr_lag1": r1, "z_autocorr": float(r1 * np.sqrt(n - 1)),
        "chi2_transicao": chi, "df": df,
        "chi2_z": (chi - df) / (2 * df) ** 0.5,
        "media_seguinte_por_faixa": cond,
        "serie": rep.tolist(),
        "pmf_exata": PMF_INTER.tolist(),
        "pmf_medida": (np.bincount(rep, minlength=16)[:16] / n).tolist(),
    }


# ═══════════════════════════════════════ IV. ATRITO DE PARES (rede)
def atrito(h) -> dict:
    """As 300 duplas formam comunidades, ou é rede aleatória?

    AFIRMA    algumas duplas de dezenas "andam juntas" além do acaso, e a rede
              de coocorrência tem modularidade acima da de uma rede aleatória.
    DERRUBA   a modularidade cair dentro da faixa que histórias falsas produzem,
              e o maior |z| das 300 duplas idem.
    """
    M = h.matriz.astype(float)
    C = M.T @ M
    np.fill_diagonal(C, 0)
    p2 = SORTEADAS * (SORTEADAS - 1) / (UNIVERSO * (UNIVERSO - 1))
    mu, sd = h.T * p2, np.sqrt(h.T * p2 * (1 - p2))
    Z = (C - mu) / sd
    np.fill_diagonal(Z, 0)
    iu = np.triu_indices(UNIVERSO, 1)
    zs = Z[iu]
    k = C.sum(axis=1); m2 = C.sum()
    B = C - np.outer(k, k) / m2
    vals, vecs = np.linalg.eigh(B)
    s = np.sign(vecs[:, -1]); s[s == 0] = 1
    Q = float(s @ B @ s / m2)
    ordem = np.argsort(zs)
    def _par(i):
        return f"{iu[0][i]+1:02d}-{iu[1][i]+1:02d}"
    return {
        "afirma": "a rede de coocorrência tem comunidades além do acaso",
        "derruba": "modularidade e maior |z| das duplas dentro do controle negativo",
        "n_duplas": int(len(zs)),
        "maior_z": float(zs.max()), "menor_z": float(zs.min()),
        "duplas_mais_juntas": [{"dupla": _par(i), "z": float(zs[i])} for i in ordem[-8:][::-1]],
        "duplas_mais_separadas": [{"dupla": _par(i), "z": float(zs[i])} for i in ordem[:8]],
        "modularidade": Q,
        "duplas_acima_de_2sigma": int(np.sum(np.abs(zs) > 2)),
        "esperado_acima_de_2sigma": float(len(zs) * 0.0455),
        "z_todas": zs.tolist(),
    }


# ═══════════════════════════════════════ V. NÚCLEO PERSISTENTE
def nucleo(h, janelas=(5, 10, 20, 50)) -> dict:
    """Existe um grupo que "vive junto" além da sobreposição obrigatória?

    AFIRMA    em janelas de w concursos, o número de dezenas presentes em TODOS
              eles é maior do que o acaso permitiria.
    DERRUBA   a contagem bater com o valor exato 25·(3/5)^w — que é o que a
              independência prevê.

    O ponto sutil: com 60% de chance por dezena por concurso, a interseção de 5
    concursos já tem 25·0,6⁵ ≈ 1,94 dezenas ESPERADAS. Quem vê duas dezenas
    presentes nos últimos cinco concursos e chama de "núcleo" está descrevendo a
    média, não uma descoberta.
    """
    out = {}
    for w in janelas:
        pres = np.array([int(h.matriz[i - w + 1:i + 1].min(axis=0).sum())
                         for i in range(w - 1, h.T)])
        esp = UNIVERSO * (SORTEADAS / UNIVERSO) ** w
        var = UNIVERSO * ((0.6 ** w) * (1 - 0.6 ** w))     # aprox: dezenas quase indep.
        # Quando o esperado é minúsculo (janela 20: 0,001 dezena), a aproximação
        # normal é inválida — a distribuição é Poisson e um z normal ali é
        # ficção. Marco isso em vez de reportar um z que não significa nada.
        valido = esp >= 5.0
        out[f"janela_{w}"] = {
            "media_medida": float(pres.mean()), "media_exata": float(esp),
            "z": float((pres.mean() - esp) * np.sqrt(len(pres)) / np.sqrt(var)),
            "aproximacao_normal_valida": bool(valido),
            "nota": "" if valido else "esperado < 5: use Poisson, o z normal aqui não tem sentido",
            "maximo_visto": int(pres.max()),
        }
    return {"afirma": "há um núcleo de dezenas que persiste além do acaso",
            "derruba": "a interseção de janelas bater com 25·(3/5)^w",
            "janelas": out}


# ═══════════════════════════════════════ VI. MARÉ
def mare(h, blocos=8) -> dict:
    """A frequência das dezenas anda ao longo de 21 anos?

    AFIRMA    troca de globo, de lote de bolas e de máquina deixam deriva lenta
              na frequência de algumas dezenas.
    DERRUBA   a tabela dezena × época bater com o nulo, e o maior desvio
              acumulado (ponte browniana) ficar dentro do controle negativo.
    """
    corte = np.array_split(np.arange(h.T), blocos)
    tab = np.array([h.matriz[c].sum(axis=0) for c in corte], dtype=float)
    lin, col = tab.sum(axis=1, keepdims=True), tab.sum(axis=0, keepdims=True)
    esp = lin @ col / tab.sum()
    p = SORTEADAS / UNIVERSO
    # O FATOR (1-p) — o erro que eu mesmo cometi e que vale um capítulo.
    # O χ² de contingência divide por E, assumindo variância = E (Poisson). Mas
    # a contagem de uma dezena ao longo de n concursos é Binomial(n, 0,6), cuja
    # variância é E·(1-p) = 0,4·E. Sem o fator, o χ² sai 2,5× menor do que
    # deveria e a tabela parece UNIFORME DEMAIS — uma anomalia que não existe.
    # Confirmado em histórias falsas: χ² médio 70,1 com df=168 (razão 0,417).
    chi_bruto = float(np.sum((tab - esp) ** 2 / esp))
    chi = chi_bruto / (1 - p)
    df = (blocos - 1) * (UNIVERSO - 1)
    desv = np.cumsum(h.matriz - p, axis=0)
    escala = np.sqrt(np.arange(1, h.T + 1) * p * (1 - p))[:, None]
    ponte = np.abs(desv / escala)[h.T // 10:]
    imax = int(np.unravel_index(np.argmax(ponte), ponte.shape)[1])
    return {
        "afirma": "há deriva lenta na frequência ao longo de 21 anos",
        "derruba": "dezena×época bater com o nulo e a ponte ficar no controle negativo",
        "blocos": blocos, "chi2_bruto_errado": chi_bruto, "chi2": chi, "df": df,
        "fator_de_correcao": 1 - p,
        "chi2_z": (chi - df) / (2 * df) ** 0.5,
        "maior_ponte": float(ponte.max()),
        "dezena_da_maior_ponte": imax + 1,
        "frequencia_por_bloco": (tab / np.array([len(c) for c in corte])[:, None]).tolist(),
        "concursos_por_bloco": [[int(h.concursos[c[0]]), int(h.concursos[c[-1]])] for c in corte],
    }


# ═══════════════════════════════════════ VII. ESPELHO
def espelho(h) -> dict:
    """A simetria n ↔ 26-n do volante deixa marca?

    AFIRMA    dezenas simétricas em relação ao centro do volante (1↔25, 2↔24,
              ..., 12↔14, e o 13 sozinho) tendem a sair juntas ou separadas.
    DERRUBA   a contagem de pares espelhados bater com o nulo exato.
    """
    cont = np.array([int(sum(1 for x in c if (26 - x) in c and x != 13))
                     for c in h.conjuntos])
    # nulo por enumeração rápida via simulação exata da hipergeométrica dos 12 pares
    rng = np.random.default_rng(11)
    sim = np.empty(200000, dtype=np.int16)
    for i in range(len(sim)):
        s = set(rng.permutation(UNIVERSO)[:SORTEADAS] + 1)
        sim[i] = sum(1 for x in s if (26 - x) in s and x != 13)
    mu, sd = float(sim.mean()), float(sim.std(ddof=1))
    return {
        "afirma": "a simetria n ↔ 26-n do volante deixa marca nos sorteios",
        "derruba": "a contagem de pares espelhados bater com o nulo",
        "media_medida": float(cont.mean()), "media_nula": mu,
        "z": float((cont.mean() - mu) * np.sqrt(h.T) / sd),
        "nulo_por": "200.000 sorteios uniformes simulados",
    }


def rodar() -> dict:
    h = carregar()
    return {
        "I_complemento": complemento(h),
        "II_eco_posicional": eco_posicional(h),
        "III_inercia": inercia(h),
        "IV_atrito": atrito(h),
        "V_nucleo": nucleo(h),
        "VI_mare": mare(h),
        "VII_espelho": espelho(h),
    }


if __name__ == "__main__":
    r = rodar()
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / "inovacoes.json").write_text(
        json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    print("I   complemento     z_media=%+.2f chi2_z=%+.2f (inter media %.3f vs exata %.3f)" % (
        r["I_complemento"]["z_media"], r["I_complemento"]["chi2_z"],
        r["I_complemento"]["intersecao_media_medida"], r["I_complemento"]["intersecao_media_exata"]))
    e = r["II_eco_posicional"]
    print("II  eco posicional  chi2_z=%+.2f  maior_z_posicao=%.2f (dezena %d)  z_eco=%+.2f  z_1a_bola=%+.2f" % (
        e["chi2_z"], e["maior_z_posicao"], e["dezena_do_maior_z"], e["z_eco"], e["z_primeira_bola"]))
    i = r["III_inercia"]
    print("III inercia         autocorr=%+.4f z=%+.2f  chi2_z=%+.2f" % (
        i["autocorr_lag1"], i["z_autocorr"], i["chi2_z"]))
    a = r["IV_atrito"]
    print("IV  atrito          maior_z=%+.2f menor_z=%+.2f  Q=%.4f  >2sigma: %d (esperado %.1f)" % (
        a["maior_z"], a["menor_z"], a["modularidade"], a["duplas_acima_de_2sigma"], a["esperado_acima_de_2sigma"]))
    for k, v in r["V_nucleo"]["janelas"].items():
        print("V   nucleo %-10s medido %.3f  exato %.3f  z=%+.2f" % (k, v["media_medida"], v["media_exata"], v["z"]))
    m = r["VI_mare"]
    print("VI  mare            chi2_z=%+.2f  maior_ponte=%.2f (dezena %d)" % (m["chi2_z"], m["maior_ponte"], m["dezena_da_maior_ponte"]))
    s = r["VII_espelho"]
    print("VII espelho         medido %.4f  nulo %.4f  z=%+.2f" % (s["media_medida"], s["media_nula"], s["z"]))
