# -*- coding: utf-8 -*-
"""
DISPOSITIVOS — achar a webcam dele pelo NOME, não por um número que muda.

O PROBLEMA REAL
───────────────
No OpenCV a câmera é um número: `VideoCapture(0)`. Esse número não é
propriedade da câmera -- é a ordem em que o Windows enumerou os dispositivos
naquele boot. Plugar um pendrive com câmera, ligar a webcam depois do boot, ou
o Windows Update mexer no driver troca a ordem. No dia da live, o `0` que era
a ly7ra passa a ser a câmera do notebook, e ele descobre isso no ar.

Então aqui o dispositivo é o NOME. O número é consequência.

O NOME DELE TEM UM 7 NO MEIO
────────────────────────────
Ele escreveu "ly7ra". Isso pode estar gravado no dispositivo de três formas:
"LY7RA", "Lyra" e "LY7RA HD Camera" -- fabricante de webcam barata escreve o
nome como quer, e às vezes o USB devolve outra grafia diferente da caixa. Por
isso a comparação também tenta a versão sem dígitos: "ly7ra" e "lyra" casam
entre si. Não é adivinhação bonita, é o que faz o botão funcionar na casa
dele em vez de só na minha cabeça.

COMO EU ENUMERO, E O QUE ISSO CUSTA
───────────────────────────────────
Windows: `ffmpeg -list_devices true -f dshow -i dummy` devolve nome de câmera
E de microfone, que é exatamente o que preciso, e o ffmpeg já é dependência da
transmissão -- não trago nada novo para isto.
Linux: `/sys/class/video4linux/*/name`.
Sem ffmpeg: sobra abrir índice por índice com o OpenCV, e aí o nome não
existe. Nesse caso eu digo na tela que estou às cegas, em vez de fingir que
o `0` é a ly7ra.
"""
from __future__ import annotations

import glob
import platform
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

JANELA = platform.system() == "Windows"


@dataclass
class Dispositivo:
    indice: int
    nome: str
    tipo: str          # "video" ou "audio"
    origem: str        # de onde eu soube o nome: dshow, v4l2, cega

    def __str__(self) -> str:
        return f"[{self.indice}] {self.nome}"


# ─────────────────────────────────────────────────────────────────────────────
# COMPARAR NOMES
# ─────────────────────────────────────────────────────────────────────────────

