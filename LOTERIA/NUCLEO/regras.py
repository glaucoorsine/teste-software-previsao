# -*- coding: utf-8 -*-
"""
REGRAS — o que cada loteria é, exatamente. A base factual de tudo o mais.

POR QUE ISTO VEM ANTES DE QUALQUER TEORIA
─────────────────────────────────────────
No cassino eu estimava o acaso: "cinco números em trinta e sete, mais ou menos
13,5% por giro". Aqui não é estimativa. O acaso de uma aposta de 7 dezenas na
Mega-Sena acertar a sena é um número exato, calculável, sem discussão:

    C(7,6) × C(53,0) / C(60,6) = 7 / 50.063.860

Isso muda o trabalho todo. A régua que eu levei meses construindo para o cassino
-- a linha de base do mesmo tamanho de aposta -- aqui é EXATA. Qualquer teoria
que ele traga pode ser medida contra o número certo, não contra a minha
estimativa. É a melhor posição em que este projeto já esteve para separar achado
de ruído.

E vale a inversa: como o acaso é exato, também é exato o que NÃO dá para fazer.
Um sorteio de bolas bem calibrado não tem vício análogo ao de uma roleta física
com desgaste. Onde há capacidade real e demonstrável -- e há -- é noutro lugar:

    FECHAMENTO   se destas 10 dezenas 5 saírem, quantas apostas eu preciso para
                 GARANTIR pelo menos uma quadra? Isso é matemática provável,
                 não previsão, e é verificável antes do sorteio.

    PARTILHA     o prêmio é dividido entre quem acertou. Escolher dezenas que
                 pouca gente escolhe não muda a chance de acertar, muda quanto
                 se recebe SE acertar. É medida sobre o comportamento dos
                 apostadores, não sobre as bolas.

Estas duas são reais e eu as construo com prazer. O que eu não vou fazer é
apresentar como previsão o que não for.

SOBRE ESTES NÚMEROS ESTAREM CERTOS
──────────────────────────────────
Escrevi as regras de memória e NÃO consigo conferir daqui -- este ambiente não
alcança o site da Caixa. Então cada jogo carrega `conferido=False` e o software
compara com a API dele assim que ela chegar (`conferir_com_api`). Regra errada
aqui contamina todo cálculo depois, silenciosamente, e é o tipo de erro que só
aparece quando o resultado não bate com o bilhete.
"""
from __future__ import annotations

from math import comb
from typing import Any, Dict, List, Optional, Sequence, Tuple


