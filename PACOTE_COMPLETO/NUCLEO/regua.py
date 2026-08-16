# -*- coding: utf-8 -*-
"""
A RÉGUA — o nulo tem que destruir EXATAMENTE o que a teoria afirma.

A CRÍTICA DELE, QUE ESTAVA CERTA
────────────────────────────────
    "a sua métrica que você chama de régua, ela é completamente errada, não
     funciona, e torna quase tudo inválido"

Estava. E o defeito não era frouxidão -- era o contrário: a régua comia o
achado. Eu usava um único nulo para tudo, embaralhar a ordem dos mesmos
números. Só que embaralhar PRESERVA a composição da amostra:

    F07 afirma "esta mesa tem classes mais frequentes que outras"

    dado real                              1,238x
    nulo embaralhado (mesma composição)    1,108x   ← preserva o viés!
    nulo uniforme (dado honesto de 37)     0,999x   ← destrói o viés

Contra o embaralhado a leitura dava 1,118x. Contra o nulo certo, 1,239x, com
0 de 15 placebos alcançando. O embaralhamento continha a própria coisa que eu
estava testando, então o teste estava cego por construção.

A REGRA, QUE É DELE
───────────────────
Cada dossiê do compêndio tem uma seção chamada "Controle negativo e
falsificação"; cada formulação do Tratado tem o contraditório na seção 4. São
1.360 réguas escritas por ele, uma por teoria -- porque o controle negativo
CERTO depende do que a teoria afirma. Não existe régua única.

    a teoria afirma            o nulo tem que destruir      então o nulo é
    ─────────────────────────  ───────────────────────────  ──────────────
    esta mesa é desigual       a desigualdade               UNIFORME
    (composição)               (sorteio honesto de N)

    há estrutura no tempo      a ordem, guardando quem      EMBARALHADO
    (ordem, atraso, motivo)    apareceu quantas vezes

    há dependência longa       a ordem longa, guardando a   BLOCO
    além da curta              vizinhança imediata

Usar o embaralhado numa teoria de composição cega o teste (foi o que eu fiz).
Usar o uniforme numa teoria de tempo credita à teoria um viés de composição
que ela não afirmou -- o erro oposto, e igualmente grave.

O QUE ESTE ARQUIVO NÃO FAZ
──────────────────────────
Não decide sozinho qual nulo cabe. Cada família DECLARA o dela em `NULO`, com
a justificativa ao lado. Quando o texto integral dos estudos estiver na pasta,
`contraditorio_declarado()` traz o que ELE escreveu para aquela formulação --
e a palavra dele vale mais que a minha classificação.
"""
from __future__ import annotations

import math
import random
from typing import Any, Callable, Dict, List, Sequence

PLACEBOS = 20          # p mínimo de 1/21 ≈ 0,048, o suficiente para o corte de 5%

# ═══════════════════════════════════════════════════════ os três nulos

def nulo_uniforme(series, rnd, n_classes: int):
    """Sorteio honesto de N. Destrói a COMPOSIÇÃO e a ordem.

    O nulo de quem afirma que a mesa é desigual: se a leitura ainda ganha
    contra um dado honesto, a desigualdade é dela e não da minha régua.
    """
    return [[rnd.randrange(n_classes) for _ in s] for s in series]


def nulo_embaralhado(series, rnd, n_classes: int):
    """Os MESMOS números, outra ordem. Destrói só o TEMPO.

    O nulo de quem afirma estrutura temporal -- atraso, transição, motivo,
    regime. A composição fica idêntica de propósito: a teoria não a reivindica.
    """
    out = []
    for s in series:
        c = list(s)
        rnd.shuffle(c)
        out.append(c)
    return out


def nulo_bloco(series, rnd, n_classes: int, tam: int = 5):
    """Embaralha BLOCOS inteiros. Guarda a vizinhança curta, destrói a longa.

    O nulo de quem afirma dependência de longo alcance: se a leitura vence um
    embaralhamento que preservou os pares imediatos, o que ela achou não era
    só o par imediato.
    """
    out = []
    for s in series:
        blocos = [s[i:i + tam] for i in range(0, len(s), tam)]
        rnd.shuffle(blocos)
        out.append([x for b in blocos for x in b])
    return out


NULOS: Dict[str, Callable] = {
    "uniforme": nulo_uniforme,
    "embaralhado": nulo_embaralhado,
    "bloco": nulo_bloco,
}

# ═══════════════════════════════ qual nulo falsifica cada família dele
#
# A pergunta para cada uma é sempre a mesma: o que esta leitura AFIRMA? O nulo
# tem que destruir aquilo, e só aquilo.
# O mapa de nulos que eu tinha inventado saiu daqui. Os controles agora são os
# DELE, 48, um por família, em `controles.py` -- lidos da seção 4 de cada
# formulação do Tratado. Ele mandou: "você tem que estudar, buscar nos meus
# PDFs mesmo". Estavam escritos lá desde o começo.

def nulo_de(familia: str) -> tuple:
    """O controle DELE para esta família, e a instrução original resumida."""
    from . import controles as C
    return C.controle_de(familia)


