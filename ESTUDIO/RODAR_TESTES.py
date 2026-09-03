# -*- coding: utf-8 -*-
"""Roda a suíte inteira. O lint vem primeiro porque custa dois segundos.

    python RODAR_TESTES.py
"""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# ordem: do mais barato e mais fatal para o mais lento
SUITE = ["test_lint.py", "test_ajustes.py", "test_imagem.py", "test_ia.py",
         "test_audio.py", "test_transmissao.py", "test_estudio.py"]

def main() -> int:
    print("=" * 68)
    print("ESTÚDIO — suíte de testes")
    print("=" * 68)
    ruins = []
    t0 = time.perf_counter()
    for nome in SUITE:
        arq = RAIZ / nome
        if not arq.is_file():
            print(f"\n### {nome}: NÃO EXISTE")
            ruins.append(nome)
            continue
        print(f"\n### {nome}")
        t = time.perf_counter()
        p = subprocess.run([sys.executable, str(arq)], cwd=str(RAIZ))
        seg = time.perf_counter() - t
        if p.returncode != 0:
            ruins.append(nome)
            print(f"### {nome}: FALHOU ({seg:.1f} s)")
        else:
            print(f"### {nome}: ok ({seg:.1f} s)")
    print("\n" + "=" * 68)
    if ruins:
        print(f"FALHARAM {len(ruins)} de {len(SUITE)}: {', '.join(ruins)}")
    else:
        print(f"TUDO OK — {len(SUITE)} arquivos em {time.perf_counter()-t0:.1f} s")
    print("=" * 68)
    return 1 if ruins else 0


if __name__ == "__main__":
    sys.exit(main())
