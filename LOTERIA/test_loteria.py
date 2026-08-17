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

import json
import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import regras as R                    # noqa: E402
from NUCLEO import base_conhecimento as B         # noqa: E402
from NUCLEO import fechamento as F                # noqa: E402
from NUCLEO import estatistica as E               # noqa: E402
from NUCLEO import historico as H                 # noqa: E402
from NUCLEO import medidor as MD                  # noqa: E402
from NUCLEO import api as API                     # noqa: E402

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

    # O DEFEITO QUE SÓ APARECEU NA TELA: o mesmo problema, com as dezenas
    # renomeadas, fechava em 15 apostas num caso e em 20 ou 21 noutro. A ordem
    # de iteração de um `set` depende dos VALORES guardados, e ele pagaria as
    # apostas a mais por causa disso. Renomear as dezenas não muda o problema,
    # então não pode mudar o tamanho da resposta.
    tres = [list(range(1, 13)),
            sorted([3, 7, 12, 19, 24, 31, 38, 45, 52, 58, 11, 27]),
            sorted([2, 9, 14, 21, 26, 33, 40, 47, 54, 60, 5, 17])]
    tamanhos = []
    for dz in tres:
        rr = F.montar(dz, k=6, acertos_previstos=5, garantir=4)
        pp = F.conferir(rr["apostas"], dz, 5, 4)
        tamanhos.append(rr["n_apostas"] if pp["provado"] else -1)
    checar(len(set(tamanhos)) == 1 and tamanhos[0] > 0,
           "as MESMAS 12 dezenas renomeadas fecham no mesmo tamanho — o "
           "resultado sai da estrutura do problema, não da ordem de um set",
           f"{tamanhos} apostas")

    # e rodar duas vezes tem de dar o mesmo conjunto: sem isso ele não consegue
    # conferir o meu resultado, nem repetir a aposta da semana passada.
    a1 = F.montar(list(range(1, 13)), k=6, acertos_previstos=5, garantir=4)
    a2 = F.montar(list(range(1, 13)), k=6, acertos_previstos=5, garantir=4)
    checar(a1["apostas"] == a2["apostas"],
           "e duas execuções devolvem exatamente as mesmas apostas")



# ═══════════════════════════════════ 6. a régua, conferida contra tabela
def teste_estatistica():
    print("\n[6] ESTATÍSTICA — a régua conferida fora dela mesma")

    # os valores clássicos de tabela do qui-quadrado. Se estes não baterem,
    # todo p-valor deste software está errado -- e errado é pior que ausente,
    # porque ausente deixa sem conclusão e errado deixa com a conclusão trocada.
    checar(abs(E.p_qui2(3.841459, 1) - 0.05) < 0.001,
           "qui² 3,841 com 1 grau dá p = 0,05 (valor de tabela)",
           f"deu {E.p_qui2(3.841459, 1):.4f}")
    checar(abs(E.p_qui2(11.0705, 5) - 0.05) < 0.001,
           "qui² 11,07 com 5 graus dá p = 0,05 (valor de tabela)",
           f"deu {E.p_qui2(11.0705, 5):.4f}")
    checar(abs(E.p_qui2(23.2093, 10) - 0.01) < 0.001,
           "qui² 23,21 com 10 graus dá p = 0,01 (valor de tabela)",
           f"deu {E.p_qui2(23.2093, 10):.4f}")
    checar(E.p_qui2(0.0, 3) == 1.0, "qui² zero dá p = 1")

    lo, hi = E.wilson(0, 100)
    checar(lo >= 0.0, "Wilson com zero acerto não desce abaixo de zero — que é "
                      "onde a fórmula de escola mente", f"[{lo:.4f}, {hi:.4f}]")
    lo, hi = E.wilson(500, 1000)
    checar(lo < 0.5 < hi, "e contém a taxa verdadeira numa moeda honesta")

    d = E.distribuicao_soma(60, 6)
    checar(sum(d.values()) == comb(60, 6),
           "a tabela de somas soma exatamente C(60,6) — nenhum caminho "
           "perdido nem contado duas vezes", f"{sum(d.values()):,}".replace(",", "."))
    checar(min(d) == 21 and max(d) == 345,
           "e vai de 1+2+3+4+5+6=21 até 55+56+57+58+59+60=345")
    checar(d[21] == 1 and d[345] == 1, "com uma única combinação em cada ponta")

    di = E.distribuicao_impares(25, 15)
    checar(sum(di.values()) == comb(25, 15),
           "a tabela de ímpares soma exatamente C(25,15)")

    iguais = E.teste_permutacao([1, 2, 3, 4, 5] * 6, [1, 2, 3, 4, 5] * 6, 2000)
    checar(iguais["p"] > 0.5, "permutação: grupos idênticos não acusam diferença",
           f"p = {iguais['p']:.3f}")
    difs = E.teste_permutacao([10, 11, 12, 11, 10] * 6, [1, 2, 3, 2, 1] * 6, 2000)
    checar(difs["p"] < 0.01, "permutação: grupos claramente diferentes acusam",
           f"p = {difs['p']:.4f}")

    # o teste que corrige o meu erro do outro software
    checar(E.poder_basta(100, 0.1)["basta"] is False,
           "com 100 observações a régua ADMITE que não daria para notar um "
           "efeito de 10% — não medir e não achar não são a mesma coisa")
    checar(E.poder_basta(100_000, 0.1)["basta"] is True,
           "com 100 mil, daria")


