# -*- coding: utf-8 -*-
"""Dispara todos os módulos do laboratório em processos separados."""
from __future__ import annotations
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MODULOS = [
    ("academia_servico.py", 2.0),
    ("mega_fire_combo.py", 0.8),
    ("lightning_combo.py", 0.8),
    ("crazy_time_combo.py", 0.8),
    ("assistente_ia.py", 0.8),
    ("central_ias.py", 0.5),
]

def main():
    py = sys.executable
    procs = []
    for nome, delay in MODULOS:
        path = ROOT / nome
        if not path.is_file():
            print(f"[pular] {nome} não encontrado")
            continue
        print(f"[abrir] {nome}")
        # CREATE_NEW_CONSOLE no Windows
        kw = {}
        if sys.platform == "win32":
            kw["creationflags"] = subprocess.CREATE_NEW_CONSOLE  # type: ignore
        procs.append(subprocess.Popen([py, str(path)], cwd=str(ROOT), **kw))
        time.sleep(delay)
    print(f"Disparados: {len(procs)} processos.")
    print("Este launcher pode ser fechado; os módulos seguem independentes.")

if __name__ == "__main__":
    main()
