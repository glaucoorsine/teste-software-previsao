# -*- coding: utf-8 -*-
"""
DOZE CAÇADORES DO FORA DO PADRÃO.

Os agentes de ocorrência procuram regularidade. Estes procuram o contrário: o
que rompe, o que falta, o que ninguém cogitaria, o improvável que insiste.

    X01 SURPRESA        quem aparece quando o palpite falha
    X02 DESLOCAMENTO    a que distância na roda o resultado cai do previsto
    X03 FRIO_QUE_ACORDA número sumido que volta — e o que vem junto
    X04 QUEBRA          o que interrompe uma sequência forte
    X05 IMPROVAVEL      configuração rara que insiste em voltar
    X06 VAZIO           ausência longa demais, e o que sai quando termina
    X07 SALTO_ANOMALO   saltos na roda fora da distribuição usual
    X08 CONTRA_MARE     resultado contrário à tendência dominante
    X09 ORFAO           números que nunca entram em padrão nenhum
    X10 RUPTURA         o instante em que o caráter da mesa muda
    X11 ENTROPIA        a sequência é menos "bagunçada" do que deveria?
    X12 SILENCIO_QUEBRADO  depois de longa ausência de zero/bônus, o que vem

DESCOBERTA E CONFIRMAÇÃO SÃO COISAS DIFERENTES
----------------------------------------------
Estes agentes trabalham em modo DESCOBERTA: registram tudo que acharam, com a
força da evidência anotada, e não apagam nada. Uma ideia fraca hoje pode estar
esperando dado para se provar amanhã.

Quem decide o que vira sugestão é a etapa de CONFIRMAÇÃO, que exige evidência
fora da amostra. A correção estatística serve para separar "confirmado" de
"em observação" — não para jogar ideia no lixo.

Isso resolve um defeito real do desenho anterior: com 360 perguntas simultâneas
e FDR, um efeito verdadeiro mas modesto era enterrado e sumia sem deixar
registro. Agora ele fica no banco, marcado, esperando mais giros.

X11 usa entropia e compressibilidade — medidas que não passam por p-valor
nenhum. Servem justamente como olhar independente da máquina probabilística.
"""
from __future__ import annotations
import math
import zlib
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

RODA = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,
        5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
POS = {n: i for i, n in enumerate(RODA)}
VERMELHOS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

# Selos de evidência. Nada é descartado; tudo recebe um selo.
SELO_CONFIRMADO = "confirmado"      # sobreviveu à régua e ao controle de volume
SELO_OBSERVACAO = "em_observacao"   # aparece, ainda sem força — NÃO é lixo
SELO_FRACO      = "indicio"         # muito tênue, guardado para o futuro


def _p_ge(h: int, n: int, p: float) -> float:
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)
                        + k*math.log(p) + (n-k)*math.log(1-p))
               for k in range(min(h, n), n+1))


def _selo(p: Optional[float], m_perguntas: int = 1) -> str:
    if p is None:
        return SELO_FRACO
    if p <= 0.05 / max(1, m_perguntas):
        return SELO_CONFIRMADO
    if p <= 0.10:
        return SELO_OBSERVACAO
    return SELO_FRACO


def _dist_roda(a: int, b: int) -> Optional[int]:
    if a not in POS or b not in POS:
        return None
    d = (POS[b] - POS[a]) % 37
    return min(d, 37 - d)


# ============================================================ os doze
def X01_surpresa(seq, prev) -> List[dict]:
    """Quem aparece quando o palpite falha."""
    erros = [p for p in (prev or [])
             if p.get("alvos") and str(p.get("saiu")) not in [str(a) for a in p["alvos"]]]
    if len(erros) < 12:
        return []
    quem = Counter(int(p["saiu"]) for p in erros if str(p["saiu"]).lstrip("-").isdigit())
    if not quem:
        return []
    top, q = quem.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(erros), 1/37) * 37)
    return [{"agente": "X01_SURPRESA", "achado": f"o {top} lidera as surpresas ({q}x)",
             "alvos": [top], "razao": (q/len(erros))/(1/37), "p": p, "n": len(erros)}]


