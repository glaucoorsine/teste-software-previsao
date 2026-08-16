# -*- coding: utf-8 -*-
"""
REPLAY — roda o núcleo sobre o histórico dele como se fosse ao vivo.

    python REPLAY.py
    python REPLAY.py --k 8 --min 80

    "faz o teste com os históricos, você já tem todos, roda um teste aí como
     se fosse ao vivo"

O QUE "COMO SE FOSSE AO VIVO" EXIGE
───────────────────────────────────
Caminha do giro mais ANTIGO para o mais NOVO. Em cada passo, o núcleo vê
exatamente o que veria na máquina dele naquele instante — nem um giro a mais —
e emite os k números. Só então o giro seguinte é revelado, contado no placar,
e devolvido como histórico para o passo seguinte.

Isso é diferente de tudo que eu medi antes. A minha "caminhada" andava para
TRÁS: para cada alvo, eu lia o histórico que vinha depois dele na lista. Cada
previsão isolada era limpa, mas o conjunto reusava o mesmo arquivo dos dois
lados e as previsões saíam quase idênticas — 47 distintas em 206. Aqui o
histórico CRESCE, a realimentação da F45/F46/F48 atua, e cada previsão é
mesmo uma previsão nova.

O VEREDITO NÃO É MEU
────────────────────
No fim, a família 12 da Régua dele decide o que pode ser dito:

    R12-VET-01  integridade é produto de portas binárias
    R12-VET-02  suporte efetivo, medido na previsão e no acerto
    R12-VET-03  controle negativo obrigatório
    R12-VET-05  vetado / dormente / não concluir / pode afirmar

Se ele disser NÃO CONCLUIR, é isso que sai na tela, por melhor que esteja a
taxa. Já me enganei três vezes lendo taxa boa como resultado.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import PREVER as P  # noqa: E402
from NUCLEO import base as B  # noqa: E402
from NUCLEO import regua as R  # noqa: E402
from NUCLEO import veto as V  # noqa: E402


def carregar() -> Dict[str, List[List[dict]]]:
    """As bases dele, agrupadas por mesa, em ordem CRONOLÓGICA.

    Os arquivos vêm recente-primeiro (é como a captura entrega). Para o replay
    a lista é invertida: o passado tem que vir antes do futuro.
    """
    por_mesa: Dict[str, List[List[dict]]] = defaultdict(list)
    for arq in sorted(glob.glob(str(RAIZ / "bases_estudo" / "*.json"))):
        if Path(arq).name == "INDICE.json":
            continue
        try:
            d = json.load(open(arq, encoding="utf-8"))
        except Exception:
            continue
        ev = [e for e in (d.get("events") or []) if isinstance(e, dict)]
        linhas = []
        for i, e in enumerate(ev):
            try:
                n = int(e.get("n", e.get("result")))
            except (TypeError, ValueError):
                continue
            linha = {"n": n, "event_id": f"{Path(arq).stem}#{i}"}
            if e.get("tags"):
                linha["tags"] = e["tags"]
            elif e.get("mult"):
                linha["tags"] = [{"lucky": [{"n": n, "x": e["mult"]}]}]
            linhas.append(linha)
        if len(linhas) >= 40:
            por_mesa[d.get("jogo", "?")].append(list(reversed(linhas)))
    return por_mesa


def replay(cronologico: List[dict], jogo: str, k: int,
           minimo: int) -> P.Placar:
    """Anda do passado para o futuro. Cada previsão vê só o passado dela."""
    placar = P.Placar(B.classes_de(jogo))
    for i in range(minimo, len(cronologico)):
        # o que a captura entregaria neste instante: recente-primeiro
        visivel = list(reversed(cronologico[:i]))
        p = P.prever(visivel, jogo, k, placar)
        if not p["numeros"]:
            continue
        alvo = str(cronologico[i]["n"])
        placar.registrar(p["numeros"], alvo, p["palpites"])
    return placar


def julgar(placar: P.Placar, nome: str) -> Dict[str, Any]:
    c = placar.constituicao()
    print(f"\n  ── {nome}")
    print(placar.linha())
    s = c["silencio"]
    print(f"  cobertura: {s['motivo']}")
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay do núcleo no histórico dele.")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--min", type=int, default=90,
                    help="giros de aquecimento antes da primeira previsão")
    ap.add_argument("--mesa", default="")
    a = ap.parse_args()

    por_mesa = carregar()
    if not por_mesa:
        print("\n  Nenhuma base em bases_estudo/.")
        return 1

    print(f"\n  REPLAY — o núcleo sobre o histórico dele, como se fosse ao vivo.")
    print(f"  k={a.k} números, {a.min} giros de aquecimento, "
          f"previsão sempre ANTES do giro.\n")
    print(B.resumo())

    geral = {}
    for jogo, sessoes in sorted(por_mesa.items()):
        if a.mesa and jogo != a.mesa:
            continue
        total = sum(len(s) for s in sessoes)
        print(f"\n{'═' * 70}")
        print(f"  {jogo.upper()} — {len(sessoes)} sessão(ões), {total} giros")
        print("═" * 70)

        juntos = P.Placar(B.classes_de(jogo))
        for idx, sessao in enumerate(sessoes, 1):
            if len(sessao) <= a.min + 5:
                print(f"\n  ── sessão {idx}: {len(sessao)} giros — "
                      f"curta demais para {a.min} de aquecimento")
                continue
            pl = replay(sessao, jogo, a.k, a.min)
            julgar(pl, f"sessão {idx} ({len(sessao)} giros)")
            # acumula para o veredito da mesa
            juntos.acertos += pl.acertos
            juntos.rodadas += pl.rodadas
            juntos.esperado += pl.esperado
            juntos.previsoes.extend(pl.previsoes)
            juntos.certos.extend(pl.certos)
            juntos.emitiu.extend(pl.emitiu)

        if juntos.rodadas:
            print(f"\n  ══ {jogo.upper()}, todas as sessões ══")
            print(juntos.linha())
            c = juntos.constituicao()
            geral[jogo] = (juntos, c)

    # ── a aderência: as mesas dele são justas? ──────────────────────────
    print(f"\n{'═' * 70}")
    print("  A RODA É JUSTA?  (aderência ao uniforme — pergunta diferente)")
    print("═" * 70)
    for jogo, sessoes in sorted(por_mesa.items()):
        if a.mesa and jogo != a.mesa:
            continue
        series = [[e["n"] for e in s] for s in sessoes]
        j = R.mesa_e_justa(series, B.classes_de(jogo))
        print(f"  {jogo:<14} {j.get('motivo', '')}")

    # ── o veredito final, dele ──────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  VEREDITO — R12-VET-05, a régua dele")
    print("═" * 70)
    for jogo, (pl, c) in sorted(geral.items()):
        d = c["decisao"]
        print(f"\n  {jogo.upper():<14} {pl.razao:.2f}x sobre {pl.rodadas} rodadas")
        print(f"     {d['decisao']}: {d['porque'][:70]}")
        print(f"     suporte: {c['previsoes']['motivo'][:66]}")
    if not geral:
        print("\n  Nenhuma mesa teve rodadas suficientes.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
