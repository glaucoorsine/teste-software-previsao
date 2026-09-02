# -*- coding: utf-8 -*-
"""Abre o painel do LYRA LIVE. É o arquivo que o atalho do Windows chama."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

if __name__ == "__main__":
    from painel import main
    raise SystemExit(main())
