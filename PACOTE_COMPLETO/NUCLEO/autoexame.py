# -*- coding: utf-8 -*-
"""
AUTOEXAME — a inteligência revendo os próprios atos, teoria por teoria.

O QUE ELE PEDIU, NAS PALAVRAS DELE
──────────────────────────────────
    "essa super inteligência analítica ela tem que rever os próprios atos. Eu
     estou acertando muito, estou errando muito, porque eu acertei muito, será
     que dá pra ficar usando isso aqui mais vezes? Porque eu errei muito, será
     que foi questão de momento? Será que foi questão de quantidade de pessoas?
     Será, o que que foi que eu errei demais? Será que eu usei corretamente a
     teoria?"

São quatro perguntas distintas, e cada uma tem uma resposta diferente:

    "acertei muito ou errei muito?"        → taxa contra o acaso da MESMA aposta
    "dá pra usar isso mais vezes?"         → a taxa sobrevive ao tamanho da amostra?
    "foi momento? foi quantidade de pessoas?" → em QUAL contexto ela erra
    "usei corretamente a teoria?"          → ela foi usada quando devia?

O QUE O SEMÁFORO JÁ FAZIA E NÃO BASTAVA
───────────────────────────────────────
A autocrítica que eu havia escrito olhava o placar GERAL: "últimas 20 janelas,
35% contra acaso 27%". Isso responde "errei muito?" e para aí. Não diz QUAL
teoria errou, nem em que momento, e portanto não permite fazer nada diferente na
volta seguinte -- que é justamente o que ele quer ("e se usar agora, e tomar
decisões inteligentes").

Aqui a conta é por teoria, e o diagnóstico é por eixo de contexto.

COMO O DIAGNÓSTICO DO ERRO É FEITO
──────────────────────────────────
Para cada teoria, as janelas em que ela votou se dividem em acertos e erros. Para
cada eixo do contexto gravado na hora (público, seca, multiplicados em 500,
magnitude, hora), mede-se o quanto o eixo SEPARA os acertos dos erros dela --
`d` de Cohen, comparável entre eixos de escalas diferentes.

Se o público separa os acertos dos erros de uma teoria, a resposta à pergunta
dele é sim: foi questão de quantidade de pessoas, e o número está ali. Se não
separa, a resposta é não -- e não inventar um culpado é parte do trabalho.

O QUE IMPEDE ISTO DE VIRAR HISTÓRIA BONITA
──────────────────────────────────────────
Com poucas janelas, qualquer eixo "separa" por sorteio, e o diagnóstico viraria
narrativa: sempre haveria um culpado plausível. Então:

    MIN_JANELAS       janelas fechadas antes de dizer qualquer coisa da teoria
    MIN_POR_LADO      acertos E erros mínimos antes de diagnosticar contexto
    D_MINIMO          separação mínima para o eixo ser apontado como causa

Abaixo disso o autoexame diz que não sabe. "Não sei ainda" é uma resposta útil;
um culpado inventado não é.

E O ACASO DA MESMA APOSTA
─────────────────────────
A taxa de uma teoria só significa algo contra o acaso da aposta que ELA fez. Uma
teoria que aponta 10 números acerta mais que uma que aponta 3 sem ser melhor.
O acaso vem de `k/n_classes` da própria janela -- é a régua dele, e comparar
apostas de tamanhos diferentes sem ela é a fraude que ele mesmo apontou.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

# janelas fechadas da teoria antes de falar dela
MIN_JANELAS = 12
# acertos E erros mínimos antes de procurar causa no contexto
MIN_POR_LADO = 5
# separação mínima para apontar um eixo como causa
def _ajuste(nome: str, padrao: float) -> float:
    try:
        from NUCLEO import automelhoria
        return automelhoria.valor(nome, padrao)
    except Exception:
        return padrao


D_MINIMO = _ajuste("autoexame.D_MINIMO", 0.45)
# razão contra o acaso a partir da qual "dá para usar mais vezes"
RAZAO_BOA = 1.20
RAZAO_RUIM = 0.85

# os eixos do contexto que podem ser causa, e como cada um se chama em português
EIXOS = {
    "publico": "quantidade de pessoas",
    "seca": "giros sem prêmio",
    "seca_quantil": "quão longa estava a seca",
    "mult_em_500": "multiplicados nas últimas 500",
    "posto_magnitude": "magnitude dos prêmios recentes",
    "em_hora": "hora do dia",
    "razao_parecidos": "o que os momentos parecidos diziam",
    "n_motivos": "quantas razões medidas havia",
}


def _d_de_cohen(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Separação entre dois grupos em desvios-padrão, com sinal.

    Positivo quer dizer que o eixo é MAIOR nos acertos. O sinal importa aqui: a
    pergunta dele não é só "o público influenciou", é "errei porque a mesa estava
    vazia ou porque estava cheia".
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
    return (ma - mb) / s


def _num(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _acaso(reg: dict, n_classes: int) -> Optional[float]:
    """O acaso da aposta que ESTA janela fez: k/n_classes."""
    k = len(reg.get("alvos") or []) or _num((reg.get("contexto") or {}).get("k"))
    if not k or not n_classes:
        return None
    return min(1.0, float(k) / float(n_classes))


# ═══════════════════════════════════════════════════ o exame de uma teoria
def examinar_teoria(nome: str, registros: Sequence[dict],
                    n_classes: int) -> Dict[str, Any]:
    """As quatro perguntas dele, respondidas para uma teoria."""
    meus = [r for r in registros
            if nome in [str(h) for h in (r.get("hips") or [])]]
    fechados = [r for r in meus if (r.get("resultado") or {}) .get("acertou") is not None]
    if len(fechados) < MIN_JANELAS:
        return {"teoria": nome, "sabe": False, "n": len(fechados),
                "nota": f"votou em {len(fechados)} janelas fechadas; preciso de "
                        f"{MIN_JANELAS} para dizer algo dela"}

    acertos = [r for r in fechados if (r["resultado"] or {}).get("acertou")]
    erros = [r for r in fechados if not (r["resultado"] or {}).get("acertou")]
    taxa = len(acertos) / len(fechados)
    # o acaso é a MÉDIA dos acasos das apostas que ela de fato fez
    acasos = [a for a in (_acaso(r, n_classes) for r in fechados) if a]
    acaso = (sum(acasos) / len(acasos)) if acasos else None
    razao = (taxa / acaso) if acaso else None

    # ── o ruído: essa taxa aguenta o tamanho da amostra? ─────────────────
    z = None
    if acaso and 0 < acaso < 1:
        se = math.sqrt(acaso * (1 - acaso) / len(fechados))
        if se > 1e-12:
            z = (taxa - acaso) / se

    # ── a causa: em qual contexto ela acerta e em qual erra ──────────────
    causas: List[Dict[str, Any]] = []
    if len(acertos) >= MIN_POR_LADO and len(erros) >= MIN_POR_LADO:
        for eixo, rotulo in EIXOS.items():
            va = [x for x in (_num((r.get("contexto") or {}).get(eixo))
                              for r in acertos) if x is not None]
            ve = [x for x in (_num((r.get("contexto") or {}).get(eixo))
                              for r in erros) if x is not None]
            if len(va) < MIN_POR_LADO or len(ve) < MIN_POR_LADO:
                continue
            d = _d_de_cohen(va, ve)
            if d is None or abs(d) < D_MINIMO:
                continue
            causas.append({
                "eixo": eixo, "rotulo": rotulo, "d": round(d, 2),
                "quando_acerta": round(sum(va) / len(va), 2),
                "quando_erra": round(sum(ve) / len(ve), 2),
                "n_acerta": len(va), "n_erra": len(ve)})
        causas.sort(key=lambda c: -abs(c["d"]))

    # ── "usei corretamente a teoria?" ────────────────────────────────────
    # a teoria foi usada em momentos que o semáforo já dizia serem bons, ou foi
    # usada no escuro? A resposta muda o que fazer: teoria que só funciona no
    # verde deve ser calada no vermelho, e não descartada.
    uso = _uso_correto(acertos, erros)

    return {"teoria": nome, "sabe": True, "n": len(fechados),
            "acertos": len(acertos), "erros": len(erros),
            "taxa": round(taxa, 4),
            "acaso": round(acaso, 4) if acaso else None,
            "razao": round(razao, 3) if razao else None,
            "z": round(z, 2) if z is not None else None,
            "causas": causas, "uso": uso,
            "usar_mais": bool(razao and razao >= RAZAO_BOA
                              and z is not None and z >= 2.0),
            "usar_menos": bool(razao and razao <= RAZAO_RUIM
                               and z is not None and z <= -2.0)}


def _uso_correto(acertos: Sequence[dict], erros: Sequence[dict]) -> Dict[str, Any]:
    """A teoria foi usada nos momentos em que o momento era bom?"""
    def cores(rs):
        c = {}
        for r in rs:
            k = str((r.get("contexto") or {}).get("cor") or "?")
            c[k] = c.get(k, 0) + 1
        return c
    ca, ce = cores(acertos), cores(erros)
    todas = set(ca) | set(ce)
    if todas <= {"?"}:
        return {"sabe": False,
                "nota": "as janelas antigas não guardaram a cor do momento"}
    linhas = {}
    for cor in sorted(todas - {"?"}):
        a, e = ca.get(cor, 0), ce.get(cor, 0)
        if a + e >= MIN_POR_LADO:
            linhas[cor] = {"n": a + e, "taxa": round(a / (a + e), 3)}
    if len(linhas) < 2:
        return {"sabe": False,
                "nota": "ainda não votou o bastante em cores diferentes para "
                        "comparar"}
    melhor = max(linhas.items(), key=lambda kv: kv[1]["taxa"])
    pior = min(linhas.items(), key=lambda kv: kv[1]["taxa"])
    return {"sabe": True, "por_cor": linhas,
            "melhor": melhor[0], "pior": pior[0],
            "so_no_verde": bool(melhor[0] == "VERDE"
                                and melhor[1]["taxa"] > pior[1]["taxa"] * 1.3)}


# ═══════════════════════════════════════════════════ o exame de todas elas
def examinar(registros: Sequence[dict], n_classes: int,
             teorias: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Todas as teorias que votaram, cada uma com o seu veredito."""
    regs = [r for r in (registros or []) if isinstance(r, dict)]
    nomes = list(teorias) if teorias else sorted(
        {str(h) for r in regs for h in (r.get("hips") or [])})
    exames = [examinar_teoria(n, regs, n_classes) for n in nomes]
    sabidas = [e for e in exames if e.get("sabe")]
    return {"exames": exames,
            "n_teorias": len(nomes), "n_avaliadas": len(sabidas),
            "usar_mais": [e["teoria"] for e in sabidas if e.get("usar_mais")],
            "usar_menos": [e["teoria"] for e in sabidas if e.get("usar_menos")]}


