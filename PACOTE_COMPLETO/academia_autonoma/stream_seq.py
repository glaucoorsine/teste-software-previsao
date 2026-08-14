# -*- coding: utf-8 -*-
"""Sequência por eventos reais; bootstrap persiste status sem avançar seq."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from .paths_dados import subdir
from .locks import file_lock, atomic_write_text


def _path(dataset_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    return subdir("stream_seq") / f"{safe}.json"


def _load(dataset_id: str) -> dict:
    p = _path(dataset_id)
    if not p.is_file():
        return {"seq": 0, "dataset_id": dataset_id, "status": "INDETERMINADO", "_exists": False}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data["_exists"] = True
        return data
    except (OSError, json.JSONDecodeError) as e:
        return {
            "seq": 0,
            "dataset_id": dataset_id,
            "status": "INDETERMINADO",
            "erro_load": str(e),
            "_exists": False,
        }


def get_seq(dataset_id: str) -> int:
    return int(_load(dataset_id).get("seq") or 0)


def peek_seq(dataset_id: str) -> int:
    return get_seq(dataset_id)


def apply_new_events(dataset_id: str, n_novos: int, status: str = "OK") -> Dict[str, Any]:
    """
    n_novos==0:
      - se arquivo não existe: persiste status recebido (BOOTSTRAP*) com seq=0
      - se existe: não reescreve; devolve status armazenado
    n_novos>0: avança seq e persiste status=OK (ou o informado)
    """
    p = _path(dataset_id)
    with file_lock(p.with_suffix(".lock")):
        data = _load(dataset_id)
        n_novos = max(0, int(n_novos))
        exists = bool(data.pop("_exists", False))

        if n_novos == 0:
            if not exists:
                out = {
                    "seq": 0,
                    "dataset_id": dataset_id,
                    "status": status,
                    "n_novos": 0,
                    "novo_evento": False,
                    "updated_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                atomic_write_text(p, json.dumps(out, ensure_ascii=False))
                return {
                    "seq": 0,
                    "novo_evento": False,
                    "n_novos": 0,
                    "same_snapshot": False,
                    "status": status,
                    "bootstrapped": True,
                }
            return {
                "seq": int(data.get("seq") or 0),
                "novo_evento": False,
                "n_novos": 0,
                "same_snapshot": True,
                "status": data.get("status") or status,
            }

        data["seq"] = int(data.get("seq") or 0) + n_novos
        data["status"] = status
        data["n_novos"] = n_novos
        data["novo_evento"] = True
        data["dataset_id"] = dataset_id
        data["updated_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        atomic_write_text(p, json.dumps({k: v for k, v in data.items() if not k.startswith("_")}, ensure_ascii=False))
        return {
            "seq": data["seq"],
            "novo_evento": True,
            "n_novos": n_novos,
            "same_snapshot": False,
            "status": status,
        }


def observe(dataset_id: str, hist: List[str], settled: Optional[List] = None) -> dict:
    from .event_log import count_new_in_window
    info = count_new_in_window(dataset_id, hist or [], settled)
    return apply_new_events(dataset_id, info["n_novos"], status=info["status"])


def bump_seq(dataset_id: str) -> int:
    r = apply_new_events(dataset_id, 1, status="BUMP_LEGADO")
    return int(r["seq"])
