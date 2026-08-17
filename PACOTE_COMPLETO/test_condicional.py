# -*- coding: utf-8 -*-
"""
TESTE DO CONDICIONAL — "esta teoria serve aqui, aquela serve ali".

O RISCO, QUE AQUI É MAIOR QUE EM QUALQUER OUTRO ARQUIVO
───────────────────────────────────────────────────────
Teoria × condição é a estrutura mais propensa a overfitting de todo o software.
Vinte teorias por seis faixas são cento e vinte células; com quinhentas janelas,
quatro por célula. Escolher a melhor teoria de cada célula e depois medir na
MESMA amostra devolve razão alta em dado puramente sorteado -- foi assim que
`situacao.py` me deu 2,70x em ruído, e o erro era meu, não do dado.

Então o teste tem duas metades espelhadas:

    PLANTADO  a teoria A rende só com mesa cheia, a B só com mesa vazia.
              A tabela TEM de achar isso, e a validação fora da amostra TEM de
              dizer que vale.

    HONESTO   nenhuma teoria depende de condição nenhuma; acerto sorteado.
              A tabela pode até mostrar contraste por sorteio -- o que NÃO pode
              é a validação fora da amostra dizer que vale.

A segunda metade é a que importa. Uma tabela condicional que sempre diz "vale"
é pior que nenhuma: levaria a trocar de teoria por ruído, toda volta.
"""
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import condicional as CD          # noqa: E402

FALHAS = []