def pesos(exame: Dict[str, Any]) -> Dict[str, float]:
    """O que o autoexame manda fazer na PRÓXIMA volta.

    Ele não pediu só o diagnóstico, pediu a consequência: "e se usar agora, e
    tomar decisões inteligentes". Então o exame devolve um multiplicador de peso
    por teoria, e quem decide o número é a medida:

        razão medida acima do acaso, além do ruído  → fala mais alto
        razão medida abaixo, além do ruído          → fala mais baixo
        sem base                                    → peso 1, não mexe

    Limitado a [0.4, 2.0] pelo mesmo motivo de `forca_dos_eixos`: uma teoria com
    sorte num punhado de janelas não pode calar todas as outras.
    """
    out: Dict[str, float] = {}
    for e in exame.get("exames") or []:
        if not e.get("sabe") or not e.get("razao"):
            continue
        z = e.get("z")
        if z is None or abs(z) < 2.0:
            continue
        w = max(0.4, min(2.0, float(e["razao"])))
        out[e["teoria"]] = round(w, 3)
    return out


def resumo(exame: Dict[str, Any], quantas: int = 4) -> List[str]:
    """As perguntas dele, respondidas em português, com o `n` de cada resposta."""
    exames = exame.get("exames") or []
    sabidas = [e for e in exames if e.get("sabe") and e.get("razao")]
    if not sabidas:
        n = max((e.get("n", 0) for e in exames), default=0)
        return [f"[Autoexame] {len(exames)} teorias votaram, mas nenhuma tem as "
                f"{MIN_JANELAS} janelas fechadas que eu preciso para julgá-la "
                f"(a mais rodada tem {n}) — ainda não sei dizer o que funcionou"]
    sabidas.sort(key=lambda e: -(e.get("razao") or 0))
    L = [f"[Autoexame] revi {len(sabidas)} de {exame.get('n_teorias')} teorias "
         f"pelas janelas que elas mesmas assinaram:"]

    for e in sabidas[:quantas]:
        seta = "↑" if (e["razao"] or 0) > 1 else "↓"
        forte = ("" if e.get("z") is None or abs(e["z"]) < 2.0
                 else "  (além do ruído)")
        L.append(f"[Autoexame]   {e['teoria']}: {e['acertos']}/{e['n']} = "
                 f"{e['taxa']:.0%} contra acaso {e['acaso']:.0%} "
                 f"{seta} {e['razao']:.2f}x, z={e.get('z')}{forte}")
        # "porque errei tanto? foi momento? foi quantidade de pessoas?"
        if e.get("causas"):
            c = e["causas"][0]
            direcao = "MAIOR" if c["d"] > 0 else "MENOR"
            L.append(f"[Autoexame]     erra/acerta por {c['rotulo']}: "
                     f"{direcao} quando acerta ({c['quando_acerta']} contra "
                     f"{c['quando_erra']}), d={c['d']:+.2f}, "
                     f"n={c['n_acerta']}/{c['n_erra']}")
        elif e.get("acertos", 0) >= MIN_POR_LADO and e.get("erros", 0) >= MIN_POR_LADO:
            L.append(f"[Autoexame]     nenhum eixo do contexto separa os acertos "
                     f"dos erros dela (d<{D_MINIMO}) — não foi momento nem "
                     f"público; não vou inventar culpado")
        # "usei corretamente a teoria?"
        u = e.get("uso") or {}
        if u.get("sabe"):
            pc = u["por_cor"]
            trecho = ", ".join(f"{k} {v['taxa']:.0%} (n={v['n']})"
                               for k, v in sorted(pc.items()))
            L.append(f"[Autoexame]     por cor do momento: {trecho}"
                     + ("  ← só serve no verde; calá-la fora dele"
                        if u.get("so_no_verde") else ""))
        elif u.get("nota"):
            L.append(f"[Autoexame]     'usei na hora certa?' — {u['nota']}")

    mais, menos = exame.get("usar_mais") or [], exame.get("usar_menos") or []
    if mais:
        L.append(f"[Autoexame] usar MAIS (bateram o acaso além do ruído): "
                 f"{', '.join(mais[:5])}")
    if menos:
        L.append(f"[Autoexame] usar MENOS (ficaram abaixo do acaso além do "
                 f"ruído): {', '.join(menos[:5])}")
    if not mais and not menos:
        L.append("[Autoexame] nenhuma teoria se separou do acaso além do ruído — "
                 "os pesos ficam como estavam, e isso é a resposta honesta")
    return L