# ═══════════════════════════ 7. a porta de entrada dos sorteios reais
def _escrever(nome, texto):
    d = RAIZ / "_teste_tmp"
    d.mkdir(exist_ok=True)
    p = d / nome
    p.write_text(texto, encoding="utf-8")
    return p


def teste_historico():
    print("\n[7] HISTÓRICO — ler o arquivo dele sem inventar o que não leu")

    csv = ("Concurso;Data do Sorteio;Bola1;Bola2;Bola3;Bola4;Bola5;Bola6;"
           "Ganhadores 6 acertos;Ganhadores 4 acertos;Arrecadacao Total\n"
           "1;11/03/1996;04;05;30;33;41;52;0;2016;R$ 1.000.000,00\n"
           "2;18/03/1996;09;37;39;41;43;49;1;1900;R$ 1.200.000,00\n"
           "3;25/03/1996;10;11;29;30;36;47;0;2100;R$ 900.000,00\n")
    h, avisos = H.de_arquivo(_escrever("mega.csv", csv), "mega_sena")
    checar(h is not None and len(h) == 3,
           "lê o CSV no formato da Caixa (Bola1..Bola6)",
           f"{len(h) if h else 0} concursos, {avisos}")
    checar(h and h.concursos[0]["dezenas"] == [4, 5, 30, 33, 41, 52],
           "e as dezenas saem certas, com o zero à esquerda")
    checar(h and h.concursos[0]["ganhadores"] == {6: 0, 4: 2016},
           "e os ganhadores por faixa vêm junto — é o que permite medir P01")
    checar(h and abs((h.concursos[0]["arrecadacao"] or 0) - 1_000_000.0) < 1,
           "e a arrecadação em formato brasileiro vira número",
           f"{h.concursos[0]['arrecadacao'] if h else None}")
    checar(h and h.conferido, "e o arquivo confere com as regras declaradas")
    checar(h and len(h.sha256) == 64,
           "e o histórico carrega a soma de verificação do arquivo — trocou o "
           "arquivo, a medição anterior deixa de valer para o novo")

    js = ('[{"concurso": 2700, "data": "01/02/2024", '
          '"dezenas": ["01","02","03","04","05","06"], '
          '"premiacoes": [{"descricao": "6 acertos", "ganhadores": 0}]}]')
    h2, _ = H.de_arquivo(_escrever("mega.json", js), "mega_sena")
    checar(h2 is not None and h2.concursos[0]["dezenas"] == [1, 2, 3, 4, 5, 6],
           "lê também o JSON das APIs, com as premiações")

    h3, _ = H.de_arquivo(_escrever("mega.txt", "1 2 3 4 5 6\n7 8 9 10 11 12\n"),
                         "mega_sena")
    checar(h3 is not None and len(h3) == 2, "e o texto solto, uma linha por sorteio")

    # O QUE MAIS IMPORTA AQUI: arquivo que contradiz as regras não passa.
    ruim = ("Concurso;Bola1;Bola2;Bola3;Bola4;Bola5;Bola6\n"
            "1;04;05;30;33;41;61\n2;09;37;39;41;43;70\n")
    h4, _ = H.de_arquivo(_escrever("ruim.csv", ruim), "mega_sena")
    checar(h4 is None or not h4.conferido,
           "arquivo com dezena fora do universo NÃO entra conferido")
    if h4:
        ok, motivo = h4.pronto_para_medir()
        checar(not ok, "e o histórico se recusa a ser medido", motivo[:70])
        r = MD.medir_C01(h4)
        checar(r["veredito"] == "sem_base",
               "e o medidor devolve sem_base em vez de número plausível e falso")
        checar(any("NÃO confere" in l for l in h4.diagnostico()),
               "e o diagnóstico mostra isso na cara, para ele conferir de olho")

    vazio, av = H.de_arquivo(_escrever("nada.csv", "isto aqui não é sorteio\n"),
                             "mega_sena")
    checar(vazio is None, "arquivo sem sorteio nenhum devolve nada, e diz por quê",
           str(av[-1])[:60] if av else "")

    faltando, av2 = H.de_arquivo(RAIZ / "_teste_tmp" / "não_existe.csv", "mega_sena")
    checar(faltando is None, "arquivo que não existe não vira histórico vazio")


