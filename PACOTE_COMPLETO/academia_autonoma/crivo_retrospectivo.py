# -*- coding: utf-8 -*-
"""
O crivo retrospectivo — toda teoria é medida no histórico antes de valer o dia.

REGRA DELE, 15/08
-----------------
    "Acho que todas teorias formadas devem passar pelo crivo da análise
     retrospectiva das informações de histórico dos sites. Aquelas que acertam
     cerca de duas ou três vezes merecem ser usadas no dia. E o consenso quem
     diz os números e não as teorias puramente."

Três coisas, e as três mudam o desenho:

1. TODA teoria passa pelo crivo. Não é seleção de elite — é um retrato de como
   cada uma se saiu no histórico que os sites já entregaram.

2. A barra é BAIXA de propósito: acertar umas duas ou três vezes basta para
   entrar no dia. Não é a barra de "provada" — é a de "mostrou que acontece".
   Teoria que nunca aconteceu no histórico inteiro não tem o que dizer hoje.

3. Quem decide o número final é o CONSENSO, não a teoria. Por isso a barra
   pode ser baixa sem virar irresponsabilidade: uma teoria fraca sozinha não
   manda em nada, ela só acrescenta um voto. O cruzamento é o filtro de
   verdade, e ele acontece depois — não antes, cortando quem podia contribuir.

POR QUE ISSO NÃO É AFROUXAR A RÉGUA
-----------------------------------
A régua continua existindo e continua medindo. O que muda é ONDE ela é
aplicada: ela deixa de ser um cadeado na porta de entrada de cada teoria e
passa a ser o termômetro do resultado do consenso. Medir e barrar são coisas
diferentes, e eu vinha misturando as duas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .dsl_hipoteses import eval_cond, pred_candidatos

# Quantos acertos no histórico bastam para a teoria valer o dia.
# "Aquelas que acertam cerca de duas ou três vezes merecem ser usadas no dia."
MIN_ACERTOS_DIA = 2
# Distâncias medidas: ele avisou que não vem sempre no giro seguinte.
DISTANCIAS = (1, 2, 3, 4, 5)
K_ALVOS = 7
MIN_HIST = 120


def _cronologico(historico: List[str]) -> List[str]:
    """A varredura anda do passado para o futuro; a captura entrega ao contrário."""
    return list(reversed([str(x) for x in (historico or [])]))


def medir(teoria: dict, historico: List[str], dominio: List[str],
          distancias=DISTANCIAS) -> Dict[str, Any]:
    """Quantas vezes esta teoria disparou no histórico, e quantas acertou.

    Para cada momento em que a condição da teoria valia, pergunta-se o que ela
    teria apontado e se aquilo saiu em cada uma das distâncias. Não se procura
    a melhor distância para depois vendê-la como se fosse a única — todas são
    devolvidas, e quem olha vê o perfil inteiro.
    """
    cron = _cronologico(historico)
    if len(cron) < MIN_HIST:
        return {"disparos": 0, "por_distancia": {}, "apta": False,
                "motivo": "histórico curto"}
    expr = teoria.get("expr") or {}
    if not expr:
        return {"disparos": 0, "por_distancia": {}, "apta": False,
                "motivo": "teoria sem condição"}

    maior = max(distancias)
    disparos = 0
    acertos = {d: 0 for d in distancias}
    soma_k = 0
    for i in range(MIN_HIST, len(cron) - maior):
        # a condição é avaliada com o histórico ATÉ ali, do mais novo primeiro
        janela = cron[:i + 1][::-1]
        try:
            if not eval_cond(expr, janela):
                continue
            alvos = {str(x) for x in
                     (pred_candidatos(expr, janela, dominio, k=K_ALVOS) or [])}
        except Exception:
            continue
        if not alvos:
            continue
        disparos += 1
        soma_k += len(alvos)
        for d in distancias:
            if cron[i + d] in alvos:
                acertos[d] += 1

    if not disparos:
        return {"disparos": 0, "por_distancia": {}, "apta": False,
                "motivo": "nunca disparou no histórico"}

    k_medio = soma_k / disparos
    n_classes = max(len(dominio), 1)
    acaso = k_medio / n_classes
    por_d = {}
    for d in distancias:
        taxa = acertos[d] / disparos
        por_d[d] = {"acertos": acertos[d], "taxa": round(taxa, 4),
                    "razao": round(taxa / acaso, 3) if acaso else 0.0}

    # A melhor distância é a de melhor RAZÃO, não a de mais acertos brutos.
    # Uma teoria que dispara 1444 vezes e acerta 44 (1,13x) tem mais acertos
    # que uma que dispara 50 e acerta 8 (1,97x) — e é muito pior. Ordenar por
    # acerto bruto poria a fraca na frente.
    melhor = max(distancias, key=lambda d: por_d[d]["razao"])
    apta = acertos[melhor] >= MIN_ACERTOS_DIA

    # Peso do voto: o quanto ela passou do acaso, limitado para que uma teoria
    # com amostra minúscula não domine a votação por sorte. Nada é excluído —
    # quem foi pior que o acaso ainda vota, só que fraco.
    margem = max(0.0, por_d[melhor]["razao"] - 1.0)
    confianca = disparos / (disparos + 30.0)
    peso = round(1.0 + min(1.5, margem) * confianca, 3)
    return {
        "disparos": disparos, "k_medio": round(k_medio, 2),
        "acaso": round(acaso, 4), "por_distancia": por_d,
        "melhor_distancia": melhor, "acertos_melhor": acertos[melhor],
        "razao_melhor": por_d[melhor]["razao"], "peso": peso,
        "apta": apta,
        "motivo": (f"{acertos[melhor]} acertos em {disparos} disparos "
                   f"(distância +{melhor})") if apta else
                  (f"só {acertos[melhor]} acerto(s) em {disparos} disparos"),
    }


def peneirar(teorias: List[dict], historico: List[str], dominio: List[str],
             min_acertos: int = MIN_ACERTOS_DIA) -> Dict[str, Any]:
    """Passa o crivo em todas as teorias e diz quais entram no dia.

    Nenhuma é apagada nem rebaixada: as que não passam apenas não votam hoje,
    e voltam a ser medidas amanhã, quando o histórico for outro.
    """
    aptas, fora = [], []
    for t in teorias or []:
        r = medir(t, historico, dominio)
        t["crivo"] = r
        if r.get("apta") and r.get("acertos_melhor", 0) >= min_acertos:
            aptas.append(t)
        else:
            fora.append(t)
    # ordena por RAZÃO: quem mais passou do acaso vem na frente
    aptas.sort(key=lambda t: -(t.get("crivo") or {}).get("razao_melhor", 0))
    return {"aptas": aptas, "fora": fora,
            "total": len(teorias or []), "n_aptas": len(aptas)}


def resumo(r: Dict[str, Any], quantas: int = 6) -> str:
    if not r or not r.get("total"):
        return "[Crivo] nenhuma teoria para peneirar"
    L = [f"[Crivo] {r['n_aptas']} de {r['total']} teorias valem o dia "
         f"(bastam {MIN_ACERTOS_DIA} acertos no histórico)"]
    for t in (r.get("aptas") or [])[:quantas]:
        c = t.get("crivo") or {}
        d = c.get("melhor_distancia")
        pd = (c.get("por_distancia") or {}).get(d) or {}
        L.append(f"   {str(t.get('descricao'))[:38]:<38} "
                 f"+{d} giro(s)  {c.get('acertos_melhor')}/{c.get('disparos'):<5} "
                 f"{pd.get('razao', 0):.2f}x  peso {c.get('peso', 1):.2f}")
    if not r.get("aptas"):
        L.append("   nenhuma disparou o bastante no histórico ainda")
    return "\n".join(L)
