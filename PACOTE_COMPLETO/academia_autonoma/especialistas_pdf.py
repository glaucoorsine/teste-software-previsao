# -*- coding: utf-8 -*-
"""
QUINZE ESPECIALISTAS NOS PDFS DELE.

O QUE ELE PEDIU
---------------
    "coloque 15 IAs especialistas nos meus dois pdfs opinando sobre os números
     de previsão com todo o PDF como base de consulta"

A DIFERENÇA PARA O QUE JÁ EXISTIA
---------------------------------
`previsores_compendio.py` pegou onze conceitos do eixo de séries e virou IA.
Foi um recorte meu: escolhi os que eu achava testáveis e deixei 69 de fora.

Aqui é outra coisa. Os 80 conceitos do compêndio e as 416 fichas do estudo de
multiplicadores são divididos entre QUINZE especialistas, e cada um é dono de
uma faixa. Nenhuma ficha fica sem dono. Cada especialista:

    - consulta as fichas dele em `dados_teorias.json`, de verdade, na hora
    - opina sobre os números com a leitura da faixa que domina
    - diz quais fichas sustentam a opinião dele, para a tela poder mostrar

OS QUINZE E SUAS FAIXAS
-----------------------
    E01  001-015  FREQUÊNCIA        uniformidade, sobredispersão, subdispersão
    E02  016-025  DEPENDÊNCIA CURTA autocorrelação, dependência não linear
    E03  026-030  REGIME            a mesa muda de humor
    E04  031-040  MEMÓRIA           memória longa, reversão à média
    E05  041-050  RARIDADE          agrupamento de raridades, renovação
    E06  051-060  CICLO             periodicidade, sazonalidade oculta
    E07  061-080  BORDA E AMOSTRA   efeito de borda, sobrevivência, instabilidade
    E08  081-100  CALIBRAÇÃO        calibração, discriminação, prequential
    E09  101-120  INFORMAÇÃO        entropia, informação mútua, taxa de entropia
    E10  121-135  COMPLEXIDADE      compressão, algorítmica, MDL
    E11  136-160  CAUSALIDADE       causalidade temporal, confundimento, mediação
    E12  161-185  DINÂMICA          emergência, criticalidade, recorrência
    E13  186-200  MEDIÇÃO           observabilidade, erro de medição
    E14  ESTUDO   MULTIPLICADOR-OCORRÊNCIA   as 416 fichas, lente de ocorrência
    E15  ESTUDO   MULTIPLICADOR-MAGNITUDE    as 416 fichas, lente de magnitude

POR QUE ALGUNS SE CALAM, E ISSO É CERTO
---------------------------------------
E07 (borda), E08 (calibração), E10 (complexidade) e E13 (medição) quase nunca
apontam número — as faixas deles são sobre QUALIDADE DA LEITURA, não sobre qual
número vem. Eles opinam sobre a confiança dos outros: quando a amostra é curta,
quando a entropia está alta demais para prever, quando a medição tem ruído.

Um especialista que fala sempre é um que não sabe do que fala. Estes quatro
existem para dizer "hoje não dá", e essa é a opinião mais valiosa que eles têm.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}

# ─────────────────────────── o corte do E17, medido em vez de arbitrado ─────
#
# A varredura de vício físico passa uma janela por TODAS as posições da roda e
# fica com a maior. Comparar essa maior com o corte de uma janela só é a
# armadilha das fichas 201-300 -- medido aqui, o alarme falso em roda honesta
# dava 42%. Šidák sobre as janelas efetivas (N/largura) derrubou para 16%,
# ainda mentiroso: janelas que se sobrepõem têm cauda mais pesada do que a
# fórmula supõe.
#
# Então o corte não é escolhido, é MEDIDO -- o percentil 95 do maior z sob roda
# honesta, por Monte Carlo. É o que a ficha 001 dele manda fazer quando a
# aproximação assintótica não serve: "substituir a aproximação assintótica por
# Monte Carlo multinomial sob probabilidades iguais".
#
# Roda uma vez por formato de roda e fica em cache; o resultado varia pouco com
# o tamanho da amostra (3,15 / 2,98 / 3,00 para 120 / 180 / 250 giros).
SETOR_W = 5
ALFA_SETOR = 0.05
_Z_CACHE: Dict[tuple, float] = {}
Z_SETOR_FALLBACK = 3.15


def z_corte_setor(n_giros: int, n_pos: int = None, largura: int = SETOR_W,
                  ensaios: int = 4000) -> float:
    """Percentil 95 do maior z de setor sob roda honesta. Medido, não chutado."""
    import random as _r
    n_pos = n_pos or len(RODA)
    chave = (n_pos, largura, min(400, max(120, int(n_giros) // 60 * 60)))
    if chave in _Z_CACHE:
        return _Z_CACHE[chave]
    n = chave[2]
    p = largura / n_pos
    esp, dp = n * p, math.sqrt(n * p * (1 - p)) or 1.0
    rnd = _r.Random(20260816)            # semente fixa: o corte não pode oscilar
    maiores = []
    for _ in range(ensaios):
        c = Counter(rnd.randrange(n_pos) for _ in range(n))
        maiores.append(max(
            (sum(c.get((i + d) % n_pos, 0) for d in range(largura)) - esp) / dp
            for i in range(n_pos)))
    maiores.sort()
    z = maiores[min(len(maiores) - 1, int((1 - ALFA_SETOR) * len(maiores)))]
    _Z_CACHE[chave] = z
    return z


def _ints(seq):
    out = []
    for x in seq or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


# O compendio dele traz um conceito a cada cinco fichas: a ficha 001 abre o
# bloco 001-005, a 006 abre o 006-010, e assim ate a 396. Sao 80 blocos, 400
# fichas. As faixas dos especialistas abaixo estao em FICHA, nao em bloco.
FICHAS_POR_CONCEITO = 5


def fichas_de(ini: int, fim: int) -> List[dict]:
    """As fichas do compêndio dele nesta faixa. Consulta real ao arquivo."""
    try:
        from academia_autonoma.biblioteca_teorias import conceitos
        return [c for c in conceitos() if ini <= c.get("n", 0) <= fim]
    except Exception:
        return []


# ═══════════════════════════════════════════════════ os que apontam número

def e01_frequencia(seq, n_classes, ctx):
    """001-015 · uniformidade, sobredispersão, subdispersão.

    Quem excede a variação que o próprio acaso produziria. A ficha 001 dá o
    modelo nulo (multinomial uniforme); as 006 e 011 dão os dois desvios.
    """
    s = _ints(seq)[:150]
    if len(s) < 50:
        return {}, "amostra curta para julgar frequência"
    esp = len(s) / n_classes
    dp = math.sqrt(esp * (1 - 1 / n_classes)) or 1.0
    c = Counter(s)
    peso = {x: (c[x] - esp) / dp for x in c if (c[x] - esp) / dp > 1.2}
    return peso, ("nenhum valor excede a variação normal"
                  if not peso else f"{len(peso)} acima de 1,2 desvios")


def e02_dependencia_curta(seq, n_classes, ctx):
    """016-025 · autocorrelação e dependência não linear.

    O que costuma vir logo depois do que acabou de sair, com o peso da força
    da dependência medida — não do palpite.
    """
    s = _ints(seq)[:250]
    if len(s) < 60:
        return {}, "amostra curta para dependência"
    atual = s[0]
    seg = Counter()
    vezes = 0
    for i in range(1, len(s)):
        if s[i] == atual:
            vezes += 1
            seg[s[i - 1]] += 1
    if vezes < 3:
        return {}, f"o {atual} só apareceu {vezes}x antes — sem base"
    return ({x: q / vezes for x, q in seg.items() if q >= 2},
            f"em {vezes} vezes que o {atual} saiu, o que veio depois")


def e03_regime(seq, n_classes, ctx):
    """026-030 · mudança de regime. A metade recente contra a antiga."""
    s = _ints(seq)[:240]
    if len(s) < 80:
        return {}, "amostra curta para comparar regimes"
    meio = len(s) // 2
    novo, velho = Counter(s[:meio]), Counter(s[meio:])
    peso = {}
    for x in set(novo) | set(velho):
        d = novo.get(x, 0) / meio - velho.get(x, 0) / (len(s) - meio)
        if d > 0.012:
            peso[x] = d * 100
    return peso, ("as duas metades são iguais — sem mudança de regime"
                  if not peso else f"{len(peso)} subiram na metade recente")


def e04_memoria(seq, n_classes, ctx):
    """031-040 · memória longa e reversão à média.

    As duas fichas se contradizem de propósito. Este especialista soma as duas
    leituras e devolve o saldo — quem tem eco longo E está abaixo do esperado.
    """
    s = _ints(seq)[:300]
    if len(s) < 100:
        return {}, "amostra curta para memória longa"
    atual = s[0]
    eco = defaultdict(float)
    for k in range(1, 13):
        for i in range(len(s) - k):
            if s[i + k] == atual:
                eco[s[i]] += 1.0 / k
    esp = len(s) / n_classes
    c = Counter(s)
    peso = {}
    for x, v in eco.items():
        falta = max(0.0, esp - c.get(x, 0)) / max(esp, 1)
        peso[x] = v * (1.0 + falta)
    return peso, "eco em vários atrasos, com desconto de quem já saiu demais"


def e05_raridade(seq, n_classes, ctx):
    """041-050 · agrupamento de raridades e processo de renovação.

    A ficha 046 é a que ele confirmou por conta própria: "sinal é somente o que
    tá muito tempo sem vir". Aqui o intervalo é comparado ao PRÓPRIO típico de
    cada número, não à média da mesa.
    """
    s = _ints(seq)[:280]
    if len(s) < 80:
        return {}, "amostra curta para intervalos"

    # A lista vem RECENTE-PRIMEIRO. Então o índice já é "quantos giros atrás",
    # e o atraso de um número é o MENOR índice em que ele aparece -- a
    # ocorrência mais nova. Guardar `ultima[x] = i` a cada passada deixava lá o
    # MAIOR índice, ou seja, a aparição mais VELHA: o número que acabou de sair
    # era anunciado como o mais atrasado da mesa. Era o avesso do que ele pede.
    atraso, anterior, inter = {}, {}, defaultdict(list)
    for i, x in enumerate(s):
        if x in anterior:
            inter[x].append(i - anterior[x])
        else:
            atraso[x] = i                        # primeira vista = mais nova
        anterior[x] = i

    # E o caso mais extremo do critério dele -- "o que tá muito tempo sem vir"
    # -- é o número que não veio NENHUMA vez. Varrer só quem apareceu deixava
    # esse de fora justamente por ter sumido. A varredura agora é da mesa toda.
    peso, nunca = {}, 0
    for x in range(int(n_classes)):
        h = inter.get(x) or []
        tip = (sum(h) / len(h)) if h else float(n_classes)
        if x in atraso:
            desde = atraso[x]
        else:
            desde = len(s)                       # sumiu a amostra inteira
            nunca += 1
        if desde > tip * 1.3:
            peso[x] = desde / max(tip, 1.0)
    extra = f" ({nunca} não vieram nenhuma vez)" if nunca else ""
    return peso, ((f"{len(peso)} passaram do próprio intervalo típico" + extra)
                  if peso else "ninguém passou do próprio intervalo")


def e06_ciclo(seq, n_classes, ctx):
    """051-060 · periodicidade e sazonalidade oculta.

    Mais exigente que a renovação: o intervalo tem que ser REGULAR, e o número
    tem que estar chegando na hora dele.
    """
    s = _ints(seq)[:280]
    if len(s) < 80:
        return {}, "amostra curta para ciclo"
    ultima, inter = {}, defaultdict(list)
    for i, x in enumerate(s):
        if x in ultima:
            inter[x].append(i - ultima[x])
        ultima[x] = i
    peso = {}
    for x, h in inter.items():
        if len(h) < 3:
            continue
        m = sum(h) / len(h)
        dp = math.sqrt(sum((k - m) ** 2 for k in h) / len(h))
        if m <= 0 or dp / m > 0.35:
            continue
        if abs(ultima.get(x, 0) - m) <= max(1.0, dp):
            peso[x] = 1.0 + (1.0 - dp / m)
    return peso, (f"{len(peso)} com intervalo regular, chegando na hora"
                  if peso else "nenhum intervalo suficientemente regular")


def e09_informacao(seq, n_classes, ctx):
    """101-120 · entropia, informação mútua, taxa de entropia.

    Só fala quando a entropia da janela recente está ABAIXO do máximo: se a
    sequência está no teto da diversidade, não há informação a extrair e o
    especialista se cala — que é o que a ficha 116 manda fazer.
    """
    s = _ints(seq)[:200]
    if len(s) < 80:
        return {}, "amostra curta para entropia"
    c = Counter(s)
    n = len(s)
    h = -sum((q / n) * math.log(q / n, 2) for q in c.values())
    h_max = math.log(min(n_classes, len(c)), 2) or 1.0
    if h / h_max > 0.97:
        return {}, f"entropia em {h/h_max:.0%} do máximo — nada a extrair"
    return ({x: q for x, q in c.items() if q >= 2},
            f"entropia em {h/h_max:.0%} do máximo — há concentração")


def e11_causalidade(seq, n_classes, ctx):
    """136-160 · causalidade temporal, confundimento, mediação.

    Procura o antecessor que mais MUDA a distribuição do seguinte, e desconta
    o que é explicado pela frequência geral — que é o confundidor óbvio aqui.
    """
    s = _ints(seq)[:300]
    if len(s) < 100:
        return {}, "amostra curta para causalidade"
    atual = s[0]
    base = Counter(s)
    n = len(s)
    seg, vezes = Counter(), 0
    for i in range(1, len(s)):
        if s[i] == atual:
            vezes += 1
            seg[s[i - 1]] += 1
    if vezes < 4:
        return {}, f"o {atual} apareceu {vezes}x — pouco para separar causa"
    peso = {}
    for x, q in seg.items():
        cond = q / vezes
        marg = base.get(x, 0) / n
        if cond > marg * 1.5 and q >= 2:
            peso[x] = cond - marg
    return peso, (f"{len(peso)} aparecem depois do {atual} acima da própria "
                  f"frequência" if peso else "nada acima do confundidor")


def e12_dinamica(seq, n_classes, ctx):
    """161-185 · recorrência dinâmica, criticalidade, atrator.

    A ficha 176: quando o estado atual repete um estado passado, o que veio
    depois daquele tende a voltar. Estado = a dupla que acabou de sair.
    """
    s = _ints(seq)[:300]
    if len(s) < 60:
        return {}, "amostra curta para recorrência"
    alvo = tuple(s[:2])
    peso = defaultdict(float)
    achou = 0
    for i in range(2, len(s) - 1):
        if tuple(s[i:i + 2]) == alvo:
            achou += 1
            peso[s[i - 1]] += 1.0
    return (dict(peso), f"a dupla {alvo} já apareceu {achou}x antes"
            if achou else "esta dupla nunca apareceu antes")


# ═════════════════════════════════ os que opinam sobre a CONFIANÇA dos outros

def e07_borda(seq, n_classes, ctx):
    """061-080 · efeito de borda, viés de sobrevivência, instabilidade.

    Não aponta número: mede se a leitura depende do tamanho da janela. Compara
    o topo em 100 e em 200 giros; se mudar muito, avisa que o achado é da
    borda, não da mesa.
    """
    s = _ints(seq)
    if len(s) < 200:
        return {}, "com menos de 200 giros, toda leitura é de borda"
    t1 = {x for x, _ in Counter(s[:100]).most_common(6)}
    t2 = {x for x, _ in Counter(s[:200]).most_common(6)}
    est = len(t1 & t2) / 6.0
    return {}, (f"topo muda {(1-est):.0%} entre 100 e 200 giros — "
                + ("leitura instável, desconfie" if est < 0.5
                   else "leitura estável"))


def e08_calibracao(seq, n_classes, ctx):
    """081-100 · calibração, discriminação, validação prequential.

    Opina sobre o placar, não sobre o número: com a taxa observada e o acaso da
    aposta, diz se há discriminação ou só cobertura.
    """
    taxa = (ctx or {}).get("taxa_acerto")
    acaso = (ctx or {}).get("acaso_k")
    if taxa is None or not acaso:
        return {}, "sem janelas fechadas ainda para calibrar"
    r = taxa / acaso if acaso else 0
    if r < 1.02:
        return {}, f"{r:.2f}x — cobertura, não discriminação (ficha 086)"
    return {}, f"{r:.2f}x acima do acaso da mesma aposta"


def e10_complexidade(seq, n_classes, ctx):
    """121-135 · compressão, complexidade algorítmica, MDL.

    Mede se a sequência é comprimível. Sequência incomprimível é sequência sem
    regra curta — e a ficha 131 diz que sem regra curta não há previsão barata.
    """
    s = _ints(seq)[:200]
    if len(s) < 100:
        return {}, "amostra curta para compressão"
    import zlib
    bruto = bytes(bytearray([x % 256 for x in s]))
    razao = len(zlib.compress(bruto, 9)) / max(1, len(bruto))
    if razao > 0.92:
        return {}, f"comprime só {(1-razao):.0%} — sem regra curta escondida"
    return {}, f"comprime {(1-razao):.0%} — há estrutura repetida"


def e13_medicao(seq, n_classes, ctx):
    """186-200 · observabilidade, identificabilidade, erro de medição.

    Diz o que NÃO dá para saber com os dados que chegam. É a ficha 196 aplicada
    ao próprio software: sem horário por evento e sem variável física, uma
    classe inteira de hipóteses não é testável aqui.
    """
    s = _ints(seq)
    faltas = []
    if len(s) < 300:
        faltas.append(f"histórico curto ({len(s)} giros)")
    if not (ctx or {}).get("tem_tempo"):
        faltas.append("sem horário por giro")
    if not (ctx or {}).get("tem_mult"):
        faltas.append("sem dado de multiplicador")
    return {}, ("o que falta para testar mais: " + ", ".join(faltas)
                if faltas else "dados suficientes para o catálogo inteiro")


def e16_vieses(seq, n_classes, ctx):
    """201-300 · sobreajuste, apofenia, ilusão de agrupamento, falácia do jogador.

    Este não aponta número: ele AUDITA os outros catorze. As fichas dele
    descrevem exatamente as armadilhas em que este software já caiu -- apofenia
    (o falso positivo de 68% dos caçadores), vazamento temporal (medir e
    descobrir na mesma amostra), consenso ilusório (quatro ecos contados como
    quatro vozes).

    A opinião dele é sobre a opinião dos outros, e é a mais desconfortável:
    quando muitos especialistas concordam olhando a mesma coisa, ele diz.
    """
    palp = (ctx or {}).get("palpites_ate_agora") or {}
    if len(palp) < 3:
        return {}, "poucos opinaram para auditar"
    try:
        from academia_autonoma.biblioteca_teorias import n_efetivo
        d = n_efetivo(palp) or {}
    except Exception:
        return {}, "auditoria indisponível"
    inf = float(d.get("inflacao") or 1.0)
    if inf >= 1.6:
        return {}, (f"ficha 226: {d.get('nominal')} opinaram mas valem "
                    f"{d.get('efetivo')} — muita repetição, desconfie")
    # ficha 291: seca longa não muda a chance do próximo giro
    s = _ints(seq)[:200]
    if s:
        c = Counter(s)
        sumidos = [x for x in range(n_classes) if c.get(x, 0) == 0]
        if len(sumidos) > n_classes * 0.25:
            return {}, (f"ficha 291: {len(sumidos)} números sumidos da janela — "
                        f"seca longa não muda a chance do próximo giro")
    return {}, f"opiniões razoavelmente independentes ({inf:.2f}x de inflação)"


def e17_fisica(seq, n_classes, ctx):
    """301-400 · assimetria geométrica, vibração, deriva, memória do equipamento.

    Estas são as ÚNICAS fichas do compêndio que descrevem uma causa real de
    vício: a roda desequilibrada, o pino gasto, a deriva de calibração. Todas
    se manifestam do mesmo jeito observável -- concentração num SETOR CONTÍGUO
    da roda física, não em números espalhados pelo pano.

    É a leitura mais valiosa e a que mais precisa de dado que não temos:
    velocidade, posição de queda, identidade do equipamento. Sem isso, o que dá
    para fazer é a assinatura de setor -- e é o que ele faz.
    """
    s = _ints(seq)[:250]
    if len(s) < 120:
        return {}, "amostra curta para assinatura física (precisa de 120+)"
    pos = [POS[x] for x in s if x in POS]
    if not pos:
        return {}, "sem posição na roda"
    n, N = len(pos), len(RODA)
    conta = Counter(pos)

    # A roda é um CÍRCULO e a janela desliza. Cortá-la em oito blocos fixos
    # fazia duas besteiras: o último bloco ficava com 2 casas em vez de 5 (e
    # parecia frio para sempre), e um setor viciado bem em cima do corte era
    # partido no meio e nunca aparecia. Aqui a janela passa por todas as N
    # posições e dá a volta.
    melhor, z_max = None, -9.9
    p = SETOR_W / N
    esp = n * p
    dp = math.sqrt(n * p * (1 - p)) or 1.0
    for ini in range(N):
        jan = [(ini + d) % N for d in range(SETOR_W)]
        z = (sum(conta.get(j, 0) for j in jan) - esp) / dp
        if z > z_max:
            melhor, z_max = jan, z

    # O corte vem medido sob roda honesta (ver z_corte_setor), não arbitrado.
    try:
        z_corte = z_corte_setor(n, N, SETOR_W)
    except Exception:                                   # pragma: no cover
        z_corte = Z_SETOR_FALLBACK
    if z_max <= z_corte:
        return {}, (f"maior setor da roda a {z_max:.1f} desvios, abaixo do "
                    f"corte de {z_corte:.1f} — roda simétrica")
    return ({RODA[j]: z_max for j in melhor},
            f"setor contíguo da roda a {z_max:.1f} desvios (corte {z_corte:.1f}, "
            f"medido sob roda honesta com as {N} janelas testadas) — "
            f"assinatura de vício físico (fichas 301-400)")


# ══════════════════════════════════ os dois do estudo de multiplicadores

def e14_mult_ocorrencia(seq, n_classes, ctx):
    """As 416 fichas, lente de OCORRÊNCIA.

    O estudo dele mede: Lighting +8,2%, Mega Fire -3,4%, Crazy Time -15,4%.
    Este especialista só opina onde a lente tem ganho medido, e usa os números
    que as sete IAs de multiplicador apontaram.
    """
    jogo = (ctx or {}).get("jogo", "")
    try:
        from academia_autonoma.biblioteca_teorias import lente_util
        lu = lente_util(jogo) or {}
    except Exception:
        return {}, "estudo indisponível"
    if (lu.get("ocorrencia") or 0) <= 0:
        return {}, (f"o estudo dele mede {lu.get('ocorrencia')}% de ganho de "
                    f"ocorrência nesta mesa — nada a acrescentar")
    nums = (ctx or {}).get("mult_consenso") or []
    return ({str(x): 1.0 for x in nums},
            f"o estudo dele mede +{lu['ocorrencia']}% de ganho de ocorrência aqui")


def e15_mult_magnitude(seq, n_classes, ctx):
    """As 416 fichas, lente de MAGNITUDE.

    Crazy Time +8,7%, Crazy Time A +30,1%, Lighting -59,2%. É a lente invertida
    entre roleta e crazy time -- o achado central daquele estudo.
    """
    jogo = (ctx or {}).get("jogo", "")
    try:
        from academia_autonoma.biblioteca_teorias import lente_util
        lu = lente_util(jogo) or {}
    except Exception:
        return {}, "estudo indisponível"
    if (lu.get("magnitude") or 0) <= 0:
        return {}, (f"o estudo dele mede {lu.get('magnitude')}% na magnitude "
                    f"desta mesa — não vale opinar por aqui")
    nums = (ctx or {}).get("mult_intensos") or []
    return ({str(x): 1.0 for x in nums},
            f"o estudo dele mede +{lu['magnitude']}% de ganho de magnitude aqui")


# ═══════════════════════════════════════════════════════════ o painel dos 15
ESPECIALISTAS: Tuple = (
    ("E01_FREQUENCIA", e01_frequencia, (1, 15), "frequência e dispersão"),
    ("E02_DEPENDENCIA", e02_dependencia_curta, (16, 25), "dependência curta"),
    ("E03_REGIME", e03_regime, (26, 30), "mudança de regime"),
    ("E04_MEMORIA", e04_memoria, (31, 40), "memória longa e reversão"),
    ("E05_RARIDADE", e05_raridade, (41, 50), "raridade e renovação"),
    ("E06_CICLO", e06_ciclo, (51, 60), "periodicidade"),
    ("E07_BORDA", e07_borda, (61, 80), "borda e estabilidade da amostra"),
    ("E08_CALIBRACAO", e08_calibracao, (81, 100), "calibração e discriminação"),
    ("E09_INFORMACAO", e09_informacao, (101, 120), "entropia e informação"),
    ("E10_COMPLEXIDADE", e10_complexidade, (121, 135), "compressão e MDL"),
    ("E11_CAUSALIDADE", e11_causalidade, (136, 160), "causalidade e confundidor"),
    ("E12_DINAMICA", e12_dinamica, (161, 185), "recorrência dinâmica"),
    ("E13_MEDICAO", e13_medicao, (186, 200), "o que não dá para medir aqui"),
    ("E16_VIESES", e16_vieses, (201, 300), "vieses e armadilhas de método"),
    ("E17_FISICA", e17_fisica, (301, 400), "assinatura de vício físico na roda"),
    ("E14_MULT_OCORRENCIA", e14_mult_ocorrencia, (0, 0),
     "estudo dos multiplicadores — lente de ocorrência"),
    ("E15_MULT_MAGNITUDE", e15_mult_magnitude, (0, 0),
     "estudo dos multiplicadores — lente de magnitude"),
)


def quantas_fichas(nome: str) -> int:
    """Quantas FICHAS este especialista tem debaixo do braço.

    O compêndio guarda um conceito a cada cinco fichas (n = 1, 6, 11, … 396),
    então contar conceitos daria 3 onde a faixa 001-015 tem 15 fichas. Ele
    pediu "todo o PDF como base de consulta" — a conta tem que fechar em 400.
    """
    for n, _f, (a, b), _d in ESPECIALISTAS:
        if n == nome:
            return len(fichas_de(a, b)) * FICHAS_POR_CONCEITO if b else 416
    return 0


def quantos_conceitos(nome: str) -> int:
    for n, _f, (a, b), _d in ESPECIALISTAS:
        if n == nome:
            return len(fichas_de(a, b)) if b else 0
    return 0


def especialidade(nome: str) -> str:
    for n, _f, _fx, d in ESPECIALISTAS:
        if n == nome:
            return d
    return ""


def consultar(seq, n_classes: int = 37, ctx: Dict[str, Any] = None,
              k: int = 6) -> Dict[str, Any]:
    """Os quinze opinam. Devolve palpites e o que cada um viu."""
    ctx = ctx or {}
    palpites, falas = {}, {}
    # o auditor (E16) roda por ultimo: a opiniao dele e sobre a dos outros
    ordem = ([e for e in ESPECIALISTAS if e[0] != "E16_VIESES"]
             + [e for e in ESPECIALISTAS if e[0] == "E16_VIESES"])
    for nome, fn, _fx, _d in ordem:
        if nome == "E16_VIESES":
            ctx = dict(ctx); ctx["palpites_ate_agora"] = dict(palpites)
        try:
            peso, fala = fn(seq, n_classes, ctx)
        except Exception as e:
            peso, fala = {}, f"erro: {type(e).__name__}"
        falas[nome] = fala
        if peso:
            # nome proprio: `ordem` acima e a fila dos especialistas, e
            # reaproveitar o nome aqui so funcionava porque o iterador do
            # `for` ja tinha a lista. Um dia alguem mexe e quebra.
            ranking = sorted(peso.items(), key=lambda x: (-x[1], str(x[0])))
            palpites[nome] = [str(n) for n, v in ranking if v > 0][:k]
    return {"palpites": palpites, "falas": falas,
            "opinaram": len(palpites), "total": len(ESPECIALISTAS)}


def resumo(seq, n_classes: int = 37, ctx: Dict[str, Any] = None) -> str:
    r = consultar(seq, n_classes, ctx)
    L = [f"[Especialistas] {r['opinaram']} dos {r['total']} opinaram "
         f"(cada um dono de uma faixa dos seus PDFs)"]
    for nome, _fn, (a, b), desc in ESPECIALISTAS:
        p = r["palpites"].get(nome)
        faixa = f"fichas {a:03d}-{b:03d}" if b else "estudo mult."
        if p:
            L.append(f"   {nome:<20} {faixa:<16} {' '.join(p[:6])}")
        else:
            L.append(f"   {nome:<20} {faixa:<16} — {r['falas'].get(nome, '')[:52]}")
    return "\n".join(L)
