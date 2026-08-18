# -*- coding: utf-8 -*-
"""
A BASE DE DADOS: OS TRÊS ESTUDOS DELE.

    "a biblioteca, a base de dados vai ser os três PDFs de fato, porque eu
     acho que ficou muito misturado"

Ele tinha razão. No software anterior os estudos dele eram uma fonte entre
outras -- a auditoria mediu: 21% do peso que decidia o número era invenção
minha, enxertada por cima. Aqui não há enxerto.

O QUE ESTE MÓDULO É
───────────────────
A única porta de entrada de conhecimento do núcleo. Nada é lido de outro
lugar. Se uma leitura não tem número de formulação, ela não existe.

O DESENHO QUE ELE PUBLICOU
──────────────────────────
O Tratado não é um catálogo solto, é uma grade fechada:

    12 inteligências  x  4 famílias cada  =  48 famílias
    48 famílias       x  5 mesas          =  240 combinações
    240              x  4 formulações     =  960 formulações

E as 48 famílias se dividem em duas metades com papéis diferentes:

    F01..F44   LEEM a mesa e apontam classe
    F45..F48   AGREGAM o que as outras disseram (a IA12)

Isso não é interpretação minha: está no cabeçalho de cada página do livro
dele, e a extração conferiu -- 960 formulações, da 1 à 960, nenhuma pulada,
192 por mesa nas cinco.

DUAS CAMADAS DE LEITURA
───────────────────────
    índice destilado    sempre presente, versionado. Número, mesa, família,
                        IA, título e FÓRMULA. É o que o programa executa.
    texto integral      só quando os PDFs estão em estudos_pdf/ e o
                        ABSORVER rodou. Traz a prosa: o contraditório de cada
                        formulação (seção 4), o estado da teoria (seção 5) e
                        os limites da amostra (seção 6).

O núcleo funciona só com o índice. O texto integral acrescenta o
contraditório dele -- que é melhor que o controle negativo que eu inventaria.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "academia_autonoma"
ARQ_INDICE = PASTA_DADOS / "indice_estudos_destilado.json"

# A chave do software -> o nome que ele escreve no cabeçalho do livro.
# `LIGHTING` é como está publicado; não é erro de digitação meu.
MESAS: Dict[str, str] = {
    "mega_fire": "MEGA FIRE",
    "lightning": "LIGHTING",
    "immersive": "IMMERSIVE",
    "crazy_time": "CRAZY TIME",
    "crazy_time_a": "CRAZY TIME A",
    "red_door": "RED DOOR",
}

# Quantas classes cada mesa tem. As roletas têm 37 casas; os jogos de roda
# grande têm 8 segmentos.
CLASSES: Dict[str, int] = {
    "mega_fire": 37, "lightning": 37, "immersive": 37,
    "crazy_time": 8, "crazy_time_a": 8, "red_door": 37,
}

# As quatro famílias que AGREGAM, em vez de ler a mesa.
FAMILIAS_AGREGADORAS = ("F45", "F46", "F47", "F48")

_CACHE: Dict[str, object] = {}


# ═══════════════════════════════════════════════════════════ identificação

def mesa_do(jogo: str) -> str:
    """O nome do livro a partir da chave do software, por prefixo mais longo.

    `crazy_time_a` começa com `crazy_time`: uma busca ingênua faria a mesa A
    citar a formulação da mesa comum. Citar a fonte errada é pior do que não
    citar.
    """
    j = str(jogo or "")
    achou = ""
    for chave in MESAS:
        if j.startswith(chave) and len(chave) > len(achou):
            achou = chave
    return MESAS.get(achou, "")


def classes_de(jogo: str) -> int:
    j = str(jogo or "")
    achou = ""
    for chave in CLASSES:
        if j.startswith(chave) and len(chave) > len(achou):
            achou = chave
    return CLASSES.get(achou, 37)


# ═══════════════════════════════════════════════════════════ o índice

def _indice() -> List[dict]:
    """As 960 formulações, cruas. Lidas uma vez."""
    if "formulacoes" in _CACHE:
        return _CACHE["formulacoes"]          # type: ignore[return-value]
    fs: List[dict] = []
    try:
        d = json.loads(ARQ_INDICE.read_text(encoding="utf-8"))
        for _estudo, corpo in (d.get("estudos") or {}).items():
            for u in corpo.get("unidades") or []:
                if u.get("tipo") == "formulacao":
                    fs.append(u)
    except Exception:
        fs = []
    fs.sort(key=lambda u: u.get("n", 0))
    _CACHE["formulacoes"] = fs
    return fs


def formulacoes(jogo: Optional[str] = None,
                familia: Optional[str] = None,
                ia: Optional[str] = None) -> List[dict]:
    """Filtra as formulações. Sem filtro, devolve as 960."""
    out = _indice()
    if jogo:
        alvo = mesa_do(jogo)
        out = [u for u in out if u.get("mesa") == alvo]
    if familia:
        out = [u for u in out if u.get("familia") == familia]
    if ia:
        out = [u for u in out if u.get("ia") == ia]
    return out


def familias() -> List[dict]:
    """As 48 famílias, uma vez cada, com a IA dona e a fórmula publicada.

    A mesma família aparece em 20 formulações (5 mesas x 4 cada); aqui ela
    aparece uma vez, que é como o programa a executa.
    """
    if "familias" in _CACHE:
        return _CACHE["familias"]             # type: ignore[return-value]
    vistas: Dict[str, dict] = {}
    for u in _indice():
        f = u.get("familia")
        if not f or f in vistas:
            continue
        vistas[f] = {
            "familia": f,
            "ia": u.get("ia", ""),
            "titulo": (u.get("titulo") or "").split("—")[0].strip(),
            "formula": u.get("formula", ""),
            "agrega": f in FAMILIAS_AGREGADORAS,
        }
    saida = sorted(vistas.values(), key=lambda d: d["familia"])
    _CACHE["familias"] = saida
    return saida


def familia(nome: str) -> Optional[dict]:
    for f in familias():
        if f["familia"] == nome:
            return f
    return None


def formulacao_de(familia_nome: str, jogo: str) -> Optional[dict]:
    """A primeira formulação desta família NESTA mesa — o endereço da leitura."""
    fs = formulacoes(jogo=jogo, familia=familia_nome)
    return fs[0] if fs else None


def endereco(familia_nome: str, jogo: str) -> str:
    """Onde conferir esta leitura no livro dele, em uma linha."""
    u = formulacao_de(familia_nome, jogo)
    if not u:
        return ""
    f = familia(familia_nome) or {}
    return (f"{u.get('ia')} · {familia_nome} · formulação #{u.get('n')} "
            f"(pág. {u.get('pagina')}) — {f.get('titulo', '')[:44]}")


# ═════════════════════════════════════════════════ o texto integral (opcional)

def _integral() -> List[dict]:
    if "integral" in _CACHE:
        return _CACHE["integral"]             # type: ignore[return-value]
    us: List[dict] = []
    for arq in sorted(PASTA_DADOS.glob("dados_livro_*.json")):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        us.extend(u for u in (d.get("unidades") or [])
                  if u.get("tipo") == "formulacao")
    _CACHE["integral"] = us
    return us


def tem_texto_integral() -> bool:
    return bool(_integral())


def _secao(familia_nome: str, jogo: str, prefixo: str) -> str:
    alvo = mesa_do(jogo)
    for u in _integral():
        if u.get("familia") == familia_nome and u.get("mesa") == alvo:
            for k, v in u.items():
                if k.startswith(prefixo) and v:
                    return str(v)
    return ""


def contraditorio(familia_nome: str, jogo: str) -> str:
    """Seção 4 — o teste que derrubaria esta leitura, escrito por ele.

    Vale mais que qualquer controle negativo que eu inventasse: quem escreveu
    a teoria é quem sabe o que a refuta.
    """
    return _secao(familia_nome, jogo, "s4_")


def estado_da_teoria(familia_nome: str, jogo: str) -> str:
    """Seção 5 — quando a teoria está ativa e quando volta para a sombra."""
    return _secao(familia_nome, jogo, "s5_")


def limites(familia_nome: str, jogo: str) -> str:
    """Seção 6 — o que a fonte não permite afirmar."""
    return _secao(familia_nome, jogo, "s6_")


# ═══════════════════════════════════════════════════════════════ conferência

def integridade() -> Dict[str, object]:
    """A grade dele está fechada? Devolve a conta, não uma opinião."""
    fs = _indice()
    ns = sorted(u.get("n", 0) for u in fs)
    mesas: Dict[str, int] = {}
    ias: Dict[str, int] = {}
    fams: Dict[str, int] = {}
    for u in fs:
        mesas[u.get("mesa", "?")] = mesas.get(u.get("mesa", "?"), 0) + 1
        ias[u.get("ia", "?")] = ias.get(u.get("ia", "?"), 0) + 1
        fams[u.get("familia", "?")] = fams.get(u.get("familia", "?"), 0) + 1
    faltando = ([] if not ns
                else sorted(set(range(min(ns), max(ns) + 1)) - set(ns)))
    return {
        "formulacoes": len(fs),
        "com_formula": sum(1 for u in fs if u.get("formula")),
        "mesas": mesas,
        "ias": len(ias),
        "familias": len(fams),
        "puladas": faltando,
        "texto_integral": tem_texto_integral(),
    }


def resumo() -> str:
    i = integridade()
    L = ["[Base] os três estudos dele são a base de dados deste núcleo",
         f"   {i['formulacoes']} formulações, {i['com_formula']} com fórmula "
         f"auditável",
         f"   {i['ias']} inteligências x {i['familias']} famílias x "
         f"{len(i['mesas'])} mesas"]
    if i["puladas"]:
        L.append(f"   ⚠ {len(i['puladas'])} formulações não foram lidas: "
                 f"{i['puladas'][:8]}")
    else:
        L.append("   a grade dele está fechada — nenhuma formulação faltando")
    L.append("   texto integral: "
             + ("presente (contraditório dele disponível)"
                if i["texto_integral"]
                else "ausente — rode ABSORVER_PDF.py com os PDFs na pasta"))
    return "\n".join(L)


if __name__ == "__main__":
    print()
    print(resumo())
    print()
    for f in familias():
        marca = "agrega" if f["agrega"] else "  lê  "
        print(f"  {f['familia']}  {f['ia']}  [{marca}]  "
              f"{f['titulo'][:40]:<40} {f['formula'][:40]}")
