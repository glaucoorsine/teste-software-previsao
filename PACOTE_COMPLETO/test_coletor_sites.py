# -*- coding: utf-8 -*-
"""Confere o coletor sem depender dos sites, com respostas de mentira.

O que motivou este arquivo foi um KeyError na tela: o Crazy Time devolve um
formato diferente do da roleta, o resumo assumia o da roleta, e a aba inteira
caía — levando junto as três mesas que tinham respondido.

    python test_coletor_sites.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import coletor_sites as CS  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


class Resposta:
    def __init__(self, status=200, dados=None, texto=""):
        self.status_code = status
        self._dados = dados
        self.text = texto

    def json(self):
        if self._dados is None:
            raise ValueError("não é JSON")
        return self._dados


print("\n[1] o resumo aguenta cada formato de mesa")

roleta = {"jogo": "lightning",
          "sequencia": [{"n": 7, "settled": "t", "tags": [{"lucky": [1]}]},
                        {"n": 3, "settled": "u", "tags": []}],
          "agregados": {"total_giros": 1767, "total_premiacoes": 4743,
                        "por_numero": {str(i): {"saiu": i} for i in range(37)}},
          "avisos": []}
t = CS.resumo(roleta)
print("       ", t.replace("\n", "\n        "))
checa("4743 premiações em 1767 giros" in t, "roleta mostra premiações", t)
checa("37 números" in t, "roleta mostra a contagem por número", t)
checa("1 giros trazem a rodada de multiplicadores" in t,
      "conta os giros com multiplicador", t)

# Este é o que quebrava: sem total_premiacoes, com símbolos e top slot.
ct = {"jogo": "crazy_time",
      "sequencia": [],
      "agregados": {"total_giros": 4000,
                    "por_simbolo": {"1": {"saiu": 900}, "2": {"saiu": 500},
                                    "5": {"saiu": 300},
                                    "pachinko": {"saiu": 80}},
                    "top_slot": {"1": {"sorteado": 40, "bateu": 3}},
                    "top_slot_multi": {"2x": {"sorteado": 10, "bateu": 1}},
                    "coinflip": {"azul": 12, "vermelho": 9}},
      "avisos": []}
try:
    t2 = CS.resumo(ct)
    quebrou = None
except Exception as e:
    t2, quebrou = "", f"{type(e).__name__}: {e}"
print("       ", t2.replace("\n", "\n        "))
checa(quebrou is None, "Crazy Time não levanta KeyError", quebrou)
checa("4000 giros" in t2, "mostra o total mesmo sem premiações", t2)
checa("símbolos:" in t2, "mostra os símbolos, que é o que essa mesa tem", t2)
checa("top slot" in t2, "mostra o top slot", t2)
checa("coinflip" in t2, "mostra o coinflip", t2)

vazio = {"jogo": "mega_fire", "sequencia": [], "agregados": {},
         "avisos": ["sem endpoint de sequência para este jogo"]}
t3 = CS.resumo(vazio)
checa("0 giros" in t3 and "aviso:" in t3, "mesa sem fonte não quebra", t3)

print("\n[2] tenta os endereços até um responder")
CS.MEMORIA = Path(RAIZ) / "Logs" / "_teste_fontes.json"
CS.MEMORIA.unlink(missing_ok=True)

pedidos = []
BOM = "https://api.trackpotapi.com/api/trackersino/megafireblazeroulette/history"


class RequestsFalso:
    @staticmethod
    def get(url, **k):
        pedidos.append(url)
        if url == BOM:
            return Resposta(200, {"data": [
                {"result": 7, "settled_at": "2026-08-14T10:00:00Z"},
                {"result": 12, "settled_at": "2026-08-14T10:01:00Z"}]})
        return Resposta(404)


CS.requests = RequestsFalso
linhas, aviso = CS.buscar_sequencia("mega_fire")
checa(len(linhas) == 2, "achou os giros no endereço que responde", len(linhas))
checa(len(pedidos) > 1, "tentou mais de um endereço antes", pedidos)
checa(BOM in pedidos, "chegou no endereço bom")

print("\n[3] o que funcionou é lembrado")
gravado = json.loads(CS.MEMORIA.read_text(encoding="utf-8"))
checa(gravado.get("mega_fire:seq") == BOM, "gravou o endereço certo", gravado)
pedidos.clear()
linhas2, _ = CS.buscar_sequencia("mega_fire")
checa(len(linhas2) == 2, "achou de novo")
checa(pedidos and pedidos[0] == BOM,
      "e foi direto nele, sem refazer a busca", pedidos)

print("\n[4] quando nenhum responde, o aviso diz o que foi tentado")


class TudoFora:
    @staticmethod
    def get(url, **k):
        return Resposta(404)


CS.MEMORIA.unlink(missing_ok=True)
CS.requests = TudoFora
linhas3, aviso3 = CS.buscar_sequencia("mega_fire")
checa(linhas3 == [], "não inventa giro")
checa("nenhum endereço respondeu" in (aviso3 or ""), "avisa com clareza", aviso3)
checa("404" in (aviso3 or ""), "e diz o que cada um respondeu", aviso3)

print("\n[5] uma mesa fora do ar não derruba as outras")
CS.requests = RequestsFalso
saidas = []
for jogo in ("lightning", "mega_fire", "immersive", "crazy_time"):
    try:
        saidas.append(CS.resumo(CS.coletar(jogo)))
    except Exception as e:
        saidas.append(f"QUEBROU: {type(e).__name__}: {e}")
checa(not any(s.startswith("QUEBROU") for s in saidas),
      "as quatro passam pelo coletor sem exceção",
      [s[:60] for s in saidas if s.startswith("QUEBROU")])
checa(len(saidas) == 4, "todas responderam alguma coisa")

CS.MEMORIA.unlink(missing_ok=True)
print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("COLETOR_OK")
