# -*- coding: utf-8 -*-
"""
O CAPTADOR — a máquina cava, ele confirma.

A IDEIA
-------
Cada um é bom numa metade. A máquina varre centenas de relações que ninguém
teria paciência de checar; ele reconhece, olhando a mesa, o que faz sentido e
o que é coincidência. O captador junta as duas: ele traz o que achou e
PERGUNTA — "quando vem X parece vir Y, você já tinha reparado?".

O que ele confirma vira teoria declarada, com autoria dele, e passa a votar.
O que ele recusa vai para uma lista de recusadas e nunca mais é oferecido.

AS TRÊS COISAS QUE ELE PEDIU
----------------------------
    rodar         a varredura é cara, então roda sob demanda (botão) ou de
                  tempos em tempos, nunca a cada giro
    interagir     cada achado tem três respostas: já vi isso · não é nada ·
                  vou observar. A terceira devolve o achado mais tarde, com
                  mais amostra, em vez de forçar decisão sem dado
    não duplicar  três filtros: o que já foi oferecido (mesmo recusado), o
                  que já existe no catálogo, e o que já é regra declarada
                  dele. Nada volta com outra roupa.

O CADERNO
---------
Fica em Logs/captador_<mesa>.json. É a memória do que já foi conversado:
sem ele, a mesma descoberta voltaria toda semana e a conversa nunca andaria.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent.parent
CADERNO = RAIZ / "Logs"

# Quantos achados oferecer de uma vez. Mais que isso vira lista que ninguém lê.
MAX_POR_VEZ = 6
# Abaixo desta razão não vale nem perguntar: é ruído com nome bonito.
MIN_RAZAO = 1.15
# "Vou observar" volta a aparecer só depois de tanto tempo, com mais amostra.
DIAS_PARA_REOFERECER = 1.0


def _arquivo(jogo: str) -> Path:
    return CADERNO / f"captador_{jogo}.json"


def caderno(jogo: str) -> Dict[str, Any]:
    try:
        return json.loads(_arquivo(jogo).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(jogo: str, d: Dict[str, Any]) -> None:
    try:
        CADERNO.mkdir(parents=True, exist_ok=True)
        tmp = _arquivo(jogo).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(_arquivo(jogo))
    except OSError:
        pass


def responder(jogo: str, chave: str, resposta: str, nota: str = "") -> None:
    """Guarda o que ele respondeu: `aceita`, `recusada` ou `observando`."""
    d = caderno(jogo)
    reg = d.get(chave) or {}
    reg["estado"] = resposta
    reg["quando"] = time.time()
    if nota:
        reg["nota"] = nota
    d[chave] = reg
    _gravar(jogo, d)


def aceitas(jogo: str) -> List[dict]:
    """As que ele confirmou — são estas que viram voto."""
    return [dict(v, chave=k) for k, v in caderno(jogo).items()
            if v.get("estado") == "aceita"]


# ───────────────────────────────────────────────────── não duplicar
def _ja_conversado(jogo: str, chave: str) -> bool:
    reg = (caderno(jogo) or {}).get(chave)
    if not reg:
        return False
    if reg.get("estado") == "observando":
        # volta depois, com mais amostra — mas não no mesmo dia
        idade = (time.time() - float(reg.get("quando") or 0)) / 86400.0
        return idade < DIAS_PARA_REOFERECER
    return True          # aceita ou recusada: assunto encerrado


def _ja_no_catalogo(chave: str, descricao: str, catalogo: List[dict]) -> bool:
    """Evita oferecer com outra roupa o que a academia já catalogou."""
    alvo = _normal(descricao)
    for t in catalogo or []:
        if _normal(t.get("descricao")) == alvo:
            return True
        if str(t.get("chave_captador") or "") == chave:
            return True
    return False


def _normal(txt) -> str:
    return " ".join(str(txt or "").lower().split())


def _ja_e_regra_dele(descricao: str) -> bool:
    """O que ele já ensinou não é descoberta — é o ponto de partida."""
    t = _normal(descricao)
    conhecidas = ("mesmo final", "final da mesma família", "família do final",
                  "os dígitos trocados", "mesma dúzia")
    return any(c in t for c in conhecidas)


# ───────────────────────────────────────────────────── o que oferecer
def _de_relacoes(achados: List[dict]) -> List[dict]:
    saida = []
    for a in achados or []:
        p = a.get("p")
        if p is None:                       # nem passou da triagem
            continue
        razao = float(a.get("razao") or 0)
        if razao < MIN_RAZAO:
            continue
        lag = a.get("lag") or a.get("janela") or 1
        chave = f"rel:{a.get('chave')}:{lag}"
        saida.append({
            "chave": chave,
            "titulo": f"{a.get('descricao')} — {lag} giro(s) depois",
            "razao": round(razao, 2),
            "taxa": a.get("taxa"), "acaso": a.get("acaso"),
            "p": p, "n": a.get("n"),
            "pergunta": (f"Quando sai um número, o de {lag} giro(s) depois "
                         f"costuma ter {a.get('descricao')}. "
                         f"Aconteceu {a.get('taxa', 0):.0%} das vezes, contra "
                         f"{a.get('acaso', 0):.0%} de acaso. Você já tinha "
                         f"reparado nisso?"),
            "origem": "relações",
        })
    return saida


def _do_crivo(teorias: List[dict]) -> List[dict]:
    saida = []
    for t in teorias or []:
        c = t.get("crivo") or {}
        razao = float(c.get("razao_melhor") or 0)
        if razao < MIN_RAZAO or not c.get("disparos"):
            continue
        d = c.get("melhor_distancia")
        chave = f"teoria:{t.get('id') or _normal(t.get('descricao'))}:{d}"
        saida.append({
            "chave": chave,
            "titulo": f"{t.get('descricao')} — {d} giro(s) depois",
            "razao": round(razao, 2),
            "taxa": None, "acaso": c.get("acaso"),
            "p": None, "n": c.get("disparos"),
            "pergunta": (f"A academia achou isto: {t.get('descricao')}. "
                         f"Acertou {c.get('acertos_melhor')} de "
                         f"{c.get('disparos')} vezes {d} giro(s) depois, "
                         f"{razao:.2f}x o acaso. Faz sentido para você?"),
            "origem": "academia",
        })
    return saida


def oferecer(jogo: str, achados_relacoes: List[dict] = None,
             teorias_crivo: List[dict] = None, catalogo: List[dict] = None,
             quantos: int = MAX_POR_VEZ) -> List[dict]:
    """O que vale perguntar a ele agora, já sem repetição."""
    candidatos = _de_relacoes(achados_relacoes) + _do_crivo(teorias_crivo)
    vistos = set()
    novos = []
    for c in sorted(candidatos, key=lambda x: -x["razao"]):
        ch = c["chave"]
        if ch in vistos:
            continue
        vistos.add(ch)
        if _ja_conversado(jogo, ch):
            continue
        if _ja_e_regra_dele(c["titulo"]):
            continue
        if _ja_no_catalogo(ch, c["titulo"], catalogo):
            continue
        # O QUE AS AUDITORIAS DELE JÁ SABEM SOBRE ISSO.
        #
        # Ele mandou cinco estudos retrospectivos, um por mesa, com até 56
        # famílias de hipótese já medidas. Um achado que cai numa família já
        # auditada não é descartado — mas ele chega acompanhado do que já se
        # sabe, para a pergunta ser feita de olhos abertos.
        try:
            from academia_autonoma.base_auditoria import veredito
            c["auditoria"] = veredito(jogo, c["titulo"])
        except Exception:
            c["auditoria"] = None
        novos.append(c)
        if len(novos) >= quantos:
            break
    # deixa registrado que foram oferecidos, sem decidir por ele
    d = caderno(jogo)
    for c in novos:
        if c["chave"] not in d:
            d[c["chave"]] = {"estado": "oferecida", "quando": time.time(),
                             "titulo": c["titulo"], "razao": c["razao"]}
    if novos:
        _gravar(jogo, d)
    return novos


def resumo(novos: List[dict], jogo: str) -> str:
    d = caderno(jogo)
    ja = sum(1 for v in d.values() if v.get("estado") in ("aceita", "recusada"))
    if not novos:
        return (f"[Captador] nada novo para perguntar em {jogo} "
                f"({ja} já respondidas, {len(d)} no caderno)")
    L = [f"[Captador] {len(novos)} achados novos em {jogo} "
         f"({ja} já respondidas antes)"]
    for c in novos:
        L.append(f"   {c['titulo'][:52]:<52} {c['razao']:.2f}x  n={c['n']}")
        a = c.get("auditoria") or {}
        if a.get("controle_negativo"):
            L.append("      ⚠ CONTROLE NEGATIVO: esta família tem que dar nada. "
                     "Achado aqui é defeito do caçador, não da mesa "
                     f"({a.get('familia')} {a.get('nome')})")
        elif a.get("conhecida"):
            L.append(f"      auditoria {a['familia']} {a['nome']} "
                     f"[{a['estado'].lower()}]: {a['conduta']}")
    return "\n".join(L)
