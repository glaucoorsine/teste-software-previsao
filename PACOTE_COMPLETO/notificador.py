# -*- coding: utf-8 -*-
"""
NOTIFICADOR — avisa no celular quando um sinal aparece.

Configure em `notificacoes.json` (criado com o modelo na primeira execução):

    {"canal": "ntfy", "topico": "algo-bem-unico-que-so-voce-sabe"}

Três canais:

  whatsapp  — {"canal":"whatsapp","telefone":"5531999998888","apikey":"123456"}
              Via CallMeBot, que é o único caminho de WhatsApp viável para uso
              pessoal: a API oficial da Meta exige empresa verificada,
              aprovação de modelo de mensagem e provedor pago.
              Para habilitar (uma vez): salve +34 644 51 95 23 nos contatos,
              mande "I allow callmebot to send me messages", e o bot responde
              com a apikey. Limite de ~1 mensagem por minuto — sobra, porque o
              gatilho abre em ~11% dos giros.

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
    "telefone": "",
    "apikey": "",
    "_ajuda": (
        "canal: 'whatsapp', 'ntfy', 'telegram' ou 'nenhum'. "
        "WhatsApp (CallMeBot): salve +34 644 51 95 23 nos contatos, mande "
        "'I allow callmebot to send me messages', copie a apikey que ele "
        "responder e preencha telefone (com codigo do pais, ex 5531999998888) "
        "e apikey aqui. "
        "ntfy: instale o app ntfy, escolha um topico unico e assine ele. "
        "telegram: crie um bot no @BotFather."
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
    if canal == "whatsapp":
        return bool(c.get("telefone") and c.get("apikey"))
    return False


def _ascii(txt: str) -> str:
    """Cabeçalho HTTP não aceita acento.

    O código antigo jogava bytes UTF-8 dentro de latin-1, e o travessão de
    "LIGHTNING — sinal" chegava no celular como "LIGHTNING â sinal". Aqui a
    acentuação é rebaixada para o equivalente sem acento, que continua legível,
    em vez de virar lixo.
    """
    import unicodedata
    trocas = {"—": "-", "–": "-", "“": '"', "”": '"', "’": "'", "×": "x"}
    for de, para in trocas.items():
        txt = txt.replace(de, para)
    plano = unicodedata.normalize("NFKD", txt)
    return "".join(c for c in plano if not unicodedata.combining(c)) \
        .encode("ascii", "ignore").decode("ascii")


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
                headers={"Title": _ascii(titulo),
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
        if canal == "whatsapp":
            # CallMeBot: o único caminho de WhatsApp que funciona para uso
            # pessoal sem conta comercial. A API oficial da Meta exige empresa
            # verificada, aprovação de modelo de mensagem e um provedor pago —
            # inviável para um estudo de uma pessoa só.
            #
            # Como habilitar (uma vez, leva 2 minutos):
            #   1. salve o número +34 644 51 95 23 nos contatos
            #   2. mande por WhatsApp: "I allow callmebot to send me messages"
            #   3. o bot responde com uma apikey — ponha aqui no arquivo
            #
            # Limite do serviço: mais ou menos uma mensagem por minuto. Como o
            # gatilho abre em ~11% dos giros e a mesa gira a cada 48s, isso
            # sobra — mas se um dia apertar, o INTERVALO_MIN_S segura.
            r = requests.get(
                "https://api.callmebot.com/whatsapp.php",
                params={"phone": c.get("telefone", ""),
                        "text": f"{titulo}\n{corpo}",
                        "apikey": c.get("apikey", "")},
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


def notificar_resultado(jogo: str, numeros: List[Any], acertou: bool,
                        saiu: Any = None, giros: int = 0, placar: str = "",
                        log_fn=None) -> None:
    """Como terminou a janela que foi avisada.

    Pedido dele: "ele normalmente está mandando janelas, mas ele não fala se
    acertou, se errou. Quando ele manda os sinais, por exemplo manda uma
    janela de três giros, ele poderia dizer no final se acertou ou errou."

    Sem isso o aviso é meia informação: chega a entrada e nunca chega o
    desfecho, então quem está longe da tela não sabe se aquilo deu certo —
    e não consegue formar percepção nenhuma sobre o que está funcionando.

    O antirrepetição de `notificar` não vale aqui: o resultado é um evento
    único e não pode ser engolido por parecer com o aviso anterior. Por isso
    o envio é direto.
    """
    nums = " ".join(str(n) for n in (numeros or []))
    marca = "ACERTOU" if acertou else "errou"
    titulo = f"{jogo.upper()} - {marca}"
    corpo = f"aposta: {nums}" if nums else "janela encerrada"
    if saiu is not None:
        corpo += f"\nsaiu: {saiu}"
    if giros:
        corpo += f"\nfechou em {giros} giro(s)"
    if placar:
        corpo += f"\n{placar}"

    def _tarefa():
        err = _enviar(titulo, corpo)
        if err and log_fn:
            try:
                log_fn(f"notificacao resultado falhou: {err}")
            except Exception:
                pass

    if not ativo():
        return
    threading.Thread(target=_tarefa, daemon=True).start()


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
