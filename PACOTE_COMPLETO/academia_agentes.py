# -*- coding: utf-8 -*-
"""ADAPTADOR completo → academia_autonoma (sem estado/ciclo próprios)."""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import time

from academia_autonoma.agentes_descoberta import AGENTES
from academia_autonoma.catalogo_persistente import listar, count, get
from academia_autonoma.ciclo_academia import ciclo as ciclo_academia
from academia_autonoma.tribunal_revisao import (
    snapshot_tribunal, TRIBUNAL_AGENTES, reavaliar_descartadas,
    listar_descartadas, ciclo_tribunal,
)
from academia_autonoma.paths_dados import subdir
from academia_autonoma.dsl_hipoteses import eval_cond, pred_candidatos, legivel


def _evidencia_sombra(teoria: dict) -> dict:
    """Fallback: recalcula a evidência da sombra se a teoria persistida ainda
    não tiver o campo (catálogo gravado por versão anterior)."""
    try:
        from academia_autonoma.meta_supervisora import avaliar_sombra
        return avaliar_sombra(teoria)
    except Exception:
        return {}

PROTOCOLO = "academia-2026.08.10-v33-unica"

_FEED: Dict[str, List[dict]] = {}


def _peso_evidencia(n: int, taxa, baseline: float, validada: bool) -> float:
    """
    Quanto vale o voto desta teoria no consenso.

    A evidência é CONTÍNUA, não um carimbo. Duas coisas a compõem:

      - a margem: quanto a teoria bate o baseline (taxa/baseline - 1)
      - a confiança: quantas ativações sustentam essa margem

    A confiança cresce como n/(n+30): com 8 ativações vale 0,21; com 30 vale
    0,50; com 120 vale 0,80. O 30 é o ponto em que a evidência passa a valer
    metade — escolhido porque é onde a barra do ic90 começa a admitir efeitos
    de 1,7x, ou seja, onde a medida deixa de ser ruído puro.

    Uma teoria já validada ganha voto cheio (1,0 de confiança), porque ela
    passou pelo ic90 contra o baseline, que é bem mais duro que isto.

    O teto de 1,0 na margem impede que uma teoria com 3 acertos em 8 (que
    marca 2x) grite mais alto que uma com 120 ativações a 1,3x.
    """
    try:
        t = float(taxa)
    except (TypeError, ValueError):
        return 0.0
    if baseline <= 0:
        return 0.0
    margem = max(0.0, min(1.0, t / baseline - 1.0))
    confianca = 1.0 if validada else (n / (n + 30.0))
    return round(margem * confianca, 4)


def _feed_row(jogo: str, agente: str, etapa: str, acao: str, resultado: str = "", proximo: str = "", amostra: int = 0) -> dict:
    return {
        "horario": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "jogo": jogo,
        "agente": agente,
        "etapa": etapa,
        "amostra": amostra,
        "acao": acao,
        "resultado": resultado,
        "proximo": proximo,
    }


def _push_feed(jogo: str, **kwargs):
    row = _feed_row(jogo, **kwargs) if "agente" in kwargs else None
    if row is None:
        row = _feed_row(jogo, "SYSTEM", "info", str(kwargs.get("msg", "")), "", "", 0)
    _FEED.setdefault(jogo, []).append(row)
    _FEED[jogo] = _FEED[jogo][-300:]


