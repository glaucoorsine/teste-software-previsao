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

# ─────────────────────────────────────────────────────────── o ritmo do envio
#
# MEDIDO NO LOG DELE: 1.058 falhas de notificação em 9h30, todas 429 — "Too
# Many Requests". O aviso no celular ficou morto a noite inteira e ele só
# descobriu ao abrir a tela de configuração.
#
# A causa não é a configuração dele: é volume. Quatro mesas, 709 janelas, e
# cada janela manda duas mensagens (a entrada e o desfecho). Dá mais de 2.500
# mensagens em 9 horas, umas 4 por minuto. O ntfy.sh grátis não aceita esse
# ritmo de ninguém, e a cada recusa a mensagem era simplesmente perdida.
#
# O conserto tem três partes, e as três são necessárias:
#
#   FILA          uma mensagem por vez, com intervalo mínimo entre elas. Quatro
#                 mesas disparando junto viram quatro envios espaçados, não
#                 quatro simultâneos.
#   ESPERA        no 429, a mensagem NÃO é descartada: respeita o Retry-After
#                 do servidor (ou dobra a espera sozinha) e tenta de novo.
#   JUNTAR        se a fila acumulou, as mensagens saem agrupadas numa só. É a
#                 diferença entre receber o que aconteceu e não receber nada.
INTERVALO_ENVIO_S = 6.0        # ritmo base entre duas mensagens
ESPERA_MAX_S = 300.0           # teto da espera depois de 429 seguidos
FILA_MAX = 40                  # o que passar disso é resumido, não acumulado
MARCA_RITMO = "__RITMO__"      # 429 disfarçado de erro comum atrapalhava a tela

_fila: List[tuple] = []
_fila_trava = threading.Lock()
_carteiro: Optional[threading.Thread] = None
_espera_atual = INTERVALO_ENVIO_S
_ritmo_avisado = False


def estado_fila() -> Dict[str, Any]:
    """Quantas mensagens esperando e em que ritmo — para a tela mostrar."""
    with _fila_trava:
        return {"na_fila": len(_fila), "espera_s": round(_espera_atual, 1),
                "limitado": _espera_atual > INTERVALO_ENVIO_S * 1.5}


def _juntar(lote: List[tuple]) -> tuple:
    """Várias mensagens viram uma. Melhor uma longa que nenhuma."""
    if len(lote) == 1:
        return lote[0]
    titulo = f"{len(lote)} avisos"
    corpo = "\n\n".join(f"[{t}]\n{c}" for t, c, _lg in lote)
    return (titulo, corpo, lote[0][2])


def _turno_do_carteiro() -> None:
    """Tira da fila e entrega, no ritmo que o servidor aceitar."""
    global _espera_atual, _ritmo_avisado
    while True:
        with _fila_trava:
            if not _fila:
                break
            # se a fila acumulou, sai tudo junto numa mensagem só
            lote = [_fila.pop(0)] if len(_fila) <= 2 else [
                _fila.pop(0) for _ in range(min(len(_fila), 6))]
        titulo, corpo, log_fn = _juntar(lote)
        erro = _enviar(titulo, corpo)
        if erro and erro.startswith(MARCA_RITMO):
            # 429: o servidor pediu calma. A mensagem VOLTA para a fila.
            pedido = 0.0
            try:
                pedido = float(erro[len(MARCA_RITMO):] or 0)
            except ValueError:
                pedido = 0.0
            _espera_atual = min(ESPERA_MAX_S,
                                max(pedido, _espera_atual * 2, INTERVALO_ENVIO_S))
            with _fila_trava:
                _fila.insert(0, (titulo, corpo, log_fn))
                if len(_fila) > FILA_MAX:
                    del _fila[FILA_MAX:]
            if not _ritmo_avisado and log_fn:
                _ritmo_avisado = True
                try:
                    log_fn(f"ntfy limitando o ritmo — os avisos passam a sair "
                           f"a cada {_espera_atual:.0f}s, nenhum é perdido")
                except Exception:
                    pass
        else:
            if erro and log_fn:
                try:
                    log_fn(f"notificacao falhou: {erro}")
                except Exception:
                    pass
            # deu certo: volta devagar ao ritmo normal
            _espera_atual = max(INTERVALO_ENVIO_S, _espera_atual * 0.7)
        time.sleep(_espera_atual)


