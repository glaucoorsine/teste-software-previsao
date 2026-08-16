# -*- coding: utf-8 -*-
"""
A FAMÍLIA 12 DA RÉGUA DELE — constituição, veto e escalonamento final.

DE ONDE VEIO
────────────
    "cuidado com essas suas métricas aí que já atrapalhou antes"

Depois desse aviso ele mandou `A Régua da Capacidade de Previsão Quântica`,
300 páginas, 60 teorias em 12 famílias, escritas sobre exatamente o problema
que eu não conseguia resolver sozinho. A carta de abertura diz o essencial:

    "Uma afirmação pode coincidir com o resultado e ainda assim ser
     epistemicamente falsa se usou certeza maior do que seus dados permitiam."

É o diagnóstico dos meus três erros. Nas três vezes eu tinha o número certo e
a certeza errada.

A FAMÍLIA 12 É A QUE FALTAVA
────────────────────────────
As outras onze medem. A décima segunda IMPEDE:

    R12-VET-01  Porta de Integridade Fatal   G_h = Π_j g_h,j , g ∈ {0,1}
    R12-VET-02  Tamanho Efetivo              n_eff ≈ n/[1+2Σ_k ρ_k]
    R12-VET-03  Controle Negativo Obrigatório CVeto = 1{T_obs sai do envelope}
    R12-VET-04  Contradição Irredutível      Contr = max_j[s_j·q_j·r_j]
    R12-VET-05  Constitucional do Não Concluir

A diferença entre medir e vetar é o PRODUTO. Uma média boa esconde uma falha
de integridade; um produto de portas binárias, não. Se qualquer g_h,j é zero,
G_h é zero, e nenhuma taxa bonita levanta isso. É o que ele chama de porta
fatal, e é o que faltava no meu placar.

E A R12-VET-02 EXPLICA MEU ERRO MAIOR
─────────────────────────────────────
Eu media a Lightning andando para trás e dava 1,317x com p=0,0025 sobre 206
previsões. Na separação disjunta caía para 1,070x, p=0,26. Eu sabia que o
desenho inflava, mas não sabia POR QUANTO.

    n_eff ≈ n / [1 + 2·Σ_k ρ_k]

As 206 previsões da caminhada compartilhavam quase todo o histórico entre si:
eram fortemente autocorrelacionadas. O n efetivo era uma fração de 206, e o
p-valor calculado sobre 206 estava errado por construção. A fórmula dele
mede isso em vez de eu ter que adivinhar.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

# Autocorrelações até este atraso entram na conta do n efetivo.
K_AUTOCORR = 30


# ═══════════════════════════════════════════════════════ R12-VET-02

def tamanho_efetivo(serie: Sequence[float], k_max: int = K_AUTOCORR) -> Dict[str, Any]:
    """R12-VET-02 · Régua do Tamanho Efetivo.

        n_eff ≈ n / [1 + 2·Σ_(k=1)^K ρ_k]

    Quantas observações INDEPENDENTES existem de fato. Medições que
    compartilham histórico não são n medições -- e o p-valor calculado sobre n
    quando o efetivo é n/5 mente por um fator de raiz de 5.

    A soma para no primeiro ρ_k negativo (regra usual de janela inicial), senão
    o ruído da cauda entra na conta e infla n_eff de volta.
    """
    x = [float(v) for v in serie or []]
    n = len(x)
    if n < 10:
        return {"n": n, "n_eff": float(n), "fator": 1.0,
                "motivo": "série curta demais para medir autocorrelação"}
    m = sum(x) / n
    var = sum((v - m) ** 2 for v in x) / n
    if var <= 0:
        return {"n": n, "n_eff": 1.0, "fator": float(n),
                "motivo": "série constante — uma observação efetiva"}
    soma = 0.0
    usados = 0
    for k in range(1, min(k_max, n // 3) + 1):
        rho = sum((x[t] - m) * (x[t + k] - m) for t in range(n - k)) / ((n - k) * var)
        if rho <= 0:
            break                      # janela inicial: para no primeiro negativo
        soma += rho
        usados = k
    fator = 1.0 + 2.0 * soma
    n_eff = n / fator if fator > 0 else float(n)
    return {
        "n": n, "n_eff": n_eff, "fator": fator, "atrasos": usados,
        "motivo": (f"{n} medições valem {n_eff:.0f} independentes "
                   f"(fator {fator:.2f} sobre {usados} atrasos)"),
    }


def previsoes_efetivas(previsoes: Sequence[Sequence[str]]) -> Dict[str, Any]:
    """R12-VET-02 aplicada à PREVISÃO, não ao acerto — e é aqui que eu errava.

    Medi a Lightning andando para trás e dei 1,317x com p=0,0025 sobre 206
    previsões. O n_eff da série de ACERTOS dava 156: quase nada. Só que a
    autocorrelação que importava não era a dos acertos, era a das previsões:

        206 previsões, mas só 47 DISTINTAS (23%)
        entre passos consecutivos muda 0,28 número de 12
        duas previsões quaisquer compartilham 6,4 dos 12

    Ou seja: eu não fiz 206 testes. Fiz 47 testes de uma hipótese quase
    constante, e calculei o p como se fossem 206. É por isso que 1,317x virou
    1,070x na separação disjunta -- lá são dois testes de verdade.

    Esta função devolve o número que eu deveria ter olhado antes de abrir a
    boca.
    """
    lst = [frozenset(str(x) for x in p) for p in (previsoes or []) if p]
    n = len(lst)
    if n < 2:
        return {"n": n, "distintas": n, "n_eff": float(n),
                "motivo": "menos de duas previsões"}
    distintas = len(set(lst))
    tam = sum(len(p) for p in lst) / n
    # sobreposição média entre previsões consecutivas
    comp = [len(lst[i] & lst[i + 1]) / max(1, len(lst[i] | lst[i + 1]))
            for i in range(n - 1)]
    jac = sum(comp) / len(comp)
    return {
        "n": n, "distintas": distintas, "n_eff": float(distintas),
        "tamanho_medio": tam, "sobreposicao": jac,
        "motivo": (f"{n} previsões, {distintas} distintas ({distintas/n:.0%}); "
                   f"consecutivas se sobrepõem em {jac:.0%}"),
    }


# ═══════════════════════════════════════════════════════ R12-VET-03

def controle_negativo_obrigatorio(observado: float,
                                  envelope: Sequence[float],
                                  alfa: float = 0.05) -> Dict[str, Any]:
    """R12-VET-03 · Régua do Controle Negativo Obrigatório.

        CVeto_h = 1{ T_h^obs se distingue do envelope N_h }

    OBRIGATÓRIO é a palavra que importa: sem envelope de controle não há
    conclusão, e a ausência dele não é neutra -- é veto. Antes eu tratava
    "não rodei o controle" como se fosse "o controle passou".
    """
    env = sorted(float(v) for v in (envelope or []))
    if len(env) < 10:
        return {"passa": False, "motivo": (f"envelope com {len(env)} controles — "
                                           f"sem controle não há conclusão")}
    acima = sum(1 for v in env if v >= observado)
    p = (acima + 1) / (len(env) + 1)
    corte = env[min(len(env) - 1, int((1 - alfa) * len(env)))]
    return {
        "passa": bool(p < alfa),
        "p": p, "corte": corte, "observado": observado, "controles": len(env),
        "motivo": (f"{observado:.3f} contra envelope de {len(env)} "
                   f"(p95={corte:.3f}) — p={p:.3f}"),
    }


# ═══════════════════════════════════════════════════════ R12-VET-01

def porta_de_integridade(portas: Dict[str, bool]) -> Dict[str, Any]:
    """R12-VET-01 · Régua da Porta de Integridade Fatal.

        G_h = Π_(j=1)^J g_h,j ,  g_h,j ∈ {0,1}

    Produto, não média. Uma média deixa a taxa boa compensar o vazamento; o
    produto não deixa. Se qualquer porta é zero, G é zero e a conclusão está
    vetada, por melhor que esteja o placar.

    É a diferença entre "quase tudo certo" e "íntegro", e as minhas três
    falhas foram todas "quase tudo certo".
    """
    G = 1
    reprovadas = []
    for nome, ok in (portas or {}).items():
        if not ok:
            G = 0
            reprovadas.append(nome)
    return {
        "G": G, "integro": G == 1, "reprovadas": reprovadas,
        "motivo": ("todas as portas de integridade abertas" if G
                   else "VETADO por: " + ", ".join(reprovadas)),
    }


# ═══════════════════════════════════════════════════════ R12-VET-04

def contradicao_irredutivel(contras: List[Dict[str, float]]) -> Dict[str, Any]:
    """R12-VET-04 · Régua da Contradição Irredutível.

        Contr_h = max_j [ s_j · q_j · r_j ]

    Severidade x qualidade x relevância. Uma contradição forte e bem medida
    não é diluída pela quantidade de evidência a favor -- o máximo, não a
    média, porque uma objeção fatal não some por estar cercada de concordância.
    """
    if not contras:
        return {"contr": 0.0, "motivo": "nenhuma contradição registrada"}
    pior = max(contras,
               key=lambda c: (float(c.get("severidade", 0))
                              * float(c.get("qualidade", 0))
                              * float(c.get("relevancia", 0))))
    v = (float(pior.get("severidade", 0)) * float(pior.get("qualidade", 0))
         * float(pior.get("relevancia", 0)))
    return {"contr": v, "pior": pior.get("nome", "?"),
            "motivo": f"contradição mais forte: {pior.get('nome','?')} ({v:.2f})"}


# ═══════════════════════════════════════════════════════ R12-VET-05

VETADO = "VETADO"
DORMENTE = "DORMENTE"
NAO_CONCLUIR = "NAO_CONCLUIR"
PODE_AFIRMAR = "PODE_AFIRMAR"


def decisao(integridade: Dict[str, Any],
            controle: Dict[str, Any],
            n_eff: Dict[str, Any],
            contradicao: Optional[Dict[str, Any]] = None,
            estabilidade: float = 1.0,
            n_eff_minimo: float = 30.0) -> Dict[str, Any]:
    """R12-VET-05 · Régua Constitucional do Não Concluir.

        Decision_h = vetado          se G_h = 0
                     dormente        se Contr_h domina a estabilidade
                     não concluir    se o suporte efetivo não sustenta
                     pode afirmar    caso contrário

    A ordem importa: integridade primeiro, contradição depois, suporte por
    último. Um placar excelente com n_eff de 6 não vira conclusão, e essa é a
    trava que me faltava -- eu vinha concluindo a partir do placar.
    """
    if not integridade.get("integro"):
        return {"decisao": VETADO, "porque": integridade.get("motivo", "")}
    c = (contradicao or {}).get("contr", 0.0)
    if c > estabilidade:
        return {"decisao": DORMENTE,
                "porque": (f"contradição ({c:.2f}) domina a estabilidade "
                           f"({estabilidade:.2f}) — "
                           + (contradicao or {}).get("motivo", ""))}
    ne = float(n_eff.get("n_eff", 0))
    if ne < n_eff_minimo:
        return {"decisao": NAO_CONCLUIR,
                "porque": (f"suporte efetivo de {ne:.0f} observações "
                           f"(mínimo {n_eff_minimo:.0f}) — "
                           + n_eff.get("motivo", ""))}
    if not controle.get("passa"):
        return {"decisao": NAO_CONCLUIR,
                "porque": "controle negativo não separou — "
                          + controle.get("motivo", "")}
    return {"decisao": PODE_AFIRMAR,
            "porque": (f"integridade íntegra, controle separou "
                       f"(p={controle.get('p', 1):.3f}), suporte efetivo "
                       f"{ne:.0f}")}


# ═══════════════════════════════════════════════ R04-UNC-03 (direito de calar)

def direito_de_silencio(acertos: Sequence[bool],
                        emitiu: Sequence[bool]) -> Dict[str, Any]:
    """R04-UNC-03 · Régua do Direito de Silêncio.

        risco seletivo R_sel = Σ_t a_t·ℓ_t / Σ_t a_t
        cobertura      Cov    = Σ_t a_t / T

    Calar não é falhar. O que se mede em quem se cala é o risco NAS RODADAS EM
    QUE FALOU, junto da fração em que falou -- as duas coisas, sempre juntas,
    porque risco baixo com cobertura de 2% não é habilidade, é seleção.
    """
    T = len(list(emitiu))
    if not T:
        return {"cobertura": 0.0, "risco": 1.0, "motivo": "nada observado"}
    a = [1 if e else 0 for e in emitiu]
    perdas = [0 if ok else 1 for ok in acertos]
    n_falou = sum(a)
    if not n_falou:
        return {"cobertura": 0.0, "risco": 0.0,
                "motivo": f"calou em todas as {T} rodadas"}
    risco = sum(ai * li for ai, li in zip(a, perdas)) / n_falou
    cob = n_falou / T
    return {"cobertura": cob, "risco": risco, "n_falou": n_falou, "T": T,
            "motivo": (f"falou em {n_falou}/{T} ({cob:.0%}) com risco "
                       f"seletivo {risco:.0%}")}


# ═══════════════════════════════════════════════ R08-ENS-02 (vozes reais)

def n_efetivo_de_ias(erros_por_ia: Dict[str, Sequence[float]]) -> Dict[str, Any]:
    """R08-ENS-02 · Régua do Número Efetivo de IAs.

        N_eff = (Σ_j λ_j)² / Σ_j λ_j²   — λ_j autovalores da matriz de correlação

    Quarenta leituras que erram junto não são quarenta testemunhas. Aqui, sem
    álgebra linear no pacote, N_eff sai da correlação média entre os erros, que
    é a aproximação usual e suficiente para o tamanho de painel deste software.
    """
    nomes = [k for k, v in (erros_por_ia or {}).items() if len(v or []) >= 5]
    A = len(nomes)
    if A < 2:
        return {"n_eff": float(A), "ias": A, "motivo": "menos de duas com dado"}
    n = min(len(erros_por_ia[k]) for k in nomes)
    cols = {k: [float(x) for x in list(erros_por_ia[k])[:n]] for k in nomes}
    med = {k: sum(v) / n for k, v in cols.items()}
    sd = {k: math.sqrt(sum((x - med[k]) ** 2 for x in v) / n) or 1e-9
          for k, v in cols.items()}
    soma = 0.0
    pares = 0
    for i in range(A):
        for j in range(i + 1, A):
            a, b = nomes[i], nomes[j]
            cov = sum((cols[a][t] - med[a]) * (cols[b][t] - med[b])
                      for t in range(n)) / n
            soma += cov / (sd[a] * sd[b])
            pares += 1
    rho = soma / pares if pares else 0.0
    n_eff = A / (1 + (A - 1) * max(0.0, rho))
    return {"n_eff": n_eff, "ias": A, "rho_medio": rho,
            "motivo": (f"{A} leituras com correlação média {rho:.2f} "
                       f"valem {n_eff:.1f} vozes independentes")}
