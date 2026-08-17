# -*- coding: utf-8 -*-
"""
FORÇA DOS EIXOS — quanto cada informação vale, medido, não decretado por mim.

O QUE ELE APONTOU
─────────────────
    "o proposito nao é prever de forma boa e acertiva? até a capacidade de
     aprendizado da ia em ver quantidade de pessoas, quantidade de
     multiplicadores, bonus e muitas outras informações é justamente aprender
     para poder ter uma acertividade maior, pois horarios, quantidade de pessoas
     influenciam e muito nas decisoes e na taxa de acertividade"

Ele tem razão, e havia uma incoerência minha em `situacao.py`: eu escrevi

    PESOS_EIXO = {"hora": 1.0, "publico": 1.0, "distintos": 0.6, ...}

e chamei aquilo de "eixos, não regras minhas". Mas o peso É a regra. Decidir que
hora vale 1,0 e repetição vale 0,6 é exatamente eu decretando quanto cada coisa
importa — o oposto de aprender.

Pior: se público influencia muito na mesa dele (ele mediu ao vivo) e eu dei 1,0
igual a tudo, estou DILUINDO o eixo forte no meio dos fracos. A parecença fica
dominada por eixos que não importam, e os momentos "parecidos" que a busca acha
não são parecidos no que conta.

O QUE ESTE ARQUIVO FAZ
──────────────────────
Mede, no histórico dele, quanto cada eixo separa acerto de erro — e devolve isso
como peso. Eixo que separa muito passa a mandar na busca; eixo que não separa
nada encolhe, sem ser excluído (ele não gosta de exclusão, e está certo: eixo
fraco numa mesa pode ser forte na outra).

COMO A SEPARAÇÃO É MEDIDA
─────────────────────────
Para cada eixo, o histórico é dividido nos momentos em que o giro seguinte
PAGOU multiplicador e nos que não pagaram. Se o eixo tem valor sistematicamente
diferente nos dois grupos, ele separa. A medida é a diferença das médias em
unidades de desvio (`d` de Cohen), que é comparável entre eixos de escalas
diferentes — comparar "hora" (0–24) com "regime" (0–1) sem normalizar daria peso
à escala, não à informação.

O CUIDADO QUE NÃO PODE FALTAR
─────────────────────────────
Peso aprendido em cima de pouco dado é peso inventado. Abaixo de
`MIN_PARA_APRENDER` observações em cada grupo, o eixo fica no peso neutro — e o
software diz que ficou. É a mesma regra que ele cobra em todo lugar: com pouca
amostra, calar.

E o peso é limitado a uma faixa. Um eixo com `d` enorme por acaso não pode
zerar todos os outros: aprender não é entregar a decisão ao primeiro eixo com
sorte.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

RAIZ = Path(__file__).resolve().parent.parent


def _arquivo() -> Path:
    """Os pesos aprendidos moram no lar, não na pasta do programa.

    Estes pesos são o resultado de horas de mesa -- é o que a mesa ENSINOU sobre
    o que importa nela. Deixá-los ao lado do executável fazia com que cada versão
    minha jogasse fora o aprendizado e recomeçasse do peso neutro.
    """
    try:
        from NUCLEO import lar as _lar
        return _lar.arquivo("forca_dos_eixos.json")
    except Exception:
        return RAIZ / "Logs" / "forca_dos_eixos.json"

# quantas observações em CADA grupo antes de aprender qualquer coisa
MIN_PARA_APRENDER = 30
# a faixa em que o peso pode andar. 0.25 é "quase não conta"; 2.5 é "manda na
# busca". Fora disso, um eixo sortudo decidiria sozinho.
PESO_MIN, PESO_MAX = 0.25, 2.5

EIXOS = ("hora", "publico", "seca_mult", "ritmo_mult",
         "distintos", "repeticao", "regime")

NEUTRO = {e: 1.0 for e in EIXOS}


def _d_de_cohen(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Separação entre dois grupos, em desvios-padrão.

    Comparável entre eixos de escalas diferentes -- é o ponto: sem isto, "hora"
    (0..24) pesaria mais que "regime" (0..1) só por ser um número maior.
    """
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    s = math.sqrt(((na - 1) * va + (nb - 1) * vb) / max(1, na + nb - 2))
    if s <= 1e-9:
        return None
    return abs(ma - mb) / s