# ══════════════════ 8. o medidor, provado nos dois lados
def teste_medidor():
    print("\n[8] MEDIDOR — acha o que existe, e fica calado onde não há")

    # a base pode ter sido mexida pelos testes anteriores; limpo antes de medir
    for ident in ("C01", "C02", "C03", "C04", "P01"):
        it = B.por_id(ident)
        if it:
            it.veredito, it.medida = None, {}

    # ── controle negativo: sorteio honesto ────────────────────────────────
    uniforme = H.sintetico_uniforme("mega_sena", 3000)
    c01 = MD.medir_C01(uniforme)
    checar(c01["veredito"] != "confirmado",
           "sorteio uniforme: o medidor NÃO acha vantagem em dezena atrasada",
           f"{c01['veredito']} — taxa {c01['taxa']:.4f} contra acaso {c01['acaso']:.4f}")
    c02 = MD.medir_C02(uniforme)
    checar(c02["veredito"] != "confirmado",
           "nem em dezena quente", f"{c02['veredito']} — taxa {c02['taxa']:.4f}")
    c03 = MD.medir_C03(uniforme)
    checar(c03["veredito"] == "derrubado",
           "e a soma observada coincide com a combinatória, como tem de coincidir",
           f"p = {c03['qui2']['p']:.3f}")
    c04 = MD.medir_C04(uniforme)
    checar(c04["veredito"] == "derrubado",
           "e o par/ímpar também — o 'equilíbrio' é contagem de combinação",
           f"p = {c04['qui2']['p']:.3f}")

    # ── controle positivo: efeito plantado ────────────────────────────────
    # Sem esta metade, o medidor poderia estar quebrado dizendo sempre "não" e
    # acertando por acidente em sorteio honesto. Um medidor cego não vale nada
    # justamente quando ele diz "não se sustentou" nos dados dele.
    viciado = H.sintetico_viciado("mega_sena", 3000, forca=3.0)
    v01 = MD.medir_C01(viciado)
    checar(v01["veredito"] == "confirmado",
           "sorteio com atraso viciado DE PROPÓSITO: o medidor acha o efeito",
           f"taxa {v01['taxa']:.4f} contra acaso {v01['acaso']:.4f}")
    checar(v01["intervalo95"][0] > v01["acaso"],
           "e o intervalo inteiro fica acima do acaso, não só a média")

    # ── o n curto não derruba nada ────────────────────────────────────────
    curto = H.sintetico_uniforme("mega_sena", 70)
    cc = MD.medir_C01(curto)
    checar(cc["veredito"] == "sem_base",
           "com 70 concursos a resposta é SEM BASE, não 'derrubado' — este era "
           "o meu erro no outro software", cc["porque"][-1][:80])

    # ── a trava contra o meu próprio teste ────────────────────────────────
    antes = B.por_id("C01").veredito
    med = MD.medir_tudo(viciado, gravar=True)
    checar(B.por_id("C01").veredito == antes and not med["gravou"],
           "veredito de histórico SINTÉTICO não entra na base, nem com "
           "gravar=True — eu inventei esse dado, e ele leria como achado dele",
           med["nota"][:60])

    # ── e o de verdade entra ──────────────────────────────────────────────
    real = H.Historico("mega_sena", uniforme.concursos,
                       fonte="arquivo de teste com procedência declarada",
                       sha256="a" * 64)
    med2 = MD.medir_tudo(real, gravar=True)
    checar("C01" in med2["gravou"] and B.por_id("C01").veredito is not None,
           "histórico com procedência declarada grava o veredito na base",
           f"gravou {med2['gravou']}")
    checar(B.por_id("C01").medida.get("procedencia", {}).get("sha256") == "a" * 64,
           "e o veredito guarda de qual arquivo ele saiu")

    # ── histórico sem procedência não mede ────────────────────────────────
    anonimo = H.Historico("mega_sena", uniforme.concursos, fonte="")
    ok, motivo = anonimo.pronto_para_medir()
    checar(not ok, "histórico sem procedência declarada não é medido", motivo[:60])

    # ── P01: a partilha ───────────────────────────────────────────────────
    sem_ganhadores = MD.medir_P01(uniforme)
    checar(sem_ganhadores["veredito"] == "sem_base",
           "P01 sem ganhadores no arquivo é SEM BASE — não se mede no que não há")

    # concursos "de data" (tudo até 31) com mais ganhadores, de propósito
    conc = []
    for i in range(1, 401):
        if i % 2 == 0:
            dez, g = [1, 2, 3, 4, 5, 6], 900
        else:
            dez, g = [41, 42, 43, 44, 45, 46], 100
        conc.append({"concurso": i, "data": "", "dezenas": dez,
                     "ganhadores": {4: g}, "arrecadacao": 1_000_000.0})
    partilha = H.Historico("mega_sena", conc, fonte="inventado para P01",
                           sintetico=True)
    p01 = MD.medir_P01(partilha, repeticoes=4000)
    checar(p01["veredito"] == "confirmado",
           "com dezenas populares rateando mais, P01 é confirmado",
           f"{p01['teste']['media_a']:.0f} contra {p01['teste']['media_b']:.0f} "
           f"por milhão, p = {p01['teste']['p']:.4f}")
    checar(p01["normalizado"] is True,
           "e a medida foi normalizada pela arrecadação — senão ela confundiria "
           "dezena popular com concurso que vendeu mais")




