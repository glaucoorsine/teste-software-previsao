# -*- coding: utf-8 -*-
"""
DESTILAR — guarda o que o software EXECUTA, sem republicar o livro dele.

    python DESTILAR_ESTUDOS.py

O PROBLEMA QUE ISTO RESOLVE
───────────────────────────
Os três estudos dele somam 1.864 páginas e ~6 milhões de caracteres. Eu deixei
esse texto fora do versionamento por um motivo certo -- o repositório é público
e aquilo é o livro dele, não meu para republicar.

Só que o container é apagado com frequência, e a cada vez o software voltava
sem saber nada: as 960 formulações sumiam, as 400 teses sumiam, e ele tinha que
subir tudo de novo. Aconteceu três vezes.

A saída não é escolher entre perder ou republicar. É separar as duas coisas:

    o RACIOCÍNIO dele        prosa, tese, mecanismo, contraditório escrito
                             → fica fora, é o livro
    o que o PROGRAMA EXECUTA número, mesa, família, IA, fórmula, título
                             → entra, é o índice

A fórmula `D_t = t - max{i<t : Y_i=1}` não é o livro dele mais do que "E=mc²" é
o artigo de 1905. É o que o código roda, e sem ela o código não roda.

O QUE ESTE ARQUIVO GRAVA
────────────────────────
Um índice por estudo, com um registro por unidade:

    formulação   n, mesa, família, IA, lente, título, fórmula
    dossiê       n, eixo, título
    auditoria    seção, título

Sem nenhuma das seções de prosa. O resultado cabe em algumas centenas de KB
contra os 6,8 MB do texto integral, e é o suficiente para cada IA do software
CITAR de onde tirou a leitura -- que é o que torna a previsão auditável, e o
livro inteiro dele é sobre leitura auditável.

Quando os PDFs estiverem na pasta, `ABSORVER_PDF.py` reconstrói o texto
completo por cima. Quando não estiverem, o software usa o índice e continua
sabendo o que executa e de onde veio.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / "academia_autonoma"
SAIDA = PASTA / "indice_estudos_destilado.json"

# Só estes campos atravessam. Tudo que for prosa fica de fora, por construção:
# a lista é de permissão, não de bloqueio -- assim uma seção nova que ele
# escreva amanhã não vaza para o repositório por esquecimento meu.
CAMPOS = {
    "formulacao": ("n", "pagina", "mesa", "familia", "ia", "lente",
                   "titulo", "formula"),
    "dossie": ("n", "pagina", "eixo", "titulo"),
    "auditoria": ("pagina", "secao", "titulo"),
}

# Título é a única coisa com texto autoral que entra, e entra cortado: ele
# nomeia a leitura ("Intervalo contextual desde a última ocorrência") sem
# carregar o desenvolvimento dela.
MAX_TITULO = 90


def destilar_unidade(u: Dict[str, Any]) -> Dict[str, Any]:
    tipo = u.get("tipo", "auditoria")
    out = {"tipo": tipo}
    for c in CAMPOS.get(tipo, CAMPOS["auditoria"]):
        v = u.get(c)
        if v in (None, "", []):
            continue
        if c == "titulo":
            v = str(v)[:MAX_TITULO]
        out[c] = v
    return out


def main() -> int:
    arquivos = sorted(PASTA.glob("dados_*.json"))
    arquivos = [a for a in arquivos
                if a.name not in ("dados_teorias.json",
                                  "dados_multiplicador_estudo.json")]
    if not arquivos:
        print("\n  Nenhum estudo absorvido em academia_autonoma/.")
        print("  Rode ABSORVER_PDF.py com os PDFs em estudos_pdf/ primeiro.")
        return 1

    print(f"\n  Destilando {len(arquivos)} estudo(s).\n")
    indice: Dict[str, Any] = {"estudos": {}}
    total = 0
    for arq in arquivos:
        try:
            d = json.load(open(arq, encoding="utf-8"))
        except Exception as e:
            print(f"  {arq.name}: não deu para ler ({type(e).__name__})")
            continue
        unidades: List[dict] = d.get("unidades") or []
        dest = [destilar_unidade(u) for u in unidades]
        chave = d.get("origem") or arq.stem
        indice["estudos"][chave] = {
            "paginas": d.get("paginas"),
            "unidades": dest,
        }
        total += len(dest)
        bruto = arq.stat().st_size
        com_formula = sum(1 for u in dest if u.get("formula"))
        print(f"  {arq.name}")
        print(f"      {len(dest)} unidades, {com_formula} com fórmula "
              f"(de {bruto // 1024} KB de texto integral)")

    SAIDA.write_text(json.dumps(indice, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    kb = SAIDA.stat().st_size // 1024
    print(f"\n  {total} unidades → {SAIDA.name}  ({kb} KB)")
    print("  Este arquivo entra no versionamento. A prosa dos estudos, não.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