def X02_deslocamento(seq, prev) -> List[dict]:
    """A que distância na roda o resultado cai do que foi previsto."""
    ds = []
    for p in (prev or []):
        try:
            saiu = int(p.get("saiu"))
        except (TypeError, ValueError):
            continue
        cand = [_dist_roda(int(a), saiu) for a in (p.get("alvos") or [])]
        cand = [c for c in cand if c is not None]
        if cand:
            ds.append(min(cand))
    if len(ds) < 20:
        return []
    c = Counter(ds)
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(ds), 1/19) * 19)
    alvos = []
    if seq and seq[0] in POS:
        alvos = [RODA[(POS[seq[0]] + top) % 37], RODA[(POS[seq[0]] - top) % 37]]
    return [{"agente": "X02_DESLOCAMENTO",
             "achado": f"o resultado cai a {top} casas do previsto com frequência ({q}x)",
             "alvos": alvos, "razao": (q/len(ds))/(1/19), "p": p, "n": len(ds)}]


def X03_frio_que_acorda(seq, prev=None) -> List[dict]:
    """Número muito atrasado que volta — e o que vem logo depois dele."""
    if len(seq) < 80:
        return []
    ultimo_visto = {}
    acordadas = []
    for i, x in enumerate(seq):
        if x in ultimo_visto and (i - ultimo_visto[x]) >= 74:   # 2x o esperado
            if i + 1 < len(seq):
                acordadas.append(seq[i+1])
        ultimo_visto[x] = i
    if len(acordadas) < 8:
        return []
    c = Counter(acordadas)
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(acordadas), 1/37) * 37)
    return [{"agente": "X03_FRIO_QUE_ACORDA",
             "achado": f"depois que um número muito atrasado volta, costuma vir {top} ({q}/{len(acordadas)})",
             "alvos": [top], "razao": (q/len(acordadas))/(1/37), "p": p,
             "n": len(acordadas)}]


def X04_quebra(seq, prev=None) -> List[dict]:
    """O que interrompe uma sequência forte de cor."""
    if len(seq) < 60:
        return []
    quebras = []
    run = 1
    for a, b in zip(seq, seq[1:]):
        ca = "V" if a in VERMELHOS else ("P" if a else "Z")
        cb = "V" if b in VERMELHOS else ("P" if b else "Z")
        if ca == cb and ca != "Z":
            run += 1
        else:
            if run >= 5:
                quebras.append(b)
            run = 1
    if len(quebras) < 6:
        return []
    c = Counter(quebras)
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(quebras), 1/37) * 37)
    return [{"agente": "X04_QUEBRA",
             "achado": f"quem quebra sequência longa de cor costuma ser {top} ({q}/{len(quebras)})",
             "alvos": [top], "razao": (q/len(quebras))/(1/37), "p": p, "n": len(quebras)}]


def X05_improvavel(seq, prev=None) -> List[dict]:
    """
    Configuração rara que insiste em voltar.

    CUIDADO COM O ANIVERSÁRIO. A conta ingênua — "esta trinca específica tinha
    chance de 1/50653 e apareceu 2x, logo é impossível" — está errada, e por
    muito. Em 300 giros há 298 trincas sorteadas de 37³ possíveis, e o número
    esperado de repetições é ~0,88: ver UMA trinca repetida é o normal.

    Medido antes da correção: o agente "confirmava" um achado em 63% dos mundos
    de ruído puro, e apareceu idêntico nas três mesas reais do usuário — não era
    sinal, era este erro.

    A pergunta certa não é "esta trinca repetiu?", e sim "há MAIS repetições do
    que o aniversário prevê?".
    """
    if len(seq) < 100:
        return []
    n = len(seq) - 2
    tri = Counter(tuple(seq[i:i+3]) for i in range(n))
    total = 37 ** 3
    # repetições observadas contra as esperadas pelo paradoxo do aniversário
    repet = sum(q - 1 for q in tri.values() if q > 1)
    esperado = n * (n - 1) / (2 * total)
    if esperado <= 0:
        return []
    # Poisson: P(ver >= repet repetições)
    p = 1.0 - sum(math.exp(-esperado) * esperado**k / math.factorial(k)
                  for k in range(int(repet)))
    mais_vista = tri.most_common(1)[0] if tri else (None, 0)
    return [{"agente": "X05_IMPROVAVEL",
             "achado": (f"{repet} repetição(ões) de trinca, esperado {esperado:.2f} "
                        f"pelo aniversário"),
             "alvos": [mais_vista[0][2]] if mais_vista[1] > 1 else [],
             "razao": repet / esperado if esperado else None,
             "p": min(1.0, max(0.0, p)), "n": n}]


