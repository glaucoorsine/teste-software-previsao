# -*- coding: utf-8 -*-
"""
PAINEL — a tela única do software. É isto que o ABRIR.bat abre.

POR QUE ISTO EXISTE, E O QUE ELE ME DISSE
─────────────────────────────────────────
    "NÃO TEM LAYOUT, TÁ HORRÍVEL ACESSIBILIDADE, NÃO TEM EXPLICAÇÕES, (…)
     NÃO SEI NEM QUAL CLICÁVEL ABRIR, POR QUE NÃO PÕE TUDO EM UM ARQUIVO DE
     ABERTURA SÓ, ABAS DAS LOTERIAS E TUDO MAIS"

Ele tem razão nos seis pontos. Eu tinha entregue linha de comando e cinco `.bat`
— software para programador, não para usar. Um botão por função, sem tela, sem
explicação, e ele com razão sem saber onde clicar.

POR QUE NAVEGADOR E NÃO UMA JANELA DE PROGRAMA
──────────────────────────────────────────────
Por causa da acessibilidade, que foi a cobrança mais séria dele. No navegador o
leitor de tela funciona, o zoom funciona, o contraste alto do Windows funciona,
e navegar só pelo teclado funciona — tudo isso de graça e testado por milhões de
pessoas. Numa janela feita com tkinter, nada disso funciona direito, e eu não
teria como consertar.

O programa sobe um servidor em 127.0.0.1 — a própria máquina dele. Nada sai para
a internet, nada entra. É só a maneira de desenhar a tela.

O DESENHO DA COISA
──────────────────
Uma tarefa lenta não pode congelar a tela. O fechamento leva segundos, e puxar o
histórico leva minutos — se a tela travasse, ele fecharia a janela achando que
quebrou (e teria feito bem). Então toda tarefa demorada roda numa linha de
trabalho separada e a tela pergunta "como vai?" de tempos em tempos, mostrando o
progresso. É por isso que existe o registro de tarefas aqui embaixo.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import traceback
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
PAINEL = RAIZ / "painel"

from NUCLEO import api as API                      # noqa: E402
from NUCLEO import base_conhecimento as BC         # noqa: E402
from NUCLEO import conferencia as CO               # noqa: E402
from NUCLEO import fechamento as FE                # noqa: E402
from NUCLEO import formular as FO                  # noqa: E402
from NUCLEO import historico as HI                 # noqa: E402
from NUCLEO import medidor as MD                   # noqa: E402
from NUCLEO import regras as RG                    # noqa: E402

# ═══════════════════════════════════════════════ as tarefas demoradas
_TAREFAS: Dict[str, Dict[str, Any]] = {}
_TRAVA = threading.Lock()


def _nova_tarefa(alvo: Callable[[Callable[[str], None]], Any]) -> str:
    """Roda `alvo` numa linha separada; devolve o número para acompanhar.

    O `alvo` recebe uma função `diga` para ir contando o que está fazendo. Sem
    isso, uma tarefa de três minutos seria uma tela parada de três minutos, que
    é indistinguível de uma tela quebrada.
    """
    ident = uuid.uuid4().hex[:12]
    with _TRAVA:
        _TAREFAS[ident] = {"estado": "correndo", "linhas": [], "resultado": None,
                           "erro": ""}

    def diga(linha: str) -> None:
        with _TRAVA:
            _TAREFAS[ident]["linhas"].append(str(linha))

    def correr() -> None:
        try:
            r = alvo(diga)
            with _TRAVA:
                _TAREFAS[ident]["resultado"] = r
                _TAREFAS[ident]["estado"] = "pronto"
        except Exception as e:
            with _TRAVA:
                _TAREFAS[ident]["erro"] = f"{type(e).__name__}: {e}"
                _TAREFAS[ident]["estado"] = "erro"
            traceback.print_exc()

    threading.Thread(target=correr, daemon=True).start()
    return ident


# ═══════════════════════════════════════════════════ o que a tela pede
def _jogos() -> List[dict]:
    saida = []
    for chave, j in RG.JOGOS.items():
        p = j.p_faixa(j.minimo, j.faixas[0])
        saida.append({
            "chave": chave, "nome": j.nome, "universo": j.universo,
            "sorteadas": j.sorteadas, "minimo": j.minimo, "maximo": j.maximo,
            "faixas": list(j.faixas), "primeiro": j.primeiro_numero,
            "nota": j.nota, "conferido": j.conferido,
            "acaso_minimo": (1 / p) if p else 0,
            "tem_historico": API.caminho_cache(chave).exists(),
        })
    return saida


def _detalhe(chave: str) -> dict:
    j = RG.jogo(chave)
    if not j:
        return {"erro": f"não conheço {chave}"}
    from math import comb
    linhas = []
    base = None
    for k in range(j.minimo, min(j.maximo, j.minimo + 9) + 1):
        custo = comb(k, j.minimo)
        p = j.p_faixa(k, j.faixas[0])
        razao = p / custo if custo else 0
        if base is None:
            base = razao
        linhas.append({
            "k": k, "custo": custo,
            "uma_em": (1 / p) if p else 0,
            "algum_premio": j.p_algum_premio(k),
            "razao": razao,
            "razao_igual": bool(base and abs(razao / base - 1) < 1e-9),
        })
    return {
        "chave": chave, "nome": j.nome, "universo": j.universo,
        "sorteadas": j.sorteadas, "minimo": j.minimo, "maximo": j.maximo,
        "faixas": list(j.faixas), "primeiro": j.primeiro_numero,
        "nota": j.nota, "conferido": j.conferido,
        "dezenas": j.dezenas(),
        "acertos_medios": j.acertos_esperados(j.minimo),
        "custo": linhas,
        "fora_do_molde": RG.FORA_DO_MOLDE,
    }


def _base(chave: str = "") -> List[dict]:
    rotulos = {BC.MATEMATICA: "Matemática demonstrada",
               BC.DELE: "Teoria sua", BC.MINHA: "Hipótese minha",
               BC.CRENCA: "Crença comum — a medir"}
    saida = []
    for it in BC.tudo(chave or None):
        d = it.como_dict()
        d["rotulo_origem"] = rotulos.get(it.origem, it.origem)
        d["autorizada"] = BC.autorizada(it.id)
        d["medivel"] = it.id in MD.MEDIDORES
        saida.append(d)
    return saida


def _historico_de(chave: str) -> Optional[HI.Historico]:
    p = API.caminho_cache(chave)
    if not p.exists():
        return None
    h, _avisos = HI.de_arquivo(p, chave, fonte=f"API: {API.carregar_fonte().get('nome')}")
    return h


def _estado_historico(chave: str) -> dict:
    p = API.caminho_cache(chave)
    if not p.exists():
        return {"tem": False,
                "nota": "ainda não há resultados no disco para esta loteria"}
    h = _historico_de(chave)
    if h is None:
        return {"tem": False, "nota": f"há um arquivo em {p.name} mas eu não "
                                      f"consegui lê-lo"}
    return {"tem": True, "n": len(h), "conferido": h.conferido,
            "problemas": h.problemas, "arquivo": str(p),
            "tem_ganhadores": h.tem_ganhadores(),
            "diagnostico": h.diagnostico(),
            "primeiro": h.concursos[0] if h.concursos else None,
            "ultimo": h.concursos[-1] if h.concursos else None}


# ═══════════════════════════════════════════════════════ o servidor
class Mao(BaseHTTPRequestHandler):
    server_version = "Loteria/1.0"

    def log_message(self, *a):
        pass                      # a janela preta não é lugar de log de HTTP

    # ── utilidades ────────────────────────────────────────────────────
    def _json(self, dados: Any, codigo: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _arquivo(self, caminho: Path) -> None:
        tipos = {".html": "text/html; charset=utf-8",
                 ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8",
                 ".svg": "image/svg+xml"}
        if not caminho.exists() or not caminho.is_file():
            self.send_error(404, "arquivo não encontrado")
            return
        corpo = caminho.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         tipos.get(caminho.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ── GET ───────────────────────────────────────────────────────────
    def do_GET(self) -> None:
        u = urlparse(self.path)
        rota, q = u.path, parse_qs(u.query)
        try:
            if rota in ("/", "/index.html"):
                return self._arquivo(PAINEL / "index.html")
            if rota.startswith("/painel/"):
                # nome de arquivo é limitado ao que existe na pasta: nada de
                # subir diretório com "..", que é o buraco clássico
                nome = Path(rota).name
                return self._arquivo(PAINEL / nome)
            if rota == "/api/jogos":
                return self._json({"jogos": _jogos(),
                                   "fonte": API.carregar_fonte()})
            if rota == "/api/jogo":
                return self._json(_detalhe(q.get("jogo", [""])[0]))
            if rota == "/api/base":
                return self._json({"itens": _base(q.get("jogo", [""])[0])})
            if rota == "/api/historico":
                return self._json(_estado_historico(q.get("jogo", [""])[0]))
            if rota == "/api/tarefa":
                ident = q.get("id", [""])[0]
                with _TRAVA:
                    t = _TAREFAS.get(ident)
                    return self._json(dict(t) if t else
                                      {"estado": "erro",
                                       "erro": "tarefa desconhecida"})
            self.send_error(404, "rota desconhecida")
        except Exception as e:
            traceback.print_exc()
            self._json({"erro": f"{type(e).__name__}: {e}"}, 500)

    # ── POST ──────────────────────────────────────────────────────────
    def do_POST(self) -> None:
        rota = urlparse(self.path).path
        d = self._corpo()
        try:
            if rota == "/api/formular":
                return self._json(self._formular(d))
            if rota == "/api/fechamento":
                return self._json({"tarefa": self._fechamento(d)})
            if rota == "/api/conferir":
                return self._json(self._conferir(d))
            if rota == "/api/puxar":
                return self._json({"tarefa": self._puxar(d)})
            if rota == "/api/medir":
                return self._json({"tarefa": self._medir(d)})
            if rota == "/api/fonte":
                f = API.gravar_fonte(str(d.get("url") or ""),
                                     str(d.get("url_concurso") or ""))
                return self._json({"ok": True, "fonte": f})
            if rota == "/api/salvar_apostas":
                caminho = API.PASTA_DADOS / f"apostas_{d.get('jogo')}.txt"
                meta = d.get("meta") or None
                p = CO.escrever_apostas(caminho, d.get("apostas") or [],
                                        str(d.get("jogo")), meta)
                return self._json({"ok": True, "arquivo": str(p)})
            self.send_error(404, "rota desconhecida")
        except Exception as e:
            traceback.print_exc()
            self._json({"erro": f"{type(e).__name__}: {e}"}, 500)

    # ── as ações ──────────────────────────────────────────────────────
    def _formular(self, d: dict) -> dict:
        chave = str(d.get("jogo") or "")
        h = _historico_de(chave) if d.get("usar_historico", True) else None
        c = FO.conselho(chave, quantas=(int(d.get("quantas") or 0) or None),
                        hist=h, semente=(int(d["semente"])
                                         if d.get("semente") else None))
        c["tem_historico"] = h is not None
        return c

    def _fechamento(self, d: dict) -> str:
        chave = str(d.get("jogo") or "")
        j = RG.jogo(chave)
        dez = sorted({int(x) for x in (d.get("dezenas") or [])})
        k = int(d.get("k") or (j.minimo if j else 6))
        se = int(d.get("se") or 0)
        garantir = int(d.get("garantir") or 0)

        def trabalho(diga):
            diga(f"montando apostas de {k} dezenas a partir das suas "
                 f"{len(dez)}…")
            r = FE.montar(dez, k=k, acertos_previstos=se, garantir=garantir)
            if not r.get("ok"):
                return {"fechamento": r, "prova": None}
            diga(f"{r['n_apostas']} apostas. Agora provando a garantia em "
                 f"todos os {r['casos_totais']} casos possíveis…")
            prova = FE.conferir(r["apostas"], dez, se, garantir)
            diga("prova terminada.")
            return {"fechamento": r, "prova": prova}

        return _nova_tarefa(trabalho)

    def _conferir(self, d: dict) -> dict:
        j = RG.jogo(str(d.get("jogo") or ""))
        if not j:
            return {"erro": "loteria desconhecida"}
        apostas = [[int(x) for x in a] for a in (d.get("apostas") or [])]
        sorteio = [int(x) for x in (d.get("sorteio") or [])]
        r = CO.conferir(j, apostas, sorteio)
        auditoria = None
        meta = d.get("meta")
        if r.get("ok") and meta:
            auditoria = CO.auditar_garantia(meta, apostas, r["sorteio"])
        return {"conferencia": r, "auditoria": auditoria}

    def _puxar(self, d: dict) -> str:
        chave = str(d.get("jogo") or "")

        def trabalho(diga):
            diga("perguntando à fonte qual é o último concurso…")
            r = API.puxar(chave, pausa=float(d.get("pausa") or 0.15),
                          aviso=diga)
            r.pop("registros", None)          # não devolver megabytes à tela
            if r.get("ok"):
                diga("lendo o que foi gravado e conferindo com as regras…")
                r["estado"] = _estado_historico(chave)
            return r

        return _nova_tarefa(trabalho)

    def _medir(self, d: dict) -> str:
        chave = str(d.get("jogo") or "")

        def trabalho(diga):
            h = _historico_de(chave)
            if h is None:
                return {"erro": "ainda não há resultados no disco para esta "
                                "loteria — puxe primeiro"}
            ok, motivo = h.pronto_para_medir()
            if not ok:
                return {"erro": motivo}
            diga(f"medindo os itens da base em {len(h)} concursos…")
            med = MD.medir_tudo(h, gravar=True)
            diga("pronto.")
            return {"medicao": med, "itens": _base(chave), "n": len(h)}

        return _nova_tarefa(trabalho)


def porta_livre(preferida: int = 8777) -> int:
    for p in (preferida, 8778, 8779, 0):
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", p))
            porta = s.getsockname()[1]
            s.close()
            return porta
        except OSError:
            continue
    return 0


def main() -> int:
    porta = porta_livre()
    servidor = ThreadingHTTPServer(("127.0.0.1", porta), Mao)
    url = f"http://127.0.0.1:{servidor.server_address[1]}/"
    print("═" * 68)
    print("  LOTERIA — o painel abriu no seu navegador")
    print("═" * 68)
    print(f"\n  Endereço: {url}")
    print("\n  Isto roda SÓ na sua máquina. Nada sai para a internet e nada")
    print("  entra — o navegador é apenas o jeito de desenhar a tela.")
    print("\n  Se o navegador não abrir sozinho, copie o endereço acima.")
    print("\n  Para FECHAR o programa: feche esta janela preta.\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Encerrado.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
