# -*- coding: utf-8 -*-
"""
AJUSTES — o que ele regulou fica regulado, e a chave do YouTube fica FORA daqui.

O QUE ELE PEDIU
───────────────
    "um software para minha webcam ly7ra, que conecte diretamente ao youtube,
     um editor de audio com capacidade de melhorar o audio direto na live,
     uma ia basica rodando pra ajudar a melhorar a qualidade da imagem,
     filtros cinematograficos ao estilo camera sony, embelezamento,
     sem a necessidade de passar pelo obs"

Este arquivo é a memória do software: dispositivo escolhido, look ativo, cada
controle de imagem e de áudio, taxa de bits. Ele mexe uma vez e não mexe mais.

POR QUE A CHAVE NÃO ENTRA NO JSON DOS AJUSTES
─────────────────────────────────────────────
A chave de transmissão do YouTube é a senha da live: quem tem a chave
transmite no canal dele. E `estudio_ajustes.json` é justamente o arquivo que
alguém manda para outra pessoa quando quer copiar a configuração -- é o que
eu faria, é o que ele faria.

Então a chave mora sozinha em `chave_youtube.txt`, que está no .gitignore e
nunca é impresso, nem no log de erro, nem na tela (a tela mostra
`•••••••••4f2a`). Se ele mandar os ajustes para alguém, manda sem a senha.

O DEFEITO QUE ESTE ARQUIVO NÃO VAI REPETIR
──────────────────────────────────────────
No outro software um ajuste salvo com chave errada derrubava a leitura toda e
voltava tudo ao padrão sem dizer nada. Aqui `carregar()` casa campo por campo
com o padrão: campo desconhecido é ignorado, campo com tipo errado cai no
padrão DAQUELE campo, e o resto do que ele regulou sobrevive.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

RAIZ = Path(__file__).resolve().parent
ARQ_AJUSTES = RAIZ / "estudio_ajustes.json"
ARQ_CHAVE = RAIZ / "chave_youtube.txt"

# Servidor de entrada do YouTube. O `live2` é o principal; o `live2?backup=1`
# é o de reserva, que o YouTube aceita em paralelo. Deixo o principal.
RTMP_YOUTUBE = "rtmp://a.rtmp.youtube.com/live2"

PADRAO: Dict[str, Any] = {
    # ── dispositivo ────────────────────────────────────────────────────────
    "camera_nome": "ly7ra",     # o que procurar pelo nome; vazio = primeira
    "camera_indice": -1,        # -1 = decidir pelo nome
    "largura": 1280,
    "altura": 720,
    "fps": 30,
    "microfone_nome": "",
    "microfone_indice": -1,

    # ── imagem: o que a IA regula sozinha ──────────────────────────────────
    "ia_ligada": True,
    "ia_exposicao": True,       # corrige claro/escuro medindo o rosto
    "ia_branco": True,          # corrige a cor da luz (branco puxando amarelo)
    "ia_ruido": True,           # reduz o chuvisco da webcam em luz baixa
    "ia_alvo_rosto": 0.55,      # luminância que a IA persegue no rosto (0..1)
    "ia_forca": 0.6,            # 0 = não mexe, 1 = corrige de uma vez (oscila)

    # ── look cinematográfico ───────────────────────────────────────────────
    "look": "s_cinetone",
    "look_forca": 0.85,
    "lut_arquivo": "",          # .cube dele, se tiver: vence o look de fábrica
    "grao": 0.10,
    "vinheta": 0.18,
    "halacao": 0.12,            # o brilho que sangra nas luzes fortes
    "nitidez": 0.35,

    # ── embelezamento ──────────────────────────────────────────────────────
    "beleza_ligada": True,
    "beleza_pele": 0.45,        # alisa a pele SEM apagar textura
    "beleza_manchas": 0.35,
    "beleza_olhos": 0.25,
    "beleza_dentes": 0.20,
    "beleza_so_no_rosto": True,

    # ── áudio ──────────────────────────────────────────────────────────────
    "audio_ligado": True,
    "au_ganho_db": 0.0,
    "au_corte_graves": 80.0,    # Hz -- tira o ronco da mesa e do ar
    "au_ruido": 0.55,           # quanto do chiado aprendido subtrair
    "au_portao": -42.0,         # dBFS abaixo disso é silêncio
    "au_ess": 0.35,             # o "sss" que estoura no microfone
    "au_eq_corpo": 1.5,         # dB em 200 Hz
    "au_eq_medio": -2.0,        # dB em 900 Hz -- o "abafado" mora aqui
    "au_eq_presenca": 3.0,      # dB em 4 kHz -- clareza da fala
    "au_compressor": 0.5,       # 0 = nada, 1 = nivela forte
    "au_teto_db": -1.0,         # limitador: nada passa disso

    # ── transmissão ────────────────────────────────────────────────────────
    "bitrate_video": 4500,      # kbps
    "bitrate_audio": 160,       # kbps
    "encoder": "auto",          # auto | libx264 | h264_nvenc | h264_qsv | h264_amf
    "gravar_local": True,       # cópia no disco, que a queda da internet não leva
    "pasta_gravacao": "",       # vazio = ao lado do software
}

# Faixa válida de cada número. Fora dela, o valor é grampeado -- não recusado.
# Ele digitar 200 em "nitidez" não pode virar um estouro no meio da live.
FAIXAS: Dict[str, tuple] = {
    "largura": (160, 3840), "altura": (120, 2160), "fps": (5, 60),
    "ia_alvo_rosto": (0.2, 0.9), "ia_forca": (0.0, 1.0),
    "look_forca": (0.0, 1.0), "grao": (0.0, 1.0), "vinheta": (0.0, 1.0),
    "halacao": (0.0, 1.0), "nitidez": (0.0, 1.0),
    "beleza_pele": (0.0, 1.0), "beleza_manchas": (0.0, 1.0),
    "beleza_olhos": (0.0, 1.0), "beleza_dentes": (0.0, 1.0),
    "au_ganho_db": (-24.0, 24.0), "au_corte_graves": (0.0, 300.0),
    "au_ruido": (0.0, 1.0), "au_portao": (-90.0, 0.0), "au_ess": (0.0, 1.0),
    "au_eq_corpo": (-12.0, 12.0), "au_eq_medio": (-12.0, 12.0),
    "au_eq_presenca": (-12.0, 12.0), "au_compressor": (0.0, 1.0),
    "au_teto_db": (-12.0, 0.0),
    "bitrate_video": (500, 51000), "bitrate_audio": (64, 320),
}


def grampear(campo: str, valor: Any) -> Any:
    """Prende o valor na faixa do campo. Fora de faixa não é erro: é limite."""
    if campo not in FAIXAS:
        return valor
    lo, hi = FAIXAS[campo]
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return PADRAO[campo]
    if v != v:  # NaN -- passa por float() e envenena tudo depois
        return PADRAO[campo]
    v = max(lo, min(hi, v))
    return int(round(v)) if isinstance(PADRAO[campo], int) else v


def carregar(caminho: Path | None = None) -> Dict[str, Any]:
    """Os ajustes dele por cima do padrão, campo por campo.

    Nunca estoura e nunca devolve dicionário incompleto: quem chama pode ler
    qualquer chave de PADRAO sem conferir se existe.
    """
    d = dict(PADRAO)
    arq = Path(caminho) if caminho else ARQ_AJUSTES
    try:
        if not arq.is_file():
            return d
        salvo = json.loads(arq.read_text(encoding="utf-8"))
        if not isinstance(salvo, dict):
            return d
    except Exception:
        return d  # arquivo corrompido volta ao padrão -- mas ver `salvar()`

    for k, padrao in PADRAO.items():
        if k not in salvo:
            continue
        v = salvo[k]
        if isinstance(padrao, bool):
            # bool antes de int: em Python True É int, e a ordem errada aqui
            # transformaria True em 1 e depois em faixa numérica.
            d[k] = bool(v) if isinstance(v, (bool, int)) else padrao
        elif isinstance(padrao, (int, float)):
            d[k] = grampear(k, v) if isinstance(v, (int, float)) else padrao
        elif isinstance(padrao, str):
            d[k] = v if isinstance(v, str) else padrao
    return d


def salvar(d: Dict[str, Any], caminho: Path | None = None) -> None:
    """Grava só o que é do padrão, e grava de forma que uma queda não corrompa.

    Escreve num temporário e troca de nome no fim (`os.replace`, atômico). Se a
    máquina cair no meio, o arquivo antigo continua inteiro -- ele não perde os
    ajustes porque faltou luz durante um autosave.
    """
    limpo = {k: (grampear(k, d[k]) if k in d else PADRAO[k]) for k in PADRAO}
    # a chave nunca, em nenhuma circunstância, entra aqui
    limpo.pop("chave", None)
    limpo.pop("chave_youtube", None)

    arq = Path(caminho) if caminho else ARQ_AJUSTES
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=str(arq.parent), prefix=".ajustes-",
                                   suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(limpo, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, arq)
        tmp = None
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# A CHAVE
# ─────────────────────────────────────────────────────────────────────────────

def chave(caminho: Path | None = None) -> str:
    """A chave de transmissão, ou vazio. Nunca estoura, nunca é impressa."""
    arq = Path(caminho) if caminho else ARQ_CHAVE
    try:
        if arq.is_file():
            return arq.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def gravar_chave(valor: str, caminho: Path | None = None) -> None:
    """Guarda a chave, só para o usuário do computador quando o sistema deixa."""
    arq = Path(caminho) if caminho else ARQ_CHAVE
    arq.write_text((valor or "").strip() + "\n", encoding="utf-8")
    try:
        os.chmod(arq, 0o600)   # no Windows não faz efeito; no Linux faz
    except OSError:
        pass


def mascara(valor: str) -> str:
    """Como a chave aparece na tela e em qualquer log: sem a chave.

    Mostro os 4 últimos porque ele precisa conferir SE é a chave certa sem que
    a gravação de tela dele entregue a chave inteira.
    """
    v = (valor or "").strip()
    if not v:
        return "(nenhuma)"
    if len(v) <= 4:
        return "•" * len(v)
    return "•" * min(12, len(v) - 4) + v[-4:]


def url_youtube(ch: str = "", servidor: str = RTMP_YOUTUBE) -> str:
    """O endereço completo da live. Só quem transmite chama isto."""
    c = (ch or chave()).strip()
    if not c:
        raise ValueError("sem chave de transmissão")
    return servidor.rstrip("/") + "/" + c
