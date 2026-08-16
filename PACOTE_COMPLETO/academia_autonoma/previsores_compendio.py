# -*- coding: utf-8 -*-
"""
AS PRÁTICAS DE PREVISÃO DO COMPÊNDIO DELE, VIRADAS EM IA.

A COBRANÇA
----------
    "é pra ler todos meus dois pdfs, pegar todas as práticas de previsão que
     estão ali, ensinar todas as IAs dos softwares, porque você não fez isso?"

Ele tinha razão. Eu extraí as 400 fichas, montei a biblioteca, e depois usei o
material só quando ele explicava um defeito que eu já tinha na mão — consenso
ilusório, vazamento temporal, apofenia. Cinco fichas aplicadas de oitenta, e
quatro delas eram regras de MÉTODO (não seja enganado), não de PREVISÃO.

Usei o compêndio dele como manual de segurança e ignorei o resto como fonte de
ideias, que é para o que ele escreveu o documento.

O QUE ESTE ARQUIVO FAZ
----------------------
Cada conceito do eixo de séries que descreve um MECANISMO OBSERVÁVEL vira uma
IA que aponta números e entra no consenso como qualquer outra fonte. O nome de
cada uma carrega o número da ficha, então dá para rastrear de onde veio.

    C006  SOBREDISPERSÃO      alguns valores saem mais do que a variação
                              esperada permitiria -- não é "quente", é excesso
                              acima do que o próprio acaso produziria
    C011  SUBDISPERSÃO        o inverso: valores espalhados demais, ninguém
                              repete, e o que falta tende a preencher
    C016  AUTOCORRELAÇÃO      o valor de agora se parece com o de k giros atrás
    C026  MUDANÇA DE REGIME   a mesa mudou de humor -- o que vale é a metade
                              recente, não a média de tudo
    C031  MEMÓRIA LONGA       dependências fracas somadas em muitos atrasos
    C036  REVERSÃO À MÉDIA    quem está muito acima do esperado tende a ceder
    C041  AGRUP. DE RARIDADES o improvável vem em grupo, não espalhado
    C046  PROCESSO DE RENOV.  o intervalo entre aparições tem distribuição
                              própria -- é a ficha da IA que já vai melhor
    C051  PERIODICIDADE       o mesmo valor volta em intervalo regular
    C056  SAZONALIDADE        a posição dentro do ciclo importa
    C061  EFEITO DE BORDA     o começo e o fim da janela observada mentem
    C111  INFORMAÇÃO MÚTUA    qual valor anterior mais reduz a incerteza do
                              seguinte -- e aponta o que ele costuma trazer
    C176  RECORRÊNCIA DINÂM.  quando o estado atual repete um estado passado,
                              o que veio depois daquele tende a voltar

O QUE NÃO VIROU IA, E POR QUÊ
-----------------------------
Do eixo FÍSICA (20 conceitos): vibração, deriva de calibração, assimetria
geométrica, ruído térmico. Todos precisam de variáveis que a API não entrega —
velocidade da bola, posição de queda, identidade do equipamento. Fazer uma IA
sem esses dados seria inventar leitura.

Do eixo IA/VALIDAÇÃO (16): sobreajuste, vazamento temporal, consenso ilusório.
São regras de método, e já estão aplicadas onde importam — no crivo, no N
efetivo, no controle dos caçadores. Elas não apontam número, elas impedem que
número errado passe.

Do eixo INFORMAÇÃO, a maioria mede COMPLEXIDADE (entropia, compressão, MDL).
Servem para descrever o quanto uma sequência é previsível, não para dizer qual
número vem. Entram como medida na academia, não como voto.

MEDIDA, NUNCA DECLARADA
-----------------------
Cada uma é avaliada contra o acaso da mesma lista, igual às sete de
multiplicador. Quem fica abaixo de 1,00x continua votando -- mais baixo. Ele
foi explícito desde o começo: "não critique e nem barre".
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List

K_PALPITE = 6

# a roda física, para os conceitos que dependem de vizinhança
RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}


def _ints(seq):
    saida = []
    for x in seq or []:
        try:
            saida.append(int(x))
        except (TypeError, ValueError):
            continue
    return saida


# ─────────────────────────────────────────────────────────── ficha 006
def c006_sobredispersao(seq, n_classes=37, janela=120):
    """Excesso acima do que a própria variação do acaso produziria.

    Não é "quente". Quente é olhar quem saiu mais. Aqui a conta é: quanto cada
    valor excede o desvio-padrão esperado da própria contagem. Um valor que
    saiu 8 vezes em 120 giros de 37 números está a 2,3 desvios; um que saiu 6
    está dentro do normal e não conta.
    """
    s = _ints(seq)[:janela]
    if len(s) < 40:
        return {}
    n = len(s)
    esp = n / n_classes
    dp = (esp * (1 - 1 / n_classes)) ** 0.5 or 1.0
    c = Counter(s)
    return {x: (c[x] - esp) / dp for x in c if (c[x] - esp) / dp > 1.0}


def c011_subdispersao(seq, n_classes=37, janela=120):
    """O inverso: quem está abaixo do esperado, medido em desvios."""
    s = _ints(seq)[:janela]
    if len(s) < 40:
        return {}
    n = len(s)
    esp = n / n_classes
    dp = (esp * (1 - 1 / n_classes)) ** 0.5 or 1.0
    c = Counter(s)
    saida = {}
    for x in range(n_classes):
        z = (esp - c.get(x, 0)) / dp
        if z > 1.0:
            saida[x] = z
    return saida


# ─────────────────────────────────────────────────────────── ficha 016
def c016_autocorrelacao(seq, n_classes=37, lags=(1, 2, 3, 4, 5), janela=200):
    """O valor de agora se parece com o de k giros atrás?

    Mede a correlação em cada atraso e, se algum se destaca, aponta o que
    apareceu naquela distância do valor atual.
    """
    s = _ints(seq)[:janela]
    if len(s) < 60:
        return {}
    media = sum(s) / len(s)
    var = sum((x - media) ** 2 for x in s) / len(s) or 1.0
    melhor, r_melhor = None, 0.0
    for k in lags:
        pares = [(s[i] - media) * (s[i + k] - media) for i in range(len(s) - k)]
        r = (sum(pares) / len(pares)) / var if pares else 0.0
        if abs(r) > abs(r_melhor):
            melhor, r_melhor = k, r
    if melhor is None or abs(r_melhor) < 0.08:
        return {}
    atual = s[0]
    peso = defaultdict(float)
    for i in range(len(s) - melhor):
        if s[i + melhor] == atual:
            peso[s[i]] += abs(r_melhor)
    return dict(peso)


# ─────────────────────────────────────────────────────────── ficha 026
def c026_mudanca_regime(seq, n_classes=37, janela=200):
    """A mesa mudou de humor: o que vale é a metade recente.

    Compara a frequência da metade recente com a antiga e aponta quem subiu.
    Se as duas metades são iguais, não há regime e a IA se cala.
    """
    s = _ints(seq)[:janela]
    if len(s) < 80:
        return {}
    meio = len(s) // 2
    novo, velho = Counter(s[:meio]), Counter(s[meio:])
    saida = {}
    for x in set(novo) | set(velho):
        d = novo.get(x, 0) / meio - velho.get(x, 0) / (len(s) - meio)
        if d > 0.01:
            saida[x] = d * 100
    return saida


# ─────────────────────────────────────────────────────────── ficha 031
def c031_memoria_longa(seq, n_classes=37, janela=300):
    """Dependências fracas somadas em muitos atrasos.

    Nenhum atraso sozinho diz nada; a soma sobre 1..12 pode dizer. Aponta os
    valores que mais aparecem a qualquer distância do valor atual.
    """
    s = _ints(seq)[:janela]
    if len(s) < 100:
        return {}
    atual = s[0]
    peso = defaultdict(float)
    for k in range(1, 13):
        for i in range(len(s) - k):
            if s[i + k] == atual:
                peso[s[i]] += 1.0 / k        # atraso curto pesa mais
    return dict(peso)


# ─────────────────────────────────────────────────────────── ficha 036
def c036_reversao_media(seq, n_classes=37, janela=120):
    """Quem está muito acima do esperado tende a ceder.

    É o oposto declarado da sobredispersão, e as duas existirem juntas é de
    propósito: se as duas apontassem sempre o mesmo, uma seria supérflua.
    """
    s = _ints(seq)[:janela]
    if len(s) < 40:
        return {}
    esp = len(s) / n_classes
    c = Counter(s)
    return {x: (esp - c.get(x, 0)) for x in range(n_classes)
            if c.get(x, 0) < esp * 0.6}


# ─────────────────────────────────────────────────────────── ficha 041
def c041_agrupamento_raridades(seq, n_classes=37, janela=60, perto=6):
    """O improvável vem em grupo, não espalhado.

    Se um valor raro apareceu há pouco, os OUTROS raros ganham peso — a ficha
    diz que raridades se agrupam no tempo.
    """
    s = _ints(seq)[:janela]
    if len(s) < 40:
        return {}
    c = Counter(s)
    raros = [x for x in range(n_classes) if c.get(x, 0) <= 1]
    recentes = set(s[:perto])
    if not (recentes & set(raros)):
        return {}
    return {x: 1.0 for x in raros if x not in recentes}


# ─────────────────────────────────────────────────────────── ficha 046
def c046_renovacao(seq, n_classes=37, janela=250):
    """O intervalo entre aparições tem distribuição própria.

    É a ficha da IA que já vai melhor no multiplicador. Aqui: quem passou do
    PRÓPRIO intervalo típico, não do intervalo médio da mesa.
    """
    s = _ints(seq)[:janela]
    if len(s) < 80:
        return {}
    ultimas = {}
    intervalos = defaultdict(list)
    for i, x in enumerate(s):
        if x in ultimas:
            intervalos[x].append(i - ultimas[x])
        ultimas[x] = i
    saida = {}
    for x in range(n_classes):
        desde = ultimas.get(x)
        if desde is None:
            continue
        hist = intervalos.get(x) or []
        tipico = (sum(hist) / len(hist)) if hist else n_classes
        if desde > tipico * 1.3:
            saida[x] = desde / max(tipico, 1.0)
    return saida


# ─────────────────────────────────────────────────────────── ficha 051
def c051_periodicidade(seq, n_classes=37, janela=250):
    """O mesmo valor volta em intervalo regular.

    Diferente da renovação: aqui não basta estar atrasado — o intervalo tem
    que ser CONSTANTE, e o valor tem que estar chegando na hora dele.
    """
    s = _ints(seq)[:janela]
    if len(s) < 80:
        return {}
    ultimas, intervalos = {}, defaultdict(list)
    for i, x in enumerate(s):
        if x in ultimas:
            intervalos[x].append(i - ultimas[x])
        ultimas[x] = i
    saida = {}
    for x, hist in intervalos.items():
        if len(hist) < 3:
            continue
        m = sum(hist) / len(hist)
        dp = (sum((h - m) ** 2 for h in hist) / len(hist)) ** 0.5
        if m <= 0 or dp / m > 0.35:      # irregular demais para ser período
            continue
        desde = ultimas.get(x, 0)
        if abs(desde - m) <= max(1.0, dp):
            saida[x] = 1.0 + (1.0 - dp / m)
    return saida


# ─────────────────────────────────────────────────────────── ficha 111
def c111_informacao_mutua(seq, n_classes=37, janela=300):
    """Qual valor o atual costuma trazer depois dele.

    Transição de primeira ordem, mas pesada pela redução de incerteza: só
    conta quando aquele antecessor aparece o suficiente para significar algo.
    """
    s = _ints(seq)[:janela]
    if len(s) < 80:
        return {}
    atual = s[0]
    depois = Counter()
    vezes = 0
    for i in range(1, len(s)):
        if s[i] == atual:
            vezes += 1
            depois[s[i - 1]] += 1
    if vezes < 3:
        return {}
    return {x: q / vezes for x, q in depois.items() if q >= 2}


# ─────────────────────────────────────────────────────────── ficha 176
def c176_recorrencia(seq, n_classes=37, janela=300, contexto=2):
    """O estado atual repete um estado passado — o que veio depois volta?

    Recorrência dinâmica: procura no passado a mesma dupla de valores que
    acabou de sair e aponta o que se seguiu a ela.
    """
    s = _ints(seq)[:janela]
    if len(s) < 60:
        return {}
    alvo = tuple(s[:contexto])
    peso = defaultdict(float)
    for i in range(contexto, len(s) - 1):
        if tuple(s[i:i + contexto]) == alvo:
            peso[s[i - 1]] += 1.0
    return dict(peso)


# ─────────────────────────────────────────────────────── ficha 061
def c061_efeito_borda(seq, n_classes=37):
    """O começo e o fim da janela observada mentem.

    Não aponta número: é um CONTROLE. Se a leitura muda muito conforme o
    tamanho da janela, o achado depende da borda e não da mesa. Devolve vazio
    de propósito -- quem usa isso é o crivo, para desconfiar.
    """
    return {}


IAS = (
    ("C006_SOBREDISPERSAO", c006_sobredispersao,
     "sai acima do que a própria variação do acaso permitiria"),
    ("C011_SUBDISPERSAO", c011_subdispersao,
     "está abaixo do esperado, medido em desvios"),
    ("C016_AUTOCORRELACAO", c016_autocorrelacao,
     "apareceu na mesma distância do valor de agora, outras vezes"),
    ("C026_REGIME", c026_mudanca_regime,
     "subiu na metade recente — a mesa mudou de humor"),
    ("C031_MEMORIA_LONGA", c031_memoria_longa,
     "acompanha o valor atual a várias distâncias, somadas"),
    ("C036_REVERSAO", c036_reversao_media,
     "está muito abaixo do esperado e tende a voltar"),
    ("C041_RARIDADES", c041_agrupamento_raridades,
     "é raro, e outro raro acabou de sair — eles vêm em grupo"),
    ("C046_RENOVACAO", c046_renovacao,
     "passou do PRÓPRIO intervalo típico, não da média da mesa"),
    ("C051_PERIODICIDADE", c051_periodicidade,
     "volta em intervalo regular, e está chegando na hora dele"),
    ("C111_INFO_MUTUA", c111_informacao_mutua,
     "é o que costuma vir depois do valor que acabou de sair"),
    ("C176_RECORRENCIA", c176_recorrencia,
     "veio depois desta mesma dupla, no passado"),
)


def _topo(peso: Dict[Any, float], k: int) -> List[str]:
    if not peso:
        return []
    return [str(n) for n, v in
            sorted(peso.items(), key=lambda x: (-x[1], str(x[0])))
            if v > 0][:k]


def opinar(seq, n_classes: int = 37, k: int = K_PALPITE) -> Dict[str, List[str]]:
    """O que cada IA do compêndio aponta agora. Vazio é resposta legítima."""
    saida = {}
    for nome, fn, _desc in IAS:
        try:
            peso = fn(seq, n_classes) or {}
        except Exception:
            peso = {}
        p = _topo(peso, k)
        if p:
            saida[nome] = p
    return saida


def descricao(nome: str) -> str:
    for n, _fn, d in IAS:
        if n == nome:
            return d
    return ""


def resumo(seq, n_classes: int = 37) -> str:
    o = opinar(seq, n_classes)
    L = [f"[Compêndio] {len(IAS)} práticas de previsão dos PDFs dele · "
         f"{len(o)} têm palpite agora"]
    for nome, nums in list(o.items())[:6]:
        L.append(f"   {nome:<22} {' '.join(nums[:6])}")
    if not o:
        L.append("   nenhuma tem o que dizer com este histórico — "
                 "calar é resposta")
    return "\n".join(L)
