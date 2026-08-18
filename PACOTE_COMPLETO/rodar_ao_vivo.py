# -*- coding: utf-8 -*-
"""
RODAR AO VIVO — entrega os giros reais ao software UM POR UM, em ordem,
exatamente como se estivessem chegando da mesa agora.

A regra que faz isso valer: no giro i o software só enxerga os giros 0..i.
A previsão dele é comparada com o giro i+1, que ele ainda NAO viu. Nenhuma
informacao do futuro entra — e' a mesma coisa que rodar ao vivo, so que o
tempo passa mais rapido.

Uso:
    python rodar_ao_vivo.py numeros.txt --jogo lightning

`numeros.txt`: os giros do MAIS ANTIGO para o MAIS RECENTE, separados por
espaco, virgula ou quebra de linha.
"""
import sys, os, json, argparse
from collections import Counter
from datetime import datetime, timedelta, timezone

ap = argparse.ArgumentParser()
ap.add_argument("arquivo", help="txt/json com os giros, do mais antigo ao mais recente")
ap.add_argument("--jogo", default="lightning",
                choices=["lightning", "mega_fire", "crazy_time", "crazy_time_a", "red_door"])
ap.add_argument("--raiz", default=".", help="pasta do PACOTE_COMPLETO")
ap.add_argument("--dados", default=None, help="pasta de dados da academia (isolada)")
ap.add_argument("--intervalo", type=int, default=45, help="segundos entre giros")
args = ap.parse_args()

RAIZ = os.path.abspath(args.raiz)
sys.path.insert(0, RAIZ)
os.environ["ACADEMIA_DATA_DIR"] = args.dados or os.path.join(RAIZ, "_dados_ao_vivo")
os.chdir(RAIZ)

CT_DOM = {"1","2","5","10","CoinFlip","CashHunt","Pachinko","CrazyBonus"}
is_ct = str(args.jogo).startswith("crazy_time")

# ---------- ler os giros ----------
bruto = open(args.arquivo, encoding="utf-8").read()
try:
    d = json.loads(bruto)
    if isinstance(d, dict):
        evs = d.get("events") or (d.get("jogos", {}).get(args.jogo, {}) or {}).get("events") or []
        itens = [e.get("valor") if e.get("valor") is not None else e.get("n") for e in evs]
        # AS TAGS PRECISAM SOBREVIVER — SEM ELAS O CACADOR NAO FALA.
        #
        # Este arquivo lia so o numero de cada giro e jogava o resto fora. Com
        # o Cacador de Multiplicador decidindo, isso e' fatal: ele le o sorteio
        # de lucky/fire/top slot, que vive nas `tags`. Sem elas ele fica mudo,
        # e como nao ha regua atras dele, a saida e' vazia em TODOS os giros.
        #
        # O relatorio entao dizia 0 acertos -- e 0 acertos por falta de dado
        # tem exatamente a mesma cara de 0 acertos por o metodo nao funcionar.
        eventos_crus = list(reversed(evs))
        # arquivos do pacote vem do mais RECENTE pro mais antigo
        itens = list(reversed(itens))
    else:
        itens = list(d)
except Exception:
    itens = [x for x in bruto.replace(",", " ").split() if x]

eventos_crus = locals().get("eventos_crus") or []
giros, descartados = [], []
for x in itens:
    s = str(x).strip()
    if is_ct:
        if s in CT_DOM: giros.append(s)
        else: descartados.append(s)
    else:
        try:
            n = int(s)
            if 0 <= n <= 36: giros.append(n)
            else: descartados.append(s)
        except Exception:
            descartados.append(s)

if descartados:
    print(f"[aviso] {len(descartados)} entradas descartadas: {descartados[:10]}")
if len(giros) < 60:
    print(f"ERRO: so {len(giros)} giros. O software precisa de historico pra comecar.")
    print("      Mande pelo menos 150 pra ter alguma leitura; 500+ pra valer.")
    raise SystemExit(1)

print(f"{len(giros)} giros reais de {args.jogo}, do mais antigo ao mais recente.")
print(f"Entregando um por um...\n")

import ia_modulos as im
T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
ts = lambda i: (T0 + timedelta(seconds=args.intervalo * i)).isoformat()

