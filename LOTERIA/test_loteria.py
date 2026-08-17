# -*- coding: utf-8 -*-
"""
TESTE DA BASE DA LOTERIA — regras, probabilidade exata, base e fechamento.

O QUE CADA PARTE ARRISCA, E O QUE O TESTE FAZ CONTRA ISSO
─────────────────────────────────────────────────────────
REGRAS      Escrevi de memória e não pude conferir contra a Caixa. Regra errada
            não dá erro: dá probabilidade plausível e falsa. O teste confere o
            que é conferível sozinho -- a hipergeométrica tem de somar 1, e os
            números famosos (1 em 50 milhões na Mega-Sena) têm de bater.

FECHAMENTO  Uma garantia entregue sem prova é a pior coisa que este software
            pode fazer: ele gastaria dinheiro dele confiando numa promessa que
            ninguém verificou. Então o teste PLANTA um fechamento incompleto e
            exige que `conferir()` o reprove. Um verificador que só sabe
            aprovar não verifica nada.

BASE        Um item sem "o que me derrubaria" é opinião com número. O teste
            tenta cadastrar um assim e exige recusa.
"""
from __future__ import annotations

import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import regras as R                    # noqa: E402
from NUCLEO import base_conhecimento as B         # noqa: E402
from NUCLEO import fechamento as F                # noqa: E402

FALHAS = []


