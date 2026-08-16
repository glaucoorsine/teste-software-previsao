# -*- coding: utf-8 -*-
"""
ABSORVER PDF — transforma um estudo dele em conhecimento que as IAs consultam.

    python ABSORVER_PDF.py                 (lê tudo que estiver em estudos_pdf/)
    python ABSORVER_PDF.py caminho.pdf     (um arquivo específico)

POR QUE ISTO EXISTE
───────────────────
Os dois primeiros estudos foram transcritos à mão. O compêndio saiu resumido a
80 conceitos quando o PDF tem 400 dossiês completos; o estudo de
multiplicadores saiu com 848 bytes — só a contagem de veredictos e os números
de skill por mesa. As 452 páginas de raciocínio ficaram de fora.

Ele cobrou isso, e a cobrança estava certa: "porque nao aplicou tudo que eu
coloquei la?". Transcrever à mão não escala e perde conteúdo em silêncio. Daqui
para frente o PDF entra inteiro, ou o programa diz exatamente o que não leu.

OS DOIS FORMATOS QUE ELE USA
────────────────────────────
Nenhum é "ficha numerada", que era o que eu tinha suposto. São dois desenhos
diferentes, ambos com UMA UNIDADE POR PÁGINA:

  dossiê numerado   `TEORIA 003 - PROBABILIDADE, ESTATÍSTICA E SÉRIES...`
                    depois o número solto, o título, e onze seções nomeadas
                    (Tese delimitada, Formalização e estimando, Mecanismo em
                    camadas, Predições diagnósticas, ...)

  auditoria         `MÉTODO` / `COMPARAÇÃO` / ... em caixa alta, um subtítulo,
                    e blocos rotulados (Vazamento direto, Controle, Regra de
                    decisão, ...) — às vezes com tabela de números.

O leitor detecta qual é, página a página. O que ele não reconhecer entra como
texto corrido em vez de sumir.

O que ele NÃO faz de propósito: julgar o conteúdo. A seção entra como ela é.
Ele já foi claro — "não critique e nem barre". Quem decide o peso de cada
trecho é o especialista dono da faixa, na hora de opinar.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parent
PASTA_PDF = RAIZ / "estudos_pdf"
PASTA_SAIDA = RAIZ / "academia_autonoma"

# O cabeçalho e o rodapé se repetem em toda página e não são conteúdo.
LIXO = (
    re.compile(r"^\s*Página\s+\d+(\s+de\s+\d+)?\s*$", re.I),
    re.compile(r"^\s*Estudo acadêmico retrospectivo\b", re.I),
    re.compile(r"^\s*Auditoria científica retrospectiva\s*$", re.I),
    re.compile(r"^\s*COMPÊNDIO CIENTÍFICO\s*$", re.I),
    re.compile(r"^\s*\d{1,4}\s*$"),             # o número solto do dossiê
)

CAB_DOSSIE = re.compile(r"^\s*TEORIA\s+(\d{1,4})\s*[-–—]\s*(.+?)\s*$", re.I)
CAB_SECAO = re.compile(r"^[A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÇ \-]{2,}$")

# Um rótulo de bloco é linha curta, sem ponto final, seguida de prosa.
MAX_ROTULO = 62


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def chave(rotulo: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", _sem_acento(rotulo)).strip("_")
    return k[:48] or "texto"


def limpar(pagina: str) -> List[str]:
    out = []
    for ln in (pagina or "").splitlines():
        s = ln.strip()
        if not s or any(p.match(s) for p in LIXO):
            continue
        out.append(s)
    return out


def e_rotulo(linha: str, proxima: Optional[str]) -> bool:
    """Rótulo de bloco: curto, sem pontuação de fim, e com prosa embaixo."""
    if not linha or len(linha) > MAX_ROTULO:
        return False
    if linha[-1] in ".:;,!?•)":
        return False
    if linha.startswith("•"):
        return False
    if not proxima or proxima.startswith("•"):
        return bool(proxima)
    # duas linhas curtas seguidas costumam ser título + subtítulo, não rótulo
    return len(proxima) > MAX_ROTULO or proxima[-1] in ".;"


def blocos(linhas: List[str]) -> Dict[str, str]:
    """Os blocos rotulados da página. O que vier antes do 1o rótulo é o título."""
    saida: Dict[str, List[str]] = {}
    atual = None
    for i, ln in enumerate(linhas):
        prox = linhas[i + 1] if i + 1 < len(linhas) else None
        if e_rotulo(ln, prox):
            atual = chave(ln)
            saida.setdefault(atual, [])
            saida[atual].append("")            # marca o rótulo original
            saida[atual][0] = ""
        elif atual:
            saida[atual].append(ln)
        else:
            saida.setdefault("_titulo", []).append(ln)
    return {k: " ".join(v).strip() for k, v in saida.items() if " ".join(v).strip()}


def rotulos_originais(linhas: List[str]) -> Dict[str, str]:
    m = {}
    for i, ln in enumerate(linhas):
        prox = linhas[i + 1] if i + 1 < len(linhas) else None
        if e_rotulo(ln, prox):
            m[chave(ln)] = ln
    return m


def ler_paginas(caminho: Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit(
            "\n  Falta a biblioteca de PDF. Rode uma vez:\n"
            "      pip install pypdf\n")
    r = PdfReader(str(caminho))
    pgs, mudas = [], 0
    for p in r.pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        if not t.strip():
            mudas += 1
        pgs.append(t)
    if mudas:
        print(f"      aviso: {mudas} de {len(pgs)} páginas sem texto extraível "
              f"(provavelmente imagem escaneada)")
    return pgs


def absorver(caminho: Path) -> Dict:
    print(f"\n  {caminho.name}")
    pgs = ler_paginas(caminho)
    print(f"      {len(pgs)} páginas")

    unidades, secao_atual = [], None
    for i, bruto in enumerate(pgs):
        linhas = limpar(bruto)
        if not linhas:
            continue
        cab = CAB_DOSSIE.match(linhas[0])
        corpo = blocos(linhas[1:] if cab else linhas)
        titulo = corpo.pop("_titulo", "").strip()

        if cab:
            unidades.append({"n": int(cab.group(1)), "pagina": i + 1,
                             "tipo": "dossie", "eixo": cab.group(2).strip(),
                             "titulo": titulo,
                             "rotulos": rotulos_originais(linhas[1:]),
                             **corpo})
        else:
            if CAB_SECAO.match(linhas[0]) and len(linhas[0]) <= MAX_ROTULO:
                secao_atual = linhas[0]
                corpo = blocos(linhas[1:])
                titulo = corpo.pop("_titulo", "").strip()
            if not corpo and not titulo:
                continue
            unidades.append({"n": len(unidades) + 1, "pagina": i + 1,
                             "tipo": "auditoria", "secao": secao_atual or "",
                             "titulo": titulo,
                             "rotulos": rotulos_originais(linhas),
                             **corpo})

    dossies = [u for u in unidades if u["tipo"] == "dossie"]
    audit = [u for u in unidades if u["tipo"] == "auditoria"]
    print(f"      {len(dossies)} dossiês numerados, {len(audit)} páginas de auditoria")

    if dossies:
        ns = [u["n"] for u in dossies]
        falta = sorted(set(range(min(ns), max(ns) + 1)) - set(ns))
        print(f"      dossiês de {min(ns)} a {max(ns)}"
              + (f" — {len(falta)} pulados: {falta[:12]}" if falta else " — nenhum pulado"))
        eixos = sorted({u["eixo"] for u in dossies})
        print(f"      {len(eixos)} eixos: {'; '.join(e[:34] for e in eixos)}")
        campos: Dict[str, int] = {}
        for u in dossies:
            for k in u:
                if k not in ("n", "pagina", "tipo", "eixo", "titulo", "rotulos"):
                    campos[k] = campos.get(k, 0) + 1
        top = sorted(campos.items(), key=lambda x: -x[1])[:12]
        print(f"      seções por dossiê: "
              + ", ".join(f"{k}({v})" for k, v in top))
        magros = [u["n"] for u in dossies if len(u.get("rotulos") or {}) < 3]
        if magros:
            print(f"      {len(magros)} dossiês com menos de 3 seções: {magros[:10]}")

    if audit:
        secoes = sorted({u["secao"] for u in audit if u["secao"]})
        print(f"      seções da auditoria: {'; '.join(secoes[:10])}"
              + (" ..." if len(secoes) > 10 else ""))

    chars = sum(len(str(v)) for u in unidades for v in u.values())
    print(f"      {chars:,} caracteres de conteúdo".replace(",", "."))
    return {"arquivo": caminho.name, "paginas": len(pgs),
            "n_dossies": len(dossies), "n_auditoria": len(audit),
            "unidades": unidades}


def nome_saida(caminho: Path) -> Path:
    base = re.sub(r"[^a-z0-9]+", "_", _sem_acento(caminho.stem)).strip("_")
    return PASTA_SAIDA / f"dados_{(base[:48] or 'estudo')}.json"


def main() -> int:
    PASTA_PDF.mkdir(exist_ok=True)
    alvos = ([Path(a) for a in sys.argv[1:]] if len(sys.argv) > 1
             else sorted(PASTA_PDF.glob("*.pdf")))
    if not alvos:
        print(f"\n  Nenhum PDF. Jogue os estudos em:\n      {PASTA_PDF}\n"
              f"  e rode de novo.\n")
        return 0

    print(f"\n  Absorvendo {len(alvos)} estudo(s).")
    indice = []
    for c in alvos:
        if not c.is_file():
            print(f"\n  {c} — não achei este arquivo")
            continue
        d = absorver(c)
        destino = nome_saida(c)
        destino.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        kb = destino.stat().st_size / 1024
        print(f"      → {destino.relative_to(RAIZ)}  ({kb:,.0f} KB)"
              .replace(",", "."))
        indice.append({"arquivo": d["arquivo"], "json": destino.name,
                       "paginas": d["paginas"], "n_dossies": d["n_dossies"],
                       "n_auditoria": d["n_auditoria"]})

    (PASTA_SAIDA / "INDICE_ESTUDOS.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = sum(x["n_dossies"] + x["n_auditoria"] for x in indice)
    print(f"\n  {tot} unidades absorvidas de {len(indice)} estudo(s).")
    print(f"  Índice em academia_autonoma/INDICE_ESTUDOS.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
