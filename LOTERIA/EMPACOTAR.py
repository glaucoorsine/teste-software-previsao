# -*- coding: utf-8 -*-
"""
EMPACOTAR — o ZIP de entrega, conferido por dentro antes de existir.

A LIÇÃO QUE ESTE ARQUIVO CARREGA
────────────────────────────────
No outro pacote eu quebrei a entrega EMPACOTANDO: o ZIP saiu sem um arquivo e
ninguém percebeu até ele abrir na máquina dele. Desde então o empacotador de lá
confere a si mesmo, e o daqui já nasce assim:

    1. junta os arquivos e fecha o ZIP;
    2. EXTRAI o próprio ZIP num canto limpo, como se fosse a máquina dele;
    3. RODA a suíte inteira de testes dentro da extração;
    4. só declara o pacote pronto se a última linha for LOTERIA_BASE_OK.

Um ZIP que não passa no próprio teste não é entregue — é apagado, com o motivo
na tela. O pacote que chega nele é um que já rodou inteiro fora daqui.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent          # .../LOTERIA
DESTINO = RAIZ.parent / "LOTERIA_v1.zip"

# o que ENTRA. Lista explícita, não "tudo menos": o erro do outro pacote foi
# justamente um filtro esperto demais, e lista explícita quebra na cara quando
# um arquivo novo não é lembrado aqui — que é como deve ser.
LEVAR = [
    # o que ele abre
    "ABRIR.bat", "_PYTHON.bat", "PAINEL.py",
    "painel/index.html", "painel/estilo.css", "painel/painel.js",
    "LEIA_PRIMEIRO.md", "dados/LEIA.md",
    # o motor
    "NUCLEO/__init__.py", "NUCLEO/regras.py", "NUCLEO/base_conhecimento.py",
    "NUCLEO/fechamento.py", "NUCLEO/estatistica.py", "NUCLEO/historico.py",
    "NUCLEO/medidor.py", "NUCLEO/api.py", "NUCLEO/formular.py",
    "NUCLEO/conferencia.py",
    # a linha de comando, para quem quiser
    "JOGAR.py", "PUXAR.py", "EMPACOTAR.py", "test_loteria.py",
    "avancado/LEIA.md", "avancado/LINHA_DE_COMANDO.bat", "avancado/PUXAR.bat",
    "avancado/TESTES.bat", "avancado/GERAR_EXE.bat",
]


def empacotar() -> int:
    print("═" * 72)
    print("EMPACOTAR — o ZIP, conferido por dentro antes de ser entregue")
    print("═" * 72)

    faltando = [a for a in LEVAR if not (RAIZ / a).exists()]
    if faltando:
        print("\n[Pacote] NÃO empacotei — arquivos da lista não existem:")
        for a in faltando:
            print(f"           {a}")
        print("[Pacote] ou o arquivo sumiu, ou a lista está desatualizada. "
              "As duas coisas são defeito; nenhuma vira ZIP.")
        return 1

    print(f"\n[Pacote] fechando {DESTINO.name} com {len(LEVAR)} arquivos…")
    with zipfile.ZipFile(DESTINO, "w", zipfile.ZIP_DEFLATED) as z:
        for a in LEVAR:
            z.write(RAIZ / a, f"LOTERIA/{a}")

    # ── a parte que importa: o pacote roda FORA daqui? ────────────────────
    print("[Pacote] extraindo o próprio ZIP num canto limpo e rodando a "
          "suíte inteira lá dentro…")
    with tempfile.TemporaryDirectory(prefix="loteria_pacote_") as tmp:
        with zipfile.ZipFile(DESTINO) as z:
            z.extractall(tmp)
        r = subprocess.run(
            [sys.executable, "test_loteria.py"],
            cwd=Path(tmp) / "LOTERIA",
            capture_output=True, text=True, timeout=900,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        ultimas = (r.stdout or "").strip().splitlines()[-3:]
        ok = r.returncode == 0 and any("LOTERIA_BASE_OK" in l for l in ultimas)

    if not ok:
        DESTINO.unlink(missing_ok=True)
        print("\n[Pacote] o ZIP NÃO passou no próprio teste — apagado, não "
              "entregue. As últimas linhas de lá:")
        for l in ultimas or ["(sem saída)"]:
            print(f"           {l}")
        if r.stderr:
            print(f"           {r.stderr.strip().splitlines()[-1]}")
        return 1

    tamanho = DESTINO.stat().st_size / 1024
    print(f"\n[Pacote] PRONTO: {DESTINO}  ({tamanho:.0f} KB)")
    print(f"[Pacote] a extração rodou as {sum(1 for l in (r.stdout or '').splitlines() if l.startswith('  ok'))} "
          f"checagens e terminou em LOTERIA_BASE_OK.")
    print("[Pacote] na máquina dele: extrair, entrar na pasta LOTERIA, e "
          "abrir ABRIR.bat — só esse.")
    return 0


if __name__ == "__main__":
    sys.exit(empacotar())