def normalizar(s: str) -> str:
    """Sem acento, sem maiúscula, sem pontuação. 'LY7RA HD (2)' -> 'ly7rahd2'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _variantes(s: str) -> Tuple[str, str]:
    """A forma normal e a forma sem dígitos -- 'ly7ra' e 'lyra'."""
    n = normalizar(s)
    return n, re.sub(r"[0-9]+", "", n)


def parece(nome: str, procurado: str) -> bool:
    """O dispositivo `nome` é o que ele chamou de `procurado`?

    Casa por conter, nas duas direções, e nas duas grafias (com e sem dígito).
    Nas duas direções porque ele digita "ly7ra" e o dispositivo se chama
    "LY7RA HD Webcam", mas também acontece o contrário: ele digita o nome
    inteiro da caixa e o dispositivo devolve só "LY7RA".
    """
    if not procurado or not procurado.strip():
        return False
    a, a_sd = _variantes(nome)
    b, b_sd = _variantes(procurado)
    if not b:
        return False
    for x, y in ((a, b), (a_sd, b_sd)):
        if x and y and (y in x or x in y):
            return True
    return False


def escolher(lista: List[Dispositivo], nome: str, indice: int = -1
             ) -> Tuple[Optional[Dispositivo], str]:
    """Qual dispositivo usar, e a frase que explica por quê.

    A ordem é: índice que ele fixou > nome que ele deu > o primeiro que existe.
    A frase volta junto porque a tela precisa poder dizer "usei a câmera do
    notebook porque não achei a ly7ra" -- silêncio aqui é o que faz ele
    transmitir com a câmera errada sem saber.
    """
    if not lista:
        return None, "nenhum dispositivo encontrado"

    if indice is not None and indice >= 0:
        for d in lista:
            if d.indice == indice:
                return d, f"índice {indice} fixado por você"
        return lista[0], (f"índice {indice} não existe agora; usei "
                          f"{lista[0].nome}")

    if nome and nome.strip():
        achados = [d for d in lista if parece(d.nome, nome)]
        if len(achados) == 1:
            return achados[0], f"achei pelo nome: {achados[0].nome}"
        if len(achados) > 1:
            return achados[0], (f"{len(achados)} casam com '{nome}'; usei a "
                                f"primeira: {achados[0].nome}")
        return lista[0], (f"NÃO achei '{nome}'. Usei {lista[0].nome} — "
                          f"confira antes de transmitir")

    return lista[0], f"primeira da lista: {lista[0].nome}"


# ─────────────────────────────────────────────────────────────────────────────
# ENUMERAR
# ─────────────────────────────────────────────────────────────────────────────

_RE_DSHOW = re.compile(r'"([^"]+)"\s*\((video|audio)\)', re.I)


def ler_dshow(texto: str) -> List[Dispositivo]:
    """Lê a saída do `ffmpeg -list_devices` do Windows.

    Puro texto de propósito: o teste roda a saída real de uma máquina Windows
    sem precisar de Windows nem de webcam.
    """
    vs, aus = [], []
    for m in _RE_DSHOW.finditer(texto or ""):
        nome, tipo = m.group(1), m.group(2).lower()
        alvo = vs if tipo == "video" else aus
        # o ffmpeg imprime "nome" e depois "@device_pnp_..." como alternativa;
        # o alternativo vem em outra linha e não casa com o regex de tipo.
        if nome not in [d.nome for d in alvo]:
            alvo.append(Dispositivo(len(alvo), nome, tipo, "dshow"))
    return vs + aus


def _rodar(cmd: List[str], seg: float = 12.0) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=seg,
                           errors="replace")
        return (p.stdout or "") + (p.stderr or "")
    except Exception:
        return ""


def listar(tipo: str = "video", ffmpeg: str = "ffmpeg") -> List[Dispositivo]:
    """Os dispositivos de `tipo` ("video" ou "audio") que existem AGORA."""
    if JANELA:
        # o dshow sempre termina em erro ("dummy" não é um dispositivo); a
        # lista vem no stderr junto com esse erro, e isso é o normal.
        txt = _rodar([ffmpeg, "-hide_banner", "-list_devices", "true",
                      "-f", "dshow", "-i", "dummy"])
        ds = [d for d in ler_dshow(txt) if d.tipo == tipo]
        if ds:
            return ds
    elif tipo == "video":
        ds = []
        for cam in sorted(glob.glob("/dev/video*")):
            n = re.sub(r"\D", "", cam)
            if not n:
                continue
            nome = cam
            try:
                p = Path(f"/sys/class/video4linux/video{n}/name")
                if p.is_file():
                    nome = p.read_text(errors="replace").strip() or cam
            except Exception:
                pass
            ds.append(Dispositivo(int(n), nome, "video", "v4l2"))
        if ds:
            return ds
    else:
        txt = _rodar(["pactl", "list", "short", "sources"])
        ds = [Dispositivo(i, ln.split("\t")[1], "audio", "pactl")
              for i, ln in enumerate(txt.splitlines())
              if len(ln.split("\t")) > 1]
        if ds:
            return ds

    return listar_as_cegas() if tipo == "video" else []


def listar_as_cegas(quantos: int = 6) -> List[Dispositivo]:
    """Último recurso: abre índice por índice e vê se veio quadro.

    Sem nome nenhum -- e é por isso que a tela avisa. Abrir e fechar câmera
    custa segundos e às vezes acende o LED dela, então o teto é baixo.
    """
    try:
        import cv2
        # O OpenCV imprime um aviso por índice que não abre. Aqui isso é o
        # NORMAL -- estou justamente procurando quais existem -- e essas
        # linhas em inglês no meio da tela dele parecem erro sem ser.
        try:
            cv2.setLogLevel(0)
        except Exception:
            pass
    except Exception:
        return []
    ds = []
    for i in range(max(1, quantos)):
        cap = None
        try:
            cap = cv2.VideoCapture(i)
            if cap is not None and cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    ds.append(Dispositivo(i, f"câmera {i} (nome desconhecido)",
                                          "video", "cega"))
        except Exception:
            pass
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
    try:
        cv2.setLogLevel(3)
    except Exception:
        pass
    return ds


def microfones() -> List[Dispositivo]:
    """Microfones pelo sounddevice, que é quem vai gravar de verdade.

    Uso o sounddevice e não o ffmpeg porque o índice tem de ser o índice DELE:
    listar por um caminho e abrir por outro é como se troca de microfone sem
    querer.
    """
    try:
        import sounddevice as sd
        ds = []
        for i, d in enumerate(sd.query_devices()):
            if int(d.get("max_input_channels", 0)) > 0:
                ds.append(Dispositivo(i, str(d.get("name", f"entrada {i}")),
                                      "audio", "sounddevice"))
        return ds
    except Exception:
        return listar("audio")
