# -*- coding: utf-8 -*-
"""NOME QUE NAO EXISTE — o teste que roda primeiro porque custa dois segundos.

Um `NameError` não precisa ser executado para ser encontrado: ele está
escrito no arquivo. E é o único defeito que derruba o programa inteiro na
primeira tela, sem nenhum outro teste perceber -- porque os outros testes não
abrem janela, e é justamente dentro do código de janela que ele se esconde.

Só procuro o que quebra de verdade: nome indefinido. Import não usado e
variável sobrando ficam de fora -- são arrumação, e misturar arrumação com
defeito faz o teste virar barulho que se aprende a ignorar.

    python test_lint.py
"""
from __future__ import annotations
import subprocess
import sys
from _base_teste import RAIZ, checa, resumo

FATAIS = ("undefined name",)

arquivos = sorted(p for p in RAIZ.glob("*.py"))
print(f"[lint] {len(arquivos)} arquivos")
try:
    p = subprocess.run([sys.executable, "-m", "pyflakes"]
                       + [str(a) for a in arquivos],
                       capture_output=True, text=True, timeout=120)
    saida = (p.stdout or "") + (p.stderr or "")
except Exception as e:
    saida = f"pyflakes não rodou: {e}"

graves = [ln for ln in saida.splitlines()
          if any(f in ln for f in FATAIS)]
checa(not graves, "nenhum nome indefinido", "; ".join(graves[:4]))

# e todo arquivo tem de ao menos COMPILAR
for a in arquivos:
    try:
        compile(a.read_text(encoding="utf-8"), str(a), "exec")
        ok, err = True, ""
    except SyntaxError as e:
        ok, err = False, f"linha {e.lineno}: {e.msg}"
    checa(ok, f"{a.name} compila", err)

sys.exit(resumo("LINT"))
