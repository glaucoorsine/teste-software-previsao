# -*- coding: utf-8 -*-
"""Memória persistente individual — escrita concorrente segura."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from .paths_dados import subdir
from .locks import file_lock, atomic_write_text


def _path(dataset_id: str, agente_id: str) -> Path:
    safe_ds = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    safe_ag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in agente_id)
    d = subdir("memoria_agentes") / safe_ds
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe_ag}.json"


def carregar(dataset_id: str, agente_id: str) -> dict:
    p = _path(dataset_id, agente_id)
    if not p.is_file():
        return {
            "agente_id": agente_id,
            "dataset_id": dataset_id,
            "ciclos": 0,
            "notas": [],
            "stats": {
                "hipoteses_total": 0,
                "rejeicoes": 0,
                "validadas": 0,
                "falsos_positivos_sombra": 0,
                "diversidade_expr": 0,
            },
            "regioes_exploradas": [],
            "ultimas_rejeicoes": [],
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            "agente_id": agente_id,
            "dataset_id": dataset_id,
            "ciclos": 0,
            "notas": [],
            "stats": {},
            "erro_load": str(e),
        }


def salvar(dataset_id: str, agente_id: str, mem: dict) -> None:
    p = _path(dataset_id, agente_id)
    mem["atualizado_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with file_lock(p.with_suffix(".lock")):
        atomic_write_text(p, json.dumps(mem, ensure_ascii=False, indent=2))


def registrar_ciclo(
    dataset_id: str,
    agente_id: str,
    n_hipoteses: int,
    nota: str = "",
    regioes: Optional[List[str]] = None,
    rejeicoes: Optional[List[str]] = None,
    validadas: int = 0,
    falso_positivo: int = 0,
    exprs: Optional[List[str]] = None,
) -> dict:
    """Read-modify-write atômico sob lock."""
    p = _path(dataset_id, agente_id)
    with file_lock(p.with_suffix(".lock")):
        if p.is_file():
            try:
                mem = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                mem = {"agente_id": agente_id, "dataset_id": dataset_id, "ciclos": 0, "notas": [], "stats": {}}
        else:
            mem = {
                "agente_id": agente_id,
                "dataset_id": dataset_id,
                "ciclos": 0,
                "notas": [],
                "stats": {
                    "hipoteses_total": 0,
                    "rejeicoes": 0,
                    "validadas": 0,
                    "falsos_positivos_sombra": 0,
                    "diversidade_expr": 0,
                },
                "regioes_exploradas": [],
                "ultimas_rejeicoes": [],
            }
        mem["ciclos"] = int(mem.get("ciclos") or 0) + 1
        st = mem.setdefault("stats", {})
        st["hipoteses_total"] = int(st.get("hipoteses_total") or 0) + int(n_hipoteses)
        st["rejeicoes"] = int(st.get("rejeicoes") or 0) + len(rejeicoes or [])
        st["validadas"] = int(st.get("validadas") or 0) + int(validadas or 0)
        st["falsos_positivos_sombra"] = int(st.get("falsos_positivos_sombra") or 0) + int(falso_positivo or 0)
        if exprs:
            seen = set(mem.get("exprs_unicas") or [])
            for e in exprs:
                seen.add(str(e)[:120])
            mem["exprs_unicas"] = list(seen)[-500:]
            st["diversidade_expr"] = len(mem["exprs_unicas"])
        if regioes:
            reg = list(mem.get("regioes_exploradas") or [])
            for r in regioes:
                if r not in reg:
                    reg.append(r)
            mem["regioes_exploradas"] = reg[-200:]
        if rejeicoes:
            ur = list(mem.get("ultimas_rejeicoes") or [])
            for r in rejeicoes:
                ur.append({"em": time.strftime("%Y-%m-%dT%H:%M:%S"), "motivo": str(r)[:200]})
            mem["ultimas_rejeicoes"] = ur[-100:]
        if nota:
            mem.setdefault("notas", []).append(
                {"em": time.strftime("%Y-%m-%dT%H:%M:%S"), "txt": nota[:200]}
            )
            mem["notas"] = mem["notas"][-50:]
        mem["atualizado_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        atomic_write_text(p, json.dumps(mem, ensure_ascii=False, indent=2))
        return mem
