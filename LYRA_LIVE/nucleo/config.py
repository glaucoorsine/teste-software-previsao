# -*- coding: utf-8 -*-
"""
O perfil: o que fica salvo entre uma live e outra.

ONDE FICA
---------
Em `Documentos/LyraLive/perfil.json` — a mesma ideia das "memórias" dos outros
softwares desta pasta: fora do código, num lugar que a pessoa acha, que não se
perde quando o programa é atualizado e que o antivírus não implica.

A CHAVE DE TRANSMISSÃO NÃO ENTRA NO PERFIL
------------------------------------------
Ela mora em `chave_transmissao.txt`, sozinha, com permissão restrita a quem
gravou. Três motivos:

1. Perfil é o arquivo que se manda para outra pessoa quando se quer copiar uma
   configuração de imagem. Mandar junto a chave da live é entregar o canal.
2. Separada, dá para apagar a chave sem perder os ajustes de imagem.
3. `ConfigSaida.como_dicionario()` já a remove na origem, então nem por engano
   ela cai no JSON.

A variável de ambiente `LYRA_CHAVE` (ou `YOUTUBE_STREAM_KEY`) tem prioridade
sobre o arquivo, para quem prefere não gravar a chave em disco nenhum.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .camera import ConfigCamera
from .filtros import Ajustes
from .fundo import EfeitoFundo
from .saida_rtmp import ConfigSaida

NOME_PERFIL = "perfil.json"
NOME_CHAVE = "chave_transmissao.txt"


def pasta_dados() -> Path:
    """A pasta do software nos Documentos, criada na hora se não existir."""
    forcada = os.environ.get("LYRA_PASTA")
    if forcada:
        alvo = Path(forcada)
    else:
        casa = Path.home()
        documentos = casa / "Documents"
        if not documentos.is_dir():
            documentos = casa / "Documentos"     # Windows em português
        if not documentos.is_dir():
            documentos = casa
        alvo = documentos / "LyraLive"
    try:
        alvo.mkdir(parents=True, exist_ok=True)
    except Exception:
        alvo = Path.cwd()
    return alvo


@dataclass
class Perfil:
    """Tudo o que o painel configura, num objeto só."""
    camera: ConfigCamera = field(default_factory=ConfigCamera)
    ajustes: Ajustes = field(default_factory=Ajustes)
    fundo: EfeitoFundo = field(default_factory=EfeitoFundo)
    saida: ConfigSaida = field(default_factory=ConfigSaida)
    segmentador: str = "auto"
    camera_virtual: bool = False
    transmitir: bool = False
    ia_ativa: bool = True
    ia_modelo: str = "qwen2.5:0.5b"
    ia_endereco: str = "http://127.0.0.1:11434"
    ia_intervalo_s: int = 20

    def como_dicionario(self) -> Dict:
        return {
            "camera": self.camera.como_dicionario(),
            "ajustes": self.ajustes.como_dicionario(),
            "fundo": self.fundo.como_dicionario(),
            "saida": self.saida.como_dicionario(),
            "segmentador": self.segmentador,
            "camera_virtual": bool(self.camera_virtual),
            "transmitir": bool(self.transmitir),
            "ia_ativa": bool(self.ia_ativa),
            "ia_modelo": self.ia_modelo,
            "ia_endereco": self.ia_endereco,
            "ia_intervalo_s": int(self.ia_intervalo_s),
        }

    @staticmethod
    def de_dicionario(d: Optional[Dict]) -> "Perfil":
        d = dict(d or {})
        p = Perfil(
            camera=ConfigCamera.de_dicionario(d.get("camera")),
            ajustes=Ajustes.de_dicionario(d.get("ajustes")),
            fundo=EfeitoFundo.de_dicionario(d.get("fundo")),
            saida=ConfigSaida.de_dicionario(d.get("saida")),
        )
        p.segmentador = str(d.get("segmentador", "auto"))
        p.camera_virtual = bool(d.get("camera_virtual", False))
        p.transmitir = bool(d.get("transmitir", False))
        p.ia_ativa = bool(d.get("ia_ativa", True))
        p.ia_modelo = str(d.get("ia_modelo", "qwen2.5:0.5b"))
        p.ia_endereco = str(d.get("ia_endereco", "http://127.0.0.1:11434"))
        try:
            p.ia_intervalo_s = max(5, int(d.get("ia_intervalo_s", 20)))
        except Exception:
            p.ia_intervalo_s = 20
        return p


def carregar(pasta: Optional[Path] = None) -> Perfil:
    """Lê o perfil. Arquivo corrompido vira perfil padrão, nunca uma exceção.

    Um JSON quebrado — queda de energia no meio da gravação — não pode impedir o
    software de abrir. O padrão funciona; a pessoa reconfigura e regrava.
    """
    alvo = (pasta or pasta_dados()) / NOME_PERFIL
    try:
        if alvo.is_file():
            return Perfil.de_dicionario(json.loads(alvo.read_text(encoding="utf-8")))
    except Exception:
        pass
    return Perfil()


def salvar(perfil: Perfil, pasta: Optional[Path] = None) -> bool:
    """Grava o perfil por arquivo temporário + troca atômica.

    Escrever direto no arquivo final significa que uma interrupção no meio
    deixa um JSON truncado — e aí a configuração inteira se perde. Gravar ao
    lado e renomear no fim faz a troca ser tudo-ou-nada.
    """
    base = pasta or pasta_dados()
    alvo = base / NOME_PERFIL
    temporario = base / (NOME_PERFIL + ".tmp")
    try:
        temporario.write_text(
            json.dumps(perfil.como_dicionario(), ensure_ascii=False, indent=2),
            encoding="utf-8")
        os.replace(temporario, alvo)
        return True
    except Exception:
        try:
            temporario.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def carregar_chave(pasta: Optional[Path] = None) -> str:
    """A chave de transmissão: ambiente primeiro, arquivo depois."""
    for variavel in ("LYRA_CHAVE", "YOUTUBE_STREAM_KEY"):
        valor = os.environ.get(variavel)
        if valor and valor.strip():
            return valor.strip()
    alvo = (pasta or pasta_dados()) / NOME_CHAVE
    try:
        if alvo.is_file():
            return alvo.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def salvar_chave(chave: str, pasta: Optional[Path] = None) -> bool:
    """Grava a chave só para o dono do arquivo (0600 onde o sistema respeita)."""
    alvo = (pasta or pasta_dados()) / NOME_CHAVE
    try:
        texto = (chave or "").strip()
        if not texto:
            alvo.unlink(missing_ok=True)
            return True
        alvo.write_text(texto, encoding="utf-8")
        try:
            os.chmod(alvo, 0o600)
        except Exception:
            pass       # no Windows o chmod não faz nada útil, e tudo bem
        return True
    except Exception:
        return False
