# -*- coding: utf-8 -*-
"""
RELATÓRIO VISUAL — o estado das teorias, numa página.

    python relatorio_visual.py                (usa os buffers de coleta)
    python relatorio_visual.py saida.html

A página inteira é organizada em torno de UMA régua horizontal centrada em
1,00x (o acaso). Toda medida está plotada nela. Isso é deliberado: o resultado
honesto de quase tudo é ficar em cima da linha do meio, e um relatório que
esconde isso em tabelas separadas mente por omissão.
"""
from __future__ import annotations

import html
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

VOIS = {22, 18, 29, 7, 28, 12, 35, 3, 26, 0, 32, 15, 19, 4, 21, 2, 25}
TIERS = {27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33}
ORF = {17, 34, 6, 1, 20, 14, 31, 9}
JOGOS = ["lightning", "mega_fire", "immersive", "crazy_time"]
CT_FATIAS = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2, "CrazyBonus": 1}


def _p_ge(h, n, p):
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1)
                        + k * math.log(p) + (n - k) * math.log(1 - p))
               for k in range(min(h, n), n + 1))


def carregar(jogo):
    """
    Lê o buffer de coleta do jogo.

    Procura em vários lugares porque o relatório costuma ser rodado de fora da
    pasta do software — de dentro de um Logs.zip extraído, por exemplo.
    """
    tentativas = []
    try:
        from fluxo_captura import buffer_path
        tentativas.append(Path(buffer_path(jogo)))
    except Exception:
        pass
    aqui = Path.cwd()
    raiz = Path(__file__).resolve().parent
    for base in (aqui, aqui / "Logs", raiz, raiz / "Logs"):
        tentativas.append(base / "hist_buffers" / f"{jogo}.json")
        tentativas.append(base / "logs" / "hist_buffers" / f"{jogo}.json")
    for p in tentativas:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            continue
        ev = sorted((d.get("events") or []), key=lambda e: e.get("settled") or "")
        return [e.get("valor") for e in ev]
    return []


def medidas_roleta(seq):
    s = []
    for x in seq:
        try:
            s.append(int(x))
        except (TypeError, ValueError):
            pass
    n = len(s)
    if n < 60:
        return []
    out = []
    for nome, S in [("Voisins du Zéro", VOIS), ("Tiers du Cylindre", TIERS),
                    ("Orphelins", ORF)]:
        h = sum(1 for x in s if x in S)
        base = len(S) / 37
        out.append({"grupo": "setor da roda", "nome": nome, "hits": h, "n": n,
                    "base": base, "razao": (h / n) / base, "p": _p_ge(h, n, base)})
    for g, nome in [((0, 1, 3, 6), "final 0-1-3-6"), ((4, 5, 9), "final 4-5-9"),
                    ((0, 2, 7, 8), "final 0-2-7-8")]:
        alvo = {x for x in range(37) if x % 10 in g}
        h = sum(1 for x in s if x in alvo)
        base = len(alvo) / 37
        out.append({"grupo": "família de final", "nome": nome, "hits": h,
                    "n": n, "base": base, "razao": (h / n) / base,
                    "p": _p_ge(h, n, base)})
    # a regra do operador: veio um da família, vem OUTRO da família.
    # A base é a taxa real da mesa, não a teórica — senão mesa quente naqueles
    # números faz toda regra parecer forte sem o gatilho ter nada a ver.
    for g, nome in [((4, 5, 9), "4-5-9 puxa 4-5-9"),
                    ((0, 1, 3, 6), "0-1-3-6 puxa 0-1-3-6"),
                    ((0, 2, 7, 8), "0-2-7-8 puxa 0-2-7-8")]:
        alvo = {x for x in range(37) if x % 10 in g}
        p_real = sum(1 for x in s if x in alvo) / n
        base = max(p_real - 1 / 37, 1e-9)
        h = t = 0
        for i in range(n - 1):
            if s[i] in alvo:
                t += 1
                if s[i + 1] in alvo and s[i + 1] != s[i]:
                    h += 1
        if t >= 20:
            out.append({"grupo": "regra do operador", "nome": nome, "hits": h,
                        "n": t, "base": base, "razao": (h / t) / base,
                        "p": _p_ge(h, t, base)})
    rep = sum(1 for i in range(n - 1) if s[i] == s[i + 1])
    out.append({"grupo": "repetição", "nome": "mesmo número seguido",
                "hits": rep, "n": n - 1, "base": 1 / 37,
                "razao": (rep / (n - 1)) * 37, "p": _p_ge(rep, n - 1, 1 / 37)})
    return out


