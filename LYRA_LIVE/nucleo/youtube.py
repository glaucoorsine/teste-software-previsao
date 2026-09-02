# -*- coding: utf-8 -*-
"""
O que o YouTube espera de quem transmite.

DUAS FORMAS DE O YOUTUBE RECONHECER ESTE SOFTWARE
-------------------------------------------------
1. COMO CODIFICADOR (é o que "software de live" quer dizer). O YouTube Studio
   entrega uma URL de ingestão e uma chave de transmissão; o software empurra
   vídeo e áudio para lá por RTMP. Do lado de lá aparece "recebendo dados" e a
   live começa. Não há cadastro, aprovação nem SDK: quem fala RTMP no formato
   certo é aceito. É o que `saida_rtmp.py` faz.

2. COMO CÂMERA. O YouTube Studio no navegador tem a opção "Webcam", e ali ele
   lista as câmeras do sistema. `saida_virtual.py` publica uma câmera virtual, e
   a Lyra JÁ FILTRADA aparece nessa lista como se fosse um dispositivo físico.

Este módulo cuida das regras do lado 1: endereços, validação da chave e as
taxas que o YouTube recomenda.

AS REGRAS QUE DERRUBAM LIVE
---------------------------
O YouTube é exigente em três pontos, e errar qualquer um dá "sem dados" ou live
que engasga:

* INTERVALO DE QUADRO-CHAVE de no máximo 4 segundos. Sem quadro-chave frequente
  o player do espectador não consegue entrar na transmissão. Aqui usamos 2 s.
* FAIXA DE ÁUDIO SEMPRE. Transmissão sem áudio nenhum é recusada — por isso o
  encoder inventa silêncio quando não há microfone escolhido.
* yuv420p. É o único formato de cor que todo player aceita.
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

INGESTAO_PRIMARIA = "rtmp://a.rtmp.youtube.com/live2"
INGESTAO_BACKUP = "rtmp://b.rtmp.youtube.com/live2?backup=1"

# A chave que o YouTube Studio entrega tem a forma xxxx-xxxx-xxxx-xxxx-xxxx.
# O padrão aceita de 4 a 6 grupos porque o formato já mudou antes e não vale a
# pena recusar uma chave boa por rigor de contagem.
_PADRAO_CHAVE = re.compile(r"^[a-z0-9]{4}(?:-[a-z0-9]{4,}){3,5}$", re.IGNORECASE)

# Recomendações do YouTube para vídeo em taxa variável, em kbps.
# (altura, é 60fps) -> (mínimo, recomendado, máximo)
_TAXAS = {
    (360, False): (400, 800, 1000),
    (480, False): (500, 1500, 2000),
    (720, False): (1500, 3000, 4000),
    (720, True): (2250, 4500, 6000),
    (1080, False): (3000, 4500, 6000),
    (1080, True): (4500, 6800, 9000),
    (1440, False): (6000, 9000, 13000),
    (1440, True): (9000, 13500, 18000),
    (2160, False): (13000, 20000, 34000),
    (2160, True): (20000, 30000, 51000),
}


def mascarar_chave(texto: str) -> str:
    """Troca a chave por asteriscos. TUDO que vira log passa por aqui.

    A chave de transmissão é a senha da live: quem a tem transmite no canal
    dele. Ela aparece na linha de comando do ffmpeg, e linha de comando de
    ffmpeg é exatamente o tipo de coisa que se cola num print para pedir ajuda.
    """
    if not texto:
        return texto
    return re.sub(r"(rtmp[s]?://[^\s]*?/live2/)([^\s\"']+)", r"\1****", str(texto))


def validar_chave(chave: str) -> Tuple[bool, str]:
    """Devolve (vale, motivo). O motivo é escrito para aparecer na tela."""
    texto = (chave or "").strip()
    if not texto:
        return False, "Cole a chave de transmissão do YouTube Studio."
    if texto.startswith("rtmp"):
        return False, ("Isso é a URL de ingestão, não a chave. A chave é o campo "
                       "de baixo no YouTube Studio, no formato xxxx-xxxx-xxxx-xxxx-xxxx.")
    if " " in texto:
        return False, "A chave não tem espaços — verifique o que foi colado."
    if not _PADRAO_CHAVE.match(texto):
        return False, ("Formato estranho para chave do YouTube (o normal é "
                       "xxxx-xxxx-xxxx-xxxx-xxxx). Confira antes de transmitir.")
    return True, "Chave com formato válido."


def montar_url(chave: str, backup: bool = False, ingestao: Optional[str] = None) -> str:
    """Monta a URL completa de envio. Nunca imprima o resultado disto cru."""
    base = (ingestao or (INGESTAO_BACKUP if backup else INGESTAO_PRIMARIA)).rstrip("/")
    if backup and "?" in base:
        # a URL de backup carrega ?backup=1: a chave entra ANTES da interrogação
        caminho, _, consulta = base.partition("?")
        return f"{caminho.rstrip('/')}/{(chave or '').strip()}?{consulta}"
    return f"{base}/{(chave or '').strip()}"


def preset(altura: int, fps: int) -> Dict[str, int]:
    """A taxa de vídeo recomendada para esta resolução e cadência.

    Escolhe a linha da tabela pela altura MAIS PRÓXIMA para baixo: transmitir
    900p com a taxa de 1080p desperdiça banda de quem tem upload apertado, e é
    upload apertado que causa a maior parte das lives que engasgam.
    """
    alturas = sorted({a for a, _ in _TAXAS})
    alvo = alturas[0]
    for a in alturas:
        if altura >= a:
            alvo = a
    sessenta = int(fps) >= 50
    faixa = _TAXAS.get((alvo, sessenta)) or _TAXAS[(alvo, False)]
    minimo, recomendado, maximo = faixa
    return {
        "video_kbps": recomendado,
        "video_min_kbps": minimo,
        "video_max_kbps": maximo,
        "audio_kbps": 128,
        "intervalo_quadro_chave": 2,          # segundos — o YouTube exige <= 4
    }


def diagnostico_conexao(texto: str) -> Optional[str]:
    """Traduz erro de rede do ffmpeg para uma frase que diz o que fazer.

    O ffmpeg é preciso e ilegível. "Operation not permitted" numa URL de RTMP
    quase sempre é chave errada, e a pessoa fica olhando para a rede.
    """
    if not texto:
        return None
    t = texto.lower()
    if "operation not permitted" in t or "unauthorized" in t or "auth" in t and "fail" in t:
        return ("O YouTube recusou a chave de transmissão. Gere de novo no YouTube "
                "Studio e cole outra vez — chave de live anterior costuma expirar.")
    if "connection refused" in t or "failed to connect" in t or "network is unreachable" in t:
        return ("Não consegui alcançar o servidor do YouTube. Verifique a internet "
                "e se algum firewall bloqueia a porta 1935.")
    if "broken pipe" in t or "connection reset" in t or "end of file" in t:
        return ("A conexão com o YouTube caiu no meio da transmissão. Costuma ser "
                "oscilação do upload; o software tenta reconectar sozinho.")
    if "no such file or directory" in t and "dshow" in t:
        return "O dispositivo de áudio escolhido não existe mais. Escolha outro no painel."
    return None
