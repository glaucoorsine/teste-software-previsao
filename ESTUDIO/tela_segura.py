# -*- coding: utf-8 -*-
"""
TELA SEGURA — mexer na interface a partir de outra thread, sem travar.

A LIÇÃO JÁ FOI PAGA UMA VEZ, NOUTRO SOFTWARE
────────────────────────────────────────────
No software de previsão dele, a tela congelava. O motivo não era desempenho:
era o Tcl por baixo do Tkinter sendo chamado de duas threads ao mesmo tempo.
Ele não é reentrante. Chamado de fora da thread da interface, às vezes
funciona, às vezes corrompe a fila de eventos, às vezes trava o laço
principal -- a janela desenhada, parada, sem erro nenhum no console.

Aqui o risco é maior, não menor: tem a thread da câmera, a do processamento,
a do áudio (que é de tempo real do sistema) e a que lê o ffmpeg. Quatro.

A regra é a mesma: QUEM NÃO É A THREAD DA INTERFACE NÃO TOCA NO WIDGET.
Deposita numa fila, e a própria interface esvazia a fila do lado dela.
"""
from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Optional

_FILA: "queue.Queue[Callable[[], None]]" = queue.Queue()
_THREAD_UI: Optional[int] = None


def marcar_thread_ui() -> None:
    """A interface chama isto uma vez, para eu saber quem é ela."""
    global _THREAD_UI
    _THREAD_UI = threading.get_ident()


def na_ui() -> bool:
    return _THREAD_UI is None or threading.get_ident() == _THREAD_UI


def depois(widget: Any, funcao: Callable[[], None], ms: int = 0) -> None:
    """Roda `funcao` na thread da interface, e só se a janela ainda existir.

    Confere a existência ANTES de rodar e engole o estouro se a janela morrer
    no meio -- fechar a janela enquanto uma thread responde é o caso normal,
    não o excepcional.
    """
    def envelope() -> None:
        try:
            if widget is not None and hasattr(widget, "winfo_exists") \
                    and not widget.winfo_exists():
                return
            funcao()
        except Exception:
            pass

    if na_ui():
        try:
            if widget is not None and hasattr(widget, "after"):
                widget.after(ms, envelope)
            else:
                envelope()
        except Exception:
            pass
    else:
        _FILA.put(envelope)


def bombear(widget: Any, intervalo_ms: int = 33) -> None:
    """A interface liga isto uma vez; ele se reagenda e esvazia a fila."""
    try:
        for _ in range(64):
            try:
                _FILA.get_nowait()()
            except queue.Empty:
                break
            except Exception:
                pass
    finally:
        try:
            if widget is not None and widget.winfo_exists():
                widget.after(intervalo_ms, lambda: bombear(widget, intervalo_ms))
        except Exception:
            pass
