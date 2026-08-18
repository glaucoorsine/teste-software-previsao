# -*- coding: utf-8 -*-
"""
FORMULAR — as inteligências que montam jogos consultando a base.

O QUE ELE PEDIU, DESDE O COMEÇO
───────────────────────────────
    "a inteligência artificial ou as inteligências artificiais irem
     consultando [a base] pra formular os jogos"

A base existe, o medidor existe — faltava exatamente isto: quem formula. E a
regra de formação vem do portão que foi a melhor decisão do outro software:

    uma inteligência que não aponta o item da base que a autoriza fica CALADA.
    E item DERRUBADO pela medida não autoriza mais ninguém.

Então cada inteligência daqui declara o que cita. Se o item citado for
derrubado nos dados dele, ela emudece — na tela, com o motivo. Se o item ainda
não foi medido, ela fala, mas carrega o aviso de que fala sem base. É o
contrário de um gerador de palpite: dá para rastrear cada jogo até a afirmação
que o sustenta, e dá para calar cada inteligência derrubando a afirmação dela.

A FRASE QUE MANDA EM TODAS
──────────────────────────
Nenhuma escolha de dezenas muda a CHANCE (M01). As inteligências não competem
em "qual acerta mais" — num sorteio honesto isso não existe. Elas diferem no
MOTIVO: uma otimiza a partilha do prêmio, duas seguem crenças que estão na base
para serem medidas, e uma é o controle honesto. A discordância entre elas é
informação sobre os motivos, nunca sobre as bolas.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import base_conhecimento as BC
from . import regras
from .historico import Historico
from .medidor import MEDIDORES

# quantos concursos contam como "recentes" para a inteligência das quentes.
# O mesmo valor do medidor de C02 — medir com uma janela e formular com outra
# seria medir uma coisa e fazer outra.
JANELA_QUENTE = 20


def _tem_sequencia(dezenas: Sequence[int], comprimento: int = 3) -> bool:
    """Há `comprimento` dezenas consecutivas? (1-2-3 no meio do jogo.)"""
    s = sorted(dezenas)
    corrida = 1
    for a, b in zip(s, s[1:]):
        corrida = corrida + 1 if b == a + 1 else 1
        if corrida >= comprimento:
            return True
    return False


def _citacoes(ids: Sequence[str]) -> Tuple[bool, List[str], List[str]]:
    """Os itens citados autorizam? Devolve (autorizado, linhas, avisos).

    O PORTÃO, APLICADO À FORMAÇÃO DE JOGO
    ─────────────────────────────────────
    Derrubado cala. Sem medida fala com aviso — e o aviso não é rodapé, é parte
    do jogo formulado, porque jogar por uma crença não medida é decisão que ELE
    tem o direito de tomar sabendo que é isso que está fazendo.
    """
    linhas: List[str] = []
    avisos: List[str] = []
    autorizado = True
    for ident in ids:
        it = BC.por_id(ident)
        if not it:
            autorizado = False
            avisos.append(f"o item {ident} não existe na base — defeito meu")
            continue
        if not BC.autorizada(ident):
            autorizado = False
            linhas.append(f"{it.id} {it.titulo} — ✗ DERRUBADO nos seus resultados")
            continue
        if it.veredito == "confirmado":
            taxa = it.medida.get("taxa")
            acaso = it.medida.get("acaso")
            detalhe = (f" (taxa {taxa:.4f} contra {acaso:.4f} de acaso)"
                       if isinstance(taxa, float) and isinstance(acaso, float)
                       else "")
            linhas.append(f"{it.id} {it.titulo} — ✓ confirmado{detalhe}")
        elif ident not in MEDIDORES and it.origem == BC.MATEMATICA:
            # matemática que o medidor nem mede (M01, M03...) não tem pendência
            # nenhuma -- dizer "sem medida" dela soaria como falta, e não há.
            linhas.append(f"{it.id} {it.titulo} — demonstrado")
        elif it.origem == BC.MATEMATICA:
            # o caso do P01: o MECANISMO é demonstrado (o prêmio se divide),
            # mas o TAMANHO do efeito é medível e ainda não foi medido. São
            # avisos diferentes porque são dúvidas diferentes.
            linhas.append(f"{it.id} {it.titulo} — mecanismo demonstrado, "
                          f"tamanho · ainda sem medida")
            avisos.append(f"o tamanho do efeito de {it.id} ainda não foi "
                          f"medido nos seus resultados — o mecanismo é certo, "
                          f"o quanto ele rende não")
        else:
            linhas.append(f"{it.id} {it.titulo} — · ainda sem medida")
            avisos.append(f"{it.id} ainda não foi medido nos seus resultados "
                          f"— este jogo segue uma crença, não um achado")
    return autorizado, linhas, avisos


def _calada(nome: str, rotulo: str, motivo: str,
            cita: Sequence[str] = ()) -> Dict[str, Any]:
    return {"inteligencia": nome, "rotulo": rotulo, "calada": True,
            "motivo": motivo, "cita": list(cita), "dezenas": [],
            "citacoes": [], "avisos": []}


def _jogo(nome: str, rotulo: str, dezenas: Sequence[int], cita: Sequence[str],
          citacoes: List[str], avisos: List[str], motivo: str,
          semente: Optional[int] = None) -> Dict[str, Any]:
    return {"inteligencia": nome, "rotulo": rotulo, "calada": False,
            "dezenas": sorted(dezenas), "cita": list(cita),
            "citacoes": citacoes, "avisos": avisos, "motivo": motivo,
            "semente": semente}


# ═══════════════════════════════════ 1. anti-partilha — a única que paga
def anti_partilha(j: regras.Jogo, quantas: int,
                  rnd: random.Random) -> Dict[str, Any]:
    """Dezenas que a multidão evita — para dividir menos SE acertar.

    OS RETRATOS DE DEZENA POPULAR QUE EU USO, DITOS UM A UM
    ───────────────────────────────────────────────────────
    Datas: todo aniversário cabe em 1–31, e dia E mês cabem em 1–12. E
    sequências: 1-2-3-4-5-6 é jogada por milhares de pessoas todo concurso.
    Estes retratos são exatamente o que P01 mede; enquanto P01 não for medido
    nos dados dele, isto aqui é a crença mais defensável da loteria — mas é
    crença, e o jogo sai avisado disso.

    E uma honestidade que ninguém pede mas eu devo: se muita gente usasse este
    mesmo software, as dezenas "pouco jogadas" dele virariam as muito jogadas.
    O sorteio da escolha (com semente mostrada) é também por isso.
    """
    cita = ("M01", "P01")
    autorizado, citacoes, avisos = _citacoes(cita)
    if not autorizado:
        return _calada("anti_partilha", "Anti-partilha",
                       "o item que me autoriza foi derrubado pela medida", cita)
    todas = j.dezenas()
    fora_de_data = [d for d in todas if d > 31]
    if len(fora_de_data) >= quantas:
        pool = fora_de_data
    else:
        # Lotofácil e Dia de Sorte cabem inteiros em datas — o retrato "≤31"
        # não separa nada ali, e fingir que separa seria enfeite. Sobram os
        # outros retratos, e o jogo diz isso.
        pool = todas
        avisos = avisos + [f"o universo de {j.nome} cabe (quase) todo em "
                           f"datas — aqui só evito sequências e concentração "
                           f"em 1–12, e a vantagem de partilha encolhe"]
    escolha: List[int] = []
    for tentativa in range(200):
        escolha = rnd.sample(pool, quantas)
        if not _tem_sequencia(escolha, 3):
            baixas = sum(1 for d in escolha if d <= 12)
            if baixas <= max(1, quantas // 5):
                break
    else:
        avisos = avisos + ["não deu para evitar sequência com esta densidade "
                           "de dezenas — ficou a melhor tentativa"]
    return _jogo("anti_partilha", "Anti-partilha", escolha, cita, citacoes,
                 avisos,
                 "a chance é idêntica à de qualquer jogo (M01); o que muda é "
                 "com quantos se divide SE acertar (P01)")


# ═══════════════════════════ 2. atrasadas — a crença C01, sob o portão
def atrasadas(j: regras.Jogo, quantas: int,
              hist: Optional[Historico]) -> Dict[str, Any]:
    """As dezenas há mais tempo sem sair. Só fala se C01 permitir."""
    cita = ("C01",)
    autorizado, citacoes, avisos = _citacoes(cita)
    if not autorizado:
        return _calada("atrasadas", "Atrasadas (C01)",
                       "a medida nos seus resultados derrubou C01: dezenas "
                       "atrasadas NÃO saíram mais que as outras. Eu não "
                       "formulo jogo por crença que a medida matou.", cita)
    if hist is None or not len(hist):
        return _calada("atrasadas", "Atrasadas (C01)",
                       "sem os resultados dos concursos eu não sei o atraso "
                       "de dezena nenhuma. Busque os resultados primeiro e eu "
                       "volto a falar.", cita)
    if hist.sintetico:
        avisos = avisos + ["o histórico é SINTÉTICO — jogo de treino, não "
                           "jogue isto com dinheiro"]
    sorteios = hist.sorteios()
    ultima: Dict[int, int] = {}
    for i, s in enumerate(sorteios):
        for d in s:
            ultima[d] = i
    n = len(sorteios)
    atraso = {d: n - 1 - ultima.get(d, -1) for d in j.dezenas()}
    escolha = sorted(j.dezenas(), key=lambda d: (-atraso[d], d))[:quantas]
    maior = max(atraso[d] for d in escolha)
    return _jogo("atrasadas", "Atrasadas (C01)", escolha, cita, citacoes,
                 avisos,
                 f"as {quantas} dezenas há mais tempo sem sair (a mais "
                 f"atrasada está há {maior} concursos)")


# ═══════════════════════════ 3. quentes — a crença C02, sob o mesmo portão
def quentes(j: regras.Jogo, quantas: int,
            hist: Optional[Historico]) -> Dict[str, Any]:
    """As que mais saíram nos últimos concursos. Só fala se C02 permitir."""
    cita = ("C02",)
    autorizado, citacoes, avisos = _citacoes(cita)
    if not autorizado:
        return _calada("quentes", "Quentes (C02)",
                       "a medida nos seus resultados derrubou C02: dezena "
                       "quente NÃO continuou saindo mais. Crença morta não "
                       "formula jogo.", cita)
    if hist is None or not len(hist):
        return _calada("quentes", "Quentes (C02)",
                       "sem os resultados dos concursos não existe dezena "
                       "quente. Busque os resultados primeiro e eu volto a "
                       "falar.", cita)
    if hist.sintetico:
        avisos = avisos + ["o histórico é SINTÉTICO — jogo de treino, não "
                           "jogue isto com dinheiro"]
    recentes = hist.sorteios()[-JANELA_QUENTE:]
    freq: Dict[int, int] = {d: 0 for d in j.dezenas()}
    for s in recentes:
        for d in s:
            freq[d] = freq.get(d, 0) + 1
    escolha = sorted(j.dezenas(), key=lambda d: (-freq[d], d))[:quantas]
    return _jogo("quentes", "Quentes (C02)", escolha, cita, citacoes, avisos,
                 f"as {quantas} mais frequentes nos últimos "
                 f"{min(JANELA_QUENTE, len(recentes))} concursos")


# ═══════════════════════════════ 4. aleatória — o controle que não finge
def aleatoria(j: regras.Jogo, quantas: int,
              rnd: random.Random) -> Dict[str, Any]:
    """Sorteio uniforme, e ponto. O controle de todas as outras.

    Existe por dois motivos. O honesto: pela CHANCE, isto empata com qualquer
    inteligência — se alguma parecer melhor que esta no histórico, ou é a
    partilha (que não é chance) ou é ruído, e o medidor decide. E o prático:
    quem escolhe dezenas na mão escolhe padrão humano (datas, simetrias), que é
    exatamente o que rateia mal.
    """
    cita = ("M01",)
    _autorizado, citacoes, avisos = _citacoes(cita)
    escolha = rnd.sample(j.dezenas(), quantas)
    return _jogo("aleatoria", "Aleatória (controle)", escolha, cita, citacoes,
                 avisos,
                 "uniforme de verdade — pela chance, empata com todas as "
                 "outras; é a régua delas")


# ═══════════════════════════════════════════════════════════ o conselho
def conselho(chave_jogo: str, quantas: Optional[int] = None,
             hist: Optional[Historico] = None,
             semente: Optional[int] = None) -> Dict[str, Any]:
    """Todas as inteligências, sobre o mesmo material, lado a lado.

    A discordância entre elas é informação — sobre os MOTIVOS, nunca sobre as
    bolas. E cada uma pode estar calada, com o motivo na tela: calar é
    resultado legítimo, não defeito.
    """
    j = regras.jogo(chave_jogo)
    if not j:
        return {"ok": False, "nota": f"jogo desconhecido: {chave_jogo}"}
    k = quantas or j.minimo
    if not (j.minimo <= k <= j.maximo):
        return {"ok": False,
                "nota": f"{j.nome} aceita de {j.minimo} a {j.maximo} dezenas; "
                        f"pediu {k}"}
    # semente mostrada e devolvida: o jogo de hoje tem de ser reproduzível
    # amanhã, senão nem ele nem eu conseguimos conferir o que foi formulado.
    semente_real = (semente if semente is not None
                    else random.randrange(1, 1_000_000))
    rnd = random.Random(semente_real)
    jogos = [anti_partilha(j, k, rnd),
             atrasadas(j, k, hist),
             quentes(j, k, hist),
             aleatoria(j, k, rnd)]
    # nenhuma inteligência entrega aposta que a Caixa recusaria
    for g in jogos:
        if not g["calada"]:
            ok, motivo = j.valida_aposta(g["dezenas"])
            if not ok:
                g["calada"] = True
                g["motivo"] = f"formulei aposta inválida ({motivo}) — defeito " \
                              f"meu, e calar é melhor que entregar"
    return {"ok": True, "jogo": j.chave, "quantas": k,
            "semente": semente_real, "jogos": jogos,
            "com_historico": hist is not None and len(hist) > 0}


def resumo(c: Dict[str, Any]) -> List[str]:
    if not c.get("ok"):
        return [f"[Formular] {c.get('nota')}"]
    j = regras.jogo(c["jogo"])
    L = [f"[Formular] {j.nome}: {c['quantas']} dezenas por jogo, "
         f"semente {c['semente']} (com --semente {c['semente']} sai igual)"]
    L.append("[Formular] a chance é IDÊNTICA nos quatro (M01). O que difere é "
             "o motivo — e está citado.")
    if not c.get("com_historico"):
        L.append("[Formular] sem histórico: atrasadas e quentes ficam caladas "
                 "até você puxar os resultados.")
    for g in c["jogos"]:
        L.append("")
        if g["calada"]:
            L.append(f"[Formular] · {g['rotulo']}: CALADA — {g['motivo']}")
            continue
        L.append(f"[Formular] ▸ {g['rotulo']}:  "
                 + "  ".join(f"{d:02d}" for d in g["dezenas"]))
        L.append(f"[Formular]     por quê: {g['motivo']}")
        for linha in g["citacoes"]:
            L.append(f"[Formular]     cita: {linha}")
        for a in g["avisos"]:
            L.append(f"[Formular]     aviso: {a}")
    L.append("")
    L.append("[Formular] para transformar um deles em apostas com garantia:")
    L.append(f"[Formular]   python JOGAR.py {c['jogo']} --dezenas \"<as "
             f"dezenas>\" --se 5 --garantir 4")
    return L