def X06_vazio(seq, prev=None) -> List[dict]:
    """Ausência longa demais — e o que sai quando ela termina."""
    if len(seq) < 100:
        return []
    visto = {}
    fins = []
    for i, x in enumerate(seq):
        if x in visto and (i - visto[x]) >= 111:      # 3x o esperado
            fins.append(x)
        visto[x] = i
    atuais = []
    for n in range(37):
        ult = visto.get(n)
        gap = len(seq) - ult if ult is not None else len(seq)
        if gap >= 111:
            atuais.append(n)
    if not fins and not atuais:
        return []
    return [{"agente": "X06_VAZIO",
             "achado": (f"{len(atuais)} número(s) sumido(s) há mais de 111 giros: "
                        f"{sorted(atuais)[:6]}"),
             "alvos": sorted(atuais)[:7], "razao": None,
             "p": None, "n": len(seq)}]


def X07_salto_anomalo(seq, prev=None) -> List[dict]:
    """Saltos na roda fora da distribuição usual."""
    saltos = [(POS[b]-POS[a]) % 37 for a, b in zip(seq, seq[1:])
              if a in POS and b in POS]
    if len(saltos) < 60:
        return []
    c = Counter(saltos)
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(saltos), 1/37) * 37)
    alvos = []
    if seq and seq[0] in POS:
        alvos = [RODA[(POS[seq[0]] + top) % 37]]
    return [{"agente": "X07_SALTO_ANOMALO",
             "achado": f"salto de {top} casas domina ({q}/{len(saltos)})",
             "alvos": alvos, "razao": (q/len(saltos))/(1/37), "p": p, "n": len(saltos)}]


