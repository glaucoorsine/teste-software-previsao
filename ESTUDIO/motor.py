# -*- coding: utf-8 -*-
"""
MOTOR — a cadeia de imagem inteira, com governador de desempenho.

A ORDEM DA CADEIA, E O PORQUÊ DE CADA POSIÇÃO
─────────────────────────────────────────────
 1. MEDIR (a cada 3 quadros)   a IA precisa saber antes de decidir
 2. correção da IA             exposição e branco: propriedades da captura,
                               têm de ser consertadas antes de qualquer gosto
 3. ruído temporal             limpar ANTES de realçar, senão realço o chiado
 4. desfoque de fundo          antes do embelezamento: o borrão do fundo não
                               deve passar pelo alisamento de pele
 5. embelezamento              sobre a pessoa já isolada
 6. LOOK (tabela 64³)          o filtro cinematográfico
 7. halação, vinheta, grão     acabamento de lente
 8. nitidez                    sempre por último: nitidez antes do contraste
                               vira borda branca de televisão antiga

O GOVERNADOR
────────────
Medi cada etapa numa máquina de 4 núcleos a 2,1 GHz (a mais fraca que tenho),
a 1280x720:

    embelezamento  22,9 ms      desfoque de fundo   9,9 ms
    look (64³)      5,9 ms      medição da IA       5,6 ms
    acabamento      ~4 ms       ruído temporal      ~2 ms

Somando com folga, passa dos 33 ms de um quadro a 30 fps. Numa máquina mais
rápida cabe; na dele eu não sei, e prometer que cabe seria mentira.

Então o motor MEDE o tempo real e, se estourar, desliga efeito -- na ordem do
que custa mais e entrega menos -- e DIZ na tela o que desligou e por quê. A
alternativa seria a live cair para 12 quadros por segundo sem explicação, que
é o que acontece em quase todo software que promete efeito demais.

A ordem de sacrifício foi escolhida pelo que ele pediu, não pelo que é fácil:
grão e halação são enfeite e caem primeiro; o embelezamento e o look, que
foram o pedido, caem por último, e antes deles eu ainda tento baixar a
resolução do embelezamento.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

import beleza as B
import fundo as F
import ia_visual as IA
import visual as V

# Ordem em que os efeitos são sacrificados quando o quadro não cabe no tempo.
SACRIFICIO = [
    ("grao", "grão de filme"),
    ("halacao", "halação"),
    ("vinheta", "vinheta"),
    ("nitidez", "nitidez"),
    ("beleza_leve", "embelezamento em resolução reduzida"),
    ("desfoque", "desfoque de fundo"),
    ("beleza", "embelezamento"),
    ("look", "filtro cinematográfico"),
]


@dataclass
class Diagnostico:
    fps: float = 0.0
    ms_quadro: float = 0.0
    etapas_ms: Dict[str, float] = field(default_factory=dict)
    desligados: List[str] = field(default_factory=list)
    motivo_ia: str = ""
    nivel_rosto: str = ""
    nivel_fundo: str = ""
    look: str = ""
    tem_rosto: bool = False


class Motor:
    def __init__(self, ajustes: Optional[dict] = None):
        self.detector = IA.Detector(cada_n=6)
        self.controlador = IA.Controlador()
        self.beleza = B.Beleza()
        self.fundo = F.Fundo()
        self.acabamento = V.Acabamento()
        self.diag = Diagnostico()

        self._tabela: Optional[np.ndarray] = None
        self._chave_tabela: Tuple = ()
        self._anterior: Optional[np.ndarray] = None      # para o ruído temporal
        self._n = 0
        self._medidas = IA.Medidas()
        self._tempos: Deque[float] = deque(maxlen=15)
        self._desligados: set = set()
        self._folgas = 0
        self.orcamento_ms = 33.0

    # ── a tabela do look, refeita só quando ele mexe ──────────────────────
    def tabela(self, look: str, forca: float, lut: str) -> np.ndarray:
        chave = (look, round(float(forca), 3), lut)
        if chave != self._chave_tabela or self._tabela is None:
            self._tabela, self.diag.look = V.assar(look, forca, lut)
            self._chave_tabela = chave
        return self._tabela

    def _ruido_temporal(self, img: np.ndarray, forca: float) -> np.ndarray:
        """Média com o quadro anterior, só onde nada se mexeu.

        Chuvisco de sensor muda a cada quadro; a parede não. Então a média
        temporal apaga o chuvisco e não borra a imagem -- desde que a média só
        valha onde não houve movimento. Onde houve, o quadro novo manda, e é
        por isso que não fica rastro atrás da mão dele.

        É o jeito mais barato que existe de limpar vídeo: um addWeighted e uma
        máscara de diferença, contra os 30 ms de um filtro espacial de verdade.
        """
        if forca <= 0.01 or not TEM_CV:
            self._anterior = img
            return img
        ant = self._anterior
        if ant is None or ant.shape != img.shape:
            self._anterior = img
            return img
        # a máscara de movimento nasce em 1/4: ela é um campo grosso, e
        # calculá-la em resolução cheia (com `max(axis=2)` em numpy, ainda por
        # cima) custava 28 dos 173 ms do quadro
        h, w = img.shape[:2]
        pw, ph = max(8, w // 4), max(8, h // 4)
        a_pq = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_AREA)
        b_pq = cv2.resize(ant, (pw, ph), interpolation=cv2.INTER_AREA)
        dif = cv2.cvtColor(cv2.absdiff(a_pq, b_pq), cv2.COLOR_BGR2GRAY)
        parado = cv2.threshold(dif, 14, 255, cv2.THRESH_BINARY_INV)[1]
        parado = cv2.GaussianBlur(parado, (0, 0), 1.5)
        a = float(np.clip(forca, 0.0, 1.0)) * 0.6
        media = cv2.addWeighted(img, 1.0 - a, ant, a, 0.0)
        saida = V.misturar(media, img, parado)
        self._anterior = saida
        return saida

    # ── o quadro ──────────────────────────────────────────────────────────
    def processar(self, img: np.ndarray, aj: dict) -> np.ndarray:
        if img is None or img.size == 0:
            return img
        t0 = time.perf_counter()
        etapas: Dict[str, float] = {}
        self._n += 1

        def marca(nome: str, t: float) -> float:
            agora = time.perf_counter()
            etapas[nome] = (agora - t) * 1000.0
            return agora

        # 1. PERCEBER e MEDIR — a cada 3 quadros; a malha não precisa de 30 Hz
        t = time.perf_counter()
        rosto = self.detector.achar(img)
        if self._n % 3 == 1:
            self._medidas = IA.medir(img, rosto)
        cor = self.controlador.passo(
            self._medidas, ligada=bool(aj.get("ia_ligada", True)),
            exposicao=bool(aj.get("ia_exposicao", True)),
            branco=bool(aj.get("ia_branco", True)),
            ruido=bool(aj.get("ia_ruido", True)))
        self.controlador.alvo = float(aj.get("ia_alvo_rosto", 0.55))
        self.controlador.forca = float(aj.get("ia_forca", 0.6))
        t = marca("ia", t)

        # 2. correção da IA — uma curva 1D de 256 entradas, 0,3 ms
        if TEM_CV and (abs(cor.ev) > 0.005 or cor.piso_preto > 0.001
                       or abs(cor.ganho_b - 1) > 0.003
                       or abs(cor.ganho_r - 1) > 0.003):
            img = cv2.LUT(img, V.curva_correcao(cor.ganho_b, cor.ganho_g,
                                                cor.ganho_r, cor.ev,
                                                cor.piso_preto))
        t = marca("correcao", t)

        # 3. ruído temporal
        img = self._ruido_temporal(img, cor.forca_ruido)
        t = marca("ruido", t)

        # 4. desfoque de fundo
        if aj.get("desfoque_fundo", 0.0) > 0.01 and "desfoque" not in self._desligados:
            img, self.diag.nivel_fundo = self.fundo.aplicar(
                img, rosto, float(aj.get("desfoque_fundo", 0.0)),
                float(aj.get("desfoque_brilho", 0.25)))
        t = marca("fundo", t)

        # 5. embelezamento
        if aj.get("beleza_ligada", True) and "beleza" not in self._desligados:
            leve = "beleza_leve" in self._desligados
            escala = 0.6 if leve else 1.0
            img = self.beleza.aplicar(
                img, rosto,
                pele=float(aj.get("beleza_pele", 0.45)) * escala,
                manchas=float(aj.get("beleza_manchas", 0.35)) * escala,
                olhos=0.0 if leve else float(aj.get("beleza_olhos", 0.25)),
                dentes=0.0 if leve else float(aj.get("beleza_dentes", 0.20)),
                so_no_rosto=bool(aj.get("beleza_so_no_rosto", True)))
        t = marca("beleza", t)

        # 6. o look
        if "look" not in self._desligados:
            tab = self.tabela(str(aj.get("look", "s_cinetone")),
                              float(aj.get("look_forca", 0.85)),
                              str(aj.get("lut_arquivo", "")))
            img = V.aplicar_tabela(img, tab)
        t = marca("look", t)

        # 7. acabamento
        if "halacao" not in self._desligados:
            img = self.acabamento.aplicar_halacao(img, float(aj.get("halacao", 0.12)))
        if "vinheta" not in self._desligados:
            img = self.acabamento.aplicar_vinheta(img, float(aj.get("vinheta", 0.18)))
        if "grao" not in self._desligados:
            img = self.acabamento.aplicar_grao(img, float(aj.get("grao", 0.10)))
        if "nitidez" not in self._desligados:
            img = self.acabamento.aplicar_nitidez(img, float(aj.get("nitidez", 0.35)))
        marca("acabamento", t)

        ms = (time.perf_counter() - t0) * 1000.0
        self._tempos.append(ms)
        self._governar(ms)

        d = self.diag
        d.ms_quadro = float(np.mean(self._tempos)) if self._tempos else ms
        d.fps = 1000.0 / max(d.ms_quadro, 0.001)
        d.etapas_ms = etapas
        d.motivo_ia = cor.motivo
        d.nivel_rosto = self.detector.nivel
        d.tem_rosto = self._medidas.tem_rosto
        d.desligados = [rot for chave, rot in SACRIFICIO
                        if chave in self._desligados]
        return img

    def _governar(self, ms: float) -> None:
        """Desliga (ou religa) efeito conforme o tempo real do quadro.

        Só decide com 30 quadros medidos, e religa devagar (precisa de 90
        quadros de folga). Sem essa assimetria o software fica ligando e
        desligando efeito na cara dele -- pior que qualquer efeito faltando.
        """
        if len(self._tempos) < self._tempos.maxlen:
            return
        media = float(np.mean(self._tempos))
        if media > self.orcamento_ms:
            self._folgas = 0
            # DESLIGA NA PROPORÇÃO DO ESTOURO, NÃO DE UM EM UM.
            # De um em um, com 15 quadros de medição entre cada decisão e oito
            # níveis para descer, o software levava uns 8 segundos para achar
            # o ponto -- 8 segundos de live picotada. Quem está ao DOBRO do
            # orçamento não precisa de oito medições para saber que precisa
            # cortar mais de um efeito.
            quantos = int(np.clip(media / max(self.orcamento_ms, 1.0), 1, 4))
            for chave, _ in SACRIFICIO:
                if quantos <= 0:
                    break
                if chave not in self._desligados:
                    self._desligados.add(chave)
                    quantos -= 1
            self._tempos.clear()
            return
        elif media < self.orcamento_ms * 0.62 and self._desligados:
            self._folgas += 1
            if self._folgas >= 60:
                for chave, _ in reversed(SACRIFICIO):
                    if chave in self._desligados:
                        self._desligados.discard(chave)
                        self._tempos.clear()
                        self._folgas = 0
                        return
        else:
            self._folgas = 0