# ═══════════════════ 9. o puxador da API, provado contra um servidor de mentira
#
# A fonte de verdade não responde daqui: a política de rede deste ambiente
# recusa a conexão antes de ela sair (e recusa as APIs do outro software dele
# do mesmo jeito). Isso impede provar a FONTE, não o CLIENTE.
#
# Então sobe um servidor local falando o formato do portal da Caixa, e o
# puxador trabalha contra ele: histórico inteiro, retomada de onde parou,
# concurso que não existe, resposta que não é JSON, e servidor fora do ar.
# O que fica por confirmar é se a API real fala este formato — e é para isso
# que existe o `--ultimo`, que mostra o que veio antes de gravar nada.
def _servidor_falso(ultimo=12, quebrado=False):
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    def concurso(n):
        base = (n * 7) % 40 + 1
        dezenas = sorted({(base + i * 6 - 1) % 60 + 1 for i in range(6)})
        while len(dezenas) < 6:
            dezenas = sorted(set(dezenas) | {(dezenas[-1] % 60) + 1})
        return {"loteria": "megasena", "numero": n,
                "dataApuracao": f"{(n % 28) + 1:02d}/01/2024",
                "listaDezenas": [f"{d:02d}" for d in dezenas],
                "valorArrecadado": 50_000_000.0 + n,
                "listaRateioPremio": [
                    {"descricaoFaixa": "6 acertos", "faixa": 1,
                     "numeroDeGanhadores": 0},
                    {"descricaoFaixa": "5 acertos", "faixa": 2,
                     "numeroDeGanhadores": 40 + n},
                    {"descricaoFaixa": "4 acertos", "faixa": 3,
                     "numeroDeGanhadores": 2000 + n}]}

    class Mao(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if quebrado:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>faca login</body></html>")
                return
            partes = [p for p in self.path.split("/") if p]
            n = None
            if partes and partes[-1].isdigit():
                n = int(partes[-1])
            if n is None:
                corpo = concurso(ultimo)
            elif n > ultimo or n < 1:
                self.send_response(404)
                self.end_headers()
                return
            else:
                corpo = concurso(n)
            dados = _json.dumps(corpo).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Mao)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def teste_api():
    print("\n[9] API — o puxador, provado contra um servidor de mentira")

    import tempfile
    temporaria = Path(tempfile.mkdtemp(prefix="loteria_api_"))
    dados_antes, fonte_antes = API.PASTA_DADOS, API.ARQUIVO_FONTE
    API.PASTA_DADOS = temporaria
    API.ARQUIVO_FONTE = temporaria / "fonte.json"
    try:
        srv, base = _servidor_falso(ultimo=12)
        fonte = {"nome": "servidor de mentira", "url": base + "/api/{slug}",
                 "url_concurso": base + "/api/{slug}/{n}",
                 "slugs": {"mega_sena": "megasena"}}

        r = API.puxar("mega_sena", pausa=0, fonte=fonte)
        checar(r.get("ok") and r.get("total") == 12,
               "puxa o histórico inteiro sem saber de antemão onde ele acaba",
               f"{r.get('total')} concursos, último {r.get('ultimo')}")

        arq = Path(r["arquivo"])
        checar(arq.exists(), "e grava no disco, cru, sem recortar campo nenhum")

        h, _ = H.de_arquivo(arq, "mega_sena", fonte="servidor de mentira")
        checar(h is not None and len(h) == 12 and h.conferido,
               "e o histórico gravado é lido e CONFERE com as regras",
               f"{len(h) if h else 0} concursos, conferido={h.conferido if h else None}")
        checar(h and h.concursos[0]["ganhadores"].get(6) == 0,
               "e a faixa de 6 acertos com ZERO ganhador sobrevive — zero é "
               "falso em Python, e some sozinho de quem usa `a or b`",
               str(h.concursos[0]["ganhadores"]) if h else "")
        checar(h and h.concursos[0]["faixas_lidas_por"] == "descrição",
               "e a faixa saiu da descrição, não do campo `faixa` — que na "
               "Caixa é a POSIÇÃO do prêmio, não o número de acertos")

        # retomada: apaga metade e puxa de novo
        cru = json.loads(arq.read_text(encoding="utf-8"))
        arq.write_text(json.dumps(cru[:5]), encoding="utf-8")
        r2 = API.puxar("mega_sena", pausa=0, fonte=fonte)
        checar(r2.get("ok") and r2["tinha"] == 5 and r2["novos"] == 7,
               "retoma de onde parou: tinha 5, buscou só os 7 que faltavam",
               f"tinha {r2['tinha']}, novos {r2['novos']}")

        r3 = API.puxar("mega_sena", pausa=0, fonte=fonte)
        checar(r3.get("ok") and r3["novos"] == 0,
               "e rodar de novo não bate na fonte à toa — não havia o que buscar")

        # concurso além do fim: a fonte devolve 404 e isso não é falha
        r4 = API.puxar("mega_sena", ate=15, pausa=0, fonte=fonte)
        checar(r4.get("ok") and len(r4.get("falhas") or []) == 3,
               "concurso que a fonte não tem vira 'não existe', não vira erro",
               f"{[n for n, _ in (r4.get('falhas') or [])]}")
        srv.shutdown()

        # resposta que não é JSON — a página de login no lugar da API
        srv2, base2 = _servidor_falso(quebrado=True)
        fonte2 = dict(fonte, url=base2 + "/api/{slug}",
                      url_concurso=base2 + "/api/{slug}/{n}")
        _d, erro = API.buscar(API.endereco("mega_sena", None, fonte2),
                              tentativas=1)
        checar("não com JSON" in erro and "faca login" in erro,
               "resposta que não é JSON é dita como é, com o começo do que veio",
               erro[:70])
        srv2.shutdown()

        # servidor fora do ar
        _d2, erro2 = API.buscar("http://127.0.0.1:9/api/megasena", tentativas=1)
        checar(bool(erro2) and "não alcancei" in erro2,
               "servidor fora do ar não vira histórico vazio, vira erro dito",
               erro2[:60])

        # e o erro que EU vejo aqui: a política deste ambiente
        _d3, erro3 = API.buscar(
            "https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena",
            tentativas=1)
        checar("DESTE ambiente" in (erro3 or ""),
               "e a recusa da rede daqui é dita como o que é — política deste "
               "ambiente, não defeito da API dele", (erro3 or "")[:60])
    finally:
        API.PASTA_DADOS, API.ARQUIVO_FONTE = dados_antes, fonte_antes
        import shutil
        shutil.rmtree(temporaria, ignore_errors=True)



def main() -> int:
    print("═" * 72)
    print("LOTERIA — regras exatas, base falsificável, garantia provada, medida")
    print("═" * 72)
    teste_regras()
    teste_aposta_valida()
    teste_conferir_com_api()
    teste_base()
    teste_fechamento()
    teste_estatistica()
    teste_historico()
    teste_medidor()
    teste_api()
    import shutil
    shutil.rmtree(RAIZ / "_teste_tmp", ignore_errors=True)

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