class Jogo:
    """Uma loteria: o universo de dezenas, quantas saem, e o que paga.

    `faixas` são as quantidades de acertos que pagam algum prêmio, da maior para
    a menor. É o que define "acertar" -- e sem isso "taxa de acerto" não
    significa nada, porque acertar 11 na Lotofácil paga e acertar 3 na Mega-Sena
    não paga.
    """

    def __init__(self, chave: str, nome: str, universo: int, sorteadas: int,
                 minimo: int, maximo: int, faixas: Sequence[int],
                 primeiro_numero: int = 1, extras: Optional[dict] = None,
                 nota: str = ""):
        self.chave = chave
        self.nome = nome
        self.universo = universo          # quantas dezenas existem
        self.sorteadas = sorteadas        # quantas são sorteadas
        self.minimo = minimo              # menor aposta permitida
        self.maximo = maximo              # maior aposta permitida
        self.faixas = tuple(sorted(faixas, reverse=True))
        self.primeiro_numero = primeiro_numero   # a Lotomania começa em 0
        self.extras = dict(extras or {})
        self.nota = nota
        self.conferido = False            # ver o cabeçalho: nada aqui foi
                                          # conferido contra a fonte oficial

    # ── o universo, como lista ────────────────────────────────────────────
    def dezenas(self) -> List[int]:
        ini = self.primeiro_numero
        return list(range(ini, ini + self.universo))

    def valida_aposta(self, nums: Sequence[int]) -> Tuple[bool, str]:
        """A aposta é legal? Devolve o motivo quando não é.

        Checar isto cedo evita a pior classe de erro deste software: calcular
        probabilidade, montar estratégia e mostrar na tela uma aposta que a
        Caixa não aceita.
        """
        n = list(nums or [])
        if len(set(n)) != len(n):
            return False, "há dezena repetida na aposta"
        if not (self.minimo <= len(n) <= self.maximo):
            return False, (f"{self.nome} aceita de {self.minimo} a "
                           f"{self.maximo} dezenas; esta tem {len(n)}")
        vale = set(self.dezenas())
        fora = [x for x in n if x not in vale]
        if fora:
            return False, (f"fora do universo de {self.nome} "
                           f"({self.primeiro_numero} a "
                           f"{self.primeiro_numero + self.universo - 1}): {fora}")
        return True, ""

    # ── o acaso, exato ────────────────────────────────────────────────────
    def combinacoes(self, k: Optional[int] = None) -> int:
        """Quantas apostas distintas de `k` dezenas existem."""
        return comb(self.universo, k or self.minimo)

    def p_exato(self, k: int, acertos: int) -> float:
        """Chance de uma aposta de `k` dezenas fazer EXATAMENTE `acertos`.

        É a hipergeométrica, e é exata -- não é simulação nem estimativa:

            C(sorteadas, acertos) × C(universo-sorteadas, k-acertos)
            ────────────────────────────────────────────────────────
                              C(universo, k)

        Lendo em português: das `sorteadas` bolas premiadas eu peguei `acertos`,
        e o resto da minha aposta veio das que não saíram.
        """
        if k < 0 or acertos < 0 or acertos > k or acertos > self.sorteadas:
            return 0.0
        resto = self.universo - self.sorteadas
        if k - acertos > resto:
            return 0.0
        return (comb(self.sorteadas, acertos) * comb(resto, k - acertos)
                / comb(self.universo, k))

    def p_faixa(self, k: int, faixa: int) -> float:
        """Chance de levar o prêmio de `faixa` acertos com uma aposta de `k`.

        ATENÇÃO A UMA ARMADILHA QUE PARECE DETALHE E NÃO É: aqui é EXATAMENTE
        `faixa` acertos, não "faixa ou mais". Quem faz 6 na Mega-Sena não leva
        também o prêmio de 5 -- leva o de 6. Somar as faixas para cima
        multiplicaria o valor esperado por um prêmio que ninguém recebe.
        """
        return self.p_exato(k, faixa)

    def p_algum_premio(self, k: int) -> float:
        """Chance de a aposta pagar ALGUMA coisa.

        Aqui sim as faixas se somam, porque são desfechos que se excluem: ou fez
        4, ou fez 5, ou fez 6 -- nunca duas ao mesmo tempo.
        """
        return sum(self.p_exato(k, f) for f in self.faixas)

    def acertos_esperados(self, k: int) -> float:
        """Quantos acertos, em média, uma aposta de `k` dezenas faz.

        `k × sorteadas / universo`. É a régua mais simples e a mais usada para
        dar errado: quem aposta 15 dezenas na Lotofácil acerta 9 em média, e
        "acertei 9!" não é achado nenhum -- é o esperado. Toda teoria que ele
        trouxer vai ser comparada com este número, não com zero.
        """
        return k * self.sorteadas / self.universo

    def resumo(self) -> List[str]:
        L = [f"{self.nome}: {self.universo} dezenas, saem {self.sorteadas}, "
             f"aposta de {self.minimo} a {self.maximo}"]
        for k in (self.minimo, min(self.maximo, self.minimo + 2)):
            if k > self.maximo:
                continue
            for f in self.faixas:
                p = self.p_faixa(k, f)
                if p > 0:
                    L.append(f"   aposta de {k}: {f} acertos = 1 em "
                             f"{1/p:,.0f}".replace(",", "."))
            break
        L.append(f"   acertos médios numa aposta mínima: "
                 f"{self.acertos_esperados(self.minimo):.2f}")
        return L