class _AcademiaProxy:
    def __init__(self, conjunto: str):
        self.conjunto = conjunto
        self.id = f"AC:{conjunto}"

    def ciclo(self, historico, settled=None, mults=None):
        out = ciclo_academia(self.conjunto, historico, settled=settled, mults=mults)
        for m in (out.get("msgs") or [])[-40:]:
            ms = str(m)
            if "[Tribunal]" in ms:
                agente = "TRIBUNAL"
                etapa = "julgamento"
            elif "[Crítico" in ms:
                agente = "CRITICO"
                etapa = "critica"
            elif "[META]" in ms:
                agente = "META"
                etapa = "decisao"
            elif "[Reformuladores]" in ms:
                agente = "REFORMULADORES"
                etapa = "variante"
            else:
                agente = "CICLO"
                etapa = "processamento"
            _push_feed(self.conjunto, agente=agente, etapa=etapa, acao="msg", resultado=ms[:140])
        # detalha votos do último julgamento no feed
        try:
            tri = snapshot_tribunal(self.conjunto)
            for u in (tri.get("ultimos") or [])[-3:]:
                _push_feed(
                    self.conjunto,
                    agente="TRIBUNAL",
                    etapa="veredito",
                    acao=str(u.get("veredito")),
                    resultado=str(u.get("motivo") or "")[:120],
                    proximo=str(u.get("teoria_id") or "")[:40],
                    amostra=int(((u.get("janela") or {}).get("n") or 0)),
                )
                for v in u.get("votos") or []:
                    _push_feed(
                        self.conjunto,
                        agente=v.get("id") or "T?",
                        etapa="voto",
                        acao=str(v.get("voto")),
                        resultado=str(v.get("motivo") or "")[:100],
                        amostra=int(((u.get("janela") or {}).get("n") or 0)),
                    )
        except Exception:
            pass
        return out

    def chat(self, agente_id: str, pergunta: str) -> str:
        teor = listar(self.conjunto)
        por = {}
        for t in teor:
            e = t.get("estado") or "?"
            por[e] = por.get(e, 0) + 1
        do_agente = [t for t in teor if t.get("autor") == agente_id][:5]
        linhas = [
            f"PROTOCOLO={PROTOCOLO}",
            f"conjunto={self.conjunto} agente={agente_id}",
            f"pergunta={pergunta}",
            f"catalogo total={len(teor)} estados={por}",
        ]
        for t in do_agente:
            p = t.get("prospectivo") or {}
            linhas.append(
                f"- {t.get('descricao')}: estado={t.get('estado')} "
                f"n_prosp={p.get('n')} taxa={p.get('taxa')} ativ={t.get('ativacao')}"
            )
        if not do_agente:
            linhas.append("(nenhuma hipótese deste autor no catálogo)")
        # se for juiz do tribunal, mostra último voto
        if str(agente_id).startswith("T") and "_" in str(agente_id):
            tri = snapshot_tribunal(self.conjunto)
            linhas.append(f"regra_tribunal={tri.get('regra')} julgamentos={tri.get('n_julgamentos')}")
            for a in tri.get("agentes") or []:
                if a.get("id") == agente_id:
                    linhas.append(f"voto_atual={a.get('estado')} motivo={a.get('ultima_descoberta')}")
            for u in (tri.get("ultimos") or [])[-3:]:
                linhas.append(f"veredito {u.get('veredito')} | {u.get('motivo')}")
        _push_feed(
            self.conjunto,
            agente=agente_id,
            etapa="chat",
            acao="consulta",
            resultado="ok",
            proximo="aguardar",
            amostra=len(teor),
        )
        return "\n".join(linhas)

    def conhecimento_validado_para_motor(self, hist: List[str] = None, dominio: List[str] = None) -> List[dict]:
        """Traduz o contrato da academia (expr/descricao) pro formato que o motor
        (ia_modulos.py) consome (nums/agente/hipotese). "nums" só é preenchido
        quando a teoria está ativa no contexto atual (hist) — teoria validada mas
        fora de contexto não deve empurrar candidatos pro consenso."""
        out = []
        for t in listar(self.conjunto):
            estado = str(t.get("estado", ""))
            _p = t.get("prospectivo") or {}
            _n = int(_p.get("n") or 0)
            _taxa = _p.get("taxa")
            # QUEM PODE VOTAR — a mudança que fez o cruzamento existir.
            #
            # Antes: só teoria com estado "validada*". Resultado medido nos
            # giros reais do operador: `0 teorias (de 0 validadas)` em TODOS os
            # ciclos, para sempre. O consenso cruzava só padrões, e a tese do
            # operador ("as IAs chegam num consenso") nunca chegou a rodar.
            #
            # A causa não era bug: era a barra chegar cedo demais. Para validar
            # é preciso ic90_low > baseline (18,9%), e com n=8 isso exige 50%
            # de acerto — 2,65x o acaso. Vício de roleta real é 1,2x a 1,4x;
            # esses precisam de 67 a 267 ativações. Ou seja, com o corte binário
            # nenhuma teoria verdadeira de tamanho realista jamais votaria.
            #
            # Agora vota também quem está ACUMULANDO com sinal positivo, e o
            # peso do voto é proporcional à evidência (ver `peso_evidencia`).
            # Teoria fraca entra com voto quase nulo; teoria provada entra com
            # voto cheio. Isso não afrouxa nada: quem decide se o número sai é
            # o consenso, e o consenso pesa. O que muda é que a evidência passa
            # a ser contínua em vez de um carimbo que nunca vem.
            validada = estado.startswith("validada")
            descartada = estado in ("descartada_pelo_tribunal", "arquivada")
            promissora = (_n >= 8 and _taxa is not None
                          and float(_taxa) > float(_p.get("baseline") or 0.189))
            if descartada or not (validada or promissora):
                continue
            expr = t.get("expr") or {}
            nums: List[Any] = []
            if hist and eval_cond(expr, hist):
                nums = pred_candidatos(expr, hist, dominio or [], k=8)
            out.append({
                "id": t.get("id"),
                "descricao": t.get("descricao"),
                "expr": expr,
                "estado": t.get("estado"),
                "ativacao": t.get("ativacao"),
                "n_prosp": (t.get("prospectivo") or {}).get("n"),
                "taxa": (t.get("prospectivo") or {}).get("taxa"),
                "agente": t.get("autor"),
                "hipotese": t.get("descricao") or legivel(expr),
                "nums": nums,  # vazio quando o contexto atual não ativa a teoria
                # evidência da sombra ao vivo — o motor usa para pesar o voto
                # desta teoria no consenso (teoria mais provada, voto maior).
                "evidencia_sombra": t.get("evidencia_sombra") or _evidencia_sombra(t),
                "validada": validada,
                "peso_evidencia": _peso_evidencia(_n, _taxa,
                                                  float(_p.get("baseline") or 0.189),
                                                  validada),
            })
        return out


    def reavaliar_descartadas_cmd(self, historico, settled=None):
        from academia_autonoma.schema_eventos import DOMAIN_BY_DATASET, ROULETTE_DOMAIN
        from academia_autonoma.catalogo_persistente import listar, merge
        hist = [str(x) for x in (historico or [])]
        dom = [str(x) for x in DOMAIN_BY_DATASET.get(self.conjunto, ROULETTE_DOMAIN)]
        out = reavaliar_descartadas(self.conjunto, hist, dom, listar(self.conjunto), merge_fn=merge)
        for m in out.get("msgs") or []:
            _push_feed(self.conjunto, agente="TRIBUNAL", etapa="reavaliacao_manual",
                       acao="cmd", resultado=str(m)[:140])
        return out

    def tribunal_agora(self, historico, settled=None):
        from academia_autonoma.schema_eventos import DOMAIN_BY_DATASET, ROULETTE_DOMAIN
        from academia_autonoma.catalogo_persistente import listar, merge
        hist = [str(x) for x in (historico or [])]
        dom = [str(x) for x in DOMAIN_BY_DATASET.get(self.conjunto, ROULETTE_DOMAIN)]
        out = ciclo_tribunal(self.conjunto, hist, dom, listar(self.conjunto), merge_fn=merge, max_julgamentos=15)
        for m in out.get("msgs") or []:
            _push_feed(self.conjunto, agente="TRIBUNAL", etapa="julgamento_manual",
                       acao="cmd", resultado=str(m)[:140])
        return out

    def estado(self) -> dict:
        return {
            "id": self.id,
            "conjunto": self.conjunto,
            "estado": "proxy",
            "n_teorias": count(self.conjunto),
            "protocolo": PROTOCOLO,
        }


