# -*- coding: utf-8 -*-
"""
ÁUDIO — a cadeia montada, o microfone lido, e os medidores que ele olha.

Este arquivo é o "editor de áudio ao vivo": junta as peças do `audio_dsp.py`
na ordem certa, lê o microfone num fluxo de tempo real e entrega blocos
prontos para a transmissão, medindo o que sai.

A REGRA DE OURO DE QUEM ESCREVE O CALLBACK DE ÁUDIO
───────────────────────────────────────────────────
O `sounddevice` chama `_callback` a cada bloco, de uma thread de tempo real do
sistema. Se essa função demorar mais que a duração do bloco, o som ESTALA --
e estala de um jeito que não dá para consertar depois.

Então dentro do callback não entra: alocação grande, arquivo, rede, interface
gráfica, `print`, nem lock que possa esperar. O callback copia o bloco para
uma fila e volta. Quem processa é outra thread. É por isso que a cadeia,
mesmo custando 6% de um núcleo, não pode rodar lá dentro.

O QUE ACONTECE SE A FILA ENCHER
───────────────────────────────
Descarto o bloco mais VELHO, não o mais novo. Numa live o som antigo não tem
valor: entregar tarde é pior que não entregar. E conto os descartes num
contador que aparece na tela, porque um descarte silencioso vira "o áudio
estava estranho e ninguém sabe por quê".
"""
from __future__ import annotations

import math
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy as np

import audio_dsp as D
from audio_dsp import TAXA, db_para_ganho, ganho_para_db

BLOCO = 1024


@dataclass
class Medidores:
    """O que a tela mostra. Tudo em dBFS, que é a unidade que ele vai ver."""
    pico_db: float = -90.0
    rms_db: float = -90.0
    reducao_db: float = 0.0       # quanto o compressor está segurando
    portao_aberto: float = 0.0    # 0 fechado, 1 aberto
    clipes: int = 0               # quantas vezes bateu no teto
    descartes: int = 0
    latencia_ms: float = 0.0


class Cadeia:
    """A cadeia inteira, na ordem que o cabeçalho do audio_dsp explica."""

    def __init__(self, taxa: int = TAXA, canais: int = 1):
        self.taxa = taxa
        self.canais = canais
        self.hp = D.passa_altas(80.0, taxa, 0.707, canais)
        self.ruido = D.ReducaoRuido(taxa)
        self.portao = D.Portao(-42.0, taxa)
        self.deesser = D.DeEsser(taxa, canais)
        self.eq_corpo = D.sino(200.0, 0.0, 0.9, taxa, canais)
        self.eq_medio = D.sino(900.0, 0.0, 1.1, taxa, canais)
        self.eq_presenca = D.prateleira_alta(4000.0, 0.0, taxa, 0.707, canais)
        self.comp = D.Compressor(taxa)
        self.lim = D.Limitador(taxa)
        self.medidores = Medidores()
        self._corte_atual = 80.0
        self._eq_atual = (0.0, 0.0, 0.0)

    # ── os controles dele, aplicados só quando MUDAM ──────────────────────
    def ajustar(self, corte_graves: float, eq_corpo: float, eq_medio: float,
                eq_presenca: float, limiar_portao: float) -> None:
        """Refazer coeficiente de biquad a cada bloco é desperdício e, pior,
        provoca um saltinho no som. Só refaço quando o número mudou."""
        if abs(corte_graves - self._corte_atual) > 0.5:
            novo = D.passa_altas(max(10.0, corte_graves), self.taxa, 0.707,
                                 self.canais)
            self.hp.set(novo.b0, novo.b1, novo.b2, novo.a1, novo.a2)
            self._corte_atual = corte_graves
        novo_eq = (round(eq_corpo, 2), round(eq_medio, 2), round(eq_presenca, 2))
        if novo_eq != self._eq_atual:
            for filtro, fab in (
                    (self.eq_corpo, D.sino(200.0, novo_eq[0], 0.9, self.taxa)),
                    (self.eq_medio, D.sino(900.0, novo_eq[1], 1.1, self.taxa)),
                    (self.eq_presenca, D.prateleira_alta(4000.0, novo_eq[2],
                                                         self.taxa))):
                filtro.set(fab.b0, fab.b1, fab.b2, fab.a1, fab.a2)
            self._eq_atual = novo_eq
        self.portao.limiar_db = float(limiar_portao)

    @property
    def latencia_ms(self) -> float:
        """O atraso que a cadeia introduz. O vídeo é atrasado no mesmo tanto.

        Sem isto a voz chega antes da imagem e a boca não casa -- o defeito
        que faz o espectador achar que "o vídeo está ruim" sem saber dizer
        o motivo.
        """
        amostras = self.ruido.latencia_amostras + self.lim.latencia_amostras
        return amostras / self.taxa * 1000.0

    def processar(self, x: np.ndarray, ganho_db: float = 0.0,
                  forca_ruido: float = 0.55, ess: float = 0.35,
                  compressor: float = 0.5, teto_db: float = -1.0
                  ) -> np.ndarray:
        """Um bloco, a cadeia inteira. Mono ou (n, canais)."""
        y = np.asarray(x, dtype=np.float32)
        if abs(ganho_db) > 0.01:
            y = y * np.float32(db_para_ganho(ganho_db))

        y = self.hp.processar(y)

        if forca_ruido > 0.001:
            # a redução trabalha em mono: chiado é igual nos dois canais e
            # processar duas vezes custaria o dobro pelo mesmo resultado
            if y.ndim > 1:
                mono = y.mean(axis=1)
                limpo = self.ruido.processar(mono, forca_ruido)
                if limpo.size == 0:
                    return np.zeros((0, y.shape[1]), dtype=np.float32)
                # a diferença aplicada aos dois canais preserva a imagem estéreo
                n = limpo.shape[0]
                y = y[:n] + (limpo - mono[:n])[:, None]
            else:
                y = self.ruido.processar(y, forca_ruido)
                if y.size == 0:
                    return y

        y, aberto = self.portao.processar(y)
        y = self.deesser.processar(y, ess)
        y = self.eq_corpo.processar(y)
        y = self.eq_medio.processar(y)
        y = self.eq_presenca.processar(y)
        y, reducao = self.comp.processar(y, compressor)
        y = self.lim.processar(y, teto_db)

        m = self.medidores
        if y.size:
            pico = float(np.abs(y).max())
            rms = float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))
            m.pico_db = ganho_para_db(pico)
            m.rms_db = ganho_para_db(rms)
            if pico >= db_para_ganho(teto_db) - 1e-6:
                m.clipes += 1
        m.reducao_db = reducao
        m.portao_aberto = aberto
        m.latencia_ms = self.latencia_ms
        return y


