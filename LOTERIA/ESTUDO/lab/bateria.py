# -*- coding: utf-8 -*-
"""
BATERIA — tudo que eu pergunto aos dados, e a mesma coisa perguntada ao acaso.

A REGRA DE OURO DESTE ARQUIVO
─────────────────────────────
Toda função aqui recebe um `Historico` e devolve um dicionário {nome: z}. Nada
mais. A consequência disso é o que dá validade ao estudo: eu posso passar por
aqui o histórico REAL da Lotofácil e passar, EXATAMENTE PELO MESMO CAMINHO,
centenas de históricos que eu mesmo gerei por acaso puro. O que a bateria
encontra nos falsos é a medida do que ela inventa sozinha.

Por isso a bateria devolve TODOS os z individuais — inclusive os 300 pares e as
300 autocorrelações — e não só os resumos. Se eu escondesse os individuais e
olhasse só o maior, estaria escondendo do controle negativo o tamanho real da
busca, que é a forma mais comum de auto-engano nesta área.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from base import (DP_INTER, MEDIA_INTER, PMF_INTER, SORTEADAS, UNIVERSO,
                  Historico)
from teorias import (NULOS_EXATOS, estatisticas_estruturais, pmf_hipergeometrica,
                     qui_quadrado)

P_DEZENA = SORTEADAS / UNIVERSO          # 0.6 — chance de uma dezena qualquer sair


def _z_chi(chi: float, df: int) -> float:
    """χ² virado em z. Para df grande, (χ²-df)/√(2df) é normal padrão.

    Uso isto porque preciso comparar coisas de naturezas diferentes — um χ² de
    24 graus com uma correlação — na MESMA régua, senão o controle negativo não
    consegue tirar um "maior |z| da bateria".
    """
    return 0.0 if df <= 0 else (chi - df) / (2.0 * df) ** 0.5


# ═══════════════════════════════════════════════ 1. ESTRUTURA
def bateria_estrutural(h: Historico) -> Dict[str, float]:
    """A forma dos sorteios bate com a forma que a combinatória exige?

    Não prevê nada. É a auditoria de aleatoriedade — e é o teste mais forte que
    existe contra a hipótese "a Caixa mexe no sorteio", porque um mecanismo
    manipulado quase inevitavelmente deixa a forma torta em algum lugar.
    """
    e = estatisticas_estruturais(h)
    out: Dict[str, float] = {}

    for chave, pmf in NULOS_EXATOS.items():
        serie = e[chave]
        serie = serie[serie >= 0]                     # repetições: pula o 1º
        cont = np.bincount(serie, minlength=SORTEADAS + 1)[: SORTEADAS + 1]
        chi, df = qui_quadrado(cont, pmf, len(serie))
        out[f"estrutura.{chave}.chi2"] = _z_chi(chi, df)
        media0 = float(np.dot(np.arange(len(pmf)), pmf))
        dp0 = float(np.sqrt(np.dot((np.arange(len(pmf)) - media0) ** 2, pmf)))
        out[f"estrutura.{chave}.media"] = (serie.mean() - media0) * np.sqrt(len(serie)) / dp0

    # soma: nulo por convolução exata seria caro; uso média/variância exatas
    # da soma de uma amostra sem reposição — ambas fechadas.
    mu_soma = SORTEADAS * (UNIVERSO + 1) / 2                       # 195
    var_soma = SORTEADAS * (UNIVERSO ** 2 - 1) / 12 * (UNIVERSO - SORTEADAS) / (UNIVERSO - 1)
    out["estrutura.soma.media"] = ((e["soma"].mean() - mu_soma)
                                   * np.sqrt(h.T) / np.sqrt(var_soma))
    out["estrutura.soma.variancia"] = ((e["soma"].var(ddof=1) / var_soma - 1)
                                       * np.sqrt(h.T / 2.0))

    # estatísticas sem fórmula fechada fácil: comparo com o nulo simulado que o
    # controle negativo já provê (aqui só registro a média padronizada bruta).
    for chave in ("consecutivos", "progressoes_aritmeticas", "espelho",
                  "amplitude", "desvio_linhas", "desvio_colunas"):
        s = e[chave].astype(float)
        out[f"estrutura.{chave}.media_bruta"] = float(s.mean())

    # perfil do volante: as 5 linhas e as 5 colunas recebem igual?
    for eixo in ("linhas", "colunas"):
        tot = e[eixo].sum(axis=0).astype(float)
        esp = tot.sum() / 5.0
        chi = float(np.sum((tot - esp) ** 2 / esp))
        out[f"estrutura.volante.{eixo}"] = _z_chi(chi, 4)
    return out


# ═══════════════════════════════════════════════ 2. DEPENDÊNCIA
def bateria_dependencia(h: Historico, lags: int = 12,
                        excluir: Tuple[int, ...] = ()) -> Dict[str, float]:
    """Existe memória? Se não existir aqui, nenhuma teoria de ranking pode valer.

    Esta é a bateria decisiva. Um sorteio sem memória não é previsível por
    nenhum método, por mais sofisticado — nem por rede neural, nem por LLM, nem
    por consenso de agentes. Toda a discussão sobre "qual modelo prever" só faz
    sentido depois que ALGUMA dependência aparecer aqui.
    """
    M = h.matriz.astype(float)
    T = h.T
    out: Dict[str, float] = {}

    # 2.1 as 25 dezenas são igualmente prováveis?
    tot = M.sum(axis=0)
    esp = T * P_DEZENA
    chi = float(np.sum((tot - esp) ** 2 / (esp * (1 - P_DEZENA))))   # normalizado
    out["dep.uniformidade_25"] = _z_chi(chi, UNIVERSO - 1)
    for i in range(UNIVERSO):
        out[f"dep.freq.dezena_{i+1:02d}"] = (tot[i] - esp) / np.sqrt(esp * (1 - P_DEZENA))

    # 2.2 autocorrelação de cada dezena, lags 1..L (300 testes — de propósito)
    for lag in range(1, lags + 1):
        a, b = M[lag:], M[:-lag]
        n = T - lag
        # corr de duas Bernoulli(p) sob independência: z = (n11 - n*p²)/√(n p²(1-p²))
        n11 = (a * b).sum(axis=0)
        mu = n * P_DEZENA ** 2
        sd = np.sqrt(n * P_DEZENA ** 2 * (1 - P_DEZENA ** 2))
        z = (n11 - mu) / sd
        for i in range(UNIVERSO):
            out[f"dep.autocorr.d{i+1:02d}.lag{lag}"] = float(z[i])

    # 2.3 as 300 duplas saem juntas mais do que deviam?
    cooc = M.T @ M
    p2 = SORTEADAS * (SORTEADAS - 1) / (UNIVERSO * (UNIVERSO - 1))   # P(i e j juntas)
    mu, sd = T * p2, np.sqrt(T * p2 * (1 - p2))
    for i in range(UNIVERSO):
        for j in range(i + 1, UNIVERSO):
            out[f"dep.dupla.{i+1:02d}_{j+1:02d}"] = float((cooc[i, j] - mu) / sd)

    # 2.4 a série de repetições tem memória? (inércia de repetição — MINHA)
    e = estatisticas_estruturais(h)
    rep = e["repeticoes"][1:].astype(float)
    if len(rep) > 30:
        x, y = rep[:-1], rep[1:]
        r = float(np.corrcoef(x, y)[0, 1])
        out["dep.repeticoes.autocorr1"] = r * np.sqrt(len(x) - 1)
        # runs test acima/abaixo da média
        s = (rep > rep.mean()).astype(int)
        trocas = int(np.sum(s[1:] != s[:-1]))
        n1, n0 = int(s.sum()), int(len(s) - s.sum())
        if n1 > 0 and n0 > 0:
            mu_r = 2 * n1 * n0 / (n1 + n0) + 1
            var_r = (2 * n1 * n0 * (2 * n1 * n0 - n1 - n0)
                     / ((n1 + n0) ** 2 * (n1 + n0 - 1)))
            out["dep.repeticoes.runs"] = (trocas + 1 - mu_r) / np.sqrt(var_r)
        # Markov entre faixas de repetição: baixa(≤8) média(9) alta(≥10)
        faixa = np.digitize(rep, [8.5, 9.5])
        tab = np.zeros((3, 3))
        for a_, b_ in zip(faixa[:-1], faixa[1:]):
            tab[a_, b_] += 1
        lin, col = tab.sum(axis=1, keepdims=True), tab.sum(axis=0, keepdims=True)
        espm = lin @ col / tab.sum()
        m = espm > 5
        chi = float(np.sum((tab[m] - espm[m]) ** 2 / espm[m]))
        out["dep.repeticoes.markov"] = _z_chi(chi, 4)

    # 2.5 espectro: alguma periodicidade na soma e nas repetições?
    for nome, serie in (("soma", e["soma"].astype(float)), ("repeticoes", rep)):
        s = serie - serie.mean()
        pot = np.abs(np.fft.rfft(s)) ** 2
        pot = pot[1:]                                    # descarta o nível
        if len(pot) > 10:
            # sob ruído branco, o maior pico normalizado segue a lei de Fisher
            g = float(pot.max() / pot.sum())
            m = len(pot)
            p_fisher = min(1.0, m * (1 - g) ** (m - 1))
            out[f"dep.espectro.{nome}"] = float(
                -np.log10(max(p_fisher, 1e-300)))        # em "sigmas de Fisher"

    # 2.6 maré: a frequência de alguma dezena anda ao longo do histórico?
    # CUSUM do desvio acumulado, padronizado pelo passeio aleatório.
    desv = np.cumsum(M - P_DEZENA, axis=0)
    escala = np.sqrt(np.arange(1, T + 1) * P_DEZENA * (1 - P_DEZENA))[:, None]
    ponte = np.abs(desv / escala)
    for i in range(UNIVERSO):
        out[f"dep.mare.d{i+1:02d}"] = float(ponte[T // 10:, i].max())

    # 2.7 viés posicional: a dezena X tende a sair na posição Y do globo?
    manter = np.array([c not in excluir for c in h.concursos])
    ordem = h.ordem[manter]
    tab = np.zeros((UNIVERSO, SORTEADAS))
    for i in range(ordem.shape[0]):
        for pos in range(SORTEADAS):
            tab[ordem[i, pos] - 1, pos] += 1
    lin, col = tab.sum(axis=1, keepdims=True), tab.sum(axis=0, keepdims=True)
    espm = lin @ col / tab.sum()
    m = espm > 5
    chi = float(np.sum((tab[m] - espm[m]) ** 2 / espm[m]))
    out["dep.posicional.dezena_x_posicao"] = _z_chi(chi, (UNIVERSO - 1) * (SORTEADAS - 1))

    # 2.8 eco posicional (MINHA): sair cedo do globo prediz sair no próximo?
    #     Compara a posição média de extração das que repetem contra as que não.
    pos_de = np.zeros((h.T, UNIVERSO))
    for i in range(h.T):
        for pos in range(SORTEADAS):
            pos_de[i, h.ordem[i, pos] - 1] = pos + 1
    dif: List[float] = []
    for i in range(h.T - 1):
        if h.concursos[i] in excluir:
            continue
        saiu = h.matriz[i] == 1
        rep_ = (h.matriz[i + 1] == 1) & saiu
        nao = saiu & ~rep_
        if rep_.sum() > 0 and nao.sum() > 0:
            dif.append(float(pos_de[i][rep_].mean() - pos_de[i][nao].mean()))
    if len(dif) > 30:
        d = np.array(dif)
        out["dep.eco_posicional"] = float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))

    # 2.9 modularidade da rede de coocorrência (MINHA)
    A = cooc.copy()
    np.fill_diagonal(A, 0)
    k = A.sum(axis=1)
    m2 = A.sum()
    B = A - np.outer(k, k) / m2
    vals, vecs = np.linalg.eigh(B)
    s = np.sign(vecs[:, -1])
    s[s == 0] = 1
    out["dep.modularidade_rede"] = float(s @ B @ s / m2)

    return out


# ═══════════════════════════════════════════════ 3. RANKING
def matrizes_de_estado(h: Historico) -> Dict[str, np.ndarray]:
    """Tudo que um preditor pode saber em t, calculado de uma vez para todo t.

    Vetorizar isto é o que torna o controle negativo viável: sem isto, rodar
    200 histórias falsas × 16 preditores × 650 concursos levaria horas.
    """
    M = h.matriz.astype(float)
    T = h.T
    cum = np.cumsum(M, axis=0)
    freq_ate = np.vstack([np.zeros((1, UNIVERSO)), cum[:-1]])       # info < t

    def janela(w: int) -> np.ndarray:
        c = np.vstack([np.zeros((1, UNIVERSO)), cum])
        j = c[np.maximum(np.arange(T) , 0)] - c[np.maximum(np.arange(T) - w, 0)]
        return j

    ultimo = np.full((T, UNIVERSO), -1.0)
    visto = np.full(UNIVERSO, -1.0)
    for t in range(T):
        ultimo[t] = visto
        visto = np.where(M[t] > 0, t, visto)
    atraso = np.arange(T)[:, None] - ultimo

    # markov por dezena: P(sai em t | saiu em t-1), estimado só com o passado
    n1 = np.vstack([np.zeros((1, UNIVERSO)), np.cumsum(M[:-1], axis=0)])
    n11 = np.zeros((T, UNIVERSO))
    acc = np.zeros(UNIVERSO)
    for t in range(1, T):
        n11[t] = acc
        acc = acc + M[t] * M[t - 1]
    markov = (n11 + 1.0) / (n1 + 2.0)

    # posição média de extração acumulada (eco posicional)
    pos = np.zeros((T, UNIVERSO))
    for i in range(T):
        for p in range(SORTEADAS):
            pos[i, h.ordem[i, p] - 1] = p + 1
    soma_pos = np.vstack([np.zeros((1, UNIVERSO)), np.cumsum(pos[:-1], axis=0)])
    pos_media = soma_pos / np.maximum(freq_ate, 1)

    # atrito de pares: força de ligação com o concurso anterior
    atrito = np.zeros((T, UNIVERSO))
    C = np.zeros((UNIVERSO, UNIVERSO))
    for t in range(1, T):
        ant = h.matriz[t - 1].astype(float)
        atrito[t] = C @ ant
        C += np.outer(M[t - 1], M[t - 1])
    return {
        "freq": freq_ate, "j5": janela(5), "j20": janela(20), "j50": janela(50),
        "j100": janela(100), "atraso": atraso, "markov": markov,
        "pos_media": pos_media, "atrito": atrito,
        "anterior": np.vstack([np.zeros((1, UNIVERSO)), M[:-1]]),
    }


def escores_dos_preditores(h: Historico, rng: np.random.Generator
                           ) -> Dict[str, np.ndarray]:
    """Cada preditor vira uma matriz T×25 de notas. As 15 maiores são a aposta.

    Um desempate aleatório fixo entra em todas: sem ele, "as 15 mais quentes"
    quando há empate viraria "as de número menor", e eu estaria medindo uma
    preferência por dezenas baixas, não a teoria.
    """
    S = matrizes_de_estado(h)
    T = h.T
    ruido = rng.random((T, UNIVERSO)) * 1e-6
    P = {
        "quente_global":      S["freq"],
        "frio_global":        -S["freq"],
        "quente_5":           S["j5"],
        "quente_20":          S["j20"],
        "quente_50":          S["j50"],
        "quente_100":         S["j100"],
        "frio_50":            -S["j50"],
        "mais_atrasadas":     S["atraso"],
        "menos_atrasadas":    -S["atraso"],
        "repetir_anterior":   S["anterior"],
        "complemento_anterior": -S["anterior"] * 10 + S["freq"] * 1e-3,
        "espelho_anterior":   S["anterior"][:, ::-1],
        "markov_dezena":      S["markov"],
        "eco_posicional":     -S["pos_media"],
        "atrito_pares":       S["atrito"],
        "aleatorio":          rng.random((T, UNIVERSO)),
    }
    return {k: v + ruido for k, v in P.items()}


def bateria_ranking(h: Historico, ini: int, fim: int, rng: np.random.Generator
                    ) -> Dict[str, float]:
    """Quantas das 15 cada teoria acerta, contra a linha de base exata de 9,0.

    O detalhe que decide tudo: sob acaso, QUALQUER conjunto de 15 acerta 9,0 em
    média. Não é aproximação — é 15×15/25. Então este teste é limpo: não
    depende de estimar nada, o alvo é um número fechado.
    """
    esc = escores_dos_preditores(h, rng)
    out: Dict[str, float] = {}
    alvo = h.matriz[ini:fim]
    n = fim - ini
    for nome, E in esc.items():
        e = E[ini:fim]
        idx = np.argpartition(-e, SORTEADAS - 1, axis=1)[:, :SORTEADAS]
        acertos = np.take_along_axis(alvo, idx, axis=1).sum(axis=1)
        media = float(acertos.mean())
        out[f"rank.{nome}"] = (media - MEDIA_INTER) * np.sqrt(n) / DP_INTER
        out[f"rank.{nome}.media_acertos"] = media
    return out


# ═══════════════════════════════════════════════ a bateria inteira
def bateria_completa(h: Historico, ini_rank: int, fim_rank: int,
                     rng: np.random.Generator,
                     excluir: Tuple[int, ...] = ()) -> Dict[str, float]:
    r: Dict[str, float] = {}
    r.update(bateria_estrutural(h))
    r.update(bateria_dependencia(h, excluir=excluir))
    r.update(bateria_ranking(h, ini_rank, fim_rank, rng))
    return r


def apenas_testes(r: Dict[str, float]) -> Dict[str, float]:
    """Só as chaves que são z de teste — as auxiliares não entram no máximo."""
    return {k: v for k, v in r.items()
            if not k.endswith(".media_acertos") and not k.endswith(".media_bruta")}
