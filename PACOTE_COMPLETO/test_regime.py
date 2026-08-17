# -*- coding: utf-8 -*-
"""
TESTE DO REGIME DE MULTIPLICADOR — as observações dele contra mesas onde a
observação FOI PLANTADA e contra mesas onde ela NÃO EXISTE.

POR QUE ESTE CONTROLE, E NÃO SÓ "rodou sem erro"
────────────────────────────────────────────────
Uma medida que confirma a teoria dele numa mesa honesta não está medindo a
teoria — está medindo o meu viés. Foi exatamente assim que `situacao.py` me
enganou: dava 2,70x em dado sorteado ao acaso, porque eu escolhia os números na
mesma amostra em que media.

Então cada uma das observações dele é testada DUAS vezes:

    plantada  → a medida TEM de encontrar (senão a medida é cega)
    honesta   → a medida NÃO PODE encontrar (senão a medida é crédula)

Só passa quem acerta os dois lados. Uma medida que só sabe dizer "sim" não serve
para decidir bom momento, porque diria sim sempre.

RECENTE-PRIMEIRO
────────────────
Como em todo o software, índice 0 é o giro mais NOVO. Os geradores aqui montam a
lista em ordem cronológica e invertem no fim -- é onde eu erraria sem pensar, e
o teste do ciclo depende disso estar certo.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import regime_multiplicador as RM          # noqa: E402
from NUCLEO.situacao import _mult_do_giro as PAGOU     # noqa: E402

FALHAS = []


def checar(ok: bool, titulo: str, detalhe: str = "") -> bool:
    print(f"  {'ok  ' if ok else 'FALHA'} {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(titulo)
    return ok


# ───────────────────────────────────────────────── gerador de mesa sintética
def linha(saiu: str, premio: float = 0.0) -> dict:
    """Um giro no formato real: o prêmio só existe se o número anunciado saiu."""
    tags = [{"fire_nums": [{"n": saiu, "x": premio}] if premio > 0 else []}]
    return {"n": saiu, "tags": tags}


def mesa(seq) -> list:
    """`seq` em ordem cronológica → lista recente-primeiro, como o software usa."""
    fora = [linha(str(random.randint(0, 36)), premio) for premio in seq]
    fora.reverse()
    return fora


# ══════════════════════════════════════════════════════════ 1. densidade
def teste_densidade():
    print("\n[1] DENSIDADE — a conta dele: 'x em 500'")
    # 60 prêmios em 500 giros, colocados de forma conhecida
    seq = [0.0] * 500
    for i in range(60):
        seq[i * 8] = 100.0
    d = RM.densidade(mesa(seq), PAGOU)
    checar(d["quantos"] == 60 and d["completa"],
           "conta exata numa janela cheia de 500",
           f"{d['quantos']} prêmios, completa={d['completa']}")
    checar(d["acima_do_limiar"] is True,
           "60 é reconhecido como acima do ponto dele (45)")

    # 30 em 500 -> abaixo
    seq2 = [0.0] * 500
    for i in range(30):
        seq2[i * 16] = 100.0
    d2 = RM.densidade(mesa(seq2), PAGOU)
    checar(d2["acima_do_limiar"] is False,
           "30 é reconhecido como abaixo do ponto dele",
           f"quantos={d2['quantos']}")

    # janela curta: precisa projetar E DIZER que projetou
    seq3 = [0.0] * 100
    for i in range(12):
        seq3[i * 8] = 100.0
    d3 = RM.densidade(mesa(seq3), PAGOU)
    checar(d3["completa"] is False and abs(d3["projetado_500"] - 60.0) < 1.0,
           "com 100 giros projeta para 500 e avisa que projetou",
           f"12/100 → {d3['projetado_500']}/500")


# ══════════════════════════════════════════════════════════ 2. o limiar 45
def bloco(n_premios: int, tamanho: int = 500, rnd=None) -> list:
    """Um bloco cronológico com exatamente `n_premios` prêmios espalhados."""
    rnd = rnd or random
    s = [0.0] * tamanho
    for p in rnd.sample(range(tamanho), n_premios):
        s[p] = 100.0
    return s


def crono_com_limiar(n_blocos: int, forca: float, rnd,
                     terminar_alto: bool = False) -> list:
    """Blocos de 500 em que passar de 45 faz o bloco SEGUINTE pagar mais.

    A PRIMEIRA VERSÃO DESTE PLANTIO TAMBÉM ESTAVA ERRADA
    ────────────────────────────────────────────────────
    Eu havia escrito pares fixos -- (80→150), (20→25), (90→160) -- e chamado
    aquilo de limiar plantado. Não é: naquela sequência um bloco de 150 é seguido
    por um de 20, então "acima de 45" era seguido às vezes por 150 e às vezes por
    20. Isso planta ALTERNÂNCIA, e a taxa média depois de blocos acima só parecia
    maior por causa de quais pares caíram de que lado. A medida via razão 1,74x
    com t=1,1 -- ou seja, ruído com cara de achado, e era o plantio que estava
    torto, não a medida.

    A afirmação dele é: contagem alta agora → mais fácil DEPOIS. Planta-se em
    cadeia: o estado do bloco seguinte segue o do anterior com probabilidade
    `forca`. Com 0,85 a mesa tem o limiar dele; com 0,5 a contagem de um bloco não
    diz nada sobre o seguinte e a mesa é honesta.
    """
    saida: list = []
    alto = rnd.random() < 0.5
    for i in range(n_blocos):
        # o ÚLTIMO bloco é forçado alto quando o cenário precisa de densidade
        # acima de 45 agora. Forçar é honesto e é o oposto de pescar semente: o
        # cenário fica declarado no código em vez de depender de qual sorteio
        # caiu bem.
        if terminar_alto and i == n_blocos - 1:
            alto = True
        n = rnd.randint(95, 125) if alto else rnd.randint(18, 40)
        saida += bloco(n, rnd=rnd)
        # o estado do PRÓXIMO bloco depende do que este acabou de ser
        alto = alto if rnd.random() < forca else (not alto)
    return saida


def teste_limiar():
    print("\n[2] LIMIAR 45 — plantado deve confirmar, honesto não pode")
    rnd = random.Random(11)

    # PLANTADO: bloco acima de 45 é SEGUIDO por bloco mais generoso.
    r = RM.limiar_confirmado(mesa(crono_com_limiar(24, 0.85, rnd)), PAGOU)
    checar(r.get("mediu") and r.get("confirma") is True,
           "encontra o limiar quando ele está plantado",
           f"{r.get('taxa_depois_de_acima')} vs {r.get('taxa_depois_de_abaixo')}"
           f" = {r.get('razao')}x (n={r.get('n_acima')}/{r.get('n_abaixo')} "
           f"blocos, t={r.get('t')})")

    # HONESTO: mesmo gerador, força 0.5 — um bloco não diz nada do seguinte.
    h = RM.limiar_confirmado(mesa(crono_com_limiar(24, 0.5, rnd)), PAGOU)
    checar(h.get("mediu") and h.get("confirma") is False,
           "NÃO encontra limiar em mesa honesta (estados sorteados)",
           f"{h.get('taxa_depois_de_acima')} vs {h.get('taxa_depois_de_abaixo')}"
           f" = {h.get('razao')}x, t={h.get('t')}")

    # HONESTO 2: taxa realmente constante de 10%, cruzando 45 só por sorteio.
    plano = []
    for _ in range(16):
        plano += bloco(rnd.randint(38, 62), rnd=rnd)
    h2 = RM.limiar_confirmado(mesa(plano), PAGOU)
    checar(h2.get("mediu") and h2.get("confirma") is False,
           "NÃO encontra limiar em mesa de taxa constante",
           f"{h2.get('razao')}x, t={h2.get('t')}")

    # pouco dado: tem de calar, não de adivinhar
    curto = RM.limiar_confirmado(mesa(bloco(50) + bloco(50)), PAGOU)
    checar(curto.get("mediu") is False and "blocos" in (curto.get("nota") or ""),
           "cala com menos de 3 blocos de 500", curto.get("nota", ""))


# ══════════════════════════════════════════════════════ 3. ciclo de magnitude
SACO_BAIXO = [40.0, 50.0, 60.0, 70.0]
SACO_ALTO = [300.0, 400.0, 500.0, 600.0]


def crono_com_reversao(n: int, forca: float, rnd) -> list:
    """Gera prêmios em que a magnitude REVERTE de acordo com as últimas 8.

    A PRIMEIRA VERSÃO DESTE GERADOR ESTAVA ERRADA, E O ERRO ERA MEU
    ───────────────────────────────────────────────────────────────
    Eu havia plantado ondas de 10 prêmios baixos seguidas de 10 altos e chamado
    aquilo de inversão. Não é: numa onda de 10, depois de 8 baixos o mais provável
    é o nono baixo. Aquele gerador planta PERSISTÊNCIA, e uma medida honesta de
    reversão tem de dizer "não confirma" nele -- que foi o que a medida disse, e
    eu tratei como falha da medida.

    A afirmação dele é outra: "quando são valores baixos, após um tempo começa a
    vir multiplicadores altos e vice-versa". Isso é reversão à média, e planta-se
    assim: olhar as 8 anteriores e escolher a próxima do saco CONTRÁRIO com
    probabilidade `forca`. Com `forca=0.85` a mesa reverte de verdade; com
    `forca=0.5` a próxima não depende do passado e a mesa é honesta -- o mesmo
    gerador serve aos dois lados do controle, o que é a única forma de o controle
    valer algo.
    """
    saida: list = []
    premios: list = []
    for _ in range(n):
        if len(premios) >= 8:
            ult = premios[-8:]
            m = sum(1 for x in ult if x >= 300.0) / 8.0
            if m < 0.5:            # veio baixo → tende a vir alto
                saco = SACO_ALTO if rnd.random() < forca else SACO_BAIXO
            else:                  # veio alto → tende a vir baixo
                saco = SACO_BAIXO if rnd.random() < forca else SACO_ALTO
        else:
            saco = rnd.choice([SACO_BAIXO, SACO_ALTO])
        v = rnd.choice(saco)
        premios.append(v)
        saida += [v] + [0.0] * 4   # um prêmio a cada 5 giros
    return saida


def teste_ciclo():
    print("\n[3] CICLO DE MAGNITUDE — 'depois de baixos vêm altos'")
    rnd = random.Random(23)

    # PLANTADO: a próxima magnitude REVERTE a média das 8 anteriores.
    c = RM.ciclo_magnitude(mesa(crono_com_reversao(900, 0.85, rnd)), PAGOU)
    checar(c.get("mediu") and c.get("confirma") is True,
           "encontra a inversão quando ela está plantada",
           f"depois de baixos {c.get('alto_depois_de_baixo')} vs depois de altos "
           f"{c.get('alto_depois_de_alto')} = {c.get('razao')}x "
           f"(n={c.get('n_baixo')}/{c.get('n_alto')})")

    # HONESTO: mesmo gerador, força 0.5 — a próxima não olha para o passado.
    h = RM.ciclo_magnitude(mesa(crono_com_reversao(900, 0.5, rnd)), PAGOU)
    checar(h.get("mediu"), "consegue medir a mesa honesta (n suficiente)",
           h.get("nota", ""))
    checar(h.get("confirma") is False,
           "NÃO encontra inversão em mesa sem inversão",
           f"depois de baixos {h.get('alto_depois_de_baixo')} vs depois de altos "
           f"{h.get('alto_depois_de_alto')} = {h.get('razao')}x")

    # PERSISTÊNCIA plantada: ondas longas. A medida de REVERSÃO não pode
    # confirmar aqui -- é o contrário do que ela procura.
    ondas = []
    for _ in range(20):
        for _ in range(10):
            ondas += [rnd.choice(SACO_BAIXO)] + [0.0] * 4
        for _ in range(10):
            ondas += [rnd.choice(SACO_ALTO)] + [0.0] * 4
    pers = RM.ciclo_magnitude(mesa(ondas), PAGOU)
    checar(pers.get("confirma") is not True,
           "não confunde persistência com inversão",
           f"depois de baixos {pers.get('alto_depois_de_baixo')} vs depois de "
           f"altos {pers.get('alto_depois_de_alto')}")

    # magnitude atual: a faixa tem de sair na direção certa
    baixo = [50.0] * 40 + [0.0] * 100
    alto = [600.0] * 40 + [0.0] * 100
    m_b = RM.magnitude(mesa(baixo[::-1] + alto), PAGOU)   # recentes = altos
    checar(m_b.get("faixa") == "altos",
           "prêmios recentes altos são chamados de altos",
           f"posto {m_b.get('posto_recente')} (média {m_b.get('media_recente')}, "
           f"mediana da mesa {m_b.get('mediana_da_mesa')}) → {m_b.get('faixa')}")
    m_a = RM.magnitude(mesa(alto[::-1] + baixo), PAGOU)   # recentes = baixos
    checar(m_a.get("faixa") == "baixos",
           "prêmios recentes baixos são chamados de baixos",
           f"posto {m_a.get('posto_recente')} → {m_a.get('faixa')}")
    # mesa sem variação nenhuma: não pode inventar 'altos' nem 'baixos'
    m_i = RM.magnitude(mesa([100.0] * 60 + [0.0] * 200), PAGOU)
    checar(m_i.get("faixa") == "normais",
           "mesa em que todo prêmio é igual não tem alto nem baixo",
           f"posto {m_i.get('posto_recente')} → {m_i.get('faixa')}")


# ══════════════════════════════════════════════════════════════ 4. seca
def teste_seca():
    print("\n[4] SECA — em quantil, não em número absoluto")
    # seca regular de 9 giros, e uma seca ATUAL de 40
    crono = ([0.0] * 9 + [100.0]) * 40
    lin = mesa(crono)
    lin = [linha(str(i % 37)) for i in range(40)] + lin   # 40 giros secos na frente
    s = RM.seca(lin, PAGOU)
    checar(s.get("mediu") and s.get("agora") == 40,
           "conta a seca atual corretamente", f"agora={s.get('agora')}")
    checar(s.get("mediana") == 9,
           "conhece a seca típica da mesa", f"mediana={s.get('mediana')}")
    checar(s.get("longa") is True,
           "40 numa mesa que seca 9 é reconhecida como longa",
           f"quantil {s.get('quantil')}")

    # seca de 3 na mesma mesa NÃO pode ser 'longa'
    lin2 = [linha(str(i)) for i in range(3)] + mesa(crono)
    s2 = RM.seca(lin2, PAGOU)
    checar(s2.get("longa") is False,
           "seca curta não é vendida como longa",
           f"agora={s2.get('agora')}, quantil {s2.get('quantil')}")

    # mesa que nunca pagou: não pode explodir nem inventar quantil
    s3 = RM.seca([linha(str(i % 37)) for i in range(50)], PAGOU)
    checar(s3.get("mediu") is False and s3.get("agora") == 50,
           "mesa sem nenhum prêmio: cala e informa a seca",
           s3.get("nota", ""))


# ═════════════════════════════════════════════════ 5. leitura completa e voz
def teste_leitura():
    print("\n[5] LEITURA COMPLETA — o que aparece na tela dele")
    rnd = random.Random(7)
    # uma mesa com as duas coisas dele dentro, para a voz sair completa
    crono = crono_com_limiar(24, 0.85, rnd)
    r = RM.ler(mesa(crono), PAGOU)
    checar(set(r) == {"densidade", "limiar", "magnitude", "ciclo", "seca"},
           "as cinco medidas vêm juntas", ", ".join(sorted(r)))
    linhas = RM.resumo(r)
    checar(len(linhas) >= 3, f"resumo fala em português ({len(linhas)} linhas)")
    for L in linhas:
        print(f"        {L}")

    # dado vazio não pode derrubar nada
    vazio = RM.ler([], PAGOU)
    checar(isinstance(vazio, dict) and RM.resumo(vazio) is not None,
           "histórico vazio não derruba a leitura")
    # uma linha só, e malformada
    RM.ler([{"n": "3"}, {}, None], PAGOU)
    checar(True, "linhas malformadas não derrubam a leitura")


# ══════════════════════════════════════ 6. o semáforo decidindo com o regime
def eixos(**ds) -> dict:
    """Uma medição de eixos fabricada: `eixos(publico=1.7)` → d=1.7 no público."""
    det = {}
    for eixo, d in ds.items():
        det[eixo] = {"d": d, "peso": 2.0, "n_pagou": 200, "n_nao": 200,
                     "media_pagou": 900, "media_nao": 300}
    return {"pesos": {}, "detalhe": det, "aprendeu": True}


def situacao_boa() -> dict:
    return {"fala": True, "n": 40, "razao": 1.6, "lift_mult": 1.8,
            "pagou": 0.22, "medida_eixos": None}


def teste_semaforo_com_regime():
    print("\n[6] SEMÁFORO — a cor sai das observações DELE, medidas")
    from NUCLEO import semaforo as SF
    rnd = random.Random(5)

    # a mesa em que o limiar dele SE CONFIRMA, e a densidade está acima
    # 40 blocos: com 24 o teste de ruído recusava por falta de amostra (t=1,7) --
    # e recusar ali era a medida funcionando, não falhando.
    lin_conf = mesa(crono_com_limiar(40, 0.85, rnd, terminar_alto=True))
    reg_conf = RM.ler(lin_conf, PAGOU)
    checar(reg_conf["limiar"].get("confirma") is True
           and reg_conf["densidade"].get("acima_do_limiar") is True,
           "cenário montado: limiar confirmado e densidade acima de 45",
           f"{reg_conf['densidade']['quantos']} em 500, "
           f"t={reg_conf['limiar'].get('t')}")

    s = SF.avaliar(situacao=situacao_boa(), regime=reg_conf)
    virou = [m for m in s["motivos"] if "multiplicado" in m]
    checar(bool(virou),
           "densidade acima do ponto dele VIRA razão quando o ponto se confirma",
           virou[0][:90] if virou else "nenhum motivo de densidade")

    # a MESMA densidade alta, mas numa mesa onde o limiar NÃO se confirma
    lin_hon = mesa(crono_com_limiar(24, 0.5, rnd))
    reg_hon = RM.ler(lin_hon, PAGOU)
    reg_hon["densidade"]["quantos"] = 120           # densidade alta de propósito
    reg_hon["densidade"]["acima_do_limiar"] = True
    reg_hon["limiar"]["confirma"] = False
    s2 = SF.avaliar(situacao=situacao_boa(), regime=reg_hon)
    checar(not any("multiplicado" in m for m in s2["motivos"]),
           "a MESMA densidade NÃO vira razão onde o ponto não se confirma")
    checar(any("NÃO se confirmou" in o or "não se confirmou" in o
               for o in s2["observacoes"]),
           "e o software diz por que não contou",
           ([o for o in s2["observacoes"] if "confirm" in o] or [""])[0][:90])

    # ── a inversão: baixos recentes + inversão confirmada = razão ────────
    reg_inv = {
        "densidade": {}, "limiar": {},
        "magnitude": {"mediu": True, "faixa": "baixos", "media_recente": 55.0,
                      "mediana_da_mesa": 400.0, "n_recentes": 8,
                      "posto_recente": 0.24},
        "ciclo": {"mediu": True, "confirma": True, "alto_depois_de_baixo": 0.79,
                  "alto_depois_de_alto": 0.23, "n_baixo": 49, "n_alto": 52,
                  "z": 5.7, "razao": 3.4},
        "seca": {},
    }
    s3 = SF.avaliar(situacao=situacao_boa(), regime=reg_inv)
    checar(any("BAIXOS" in m for m in s3["motivos"]),
           "prêmios baixos + inversão confirmada = razão para verde",
           ([m for m in s3["motivos"] if "BAIXOS" in m] or [""])[0][:90])

    # os mesmos baixos, com a inversão NÃO confirmada
    reg_inv2 = dict(reg_inv, ciclo=dict(reg_inv["ciclo"], confirma=False))
    s4 = SF.avaliar(situacao=situacao_boa(), regime=reg_inv2)
    checar(not any("BAIXOS" in m for m in s4["motivos"]),
           "os mesmos baixos não viram razão sem a inversão confirmada")

    # prêmios ALTOS com inversão confirmada = contra, não a favor
    reg_alto = dict(reg_inv, magnitude=dict(reg_inv["magnitude"], faixa="altos",
                                            media_recente=580.0))
    s5 = SF.avaliar(situacao=situacao_boa(), regime=reg_alto)
    checar(any("ALTOS" in c for c in s5["contra"]),
           "prêmios altos com inversão confirmada seguram, não empurram",
           ([c for c in s5["contra"] if "ALTOS" in c] or [""])[0][:80])

    # ── a seca só conta se a seca separar NESTA mesa ─────────────────────
    reg_seca = {"densidade": {}, "limiar": {}, "magnitude": {}, "ciclo": {},
                "seca": {"mediu": True, "agora": 41, "mediana": 9,
                         "maior_do_historico": 44, "quantil": 0.97,
                         "longa": True, "n_secas": 120}}
    sem_medida = SF.avaliar(situacao=situacao_boa(), regime=reg_seca)
    checar(not any("seca longa" in m for m in sem_medida["motivos"]),
           "seca longa sem medida NÃO vira razão")
    com_medida = SF.avaliar(
        situacao=dict(situacao_boa(), medida_eixos=eixos(seca_mult=1.4)),
        regime=reg_seca)
    checar(any("seca longa" in m for m in com_medida["motivos"]),
           "seca longa VIRA razão onde a seca separa (d=1.40)",
           ([m for m in com_medida["motivos"] if "seca longa" in m] or [""])[0][:90])

    # ── o verde e o aviso ────────────────────────────────────────────────
    verde = SF.avaliar(
        situacao=dict(situacao_boa(), medida_eixos=eixos(seca_mult=1.4)),
        regime=dict(reg_inv, seca=reg_seca["seca"]))
    checar(verde["cor"] == SF.VERDE and verde["avisar"] is True,
           f"com {len(verde['motivos'])} razões medidas a cor é VERDE e avisa",
           verde["cor"])
    for L in SF.resumo(verde):
        print(f"        {L}")

    # nada medido: não pode dar verde, e não pode avisar
    nada = SF.avaliar(situacao=situacao_boa(), regime=None)
    checar(nada["avisar"] is (nada["cor"] == SF.VERDE),
           "avisar acompanha o verde, sempre")
    seco = SF.avaliar(situacao={"fala": False, "nota": "sem vizinhos"},
                      regime={"densidade": {}, "limiar": {}, "magnitude": {},
                              "ciclo": {}, "seca": {}})
    checar(seco["cor"] == SF.VERMELHO and seco["avisar"] is False,
           "sem base nenhuma: vermelho e nenhum aviso ao celular", seco["cor"])


def main() -> int:
    print("═" * 72)
    print("REGIME DE MULTIPLICADOR — plantado deve achar, honesto não pode")
    print("═" * 72)
    teste_densidade()
    teste_limiar()
    teste_ciclo()
    teste_seca()
    teste_leitura()
    teste_semaforo_com_regime()
    print("\n" + "═" * 72)
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"  ✗ {f}")
        return 1
    print("tudo passou — cada medida acha o que foi plantado e recusa o honesto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