def get_academia(conjunto: str) -> _AcademiaProxy:
    return _AcademiaProxy(conjunto)


def feed_tail(conjunto: str, n: int = 50) -> List[dict]:
    rows: List[dict] = []
    try:
        p = subdir("bus") / f"{conjunto}_bus.jsonl"
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines()[-n:]:
                try:
                    m = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows.append({
                    "horario": m.get("criada_em") or m.get("horario") or "",
                    "jogo": m.get("dataset_id") or conjunto,
                    "agente": m.get("origem") or "BUS",
                    "etapa": m.get("tipo") or "bus",
                    "amostra": (m.get("payload") or {}).get("n") or 0,
                    "acao": m.get("status") or "msg",
                    "resultado": str((m.get("payload") or {}).get("msg") or m.get("tipo") or "")[:80],
                    "proximo": m.get("destino") or "",
                })
    except OSError as e:
        _push_feed(conjunto, agente="FEED", etapa="erro", acao="read", resultado=str(e))
    mem = list(_FEED.get(conjunto, []))
    if not rows:
        rows = mem
    else:
        rows = rows + mem
    # normaliza campos
    out = []
    for r in rows[-n:]:
        out.append({
            "horario": r.get("horario") or "",
            "jogo": r.get("jogo") or conjunto,
            "agente": r.get("agente") or "?",
            "etapa": r.get("etapa") or "?",
            "amostra": r.get("amostra") or 0,
            "acao": r.get("acao") or "",
            "resultado": r.get("resultado") or "",
            "proximo": r.get("proximo") or "",
        })
    return out


