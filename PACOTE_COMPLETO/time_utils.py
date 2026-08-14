# -*- coding: utf-8 -*-
"""Normalização canônica de timestamps — evita Z vs +00:00 e IDs divergentes."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

def parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # epoch seconds or ms
        v = float(value)
        if v > 1e12:
            v /= 1000.0
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    s = str(value).strip()
    if not s:
        return None
    # normaliza Z → +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # remove micros demais se necessário
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # tenta formatos comuns
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(s.replace("Z", "+0000"), fmt.replace("%z", "%z") if "%z" in fmt else fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt

def canonical_ts(value: Any) -> Optional[str]:
    """Sempre ISO-8601 UTC com +00:00 (nunca Z)."""
    dt = parse_ts(value)
    if dt is None:
        return None
    # timespec seconds — determinístico
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")

def event_key(dataset_id: str, valor: Any, settled: Any, idx: int = 0) -> str:
    ts = canonical_ts(settled) or f"i{idx}"
    return f"{dataset_id}|{valor}|{ts}"

def sort_key_ts(value: Any):
    dt = parse_ts(value)
    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return dt
