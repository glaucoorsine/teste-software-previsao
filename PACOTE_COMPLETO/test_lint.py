# -*- coding: utf-8 -*-
"""NOME QUE NAO EXISTE — o teste que faltava.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
A v102 passou nos treze testes e nao abria. Uma linha de CENTRAL.py dizia
`str(jogo)` onde tinha que dizer `str(self.jogo)`, e o software morria na
primeira tela com NameError.

Os treze testes nao pegaram porque nenhum deles executa `_montar()` de
verdade: a tela e substituida por um dublê. O dublê e o certo -- nao da para
abrir janela num teste automatico -- mas ele apaga justamente as linhas onde
esse erro mora.

Um NameError nao precisa ser executado para ser encontrado. Ele esta escrito
no arquivo, e uma leitura estatica acha. E o unico tipo de defeito que derruba
o programa inteiro sem aviso, entao ele vem PRIMEIRO na suite: falhar aqui em
dois segundos vale mais que falhar em vinte minutos.

Este teste procura so o que quebra de verdade -- nome indefinido. Import nao
usado, variavel sobrando e f-string sem placeholder ficam de fora: sao
arrumacao, e misturar arrumacao com defeito faz o teste virar barulho que se
aprende a ignorar.

    python test_lint.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# So estes. Ver o cabecalho: o resto e arrumacao, nao defeito.
FATAIS = ("undefined name",)

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


def arquivos():
    fs = sorted(RAIZ.glob("*.py"))
    fs += sorted((RAIZ / "academia_autonoma").glob("*.py"))
    return [str(f) for f in fs]


print("\n[1] pyflakes disponivel?")
try:
    import pyflakes  # noqa: F401
    tem = True
except ImportError:
    tem = False

if not tem:
    print("""
  pyflakes nao esta instalado, e sem ele esta checagem nao roda.

      pip install pyflakes

  (ou rode 0_INSTALAR_DEPENDENCIAS.bat de novo -- ele ja pede)

  Nao vou dar este teste como passado sem ter rodado: um teste que
  passa por nao ter sido executado e pior que teste nenhum.
""")
    sys.exit(1)

print("  ok   pyflakes presente")

print("\n[2] nenhum nome indefinido em nenhum arquivo")
alvos = arquivos()
print(f"       lendo {len(alvos)} arquivos...")
r = subprocess.run([sys.executable, "-m", "pyflakes"] + alvos,
                   capture_output=True, text=True, cwd=str(RAIZ))
graves = [l for l in (r.stdout or "").splitlines()
          if any(m in l for m in FATAIS)]
if graves:
    print("\n  NOMES INDEFINIDOS -- cada um destes derruba o programa quando a")
    print("  linha for executada:\n")
    for l in graves:
        print("     " + l)
    print()
checa(not graves, f"nenhum nome indefinido em {len(alvos)} arquivos",
      f"{len(graves)} encontrados")

print("\n[3] o proprio teste tem forca: um erro plantado e PEGO")
plantado = RAIZ / "_lint_plantado_temp.py"
try:
    plantado.write_text(
        "def f():\n    return variavel_que_nunca_existiu\n", encoding="utf-8")
    r2 = subprocess.run([sys.executable, "-m", "pyflakes", str(plantado)],
                        capture_output=True, text=True, cwd=str(RAIZ))
    pegou = any(m in (r2.stdout or "") for m in FATAIS)
    checa(pegou, "erro plantado de proposito e encontrado", r2.stdout.strip())
finally:
    try:
        plantado.unlink()
    except OSError:
        pass

print("\n[4] o caso exato da v102 seria pego")
caso = RAIZ / "_lint_v102_temp.py"
try:
    caso.write_text(
        "class Mesa:\n"
        "    def __init__(self, jogo):\n"
        "        self.jogo = jogo\n"
        "    def _montar(self):\n"
        "        return 3 if str(jogo).startswith('crazy_time') else 10\n",
        encoding="utf-8")
    r3 = subprocess.run([sys.executable, "-m", "pyflakes", str(caso)],
                        capture_output=True, text=True, cwd=str(RAIZ))
    checa(any(m in (r3.stdout or "") for m in FATAIS),
          "o 'jogo' sem self, que derrubou a v102, e pego", r3.stdout.strip())
finally:
    try:
        caso.unlink()
    except OSError:
        pass

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("LINT_OK")
