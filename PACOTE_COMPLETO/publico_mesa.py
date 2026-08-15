# -*- coding: utf-8 -*-
"""
PÚBLICO DA MESA — quanta gente está jogando, e o que isso significa.

O QUE ELE PEDIU
---------------
    "crie métricas do quantitativo de pessoas que as api fornecem
     mínimo, não jogável
     médio, talvez jogar
     número alto, bom para jogar"

E o porquê, que ele já tinha dado:

    "normalmente quando o volume maior de pessoas online, mega acima de 800
     por exemplo, crazy acima de 13 mil, mais fácil a previsão e os
     multiplicadores"

AS ÂNCORAS SÃO DELE, O MEIO SERIA CHUTE MEU
-------------------------------------------
Ele deu o ponto de "cheia": 800 na roleta, 13 mil no Crazy Time. Esse número
vem de meses olhando a mesa e vale mais que qualquer estimativa minha.

O que ele não deu foi onde termina o "vazio". Eu poderia inventar, e seria
palpite com cara de número. Então o começo é uma proporção das âncoras dele —
e assim que houver observação suficiente, as faixas se recalibram sozinhas
pelos TERCIS do que aquela mesa realmente mostrou. A mesa passa a definir o
que é vazio e cheio nela mesma, em vez de eu decidir de fora.

O QUE A FAIXA FAZ
-----------------
Ela não some com a previsão: informa. A tela mostra em que faixa a mesa está,
a autópsia grava a faixa junto de cada janela — e é isso que vai responder, com
número, se a percepção dele se sustenta. Barrar por conta própria seria
transformar a percepção dele em regra antes de ela ter sido medida.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent
HISTORICO = RAIZ / "Logs" / "publico_mesa.json"

# O ponto de "cheia" é dele. O de "vazia" começa como uma fração dessa âncora
# e é substituído por dados assim que houver.
ANCORAS: Dict[str, Dict[str, int]] = {
    "lightning":    {"alto": 800, "medio": 300},
    "mega_fire":    {"alto": 800, "medio": 300},
    "immersive":    {"alto": 800, "medio": 300},
    "crazy_time":   {"alto": 13000, "medio": 6000},
    "crazy_time_a": {"alto": 13000, "medio": 6000},
}
PADRAO = {"alto": 800, "medio": 300}

# Abaixo disto as faixas continuam sendo as âncoras dele: pouca observação
# recalibrada vira ruído com aparência de precisão.
MIN_PARA_CALIBRAR = 40

FAIXAS = ("vazia", "media", "cheia")
LEITURA = {
    "vazia": ("mesa vazia", "não vale jogar"),
    "media": ("mesa média", "talvez jogar"),
    "cheia": ("mesa cheia", "bom para jogar"),
}
# Como ele pediu para aparecer no celular: "pessoas ruim, médio, bom".
# Aviso no celular é lido de relance, e "mesa vazia — não vale jogar" ocupa
# uma linha inteira para dizer o que uma palavra dele já dizia.
CURTO = {"vazia": "ruim", "media": "médio", "cheia": "bom"}


def _ler() -> Dict[str, Any]:
    try:
        return json.loads(HISTORICO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(d: Dict[str, Any]) -> None:
    try:
        HISTORICO.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORICO.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(HISTORICO)
    except OSError:
        pass


def observar(jogo: str, jogadores: int, maximo: int = 500) -> None:
    """Guarda mais uma leitura do público desta mesa."""
    if not jogadores or jogadores <= 0:
        return
    d = _ler()
    lista = d.get(jogo) or []
    lista.append({"n": int(jogadores), "quando": time.time()})
    d[jogo] = lista[-maximo:]
    _gravar(d)


def limiares(jogo: str) -> Dict[str, Any]:
    """Onde ficam as fronteiras desta mesa, e de onde elas vieram."""
    base = ANCORAS.get(jogo, PADRAO)
    obs = [x.get("n") for x in (_ler().get(jogo) or []) if x.get("n")]
    if len(obs) < MIN_PARA_CALIBRAR:
        return {"medio": base["medio"], "alto": base["alto"],
                "origem": "âncoras dele", "n_obs": len(obs)}
    ordenado = sorted(obs)
    n = len(ordenado)
    # tercis: um terço da vida da mesa em cada faixa
    medio = ordenado[n // 3]
    alto = ordenado[(2 * n) // 3]
    if alto <= medio:                      # mesa sem variação: mantém a âncora
        return {"medio": base["medio"], "alto": base["alto"],
                "origem": "âncoras dele (mesa sem variação)", "n_obs": n}
    return {"medio": int(medio), "alto": int(alto),
            "origem": f"tercis de {n} leituras desta mesa", "n_obs": n}


def classificar(jogo: str, jogadores: Optional[int]) -> Dict[str, Any]:
    """Em que faixa a mesa está agora."""
    lim = limiares(jogo)
    if not jogadores:
        return {"faixa": None, "rotulo": "público desconhecido",
                "conselho": "sem dado desta mesa agora", **lim}
    if jogadores >= lim["alto"]:
        faixa = "cheia"
    elif jogadores >= lim["medio"]:
        faixa = "media"
    else:
        faixa = "vazia"
    rotulo, conselho = LEITURA[faixa]
    return {"faixa": faixa, "rotulo": rotulo, "conselho": conselho,
            "jogadores": int(jogadores), **lim}


def texto(jogo: str, jogadores: Optional[int]) -> str:
    c = classificar(jogo, jogadores)
    if not c.get("faixa"):
        return c["rotulo"]
    return (f"{c['jogadores']} pessoas · {c['rotulo']} — {c['conselho']}  "
            f"(médio ≥{c['medio']} · cheia ≥{c['alto']}, {c['origem']})")


def texto_curto(jogo: str, jogadores: Optional[int]) -> str:
    """Uma linha para o aviso do celular. Vazio quando não há leitura."""
    c = classificar(jogo, jogadores)
    if not c.get("faixa"):
        return ""
    return f"pessoas: {c['jogadores']} — {CURTO[c['faixa']]}"


def resumo(jogos: List[str] = None) -> str:
    jogos = jogos or list(ANCORAS)
    d = _ler()
    L = ["[Público] faixas por mesa"]
    for j in jogos:
        obs = [x.get("n") for x in (d.get(j) or []) if x.get("n")]
        lim = limiares(j)
        atual = obs[-1] if obs else None
        c = classificar(j, atual)
        L.append(f"   {j:<13} "
                 + (f"{atual:>6} agora · {c['rotulo']:<11}" if atual
                    else f"{'—':>6}          {'sem leitura':<11}")
                 + f" · médio ≥{lim['medio']} · cheia ≥{lim['alto']}"
                 + f" ({lim['n_obs']} leituras)")
    return "\n".join(L)
