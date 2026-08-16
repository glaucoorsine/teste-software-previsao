# -*- coding: utf-8 -*-
import traceback
from ia_modulos import PipelinePerceptivo

def process_cerebro(in_q, out_q, jogo="mega_fire"):
    pipe = PipelinePerceptivo(jogo=jogo)
    while True:
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
            out_q.put(sug)
        except Exception as e:
            out_q.put({"erro": str(e), "trace": traceback.format_exc(), "pad5": [], "msgs": [str(e)], "modo": "AGUARDANDO"})
