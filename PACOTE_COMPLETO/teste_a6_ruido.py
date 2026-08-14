# -*- coding: utf-8 -*-
"""
TESTE DO A6 — a inteligencia enxerga padrao onde NAO EXISTE?

Alimenta o aplicador A6 com sequencias 100% aleatorias e conta quantas vezes
ele AFIRMA ver convergencia. Nao ha nada para ver: qualquer afirmacao aqui e'
invencao.

    python teste_a6_ruido.py            30 rodadas
    python teste_a6_ruido.py --n 60

Como ler o resultado:

    ate ~10%   a lente e' honesta; o voto dela vale
    10 a 30%   confabula as vezes; peso reduzido
    acima 30%  inventa padrao em ruido; o voto NAO deve entrar na mesa

Este teste custa chamadas de API. Rode uma vez para calibrar, nao a cada ciclo.
"""
import sys, os, random, argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30, help="quantas rodadas de ruido")
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()

from academia_autonoma import aplicador_llm
from academia_autonoma.dsl_hipoteses import pred_candidatos

if not aplicador_llm.disponivel():
    print("A6 nao esta configurado (sem chave de API em llm_config.json).")
    print("Sem ele, a mesa roda com as outras 5 lentes normalmente.")
    raise SystemExit(0)

ROL = [str(i) for i in range(37)]
rng = random.Random(args.seed)

def teorias_falsas(hist, quantas=8):
    """Teorias plausiveis mas SEM valor — apontam numeros ao acaso."""
    out = []
    for i in range(quantas):
        alvo = rng.choice(ROL)
        gat = hist[0]
        n_rec = rng.randint(4, 10)
        acertos = rng.randint(0, n_rec)          # desempenho tambem aleatorio
        out.append({
            "id": f"FAKE{i}", "dataset_id": "lightning",
            "expr": {"op": "transition", "a": gat, "b": alvo},
            "descricao": f"apos {gat} vem {alvo}",
            "prospectivo": {
                "n": n_rec, "hits": acertos,
                "hist": [{"hit": j < acertos, "baseline_hit": rng.random() < 0.19}
                         for j in range(n_rec)],
            },
        })
    return out

print(f"Testando o A6 com {args.n} sequencias ALEATORIAS.")
print("Nao ha padrao nenhum nelas. Toda afirmacao e' invencao.\n")

afirmou = 0
confs = []
erros = 0
exemplos = []

for r in range(args.n):
    hist = [rng.choice(ROL) for _ in range(60)]
    cab = teorias_falsas(hist)
    res = aplicador_llm.opinar(hist, ROL, cab, pred_candidatos, k=7)
    if res.get("erro"):
        erros += 1
        if erros <= 2:
            print(f"  [erro] {res['erro']}")
        continue
    nums = res.get("numeros") or []
    if nums:
        afirmou += 1
        confs.append(res.get("confianca", 0))
        if len(exemplos) < 3:
            exemplos.append((nums, round(res.get("confianca", 0), 2), res.get("motivo", "")))
    print(f"  {r+1:>3}/{args.n}  {'AFIRMOU ' + str(nums[:4]) if nums else 'nao viu padrao'}")

validas = args.n - erros
print("\n" + "=" * 62)
if not validas:
    print("Nenhuma rodada valida — verifique a chave de API e a rede.")
    raise SystemExit(1)

pct = 100 * afirmou / validas
print(f"Afirmou ver padrao em {afirmou} de {validas} sequencias aleatorias  ({pct:.0f}%)")
if confs:
    print(f"Confianca media quando afirmou: {sum(confs)/len(confs):.2f}")
print("=" * 62)
if pct <= 10:
    veredito, peso = "HONESTA — o voto dela vale integral", 1.0
elif pct <= 30:
    veredito, peso = "CONFABULA AS VEZES — peso reduzido", 0.5
else:
    veredito, peso = "INVENTA PADRAO EM RUIDO — nao deve votar", 0.0
print(f"{veredito}   (peso sugerido: {peso})")

if exemplos:
    print("\nExemplos do que ela 'viu' em dados sem padrao nenhum:")
    for nums, cf, mot in exemplos:
        print(f"  {nums} conf={cf} — {mot[:90]}")

Path("a6_calibracao.json").write_text(json.dumps({
    "rodadas": validas, "afirmou": afirmou, "pct_falso_positivo": round(pct, 1),
    "peso_sugerido": peso,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n-> a6_calibracao.json gravado (a mesa le o peso daqui)")
