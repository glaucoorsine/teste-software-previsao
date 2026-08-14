# -*- coding: utf-8 -*-
"""
NOTIFICADOR — avisa no celular quando um sinal aparece.

Configure em `notificacoes.json` (criado com o modelo na primeira execução):

    {"canal": "ntfy", "topico": "algo-bem-unico-que-so-voce-sabe"}

Dois canais:

  ntfy      — sem conta, sem cadastro. Instale o app "ntfy" (iOS/Android),
              assine o mesmo tópico, pronto. O tópico é a senha: quem souber
              o nome recebe os avisos, então use algo único.

  telegram  — {"canal":"telegram","token":"...","chat_id":"..."}
              Fale com @BotFather pra criar o bot e pegar o token.

Regras de funcionamento:
  - nunca trava a interface: envia em thread separada, com timeout curto
  - nunca derruba o combo: qualquer erro é engolido e registrado
  - antirrepetição: não manda o mesmo sinal duas vezes seguidas, e respeita
    um intervalo mínimo entre avisos
"""
from __future__ import annotations
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
CFG = ROOT / "notificacoes.json"

INTERVALO_MIN_S = 25          # não avisa de novo antes disso
TIMEOUT_S = 8

MODELO = {
    "canal": "nenhum",
    "topico": "",
    "token": "",
    "chat_id": "",
    "_ajuda": (
        "canal: 'ntfy' (mais simples, sem conta) ou 'telegram' ou 'nenhum'. "
        "Para ntfy: instale o app ntfy no celular, escolha um tópico único e "
        "assine ele. Para telegram: crie um bot no @BotFather."
    ),
}

_ultimo: Dict[str, Any] = {"quando": 0.0, "texto": ""}
_trava = threading.Lock()


def _cfg() -> dict:
    if not CFG.is_file():
        try:
            CFG.write_text(json.dumps(MODELO, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        except OSError:
            pass
        return dict(MODELO)
    try:
        c = dict(MODELO)
        c.update(json.loads(CFG.read_text(encoding="utf-8")))
        return c
    except Exception:
        return dict(MODELO)


def ativo() -> bool:
    c = _cfg()
    canal = (c.get("canal") or "nenhum").lower()
    if canal == "ntfy":
        return bool(c.get("topico"))
    if canal == "telegram":
        return bool(c.get("token") and c.get("chat_id"))
    return False


def _enviar(titulo: str, corpo: str) -> Optional[str]:
    try:
        import requests
    except Exception:
        return "requests ausente"
    c = _cfg()
    canal = (c.get("canal") or "nenhum").lower()
    try:
        if canal == "ntfy":
            r = requests.post(
                f"https://ntfy.sh/{c['topico']}",
                data=corpo.encode("utf-8"),
                headers={"Title": titulo.encode("utf-8").decode("latin-1", "ignore"),
                         "Priority": "high", "Tags": "game_die"},
                timeout=TIMEOUT_S)
            r.raise_for_status()
            return None
        if canal == "telegram":
            r = requests.post(
                f"https://api.telegram.org/bot{c['token']}/sendMessage",
                json={"chat_id": c["chat_id"], "text": f"{titulo}\n{corpo}"},
                timeout=TIMEOUT_S)
            r.raise_for_status()
            return None
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:60]}"
    return "canal desconhecido"


def notificar(titulo: str, corpo: str, log_fn=None) -> None:
    """Dispara em segundo plano. Nunca bloqueia, nunca levanta exceção."""
    if not ativo():
        return
    agora = time.time()
    with _trava:
        if corpo == _ultimo["texto"] and agora - _ultimo["quando"] < 300:
            return                                   # mesmo sinal, ignora
        if agora - _ultimo["quando"] < INTERVALO_MIN_S:
            return                                   # rápido demais
        _ultimo["quando"] = agora
        _ultimo["texto"] = corpo

    def _tarefa():
        err = _enviar(titulo, corpo)
        if err and log_fn:
            try:
                log_fn(f"notificacao falhou: {err}")
            except Exception:
                pass

    threading.Thread(target=_tarefa, daemon=True).start()


def notificar_sinal(jogo: str, numeros: List[Any], modo: str = "",
                    janela: int = 0, extra: str = "", log_fn=None) -> None:
    """O aviso que interessa: um sinal novo apareceu nesta mesa."""
    if not numeros:
        return
    nums = " ".join(str(n) for n in numeros)
    corpo = nums
    if janela:
        corpo += f"\njanela: {janela} giros"
    if extra:
        corpo += f"\n{extra}"
    notificar(f"{jogo.upper()} — sinal", corpo, log_fn=log_fn)


def testar() -> str:
    """Manda um aviso de teste. Devolve mensagem legível do que aconteceu."""
    c = _cfg()
    canal = (c.get("canal") or "nenhum").lower()
    if canal == "nenhum":
        return ("Nenhum canal configurado. Edite notificacoes.json — o mais "
                "simples é {\"canal\":\"ntfy\",\"topico\":\"seu-topico-unico\"}")
    if not ativo():
        return f"Canal '{canal}' configurado pela metade — faltam campos."
    err = _enviar("Teste do laboratório", "Se você recebeu isto, está funcionando.")
    return "Enviado. Confira o celular." if not err else f"Falhou: {err}"


if __name__ == "__main__":
    print(testar())
