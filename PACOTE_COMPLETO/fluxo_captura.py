# -*- coding: utf-8 -*-
"""
Fluxo principal de captura — único ponto de entrada.
Conecta: fetch_historico + time_utils + hist_buffer.
Garante: idempotência de snapshot, dedupe de evento, domínio válido.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from time_utils import canonical_ts, event_key, sort_key_ts
from hist_buffer import merge, load, normalizar_evento, DOMAIN
from fetch_historico import fetch_paginas
from engolido import engolido

ROOT = Path(__file__).resolve().parent
BUF_DIR = ROOT / "Logs" / "hist_buffers"
BUF_DIR.mkdir(parents=True, exist_ok=True)
MAX_GIROS_BUFFER = 20000   # quantos giros o buffer de cada mesa guarda
SNAP_DIR = ROOT / "Logs" / "snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)

API_BY_GAME = {
    "mega_fire": "https://api-cs.casino.org/svc-evolution-game-events/api/megafireblazeroulette",
    "lightning": "https://api-cs.casino.org/svc-evolution-game-events/api/lightningroulette",
    "crazy_time": "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime",
    # Crazy Time A e uma segunda mesa do mesmo jogo. O nome no endpoint nao
    # da para adivinhar daqui, entao a lista abaixo e tentada em ordem e a
    # primeira que responder fica valendo.
    "crazy_time_a": "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimea",
}

# Candidatos alternativos por mesa, tentados quando o principal nao responde.
# CRAZY TIME A NAO ABRE, E O MOTIVO E O NOME DO ENDERECO.
#
# Ele relatou: "Crazy time a tambem nao [funcionou]". A mesa existe, o resto do
# software esta pronto para ela, e o que falta e uma unica coisa -- como o
# provedor chama essa mesa na URL. Nao da para adivinhar daqui: o proxy deste
# ambiente bloqueia o dominio, entao quem descobre e a maquina dele.
#
# A lista abaixo cobre as grafias plausiveis, e agora existe uma segunda
# familia de candidatos: o trackpotapi, que o coletor ja descobriu sozinho para
# lightning e immersive (esta em Logs/fontes_descobertas.json, na maquina dele).
# Se o casino.org nao tiver essa mesa, e bem possivel que o outro tenha.
#
# O que responder primeiro fica GRAVADO (ver `_lembrar_fonte`), entao a
# descoberta acontece uma vez e nunca mais.
# DUAS FONTES EXISTEM, E EU SO USAVA UMA.
#
# Ele reparou: "tanto a immersive quanto a crazy time a possuem dois links de
# api, porque so esta no casino?". Tinha razao, e a prova estava no proprio
# arquivo dele: Logs/fontes_descobertas.json ja trazia
#
#     "immersive:seq": ".../trackersino/immersive-roulette/history"
#
# O coletor descobriu essa fonte sozinho, gravou, e o fluxo de captura NUNCA
# consultou -- porque so o Crazy Time A tinha alternativas cadastradas aqui.
# Quando o casino.org falhava, a mesa simplesmente morria tendo uma segunda
# fonte disponivel e ignorada.
#
# Agora TODAS as mesas tem alternativa. Se a primeira nao responder, cai para
# a outra e grava qual funcionou.
API_ALTERNATIVAS = {
    "lightning": [
        "https://api.trackpotapi.com/api/trackersino/lightningroulette/history",
        "https://api.trackpotapi.com/api/trackersino/lightning-roulette/history",
    ],
    "mega_fire": [
        "https://api.trackpotapi.com/api/trackersino/mega-fire-blaze-roulette/history",
        "https://api.trackpotapi.com/api/trackersino/megafireblazeroulette/history",
    ],
    "crazy_time": [
        "https://api.trackpotapi.com/api/trackersino/crazy-time/history",
        "https://api.trackpotapi.com/api/trackersino/crazytime/history",
    ],
    "crazy_time_a": [
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime-a",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimeA",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazy-time-a",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime2",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimeatable",
        "https://api.trackpotapi.com/api/trackersino/crazy-time-a/history",
        "https://api.trackpotapi.com/api/trackersino/crazytimea/history",
        "https://api.trackpotapi.com/api/trackersino/crazy-time-a-roulette/history",
    ],
}

# onde fica gravado o endereco que respondeu, por mesa
FONTES_OK = ROOT / "Logs" / "fontes_que_funcionam.json"

# quando cada mesa procurou endereco pela ultima vez (a procura e cara)
_ULTIMA_PROCURA: dict = {}

# a assinatura da ultima pagina HTML lida, por mesa -- e ela que diz se houve
# giro novo numa fonte que nao tem horario nem identificador
_ultimo_head_html: dict = {}


# a mesma coisa, mas em disco: sem isto, reabrir o programa fazia a primeira
# leitura parecer giro novo sempre, e a mesa contava um giro que nao houve
_HEADS_HTML = ROOT / "Logs" / "heads_html.json"
# os identificadores que ja foram dados a cada giro desta pagina, na ordem em
# que ela devolveu na ultima leitura
_ids_html: dict = {}
_seq_html: dict = {}


def _gravar_json(destino: Path, dados: dict) -> None:
    """Grava trocando o arquivo pronto pelo antigo, nunca escrevendo por cima.

    ESCREVER POR CIMA É PERDER TUDO QUANDO DÁ ERRADO.
    -------------------------------------------------
    `write_text` trunca o arquivo antes de escrever. Se o programa for fechado,
    a máquina desligar ou o disco encher no meio, o que fica no lugar é um JSON
    cortado — e `json.loads` falha na próxima leitura.

    Aqui isso não é um arquivo qualquer: é a memória de qual endereço funciona
    em cada mesa. Corrompido, TODAS as mesas voltam a procurar endereço do
    zero, e a procura é cara e lenta. Um fechamento infeliz custaria a
    descoberta inteira.

    Escrevendo ao lado e trocando no fim (`os.replace` é atômico), ou o arquivo
    novo está inteiro, ou o antigo continua lá. Nunca meio.
    """
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    os.replace(str(tmp), str(destino))


def _gravar_head_html(dataset_id: str, hid: str) -> None:
    try:
        d = {}
        if _HEADS_HTML.is_file():
            d = json.loads(_HEADS_HTML.read_text(encoding="utf-8")) or {}
        if d.get(dataset_id) == hid:
            return
        d[dataset_id] = hid
        _gravar_json(_HEADS_HTML, d)
    except Exception as _e:
        engolido("fluxo_captura/_gravar_head_html", _e)


def _head_html_salvo(dataset_id: str):
    try:
        import json as _j
        if _HEADS_HTML.is_file():
            return (_j.loads(_HEADS_HTML.read_text(encoding="utf-8"))
                    or {}).get(dataset_id)
    except Exception as _e:
        engolido("fluxo_captura/_head_html_salvo", _e)
    return None


def _identidade_html(dataset_id: str, linhas: List[dict]) -> tuple:
    """A digital da página e um identificador estável para cada giro dela.

    A PÁGINA NÃO TEM HORÁRIO NEM ID — E O RESTO DO SOFTWARE PRECISA DE UM.
    ---------------------------------------------------------------------
    Sem identificador por giro, a marca de acerto do histórico (`✓`/`✗`) nunca
    aparecia nesta fonte: `_marca_do_giro` procura pela chave do giro, a chave
    vinha de `settled`, e aqui `settled` é `None` para todos. Todos caíam na
    mesma chave vazia, então nenhum casava.

    Dar `posição` como identidade não resolve: o giro que hoje é o primeiro
    amanhã é o segundo, e perderia a marca junto com a posição.

    O que dá para fazer com honestidade é seguir a SEQUÊNCIA. A página devolve
    do mais novo para o mais velho; entre duas leituras, o que mudou foi
    entrar giro na frente. Achando quantos entraram, os que já existiam
    mantêm o identificador que receberam antes, e só os novos ganham um
    número novo. Nada é inventado: a única suposição é a de que o histórico
    anda para frente, que é o que histórico faz.
    """
    import hashlib as _hl
    vals = [str(r.get("n")) for r in linhas]
    hid = "html:" + _hl.sha1("|".join(vals).encode("utf-8")).hexdigest()[:16]

    antes_vals = _ids_html.get(dataset_id, {}).get("vals") or []
    antes_ids = _ids_html.get(dataset_id, {}).get("ids") or []
    # quantos entraram na frente: o menor deslocamento que faz o resto casar
    novos = len(vals)
    for d in range(0, min(len(vals), len(antes_vals)) + 1):
        if vals[d:d + len(antes_vals)] == antes_vals[:len(vals) - d]:
            novos = d
            break
    seq = int(_seq_html.get(dataset_id, 0))
    ids = []
    for i in range(novos):
        seq += 1
        ids.append(f"{hid[:11]}:{dataset_id}:{seq}")
    _seq_html[dataset_id] = seq
    ids.extend(antes_ids[:len(vals) - novos])
    while len(ids) < len(vals):
        # primeira leitura (ou histórico que encolheu): completa o que falta
        seq += 1
        ids.append(f"{hid[:11]}:{dataset_id}:{seq}")
    _seq_html[dataset_id] = seq
    _ids_html[dataset_id] = {"vals": vals, "ids": ids}
    return hid, ids


def _lembrar_fonte(dataset_id: str, url: str) -> None:
    """Grava o endereco que respondeu, para nao procurar de novo."""
    try:
        d = {}
        if FONTES_OK.is_file():
            d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        if d.get(dataset_id) == url:
            return
        d[dataset_id] = url
        # troca atômica: este arquivo é a memória de qual endereço funciona em
        # cada mesa, e corrompê-lo custa a descoberta de todas elas
        _gravar_json(FONTES_OK, d)
    except Exception as _e:
        engolido("fluxo_captura/_lembrar_fonte", _e)


def fonte_lembrada(dataset_id: str):
    try:
        import json as _j
        if FONTES_OK.is_file():
            return (_j.loads(FONTES_OK.read_text(encoding="utf-8"))
                    or {}).get(dataset_id)
    except Exception as _e:
        engolido("fluxo_captura/fonte_lembrada", _e)
    return None


# OS LINKS QUE ELE MANDOU, COMO FONTE DE CAPTURA -- NAO SO PARA CONTAR GENTE.
#
# Ele cobrou, e com razao: "coloque todos os links que te passei como base para
# captura, api, eu ja te pedi milhares de vezes, e voce diz que faz e nao faz".
#
# Ele tinha dito, quando mandou os cinco enderecos: "para saber quantas pessoas
# tem E PEGAR OS ULTIMOS 200 RESULTADOS para analise rapida". Eu fiz a primeira
# metade -- o contador de pessoas em publico_mesa.py -- e deixei a segunda de
# fora. Os resultados estavam la, sendo lidos por `extrair_resultados()`, e
# nunca chegavam ao fluxo de captura.
#
# Agora sao terceira fonte de cada mesa. Ficam DEPOIS das duas de API porque
# sao pagina HTML (mais fragil, e ja levou 403 de Cloudflare), mas existir como
# reserva e melhor que a mesa morrer com tres fontes disponiveis.
FONTES_HTML = {
    "lightning": "https://gamblingcounting.com/lightning-roulette",
    "mega_fire": "https://gamblingcounting.com/roulette",
    "crazy_time": "https://gamblingcounting.com/crazy-time",
    "crazy_time_a": "https://gamblingcounting.com/crazy-time-a",
}


def capturar_html(dataset_id: str) -> List[dict]:
    """Os ultimos resultados pela pagina do gamblingcounting.

    Devolve no mesmo formato das outras fontes, para o resto do software nao
    precisar saber de onde veio.
    """
    url = FONTES_HTML.get(dataset_id)
    if not url:
        return []
    try:
        from fonte_gamblingcounting import coletar
        d = coletar(dataset_id) or {}
    except Exception:
        return []
    if d.get("erro"):
        return []
    saida = []
    for v in (d.get("resultados") or [])[:200]:
        v = str(v).strip()
        if not v:
            continue
        if str(dataset_id).startswith("crazy_time"):
            saida.append({"n": v, "sec": v, "settled": None, "tags": []})
        else:
            try:
                n = int(v)
            except ValueError:
                continue
            if 0 <= n <= 36:
                saida.append({"n": n, "settled": None, "tags": []})
    return saida


def enderecos_para(dataset_id: str):
    """Todos os candidatos desta mesa, com o que ja funcionou na frente."""
    lista = []
    lembrado = fonte_lembrada(dataset_id)
    if lembrado:
        lista.append(lembrado)
    principal = API_BY_GAME.get(dataset_id)
    if principal and principal not in lista:
        lista.append(principal)
    for u in API_ALTERNATIVAS.get(dataset_id, []):
        if u not in lista:
            lista.append(u)
    return lista

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.casino.org",
    "Referer": "https://www.casino.org/casinoscores/pt-br/",
}


def buffer_path(dataset_id: str) -> Path:
    return BUF_DIR / f"{dataset_id}.json"


def snap_path(dataset_id: str) -> Path:
    return SNAP_DIR / f"{dataset_id}_last_snap.json"


# Nenhuma rodada ao vivo fecha em menos que isto: as mesas giram a 40-70s e
# 20s e' folgado de proposito, para nao descartar giro legitimo em mesa rapida.
MIN_SEG_RODADA = 20.0

# De quantos em quantos ciclos vale bater nos sites. A fonte principal ja cobre
# o giro a giro; os sites servem para o historico profundo, que nao muda a cada
# 45 segundos.
PUXAR_SITES_A_CADA = 40
_passo_sites: Dict[str, int] = {}


def _seg_entre(a, b) -> Optional[float]:
    from datetime import datetime
    try:
        ta = datetime.fromisoformat(str(a).replace("Z", "+00:00"))
        tb = datetime.fromisoformat(str(b).replace("Z", "+00:00"))
    except Exception:
        return None
    return abs((tb - ta).total_seconds())


def _purge_invalid(events: List[dict], dataset_id: str) -> List[dict]:
    dom = DOMAIN.get(dataset_id, set())
    out = []
    seen = set()
    for e in events:
        _raw = e.get("valor") if e.get("valor") is not None else e.get("n")
        v = "" if _raw is None else str(_raw)
        if v not in dom:
            continue
        settled = canonical_ts(e.get("settled"))
        # GIRO SEM HORÁRIO NÃO ENTRA NA SEQUÊNCIA.
        #
        # Todo o estudo mede ORDEM — transição, janela, "o que vem depois".
        # Um número sem carimbo de tempo não tem lugar na fila: a ordenação o
        # joga numa posição indefinida e ele embaralha justamente aquilo que
        # se está medindo. Aumentar o histórico assim não é ganhar dado, é
        # perder o que já se tinha.
        #
        # Havia dois estragos ao mesmo tempo. Além da posição indefinida, o
        # identificador desses eventos saía como `jogo|valor|i0` para todos —
        # dois giros diferentes do mesmo número viravam um só no dedupe.
        #
        # Hoje isso é inofensivo porque as fontes de HTML não devolvem nada.
        # No dia em que voltarem a funcionar (elas raspam número sem horário),
        # entrariam corrompendo. Fechado antes.
        if not settled:
            continue
        eid = e.get("event_id") or event_key(dataset_id, v, settled)
        if eid in seen:
            continue
        seen.add(eid)
        e = dict(e)
        e["valor"] = v
        e["settled"] = settled
        e["event_id"] = eid
        # A COMPARAÇÃO ERA `!= "crazy_time"`, E ISSO QUEBRAVA A CRAZY TIME A.
        #
        # Os setores numéricos dela ("1", "2", "5", "10") voltavam a virar
        # inteiro aqui, enquanto "CoinFlip" e "Pachinko" continuavam texto. O
        # histórico saía misturado -- [5, "CoinFlip", 2, "Pachinko"] -- e do
        # outro lado `ia_modulos` compara com `CT_SETORES`, que é tudo texto.
        # Resultado: metade dos giros da mesa era invisível para as
        # inteligências, sem erro nenhum aparecer.
        #
        # É a mesma raiz do `DOMAIN` sem `crazy_time_a`: o nome da mesa nova
        # não é `crazy_time`, é `crazy_time_a`. Toda comparação exata com o
        # nome antigo esquece a mesa nova. Por isso agora é prefixo.
        if not dataset_id.startswith("crazy_time") and v.isdigit():
            e["n"] = int(v)
        else:
            e["n"] = v
        out.append(e)

    # DUPLICATA COM CARIMBO DIFERENTE. O event_id e' jogo|valor|settled, entao
    # o MESMO giro relatado duas vezes com o carimbo deslocado em 1 segundo
    # entra como giro novo -- sempre com o valor repetido, porque e' o mesmo
    # giro. Infla exatamente a medida de repeticao. Nos 691 giros de Crazy Time
    # do operador, 21 duplicatas assim levaram a repeticao de 27,5% a 29,7% e
    # um p=0,089 (nada) virou p=0,0010 (o "achado mais forte do estudo").
    out.sort(key=lambda x: sort_key_ts(x.get("settled")))
    limpo = []
    for e in out:
        if limpo and str(e.get("valor")) == str(limpo[-1].get("valor")):
            dt = _seg_entre(limpo[-1].get("settled"), e.get("settled"))
            if dt is not None and dt < MIN_SEG_RODADA:
                continue
        limpo.append(e)
    limpo.sort(key=lambda x: sort_key_ts(x.get("settled")), reverse=True)
    return limpo



def _extract_number(obj):
    if obj is None:
        return None
    if isinstance(obj, (int, float)):
        return int(obj)
    if isinstance(obj, str) and obj.strip().lstrip("-").isdigit():
        return int(obj.strip())
    if isinstance(obj, dict):
        for k in ("number", "n", "value", "result", "outcome"):
            if k in obj:
                v = _extract_number(obj[k])
                if v is not None:
                    return v
    return None

def _anunciados_no_giro(obj, fundo: int = 0, achados=None) -> List[dict]:
    """Procura, em qualquer lugar da resposta, a lista de números anunciados.

    POR QUE UMA BUSCA EM VEZ DE UM CAMPO
    ────────────────────────────────────
    O código antigo lia `res["fireNumbers"]` -- e SÓ quando `superBoost` era
    verdadeiro. Nos dados reais dele isso deu 7 giros com marca em 132: nos
    outros 125 a Mega Fire anunciou os números e o software descartou.

    É o mesmo defeito que quase matou a v103 no Lightning: guardar o anúncio só
    quando ele pagou. Ali eram 10 registros de umas 600 premiações; aqui são 7
    de 132. E a consequência é a mesma -- `[Multiplicador] mega_fire: sem
    palpite (254 rodadas lidas)`, que foi exatamente o que ele viu na tela.

    Como daqui não dá para inspecionar a resposta da API, não adianta eu
    adivinhar mais um nome de campo. Esta função procura o FORMATO: uma lista
    de itens que tenham um número de roleta (0..36) e, quando houver, um
    multiplicador. Funciona seja qual for o nome que o provedor use, e sobrevive
    a ele renomear amanhã.
    """
    if achados is None:
        achados = []
    if fundo > 6 or len(achados) >= 40:
        return achados
    if isinstance(obj, dict):
        for v in obj.values():
            _anunciados_no_giro(v, fundo + 1, achados)
    elif isinstance(obj, list):
        # uma lista de dicts com número de roleta dentro é candidata a anúncio
        lote = []
        for it in obj[:40]:
            if not isinstance(it, dict):
                lote = []
                break
            num = None
            for c in ("number", "n", "value", "num", "slot", "position"):
                if c in it:
                    try:
                        num = int(it[c])
                    except (TypeError, ValueError):
                        num = None
                    break
            if num is None or not (0 <= num <= 36):
                lote = []
                break
            mx = None
            for c in ("roundedMultiplier", "multiplier", "x", "payout",
                      "mult", "multiplicator"):
                if it.get(c):
                    try:
                        mx = int(it[c])
                    except (TypeError, ValueError):
                        mx = None
                    break
            lote.append({"n": num, "x": mx})
        # UM HISTORICO TAMBEM E LISTA DE NUMEROS DE ROLETA.
        #
        # Sem este crivo, uma lista de giros passados aninhada na resposta
        # entraria como se fosse o anuncio -- e o software passaria a prever
        # multiplicador em cima de resultados velhos, calado. O que separa os
        # dois e o MULTIPLICADOR: anuncio de lucky/fire carrega valor, lista de
        # historico nao. Exigir pelo menos um, e a lista ser curta como um
        # anuncio de verdade.
        if lote and len(lote) <= 12 and any(it["x"] for it in lote):
            achados.extend(lote)
        else:
            for it in obj[:40]:
                _anunciados_no_giro(it, fundo + 1, achados)
    return achados


def parse_items_roulette(items: List[dict]) -> List[dict]:
    """Aceita estruturas aninhadas antigas e planas."""
    # expande se item contém lista interna de resultados
    expanded = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        d = it.get("data") if isinstance(it.get("data"), dict) else it
        nested_lists = []
        for k in ("results", "gameResults", "events", "items"):
            if isinstance(d.get(k), list):
                nested_lists.append(d[k])
            if isinstance(it.get(k), list):
                nested_lists.append(it[k])
        if nested_lists:
            for lst in nested_lists:
                expanded.extend(lst)
        else:
            expanded.append(it)
    items = expanded
    rows = []
    for it in items:
        try:
            d = it.get("data") if isinstance(it, dict) else None
            if not isinstance(d, dict):
                d = it if isinstance(it, dict) else {}
            res = d.get("result") if isinstance(d.get("result"), dict) else d
            out = res.get("outcome") if isinstance(res.get("outcome"), dict) else res
            n = None
            for cand in (out, res, d, it):
                n = _extract_number(cand)
                if n is not None:
                    break
            if n is None:
                continue
            n = int(n)
            if n < 0 or n > 36:
                continue
            settled = canonical_ts(
                d.get("settledAt") or d.get("settled") or it.get("settledAt") or it.get("settled")
            )
            tags = []
            # GUARDAR A RODADA DE MULTIPLICADORES INTEIRA, não só quando bate.
            #
            # O Lightning sorteia de 1 a 5 lucky numbers em TODA rodada, cada um
            # com seu multiplicador. O código antigo só registrava quando o lucky
            # calhava de ser o número que saiu: em 205 giros reais isso deixou 10
            # registros, de umas 600 premiações que de fato aconteceram.
            #
            # Qualquer estudo sobre multiplicador feito em cima disso enxergava
            # 2% do fenômeno — e é por isso que a métrica antiga de "o que vai
            # vir multiplicado" acertava de vez em quando e errava quase sempre.
            #
            # `x` continua sendo só o acerto (nada que já dependia dele muda).
            # `lucky` passa a carregar a rodada completa: quais números foram
            # sorteados e com que multiplicador, tenham saído ou não.
            lucky = res.get("luckyNumbersList") or d.get("luckyNumbersList") or []
            _sorteados = []
            for ln in lucky:
                try:
                    num = int(ln.get("number", ln)) if isinstance(ln, dict) else int(ln)
                    mult = None
                    if isinstance(ln, dict):
                        mult = ln.get("roundedMultiplier") or ln.get("multiplier")
                    if mult:
                        _sorteados.append({"n": num, "x": int(mult)})
                        if num == n:
                            tags.append({"x": mult})
                except Exception as _e:
                    engolido("fluxo_captura/parse_items_roulette", _e)
            if _sorteados:
                tags.append({"lucky": _sorteados})
            # MEGA FIRE BLAZE — guardar o que veio dentro, não só o sim/não.
            #
            # Mesmo erro que os lucky numbers do Lightning: o código antigo
            # registrava `{"fire": True}` e descartava o conteúdo. Se a API
            # informa quais números pegaram fogo e com que multiplicador, isso
            # estava sendo jogado fora, e nenhum estudo sobre multiplicador
            # nesta mesa poderia funcionar.
            #
            # Como não dá para inspecionar a resposta ao vivo daqui, o payload
            # é guardado inteiro quando é estruturado (dict ou lista) — o que
            # não se sabe ler hoje fica registrado para ser lido depois. Perder
            # dado é irreversível; guardar demais custa alguns bytes.
            _boost = res.get("superBoost")
            if _boost is None:
                _boost = d.get("superBoost")

            # O ANUNCIO VEM TODO GIRO, TENHA PAGO OU NAO.
            #
            # Antes, tudo isto vivia dentro do `if _boost:`, entao o canal
            # anunciado da Mega Fire so era guardado nos giros em que o super
            # boost disparou -- 7 em 132 nos dados dele. As 7 IAs de
            # multiplicador liam 254 rodadas e nao tinham o que dizer.
            # UM ANUNCIO POR GIRO, NAO DOIS.
            #
            # Havia dois caminhos que acrescentavam `fire_nums`: a busca por
            # formato (quando o giro nao trouxe sorteados) e a leitura do campo
            # `fireNumbers` (quando o super boost disparou). Nada impedia os
            # dois de acontecerem no mesmo giro -- e ai a rodada saia com DUAS
            # tags `fire_nums`.
            #
            # `extrair()` concatena as listas de todas as tags, entao a rodada
            # ficava com o dobro de premiados. Justamente nos giros de super
            # boost, que sao os mais informativos. Todo agente que conta
            # premiacao por rodada media errado exatamente onde mais importa.
            #
            # Agora as duas fontes alimentam UMA lista, sem repetir numero.
            _anuncio: List[dict] = []
            _ja_anunciado = set()

            def _anunciar(itens):
                for _it in (itens or []):
                    if not isinstance(_it, dict):
                        continue
                    _k = str(_it.get("n"))
                    if _k in _ja_anunciado:
                        continue
                    _ja_anunciado.add(_k)
                    _anuncio.append(_it)

            if _boost:
                tags.append({"fire": True})
                if isinstance(_boost, (dict, list)):
                    tags.append({"fire_bruto": _boost})
                _fn = res.get("fireNumbers") or d.get("fireNumbers") or []
                _lista = []
                for fb in (_fn if isinstance(_fn, list) else []):
                    try:
                        if isinstance(fb, dict):
                            _num = int(fb.get("number", fb.get("n")))
                            _mx = fb.get("roundedMultiplier") or fb.get("multiplier")
                            _lista.append({"n": _num,
                                           "x": int(_mx) if _mx else None})
                        else:
                            _lista.append({"n": int(fb), "x": None})
                    except (TypeError, ValueError):
                        pass
                # o campo declarado vem primeiro: ele traz o multiplicador
                _anunciar(_lista)

            if not _sorteados:
                _anunciar(_anunciados_no_giro(res) or _anunciados_no_giro(d))

            if _anuncio:
                tags.append({"fire_nums": _anuncio})
            rows.append({"n": n, "settled": settled, "tags": tags})
        except Exception as _e:
            engolido("fluxo_captura/parse_items_roulette", _e)
            continue
    return rows


def parse_items_ct(items: List[dict]) -> List[dict]:
    """
    API casino.org Crazy Time devolve:
      data.result.outcome.wheelResult.wheelSector  → "1"|"2"|"5"|"10"|"CoinFlip"|...
    Fallbacks para formatos antigos / outras fontes.
    """
    rows = []
    aliases = {
        "coinflip": "CoinFlip", "coin flip": "CoinFlip", "coin_flip": "CoinFlip",
        "cashhunt": "CashHunt", "cash hunt": "CashHunt", "cash_hunt": "CashHunt",
        "pachinko": "Pachinko",
        "crazybonus": "CrazyBonus", "crazy bonus": "CrazyBonus", "crazytime": "CrazyBonus",
        "crazy time": "CrazyBonus", "bonus": "CrazyBonus",
        "1": "1", "2": "2", "5": "5", "10": "10",
    }
    for it in items:
        try:
            d = it.get("data") or it
            res = d.get("result") or d
            out = res.get("outcome") or res
            sec = None
            # formato atual Evolution / casino.org
            wr = out.get("wheelResult") if isinstance(out, dict) else None
            if isinstance(wr, dict):
                sec = wr.get("wheelSector") or wr.get("sector") or wr.get("result")
            if sec is None and isinstance(out, dict):
                top = out.get("topSlot") or {}
                # só usa topSlot se não houver wheelResult
                sec = out.get("result") or out.get("sector") or out.get("number") or out.get("sec")
            if sec is None:
                sec = d.get("sector") or d.get("number") or d.get("sec") or d.get("result")
            if sec is None:
                continue
            s = str(sec).strip()
            low = s.lower().replace("_", " ")
            s = aliases.get(low, aliases.get(low.replace(" ", ""), s))
            # normaliza espaços CamelCase já corretos
            if s not in DOMAIN["crazy_time"]:
                # tenta sem espaços
                s2 = s.replace(" ", "")
                for k, v in aliases.items():
                    if k.replace(" ", "") == s2.lower():
                        s = v
                        break
            if s not in DOMAIN["crazy_time"]:
                continue
            settled = canonical_ts(d.get("settledAt") or d.get("settled") or it.get("settledAt"))
            tags = []
            # O TOP SLOT é meia informação sem o símbolo.
            #
            # Antes só o multiplicador era guardado, e o símbolo sorteado ia
            # fora. Mas é o cruzamento dos dois que conta a história do giro:
            # o top slot sorteia um símbolo com um multiplicador, e ele só
            # paga se a roda parar no MESMO símbolo — senão é "Miss". Sem
            # guardar o símbolo não dá para mostrar isso nem para estudar
            # quantas vezes o top slot bate.
            try:
                if isinstance(out, dict):
                    top = out.get("topSlot") or {}
                    mult = top.get("multiplier") or out.get("maxMultiplier")
                    simbolo = None
                    for c in ("sector", "result", "wheelSector", "symbol",
                              "slotResult", "value"):
                        v = top.get(c) if isinstance(top, dict) else None
                        if v:
                            simbolo = str(v).strip()
                            break
                    if simbolo:
                        low = simbolo.lower().replace("_", " ")
                        simbolo = aliases.get(
                            low, aliases.get(low.replace(" ", ""), simbolo))
                    if mult or simbolo:
                        tags.append({"top": {"simbolo": simbolo, "x": mult}})
                    if mult:
                        tags.append({"x": mult})
            except Exception as _e:
                engolido("fluxo_captura/parse_items_ct", _e)
            rows.append({"n": s, "sec": s, "settled": settled, "tags": tags})
        except Exception as _e:
            engolido("fluxo_captura/parse_items_ct", _e)
            continue
    return rows


def capturar(
    dataset_id: str,
    *,
    page_size: int = 50,
    max_pages: int = 2,
    duration: int = 90,
) -> Dict[str, Any]:
    """
    Retorna:
      rows: eventos normalizados (recente→antigo)
      novo_head: True se o evento mais recente é diferente do último processado
      head_id: event_id do topo
      err: mensagem ou None
      mults: lista de multiplicadores (roleta)
    """
    fontes_extra: List[str] = []
    candidatos = enderecos_para(dataset_id)

    # A FONTE QUE JA FOI DESCOBERTA VEM NA FRENTE.
    #
    # `descobridor_endereco` procura o endereco da mesa gerando as grafias a
    # partir do nome dela, em vez de eu chutar uma lista a mao -- foi assim
    # que o Crazy Time A ficou semanas sem abrir. O que ele achou uma vez fica
    # gravado, entao aqui e so consultar.
    try:
        from descobridor_endereco import lembradas as _lembradas_desc
        _ja = _lembradas_desc().get(str(dataset_id))
        if _ja:
            candidatos = [_ja] + [u for u in candidatos if u != _ja]
    except Exception as _e:
        engolido("fluxo_captura/capturar", _e)

    if not candidatos:
        return {"rows": [], "novo_head": False, "head_id": None, "err": "dataset desconhecido", "mults": []}

    # AS ALTERNATIVAS EXISTIAM E NUNCA ERAM TENTADAS.
    #
    # `API_ALTERNATIVAS` estava escrita no topo do arquivo desde que o Crazy
    # Time A entrou, com tres grafias possiveis do endereco -- e este trecho
    # usava so o principal. Se ele nao respondesse, a mesa simplesmente nao
    # abria, sem nunca experimentar as outras. Era o caso do Crazy Time A.
    #
    # Agora percorre os candidatos e GRAVA o que funcionar, para a procura
    # acontecer uma vez so.
    items, err = [], None
    for _url in candidatos:
        items, err = fetch_paginas(
            _url, HEADERS, page_size=page_size, max_pages=max_pages,
            duration=duration)
        if items:
            _lembrar_fonte(dataset_id, _url)
            break
    if err and not items:
        # ULTIMO RECURSO ANTES DE DESISTIR: PROCURAR O ENDERECO.
        #
        # Se nenhum endereco conhecido respondeu, o provedor pode ter mudado o
        # nome da mesa na URL -- foi o que manteve o Crazy Time A fechado por
        # semanas. Em vez de eu chutar mais uma grafia a cada versao, o
        # descobridor gera as grafias a partir do nome e testa todas, aceitando
        # so a que devolver giros reconheciveis. Acha uma vez e grava.
        #
        # Roda no maximo uma vez a cada dez minutos por mesa: a procura custa
        # dezenas de requisicoes e nao pode virar tempestade em cima do
        # provedor a cada ciclo de captura.
        try:
            import time as _t
            from descobridor_endereco import descobrir as _descobrir
            _ultima = _ULTIMA_PROCURA.get(dataset_id, 0.0)
            if _t.time() - _ultima > 600:
                _ULTIMA_PROCURA[dataset_id] = _t.time()
                _novo = _descobrir(str(dataset_id))
                if _novo:
                    items, err = fetch_paginas(
                        _novo, HEADERS, page_size=page_size,
                        max_pages=max_pages, duration=duration)
                    if items:
                        _lembrar_fonte(dataset_id, _novo)
        except Exception as _e:
            engolido("fluxo_captura/capturar", _e)

    if err and not items:
        # TERCEIRA FONTE: a pagina que ele mandou. So chega aqui quando as duas
        # APIs falharam -- e antes disso a mesa simplesmente morria.
        _html = capturar_html(dataset_id)
        if _html:
            # O MESMO "5" VIRAVA GIRO NOVO A CADA CONSULTA.
            #
            # A pagina do gamblingcounting nao traz horario nem identificador.
            # Este trecho declarava `novo_head=True` sempre e `head_id=None`,
            # e a tela, sem horario para usar de chave, inventava `5#s1`,
            # `5#s2`, `5#s3`... com um contador que so cresce. Resultado: a
            # mesma leitura estatica era contada como giro novo em toda volta,
            # e o Crazy Time ficava repetindo o mesmo simbolo -- que foi
            # exatamente o que ele viu.
            #
            # A pagina nao tem identificador, mas TEM conteudo: a sequencia dos
            # ultimos resultados. Se ela nao mudou, nao houve giro. O head_id
            # passa a ser a impressao digital dessa sequencia.
            # DOZE VALORES NAO SAO IMPRESSAO DIGITAL NO CRAZY TIME.
            #
            # A assinatura usava so `_html[:12]`. Numa roleta isso e' quase
            # unico; no Crazy Time, nao: sao 8 simbolos, e o "1" sozinho ocupa
            # 21 das 54 casas. Doze posicoes com esse alfabeto repetem sozinhas
            # com frequencia -- e quando repetem, uma pagina NOVA tem a mesma
            # assinatura da anterior e o giro e' descartado como se fosse
            # releitura.
            #
            # Agora a assinatura e' a pagina inteira. Nao custa nada (e um
            # sha1 de duzentos valores) e para de perder giro.
            _hid, _ids = _identidade_html(dataset_id, _html)
            for _r, _eid in zip(_html, _ids):
                _r["event_id"] = _eid
            # a memoria era so de processo: reabrindo o programa, a MESMA
            # pagina voltava a valer como giro novo e a mesa contava um giro
            # que nao aconteceu. Agora a digital anterior tambem vem do disco.
            _antes = _ultimo_head_html.get(dataset_id)
            if _antes is None:
                _antes = _head_html_salvo(dataset_id)
            _ultimo_head_html[dataset_id] = _hid
            _gravar_head_html(dataset_id, _hid)
            return {"rows": _html, "novo_head": _hid != _antes,
                    "head_id": _hid, "err": None, "mults": [],
                    "fonte": "gamblingcounting"}
        # A API caiu -- mas o historico ja coletado esta salvo em disco.
        # Devolver rows=[] fazia a tela apagar e o motor parar de analisar por
        # causa de um 500 passageiro, jogando fora centenas de giros ja ali.
        try:
            salvos = _purge_invalid(
                (load(buffer_path(dataset_id)).get("events") or []), dataset_id)
        except Exception:
            salvos = []
        if not salvos:
            return {"rows": [], "novo_head": False, "head_id": None,
                    "err": err, "mults": []}
        rows_off, mults_off = [], []
        for e in salvos:
            rows_off.append({"n": e.get("n"), "sec": e.get("n"),
                             "settled": e.get("settled"),
                             "tags": e.get("tags") or [],
                             "event_id": e.get("event_id")})
            for t in e.get("tags") or []:
                if "x" in t:
                    mults_off.append({"n": e.get("n"), "x": t["x"]})
        return {"rows": rows_off, "novo_head": False,
                "head_id": rows_off[0]["event_id"] if rows_off else None,
                "err": err, "mults": mults_off, "offline": True}

    # CRAZY TIME A CAIA NO PARSER DE ROLETA.
    #
    # A comparacao era `== "crazy_time"`, entao a segunda mesa do mesmo jogo ia
    # para `parse_items_roulette` e seus simbolos (CoinFlip, Pachinko...) eram
    # lidos como numeros de roleta. Mesmo com a API respondendo, os dados
    # sairiam errados -- e sairiam calados, que e pior.
    if str(dataset_id).startswith("crazy_time"):
        brutos = parse_items_ct(items)
    else:
        brutos = parse_items_roulette(items)

    # merge no buffer (dedupe + domínio + lock)
    bp = buffer_path(dataset_id)
    # 400 dava ~5h de mesa e truncava coleta longa: quem deixasse rodando o
    # dia inteiro perdia o começo. 20000 cobre semanas e o arquivo continua
    # pequeno (~2 MB por mesa).
    # HISTÓRICO PROFUNDO DOS SITES.
    #
    # A API principal devolve as últimas dezenas de rodadas; o casinotrackpot
    # devolve até mil das últimas 72 horas, com os lucky numbers e o
    # multiplicador de cada uma. Puxar de vez em quando enche o buffer com
    # semanas do que a coleta ao vivo levaria semanas para juntar.
    #
    # É de vez em quando de propósito: a fonte principal já cobre o giro a giro,
    # e bater na outra a cada 45 segundos seria peso sem ganho. O dedupe do
    # merge cuida da sobreposição, e giro sem horário nem chega aqui.
    try:
        _n = _passo_sites.get(dataset_id, 0)
        _passo_sites[dataset_id] = _n + 1
        if _n % PUXAR_SITES_A_CADA == 0:
            from coletor_sites import buscar_sequencia
            _extra, _av = buscar_sequencia(dataset_id)
            if _extra:
                brutos = list(brutos) + _extra
                fontes_extra.append(f"sites:{len(_extra)}")
            if _av:
                fontes_extra.append(f"sites_aviso:{_av}")
    except Exception as _e:
        fontes_extra.append(f"sites_erro:{type(_e).__name__}")

    merged = merge(bp, dataset_id, brutos, max_keep=MAX_GIROS_BUFFER)
    events = _purge_invalid(merged.get("events") or [], dataset_id)

    # regrava limpo se houve purge
    if events != (merged.get("events") or []):
        data = load(bp)
        data["events"] = events
        data["dataset_id"] = dataset_id
        try:
            from hist_buffer import _acquire, _release, _atomic_write
            if _acquire(bp):
                try:
                    _atomic_write(bp, data)
                finally:
                    _release(bp)
        except Exception as _e:
            engolido("fluxo_captura/capturar", _e)

    rows = []
    mults = []
    for e in events:
        row = {
            "n": e.get("n"),
            "sec": e.get("n"),
            "settled": e.get("settled"),
            "tags": e.get("tags") or [],
            "event_id": e.get("event_id"),
        }
        rows.append(row)
        # O MESMO PREMIO ENTRAVA DUAS VEZES NO MESMO GIRO.
        #
        # Um giro premiado costuma trazer as duas coisas: a tag solta
        # `{"x": 500}` e a lista `{"lucky": [{"n": 20, "x": 500}]}`. Sao duas
        # descricoes do MESMO sorteio, e as duas eram acrescentadas.
        #
        # Quem consome `mults` soma o `x` por numero (`mult_hits[n] += x`).
        # Contado duas vezes, o numero premiado sai com o dobro do peso, e o
        # dobro nao veio de evidencia nenhuma -- veio de a resposta descrever a
        # mesma coisa em dois lugares. O `visto` abaixo conta uma vez so.
        _visto = set()

        def _por(n, x):
            try:
                _x = int(float(x))
            except (TypeError, ValueError):
                return
            # NAO forcar int no numero: no Crazy Time o "n" e' simbolo
            # ("CoinFlip", "Pachinko"), e o int() estourava. O anuncio da mesa
            # inteira caia fora por causa dessa conversao.
            _n = n
            if isinstance(_n, str) and _n.strip().lstrip("-").isdigit():
                _n = int(_n)
            chave = (str(_n), _x)
            if chave in _visto:
                return
            _visto.add(chave)
            mults.append({"n": _n, "x": _x})

        for t in e.get("tags") or []:
            if not isinstance(t, dict):
                continue
            if "x" in t and not isinstance(t.get("x"), (dict, list)):
                _por(e.get("n"), t["x"])
            # `mults` so era montado das tags "x" -- o anuncio inteiro, que
            # vive em `lucky` e `fire_nums`, nao chegava a interface nem as
            # analises. Na Mega Fire isso zerava o canal do multiplicador.
            for _ch in ("lucky", "fire_nums"):
                for _it in (t.get(_ch) or []):
                    if isinstance(_it, dict) and _it.get("x"):
                        _por(_it.get("n"), _it["x"])
            # o top slot do Crazy Time tambem e' anuncio: sorteia simbolo e
            # multiplicador todo giro, pagando ou nao
            _top = t.get("top")
            if isinstance(_top, dict) and _top.get("x"):
                _por(_top.get("simbolo", _top.get("n")), _top["x"])

    head_id = rows[0]["event_id"] if rows else None

    # snapshot idempotência
    sp = snap_path(dataset_id)
    last = {}
    if sp.is_file():
        try:
            last = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            last = {}
    last_head = last.get("head_id")
    novo_head = bool(head_id and head_id != last_head)

    try:
        from fontes_externas import capturar_multi_fonte
        # Uma única agregação: bases_estudo + tracksino + HTML.
        # Sempre mescla extra["rows"] (antes só fontes_ok era anotado e o fetch
        # era descartado). bases_estudo já entra dentro de capturar_multi_fonte.
        extra = capturar_multi_fonte(dataset_id, max_total=120)
        fontes_extra.extend(extra.get("fontes_ok") or [])
        if extra.get("erros"):
            fontes_extra.append("avisos:" + ";".join(extra["erros"][:2]))
        # chave inclui "origem": settled sintético pode colidir por acaso entre
        # arquivos diferentes de bases_estudo (mesmo relógio fabricado) — sem
        # origem na chave, dois eventos reais distintos seriam tratados como 1.
        seen = {(str(r.get("n")), str(r.get("settled")), str(r.get("origem") or "")) for r in rows}
        dom_alvo = DOMAIN.get(dataset_id)
        anexados = 0
        descartados_dominio = 0
        for er in (extra.get("rows") or []):
            # fetch_html_numeros() (fontes_externas.py) foi escrito pra roleta
            # (extrai qualquer número 0-36 da página) e é reaproveitado também
            # nas URLs do Crazy Time — sem esse filtro, número fora do domínio
            # do jogo (lixo de outra parte da página raspada) entrava direto
            # em "rows" e aparecia no histórico da tela como se fosse resultado
            # real.
            n_str = str(er.get("n"))
            if dom_alvo is not None and n_str not in dom_alvo:
                descartados_dominio += 1
                continue
            # Normaliza o TIPO de "n" pra convenção que QualidadeDados.validar()
            # (ia_modulos.py) exige por jogo — mesma regra já usada pra fonte
            # primária em hist_buffer.normalizar_evento(): crazy_time = string
            # ("1" != 1 pra "in CT_SETORES"); roleta = int. fetch_html_numeros()
            # sempre devolve int (foi escrito pra roleta) — sem essa conversão,
            # um valor numérico válido do Crazy Time (1,2,5,10) chegava como
            # int, era marcado "inválido" por QualidadeDados e nunca contava
            # pro histórico (Hist:0 na tela, mesmo com número aparecendo).
            if str(dataset_id).startswith("crazy_time"):
                n_norm = n_str
            else:
                n_norm = int(n_str) if n_str.isdigit() else er.get("n")
            k = (str(er.get("n")), str(er.get("settled")), str(er.get("origem") or ""))
            if k in seen:
                continue
            row = {
                "n": n_norm,
                # "sec" espelha "n" — mesma convenção das rows da fonte primária
                # (ver "sec": e.get("n") acima). crazy_time_combo.py indexa r["sec"]
                # direto (sem .get), então uma row sem essa chave quebra a UI com
                # KeyError assim que passa a ser mesclada aqui.
                "sec": n_norm,
                "settled": er.get("settled"),
                "tags": er.get("tags") or [],
                "event_id": er.get("event_id"),
                "origem": er.get("origem"),
            }
            if er.get("timestamp_sintetico"):
                row["timestamp_sintetico"] = True
            rows.append(row)
            seen.add(k)
            anexados += 1
        if anexados:
            fontes_extra.append(f"anexados:{anexados}")
        if descartados_dominio:
            fontes_extra.append(f"descartados_fora_dominio:{descartados_dominio}")
        if not head_id and rows:
            head_id = rows[0].get("event_id")
            # só é "novo" se difere do último head persistido — reusar dado
            # estático de bases_estudo/tracksino não deve parecer um evento novo
            # a cada ciclo quando a fonte primária está fora do ar.
            novo_head = bool(head_id and head_id != last_head)
        # se a API principal falhou mas há rows de estudo/extra, não bloqueia
        if err and rows:
            err = None
    except Exception as e:
        fontes_extra.append(f"fontes_externas_erro:{e}")

    return {
        "rows": rows,
        "novo_head": novo_head,
        "head_id": head_id,
        "err": err,
        "mults": mults,
        "rejected": merged.get("rejected", 0),
        "fontes_extra": fontes_extra,
    }


def marcar_snapshot_processado(dataset_id: str, head_id: str, extra: dict = None):
    sp = snap_path(dataset_id)
    data = {"head_id": head_id, "extra": extra or {}}
    from time_utils import canonical_ts
    import time as _t
    data["em"] = canonical_ts(_t.time())
    tmp = sp.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(sp))


def estado_ciclo_path(dataset_id: str) -> Path:
    return ROOT / "Logs" / f"{dataset_id}_ciclo_ativo.json"


def salvar_ciclo_ativo(dataset_id: str, escolhas, restantes, janela_hit, ok, err):
    """Persiste ciclo em andamento para restaurar após restart."""
    p = estado_ciclo_path(dataset_id)
    data = {
        "escolhas": list(escolhas or []),
        "restantes": int(restantes or 0),
        "janela_hit": bool(janela_hit),
        "ok": int(ok or 0),
        "err": int(err or 0),
    }
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(str(tmp), str(p))


def carregar_ciclo_ativo(dataset_id: str) -> Optional[dict]:
    p = estado_ciclo_path(dataset_id)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def limpar_ciclo_ativo(dataset_id: str):
    p = estado_ciclo_path(dataset_id)
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass
