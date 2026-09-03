# -*- coding: utf-8 -*-
"""
BASE — os dados, o acaso exato, e o gerador de histórias falsas.

POR QUE O GERADOR DE HISTÓRIAS FALSAS VEM JUNTO COM OS DADOS REAIS
──────────────────────────────────────────────────────────────────
Este é o ponto inteiro do estudo, e ele fica aqui embaixo em vinte linhas.

Se eu procurar padrão em 3.246 concursos com cem testes diferentes, eu VOU
achar alguma coisa com z alto. Não porque exista, mas porque cem testes num
ruído produzem, por construção, alguns extremos. É assim que quase toda teoria
de loteria nasce: alguém procurou muito e encontrou o inevitável.

A defesa não é Bonferroni. Bonferroni corrige o número de testes que eu declaro
ter feito, e ninguém declara honestamente quantos olhou. A defesa é rodar a
bateria INTEIRA, exatamente igual, sobre histórias que eu SEI que são acaso
puro — sorteios uniformes gerados aqui — e guardar o maior |z| que a bateria
produz em cada uma delas. Isso me dá a distribuição do "melhor achado possível
num mundo sem padrão nenhum".

Depois disso a pergunta deixa de ser "o z de 2,4 é grande?" e passa a ser:
"num mundo comprovadamente sem padrão, com que frequência esta mesma bateria
produz um z de 2,4?". Se a resposta for "em 60% das histórias falsas", o achado
morre — e morre com número, não com opinião.

O ACASO EXATO DA LOTOFÁCIL
──────────────────────────
Saem 15 de 25. Então a interseção entre dois concursos independentes segue
hipergeométrica H(N=25, K=15, n=15): média 9, e P(9) ≈ 23,4%. E repare na
coincidência que organiza o estudo todo: uma APOSTA de 15 dezenas é
matematicamente a mesma coisa que um concurso anterior. Apostar o resultado
passado dá exatamente a linha de base — 9 acertos em média. Qualquer teoria só
existe se bater isso, e "bater isso" é um número, não uma impressão.
"""
from __future__ import annotations

import json
from math import comb
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
RESULTADOS = RAIZ / "resultados"
FIGURAS = RAIZ / "figuras"

UNIVERSO = 25
SORTEADAS = 15
AUSENTES = UNIVERSO - SORTEADAS          # 10 — o complemento, tema de uma das teorias
DEZENAS = np.arange(1, UNIVERSO + 1)

PRIMOS = frozenset({2, 3, 5, 7, 11, 13, 17, 19, 23})
FIBONACCI = frozenset({1, 2, 3, 5, 8, 13, 21})

# O volante da Lotofácil é uma grade 5x5: 1..5 na primeira linha, 6..10 na
# segunda, e assim por diante. Isso não é enfeite: é a geometria física do
# cartão, e várias teorias populares ("moldura", "miolo", "linhas") só fazem
# sentido nela.
def linha(n: int) -> int:
    return (n - 1) // 5

def coluna(n: int) -> int:
    return (n - 1) % 5

MOLDURA = frozenset(n for n in range(1, 26) if linha(n) in (0, 4) or coluna(n) in (0, 4))
MIOLO = frozenset(range(1, 26)) - MOLDURA          # 7, 8, 9, 12, 13, 14, 17, 18, 19


# ── o acaso, exato ────────────────────────────────────────────────────────
def pmf_intersecao() -> np.ndarray:
    """P(|A ∩ B| = k) para dois conjuntos independentes de 15 dezenas em 25.

    Índice = k, de 0 a 15. Fora de 5..15 é zero por pura contagem: com 15
    escolhidas de 25, sobram só 10 fora, então duas escolhas quaisquer
    obrigatoriamente compartilham ao menos 5. Isso já diz uma coisa que
    surpreende quem olha a Lotofácil pela primeira vez: dois concursos
    seguidos SEMPRE repetem pelo menos 5 dezenas. Não é padrão, é aritmética.
    """
    p = np.zeros(SORTEADAS + 1)
    tot = comb(UNIVERSO, SORTEADAS)
    for k in range(SORTEADAS + 1):
        resto = UNIVERSO - SORTEADAS
        if k > SORTEADAS or (SORTEADAS - k) > resto:
            continue
        p[k] = comb(SORTEADAS, k) * comb(resto, SORTEADAS - k) / tot
    return p


PMF_INTER = pmf_intersecao()
MEDIA_INTER = float(np.dot(np.arange(SORTEADAS + 1), PMF_INTER))          # 9.0 exato
VAR_INTER = float(np.dot((np.arange(SORTEADAS + 1) - MEDIA_INTER) ** 2, PMF_INTER))
DP_INTER = VAR_INTER ** 0.5


