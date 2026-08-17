# -*- coding: utf-8 -*-
"""
MEDIDOR — o que os dados dele dizem sobre cada item da base de conhecimento.

A REGRA QUE MANDA AQUI
──────────────────────
Cada item da base declara o que o DERRUBARIA. O medidor implementa ESSE
critério, não um critério meu. Se eu medisse C01 por um teste que eu escolhesse
depois de ver o resultado, o `derruba` do item viraria enfeite e a base inteira
voltaria a ser opinião com número. É a diferença entre o item mandar no medidor
e o medidor mandar no item.

AS TRÊS RESPOSTAS, E POR QUE A TERCEIRA É A MAIS IMPORTANTE
──────────────────────────────────────────────────────────
    confirmado   a medida excluiu o acaso, no sentido que o item afirma
    derrubado    o critério de queda que o item declarou aconteceu
    sem_base     o n não dá para dizer nem uma coisa nem outra

A terceira existe por causa de um erro meu no outro software: eu escrevia "não
se sustentou" com pouco dado. Só que com pouco dado o intervalo é largo, ele
engole o acaso quase sempre, e o software "derruba" tudo o que olha — não medir
e não achar viram a mesma tela. Aqui, antes de derrubar, o medidor pergunta se o
n daria para NOTAR o efeito (`poder_basta`). Se nem isso, a resposta é sem_base.

SÓ O PASSADO, SEMPRE
────────────────────
C01 e C02 são medidos andando para frente: em cada concurso, o atraso e a
frequência saem SÓ dos concursos anteriores, e a aposta é conferida no concurso
seguinte. Usar a amostra inteira para escolher e depois medir na mesma amostra é
o erro que faz qualquer coisa parecer que funciona — foi o que o crivo
retrospectivo do outro pacote existia para impedir, e a lição vem junto.

UMA CONSERVADORIA QUE EU DEVO DECLARAR
──────────────────────────────────────
O intervalo de Wilson trata as `m` dezenas de um concurso como `m` sorteios
independentes. Dentro de um mesmo concurso elas não são: as bolas saem sem
reposição, e isso torna a variância real MENOR que a binomial. O efeito é que o
meu intervalo é um pouco largo demais — ou seja, ele erra para o lado de NÃO
confirmar. Prefiro esse lado, e prefiro dizer que é assim a fingir precisão que
não tenho.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import base_conhecimento as BC
from . import estatistica as ES
from . import regras
from .historico import Historico

# quantos concursos passam antes de a medição começar a valer. Antes disso o
# atraso de quase toda dezena é "nunca saiu", e isso não é atraso, é falta de
# histórico.
AQUECIMENTO = 50

# janela do "quente" em C02. 20 concursos é o que se costuma chamar de quente no
# meio da loteria; está aqui como parâmetro porque é escolha, não descoberta.
JANELA_QUENTE = 20

# quantos concursos abaixo disto o qui-quadrado de C03/C04 não conclui nada.
MINIMO_PARA_FORMA = 200


def _sem_base(ident: str, motivo: str, extra: Optional[dict] = None) -> Dict[str, Any]:
    d = {"id": ident, "veredito": "sem_base", "porque": [motivo]}
    d.update(extra or {})
    return d


def _porta(hist: Historico, ident: str) -> Optional[Dict[str, Any]]:
    """O histórico presta para medir? Devolve o 'sem_base' pronto quando não."""
    ok, motivo = hist.pronto_para_medir()
    if not ok:
        return _sem_base(ident, motivo)
    return None


# ═══════════════════════════════════════════════ C01 — dezenas atrasadas
def medir_C01(hist: Historico, aquecimento: int = AQUECIMENTO,
              efeito_minimo: float = 0.10) -> Dict[str, Any]:
    """As dezenas mais atrasadas saem mais que as outras?

    O DESENHO
    ─────────
    Em cada concurso, olho só o que veio antes, separo as `sorteadas` dezenas de
    maior atraso, e conto quantas delas saíram naquele concurso. A linha de base
    não é estimada: é `sorteadas/universo`, exata.

    O que o item C01 declara como queda: "a taxa das mais atrasadas ficar dentro
    do intervalo de confiança da taxa geral". É isso que está implementado.
    """
    barrado = _porta(hist, "C01")
    if barrado:
        return barrado
    j = regras.jogo(hist.chave_jogo)
    sorteios = hist.sorteios()
    if len(sorteios) <= aquecimento + 10:
        return _sem_base("C01", f"só {len(sorteios)} concursos; com o "
                                f"aquecimento de {aquecimento} não sobra "
                                f"histórico para medir")

    m = j.sorteadas
    ultima_vez: Dict[int, int] = {}
    acertos = tentativas = 0
    for i, sorteio in enumerate(sorteios):
        if i >= aquecimento:
            # atraso = há quantos concursos não sai. Quem nunca saiu recebe o
            # maior atraso possível — é o que ele é, não é dado faltando.
            atraso = {d: i - ultima_vez.get(d, -1) for d in j.dezenas()}
            escolhidas = sorted(j.dezenas(),
                                key=lambda d: (-atraso[d], d))[:m]
            acertos += len(set(escolhidas) & set(sorteio))
            tentativas += m
        for d in sorteio:
            ultima_vez[d] = i

    return _veredito_de_taxa(
        "C01", acertos, tentativas, j.sorteadas / j.universo, efeito_minimo,
        rotulo=f"as {m} dezenas mais atrasadas",
        extra={"concursos_usados": len(sorteios) - aquecimento})


# ══════════════════════════════════════════════════ C02 — dezenas quentes
def medir_C02(hist: Historico, janela: int = JANELA_QUENTE,
              aquecimento: int = AQUECIMENTO,
              efeito_minimo: float = 0.10) -> Dict[str, Any]:
    """As dezenas que mais saíram na janela anterior continuam saindo mais?

    Mesmo desenho de C01 com o sinal trocado. Medir as duas na mesma base é o
    que resolve a contradição do meio da loteria — atrasada e quente são
    conselhos opostos ditos com a mesma convicção, e podem perfeitamente ser as
    duas falsas.
    """
    barrado = _porta(hist, "C02")
    if barrado:
        return barrado
    j = regras.jogo(hist.chave_jogo)
    sorteios = hist.sorteios()
    if len(sorteios) <= aquecimento + 10:
        return _sem_base("C02", f"só {len(sorteios)} concursos — não sobra "
                                f"histórico depois do aquecimento")

    m = j.sorteadas
    acertos = tentativas = 0
    for i in range(aquecimento, len(sorteios)):
        recentes = sorteios[max(0, i - janela):i]
        freq: Dict[int, int] = {d: 0 for d in j.dezenas()}
        for s in recentes:
            for d in s:
                freq[d] = freq.get(d, 0) + 1
        escolhidas = sorted(j.dezenas(), key=lambda d: (-freq[d], d))[:m]
        acertos += len(set(escolhidas) & set(sorteios[i]))
        tentativas += m

    return _veredito_de_taxa(
        "C02", acertos, tentativas, j.sorteadas / j.universo, efeito_minimo,
        rotulo=f"as {m} dezenas mais quentes nos últimos {janela} concursos",
        extra={"janela": janela,
               "concursos_usados": len(sorteios) - aquecimento})


def _veredito_de_taxa(ident: str, acertos: int, tentativas: int, p0: float,
                      efeito_minimo: float, rotulo: str,
                      extra: Optional[dict] = None) -> Dict[str, Any]:
    """A taxa observada contra o acaso exato — e o veredito que o item manda.

    A ORDEM DAS PERGUNTAS IMPORTA
    ─────────────────────────────
    Primeiro: o n daria para notar o efeito? Se não, sem_base, e acabou — não
    interessa onde o intervalo caiu, porque com n curto ele cai onde quiser.
    Só depois de o poder bastar é que "dentro do intervalo" significa derrubado.
    """
    if tentativas <= 0:
        return _sem_base(ident, "nenhuma observação")
    taxa = acertos / tentativas
    lo, hi = ES.wilson(acertos, tentativas)
    poder = ES.poder_basta(tentativas, p0, efeito_minimo)

    if not poder["basta"]:
        v = "sem_base"
        porque = [f"{rotulo}: {acertos} acertos em {tentativas} chances "
                  f"({taxa:.4f}), contra {p0:.4f} de acaso",
                  poder["nota"]]
    elif lo > p0:
        v = "confirmado"
        porque = [f"{rotulo} saíram {taxa:.4f} das vezes, e o intervalo de 95% "
                  f"({lo:.4f} a {hi:.4f}) fica INTEIRO acima do acaso "
                  f"({p0:.4f})",
                  f"vantagem relativa: {(taxa / p0 - 1):+.1%} — e isto é o que "
                  f"a medida diz sobre o PASSADO dele; que continue valendo é "
                  f"outra afirmação, que esta medida não sustenta"]
    elif hi < p0:
        v = "derrubado"
        porque = [f"{rotulo} saíram MENOS que o acaso: {taxa:.4f} contra "
                  f"{p0:.4f}, intervalo inteiro abaixo",
                  "o item afirma que elas saem MAIS; sair menos derruba a "
                  "afirmação tanto quanto sair igual"]
    else:
        v = "derrubado"
        porque = [f"{rotulo} saíram {taxa:.4f} das vezes; o acaso é {p0:.4f} e "
                  f"cabe dentro do intervalo de 95% ({lo:.4f} a {hi:.4f})",
                  f"e o n bastava para notar um efeito de {efeito_minimo:+.0%} "
                  f"— então isto é medida, não falta de dado"]

    d = {"id": ident, "veredito": v, "acertos": acertos,
         "tentativas": tentativas, "taxa": taxa, "acaso": p0,
         "intervalo95": [lo, hi], "poder": poder, "porque": porque}
    d.update(extra or {})
    return d


# ═════════════════════════════════════════════ C03 — soma das dezenas
def medir_C03(hist: Historico) -> Dict[str, Any]:
    """A soma dos sorteios se distribui diferente do que a combinatória manda?

    A ARMADILHA QUE ESTE MEDIDOR EVITA
    ──────────────────────────────────
    Existem muito mais combinações com soma média que com soma extrema. Então os
    sorteios reais SEMPRE vão parecer concentrados no meio — num sorteio
    perfeitamente honesto, inclusive. Comparar a soma observada com "o meio da
    faixa" acusaria padrão em qualquer loteria do mundo, e é o que sustenta meia
    indústria de palpite.

    O comparativo certo é a distribuição combinatória exata, calculada aqui sem
    amostragem. Se as duas coincidem, o sorteio é uniforme quanto à soma — e o
    item C03 declara isso como a sua queda.
    """
    barrado = _porta(hist, "C03")
    if barrado:
        return barrado
    j = regras.jogo(hist.chave_jogo)
    sorteios = hist.sorteios()
    if len(sorteios) < MINIMO_PARA_FORMA:
        return _sem_base("C03", f"{len(sorteios)} concursos — abaixo dos "
                                f"{MINIMO_PARA_FORMA} que eu exijo para "
                                f"comparar formas de distribuição")

    exata = ES.distribuicao_soma(j.universo, j.sorteadas, j.primeiro_numero)
    total = sum(exata.values())
    n = len(sorteios)
    somas = [sum(s) for s in sorteios]
    chaves = sorted(exata)
    observado = [0] * len(chaves)
    indice = {s: i for i, s in enumerate(chaves)}
    for s in somas:
        if s in indice:
            observado[indice[s]] += 1
    esperado = [exata[s] / total * n for s in chaves]

    q = ES.qui2(observado, esperado)
    if not q.get("ok"):
        return _sem_base("C03", f"não deu para comparar: {q.get('nota')}")

    media_obs = sum(somas) / n
    media_esp = sum(s * exata[s] for s in chaves) / total
    if q["p"] < 0.05:
        v, porque = "confirmado", [
            f"a distribuição das somas observadas difere da combinatória "
            f"(qui² = {q['estatistica']:.1f}, {q['graus']} graus, p = {q['p']:.4f})",
            f"média observada {media_obs:.1f} contra {media_esp:.1f} esperada"]
    else:
        v, porque = "derrubado", [
            f"as duas distribuições coincidem (qui² = {q['estatistica']:.1f}, "
            f"{q['graus']} graus, p = {q['p']:.3f}) — que é o que o item C03 "
            f"declarou como a sua queda",
            f"média observada {media_obs:.1f} contra {media_esp:.1f} esperada — "
            f"a concentração no meio existe, mas é efeito de haver mais "
            f"combinações com soma média, não de elas saírem mais"]
    porque.append("e vale o aviso que está na própria base: filtrar por soma "
                  "NÃO aumenta a chance de acertar. Reduz o número de apostas, "
                  "e só isso já pode ser motivo — mas é outra coisa.")
    return {"id": "C03", "veredito": v, "n": n, "qui2": q,
            "media_observada": media_obs, "media_esperada": media_esp,
            "porque": porque}


# ═════════════════════════════════════════ C04 — pares e ímpares
def medir_C04(hist: Historico) -> Dict[str, Any]:
    """A conta de ímpares por sorteio foge da distribuição combinatória?"""
    barrado = _porta(hist, "C04")
    if barrado:
        return barrado
    j = regras.jogo(hist.chave_jogo)
    sorteios = hist.sorteios()
    if len(sorteios) < MINIMO_PARA_FORMA:
        return _sem_base("C04", f"{len(sorteios)} concursos — abaixo dos "
                                f"{MINIMO_PARA_FORMA} exigidos para comparar "
                                f"formas de distribuição")

    exata = ES.distribuicao_impares(j.universo, j.sorteadas, j.primeiro_numero)
    total = sum(exata.values())
    n = len(sorteios)
    chaves = sorted(exata)
    indice = {c: i for i, c in enumerate(chaves)}
    observado = [0] * len(chaves)
    for s in sorteios:
        imp = sum(1 for d in s if d % 2 == 1)
        if imp in indice:
            observado[indice[imp]] += 1
    esperado = [exata[c] / total * n for c in chaves]

    q = ES.qui2(observado, esperado)
    if not q.get("ok"):
        return _sem_base("C04", f"não deu para comparar: {q.get('nota')}")
    if q["p"] < 0.05:
        v, porque = "confirmado", [
            f"a conta de ímpares difere da combinatória (qui² = "
            f"{q['estatistica']:.1f}, {q['graus']} graus, p = {q['p']:.4f})"]
    else:
        v, porque = "derrubado", [
            f"a conta de ímpares bate com a combinatória (qui² = "
            f"{q['estatistica']:.1f}, {q['graus']} graus, p = {q['p']:.3f})",
            "o 'equilíbrio' que se vê nos sorteios é contagem de combinações, "
            "não tendência do sorteio: existem mais combinações equilibradas, "
            "então elas saem mais sem serem mais prováveis"]
    return {"id": "C04", "veredito": v, "n": n, "qui2": q, "porque": porque}


# ═══════════════════════════════════════ P01 — a partilha do prêmio
def medir_P01(hist: Historico, repeticoes: int = 20_000) -> Dict[str, Any]:
    """Concursos com dezenas "populares" têm mais ganhadores?

    POR QUE ESTE É O ÚNICO ITEM QUE PODE VALER DINHEIRO SEM PREVER NADA
    ──────────────────────────────────────────────────────────────────
    A chance de acertar não muda com a escolha das dezenas. O VALOR recebido
    muda, porque o prêmio é rateado. Se dezenas que muita gente joga produzem
    mais ganhadores, então evitá-las aumenta o quinhão de quem acerta — sem
    prever coisa alguma.

    A medida usa o retrato mais conhecido de dezena popular: o volante preenchido
    com datas, ou seja, todas as dezenas de 1 a 31. Concursos assim contra os
    demais, no número de ganhadores, por permutação — que não supõe forma nenhuma
    para uma variável de cauda feia como "quantidade de ganhadores".

    O QUE ISTO NÃO CONTROLA, E EU DIGO ANTES DE ELE PERGUNTAR
    ────────────────────────────────────────────────────────
    Concurso com prêmio acumulado vende mais bilhete, e mais bilhete é mais
    ganhador — independente das dezenas. Quando o arquivo traz a arrecadação, eu
    divido por ela (ganhadores por milhão arrecadado) e o efeito de tamanho sai.
    Quando não traz, a comparação é bruta e fica DITO que é bruta, porque aí ela
    confunde popularidade com movimento do concurso.
    """
    barrado = _porta(hist, "P01")
    if barrado:
        return barrado
    if not hist.tem_ganhadores():
        return _sem_base("P01", "o arquivo não traz ganhadores por faixa — sem "
                                "isso não há o que medir. O arquivo completo de "
                                "resultados da Caixa traz; um só com as dezenas, "
                                "não.")
    j = regras.jogo(hist.chave_jogo)
    # a faixa com mais ganhadores no total é a que tem sinal: a sena tem
    # concursos inteiros com zero, e zero quase sempre não distingue nada.
    totais: Dict[int, int] = {}
    for c in hist.concursos:
        for faixa, g in (c.get("ganhadores") or {}).items():
            totais[faixa] = totais.get(faixa, 0) + (g or 0)
    if not totais:
        return _sem_base("P01", "ganhadores vieram todos vazios")
    faixa = max(totais, key=lambda f: totais[f])

    normalizado = all(c.get("arrecadacao") for c in hist.concursos
                      if c.get("ganhadores"))
    populares: List[float] = []
    demais: List[float] = []
    for c in hist.concursos:
        g = (c.get("ganhadores") or {}).get(faixa)
        if g is None:
            continue
        valor = float(g)
        if normalizado:
            arr = c.get("arrecadacao") or 0.0
            if arr <= 0:
                continue
            valor = valor / (arr / 1_000_000.0)
        dez = c.get("dezenas") or []
        (populares if dez and max(dez) <= 31 else demais).append(valor)

    if len(populares) < 2 or len(demais) < 2:
        return _sem_base("P01", f"só {len(populares)} concursos com todas as "
                                f"dezenas até 31 — não dá para comparar grupos")

    t = ES.teste_permutacao(populares, demais, repeticoes=repeticoes)
    unidade = ("ganhadores por milhão arrecadado" if normalizado
               else "ganhadores (SEM controlar pela arrecadação)")
    if t["p"] < 0.05 and t["diferenca"] > 0:
        v = "confirmado"
        porque = [f"concursos com todas as dezenas até 31 tiveram "
                  f"{t['media_a']:.1f} contra {t['media_b']:.1f} {unidade} "
                  f"na faixa de {faixa} acertos (p = {t['p']:.4f})",
                  "isto NÃO muda a chance de acertar; muda com quantos se "
                  "divide o prêmio — que é o único jeito honesto de este "
                  "software aumentar o que ele recebe"]
    elif t["p"] < 0.05:
        v = "derrubado"
        porque = [f"o efeito existe mas ao contrário: {t['media_a']:.1f} contra "
                  f"{t['media_b']:.1f} {unidade} (p = {t['p']:.4f})"]
    else:
        v = "derrubado"
        porque = [f"não houve diferença: {t['media_a']:.1f} contra "
                  f"{t['media_b']:.1f} {unidade}, p = {t['p']:.3f} em "
                  f"{repeticoes} embaralhamentos"]
    if not normalizado:
        porque.append("ATENÇÃO: o arquivo não trouxe arrecadação, então isto "
                      "não separa 'dezenas populares' de 'concurso que vendeu "
                      "mais'. Com a arrecadação no arquivo, a medida melhora.")
    return {"id": "P01", "veredito": v, "faixa_usada": faixa,
            "normalizado": normalizado, "n_populares": len(populares),
            "n_demais": len(demais), "teste": t, "porque": porque}


# ═══════════════════════════════════════════════════════ medir tudo
MEDIDORES = {"C01": medir_C01, "C02": medir_C02, "C03": medir_C03,
             "C04": medir_C04, "P01": medir_P01}


def medir_tudo(hist: Historico, gravar: bool = True) -> Dict[str, Any]:
    """Mede os itens mensuráveis e grava o veredito na base de conhecimento.

    O TRAVAMENTO CONTRA O MEU PRÓPRIO TESTE
    ───────────────────────────────────────
    Histórico sintético NUNCA grava veredito, mesmo com `gravar=True`. Os meus
    testes fabricam sorteios de propósito — um uniforme, um viciado — e sem esta
    trava um deles poderia escrever "C01 confirmado" na base dele com número que
    eu mesmo inventei. Ele leria isso como achado nos dados dele. Seria uma
    mentira de boa-fé, que é como as piores acontecem.
    """
    resultados: Dict[str, Any] = {}
    for ident, fn in MEDIDORES.items():
        try:
            resultados[ident] = fn(hist)
        except Exception as e:
            resultados[ident] = _sem_base(
                ident, f"o medidor quebrou ({type(e).__name__}: {e}) — e um "
                       f"medidor que quebra não derruba item nenhum")

    gravou: List[str] = []
    if gravar and not hist.sintetico:
        for ident, r in resultados.items():
            medida = {k: v for k, v in r.items() if k != "porque"}
            medida["procedencia"] = {"arquivo": hist.arquivo,
                                     "sha256": hist.sha256,
                                     "fonte": hist.fonte,
                                     "concursos": len(hist)}
            if BC.registrar_veredito(ident, r["veredito"], medida):
                gravou.append(ident)
    return {"resultados": resultados, "gravou": gravou,
            "sintetico": hist.sintetico,
            "nota": ("histórico SINTÉTICO — medi para conferir o medidor, e não "
                     "gravei nada na base" if hist.sintetico else
                     f"vereditos gravados na base: {', '.join(gravou) or 'nenhum'}")}


def resumo(medicao: Dict[str, Any]) -> List[str]:
    L = ["[Medidor] o que os dados disseram sobre cada item:"]
    marca = {"confirmado": "✓", "derrubado": "✗", "sem_base": "·"}
    for ident, r in medicao.get("resultados", {}).items():
        it = BC.por_id(ident)
        titulo = it.titulo if it else ident
        L.append(f"[Medidor]   {marca.get(r['veredito'], '?')} {ident} "
                 f"{titulo}: {r['veredito'].replace('_', ' ')}")
        for linha in r.get("porque", []):
            L.append(f"[Medidor]       {linha}")
    L.append(f"[Medidor] {medicao.get('nota')}")
    return L
