# -*- coding: utf-8 -*-
"""Caminhos portáteis (Windows/Linux) fora de /tmp quando possível."""
from __future__ import annotations
import os
from pathlib import Path

def data_root() -> Path:
    env = os.environ.get("ACADEMIA_DATA_DIR")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    candidates = [
        Path.home() / ".academia_autonoma" / "data",
        Path(__file__).resolve().parent / "data",
    ]
    for key in ("LOCALAPPDATA", "APPDATA", "TEMP", "TMP"):
        v = os.environ.get(key)
        if v:
            candidates.append(Path(v) / "academia_autonoma" / "data")
    candidates.append(Path("/tmp/academia_autonoma_data"))
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_ok"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return p
        except Exception:
            continue
    p = Path("/tmp/academia_autonoma_data")
    p.mkdir(parents=True, exist_ok=True)
    return p

def subdir(name: str) -> Path:
    p = data_root() / name
    p.mkdir(parents=True, exist_ok=True)
    return p