def checar(ok, titulo, detalhe=""):
    print(f"  {'ok  ' if ok else 'FALHA'} {titulo}" + (f"  — {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(titulo)
    return ok


def janela(teorias, acertou, ctx, k=5, quando=None) -> dict:
    return {"hips": list(teorias), "alvos": [str(i) for i in range(k)],
            "resultado": {"acertou": bool(acertou)},
            "contexto": dict(ctx),
            "em": (quando or datetime.now()).isoformat(timespec="seconds")}


# ═══════════════════════════════════ 1. as condições, grosseiras de propósito
def teste_condicoes():
    print("\n[1] AS CONDIÇÕES — poucas faixas, para o n não se desfazer")
    c = CD.condicoes_de({"publico": 1400, "seca_quantil": 0.9,
                         "acima_do_45": True, "magnitude": "baixos",
                         "em_hora": 22})
    checar(c.get("publico") == "cheia" and c.get("seca") == "longa"
           and c.get("densidade") == "muito_mult"
           and c.get("magnitude") == "baixos" and c.get("hora") == "noite",
           "lê as cinco condições do momento", str(c))
    checar(CD.condicoes_de({"publico": 300}).get("publico") == "vazia",
           "mesa de 300 pessoas é 'vazia'")
    checar(CD.condicoes_de({}) == {},
           "contexto vazio não inventa condição nenhuma")
    checar(CD.condicoes_de({"publico": "xx", "em_hora": None}) == {},
           "valor estragado não derruba nem inventa")

    # o recorte de dez dias
    velho = datetime.now() - timedelta(days=40)
    novo = datetime.now() - timedelta(hours=3)
    regs = [janela(["A"], True, {}, quando=velho),
            janela(["A"], True, {}, quando=novo),
            {"hips": ["A"], "resultado": {"acertou": True}}]   # sem data
    r = CD.recentes(regs, dias=10)
    checar(len(r) == 2, "pega os últimos 10 dias e mantém o registro sem data "
                        "(memória antiga não se joga fora por falta de campo)",
           f"{len(r)} de 3")


# ═════════════════════════════════════ 2. PLANTADO: A serve aqui, B serve ali
def mesa_condicional(n, rnd, forca=True):
    """A rende com mesa cheia, B rende com mesa vazia. Ou nada disso, se forca=False."""
    regs = []
    base = datetime.now() - timedelta(days=5)
    for i in range(n):
        cheia = rnd.random() < 0.5
        pub = rnd.gauss(1400, 120) if cheia else rnd.gauss(380, 100)
        ctx = {"publico": pub, "em_hora": rnd.randint(0, 23)}
        if forca:
            pA = 0.45 if cheia else 0.06
            pB = 0.06 if cheia else 0.45
        else:
            pA = pB = 0.20      # nenhuma depende de nada
        regs.append(janela(["TEORIA_A"], rnd.random() < pA, ctx,
                           quando=base + timedelta(minutes=i)))
        regs.append(janela(["TEORIA_B"], rnd.random() < pB, ctx,
                           quando=base + timedelta(minutes=i)))
    return regs


def teste_plantado():
    print("\n[2] PLANTADO — 'A funciona aqui, B funciona onde A não funcionou'")
    rnd = random.Random(17)
    regs = mesa_condicional(220, rnd, forca=True)
    tab = CD.tabela(regs, 37)
    a = (tab.get("TEORIA_A") or {}).get("publico") or {}
    b = (tab.get("TEORIA_B") or {}).get("publico") or {}
    checar(a.get("cheia", {}).get("razao", 0) > a.get("vazia", {}).get("razao", 9),
           "vê que A rende com mesa cheia e não com vazia",
           f"cheia {a.get('cheia',{}).get('razao')}x vs vazia "
           f"{a.get('vazia',{}).get('razao')}x")
    checar(b.get("vazia", {}).get("razao", 0) > b.get("cheia", {}).get("razao", 9),
           "e que B é o contrário — serve onde A falha",
           f"vazia {b.get('vazia',{}).get('razao')}x vs cheia "
           f"{b.get('cheia',{}).get('razao')}x")

    ctr = CD.contraste(tab)
    checar(len(ctr) >= 2 and all(c["confia"] for c in ctr[:2]),
           "declara o contraste das duas, além do ruído",
           "; ".join(f"{c['teoria']}: {c['boa_faixa']} {c['boa']['razao']}x "
                     f"z={c['z']}" for c in ctr[:2]))

    # ── a escolha na condição de AGORA ───────────────────────────────────
    ctr_p = CD.contraste(tab)
    esc_cheia = CD.escolher(tab, {"publico": "cheia"}, ctr_p)["pesos"]
    checar(esc_cheia.get("TEORIA_A", 0) > esc_cheia.get("TEORIA_B", 9),
           "com a mesa CHEIA agora, manda confiar em A", str(esc_cheia))
    esc_vazia = CD.escolher(tab, {"publico": "vazia"}, ctr_p)["pesos"]
    checar(esc_vazia.get("TEORIA_B", 0) > esc_vazia.get("TEORIA_A", 9),
           "com a mesa VAZIA agora, troca para B — é a substituição que ele pediu",
           str(esc_vazia))

    # ── A PROVA: a escolha vale no que ela não viu? ──────────────────────
    v = CD.validar(regs, 37)
    checar(v.get("mediu") and v.get("vale") is True,
           "fora da amostra: onde ela disse CONFIE rendeu mais que onde disse "
           "DESCONFIE",
           f"confie {v.get('razao_confie')}x (n={v.get('n_confie')}) vs "
           f"desconfie {v.get('razao_desconfie')}x (n={v.get('n_desconfie')}), "
           f"z={v.get('z')}, ganho {v.get('ganho')}x")


# ══════════════════════════ 3. O CONTROLE: honesto NÃO pode dizer que vale
def teste_honesto():
    print("\n[3] O CONTROLE — nenhuma teoria depende de condição: não pode 'valer'")
    valeu = 0
    tentativas = 25
    for semente in range(tentativas):
        rnd = random.Random(5000 + semente)
        regs = mesa_condicional(220, rnd, forca=False)
        v = CD.validar(regs, 37)
        if v.get("vale"):
            valeu += 1
    checar(valeu <= tentativas * 0.20,
           f"em {tentativas} mesas sem estrutura condicional, disse que vale "
           f"{valeu} vez(es)",
           f"{valeu}/{tentativas} = {valeu/tentativas:.0%}; o aceitável é ≤20%")

    # e o resumo tem de dizer que não vale, não ficar calado
    rnd = random.Random(99)
    regs = mesa_condicional(220, rnd, forca=False)
    r = CD.ler(regs, 37, contexto_agora={"publico": 1400, "em_hora": 21})
    txt = " ".join(CD.resumo(r))
    checar("NÃO VALE" in txt or "não é testável" in txt,
           "e diz em português que a escolha condicional não se sustenta",
           [L for L in CD.resumo(r) if "VALE" in L or "testável" in L][:1])

    # ── pouca janela: cala em vez de adivinhar ───────────────────────────
    curto = CD.ler([janela(["A"], True, {"publico": 1200}) for _ in range(8)], 37)
    checar(not curto["tabela"] and "não sei dizer" in " ".join(CD.resumo(curto)),
           "com 8 janelas não monta tabela e diz que não sabe",
           CD.resumo(curto)[0][:95])


# ══════════════════════ 4. teoria boa em tudo não é 'condicional'
def teste_nao_inventa_regra():
    print("\n[4] NÃO INVENTAR REGRA — teoria boa em toda condição não é condicional")
    rnd = random.Random(41)
    regs = []
    base = datetime.now() - timedelta(days=3)
    for i in range(300):
        cheia = rnd.random() < 0.5
        ctx = {"publico": rnd.gauss(1400, 120) if cheia else rnd.gauss(380, 100),
               "em_hora": rnd.randint(0, 23)}
        # rende 40% em QUALQUER condição
        regs.append(janela(["SEMPRE_BOA"], rnd.random() < 0.40, ctx,
                           quando=base + timedelta(minutes=i)))
    ctr = CD.contraste(CD.tabela(regs, 37))
    de_publico = [c for c in ctr if c["eixo"] == "publico" and c["confia"]]
    checar(not de_publico,
           "não declara contraste de público confiável onde não há",
           str([(c['boa_faixa'], c['boa']['razao'], c['z']) for c in ctr
                if c['eixo'] == 'publico']))

    # UMA SEMENTE NAO MEDE UM CORTE DE CONFIANCA. O que importa e a TAXA de
    # contraste inventado ao longo de muitas mesas honestas -- foi uma semente
    # sortuda que revelou o corte anterior (z=1,8) sendo generoso demais.
    inventou = 0
    tent = 30
    for sem in range(tent):
        r2 = random.Random(7000 + sem)
        rr = []
        b2 = datetime.now() - timedelta(days=3)
        for i in range(300):
            cheia = r2.random() < 0.5
            rr.append(janela(["SEMPRE_BOA"], r2.random() < 0.40,
                             {"publico": r2.gauss(1400, 120) if cheia
                              else r2.gauss(380, 100),
                              "em_hora": r2.randint(0, 23)},
                             quando=b2 + timedelta(minutes=i)))
        if [c for c in CD.contraste(CD.tabela(rr, 37)) if c["confia"]]:
            inventou += 1
    checar(inventou <= tent * 0.15,
           f"em {tent} mesas sem condicionalidade, inventou contraste "
           f"confiável {inventou} vez(es)",
           f"{inventou}/{tent} = {inventou/tent:.0%}; aceitável ≤15% testando "
           f"5 eixos por teoria")


# ═══════════════ 5. a autópsia do consenso: "foi consenso ou teoria única?"
def teste_formacao():
    print("\n[5] A AUTÓPSIA — 'usei teoria única ou consenso de vinte?'")
    rnd = random.Random(23)
    regs = []
    base = datetime.now() - timedelta(days=2)
    for i in range(120):
        # teoria única rende pouco
        regs.append(janela(["SO_UMA"], rnd.random() < 0.10, {"publico": 900},
                           quando=base + timedelta(minutes=i)))
    for i in range(120):
        # consenso largo rende bem
        muitas = [f"T{j}" for j in range(14)]
        regs.append(janela(muitas, rnd.random() < 0.40, {"publico": 900},
                           quando=base + timedelta(minutes=i)))
    f = CD.por_formacao(regs, 37)
    checar("teoria única" in f and "consenso largo (11+)" in f,
           "separa teoria única de consenso largo", str(list(f)))
    checar(f["consenso largo (11+)"]["razao"] > f["teoria única"]["razao"],
           "e mede qual dos dois rendeu mais, contra o acaso da mesma aposta",
           f"largo {f['consenso largo (11+)']['razao']}x vs única "
           f"{f['teoria única']['razao']}x")

    # ── E A PARTE QUE ELE FRISOU: "mas as vinte faziam sentido?" ─────────
    regs2 = []
    for i in range(150):
        muitas = [f"T{j}" for j in range(14)]
        serviam = rnd.random() < 0.5
        # consenso de teorias que serviam rende; das que não serviam, não
        p = 0.40 if serviam else 0.08
        regs2.append(janela(muitas, rnd.random() < p,
                            {"publico": 900,
                             "votantes_em_condicao": 12 if serviam else 1},
                            quando=base + timedelta(minutes=i)))
    f2 = CD.por_formacao(regs2, 37)
    serv = f2.get("consenso de teorias que serviam") or {}
    nao = f2.get("consenso de teorias que não serviam") or {}
    checar(serv.get("razao", 0) > nao.get("razao", 9),
           "distingue consenso de teorias que SERVIAM do consenso de vinte "
           "vozes erradas",
           f"serviam {serv.get('razao')}x (n={serv.get('n')}) vs não serviam "
           f"{nao.get('razao')}x (n={nao.get('n')})")

    for L in CD.resumo(CD.ler(regs2, 37, {"publico": 900, "em_hora": 15})):
        print(f"        {L}")


def main() -> int:
    print("═" * 72)
    print("CONDICIONAL — a teoria certa para a situação, com prova fora da amostra")
    print("═" * 72)
    teste_condicoes()
    teste_plantado()
    teste_honesto()
    teste_nao_inventa_regra()
    teste_formacao()
    print("\n" + "═" * 72)
    if FALHAS:
        print(f"{len(FALHAS)} FALHA(S):")
        for f in FALHAS:
            print(f"  ✗ {f}")
        return 1
    print("CONDICIONAL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
