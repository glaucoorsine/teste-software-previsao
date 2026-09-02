# -*- coding: utf-8 -*-
"""
As medições — a matéria-prima da IA supervisora.

POR QUE ISTO EXISTE SEPARADO
----------------------------
A IA que acompanha a live não olha a imagem nem adivinha: ela lê estes números.
Se a medição for vaga, o diagnóstico vira chute com cara de autoridade — que é
o pior resultado possível de colocar um modelo de linguagem para vigiar algo.

Então cada número aqui tem definição exata e origem única:

* `fps_captura` — quadros que a câmera entregou, contados por relógio numa
  janela deslizante de alguns segundos. Não é o fps que a câmera PROMETE.
* `fps_saida` — quadros que saíram para o encoder. A diferença entre os dois é
  exatamente o que o computador não deu conta de processar.
* `ms_processamento` — quanto o filtro leva por quadro, com a mediana e o pico.
  A mediana diz se dá para manter a cadência; o pico diz se trava às vezes.
* `descartes` — quadros jogados fora por fila cheia. Zero é o normal.
* `reconexoes` — quantas vezes a câmera precisou ser reaberta.
* `encoder` — o que o próprio ffmpeg relata: velocidade, taxa real, quadros
  perdidos. Isso não é estimado aqui, é lido de quem está transmitindo.

JANELA DESLIZANTE, NÃO MÉDIA DESDE O INÍCIO
-------------------------------------------
Média desde o início esconde problema: uma live que rodou uma hora a 30 fps e
despencou para 5 fps agora ainda mostra média de 29. A janela é curta de
propósito — o que interessa é como está AGORA.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

JANELA_S = 5.0          # segundos de história para as taxas
MAX_AMOSTRAS = 600


class Metricas:
    """Coletor com trava — as threads de captura, filtro e envio escrevem aqui."""

    def __init__(self, fps_alvo: int = 30, janela_s: float = JANELA_S):
        self._trava = threading.Lock()
        self.fps_alvo = int(fps_alvo)
        self._janela = float(janela_s)
        self._captura: Deque[float] = deque(maxlen=MAX_AMOSTRAS)
        self._saida: Deque[float] = deque(maxlen=MAX_AMOSTRAS)
        self._proc: Deque[float] = deque(maxlen=MAX_AMOSTRAS)
        self.descartes = 0
        self.reconexoes = 0
        self.quadros_capturados = 0
        self.quadros_enviados = 0
        self.inicio: Optional[float] = None
        self.encoder: Dict[str, float] = {}
        self.avisos: Deque[str] = deque(maxlen=40)
        self.segmentador = ""
        self.brilho_medio: Optional[float] = None

    # -- escrita ------------------------------------------------------------
    def comecar(self) -> None:
        with self._trava:
            self.inicio = time.time()

    def marcar_captura(self) -> None:
        agora = time.time()
        with self._trava:
            self._captura.append(agora)
            self.quadros_capturados += 1

    def marcar_saida(self) -> None:
        agora = time.time()
        with self._trava:
            self._saida.append(agora)
            self.quadros_enviados += 1

    def marcar_processamento(self, ms: float) -> None:
        with self._trava:
            self._proc.append(float(ms))

    def marcar_descarte(self, n: int = 1) -> None:
        with self._trava:
            self.descartes += int(n)

    def marcar_reconexao(self) -> None:
        with self._trava:
            self.reconexoes += 1

    def marcar_brilho(self, valor: float) -> None:
        with self._trava:
            self.brilho_medio = float(valor)

    def atualizar_encoder(self, dados: Dict) -> None:
        with self._trava:
            self.encoder.update(dados)

    def avisar(self, texto: str) -> None:
        """Guarda uma linha de aviso técnico (stderr do ffmpeg, falha de câmera)."""
        if not texto:
            return
        with self._trava:
            self.avisos.append(f"{time.strftime('%H:%M:%S')} {str(texto).strip()[:300]}")

    # -- leitura ------------------------------------------------------------
    def _taxa(self, marcas: Deque[float], agora: float) -> float:
        """Quadros por segundo dentro da janela. Precisa de 2 marcas para existir."""
        corte = agora - self._janela
        recentes = [t for t in marcas if t >= corte]
        if len(recentes) < 2:
            return 0.0
        intervalo = recentes[-1] - recentes[0]
        if intervalo <= 0:
            return 0.0
        return (len(recentes) - 1) / intervalo

    @staticmethod
    def _percentil(valores: List[float], p: float) -> float:
        if not valores:
            return 0.0
        ordenados = sorted(valores)
        i = min(len(ordenados) - 1, max(0, int(round((len(ordenados) - 1) * p))))
        return float(ordenados[i])

    def instantaneo(self) -> Dict:
        """Uma fotografia coerente de tudo. É isto que a IA supervisora recebe."""
        agora = time.time()
        with self._trava:
            captura = list(self._captura)
            saida = list(self._saida)
            proc = list(self._proc)[-120:]
            dados = {
                "fps_alvo": self.fps_alvo,
                "descartes": self.descartes,
                "reconexoes": self.reconexoes,
                "quadros_capturados": self.quadros_capturados,
                "quadros_enviados": self.quadros_enviados,
                "encoder": dict(self.encoder),
                "avisos": list(self.avisos)[-6:],
                "segmentador": self.segmentador,
                "brilho_medio": self.brilho_medio,
                "segundos_no_ar": (agora - self.inicio) if self.inicio else 0.0,
            }
        dados["fps_captura"] = round(self._taxa(deque(captura), agora), 1)
        dados["fps_saida"] = round(self._taxa(deque(saida), agora), 1)
        dados["ms_processamento"] = round(self._percentil(proc, 0.5), 1)
        dados["ms_processamento_pico"] = round(self._percentil(proc, 0.95), 1)
        dados["orcamento_ms"] = round(1000.0 / max(1, self.fps_alvo), 1)
        return dados


def analisar_progresso(linha: str) -> Dict[str, float]:
    """Lê uma linha `chave=valor` do `-progress` do ffmpeg.

    Pedimos ao ffmpeg o relatório estruturado em vez de raspar o stderr dele.
    O stderr muda de formato entre versões e mistura erro com estatística; o
    `-progress` é feito para ser lido por programa e não mudou em anos.
    """
    fora: Dict[str, float] = {}
    if not linha or "=" not in linha:
        return fora
    chave, _, valor = linha.strip().partition("=")
    chave, valor = chave.strip(), valor.strip()
    try:
        if chave == "bitrate" and valor.endswith("bits/s"):
            numero = valor.replace("kbits/s", "").replace("bits/s", "")
            fora["bitrate_kbps"] = float(numero) if "kbits" in valor else float(numero) / 1000.0
        elif chave == "speed" and valor.endswith("x"):
            fora["velocidade"] = float(valor[:-1])
        elif chave == "fps":
            fora["fps_encoder"] = float(valor)
        elif chave == "drop_frames":
            fora["quadros_perdidos"] = float(valor)
        elif chave == "dup_frames":
            fora["quadros_duplicados"] = float(valor)
        elif chave == "total_size":
            fora["bytes_enviados"] = float(valor)
        elif chave == "out_time_us":
            fora["segundos_codificados"] = float(valor) / 1e6
    except (ValueError, TypeError):
        return {}
    return fora
