# -*- coding: utf-8 -*-
"""
TELA SEGURA — agendar coisa na interface sem quebrar quando a janela fecha.

O ERRO QUE ELE FOTOGRAFOU
─────────────────────────
    _tkinter.TclError: invalid command name ".!telaconfig.!ctklabel3.!label"
      File "CENTRAL.py", line 525, in <lambda>
        self.after(0, lambda: (self.aviso.configure(text=msg, ...)))

O que aconteceu: ele clicou em "Testar agora", a checagem foi para uma thread
de fundo, e ele fechou a tela de configuração antes de ela responder. Quando a
resposta chegou, o `after` disparou e tentou escrever num rótulo que não
existia mais.

Tkinter não avisa que o widget morreu -- ele estoura. E um estouro dentro do
laço de eventos aparece como o programa "travado", que foi o que ele viu.

POR QUE ISTO É UM ARQUIVO E NÃO UM REMENDO
──────────────────────────────────────────
Não é um caso: são 71 chamadas de `after` no software, todas com o mesmo
formato e o mesmo risco. Consertar a linha 525 deixaria as outras setenta de
pé, esperando a vez.

    CENTRAL.py            17
    os quatro combos      12 cada
    central_ias.py         6

`depois()` faz o que o `after` deveria fazer aqui: confere se a janela ainda
existe ANTES de rodar, e engole o estouro se ela morrer no meio. O código que
chama continua igual -- só troca `self.after(...)` por `depois(self, ...)`.
"""
from __future__ import annotations

import queue as _queue
import threading
from typing import Any, Callable, Optional

# ─────────────────────────────────────────────────────────────────────────────
# E TEM O OUTRO LADO DO PROBLEMA: DE QUAL THREAD ISTO É CHAMADO.
#
# `depois()` conferia se a janela existe, e isso resolve o widget destruído.
# Mas quase toda chamada vem de uma thread de fundo -- `_trabalhar`, os
# `threading.Thread(target=tarefa)` espalhados pela CENTRAL -- e chamar
# `widget.after()` de fora da thread da interface é usar o Tk de um lugar de
# onde ele não pode ser usado.
#
# O Tcl por baixo do Tkinter não é reentrante. Chamado de duas threads, ele
# não estoura de forma limpa: às vezes funciona, às vezes corrompe a fila
# interna de eventos, às vezes trava o laço principal. Travar o laço principal
# é exatamente o sintoma que ele fotografou -- a janela desenhada, parada,
# sem responder, sem erro nenhum no console.
#
# Isso explica por que os travamentos dele eram intermitentes e não davam
# rastro: não é um estouro, é uma corrida.
#
# A correção é a padrão em Tk: quem não é a thread da interface não toca no
# widget. Deposita o trabalho numa fila (que É segura entre threads) e a
# própria interface, do lado dela, esvazia a fila. `bombear()` é quem esvazia,
# e a janela principal a liga uma vez.
_pendentes: "_queue.Queue" = _queue.Queue()
_thread_da_tela: Optional[int] = None


def registrar_thread_da_tela() -> None:
    """Marca a thread atual como a da interface. Chamado pela janela principal."""
    global _thread_da_tela
    _thread_da_tela = threading.get_ident()


def _na_thread_da_tela() -> bool:
    # antes de a janela principal se registrar, assume que sim: é o que era
    # antes, e nesse momento ainda não há thread de fundo rodando
    return _thread_da_tela is None or threading.get_ident() == _thread_da_tela


def bombear(raiz: Any, intervalo_ms: int = 40) -> None:
    """Esvazia, na thread da interface, o que as threads de fundo pediram.

    A janela principal chama isto uma vez; ele se reagenda sozinho.
    """
    registrar_thread_da_tela()
    while True:
        try:
            widget, fn = _pendentes.get_nowait()
        except _queue.Empty:
            break
        _executar(widget, fn)
    try:
        raiz.after(intervalo_ms, lambda: bombear(raiz, intervalo_ms))
    except Exception:
        pass


def vivo(widget: Any) -> bool:
    """A janela ainda existe? Perguntar é a única forma de saber no Tk."""
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def depois(widget: Any, ms: int, fn: Callable[[], Any]) -> Optional[str]:
    """Agenda `fn` só se a janela existir, e protege a execução.

    Devolve o identificador do agendamento (como `after`) ou None quando a
    janela já morreu -- assim dá para cancelar do lado de fora se precisar.
    """
    if not vivo(widget):
        return None

    if not _na_thread_da_tela():
        # thread de fundo: não toca no Tk. Deixa na fila e a interface pega.
        # O atraso `ms` se perde aqui, e isso é aceitável -- praticamente todas
        # as chamadas de fundo usam `ms=0`, e as que não usam querem "daqui a
        # pouco", não um instante exato.
        _pendentes.put((widget, fn))
        return None

    def envelope():
        _executar(widget, fn)

    try:
        return widget.after(ms, envelope)
    except Exception:
        return None


def _executar(widget: Any, fn: Callable[[], Any]) -> None:
    # a janela pode ter fechado ENTRE o agendamento e o disparo; é exatamente
    # essa fresta que derrubava o programa
    if not vivo(widget):
        return
    try:
        fn()
    except Exception as e:
        # `invalid command name` é a janela fechando -- não é defeito e não
        # merece barulho. Qualquer outra coisa é defeito de verdade e tem que
        # aparecer, senão eu escondo erro meu atrás deste guarda.
        if "invalid command name" in str(e) or "application has been" in str(e):
            return
        import traceback
        traceback.print_exc()


def cancelar(widget: Any, identificador: Optional[str]) -> None:
    """Cancela um agendamento sem estourar se a janela já se foi."""
    if not identificador or not vivo(widget):
        return
    try:
        widget.after_cancel(identificador)
    except Exception:
        pass
