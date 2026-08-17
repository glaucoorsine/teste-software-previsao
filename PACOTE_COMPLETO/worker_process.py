# -*- coding: utf-8 -*-
"""O cérebro rodando em processo separado — e devolvendo PARA QUAL giro pensou.

O DEFEITO DE CORRELAÇÃO
-----------------------
As duas filas não tinham identificador. A CENTRAL mandava o pedido, esperava
até 45 segundos e, se não viesse nada, desistia daquela volta. Só que o
cérebro não desiste junto: ele termina de pensar e coloca a resposta na fila
de saída depois.

Na volta seguinte, o `saida.get()` pega essa resposta atrasada no ato — e ela
é aplicada ao giro NOVO. A aposta mostrada na tela foi calculada para o giro
anterior, e nada denuncia isso: é um dicionário bem formado, com números
plausíveis, chegando na hora certa.

Depois de duas quedas assim a fila fica permanentemente uma resposta atrás, e
o software passa a operar inteiro no passado.

A correção é a mais barata que existe: o pedido leva um carimbo, a resposta
devolve o mesmo carimbo, e quem recebe confere. Resposta de outro giro é
descartada em vez de virar aposta.
"""
from __future__ import annotations

import traceback

from ia_modulos import PipelinePerceptivo


def _carimbo(dados: dict) -> dict:
    """O que precisa voltar junto para a resposta ser reconhecível."""
    return {"head_id": (dados or {}).get("head_id"),
            "req_id": (dados or {}).get("req_id")}


def process_cerebro(in_q, out_q, jogo="mega_fire"):
    pipe = PipelinePerceptivo(jogo=jogo)
    while True:
        dados = None
        try:
            dados = in_q.get()
            if dados is None:
                break
            sug = pipe.processar(
                dados.get("nums") or [],
                int(dados.get("ok") or 0),
                int(dados.get("err") or 0),
                settled=dados.get("settled"),
                mults=dados.get("mults"),
                linhas=dados.get("linhas"),
                last_result=dados.get("last_result"),
                active_selection=dados.get("active_selection"),
            )
            if not isinstance(sug, dict):
                sug = {"pad5": [], "msgs": [f"resposta inesperada: {type(sug).__name__}"],
                       "modo": "AGUARDANDO"}
            sug.update(_carimbo(dados))
            out_q.put(sug)
        except Exception as e:
            # o carimbo vai no erro também: senão a volta que estourou fica
            # sem resposta reconhecível e a CENTRAL espera o prazo inteiro à
            # toa, achando que o cérebro ainda está pensando
            erro = {"erro": str(e), "trace": traceback.format_exc(),
                    "pad5": [], "msgs": [str(e)], "modo": "AGUARDANDO"}
            erro.update(_carimbo(dados))
            out_q.put(erro)