def _valor(m, eixo: str) -> Optional[float]:
    v = getattr(m, eixo, None)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def medir(momentos: Sequence[Any], linhas: Sequence[dict],
          pagou_de) -> Dict[str, Any]:
    """Quanto cada eixo separa o giro que PAGOU do que não pagou.

    `pagou_de` é a função que diz se um giro pagou -- vem de `situacao.py` para
    não haver duas definições de "pagou" no software (duas definições foi como
    o anúncio sumiu do fallback offline).
    """
    grupos: Dict[str, Dict[str, List[float]]] = {
        e: {"pagou": [], "nao": []} for e in EIXOS}
    for m in momentos:
        j = m.i - 1                      # o giro SEGUINTE (recente-primeiro)
        if j < 0 or j >= len(linhas):
            continue
        pagou = pagou_de(linhas[j])[0] > 0
        for e in EIXOS:
            v = _valor(m, e)
            if v is None:
                continue
            grupos[e]["pagou" if pagou else "nao"].append(v)

    pesos: Dict[str, float] = {}
    detalhe: Dict[str, Any] = {}
    for e in EIXOS:
        a, b = grupos[e]["pagou"], grupos[e]["nao"]
        if len(a) < MIN_PARA_APRENDER or len(b) < MIN_PARA_APRENDER:
            pesos[e] = 1.0
            detalhe[e] = {"peso": 1.0, "n_pagou": len(a), "n_nao": len(b),
                          "nota": "amostra pequena — peso neutro"}
            continue
        d = _d_de_cohen(a, b)
        if d is None:
            pesos[e] = 1.0
            detalhe[e] = {"peso": 1.0, "n_pagou": len(a), "n_nao": len(b),
                          "nota": "sem variação — peso neutro"}
            continue
        # d=0 → 0.25 (quase não conta); d=0.5 → ~1.4; d>=1 → teto
        w = max(PESO_MIN, min(PESO_MAX, PESO_MIN + 2.25 * min(1.0, d)))
        pesos[e] = round(w, 3)
        detalhe[e] = {"peso": round(w, 3), "d": round(d, 3),
                      "n_pagou": len(a), "n_nao": len(b),
                      "media_pagou": round(sum(a) / len(a), 3),
                      "media_nao": round(sum(b) / len(b), 3)}
    return {"pesos": pesos, "detalhe": detalhe,
            "aprendeu": any(v.get("d") is not None for v in detalhe.values())}


# ────────────────────────────────────────────────────── memória por mesa
def carregar(jogo: str) -> Dict[str, float]:
    try:
        arq = _arquivo()
        if arq.is_file():
            d = json.loads(arq.read_text(encoding="utf-8")) or {}
            p = (d.get(str(jogo)) or {}).get("pesos")
            if isinstance(p, dict) and p:
                return {e: float(p.get(e, 1.0)) for e in EIXOS}
    except Exception:
        pass
    return dict(NEUTRO)


def gravar(jogo: str, medida: Dict[str, Any]) -> None:
    try:
        arq = _arquivo()
        d = {}
        if arq.is_file():
            d = json.loads(arq.read_text(encoding="utf-8")) or {}
        d[str(jogo)] = medida
        arq.parent.mkdir(parents=True, exist_ok=True)
        tmp = arq.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        import os
        os.replace(tmp, arq)
    except Exception:
        pass


def resumo(jogo: str, medida: Dict[str, Any]) -> List[str]:
    """As linhas para a tela: o que a mesa ENSINOU sobre cada eixo."""
    det = medida.get("detalhe") or {}
    fortes = sorted(((v.get("peso", 1.0), e) for e, v in det.items()
                     if v.get("d") is not None), reverse=True)
    if not fortes:
        n = max((v.get("n_pagou", 0) for v in det.values()), default=0)
        return [f"[Eixos] ainda sem peso aprendido — preciso de "
                f"{MIN_PARA_APRENDER} giros com prêmio e {MIN_PARA_APRENDER} "
                f"sem, em {jogo} (tenho {n} com)"]
    L = [f"[Eixos] o que esta mesa ensinou sobre o que importa:"]
    for w, e in fortes[:4]:
        d = det[e]
        L.append(f"[Eixos]   {e:<11} peso {w:.2f}  (separação d={d['d']:.2f}; "
                 f"quando paga {d['media_pagou']}, quando não {d['media_nao']})")
    fraco = [e for w, e in fortes if w <= PESO_MIN + 0.05]
    if fraco:
        L.append(f"[Eixos]   quase não separa nesta mesa: {', '.join(fraco[:4])}"
                 f" — encolhe, mas não sai")
    return L
