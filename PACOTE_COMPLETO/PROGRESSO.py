# -*- coding: utf-8 -*-
"""
PROGRESSO — o estado do estudo numa tela só.

    python PROGRESSO.py

Feito para quem deixa o software rodando dias e quer conferir de manhã sem
abrir log nenhum. Mostra, por mesa: quantos giros já entraram, o estado de
cada compromisso pré-declarado, as teorias do Crazy Time, e quanto falta para
cada uma fechar.

Não decide nada e não escreve nada. Só lê e conta.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

JOGOS = ["lightning", "mega_fire", "crazy_time", "crazy_time_a", "red_door"]
LARG = 78


def linha(c="─"):
    print(c * LARG)


def cabeca(t):
    print()
    linha("═")
    print(f" {t}")
    linha("═")


def _giros(jogo):
    try:
        from fluxo_captura import buffer_path, _purge_invalid
        d = json.loads(Path(buffer_path(jogo)).read_text(encoding="utf-8"))
        ev = _purge_invalid(d.get("events") or [], jogo)
        brutos = len(d.get("events") or [])
        if not ev:
            return 0, 0, None, None
        ts = sorted(e.get("settled") or "" for e in ev)
        return len(ev), brutos - len(ev), ts[0][:16], ts[-1][:16]
    except Exception:
        return 0, 0, None, None


def _horas(a, b):
    try:
        d = datetime.fromisoformat(b) - datetime.fromisoformat(a)
        return d.total_seconds() / 3600
    except Exception:
        return 0.0


cabeca("COLETA")
print(f" {'mesa':<12} {'giros':>7} {'duplicatas':>11} {'de':>17} {'até':>17}")
linha()
total = 0
for j in JOGOS:
    n, dup, ini, fim = _giros(j)
    total += n
    if not n:
        print(f" {j:<12} {'sem coleta':>7}")
        continue
    h = _horas(ini, fim) if (ini and fim) else 0
    print(f" {j:<12} {n:>7} {dup:>11} {ini:>17} {fim:>17}   ({h:.1f}h)")
linha()
print(f" {'TOTAL':<12} {total:>7} giros")

cabeca("COMPROMISSOS PRÉ-DECLARADOS")
print(" Fórmulas travadas antes do dado. O veredito só sai no tamanho")
print(" combinado — nunca na primeira vez que o número agrada.")
print()
try:
    from academia_autonoma import hipoteses_predeclaradas as HP
    achou = False
    for j in JOGOS:
        rs = [r for r in HP.avaliar(j) if r["n"]]
        if not rs:
            continue
        achou = True
        print(f" {j.upper()}")
        for r in rs:
            falta = max(0, r["n_alvo"] - r["n"])
            barra = int(28 * min(1.0, r["n"] / max(1, r["n_alvo"])))
            pct = 100 * min(1.0, r["n"] / max(1, r["n_alvo"]))
            print(f"   {r['id']:<4} {r['hits']:>4}/{r['n']:<5} = {r['taxa']:>5.1%} "
                  f"(acaso {r['base']:.1%})  {r['razao']:>5.2f}x   {r['veredito']}")
            print(f"        [{'█'*barra}{'·'*(28-barra)}] {pct:>3.0f}%"
                  + (f"  faltam {falta} ativações" if falta else "  pronto para veredito"))
            print(f"        {r['nome']}")
        print()
    if not achou:
        print(" nenhuma ativação registrada ainda — deixe rodando")
except Exception as e:
    print(f" indisponível: {type(e).__name__}: {e}")

cabeca("TEORIAS DO OPERADOR — CRAZY TIME")
try:
    from academia_autonoma.teorias_do_operador_ct import avaliar_ct, resumo_ct
    from fluxo_captura import buffer_path, _purge_invalid
    d = json.loads(Path(buffer_path("crazy_time")).read_text(encoding="utf-8"))
    ev = _purge_invalid(d.get("events") or [], "crazy_time")
    ev.sort(key=lambda e: e.get("settled") or "")
    res = avaliar_ct([str(e.get("valor")) for e in ev])
    if not res:
        print(" histórico curto ainda")
    for r in res:
        if not r["n"]:
            print(f"   {r['nome']}")
            print(f"        nenhuma ocorrência ainda")
            continue
        raz = f"{r['razao']:.2f}x" if r["razao"] is not None else "  -  "
        pt = f"p={r['p']:.3f}" if r["p"] is not None else "p=-"
        aviso = "  ← amostra pequena" if r["n"] < 25 else ""
        print(f"   {r['nome']}")
        print(f"        {r['hits']}/{r['n']} (esperado {r['base']:.0%})  {raz}  {pt}{aviso}")
except Exception as e:
    print(f" indisponível: {type(e).__name__}: {e}")

cabeca("ACADEMIA")
try:
    from academia_autonoma.catalogo_persistente import listar
    for j in JOGOS:
        cat = listar(j)
        if not cat:
            continue
        val = sum(1 for t in cat if str(t.get("estado", "")).startswith("validada"))
        mad = sum(1 for t in cat
                  if int((t.get("prospectivo") or {}).get("n") or 0) >= 8)
        arq = sum(1 for t in cat if t.get("estado") in
                  ("descartada_pelo_tribunal", "arquivada"))
        print(f" {j:<12} catálogo {len(cat):>3}   maduras {mad:>3}   "
              f"validadas {val:>3}   arquivadas {arq:>3}")
except Exception as e:
    print(f" indisponível: {type(e).__name__}: {e}")

print()
linha("═")
print(" Para gerar a página visual:  python relatorio_visual.py")
linha("═")
print()
