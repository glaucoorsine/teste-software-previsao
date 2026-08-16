# -*- coding: utf-8 -*-
"""
A AGREGAÇÃO — F45 a F48, a IA12 dele.

POR QUE ISTO É UM ARQUIVO SEPARADO
──────────────────────────────────
Porque no desenho dele a IA12 não é uma leitura entre outras: ela não olha
para a mesa, olha para as ONZE que olharam. As quatro famílias dela são quatro
respostas diferentes para a mesma pergunta -- como juntar opiniões sem
transformar quantidade de votos em verdade:

    F45  Agregação de especialistas independentes
         w_(j,t) ∝ exp(-η·Loss_(j,1:t-1))

    F46  Especialistas adormecidos e reativação
         L_j = Σ_(t: awake_j(t)) loss_j(t) ;  Regret_j = L_j - L_min

    F47  Falsificação adversarial e multiverso
         RobustRate = count_j(sign(θ_j) = sign(θ_main)) / J

    F48  Memória epistemológica com dormência
         E_t = λ·E_(t-1) + log(BF_t)

ISTO CORRIGE UM DEFEITO MEU
───────────────────────────
O consenso que eu tinha escrito somava peso FIXO por fonte. Quem errava a
semana inteira continuava pesando igual no domingo. Na fórmula dele o peso cai
sozinho conforme a perda acumula -- sem que eu precise podar ninguém, o que
também respeita o que ele já tinha mandado: "não critique e nem barre".

Ninguém é zerado. Encolher não é podar.

O PROBLEMA QUE A F46 RESOLVE, E QUE EU NÃO TINHA VISTO
──────────────────────────────────────────────────────
Metade das 44 leituras se cala na maior parte dos giros -- e com razão, porque
medem condições que raramente ocorrem. Se a perda fosse contada nos giros em
que a leitura estava CALADA, quem fala pouco seria punido por prudência e
quem fala sempre seria premiado por imprudência.

A F46 diz exatamente como evitar isso: a perda de cada especialista só conta
nos giros em que ele estava ACORDADO. É a diferença entre `Loss` e
`Σ_(t: awake_j(t))`, e é toda a diferença.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, List, Optional

# η da F45: o quanto o erro passado pesa. Alto demais vira ditadura da última
# rodada; baixo demais deixa todo mundo igual para sempre. 0,6 leva umas cinco
# janelas para separar quem acerta de quem não acerta.
ETA = 0.6

# λ da F48: quanto a memória epistemológica retém a cada giro.
LAMBDA = 0.94


# ═══════════════════════════════════════════════════════════════════ F45

def f45_pesos(perdas: Dict[str, float], acordado: Optional[Dict[str, int]] = None,
              eta: float = ETA) -> Dict[str, float]:
    """F45 · Agregação de especialistas independentes.

        w_(j,t) ∝ exp(-η · Loss_(j,1:t-1))

    A perda entra NORMALIZADA pelos giros em que o especialista estava
    acordado (a correção que a F46 exige). Sem histórico, todos valem 1 -- que
    é o certo no começo, porque ninguém errou ainda.

    A média dos pesos é mantida em 1,0 para que a escala do placar não infle
    nem encolha conforme quem está falando.
    """
    if not perdas:
        return {}
    med = {}
    for j, L in perdas.items():
        n = max(1, (acordado or {}).get(j, 1))
        med[j] = L / n
    menor = min(med.values())
    w = {j: math.exp(-eta * (v - menor)) for j, v in med.items()}
    s = sum(w.values()) or 1.0
    return {j: v / s * len(w) for j, v in w.items()}


# ═══════════════════════════════════════════════════════════════════ F46

def f46_arrependimento(perdas: Dict[str, float],
                       acordado: Dict[str, int]) -> Dict[str, float]:
    """F46 · Especialistas adormecidos e reativação.

        L_j = Σ_(t: awake_j(t)) loss_j(t) ;  Regret_j = L_j - L_min

    O arrependimento de cada um contra o melhor, medido só quando estava
    acordado. É isto que impede que uma leitura prudente -- que só fala quando
    tem o que dizer -- seja punida pelo silêncio.
    """
    if not perdas:
        return {}
    med = {j: perdas[j] / max(1, acordado.get(j, 1)) for j in perdas}
    melhor = min(med.values())
    return {j: v - melhor for j, v in med.items()}


def f46_dormentes(acordado: Dict[str, int], giros: int,
                  piso: float = 0.05) -> List[str]:
    """Quem está dormindo quase sempre. Não é defeito -- é informação."""
    return sorted(j for j, n in acordado.items()
                  if giros > 0 and n / giros < piso)


# ═══════════════════════════════════════════════════════════════════ F47

def f47_robustez(pesos_por_leitura: Dict[str, Dict[str, float]],
                 classe: str) -> float:
    """F47 · Falsificação adversarial e multiverso.

        RobustRate = count_j( sign(θ_j) = sign(θ_main) ) / J

    Quantas das leituras que falaram concordam com o sinal da leitura
    principal para esta classe. É o antídoto contra o achado que existe só
    porque uma leitura em particular foi escolhida.

    Baixa robustez não derruba a classe -- ele foi claro, "não critique e nem
    barre". Ela vira número na tela, e quem lê decide.
    """
    if not pesos_por_leitura:
        return 0.0
    votaram = [p for p in pesos_por_leitura.values() if p]
    if not votaram:
        return 0.0
    a_favor = sum(1 for p in votaram if float(p.get(str(classe), 0.0)) > 0)
    return a_favor / len(votaram)


# ═══════════════════════════════════════════════════════════════════ F48

def f48_memoria(memoria: Dict[str, float], acertou: Dict[str, bool],
                lam: float = LAMBDA) -> Dict[str, float]:
    """F48 · Memória epistemológica com dormência.

        E_t = λ·E_(t-1) + log(BF_t)

    A evidência acumulada de cada leitura, com esquecimento. `log(BF_t)` aqui
    é positivo quando ela acertou e negativo quando errou -- o fator de Bayes
    da rodada, na versão mais simples que a informação disponível sustenta.

    Quem some volta a valer com o tempo, em vez de carregar para sempre um
    erro de três meses atrás. É a dormência do nome da família.
    """
    novo = dict(memoria or {})
    for j, ok in (acertou or {}).items():
        novo[j] = lam * novo.get(j, 0.0) + (0.35 if ok else -0.35)
    for j in novo:
        if j not in (acertou or {}):
            novo[j] = lam * novo[j]              # dormente: só esquece
    return novo


# ═════════════════════════════════════════════════════════ o consenso

def consenso(pesos_por_leitura: Dict[str, Dict[str, float]],
             perdas: Optional[Dict[str, float]] = None,
             acordado: Optional[Dict[str, int]] = None,
             memoria: Optional[Dict[str, float]] = None,
             k: int = 12, eta: float = ETA) -> Dict[str, Any]:
    """As quatro famílias da IA12 juntas, produzindo a lista final.

    Devolve, para cada classe: o placar, QUEM votou nela e a robustez da F47.
    Um número escolhido sem dizer quem o escolheu não é auditável, e o livro
    inteiro dele é sobre leitura auditável.
    """
    w = f45_pesos(perdas or {}, acordado or {}, eta)
    mem = memoria or {}
    placar: Dict[str, float] = defaultdict(float)
    quem: Dict[str, List[str]] = defaultdict(list)
    for leitura, peso in (pesos_por_leitura or {}).items():
        # F45 dá o peso pela perda; F48 acrescenta a evidência acumulada.
        # `exp` mantém o fator positivo: memória ruim encolhe, não inverte.
        wj = w.get(leitura, 1.0) * math.exp(mem.get(leitura, 0.0))
        for classe, v in (peso or {}).items():
            placar[str(classe)] += wj * float(v)
            quem[str(classe)].append(leitura)
    ordem = sorted(placar.items(), key=lambda t: (-t[1], t[0]))[:k]
    return {
        "ordem": [c for c, _ in ordem],
        "placar": {c: round(v, 4) for c, v in ordem},
        "quem": {c: quem[c] for c, _ in ordem},
        "robustez": {c: round(f47_robustez(pesos_por_leitura, c), 3)
                     for c, _ in ordem},
        "pesos": {j: round(v, 3) for j, v in w.items()},
        "arrependimento": {j: round(v, 3) for j, v in
                           f46_arrependimento(perdas or {},
                                              acordado or {}).items()},
    }
