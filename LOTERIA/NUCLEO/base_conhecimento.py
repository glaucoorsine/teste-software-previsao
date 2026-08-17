# -*- coding: utf-8 -*-
"""
BASE DE CONHECIMENTO — o que as inteligências consultam para formular os jogos.

O QUE ELE PEDIU
───────────────
    "tem que ter uma base de conhecimento pra ir pras, a inteligência artificial
     ou as inteligências artificiais irem consultando pra formular os jogos"

Ele está certo e o pedido é preciso: sem base, cada IA inventa o próprio critério
e a discordância entre elas não significa nada. Com base, todas partem do mesmo
material e a discordância vira informação.

A LIÇÃO QUE EU TRAGO DO OUTRO SOFTWARE, E QUE MUDA O FORMATO DESTA BASE
──────────────────────────────────────────────────────────────────────
No PACOTE_COMPLETO eu indexei 1616 fichas dos PDFs dele e construí um portão
(`procedencia.py`): uma inteligência que não aponta a ficha que a autoriza fica
CALADA. Foi a melhor decisão daquele projeto, e o teste destrutivo provou:
tirando os PDFs, 12 inteligências emudeceram; devolvendo, as 12 voltaram.

Então esta base já nasce assim. Cada item aqui tem quatro partes obrigatórias:

    afirma      o que se sustenta, em uma frase
    como_medir  o procedimento exato que confirmaria ou derrubaria
    derruba     o resultado que a mataria -- se não existe, não é conhecimento
    origem      de onde veio: matemática provada, teoria dele, ou hipótese minha

Um item sem `derruba` não entra. Não por rigor decorativo: uma afirmação que
nenhum resultado pode derrubar não ajuda a escolher dezena nenhuma, e ocupa o
lugar de uma que ajudaria.

E `origem` NÃO é hierarquia de valor
────────────────────────────────────
`MATEMATICA` é o que se demonstra e não precisa de dado. `DELE` é observação
dele -- ele tem anos de loteria e eu tenho zero, então observação dele entra como
hipótese séria, para ser medida, nunca descartada por vir dele. `MINHA` é
hipótese minha, e essa eu trato com mais desconfiança que as outras duas, porque
é a única que não tem nem demonstração nem observação de campo por trás.

O QUE ESTA BASE JÁ SABE, ANTES DAS TEORIAS DELE
───────────────────────────────────────────────
Está tudo aqui embaixo, mas o resumo é: quatro fatos matemáticos que qualquer
estratégia tem de respeitar, e cinco crenças comuns de loteria que este software
vai MEDIR nos dados dele em vez de repetir ou desprezar.

As teorias dele entram por `acrescentar()`, com a mesma exigência de todas as
outras -- inclusive a de dizer o que as derrubaria. Essa pergunta não é
desconfiança: é o que permite que, quando a medida CONFIRMAR, a confirmação valha
alguma coisa.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

# de onde vem cada item
MATEMATICA = "MATEMATICA"      # demonstrável; não depende de dado
DELE = "DELE"                  # observação dele, para ser medida
MINHA = "MINHA"                # hipótese minha, a mais suspeita das três
CRENCA = "CRENCA_COMUM"        # o que se repete no meio da loteria — a medir

ORIGENS = (MATEMATICA, DELE, MINHA, CRENCA)


class Item:
    """Uma peça de conhecimento que uma IA pode citar para justificar um jogo."""

    def __init__(self, ident: str, titulo: str, afirma: str, como_medir: str,
                 derruba: str, origem: str, aplica_a: Sequence[str] = (),
                 nota: str = ""):
        if origem not in ORIGENS:
            raise ValueError(f"origem desconhecida: {origem}")
        if not derruba.strip():
            # o portão: sem isto, não é conhecimento, é opinião com número
            raise ValueError(f"{ident}: falta dizer o que derrubaria esta "
                             f"afirmação — sem isso ela não entra na base")
        self.id = ident
        self.titulo = titulo
        self.afirma = afirma
        self.como_medir = como_medir
        self.derruba = derruba
        self.origem = origem
        self.aplica_a = tuple(aplica_a) or ("todos",)
        self.nota = nota
        # preenchido quando o software medir nos dados dele
        self.veredito: Optional[str] = None      # "confirmado"/"derrubado"/None
        self.medida: Dict[str, Any] = {}

    def serve_para(self, chave_jogo: str) -> bool:
        return "todos" in self.aplica_a or chave_jogo in self.aplica_a

    def como_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "titulo": self.titulo, "afirma": self.afirma,
                "como_medir": self.como_medir, "derruba": self.derruba,
                "origem": self.origem, "aplica_a": list(self.aplica_a),
                "veredito": self.veredito, "medida": self.medida,
                "nota": self.nota}


# ═════════════════════════════ o que é demonstrável, e não se discute
_MATEMATICA = [
    Item("M01", "toda combinação tem a mesma chance",
         afirma="Num sorteio honesto, 1-2-3-4-5-6 tem exatamente a mesma chance "
                "que qualquer outra combinação de seis dezenas.",
         como_medir="Não se mede: decorre de o sorteio ser uniforme. O que SE "
                    "MEDE é se o sorteio é uniforme — teste de qui-quadrado "
                    "sobre a frequência de cada dezena no histórico dele.",
         derruba="Uma dezena aparecer com frequência fora do intervalo de "
                 "confiança em milhares de concursos. Aí o sorteio não é "
                 "uniforme e esta afirmação cai para aquela loteria.",
         origem=MATEMATICA,
         nota="Isto NÃO diz que escolher dezenas dá no mesmo. Diz que dá no "
              "mesmo para a CHANCE. Para o VALOR do prêmio não dá, e é aí que "
              "há o que fazer — ver P01."),

    Item("M02", "o acaso da aposta cresce com o tamanho dela",
         afirma="Aumentar as dezenas apostadas aumenta a chance na proporção "
                "exata de C(k, acertos), e o custo cresce mais rápido que a "
                "chance.",
         como_medir="Comparar `p_faixa(k, f)` com o preço de cada k. A razão "
                    "chance/custo é calculável para todo k.",
         derruba="Encontrar um k em que a chance por real gasto seja maior que "
                 "no k mínimo. (Isso é aritmética; se acontecer, é erro meu no "
                 "cálculo — e o teste tem de pegar.)",
         origem=MATEMATICA,
         nota="É a régua central deste software: comparar duas estratégias com "
              "número de apostas diferente sem igualar o gasto é a mesma fraude "
              "que comparar apostas de tamanhos diferentes na roleta."),

    Item("M03", "fechamento dá garantia, não previsão",
         afirma="É possível montar um conjunto de apostas tal que, SE x das "
                "minhas d dezenas forem sorteadas, pelo menos uma aposta terá "
                "y acertos — garantido, sem depender de sorte.",
         como_medir="Verificação exaustiva: para todo subconjunto de x dezenas "
                    "entre as d escolhidas, conferir se alguma aposta do "
                    "fechamento cobre y delas. Ou vale para TODOS os casos, ou "
                    "a garantia não existe.",
         derruba="Um único subconjunto de x dezenas que nenhuma aposta cubra "
                 "com y acertos. Um contraexemplo derruba a garantia inteira.",
         origem=MATEMATICA,
         nota="A capacidade mais real deste software. Não aumenta a chance de "
              "acertar a sena — reorganiza as apostas para converter acertos "
              "parciais em prêmios com certeza."),

    Item("M04", "acertos médios são o piso de comparação",
         afirma="Uma aposta de k dezenas acerta, em média, k×sorteadas/universo "
                "— e nenhuma escolha de dezenas muda essa média num sorteio "
                "uniforme.",
         como_medir="`acertos_esperados(k)` em regras.py, contra a média "
                    "observada da estratégia no histórico dele.",
         derruba="Uma estratégia cuja média de acertos supere esse número, "
                 "medida FORA da amostra em que foi escolhida, com n grande.",
         origem=MATEMATICA,
         nota="Toda teoria será comparada com este número. 'Acertei 9 na "
              "Lotofácil' não é achado: 9 é a média de quem aposta 15."),
]

# ═══════════════════ o que se repete no meio da loteria — para MEDIR
_CRENCAS = [
    Item("C01", "dezenas atrasadas",
         afirma="Dezenas que não saem há muitos concursos ficam mais prováveis.",
         como_medir="Para cada concurso do histórico, calcular o atraso de cada "
                    "dezena ANTES do sorteio e comparar a taxa de saída das "
                    "mais atrasadas com a das demais. O passado é o que veio "
                    "antes, nunca a amostra inteira.",
         derruba="A taxa de saída das dezenas mais atrasadas ficar dentro do "
                 "intervalo de confiança da taxa geral (sorteadas/universo).",
         origem=CRENCA, aplica_a=("todos",),
         nota="É o critério de atrasado que ele já usa no outro software. Lá "
              "ele foi medido e não se sustentou nos 1885 giros; aqui será "
              "medido de novo, porque loteria é outro sorteio e o resultado de "
              "lá não vale aqui."),

    Item("C02", "dezenas quentes",
         afirma="Dezenas que saíram muito nos últimos concursos continuam "
                "saindo mais.",
         como_medir="Mesmo desenho de C01, com o sinal invertido: separar as "
                    "mais frequentes na janela anterior e medir a taxa delas no "
                    "concurso seguinte.",
         derruba="Taxa dentro do intervalo de confiança do acaso.",
         origem=CRENCA,
         nota="C01 e C02 se contradizem, e as duas são repetidas com a mesma "
              "convicção. Medir as duas na mesma base é o que resolve — e é "
              "possível que nenhuma se sustente."),

    Item("C03", "soma e faixa das dezenas",
         afirma="As combinações sorteadas concentram-se numa faixa de soma, "
                "então apostas com soma muito alta ou muito baixa saem menos.",
         como_medir="Distribuição da soma dos sorteios reais contra a "
                    "distribuição da soma de TODAS as combinações possíveis "
                    "(ou de uma amostra grande e uniforme delas).",
         derruba="As duas distribuições coincidirem — o que é o esperado num "
                 "sorteio uniforme, e tornaria a 'concentração' um efeito de "
                 "haver mais combinações com soma média, não de elas saírem "
                 "mais.",
         origem=CRENCA,
         nota="A armadilha aqui é sutil e vale explicá-la: existem MUITO mais "
              "combinações com soma média. Elas saem mais em número absoluto "
              "sem que nenhuma delas seja mais provável. Filtrar por soma não "
              "aumenta a chance — mas reduz o número de apostas, e pode ser "
              "defensável por isso. São coisas diferentes e o software não pode "
              "confundi-las."),

    Item("C04", "pares e ímpares equilibrados",
         afirma="Sorteios tendem a sair com pares e ímpares equilibrados, então "
                "apostas muito desequilibradas valem menos.",
         como_medir="Mesmo desenho de C03: distribuição observada contra a "
                    "distribuição combinatória esperada.",
         derruba="Coincidirem — sinal de que o 'equilíbrio' é só contagem de "
                 "combinações, não tendência do sorteio.",
         origem=CRENCA),

    Item("P01", "as dezenas que muita gente joga dividem mais o prêmio",
         afirma="Escolher dezenas pouco jogadas não muda a chance de acertar, "
                "mas aumenta o valor recebido SE acertar, porque o prêmio é "
                "rateado entre os ganhadores.",
         como_medir="Comparar o número de ganhadores por concurso com as "
                    "características das dezenas sorteadas (datas ≤31, "
                    "sequências, padrões visuais do volante). Se concursos "
                    "'populares' têm mais ganhadores para o mesmo prêmio, o "
                    "efeito existe e é mensurável.",
         derruba="O número de ganhadores não variar com o perfil das dezenas "
                 "sorteadas, controlando pela arrecadação do concurso.",
         origem=MATEMATICA,
         nota="Este é o único item da base que pode aumentar o RETORNO sem "
              "precisar prever nada. A chance de acertar continua idêntica; o "
              "que muda é com quantos se divide. É medível no histórico dele "
              "porque a Caixa publica o número de ganhadores por faixa."),
]

_BASE: List[Item] = list(_MATEMATICA) + list(_CRENCAS)


# ═══════════════════════════════════════════════════════════ a base viva
def tudo(chave_jogo: Optional[str] = None) -> List[Item]:
    if not chave_jogo:
        return list(_BASE)
    return [i for i in _BASE if i.serve_para(chave_jogo)]


def por_id(ident: str) -> Optional[Item]:
    return next((i for i in _BASE if i.id == str(ident).upper()), None)


def por_origem(origem: str) -> List[Item]:
    return [i for i in _BASE if i.origem == origem]


def acrescentar(ident: str, titulo: str, afirma: str, como_medir: str,
                derruba: str, origem: str = DELE,
                aplica_a: Sequence[str] = (), nota: str = "") -> Item:
    """Entra uma teoria nova -- as dele, quando ele as mandar.

    A exigência é a mesma de todas: dizer o que a derrubaria. Não é
    desconfiança da teoria dele; é o que faz a CONFIRMAÇÃO valer alguma coisa
    quando vier. Uma afirmação que nada pode derrubar também não pode ser
    confirmada -- ela só pode ser repetida.
    """
    if por_id(ident):
        raise ValueError(f"já existe item {ident} na base")
    it = Item(ident, titulo, afirma, como_medir, derruba, origem, aplica_a, nota)
    _BASE.append(it)
    return it


def registrar_veredito(ident: str, veredito: str, medida: Dict[str, Any]) -> bool:
    """Grava o que a medição nos dados dele disse sobre um item.

    `veredito` é "confirmado", "derrubado" ou "sem_base". O terceiro é o mais
    comum no começo e não é fracasso: é a resposta honesta enquanto o `n` não
    chega.
    """
    it = por_id(ident)
    if not it or veredito not in ("confirmado", "derrubado", "sem_base"):
        return False
    it.veredito = veredito
    it.medida = dict(medida or {})
    return True


def autorizada(ident: str) -> bool:
    """Uma IA pode citar este item para justificar um jogo?

    O PORTÃO, IGUAL AO DO OUTRO SOFTWARE
    ────────────────────────────────────
    Item derrubado pela medida não autoriza mais nada. Item ainda sem base
    autoriza -- mas quem o citar tem de dizer que ele está sem base, e é o
    resumo que garante isso. Só o que foi DERRUBADO cala de vez.

    Sem este portão a base viraria enfeite: as IAs citariam o que lhes conviesse
    e continuariam fazendo o que já faziam. Foi exatamente o que aconteceu na
    primeira versão do outro software, e o teste destrutivo é que mostrou.
    """
    it = por_id(ident)
    return bool(it and it.veredito != "derrubado")


def resumo(chave_jogo: Optional[str] = None) -> List[str]:
    itens = tudo(chave_jogo)
    L = [f"[Base] {len(itens)} itens de conhecimento"
         + (f" que servem para {chave_jogo}" if chave_jogo else "")
         + ":"]
    for origem, rotulo in ((MATEMATICA, "demonstrado"),
                           (DELE, "teoria dele"),
                           (CRENCA, "crença comum — a medir"),
                           (MINHA, "hipótese minha")):
        do_tipo = [i for i in itens if i.origem == origem]
        if not do_tipo:
            continue
        L.append(f"[Base]   {rotulo}: {len(do_tipo)}")
        for i in do_tipo:
            estado = {"confirmado": "✓ confirmado nos dados dele",
                      "derrubado": "✗ DERRUBADO — não autoriza mais nada",
                      "sem_base": "· ainda sem base para dizer",
                      None: "· ainda não medido"}[i.veredito]
            L.append(f"[Base]     {i.id} {i.titulo} — {estado}")
    derrubados = [i for i in itens if i.veredito == "derrubado"]
    if derrubados:
        L.append(f"[Base] {len(derrubados)} item(ns) derrubado(s) pela medida "
                 f"não podem mais justificar jogo nenhum")
    return L


def exportar(caminho) -> bool:
    """Grava a base como JSON — para ele ler, conferir e discordar."""
    try:
        from pathlib import Path
        p = Path(caminho)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([i.como_dict() for i in _BASE],
                                ensure_ascii=False, indent=1),
                     encoding="utf-8")
        return True
    except Exception:
        return False
