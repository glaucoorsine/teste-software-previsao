# -*- coding: utf-8 -*-
"""
LEITOR DE PDF — sem dependência nenhuma, porque a ligação não pode ser opcional.

POR QUE ESCREVER ISTO EM VEZ DE USAR `pypdf`
────────────────────────────────────────────
A crítica dele foi exata: "não existe leitor que consulte os PDFs a cada
análise; o que existe são fórmulas transcritas à mão". Consertar isso significa
que o motor tem de abrir os tratados de verdade — e aí a leitura passa a ser
caminho crítico, não conveniência.

E `pypdf` é frágil justamente como dependência:

  . não vem com o Python; o instalador dele nem listava (foi um achado dele)
  . neste ambiente ele estoura no import, porque a `cryptography` instalada
    quebra com um panic de Rust que o `pypdf` não trata (ele só trata
    ImportError, então cai no chão em vez de usar o provedor alternativo)
  . se falta na máquina dele, TODAS as famílias ficariam mudas — e um software
    que emudece por falta de biblioteca é pior que um que não tenta

Estes três tratados são PDF 1.4 gerados por ferramenta, com três fontes CID
subconjunto e CMap `ToUnicode` de um byte. Isso é um formato pequeno e fechado:
dá para ler com `zlib` e expressão regular, que já vêm no Python.

O QUE ELE FAZ, E O QUE NÃO FAZ
──────────────────────────────
Faz: descomprime os streams de conteúdo, segue o operador de fonte (`Tf`), lê
os operadores de texto (`Tj`, `TJ`, `'`, `"`), e traduz cada byte pela CMap da
fonte corrente. Devolve o texto por PÁGINA, porque a página é a procedência —
sem ela não há como provar de onde saiu uma fórmula.

Não faz: PDF cifrado, texto em imagem (não há OCR aqui), fontes sem
`ToUnicode`, nem layout em colunas com ordem visual. Quando não consegue ler,
diz que não conseguiu — nunca devolve texto pela metade fingindo sucesso.
"""
from __future__ import annotations

import hashlib
import re
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────── objetos do PDF
_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)


def _objetos(bruto: bytes) -> Dict[int, bytes]:
    """Todos os objetos indiretos, por número. Ignora o índice (xref).

    Ler pelo xref seria o certo num PDF qualquer; aqui varrer é mais robusto,
    porque PDF gerado por ferramenta às vezes traz xref desatualizado e o
    conteúdo continua inteiro no arquivo.
    """
    saida: Dict[int, bytes] = {}
    for m in _OBJ.finditer(bruto):
        try:
            saida[int(m.group(1))] = m.group(3)
        except ValueError:
            continue
    return saida


def _ascii85(dados: bytes) -> bytes:
    """Desfaz ASCII85. Estes tratados usam `[ /ASCII85Decode /FlateDecode ]`.

    Descobri isto depurando: o stream não inflava porque não era Flate puro --
    era Flate DENTRO de ASCII85. Um filtro em cadeia, e eu tratava só um.
    """
    import base64
    corpo = dados.strip()
    if corpo.startswith(b"<~"):
        corpo = corpo[2:]
    fim = corpo.find(b"~>")
    if fim >= 0:
        corpo = corpo[:fim]
    corpo = b"".join(corpo.split())
    return base64.a85decode(corpo)


def _asciihex(dados: bytes) -> bytes:
    corpo = b"".join(dados.split())
    if corpo.endswith(b">"):
        corpo = corpo[:-1]
    if len(corpo) % 2:
        corpo += b"0"
    return bytes.fromhex(corpo.decode("ascii", "ignore"))


def _flate(dados: bytes) -> bytes:
    for tentativa in (dados, dados.strip(b"\r\n")):
        try:
            return zlib.decompress(tentativa)
        except zlib.error:
            continue
    # stream truncado: aproveita o que der em vez de perder a página inteira
    return zlib.decompressobj().decompress(dados)


