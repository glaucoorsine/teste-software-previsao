# -*- coding: utf-8 -*-
"""
ENGOLIDO — o erro que foi engolido de propósito, mas deixa rastro.

O QUE ELE APONTOU
-----------------
Perto de 250 blocos `except Exception:` terminando em `pass`, `return` ou
`continue`. Muitos são legítimos: gravar um arquivo de conveniência, tentar
uma fonte alternativa, fechar uma janela que já morreu. Nesses casos o
programa DEVE continuar.

O problema não é engolir — é engolir sem deixar rastro. Foi assim que três dos
quatro defeitos que ele rastreou ficaram invisíveis por semanas: o dado morria
dentro de um `except` e a tela seguia como se nada tivesse acontecido. Não
havia o que diagnosticar porque não havia o que ler.

COMO USAR
---------
    from engolido import engolido
    try:
        ...
    except Exception as e:
        engolido("capturar/anuncio", e)
        continue

Por padrão o rastro vai só para `Logs/engolidos.txt`, com hora e local, e o
mesmo local não repete mais que uma vez por minuto — senão um erro dentro do
laço de captura enche o disco.

Ligando `LAB_MOSTRAR_ERROS=1` no ambiente, ele também aparece no console com o
traceback inteiro. É o que se liga quando alguma coisa "não funciona e não dá
erro".
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

RAIZ = Path(__file__).resolve().parent
ARQUIVO = RAIZ / "Logs" / "engolidos.txt"
SEGUNDOS_ENTRE_REPETICOES = 60.0
TETO_BYTES = 2 * 1024 * 1024

_ultimo: dict = {}


def mostrando() -> bool:
    return str(os.environ.get("LAB_MOSTRAR_ERROS", "")).strip() not in ("", "0")


def engolido(onde: str, erro: Optional[BaseException] = None) -> None:
    """Registra um erro que foi engolido de propósito."""
    agora = time.time()
    if agora - _ultimo.get(onde, 0.0) < SEGUNDOS_ENTRE_REPETICOES:
        return
    _ultimo[onde] = agora
    tipo = type(erro).__name__ if erro is not None else "?"
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {onde}  {tipo}: {erro}"
    if mostrando():
        print("[engolido] " + linha)
        if erro is not None:
            traceback.print_exception(type(erro), erro, erro.__traceback__)
    try:
        ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
        # o arquivo não pode crescer para sempre: rodando dias, com onze
        # lugares marcados e uma linha por minuto cada, isso vira megabytes de
        # log que ninguém lê. Passou do teto, fica a metade mais recente.
        if ARQUIVO.is_file() and ARQUIVO.stat().st_size > TETO_BYTES:
            velho = ARQUIVO.read_text(encoding="utf-8", errors="replace")
            ARQUIVO.write_text(velho[len(velho) // 2:], encoding="utf-8")
        with ARQUIVO.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except OSError:
        pass
