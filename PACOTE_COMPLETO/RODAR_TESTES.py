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

# (arquivo, marca de sucesso no fim da saída, limite de segundos)
TESTES = [
    ("test_central.py", "CENTRAL_TESTES_OK", 300),
    ("test_base_auditoria.py", "BASE_AUDITORIA_OK", 300),
    ("test_multiplicador.py", "MULTIPLICADOR_OK", 600),
    ("test_autopsia.py", "AUTOPSIA_OK", 200),
    ("test_publico.py", "PUBLICO_OK", 200),
    ("test_captador.py", "CAPTADOR_OK", 200),
    ("test_resultado.py", "RESULTADO_OK", 200),
    ("test_notificador.py", "NTFY_OK", 200),
    ("test_fluxo_captura.py", "FLUXO_TESTES_OK", 300),
    ("test_honestidade_gates.py", "HONEST_TESTS_OK", 300),
    ("test_coletor_sites.py", "COLETOR_OK", 300),
    ("teste_a6_ruido.py", None, 900),
    ("teste_ocorrencia.py", None, 2400),
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
    existem = [(a, m, l) for a, m, l in TESTES if (RAIZ / a).is_file()]
    faltando = [a for a, _m, _l in TESTES if not (RAIZ / a).is_file()]
    print(f"\n  Rodando {len(existem)} testes."
          + (f"  ({len(faltando)} não encontrados: "
             f"{', '.join(faltando)})" if faltando else ""))
    print("  Cada ponto da barra é um teste inteiro; os dois últimos são os"
          " demorados.\n")
    p = Progresso(len(existem), titulo="suíte completa")
    falhas = []
    for arquivo, marca, limite in existem:
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
