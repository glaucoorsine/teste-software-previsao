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

ROOT = Path(__file__).resolve().parent
BUF_DIR = ROOT / "Logs" / "hist_buffers"
BUF_DIR.mkdir(parents=True, exist_ok=True)
MAX_GIROS_BUFFER = 20000   # quantos giros o buffer de cada mesa guarda
SNAP_DIR = ROOT / "Logs" / "snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)

API_BY_GAME = {
    "mega_fire": "https://api-cs.casino.org/svc-evolution-game-events/api/megafireblazeroulette",
    "lightning": "https://api-cs.casino.org/svc-evolution-game-events/api/lightningroulette",
    "immersive": "https://api-cs.casino.org/svc-evolution-game-events/api/immersiveroulette",
    "crazy_time": "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime",
    # Crazy Time A e uma segunda mesa do mesmo jogo. O nome no endpoint nao
    # da para adivinhar daqui, entao a lista abaixo e tentada em ordem e a
    # primeira que responder fica valendo.
    "crazy_time_a": "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimea",
}

# Candidatos alternativos por mesa, tentados quando o principal nao responde.
API_ALTERNATIVAS = {
    "crazy_time_a": [
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime-a",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazytimeA",
        "https://api-cs.casino.org/svc-evolution-game-events/api/crazy-time-a",
    ],
}

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
        if dataset_id != "crazy_time" and v.isdigit():
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
                except Exception:
                    pass
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
                if _lista:
                    tags.append({"fire_nums": _lista})
            rows.append({"n": n, "settled": settled, "tags": tags})
        except Exception:
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
            except Exception:
                pass
            rows.append({"n": s, "sec": s, "settled": settled, "tags": tags})
        except Exception:
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
    api = API_BY_GAME.get(dataset_id)
    if not api:
        return {"rows": [], "novo_head": False, "head_id": None, "err": "dataset desconhecido", "mults": []}

    items, err = fetch_paginas(
        api, HEADERS, page_size=page_size, max_pages=max_pages, duration=duration
    )
    if err and not items:
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

    if dataset_id == "crazy_time":
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
        except Exception:
            pass

    rows = []
    mults = []
    for e in events:
        row = {
            "n": e.get("n"),
            "sec": e.get("n") if dataset_id == "crazy_time" else e.get("n"),
            "settled": e.get("settled"),
            "tags": e.get("tags") or [],
            "event_id": e.get("event_id"),
        }
        rows.append(row)
        for t in e.get("tags") or []:
            if "x" in t:
                mults.append({"n": e.get("n"), "x": t["x"]})

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
            if dataset_id == "crazy_time":
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
