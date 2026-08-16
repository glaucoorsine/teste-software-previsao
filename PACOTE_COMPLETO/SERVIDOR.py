# -*- coding: utf-8 -*-
"""
SERVIDOR — o software inteiro servindo a previsão para o navegador.

    python SERVIDOR.py
    python SERVIDOR.py --porta 8000 --mesas lightning,crazy_time

Depois é só abrir no Chrome, de qualquer aparelho da casa:

    http://SEU-IP:8000

O endereço certo aparece impresso quando o servidor sobe.

POR QUE ASSIM, E NÃO UM HTML SOLTO
──────────────────────────────────
    "É uma coisa automática, o HTML era pra ser automático, uma cópia do
     software. Eu não vou ficar marcando nada."

Ele tem razão -- e a primeira tentativa foi um erro meu. Um HTML aberto
direto do arquivo não consegue ler as APIs do provedor: o navegador bloqueia
leitura entre domínios diferentes a menos que o servidor de lá autorize, e não
há como eu garantir daqui que ele autoriza.

Aqui não tem esse problema, e tem uma vantagem maior: a previsão é calculada
pelo NÚCLEO EM PYTHON, o mesmo do `PREVER.py`. Não é uma reescrita em
JavaScript que pode divergir -- é o mesmo código, com as 44 famílias dele, o
canal anunciado, o consenso IA12 e a régua com veto. O navegador só desenha.

O QUE ACONTECE SOZINHO
──────────────────────
    · uma linha de captura por mesa, em segundo plano, sem parar
    · a previsão é recalculada quando chega giro novo
    · o carimbo garante que ela foi feita ANTES do giro que a julga
    · o placar e o veredito da régua atualizam junto
    · a página busca o estado a cada poucos segundos

Nada para marcar. É o software rodando, com a tela do lado de fora.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import PREVER as P  # noqa: E402
from NUCLEO import base as B  # noqa: E402

MESAS_PADRAO = ["lightning", "mega_fire", "crazy_time"]
PAGINA = RAIZ / "painel.html"

_lock = threading.Lock()
ESTADO: Dict[str, Dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════ o laço por mesa

def girar(mesa: str, k: int, intervalo: int) -> None:
    """Captura, prevê, carimba, e fecha a rodada quando o giro chega.

    É o mesmo laço do PREVER.py. A diferença é que o resultado vai para
    `ESTADO` em vez da tela, e o navegador lê de lá.
    """
    from fluxo_captura import capturar

    placar = P.Placar(B.classes_de(mesa))
    pendente = None
    ultimo_erro = ""

    while True:
        try:
            cap = capturar(mesa, duration=60)
            rows = cap.get("rows") or []
            ultimo_erro = cap.get("err") or ""
        except Exception as e:
            rows, ultimo_erro = [], f"{type(e).__name__}: {e}"

        if rows:
            topo = str(rows[0].get("event_id") or rows[0].get("id") or "")

            # fecha a rodada anterior, se o giro é mesmo posterior ao carimbo
            if pendente and topo and topo != pendente["carimbo"]:
                alvo = rows[0].get("n", rows[0].get("sec"))
                ids = [str(r.get("event_id") or r.get("id") or "") for r in rows]
                if pendente["carimbo"] in ids[1:]:
                    acertou = placar.registrar(pendente["numeros"], str(alvo),
                                               pendente["palpites"])
                    with _lock:
                        ESTADO.setdefault(mesa, {})["ultimo"] = {
                            "saiu": str(alvo), "acertou": acertou,
                            "previa": pendente["numeros"],
                            "quando": datetime.now().strftime("%H:%M:%S")}
                else:
                    placar.descartadas += 1
                pendente = None

            # faz a próxima, e carimba
            if pendente is None:
                try:
                    p = P.prever(rows, mesa, k, placar)
                except Exception as e:
                    p = {"numeros": [], "erro": f"{type(e).__name__}: {e}"}
                if p.get("numeros"):
                    pendente = {"numeros": p["numeros"],
                                "palpites": p.get("palpites") or {},
                                "carimbo": topo}
                    with _lock:
                        ESTADO.setdefault(mesa, {}).update(
                            instantaneo(mesa, p, placar))
                else:
                    with _lock:
                        ESTADO.setdefault(mesa, {}).update({
                            "mesa": mesa, "numeros": [],
                            "aguardando": p.get("erro")
                            or f"aquecendo — {p.get('n_giros', 0)} giros lidos"})

        with _lock:
            ESTADO.setdefault(mesa, {})["erro"] = ultimo_erro
            ESTADO[mesa]["atualizado"] = datetime.now().strftime("%H:%M:%S")
        time.sleep(intervalo)


def instantaneo(mesa: str, p: Dict[str, Any], placar: P.Placar) -> Dict[str, Any]:
    """O que a tela precisa saber, já mastigado — inclusive o veredito."""
    lo, hi = placar.intervalo()
    c = placar.constituicao() if placar.rodadas >= 5 else None
    fontes = {}
    for n in p["numeros"][:12]:
        quem = (p.get("quem") or {}).get(n, [])
        fam = quem[0].replace("CANAL_", "") if quem else ""
        fontes[n] = {"n": len(quem),
                     "robustez": (p.get("robustez") or {}).get(n, 0),
                     "onde": B.endereco(fam, mesa) if fam else ""}
    canal = p.get("canal") or {}
    return {
        "mesa": mesa, "aguardando": "",
        "numeros": p["numeros"],
        "fontes": fontes,
        "n_giros": p.get("n_giros", 0),
        "roda": {"falaram": (p.get("roda") or {}).get("apontaram", 0),
                 "total": (p.get("roda") or {}).get("total", 0)},
        "canal": {"vota": bool(canal.get("vota")),
                  "motivo": (canal.get("motivo") or "")[:110],
                  "acoplamento": round(float((canal.get("acoplamento") or {})
                                             .get("razao") or 0), 2)},
        "placar": {
            "acertos": placar.acertos, "rodadas": placar.rodadas,
            "taxa": placar.taxa, "acaso": placar.acaso,
            "razao": placar.razao, "lo": lo, "hi": hi,
            "descartadas": placar.descartadas,
            "veredito": placar.veredito() if placar.rodadas else "",
            "regua": (c["decisao"]["decisao"] if c else ""),
            "porque": (c["decisao"]["porque"][:140] if c else ""),
            "suporte": (c["previsoes"]["motivo"][:110] if c else ""),
        },
    }


# ═══════════════════════════════════════════════════════════ o servidor

class Painel(BaseHTTPRequestHandler):
    def log_message(self, *a):            # sem ruído no terminal dele
        pass

    def _envia(self, corpo: bytes, tipo: str, cache=False):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path.startswith("/estado"):
            with _lock:
                corpo = json.dumps(ESTADO, ensure_ascii=False).encode("utf-8")
            self._envia(corpo, "application/json; charset=utf-8")
            return
        if not PAGINA.is_file():
            self._envia(b"painel.html nao encontrado", "text/plain; charset=utf-8")
            return
        self._envia(PAGINA.read_bytes(), "text/html; charset=utf-8")


def meu_ip() -> str:
    """O IP da máquina na rede local — é por ele que o celular chega aqui."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> int:
    ap = argparse.ArgumentParser(description="O software servindo o navegador.")
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--k", type=int, default=10, help="números por previsão")
    ap.add_argument("--intervalo", type=int, default=15, help="segundos entre capturas")
    ap.add_argument("--mesas", default=",".join(MESAS_PADRAO))
    a = ap.parse_args()

    mesas = [m.strip() for m in a.mesas.split(",") if m.strip()]
    print()
    print(B.resumo())
    print()
    for m in mesas:
        threading.Thread(target=girar, args=(m, a.k, a.intervalo),
                         daemon=True).start()
        print(f"  capturando {m} a cada {a.intervalo}s")

    ip = meu_ip()
    print()
    print("  ┌" + "─" * 52 + "┐")
    print(f"  │  Abra no Chrome:                                   │")
    print(f"  │      neste computador   http://localhost:{a.porta:<11}│")
    print(f"  │      no celular         http://{ip}:{a.porta:<11}".ljust(55) + "│")
    print("  └" + "─" * 52 + "┘")
    print()
    print("  O celular precisa estar no mesmo wi-fi. Ctrl+C encerra.")
    print()

    srv = ThreadingHTTPServer(("0.0.0.0", a.porta), Painel)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  encerrado.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
