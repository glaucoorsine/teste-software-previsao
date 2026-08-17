# -*- coding: utf-8 -*-
"""
FILA DO CÉREBRO — conferir se a resposta é do giro que foi perguntado.

O DEFEITO
---------
A conversa com o processo do cérebro são duas filas sem identificador. Quem
pergunta manda o pedido, espera um prazo e desiste se estourar. O cérebro não
desiste junto: ele termina de pensar e deposita a resposta na fila depois.

Na volta seguinte, `out_q.get()` devolve essa resposta atrasada no ato. Ela é
aplicada ao giro NOVO — e nada denuncia: dicionário bem formado, números
plausíveis, chegando na hora esperada. Depois de dois estouros a fila fica
permanentemente uma resposta atrás, e o software passa a operar inteiro no
passado com aparência de normalidade.

POR QUE UM ARQUIVO
------------------
Porque são quatro telas com o mesmo par de filas e o mesmo defeito: a CENTRAL
e as três janelas avulsas. Consertar só a CENTRAL deixaria três de pé.

Uso:

    self._req = novo_pedido(self)            # antes do put
    payload["req_id"] = self._req
    sug = resposta_de(self, out_q, prazo)    # em vez de out_q.get(timeout=)
"""
from __future__ import annotations

import queue as _queue
import time
from typing import Any, Callable, Optional


def garantir_cerebro(dono: Any, jogo: str,
                     registrar: Optional[Callable[[str], Any]] = None) -> bool:
    """Confere se o processo do cérebro morreu — e levanta outro se morreu.

    O CÉREBRO MORTO NÃO ERA NOTADO POR NINGUÉM.
    -------------------------------------------
    Ele roda em processo separado justamente para que um estouro nele não leve
    a janela junto. Só que ninguém perguntava se ele ainda estava lá. Morrendo
    — falta de memória, erro carregando o modelo, processo derrubado pelo
    sistema — a janela seguia capturando, seguia empurrando pedido na fila, e
    seguia esperando resposta que não viria nunca mais.

    Na tela isso é "Timeout motor" a cada volta, para sempre. Nunca "morreu,
    vou levantar de novo".

    Espera que `dono` tenha `proc`, `in_q` e `out_q`.
    """
    import multiprocessing as mp
    from worker_process import process_cerebro

    p = getattr(dono, "proc", None)
    if p is not None and p.is_alive():
        return True
    if registrar:
        try:
            registrar(f"CEREBRO_MORREU codigo="
                      f"{getattr(p, 'exitcode', None)} — levantando outro")
        except Exception:
            pass
    # filas novas: as antigas podem ter pedido pela metade do processo morto,
    # e resposta órfã seria aplicada ao giro errado
    for q in ("in_q", "out_q"):
        try:
            getattr(dono, q).close()
        except Exception:
            pass
    dono.in_q = mp.Queue(maxsize=4)
    dono.out_q = mp.Queue(maxsize=8)
    dono.primeira = True
    try:
        dono.proc = mp.Process(target=process_cerebro,
                               args=(dono.in_q, dono.out_q, jogo), daemon=True)
        dono.proc.start()
    except Exception as e:
        if registrar:
            try:
                registrar(f"CEREBRO_NAO_SOBE {type(e).__name__}: {e}")
            except Exception:
                pass
        return False
    return True


def novo_pedido(dono: Any, jogo: str = "") -> str:
    """Um identificador por volta, guardado no próprio objeto que perguntou."""
    n = int(getattr(dono, "_seq_pedido", 0)) + 1
    dono._seq_pedido = n
    nome = jogo or getattr(dono, "jogo", None) or getattr(dono, "GAME", "") or "mesa"
    dono._pedido_atual = f"{nome}#{n}"
    return dono._pedido_atual


def resposta_de(dono: Any, out_q: Any, prazo: float,
                registrar: Optional[Callable[[str], Any]] = None) -> Optional[dict]:
    """Espera a resposta DO pedido corrente, descartando as atrasadas.

    Devolve `None` se o prazo acabar — mesmo significado que o `queue.Empty`
    de antes, para quem chama não precisar mudar de forma.

    O prazo é do relógio, não do `get`: uma resposta velha descartada não
    reinicia a contagem, senão uma fila entupida de respostas antigas
    prenderia a volta indefinidamente.
    """
    fim = time.time() + max(0.0, float(prazo))
    esperado = getattr(dono, "_pedido_atual", None)
    while True:
        resta = fim - time.time()
        if resta <= 0:
            return None
        try:
            sug = out_q.get(timeout=resta)
        except _queue.Empty:
            return None
        except Exception:
            return None
        if not isinstance(sug, dict):
            continue
        veio = sug.get("req_id")
        if esperado is None or veio is None or veio == esperado:
            # sem carimbo dos dois lados não há o que conferir: aceita, que é
            # o comportamento antigo. Só não fico calado a respeito.
            return sug
        if registrar:
            try:
                registrar(f"RESPOSTA_ATRASADA descartada (era {veio}, "
                          f"esperava {esperado}) pad={sug.get('pad5')}")
            except Exception:
                pass
