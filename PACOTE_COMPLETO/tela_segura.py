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

from typing import Any, Callable, Optional


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

    def envelope():
        # a janela pode ter fechado ENTRE o agendamento e o disparo; é
        # exatamente essa fresta que derrubava o programa
        if not vivo(widget):
            return
        try:
            fn()
        except Exception as e:
            # `invalid command name` é a janela fechando -- não é defeito e
            # não merece barulho. Qualquer outra coisa é defeito de verdade e
            # tem que aparecer, senão eu escondo erro meu atrás deste guarda.
            if "invalid command name" in str(e) or "application has been" in str(e):
                return
            import traceback
            traceback.print_exc()

    try:
        return widget.after(ms, envelope)
    except Exception:
        return None


def cancelar(widget: Any, identificador: Optional[str]) -> None:
    """Cancela um agendamento sem estourar se a janela já se foi."""
    if not identificador or not vivo(widget):
        return
    try:
        widget.after_cancel(identificador)
    except Exception:
        pass