# ═════════════════════════════════════ qual teoria está em uso AGORA
def em_uso_agora(hips: Sequence[dict], sig: Optional[dict] = None,
                 aprovados: Optional[Sequence[Any]] = None,
                 giros: int = 20) -> List[str]:
    """"qual teoria que está sendo utilizada naquele momento com base nos vinte
    últimos giros" — a pergunta dele, respondida com quem de fato votou.

    Não é uma lista do que existe no software: é a lista de quem falou nesta
    volta, com o peso que trouxe e o que cada uma conseguiu aprovar. Uma teoria
    que está no pacote mas cujas condições não se cumpriram agora não aparece --
    e é essa diferença que ele quer ver.
    """
    ativos = [h for h in (hips or []) if isinstance(h, dict) and h.get("nums")]
    if not ativos:
        return [f"[Em uso] nenhuma teoria teve condição cumprida nos últimos "
                f"{giros} giros — a sugestão desta volta não vem de teoria"]
    ativos.sort(key=lambda h: -float(h.get("peso") or 0))
    L = [f"[Em uso] {len(ativos)} teorias com condição cumprida nos últimos "
         f"{giros} giros, da que fala mais alto para a mais baixa:"]
    for h in ativos[:8]:
        nums = [str(x) for x in (h.get("nums") or [])][:6]
        L.append(f"[Em uso]   {h.get('nome')}  peso {float(h.get('peso') or 0):.2f}"
                 f"  aponta {', '.join(nums)}")
    if len(ativos) > 8:
        L.append(f"[Em uso]   (+{len(ativos) - 8} outras)")
    # quem venceu a votação, e por quantos votos
    if sig and aprovados:
        partes = []
        for n in list(aprovados)[:6]:
            s = sig.get(n) or sig.get(str(n)) or {}
            vt = s.get("votos_teoria", 0)
            if vt:
                partes.append(f"{n}←{vt} teorias")
        if partes:
            L.append("[Em uso]   venceram a votação: " + ", ".join(partes))
    return L