def X08_contra_mare(seq, prev=None) -> List[dict]:
    """Resultado contrário à tendência recente de dúzia."""
    if len(seq) < 60:
        return []
    contras = []
    for i in range(12, len(seq)-1):
        jan = [x for x in seq[i-12:i] if x]
        if not jan:
            continue
        duz = Counter((x-1)//12 for x in jan)
        dom, q = duz.most_common(1)[0]
        if q < 7:
            continue
        prox = seq[i]
        if prox and (prox-1)//12 != dom:
            contras.append(prox)
    if len(contras) < 10:
        return []
    c = Counter(contras)
    top, q = c.most_common(1)[0]
    p = min(1.0, _p_ge(q, len(contras), 1/37) * 37)
    return [{"agente": "X08_CONTRA_MARE",
             "achado": f"quando a maré vira, {top} aparece {q}/{len(contras)}",
             "alvos": [top], "razao": (q/len(contras))/(1/37), "p": p, "n": len(contras)}]


def X09_orfao(seq, prev=None) -> List[dict]:
    """Números que quase não participam de nada."""
    if len(seq) < 100:
        return []
    c = Counter(seq)
    esperado = len(seq) / 37
    orfaos = sorted([n for n in range(37) if c.get(n, 0) <= max(1, esperado * 0.4)])
    if not orfaos:
        return []
    return [{"agente": "X09_ORFAO",
             "achado": f"{len(orfaos)} número(s) muito abaixo do esperado: {orfaos[:8]}",
             "alvos": orfaos[:7], "razao": None, "p": None, "n": len(seq)}]


def X10_ruptura(seq, prev=None) -> List[dict]:
    """O instante em que o caráter da mesa muda."""
    if len(seq) < 120:
        return []
    meio = len(seq) // 2
    def perfil(s):
        return Counter((x-1)//12 if x else -1 for x in s)
    a, b = perfil(seq[:meio]), perfil(seq[meio:])
    dif = sum(abs(a.get(k, 0)/max(1, meio) - b.get(k, 0)/max(1, len(seq)-meio))
              for k in set(a) | set(b))
    if dif < 0.15:
        return []
    return [{"agente": "X10_RUPTURA",
             "achado": f"o perfil da mesa mudou entre as duas metades (dif={dif:.2f})",
             "alvos": [], "razao": None, "p": None, "n": len(seq)}]


def X11_entropia(seq, prev=None) -> List[dict]:
    """
    Medida SEM p-valor de hipótese: a sequência é menos bagunçada do que deveria?

    Entropia de Shannon e compressibilidade são outra forma de olhar —
    independentes da máquina probabilística, que é o que o usuário pediu.

    Só que MEDIR não basta: uma entropia de 5,12 não diz nada sozinha, porque
    mesmo uma sequência perfeitamente aleatória de 300 giros não atinge o
    máximo teórico (5,21) — falta amostra para todos os 37 aparecerem por
    igual. Sem uma régua o agente media e ficava mudo: detectava 0 de 25
    sequências com entropia artificialmente baixa.

    A régua aqui não é p-valor de hipótese: é a distribuição EMPÍRICA da
    entropia em sequências uniformes do mesmo tamanho, obtida por simulação
    direta. Compara-se com o percentil, não com um teste.
    """
    if len(seq) < 100:
        return []
    n = len(seq)
    c = Counter(seq)
    H = -sum((q/n) * math.log2(q/n) for q in c.values() if q)
    Hmax = math.log2(37)
    bruto = bytes(x % 256 for x in seq)
    comp = len(zlib.compress(bruto, 9)) / max(1, len(bruto))

    # régua: entropia típica de sequências uniformes deste tamanho
    import random as _r
    rng = _r.Random(9182736)
    amostras = []
    for _ in range(200):
        cc = Counter(rng.randrange(37) for _ in range(n))
        amostras.append(-sum((q/n) * math.log2(q/n) for q in cc.values() if q))
    amostras.sort()
    abaixo = sum(1 for a in amostras if a <= H)
    percentil = abaixo / len(amostras)
    # p = fração de sequências uniformes com entropia AINDA MENOR que a nossa
    p = max(percentil, 1.0 / (len(amostras) + 1))

    tipica = amostras[len(amostras)//2]
    return [{"agente": "X11_ENTROPIA",
             "achado": (f"entropia {H:.3f} (típica {tipica:.3f}, máx {Hmax:.3f}); "
                        f"compressão {comp:.3f} — percentil {100*percentil:.0f}"),
             "alvos": [n for n, _ in c.most_common(5)] if percentil < 0.10 else [],
             "razao": (tipica / H) if H else None,
             "p": p, "n": n,
             "entropia": round(H, 4), "compressao": round(comp, 4),
             "entropia_tipica": round(tipica, 4)}]


def X12_silencio_quebrado(seq, prev=None) -> List[dict]:
    """Depois de longa ausência do zero, o que vem."""
    if len(seq) < 80:
        return []
    depois = []
    ult = None
    for i, x in enumerate(seq):
        if x == 0:
            if ult is not None and (i - ult) >= 55 and i + 1 < len(seq):
                depois.append(seq[i+1])
            ult = i
    if len(depois) < 5:
        return []
    c = Counter(depois)
    top, q = c.most_common(1)[0]
    return [{"agente": "X12_SILENCIO_QUEBRADO",
             "achado": f"após zero muito atrasado, veio {top} em {q}/{len(depois)}",
             "alvos": [top], "razao": (q/len(depois))/(1/37),
             "p": min(1.0, _p_ge(q, len(depois), 1/37) * 37), "n": len(depois)}]


AGENTES_X = [X01_surpresa, X02_deslocamento, X03_frio_que_acorda, X04_quebra,
             X05_improvavel, X06_vazio, X07_salto_anomalo, X08_contra_mare,
             X09_orfao, X10_ruptura, X11_entropia, X12_silencio_quebrado]


# --------------------------------------------------------------- Crazy Time
# A roda do Crazy Time NAO e' a roleta: sao 54 fatias com 8 simbolos de
# frequencias muito diferentes. Os doze agentes acima assumem 37 casas em toda
# parte (1/37, log2(37), distancia na roda). Rodá-los aqui nao e' impreciso, e'
# sem sentido -- e pior: int(x) DERRUBA CoinFlip/CashHunt/Pachinko/CrazyBonus,
# deixando uma sequencia mutilada de 1/2/5/10 que e' lida como roleta.
#
# O estrago era garantido, nao ocasional: 334 giros reais de Crazy Time davam
# 3 "confirmados" -- entropia 1,71 contra uma regua de 5,12 que e' da roleta,
# "salto de 0 casas domina" (so sobraram 4 simbolos), e "quebra de sequencia
# de cor" num jogo que nao tem cor.
CT_FATIAS = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2, "CrazyBonus": 1}
CT_TOTAL = 54
CT_BONUS = {"CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"}
CT_P_BONUS = sum(CT_FATIAS[s] for s in CT_BONUS) / CT_TOTAL


def _p_le(h: int, n: int, p: float) -> float:
    """Cauda inferior: sair TAO POUCO quanto isto."""
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n+1) - math.lgamma(k+1) - math.lgamma(n-k+1)
                        + k*math.log(p) + (n-k)*math.log(1-p))
               for k in range(0, min(h, n) + 1))


