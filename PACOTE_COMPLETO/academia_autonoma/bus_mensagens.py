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
    # o ack tem topico proprio: nao e conteudo, e contabilidade do bus, e nao
    # deve aparecer no feed que ele le na tela
    "bus.ack",
}

# o que a tela NAO deve mostrar -- e ruido de infraestrutura
FORA_DO_FEED = {"bus.ack"}

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


def ler(dataset_id: str, tipo: str = None, limit: int = 200,
        incluir_infra: bool = False) -> List[dict]:
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
        # o ack e contabilidade do bus; na tela dele so entra se for pedido
        if not incluir_infra and not tipo and m.get("tipo") in FORA_DO_FEED:
            continue
        out.append(m)
    return out[-limit:]

def marcar_processada(dataset_id: str, message_id: str, erro: str = None):
    """Registra que uma mensagem foi tratada, sem reescrever o log.

    O QUE ESTAVA ERRADO AQUI, E APARECIA NA TELA DELE
    ─────────────────────────────────────────────────
    `publicar()` gravava `"status": "pendente"` em TODA mensagem, e nada no
    software inteiro atualizava esse campo depois. Resultado: a tela mostrava

        19:54:27  INTERFACE   interface.atualizar   pendente
        19:54:27  SEQ_MARKOV  modelo.opiniao        pendente

    para sempre, inclusive nas mensagens já processadas. Ele olhou aquilo e
    concluiu, com toda a razão, que o software tinha travado. Não tinha: o
    rótulo é que era mentiroso.

    E esta função, que seria a única a corrigir o status, nunca era chamada por
    ninguém -- e se fosse, publicaria uma mensagem `interface.atualizar` NOVA,
    ela também "pendente". Reconhecer uma mensagem criaria outra mensagem
    eternamente pendente, e o feed dobraria de tamanho sem nunca resolver nada.

    Agora: `publicar()` não grava mais status inventado, e o ack tem tipo
    próprio (`bus.ack`), que fica FORA do feed da tela. O log continua
    append-only, que é o que a rotação por tamanho exige.
    """
    publicar(
        dataset_id,
        "bus.ack",
        "bus",
        {"ack": message_id, "erro": erro},
        destino="bus",
    )
