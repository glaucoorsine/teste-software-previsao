# -*- coding: utf-8 -*-
"""CRAZY TIME A — a janela avulsa da mesa que não tinha nenhuma.

As três janelas avulsas cobriam Mega Fire, Lightning e Crazy Time. A Crazy
Time A só existia dentro da CENTRAL: não havia atalho para ela, e o
`ABRIR_TUDO.bat` sequer a iniciava — ele ainda chamava a Immersive, que foi
apagada por decisão dele.

Este arquivo não copia o Crazy Time: ele diz qual mesa é e reusa a mesma
janela. Duplicar o módulo significaria manter dois arquivos iguais e ter de
lembrar de corrigir os dois — que é exatamente como um defeito sobrevive.

    python crazy_time_a_combo.py        (ou 7_INICIAR_CRAZY_TIME_A.bat)
"""
from __future__ import annotations

import os
import sys

os.environ["LAB_MESA"] = "crazy_time_a"

from crazy_time_combo import main  # noqa: E402  (depois do LAB_MESA)

if __name__ == "__main__":
    sys.exit(main() or 0)
