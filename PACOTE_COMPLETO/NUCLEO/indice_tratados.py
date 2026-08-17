# -*- coding: utf-8 -*-
"""
ÍNDICE DOS TRATADOS — as fórmulas vindas do PDF, com página e impressão digital.

O QUE ELE COBROU
────────────────
    "77. O pacote não contém os três PDFs nem uma pasta operacional de PDFs.
     79. Não existe leitor semântico/RAG que consulte os PDFs a cada análise.
     80. Não existem hashes dos PDFs no índice que permitam provar a origem.
     88. As funções do livro de 1.000 páginas são algoritmos Python escritos
         manualmente.
     Conclusão: a ligação aos PDFs é indireta, parcial e não verificável."

Estava certo em todos. O que existia era eu tendo lido os tratados e digitado
as fórmulas no código. Isso não é ligação: é memória minha, e ninguém pode
conferir.

POR QUE NÃO É RAG
─────────────────
RAG é busca semântica alimentando um modelo de linguagem, e não existe modelo
de linguagem no momento da previsão — o motor é aritmética. Chamar de RAG seria
vender outra coisa.

O que os tratados dele permitem é melhor que RAG, porque eles não são prosa
solta: são FICHAS com formato fixo. A página 25 do Livro começa assim —

    MEGA FIRE  |  F01  |  IA01  |  FORMULAÇÃO 001
    Intervalo contextual desde a última ocorrência
    ...
    3. Formulação e leitura auditável
    Formulação auditável: D_t = t - max{i<t : Y_i=1}. Comparar a distribuição…

Mesa, família, inteligência, número da formulação, lente e a FÓRMULA, escritas.
Isso se lê exatamente, sem heurística e sem adivinhação. E a Régua tem o
próprio formato (`TEORIA 01/60 • R01-CAL-01 • LENTE 1/4` + `2. Fórmula
principal`), e o Estudo o dele (`MEGA FIRE | H006 | INTERVALOS`).

O QUE ESTE ÍNDICE GARANTE
─────────────────────────
Cada registro carrega o `sha256` do PDF e o número da página. Então dá para
apontar: "esta conta veio da página 25 do arquivo cujo hash é 3b63e598". É a
procedência que ele pediu nos achados 80 e 82.

E o índice é reconstruído quando qualquer hash muda (achado 44). Um PDF trocado
não continua valendo pelo índice velho.

O QUE ELE NÃO GARANTE, E EU NÃO VOU FINGIR
──────────────────────────────────────────
Ler a fórmula não é executá-la. `D_t = t - max{i<t : Y_i=1}` sai do PDF como
TEXTO; quem calcula intervalo continua sendo código Python. A diferença — e ela
é grande — é que agora o código declara qual registro do PDF ele implementa, e
`veto.py` cala a família quando esse registro não existe. A transcrição passa
de invisível a conferível: dá para ler a fórmula no índice, ler o código ao
lado, e me pegar errando.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from .leitor_pdf import abrir

RAIZ = Path(__file__).resolve().parent.parent
PASTA_PDFS = RAIZ / "tratados"
INDICE = RAIZ / "Logs" / "indice_tratados.json"
VERSAO_ESQUEMA = 3

# As mesas, como os tratados as escrevem. "LIGHTING" é como está no PDF dele —
# não corrijo o texto da fonte, mapeio.
MESAS = {
    "MEGA FIRE": "mega_fire",
    "LIGHTING": "lightning",
    "LIGHTNING": "lightning",
    "CRAZY TIME A": "crazy_time_a",
    "CRAZY TIME": "crazy_time",
    "IMMERSIVE": "immersive",
}


def _limpo(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


def _mesa(cabeca: str) -> Optional[str]:
    alvo = _sem_acento(cabeca).upper()
    for escrito, chave in MESAS.items():
        if escrito in alvo:
            return chave
    return None


# ─────────────────────────────────────────────────────── o Livro: 960 fichas
_CAB_LIVRO = re.compile(
    r"^\s*([A-ZÇÃÊÉÍÓÚ ]+?)\s*\|\s*(F\d{2})\s*\|\s*(IA\d{2})\s*\|\s*"
    r"FORMULA[ÇC][ÃA]O\s*(\d{1,4})", re.M | re.I)
_FORM_LIVRO = re.compile(
    r"Formula[çc][ãa]o\s+audit[áa]vel\s*:\s*(.+?)(?:\n\s*\d+\.\s|\Z)",
    re.S | re.I)
_LENTE = re.compile(r"\bL(\d)\b\s*\n?\s*lente", re.I)


def _ficha_livro(txt: str, pagina: int) -> Optional[Dict[str, Any]]:
    m = _CAB_LIVRO.search(txt)
    if not m:
        return None
    mesa = _mesa(m.group(1))
    if not mesa:
        return None
    corpo = txt[m.end():]
    linhas = [l for l in corpo.split("\n") if l.strip()]
    titulo = _limpo(" ".join(linhas[:2])) if linhas else ""
    mf = _FORM_LIVRO.search(txt)
    formula = _limpo(mf.group(1))[:400] if mf else ""
    ml = _LENTE.search(txt)
    return {
        "fonte": "livro", "mesa": mesa,
        "familia": m.group(2).upper(), "ia": m.group(3).upper(),
        "n_formulacao": int(m.group(4)),
        "titulo": titulo[:180],
        "lente": f"L{ml.group(1)}" if ml else None,
        "formula": formula,
        "pagina": pagina,
    }


# ────────────────────────────────────────────────────── a Régua: 60 teorias
_CAB_REGUA = re.compile(
    r"TEORIA\s*(\d{1,3})\s*/\s*(\d{1,3})\s*[•·|-]\s*"
    r"(R\d{2}-[A-Z]{3}-\d{2})\s*[•·|-]\s*LENTE\s*(\d)\s*/\s*(\d)", re.I)
_FORM_REGUA = re.compile(
    r"\d+\.\s*F[óo]rmula\s+principal\s*(.+?)(?:\n\s*\d+\.\s|\Z)", re.S | re.I)
_FAMILIA_REGUA = re.compile(r"Fam[íi]lia\s*(\d+)\s*:\s*([^•\n]+)", re.I)


def _ficha_regua(txt: str, pagina: int) -> Optional[Dict[str, Any]]:
    m = _CAB_REGUA.search(txt)
    if not m:
        return None
    linhas = [l for l in txt[m.end():].split("\n") if l.strip()]
    mf = _FORM_REGUA.search(txt)
    mfam = _FAMILIA_REGUA.search(txt)
    return {
        "fonte": "regua", "mesa": None,
        "familia": m.group(3).upper(), "ia": None,
        "n_formulacao": int(m.group(1)),
        "titulo": _limpo(linhas[0])[:180] if linhas else "",
        "lente": f"L{m.group(4)}",
        "grupo": _limpo(mfam.group(2))[:120] if mfam else None,
        "formula": _limpo(mf.group(1))[:400] if mf else "",
        "pagina": pagina,
    }


# ──────────────────────────────────────────── o Estudo: hipóteses H001..Hnnn
_CAB_ESTUDO = re.compile(
    r"^\s*([A-ZÇÃÊÉÍÓÚ ]+?)\s*\|\s*(H\d{3})\s*\|\s*([A-ZÇÃÊÉÍÓÚ /-]+)", re.M)


def _ficha_estudo(txt: str, pagina: int) -> Optional[Dict[str, Any]]:
    m = _CAB_ESTUDO.search(txt)
    if not m:
        return None
    mesa = _mesa(m.group(1))
    if not mesa:
        return None
    linhas = [l for l in txt[m.end():].split("\n") if l.strip()]
    mf = _FORM_REGUA.search(txt) or _FORM_LIVRO.search(txt)
    return {
        "fonte": "estudo", "mesa": mesa,
        "familia": m.group(2).upper(), "ia": None,
        "n_formulacao": int(m.group(2)[1:]),
        "titulo": _limpo(" ".join(linhas[:2]))[:180],
        "grupo": _limpo(m.group(3))[:80],
        "lente": None,
        "formula": _limpo(mf.group(1))[:400] if mf else "",
        "pagina": pagina,
    }


LEITORES = {"livro": _ficha_livro, "regua": _ficha_regua, "estudo": _ficha_estudo}


def _tipo_do_arquivo(nome: str) -> str:
    n = _sem_acento(nome).lower()
    if "regua" in n:
        return "regua"
    if "multiplicador" in n or "estudo" in n:
        return "estudo"
    return "livro"


def pdfs_presentes() -> List[Path]:
    """Os PDFs que o motor vai ler. A pasta é fixa e vem no pacote."""
    if not PASTA_PDFS.is_dir():
        return []
    return sorted(p for p in PASTA_PDFS.glob("*.pdf") if p.is_file())


def construir() -> Dict[str, Any]:
    """Lê os PDFs presentes e monta o índice, com procedência de cada ficha."""
    fichas: List[Dict[str, Any]] = []
    docs: List[Dict[str, Any]] = []
    for caminho in pdfs_presentes():
        t = abrir(caminho)
        tipo = _tipo_do_arquivo(caminho.name)
        ler = LEITORES[tipo]
        paginas = t.paginas()
        achadas = 0
        for i, txt in enumerate(paginas):
            if not txt.strip():
                continue
            f = ler(txt, i + 1)
            if f:
                f["sha256"] = t.sha256
                f["arquivo"] = caminho.name
                # A LENTE ENTRA NO ID, senão a Régua colide.
                # Cada teoria dela ocupa quatro páginas -- uma por lente -- e
                # sem a lente as quatro viravam o mesmo registro, com a fórmula
                # de uma delas valendo pelas outras três.
                f["id"] = (f"{f['fonte']}:{f['familia']}:"
                           f"{f.get('mesa') or '-'}:{f['n_formulacao']}"
                           f":{f.get('lente') or 'L0'}:p{f['pagina']}")
                fichas.append(f)
                achadas += 1
        docs.append({
            "arquivo": caminho.name, "tipo": tipo, "sha256": t.sha256,
            "paginas": len(paginas),
            "paginas_com_texto": sum(1 for x in paginas if x.strip()),
            "fichas": achadas, "erro": t.erro,
        })
    com_formula = sum(1 for f in fichas if f.get("formula"))
    return {
        "esquema": VERSAO_ESQUEMA,
        "documentos": docs,
        "fichas": fichas,
        "total_fichas": len(fichas),
        "fichas_com_formula": com_formula,
    }


def _assinatura(dados: Dict[str, Any]) -> str:
    return "|".join(f"{d['arquivo']}={d['sha256']}"
                    for d in sorted(dados.get("documentos") or [],
                                    key=lambda x: x["arquivo"]))


def carregar(reconstruir: bool = False) -> Dict[str, Any]:
    """O índice, reconstruído quando um PDF muda ou desaparece.

    A invalidação por hash é o achado 44 dele: antes só `esquema` e versão de
    código eram comparados, então trocar o PDF não invalidava nada e o índice
    velho seguia valendo — exatamente o oposto do que procedência significa.
    """
    atual = {d.name: None for d in pdfs_presentes()}
    if not reconstruir and INDICE.is_file():
        try:
            salvo = json.loads(INDICE.read_text(encoding="utf-8"))
        except Exception:
            salvo = None
        if salvo and salvo.get("esquema") == VERSAO_ESQUEMA:
            nomes = {d["arquivo"] for d in salvo.get("documentos") or []}
            if nomes == set(atual):
                # confere hash de verdade, não só o nome
                vivo = {}
                for p in pdfs_presentes():
                    import hashlib
                    vivo[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
                iguais = all(
                    vivo.get(d["arquivo"]) == d["sha256"]
                    for d in salvo.get("documentos") or [])
                if iguais:
                    return salvo
    dados = construir()
    try:
        INDICE.parent.mkdir(parents=True, exist_ok=True)
        tmp = INDICE.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        import os
        os.replace(tmp, INDICE)
    except OSError:
        pass
    return dados


# ─────────────────────────────────────────────────────────────── consultas
def por_familia(dados: Dict[str, Any], familia: str,
                mesa: Optional[str] = None) -> List[Dict[str, Any]]:
    """As fichas desta família (e desta mesa, se pedida)."""
    f = familia.upper()
    saida = [x for x in (dados.get("fichas") or [])
             if str(x.get("familia", "")).upper() == f]
    if mesa:
        saida = [x for x in saida if x.get("mesa") in (None, mesa)]
    return saida


def formula_de(dados: Dict[str, Any], familia: str,
               mesa: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A ficha COM fórmula desta família — ou None, que é resposta legítima.

    None é o que faz o gate funcionar: sem ficha, a família se cala em vez de
    rodar a minha transcrição por trás.
    """
    for x in por_familia(dados, familia, mesa):
        if x.get("formula"):
            return x
    return None


def resumo(dados: Dict[str, Any]) -> str:
    L = []
    for d in dados.get("documentos") or []:
        L.append(f"  {d['arquivo'][:44]:<44} {d['paginas']:>5}p  "
                 f"{d['fichas']:>4} fichas  sha {d['sha256'][:10]}"
                 + (f"  ERRO {d['erro']}" if d.get("erro") else ""))
    if not L:
        L.append("  nenhum PDF em tratados/ — as famílias que dependem deles"
                 " ficam caladas")
    L.append(f"  total: {dados.get('total_fichas', 0)} fichas, "
             f"{dados.get('fichas_com_formula', 0)} com fórmula legível")
    return "\n".join(L)
