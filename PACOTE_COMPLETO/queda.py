# -*- coding: utf-8 -*-
"""
QUEDA — guardar o estouro de cada janela num arquivo que não apaga o da outra.

O QUE ACONTECIA
---------------
As três janelas avulsas terminavam assim:

    except Exception:
        open("crash_log.txt", "w").write(traceback.format_exc())

Mesmo nome, modo "w", caminho relativo. Três problemas de uma vez:

  1. a segunda janela a cair APAGA o rastro da primeira -- e quando duas caem
     juntas é justamente porque a causa é comum, que é o caso que mais
     interessa;
  2. `"w"` joga fora a queda anterior da MESMA janela, então "aconteceu de
     novo" nunca aparece;
  3. o caminho é relativo ao diretório de onde o programa foi aberto. Clicando
     no `.bat` isso é a pasta do software; abrindo por atalho, pode ser
     qualquer outra -- e aí o arquivo existe em algum lugar que ninguém acha.

Sem hora gravada também não dá para saber se o rastro é de agora ou de três
semanas atrás.

Aqui cada janela tem o arquivo dela, em `Logs/`, com data e hora, e o texto é
ACRESCENTADO. O caminho volta para quem chamou poder mostrar na tela.
"""
from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / "Logs"


def registrar_queda(quem: str, erro: Optional[BaseException] = None) -> Path:
    """Grava o estouro de `quem` e devolve o arquivo onde ficou."""
    seguro = "".join(c if (c.isalnum() or c in "_-") else "_" for c in str(quem))
    destino = PASTA / f"crash_{seguro or 'desconhecido'}.txt"
    texto = traceback.format_exc() if erro is None else "".join(
        traceback.format_exception(type(erro), erro, erro.__traceback__))
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        with destino.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {quem}\n")
            f.write("=" * 70 + "\n")
            f.write(texto)
            f.write("\n")
    except OSError:
        # se nem o log grava, ao menos aparece no console de quem abriu
        print(texto)
    return destino
