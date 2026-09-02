# -*- coding: utf-8 -*-
"""
A esteira: câmera -> fundo -> filtros -> YouTube e câmera virtual.

TRÊS THREADS, E POR QUE NÃO UMA
-------------------------------
Num laço só, o tempo de escrever no ffmpeg entraria no intervalo entre duas
leituras da câmera. Como a escrita bloqueia quando a rede engasga, a captura
pararia junto — e o driver da webcam, sem ninguém consumindo, acumula quadros
velhos. O resultado é a live atrasando alguns segundos e nunca mais recuperando.

Separado em três:

    captura  ->  [fila crua]  ->  processamento  ->  [fila pronta]  ->  envio

cada etapa sofre sozinha. Rede ruim segura só o envio; filtro pesado segura só
o processamento; a câmera continua sendo lida na cadência dela.

FILA CURTA QUE DESCARTA O MAIS VELHO
------------------------------------
As duas filas têm dois ou três lugares e, quando enchem, jogam fora o quadro
ANTIGO para guardar o novo. Isso é deliberado: em transmissão ao vivo, um
quadro atrasado não vale nada — ninguém quer ver o que aconteceu há dois
segundos. Fila grande transformaria pico de carga em atraso permanente. O
descarte é contado, aparece nas métricas e é o que a IA supervisora usa para
dizer "seu computador não está dando conta", com número em vez de palpite.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Dict, Optional

import numpy as np

from . import imagem as IMG
from .camera import Fonte, abrir_fonte
from .config import Perfil
from .filtros import Ajustes, aplicar
from .fundo import EfeitoFundo, MotorFundo, SegmentadorFundoAprendido, criar_segmentador
from .metricas import Metricas
from .saida_rtmp import EncoderRTMP
from .saida_virtual import abrir_camera_virtual


def _por_ultimo(fila: "queue.Queue", item, ao_descartar: Callable[[], None]) -> None:
    """Coloca na fila; se estiver cheia, descarta o mais antigo e insere."""
    try:
        fila.put_nowait(item)
    except queue.Full:
        try:
            fila.get_nowait()
            ao_descartar()
        except queue.Empty:
            pass
        try:
            fila.put_nowait(item)
        except queue.Full:
            ao_descartar()


class Pipeline:
    """A transmissão inteira, ligável e desligável."""

    def __init__(self, perfil: Perfil, ao_avisar: Optional[Callable[[str], None]] = None):
        self.perfil = perfil
        self._avisar_externo = ao_avisar or (lambda _: None)
        self.metricas = Metricas(fps_alvo=perfil.camera.fps)
        self.fonte: Optional[Fonte] = None
        self.encoder: Optional[EncoderRTMP] = None
        self.camera_virtual = None
        self.motor_fundo = MotorFundo(criar_segmentador(perfil.segmentador), perfil.fundo)

        self._fila_crua: "queue.Queue" = queue.Queue(maxsize=2)
        self._fila_pronta: "queue.Queue" = queue.Queue(maxsize=3)
        self._parar = threading.Event()
        self._threads: list[threading.Thread] = []
        self._trava = threading.Lock()

        self._ajustes = perfil.ajustes
        self._ultimo_cru: Optional[np.ndarray] = None
        self._ultimo_pronto: Optional[np.ndarray] = None
        self.rodando = False
        self.mensagem_saida = ""
        self._contador = 0

    # -- controles ao vivo --------------------------------------------------
    @property
    def ajustes(self) -> Ajustes:
        return self._ajustes

    def definir_ajustes(self, ajustes: Ajustes) -> None:
        with self._trava:
            self._ajustes = ajustes.validar()
            self.perfil.ajustes = self._ajustes

    def definir_fundo(self, efeito: EfeitoFundo) -> None:
        self.motor_fundo.definir_efeito(efeito)
        self.perfil.fundo = efeito

    def definir_segmentador(self, preferencia: str) -> None:
        self.motor_fundo.definir_segmentador(criar_segmentador(preferencia))
        self.perfil.segmentador = preferencia
        self.metricas.segmentador = self.motor_fundo.segmentador.nome

    def aprender_fundo(self) -> bool:
        """Memoriza o fundo vazio para o recorte sem rede neural."""
        seg = self.motor_fundo.segmentador
        quadro = self._ultimo_cru
        if not isinstance(seg, SegmentadorFundoAprendido) or quadro is None:
            return False
        seg.aprender(quadro)
        self._avisar("Fundo memorizado. Pode voltar para o quadro.")
        return True

    def preview(self) -> Optional[np.ndarray]:
        """O último quadro pronto, para a tela do painel."""
        return self._ultimo_pronto

    def _avisar(self, texto: str) -> None:
        self.metricas.avisar(texto)
        try:
            self._avisar_externo(texto)
        except Exception:
            pass

    # -- ciclo de vida ------------------------------------------------------
    def iniciar(self) -> None:
        if self.rodando:
            return
        self._parar.clear()
        cfg = self.perfil.camera

        self.fonte = abrir_fonte(cfg)
        self.fonte.iniciar()
        self.metricas = Metricas(fps_alvo=cfg.fps)
        self.metricas.segmentador = self.motor_fundo.segmentador.nome
        self.metricas.comecar()

        if self.perfil.transmitir:
            saida = self.perfil.saida
            saida.largura, saida.altura, saida.fps = cfg.largura, cfg.altura, cfg.fps
            self.encoder = EncoderRTMP(
                saida,
                ao_medir=self.metricas.atualizar_encoder,
                ao_avisar=self._avisar)
            self.encoder.iniciar()
            self._avisar("Transmissão iniciada — confira o YouTube Studio.")

        if self.perfil.camera_virtual:
            self.camera_virtual, self.mensagem_saida = abrir_camera_virtual(
                cfg.largura, cfg.altura, cfg.fps)
            self._avisar(self.mensagem_saida.split("\n")[0])

        self.rodando = True
        for alvo in (self._laco_captura, self._laco_processamento, self._laco_envio):
            t = threading.Thread(target=alvo, name=alvo.__name__, daemon=True)
            t.start()
            self._threads.append(t)

    def parar(self) -> None:
        self._parar.set()
        for t in self._threads:
            t.join(timeout=3.0)
        self._threads.clear()
        for recurso in (self.encoder, self.camera_virtual, self.fonte):
            if recurso is not None:
                try:
                    recurso.parar()
                except Exception:
                    pass
        self.encoder = None
        self.camera_virtual = None
        self.fonte = None
        self.rodando = False

    # -- as três esteiras ---------------------------------------------------
    def _laco_captura(self) -> None:
        cfg = self.perfil.camera
        reconexoes_vistas = 0

        # RITMO DA CAPTURA
        # Uma webcam entrega quadro na cadência dela e a leitura BLOQUEIA até o
        # próximo chegar — o laço se acerta sozinho. Mas arquivo de vídeo e a
        # fonte sintética devolvem quadro na velocidade do processador: sem
        # relógio aqui, o laço rodaria a 100 fps para transmitir 30, gastando
        # CPU para produzir quadro que a fila descarta em seguida. Com o
        # relógio, quem já é ritmado não espera nada e quem não é passa a ser.
        intervalo = 1.0 / max(1, int(cfg.fps))
        proximo = time.perf_counter()

        while not self._parar.is_set():
            agora = time.perf_counter()
            if agora < proximo:
                time.sleep(min(0.05, proximo - agora))
                continue
            # sem recuperar atraso em rajada: depois de uma pausa longa, o
            # próximo prazo parte de agora, não de um passado acumulado
            proximo = max(proximo + intervalo, agora)

            quadro = None
            try:
                quadro = self.fonte.ler() if self.fonte else None
            except Exception as e:
                self._avisar(f"Falha lendo a câmera: {e}")

            vistas_agora = getattr(self.fonte, "reconexoes", 0)
            if vistas_agora > reconexoes_vistas:
                self.metricas.marcar_reconexao()
                self._avisar("A câmera caiu e foi reaberta.")
                reconexoes_vistas = vistas_agora

            if quadro is None:
                time.sleep(0.02)
                continue

            if quadro.shape[0] != cfg.altura or quadro.shape[1] != cfg.largura:
                quadro = IMG.para_bytes(IMG.enquadrar(quadro, cfg.largura, cfg.altura))

            self._ultimo_cru = quadro
            self.metricas.marcar_captura()
            _por_ultimo(self._fila_crua, quadro, self.metricas.marcar_descarte)

    def _laco_processamento(self) -> None:
        while not self._parar.is_set():
            try:
                quadro = self._fila_crua.get(timeout=0.2)
            except queue.Empty:
                continue

            comecou = time.perf_counter()
            try:
                com_fundo, mascara = self.motor_fundo.aplicar(quadro)
                with self._trava:
                    ajustes = self._ajustes
                pronto = aplicar(com_fundo, ajustes, mascara)
            except Exception as e:
                # Um quadro que explode no filtro não pode derrubar a live: passa
                # o quadro cru adiante e registra. Melhor a imagem sem efeito por
                # um instante do que a transmissão morta.
                self._avisar(f"Erro ao processar um quadro: {e}")
                pronto = quadro
            self.metricas.marcar_processamento((time.perf_counter() - comecou) * 1000.0)

            self._contador += 1
            if self._contador % 30 == 0:
                # o brilho médio é para o diagnóstico de exposição; a cada 30
                # quadros é suficiente e não pesa no orçamento por quadro
                amostra = pronto[::8, ::8]
                self.metricas.marcar_brilho(float(amostra.mean()) / 255.0)

            self._ultimo_pronto = pronto
            _por_ultimo(self._fila_pronta, pronto, self.metricas.marcar_descarte)

    def _laco_envio(self) -> None:
        while not self._parar.is_set():
            try:
                quadro = self._fila_pronta.get(timeout=0.2)
            except queue.Empty:
                continue
            enviou = False
            if self.encoder is not None:
                enviou = self.encoder.escrever(quadro) or enviou
            if self.camera_virtual is not None:
                enviou = self.camera_virtual.escrever(quadro) or enviou
            if self.encoder is None and self.camera_virtual is None:
                enviou = True          # modo só-preview: o quadro "chegou" ao destino
            if enviou:
                self.metricas.marcar_saida()

    # -- leitura ------------------------------------------------------------
    def _video_kbps_alvo(self) -> int:
        from . import youtube as YT
        cfg = self.perfil.saida
        if cfg.video_kbps:
            return int(cfg.video_kbps)
        return int(YT.preset(self.perfil.camera.altura, self.perfil.camera.fps)["video_kbps"])

    def estado(self) -> Dict:
        """Instantâneo completo — é o que o painel mostra e a IA analisa."""
        dados = self.metricas.instantaneo()
        seg = self.motor_fundo.segmentador
        dados.update({
            "rodando": self.rodando,
            "transmitindo": self.encoder is not None and self.encoder.vivo(),
            "camera_virtual": self.camera_virtual is not None,
            "reinicios_encoder": self.encoder.reinicios if self.encoder else 0,
            "modo_fundo": self.motor_fundo.efeito.modo,
            "segmentador": seg.nome,
            "segmentador_pronto": seg.pronto(),
            "aviso_segmentador": seg.aviso(),
            "resolucao": f"{self.perfil.camera.largura}x{self.perfil.camera.altura}",
            # a taxa configurada vai junto para a regra que compara o que foi
            # pedido com o que o ffmpeg conseguiu de fato empurrar
            "video_kbps_alvo": self._video_kbps_alvo(),
            "origem": str(self.perfil.camera.origem),
        })
        return dados
