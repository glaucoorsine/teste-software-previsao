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
from api_fetch import ORCAMENTO_VOLTA_S
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
    # O NOME DA MESA VEIO DA PAGINA QUE ELE MANDOU.
    #
    #     "coloque https://www.casino.org/casinoscores/pt-br/crazy-time-a/"
    #
    # Eu vinha chutando grafias -- `crazytimea`, `crazytime-a`, `crazytimeA` --
    # e levando 404 em todas. O endereco dele resolve isso sem chute: as
    # paginas do casinoscores e os endpoints do svc-evolution usam O MESMO
    # slug, e a pagina dele diz qual e'. E `crazy-time-a`, com hifens.
    #
    # Nao e adivinhacao minha: e o nome que o proprio provedor usa na URL
    # publica da mesa.
    "crazy_time_a": "https://api-cs.casino.org/svc-evolution-game-events/api/crazy-time-a",
    # A QUINTA MESA. O slug segue o MESMO padrao que funcionou para lightning,
    # mega_fire e crazy_time -- nome da pagina sem hifen -- mas eu nao consigo
    # confirmar contra a API real daqui (o proxy nega casino.org). Por isso ha
    # tres redes de seguranca por tras deste palpite: a descoberta pela pagina,
    # o gerador de grafias, e identidade_ok() recusando qualquer endereco que
    # nao diga "red door". Ver o cabecalho de red_door_combo.py.
    "red_door": "https://api-cs.casino.org/svc-evolution-game-events/api/reddoorroulette",
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
    "red_door": [
        "https://api-cs.casino.org/svc-evolution-game-events/api/red-door-roulette",
        "https://api-cs.casino.org/svc-evolution-game-events/api/reddoor",
        "https://api.trackpotapi.com/api/trackersino/red-door-roulette/history",
        "https://api.trackpotapi.com/api/trackersino/reddoorroulette/history",
    ],
    "crazy_time_a": [
        # o slug da pagina dele, tambem no formato de consulta que algumas
        # rotas do casinoscores usam
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazy-time-a",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimea",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime-a",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimeA",
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
# a descoberta pela pagina baixa o pacote de scripts inteiro: cara, e inutil
# repetir a cada volta. Cinco minutos e frequente o bastante para uma mesa que
# acabou de perder a fonte e raro o bastante para nao comer o orcamento.
_ULTIMA_PAGINA: dict = {}
INTERVALO_PAGINA_S = 300.0

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


def _mults_do_evento(e: dict) -> List[dict]:
    """Todo o anúncio de um giro, uma vez cada.

    UMA REGRA, UM LUGAR.
    --------------------
    Isto existia duplicado: uma vez no caminho online e outra no fallback
    offline. As duas cópias divergiram — a de baixo continuou lendo só as tags
    `x` depois que a de cima aprendeu a ler `lucky`, `fire_nums` e o top slot.
    Resultado: com a API instável, o Caçador ficava mudo exatamente quando a
    captura mais precisava dele.

    Também deduplica: um giro premiado costuma trazer a tag solta `{"x": 500}`
    E a lista `{"lucky": [{"n": 20, "x": 500}]}`. São duas descrições do mesmo
    sorteio, e quem soma `x` por número contava em dobro.
    """
    saida: List[dict] = []
    visto = set()

    def por(n, x):
        try:
            _x = int(float(x))
        except (TypeError, ValueError):
            return
        # sem forçar int no número: no Crazy Time ele é símbolo ("CoinFlip"),
        # e o int() derrubava o anúncio da mesa inteira
        _n = n
        if isinstance(_n, str) and _n.strip().lstrip("-").isdigit():
            _n = int(_n)
        chave = (str(_n), _x)
        if chave in visto:
            return
        visto.add(chave)
        saida.append({"n": _n, "x": _x})

    for t in (e.get("tags") or []):
        if not isinstance(t, dict):
            continue
        if "x" in t and not isinstance(t.get("x"), (dict, list)):
            por(e.get("n"), t["x"])
        for canal in ("lucky", "fire_nums"):
            for it in (t.get(canal) or []):
                if isinstance(it, dict) and it.get("x"):
                    por(it.get("n"), it["x"])
        top = t.get("top")
        if isinstance(top, dict) and top.get("x"):
            por(top.get("simbolo", top.get("n")), top["x"])
    return saida


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


# o head de cada mesa na ultima captura -- para detectar mesas gemeas
_HEAD_POR_MESA: dict = {}


def conferir_mesas_distintas(dataset_id: str, rows: list) -> Optional[str]:
    """Esta mesa esta mostrando o giro de outra? Devolve o aviso, ou None.

    O crivo de identidade no `_lembrar_fonte` impede o caso conhecido, mas nao
    todos: o provedor pode servir a mesma mesa em dois enderecos diferentes, e
    ai os dois passariam. Este confere o SINTOMA em vez da causa -- se duas
    mesas trazem o mesmo giro no mesmo horario, sao a mesma mesa, seja qual for
    o endereco.

    E o sintoma e o que ele viu na tela: "crazy time normal e crazy time A estao
    puxando a mesma api". Duas mesas concordando em tudo nao e consenso, e
    duplicata -- e sem este aviso passa por coincidencia feliz.
    """
    if not rows:
        return None
    r0 = rows[0] or {}
    chave = f"{r0.get('n')}|{r0.get('settled')}"
    if not r0.get("settled"):
        return None
    _HEAD_POR_MESA[dataset_id] = chave
    iguais = [m for m, c in _HEAD_POR_MESA.items()
              if m != dataset_id and c == chave]
    if iguais:
        return (f"MESA_DUPLICADA {dataset_id} traz o MESMO giro de "
                f"{', '.join(iguais)} ({chave}) — sao a mesma mesa, e o "
                f"historico de uma esta aparecendo como o da outra")
    return None


def limpar_fontes_alheias() -> list:
    """Apaga fonte gravada que NAO e da mesa. Roda na abertura.

    ISTO CONSERTA O QUE JA ESTA NA MAQUINA DELE
    ───────────────────────────────────────────
    O arquivo de fontes que ele mandou tem:

        "lightning": ".../api/megaroulette"

    Mega Roulette e outro jogo. O crivo novo impede que isso ACONTECA de novo,
    mas nao desfaz o que ja esta gravado -- e enquanto estiver gravado, o
    Lightning continua lendo a mesa errada, porque a fonte lembrada e sempre o
    primeiro candidato. Correcao que nao limpa o estado antigo nao conserta nada
    na pratica, e isso ele ja me disse uma vez.

    A duplicada (`crazy_time_a` -> crazytime) nem chegou a ser gravada: o crivo
    antigo barrava a gravacao. Por isso ela nao aparece no arquivo dele, e mesmo
    assim as duas mesas mostravam o mesmo historico -- o dado entrava pelo uso.
    """
    apagadas = []
    try:
        if not FONTES_OK.is_file():
            return apagadas
        d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        mudou = False
        for mesa, u in list(d.items()):
            ok, motivo = identidade_ok(mesa, str(u))
            if not ok:
                d.pop(mesa, None)
                apagadas.append(f"{mesa} ({motivo})")
                mudou = True
        if mudou:
            _gravar_json(FONTES_OK, d)
    except Exception as _e:
        engolido("fluxo_captura/limpar_fontes_alheias", _e)
    return apagadas


def limpar_fontes_duplicadas() -> list:
    """Apaga a memoria de fonte quando duas mesas ficaram com o mesmo endereco.

    O crivo novo impede que isso ACONTECA, mas nao desfaz o que ja esta gravado
    na maquina dele -- e la ja esta: a Crazy Time A gravou o endereco da Crazy
    Time comum e vai continuar lendo dela enquanto o arquivo disser isso.
    Correcao que nao limpa o estado antigo nao conserta nada na pratica.

    Roda uma vez, na abertura. A mesa que perdeu a fonte volta a procurar.
    """
    apagadas = []
    try:
        if not FONTES_OK.is_file():
            return apagadas
        d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        por_url: dict = {}
        for mesa, u in list(d.items()):
            por_url.setdefault(str(u), []).append(mesa)
        mudou = False
        for u, mesas in por_url.items():
            if len(mesas) < 2:
                continue
            # QUEM FICA: A MESA COM O NOME MAIS ESPECIFICO NO ENDERECO.
            #
            # Isto era `next(m for m in sorted(mesas) if ...)`, e `sorted` poe
            # `crazy_time` antes de `crazy_time_a`. Como `crazytime` esta DENTRO
            # de `crazytimea`, o Crazy Time comum "batia" no endereco do A e
            # ficava com ele -- e o A, o dono de verdade, era quem perdia o
            # registro e ia procurar. Na abertura seguinte a mesma coisa. Era um
            # dos caminhos para "perde conexao e nao volta mais", e vinha da
            # correcao que eu escrevi para o problema oposto.
            donos = [m for m in mesas
                     if m.replace("_", "") in u.replace("-", "").replace("_", "").lower()]
            fica = max(donos, key=len) if donos else sorted(mesas)[0]
            for m in mesas:
                if m != fica:
                    d.pop(m, None)
                    apagadas.append(m)
                    mudou = True
        if mudou:
            _gravar_json(FONTES_OK, d)
    except Exception as _e:
        engolido("fluxo_captura/limpar_fontes_duplicadas", _e)
    return apagadas


def head_atual_do_buffer(dataset_id: str) -> Optional[str]:
    """O identificador do giro mais recente JA SALVO, sem tocar na rede.

    Serve para a CENTRAL saber, na abertura, se a mesa andou enquanto o software
    esteve fechado. Se andou, a janela que estava aberta nao pode ser julgada:
    ela teria mais chances do que declarou.
    """
    try:
        evs = (load(buffer_path(dataset_id)).get("events") or [])
        if not evs:
            return None
        e0 = evs[0] or {}
        return str(e0.get("event_id")
                   or event_key(dataset_id, e0.get("valor") or e0.get("n"),
                                e0.get("settled")))
    except Exception as _e:
        engolido("fluxo_captura/head_atual_do_buffer", _e)
        return None


def fonte_de_outra_mesa(dataset_id: str, url: str) -> Optional[str]:
    """Alguma OUTRA mesa já usa este endereco? Devolve o nome dela.

    DUAS MESAS LENDO A MESMA API E O PIOR DEFEITO POSSIVEL.
    -------------------------------------------------------
    Ele viu: Crazy Time e Crazy Time A mostrando o MESMO historico, o mesmo
    palpite, os mesmos giros. E foi eu que causei -- a descoberta pela pagina
    valida o endereco perguntando "isto devolve giros que o parser reconhece?",
    e a API do Crazy Time comum devolve giros perfeitamente validos de Crazy
    Time. Passa no crivo com louvor, e a mesa nova passa a ler a mesa velha.

    Ele ja tinha apontado a raiz disso no achado 6: "uma resposta nao vazia,
    mesmo contendo lixo, e memorizada como fonte valida". Eu tratei o "lixo" e
    deixei passar o caso pior, que e dado BOM da mesa ERRADA -- porque esse nao
    parece defeito nenhum: a tela enche, os numeros sao plausiveis, e as duas
    mesas concordam. Concordam porque sao a mesma.

    O crivo que faltava nao e sobre o formato: e sobre IDENTIDADE. Um endereco
    pertence a uma mesa so.
    """
    try:
        d = {}
        if FONTES_OK.is_file():
            d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        for mesa, u in d.items():
            if mesa != dataset_id and str(u) == str(url):
                return str(mesa)
    except Exception as _e:
        engolido("fluxo_captura/fonte_de_outra_mesa", _e)
    return None


# ═══════════════════ DE QUEM É ESTE ENDEREÇO — a regra que faltava
#
# O QUE OS LOGS DELE MOSTRARAM, E QUE É PIOR DO QUE EU TINHA ADMITIDO
# ───────────────────────────────────────────────────────────────────
#     lightning:    VALIDADO .../api/megaroulette      ← mesa ERRADA
#     mega_fire:    VALIDADO .../api/megaroulette      ← a MESMA do lightning
#     crazy_time:   VALIDADO .../api/crazytime
#     crazy_time_a: VALIDADO .../api/crazytime         ← a MESMA do crazy_time
#
# As páginas do casinoscores carregam o MESMO pacote de scripts, e nele estão os
# endereços de TODAS as mesas -- por isso o log diz "17 endereço(s)" igual para
# as quatro. O descobridor validava perguntando "isto devolve giros que meu
# parser reconhece?", e `megaroulette` devolve giros de roleta perfeitamente
# válidos. Passa no crivo com louvor, para qualquer mesa de roleta.
#
# EU JÁ HAVIA ESCRITO QUE O CRIVO QUE FALTAVA ERA DE IDENTIDADE, não de formato.
# Escrevi isso no comentário de `fonte_de_outra_mesa`, e aí está o meu erro: eu
# apliquei o crivo só na hora de GRAVAR a fonte. O log prova a consequência --
# `FONTE_DUPLICADA crazy_time_a tentou usar o endereco de crazy_time` -- e mesmo
# assim as duas mesas mostraram a mesma sequência, porque o laço de captura USA
# os itens e só depois recusa gravar. Recusar a memória sem recusar o dado não
# conserta nada: a tela enche igual, com dado alheio, e ele me disse com todas as
# letras que eu não tinha consertado.
#
# Agora a regra é uma só, neste lugar, e vale nos quatro pontos: descobrir, USAR,
# gravar e limpar o que já está gravado errado.
#
# POR QUE EXIGIR O NOME E NÃO SÓ PROIBIR O DOS OUTROS
# ───────────────────────────────────────────────────
# Proibir o nome das outras mesas não pega o caso do Lightning: `megaroulette`
# não é nenhuma das quatro, é um terceiro jogo. Só a exigência positiva -- "o
# endereço do Lightning tem de dizer lightning" -- fecha esse caso.
IDENTIDADE = {
    "lightning": ("lightningroulette", "lightning"),
    "mega_fire": ("megafireblazeroulette", "megafireblaze", "fireblaze",
                  "megafire"),
    "crazy_time": ("crazytime",),
    "crazy_time_a": ("crazytimea", "crazytime2", "crazytimeatable",
                     "crazytimearoulette"),
    "immersive": ("immersiveroulette", "immersive"),
    "red_door": ("reddoorroulette", "reddoor"),
}

# quando o nome de uma mesa é PREFIXO do da outra, exigir não basta: `crazytime`
# está dentro de `crazytimea`, então o endereço do A satisfaria o comum. É a
# mesma armadilha de prefixo que já derrubou o parser, o DOMAIN e a limpeza de
# fontes duplicadas neste arquivo.
IDENTIDADE_RECUSA = {
    "crazy_time": ("crazytimea", "crazytime2", "crazytimeatable",
                   "crazytimearoulette"),
}


def _normal(url: str) -> str:
    return str(url).replace("-", "").replace("_", "").lower()


def identidade_ok(dataset_id: str, url: str):
    """Este endereço é DESTA mesa? Devolve (ok, motivo)."""
    chave = str(dataset_id)
    exige = IDENTIDADE.get(chave)
    if not exige:
        return True, ""            # mesa que eu não conheço: não julgo
    u = _normal(url)
    for proibido in IDENTIDADE_RECUSA.get(chave, ()):
        if proibido in u:
            return False, (f"o endereco diz '{proibido}', que e de outra mesa")
    if any(t in u for t in exige):
        return True, ""
    return False, (f"o endereco nao diz nenhum de {list(exige)} — nao da para "
                   f"afirmar que e de {chave}")


def _endereco_e_da_mesa(dataset_id: str, url: str) -> bool:
    """O nome DESTA mesa aparece no endereço?

    Serve para desempatar um caso que a minha própria proteção criou. O guarda
    contra duas mesas na mesma API é necessário -- ele resolveu o Crazy Time e o
    Crazy Time A mostrarem histórico idêntico. Mas ele julga por posse: "outra
    mesa já gravou este endereço, então você não pode".

    Isso deixa uma armadilha sem saída. Se o Crazy Time comum tiver gravado, por
    engano de alguma versão anterior, o endereço que na verdade é do Crazy Time A,
    o A é barrado do PRÓPRIO endereço para sempre -- e como nada nunca esquece
    uma fonte, o engano é permanente.

    A saída é olhar a evidência em vez da ordem de chegada: `crazy_time_a` num
    endereço que termina em `crazy-time-a` é o dono legítimo, tenha ele gravado
    antes ou depois. Comparação sem `_` e sem `-` porque as duas grafias
    circulam.
    """
    alvo = str(dataset_id).replace("_", "")
    limpo = str(url).replace("-", "").replace("_", "").lower()
    return alvo in limpo


def _lembrar_fonte(dataset_id: str, url: str) -> None:
    """Grava o endereco que respondeu, para nao procurar de novo."""
    try:
        d = {}
        if FONTES_OK.is_file():
            d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        if d.get(dataset_id) == url:
            return
        _ok_grava, _motivo_grava = identidade_ok(dataset_id, url)
        if not _ok_grava:
            engolido(f"fluxo_captura/ENDERECO_ALHEIO {dataset_id} nao grava "
                     f"{url}: {_motivo_grava}", None)
            return
        _outra = fonte_de_outra_mesa(dataset_id, url)
        if _outra:
            # O DONO LEGITIMO TOMA O ENDERECO DE VOLTA.
            #
            # Antes isto so recusava, e recusar sozinho cria prisao perpetua: se
            # a outra mesa gravou por engano um endereco que e DESTA, esta mesa
            # ficava barrada do proprio endereco para sempre -- e nada esquecia
            # fontes, entao o engano nunca se desfazia. Era um caminho direto
            # para "perde conexao e nao volta mais".
            #
            # Quando o nome desta mesa esta no endereco e o da outra nao, a posse
            # e desta: a outra perde o registro e volta a procurar o dela.
            # E QUEM VENCE E O NOME MAIS ESPECIFICO, NAO SO "quem bate".
            #
            # `crazytime` esta dentro de `crazytimea`. Entao no endereco
            # .../crazy-time-a as DUAS mesas "batem", e uma regra de igualdade
            # simples nunca decide -- foi assim que a primeira versao deste
            # desempate falhou no teste. E a mesma armadilha de prefixo que ja
            # derrubou o parser (`== "crazy_time"` esquecendo a mesa nova) e o
            # DOMAIN. Aqui ela se resolve pelo comprimento: entre dois nomes que
            # aparecem no endereco, o mais longo e o mais especifico, e o dono.
            _meu = _endereco_e_da_mesa(dataset_id, url)
            _dela = _endereco_e_da_mesa(_outra, url)
            if _meu and (not _dela or len(str(dataset_id)) > len(str(_outra))):
                d.pop(_outra, None)
                _FALHAS_FONTE.pop(_outra, None)
                engolido(f"fluxo_captura/FONTE_DEVOLVIDA {url} e de "
                         f"{dataset_id} (o nome esta no endereco); {_outra} "
                         f"perdeu o registro e vai procurar o proprio", None)
            else:
                # nao grava, e deixa rastro: e mais honesto a mesa ficar sem
                # fonte do que ler a fonte de outra e mostrar historico alheio
                engolido(f"fluxo_captura/FONTE_DUPLICADA {dataset_id} tentou "
                         f"usar o endereco de {_outra}: {url}", None)
                return
        d[dataset_id] = url
        # troca atômica: este arquivo é a memória de qual endereço funciona em
        # cada mesa, e corrompê-lo custa a descoberta de todas elas
        _gravar_json(FONTES_OK, d)
    except Exception as _e:
        engolido("fluxo_captura/_lembrar_fonte", _e)


# quantas voltas seguidas a fonte gravada pode falhar antes de ser esquecida
FALHAS_ATE_ESQUECER = 3
_FALHAS_FONTE: dict = {}


def esquecer_fonte(dataset_id: str, motivo: str = "") -> bool:
    """Apaga o endereço gravado desta mesa, para ela voltar a procurar.

    O DEFEITO QUE ISTO CONSERTA — "crazy time a perde conexão e não volta mais"
    ────────────────────────────────────────────────────────────────────────
    Não existia jeito de esquecer uma fonte. `_lembrar_fonte` gravava o endereço
    que funcionou, e ele ficava gravado para sempre -- inclusive depois de o
    provedor desligá-lo.

    O que acontece então, toda volta, para sempre:

        candidatos = [o endereço morto, o principal, as alternativas]

    O endereço morto é sempre o PRIMEIRO. Ele consome timeout e novas
    tentativas, e o orçamento da volta acaba antes de chegar nos outros. E como
    `fonte_lembrada` continua devolvendo alguma coisa, o atalho da página dele --
    aquele que só roda "quando a mesa não tem fonte conhecida" -- nunca dispara.

    A mesa fica presa consultando um endereço que não existe mais, com um
    registro dizendo que aquele endereço funciona. É exatamente "perde conexão e
    não volta mais": ela não perdeu nada, ela está insistindo num cadáver.

    Três falhas seguidas, não uma: uma API cai por trinta segundos e volta, e
    esquecer na primeira faria a mesa reprocurar o endereço a cada soluço.
    """
    try:
        d = {}
        if FONTES_OK.is_file():
            d = json.loads(FONTES_OK.read_text(encoding="utf-8")) or {}
        if dataset_id not in d:
            return False
        antigo = d.pop(dataset_id, None)
        _gravar_json(FONTES_OK, d)
        _FALHAS_FONTE.pop(dataset_id, None)
        engolido(f"fluxo_captura/FONTE_ESQUECIDA {dataset_id} deixou de usar "
                 f"{antigo} — {motivo or 'falhou seguidas vezes'}; volta a "
                 f"procurar endereco", None)
        return True
    except Exception as _e:
        engolido("fluxo_captura/esquecer_fonte", _e)
    return False


def _fonte_falhou(dataset_id: str) -> bool:
    """Conta mais uma falha da fonte gravada; esquece ao chegar no limite."""
    n = int(_FALHAS_FONTE.get(dataset_id, 0)) + 1
    _FALHAS_FONTE[dataset_id] = n
    if n >= FALHAS_ATE_ESQUECER:
        return esquecer_fonte(dataset_id,
                              f"{n} voltas seguidas sem resposta")
    return False


def _fonte_funcionou(dataset_id: str) -> None:
    _FALHAS_FONTE.pop(dataset_id, None)


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
# AGORA E UMA LISTA POR MESA, E A PAGINA DELE VEM PRIMEIRO.
#
# Era um endereco so por mesa. Com um endereco so, uma fonte fora do ar (ou
# atras de Cloudflare, que ja aconteceu aqui com 403) mata a mesa inteira -- e
# foi o caso da Crazy Time A, que levava 404 na API e nao tinha para onde cair.
#
# O casinoscores e a pagina oficial do provedor, entao vem na frente do
# gamblingcounting, que e' agregador. As duas continuam valendo: a segunda so
# e' consultada se a primeira nao devolver giro.
FONTES_HTML = {
    "lightning": [
        "https://www.casino.org/casinoscores/pt-br/lightning-roulette/",
        "https://gamblingcounting.com/lightning-roulette",
    ],
    "mega_fire": [
        "https://www.casino.org/casinoscores/pt-br/mega-fire-blaze-roulette/",
        "https://gamblingcounting.com/roulette",
    ],
    "crazy_time": [
        "https://www.casino.org/casinoscores/pt-br/crazy-time/",
        "https://gamblingcounting.com/crazy-time",
    ],
    "red_door": [
        "https://www.casino.org/casinoscores/pt-br/red-door-roulette/",
        "https://gamblingcounting.com/roulette",
    ],
    "crazy_time_a": [
        # o endereco que ele mandou, textual
        "https://www.casino.org/casinoscores/pt-br/crazy-time-a/",
        "https://gamblingcounting.com/crazy-time-a",
    ],
}


def enderecos_html(dataset_id: str) -> List[str]:
    """As paginas desta mesa, na ordem de tentativa."""
    v = FONTES_HTML.get(dataset_id)
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def capturar_html(dataset_id: str) -> List[dict]:
    """Os ultimos resultados pelas paginas publicas da mesa.

    Tenta cada endereco em ordem e fica com o primeiro que devolver giro. O
    leitor e o mesmo para qualquer site: ele procura, no HTML, um bloco JSON
    com uma lista de resultados e CONFERE cada valor contra o dominio da mesa.
    E isso que permite trocar de site sem trocar de parser -- e que impede um
    array qualquer da pagina de virar historico.

    Devolve no mesmo formato das outras fontes, para o resto do software nao
    precisar saber de onde veio.
    """
    urls = enderecos_html(dataset_id)
    if not urls:
        return []
    d: Dict[str, Any] = {}
    for _u in urls:
        try:
            from fonte_gamblingcounting import coletar_url
            d = coletar_url(_u, dataset_id) or {}
        except Exception as _e:
            engolido("fluxo_captura/capturar_html", _e)
            continue
        if d.get("resultados"):
            break
    if not d or d.get("erro") and not d.get("resultados"):
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
# QUANTO TEMPO SEPARA "O MESMO GIRO RELATADO DUAS VEZES" DE "O NUMERO REPETIU".
#
# Isto era 20 segundos, e 20 segundos come giro de verdade. O site dele mostra
# quatro "1" seguidos entre 18:21 e 18:23 -- rodadas legitimas, com o mesmo
# resultado, em menos de um minuto. O software apagava as repetidas e o
# historico saia menor que o do site, que foi exatamente o que ele apontou.
#
# O problema que esta regra existe para resolver e outro e menor: o MESMO
# evento relatado duas vezes com o carimbo deslocado em 1 segundo. Para isso
# bastam poucos segundos. Vinte era eu resolvendo um problema de 1 segundo com
# uma rede que pega tres rodadas.
#
# E o pior: repeticao e uma das coisas que o estudo MEDE. Apagar repeticao real
# nao deixa o historico so mais curto -- deixa a medida de repeticao errada
# para baixo, em silencio.
MIN_SEG_RODADA = 5.0

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
        lote = _lote_de_anuncio(obj)
        if lote is not None:
            achados.extend(lote)
        else:
            for it in obj[:40]:
                _anunciados_no_giro(it, fundo + 1, achados)
    return achados


# chaves que so aparecem em item de HISTORICO, nunca num numero anunciado
MARCAS_DE_HISTORICO = {
    "settledat", "settled", "startedat", "gameid", "tableid", "id",
    "result", "outcome", "data", "wheelresult", "players", "currency",
    "dealer", "round", "roundid", "timestamp", "time", "createdat",
}
MAX_ANUNCIADOS = 12


def _lote_de_anuncio(obj: list):
    """Esta lista e um anuncio de numeros? Devolve o lote, ou None.

    O CRIVO EXIGIA MULTIPLICADOR, E O ANUNCIO QUASE NUNCA TEM.
    ---------------------------------------------------------
    Era assim:

        if lote and len(lote) <= 12 and any(it["x"] for it in lote):

    A ideia era separar anuncio de historico -- os dois sao lista de numeros de
    roleta, e confundir um com o outro faria o software prever multiplicador em
    cima de giro velho. O separador escolhido foi o multiplicador: "anuncio
    carrega valor, historico nao".

    Esta errado, e o print da mesa dele mostra por que. Na tabela "Numeros de
    Fogo Coincidiu" a coluna Multip. esta VAZIA em quase toda linha -- so o 26
    tem 38X. O multiplicador aparece quando o numero PAGA. O anuncio dos
    numeros de fogo acontece todo giro, com ou sem valor.

    Entao a condicao `any(x)` descartava a lista inteira em todos os giros que
    nao pagaram -- que sao a esmagadora maioria. Resultado exato do que ele
    viu: 213 giros lidos, `tags=[]` em todos, "[Multiplicador] sem palpite", e
    -- porque o Cacador decide sozinho -- `alvos=[]`, tela vazia, contadores
    parados e nenhum acerto/erro marcado no historico.

    E o mesmo defeito que eu ja tinha consertado duas vezes noutros lugares,
    escrito de terceira forma: guardar o anuncio so quando ele pagou.

    O QUE SEPARA OS DOIS DE VERDADE
    -------------------------------
    Nao e o multiplicador -- e a FORMA do item. Item de historico carrega
    carimbo de giro: settledAt, gameId, result, outcome. Numero anunciado nao
    tem nada disso: e um numero, as vezes com um valor ao lado.

    E anuncio nao repete numero. Uma lista de 40 giros repete; uma lista de
    numeros de fogo, nao.
    """
    if not obj or len(obj) > MAX_ANUNCIADOS:
        return None
    lote = []
    for it in obj:
        num = None
        mx = None
        if isinstance(it, dict):
            # carimbo de giro: isto e historico, nao anuncio
            if any(str(k).lower() in MARCAS_DE_HISTORICO for k in it.keys()):
                return None
            for c in ("number", "n", "value", "num", "slot", "position"):
                if c in it:
                    try:
                        num = int(it[c])
                    except (TypeError, ValueError):
                        return None
                    break
            for c in ("roundedMultiplier", "multiplier", "x", "payout",
                      "mult", "multiplicator"):
                if it.get(c):
                    try:
                        mx = int(float(it[c]))
                    except (TypeError, ValueError):
                        mx = None
                    break
        elif isinstance(it, (int, str)):
            # `fireNumbers: [7, 12, 20]` -- lista crua, sem valor nenhum.
            # O crivo antigo rejeitava isto no primeiro item, por nao ser dict.
            try:
                num = int(str(it).strip())
            except (TypeError, ValueError):
                return None
        else:
            return None
        if num is None or not (0 <= num <= 36):
            return None
        lote.append({"n": num, "x": mx})
    if not lote:
        return None
    # anuncio nao repete numero; historico repete
    if len({it["n"] for it in lote}) != len(lote):
        return None
    return lote


def parse_items_roulette(items: List[dict]) -> List[dict]:
    """Aceita estruturas aninhadas antigas e planas."""
    # expande se item contém lista interna de resultados
    expanded = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        d = it.get("data") if isinstance(it.get("data"), dict) else it
        # O MESMO GIRO ENTRAVA DUAS VEZES.
        #
        # Este laço acrescentava `d[k]` E `it[k]` para cada chave. Quando não
        # há envelope `data`, `d` É `it` -- então a MESMA lista era acrescentada
        # duas vezes, e todo giro daquela resposta virava dois giros.
        #
        # Isso não some no dedupe: o `event_id` é `jogo|valor|settled`, e as
        # duas cópias têm valor e horário idênticos, então uma sobrescreve a
        # outra sem erro... mas só depois de passar pelo parser inteiro, e
        # `mults` já foi montado em dobro no caminho. Onde a resposta traz
        # `data` E `it` com listas diferentes, as duas de fato entram — e aí a
        # duplicata sobrevive.
        #
        # Comparação por identidade, não por igualdade: duas listas com o mesmo
        # conteúdo vindas de lugares diferentes são dois relatos, e aí as duas
        # valem. A mesma lista lida duas vezes, não.
        nested_lists = []
        vistas = set()
        for k in ("results", "gameResults", "events", "items"):
            for fonte in (d, it):
                lst = fonte.get(k) if isinstance(fonte, dict) else None
                if isinstance(lst, list) and id(lst) not in vistas:
                    vistas.add(id(lst))
                    nested_lists.append(lst)
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

            # O CAMPO DECLARADO SE LE SEMPRE -- ELE E QUEM TRAZ O MULTIPLICADOR.
            #
            # EU CONSERTEI ISTO PELA METADE, e ele viu o resultado: o site
            # mostrando 74X no 30 e 132X no 8 na mesma meia hora, e o software
            # dizendo "0% de multiplicador, seca de 97 giros". Os NUMEROS batiam
            # -- 5, 19, 28, 30, 22, 2, 34 -- entao a captura estava viva; so o
            # valor sumia.
            #
            # O comentario aqui em cima chega a dizer "antes tudo isto vivia
            # dentro do if _boost". Saiu dali a busca generica; a leitura do
            # campo declarado FICOU. E `superBoost` marca a rodada especial, nao
            # o anuncio -- entao nos giros que pagaram sem ser rodada especial o
            # valor nunca era lido. A busca generica achava os numeros (dai "97
            # rodadas com sorteio em 217") mas sem `x`, e sem `x` nada paga.
            #
            # E o mesmo erro pela terceira vez neste arquivo, escrito de outro
            # jeito: guardar o anuncio so quando ele pagou.
            _fn = None
            for _campo in ("fireNumbers", "fireNumbersList", "blazeNumbers",
                           "fireBlazeNumbers", "fireballNumbers", "hotNumbers",
                           "fireNumberList"):
                _fn = res.get(_campo) or d.get(_campo)
                if _fn:
                    break
            _lista = []
            for fb in (_fn if isinstance(_fn, list) else []):
                try:
                    if isinstance(fb, dict):
                        _num = fb.get("number", fb.get("n", fb.get("value")))
                        if _num is None:
                            continue
                        _mx = (fb.get("roundedMultiplier") or fb.get("multiplier")
                               or fb.get("x") or fb.get("mult"))
                        _lista.append({"n": int(_num),
                                       "x": int(float(_mx)) if _mx else None})
                    else:
                        _lista.append({"n": int(fb), "x": None})
                except (TypeError, ValueError):
                    pass
            # o campo declarado vem primeiro: ele traz o multiplicador, e a
            # busca generica so completa o que faltar
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
            # `result` PODE SER O VALOR, NAO O ENVELOPE.
            #
            # Isto era `res = d.get("result") or d`. Quando a fonte devolve
            # `result: "5"` -- que e' o formato de varias delas -- `res` virava
            # a STRING "5", e a linha seguinte fazia `"5".get("outcome")`.
            # `AttributeError`, engolido pelo `except` la embaixo, `continue`:
            # o giro sumia inteiro, sem erro na tela.
            #
            # E some justamente nos setores numericos, que sao os mais comuns
            # da mesa. O "1" sozinho ocupa 21 das 54 casas.
            _r = d.get("result")
            res = _r if isinstance(_r, dict) else d
            _sec_direto = _r if _r is not None and not isinstance(_r, (dict, list)) else None
            _o = res.get("outcome") if isinstance(res, dict) else None
            out = _o if isinstance(_o, dict) else res
            sec = _sec_direto
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
                    # O `{"x": ...}` SOLTO SIGNIFICA "ESTE GIRO PAGOU".
                    #
                    # Ele era acrescentado sempre que havia multiplicador no
                    # top slot -- inclusive quando o símbolo sorteado NÃO era o
                    # que a roda parou. Mas o top slot só paga quando os dois
                    # coincidem; nos outros giros é "Miss" e o jogador não
                    # recebe nada.
                    #
                    # Quem lê `{"x": ...}` entende que aquele giro pagou. Então
                    # o Crazy Time saía com multiplicador registrado na maioria
                    # dos giros — inflando intensidade, magnitude e a coluna da
                    # tela com prêmio que não existiu. O `top` acima continua
                    # guardando o sorteio inteiro (símbolo e valor), que é o
                    # dado honesto: dá para estudar quantas vezes bate.
                    if mult and simbolo and str(simbolo) == str(s):
                        tags.append({"x": mult})
            except Exception as _e:
                engolido("fluxo_captura/parse_items_ct", _e)
            rows.append({"n": s, "sec": s, "settled": settled, "tags": tags})
        except Exception as _e:
            engolido("fluxo_captura/parse_items_ct", _e)
            continue
    return rows


# PROFUNDIDADE DO HISTORICO — MEDIDO NA MAQUINA DELE, NAO SUPOSTO.
#
# A sonda que ele rodou respondeu tres coisas que eu vinha adivinhando:
#   1. o servidor devolve NO MAXIMO 100 itens por pagina
#   2. `duration` e IGNORADO — 90 a 525600 devolvem os MESMOS 100 itens
#   3. a PAGINACAO funciona: pag0 comecava 22:39, pag3 comecava 18:25
#
# E dai sai o defeito: a CENTRAL pedia `page_size=50, max_pages=2` — cem giros,
# exatamente o "historico 104" da tela dele. O teto era meu, nao do servidor.
# Enquanto isso, metade das medidas dizia "amostra insuficiente" por falta de
# historico que estava ali para ser puxado (o limiar dele exige 3 blocos de 500).
#
# Buffer raso pede fundo; buffer cheio pede so a frente, porque giro novo nasce
# no topo. Automatico de proposito: depender de eu lembrar de passar o parametro
# certo em cada chamada foi o que produziu o teto de 100.
TAMANHO_PAGINA = 100          # teto do servidor, medido pela sonda
PROFUNDIDADE_ALVO = 500       # o mesmo teto que o buffer guarda
PAGINAS_A_FUNDO = 6           # 6 x 100 = 600, com folga sobre o alvo


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
    # quanto historico esta mesa ja tem — raso pede fundo, cheio pede a frente
    try:
        _ja_tem = len(load(buffer_path(dataset_id)).get("events") or [])
    except Exception:
        _ja_tem = 0
    page_size = max(int(page_size), TAMANHO_PAGINA)
    if _ja_tem < PROFUNDIDADE_ALVO:
        max_pages = max(int(max_pages), PAGINAS_A_FUNDO)

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
    # A VOLTA TEM HORA PARA ACABAR.
    #
    # Com a API fora do ar, cada endereco custava 81s (25s de timeout x 3
    # tentativas + backoff). O Lightning tem 3 enderecos: 4 minutos numa volta.
    # A Crazy Time A tem 10: treze minutos e meio. A mesa consulta a cada 10s,
    # mas a trava `ocupado` segura tudo enquanto isto move -- e a tela fica
    # identica esse tempo todo. Foi o "o lightning ta travado".
    #
    # Insistir faz sentido para um 500 passageiro; nao faz para uma API que
    # esta fora ha minutos. Agora a volta inteira tem orcamento, e quando ele
    # acaba a captura cai para o historico salvo -- que mantem o software
    # analisando em vez de congelar esperando.
    import time as _t
    _fim = _t.time() + ORCAMENTO_VOLTA_S
    items, err = [], None

    # A PAGINA DELE VEM PRIMEIRO QUANDO A MESA NAO TEM FONTE CONHECIDA.
    #
    #     "use este https://www.casino.org/casinoscores/pt-br/crazy-time-a/"
    #
    # Ele pediu duas vezes, e ele esta certo: se a mesa nunca conseguiu abrir
    # por nenhum endereco (nada gravado em fontes_que_funcionam.json), insistir
    # na minha lista de grafias e' gastar o orcamento da volta em 404 antes de
    # olhar a unica fonte que ELE confirmou existir.
    #
    # Com fonte gravada, este atalho nao roda: ai a API conhecida e' mais
    # rapida e mais rica (traz o anuncio de multiplicador, que a pagina nao
    # traz). O atalho e para destravar mesa nova -- que e' o caso da Crazy
    # Time A desde o comeco.
    # A DESCOBERTA PELA PAGINA TEM INTERVALO — O LOG DELE MOSTROU POR QUE.
    #
    #   16:10:18 crazy_time_a: depois dos scripts, 17 endereco(s)
    #   16:11:28 crazy_time_a: depois dos scripts, 17 endereco(s)
    #   16:12:38 crazy_time_a: depois dos scripts, 17 endereco(s)
    #   16:13:38, 16:14:48, 16:15:49 ... uma vez por volta, para sempre
    #
    # Cada uma custa ~60s do orcamento de 45s da volta, e a mesa passa a vida
    # baixando o mesmo pacote de scripts. Enquanto isso ela nao le giro nenhum --
    # que e a mesa parada que ele viu. Isto ja tinha portao no descobridor de
    # ultimo recurso e nao tinha aqui.
    _ult_pag = _ULTIMA_PAGINA.get(dataset_id, 0.0)
    if not fonte_lembrada(dataset_id) and _t.time() - _ult_pag > INTERVALO_PAGINA_S:
        _ULTIMA_PAGINA[dataset_id] = _t.time()
        try:
            from descobridor_pela_pagina import procurar as _proc
            for _pag in enderecos_html(dataset_id):
                if _t.time() >= _fim - 5:
                    break
                _r = _proc(_pag, str(dataset_id),
                           registrar=lambda m: engolido("fluxo_captura/" + m,
                                                        None))
                if (_r.get("api")
                        and identidade_ok(dataset_id, _r["api"])[0]
                        and not fonte_de_outra_mesa(dataset_id, _r["api"])):
                    # a propria pagina disse onde busca; grava e usa
                    _lembrar_fonte(dataset_id, _r["api"])
                    candidatos = [_r["api"]] + [c for c in candidatos
                                                if c != _r["api"]]
                    break
        except Exception as _e:
            engolido("fluxo_captura/pagina_primeiro", _e)

    _lembrada = fonte_lembrada(dataset_id)
    for _url in candidatos:
        if _t.time() >= _fim:
            err = err or "prazo da volta esgotado"
            break
        # O CRIVO DE IDENTIDADE VEM ANTES DE BUSCAR, NAO DEPOIS DE GRAVAR.
        #
        # Era so na gravacao, e o log dele mostrou a consequencia: a mesa
        # recusava MEMORIZAR o endereco alheio e continuava USANDO os giros que
        # ele devolveu. Crazy Time e Crazy Time A apareceram na tela com a mesma
        # sequencia deslocada em dois giros, com `FONTE_DUPLICADA` no log o tempo
        # todo. Recusar a memoria sem recusar o dado nao conserta nada.
        _ok_id, _motivo_id = identidade_ok(dataset_id, _url)
        if not _ok_id:
            engolido(f"fluxo_captura/ENDERECO_ALHEIO {dataset_id} nao usa "
                     f"{_url}: {_motivo_id}", None)
            # RECUSAR TEM DE CONTAR COMO FALHA, senao os caminhos de reserva
            # nao rodam: eles sao guardados por `if err and not items`, e um
            # candidato pulado nao deixava `err` nenhum. A mesa cujos candidatos
            # fossem todos alheios devolveria vazio EM SILENCIO -- trocando um
            # defeito (ler a mesa errada) por outro (nao ler nada e nao dizer).
            err = err or f"nenhum endereco desta mesa respondeu ({_motivo_id})"
            continue
        items, err = fetch_paginas(
            _url, HEADERS, page_size=page_size, max_pages=max_pages,
            duration=duration, prazo=_fim)
        if items:
            _lembrar_fonte(dataset_id, _url)
            _fonte_funcionou(dataset_id)
            break
    # A FONTE GRAVADA QUE NAO RESPONDE MAIS TEM DE SER ESQUECIDA.
    #
    # Sem isto ela continua sendo o PRIMEIRO candidato de toda volta, para
    # sempre: consome o orcamento em timeout antes de os outros enderecos serem
    # tentados, e -- pior -- mantem `fonte_lembrada` respondendo, o que desliga o
    # atalho da pagina dele, que so roda "quando a mesa nao tem fonte conhecida".
    # A mesa nao perdeu a conexao; ela esta insistindo num cadaver.
    if not items and _lembrada:
        if _fonte_falhou(dataset_id):
            # esqueceu agora: tenta JA os enderecos que sobraram, sem esperar a
            # volta seguinte -- se ha orcamento, nao ha motivo para adiar
            for _url in [c for c in candidatos if c != _lembrada]:
                if _t.time() >= _fim:
                    break
                if not identidade_ok(dataset_id, _url)[0]:
                    continue
                items, err = fetch_paginas(
                    _url, HEADERS, page_size=page_size, max_pages=max_pages,
                    duration=duration, prazo=_fim)
                if items:
                    _lembrar_fonte(dataset_id, _url)
                    _fonte_funcionou(dataset_id)
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
            from descobridor_endereco import descobrir as _descobrir
            _ultima = _ULTIMA_PROCURA.get(dataset_id, 0.0)
            # a procura custa dezenas de requisicoes: nao comeca sem tempo
            # 20s, nao 5: a procura consulta dezenas de enderecos, e comecar
            # com 5 segundos garantia que ela nao terminaria -- so gastaria o
            # portao de dez minutos sem chegar a lugar nenhum, e a mesa ficaria
            # bloqueada de procurar por mais dez minutos por causa de uma
            # tentativa que nunca teve chance.
            if _t.time() < _fim - 20 and _t.time() - _ultima > 600:
                _ULTIMA_PROCURA[dataset_id] = _t.time()
                # PRIMEIRO PERGUNTA A PAGINA DA MESA, DEPOIS CHUTA GRAFIA.
                #
                # A pagina que ele mandou EXIBE os resultados, entao ela sabe de
                # onde os tira. Ler o endereco dela e seguir uma referencia;
                # gerar grafias e adivinhar. Eu venho adivinhando o nome da
                # Crazy Time A ha versoes -- crazytimea, crazytime-a,
                # crazytimeA, crazytime2, crazy-time-a -- e todas deram 404,
                # sem eu poder testar nenhuma (o proxy daqui nega casino.org).
                #
                # A ordem certa e: evidencia primeiro, palpite depois.
                _novo = None
                try:
                    from descobridor_pela_pagina import procurar as _proc
                    for _pag in enderecos_html(dataset_id):
                        _r = _proc(_pag, str(dataset_id),
                                   registrar=lambda m: engolido(
                                       "fluxo_captura/" + m, None))
                        if _r.get("api") and identidade_ok(
                                dataset_id, _r["api"])[0]:
                            _novo = _r["api"]
                            break
                except Exception as _e:
                    engolido("fluxo_captura/descobrir_pela_pagina", _e)
                if not _novo:
                    _novo = _descobrir(str(dataset_id))
                if _novo and not identidade_ok(dataset_id, _novo)[0]:
                    engolido(f"fluxo_captura/ENDERECO_ALHEIO a descoberta de "
                             f"{dataset_id} devolveu {_novo}, que nao e desta "
                             f"mesa — descartado", None)
                    _novo = None
                if _novo:
                    items, err = fetch_paginas(
                        _novo, HEADERS, page_size=page_size,
                        max_pages=max_pages, duration=duration, prazo=_fim)
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
            # DESISTIR AQUI ERA DESISTIR ANTES DAS FONTES ALTERNATIVAS.
            #
            # Este `return` acontece quando as duas APIs falharam, o HTML
            # falhou e o buffer está vazio. Só que as fontes externas
            # (`capturar_multi_fonte`: bases_estudo, tracksino, HTML de
            # terceiros) só são consultadas MUITO mais abaixo nesta função --
            # e este retorno passa por cima delas.
            #
            # O caso em que isso importa é exatamente o pior: mesa NOVA, sem
            # buffer nenhum. É a situação da Crazy Time A. Enquanto ela não
            # tivesse um único giro salvo, as fontes alternativas nunca seriam
            # tentadas -- e sem elas ela nunca teria o primeiro giro. Um nó:
            # precisa de dado para ir buscar dado.
            try:
                from fontes_externas import capturar_multi_fonte
                _ex = capturar_multi_fonte(dataset_id, max_total=120) or {}
                _lin = _purge_invalid(list(_ex.get("rows") or []), dataset_id)
            except Exception as _e:
                engolido("fluxo_captura/socorro_externo", _e)
                _lin = []
            if _lin:
                _mx = []
                for _e2 in _lin:
                    _mx.extend(_mults_do_evento(_e2))
                merge(buffer_path(dataset_id), dataset_id, _lin,
                      max_keep=MAX_GIROS_BUFFER)
                return {"rows": _lin, "novo_head": True,
                        "head_id": _lin[0].get("event_id"),
                        "err": err, "mults": _mx, "offline": True,
                        "fonte": "externa"}
            return {"rows": [], "novo_head": False, "head_id": None,
                    "err": err, "mults": []}
        rows_off, mults_off = [], []
        for e in salvos:
            rows_off.append({"n": e.get("n"), "sec": e.get("n"),
                             "settled": e.get("settled"),
                             "tags": e.get("tags") or [],
                             "event_id": e.get("event_id")})
            # O FALLBACK OFFLINE MONTAVA `mults` SÓ DAS TAGS `x`.
            #
            # É o mesmo esquecimento do caminho online, que já foi corrigido
            # lá — e sobreviveu aqui. Quando a API cai e o software segue com
            # o histórico salvo, o anúncio inteiro (lucky, fire_nums, top slot)
            # sumia, e o Caçador ficava mudo justamente nas horas em que a
            # captura está instável.
            #
            # Agora os dois caminhos usam a MESMA função. Duas cópias da mesma
            # regra é como este defeito nasceu.
            mults_off.extend(_mults_do_evento(e))
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
        # a MESMA funcao do caminho offline: duas copias da regra e como o
        # anuncio sumiu do fallback sem ninguem notar
        mults.extend(_mults_do_evento(e))

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
    """Persiste ciclo em andamento para restaurar apos restart.

    Grava tambem EM QUE GIRO a janela estava. Sem isso, ao reabrir o software a
    janela e julgada contra o giro mais novo de agora -- pulando todos os que
    aconteceram enquanto o programa esteve fechado. Uma janela contabilizada como
    "3 giros" ganharia tantas chances quantos giros passaram, e o placar ficaria
    bom no inicio por construcao. Com o head gravado, a CENTRAL sabe que a mesa
    andou e abandona a janela em vez de pontua-la.
    """
    p = estado_ciclo_path(dataset_id)
    data = {
        "escolhas": list(escolhas or []),
        "restantes": int(restantes or 0),
        "janela_hit": bool(janela_hit),
        "ok": int(ok or 0),
        "err": int(err or 0),
        "head_id": head_atual_do_buffer(dataset_id),
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