def snapshot_somente_leitura(conjunto: str) -> dict:
    """Snapshot para a Central: pesquisadores + META + CRÍTICO + TRIBUNAL."""
    teor = listar(conjunto)
    por = {}
    for t in teor:
        e = t.get("estado") or "?"
        por[e] = por.get(e, 0) + 1
    agentes = []
    for a in AGENTES:
        aid = getattr(a, "id", None) or getattr(a, "nome", None) or str(a)
        nome = getattr(a, "nome", None) or aid
        do_a = [t for t in teor if t.get("autor") == aid]
        agentes.append({
            "id": aid,
            "nome": nome,
            "conjunto": conjunto,
            "estado": "ativo" if do_a else "idle",
            "tarefa": "descoberta",
            "amostra": len(do_a),
            "modelo": "dsl",
            "duracao_ms": 0,
            "ultima_descoberta": (do_a[0].get("descricao") if do_a else "—"),
            "confianca": 0.5,
            "tipo": "PESQUISADOR",
        })
    tri = snapshot_tribunal(conjunto)
    return {
        "agentes": agentes,
        "tribunal": tri,
        "meta": {
            "id": "META_SUPERVISOR",
            "estado": "coordenando",
            "tarefa": "promover/rebaixar",
            "ultima_descoberta": f"estados={por}",
        },
        "critico": {
            "id": "CRITICO",
            "estado": "observacional",
            "tarefa": "sinal matemático (não lixeira)",
            "ultima_descoberta": "p-valor=sinal",
        },
        "biblioteca": {
            "validadas": por.get("validada_dormente", 0) + por.get("validada_ativa", 0),
            "em_teste": por.get("em_teste", 0) + por.get("em_observacao_viva", 0) + por.get("em_revisao_tribunal", 0),
            "rejeitadas": por.get("rejeitada", 0) + por.get("descartada_pelo_tribunal", 0),
            "por_estado": por,
        },
        "monitor": {},
        "protocolo": PROTOCOLO,
        "feed_hint": "Tribunal + ciclo gravam no feed em memória",
    }


def ciclo(*a, **k):
    return ciclo_academia(*a, **k)


# aliases no módulo para quem importa de academia_agentes
def conhecimento_validado_para_motor(conjunto: str, hist: List[str] = None, dominio: List[str] = None) -> List[dict]:
    return get_academia(conjunto).conhecimento_validado_para_motor(hist=hist, dominio=dominio)
