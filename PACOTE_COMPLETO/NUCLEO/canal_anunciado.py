# -*- coding: utf-8 -*-
"""
O CANAL ANUNCIADO — a base da descoberta de multiplicador, virada para números.

O QUE ELE PEDIU
───────────────
    "descoberta de multiplicador que estava na 103, ela sim eu quero que você
     use, porque ela conseguia fazer previsões perfeitas... eu quero que você
     use no sentido de qual foi a base que você utilizou"

    "o estudo que eles usavam pra identificar multiplicador, na verdade vai
     identificar os números"

Fui atrás do que aquela técnica realmente fazia. A base não é uma fórmula --
é uma OBSERVAÇÃO sobre o jogo, e está escrita no cabeçalho daquele arquivo:

    "o sorteio de multiplicador é ANUNCIADO a cada rodada,
     saindo ou não o número"

É isso, e é tudo. Repare no que essa frase implica:

    o RESULTADO      dá 1 observação por giro
    o ANÚNCIO        dá de 1 a 5 observações por giro, e todas ficam
                     registradas mesmo quando não pagam

O Lightning sorteia de 1 a 5 lucky numbers por giro. O Mega Fire acende seus
fire numbers. O Crazy Time gira o top slot com símbolo e multiplicador. Nada
disso depende de acertar: o anúncio acontece e é observável de qualquer jeito.

Por isso aquela previsão parecia "perfeita" perto das outras. Não era um
método mais esperto -- era CINCO VEZES MAIS DADO sobre o mesmo conjunto de 37
classes, num canal que não precisa esperar coincidência para ser medido.

(E foi aí, aliás, que a v103 quase morreu: a captura só guardava o lucky
quando ele calhava de ser o número sorteado. Em 205 giros sobraram 10
registros de umas 600 premiações -- 2% do fenômeno. Consertar a captura foi o
que fez a técnica aparecer.)

COMO ISSO VIRA PREVISÃO DE NÚMERO
─────────────────────────────────
O anúncio é sobre o MESMO domínio do resultado: 0..36 nas roletas, os símbolos
no Crazy Time. Então há duas coisas a fazer, e a segunda é a que interessa:

  1. LER O CANAL       rodar as mesmas leituras sobre a série anunciada, que é
                       de 3 a 5 vezes mais longa que a de resultados

  2. MEDIR O ACOPLAMENTO  o que é quente no canal anunciado é quente na roda?
                       Se o anúncio e o giro saem do mesmo processo, o viés de
                       um aparece no outro -- e o canal, por ter mais dado,
                       enxerga primeiro.

O ITEM 2 NÃO É SUPOSIÇÃO -- É MEDIDO
────────────────────────────────────
`acoplamento()` calcula quanto o canal anunciado prevê o resultado, fora da
amostra e contra o acaso do mesmo tamanho. Se o acoplamento não existe nessa
mesa, este módulo DIZ ISSO e não vota. Seria fácil (e desonesto) assumir que
existe só porque a ideia é boa.

POR QUE ESTE ARQUIVO PODE EXISTIR NUM NÚCLEO QUE SÓ ACEITA OS PDFS
──────────────────────────────────────────────────────────────────
Porque ele mandou, nominalmente, e porque a coisa é honesta: o canal anunciado
não é teoria minha sobre como o jogo funciona -- é uma FONTE DE DADO que o
jogo publica e que o núcleo estava ignorando. As leituras aplicadas sobre ele
continuam sendo as 44 famílias dele.

Dito de outro jeito: os três PDFs continuam sendo o que o software PENSA.
Isto aqui é mais do que ele VÊ.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List

SEM_ANUNCIO = ("immersive",)          # a mesa não tem multiplicador nenhum
CRAZY = ("crazy_time", "crazy_time_a")


def tem_canal(jogo: str) -> bool:
    """A mesa publica anúncio? Perguntar na Immersive é pergunta sem objeto."""
    return not str(jogo or "").startswith(SEM_ANUNCIO)


# ═══════════════════════════════════════════════════ extração do anúncio

def rodadas(historico: List[dict], jogo: str) -> List[Dict[str, Any]]:
    """De cada giro, o anúncio daquele giro. Recente → antigo.

        {"saiu": resultado, "anunciados": [classe...], "x": {classe: mult}}

    Giro sem anúncio nenhum vira lista vazia, e isso é informação -- é o que
    permite medir ritmo e seca do próprio canal.
    """
    saida = []
    e_crazy = str(jogo or "").startswith(CRAZY)
    for linha in (historico or []):
        if not isinstance(linha, dict):
            continue
        saiu = linha.get("n", linha.get("sec"))
        anunciados: List[Any] = []
        valores: Dict[Any, float] = {}
        for t in (linha.get("tags") or []):
            if not isinstance(t, dict):
                continue
            if e_crazy:
                top = t.get("top") or {}
                if isinstance(top, dict) and top.get("simbolo"):
                    s = str(top["simbolo"]).strip()
                    anunciados.append(s)
                    try:
                        valores[s] = float(top.get("x") or 0)
                    except (TypeError, ValueError):
                        pass
                continue
            for chave in ("lucky", "fire_nums"):
                for it in (t.get(chave) or []):
                    if not isinstance(it, dict):
                        continue
                    try:
                        n = int(it.get("n"))
                    except (TypeError, ValueError):
                        continue
                    anunciados.append(n)
                    try:
                        if it.get("x"):
                            valores[n] = float(it["x"])
                    except (TypeError, ValueError):
                        pass
        saida.append({"saiu": saiu, "anunciados": anunciados, "x": valores})
    return saida


def serie_do_canal(rds: List[dict]) -> List[int]:
    """O canal anunciado como série de classes, recente → antiga.

    Um giro que anunciou cinco números contribui com cinco entradas. É
    exatamente daí que vem a vantagem: a série do canal é de três a cinco
    vezes mais longa que a de resultados, sobre as mesmas 37 classes.
    """
    fora: List[int] = []
    for r in rds or []:
        for a in (r.get("anunciados") or []):
            try:
                fora.append(int(a))
            except (TypeError, ValueError):
                continue
    return fora


def serie_de_resultados(rds: List[dict]) -> List[int]:
    fora: List[int] = []
    for r in rds or []:
        try:
            fora.append(int(r.get("saiu")))
        except (TypeError, ValueError):
            continue
    return fora


def densidade(rds: List[dict]) -> Dict[str, float]:
    """Quantas observações o canal dá por giro. É a medida da vantagem."""
    giros = len(rds or [])
    obs = sum(len(r.get("anunciados") or []) for r in (rds or []))
    return {
        "giros": giros,
        "observacoes": obs,
        "por_giro": (obs / giros) if giros else 0.0,
        "vantagem": (obs / giros) if giros else 0.0,
    }


# ═══════════════════════════════════════════════ o acoplamento, MEDIDO

def _binom_cauda(k: int, n: int, p: float) -> float:
    if n <= 0 or k <= 0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
                        for i in range(k, n + 1)))


def acoplamento(rds: List[dict], n_classes: int = 37, k: int = 12,
                min_giros: int = 60) -> Dict[str, Any]:
    """O canal anunciado prevê o resultado? A conta, não a esperança.

    Para cada giro, monta o topo do canal usando SÓ os giros anteriores e
    confere se o resultado daquele giro caiu ali dentro. Fora da amostra, e
    contra o acaso do mesmo tamanho de lista -- comparar aposta de 12 números
    com o acaso de 1 seria fraude, e é a fraude mais fácil de cometer aqui.

    Devolve `existe=True` só quando p < 0,05 E a razão passa de 1. Se não
    passar, o canal não vota: ideia boa sem medida é palpite.
    """
    if len(rds or []) < min_giros:
        return {"existe": False, "n": 0,
                "motivo": f"só {len(rds or [])} giros (precisa de {min_giros})"}
    acertos = tentativas = 0
    esperado = 0.0
    for i in range(len(rds) - min_giros):
        alvo = rds[i].get("saiu")
        try:
            alvo = int(alvo)
        except (TypeError, ValueError):
            continue
        passado = serie_do_canal(rds[i + 1:])
        if len(passado) < 40:
            continue
        topo = [c for c, _q in Counter(passado).most_common(k)]
        if not topo:
            continue
        tentativas += 1
        esperado += len(set(topo)) / n_classes
        if alvo in topo:
            acertos += 1
    if tentativas < 30:
        return {"existe": False, "n": tentativas,
                "motivo": f"só {tentativas} janelas medidas (precisa de 30)"}
    acaso = esperado / tentativas
    taxa = acertos / tentativas
    razao = taxa / acaso if acaso else 0.0
    p = _binom_cauda(acertos, tentativas, acaso)
    return {
        "existe": bool(p < 0.05 and razao > 1.0),
        "n": tentativas, "acertos": acertos, "taxa": taxa,
        "acaso": acaso, "razao": razao, "p": p,
        "motivo": (f"{acertos}/{tentativas} = {taxa:.1%} contra acaso "
                   f"{acaso:.1%} — {razao:.2f}x, p={p:.4f}"),
    }


# ═══════════════════════════════════════════════════════ a leitura do canal

def ler(historico: List[dict], jogo: str, n_classes: int = 37,
        k: int = 12, exigir_acoplamento: bool = True) -> Dict[str, Any]:
    """Roda as 44 famílias dele SOBRE O CANAL ANUNCIADO.

    As leituras são as mesmas -- o que muda é a série que elas leem, que aqui
    é de três a cinco vezes mais longa. É literalmente a base da v103 aplicada
    a números, que foi o que ele pediu.

    Com `exigir_acoplamento`, o canal só vota depois de provar que prevê o
    resultado nesta mesa. Sem isso eu estaria empurrando 44 leituras a mais no
    placar com base numa ideia bonita e nenhuma medida.
    """
    from . import leituras as L

    if not tem_canal(jogo):
        return {"vota": False, "motivo": "esta mesa não tem anúncio",
                "palpites": {}, "pesos": {}, "falas": {}}

    rds = rodadas(historico, jogo)
    dens = densidade(rds)
    canal = serie_do_canal(rds)
    if len(canal) < 60:
        return {"vota": False, "densidade": dens,
                "motivo": (f"canal com {len(canal)} observações — a captura "
                           f"pode estar guardando só o anúncio que pagou, "
                           f"que foi o defeito original da v103"),
                "palpites": {}, "pesos": {}, "falas": {}}

    ac = acoplamento(rds, n_classes, k)
    if exigir_acoplamento and not ac.get("existe"):
        return {"vota": False, "densidade": dens, "acoplamento": ac,
                "motivo": f"acoplamento não comprovado — {ac.get('motivo','')}",
                "palpites": {}, "pesos": {}, "falas": {}}

    r = L.executar(canal, n_classes, {"mults": _mults_do_canal(rds)}, k=k)
    return {
        "vota": True, "densidade": dens, "acoplamento": ac,
        "motivo": (f"canal com {dens['por_giro']:.1f} observações por giro "
                   f"({len(canal)} contra {dens['giros']} de resultado)"),
        "palpites": {f"CANAL_{n}": v for n, v in r["palpites"].items()},
        "pesos": {f"CANAL_{n}": v for n, v in r["pesos"].items()},
        "falas": {f"CANAL_{n}": v for n, v in r["falas"].items()},
        "apontaram": r["apontaram"], "total": r["total"],
    }


def _mults_do_canal(rds: List[dict]) -> List[float]:
    """Os valores anunciados, alinhados com `serie_do_canal`."""
    fora: List[float] = []
    for r in rds or []:
        vals = r.get("x") or {}
        for a in (r.get("anunciados") or []):
            try:
                fora.append(float(vals.get(a, 0) or 0))
            except (TypeError, ValueError):
                fora.append(0.0)
    return fora


def resumo(historico: List[dict], jogo: str, n_classes: int = 37) -> str:
    r = ler(historico, jogo, n_classes)
    d = r.get("densidade") or {}
    L = [f"[Canal anunciado] {r.get('motivo', '')}"]
    if d:
        L.append(f"   {d['observacoes']} observações em {d['giros']} giros "
                 f"= {d['por_giro']:.1f} por giro de vantagem sobre o resultado")
    ac = r.get("acoplamento")
    if ac and ac.get("n"):
        L.append(f"   acoplamento com a roda: {ac.get('motivo', '')}")
    if r.get("vota"):
        L.append(f"   {r.get('apontaram')} das {r.get('total')} famílias "
                 f"leram o canal")
    return "\n".join(L)
