# -*- coding: utf-8 -*-
"""
DE QUAL TEORIA DELE CADA CAÇADOR SAIU.

A COBRANÇA
──────────
    "todas ias devem aprender tudo que eu ditos nestes 3 pdfs"

A auditoria mostrou que 13 vozes decidiam 1 em cada 5 números sem consultar
estudo nenhum -- e entre elas os 25 caçadores de ocorrência, que são
justamente os que procuram vício. Eles nunca tinham lido uma linha dele.

O QUE ESTE ARQUIVO FAZ
──────────────────────
Cada caçador declara qual teoria dele está testando. Não é etiqueta
decorativa: é o que torna o achado auditável, porque passa a existir uma
resposta para "de onde veio essa leitura?" que não seja "o Claude inventou".

E serve para uma coisa mais concreta. Cada formulação do Tratado traz, na
seção 4, o CONTRADITÓRIO -- o teste que derrubaria aquela leitura. Os controles
negativos dos caçadores eu inventei; os dele estão escritos. Quando o texto
integral dos estudos está na pasta, `contraditorio_de()` devolve o dele.

O MAPA
──────
Feito lendo o que cada caçador MEDE e procurando no índice a formulação que
descreve aquela medida. Onde não havia correspondência honesta, ficou vazio --
inventar parentesco seria pior que admitir que o caçador é meu.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent
ARQ_INDICE = RAIZ / "indice_estudos_destilado.json"

# caçador -> (IA do Tratado, faixa de ficha do Compêndio, o que ele mede)
#
# A IA do Tratado dá a formulação por mesa (16 de cada); a faixa do Compêndio
# dá o dossiê que discute o mecanismo. Um caçador pode ter os dois, um só, ou
# -- se eu não achei parentesco honesto -- nenhum.
MAPA: Dict[str, Tuple[str, Optional[Tuple[int, int]], str]] = {
    # o que vem DEPOIS de quê: transição
    "O01_SUCESSOR": ("IA04", (16, 25), "o que costuma vir depois de um valor"),
    "O11_PAR_ORDENADO": ("IA04", (16, 25), "o par ordenado que se repete"),

    # motivos e formas que sobrevivem à mudança
    "O02_FINAIS": ("IA03", (101, 120), "aglomeração por final"),
    "O02F_FAMILIA_FINAL": ("IA03", (101, 120), "família de finais junta"),
    "O09_ESPELHO": ("IA03", (101, 120), "o espelho do número (12/21)"),

    # aglomeração de atributo: sobredispersão da ficha 006
    "O03_DUZIA": ("IA06", (1, 15), "aglomeração por dúzia"),
    "O04_COLUNA": ("IA06", (1, 15), "aglomeração por coluna"),
    "O05_COR": ("IA06", (1, 15), "aglomeração por cor"),
    "O06_PARIDADE": ("IA06", (1, 15), "aglomeração por paridade"),
    "O16_ALTO_BAIXO": ("IA06", (1, 15), "aglomeração por metade"),
    "O17_SEXTO": ("IA06", (1, 15), "aglomeração por sexto"),
    "O18_QUADRA": ("IA06", (1, 15), "aglomeração por quadra"),
    "O20_RAJADA": ("IA06", (41, 50), "rajada — o improvável vem em grupo"),

    # geometria da roda: é onde vício FÍSICO se manifesta
    "O07_SETOR": ("IA08", (301, 400), "setor contíguo do cilindro"),
    "O14_VIES_SETOR": ("IA08", (301, 400), "viés persistente de setor"),
    "O15_FAMILIA_RODA": ("IA08", (301, 400), "voisins, tiers, orphelins"),
    "O08_SALTO": ("IA08", (301, 400), "distância percorrida na roda"),
    "O22_DISTANCIA": ("IA08", (301, 400), "distância entre giros seguidos"),

    # vizinhança como estrutura, não como contagem
    "O12_VIZINHOS": ("IA05", (136, 160), "vizinhos na roda física"),

    # intervalo e renovação — a regra que ele confirmou por conta própria
    "O10_RETORNO": ("IA01", (41, 50), "quanto tempo até voltar"),
    "O22_FRIOS": ("IA01", (41, 50), "os que sumiram há mais tempo"),

    # uniformidade marginal: a ficha 001
    "O13_VIES_NUMERO": ("IA02", (1, 15), "número acima da variação normal"),
    "O19_VIES_FAMILIA": ("IA02", (1, 15), "família acima da variação normal"),

    # surpresa: a anomalia muda a teoria ou só chama atenção?
    "O21_ANOMALIA": ("IA09", (201, 300), "recorrência improvável"),
    "O22_SURPRESA": ("IA09", (201, 300), "o que a crença não previa"),

    # os canários NÃO têm teoria dele, e é de propósito: eles existem para
    # disparar em roda honesta e denunciar que o crivo está frouxo. Amarrá-los
    # a uma teoria dele seria dar respaldo a um detector feito para errar.
    "C90_PRIMO": ("", None, "[canário] controle negativo"),
    "C91_SOMA_DIG": ("", None, "[canário] controle negativo"),
    "C92_MULT3": ("", None, "[canário] controle negativo"),
}

MESAS = {
    "mega_fire": "MEGA FIRE", "lightning": "LIGHTING",
    "crazy_time": "CRAZY TIME", "crazy_time_a": "CRAZY TIME A",
}


def mesa_do(jogo: str) -> str:
    """O nome que o livro dele usa, a partir da chave do software.

    O `dataset_id` que circula no programa nem sempre é a chave limpa -- vem
    com sufixo. Por isso a busca é pelo PREFIXO MAIS LONGO: sem isso,
    `crazy_time_a_seja_la_o_que` casaria com `crazy_time` e a IA citaria a
    formulação da mesa errada, que é pior do que não citar.
    """
    j = str(jogo or "")
    achou = ""
    for chave in MESAS:
        if j.startswith(chave) and len(chave) > len(achou):
            achou = chave
    return MESAS.get(achou, "")

_IDX: Optional[Dict[str, List[dict]]] = None


def _indice() -> Dict[str, List[dict]]:
    global _IDX
    if _IDX is not None:
        return _IDX
    _IDX = {}
    try:
        d = json.loads(ARQ_INDICE.read_text(encoding="utf-8"))
        for _e, corpo in (d.get("estudos") or {}).items():
            for u in corpo.get("unidades") or []:
                if u.get("tipo") == "formulacao":
                    _IDX.setdefault(f"{u.get('mesa','')}|{u.get('ia','')}",
                                    []).append(u)
    except Exception:
        _IDX = {}
    return _IDX


def teoria_de(cacador: str, jogo: str = "lightning") -> Dict[str, str]:
    """A teoria dele que este caçador está testando. Vazio se não houver."""
    ia, faixa, mede = MAPA.get(str(cacador), ("", None, ""))
    out: Dict[str, str] = {"mede": mede}
    if ia:
        fs = sorted(_indice().get(f"{mesa_do(jogo)}|{ia}") or [],
                    key=lambda u: u.get("n", 0))
        if fs:
            u = fs[0]
            out.update(ia=ia, formulacao=str(u.get("n")),
                       familia=str(u.get("familia") or ""),
                       formula=str(u.get("formula") or ""),
                       titulo=str(u.get("titulo") or "").split("—")[0].strip())
    if faixa:
        out["fichas"] = f"{faixa[0]:03d}-{faixa[1]:03d}"
    return out


def texto_teoria(cacador: str, jogo: str = "lightning") -> str:
    """Uma linha em português dizendo de qual teoria dele o caçador saiu."""
    t = teoria_de(cacador, jogo)
    if not t.get("ia") and not t.get("fichas"):
        return ""
    p = []
    if t.get("ia"):
        p.append(f"{t['ia']} formulação #{t['formulacao']} (família {t['familia']})")
    if t.get("fichas"):
        p.append(f"compêndio {t['fichas']}")
    cab = " · ".join(p)
    return f"{cab} — {t['titulo'][:48]}" if t.get("titulo") else cab


def contraditorio_de(cacador: str, jogo: str = "lightning") -> str:
    """O teste que DERRUBARIA esta leitura, escrito por ele.

    Sai da seção 4 da formulação ("Sombra, contraditório e independência"). Só
    existe quando o texto integral dos estudos está na pasta -- o índice
    versionado guarda fórmula e título, não a prosa. Sem ele, devolve vazio e
    o caçador segue com o controle negativo que eu escrevi.
    """
    ia, _fx, _m = MAPA.get(str(cacador), ("", None, ""))
    if not ia:
        return ""
    alvo = mesa_do(jogo)
    for arq in RAIZ.glob("dados_livro_*.json"):
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except Exception:
            continue
        for u in d.get("unidades") or []:
            if (u.get("tipo") == "formulacao" and u.get("ia") == ia
                    and u.get("mesa") == alvo):
                for k, v in u.items():
                    if k.startswith("s4_") and v:
                        return str(v)[:400]
    return ""


def cobertura() -> Dict[str, int]:
    """Quantos caçadores têm teoria dele, e quantos ainda são só meus."""
    com = sum(1 for c, (ia, fx, _m) in MAPA.items() if ia or fx)
    return {"total": len(MAPA), "com_teoria": com, "sem": len(MAPA) - com}


def resumo(jogo: str = "lightning") -> str:
    c = cobertura()
    L = [f"[Caçadores] {c['com_teoria']} de {c['total']} declaram a teoria "
         f"dele que testam"]
    for nome in sorted(MAPA):
        t = texto_teoria(nome, jogo)
        L.append(f"   {nome:<22} {t[:78]}" if t
                 else f"   {nome:<22} — sem teoria dele (controle negativo meu)")
    return "\n".join(L)