def contraditorio_declarado(familia: str, jogo: str) -> str:
    """O contraditório que ELE escreveu para esta família, se estiver na pasta.

    A palavra dele vale mais que a minha classificação acima. Sem o texto
    integral, devolve vazio -- e aí a tabela `NULO` é o melhor que eu tenho.
    """
    try:
        from . import base as B
        return B.contraditorio(familia, jogo)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════ a medição

def separacao_limpa(series: Sequence[List[int]],
                    ler: Callable[[List[int]], List[str]],
                    n_classes: int = 37, k: int = 12):
    """O desenho honesto: treina no passado DISTANTE, prevê o futuro inteiro.

    POR QUE ISTO SUBSTITUIU A CAMINHADA
    ───────────────────────────────────
    Eu media andando para trás: para cada giro, ler o histórico que vem
    depois dele na lista e conferir. Cada previsão sozinha é limpa -- o alvo
    nunca entra no histórico que a produziu.

    Só que as previsões não são independentes umas das outras. O alvo do giro
    5 está DENTRO do histórico usado para prever o giro 3. O mesmo arquivo
    finito é contado dos dois lados, dezenas de vezes, e a desigualdade que
    ele tem por acaso vira "acerto" repetido.

    Medido nas bases dele, a diferença entre os dois desenhos:

        Lightning   caminhada 1,317x p=0,0025    separação 1,070x p=0,26
        Mega Fire   caminhada 0,925x p=0,78      separação 0,933x p=0,75

    O achado da Lightning era do desenho, não da mesa.

    Aqui as duas metades são DISJUNTAS: a metade antiga constrói a leitura, a
    metade recente é prevista, e nenhum giro aparece dos dois lados.
    """
    acertos = tentativas = 0
    esperado = 0.0
    for s in series:
        if len(s) < 60:
            continue
        meio = len(s) // 2
        novo, velho = s[:meio], s[meio:]      # a lista vem recente-primeiro
        topo = ler(velho)[:k]
        if not topo:
            continue
        for alvo in novo:
            tentativas += 1
            esperado += len(set(topo)) / n_classes
            if str(alvo) in topo:
                acertos += 1
    return acertos, tentativas, esperado


def medir_limpo(series: Sequence[List[int]],
                ler: Callable[[List[int]], List[str]],
                familia: str = "", n_classes: int = 37, k: int = 12,
                placebos: int = PLACEBOS,
                semente: int = 20260816) -> Dict[str, Any]:
    """Separação limpa + o nulo que falsifica aquela família. É a régua final."""
    def avaliar(ss):
        return separacao_limpa(ss, ler, n_classes, k)
    return medir(series, avaliar, familia, n_classes, placebos, semente)


def binom_cauda(k: int, n: int, p: float) -> float:
    if n <= 0 or k <= 0:
        return 1.0
    return min(1.0, sum(math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
                        for i in range(k, n + 1)))


def razao(acertos: int, tentativas: int, esperado: float) -> float:
    if not tentativas or esperado <= 0:
        return 0.0
    return (acertos / tentativas) / (esperado / tentativas)


