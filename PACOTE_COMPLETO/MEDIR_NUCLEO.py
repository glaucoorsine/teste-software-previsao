# -*- coding: utf-8 -*-
"""
MEDIR O NÚCLEO NAS BASES REAIS DELE.

    python MEDIR_NUCLEO.py

A pergunta dele é sempre a mesma, e é a certa: "como está a acertividade?".

A COMPARAÇÃO HONESTA
────────────────────
Cada leitura aponta o tanto de classe que a fórmula dela produziu -- F01
aponta 12, F41 costuma apontar 1. Cobrar as duas contra o mesmo acaso de 12/37
seria fraude, e é a fraude mais fácil de cometer aqui. Então o acaso de cada
uma é o do TAMANHO QUE ELA APOSTA, acumulado previsão a previsão.

FORA DA AMOSTRA
───────────────
O giro que está sendo previsto nunca entra no histórico que o produziu. Sem
isso qualquer método "acerta" e a medição não vale nada -- é o vazamento
temporal que o compêndio dele descreve, e que a própria F36 do Tratado
denuncia.
"""
from __future__ import annotations

import glob
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import agregacao as A  # noqa: E402
from NUCLEO import base as B  # noqa: E402
from NUCLEO import leituras as L  # noqa: E402

K = 12                  # o teto que ele fixou: "20 números é demais, deixe até 12"
MIN_HIST = 90


def binom_cauda(k: int, n: int, p: float) -> float:
    if n <= 0 or k <= 0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
                        for i in range(k, n + 1)))


def carregar():
    for arq in sorted(glob.glob(str(RAIZ / "bases_estudo" / "*.json"))):
        if Path(arq).name == "INDICE.json":
            continue
        try:
            d = json.load(open(arq, encoding="utf-8"))
        except Exception:
            continue
        ev = d.get("events") or []
        if not isinstance(ev, list) or len(ev) < MIN_HIST + 15:
            continue
        nums, mults = [], []
        for e in ev:
            if not isinstance(e, dict):
                continue
            try:
                nums.append(int(e.get("n", e.get("result"))))
            except (TypeError, ValueError):
                continue
            try:
                mults.append(float(e.get("mult", e.get("multiplier", 0)) or 0))
            except (TypeError, ValueError):
                mults.append(0.0)
        if len(nums) >= MIN_HIST + 15:
            yield Path(arq).name, d.get("jogo", "?"), nums, mults


def medir(nums, mults, n_classes=37):
    ac = defaultdict(int)
    tn = defaultdict(int)
    esp = defaultdict(float)
    a12 = n12 = 0
    e12 = 0.0
    for i in range(0, len(nums) - MIN_HIST):
        alvo = str(nums[i])
        passado = nums[i + 1:]
        pm = mults[i + 1:] if mults else []
        r = L.executar(passado, n_classes, {"mults": pm}, k=K)
        for fam, palpite in (r.get("palpites") or {}).items():
            p = palpite[:K]
            if not p:
                continue
            tn[fam] += 1
            esp[fam] += len(set(p)) / n_classes
            if alvo in p:
                ac[fam] += 1
        ag = A.consenso(r.get("pesos") or {}, k=K)
        if ag["ordem"]:
            o = ag["ordem"][:K]
            n12 += 1
            e12 += len(set(o)) / n_classes
            if alvo in o:
                a12 += 1
    return ac, tn, esp, a12, n12, e12


def linha(nome, a, n, e):
    if not n:
        return f"  {nome:<20}      — não opinou"
    acaso = e / n
    taxa = a / n
    razao = taxa / acaso if acaso else 0
    p = binom_cauda(a, n, acaso)
    marca = "  <<<" if (p < 0.05 and razao > 1) else ""
    return (f"  {nome:<20} {a:4d}/{n:<4d} {taxa:6.1%}  acaso {acaso:5.1%} "
            f"({acaso * 37:4.1f} núm)  {razao:5.2f}x  p={p:6.4f}{marca}")


def main() -> int:
    print("\n  Medindo o NÚCLEO — as 44 famílias dele — nas bases reais.")
    print(f"  k={K}, fora da amostra, contra o acaso do MESMO tamanho.\n")
    ga, gn, ge = defaultdict(int), defaultdict(int), defaultdict(float)
    g12a = g12n = 0
    g12e = 0.0
    por_jogo = {}
    bases = list(carregar())
    if not bases:
        print("  Nenhuma base em bases_estudo/.")
        return 0
    for nome, jogo, nums, mults in bases:
        n_classes = B.classes_de(jogo)
        print(f"  ── {nome}  ({jogo}, {len(nums)} giros)")
        a, n, e, a12, n12, e12 = medir(nums, mults, n_classes)
        J = por_jogo.setdefault(jogo, [defaultdict(int), defaultdict(int),
                                       defaultdict(float), 0, 0, 0.0])
        for fam in n:
            ga[fam] += a.get(fam, 0); gn[fam] += n[fam]; ge[fam] += e[fam]
            J[0][fam] += a.get(fam, 0); J[1][fam] += n[fam]; J[2][fam] += e[fam]
        J[3] += a12; J[4] += n12; J[5] += e12
        g12a += a12; g12n += n12; g12e += e12
    print()
    for jogo in sorted(por_jogo):
        Aa, Nn, Ee, A2, N2, E2 = por_jogo[jogo]
        print(f"  ══ {jogo.upper()} ══")
        for fam, _fn in L.LEITURAS:
            if Nn.get(fam):
                print(linha(fam, Aa[fam], Nn[fam], Ee[fam]))
        print(linha("CONSENSO (IA12)", A2, N2, E2))
        print()
    print("  ══ TODAS AS MESAS ══")
    ordenado = sorted((f for f, _x in L.LEITURAS if gn.get(f)),
                      key=lambda f: -(ga[f] / gn[f]) / max(1e-9, ge[f] / gn[f]))
    for fam in ordenado:
        print(linha(fam, ga[fam], gn[fam], ge[fam]))
    print(linha("CONSENSO (IA12)", g12a, g12n, g12e))
    print("\n  1,00x = está no acaso. p<0,05 marcado com <<<.")
    print("  Testando 44 famílias, a melhor delas passa de 0,05 por sorte")
    print("  em ~90% das vezes — é a armadilha das fichas 201-300 dele.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
