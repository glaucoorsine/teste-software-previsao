# -*- coding: utf-8 -*-
"""MEGA FIRE — a janela avulsa, reusando a UI comum das roletas.

ESTE ARQUIVO ERA UMA CÓPIA INTEIRA DE `lightning_combo.py`, 596 LINHAS.
────────────────────────────────────────────────────────────────────────
Byte a byte, exceto o nome do jogo e três strings de título. É a mesma
armadilha que `crazy_time_a_combo.py` já apontou: "duplicar o módulo
significaria manter dois arquivos iguais e ter de lembrar de corrigir os
dois -- que é exatamente como um defeito sobrevive". Corrigi um bug aqui
(a logo carregava sempre a do Lightning, mesmo nesta janela) e ele não teria
ido para o outro arquivo sozinho.

`lightning_combo.py` passou a ler a mesa de `LAB_MESA`, com uma lista das
roletas comuns que ele sabe desenhar. Este arquivo só diz qual mesa é.

    python mega_fire_combo.py        (ou 1_INICIAR_MEGA_FIRE.bat)
"""
from __future__ import annotations

import os
import sys

os.environ["LAB_MESA"] = "mega_fire"

from lightning_combo import main  # noqa: E402  (depois do LAB_MESA)

if __name__ == "__main__":
    sys.exit(main() or 0)