def medir(series: Sequence[List[int]],
          avaliar: Callable[[Sequence[List[int]]], Any],
          familia: str = "",
          n_classes: int = 37,
          placebos: int = PLACEBOS,
          semente: int = 20260816) -> Dict[str, Any]:
    """Mede a leitura contra o nulo que a falsificaria.

    `avaliar` recebe as séries e devolve (acertos, tentativas, esperado).
    """
    from . import controles as C
    tipo, porque = nulo_de(familia)

    def gerar(ss, rnd, nc):
        return C.aplicar(familia, ss, rnd, nc)
    a, n, e = avaliar(series)
    r_real = razao(a, n, e)

    rnd = random.Random(semente)
    rs: List[float] = []
    for _ in range(placebos):
        a2, n2, e2 = avaliar(gerar(series, rnd, n_classes))
        if n2:
            rs.append(razao(a2, n2, e2))
    if not rs:
        return {"familia": familia, "nulo": tipo, "razao": r_real,
                "tentativas": n, "motivo": "nenhum placebo pôde ser medido"}

    ordenado = sorted(rs)
    mediana = ordenado[len(ordenado) // 2]
    alcancaram = sum(1 for x in rs if x >= r_real)
    p_perm = (alcancaram + 1) / (len(rs) + 1)
    honesto = (r_real / mediana) if mediana else 0.0
    return {
        "familia": familia, "nulo": tipo, "porque_este_nulo": porque,
        "acertos": a, "tentativas": n,
        "razao_bruta": r_real, "razao_nulo": mediana, "razao": honesto,
        "delta_neg": r_real - mediana,
        "p": p_perm, "placebos": len(rs), "alcancaram": alcancaram,
        "p_ingenuo": binom_cauda(a, n, e / n) if n else 1.0,
        "motivo": (f"{a}/{n} = {r_real:.3f}x bruto; nulo {tipo} {mediana:.3f}x; "
                   f"honesto {honesto:.3f}x; p={p_perm:.3f}"),
    }


def mesa_e_justa(series, n_classes: int = 37) -> dict:
    """A roda é justa? Aderência ao uniforme — e aqui o uniforme É o certo.

    ISTO NÃO É UM CONTROLE NEGATIVO, e a diferença é o que eu vinha errando.

    Os 48 controles dele respondem "esta LEITURA acrescenta alguma coisa além
    da composição?" — e por isso todos preservam a composição, como manda a
    F35. Testar viés de roda com um deles é cego por construção: o controle
    carrega o próprio viés que se quer detectar.

    "esta roda é desigual?" é outra pergunta, e é de ADERÊNCIA: as contagens
    observadas batem com as de uma roda justa? Aí o uniforme é a referência
    certa, porque a hipótese nula é literalmente "a roda é justa".

    Duas perguntas, dois nulos. Confundir as duas foi a raiz de tudo:

        viés de roda            aderência ao uniforme      (esta função)
        a leitura acrescenta?   permutação que preserva    (os controles dele)
                                composição

    Devolve o qui-quadrado, os graus de liberdade e o p por Monte Carlo — que
    é o que a ficha 001 do compêndio dele manda usar quando há célula esparsa,
    e com 37 classes em algumas centenas de giros sempre há.
    """
    from collections import Counter
    todas = [x for s in series for x in s]
    n = len(todas)
    if n < 4 * n_classes:
        return {"justa": None, "n": n,
                "motivo": f"só {n} giros para {n_classes} classes — sem poder"}
    esp = n / n_classes
    c = Counter(todas)
    q = sum((c.get(x, 0) - esp) ** 2 / esp for x in range(int(n_classes)))

    rnd = random.Random(20260816)
    piores = 0
    ENSAIOS = 2000
    for _ in range(ENSAIOS):
        c2 = Counter(rnd.randrange(int(n_classes)) for _ in range(n))
        q2 = sum((c2.get(x, 0) - esp) ** 2 / esp for x in range(int(n_classes)))
        if q2 >= q:
            piores += 1
    p = (piores + 1) / (ENSAIOS + 1)
    return {
        "justa": bool(p >= 0.05), "n": n, "qui2": q, "gl": int(n_classes) - 1,
        "p": p,
        "motivo": (f"qui-quadrado {q:.1f} em {int(n_classes)-1} gl, "
                   f"p={p:.4f} por Monte Carlo — "
                   + ("nada distingue esta roda de uma justa"
                      if p >= 0.05 else "esta roda NÃO é justa")),
    }


def benjamini_hochberg(ps: Dict[str, float], fdr: float = 0.05) -> List[str]:
    """Quais sobrevivem quando muitos são testados ao mesmo tempo.

    Com 44 famílias, a melhor passa de 0,05 por sorte em ~90% das vezes.
    """
    if not ps:
        return []
    ordem = sorted(ps.items(), key=lambda t: t[1])
    m = len(ordem)
    corte = 0
    for i, (_nome, p) in enumerate(ordem, 1):
        if p <= i / m * fdr:
            corte = i
    return [nome for nome, _p in ordem[:corte]]


def conferir_calibragem(n_classes: int = 37, giros: int = 200,
                        repeticoes: int = 60, k: int = 12) -> Dict[str, float]:
    """A régua está calibrada? Em mesa honesta ela TEM que dar 1,00x.

    Este é o auto-exame que deveria ter existido antes de eu anunciar qualquer
    coisa. Ele roda a régua inteira -- separação limpa mais nulo -- sobre um
    dado honesto de 37 faces. Se sair 1,10x, a régua está creditando à leitura
    uma vantagem que veio da própria medição, e foi exatamente o que a minha
    fazia.

    Devolve a razão medida por desenho. Longe de 1,00 = régua quebrada.
    """
    from collections import Counter
    rnd = random.Random(4242)

    def ler(velho):
        return [str(c) for c, _q in Counter(velho).most_common(k)]

    fora = {}
    # o desenho limpo, que é o que o núcleo usa
    rs = []
    for _ in range(repeticoes):
        s = [[rnd.randrange(n_classes) for _ in range(giros)]]
        a, n, e = separacao_limpa(s, ler, n_classes, k)
        if n and e:
            rs.append((a / n) / (e / n))
    fora["separacao_limpa"] = sum(rs) / max(1, len(rs))

    # e a caminhada, para o contraste ficar registrado no próprio código
    rs = []
    for _ in range(max(8, repeticoes // 5)):
        s = [rnd.randrange(n_classes) for _ in range(giros)]
        a = n = 0
        e = 0.0
        for i in range(0, len(s) - 90):
            topo = [c for c, _q in Counter(s[i + 1:]).most_common(k)]
            if not topo:
                continue
            n += 1
            e += len(set(topo)) / n_classes
            if s[i] in topo:
                a += 1
        if n and e:
            rs.append((a / n) / (e / n))
    fora["caminhada"] = sum(rs) / max(1, len(rs))
    return fora