def _anomalias_ct(sim: List[str]) -> List[dict]:
    """
    O fora-do-padrao no Crazy Time, com a regua do Crazy Time.

    Cada pergunta e' comparada com a roda real (21/13/7/4/4/2/2/1 em 54), nao
    com uma roleta imaginaria. As perguntas de geometria (deslocamento, salto,
    orfao) nao tem equivalente aqui e simplesmente nao sao feitas -- melhor uma
    pergunta a menos do que uma resposta inventada.
    """
    import random as _r
    n = len(sim)
    out: List[dict] = []
    c = Counter(sim)

    # XC1 -- o bonus dorme e acorda?
    for k in (3, 5, 8):
        h = t = 0
        seco = 0
        for x in sim:
            if seco >= k:
                t += 1
                if x in CT_BONUS:
                    h += 1
            seco = 0 if x in CT_BONUS else seco + 1
        if t >= 15:
            out.append({"agente": f"XC1_BONUS_ACORDA@{k}",
                        "achado": f"apos {k}+ giros sem bonus, veio bonus {h}/{t}",
                        "alvos": sorted(CT_BONUS),
                        "razao": (h/t)/CT_P_BONUS if t else None,
                        "p": _p_ge(h, t, CT_P_BONUS), "n": t})

    # XC2 -- algum simbolo esta SUMINDO
    for s_, fat in CT_FATIAS.items():
        p = fat / CT_TOTAL
        obs = c.get(s_, 0)
        if n * p >= 5:
            out.append({"agente": f"XC2_SUMIU_{s_}",
                        "achado": f"{s_} saiu {obs}x, esperado {n*p:.1f}",
                        "alvos": [], "razao": (obs/n)/p if n else None,
                        "p": _p_le(obs, n, p), "n": n})

    # XC3 -- repeticao imediata. REGUA E' REORDENACAO, nao binomial: os pares
    # (i, i+1) se sobrepoem, tratá-los como independentes exagera a forca. Nos
    # 334 giros reais o binomial dava "confirmado" e a reordenacao da 0,043.
    p_rep = sum((f/CT_TOTAL)**2 for f in CT_FATIAS.values())
    rep = sum(1 for i in range(n-1) if sim[i] == sim[i+1])
    if n > 60:
        rng_r = _r.Random(31337)
        copia = sim[:]
        piores = 0
        N_REGUA = 1000
        for _ in range(N_REGUA):
            rng_r.shuffle(copia)
            if sum(1 for i in range(n-1) if copia[i] == copia[i+1]) >= rep:
                piores += 1
        out.append({"agente": "XC3_REPETE",
                    "achado": f"repetiu o mesmo simbolo {rep}/{n-1}, esperado {p_rep*(n-1):.1f}",
                    "alvos": [], "razao": (rep/(n-1))/p_rep,
                    "p": (piores + 1) / (N_REGUA + 1), "n": n-1})

    # XC4 -- a mesa mudou no meio?
    if n >= 120:
        meio = n // 2
        b1 = sum(1 for x in sim[:meio] if x in CT_BONUS)
        b2 = sum(1 for x in sim[meio:] if x in CT_BONUS)
        alto, n_alto = ((b2, n - meio) if b2/(n-meio) > b1/meio else (b1, meio))
        base = (b1 + b2) / n
        out.append({"agente": "XC4_RUPTURA",
                    "achado": f"bonus 1a metade {b1}/{meio} vs 2a {b2}/{n-meio}",
                    "alvos": [], "razao": None,
                    "p": _p_ge(alto, n_alto, base) if base > 0 else None, "n": n})

    # XC5 -- entropia contra a regua CERTA: simulacao da propria roda do CT
    if n >= 100:
        H = -sum((q/n) * math.log2(q/n) for q in c.values() if q)
        pool = [s_ for s_, f in CT_FATIAS.items() for _ in range(f)]
        rng = _r.Random(5150)
        amostras = []
        for _ in range(300):
            cc = Counter(rng.choice(pool) for _ in range(n))
            amostras.append(-sum((q/n) * math.log2(q/n) for q in cc.values() if q))
        amostras.sort()
        percentil = sum(1 for a in amostras if a <= H) / len(amostras)
        tipica = amostras[len(amostras)//2]
        out.append({"agente": "XC5_ENTROPIA",
                    "achado": (f"entropia {H:.3f} (tipica desta roda {tipica:.3f}) "
                               f"-- percentil {100*percentil:.0f}"),
                    "alvos": [], "razao": (tipica/H) if H else None,
                    "p": max(percentil, 1.0/(len(amostras)+1)), "n": n})
    return out


def cacar_anomalias(historico, previsoes=None) -> Dict[str, Any]:
    """
    Roda os doze. NADA é descartado — cada achado sai com um selo de evidência.

    O selo separa "pode virar sugestão agora" de "guardado, esperando dado".
    Ideia fraca não é ideia morta.
    """
    brutos = [str(x) for x in (historico or [])]
    if sum(1 for x in brutos if x in CT_BONUS) >= 2:
        sim = [x for x in brutos if x in CT_FATIAS]
        if len(sim) < 60:
            return {"achados": [], "candidatos": [], "erro": "histórico curto"}
        achados = _anomalias_ct(sim)
        m = sum(1 for a in achados if a.get("p") is not None)
        for a in achados:
            a["selo"] = _selo(a.get("p"), m or 1)
        por_selo = Counter(a["selo"] for a in achados)
        cand = sorted(CT_BONUS) if any(
            a["selo"] == SELO_CONFIRMADO and a["agente"].startswith("XC1")
            for a in achados) else []
        return {"achados": achados, "candidatos": cand,
                "confirmados": por_selo[SELO_CONFIRMADO],
                "em_observacao": por_selo[SELO_OBSERVACAO],
                "indicios": por_selo[SELO_FRACO], "n_giros": len(sim)}

    seq = []
    for x in (historico or []):
        try:
            seq.append(int(x))
        except (TypeError, ValueError):
            pass
    if len(seq) < 40:
        return {"achados": [], "candidatos": [], "erro": "histórico curto"}

    achados = []
    for ag in AGENTES_X:
        try:
            achados.extend(ag(seq, previsoes) or [])
        except Exception as e:
            achados.append({"agente": getattr(ag, "__name__", "?"),
                            "achado": f"[erro: {type(e).__name__}]",
                            "alvos": [], "razao": None, "p": None, "n": 0})

    m = sum(1 for a in achados if a.get("p") is not None)
    for a in achados:
        a["selo"] = _selo(a.get("p"), m or 1)

    cand: Dict[int, float] = defaultdict(float)
    for a in achados:
        peso = {SELO_CONFIRMADO: 1.0, SELO_OBSERVACAO: 0.4, SELO_FRACO: 0.0}[a["selo"]]
        if peso and (a.get("razao") or 0) > 1:
            for n in (a.get("alvos") or []):
                cand[int(n)] += peso * min(3.0, a["razao"] - 1)

    por_selo = Counter(a["selo"] for a in achados)
    return {
        "achados": achados,
        "candidatos": [n for n, _ in sorted(cand.items(), key=lambda kv: -kv[1])][:7],
        "confirmados": por_selo[SELO_CONFIRMADO],
        "em_observacao": por_selo[SELO_OBSERVACAO],
        "indicios": por_selo[SELO_FRACO],
        "n_giros": len(seq),
    }


def resumo_anomalias(r: Dict[str, Any]) -> str:
    if r.get("erro"):
        return f"[Anomalias] {r['erro']}"
    L = [f"[Anomalias] {r['confirmados']} confirmado(s), "
         f"{r['em_observacao']} em observação, {r['indicios']} indício(s) "
         f"— nada foi descartado"]
    for a in r["achados"]:
        if a["selo"] == SELO_FRACO:
            continue
        marca = "✓" if a["selo"] == SELO_CONFIRMADO else "·"
        L.append(f"   {marca} {a['agente']}: {a['achado']}")
    if r.get("candidatos"):
        L.append(f"   candidatos: {r['candidatos']}")
    return "\n".join(L)
