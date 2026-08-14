# -*- coding: utf-8 -*-
"""Fetch resiliente da API casino.org — retries, backoff, sem traceback no log."""
from __future__ import annotations
import time
import requests

def fetch_api(api_url: str, params: dict, headers: dict | None = None,
              timeout: int = 25, max_retries: int = 3) -> tuple[dict | list | None, str | None]:
    """
    Retorna (json, None) em sucesso ou (None, mensagem_curta) em falha.
    Nunca propaga traceback completo.
    """
    last_err = "sem tentativa"
    sess = requests.Session()
    if headers:
        sess.headers.update(headers)
    for attempt in range(1, max_retries + 1):
        try:
            r = sess.get(api_url, params=params, timeout=timeout)
            if r.status_code == 200:
                try:
                    return r.json(), None
                except Exception:
                    return None, f"JSON inválido HTTP {r.status_code}"
            # 500 estava DE FORA desta lista e era o erro mais comum da API:
            # um 500 passageiro derrubava a captura na primeira tentativa e a
            # tela pintava "API offline" sem nem repetir. 520-524 sao da
            # Cloudflare na frente do host e tambem passam sozinhos.
            if r.status_code in (429, 500, 502, 503, 504, 520, 521, 522, 523, 524):
                last_err = f"HTTP {r.status_code}"
                time.sleep(min(8, 1.5 * attempt))
                continue
            return None, f"HTTP {r.status_code}"
        except requests.exceptions.ConnectTimeout:
            last_err = "timeout conexão"
        except requests.exceptions.ReadTimeout:
            last_err = "timeout leitura"
        except requests.exceptions.ConnectionError as e:
            msg = str(e)
            if "10054" in msg or "ConnectionReset" in msg or "Connection aborted" in msg:
                last_err = "conexão resetada pelo host"
            else:
                last_err = "erro de conexão"
        except Exception as e:
            last_err = type(e).__name__
        time.sleep(min(10, 2 * attempt))
    return None, f"{last_err} (após {max_retries} tentativas)"
