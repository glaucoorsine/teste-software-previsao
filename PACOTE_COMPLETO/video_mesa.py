# -*- coding: utf-8 -*-
"""
VÍDEO DA MESA — a mesa ao vivo numa janela do próprio software, uma por jogo.

    "coloque os videos ao vivo para rodar dentro do software,
     cada jogo com seu video"

O QUE DÁ E O QUE NÃO DÁ, DITO ANTES
───────────────────────────────────
O Tkinter não decodifica vídeo. Não existe widget de vídeo nele, e não há como
"colar" um stream dentro de um `CTkFrame`. Então "dentro do software" tem de
significar outra coisa, e significa isto: uma janela pertencente ao software,
com um motor de navegador dentro, abrindo a página da mesa.

O que eu NÃO consigo fazer, e não vou fingir: pegar o stream do cassino e
redesenhá-lo aqui. O vídeo ao vivo fica atrás da sessão autenticada do operador
e com proteção de conteúdo. Se a página exigir login, você loga na janela — a
sessão é sua, não minha.

TRÊS CAMINHOS, NESTA ORDEM
──────────────────────────
1. `pywebview` — janela nativa com motor de navegador (WebView2 no Windows). É o
   que mais se aproxima do que ele pediu: parece parte do programa.
2. `webbrowser` — abre no navegador dele. Menos bonito, sempre funciona.
3. dizer o motivo. Nunca ficar sem nada e sem explicação.

POR QUE EM OUTRO PROCESSO
─────────────────────────
`pywebview` toma conta do laço principal da thread em que roda. O Tkinter também
toma. Os dois no mesmo processo brigam pelo laço e a janela congela — seria o
travamento que ele fotografou, de novo, agora por minha escolha de arquitetura.

Então cada vídeo é um processo próprio. Fechar o vídeo não mexe na CENTRAL;
travar o vídeo não trava a CENTRAL. E é por isso que este arquivo tem um
`__main__`: ele é o programa que o processo filho executa.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "video_mesas.json"

# Onde cada mesa é assistida. Editável por ele -- é o cassino DELE que importa,
# e eu não tenho como saber em qual ele joga. O casinoscores é o padrão porque
# mostra a mesa ao vivo sem exigir conta.
PADRAO: Dict[str, str] = {
    "lightning": "https://www.casino.org/casinoscores/pt-br/lightning-roulette/",
    "mega_fire": "https://www.casino.org/casinoscores/pt-br/mega-fire-blaze-roulette/",
    "crazy_time": "https://www.casino.org/casinoscores/pt-br/crazy-time/",
    "crazy_time_a": "https://www.casino.org/casinoscores/pt-br/crazy-time-a/",
}

TITULOS = {
    "lightning": "Lightning Roulette — ao vivo",
    "mega_fire": "Mega Fire Blaze — ao vivo",
    "crazy_time": "Crazy Time — ao vivo",
    "crazy_time_a": "Crazy Time A — ao vivo",
}


def enderecos() -> Dict[str, str]:
    """Os endereços de vídeo, com o que ele configurou por cima do padrão."""
    d = dict(PADRAO)
    try:
        if CONFIG.is_file():
            salvo = json.loads(CONFIG.read_text(encoding="utf-8")) or {}
            for k, v in salvo.items():
                if isinstance(v, str) and v.strip():
                    d[str(k)] = v.strip()
    except Exception:
        pass
    return d


def gravar_endereco(jogo: str, url: str) -> bool:
    """Guarda o endereço que ELE quer para esta mesa."""
    try:
        d = {}
        if CONFIG.is_file():
            d = json.loads(CONFIG.read_text(encoding="utf-8")) or {}
        d[str(jogo)] = str(url).strip()
        tmp = CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        import os
        os.replace(tmp, CONFIG)
        return True
    except Exception:
        return False


def tem_webview() -> bool:
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


def abrir(jogo: str, registrar=None) -> str:
    """Abre a mesa ao vivo. Devolve como abriu, em português."""
    url = enderecos().get(str(jogo))
    if not url:
        return f"não há endereço de vídeo para {jogo}"

    def log(m):
        if registrar:
            try:
                registrar(m)
            except Exception:
                pass

    if tem_webview():
        try:
            # processo próprio: pywebview e Tkinter não dividem o laço principal
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), str(jogo)],
                cwd=str(RAIZ),
                creationflags=(subprocess.CREATE_NO_WINDOW
                               if hasattr(subprocess, "CREATE_NO_WINDOW")
                               else 0))
            log(f"VIDEO {jogo} aberto em janela do software: {url}")
            return "janela do software"
        except Exception as e:
            log(f"VIDEO {jogo} pywebview falhou ({type(e).__name__}) — "
                f"caindo para o navegador")

    try:
        import webbrowser
        webbrowser.open(url, new=2)
        motivo = ("pywebview não instalado" if not tem_webview()
                  else "pywebview falhou")
        log(f"VIDEO {jogo} aberto no navegador ({motivo}): {url}")
        return f"navegador — {motivo}"
    except Exception as e:
        log(f"VIDEO {jogo} não abriu: {type(e).__name__}")
        return f"não abriu: {type(e).__name__}"


def como_instalar() -> str:
    return ("Para a mesa abrir DENTRO do software em vez do navegador:\n"
            "    pip install pywebview\n"
            "No Windows ele usa o WebView2, que já vem com o Edge.")


def main() -> int:
    """O programa do processo filho: só abre a janela e fica nela."""
    jogo = sys.argv[1] if len(sys.argv) > 1 else "crazy_time"
    url = enderecos().get(jogo)
    if not url:
        print(f"sem endereço para {jogo}")
        return 1
    try:
        import webview
    except Exception:
        import webbrowser
        webbrowser.open(url, new=2)
        return 0
    webview.create_window(TITULOS.get(jogo, jogo), url,
                          width=1024, height=720, resizable=True)
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
