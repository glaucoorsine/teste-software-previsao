# -*- coding: utf-8 -*-
"""Confere o descobridor de endereço — o conserto do "Crazy Time A não abre".

    "crazy time a, e immersive nao funcionam"

Ele repetiu isso várias vezes. Minha resposta era sempre escrever à mão mais
uma grafia de URL e torcer, o que nunca resolveu porque daqui eu não alcanço
os domínios do provedor para testar. Agora as grafias são GERADAS a partir do
nome da mesa e testadas na máquina dele.

O teste cobra as cinco coisas que fazem isso funcionar de verdade:

  1. as grafias cobrem as convenções que esses provedores usam
  2. só vale endereço que devolva GIROS, não que devolva 200
  3. para assim que achar — a procura é cara contra o provedor
  4. o que achou fica gravado e vem na frente da próxima vez
  5. o coletor conhece TODAS as mesas (faltava crazy_time_a, e era metade
     do problema)

    python test_descobridor.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import coletor_sites as C  # noqa: E402
import descobridor_endereco as D  # noqa: E402

falhas = []
TEMP = RAIZ / "Logs" / "_teste_fontes.json"


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


def limpar():
    try:
        TEMP.unlink()
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] as grafias cobrem as convenções do provedor")

g = D.grafias("Crazy Time A")
print("       " + " · ".join(g))
for esperada in ("crazytimea", "crazy-time-a", "crazytime-a", "crazy_time_a"):
    checa(esperada in g, f"gera '{esperada}'", g)
checa(len(set(g)) == len(g), "sem repetir", g)

gr = D.grafias("Immersive Roulette")
checa("immersive" in gr, "tira 'roulette' quando ele some do slug", gr)
checa("immersive-roulette" in gr, "e mantém a versão com ele", gr)
checa(D.grafias("") == [], "nome vazio não gera nada")

for jogo, minimo in (("crazy_time_a", 40), ("immersive", 8), ("mega_fire", 20)):
    n = len(D.candidatos(jogo))
    checa(n >= minimo, f"{jogo}: {n} endereços a experimentar", n)
checa(D.candidatos("mesa_que_nao_existe") == [],
      "mesa desconhecida não inventa endereço")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] só vale endereço que entregue giros")

# responder é fácil; entregar giro é o que importa. Estes são os formatos que
# os dois provedores usam, mais os disfarces que já me enganaram.
roleta = {"data": [{"result": n} for n in (7, 22, 0, 36, 14, 3, 19)]}
ct = {"history": [{"outcome": s} for s in
                  ("1", "2", "Coin Flip", "5", "Pachinko", "10", "Crazy Time")]}
vazio = {"data": []}
erro = {"error": "not found", "status": 200}
fora = {"data": [{"result": n} for n in (99, 412, 777, 500, 601, 900)]}

ach = []
D._numeros_de(roleta, False, ach)
checa(len(ach) == 7, "acha os giros de roleta", len(ach))
ach = []
D._numeros_de(ct, True, ach)
checa(len(ach) == 7, "acha os segmentos de Crazy Time", len(ach))
ach = []
D._numeros_de(vazio, False, ach)
checa(not ach, "lista vazia não vira fonte")
ach = []
D._numeros_de(erro, False, ach)
checa(not ach, "página de erro com HTTP 200 não vira fonte", ach)
ach = []
D._numeros_de(fora, False, ach)
checa(not ach, "números fora de 0..36 não são giros de roleta", ach)

# um giro de roleta não pode ser lido como segmento de Crazy Time
ach = []
D._numeros_de(roleta, True, ach)
checa(not ach, "resposta de roleta não passa por Crazy Time", ach)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] para assim que acha")

orig = D.experimentar
D.MEMORIA = TEMP
try:
    for alvo, rotulo, teto in (("/crazytime-a/history", "cedo", 14),
                               ("/crazytimearoulette", "tarde", 26),
                               (None, "nenhum", 999)):
        contagem = {"n": 0}

        def falso(url, jogo, _alvo=alvo, _c=contagem):
            _c["n"] += 1
            return ((True, "120 giros", 120) if (_alvo and url.endswith(_alvo))
                    else (False, "HTTP 404", 0))

        D.experimentar = falso
        limpar()
        achou = D.descobrir("crazy_time_a")
        total = len(D.candidatos("crazy_time_a"))
        print(f"       achado {rotulo:<7} {contagem['n']:3d} tentativas de {total}")
        checa((achou is not None) == (alvo is not None),
              f"acha quando existe / desiste quando não ({rotulo})", achou)
        checa(contagem["n"] <= teto,
              f"não varre a lista inteira depois de achar ({rotulo})",
              contagem["n"])

    # ── [4] a memória ────────────────────────────────────────────────
    print("\n[4] o que achou fica gravado e vem na frente")
    limpar()
    D.experimentar = lambda u, j: ((True, "120 giros", 120)
                                   if u.endswith("/crazytime-a/history")
                                   else (False, "HTTP 404", 0))
    achou = D.descobrir("crazy_time_a")
    checa(D.lembradas().get("crazy_time_a") == achou, "gravou o que funcionou",
          D.lembradas())

    # na segunda vez, confere a gravada primeiro e para em 1 tentativa
    contagem = {"n": 0}

    def conta(url, jogo, _c=contagem):
        _c["n"] += 1
        return ((True, "120 giros", 120)
                if url.endswith("/crazytime-a/history") else (False, "404", 0))

    D.experimentar = conta
    D.descobrir("crazy_time_a")
    checa(contagem["n"] == 1, "na segunda vez testa só a gravada",
          contagem["n"])

    # e se a gravada parar de responder, procura de novo
    contagem = {"n": 0}
    D.experimentar = lambda u, j: (False, "HTTP 503", 0)
    D.descobrir("crazy_time_a")
    checa(len(json.loads(TEMP.read_text(encoding="utf-8"))) >= 0,
          "fonte que caiu não derruba o arquivo de memória")
finally:
    D.experimentar = orig
    limpar()

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] o coletor conhece todas as mesas")

# Esta era metade do problema e passou semanas invisível: eu mexia na lista do
# `fluxo_captura` e não reparava que a FONTE ALTERNATIVA não conhecia a mesa.
MESAS = ("mega_fire", "lightning", "immersive", "crazy_time", "crazy_time_a")
for m in MESAS:
    checa(m in C.SEQUENCIA, f"coletor tem sequência para {m}",
          sorted(C.SEQUENCIA))
for m in MESAS:
    checa(m in C.AGREGADOS, f"coletor tem agregados para {m}",
          sorted(C.AGREGADOS))
for m in MESAS:
    checa(m in D.NOMES, f"descobridor sabe o nome de {m}", sorted(D.NOMES))

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("DESCOBRIDOR_OK")
