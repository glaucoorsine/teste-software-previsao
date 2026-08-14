# -*- coding: utf-8 -*-
"""Log append-only de eventos com identidade por timestamp/ID prioritário."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from .paths_dados import subdir
from .locks import file_lock

def _path(dataset_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    return subdir("event_log") / f"{safe}.jsonl"


def _eid(dataset_id: str, abs_idx: int, valor: str, ts: Optional[str] = None) -> str:
    base = f"{dataset_id}|{abs_idx}|{valor}|{ts or ''}"
    h = hashlib.sha256(base.encode()).hexdigest()
    return f"{dataset_id}:{valor}:s{abs_idx}:{h[:16]}"


def _load_log(dataset_id: str) -> List[dict]:
    p = _path(dataset_id)
    log = []
    if not p.is_file():
        return log
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            log.append(json.loads(line))
        except json.JSONDecodeError as e:
            # linha corrompida — regista e continua
            log.append({"_corrupt": True, "erro": str(e)})
    return [x for x in log if not x.get("_corrupt")]


def _append(dataset_id: str, recs: List[dict]) -> None:
    if not recs:
        return
    p = _path(dataset_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p.with_suffix(".lock")):
        with p.open("a", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass


def count_new_in_window(
    dataset_id: str, hist: List[str], settled: Optional[List] = None
) -> Dict[str, Any]:
    """Conta eventos novos sob lock exclusivo (read+decide+write)."""
    hist = [str(x) for x in (hist or [])]
    settled = list(settled or [])
    while len(settled) < len(hist):
        settled.append(None)
    if not hist:
        return {"n_novos": 0, "status": "OK", "paired": []}

    p = _path(dataset_id)
    with file_lock(p.with_suffix(".lock")):
        tem_ts = any(s is not None for s in settled[: len(hist)])
        log = _load_log(dataset_id)
        chrono = list(reversed(hist))
        chrono_ts = list(reversed(settled[: len(hist)]))

        if not log:
            status = "BOOTSTRAP" if tem_ts else "BOOTSTRAP_SEM_TS"
            recs = []
            for i, v in enumerate(chrono):
                ts = chrono_ts[i]
                rec = {"abs_idx": i, "valor": v, "ts": ts}
                rec["event_id"] = _eid(dataset_id, i, v, ts)
                recs.append(rec)
            # append without nested lock
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                for rec in recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            paired = list(reversed([(r["event_id"], r["valor"]) for r in recs]))
            return {"n_novos": 0, "status": status, "paired": paired, "bootstrapped": True}

        best = 0
        max_k = min(len(log), len(chrono))
        for k in range(max_k, 0, -1):
            ok = True
            for j in range(k):
                lv, lts = log[-k + j]["valor"], log[-k + j].get("ts")
                cv, cts = chrono[j], chrono_ts[j]
                if lts is not None and cts is not None:
                    if not (str(lv) == str(cv) and str(lts) == str(cts)):
                        ok = False
                        break
                else:
                    if str(lv) != str(cv):
                        ok = False
                        break
            if ok:
                best = k
                break

        n_novos_calc = len(chrono) - best
        if n_novos_calc > 0 and not tem_ts:
            tail_vals = [x["valor"] for x in log[-len(chrono):]] if len(log) >= len(chrono) else None
            if tail_vals == chrono:
                return {
                    "n_novos": 0,
                    "status": "INDETERMINADO",
                    "paired": list(reversed([(r["event_id"], r["valor"]) for r in log[-len(hist):]])),
                }
            return {
                "n_novos": 0,
                "status": "INDETERMINADO",
                "paired": list(reversed([(r["event_id"], r["valor"]) for r in log[-min(len(hist), len(log)):]])),
            }

        next_idx = (log[-1]["abs_idx"] + 1) if log else 0
        new_recs = []
        for j in range(best, len(chrono)):
            v = chrono[j]
            ts = chrono_ts[j]
            rec = {"abs_idx": next_idx, "valor": v, "ts": ts}
            rec["event_id"] = _eid(dataset_id, next_idx, v, ts)
            new_recs.append(rec)
            next_idx += 1
        if new_recs:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                for rec in new_recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
            log.extend(new_recs)

        paired = list(reversed([(r["event_id"], r["valor"]) for r in log[-len(hist):]]))
        return {"n_novos": len(new_recs), "status": "OK", "paired": paired}


def sync_window(dataset_id: str, hist: List[str], settled: Optional[List] = None) -> List[Tuple[str, str]]:
    info = count_new_in_window(dataset_id, hist, settled)
    return info.get("paired") or []