def checar(ok, titulo, detalhe=""):
    print(f"  {'ok  ' if ok else 'FALHA'} {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(titulo)
    return ok


# ═══════════════════════════════════════════ 1. as regras e o acaso exato
def teste_regras():
    print("\n[1] REGRAS E ACASO — o número exato, não estimativa")
    ms = R.jogo("mega_sena")
    checar(ms and ms.universo == 60 and ms.sorteadas == 6,
           "Mega-Sena: 60 dezenas, saem 6")

    # o número que todo mundo conhece: 1 em 50.063.860
    p = ms.p_faixa(6, 6)
    checar(abs(1 / p - 50_063_860) < 1,
           "aposta de 6 acerta a sena: 1 em 50.063.860",
           f"1 em {1/p:,.0f}".replace(",", "."))
    checar(comb(60, 6) == 50_063_860, "e C(60,6) confirma o mesmo número")

    # a hipergeométrica tem de somar 1 -- se não somar, está errada
    for chave in ("mega_sena", "quina", "lotofacil", "dupla_sena"):
        j = R.jogo(chave)
        k = j.minimo
        soma = sum(j.p_exato(k, a) for a in range(0, min(k, j.sorteadas) + 1))
        checar(abs(soma - 1.0) < 1e-9,
               f"{j.nome}: as probabilidades de 0..{min(k, j.sorteadas)} "
               f"acertos somam 1", f"{soma:.12f}")

    # aposta de 7 na Mega: exatamente 7 vezes mais chance de sena que a de 6
    checar(abs(ms.p_faixa(7, 6) / ms.p_faixa(6, 6) - 7.0) < 1e-9,
           "aposta de 7 dezenas tem 7x a chance de sena da aposta de 6 — "
           "C(7,6)=7, e é assim que o preço tem de ser comparado")

    # acertos médios: a régua contra a qual toda teoria será medida
    lf = R.jogo("lotofacil")
    checar(abs(lf.acertos_esperados(15) - 9.0) < 1e-9,
           "Lotofácil: quem aposta 15 acerta 9 em média — 'acertei 9' não é "
           "achado", f"{lf.acertos_esperados(15)}")

    # a soma das faixas nunca pode passar de 1
    for chave in ("mega_sena", "quina", "lotofacil"):
        j = R.jogo(chave)
        checar(0 < j.p_algum_premio(j.minimo) <= 1.0,
               f"{j.nome}: chance de algum prêmio é uma probabilidade válida",
               f"{j.p_algum_premio(j.minimo):.6f}")

    # a Lotomania começa no ZERO -- e zero acerto paga
    lm = R.jogo("lotomania")
    checar(lm.dezenas()[0] == 0 and lm.dezenas()[-1] == 99,
           "Lotomania vai de 0 a 99")
    checar(0 in lm.faixas, "e ZERO acerto paga nela — o único caso assim")
    checar(abs(lm.p_exato(50, 0) - lm.p_faixa(50, 0)) < 1e-15,
           "a faixa de 0 acertos é calculada como qualquer outra",
           f"1 em {1/lm.p_exato(50,0):,.0f}".replace(",", "."))


def teste_aposta_valida():
    print("\n[2] A APOSTA TEM QUE SER LEGAL — antes de qualquer cálculo")
    ms = R.jogo("mega_sena")
    ok, _ = ms.valida_aposta([1, 2, 3, 4, 5, 6])
    checar(ok, "aposta mínima de 6 é aceita")
    ok, m = ms.valida_aposta([1, 2, 3, 4, 5])
    checar(not ok and "6 a 20" in m, "5 dezenas é recusada com o motivo", m)
    ok, m = ms.valida_aposta([1, 2, 3, 4, 5, 61])
    checar(not ok and "fora do universo" in m, "dezena 61 é recusada", m)
    ok, m = ms.valida_aposta([1, 1, 2, 3, 4, 5])
    checar(not ok and "repetida" in m, "dezena repetida é recusada", m)
    ok, _ = R.jogo("lotomania").valida_aposta(list(range(0, 50)))
    checar(ok, "na Lotomania o 0 é dezena legítima")


def teste_conferir_com_api():
    print("\n[3] AS REGRAS QUE ESCREVI DE MEMÓRIA DESCONFIAM DE MIM")
    checar(all(v is False for v in R.conferidos().values()),
           "nenhum jogo nasce 'conferido' — não conferi contra a Caixa")
    bons = [[4, 12, 23, 31, 45, 58], [1, 9, 17, 22, 38, 60]]
    r = R.conferir_com_api("mega_sena", bons)
    checar(r["ok"] and R.jogo("mega_sena").conferido,
           "sorteios reais de 6 dezenas em 1..60 confirmam a regra", r["nota"])
    # e o caso que importa: dado que NÃO bate tem de reprovar
    r2 = R.conferir_com_api("quina", [[1, 2, 3, 4, 5, 6, 7]])
    checar(not r2["ok"] and any("sorteadas" in p for p in r2["problemas"]),
           "sorteio com quantidade diferente REPROVA a regra que escrevi",
           r2["problemas"][0][:70])
    r3 = R.conferir_com_api("mega_sena", [[1, 2, 3, 4, 5, 99]])
    checar(not r3["ok"], "dezena fora do universo também reprova",
           (r3["problemas"] or [""])[0][:70])


# ═══════════════════════════════════════════════ 4. a base de conhecimento
def teste_base():
    print("\n[4] A BASE — sem 'o que me derrubaria', não entra")
    itens = B.tudo()
    checar(len(itens) >= 9, f"a base já nasce com {len(itens)} itens")
    checar(all(i.derruba.strip() for i in itens),
           "TODO item diz o que o derrubaria")
    checar(all(i.como_medir.strip() for i in itens),
           "e todo item diz como seria medido")

    # o portão: opinião sem falsificação é recusada
    try:
        B.acrescentar("X99", "palpite", afirma="o 7 é um número de sorte",
                      como_medir="", derruba="", origem=B.MINHA)
        checar(False, "item sem falsificação DEVE ser recusado")
    except ValueError as e:
        checar("derrubaria" in str(e),
               "item sem 'o que me derrubaria' é recusado, com o motivo",
               str(e)[:70])

    # uma teoria dele entra normalmente, com a mesma exigência
    it = B.acrescentar(
        "D01", "teste de teoria dele",
        afirma="exemplo para o teste",
        como_medir="comparar com o acaso exato da mesma aposta",
        derruba="a taxa ficar dentro do intervalo de confiança do acaso",
        origem=B.DELE, aplica_a=("mega_sena",))
    checar(it.origem == B.DELE and it.serve_para("mega_sena"),
           "teoria dele entra na base e fica marcada como dele")
    checar(not it.serve_para("quina"),
           "e vale só para o jogo em que ele disse que vale")

    # o portão de procedência: derrubado cala
    checar(B.autorizada("C01"), "item ainda não medido pode ser citado")
    B.registrar_veredito("C01", "derrubado", {"razao": 1.0, "n": 4000})
    checar(not B.autorizada("C01"),
           "item DERRUBADO pela medida não autoriza mais nenhum jogo")
    checar(B.autorizada("M01"), "e derrubar um não cala os outros")
    txt = " ".join(B.resumo())
    checar("DERRUBADO" in txt, "e o resumo mostra isso na cara",
           [L for L in B.resumo() if "DERRUBADO" in L][:1])
    B.registrar_veredito("C01", "sem_base", {})   # devolve para os outros testes

    # o item que pode render sem prever nada
    p01 = B.por_id("P01")
    checar(p01 and p01.origem == B.MATEMATICA,
           "a partilha do prêmio está na base como MATEMÁTICA, não como crença",
           p01.titulo if p01 else "")


# ══════════════════════════════════════ 5. o fechamento, e a prova dele
def teste_fechamento():
    print("\n[5] FECHAMENTO — garantia provada, ou nenhuma garantia")
    dez = list(range(1, 11))          # 10 dezenas
    r = F.montar(dez, k=6, acertos_previstos=5, garantir=4)
    checar(r["ok"], "fecha 10 dezenas com garantia de quadra para 5 acertos",
           f"{r['n_apostas']} apostas contra {r['custo_de_cobrir_tudo']} de "
           f"cobrir tudo")

    # A PROVA, exaustiva
    prova = F.conferir(r["apostas"], dez, 5, 4)
    checar(prova["provado"],
           f"e a garantia é PROVADA em todos os {prova['casos_testados']} casos",
           prova["nota"][:70])
    checar(prova["casos_testados"] == comb(10, 5),
           "testou C(10,5) casos — todos, não uma amostra",
           f"{prova['casos_testados']} = C(10,5)")

    # ── O TESTE QUE IMPORTA: verificador que só aprova não verifica ──────
    incompleto = r["apostas"][:-1]
    p2 = F.conferir(incompleto, dez, 5, 4)
    checar(not p2["provado"] and p2["falhas"],
           "tirando UMA aposta, a prova REPROVA e mostra o caso descoberto",
           f"primeiro descoberto: {p2['falhas'][0] if p2['falhas'] else '—'}")
    p3 = F.conferir([dez[:6]], dez, 5, 4)
    checar(not p3["provado"],
           "uma aposta só não garante nada, e a prova diz isso")

    # ── pedidos impossíveis são recusados, não 'quase atendidos' ─────────
    imp = F.montar(dez, k=6, acertos_previstos=3, garantir=4)
    checar(not imp["ok"] and "não pode prometer mais acerto" in imp["nota"],
           "garantir 4 acertos com só 3 dezenas saindo é recusado",
           imp["nota"][:70])
    imp2 = F.montar(dez, k=6, acertos_previstos=5, garantir=7)
    checar(not imp2["ok"],
           "garantir 7 acertos numa aposta de 6 é recusado")
    imp3 = F.montar([1, 2, 3], k=6, acertos_previstos=3, garantir=2)
    checar(not imp3["ok"], "aposta maior que o conjunto escolhido é recusada")

    # ── a economia é real e verificável ──────────────────────────────────
    dez12 = list(range(1, 13))
    r12 = F.montar(dez12, k=6, acertos_previstos=5, garantir=4)
    if r12["ok"]:
        prova12 = F.conferir(r12["apostas"], dez12, 5, 4)
        checar(prova12["provado"] and r12["n_apostas"] < comb(12, 6),
               f"12 dezenas: {r12['n_apostas']} apostas provadas contra "
               f"{comb(12,6)} de cobrir tudo",
               f"economia de {r12['economia']} apostas com a MESMA garantia")
        for L in F.resumo(r12, prova12):
            print(f"        {L}")

    # ── e o software nunca chama isto de ótimo ───────────────────────────
    checar(r.get("otimo") is False,
           "o fechamento não se declara o MENOR possível — isso é problema em "
           "aberto da matemática, e prometer seria mentira")


def main() -> int:
    print("═" * 72)
    print("LOTERIA — a base: regras exatas, conhecimento falsificável, garantia")
    print("═" * 72)
    teste_regras()
    teste_aposta_valida()
    teste_conferir_com_api()
    teste_base()
    teste_fechamento()
    print("\n" + "═" * 72)
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"  ✗ {f}")
        return 1
    print("LOTERIA_BASE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
