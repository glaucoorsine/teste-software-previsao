# -*- coding: utf-8 -*-
"""
O gerador de relações — descoberta de verdade, não lista de compras.

POR QUE ESTE ARQUIVO SUBSTITUI O CATÁLOGO
-----------------------------------------
No A14 eu escrevi quinze relações à mão e chamei aquilo de descoberta. Ele
respondeu: "tem inúmeras outras que podem descobrir, eles foram feitos pra
descobrir mas não fazem". Estava certo. Um catálogo que eu escrevo só acha o
que eu já pensei — o limite passa a ser a minha imaginação, não a capacidade
delas.

Aqui as relações são MONTADAS. Cada uma nasce de um atributo do número
cruzado com um comparador:

    atributo    o que se olha no número: final, dezena, posição na roda,
                dúzia, coluna, cor, paridade, soma dos dígitos, alto/baixo,
                metade da roda, distância ao zero
    comparador  como os dois se relacionam: igual, difere de k, perto de k
                (na roda, que é circular), soma dá k, um é múltiplo do outro

O cruzamento dá centenas de relações. Algumas são as que ele já conhece — a
família de finais aparece como "mesmo final". Outras nunca me ocorreriam:
"posição na roda difere de 9", "soma dos dígitos difere de 2". Essas são as
que ele está cobrando.

A CONTA DE HONESTIDADE
----------------------
Gerar centenas de perguntas custa: quanto mais se pergunta, mais fácil alguma
parecer boa por sorte. Por isso a correção é feita sobre o número REAL de
relações geradas, e não sobre as poucas que sobreviveram.

A RÉGUA, EM DUAS ETAPAS
-----------------------
Triagem analítica: para uma sequência embaralhada, a chance de a relação valer
entre dois giros quaisquer é calculável EXATAMENTE a partir da composição do
histórico — não precisa embaralhar. Isso permite varrer centenas de relações
em segundos.

Refino por embaralhamento: só nas que passam da triagem, porque é ali que a
ordem importa e o piso da régua precisa ser baixo.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Callable, Dict, List, Tuple

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}
VERMELHOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
DOMINIO = list(range(37))

EMBARALHAMENTOS_FINO = 6000
TRIAGEM_Z = 2.0          # quem se afasta menos que isso não vale o refino
MIN_GIROS = 250


def _duzia(n): return 0 if n == 0 else (n - 1) // 12 + 1
def _coluna(n): return 0 if n == 0 else (n - 1) % 3 + 1
def _soma_dig(n): return sum(int(c) for c in str(n))
def _dist_roda(a, b):
    d = abs(POS[a] - POS[b])
    return min(d, 37 - d)


# ────────────────────────────────────────────────────────── os atributos
ATRIBUTOS: Dict[str, Callable[[int], int]] = {
    "final": lambda n: n % 10,
    "dezena": lambda n: n // 10,
    "posição na roda": lambda n: POS[n],
    "dúzia": _duzia,
    "coluna": _coluna,
    "cor": lambda n: -1 if n == 0 else (1 if n in VERMELHOS else 0),
    "paridade": lambda n: -1 if n == 0 else n % 2,
    "soma dos dígitos": _soma_dig,
    "metade da mesa": lambda n: -1 if n == 0 else (0 if n <= 18 else 1),
    "metade da roda": lambda n: 0 if POS[n] < 18 else 1,
    "valor": lambda n: n,
}

# atributos onde "difere de k" faz sentido (são ordinais, não rótulos)
ORDINAIS = {"final", "dezena", "posição na roda", "soma dos dígitos", "valor"}
# atributos circulares: a distância dá a volta
CIRCULARES = {"posição na roda": 37, "final": 10}


def gerar() -> Dict[str, Tuple[Callable[[int, int], bool], str]]:
    """Monta o conjunto de relações a partir dos atributos e comparadores."""
    rel: Dict[str, Tuple[Callable[[int, int], bool], str]] = {}

    for nome, f in ATRIBUTOS.items():
        # igual
        rel[f"{nome}:igual"] = (
            (lambda f: lambda a, b: f(a) == f(b) and f(a) >= 0)(f),
            f"mesmo {nome}")
        # diferente
        rel[f"{nome}:difere"] = (
            (lambda f: lambda a, b: f(a) != f(b))(f),
            f"{nome} diferente")

        if nome in ORDINAIS:
            limite = 6 if nome != "posição na roda" else 12
            for k in range(1, limite + 1):
                if nome in CIRCULARES:
                    m = CIRCULARES[nome]
                    rel[f"{nome}:dist={k}"] = (
                        (lambda f, k, m: lambda a, b: min(
                            abs(f(a) - f(b)), m - abs(f(a) - f(b))) == k)(f, k, m),
                        f"{nome} a {k} de distância")
                    rel[f"{nome}:dist<={k}"] = (
                        (lambda f, k, m: lambda a, b: min(
                            abs(f(a) - f(b)), m - abs(f(a) - f(b))) <= k)(f, k, m),
                        f"{nome} até {k} de distância")
                else:
                    rel[f"{nome}:dif={k}"] = (
                        (lambda f, k: lambda a, b: abs(f(a) - f(b)) == k)(f, k),
                        f"{nome} difere de {k}")
            # soma constante
            for s in range(2, 13):
                rel[f"{nome}:soma={s}"] = (
                    (lambda f, s: lambda a, b: f(a) + f(b) == s)(f, s),
                    f"{nome}s somam {s}")

    # relações entre atributos diferentes: o final de um vira a dezena do outro
    rel["final vira dezena"] = (
        lambda a, b: a % 10 == b // 10 and b >= 10,
        "o final de um é a dezena do outro")
    rel["espelho"] = (
        lambda a, b: str(a).zfill(2) != str(b).zfill(2)
        and str(a).zfill(2) == str(b).zfill(2)[::-1],
        "os dígitos trocados")
    rel["dobro"] = (lambda a, b: a > 0 and (b == 2 * a or a == 2 * b),
                    "um é o dobro do outro")
    rel["dígito em comum"] = (lambda a, b: bool(set(str(a)) & set(str(b))),
                              "compartilham um algarismo")
    return rel


def _matriz(rel: Callable[[int, int], bool]):
    """A relação vira tabela 37x37: depois é só consultar."""
    return [[bool(rel(a, b)) for b in DOMINIO] for a in DOMINIO]


def _taxa(seq: List[int], M, janela: int) -> float:
    ok = t = 0
    for i in range(len(seq) - janela):
        linha = M[seq[i]]
        t += 1
        for j in range(i + 1, i + 1 + janela):
            if linha[seq[j]]:
                ok += 1
                break
    return ok / t if t else 0.0


def _acaso_analitico(cont: Counter, M, janela: int) -> float:
    """A chance da relação valer numa sequência embaralhada, calculada exata.

    Para um par de posições quaisquer da sequência embaralhada, a chance de a
    relação valer é a densidade dela sobre a composição do histórico. Não
    precisa embaralhar mil vezes para saber isso — e é o que torna possível
    varrer centenas de relações em segundos.
    """
    N = sum(cont.values())
    if N < 2:
        return 0.0
    p = 0.0
    for a, ca in cont.items():
        linha = M[a]
        for b, cb in cont.items():
            if linha[b]:
                p += ca * (cb - 1 if a == b else cb)
    p /= N * (N - 1)
    return 1.0 - (1.0 - p) ** janela


def varrer(historico: List, janelas=(1, 3), semente: int = 20260815,
           n_fino: int = EMBARALHAMENTOS_FINO) -> List[dict]:
    seq = []
    for x in (historico or []):
        try:
            v = int(str(x).strip())
        except (TypeError, ValueError):
            continue
        if 0 <= v <= 36:
            seq.append(v)
    if len(seq) < MIN_GIROS:
        return []

    cont = Counter(seq)
    relacoes = gerar()
    achados = []
    for chave, (fn, texto) in relacoes.items():
        try:
            M = _matriz(fn)
        except Exception:
            continue
        densidade = sum(sum(1 for v in linha if v) for linha in M) / (37 * 37)
        if densidade < 0.005 or densidade > 0.95:
            continue                     # relação quase nunca ou quase sempre
        for janela in janelas:
            real = _taxa(seq, M, janela)
            acaso = _acaso_analitico(cont, M, janela)
            if acaso <= 0 or acaso >= 1:
                continue
            n = len(seq) - janela
            desvio = (acaso * (1 - acaso) / n) ** 0.5
            z = (real - acaso) / desvio if desvio else 0.0
            achados.append({
                "chave": chave, "descricao": texto, "janela": janela,
                "taxa": round(real, 4), "acaso": round(acaso, 4),
                "razao": round(real / acaso, 3), "z": round(z, 2),
                "n": n, "p": None, "M": M, "fn": fn,
            })

    # refino só em quem se afastou: lá a ordem pode estar dizendo algo
    candidatos = [a for a in achados if abs(a["z"]) >= TRIAGEM_Z]
    rng = random.Random(semente)
    for a in candidatos:
        copia = list(seq)
        batidas = 0
        for _ in range(n_fino):
            rng.shuffle(copia)
            if _taxa(copia, a["M"], a["janela"]) >= a["taxa"]:
                batidas += 1
        a["p"] = (batidas + 1) / (n_fino + 1)

    for a in achados:
        a.pop("M", None)
        a.pop("fn", None)
    achados.sort(key=lambda a: (a["p"] if a["p"] is not None else 1.0, -abs(a["z"])))
    return achados


def resumo(achados: List[dict], corte: float = 0.05) -> str:
    if not achados:
        return "[Relações] histórico curto demais para a varredura"
    m = len(achados)
    com_p = [a for a in achados if a["p"] is not None]
    L = [f"[Relações] {m} relações montadas e testadas · "
         f"{len(com_p)} passaram da triagem e foram ao refino"]
    maior = 0.0
    sobrev = []
    for k, a in enumerate(com_p):
        aj = min(1.0, max(maior, a["p"] * m))     # corrige pelo TOTAL gerado
        maior = aj
        a["p_ajustado"] = round(aj, 4)
        if aj < corte:
            sobrev.append(a)
    for a in achados[:8]:
        p = a["p"]
        marca = "  <<<" if a.get("p_ajustado", 1) < corte else ""
        ptxt = f"p={p:.4f}" if p is not None else f"z={a['z']:+.1f}"
        L.append(f"   {a['descricao']:<34} janela {a['janela']}  "
                 f"{a['taxa']:.1%} vs {a['acaso']:.1%}  {a['razao']:.2f}x  "
                 f"{ptxt}{marca}")
    if sobrev:
        L.append(f"   {len(sobrev)} sobreviveram à correção por {m} perguntas")
    else:
        L.append(f"   nenhuma sobreviveu à correção por {m} perguntas")
    return "\n".join(L)
