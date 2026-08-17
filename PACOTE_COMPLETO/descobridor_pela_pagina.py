# -*- coding: utf-8 -*-
"""
DESCOBRIR PELA PÁGINA — parar de chutar o nome da mesa e ler onde ele está.

POR QUE ISTO EXISTE
───────────────────
    "voce nao consertou o que pedi"   — com o print: Crazy Time A, HTTP 404

Ele tem razão, e a culpa é de método, não de esforço. Eu venho escrevendo o
endereço da Crazy Time A por dedução, versão após versão:

    crazytimea, crazytime-a, crazytimeA, crazytime2, crazytimeatable,
    crazy-time-a

Todos 404. E eu não consigo testar nenhum daqui: o proxy deste ambiente nega
CONNECT para casino.org (403), então cada palpite meu chega na máquina dele sem
nunca ter sido verificado. Isso não é engenharia, é loteria — e ele que paga o
tempo de cada rodada.

O QUE MUDA
──────────
Ele mandou a página da mesa:

    https://www.casino.org/casinoscores/pt-br/crazy-time-a/

Essa página EXIBE os resultados. Logo ela sabe de onde os tira. Em vez de eu
adivinhar o nome, o software lê a página e procura, no HTML e nos scripts que
ela carrega, o endereço de API que ela mesma usa. Seja qual for o nome que o
provedor deu à mesa, ele está escrito ali — porque sem ele a página não
funcionaria.

Não é chute: é seguir a referência.

E TEM O CAMINHO CURTO
─────────────────────
Páginas assim costumam trazer o estado inicial embutido (`__NEXT_DATA__` ou
equivalente). Quando traz, os giros estão ali e nem é preciso achar a API: o
`extrair_resultados` lê direto, com a validação de domínio que já existe. Dois
caminhos independentes, e basta um funcionar.

O QUE EU CONFIRMEI E O QUE NÃO
──────────────────────────────
Testei contra páginas de mentira que eu montei nos dois formatos, e a busca
acha o endereço e recusa lixo. O que NÃO pude testar é a página real — o proxy
não deixa. Então isto não é promessa de que vai funcionar: é o software
passando a procurar em vez de eu adivinhar, e registrando no log o que
encontrou, para o próximo passo sair de evidência.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except Exception:                                   # pragma: no cover
    requests = None

RAIZ = Path(__file__).resolve().parent
TIMEOUT = 20

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://www.casino.org/",
}

# Endereço de API dentro do HTML ou dos scripts. Aceita os dois hosts que o
# provedor usa, e qualquer nome de mesa -- é justamente o nome que se procura.
_API = re.compile(
    r"https?://(?:api-cs\.casino\.org|api\.casinoscores\.com|"
    r"api\.trackpotapi\.com)/[A-Za-z0-9_\-/.]+")
# caminho relativo, que aparece quando a página monta a URL em partes
_CAMINHO = re.compile(
    r"[\"'](/(?:svc-[A-Za-z0-9\-]+|api)/[A-Za-z0-9_\-/.]+)[\"']")
# os scripts que a página carrega (é neles que a URL costuma estar)
_SCRIPT = re.compile(r'<script[^>]+src=["\']([^"\']+)["\']')

# um endereço só interessa se puder trazer histórico de jogo
_PISTAS = ("game-events", "gameevents", "history", "results", "spins",
           "svc-evolution", "latest")
# e nunca serve para isto
_LIXO = ("analytics", "gtm", "consent", "sentry", "recaptcha", "adservice",
         "doubleclick", "hotjar", "segment", "facebook")


def _pegar(url: str, sess=None) -> Tuple[Optional[str], Optional[str]]:
    if requests is None:
        return None, "requests ausente"
    try:
        s = sess or requests
        r = s.get(url, headers=CABECALHO, timeout=TIMEOUT)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:60]}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.text or "", None


def _absoluto(u: str, base: str) -> str:
    if u.startswith("http"):
        return u
    if u.startswith("//"):
        return "https:" + u
    raiz = re.match(r"(https?://[^/]+)", base)
    if not raiz:
        return u
    if u.startswith("/"):
        return raiz.group(1) + u
    return base.rstrip("/") + "/" + u


def enderecos_citados(html: str, base: str) -> List[str]:
    """Todo endereço de API que a página menciona, do mais promissor ao menos."""
    achados: List[str] = []
    for m in _API.finditer(html or ""):
        u = m.group(0).rstrip("\\\"'),;")
        if u not in achados:
            achados.append(u)
    for m in _CAMINHO.finditer(html or ""):
        u = _absoluto(m.group(1), base)
        if u not in achados:
            achados.append(u)
    bons = [u for u in achados
            if not any(x in u.lower() for x in _LIXO)]
    # quem cita pista de histórico vem primeiro
    bons.sort(key=lambda u: (0 if any(p in u.lower() for p in _PISTAS) else 1,
                             len(u)))
    return bons


def procurar(pagina: str, jogo: str,
             max_scripts: int = 8,
             registrar=None) -> Dict[str, Any]:
    """Lê a página da mesa e devolve o que ela revelou.

    Devolve `{"api": url|None, "resultados": [...], "citados": [...],
    "erro": str|None}`. Nada aqui inventa endereço: tudo o que sai daqui estava
    escrito na página ou nos scripts dela.
    """
    def log(m: str):
        if registrar:
            try:
                registrar(m)
            except Exception:
                pass

    html, err = _pegar(pagina)
    if html is None:
        return {"api": None, "resultados": [], "citados": [], "erro": err}

    # ── caminho curto: os giros já estão na página ──────────────────────────
    resultados: List[str] = []
    try:
        from fonte_gamblingcounting import extrair_resultados
        resultados = extrair_resultados(html, jogo)
    except Exception:
        resultados = []
    if resultados:
        log(f"DESCOBERTA_PAGINA {jogo}: {len(resultados)} giros lidos direto "
            f"da página, sem precisar da API")

    # ── caminho longo: achar o endereço que a página usa ───────────────────
    citados = enderecos_citados(html, pagina)
    if citados:
        log(f"DESCOBERTA_PAGINA {jogo}: {len(citados)} endereço(s) citados na "
            f"página — 1º {citados[0][:90]}")

    # os scripts costumam guardar a URL montada; só os da própria origem
    if len(citados) < 3:
        origem = re.match(r"(https?://[^/]+)", pagina)
        origem = origem.group(1) if origem else ""
        for src in _SCRIPT.findall(html)[:max_scripts * 3]:
            u = _absoluto(src, pagina)
            if origem and not u.startswith(origem):
                continue
            if any(x in u.lower() for x in _LIXO):
                continue
            js, e2 = _pegar(u)
            if not js:
                continue
            for extra in enderecos_citados(js, pagina):
                if extra not in citados:
                    citados.append(extra)
            if len(citados) >= 6:
                break
        if citados:
            log(f"DESCOBERTA_PAGINA {jogo}: depois dos scripts, "
                f"{len(citados)} endereço(s)")

    # ── validar: só vale endereço que devolva giro DESTA mesa ──────────────
    escolhido = None
    for u in citados[:12]:
        if _serve(u, jogo):
            escolhido = u
            log(f"DESCOBERTA_PAGINA {jogo}: VALIDADO {u[:100]}")
            break
    if citados and not escolhido:
        log(f"DESCOBERTA_PAGINA {jogo}: nenhum dos {len(citados)} endereços "
            f"citados devolveu giro reconhecível")

    return {"api": escolhido, "resultados": resultados,
            "citados": citados, "erro": None}


def _serve(url: str, jogo: str) -> bool:
    """O endereço devolve giros que o parser desta mesa reconhece?

    Aceitar sem conferir foi um achado dele (nº 6: "uma resposta não vazia,
    mesmo contendo lixo, é memorizada como fonte válida antes de passar pelo
    parser"). Aqui o crivo é o parser de verdade.
    """
    if requests is None:
        return False
    for params in ({"size": 10, "page": 0}, {"limit": 10}, {}):
        try:
            r = requests.get(url, headers=CABECALHO, params=params,
                             timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            dados = r.json()
        except Exception:
            continue
        itens = dados
        if isinstance(dados, dict):
            for c in ("content", "data", "results", "history", "items", "rows"):
                if isinstance(dados.get(c), list):
                    itens = dados[c]
                    break
        if not isinstance(itens, list) or not itens:
            continue
        try:
            from fluxo_captura import parse_items_ct, parse_items_roulette
            linhas = (parse_items_ct(itens)
                      if str(jogo).startswith("crazy_time")
                      else parse_items_roulette(itens))
        except Exception:
            continue
        if len(linhas) >= 3:
            return True
    return False