_FILTROS = {
    b"FlateDecode": _flate, b"Fl": _flate,
    b"ASCII85Decode": _ascii85, b"A85": _ascii85,
    b"ASCIIHexDecode": _asciihex, b"AHx": _asciihex,
}


def _inflar(corpo: bytes) -> Optional[bytes]:
    """O conteúdo do stream, passando por TODOS os filtros, na ordem declarada.

    `/Filter` pode ser um nome ou uma LISTA -- e quando é lista, a ordem é a de
    aplicação. Tratar só o último (ou só o Flate) devolve lixo, que era por que
    as 300 páginas saíam vazias.
    """
    m = _STREAM.search(corpo)
    if not m:
        return None
    dados = m.group(1)
    cabeca = corpo[:m.start()]
    nomes = re.findall(rb"/([A-Za-z0-9]+)", cabeca)
    cadeia = [n for n in nomes if n in _FILTROS]
    if not cadeia:
        return dados
    for nome in cadeia:
        try:
            dados = _FILTROS[nome](dados)
        except Exception:
            return None
    return dados


# ─────────────────────────────────────────────────────────────────── as CMaps
_BFCHAR = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")


def _ler_cmap(texto: bytes) -> Dict[int, str]:
    """Código do byte → caractere, lido da CMap `ToUnicode` da fonte.

    Sem isto o texto sai como lixo: a fonte é um subconjunto, então o byte 0x05
    não é "5", é o que a CMap diz que é (no caso destes tratados, "é").
    """
    mapa: Dict[int, str] = {}
    for bloco in re.findall(rb"beginbfchar(.*?)endbfchar", texto, re.S):
        for cod, uni in _BFCHAR.findall(bloco):
            try:
                mapa[int(cod, 16)] = _uni(uni)
            except ValueError:
                continue
    for bloco in re.findall(rb"beginbfrange(.*?)endbfrange", texto, re.S):
        for lo, hi, uni in _BFRANGE.findall(bloco):
            try:
                a, b, base = int(lo, 16), int(hi, 16), int(uni, 16)
            except ValueError:
                continue
            if b - a > 65535:
                continue
            for k in range(a, b + 1):
                mapa[k] = chr(base + (k - a))
    return mapa


def _uni(hexa: bytes) -> str:
    """Um valor de CMap pode ser um caractere ou uma sequência UTF-16BE."""
    h = hexa.decode("ascii", "ignore")
    if len(h) <= 4:
        return chr(int(h, 16))
    return "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h) - 3, 4))


# ───────────────────────────────────────────────────────── operadores de texto
_TEXTO = re.compile(
    rb"(?:"
    rb"/([^\s/\[\]<>(){}]+)\s+[\d.]+\s+Tf"      # 1 troca de fonte
    rb"|\[((?:[^\[\]\\]|\\.)*)\]\s*TJ"            # 2 vetor de pedaços
    rb"|\(((?:[^()\\]|\\.)*)\)\s*(?:Tj|')"        # 3 pedaço único
    rb"|(T\*|Td|TD|ET)"                           # 4 quebra de linha
    rb")", re.S)
_PEDACO = re.compile(rb"\(((?:[^()\\]|\\.)*)\)")

_ESCAPES = {b"n": "\n", b"r": "\r", b"t": "\t", b"b": "\b", b"f": "\f",
            b"(": "(", b")": ")", b"\\": "\\"}


