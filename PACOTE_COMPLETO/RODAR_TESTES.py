# -*- coding: utf-8 -*-
"""
RODAR TUDO — a suíte inteira, com percentual e tempo restante.

    python RODAR_TESTES.py          (ou clique em RODAR_TESTES.bat)

Ele pediu: "teste absolutamente tudo e só me entregue tudo funcionando
perfeitamente" e "quando estiver em testes, me mostre o percentual de evolução
e tempo restante".

Cada teste roda em processo próprio. Um que trave não leva os outros junto: o
tempo limite corta, a suíte segue, e o relatório final diz qual foi.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from progresso_teste import Progresso, _mmss  # noqa: E402

# (arquivo, marca de sucesso no fim da saída, limite em segundos, custo típico)
#
# O CUSTO é em SEGUNDOS, medidos aqui. Onze destes levam um segundo e o último
# leva vinte minutos; sem declarar isso, a barra anunciaria "falta 4s" com
# vinte minutos pela frente — foi exatamente o que ela fez antes destes
# números existirem.
#
# O ritmo da máquina dele corrige a estimativa, mas só depois que uma fatia
# suficiente do trabalho passou: reajustar pelos doze testes de um segundo
# diria que o pesado também leva um segundo.
TESTES = [
    # PRIMEIRO de todos, e de proposito: nome indefinido derruba o programa
    # inteiro e leva dois segundos para achar. Falhar aqui vale mais que
    # falhar depois de vinte minutos de suite. Foi o que derrubou a v102.
    ("test_lint.py", "LINT_OK", 120, 3),
    ("test_nucleo.py", "NUCLEO_OK", 900, 40),
    ("test_canal.py", "CANAL_OK", 600, 25),
    ("test_controles.py", "CONTROLES_OK", 900, 45),
    ("test_central.py", "CENTRAL_TESTES_OK", 300, 1),
    ("test_base_auditoria.py", "BASE_AUDITORIA_OK", 300, 1),
    ("test_biblioteca.py", "BIBLIOTECA_OK", 300, 1),
    ("test_especialistas.py", "ESPECIALISTAS_OK", 600, 30),
    ("test_inteligencias.py", "INTELIGENCIAS_OK", 600, 6),
    ("test_fonte_cacadores.py", "FONTE_CACADORES_OK", 300, 1),
    ("test_multiplicador.py", "MULTIPLICADOR_OK", 900, 2),
    ("test_autopsia.py", "AUTOPSIA_OK", 200, 1),
    ("test_publico.py", "PUBLICO_OK", 200, 1),
    ("test_captador.py", "CAPTADOR_OK", 200, 1),
    ("test_resultado.py", "RESULTADO_OK", 200, 1),
    ("test_notificador.py", "NTFY_OK", 200, 4),
    ("test_fluxo_captura.py", "FLUXO_TESTES_OK", 300, 1),
    ("test_honestidade_gates.py", "HONEST_TESTS_OK", 300, 1),
    ("test_coletor_sites.py", "COLETOR_OK", 300, 1),
    ("teste_a6_ruido.py", None, 900, 1),
    # o pesado: 75 roletas com regua de permutacao, divididas pelos nucleos.
    # Vinte minutos aqui e o normal, nao travamento.
    ("teste_ocorrencia.py", None, 5400, 1200),
]


def rodar_um(arquivo: str, marca, limite: int):
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(RAIZ / arquivo)],
                           cwd=str(RAIZ), capture_output=True, text=True,
                           timeout=limite)
    except subprocess.TimeoutExpired:
        return False, f"passou de {_mmss(limite)} sem terminar", time.time() - t0
    saida = (r.stdout or "") + (r.returncode and (r.stderr or "") or "")
    if r.returncode != 0:
        cauda = [l for l in (r.stdout or "").splitlines() if l.strip()][-3:]
        return False, " / ".join(cauda) or (r.stderr or "")[-160:], time.time() - t0
    if marca and marca not in saida:
        return False, f"terminou sem a marca {marca}", time.time() - t0
    return True, "", time.time() - t0


def main() -> int:
    existem = [x for x in TESTES if (RAIZ / x[0]).is_file()]
    faltando = [x[0] for x in TESTES if not (RAIZ / x[0]).is_file()]
    print(f"\n  Rodando {len(existem)} testes."
          + (f"  ({len(faltando)} não encontrados: "
             f"{', '.join(faltando)})" if faltando else ""))
    _tot = sum(x[3] for x in existem)
    print("  O último deles sozinho leva a maior parte do tempo — 75 roletas"
          " com régua de permutação, divididas pelos núcleos da máquina.")
    print(f"  Estimativa total desta suíte: ~{_mmss(_tot)}.\n")
    p = Progresso(len(existem), titulo="suíte completa",
                  pesos=[x[3] for x in existem])
    falhas = []
    for arquivo, marca, limite, _custo in existem:
        p.comecou(arquivo)
        ok, motivo, gasto = rodar_um(arquivo, marca, limite)
        if not ok:
            falhas.append((arquivo, motivo))
        p.terminou(f"{arquivo} ({gasto:.0f}s)", ok=ok)
    print(p.fim(f"{len(existem) - len(falhas)} passaram, {len(falhas)} falharam"))
    if falhas:
        print("\n  FALHOU:")
        for arquivo, motivo in falhas:
            print(f"    {arquivo}: {motivo}")
        return 1
    print("\n  Tudo verde.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
