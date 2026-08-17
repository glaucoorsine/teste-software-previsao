# -*- coding: utf-8 -*-
"""
EMPACOTAR — monta o ZIP de entrega e CONFERE que nada de código ficou fora.

    python EMPACOTAR.py            (gera ../PACOTE_COMPLETO_vNNN.zip)

POR QUE ISTO EXISTE
───────────────────
Porque eu já quebrei o pacote empacotando. Na v124 escrevi o filtro assim:

    if p.name.startswith(("memoria_", "biblioteca_estudos_", "crash_")):
        return True                      # não entra no zip

A intenção era excluir ESTADO: `memoria_lightning.json`, que é placar gravado
pelo software e não pode viajar no pacote (achado 26 dele). Mas o filtro olha só
o começo do nome — e existe um MÓDULO chamado `memoria_agentes.py`. Ele começa
com `memoria_`, então foi jogado fora junto.

O resultado apareceu na tela dele, nas quatro mesas:

    ModuleNotFoundError: No module named 'academia_autonoma.memoria_agentes'

Na versão anterior o filtro exigia `p.suffix == ".json"` e estava certo. Eu
reescrevi o filtro à mão para a entrega nova e perdi a condição no caminho.

E é isso que este arquivo resolve: enquanto o filtro for uma linha que eu digito
de novo a cada versão, esse erro volta. Aqui ele é código, com uma conferência
que não depende de eu lembrar — **todo `.py` que existe na pasta tem de estar no
ZIP**, e se faltar um, o empacotamento FALHA em vez de gerar um pacote quebrado.

A REGRA, EM UMA FRASE
─────────────────────
Código sempre entra. Estado nunca entra. E o que decide não é o começo do nome:
é a extensão e a pasta.
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DESTINO_DIR = RAIZ.parent

# Pastas que são estado de execução, inteiras.
PASTAS_FORA = {"__pycache__", "Logs", "_dados_ao_vivo", ".git", ".pytest_cache",
               ".mypy_cache", "data"}

# Extensões que NUNCA são código.
EXT_ESTADO = {".pyc", ".pyo", ".tmp", ".lock", ".log"}

# Estado gravado pelo software. Note que todos exigem a extensão junto: é a
# condição que faltou na v124 e derrubou o `memoria_agentes.py`.
ESTADO_JSON = ("memoria_", "biblioteca_estudos_", "tribunal_", "ciclo_ativo_")
ESTADO_EXATO = {"a6_calibracao.json", "dashboard_state.json",
                "super_ia_state.json"}
ESTADO_TXT = ("crash_",)

# O que é código e portanto entra sempre, doa onde estiver.
EXT_CODIGO = {".py", ".bat", ".md", ".txt", ".html", ".pt", ".json"}


def e_estado(p: Path) -> bool:
    """Este arquivo é estado de execução?

    A ordem importa: primeiro pasta, depois extensão, e só então o nome — e o
    nome só conta junto com a extensão certa.
    """
    if any(x in PASTAS_FORA for x in p.parts):
        return True
    if p.suffix.lower() in EXT_ESTADO:
        return True
    if p.name in ESTADO_EXATO:
        return True
    if p.suffix.lower() == ".json" and p.name.startswith(ESTADO_JSON):
        return True
    if p.suffix.lower() == ".txt" and p.name.startswith(ESTADO_TXT):
        return True
    if p.name.endswith("_state.json"):
        return True
    return False


def montar(versao: str) -> Path:
    destino = DESTINO_DIR / f"PACOTE_COMPLETO_{versao}.zip"
    if destino.exists():
        destino.unlink()
    entraram: list[Path] = []
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for p in sorted(RAIZ.rglob("*")):
            if p.is_dir() or e_estado(p):
                continue
            z.write(p, (Path(RAIZ.name) / p.relative_to(RAIZ)).as_posix())
            entraram.append(p)
    return destino


def conferir(destino: Path) -> list[str]:
    """A conferência que a v124 não tinha: nenhum código pode faltar.

    Um pacote sem um módulo não dá erro na hora de montar — dá erro na máquina
    dele, dias depois, como `ModuleNotFoundError` no meio da tela. Então a hora
    de descobrir é aqui.
    """
    dentro = set(zipfile.ZipFile(destino).namelist())
    problemas: list[str] = []
    for p in sorted(RAIZ.rglob("*")):
        if p.is_dir() or e_estado(p):
            continue
        if p.suffix.lower() not in EXT_CODIGO:
            continue
        alvo = (Path(RAIZ.name) / p.relative_to(RAIZ)).as_posix()
        if alvo not in dentro:
            problemas.append(f"FALTA no zip: {p.relative_to(RAIZ)}")

    # e todo import de módulo interno tem de achar o arquivo dele
    import re
    modulos = {p.relative_to(RAIZ).as_posix()[:-3].replace("/", ".")
               for p in RAIZ.rglob("*.py") if not e_estado(p)}
    for p in RAIZ.rglob("*.py"):
        if e_estado(p):
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in re.finditer(r"^\s*from\s+([\w.]+)\s+import|^\s*import\s+([\w.]+)",
                             src, re.M):
            nome = (m.group(1) or m.group(2) or "").strip()
            if not nome or nome.startswith("."):
                continue
            raiz = nome.split(".")[0]
            # só cobra os módulos que são nossos
            if raiz not in {x.split(".")[0] for x in modulos}:
                continue
            if nome in modulos or f"{nome}.__init__" in modulos:
                continue
            if any(x.startswith(nome + ".") for x in modulos):
                continue
            problemas.append(
                f"{p.relative_to(RAIZ)} importa `{nome}`, que não existe")
    return problemas


def main() -> int:
    versao = sys.argv[1] if len(sys.argv) > 1 else "v0"
    destino = montar(versao)
    tam = destino.stat().st_size / 1024 / 1024
    n = len(zipfile.ZipFile(destino).namelist())
    print(f"\n  {destino.name}: {n} arquivos, {tam:.1f} MB")

    problemas = conferir(destino)
    if problemas:
        print(f"\n  {len(problemas)} PROBLEMA(S) — o pacote NÃO está bom:")
        for x in problemas[:20]:
            print(f"     {x}")
        destino.unlink(missing_ok=True)
        print(f"\n  ZIP apagado. Um pacote incompleto é pior que nenhum: o erro"
              f"\n  aparece na máquina dele, dias depois, no meio da tela.")
        return 1

    # o que ficou de fora, para dar para ler e conferir a decisão
    fora = [p.relative_to(RAIZ) for p in sorted(RAIZ.rglob("*"))
            if not p.is_dir() and e_estado(p)
            and "__pycache__" not in p.parts]
    if fora:
        print(f"\n  ficaram fora {len(fora)} arquivo(s) de estado:")
        for x in fora[:8]:
            print(f"     {x}")
    print("\n  conferido: todo módulo, .bat e documento está dentro,")
    print("  e todo import interno acha o arquivo dele.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