# ═══════════════════════════════════════════════════════════ as loterias
#
# NENHUM DESTES NÚMEROS FOI CONFERIDO CONTRA A FONTE OFICIAL, e eu não consigo
# conferir daqui. Estão escritos de memória e servem para o software começar a
# existir; `conferir_com_api()` compara cada um com o que a API dele devolver, e
# até lá o software diz que não conferiu. Regra errada aqui não dá erro: dá
# número plausível e falso, que é pior.
JOGOS: Dict[str, Jogo] = {
    "mega_sena": Jogo(
        "mega_sena", "Mega-Sena", universo=60, sorteadas=6,
        minimo=6, maximo=20, faixas=(6, 5, 4),
        nota="sena, quina e quadra"),
    "quina": Jogo(
        "quina", "Quina", universo=80, sorteadas=5,
        minimo=5, maximo=15, faixas=(5, 4, 3, 2),
        nota="quina, quadra, terno e duque"),
    "lotofacil": Jogo(
        "lotofacil", "Lotofácil", universo=25, sorteadas=15,
        minimo=15, maximo=20, faixas=(15, 14, 13, 12, 11),
        nota="paga a partir de 11 acertos — a de faixa mais generosa"),
    "lotomania": Jogo(
        "lotomania", "Lotomania", universo=100, sorteadas=20,
        minimo=50, maximo=50, faixas=(20, 19, 18, 17, 16, 15, 0),
        primeiro_numero=0,
        nota="começa no 0, e ZERO acerto também paga — o único caso assim"),
    "dupla_sena": Jogo(
        "dupla_sena", "Dupla Sena", universo=50, sorteadas=6,
        minimo=6, maximo=15, faixas=(6, 5, 4, 3),
        extras={"sorteios_por_concurso": 2},
        nota="dois sorteios no mesmo concurso; a aposta vale para os dois"),
    "timemania": Jogo(
        "timemania", "Timemania", universo=80, sorteadas=7,
        minimo=10, maximo=10, faixas=(7, 6, 5, 4, 3),
        extras={"time_do_coracao": True},
        nota="aposta fixa de 10 dezenas, mais o Time do Coração"),
    "dia_de_sorte": Jogo(
        "dia_de_sorte", "Dia de Sorte", universo=31, sorteadas=7,
        minimo=7, maximo=15, faixas=(7, 6, 5, 4),
        extras={"mes_da_sorte": True},
        nota="dezenas de 1 a 31, mais o Mês da Sorte"),
    "mais_milionaria": Jogo(
        "mais_milionaria", "+Milionária", universo=50, sorteadas=6,
        minimo=6, maximo=12, faixas=(6, 5, 4, 3, 2),
        extras={"trevos": 6, "trevos_sorteados": 2,
                "trevos_min": 2, "trevos_max": 6},
        nota="além das dezenas, 2 trevos de 6 — as faixas cruzam os dois"),
}

# A Super Sete e a Loteca não cabem neste molde: a Super Sete é sete colunas de
# 0 a 9 (não é "escolher k de n"), e a Loteca é palpite em jogos de futebol.
# Forçá-las aqui daria probabilidade errada com cara de certa. Entram quando ele
# disser que quer, com o molde delas.
FORA_DO_MOLDE = {
    "super_sete": "sete colunas de 0 a 9 — não é escolha de k dezenas em n",
    "loteca": "palpite em 14 jogos de futebol — não é sorteio de bolas",
}


def jogo(chave: str) -> Optional[Jogo]:
    return JOGOS.get(str(chave).strip().lower())


def conferir_com_api(chave: str, amostra: Sequence[Sequence[int]]) -> Dict[str, Any]:
    """As regras que escrevi batem com os resultados reais da API dele?

    Confere o que dá para conferir sozinho, a partir dos sorteios: quantas
    dezenas saem por concurso, e se todas caem dentro do universo declarado.
    Não confere as faixas de prêmio -- isso vem no retorno da API, e entra
    quando ele mandar o formato.

    Existe porque eu escrevi as regras de memória, sem poder checar. Um universo
    errado não gera erro nenhum: gera probabilidade plausível e falsa. Prefiro
    que o software desconfie de mim.
    """
    j = jogo(chave)
    if not j:
        return {"ok": False, "nota": f"jogo desconhecido: {chave}"}
    conc = [list(c) for c in (amostra or []) if c]
    if not conc:
        return {"ok": False, "nota": "nenhum concurso para conferir"}
    problemas: List[str] = []
    tamanhos = {len(c) for c in conc}
    if tamanhos != {j.sorteadas}:
        problemas.append(f"declarei {j.sorteadas} dezenas sorteadas, mas os "
                         f"concursos trazem {sorted(tamanhos)}")
    vale = set(j.dezenas())
    fora = sorted({x for c in conc for x in c if x not in vale})
    if fora:
        problemas.append(f"dezenas fora do universo {j.primeiro_numero}–"
                         f"{j.primeiro_numero + j.universo - 1}: {fora[:8]}")
    maior = max((max(c) for c in conc if c), default=0)
    menor = min((min(c) for c in conc if c), default=0)
    if not problemas:
        j.conferido = True
    return {"ok": not problemas, "problemas": problemas,
            "n_concursos": len(conc), "menor_visto": menor, "maior_visto": maior,
            "nota": ("regras confirmadas contra os sorteios reais"
                     if not problemas else
                     "as regras que escrevi NÃO batem com os dados — corrigir "
                     "antes de calcular qualquer coisa")}


def conferidos() -> Dict[str, bool]:
    return {k: v.conferido for k, v in JOGOS.items()}
