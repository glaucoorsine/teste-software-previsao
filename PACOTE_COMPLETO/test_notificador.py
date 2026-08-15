# -*- coding: utf-8 -*-
"""Prova que o aviso de ntfy sai de verdade, sem depender do ntfy.sh.

Um servidor local finge ser o ntfy e guarda o que chegou. Se o titulo, o
corpo e os numeros aparecerem ali, o caminho ate o celular esta inteiro --
o que sobra e a internet e o app, que nao dependem deste codigo.
"""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

recebido = []

class Falso(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        recebido.append({"caminho": self.path,
                         "titulo": self.headers.get("Title"),
                         "prioridade": self.headers.get("Priority"),
                         "corpo": self.rfile.read(n).decode("utf-8")})
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass

srv = HTTPServer(("127.0.0.1", 8899), Falso)
threading.Thread(target=srv.serve_forever, daemon=True).start()

import notificador
import tempfile
notificador.CFG = Path(tempfile.mkdtemp()) / "notif_teste.json"
notificador.CFG.write_text(json.dumps({"canal": "ntfy", "topico": "lab-teste"}))

# aponta o envio para o servidor local
src = (RAIZ / "notificador.py").read_text(encoding="utf-8")
assert 'https://ntfy.sh/' in src, "endereco do ntfy mudou"
import requests
_post = requests.post
def post(url, *a, **k):
    return _post(url.replace("https://ntfy.sh/", "http://127.0.0.1:8899/"), *a, **k)
requests.post = post

# A FILA, NO RITMO DE TESTE.
#
# O notificador agora espaca os envios (ver INTERVALO_ENVIO_S): foi assim que
# as 1.058 falhas de 429 do log dele foram resolvidas. Num teste, esperar 6s
# por mensagem nao prova nada -- entao o ritmo cai para 50ms e o que se cobra
# passa a ser o CONTEUDO entregue, nao o instante da entrega.
notificador.INTERVALO_ENVIO_S = 0.05
notificador.ESPERA_MAX_S = 0.5
notificador._espera_atual = 0.05

def esperar_fila(limite=8.0):
    """Espera a fila esvaziar. Devolve True se esvaziou."""
    fim = time.time() + limite
    while time.time() < fim:
        if notificador.estado_fila()["na_fila"] == 0 and recebido:
            time.sleep(0.15)      # deixa o ultimo envio terminar
            return True
        time.sleep(0.05)
    return notificador.estado_fila()["na_fila"] == 0

def tudo():
    """Todo o texto que chegou no servidor, junto."""
    return "\n".join((r.get("titulo") or "") + "\n" + (r.get("corpo") or "")
                     for r in recebido)

falhas = []
def checa(c, nome, det=""):
    print(("  ok   " if c else "  FALHA ") + nome + ("" if c else f" {det}"))
    if not c: falhas.append(nome)

checa(notificador.ativo(), "canal ntfy reconhecido como pronto")

err = notificador._enviar("Laboratorio - teste", "corpo de teste")
checa(err is None, "envio direto sem erro", err)
checa(len(recebido) == 1, "chegou no servidor", len(recebido))
if recebido:
    r = recebido[0]
    checa(r["caminho"] == "/lab-teste", "topico certo na URL", r["caminho"])
    checa(r["corpo"] == "corpo de teste", "corpo intacto", r["corpo"])
    checa(r["prioridade"] == "high", "prioridade alta (toca no celular)")

recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_sinal("lightning", [4, 5, 9, 14], modo="OPERAR",
                            janela=4, extra="acerto 31% vs acaso 19% (1.63x)")
esperar_fila()
checa(len(recebido) == 1, "sinal virou aviso", len(recebido))
if recebido:
    txt = recebido[0]["corpo"] + " " + (recebido[0]["titulo"] or "")
    print("      titulo:", recebido[0]["titulo"])
    print("      corpo :", recebido[0]["corpo"])
    checa("4" in txt and "5" in txt and "9" in txt, "numeros no aviso")
    checa("1.63x" in txt or "31%" in txt, "taxa medida vai junto")
    checa(recebido[0]["titulo"] == "LIGHTNING - sinal",
          "titulo legivel, sem lixo de acento", recebido[0]["titulo"])
    checa(all(ord(c) < 128 for c in recebido[0]["titulo"]),
          "titulo cabe no cabecalho HTTP")

# antirrepeticao: o mesmo sinal em seguida nao pode virar segundo aviso
recebido.clear()
notificador.notificar_sinal("lightning", [4, 5, 9, 14], modo="OPERAR", janela=4,
                           extra="acerto 31% vs acaso 19% (1.63x)")
esperar_fila()
checa(len(recebido) == 0, "nao repete o mesmo sinal", len(recebido))



print("\n[6] o desfecho da janela tambem avisa")
recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_resultado("lightning", [4, 5, 9], True, saiu=5, giros=3,
                                placar="placar: 7 certas de 10 (70%)")
esperar_fila()
checa(len(recebido) == 1, "o acerto vira aviso", len(recebido))
if recebido:
    r = recebido[0]
    print("      titulo:", r["titulo"]); print("      corpo :", r["corpo"])
    checa("ACERTOU" in (r["titulo"] or ""), "diz que acertou", r["titulo"])
    checa("saiu: 5" in r["corpo"], "diz qual numero saiu")
    checa("4 5 9" in r["corpo"], "lembra qual era a aposta")
    checa("70%" in r["corpo"], "manda o placar junto")

print("\n[6b] os DOIS placares rotulados, e o publico da mesa")
recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_resultado(
    "mega_fire", [4, 5, 9], False, saiu=13, giros=5,
    placar="JANELAS: 7 certas | 3 erradas (70%)",
    placar_num="NÚMEROS: 9 certos | 41 errados (18%)",
    publico="pessoas: 940 — bom")
esperar_fila()
checa(len(recebido) == 1, "o aviso sai")
if recebido:
    corpo = recebido[0]["corpo"]
    print("      corpo :", corpo.replace("\n", " | "))
    checa("JANELAS:" in corpo and "NÚMEROS:" in corpo,
          "os dois placares vao rotulados -- da pra confundir sem rotulo", corpo)
    checa("7 certas" in corpo and "9 certos" in corpo,
          "e cada um com o seu numero, nao o do outro", corpo)
    checa("pessoas: 940 — bom" in corpo,
          "e o publico da mesa vai junto", corpo)

recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_sinal("crazy_time", ["5", "10"], modo="OPERAR", janela=5,
                            publico="pessoas: 4200 — ruim")
esperar_fila()
checa(recebido and "pessoas: 4200 — ruim" in recebido[0]["corpo"],
      "o sinal tambem leva o publico", recebido and recebido[0]["corpo"])

print("\n[6c] o fogo vai no aviso, e a immersive nao recebe linha nenhuma")
recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_sinal("mega_fire", [4, 9, 17, 21, 30], janela=5,
                            multiplicador="🔥 chance de vir multiplicador: 9 21")
esperar_fila()
checa(recebido and "🔥" in recebido[0]["corpo"],
      "o sinal leva quais podem vir multiplicados",
      recebido and recebido[0]["corpo"])
recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_sinal("immersive", [4, 9, 17], janela=5,
                            multiplicador="")
esperar_fila()
checa(recebido and "🔥" not in recebido[0]["corpo"],
      "e a immersive nao ganha linha de fogo -- a mesa nao tem",
      recebido and recebido[0]["corpo"])

recebido.clear()
notificador.notificar_resultado("crazy_time", ["5"], False, saiu="1", giros=3)
esperar_fila()
checa(len(recebido) == 1, "o erro tambem avisa")
if recebido:
    checa("errou" in (recebido[0]["titulo"] or ""), "e diz que errou",
          recebido[0]["titulo"])

# o antirrepeticao nao pode engolir um desfecho
recebido.clear()
for _ in range(3):
    notificador.notificar_resultado("lightning", [1], False, saiu="9", giros=3)
esperar_fila()
checa(len(recebido) == 3,
      "desfecho nunca e engolido pelo antirrepeticao — cada janela e um evento",
      len(recebido))

print("\n[7] o 429 NAO perde mensagem -- o defeito do log dele")
# No log de 9h30 da v96: 1.058 falhas, todas 429, e cada uma era uma mensagem
# jogada fora. Aqui o servidor recusa as tres primeiras e aceita depois; as
# tres mensagens tem que chegar assim mesmo.
recusar = {"quantas": 3}
_post_ok = requests.post
def post_429(url, *a, **k):
    if recusar["quantas"] > 0:
        recusar["quantas"] -= 1
        class R:
            status_code = 429
            headers = {"Retry-After": "0"}
            def raise_for_status(self): pass
        return R()
    return _post_ok(url, *a, **k)
requests.post = post_429

recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador._espera_atual = 0.05
notificador._ritmo_avisado = False
avisos_log = []
notificador.notificar_resultado("mega_fire", [7], True, saiu=7, giros=2,
                                log_fn=avisos_log.append)
esperar_fila(limite=10.0)
requests.post = post_429                      # segue com o falso
checa(recebido, "depois de tres recusas, a mensagem chega", len(recebido))
checa("saiu: 7" in tudo(), "e chega inteira, nao truncada", tudo()[:80])
checa(any("ritmo" in x for x in avisos_log),
      "e o log explica que e ritmo, nao erro de configuracao", avisos_log)
requests.post = _post_ok

print("\n[8] com a fila cheia, as mensagens saem juntas em vez de sumir")
recebido.clear()
notificador._espera_atual = 0.05
for i in range(8):
    notificador.notificar_resultado("lightning", [i], i % 2 == 0, saiu=i, giros=2)
esperar_fila(limite=10.0)
txt = tudo()
chegaram = sum(1 for i in range(8) if f"saiu: {i}" in txt)
print(f"       8 desfechos -> {len(recebido)} mensagens, {chegaram} desfechos dentro")
checa(chegaram == 8, "os oito desfechos chegam, agrupados ou nao", chegaram)
checa(len(recebido) <= 8, "e sem gastar mais requisicoes que mensagens",
      len(recebido))

srv.shutdown()
print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("NTFY_OK")
