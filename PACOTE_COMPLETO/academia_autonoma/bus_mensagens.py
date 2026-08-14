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
        _rotacionar(p)
    return msg


# O bus era append-only sem poda nenhuma, e o `ler()` carregava o arquivo
# INTEIRO na memória a cada consulta. Medido: 1.279 ciclos de uma mesa geraram
# 7,5 MB. Projetando quatro mesas rodando dias seguidos:
#     3 dias  -> ~42 MB
#     30 dias -> ~420 MB
# O disco aguenta, mas a leitura não: depois de um mês cada consulta ao bus
# carregaria 420 MB para devolver 200 linhas. O software trava de lentidão
# antes de faltar espaço — e trava justamente em quem deixa rodando, que é o
# uso para o qual ele existe.
MAX_BYTES_BUS = 8 * 1024 * 1024      # rotaciona acima disto
# O corte é por TAMANHO, não por número de linhas. Cortar por linhas parece
# equivalente e não é: com mensagens de ~700 bytes, guardar 20.000 linhas dá
# 13,6 MB — acima do teto. O arquivo passava a rotacionar a CADA publicação,
# lendo e reescrevendo 13 MB de cada vez. Guardando metade do teto, a rotação
# só volta a acontecer milhares de mensagens depois, e o custo se dilui.
MANTER_BYTES = MAX_BYTES_BUS // 2


def _tail(p, n_bytes: int) -> List[str]:
    """Últimas linhas do arquivo sem carregar o resto."""
    try:
        tam = p.stat().st_size
        with p.open("rb") as f:
            if tam > n_bytes:
                f.seek(tam - n_bytes)
                f.readline()          # descarta a linha partida ao meio
            bruto = f.read()
        return bruto.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return []


def _rotacionar(p) -> None:
    """Corta o começo do log quando ele passa do teto, preservando o fim."""
    try:
        if p.stat().st_size <= MAX_BYTES_BUS:
            return
        linhas = _tail(p, MANTER_BYTES)
        if not linhas:
            return
        tmp = p.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(linhas) + "\n", encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def ler(dataset_id: str, tipo: str = None, limit: int = 200) -> List[dict]:
    p = _path(dataset_id)
    if not p.is_file():
        return []
    # lê só a cauda: 4 KB por mensagem pedida cobre folgado o tamanho real
    # (~590 bytes), e mesmo com filtro por tipo sobra margem.
    out = []
    for line in _tail(p, max(64 * 1024, limit * 4096)):
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
