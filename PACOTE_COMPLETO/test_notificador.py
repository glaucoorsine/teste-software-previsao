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
for _ in range(60):
    if recebido: break
    time.sleep(0.05)
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
time.sleep(0.6)
checa(len(recebido) == 0, "nao repete o mesmo sinal", len(recebido))



print("\n[6] o desfecho da janela tambem avisa")
recebido.clear()
notificador._ultimo.update({"quando": 0.0, "texto": ""})
notificador.notificar_resultado("lightning", [4, 5, 9], True, saiu=5, giros=3,
                                placar="placar: 7 certas de 10 (70%)")
for _ in range(60):
    if recebido: break
    time.sleep(0.05)
checa(len(recebido) == 1, "o acerto vira aviso", len(recebido))
if recebido:
    r = recebido[0]
    print("      titulo:", r["titulo"]); print("      corpo :", r["corpo"])
    checa("ACERTOU" in (r["titulo"] or ""), "diz que acertou", r["titulo"])
    checa("saiu: 5" in r["corpo"], "diz qual numero saiu")
    checa("4 5 9" in r["corpo"], "lembra qual era a aposta")
    checa("70%" in r["corpo"], "manda o placar junto")

recebido.clear()
notificador.notificar_resultado("crazy_time", ["5"], False, saiu="1", giros=3)
for _ in range(60):
    if recebido: break
    time.sleep(0.05)
checa(len(recebido) == 1, "o erro tambem avisa")
if recebido:
    checa("errou" in (recebido[0]["titulo"] or ""), "e diz que errou",
          recebido[0]["titulo"])

# o antirrepeticao nao pode engolir um desfecho
recebido.clear()
for _ in range(3):
    notificador.notificar_resultado("lightning", [1], False, saiu="9", giros=3)
time.sleep(0.6)
checa(len(recebido) == 3,
      "desfecho nunca e engolido pelo antirrepeticao — cada janela e um evento",
      len(recebido))

srv.shutdown()
print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("NTFY_OK")