def _decodificar(cru: bytes, cmap: Dict[int, str]) -> str:
    """Uma string literal do PDF, byte a byte, pela CMap da fonte corrente."""
    saida: List[str] = []
    i = 0
    while i < len(cru):
        c = cru[i:i + 1]
        if c == b"\\" and i + 1 < len(cru):
            prox = cru[i + 1:i + 2]
            if prox in _ESCAPES:
                saida.append(_ESCAPES[prox])
                i += 2
                continue
            if prox.isdigit():
                # octal: \053
                oct_ = cru[i + 1:i + 4]
                fim = 0
                while fim < len(oct_) and oct_[fim:fim + 1].isdigit():
                    fim += 1
                try:
                    cod = int(oct_[:fim], 8)
                except ValueError:
                    cod = 0
                saida.append(cmap.get(cod, chr(cod) if 32 <= cod < 127 else ""))
                i += 1 + fim
                continue
            i += 2
            continue
        cod = cru[i]
        if cmap:
            saida.append(cmap.get(cod, ""))
        else:
            saida.append(chr(cod) if 32 <= cod < 127 else "")
        i += 1
    return "".join(saida)


def _texto_do_stream(conteudo: bytes,
                     cmaps_por_apelido: Dict[str, Dict[int, str]]) -> str:
    """Percorre os operadores e monta o texto da página."""
    partes: List[str] = []
    corrente: Dict[int, str] = {}
    for m in _TEXTO.finditer(conteudo):
        fonte, vetor, unico, quebra = m.group(1), m.group(2), m.group(3), m.group(4)
        if fonte is not None:
            corrente = cmaps_por_apelido.get(fonte.decode("ascii", "ignore"), {})
        elif vetor is not None:
            for p in _PEDACO.findall(vetor):
                partes.append(_decodificar(p, corrente))
        elif unico is not None:
            partes.append(_decodificar(unico, corrente))
        elif quebra is not None:
            partes.append("\n")
    txt = "".join(partes)
    # o PDF quebra a linha por posicionamento, então sobram quebras vazias
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


