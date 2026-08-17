# -*- coding: utf-8 -*-
"""
SETE IAS DE MULTIPLICADOR — quais números têm chance de vir com fogo.

O QUE ELE PEDIU
---------------
    "de 5 a 10 números na roleta, mostrando quais têm chance de vir
     multiplicador fire; a immersive não tem multiplicador então deixa sem"
    "os dois crazy times são de 1 a 3 opções, mostrando quais têm maior chance
     de vir multiplicador"
    "crie e teste 7 IAs capazes de prever multiplicadores, sendo 7 pra cada jogo"

POR QUE ISTO É UM PROBLEMA DIFERENTE
------------------------------------
Prever QUAL número sai e prever QUAL número vem multiplicado são duas perguntas
separadas, e a segunda tem uma vantagem enorme: o sorteio de multiplicador é
ANUNCIADO a cada rodada, saindo ou não o número. O Lightning sorteia de 1 a 5
lucky numbers por giro; o Mega Fire acende seus fire numbers; o Crazy Time gira
o top slot com símbolo e multiplicador.

Ou seja: enquanto o número que sai dá 1 observação por giro, o multiplicador dá
de 1 a 5 — e todas ficam registradas mesmo quando não pagam. É muito mais dado
por hora do que o outro lado do problema tem.

Isso já esteve quebrado aqui: a captura só guardava o lucky quando ele calhava
de ser o número sorteado. Em 205 giros reais sobraram 10 registros de umas 600
premiações. Qualquer IA treinada naquilo enxergava 2% do fenômeno. Hoje a
rodada inteira é guardada, e é sobre ela que estas sete trabalham.

AS SETE, E POR QUE SÃO SETE DIFERENTES
--------------------------------------
Sete cópias da mesma ideia não são sete IAs. Cada uma aqui olha para um
mecanismo distinto, e duas delas se contradizem de propósito (quente x atraso):
se as duas concordassem sempre, uma seria supérflua.

    QUENTE       quem mais foi sorteado ultimamente
    ATRASO       quem está há mais tempo sem ser sorteado
    VIZINHOS     quem fica ao lado, na roda física, dos últimos sorteados
    FAMILIA      as famílias de final que ele ensinou (0136 / 0278 / 459)
    REPETE       quem repetiu como sorteado em rodadas seguidas
    SETOR        o setor da roda onde os últimos se concentraram
    INTENSIDADE  quem carregou os maiores multiplicadores, não só a presença

No Crazy Time as sete olham o top slot: símbolo quente, símbolo atrasado, quem
de fato PAGOU (top slot casando com a roda), o que o giro atual costuma puxar,
intensidade, o par top→roda e o ritmo das marcas grandes.

MEDIDA, NUNCA DECLARADA
-----------------------
Cada IA é avaliada contra o acaso do MESMO tamanho de lista: acertar 2 em 5
palpites não quer dizer nada se qualquer 5 números acertariam 2. `medir()` faz
esse backtest e devolve a razão de cada uma. Enquanto não houver rodada
suficiente, elas votam e a tela mostra "ainda sem medida" — não uma taxa
inventada com três observações.

IMMERSIVE FICA DE FORA
----------------------
A mesa não tem multiplicador. Perguntar "quais vêm com fogo" ali é pergunta sem
objeto, e o software não deve fingir que tem resposta. `tem_multiplicador()`
devolve False e a tela não mostra nada nessa mesa — foi o que ele pediu.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

# ------------------------------------------------------------------ mesas
SEM_MULTIPLICADOR = ("immersive",)
CRAZY = ("crazy_time", "crazy_time_a")

# A ordem física da roda europeia. VIZINHOS e SETOR dependem dela: dois números
# vizinhos no pano podem estar em lados opostos da roda, e é a roda que a bola
# percorre.
RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS_RODA = {n: i for i, n in enumerate(RODA)}

FAMILIAS_FINAIS = ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9))

SIMBOLOS_CT = ("1", "2", "5", "10", "CoinFlip", "Pachinko", "CashHunt",
               "CrazyBonus")

# quantos palpites cada IA entrega. Curto de propósito: uma lista de 15 números
# "acerta" quase sempre e não informa nada.
K_PALPITE = 6
K_PALPITE_CT = 3

MIN_RODADAS_PARA_MEDIR = 25


def tem_multiplicador(jogo: str) -> bool:
    """A Immersive não tem. Dizer o contrário seria inventar objeto."""
    return str(jogo) not in SEM_MULTIPLICADOR


# ------------------------------------------------- leitura das rodadas
def rodadas(historico: List[dict], jogo: str) -> List[Dict[str, Any]]:
    """Extrai, de cada giro, o sorteio de multiplicador daquele giro.

    Devolve do mais RECENTE para o mais antigo, como o histórico chega, com:
        {"saiu": resultado do giro, "premiados": [n...], "x": {n: mult}}

    Giro sem sorteio nenhum vira lista vazia — e isso é informação: é o que
    permite medir ritmo e seca.
    """
    saida = []
    for linha in (historico or []):
        if not isinstance(linha, dict):
            continue
        saiu = linha.get("n", linha.get("sec"))
        premiados: List[Any] = []
        valores: Dict[Any, int] = {}
        for t in (linha.get("tags") or []):
            if not isinstance(t, dict):
                continue
            if str(jogo) in CRAZY:
                top = t.get("top") or {}
                if isinstance(top, dict) and top.get("simbolo"):
                    s = str(top["simbolo"]).strip()
                    premiados.append(s)
                    try:
                        valores[s] = int(top.get("x") or 0)
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
                    premiados.append(n)
                    try:
                        if it.get("x"):
                            valores[n] = int(it["x"])
                    except (TypeError, ValueError):
                        pass
        saida.append({"saiu": saiu, "premiados": premiados, "x": valores})
    return saida


def _dominio(jogo: str) -> List[Any]:
    return list(SIMBOLOS_CT) if str(jogo) in CRAZY else list(range(37))


# --------------------------------------------------------- as sete IAs
# Cada uma recebe as rodadas (recente→antigo) e devolve {candidato: peso}.
# Peso alto = mais aposta nela. Devolver {} é resposta legítima: significa
# "não tenho nada a dizer com este histórico", e é melhor que chutar.

def _ia_quente(rds, jogo, janela=60):
    c = Counter()
    for r in rds[:janela]:
        for n in r["premiados"]:
            c[n] += 1
    return {n: float(v) for n, v in c.items()}


def _ultima_vez(rds, janela):
    """Há quantas rodadas cada candidato foi sorteado pela última vez."""
    visto = {}
    for i, r in enumerate(rds[:janela]):
        for n in r["premiados"]:
            visto.setdefault(n, i)
    return visto


def _ia_atraso(rds, jogo, janela=120):
    """Quem está há mais tempo sem ser sorteado.

    Só entra quem JÁ foi sorteado ao menos uma vez na janela. Quem nunca
    apareceu não é "atrasado" — é desconhecido, e tratá-lo como o mais atrasado
    de todos enchia a lista de dezenas de empates que só eram desempatados pela
    ordem alfabética. Empate desfeito por alfabeto é precisão de mentira.
    """
    visto = _ultima_vez(rds, janela)
    return {n: float(i + 1) for n, i in visto.items()}


def _ia_vizinhos(rds, jogo, ultimas=6, raio=2):
    if str(jogo) in CRAZY:
        return {}
    peso = defaultdict(float)
    for r in rds[:ultimas]:
        for n in r["premiados"]:
            i = POS_RODA.get(n)
            if i is None:
                continue
            for d in range(-raio, raio + 1):
                if d == 0:
                    continue
                viz = RODA[(i + d) % len(RODA)]
                peso[viz] += 1.0 / abs(d)
    return dict(peso)


def _ia_familia(rds, jogo, ultimas=6):
    if str(jogo) in CRAZY:
        return {}
    finais = set()
    for r in rds[:ultimas]:
        for n in r["premiados"]:
            for fam in FAMILIAS_FINAIS:
                if n % 10 in fam:
                    finais.update(fam)
    if not finais:
        return {}
    # Dentro da família, a ordem é a que ele ensinou: os que MENOS saíram vêm
    # primeiro. Sem isso os quinze números da família empatavam em 1.0 e o
    # desempate virava ordem alfabética — quinze empates e seis vagas.
    visto = _ultima_vez(rds, 120)
    return {n: 1.0 + (visto.get(n, 120) / 240.0)
            for n in range(37) if n % 10 in finais}


def _ia_repete(rds, jogo, janela=40):
    """Quem foi sorteado em rodadas CONSECUTIVAS."""
    peso = defaultdict(float)
    for i in range(min(len(rds), janela) - 1):
        atual = set(rds[i]["premiados"])
        seguinte = set(rds[i + 1]["premiados"])
        for n in atual & seguinte:
            peso[n] += 1.0
    return dict(peso)


def _ia_setor(rds, jogo, ultimas=10, largura=5):
    if str(jogo) in CRAZY:
        return {}
    c = Counter()
    for r in rds[:ultimas]:
        for n in r["premiados"]:
            i = POS_RODA.get(n)
            if i is not None:
                c[i // largura] += 1
    if not c:
        return {}
    # o setor dá a força; dentro dele, quem está há mais tempo sem sair vem na
    # frente — de novo para o empate não cair no alfabeto
    visto = _ultima_vez(rds, 120)
    peso = {}
    for setor, v in c.items():
        for j in range(setor * largura, min((setor + 1) * largura, len(RODA))):
            n = RODA[j]
            peso[n] = float(v) + visto.get(n, 120) / 240.0
    return peso


def _ia_intensidade(rds, jogo, janela=80):
    """Quem carrega os maiores multiplicadores, não só a presença.

    Presença e tamanho são coisas diferentes: um número que aparece toda hora
    a 50x vale menos que um que aparece pouco a 500x.
    """
    peso = defaultdict(float)
    for r in rds[:janela]:
        for n, x in (r["x"] or {}).items():
            peso[n] += float(x or 0)
    return dict(peso)


# --- as três específicas do Crazy Time (substituem vizinhos/família/setor) ---
def _ct_pagou(rds, jogo, janela=80):
    """Símbolos em que o top slot CASOU com a roda — o que de fato pagou."""
    c = Counter()
    for r in rds[:janela]:
        saiu = str(r.get("saiu") or "").strip()
        for s in r["premiados"]:
            if str(s).strip() == saiu:
                c[s] += 1
    return {k: float(v) for k, v in c.items()}


def _ct_puxa(rds, jogo, janela=80):
    """O que o resultado ATUAL costuma puxar para o top slot do giro seguinte."""
    if not rds:
        return {}
    atual = str(rds[0].get("saiu") or "").strip()
    c = Counter()
    for i in range(1, min(len(rds), janela)):
        if str(rds[i].get("saiu") or "").strip() == atual:
            for s in rds[i - 1]["premiados"]:
                c[s] += 1
    return {k: float(v) for k, v in c.items()}


def _ct_ritmo(rds, jogo, janela=60):
    """Ritmo das marcas grandes: depois de quantos giros elas costumam voltar.

    Não aponta símbolo — aponta MOMENTO. Quando a seca passa do intervalo
    típico, ela levanta todos os símbolos por igual, e quem escolhe entre eles
    são as outras seis.
    """
    grandes = [i for i, r in enumerate(rds[:janela])
               if any((r["x"] or {}).get(s, 0) >= 10 for s in r["premiados"])]
    if len(grandes) < 3:
        return {}
    saltos = [b - a for a, b in zip(grandes, grandes[1:])]
    tipico = sum(saltos) / len(saltos)
    desde = grandes[0]
    if desde <= tipico:
        return {}
    return {s: (desde / max(tipico, 1.0)) for s in SIMBOLOS_CT}


IAS_ROLETA = (
    ("QUENTE", _ia_quente, "quem mais foi sorteado ultimamente"),
    ("ATRASO", _ia_atraso, "quem está há mais tempo sem ser sorteado"),
    ("VIZINHOS", _ia_vizinhos, "quem fica ao lado dos últimos, na roda física"),
    ("FAMILIA", _ia_familia, "as famílias de final que ele ensinou"),
    ("REPETE", _ia_repete, "quem repetiu em rodadas seguidas"),
    ("SETOR", _ia_setor, "o setor da roda onde os últimos se concentraram"),
    ("INTENSIDADE", _ia_intensidade, "quem carrega os maiores multiplicadores"),
)

IAS_CRAZY = (
    ("QUENTE", _ia_quente, "símbolo que mais veio no top slot"),
    ("ATRASO", _ia_atraso, "símbolo há mais tempo fora do top slot"),
    ("PAGOU", _ct_pagou, "símbolos em que o top slot casou com a roda"),
    ("PUXA", _ct_puxa, "o que o giro atual costuma puxar para o top slot"),
    ("REPETE", _ia_repete, "símbolo que repetiu em rodadas seguidas"),
    ("INTENSIDADE", _ia_intensidade, "quem carrega os maiores multiplicadores"),
    ("RITMO", _ct_ritmo, "a seca passou do intervalo típico das marcas grandes"),
)


# DUAS PERGUNTAS, NÃO UMA — e a resposta muda de mesa para mesa.
#
# O estudo de 416 fichas dele mede cada mesa por duas lentes separadas, e o
# resultado vem invertido entre elas:
#
#     mesa            SE vem destaque       o TAMANHO
#     Lighting             +8,2%              -59,2%
#     Mega Fire            -3,4%              -16,5%
#     Crazy Time          -15,4%               +8,7%
#     Crazy Time A         -9,9%              +30,1%
#
# "Detectar ocorrência e estimar intensidade são tarefas independentes" — é a
# frase do estudo, e os números provam: no Lighting a magnitude perde 59%
# enquanto a ocorrência ganha 8%.
#
# As sete IAs misturavam as duas. INTENSIDADE (que soma multiplicadores, ou
# seja, mede TAMANHO) votava lado a lado com QUENTE (que conta aparições, ou
# seja, mede OCORRÊNCIA). Somar um sinal com um anti-sinal é o jeito mais
# discreto de zerar os dois.
#
# Agora cada IA declara que pergunta responde, e o voto pesa mais na lente que
# aquela mesa mostrou ter ganho. Nada é excluído: a lente fraca continua
# votando, mais baixo.
LENTE = {
    "QUENTE": "ocorrencia", "ATRASO": "ocorrencia", "VIZINHOS": "ocorrencia",
    "FAMILIA": "ocorrencia", "REPETE": "ocorrencia", "SETOR": "ocorrencia",
    "INTENSIDADE": "magnitude",
    "PAGOU": "ocorrencia", "PUXA": "ocorrencia", "RITMO": "magnitude",
}
PESO_LENTE_BOA = 1.0
PESO_LENTE_FRACA = 0.6


def peso_da_lente(jogo: str, nome_ia: str) -> float:
    """Quanto o voto desta IA vale nesta mesa, pela lente que ela responde."""
    try:
        from academia_autonoma.biblioteca_teorias import lente_util
        melhor = (lente_util(jogo) or {}).get("melhor")
    except Exception:
        melhor = None
    if not melhor:
        return PESO_LENTE_BOA          # sem estudo para esta mesa: todas iguais
    return PESO_LENTE_BOA if LENTE.get(nome_ia) == melhor else PESO_LENTE_FRACA


def ias(jogo: str):
    return IAS_CRAZY if str(jogo) in CRAZY else IAS_ROLETA


def _topo(peso: Dict[Any, float], k: int) -> List[Any]:
    if not peso:
        return []
    return [n for n, _ in sorted(peso.items(), key=lambda x: (-x[1], str(x[0])))
            if _ > 0][:k]


# ------------------------------------------- os quinze agentes estatísticos
# OS `alvos` DELES SÓ VIRAVAM TEXTO.
#
# `agentes_multiplicador.py` roda quinze agentes que procuram vício no sorteio
# de multiplicador, e vários deles terminam apontando NÚMERO: M05 acha o número
# que aparece premiado acima do esperado, M10 acha o setor da roda que
# concentra prêmio, M06 acha o que repete. Cada achado sai com `alvos` e com
# selo estatístico (confirmado / em observação / indício, já com correção para
# múltiplos testes).
#
# E o único consumidor disso era `ciclo_academia.py`, que chamava
# `resumo_multiplicadores()` e jogava as linhas no log. Quinze agentes com
# medida de significância produzindo relatório para ninguém ler, enquanto a
# escolha do número era feita sem eles.
#
# Como agora quem escolhe é o Caçador, e estes são caçadores, eles votam. Com
# peso vindo do selo -- não do meu gosto: confirmado (sobrevive à correção de
# múltiplos testes) fala mais alto que indício, e indício fala baixinho em vez
# de ser calado.
PESO_DO_SELO = {"confirmado": 1.0, "em_observacao": 0.55, "indicio": 0.2}
MIN_GIROS_AGENTES = 60


def votos_dos_agentes(historico: List[dict]) -> Dict[str, Dict[str, Any]]:
    """O que cada agente estatístico aponta, com o peso do selo dele.

    Devolve `{nome_do_agente: {"alvos": [...], "peso": float, "achado": str}}`.
    Agente sem `alvos` não entra -- ele mediu ritmo ou intervalo, não número,
    e forçá-lo a apontar seria inventar palpite que ele não deu.
    """
    try:
        from .agentes_multiplicador import cacar_multiplicadores
    except Exception:
        return {}
    try:
        r = cacar_multiplicadores(historico or [])
    except Exception:
        return {}
    if r.get("erro"):
        return {}
    saida: Dict[str, Dict[str, Any]] = {}
    for a in r.get("achados") or []:
        alvos = [x for x in (a.get("alvos") or []) if x is not None]
        if not alvos:
            continue
        peso = PESO_DO_SELO.get(str(a.get("selo")), 0.2)
        # razão acima de 1 empurra, abaixo segura -- mas dentro de limites,
        # para um agente com n pequeno e razão 4x não decidir sozinho
        raz = a.get("razao")
        if raz:
            peso *= min(1.6, max(0.5, float(raz)))
        nome = str(a.get("agente") or "M??")
        anterior = saida.get(nome)
        if anterior and anterior["peso"] >= peso:
            continue
        saida[nome] = {"alvos": [str(x) for x in alvos],
                       "peso": round(peso, 3),
                       "achado": str(a.get("achado") or ""),
                       "selo": a.get("selo"), "p": a.get("p")}
    return saida


# ------------------------------------------------------------- previsão
def prever(jogo: str, historico: List[dict],
           k: int = None) -> Dict[str, Any]:
    """O que as sete dizem, e no que elas concordam.

    Devolve também o palpite de CADA uma: sem isso não dá para medir quem está
    puxando o acerto, e o crédito acaba indo para quem fala mais alto.
    """
    if not tem_multiplicador(jogo):
        return {"jogo": jogo, "tem": False, "consenso": [], "por_ia": {},
                "nota": "esta mesa não tem multiplicador"}
    ct = str(jogo) in CRAZY
    k = k or (K_PALPITE_CT if ct else K_PALPITE)
    rds = rodadas(historico, jogo)
    if not rds:
        return {"jogo": jogo, "tem": True, "consenso": [], "por_ia": {},
                "n_rodadas": 0, "nota": "sem rodada de multiplicador no histórico"}
    por_ia, votos = {}, defaultdict(float)
    for nome, fn, _desc in ias(jogo):
        try:
            peso = fn(rds, jogo) or {}
        except Exception:
            peso = {}
        palpite = _topo(peso, k)
        por_ia[nome] = palpite
        # voto com decaimento por posição: o 1º da lista de cada IA pesa mais
        # nesta mesa, ocorrencia e magnitude nao valem igual (ver LENTE)
        wl = peso_da_lente(jogo, nome)
        for i, n in enumerate(palpite):
            votos[str(n)] += wl / (1 + i * 0.3)
    # os quinze agentes estatísticos votam junto -- eles também são caçadores,
    # e até aqui o que eles achavam só virava linha de log
    por_agente = votos_dos_agentes(historico)
    for nome, dado in por_agente.items():
        for i, n in enumerate(dado["alvos"][:k]):
            votos[str(n)] += dado["peso"] / (1 + i * 0.3)

    consenso = [n for n, _ in sorted(votos.items(),
                                     key=lambda x: (-x[1], str(x[0])))][:k]
    quantas = {n: sum(1 for p in por_ia.values() if str(n) in [str(x) for x in p])
               for n in consenso}
    quantos_agentes = {n: sum(1 for d in por_agente.values()
                              if str(n) in d["alvos"])
                       for n in consenso}
    return {
        "jogo": jogo, "tem": True, "consenso": consenso, "por_ia": por_ia,
        "por_agente": por_agente, "quantos_agentes": quantos_agentes,
        "quantas_ias": quantas, "n_rodadas": len(rds),
        "com_sorteio": sum(1 for r in rds if r["premiados"]),
    }


def pontuar(jogo: str, escolhidos: List[Any],
            historico: List[dict]) -> List[tuple]:
    """Ordena os números JÁ ESCOLHIDOS pelo apoio das sete.

    Devolve [(numero, quantas IAs, peso)] do mais apoiado para o menos.

    Aqui a pergunta é outra e o alvo é outro: não é "quais números do mundo
    todo vêm com fogo", é "destes que já vão ser apostados, quais têm mais
    chance". Cruzar a lista das sete com a aposta e mostrar só a interseção
    dava vazio quase sempre — sete escolhem 6 entre 37, a aposta tem 8, e as
    duas raramente se encontram. A tela ficava muda tendo o que dizer.
    """
    if not tem_multiplicador(jogo) or not escolhidos:
        return []
    rds = rodadas(historico, jogo)
    if not rds:
        return []
    alvo = [str(x).strip() for x in escolhidos]
    votos = defaultdict(float)
    quantas = defaultdict(int)
    for nome, fn, _d in ias(jogo):
        try:
            peso = fn(rds, jogo) or {}
        except Exception:
            continue
        if not peso:
            continue
        # normaliza dentro da IA: senão INTENSIDADE (que soma multiplicadores)
        # esmagaria QUENTE (que conta ocorrências) só pela escala do número
        maior = max(peso.values()) or 1.0
        wl = peso_da_lente(jogo, nome)
        for n in alvo:
            v = 0.0
            for chave, w in peso.items():
                if str(chave).strip() == n:
                    v = float(w)
                    break
            if v > 0:
                votos[n] += (v / maior) * wl
                quantas[n] += 1
    if not votos:
        return []
    ordem = sorted(votos.items(), key=lambda x: -x[1])
    return [(n, quantas[n], round(v, 3)) for n, v in ordem]


def marcar(jogo: str, escolhidos: List[Any], historico: List[dict],
           quantos: int = None) -> List[Any]:
    """Dos números já escolhidos, os mais apontados para multiplicador.

    Não muda a aposta — marca. A escolha continua sendo do consenso das
    teorias; isto responde a outra pergunta em cima da mesma lista.

    Duas travas para a marca continuar querendo dizer alguma coisa:

        no máximo METADE da aposta (teto de 3). Marcar 7 de 8 não separa
        nada — seria pintar a lista inteira de laranja e chamar isso de
        informação. No Crazy Time, com 3 opções, isso dá 2.

        ao menos DUAS das sete atrás de cada marcado. Uma IA sozinha
        apontando não é consenso, é palpite.
    """
    if quantos is None:
        n = len(escolhidos or [])
        quantos = min(3, max(1, (n + 1) // 2))
    p = pontuar(jogo, escolhidos, historico)
    return [x for x, q, _v in p if q >= 2][:quantos]


# -------------------------------------------------------------- medição
def medir(jogo: str, historico: List[dict], k: int = None,
          minimo: int = MIN_RODADAS_PARA_MEDIR) -> Dict[str, Any]:
    """Backtest honesto: cada IA prevê a rodada seguinte usando só o passado.

    O acaso é o da MESMA lista: k sorteios num domínio de N, com quantos
    premiados aquela rodada teve. Comparar 6 palpites contra 1/37 infla tudo.
    """
    if not tem_multiplicador(jogo):
        return {"jogo": jogo, "tem": False}
    ct = str(jogo) in CRAZY
    k = k or (K_PALPITE_CT if ct else K_PALPITE)
    rds = rodadas(historico, jogo)
    n_dom = len(_dominio(jogo))
    # ordem cronológica para o backtest: o passado vem antes
    cron = list(reversed(rds))
    if len(cron) < minimo + 5:
        return {"jogo": jogo, "tem": True, "n": len(cron),
                "suficiente": False,
                "nota": f"só {len(cron)} rodadas — precisa de {minimo + 5}"}
    placar = {nome: {"acertos": 0, "tentativas": 0, "acaso": 0.0}
              for nome, _f, _d in ias(jogo)}
    for i in range(minimo, len(cron) - 1):
        passado = list(reversed(cron[:i]))       # recente→antigo, como chega
        alvo = set(str(x) for x in cron[i]["premiados"])
        if not alvo:
            continue
        for nome, fn, _d in ias(jogo):
            try:
                peso = fn(passado, jogo) or {}
            except Exception:
                peso = {}
            palpite = _topo(peso, k)
            if not palpite:
                continue
            p = placar[nome]
            p["tentativas"] += 1
            if any(str(x) in alvo for x in palpite):
                p["acertos"] += 1
            # acaso de acertar ao menos um: 1 - C(N-m, k)/C(N, k), aproximado
            m = len(alvo)
            q = 1.0
            for j in range(len(palpite)):
                q *= max(0.0, (n_dom - m - j)) / max(1, (n_dom - j))
            p["acaso"] += (1.0 - q)
    saida = {}
    for nome, p in placar.items():
        t = p["tentativas"]
        if not t:
            saida[nome] = {"n": 0}
            continue
        taxa = p["acertos"] / t
        acaso = p["acaso"] / t
        saida[nome] = {
            "n": t, "acertos": p["acertos"], "taxa": round(taxa, 4),
            "acaso": round(acaso, 4),
            "razao": round(taxa / acaso, 3) if acaso > 0 else None,
        }
    return {"jogo": jogo, "tem": True, "suficiente": True,
            "n": len(cron), "k": k, "por_ia": saida}


def resumo(jogo: str, historico: List[dict]) -> str:
    if not tem_multiplicador(jogo):
        return f"[Multiplicador] {jogo}: esta mesa não tem multiplicador"
    p = prever(jogo, historico)
    if not p.get("consenso"):
        return (f"[Multiplicador] {jogo}: {p.get('nota') or 'sem palpite'} "
                f"({p.get('n_rodadas', 0)} rodadas lidas)")
    L = [f"[Multiplicador] {jogo}: as 7 IAs apontam "
         + " ".join(str(x) for x in p["consenso"])
         + f"   ({p.get('com_sorteio', 0)} rodadas com sorteio "
           f"em {p.get('n_rodadas', 0)})"]
    for n in p["consenso"]:
        L.append(f"   {str(n):<12} {p['quantas_ias'].get(n, 0)} das 7 IAs")
    m = medir(jogo, historico)
    if not m.get("suficiente"):
        L.append(f"   medida: {m.get('nota')} — os palpites saem sem taxa até lá")
    else:
        boas = sorted(((k, v) for k, v in m["por_ia"].items()
                       if v.get("razao")), key=lambda x: -(x[1]["razao"] or 0))
        L.append("   medida contra o acaso da mesma lista: "
                 + ", ".join(f"{k} {v['razao']:.2f}x(n={v['n']})"
                             for k, v in boas[:4]))
    return "\n".join(L)
