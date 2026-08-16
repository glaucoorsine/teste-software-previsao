# -*- coding: utf-8 -*-
"""
BIBLIOTECA DE TEORIAS — os dois compêndios dele, virados em conhecimento usável.

O QUE ELE PEDIU
---------------
    "eu prefiro que você extraia tudo dos meus pdfs e ensine as IAs sobre
     teorias"

E é isso que este módulo faz. Não é resumo: são as 400 fichas do compêndio e as
416 do estudo de multiplicadores, extraídas inteiras e condensadas nos 80
conceitos que elas formam — cada conceito com tese, forma de medir, mecanismo e
o diagnóstico que o distingue.

O QUE FOI EXTRAÍDO
------------------
    COMPÊNDIO       400 fichas · 80 conceitos · 4 eixos, cada conceito visto
                    por cinco lentes (definição, assinatura temporal, teste
                    comparativo, robustez, replicação)

    MULTIPLICADORES 416 fichas com veredicto, das quais:
                        156  sem sinal confirmado
                        104  replicação ausente
                         52  sem ganho atual
                         52  candidato exploratório
                         52  exploratório e instável

ENSINAR NÃO É GUARDAR
---------------------
Um arquivo de teorias que ninguém lê é enfeite. O ensino acontece em três
lugares concretos, e cada um deles mudou por causa de uma ficha específica:

    ficha 226   CONSENSO ILUSÓRIO. "Muitos agentes derivados do mesmo código
                podem parecer independentes; unanimidade aparente não
                multiplica informação." Daqui saiu `n_efetivo()` — quando sete
                fontes correlacionadas concordam, o software passa a dizer
                quantas vozes existem de verdade, não quantas falaram.

    ficha 206   VAZAMENTO TEMPORAL. Descobrir e medir na mesma amostra. É o
                erro que já aconteceu aqui, e o `crivo_retrospectivo` carrega
                a separação por causa dele.

    ficha 281   APOFENIA. Ver padrão onde não há. Foi o falso positivo de 68%
                dos caçadores, corrigido em `agentes_ocorrencia`.

O ACHADO QUE MUDA O DESENHO DAS SETE IAS
----------------------------------------
O estudo de multiplicadores mede cada série por duas lentes separadas, e o
resultado é invertido entre as mesas:

    mesa            prever SE vem destaque      prever o TAMANHO
    Lighting              +8,2%                    -59,2%
    Mega Fire             -3,4%                    -16,5%
    Crazy Time           -15,4%                     +8,7%
    Crazy Time A          -9,9%                    +30,1%

Ou seja: na roleta o que dá sinal é a OCORRÊNCIA; no Crazy Time é a MAGNITUDE.
Misturar as duas — que é o que as sete IAs faziam, com INTENSIDADE votando ao
lado de QUENTE — soma um sinal com um anti-sinal. `lente_util()` diz, por mesa,
qual das duas perguntas tem chance de ser respondida.

NENHUM DESSES NÚMEROS É PROVA
-----------------------------
São 4 séries de 100 a 197 eventos, e o próprio estudo classifica o melhor caso
como "candidato exploratório". +30,1% no Crazy Time A vem de nove eventos. Isso
serve para escolher ONDE olhar, nunca para afirmar que funciona.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent
ARQ_TEORIAS = RAIZ / "dados_teorias.json"
ARQ_MULT = RAIZ / "dados_multiplicador_estudo.json"

# Abaixo disto, "skill positivo" é ruído com aparência de resultado. O próprio
# estudo diz: o +30,1% do Crazy Time A vem de nove eventos.
MIN_EVENTOS_PARA_CONFIAR = 30

# A partir de quanta sobreposição duas fontes viram "quase a mesma voz" na tela.
# Metade das listas em comum já é repetição suficiente para valer o aviso — e o
# aviso é só informativo: quem desconta de fato é o N efetivo, que usa a
# correlação inteira e não este corte.
QUASE_A_MESMA_VOZ = 0.5

_cache: Dict[str, Any] = {}


def _ler(arq: Path, padrao):
    chave = str(arq)
    if chave not in _cache:
        try:
            _cache[chave] = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache[chave] = padrao
    return _cache[chave]


def conceitos() -> List[dict]:
    """Os 80 conceitos do compêndio -- o resumo curado, um a cada cinco fichas."""
    return _ler(ARQ_TEORIAS, [])


# ─────────────────────────── os 400 dossiês inteiros, quando existirem ──────
#
# `conceitos()` acima é o que sobrou de eu ter transcrito o compêndio à mão:
# 80 conceitos, um a cada cinco teorias. O PDF tem 400 dossiês completos, cada
# um com nove a doze seções próprias -- tese, formalização, mecanismo,
# predições, competição entre explicações, identificação, controle negativo,
# condições-limite, leitura das amostras, valor teórico.
#
# `ABSORVER_PDF.py` extrai isso inteiro. Quando o arquivo estiver lá, é ELE que
# vale; o resumo de 80 fica só como rede de segurança para quem clonar o
# repositório sem os PDFs.
ARQ_DOSSIES = RAIZ / "dados_compendio_400_teorias_aleatoriedade_previsibilid.json"
ARQ_MULT_INTEGRAL = RAIZ / "dados_estudo_capacidade_preditiva_multiplicadores_400_.json"

# Do nome comprido do eixo no PDF para o código curto que o software já usa.
_EIXO_CURTO = {
    "PROBABILIDADE": "series",
    "INFORMAÇÃO": "informacao",
    "IA,": "ia",
    "FUNDAMENTOS": "fisica",
}

# Da seção do dossiê para o nome que o resto do programa já consulta.
_DE_PARA = {
    "titulo": "conceito",
    "tese_delimitada": "tese",
    "formalizacao_e_estimando": "medida",
    "mecanismo_em_camadas": "mecanismo",
    "predicoes_diagnosticas": "diagnostico",
}


def _eixo_curto(longo: str) -> str:
    for prefixo, curto in _EIXO_CURTO.items():
        if (longo or "").upper().startswith(prefixo):
            return curto
    return "series"


def dossies() -> List[dict]:
    """Os 400 dossiês do compêndio, inteiros. Lista vazia se o PDF não passou."""
    if "dossies" in _cache:
        return _cache["dossies"]
    d = _ler(ARQ_DOSSIES, {})
    saida = []
    for u in (d.get("unidades") or []):
        if u.get("tipo") != "dossie":
            continue
        reg = {k: v for k, v in u.items()
               if k not in ("tipo", "rotulos", "pagina")}
        for de, para in _DE_PARA.items():
            if de in reg:
                reg[para] = reg.pop(de)
        reg["eixo_longo"] = reg.get("eixo", "")
        reg["eixo"] = _eixo_curto(reg.get("eixo", ""))
        saida.append(reg)
    saida.sort(key=lambda r: r.get("n", 0))
    _cache["dossies"] = saida
    return saida


def fonte_do_compendio() -> str:
    """De onde as fichas estão saindo agora -- para o programa poder dizer."""
    return "400 dossiês do PDF" if dossies() else "resumo de 80 conceitos"


def estudo_multiplicador() -> dict:
    return _ler(ARQ_MULT, {})


def estudo_multiplicador_integral() -> List[dict]:
    """As 452 páginas do estudo de multiplicadores. Vazio se o PDF não passou."""
    if "mult_integral" in _cache:
        return _cache["mult_integral"]
    d = _ler(ARQ_MULT_INTEGRAL, {})
    _cache["mult_integral"] = list(d.get("unidades") or [])
    return _cache["mult_integral"]


def buscar(termo: str, limite: int = 5) -> List[dict]:
    """Conceitos cujo nome ou tese fala do termo."""
    t = (termo or "").lower().strip()
    if not t:
        return []
    achados = []
    for c in conceitos():
        alvo = (c.get("conceito", "") + " " + c.get("tese", "")).lower()
        if t in alvo:
            achados.append(c)
    return achados[:limite]


def por_eixo(eixo: str) -> List[dict]:
    return [c for c in conceitos() if c.get("eixo") == eixo]


def ficha(n: int) -> Optional[dict]:
    for c in conceitos():
        if c.get("n") == n:
            return c
    return None


# ────────────────────────────────────────────── ficha 226: consenso ilusório
def n_efetivo(votos_por_fonte: Dict[str, List[Any]],
              pesos: Dict[str, float] = None) -> Dict[str, Any]:
    """Quantas fontes INDEPENDENTES existem entre as que votaram.

    A ficha 226 dá a fórmula:

        N_ef = (Σ w)² / ΣΣ w_m·w_n·ρ_mn

    onde ρ é a correlação entre os votos de duas fontes. Aqui ρ é medido pela
    sobreposição das listas (Jaccard): duas fontes que apontam sempre os mesmos
    números têm ρ perto de 1 e valem por uma só.

    Por que isso importa na tela: "21 ← 4 teorias" parece quatro confirmações
    independentes. Se as quatro leem a mesma evidência, é UMA confirmação dita
    quatro vezes — e a confiança que o operador lê está inflada por construção.

    Devolve o número nominal, o efetivo e o quanto um infla o outro.
    """
    nomes = [k for k, v in (votos_por_fonte or {}).items() if v]
    if not nomes:
        return {"nominal": 0, "efetivo": 0.0, "inflacao": 1.0, "pares": []}
    w = {n: float((pesos or {}).get(n, 1.0)) for n in nomes}
    conj = {n: {str(x).strip() for x in votos_por_fonte[n]} for n in nomes}

    def rho(a, b):
        A, B = conj[a], conj[b]
        if not A or not B:
            return 0.0
        return len(A & B) / len(A | B)          # Jaccard

    soma_w = sum(w.values())
    denom = 0.0
    pares = []
    for a in nomes:
        for b in nomes:
            r = 1.0 if a == b else rho(a, b)
            denom += w[a] * w[b] * r
            if a < b and r >= QUASE_A_MESMA_VOZ:
                pares.append((a, b, round(r, 2)))
    efetivo = (soma_w ** 2) / denom if denom > 0 else float(len(nomes))
    efetivo = max(1.0, min(float(len(nomes)), efetivo))
    return {
        "nominal": len(nomes),
        "efetivo": round(efetivo, 2),
        "inflacao": round(len(nomes) / efetivo, 2) if efetivo else 1.0,
        # os pares que quase se repetem: é neles que o número nominal mente
        "pares": sorted(pares, key=lambda x: -x[2])[:5],
    }


def texto_n_efetivo(d: Dict[str, Any]) -> str:
    if not d or not d.get("nominal"):
        return ""
    if d["inflacao"] < 1.25:
        return f"{d['nominal']} fontes, praticamente independentes"
    return (f"{d['nominal']} fontes valendo {d['efetivo']:.1f} independentes "
            f"(ficha 226: concordância entre parecidas não multiplica prova)")


# ──────────────────────────────── estudo dos multiplicadores: qual lente serve
def lente_util(jogo: str) -> Dict[str, Any]:
    """Nesta mesa, vale perguntar SE vem destaque ou QUAL o tamanho?

    Responde com os números medidos no estudo dele, e diz claramente quando a
    resposta é "nenhuma das duas" — que é o caso do Mega Fire, negativo nas
    duas lentes.
    """
    d = (estudo_multiplicador().get("por_serie") or {}).get(str(jogo)) or {}
    sk = d.get("skill") or {}
    ocorrencia = sk.get("discriminação de ocorrência")
    magnitude = sk.get("magnitude")
    melhor = None
    if ocorrencia is not None and magnitude is not None:
        melhor = "ocorrencia" if ocorrencia >= magnitude else "magnitude"
        if max(ocorrencia, magnitude) <= 0:
            melhor = None
    return {
        "jogo": jogo, "ocorrencia": ocorrencia, "magnitude": magnitude,
        "melhor": melhor, "n_fichas": d.get("n"),
        "aviso": ("nenhuma das duas lentes teve ganho nesta mesa no estudo"
                  if melhor is None else
                  f"o estudo dele achou ganho na lente de {melhor}"),
    }


def resumo(jogo: str = None) -> str:
    cs = conceitos()
    em = estudo_multiplicador()
    L = [f"[Biblioteca] {len(cs)} conceitos do compêndio · "
         f"{em.get('n_fichas', 0)} fichas de multiplicador"]
    v = em.get("veredictos") or {}
    if v:
        L.append("   veredictos: " + " · ".join(f"{k.lower()} {n}"
                                                for k, n in v.items()))
    if jogo:
        lu = lente_util(jogo)
        if lu.get("ocorrencia") is not None:
            L.append(f"   {jogo}: ocorrência {lu['ocorrencia']:+.1f}% · "
                     f"magnitude {lu['magnitude']:+.1f}% — {lu['aviso']}")
    L.append("   nenhum destes números é prova: 100 a 197 eventos por série, "
             "e o melhor caso é 'candidato exploratório'")
    return "\n".join(L)