def medidas_ct(seq):
    s = [str(x) for x in seq if str(x) in CT_FATIAS]
    n = len(s)
    if n < 60:
        return []
    out = []
    c = Counter(s)
    for sim, fat in CT_FATIAS.items():
        base = fat / 54
        if n * base < 5:
            continue
        out.append({"grupo": "símbolo", "nome": sim, "hits": c.get(sim, 0),
                    "n": n, "base": base, "razao": (c.get(sim, 0) / n) / base,
                    "p": _p_ge(c.get(sim, 0), n, base)})
    p_rep = sum((f / 54) ** 2 for f in CT_FATIAS.values())
    rep = sum(1 for i in range(n - 1) if s[i] == s[i + 1])
    out.append({"grupo": "repetição", "nome": "mesmo símbolo seguido",
                "hits": rep, "n": n - 1, "base": p_rep,
                "razao": (rep / (n - 1)) / p_rep, "p": _p_ge(rep, n - 1, p_rep)})
    bon = {"CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"}
    pb = sum(CT_FATIAS[x] for x in bon) / 54
    for k in (3, 5):
        h = t = 0
        seco = 0
        for x in s:
            if seco >= k:
                t += 1
                if x in bon:
                    h += 1
            seco = 0 if x in bon else seco + 1
        if t >= 20:
            out.append({"grupo": "bônus", "nome": f"bônus após {k}+ giros secos",
                        "hits": h, "n": t, "base": pb, "razao": (h / t) / pb,
                        "p": _p_ge(h, t, pb)})
    return out


def _cor(m):
    if m["p"] <= 0.01:
        return "v"
    if m["p"] <= 0.10:
        return "o"
    return "m"


def montar(dados, saida: Path) -> Path:
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    tot_perg = sum(len(v["medidas"]) for v in dados.values())
    tot_giros = sum(v["n"] for v in dados.values())
    fortes = sum(1 for v in dados.values() for m in v["medidas"] if m["p"] <= 0.05)

    def pos(m):
        r = max(0.5, min(2.0, m["razao"]))
        return (math.log(r) - math.log(0.5)) / (math.log(2.0) - math.log(0.5)) * 100

    L = []
    for jogo, v in dados.items():
        if not v["medidas"]:
            continue
        L.append(f'<h3 class="mesa">{html.escape(jogo)}'
                 f'<em>{v["n"]} giros</em></h3><div class="lista">')
        for m in sorted(v["medidas"], key=lambda x: -x["razao"]):
            c = _cor(m)
            L.append(
                f'<div class="linha"><div class="rot">{html.escape(m["nome"])}'
                f'<i>{html.escape(m["grupo"])}</i></div>'
                f'<div class="track"><span class="meio"></span>'
                f'<span class="ponto {c}" style="left:{pos(m):.2f}%"></span></div>'
                f'<div class="num"><b>{m["razao"]:.2f}x</b>'
                f'<span>{m["hits"]}/{m["n"]}</span></div>'
                f'<div class="pv {c}">p={m["p"]:.3f}</div></div>')
        L.append('</div>')

    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Estado das Teorias</title><style>
