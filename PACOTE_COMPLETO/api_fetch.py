# -*- coding: utf-8 -*-
"""
Fetch da API — resiliente, mas com HORA PARA ACABAR.

O QUE ELE VIU: "o lightning ta travado"
---------------------------------------
Não estava travado: estava esperando. E a espera era esta, em aritmética:

    timeout 25s × 3 tentativas + 6s de backoff  =  81s por endereço
    lightning tem 3 endereços                   =  243s = 4 minutos
    crazy_time_a tem 10                         =  810s = 13,5 minutos

A mesa consulta a cada 10 segundos, mas enquanto `_trabalhar` está moendo, a
trava `ocupado` bloqueia a volta seguinte. Então, com a API fora do ar, a tela
fica exatamente igual por quatro minutos seguidos — desenhada, com dados
velhos, sem responder. É indistinguível de travamento, e foi o que ele
fotografou.

O erro de projeto não é ter retry: é retry sem teto num laço que roda a cada
10 segundos. Insistir faz sentido para um 500 passageiro; não faz para uma
API que está fora há minutos.

O QUE MUDOU
-----------
1. `prazo`: um relógio único para a volta inteira. Cada tentativa usa o que
   sobrou, e quando acaba, acaba — quem chamou cai para o histórico salvo, que
   é o comportamento certo (o software continua analisando o que já tem).
2. Sessão reaproveitada por processo, em vez de uma nova a cada chamada. Eram
   três mesas × uma sessão a cada 10 segundos, nunca fechadas.
"""
from __future__ import annotations

import threading
import time

import requests

# teto de uma tentativa isolada quando ninguém passou prazo
TIMEOUT_PADRAO = 12
# quanto uma volta de captura inteira pode custar, no pior caso
ORCAMENTO_VOLTA_S = 45.0

_sessoes: dict = {}
_trava = threading.Lock()


def sessao(headers: dict | None = None) -> requests.Session:
    """Uma sessão por thread, reaproveitada.

    `requests.Session()` a cada chamada abre um pool de conexões novo e nunca
    o fecha. Com três mesas consultando a cada dez segundos, isso é um socket
    novo por consulta e nenhum devolvido -- o tipo de vazamento que só aparece
    depois de horas rodando, que é justamente como ele usa o software.

    Por thread, e não global, porque `requests.Session` não é seguro para uso
    simultâneo entre threads.
    """
    ident = threading.get_ident()
    with _trava:
        s = _sessoes.get(ident)
        if s is None:
            s = requests.Session()
            _sessoes[ident] = s
    if headers:
        s.headers.update(headers)
    return s


def fetch_api(api_url: str, params: dict, headers: dict | None = None,
              timeout: int = TIMEOUT_PADRAO, max_retries: int = 3,
              prazo: float | None = None) -> tuple[dict | list | None, str | None]:
    """Devolve (json, None) em sucesso ou (None, mensagem_curta) em falha.

    `prazo` é um instante (time.time() + n). Passado ele, a função desiste na
    hora em vez de começar mais uma tentativa de 25 segundos. Nunca propaga
    traceback.
    """
    last_err = "sem tentativa"
    sess = sessao(headers)

    def resta() -> float:
        return 1e9 if prazo is None else (prazo - time.time())

    for attempt in range(1, max_retries + 1):
        sobra = resta()
        if sobra <= 0.5:
            return None, f"{last_err} (prazo da volta esgotado)"
        # a tentativa nunca pode durar mais do que o que sobrou da volta
        t = max(1.0, min(float(timeout), sobra))
        try:
            r = sess.get(api_url, params=params, timeout=t)
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
                _dormir(min(4.0, 1.5 * attempt), prazo)
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
        _dormir(min(4.0, 2.0 * attempt), prazo)
    return None, f"{last_err} (após {max_retries} tentativas)"


def _dormir(segundos: float, prazo: float | None) -> None:
    """Espera, sem passar do prazo da volta."""
    if prazo is not None:
        segundos = min(segundos, max(0.0, prazo - time.time()))
    if segundos > 0:
        time.sleep(segundos)
