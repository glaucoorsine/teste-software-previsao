# -*- coding: utf-8 -*-
"""
GAMBLINGCOUNTING — quantas pessoas estão na mesa, e os últimos resultados.

POR QUE ESTA FONTE
------------------
Ele mandou os cinco endereços e disse o que quer deles:

    "para saber quantas pessoas tem e pegar os últimos 200 resultados para
     análise rápida"

E junto veio uma percepção que nenhuma outra fonte permitia testar:

    "normalmente quando o volume maior de pessoas online, mega acima de 800
     por exemplo, crazy acima de 13 mil, mais fácil a previsão e os
     multiplicadores"

Isso é uma hipótese com mecanismo plausível: mais gente na mesa é horário de
pico, e horário de pico muda o ritmo do crupiê, a frequência de giro e o
comportamento da casa. Se for verdade, o software deve prever mais quando a
mesa está cheia e ficar quieto quando está vazia — e isso é medível.

Sem este número, essa teoria não tinha como ser testada. É a razão principal
desta fonte existir.

ATENÇÃO AO QUE JÁ FALHOU AQUI
-----------------------------
Numa sondagem anterior este site respondeu 403 em todos os endereços — é um
Cloudflare que barra cliente que não parece navegador. Por isso: cabeçalho de
navegador de verdade, e falha silenciosa que não derruba nada. Se voltar 403
na máquina dele, o aviso diz exatamente isso, em vez de um erro cru.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:      # pragma: no cover - ambiente sem a biblioteca
    requests = None

RAIZ = Path(__file__).resolve().parent
TIMEOUT = 20

PAGINAS = {
    "lightning": "https://gamblingcounting.com/lightning-roulette",
    "mega_fire": "https://gamblingcounting.com/roulette",
    "crazy_time": "https://gamblingcounting.com/crazy-time",
    "crazy_time_a": "https://gamblingcounting.com/crazy-time-a",
}

# O limiar em que ele diz que a mesa "fica boa". Guardado por mesa porque a
# escala é完全 diferente: 800 pessoas no Mega Fire é cheio, no Crazy Time é vazio.
PICO = {
    "mega_fire": 800,
    "lightning": 800,
    "crazy_time": 13000,
    "crazy_time_a": 13000,
}

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def _numero(txt: str) -> Optional[int]:
    """'13,482' e '13.482' e '13 482' viram 13482."""
    t = re.sub(r"[^\d]", "", str(txt or ""))
    try:
        return int(t) if t else None
    except ValueError:
        return None


def extrair_jogadores(html: str) -> Optional[int]:
    """Quantas pessoas estão na mesa agora.

    O site pode escrever isso de várias formas conforme o layout muda, então
    as tentativas vão da mais específica para a mais genérica. Melhor devolver
    None do que devolver um número de outra coisa.
    """
    padroes = [
        r'"players"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'"onlinePlayers"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'"playersOnline"\s*:\s*"?(\d[\d.,\s]*)"?',
        r'([\d.,\s]{2,})\s*(?:players|jogadores)\s*(?:online)?',
        r'(?:players|jogadores)\s*(?:online)?\s*[:\-]?\s*([\d.,\s]{2,})',
    ]
    for p in padroes:
        m = re.search(p, html or "", re.I)
        if m:
            n = _numero(m.group(1))
            if n and 0 < n < 10_000_000:
                return n
    return None


# O "data" ACEITAVA QUALQUER COISA.
#
# A busca varria `results`, `history`, `spins`, `lastResults` e `data`, pegava
# o PRIMEIRO array que desse `json.loads` e devolvia como histórico -- sem
# conferir se aquilo eram giros.
#
# `"data"` é o nome mais comum que existe numa página. Qualquer bloco de
# anúncio, de configuração ou de rastreio que traga `"data": [...]` casa com a
# expressão e ganha da fonte verdadeira, porque a ordem das chaves decide e
# `data` estava na lista. Isso vira histórico inteiro inventado.
#
# E foi o que ele fotografou: Crazy Time mostrando "5" e mais nada, volta após
# volta. Não havia como a mesa saber que estava lendo lixo -- números são
# números, e a tela não tem como distinguir um giro de um id de banner.
#
# Agora todo valor é conferido contra o domínio da mesa (as 37 casas da
# roleta, os 8 símbolos do Crazy Time) e o array só é aceito se a MAIORIA dos
# itens passar. Um array de ids não passa; um histórico de verdade passa
# inteiro.
CHAVES = ("results", "history", "spins", "lastResults", "data")
FRACAO_VALIDA = 0.8
MIN_ITENS = 5


def _dominio(jogo: str) -> set:
    try:
        from hist_buffer import DOMAIN, ROULETTE
        return DOMAIN.get(jogo) or ROULETTE
    except Exception:
        return {str(i) for i in range(37)}


def _valores_validos(arr, dom, aliases) -> tuple:
    """Quantos itens da lista são giros DESTA mesa. Devolve (valores, vistos)."""
    saida, vistos = [], 0
    for it in arr:
        v = it
        if isinstance(it, dict):
            for c in ("result", "value", "number", "outcome", "sector",
                      "wheelSector", "slotResult", "segment", "n"):
                if it.get(c) is not None:
                    v = it[c]
                    break
        if isinstance(v, (dict, list)):
            vistos += 1
            continue
        vistos += 1
        s = str(v).strip()
        if not s:
            continue
        s = aliases.get(s.lower().replace(" ", "").replace("_", ""), s)
        if s in dom:
            saida.append(s)
    return saida, vistos


def _varrer(obj, dom, aliases, melhor, fundo=0):
    """Procura a lista de giros em QUALQUER profundidade do JSON.

    A BUSCA SÓ OLHAVA O PRIMEIRO NÍVEL, E A PÁGINA DELE É ANINHADA.
    --------------------------------------------------------------
    A versão anterior casava `"history": [...]` por expressão regular no texto
    do HTML. Isso pega um JSON raso e perde o formato que as páginas modernas
    usam de fato -- o casinoscores é um app React e guarda o estado assim:

        __NEXT_DATA__ → props → pageProps → initialData → table → latestResults

    Testado: com `latestResults` aninhado, a leitura devolvia `[]`. Ou seja, a
    página que ele mandou seria lida como vazia, e a Crazy Time A continuaria
    sem dados mesmo com o endereço certo.

    Agora o JSON é percorrido inteiro e vale a MAIOR lista que passe no crivo de
    domínio -- o nome da chave deixa de importar, o que também tira o problema
    do `"data"` genérico: não é o nome que autoriza, é o conteúdo.
    """
    if fundo > 8:
        return melhor
    if isinstance(obj, list):
        if len(obj) >= MIN_ITENS:
            vals, vistos = _valores_validos(obj, dom, aliases)
            if vistos and len(vals) / vistos >= FRACAO_VALIDA and len(vals) > len(melhor):
                melhor = vals
        for it in obj[:60]:
            if isinstance(it, (dict, list)):
                melhor = _varrer(it, dom, aliases, melhor, fundo + 1)
    elif isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (dict, list)):
                melhor = _varrer(v, dom, aliases, melhor, fundo + 1)
    return melhor


_BLOCOS = re.compile(r"[\[{]", re.S)


def extrair_resultados(html: str, jogo: str, limite: int = 200) -> List[str]:
    """Os últimos resultados, do mais novo para o mais velho.

    Lê de duas formas, e fica com a melhor: os blocos JSON embutidos na página
    (varridos até o fim, em qualquer profundidade) e, como reserva, o casamento
    direto das chaves conhecidas. Em ambos, todo valor é conferido contra o
    domínio da mesa -- é isso que impede um array de ids de virar histórico.
    """
    if not html:
        return []
    dom = _dominio(jogo)
    aliases = {"coinflip": "CoinFlip", "cashhunt": "CashHunt",
               "pachinko": "Pachinko", "crazybonus": "CrazyBonus",
               "bonus": "CrazyBonus", "crazytime": "CrazyBonus"}
    melhor: List[str] = []

    # 1) os JSON grandes embutidos (é onde o casinoscores guarda o estado)
    for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S | re.I):
        corpo = m.group(1).strip()
        for inicio in (corpo.find("{"), corpo.find("[")):
            if inicio < 0:
                continue
            try:
                dados = json.loads(corpo[inicio:])
            except ValueError:
                continue
            melhor = _varrer(dados, dom, aliases, melhor)
            break
    if melhor:
        return melhor[:limite]

    # 2) reserva: casar as chaves conhecidas direto no texto
    for chave in CHAVES:
        for m in re.finditer(rf'"{chave}"\s*:\s*(\[.*?\])', html, re.S):
            try:
                arr = json.loads(m.group(1))
            except ValueError:
                continue
            if not isinstance(arr, list) or len(arr) < MIN_ITENS:
                continue
            vals, vistos = _valores_validos(arr, dom, aliases)
            if not vistos or len(vals) / vistos < FRACAO_VALIDA:
                continue
            if len(vals) > len(melhor):
                melhor = vals
        if melhor:
            return melhor[:limite]
    return melhor[:limite]


def coletar(jogo: str) -> Dict[str, Any]:
    """Jogadores online e últimos resultados desta mesa, na página padrão."""
    url = PAGINAS.get(jogo)
    if not url:
        return {"jogo": jogo, "erro": "mesa sem página neste site"}
    return coletar_url(url, jogo)


def coletar_url(url: str, jogo: str) -> Dict[str, Any]:
    """A mesma leitura, de QUALQUER página.

    O CASINOSCORES É A PÁGINA DO PROVEDOR, E EU SÓ LIA O AGREGADOR.
    ---------------------------------------------------------------
    Este arquivo estava amarrado ao gamblingcounting: `PAGINAS` era um mapa
    fixo e `coletar()` só sabia ler de lá. Quando ele mandou

        https://www.casino.org/casinoscores/pt-br/crazy-time-a/

    não havia como usar — a função não aceitava endereço, só nome de mesa.

    E não precisava de parser novo: `extrair_resultados` não procura o layout
    do site, procura um bloco JSON com lista de resultados e confere cada
    valor contra o domínio da mesa. Isso funciona em qualquer página que
    embuta o histórico, e recusa o que não for daquela mesa.

    A separação também importa para o número de jogadores: `extrair_jogadores`
    tem o formato do gamblingcounting, e num site diferente ele devolve None
    em vez de inventar — que é o certo.
    """
    if not url:
        return {"jogo": jogo, "erro": "sem endereço"}
    if requests is None:
        return {"jogo": jogo, "erro": "biblioteca requests ausente"}
    try:
        r = requests.get(url, headers=CABECALHO, timeout=TIMEOUT)
    except Exception as e:
        return {"jogo": jogo, "erro": f"{type(e).__name__}: {str(e)[:60]}"}
    if r.status_code == 403:
        return {"jogo": jogo,
                "erro": "403 — o site bloqueia quem não parece navegador "
                        "(Cloudflare). Já aconteceu antes nesta fonte."}
    if r.status_code != 200:
        return {"jogo": jogo, "erro": f"HTTP {r.status_code}"}

    html = r.text or ""
    jogadores = extrair_jogadores(html)
    resultados = extrair_resultados(html, jogo)
    pico = PICO.get(jogo)
    return {
        "jogo": jogo, "url": url,
        "jogadores": jogadores, "resultados": resultados,
        "n_resultados": len(resultados),
        "pico": pico,
        "mesa_cheia": (jogadores >= pico) if (jogadores and pico) else None,
        # página que respondeu 200 mas sem histórico reconhecível NÃO é
        # sucesso: quem chamou precisa saber para tentar a próxima
        "erro": None if resultados else "página sem histórico desta mesa",
    }


def resumo(d: Dict[str, Any]) -> str:
    if d.get("erro"):
        return f"[GC] {d['jogo']}: {d['erro']}"
    j = d.get("jogadores")
    L = [f"[GC] {d['jogo']}: "
         + (f"{j} pessoas na mesa" if j else "não achou o número de pessoas")
         + f" · {d.get('n_resultados', 0)} resultados"]
    if d.get("mesa_cheia") is True:
        L.append(f"     mesa CHEIA (acima de {d.get('pico')}) — "
                 f"é o momento que ele diz ser melhor para prever")
    elif d.get("mesa_cheia") is False:
        L.append(f"     mesa vazia (abaixo de {d.get('pico')})")
    return "\n".join(L)
