# -*- coding: utf-8 -*-
"""
TESTE DO AUTOEXAME — a autocrítica tem de achar a causa plantada E recusar
inventar causa onde não há.

O RISCO ESPECÍFICO DESTE ARQUIVO
────────────────────────────────
Um diagnóstico de erro é o lugar mais fácil do software para produzir história
bonita. Com cinco eixos de contexto e poucas janelas, sempre haverá um eixo que
"separa" os acertos dos erros por sorteio, e a inteligência diria com aprumo
"errei porque a mesa estava vazia" sobre dado onde o público não teve nada a ver.

Então o teste central aqui é o NEGATIVO: janelas em que acerto e erro foram
sorteados sem olhar o contexto nenhum, e o autoexame tem de dizer que não achou
causa. Uma autocrítica que sempre encontra culpado é pior que nenhuma, porque
leva a mudar de rumo por ruído.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import autoexame as AX          # noqa: E402

FALHAS = []


def checar(ok, titulo, detalhe=""):
    print(f"  {'ok  ' if ok else 'FALHA'} {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(titulo)
    return ok


def janela(teorias, acertou, contexto=None, k=5) -> dict:
    return {"hips": list(teorias), "alvos": [str(i) for i in range(k)],
            "resultado": {"acertou": bool(acertou)},
            "contexto": dict(contexto or {})}


# ══════════════════════════════════════════════ 1. acertei muito ou errei muito
def teste_taxa():
    print("\n[1] 'ACERTEI MUITO OU ERREI MUITO?' — contra o acaso da MESMA aposta")
    rnd = random.Random(3)
    # T_BOA acerta 40% apostando 5 em 37 (acaso 13.5%) -> ~3x
    regs = [janela(["T_BOA"], rnd.random() < 0.40, {"cor": "VERDE"})
            for _ in range(200)]
    e = AX.examinar_teoria("T_BOA", regs, 37)
    checar(e["sabe"] and e["razao"] and e["razao"] > 2.0,
           "teoria boa aparece acima do acaso",
           f"{e['taxa']:.0%} contra {e['acaso']:.0%} = {e['razao']}x, z={e['z']}")
    checar(e["usar_mais"] is True, "e é marcada para usar MAIS")

    # T_ACASO acerta exatamente o acaso: 5/37 = 13.5%
    regs2 = [janela(["T_ACASO"], rnd.random() < (5 / 37), {"cor": "VERDE"})
             for _ in range(300)]
    e2 = AX.examinar_teoria("T_ACASO", regs2, 37)
    checar(not e2["usar_mais"] and not e2["usar_menos"],
           "teoria que empata com o acaso não é promovida nem rebaixada",
           f"{e2['razao']}x, z={e2['z']}")

    # aposta MAIOR não pode virar 'melhor': 10 em 37 acerta mais e não é melhor
    regs3 = [janela(["T_LARGA"], rnd.random() < (10 / 37), {"cor": "VERDE"}, k=10)
             for _ in range(300)]
    e3 = AX.examinar_teoria("T_LARGA", regs3, 37)
    checar(not e3["usar_mais"],
           "apostar em 10 números não vira mérito (o acaso sobe com o k)",
           f"taxa {e3['taxa']:.0%}, acaso {e3['acaso']:.0%} = {e3['razao']}x")

    # pouca janela: tem de calar
    e4 = AX.examinar_teoria("T_NOVA", [janela(["T_NOVA"], True) for _ in range(6)], 37)
    checar(e4["sabe"] is False and "preciso de" in e4["nota"],
           "com 6 janelas não julga a teoria", e4["nota"])


# ══════════════════════════════════════ 2. foi momento? foi quantidade de pessoas?
def teste_causa_plantada():
    print("\n[2] 'FOI QUESTÃO DE QUANTIDADE DE PESSOAS?' — causa plantada")
    rnd = random.Random(9)
    regs = []
    for _ in range(160):
        cheia = rnd.random() < 0.5
        # PLANTADO: ela acerta com plateia e erra sem
        acertou = (rnd.random() < 0.55) if cheia else (rnd.random() < 0.08)
        pub = rnd.gauss(1300, 150) if cheia else rnd.gauss(400, 120)
        regs.append(janela(["T_PUB"], acertou,
                           {"publico": pub, "seca": rnd.randint(0, 20),
                            "em_hora": rnd.randint(0, 23), "cor": "AMARELO"}))
    e = AX.examinar_teoria("T_PUB", regs, 37)
    top = (e.get("causas") or [{}])[0]
    checar(top.get("eixo") == "publico" and top.get("d", 0) > 0,
           "aponta o público como o eixo que separa, na direção certa",
           f"d={top.get('d')}: acerta com {top.get('quando_acerta')}, "
           f"erra com {top.get('quando_erra')}")
    outros = [c["eixo"] for c in (e.get("causas") or []) if c["eixo"] != "publico"]
    checar(not outros or abs(e["causas"][0]["d"]) > abs(e["causas"][1]["d"]),
           "e o público vem à frente dos eixos que não foram plantados",
           f"ordem: {[c['eixo'] for c in e.get('causas') or []]}")

    # ── a seca como causa, na direção OPOSTA (erra quando a seca é longa) ──
    regs2 = []
    for _ in range(160):
        seca = rnd.randint(0, 40)
        acertou = rnd.random() < (0.50 if seca < 12 else 0.08)
        regs2.append(janela(["T_SECA"], acertou,
                            {"publico": rnd.gauss(900, 300), "seca": seca,
                             "em_hora": rnd.randint(0, 23), "cor": "AMARELO"}))
    e2 = AX.examinar_teoria("T_SECA", regs2, 37)
    top2 = (e2.get("causas") or [{}])[0]
    checar(top2.get("eixo") == "seca" and top2.get("d", 0) < 0,
           "aponta a seca, e diz que erra quando ela é LONGA",
           f"d={top2.get('d')}: acerta com seca {top2.get('quando_acerta')}, "
           f"erra com {top2.get('quando_erra')}")


# ═════════════════════════ 3. O TESTE QUE IMPORTA: não inventar culpado
def teste_sem_causa():
    print("\n[3] O CONTROLE — acerto sorteado sem olhar contexto: NENHUMA causa")
    achou = 0
    tentativas = 40
    for semente in range(tentativas):
        rnd = random.Random(1000 + semente)
        regs = []
        for _ in range(160):
            # o acerto NÃO depende de nada do contexto
            acertou = rnd.random() < 0.30
            regs.append(janela(["T_CEGA"], acertou, {
                "publico": rnd.gauss(900, 300),
                "seca": rnd.randint(0, 40),
                "seca_quantil": rnd.random(),
                "mult_em_500": rnd.randint(20, 120),
                "posto_magnitude": rnd.random(),
                "em_hora": rnd.randint(0, 23),
                "n_motivos": rnd.randint(0, 4),
                "cor": rnd.choice(["VERDE", "AMARELO", "VERMELHO"])}))
        e = AX.examinar_teoria("T_CEGA", regs, 37)
        if e.get("causas"):
            achou += 1
    checar(achou <= tentativas * 0.15,
           f"em {tentativas} mesas sem causa nenhuma, inventou culpado {achou} "
           f"vez(es)",
           f"{achou}/{tentativas} = {achou/tentativas:.0%}; o aceitável é ≤15% "
           f"com 8 eixos testados")

    # e a voz tem de dizer isso, não ficar calada
    rnd = random.Random(77)
    regs = [janela(["T_CEGA"], rnd.random() < 0.30,
                   {"publico": rnd.gauss(900, 300), "seca": rnd.randint(0, 40),
                    "em_hora": rnd.randint(0, 23), "cor": "AMARELO"})
            for _ in range(160)]
    ex = AX.examinar(regs, 37)
    txt = " ".join(AX.resumo(ex))
    checar("não vou inventar culpado" in txt,
           "e diz em português que não achou causa",
           [L for L in AX.resumo(ex) if "culpado" in L][0][:100]
           if "culpado" in txt else "não disse")


# ═══════════════════════════════════════════ 4. usei corretamente a teoria?
def teste_uso_correto():
    print("\n[4] 'SERÁ QUE EU USEI CORRETAMENTE A TEORIA?'")
    rnd = random.Random(31)
    regs = []
    for _ in range(240):
        cor = rnd.choice(["VERDE", "AMARELO", "VERMELHO"])
        # PLANTADO: só funciona no verde
        p = {"VERDE": 0.55, "AMARELO": 0.14, "VERMELHO": 0.10}[cor]
        regs.append(janela(["T_VERDE"], rnd.random() < p, {"cor": cor}))
    e = AX.examinar_teoria("T_VERDE", regs, 37)
    u = e.get("uso") or {}
    checar(u.get("sabe") and u.get("so_no_verde") is True,
           "descobre que a teoria só serve no verde",
           f"melhor={u.get('melhor')}, por cor="
           f"{ {k: v['taxa'] for k, v in (u.get('por_cor') or {}).items()} }")

    # teoria que funciona igual em qualquer cor: não pode ser rotulada
    regs2 = [janela(["T_IGUAL"], rnd.random() < 0.30,
                    {"cor": rnd.choice(["VERDE", "AMARELO", "VERMELHO"])})
             for _ in range(240)]
    u2 = (AX.examinar_teoria("T_IGUAL", regs2, 37).get("uso") or {})
    checar(u2.get("so_no_verde") is not True,
           "teoria que rende igual em toda cor não é rotulada de 'só no verde'",
           f"{ {k: v['taxa'] for k, v in (u2.get('por_cor') or {}).items()} }")

    # janelas antigas sem a cor gravada: tem de dizer que não sabe
    regs3 = [janela(["T_ANTIGA"], rnd.random() < 0.30, {}) for _ in range(40)]
    u3 = (AX.examinar_teoria("T_ANTIGA", regs3, 37).get("uso") or {})
    checar(u3.get("sabe") is False and "não guardaram" in (u3.get("nota") or ""),
           "janelas antigas sem contexto: diz que não sabe", u3.get("nota", ""))


# ══════════════════════════════════════ 5. a consequência: o peso da próxima volta
def teste_pesos_e_voz():
    print("\n[5] A CONSEQUÊNCIA — 'e se usar agora, e tomar decisões inteligentes'")
    rnd = random.Random(5)
    regs = []
    for _ in range(260):
        regs.append(janela(["BOA"], rnd.random() < 0.40, {"cor": "VERDE"}))
    for _ in range(260):
        regs.append(janela(["RUIM"], rnd.random() < 0.05, {"cor": "VERDE"}))
    for _ in range(260):
        regs.append(janela(["NEUTRA"], rnd.random() < (5 / 37), {"cor": "VERDE"}))
    ex = AX.examinar(regs, 37)
    p = AX.pesos(ex)
    checar(p.get("BOA", 0) > 1.0, "a teoria que bateu o acaso fala mais alto",
           f"peso {p.get('BOA')}")
    checar(p.get("RUIM", 9) < 1.0, "a que ficou abaixo fala mais baixo",
           f"peso {p.get('RUIM')}")
    checar("NEUTRA" not in p,
           "a que empatou com o acaso não tem o peso mexido",
           f"pesos: {p}")
    checar(all(0.4 <= v <= 2.0 for v in p.values()),
           "nenhum peso escapa da faixa [0.4, 2.0]", str(p))
    checar("BOA" in (ex.get("usar_mais") or []) and "RUIM" in (ex.get("usar_menos") or []),
           "e o veredito sai nomeado",
           f"mais={ex.get('usar_mais')} menos={ex.get('usar_menos')}")
    for L in AX.resumo(ex):
        print(f"        {L}")

    # nada fechado ainda
    vazio = AX.examinar([], 37)
    checar(AX.resumo(vazio) and "nenhuma" in " ".join(AX.resumo(vazio)).lower(),
           "sem janela nenhuma, diz que ainda não sabe",
           AX.resumo(vazio)[0][:90])


# ═════════════════════════════════ 6. qual teoria está em uso AGORA
def teste_em_uso():
    print("\n[6] 'QUAL TEORIA ESTÁ SENDO UTILIZADA COM BASE NOS 20 ÚLTIMOS GIROS'")
    hips = [{"nome": "ACADEMIA_A07", "nums": ["24", "12"], "peso": 1.8},
            {"nome": "SITUACAO", "nums": ["24", "18", "25"], "peso": 2.4},
            {"nome": "ESTRUTURA", "nums": ["12"], "peso": 0.9},
            {"nome": "VAZIA", "nums": [], "peso": 3.0}]
    sig = {"24": {"votos_teoria": 12, "votos_outros": 2},
           "12": {"votos_teoria": 9, "votos_outros": 1}}
    L = AX.em_uso_agora(hips, sig, ["24", "12"])
    txt = " ".join(L)
    checar("SITUACAO" in txt and "ACADEMIA_A07" in txt,
           "lista quem votou nesta volta")
    checar("VAZIA" not in txt,
           "e NÃO lista a teoria que não apontou nada — é essa diferença que ele "
           "quer ver")
    checar(L[1].startswith("[Em uso]   SITUACAO"),
           "ordena da que fala mais alto para a mais baixa", L[1][:60])
    checar("24←12 teorias" in txt, "e diz por quantos votos cada número venceu")
    for x in L:
        print(f"        {x}")
    vazio = AX.em_uso_agora([], None, None)
    checar("nenhuma teoria" in vazio[0],
           "sem teoria ativa, diz isso em vez de mostrar lista vazia",
           vazio[0][:80])


def main() -> int:
    print("═" * 72)
    print("AUTOEXAME — achar a causa plantada, e não inventar onde não há")
    print("═" * 72)
    teste_taxa()
    teste_causa_plantada()
    teste_sem_causa()
    teste_uso_correto()
    teste_pesos_e_voz()
    teste_em_uso()
    print("\n" + "═" * 72)
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"  ✗ {f}")
        return 1
    print("AUTOEXAME_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
