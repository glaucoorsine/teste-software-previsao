# -*- coding: utf-8 -*-
"""
RESULTADO — a taxa de acerto real, lida do que já aconteceu.

    RESULTADO.bat        (ou: python RESULTADO.py)

Pode rodar com a CENTRAL aberta: só lê arquivo, não mexe em nada.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
"Deu um monte de erro" e "está funcionando" são a mesma frase quando não se
sabe qual era o acaso. Uma aposta de 2 números numa janela de 3 giros acerta
15% das vezes por sorte pura — errar 85% ali é o esperado, não defeito. E uma
aposta de 7 números que acerte 30% está EMPATANDO com o acaso, apesar de
parecer boa.

Então aqui nada é comparado com a impressão. Cada janela é comparada com a
chance daquela aposta específica: o tamanho que ela tinha e a janela que ela
teve. É a única conta que responde se o software está achando alguma coisa.

O QUE ELE LÊ
------------
Logs/central_log.txt, que a CENTRAL escreve sozinha:

    NOVA_JANELA [4, 5, 9] OPERAR    ← quantos números foram apostados
    HIT 5 restam=2                  ← o giro caiu na aposta
    MISS 30 restam=1                ← não caiu
    JANELA OK ok=3 err=7            ← a janela fechou
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
LOG = RAIZ / "Logs" / "central_log.txt"
JOGOS = ("lightning", "mega_fire", "crazy_time", "crazy_time_a", "red_door")

# A CRAZY TIME A FALTAVA AQUI, E ISSO ERA UM KeyError NA PRIMEIRA JANELA.
#
# `JOGOS` tinha a mesa, `N_CLASSES` não. Na primeira janela fechada da Crazy
# Time A, `chance_por_giro` fazia `N_CLASSES[jogo]` e o relatório inteiro
# morria -- não só a linha dela: as quatro mesas sumiam junto, porque o
# estouro acontece antes de qualquer coisa ser impressa.
#
# É o tipo de defeito que só aparece quando o software finalmente funciona:
# enquanto a Crazy Time A não capturava nada, nenhuma janela dela fechava, e
# o erro ficava dormindo.
N_CLASSES = {"lightning": 37, "mega_fire": 37,
             "crazy_time": 54, "crazy_time_a": 54, "red_door": 37}

# A RODA DO CRAZY TIME NÃO TEM CASAS IGUAIS.
#
# São 54 casas, mas o "1" ocupa 21 delas e o CrazyTime uma só. Tratar todo
# símbolo como 1/54 — que era o que eu fazia — infla a razão em até 7 vezes.
#
# Na primeira leitura do log dele deu "5,32x acima do acaso" no Crazy Time.
# Só que o software apostou `['5']` em 36 das 56 janelas, e o 5 vale 13,0% por
# giro, não 1,9%. O 5,32x era erro meu de baseline, não vantagem dele.
#
# O resto do software chama a casa premiada de "CrazyBonus" (é o nome que
# `hist_buffer.CT` valida). Aqui estava escrito "CrazyTime", então o símbolo
# caía no `.get(..., 1)` por acidente. Deu certo por coincidência -- a casa
# vale 1 mesmo -- mas coincidência não é conta. Os dois nomes entram.
FATIAS_CT = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2,
             "CrazyBonus": 1, "CrazyTime": 1}

LINHA = re.compile(
    r"^\S+ \S+ \| (\w+) (NOVA_JANELA|HIT|MISS|JANELA) ?(.*)$")


def ler(caminho: Path) -> dict:
    """Reconstrói as janelas a partir do log, na ordem em que aconteceram."""
    dados = {j: {"janelas": [], "aberta": None} for j in JOGOS}
    if not caminho.is_file():
        return dados
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINHA.match(linha.strip())
        if not m:
            continue
        jogo, tipo, resto = m.group(1), m.group(2), m.group(3)
        d = dados.get(jogo)
        if d is None:
            continue
        if tipo == "NOVA_JANELA":
            alvos = re.findall(r"'([^']+)'", resto.split("]")[0]) or \
                re.findall(r"\b\w+\b", resto.split("]")[0])
            # APOSTA REPETIDA É ESPERA, NÃO JANELA NOVA.
            #
            # Insistir num atrasado está certo pelo critério dele. O que estava
            # errado era a contabilidade: cada volta reabria uma janela, e
            # quinze minutos esperando o CashHunt viravam vinte janelas
            # perdidas no placar em vez de uma espera longa. O placar mentia
            # para baixo — e mentia justamente nas horas em que ele estava
            # fazendo o que o método manda.
            #
            # A CENTRAL agora marca essas reaberturas com REPETICAO. Aqui elas
            # voltam para a janela anterior, somando giros nela.
            if "REPETICAO" in resto and d["janelas"]:
                ultima = d["janelas"][-1]
                if [str(x) for x in (ultima.get("alvos") or [])] == \
                        [str(x) for x in alvos]:
                    ultima.pop("fechou_bem", None)
                    d["aberta"] = d["janelas"].pop()
                    continue
            d["aberta"] = {"k": len(alvos), "alvos": list(alvos),
                           "acertos": 0, "giros": 0}
        elif tipo in ("HIT", "MISS"):
            if d["aberta"] is None:
                # janela aberta antes deste log começar: conta o giro num
                # balde separado em vez de inventar o tamanho da aposta
                d["aberta"] = {"k": None, "acertos": 0, "giros": 0}
            d["aberta"]["giros"] += 1
            if tipo == "HIT":
                d["aberta"]["acertos"] += 1
        elif tipo == "JANELA":
            if d["aberta"] is not None:
                d["aberta"]["fechou_bem"] = resto.strip().startswith("OK")
                d["janelas"].append(d["aberta"])
                d["aberta"] = None
    return dados


def chance_por_giro(jogo: str, alvos, k: int) -> float:
    """A chance de a aposta acertar em UM giro.

    Na roleta toda casa vale igual, então é k/37. No Crazy Time não: cada
    símbolo ocupa um número diferente de casas, e é preciso somar as casas
    dos símbolos apostados.
    """
    n = N_CLASSES.get(jogo)
    if n is None:
        # mesa que o log conhece e este arquivo não: melhor devolver 0 e a
        # linha sair marcada como "sem baseline" do que derrubar o relatório
        # inteiro das outras mesas por causa dela
        return 0.0
    if not str(jogo).startswith("crazy_time"):
        return min(k, n) / n
    casas = sum(FATIAS_CT.get(str(a), 1) for a in (alvos or []))
    if not casas:
        casas = k
    return min(casas, n) / n


def chance_janela(p_giro: float, giros: int) -> float:
    """Chance de acertar ao menos uma vez em `giros`, dada a chance por giro."""
    if p_giro <= 0 or not giros:
        return 0.0
    return 1.0 - (1.0 - p_giro) ** giros


def barra(x: float, largura: int = 22) -> str:
    cheio = max(0, min(largura, round(x * largura)))
    return "█" * cheio + "·" * (largura - cheio)


def relatar(jogo: str, d: dict) -> list:
    fechadas = [j for j in d["janelas"] if j.get("k")]
    L = [f"  {jogo.upper()}"]
    if not fechadas:
        abertas = len(d["janelas"])
        L.append(f"     nenhuma janela fechada com aposta registrada"
                 + (f" ({abertas} de antes deste log)" if abertas else ""))
        return L

    n = len(fechadas)
    ok = sum(1 for j in fechadas if j.get("fechou_bem"))
    esperado = sum(chance_janela(chance_por_giro(jogo, j.get("alvos"), j["k"]),
                                 j["giros"])
                   for j in fechadas)
    taxa = ok / n
    acaso = esperado / n
    razao = (taxa / acaso) if acaso else 0.0

    giros = sum(j["giros"] for j in fechadas)
    acertos_num = sum(j["acertos"] for j in fechadas)
    k_medio = sum(j["k"] for j in fechadas) / n
    acaso_num = sum(chance_por_giro(jogo, j.get("alvos"), j["k"])
                    for j in fechadas) / n
    taxa_num = acertos_num / giros if giros else 0.0

    L.append(f"     janelas   {ok:>4} certas de {n:<4}  {taxa:6.1%}  "
             f"acaso {acaso:6.1%}   {razao:.2f}x  {barra(min(taxa, 1))}")
    L.append(f"     números   {acertos_num:>4} de {giros:<4} giros    "
             f"{taxa_num:6.1%}  acaso {acaso_num:6.1%}   "
             f"{(taxa_num/acaso_num if acaso_num else 0):.2f}x")
    L.append(f"     aposta média {k_medio:.1f} números")

    if n < 20:
        L.append(f"     ⚠ {n} janelas é pouco para concluir — "
                 f"nesse tamanho, sorte e vantagem se parecem")
    elif razao >= 1.0:
        L.append(f"     acima do acaso por enquanto")
    else:
        L.append(f"     abaixo do acaso — as escolhas não estão ajudando")
    return L


def por_fase(dados: dict) -> list:
    """A taxa nas primeiras janelas contra a taxa depois — a pergunta dele.

        "quando abro o software, as primeiras leituras e sugestoes sao muito
         precisas e boas, porque seera?"
        "nao, foi previsao mesmo"  /  "ele preveu na hora e eu vi"

    Eu levantei vazamento e ele estava errado: a conta do print fechava com
    previsao de verdade. Então a pergunta continua aberta, e adivinhar não
    resolve -- isto mede.

    Se a taxa das primeiras janelas for consistentemente melhor que a das
    últimas, existe uma causa e ela é grande. A candidata mais séria é
    desconfortável para mim: a reponderação por perda (F45, `w ∝ exp(-η·Loss)`)
    pode estar PIORANDO a previsão em vez de melhorá-la. Na abertura os pesos
    estão no estado inicial; depois de horas, foram movidos pelo que o software
    julgou ser erro. Se o julgamento for ruidoso, mover o peso degrada -- e o
    sintoma é exatamente "abre bem e piora".

    Se as duas taxas ficarem iguais, a resposta é a mais simples: as primeiras
    janelas são poucas, e poucas janelas parecem o que a sorte quiser.
    """
    L = ["", "-" * 72, " AS PRIMEIRAS JANELAS CONTRA AS SEGUINTES",
         " (a taxa cai, sobe ou fica igual conforme a sessao anda?)", ""]
    algo = False
    for jogo in JOGOS:
        fechadas = [j for j in dados[jogo]["janelas"] if j.get("k")]
        if len(fechadas) < 8:
            continue
        algo = True
        corte = max(3, len(fechadas) // 3)
        primeiras, ultimas = fechadas[:corte], fechadas[corte:]

        def taxa_e_acaso(bloco):
            n = len(bloco) or 1
            ok = sum(1 for j in bloco if j.get("fechou_bem"))
            esp = sum(chance_janela(
                chance_por_giro(jogo, j.get("alvos"), j["k"]), j["giros"])
                for j in bloco)
            return ok / n, (esp / n if n else 0.0), n, ok

        t1, a1, n1, o1 = taxa_e_acaso(primeiras)
        t2, a2, n2, o2 = taxa_e_acaso(ultimas)
        r1 = (t1 / a1) if a1 else 0.0
        r2 = (t2 / a2) if a2 else 0.0
        L.append(f"  {jogo.upper()}")
        L.append(f"     primeiras {n1:>3} janelas   {o1:>3} certas  "
                 f"{t1:6.1%}  acaso {a1:6.1%}   {r1:.2f}x")
        L.append(f"     depois     {n2:>3} janelas   {o2:>3} certas  "
                 f"{t2:6.1%}  acaso {a2:6.1%}   {r2:.2f}x")
        dif = r1 - r2
        if n1 < 10 or n2 < 10:
            L.append(f"     ⚠ blocos pequenos ({n1} e {n2}) — nesse tamanho a "
                     f"diferenca ainda e sorte")
        elif dif > 0.25:
            L.append(f"     as primeiras foram MELHOR por {dif:.2f}x — se isto "
                     f"repetir em varias sessoes, ha causa, e a suspeita e a "
                     f"reponderacao por perda estar degradando")
        elif dif < -0.25:
            L.append(f"     as primeiras foram PIOR por {abs(dif):.2f}x — a "
                     f"reponderacao estaria ajudando")
        else:
            L.append(f"     praticamente iguais ({dif:+.2f}x) — a impressao de "
                     f"'abre bem' vem do tamanho da amostra, nao do momento")
        L.append("")
    if not algo:
        L.append("  ainda nao ha 8 janelas fechadas em nenhuma mesa.")
        L.append("  Deixe rodando: e a comparacao entre o comeco e o resto que")
        L.append("  responde por que as primeiras parecem melhores.")
        L.append("")
    return L


def main() -> int:
    print()
    print("=" * 72)
    print(" RESULTADO — o que realmente aconteceu")
    print("=" * 72)
    if not LOG.is_file():
        print(f"\n  Ainda não há {LOG}.")
        print("  Rode a CENTRAL por um tempo e volte aqui.\n")
        return 0

    dados = ler(LOG)
    total_j = sum(len([x for x in d["janelas"] if x.get("k")])
                  for d in dados.values())
    print()
    for jogo in JOGOS:
        for linha in relatar(jogo, dados[jogo]):
            print(linha)
        print()

    for linha in por_fase(dados):
        print(linha)

    print("-" * 72)
    print(" Como ler: 'acaso' é a chance daquela aposta exata — o tamanho que")
    print(" ela teve, na janela que ela teve. 1.00x é empatar com a sorte.")
    print(" Errar muito com aposta pequena é o normal, não é defeito: 2")
    print(" números em 3 giros acertam 15% das vezes por sorte pura.")
    if total_j and total_j < 30:
        print()
        print(f" Só {total_j} janelas no total. Deixe rodando mais — abaixo de")
        print(" umas 30 por mesa, qualquer número aqui ainda é chute.")
    print("=" * 72)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
