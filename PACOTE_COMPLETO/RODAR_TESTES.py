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
# O CUSTO é o que faz a estimativa de tempo prestar. Onze destes levam
# segundos e o último leva a maior parte de uma hora; sem declarar isso, a
# barra anunciaria "falta 4s" com quarenta minutos pela frente. O número não
# precisa ser exato — ele é reajustado pelo ritmo real da máquina dele
# conforme a suíte anda.
TESTES = [
    ("test_central.py", "CENTRAL_TESTES_OK", 300, 8),
    ("test_base_auditoria.py", "BASE_AUDITORIA_OK", 300, 6),
    ("test_multiplicador.py", "MULTIPLICADOR_OK", 900, 60),
    ("test_autopsia.py", "AUTOPSIA_OK", 200, 3),
    ("test_publico.py", "PUBLICO_OK", 200, 3),
    ("test_captador.py", "CAPTADOR_OK", 200, 3),
    ("test_resultado.py", "RESULTADO_OK", 200, 3),
    ("test_notificador.py", "NTFY_OK", 200, 5),
    ("test_fluxo_captura.py", "FLUXO_TESTES_OK", 300, 6),
    ("test_honestidade_gates.py", "HONEST_TESTS_OK", 300, 6),
    ("test_coletor_sites.py", "COLETOR_OK", 300, 6),
    ("teste_a6_ruido.py", None, 900, 20),
    # o pesado: 25 roletas limpas + 25 viciadas, cada uma com régua de
    # permutação. Meia hora é o normal dele, não travamento.
    ("teste_ocorrencia.py", None, 5400, 2100),
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
    print(f"  O último deles sozinho leva a maior parte do tempo — 25 roletas"
          f" limpas e 25 viciadas, com régua de permutação.")
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
