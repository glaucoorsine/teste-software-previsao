# -*- coding: utf-8 -*-
"""
APLICADORES — cinco leituras do que está acontecendo AGORA, e uma mesa que
concilia as cinco.

Por que isto existe. O catálogo pode estar cheio de teorias boas e o resultado
ainda ser ruim, porque quem escolhe O QUE APLICAR não olha o momento: aplica
tudo que casa com o gatilho, inclusive teorias que naquele contexto não têm
chance. Duas coisas se perdem de uma vez — a oportunidade, e o registro da
teoria, que leva um erro que não era dela.

Cada aplicador pontua as teorias CABÍVEIS por um critério diferente:

  A1 RECENCIA    o que vem acertando nas últimas ativações (não na vida toda)
  A2 VANTAGEM    quem está de fato à frente da régua de frequência agora
  A3 REGIME      como cada teoria se saiu em regimes parecidos com o de agora
  A4 ESTRUTURA   geometria da roda no momento (setor, vizinhos, finais)
  A5 CONVERGENCIA onde as outras quatro se encontram

A MESA junta os cinco. Um número só é sugerido com no mínimo
`MIN_APLICADORES_CONCORDES` lentes independentes apontando para ele.

HONESTIDADE — o registro da teoria NÃO é alterado por nada disto. A sombra de
cada teoria continua sendo gravada em todas as ativações, sem filtro, para o
histórico dela permanecer não-enviesado. O que a mesa escolhe é registrado à
PARTE (`decisao_mesa`), para dar pra medir separadamente:
    - a teoria sozinha  (registro limpo)
    - a escolha da mesa (isto aqui ajuda ou atrapalha?)
Se a mesa filtrasse a sombra, ela inflaria a taxa das teorias por construção e
a gente nunca saberia se escolher bem tem valor.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from .dsl_hipoteses import eval_cond, pred_candidatos
from .detector_regimes import detectar

# quantas lentes independentes precisam apontar o mesmo número
MIN_APLICADORES_CONCORDES = 2
# janela de "agora" para os aplicadores de recência/vantagem
JANELA_RECENTE = 10
# quantos números a mesa entrega no máximo
K_MESA = 7

# ordem física da roda europeia — vizinhança real, não numérica
RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}


def _hist_recente(t: dict, k: int = JANELA_RECENTE) -> List[dict]:
    h = (t.get("prospectivo") or {}).get("hist") or []
    return [e for e in h if isinstance(e, dict)][-k:]


def _nums_da_teoria(t: dict, hist: List[str], dominio: List[str], k: int) -> List[str]:
    try:
        return [str(x) for x in (pred_candidatos(t.get("expr") or {}, hist, dominio, k=k) or [])]
    except Exception:
        return []


# ---------------------------------------------------------------- A1
def a1_recencia(cabiveis, hist, dominio) -> Dict[str, float]:
    """O que vem acertando AGORA. Vida inteira não interessa aqui."""
    pontos: Dict[str, float] = defaultdict(float)
    for t in cabiveis:
        rec = _hist_recente(t)
        if len(rec) < 3:
            continue
        taxa = sum(1 for e in rec if e.get("hit")) / len(rec)
        if taxa <= 0:
            continue
        # peso cresce com a taxa recente e com quantas amostras a sustentam
        peso = taxa * min(1.0, len(rec) / JANELA_RECENTE)
        for n in _nums_da_teoria(t, hist, dominio, K_MESA):
            pontos[n] += peso
    return dict(pontos)


# ---------------------------------------------------------------- A2
def a2_vantagem(cabiveis, hist, dominio) -> Dict[str, float]:
    """Quem está à frente da RÉGUA agora — não do acaso."""
    pontos: Dict[str, float] = defaultdict(float)
    for t in cabiveis:
        rec = [e for e in _hist_recente(t) if "baseline_hit" in e]
        if len(rec) < 3:
            continue
        meu = sum(1 for e in rec if e.get("hit")) / len(rec)
        regua = sum(1 for e in rec if e.get("baseline_hit")) / len(rec)
        vant = meu - regua
        if vant <= 0:
            continue                       # perder da régua não pontua
        for n in _nums_da_teoria(t, hist, dominio, K_MESA):
            pontos[n] += vant * 3.0
    return dict(pontos)


# ---------------------------------------------------------------- A3
def a3_regime(cabiveis, hist, dominio) -> Dict[str, float]:
    """Como cada teoria se saiu quando o jogo estava parecido com agora."""
    try:
        reg_agora = (detectar(hist) or {}).get("regime")
    except Exception:
        reg_agora = None
    pontos: Dict[str, float] = defaultdict(float)
    for t in cabiveis:
        eps = t.get("episodios_ativacao") or []
        mesmos = [e for e in eps if isinstance(e, dict) and e.get("regime") == reg_agora]
        if len(mesmos) >= 3:
            taxa = sum(1 for e in mesmos if e.get("hit")) / len(mesmos)
            peso = taxa * 1.5
        else:
            # sem histórico neste regime: contribui fraco, não zera
            p = t.get("prospectivo") or {}
            n = int(p.get("n") or 0)
            peso = ((p.get("hits") or 0) / n) * 0.4 if n >= 3 else 0.0
        if peso <= 0:
            continue
        for n in _nums_da_teoria(t, hist, dominio, K_MESA):
            pontos[n] += peso
    return dict(pontos)


# ---------------------------------------------------------------- A4
def a4_estrutura(cabiveis, hist, dominio) -> Dict[str, float]:
    """
    A geometria do momento. É o tipo de leitura que o usuário descreve como
    "veio 31 e 3, isso aqui está seguindo a regrinha do setor" — vizinhança na
    RODA FÍSICA (não numérica), setor quente e final repetido.

    Não olha teoria nenhuma: olha o que a mesa está fazendo agora. Serve
    justamente como voz independente das outras quatro.
    """
    pontos: Dict[str, float] = defaultdict(float)
    numeros = []
    for x in hist[:12]:
        try:
            numeros.append(int(x))
        except (TypeError, ValueError):
            return {}                      # Crazy Time: não tem roda física
    if len(numeros) < 5:
        return {}

    # 1) vizinhos na roda dos últimos 3 giros
    for i, n in enumerate(numeros[:3]):
        if n not in POS:
            continue
        p = POS[n]
        for d in (-2, -1, 1, 2):
            viz = RODA[(p + d) % len(RODA)]
            pontos[str(viz)] += (0.6 if i == 0 else 0.35) / (abs(d) ** 0.5)

    # 2) setor quente: terço da roda com mais saídas recentes
    setores = Counter()
    for n in numeros:
        if n in POS:
            setores[POS[n] // 13] += 1
    if setores:
        quente, q = setores.most_common(1)[0]
        if q >= 5:                          # concentração real, não ruído
            for i in range(quente * 13, min((quente + 1) * 13, len(RODA))):
                pontos[str(RODA[i])] += 0.25

    # 3) final repetido (o "3, 13, 23, 33")
    finais = Counter(n % 10 for n in numeros[:8])
    for f, q in finais.items():
        if q >= 3:
            for n in range(0, 37):
                if n % 10 == f:
                    pontos[str(n)] += 0.3
    return dict(pontos)


# ---------------------------------------------------------------- A5 + mesa
def _normaliza(d: Dict[str, float]) -> Dict[str, float]:
    if not d:
        return {}
    mx = max(d.values())
    return {k: v / mx for k, v in d.items()} if mx > 0 else {}


def _peso_a6() -> float:
    """Peso do A6, vindo do teste de ruído. Sem calibração, não vota.

    Uma lente que enxerga padrão em sequência aleatória não pode votar com o
    mesmo peso de uma que fica calada — e só o teste diz qual é qual.
    """
    import json as _json
    from pathlib import Path as _P
    try:
        d = _json.loads((_P(__file__).resolve().parents[1] / "a6_calibracao.json")
                        .read_text(encoding="utf-8"))
        return max(0.0, min(1.0, float(d.get("peso_sugerido", 0))))
    except Exception:
        return 0.0


def mesa(dataset_id: str, hist, dominio, cabiveis, usar_llm: bool = True) -> Dict[str, Any]:
    """
    Concilia os quatro aplicadores; A5 é a convergência entre eles.

    Devolve os números escolhidos, quem votou em cada um e por quê — o "por quê"
    é o que permite auditar depois se a mesa está ajudando ou atrapalhando.
    """
    hist = [str(x) for x in (hist or [])]
    dominio = [str(x) for x in (dominio or [])]
    cabiveis = list(cabiveis or [])
    if not hist:
        return {"numeros": [], "motivo": "sem histórico", "detalhe": {}, "n_cabiveis": 0}

    lentes = {
        "A1_recencia": _normaliza(a1_recencia(cabiveis, hist, dominio)),
        "A2_vantagem": _normaliza(a2_vantagem(cabiveis, hist, dominio)),
        "A3_regime": _normaliza(a3_regime(cabiveis, hist, dominio)),
        "A4_estrutura": _normaliza(a4_estrutura(cabiveis, hist, dominio)),
    }

    # A6 — a lente com raciocínio de linguagem. Vota como as outras, com o peso
    # que ela mereceu no teste de ruído (teste_a6_ruido.py grava a calibração).
    # Sem chave de API, sem calibração ou com peso 0, ela simplesmente não vota.
    peso_a6 = _peso_a6()
    if peso_a6 > 0 and usar_llm:
        try:
            from . import aplicador_llm
            r6 = aplicador_llm.opinar(hist, dominio, cabiveis, pred_candidatos, k=K_MESA)
            if r6.get("numeros"):
                base = peso_a6 * max(0.3, float(r6.get("confianca") or 0.5))
                lentes["A6_raciocinio"] = {n: base for n in r6["numeros"]}
                lentes["A6_raciocinio"] = _normaliza(lentes["A6_raciocinio"])
        except Exception:
            pass

    # A5: convergência — quantas lentes independentes apontam cada número
    apoio: Dict[str, List[str]] = defaultdict(list)
    soma: Dict[str, float] = defaultdict(float)
    for nome, pts in lentes.items():
        for n, v in pts.items():
            if v >= 0.25:                  # ruído fraco não conta como voto
                apoio[n].append(nome)
            soma[n] += v

    escolhidos = [n for n, quem in apoio.items() if len(quem) >= MIN_APLICADORES_CONCORDES]
    escolhidos.sort(key=lambda n: (-len(apoio[n]), -soma[n]))
    escolhidos = escolhidos[:K_MESA]

    if not escolhidos:
        melhor = max((len(v) for v in apoio.values()), default=0)
        motivo = (f"sem convergência — melhor número teve {melhor} de "
                  f"{MIN_APLICADORES_CONCORDES} aplicadores")
    else:
        motivo = " | ".join(
            f"{n}←{len(apoio[n])} ({','.join(a.split('_')[0] for a in apoio[n])})"
            for n in escolhidos
        )

    return {
        "numeros": escolhidos,
        "motivo": motivo,
        "n_cabiveis": len(cabiveis),
        "detalhe": {n: {"apoiadores": apoio[n], "peso": round(soma[n], 3)}
                    for n in escolhidos},
        "lentes_ativas": [k for k, v in lentes.items() if v],
    }
