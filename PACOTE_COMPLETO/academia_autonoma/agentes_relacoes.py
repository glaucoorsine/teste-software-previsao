# -*- coding: utf-8 -*-
"""
A14 — o agente que percebe RELAÇÕES, que é o jeito como ele percebe.

POR QUE ESTE AGENTE EXISTE
--------------------------
Ele perguntou por que as IAs não descobrem o que ele descobre, e depois
insistiu: "mas elas têm a capacidade de ter essas percepções". Estava certo. O
que faltava não era capacidade, era eu ter construído.

O jeito dele de perceber não é contar frequência — é reparar que dois números
que saíram seguidos têm ALGUMA COISA a ver, e dar nome àquilo. "Veio 16 e
logo depois 14." "Veio 20 e depois o 2." O que ele enxerga é a relação, e cada
teoria dele é uma relação nomeada.

Os outros doze agentes olham uma lente cada um: frequência, gap, subsequência.
Este olha o catálogo de relações inteiro e pergunta, de cada uma: isso acontece
mais do que aconteceria por acaso?

O CATÁLOGO
----------
Cada relação é uma pergunta que alguém poderia fazer olhando a mesa:

    mesmo final          16 → 26      o final se repete
    final da família     20 → 2       as famílias que ele ensinou
    vizinho na roda      21 → 25      perto no prato, não na mesa
    mesma dúzia          14 → 17      1-12, 13-24, 25-36
    mesma coluna         14 → 17      as três colunas da mesa
    mesma cor            16 → 14      vermelho/preto
    espelho              12 → 21      os dígitos trocados
    dígito em comum      16 → 14      compartilham um algarismo
    soma dos dígitos     19 → 28      1+9 = 2+8
    diferença fixa       14 → 16      distância constante na mesa
    metade / dobro       12 → 24      um é o dobro do outro
    mesma paridade       14 → 16      par com par, ímpar com ímpar

A RÉGUA
-------
Embaralhar o próprio histórico. Se a relação aparece tanto no histórico real
quanto nos embaralhados, ela é uma propriedade da composição dos números e não
da ordem em que saíram — e ordem é o que interessa para prever.

Nada aqui vira teoria sozinho: o que se destaca vira PROPOSTA, e proposta ainda
enfrenta a sombra ao vivo como qualquer outra.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Callable, Dict, List, Tuple

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}
VERMELHOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
FAMILIAS = ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9))

# DUAS ETAPAS, e não uma.
#
# Com N embaralhamentos o menor p possível é 1/(N+1). Com 400, isso é 0,0025 —
# e corrigindo por 30 perguntas vira 0,075. O piso da própria régua impedia
# QUALQUER coisa de passar: no teste, uma regra plantada a 1,77x com p no chão
# foi reprovada. A régua estava barrando o que ela deveria medir.
#
# Então: uma triagem barata em todas as perguntas, e o refino caro só nas
# poucas que sobrevivem — onde o piso precisa mesmo ser baixo.
EMBARALHAMENTOS = 400        # triagem
EMBARALHAMENTOS_FINO = 6000  # refino: piso 1/6001, sobra folga para 30 testes
TRIAGEM_CORTE = 0.10         # quem passa daqui vai para o refino
MIN_GIROS = 200


def _dist_roda(a: int, b: int) -> int:
    if a not in POS or b not in POS:
        return 99
    d = abs(POS[a] - POS[b])
    return min(d, len(RODA) - d)


def _duzia(n: int) -> int:
    return 0 if n == 0 else (n - 1) // 12 + 1


def _coluna(n: int) -> int:
    return 0 if n == 0 else (n - 1) % 3 + 1


def _familia_do_final(f: int) -> set:
    s = set()
    for g in FAMILIAS:
        if f in g:
            s |= set(g)
    return s or {f}


def _espelho(a: int, b: int) -> bool:
    """12 e 21, 13 e 31. Só conta quando os dígitos são de fato trocados."""
    sa, sb = str(a).zfill(2), str(b).zfill(2)
    return sa != sb and sa == sb[::-1]


# ─────────────────────────────────────────────────────── o catálogo
RELACOES: Dict[str, Tuple[Callable[[int, int], bool], str]] = {
    "mesmo_final":      (lambda a, b: a % 10 == b % 10,
                         "o final se repete"),
    "familia_final":    (lambda a, b: b % 10 in _familia_do_final(a % 10),
                         "final da mesma família"),
    "vizinho_roda_2":   (lambda a, b: _dist_roda(a, b) <= 2,
                         "até 2 casas na roda"),
    "vizinho_roda_4":   (lambda a, b: _dist_roda(a, b) <= 4,
                         "até 4 casas na roda"),
    "mesma_duzia":      (lambda a, b: _duzia(a) == _duzia(b) != 0,
                         "mesma dúzia"),
    "mesma_coluna":     (lambda a, b: _coluna(a) == _coluna(b) != 0,
                         "mesma coluna"),
    "mesma_cor":        (lambda a, b: a and b and (a in VERMELHOS) == (b in VERMELHOS),
                         "mesma cor"),
    "espelho":          (_espelho, "os dígitos trocados"),
    "digito_comum":     (lambda a, b: bool(set(str(a)) & set(str(b))),
                         "compartilham um algarismo"),
    "soma_digitos":     (lambda a, b: sum(map(int, str(a))) == sum(map(int, str(b))),
                         "mesma soma de dígitos"),
    "dobro_metade":     (lambda a, b: a and b and (a == 2 * b or b == 2 * a),
                         "um é o dobro do outro"),
    "mesma_paridade":   (lambda a, b: a and b and a % 2 == b % 2,
                         "mesma paridade"),
    "diferenca_1":      (lambda a, b: abs(a - b) == 1, "vizinhos na mesa"),
    "diferenca_2":      (lambda a, b: abs(a - b) == 2, "distância 2 na mesa"),
    "diferenca_3":      (lambda a, b: abs(a - b) == 3, "distância 3 na mesa"),
}


def _taxa(seq: List[int], rel: Callable[[int, int], bool], janela: int) -> float:
    """Com que frequência a relação aparece dentro de `janela` giros."""
    ok = t = 0
    for i in range(len(seq) - janela):
        a = seq[i]
        t += 1
        if any(rel(a, b) for b in seq[i + 1:i + 1 + janela]):
            ok += 1
    return ok / t if t else 0.0


def varrer(historico: List, janelas=(1, 3), n_emb: int = EMBARALHAMENTOS,
           semente: int = 20260815) -> List[dict]:
    """Passa o catálogo inteiro no histórico e devolve o que se destaca.

    A ordem de `historico` não importa para o resultado — o que importa é que
    ela seja a ordem real, porque é contra ela que os embaralhamentos comparam.
    """
    seq = []
    for x in (historico or []):
        try:
            seq.append(int(str(x).strip()))
        except (TypeError, ValueError):
            pass
    if len(seq) < MIN_GIROS:
        return []

    def medir(rel, janela, real, n, semente_local):
        rng = random.Random(semente_local)
        copia = list(seq)
        batidas = 0
        soma = 0.0
        for _ in range(n):
            rng.shuffle(copia)
            v = _taxa(copia, rel, janela)
            soma += v
            if v >= real:
                batidas += 1
        return soma / n, (batidas + 1) / (n + 1)

    achados = []
    for nome, (rel, texto) in RELACOES.items():
        for janela in janelas:
            real = _taxa(seq, rel, janela)
            if real <= 0:
                continue
            acaso, p = medir(rel, janela, real, n_emb, semente)
            achados.append({
                "relacao": nome, "descricao": texto, "janela": janela,
                "taxa": round(real, 4), "acaso": round(acaso, 4),
                "razao": round(real / acaso, 3) if acaso else 0.0,
                "p": round(p, 4), "n": len(seq) - janela,
                "embaralhamentos": n_emb,
            })

    # refino só em quem passou da triagem: é lá que o piso da régua atrapalha
    for a in achados:
        if a["p"] > TRIAGEM_CORTE:
            continue
        rel = RELACOES[a["relacao"]][0]
        acaso, p = medir(rel, a["janela"], a["taxa"],
                         EMBARALHAMENTOS_FINO, semente + 1)
        a["acaso"] = round(acaso, 4)
        a["razao"] = round(a["taxa"] / acaso, 3) if acaso else 0.0
        a["p"] = round(p, 5)
        a["embaralhamentos"] = EMBARALHAMENTOS_FINO

    achados.sort(key=lambda a: a["p"])
    return achados


def resumo(achados: List[dict], corte: float = 0.05) -> str:
    if not achados:
        return "[Relações] histórico curto demais para varrer o catálogo"
    L = [f"[Relações] {len(achados)} perguntas feitas ao histórico"]
    m = len(achados)
    maior = 0.0
    destaques = []
    for k, a in enumerate(achados):
        aj = min(1.0, max(maior, a["p"] * (m - k)))
        maior = aj
        a["p_ajustado"] = round(aj, 4)
        if aj < corte:
            destaques.append(a)
    for a in achados[:6]:
        marca = "  <<<" if a.get("p_ajustado", 1) < corte else ""
        L.append(f"   {a['descricao']:<28} janela {a['janela']}  "
                 f"{a['taxa']:.1%} vs {a['acaso']:.1%}  "
                 f"{a['razao']:.2f}x  p={a['p']:.3f}{marca}")
    if destaques:
        L.append(f"   {len(destaques)} sobreviveram à correção por {m} perguntas")
    else:
        L.append("   nenhuma sobreviveu à correção — nada aqui se distingue do acaso")
    return "\n".join(L)
