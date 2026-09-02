# -*- coding: utf-8 -*-
"""
Roda a suíte inteira do LYRA LIVE, com percentual e tempo restante.

    python RODAR_TESTES.py          (ou clique em 2_RODAR_TESTES.bat)

Cada arquivo roda em processo próprio. Um que trave não leva os outros junto: o
tempo limite corta, a suíte segue, e o relatório final diz qual foi.

A suíte NÃO precisa de câmera, de ffmpeg, de internet nem do Qwen. Tudo o que
depende do mundo externo é testado pela forma do comando que seria executado ou
por uma fonte de vídeo gerada em memória. Isso é de propósito: um teste que só
passa na máquina certa não prova nada sobre as outras.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# (módulo, custo típico em segundos nesta máquina)
#
# O CUSTO é para a barra não mentir: a esteira leva dez segundos de relógio
# porque mede fps de verdade, e os outros levam frações. Sem declarar isso, a
# barra anunciaria "falta 1s" com dez segundos pela frente.
TESTES = [
    ("tests.test_imagem", 1),
    ("tests.test_filtros", 1),
    ("tests.test_fundo", 1),
    ("tests.test_camera", 3),
    ("tests.test_saida", 1),
    ("tests.test_config", 1),
    ("tests.test_ia", 1),
    ("tests.test_pipeline", 10),
]
LIMITE_S = 180


def _mmss(segundos: float) -> str:
    segundos = max(0, int(segundos))
    return f"{segundos // 60:d}m{segundos % 60:02d}s"


def principal() -> int:
    total_custo = sum(c for _, c in TESTES)
    feito_custo = 0
    comeco = time.time()
    falhas = []

    print("=" * 64)
    print("  LYRA LIVE — suíte de testes")
    print("=" * 64)

    for modulo, custo in TESTES:
        pct = int(100 * feito_custo / total_custo)
        gasto = time.time() - comeco
        # a estimativa só vale depois que uma fatia do trabalho passou
        restante = (gasto / feito_custo * (total_custo - feito_custo)) if feito_custo else 0
        print(f"  [{pct:3d}%] {modulo:24s} restam ~{_mmss(restante)} ... ", end="", flush=True)

        t0 = time.time()
        try:
            saida = subprocess.run(
                [sys.executable, "-m", "unittest", modulo],
                cwd=str(RAIZ), capture_output=True, text=True, timeout=LIMITE_S)
            ok = saida.returncode == 0
            detalhe = (saida.stderr or saida.stdout or "").strip()
        except subprocess.TimeoutExpired:
            ok, detalhe = False, f"passou de {LIMITE_S}s e foi cortado"

        gasto_teste = time.time() - t0
        quantos = ""
        for linha in detalhe.splitlines():
            if linha.startswith("Ran "):
                quantos = linha.split()[1] + " testes"
        print(f"{'OK' if ok else 'FALHOU'}  ({quantos}, {gasto_teste:.1f}s)")
        if not ok:
            falhas.append((modulo, detalhe))
        feito_custo += custo

    print("=" * 64)
    if not falhas:
        print(f"  TUDO PASSOU em {_mmss(time.time() - comeco)}.")
        print("=" * 64)
        print("LYRA_TESTES_OK")
        return 0

    for modulo, detalhe in falhas:
        print(f"\n  FALHOU: {modulo}")
        print("  " + "\n  ".join(detalhe.splitlines()[-25:]))
    print("=" * 64)
    print(f"  {len(falhas)} de {len(TESTES)} arquivos com falha.")
    return 1


if __name__ == "__main__":
    sys.exit(principal())