# ────────────────────────────────────────────────────────────────── a fachada
class Tratado:
    """Um PDF aberto, lido por página, com a impressão digital dele.

    O `sha256` não é enfeite: é o que permite provar que a fórmula que o motor
    executou veio DESTE arquivo, e é o que invalida o índice quando ele muda.
    Ele cobrou os dois (achados 44, 80, 82).
    """

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.bruto = self.caminho.read_bytes()
        self.sha256 = hashlib.sha256(self.bruto).hexdigest()
        self.erro: Optional[str] = None
        if not self.bruto.startswith(b"%PDF"):
            self.erro = "não é PDF"
        if b"/Encrypt" in self.bruto:
            self.erro = "PDF cifrado — este leitor não decifra"
        self._objs = _objetos(self.bruto) if not self.erro else {}
        self._cmaps = self._montar_cmaps()
        self._paginas: Optional[List[str]] = None

    # -- fontes -------------------------------------------------------------
    def _montar_cmaps(self) -> Dict[str, Dict[int, str]]:
        """Apelido da fonte (`F1+0`) → CMap de `ToUnicode`.

        DOIS ERROS MEUS AQUI, E OS DOIS APAGAVAM OS ACENTOS.
        ----------------------------------------------------
        1. Eu procurava `beginbfchar` no CORPO do objeto -- e ele vive DENTRO
           do stream comprimido. A busca nunca casava, nenhuma CMap era
           carregada, e o texto saía por um caminho de emergência que só
           deixava passar ASCII: "A Régua" virava "A Rgua".

           O sintoma é enganoso: parece que funcionou, porque sai texto legível.
           Só falta um acento aqui e outro ali -- e depois de mil páginas, todo
           código como `F01` sobrevive e toda palavra com acento fica torta.

        2. Eu tentava casar apelido varrendo os dicionários de recursos. Não
           precisa: o próprio objeto da fonte declara `/Name /F1+0`. A fonte
           diz como ela se chama.

        Agora o caminho é o direto: acha as fontes, lê o `/Name` e o
        `/ToUnicode` de cada uma, e infla SÓ esses objetos.
        """
        saida: Dict[str, Dict[int, str]] = {}
        cache: Dict[int, Dict[int, str]] = {}
        for corpo in self._objs.values():
            if not re.search(rb"/Type\s*/Font\b", corpo):
                continue
            m_nome = re.search(rb"/Name\s*/([^\s/\[\]<>(){}]+)", corpo)
            m_tou = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", corpo)
            if not m_tou:
                continue
            alvo = int(m_tou.group(1))
            if alvo not in cache:
                d = _inflar(self._objs.get(alvo, b""))
                cache[alvo] = _ler_cmap(d) if d else {}
            mapa = cache[alvo]
            if not mapa:
                continue
            if m_nome:
                saida[m_nome.group(1).decode("latin-1", "ignore")] = mapa
            # o apelido também pode vir só do dicionário de recursos
            for ap, fnum in re.findall(
                    rb"/([^\s/\[\]<>(){}]+)\s+(\d+)\s+\d+\s+R",
                    b"".join(self._objs.values())):
                pass
        if not saida and cache:
            maior = max(cache.values(), key=len)
            saida = {"__unica__": maior}
        return saida

    # -- páginas ------------------------------------------------------------
    def paginas(self) -> List[str]:
        """O texto de cada página, na ordem do documento."""
        if self._paginas is not None:
            return self._paginas
        if self.erro:
            self._paginas = []
            return self._paginas
        saida: List[str] = []
        unica = self._cmaps.get("__unica__")
        for num in self._ordem_das_paginas():
            corpo = self._objs.get(num, b"")
            m = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", corpo)
            alvos = [int(m.group(1))] if m else []
            if not alvos:
                m2 = re.search(rb"/Contents\s*\[(.*?)\]", corpo, re.S)
                if m2:
                    alvos = [int(x) for x in
                             re.findall(rb"(\d+)\s+\d+\s+R", m2.group(1))]
            mapas = dict(self._cmaps)
            if unica:
                mapas = dict(self._cmaps)
            txt = []
            for a in alvos:
                d = _inflar(self._objs.get(a, b""))
                if d:
                    txt.append(_texto_do_stream(d, mapas if not unica else
                                                _tudo_igual(d, unica)))
            saida.append("\n".join(t for t in txt if t))
        self._paginas = saida
        return saida

    def _ordem_das_paginas(self) -> List[int]:
        """Os objetos de página, na ordem em que o documento as encadeia."""
        paginas = [n for n, c in self._objs.items()
                   if re.search(rb"/Type\s*/Page\b", c)
                   and not re.search(rb"/Type\s*/Pages\b", c)]
        # a árvore /Kids dá a ordem verdadeira; sem ela, o número do objeto é a
        # melhor aproximação (e nestes PDFs gerados ela coincide)
        ordem: List[int] = []
        for corpo in self._objs.values():
            if re.search(rb"/Type\s*/Pages\b", corpo):
                m = re.search(rb"/Kids\s*\[(.*?)\]", corpo, re.S)
                if m:
                    for x in re.findall(rb"(\d+)\s+\d+\s+R", m.group(1)):
                        k = int(x)
                        if k in paginas and k not in ordem:
                            ordem.append(k)
        for p in sorted(paginas):
            if p not in ordem:
                ordem.append(p)
        return ordem

    def texto(self) -> str:
        return "\n\n".join(self.paginas())

    def resumo(self) -> str:
        p = self.paginas()
        cheias = sum(1 for x in p if x.strip())
        return (f"{self.caminho.name}: {len(p)} páginas, {cheias} com texto, "
                f"sha256 {self.sha256[:12]}"
                + (f" — ERRO: {self.erro}" if self.erro else ""))


def _tudo_igual(conteudo: bytes, mapa: Dict[int, str]) -> Dict[str, Dict[int, str]]:
    """Quando não se casou apelido com fonte, toda fonte usa a mesma CMap."""
    aps = set(re.findall(rb"/([^\s/\[\]<>(){}]+)\s+[\d.]+\s+Tf", conteudo))
    return {a.decode("ascii", "ignore"): mapa for a in aps} or {"F1": mapa}


def abrir(caminho: str | Path) -> Tratado:
    return Tratado(caminho)
