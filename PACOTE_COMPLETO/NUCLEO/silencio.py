# -*- coding: utf-8 -*-
"""
O DIREITO DE SILÊNCIO — R04-UNC-03 e R04-UNC-04 da Régua dele.

O QUE O REPLAY EXPÔS
────────────────────
Rodei o núcleo sobre os 1.006 giros dele como se fosse ao vivo. O placar ficou
no acaso, o que já era esperado. Mas apareceu uma coisa que eu não tinha visto:

    cobertura: falou em 206/206 (100%) com risco seletivo 69%
    cobertura: falou em 140/140 (100%) com risco seletivo 72%

O núcleo fala em TODA rodada. Nunca se cala. Pela régua dele isso não é
neutro, é fraqueza: uma leitura que só falasse quando tem o que dizer poderia
ter risco menor, e do jeito que estava não havia como saber.

    R04-UNC-03 · "avaliar quando a teoria deveria ter se abstido, tornando o
                  silêncio uma saída legítima da pesquisa"

        R_sel = Σ_t a_t·ℓ_t / Σ_t a_t        risco entre as vezes que falou
        Cov   = |W|^-1 Σ_t a_t               fração em que falou

        com a_t ∈ {0,1} CONGELADO ANTES de revelar y_t

O CRITÉRIO PARA CALAR VEM DA FICHA SEGUINTE
───────────────────────────────────────────
    R04-UNC-04 · "distinguir concentração genuína de massa probabilística de
                  uma escolha arbitrária do maior valor"

        H_t = -Σ_k p_(t,k)·log p_(t,k)       entropia
        M_t = p_(t,(1)) - p_(t,(2))          margem entre os dois maiores

É a descrição exata do defeito. Quando as 44 famílias discordam, o placar sai
quase plano -- e pegar os 10 primeiros de um placar plano não é previsão, é
ordenação arbitrária de empate. A entropia mede isso, a margem confirma, e o
núcleo passa a ter o direito de dizer "hoje não sei".

A HONESTIDADE DA ABSTENÇÃO
──────────────────────────
`a_t` é decidido a partir do PLACAR, antes de o giro sair. Nada do resultado
entra na decisão de calar -- senão o risco seletivo viraria escolha a
posteriori, que é a fraude mais fácil desta métrica: calar retroativamente nas
rodadas em que errou faz qualquer leitura parecer excelente.

E cobertura entra SEMPRE junto do risco. Risco de 20% com cobertura de 3% não
é habilidade, é seleção.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

# Quantil da entropia histórica abaixo do qual a concentração é considerada
# genuína. 0,5 = fala nas rodadas em que o placar está mais concentrado que a
# mediana das rodadas anteriores. É o único número escolhido por mim aqui, e
# está exposto para ele mexer.
QUANTIL_ENTROPIA = 0.5
MIN_HISTORICO = 15          # antes disso não há distribuição para comparar


def entropia_e_margem(placar: Dict[str, float]) -> Dict[str, float]:
    """R04-UNC-04 · H_t e M_t do placar do consenso.

    O placar vira distribuição (normalizado para somar 1) antes de medir --
    entropia sobre pesos não normalizados não é entropia.
    """
    vals = [float(v) for v in (placar or {}).values() if float(v) > 0]
    if not vals:
        return {"H": 0.0, "H_norm": 1.0, "M": 0.0, "n": 0}
    s = sum(vals)
    p = sorted((v / s for v in vals), reverse=True)
    H = -sum(x * math.log(x) for x in p if x > 0)
    H_max = math.log(len(p)) if len(p) > 1 else 1.0
    M = p[0] - (p[1] if len(p) > 1 else 0.0)
    return {"H": H, "H_norm": (H / H_max) if H_max else 1.0, "M": M, "n": len(p)}


class Silencio:
    """Decide falar ou calar, e mede risco seletivo com cobertura.

    A decisão sai da comparação com as rodadas ANTERIORES da própria mesa: o
    núcleo fala quando o placar de agora está mais concentrado que o típico
    dele. Isso evita limiar absoluto, que teria de ser diferente por mesa e
    por k, e que eu acabaria escolhendo com o resultado na mão.
    """

    def __init__(self, quantil: float = QUANTIL_ENTROPIA,
                 min_historico: int = MIN_HISTORICO):
        self.quantil = quantil
        self.min_historico = min_historico
        self.hist_H: List[float] = []
        self.hist_M: List[float] = []
        self.falou: List[bool] = []
        self.acertou: List[bool] = []
        self.calados = 0

    def decidir(self, placar: Dict[str, float]) -> Dict[str, Any]:
        """a_t ∈ {0,1}, decidido SÓ com o placar — antes do giro sair."""
        em = entropia_e_margem(placar)
        H, M = em["H_norm"], em["M"]
        if len(self.hist_H) < self.min_historico:
            # sem base de comparação ainda: fala, e vai formando a régua dela
            self.hist_H.append(H)
            self.hist_M.append(M)
            return {"falar": True, "motivo": "aquecendo a régua de entropia",
                    **em}
        ordH = sorted(self.hist_H)
        ordM = sorted(self.hist_M)
        corteH = ordH[min(len(ordH) - 1, int(self.quantil * len(ordH)))]
        corteM = ordM[min(len(ordM) - 1, int((1 - self.quantil) * len(ordM)))]
        # concentração genuína: entropia abaixo do típico E margem acima
        falar = bool(H <= corteH and M >= corteM)
        self.hist_H.append(H)
        self.hist_M.append(M)
        if not falar:
            self.calados += 1
        return {
            "falar": falar, **em,
            "corte_H": corteH, "corte_M": corteM,
            "motivo": (f"H={H:.3f} (corte {corteH:.3f}) · "
                       f"M={M:.4f} (corte {corteM:.4f}) — "
                       + ("concentração genuína" if falar
                          else "placar plano demais: escolher o topo seria arbitrário")),
        }

    def registrar(self, falou: bool, acertou: Optional[bool]) -> None:
        """`acertou` só é usado DEPOIS; nunca entra na decisão de calar."""
        self.falou.append(bool(falou))
        self.acertou.append(bool(acertou) if falou else False)

    def medida(self) -> Dict[str, Any]:
        """R04-UNC-03 · risco seletivo e cobertura, sempre juntos."""
        T = len(self.falou)
        if not T:
            return {"cobertura": 0.0, "risco": 1.0, "T": 0,
                    "motivo": "nada observado"}
        n = sum(1 for f in self.falou if f)
        if not n:
            return {"cobertura": 0.0, "risco": 0.0, "T": T,
                    "motivo": f"calou nas {T} rodadas"}
        erros = sum(1 for f, ok in zip(self.falou, self.acertou)
                    if f and not ok)
        return {
            "cobertura": n / T, "risco": erros / n, "n_falou": n, "T": T,
            "motivo": (f"falou em {n}/{T} ({n/T:.0%}) com risco seletivo "
                       f"{erros/n:.0%}"),
        }


def comparar(sem_silencio: Sequence[bool],
             com_silencio: Sequence[bool],
             falou: Sequence[bool]) -> Dict[str, Any]:
    """Calar melhorou? A conta que justifica (ou não) o silêncio.

    Sem esta comparação, abster-se é só reduzir a amostra. O ganho tem que
    aparecer como risco MENOR nas rodadas em que falou -- e ainda assim ele
    precisa ser lido junto da cobertura.
    """
    T = len(sem_silencio)
    if not T:
        return {"vale": False, "motivo": "sem dados"}
    risco_total = sum(1 for ok in sem_silencio if not ok) / T
    n = sum(1 for f in falou if f)
    if not n:
        return {"vale": False, "motivo": "calou sempre — nada a comparar"}
    risco_sel = sum(1 for f, ok in zip(falou, com_silencio)
                    if f and not ok) / n
    return {
        "vale": bool(risco_sel < risco_total),
        "risco_falando_sempre": risco_total,
        "risco_seletivo": risco_sel,
        "cobertura": n / T,
        "ganho": risco_total - risco_sel,
        "motivo": (f"risco {risco_total:.1%} falando sempre → {risco_sel:.1%} "
                   f"falando em {n/T:.0%} das rodadas "
                   f"(ganho {risco_total - risco_sel:+.1%})"),
    }