pipe = im.PipelinePerceptivo(args.jogo)
INICIO = min(120, len(giros) // 3)

sug = ok = err = 0
base_ok = base_err = 0
so_ele = so_base = 0
linhas = []

# as linhas cruas na mesma ordem do historico (recente primeiro)
def _linhas_ate(i, quantos):
    """As linhas COM tags, do giro i para tras, no formato que o motor espera."""
    if not eventos_crus:
        return None
    fatia = list(reversed(eventos_crus[:i + 1]))[:quantos]
    saida = []
    for k, e in enumerate(fatia):
        if not isinstance(e, dict):
            continue
        saida.append({"n": e.get("n", e.get("valor")),
                      "sec": e.get("valor", e.get("n")),
                      "settled": ts(i - k),
                      "tags": e.get("tags") or []})
    return saida or None


if not eventos_crus:
    print()
    print("  AVISO: este arquivo traz so os numeros, sem o sorteio de")
    print("  multiplicador de cada giro. Quem escolhe hoje e' o Cacador de")
    print("  Multiplicador, e ele le esse sorteio -- sem ele nao ha palpite,")
    print("  e o placar abaixo vai medir zero por falta de dado, nao por")
    print("  falta de metodo. Use um buffer do pacote (Logs/hist_buffers).")
    print()

for i in range(INICIO, len(giros) - 1):
    hist = list(reversed(giros[:i+1]))[:300]
    settled = [ts(i-k) for k in range(len(hist))]
    out = pipe.processar(hist, ok, err, settled=settled,
                         linhas=_linhas_ate(i, 300))

    alvos = [str(x) for x in (out.get("pad5") or [])]
    saiu = str(giros[i+1])                       # o software ainda NAO viu isto

    # regua: os 7 mais frequentes dos ultimos 40 (o que qualquer um faria)
    k = len(alvos) if alvos else 7
    base = [x for x, _ in Counter(str(g) for g in hist[:40]).most_common(k)]
    b_hit = saiu in base
    if b_hit: base_ok += 1
    else: base_err += 1

    if alvos:
        sug += 1
        hit = saiu in alvos
        if hit: ok += 1
        else: err += 1
        if hit != b_hit:
            if hit: so_ele += 1
            else: so_base += 1
        linhas.append((i+1, alvos, saiu, hit, out.get("modo")))

# ---------- relatorio ----------
n = ok + err
print("=" * 66)
print(f"RESULTADO — {args.jogo}, {len(giros)} giros reais")
print("=" * 66)
print(f"  giros avaliados ................ {len(giros)-1-INICIO}")
print(f"  giros com SUGESTAO na tela ..... {sug}")
if not sug:
    print("\n  O software nao sugeriu nada em nenhum giro.")
    print("  Isso nao e' erro: ele so fala quando tem evidencia. Com este")
    print("  volume, provavelmente nao houve teoria validada suficiente.")
    raise SystemExit(0)

taxa = 100*ok/n
print(f"  acertos ........................ {ok}")
print(f"  erros .......................... {err}")
print(f"  TAXA ........................... {taxa:.1f}%")
print()
nb = base_ok + base_err
print(f"  regua (7 mais quentes) ......... {100*base_ok/nb:.1f}%  em {nb} giros")

# significancia pareada (McNemar exato) nos giros em que houve sugestao
from math import comb
d = so_ele + so_base
if d:
    kmin = min(so_ele, so_base)
    p = min(1.0, sum(comb(d, i) for i in range(kmin+1)) / (2**d) * 2)
    print(f"\n  so ELE acertou: {so_ele}   so a regua acertou: {so_base}   p={p:.3f}")
    if p > 0.05:
        print("  -> a diferenca cabe dentro da sorte. Precisa de mais giros.")
    elif so_ele > so_base:
        print("  -> vantagem consistente sobre a regua.")
    else:
        print("  -> a regua e' melhor que o software neste periodo.")
else:
    print("\n  software e regua acertaram e erraram nos mesmos giros.")

print(f"\n{'giro':>6} {'sugeriu':<34} {'saiu':>5}  ")
print("-" * 66)
for g, a, s, h, mo in linhas[-25:]:
    print(f"{g:>6} {str(a)[:32]:<34} {s:>5}  {'ACERTOU' if h else ''}")
