# -*- coding: utf-8 -*-
"""Barramento de eventos persistentes por dataset."""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path
from .locks import file_lock
from typing import Any, Dict, List, Optional

from .paths_dados import subdir
ROOT = subdir("bus")

TOPICOS = {
    "dados.qualidade_aprovada",
    "familiaridade.proposta",
    "familiaridade.criticada",
    "familiaridade.validada",
    "familiaridade.ativada",
    "familiaridade.dormente",
    "familiaridade.reativacao",
    "familiaridade.degradada",
    "sombra.registrada",
    "sombra.avaliada",
    "modelo.opiniao",
    "meta.decisao",
    "interface.atualizar",
}

def _path(dataset_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    return ROOT / f"{safe}_bus.jsonl"

def publicar(
    dataset_id: str,
    tipo: str,
    origem: str,
    payload: dict,
    destino: str = "*",
    event_id: str = None,
    cycle_id: str = None,
) -> dict:
    if tipo not in TOPICOS:
        tipo = tipo  # permite extensão, mas registra
    msg = {
        "message_id": uuid.uuid4().hex,
        "dataset_id": dataset_id,
        "event_id": event_id,
        "cycle_id": cycle_id or uuid.uuid4().hex[:12],
        "origem": origem,
        "destino": destino,
        "tipo": tipo,
        "payload": payload,
        "criada_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "processada_em": None,
        "status": "pendente",
        "erro": None,
    }
    p = _path(dataset_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(p.with_suffix(".lock")):
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            f.flush()
    return msg

def ler(dataset_id: str, tipo: str = None, limit: int = 200) -> List[dict]:
    p = _path(dataset_id)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines()[-limit * 2:]:
        try:
            m = json.loads(line)
        except Exception:
            continue
        if tipo and m.get("tipo") != tipo:
            continue
        out.append(m)
    return out[-limit:]

def marcar_processada(dataset_id: str, message_id: str, erro: str = None):
    """Append-only: grava evento de ack (não reescreve o log)."""
    publicar(
        dataset_id,
        "interface.atualizar",
        "bus",
        {"ack": message_id, "erro": erro},
        destino="bus",
    )