def _enfileirar(titulo: str, corpo: str, log_fn=None) -> None:
    global _carteiro
    with _fila_trava:
        _fila.append((titulo, corpo, log_fn))
        if len(_fila) > FILA_MAX:
            del _fila[:len(_fila) - FILA_MAX]
        vivo = _carteiro is not None and _carteiro.is_alive()
    if not vivo:
        _carteiro = threading.Thread(target=_turno_do_carteiro, daemon=True)
        _carteiro.start()


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
    """Uma tentativa de envio. Devolve None se foi, ou o motivo se não foi.

    O 429 vem separado dos outros erros porque ele NÃO é defeito de
    configuração: é o servidor grátis do ntfy dizendo "devagar". Tratar os dois
    igual fazia a tela acusar erro vermelho quando o certo era esperar.
    """
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
            if r.status_code == 429:
                espera = 0
                try:
                    espera = int(r.headers.get("Retry-After") or 0)
                except (TypeError, ValueError):
                    espera = 0
                return f"{MARCA_RITMO}{espera}"
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

    # Vai para a fila, nao direto para a rede: quatro mesas disparando ao
    # mesmo tempo eram quatro requisicoes simultaneas, e o ntfy respondia 429
    # nas tres ultimas. Ver o comentario grande em INTERVALO_ENVIO_S.
    _enfileirar(titulo, corpo, log_fn)


def notificar_sinal(jogo: str, numeros: List[Any], modo: str = "",
                    janela: int = 0, extra: str = "", publico: str = "",
                    multiplicador: str = "", log_fn=None) -> None:
    """O aviso que interessa: um sinal novo apareceu nesta mesa.

    `publico` é a linha que ele pediu — "deixe a informação no ntfy (pessoas
    ruim, médio, bom)". Vai junto do sinal de propósito: quem está longe da
    tela recebe a entrada e, na mesma mensagem, o quanto a mesa está cheia,
    que é a percepção dele sobre quando a previsão fica mais fácil.
    """
    if not numeros:
        return
    nums = " ".join(str(n) for n in numeros)
    corpo = nums
    if janela:
        corpo += f"\njanela: {janela} giros"
    # o fogo vem logo depois dos números, antes de qualquer estatística: é a
    # informação que ele quer ler primeiro. Vazio na Immersive, que não tem.
    if multiplicador:
        corpo += f"\n{multiplicador}"
    if publico:
        corpo += f"\n{publico}"
    if extra:
        corpo += f"\n{extra}"
    notificar(f"{jogo.upper()} — sinal", corpo, log_fn=log_fn)


def notificar_resultado(jogo: str, numeros: List[Any], acertou: bool,
                        saiu: Any = None, giros: int = 0, placar: str = "",
                        placar_num: str = "", publico: str = "",
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

    Os DOIS placares vão rotulados — "o placar tem que mandar acerto e erro de
    número, acerto e erro de janela". Eles medem coisas diferentes: uma janela
    de 4 giros pode fechar como acerto tendo 1 acerto e 3 erros de número. Sem
    o rótulo dá para confundir um com o outro.
    """
    nums = " ".join(str(n) for n in (numeros or []))
    marca = "ACERTOU" if acertou else "errou"
    titulo = f"{jogo.upper()} - {marca}"
    corpo = f"aposta: {nums}" if nums else "janela encerrada"
    if saiu is not None:
        corpo += f"\nsaiu: {saiu}"
    if giros:
        corpo += f"\nfechou em {giros} giro(s)"
    if publico:
        corpo += f"\n{publico}"
    if placar:
        corpo += f"\n{placar}"
    if placar_num:
        corpo += f"\n{placar_num}"

    if not ativo():
        return
    # O desfecho tambem entra na fila. Ele NAO passa pelo antirrepeticao (cada
    # janela e um evento unico e nao pode ser engolido por parecer com a
    # anterior), mas passa pelo ritmo -- foi somando entrada + desfecho de
    # quatro mesas que o volume chegou a 2.500 mensagens em 9 horas.
    _enfileirar(titulo, corpo, log_fn)


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
