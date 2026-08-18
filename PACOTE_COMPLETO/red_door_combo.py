# -*- coding: utf-8 -*-
"""RED DOOR — a quinta mesa, pedida por ele.

    "adicione esta roleta https://www.casino.org/casinoscores/pt-br/red-door-roulette/"

É uma roleta comum -- mesma UI, mesmo pipeline de 37 números que o Lightning
e o Mega Fire já usam. `lightning_combo.py` desenha qualquer roleta da lista
`_ROLETAS_COMUNS`; este arquivo só diz qual mesa é.

O QUE EU SEI E O QUE EU NÃO SEI SOBRE ESTA MESA, DITO ANTES DE QUALQUER LINHA
──────────────────────────────────────────────────────────────────────────
Eu não alcanço casino.org daqui -- o proxy deste ambiente nega o domínio,
confirmado de novo agora. Então:

  - o ENDEREÇO da API (`fluxo_captura.API_BY_GAME["red_door"]`) segue o mesmo
    padrão que funcionou para as outras três mesas do casino.org (nome da
    página, sem hífen), mas não está verificado contra a fonte real. Por
    trás dele há três redes de segurança que já existiam antes desta mesa:
    a descoberta pela página (lê os scripts que a página de vocês carrega e
    aceita o que responder giro reconhecível), o gerador de grafias
    (`descobridor_endereco.NOMES`), e `identidade_ok()` (recusa qualquer
    endereço que não diga "red door" nele, então mesmo que a descoberta erre,
    ela não vai fazer esta mesa ler outra por engano).

  - o MULTIPLICADOR, se esta mesa tiver um mecanismo de bônus como o Mega
    Fire, não tem nome de campo nenhum chutado por mim -- o Mega Fire me
    ensinou isso do jeito caro. `_anunciados_no_giro()` em `fluxo_captura.py`
    já procura, em qualquer formato, uma lista de números com valor ao lado,
    sem depender do nome do campo. Se a Red Door anunciar assim, o software
    já lê; se não anunciar nada parecido, o software simplesmente não mostra
    multiplicador nenhum, sem inventar.

  - Rode `SONDA_MESAS.bat` depois de abrir esta janela pela primeira vez.
    Com o `sonda_mesas.json` que ela gera eu confirmo o endereço e o campo do
    multiplicador por LEITURA, não por outro chute.

    python red_door_combo.py        (ou 9_INICIAR_RED_DOOR.bat)
"""
from __future__ import annotations

import os
import sys

os.environ["LAB_MESA"] = "red_door"

from lightning_combo import main  # noqa: E402  (depois do LAB_MESA)

if __name__ == "__main__":
    sys.exit(main() or 0)