# ── carregar ──────────────────────────────────────────────────────────────
class Historico:
    """Os concursos, em três representações — e as três são usadas.

    `matriz`   3246x25 de 0/1: rápido para conta vetorial.
    `conjuntos` lista de frozenset: legível para as teorias estruturais.
    `ordem`    3246x15 com as dezenas NA ORDEM EM QUE SAÍRAM DO GLOBO.

    A terceira é a que quase nenhum estudo usa, e é a única que pode carregar
    viés físico da máquina. Um conjunto {1,2,3} apaga a informação de qual bola
    saiu primeiro; se existisse desgaste, tendência de posição, ou qualquer
    coisa mecânica, seria AQUI que apareceria — e some quando se ordena.
    """

    def __init__(self, concursos: Sequence[int], ordem: np.ndarray):
        self.concursos = np.asarray(concursos, dtype=int)
        self.ordem = np.asarray(ordem, dtype=np.int8)         # (T, 15)
        self.T = len(self.concursos)
        self.matriz = np.zeros((self.T, UNIVERSO), dtype=np.int8)
        for i in range(self.T):
            self.matriz[i, self.ordem[i] - 1] = 1
        self.conjuntos = [frozenset(int(x) for x in linha_) for linha_ in self.ordem]
        self.ordenados = np.sort(self.ordem, axis=1)

    def fatia(self, ini: int, fim: int) -> "Historico":
        """Recorte por índice (não por número de concurso). `fim` exclusivo."""
        return Historico(self.concursos[ini:fim], self.ordem[ini:fim])

    def __len__(self) -> int:
        return self.T


def carregar(caminho: Path | None = None) -> Historico:
    caminho = caminho or (DADOS / "lotofacil_bruto.json")
    cru = json.loads(caminho.read_text(encoding="utf-8"))
    chaves = sorted(int(k) for k in cru)
    ordem = np.array([[int(x) for x in cru[str(k)]] for k in chaves], dtype=np.int8)
    return Historico(chaves, ordem)


def conferir_integridade(h: Historico) -> Dict[str, object]:
    """O que eu confiro ANTES de calcular qualquer coisa.

    Regra que veio do outro software e que já me salvou: base errada não dá
    erro, dá número plausível e falso. Aqui a checagem mais importante é a
    última — se a "ordem de sorteio" vier ordenada, ela é ficção do coletor, e
    toda a bateria posicional deste estudo teria de ser jogada fora.
    """
    faltando = [int(c) for c in range(int(h.concursos[0]), int(h.concursos[-1]) + 1)
                if c not in set(h.concursos.tolist())]
    tamanhos = sorted({int(x) for x in h.matriz.sum(axis=1)})
    fora = sorted({int(x) for x in h.ordem.ravel() if not (1 <= x <= UNIVERSO)})
    repetidas = int(sum(1 for i in range(h.T) if len(h.conjuntos[i]) != SORTEADAS))
    ja_ordenados = int(sum(1 for i in range(h.T)
                           if list(h.ordem[i]) == sorted(h.ordem[i])))
    return {
        "n_concursos": h.T,
        "primeiro": int(h.concursos[0]),
        "ultimo": int(h.concursos[-1]),
        "concursos_faltando": faltando,
        "tamanhos_distintos": tamanhos,
        "dezenas_fora_do_universo": fora,
        "concursos_com_dezena_repetida": repetidas,
        "concursos_ja_ordenados": ja_ordenados,
        "esperado_ordenados_por_acaso": h.T / 1307674368000.0,   # T / 15!
        "ordem_parece_real": ja_ordenados <= 1,
    }


# ── histórias falsas: o controle negativo ────────────────────────────────
def historia_falsa(T: int, rng: np.random.Generator) -> Historico:
    """Um histórico de T concursos gerado por acaso puro e uniforme.

    É o mundo onde a resposta certa é "não há padrão". Tudo que a bateria
    encontrar aqui é falso positivo por definição — e é exatamente essa
    quantidade que eu preciso medir para saber se o achado no mundo real vale
    alguma coisa.
    """
    ordem = np.empty((T, SORTEADAS), dtype=np.int8)
    for i in range(T):
        ordem[i] = rng.permutation(UNIVERSO)[:SORTEADAS] + 1
    return Historico(np.arange(1, T + 1), ordem)


def z_binomial(acertos: int, n: int, p0: float) -> float:
    if n <= 0 or p0 <= 0 or p0 >= 1:
        return 0.0
    return (acertos - n * p0) / ((n * p0 * (1 - p0)) ** 0.5)


def z_media(media_obs: float, media0: float, dp0: float, n: int) -> float:
    if n <= 0 or dp0 <= 0:
        return 0.0
    return (media_obs - media0) * (n ** 0.5) / dp0
