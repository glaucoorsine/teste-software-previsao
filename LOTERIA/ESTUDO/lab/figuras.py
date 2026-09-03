# -*- coding: utf-8 -*-
"""FIGURAS — cada uma existe para responder uma pergunta, não para enfeitar."""
from __future__ import annotations
import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, "lab")
from base import FIGURAS, RESULTADOS, DP_INTER, PMF_INTER, carregar, historia_falsa

plt.rcParams.update({
    "figure.dpi": 170, "savefig.dpi": 170, "font.size": 8.4,
    "font.family": "DejaVu Sans", "axes.grid": True, "grid.alpha": 0.22,
    "grid.linewidth": 0.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.7, "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "axes.titlesize": 9.2, "axes.titleweight": "bold", "legend.frameon": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})
TINTA = "#1c2833"; REAL = "#b3402f"; NULO = "#4a6d8c"; VERDE = "#3d7a52"; CINZA = "#9aa5ad"


def salvar(fig, nome):
    FIGURAS.mkdir(exist_ok=True)
    fig.tight_layout(pad=0.7)
    fig.savefig(FIGURAS / nome, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ", nome)


def main():
    h = carregar()
    prot = json.loads((RESULTADOS / "protocolo.json").read_text(encoding="utf-8"))
    pers = json.loads((RESULTADOS / "persistencia.json").read_text(encoding="utf-8"))
    asse = json.loads((RESULTADOS / "assertividade.json").read_text(encoding="utf-8"))
    inov = json.loads((RESULTADOS / "inovacoes.json").read_text(encoding="utf-8"))

    # 1 ── o controle negativo
    amostra = np.array(prot["controle_negativo"]["amostra"])
    cn = prot["controle_negativo"]
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    ax.hist(amostra, bins=34, color=NULO, alpha=0.72, edgecolor="white", linewidth=0.4)
    for q, lab, c, alt in ((cn["max_z_p50"], "mediana do acaso", "#5a6b78", 0.60),
                           (cn["max_z_p95"], "p95 do acaso", TINTA, 0.90)):
        ax.axvline(q, color=c, lw=1.1, ls="--")
        ax.text(q, ax.get_ylim()[1]*alt, f"  {lab} = {q:.2f}", fontsize=7.2,
                color=c, va="top", fontweight="bold")
    zr = max(abs(v["z"]) for v in prot["veredicto"].values())
    ax.axvline(zr, color=REAL, lw=1.6)
    ax.text(zr, ax.get_ylim()[1]*0.36, f" maior |z| no dado REAL: {zr:.2f}",
            fontsize=7.4, color=REAL, fontweight="bold")
    ax.set_xlabel("maior |z| que a bateria de 689 testes produziu na história")
    ax.set_ylabel("histórias falsas")
    ax.set_title("Figura 1 — O que a busca inventa sozinha: 200 de 1.000 histórias de acaso puro")
    salvar(fig, "01_controle_negativo.png")

    # 2 ── as 25 dezenas
    z = np.array(pers["z_total"]); ordem = np.argsort(-z)
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    cores = [REAL if abs(v) > 2 else NULO for v in z[ordem]]
    ax.bar(range(25), z[ordem], color=cores, width=0.72)
    ax.axhline(0, color=TINTA, lw=0.8)
    for k, ls in ((2, "--"), (-2, "--")):
        ax.axhline(k, color=CINZA, lw=0.8, ls=ls)
    ax.set_xticks(range(25))
    ax.set_xticklabels([f"{i+1:02d}" for i in ordem], fontsize=6.6)
    ax.set_xlabel("dezena"); ax.set_ylabel("z da frequência")
    ax.set_title(f"Figura 2 — As 25 dezenas em 3.246 concursos  (χ² = {pers['veredicto']['chi2_total']['observado']:.2f}, "
                 f"df = 24, p isolado = {pers['veredicto']['chi2_total']['p_unilateral_maior']:.4f})")
    salvar(fig, "02_frequencia_25_dezenas.png")

    # 3 ── persistência fora da amostra
    zd = np.array(pers["z_por_dezena"]["descoberta"]); zt = np.array(pers["z_por_dezena"]["teste"])
    zv = np.array(pers["z_por_dezena"]["validacao"])
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.5))
    for ax, (a, b, la, lb, key) in zip(axes, [
            (zd, zv, "descoberta (1–1948)", "validação (1949–2597)", "r_descoberta_x_validacao"),
            (zd, zt, "descoberta (1–1948)", "teste (2598–3246)", "r_descoberta_x_teste"),
            (zv, zt, "validação (1949–2597)", "teste (2598–3246)", "r_validacao_x_teste")]):
        ax.scatter(a, b, s=16, color=NULO, alpha=0.85, zorder=3)
        for i in (19, 15):
            ax.scatter(a[i], b[i], s=30, color=REAL, zorder=4)
            ax.annotate(f"{i+1}", (a[i], b[i]), fontsize=6.6, color=REAL,
                        xytext=(3, 3), textcoords="offset points", fontweight="bold")
        k = np.polyfit(a, b, 1); xs = np.linspace(a.min(), a.max(), 10)
        ax.plot(xs, np.polyval(k, xs), color=REAL, lw=1.0, alpha=0.75)
        ax.axhline(0, color=CINZA, lw=0.6); ax.axvline(0, color=CINZA, lw=0.6)
        r = pers["veredicto"][key]
        ax.set_title(f"r = {r['observado']:+.3f}   (p = {r['p_unilateral_maior']:.3f})", fontsize=8)
        ax.set_xlabel(la, fontsize=7); ax.set_ylabel(lb, fontsize=7)
    fig.suptitle("Figura 3 — O desvio se repete: as mesmas dezenas, em janelas que não se tocam",
                 fontsize=9.2, fontweight="bold", y=1.04)
    salvar(fig, "03_persistencia.png")

    # 4 ── repetições: exato x medido
    inr = inov["III_inercia"]
    ex = np.array(inr["pmf_exata"]); me = np.array(inr["pmf_medida"])
    ks = np.arange(4, 15)
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    w = 0.4
    ax.bar(ks - w/2, ex[ks]*100, w, label="exato (hipergeométrica)", color=NULO)
    ax.bar(ks + w/2, me[ks]*100, w, label="medido em 3.245 pares", color=REAL, alpha=0.85)
    ax.set_xticks(ks); ax.set_xlabel("dezenas repetidas do concurso anterior")
    ax.set_ylabel("% dos concursos"); ax.legend(fontsize=7.4)
    ax.set_title("Figura 4 — Repetição: o real cai em cima do exato (média medida "
                 f"{inr['media']:.4f} contra 9,0000)")
    salvar(fig, "04_repeticoes.png")

    # 5 ── o teorema do ganho = 1
    linhas = [r for r in asse["regras"] if r["janela"] == "historico_todo"]
    x = np.array([r["assertividade_exata"] for r in linhas]) * 100
    y = np.array([r["assertividade_medida"] for r in linhas]) * 100
    fig, ax = plt.subplots(figsize=(5.0, 3.5))
    lo = min(x.min(), y.min()) - 2
    ax.plot([lo, 101], [lo, 101], color=CINZA, lw=1.0, ls="--", label="ganho = 1 (sem vantagem)")
    ax.scatter(x, y, s=20, color=REAL, zorder=3, alpha=0.82,
               edgecolor="white", linewidth=0.4)
    piores = np.argsort(-np.abs(np.array([r["ganho"] for r in linhas]) - 1))[:6]
    for i in piores:
        ax.annotate(linhas[i]["regra"], (x[i], y[i]), fontsize=5.6, color=TINTA,
                    xytext=(4, -1.5), textcoords="offset points")
    ax.set_xlabel("fração do espaço das 3.268.760 combinações  (%)")
    ax.set_ylabel("acerto medido nos 3.246 concursos  (%)")
    ax.legend(fontsize=7)
    ax.set_title(f"Figura 5 — Assertividade = tamanho.\n{len(linhas)} regras do catálogo, nenhuma fora da reta")
    salvar(fig, "05_ganho_igual_um.png")

    # 6 ── as teorias de ranking
    rj = prot["ranking_por_janela"]["teste"]
    nomes = sorted({k[5:].replace(".media_acertos", "") for k in rj if k.endswith(".media_acertos")},
                   key=lambda n: rj[f"rank.{n}.media_acertos"])
    v = [rj[f"rank.{n}.media_acertos"] for n in nomes]
    err = DP_INTER / np.sqrt(649) * 1.96
    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    cores = [REAL if abs(x_-9) > err else NULO for x_ in v]
    ax.barh(range(len(nomes)), np.array(v) - 9, left=9, color=cores, height=0.68)
    ax.errorbar(v, range(len(nomes)), xerr=err, fmt="none", ecolor=TINTA, elinewidth=0.8, capsize=2)
    ax.axvline(9.0, color=TINTA, lw=1.2)
    ax.axvspan(9 - err, 9 + err, color=CINZA, alpha=0.2)
    ax.set_yticks(range(len(nomes))); ax.set_yticklabels(nomes, fontsize=7)
    ax.set_xlabel("acertos médios por jogo de 15 dezenas — janela de teste (649 concursos)")
    ax.set_xlim(8.80, 9.20)
    ax.set_title("Figura 6 — 16 teorias contra a linha exata de 9,0 acertos\n(faixa cinza = ±IC 95%)")
    salvar(fig, "06_ranking_teorias.png")

    # 7 ── distribuições estruturais
    d = asse["distribuicoes_exatas"]
    fig, axes = plt.subplots(2, 2, figsize=(6.8, 4.0))
    for ax, chave, titulo in zip(axes.ravel(),
            ["soma", "pares", "moldura", "consecutivos"],
            ["soma das 15 dezenas", "quantidade de pares", "dezenas na moldura",
             "pares de dezenas vizinhas"]):
        ex = np.array(d[chave]["exato"]); me = np.array(d[chave]["medido"])
        v = np.arange(len(ex)); m = ex > (1e-4 if chave == "soma" else 0)
        if chave == "soma":
            ax.plot(v[m], ex[m]*100, color=NULO, lw=1.2, label="exato")
            ax.plot(v[m], me[m]*100, color=REAL, lw=0.8, alpha=0.85, label="medido")
        else:
            w = 0.4
            ax.bar(v[m]-w/2, ex[m]*100, w, color=NULO, label="exato")
            ax.bar(v[m]+w/2, me[m]*100, w, color=REAL, alpha=0.85, label="medido")
        ax.set_title(titulo, fontsize=8); ax.legend(fontsize=6.4)
        ax.xaxis.set_major_locator(MaxNLocator(8))
    fig.suptitle("Figura 7 — Quatro formas do sorteio: exato por enumeração contra medido",
                 fontsize=9.2, fontweight="bold", y=1.02)
    salvar(fig, "07_distribuicoes_estruturais.png")

    # 8 ── a autópsia do falso positivo
    M = h.matriz.astype(float); T = h.T
    fig, ax = plt.subplots(figsize=(6.4, 2.7))
    lags = np.arange(1, 13)
    for dz, cor, mk in ((20, REAL, "o"), (16, NULO, "s")):
        i = dz - 1; pr = M[:, i].mean()
        z0, z1 = [], []
        for lag in lags:
            a, b = M[lag:, i], M[:-lag, i]; n = T - lag; n11 = float((a*b).sum())
            z0.append((n11 - n*0.36)/np.sqrt(n*0.36*0.64))
            z1.append((n11 - n*pr**2)/np.sqrt(n*pr**2*(1-pr**2)))
        ax.plot(lags, z0, marker=mk, ms=3.4, color=cor, lw=1.1,
                label=f"dezena {dz} — nulo p = 0,600 (errado)")
        ax.plot(lags, z1, marker=mk, ms=3.4, color=cor, lw=1.1, ls=":", alpha=0.75,
                label=f"dezena {dz} — nulo p = {pr:.3f} (correto)")
    ax.axhline(0, color=TINTA, lw=0.8)
    for k in (2, -2): ax.axhline(k, color=CINZA, lw=0.7, ls="--")
    ax.set_xlabel("lag (concursos)"); ax.set_ylabel("z da autocorrelação")
    ax.legend(fontsize=6.6, ncol=2)
    ax.set_title("Figura 8 — Autópsia dos 3 'sobreviventes': a memória some quando o nulo é o certo")
    salvar(fig, "08_autopsia_falso_positivo.png")

    # 9 ── ponte browniana
    p = 0.6
    desv = np.cumsum(h.matriz - p, axis=0)
    esc = np.sqrt(np.arange(1, T+1) * p * (1-p))[:, None]
    ponte = desv / esc
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    for i in range(25):
        dz = i + 1
        destaque = dz in (20, 16)
        ax.plot(h.concursos, ponte[:, i], lw=1.25 if destaque else 0.5,
                color=(REAL if dz == 20 else VERDE) if destaque else CINZA,
                alpha=1.0 if destaque else 0.5, zorder=3 if destaque else 1,
                label=f"dezena {dz}" if destaque else None)
    for k in (2, -2, 3, -3):
        ax.axhline(k, color=TINTA, lw=0.6, ls="--", alpha=0.5)
    ax.axhline(0, color=TINTA, lw=0.8)
    ax.set_xlim(200, 3246); ax.set_ylim(-4.4, 4.4)
    ax.set_xlabel("concurso"); ax.set_ylabel("desvio acumulado padronizado")
    ax.legend(fontsize=7)
    ax.set_title("Figura 9 — 21 anos de desvio acumulado: as 25 trajetórias")
    salvar(fig, "09_ponte_browniana.png")

    # 10 ── χ² por janela contra o nulo
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    rng = np.random.default_rng(3)
    nulo = []
    for _ in range(2500):
        f = historia_falsa(649, rng)
        tot = f.matriz.sum(axis=0)
        nulo.append(float((((tot - 649*p)/np.sqrt(649*p*(1-p)))**2).sum()))
    ax.hist(nulo, bins=44, color=NULO, alpha=0.7, edgecolor="white", linewidth=0.3,
            label="χ² em janelas de 649 concursos de acaso puro")
    for nome, key, cor in (("validação", "chi2_validacao", REAL), ("teste", "chi2_teste", VERDE)):
        v = pers["veredicto"][key]["observado"]
        ax.axvline(v, color=cor, lw=1.5)
        ax.text(v, ax.get_ylim()[1]*0.9, f" {nome}\n {v:.1f}", fontsize=7, color=cor, fontweight="bold")
    ax.set_xlabel("χ² de uniformidade das 25 dezenas (df = 24)")
    ax.set_ylabel("frequência"); ax.legend(fontsize=7, loc="upper right")
    ax.set_title("Figura 10 — As duas janelas fora da amostra, contra o acaso")
    salvar(fig, "10_chi2_por_janela.png")


if __name__ == "__main__":
    print("gerando figuras:")
    main()