def para_pcm16(x: np.ndarray) -> bytes:
    """Float -1..1 para PCM 16 bits, que é o que o ffmpeg vai receber.

    O corte antes da conversão não é firula: sem ele, uma amostra em 1.01
    daria a volta no inteiro e viraria um estouro NEGATIVO -- um estalo alto
    no meio da live, vindo justamente de um sinal quase correto.
    """
    y = np.clip(np.asarray(x, dtype=np.float32), -1.0, 1.0)
    return (y * 32767.0).astype("<i2").tobytes()


class Microfone:
    """Lê o microfone e entrega blocos JÁ PROCESSADOS a quem pediu."""

    def __init__(self, indice: int = -1, taxa: int = TAXA, canais: int = 1,
                 bloco: int = BLOCO):
        self.indice = indice
        self.taxa = taxa
        self.canais = max(1, min(2, int(canais)))
        self.bloco = int(bloco)
        self.cadeia = Cadeia(taxa, self.canais)
        self.fila: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=16)
        self.saida: Optional[Callable[[np.ndarray], None]] = None
        self.ajustes = dict(ganho_db=0.0, forca_ruido=0.55, ess=0.35,
                            compressor=0.5, teto_db=-1.0)
        self.erro = ""
        self._stream = None
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _callback(self, dados, quadros, tempo, estado):        # noqa: ARG002
        """Roda na thread de tempo real do sistema. Não faz nada além disto."""
        try:
            self.fila.put_nowait(np.array(dados, dtype=np.float32, copy=True))
        except queue.Full:
            # descarta o mais VELHO: numa live, som atrasado não vale nada
            try:
                self.fila.get_nowait()
                self.fila.put_nowait(np.array(dados, dtype=np.float32,
                                              copy=True))
            except Exception:
                pass
            self.cadeia.medidores.descartes += 1

    def _trabalhar(self) -> None:
        while not self._parar.is_set():
            try:
                bloco = self.fila.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                if bloco.ndim > 1 and bloco.shape[1] == 1:
                    bloco = bloco[:, 0]
                pronto = self.cadeia.processar(bloco, **self.ajustes)
                if pronto.size and self.saida is not None:
                    self.saida(pronto)
            except Exception as e:                    # nunca derruba a thread
                self.erro = f"{type(e).__name__}: {e}"

    def abrir(self) -> Tuple[bool, str]:
        try:
            import sounddevice as sd
        except Exception:
            return False, ("sounddevice não instalado — sem áudio. "
                           "Rode 0_INSTALAR.bat")
        try:
            kw = {}
            if self.indice is not None and self.indice >= 0:
                kw["device"] = self.indice
            self._stream = sd.InputStream(
                samplerate=self.taxa, channels=self.canais, dtype="float32",
                blocksize=self.bloco, callback=self._callback, **kw)
            self._stream.start()
        except Exception as e:
            return False, f"não abriu o microfone: {e}"
        self._parar.clear()
        self._thread = threading.Thread(target=self._trabalhar, daemon=True,
                                        name="audio")
        self._thread.start()
        return True, f"microfone aberto a {self.taxa} Hz, {self.canais} canal(is)"

    def fechar(self) -> None:
        self._parar.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._thread is not None:
            self._thread.join(timeout=1.5)
            self._thread = None
