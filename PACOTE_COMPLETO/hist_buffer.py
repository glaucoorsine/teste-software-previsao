# -*- coding: utf-8 -*-
"""
Buffer histórico único — merge seguro, validação de domínio, lock real.
page_size/max_pages respeitados pelo coletor (ver fetch_historico).
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from time_utils import canonical_ts, event_key, sort_key_ts

ROULETTE = {str(i) for i in range(37)}  # 0..36
CT = {"1", "2", "5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"}
# CRAZY TIME A NAO ESTAVA AQUI, E ISSO APAGAVA A MESA INTEIRA.
#
# `_purge_invalid` faz `DOMAIN.get(dataset_id, set())`. Sem a chave, o dominio
# vinha VAZIO e o filtro descartava todos os eventos -- inclusive um buffer
# offline valido ja salvo em disco. Ou seja: mesmo com a captura funcionando
# perfeitamente, o Crazy Time A nunca teria historico.
#
# Eu passei semanas atras do endereco da API sem ver que o dado, se chegasse,
# seria jogado fora tres funcoes depois.
DOMAIN = {
    "mega_fire": ROULETTE,
    "lightning": ROULETTE,
    "crazy_time": CT,
    "crazy_time_a": CT,
    "red_door": ROULETTE,
}

def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")

def _acquire(path: Path, tries: int = 20, delay: float = 0.05) -> bool:
    lp = _lock_path(path)
    for _ in range(tries):
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            # lock antigo?
            try:
                age = time.time() - lp.stat().st_mtime
                if age > 30:
                    lp.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            time.sleep(delay)
        except OSError:
            time.sleep(delay)
    return False

def _release(path: Path):
    try:
        _lock_path(path).unlink(missing_ok=True)
    except OSError:
        pass

def _atomic_write(path: Path, data: dict) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))
        return True
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False

def load(path: Path) -> dict:
    if not path.is_file():
        return {"events": [], "dataset_id": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"events": [], "dataset_id": None}

def normalizar_evento(raw: dict, dataset_id: str) -> Optional[dict]:
    dom = DOMAIN.get(dataset_id, ROULETTE)
    n = raw.get("n")
    if n is None:
        n = raw.get("valor")
    if n is None:
        n = raw.get("result")
    if n is None:
        n = raw.get("sec")
    if n is None:
        return None
    s = str(n).strip()
    # aliases CT
    low = s.lower().replace(" ", "")
    aliases = {
        "coinflip": "CoinFlip", "cashhunt": "CashHunt", "pachinko": "Pachinko",
        "crazybonus": "CrazyBonus", "bonus": "CrazyBonus",
    }
    if low in aliases:
        s = aliases[low]
    if s not in dom:
        return None  # rejeita n=99, setores inválidos, etc.
    settled = canonical_ts(raw.get("settled") or raw.get("settledAt") or raw.get("ts"))
    tags = raw.get("tags") or []
    return {
        "n": s if str(dataset_id).startswith("crazy_time") else (int(s) if s.isdigit() else s),
        "valor": s,
        "settled": settled,
        "tags": tags,
        "event_id": event_key(dataset_id, s, settled),
    }

def _fundir_tags(velho: dict, novo: dict) -> list:
    """Junta as marcas do giro em vez de deixar a última leitura apagar as outras.

    O APAGAMENTO SILENCIOSO
    -----------------------
    `merge` fazia `by_id[eid] = norm` -- o evento novo substituía o antigo
    inteiro. Parece certo (é o mesmo giro, o dado é o mesmo), mas não é: as
    marcas não vêm todas da mesma leitura.

    O anúncio da Mega Fire (`fire_nums`) só aparece na resposta ao vivo. Numa
    releitura de histórico, o MESMO giro volta sem `tags`. Como o event_id é
    `jogo|valor|settled`, ele bate com o que já estava guardado -- e a versão
    pobre sobrescrevia a rica.

    O efeito é o que ele viu: o Caçador lê 254 rodadas e diz "sem palpite". O
    anúncio tinha sido capturado, guardado, e apagado depois pela releitura.
    Sem erro nenhum: o giro continua lá, com o número certo e o horário certo.
    Só o que interessa é que sumiu.

    Aqui as duas listas se somam, sem repetir marca idêntica.
    """
    a = [t for t in (velho.get("tags") or []) if isinstance(t, dict)]
    b = [t for t in (novo.get("tags") or []) if isinstance(t, dict)]
    if not a:
        return b
    if not b:
        return a
    juntas, vistas = [], set()
    for t in a + b:
        try:
            chave = json.dumps(t, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            chave = repr(t)
        if chave in vistas:
            continue
        vistas.add(chave)
        juntas.append(t)
    return juntas


def merge(path: Path, dataset_id: str, novos: List[dict], max_keep: int = 500) -> dict:
    """
    Merge seguro. Se lock falhar, NÃO grava (não apaga conteúdo anterior).
    """
    if not _acquire(path):
        return {"ok": False, "erro": "lock_falhou", "events": load(path).get("events") or []}
    try:
        data = load(path)
        data["dataset_id"] = dataset_id
        by_id = {}
        for e in data.get("events") or []:
            eid = e.get("event_id") or event_key(dataset_id, e.get("valor") or e.get("n"), e.get("settled"))
            by_id[eid] = e
        added = 0
        rejected = 0
        for raw in novos:
            norm = normalizar_evento(raw, dataset_id)
            if norm is None:
                rejected += 1
                continue
            anterior = by_id.get(norm["event_id"])
            if anterior is None:
                added += 1
            else:
                # o giro já estava guardado: preserva o que a leitura de agora
                # não trouxe (anúncio, top slot) em vez de substituir o evento
                norm["tags"] = _fundir_tags(anterior, norm)
                if not norm.get("settled"):
                    norm["settled"] = anterior.get("settled")
            by_id[norm["event_id"]] = norm
        events = list(by_id.values())
        events.sort(key=lambda e: sort_key_ts(e.get("settled")), reverse=True)  # recente primeiro
        data["events"] = events[:max_keep]
        data["updated_at"] = canonical_ts(time.time())
        data["last_merge"] = {"added": added, "rejected": rejected, "total": len(data["events"])}
        ok = _atomic_write(path, data)
        return {"ok": ok, "events": data["events"], "added": added, "rejected": rejected}
    finally:
        _release(path)
