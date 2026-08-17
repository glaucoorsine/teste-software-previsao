# -*- coding: utf-8 -*-
"""Coletor paginado — page_size e max_pages são respeitados."""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from api_fetch import fetch_api
from time_utils import canonical_ts

def fetch_paginas(
    api_url: str,
    headers: dict,
    *,
    page_size: int = 50,
    max_pages: int = 3,
    duration: int = 90,
    sort: str = "data.settledAt,desc",
    prazo: Optional[float] = None,
) -> Tuple[List[dict], Optional[str]]:
    page_size = max(1, min(int(page_size), 100))
    max_pages = max(1, min(int(max_pages), 20))
    all_items: List[dict] = []
    err_last = None
    import time as _t
    for page in range(max_pages):
        # o prazo vale para a paginacao toda: nao adianta cortar a tentativa e
        # depois pedir mais tres paginas
        if prazo is not None and _t.time() >= prazo:
            err_last = err_last or "prazo da volta esgotado"
            break
        params = {
            "page": page,
            "size": page_size,
            "sort": sort,
            "duration": duration,
        }
        data, err = fetch_api(api_url, params, headers=headers,
                              prazo=prazo)
        if err:
            err_last = err
            break
        if not data:
            break
        content = []
        if isinstance(data, dict):
            content = data.get("content") or data.get("data") or data.get("results") or []
        elif isinstance(data, list):
            content = data
        if not content:
            break
        all_items.extend(content)
        if len(content) < page_size:
            break
    return all_items, err_last

def parse_roulette_items(items: List[dict]) -> List[dict]:
    rows = []
    for it in items:
        try:
            data = it.get("data") or it
            n = data.get("result") or data.get("number") or data.get("n")
            if n is None:
                continue
            n = int(n)
            if n < 0 or n > 36:
                continue  # rejeita 99 etc
            settled = canonical_ts(data.get("settledAt") or data.get("settled") or it.get("settledAt"))
            tags = []
            for ln in data.get("luckyNumbersList") or []:
                try:
                    num = int(ln.get("number", ln))
                    mult = ln.get("roundedMultiplier") or ln.get("multiplier")
                    if num == n and mult:
                        tags.append({"x": mult})
                except Exception:
                    pass
            if data.get("superBoost"):
                tags.append({"fire": True})
            rows.append({"n": n, "settled": settled, "tags": tags})
        except Exception:
            continue
    return rows