*{{box-sizing:border-box}}
:root{{--ground:#f4f3ee;--panel:#fffefb;--ink:#171c19;--ink2:#5c6761;
--line:#e1dfd5;--brass:#8a6a31;--track:#e8e6dc;
--v:#2f6b4c;--o:#8e7420;--m:#9a5044;--rule:#d6d3c7}}
@media(prefers-color-scheme:dark){{:root:not([data-theme="light"]){{
--ground:#0e120d;--panel:#151a14;--ink:#e8e7dd;--ink2:#909a8f;
--line:#262d25;--brass:#c4a263;--track:#212820;
--v:#5cab80;--o:#cfae49;--m:#c4776b;--rule:#2b3229}}}}
:root[data-theme="dark"]{{--ground:#0e120d;--panel:#151a14;--ink:#e8e7dd;
--ink2:#909a8f;--line:#262d25;--brass:#c4a263;--track:#212820;
--v:#5cab80;--o:#cfae49;--m:#c4776b;--rule:#2b3229}}
body{{margin:0;background:var(--ground);color:var(--ink);padding:52px 20px 88px;
font:17px/1.65 Georgia,'Iowan Old Style','Times New Roman',serif}}
.wrap{{max-width:920px;margin:0 auto}}
.eyebrow{{font:600 11px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.18em;
text-transform:uppercase;color:var(--brass);margin:0 0 16px}}
h1{{font-size:40px;line-height:1.12;margin:0 0 14px;font-weight:600;text-wrap:balance}}
.lede{{color:var(--ink2);margin:0 0 38px;max-width:60ch;font-size:19px}}
.contas{{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:8px}}
.conta{{background:var(--panel);padding:20px}}
.conta b{{display:block;font:600 30px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
font-variant-numeric:tabular-nums;margin-bottom:8px}}
.conta span{{font:500 11px/1.4 ui-sans-serif,system-ui,sans-serif;letter-spacing:.09em;
text-transform:uppercase;color:var(--ink2)}}
h2{{font:600 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.16em;
text-transform:uppercase;color:var(--brass);border-top:1px solid var(--rule);
padding-top:18px;margin:52px 0 6px}}
.h2sub{{color:var(--ink2);margin:0 0 22px;max-width:62ch;font-size:16px}}
.mesa{{font-size:21px;margin:30px 0 12px;font-weight:600}}
.mesa em{{font:500 11px/1 ui-sans-serif,system-ui,sans-serif;font-style:normal;
letter-spacing:.1em;text-transform:uppercase;color:var(--ink2);margin-left:12px}}
.lista{{display:flex;flex-direction:column;gap:1px;background:var(--line);
border:1px solid var(--line)}}
.linha{{display:grid;grid-template-columns:minmax(160px,1.4fr) minmax(130px,1.6fr) 88px 74px;
gap:16px;align-items:center;background:var(--panel);padding:12px 18px}}
.rot{{font-size:15px;line-height:1.3}}
.rot i{{display:block;font:500 10px/1.5 ui-sans-serif,system-ui,sans-serif;
font-style:normal;letter-spacing:.09em;text-transform:uppercase;color:var(--ink2)}}
.track{{position:relative;height:20px;background:var(--track);border-radius:2px}}
.meio{{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;
background:var(--brass);opacity:.6}}
.ponto{{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;
transform:translate(-50%,-50%)}}
.ponto.v{{background:var(--v)}}.ponto.o{{background:var(--o)}}.ponto.m{{background:var(--m)}}
.num{{font:600 15px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;
font-variant-numeric:tabular-nums;text-align:right}}
.num span{{display:block;font-weight:400;font-size:11px;color:var(--ink2)}}
.pv{{font:500 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
font-variant-numeric:tabular-nums;text-align:right;color:var(--ink2)}}
.pv.v{{color:var(--v)}}.pv.o{{color:var(--o)}}
.leg{{display:flex;gap:24px;flex-wrap:wrap;margin:18px 0 0;
font:500 11px/1.5 ui-sans-serif,system-ui,sans-serif;letter-spacing:.08em;
text-transform:uppercase;color:var(--ink2)}}
.leg i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}}
.nota{{background:var(--panel);border-left:2px solid var(--brass);padding:20px 24px;
margin-top:36px;font-size:16px;color:var(--ink2)}}
.nota b{{color:var(--ink)}}
@media(max-width:660px){{body{{padding:34px 16px 68px}}h1{{font-size:31px}}
.linha{{grid-template-columns:1fr 80px;gap:9px}}
.track{{grid-column:1/-1;order:3}}.pv{{grid-column:1/-1;order:4;text-align:left}}}}
</style></head><body><div class="wrap">
<p class="eyebrow">Estudo de mesas ao vivo &middot; {hoje}</p>
<h1>O que as réguas dizem hoje</h1>
<p class="lede">Cada medida está plotada na mesma escala. A linha central é o
acaso. Ficar em cima dela é o resultado esperado de uma mesa honesta — e é o
que acontece com quase tudo.</p>
<div class="contas">
<div class="conta"><b>{tot_giros}</b><span>giros reais</span></div>
<div class="conta"><b>{tot_perg}</b><span>perguntas feitas</span></div>
<div class="conta"><b>{fortes}</b><span>com p ≤ 0,05</span></div>
<div class="conta"><b>{tot_perg*0.05:.1f}</b><span>esperadas por acaso</span></div>
</div>
<h2>Medidas por mesa</h2>
{''.join(L)}
<div class="leg">
<span><i style="background:var(--v)"></i>p ≤ 0,01</span>
<span><i style="background:var(--o)"></i>p ≤ 0,10</span>
<span><i style="background:var(--m)"></i>sem força</span></div>
<div class="nota"><b>Como ler a coluna p.</b> Ela responde: se a mesa fosse
honesta, com que frequência o acaso produziria um número assim? Um p de 0,05
sozinho não prova nada quando foram feitas {tot_perg} perguntas — o acaso
entrega {tot_perg*0.05:.1f} delas de graça. Por isso o cabeçalho mostra as duas
contas lado a lado: quantas apareceram e quantas eram esperadas.</div>
</div></body></html>"""
    saida.write_text(doc, encoding="utf-8")
    return saida


def main():
    saida = Path(sys.argv[1] if len(sys.argv) > 1 else "relatorio_teorias.html")
    dados = {}
    for j in JOGOS:
        vals = carregar(j)
        if not vals:
            continue
        dados[j] = {"n": len(vals),
                    "medidas": medidas_ct(vals) if j == "crazy_time"
                    else medidas_roleta(vals)}
    if not dados:
        print("Nenhum histórico encontrado. Rode a coleta primeiro.")
        return 1
    montar(dados, saida)
    print(f"Relatório gerado: {saida.resolve()}")
    for j, v in dados.items():
        print(f"  {j:<12} {v['n']:>5} giros, {len(v['medidas']):>3} medidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
