# -*- coding: utf-8 -*-
"""
ÁUDIO DSP — "melhorar o audio direto na live", peça por peça.

O QUE ELE PEDIU
───────────────
    "te pedi tambem, no mesmo software, um editor de audio com capacidade
     de melhorar o audio direto na live"

A DIFERENÇA ENTRE EDITAR E MELHORAR AO VIVO
───────────────────────────────────────────
Editar é ter o arquivo inteiro e poder olhar o futuro. Ao vivo o futuro não
existe: chega um bloco de 1024 amostras, e o que sair tem de sair agora. Isso
proíbe metade dos truques de estúdio e obriga a uma regra que atravessa este
arquivo inteiro:

    TODO FILTRO GUARDA SEU ESTADO ENTRE BLOCOS.

Um filtro que zera o estado a cada bloco produz um clique a cada 21 ms -- 47
cliques por segundo. É o defeito mais comum de quem escreve DSP em blocos, é
inaudível num teste de um bloco só, e destrói a live. O `test_audio.py`
processa o mesmo sinal em um bloco e em cem blocos e exige que o resultado
seja o MESMO. Sem isso, nada aqui vale.

A CADEIA, NA ORDEM, E POR QUE NESTA ORDEM
─────────────────────────────────────────
 1. corte de graves     tira ronco de mesa/ar antes que ele alimente tudo
 2. redução de ruído    limpa o chiado antes que o compressor o amplifique
 3. portão              silêncio vira silêncio de verdade
 4. de-esser            doma o "sss" antes de a presença aumentá-lo
 5. equalização         corpo, tira o abafado, presença
 6. compressor          nivela: sussurro e grito na mesma altura
 7. limitador           teto que nada ultrapassa

A ordem não é gosto. Comprimir antes de limpar amplifica o chiado nas pausas
-- o erro clássico. Dar presença antes do de-esser é pedir para o "sss"
estourar. Limitador em último porque ele é a garantia final, e garantia com
alguém depois dela não é garantia.

LATÊNCIA, DITA E NÃO ESCONDIDA
──────────────────────────────
A redução de ruído trabalha por janelas com sobreposição e atrasa uma janela:
21 ms a 48 kHz. O limitador olha 3 ms à frente. Total ~24 ms, e o software
mostra esse número na tela. Isso é o que faz a boca casar com a voz na live:
o vídeo é atrasado pelo mesmo tanto, senão a voz chega antes da imagem.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

try:
    from scipy.signal import lfilter
    from scipy.ndimage import maximum_filter1d
    TEM_SCIPY = True
except Exception:                                    # pragma: no cover
    TEM_SCIPY = False

TAXA = 48000

# POR QUE O SCIPY É DEPENDÊNCIA DE VERDADE AQUI, E NÃO UM LUXO
# ────────────────────────────────────────────────────────────
# Um filtro IIR é recursivo: a saída de agora depende da saída de antes. Isso
# não vetoriza em numpy, então a versão honesta em Python é um laço por
# amostra. Medi a cadeia inteira assim, para 1 segundo de áudio:
#
#     passa-altas  178 ms · EQ (3 bandas) ~450 ms · de-esser 368 ms
#     limitador     66 ms · portão 26 ms · compressor 12 ms
#     ------------------------------------------------------------
#     mais de 1100 ms de CPU para 1 segundo de som
#
# Isto é mais de um núcleo inteiro só para o áudio, e ele ainda ia disputar
# CPU com a imagem. Com `scipy.signal.lfilter` o mesmo passa-altas cai de
# 178 ms para 2,65 ms -- 67 vezes.
#
# O caminho em Python puro CONTINUA aqui, e não por decoração: se o scipy não
# estiver instalado o software funciona, só que o áudio pesado precisa ser
# desligado. A tela avisa em vez de engasgar sem explicar.


def db_para_ganho(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def ganho_para_db(g: float) -> float:
    return float(20.0 * math.log10(max(g, 1e-10)))


# ─────────────────────────────────────────────────────────────────────────────
# BIQUAD — o tijolo de todos os filtros
# ─────────────────────────────────────────────────────────────────────────────

class Biquad:
    """Filtro de 2ª ordem, forma direta II transposta, com estado por canal.

    As fórmulas são as do Audio EQ Cookbook (Robert Bristow-Johnson), que são
    as que todo mundo usa porque são estáveis e casam com o que o ouvido
    espera de um controle de tom.
    """

    def __init__(self, b0=1.0, b1=0.0, b2=0.0, a1=0.0, a2=0.0, canais: int = 1):
        self.set(b0, b1, b2, a1, a2)
        self.z1 = np.zeros(canais, dtype=np.float64)
        self.z2 = np.zeros(canais, dtype=np.float64)

    def set(self, b0, b1, b2, a1, a2) -> None:
        self.b0, self.b1, self.b2, self.a1, self.a2 = \
            float(b0), float(b1), float(b2), float(a1), float(a2)

    def zerar(self) -> None:
        self.z1[:] = 0.0
        self.z2[:] = 0.0

    def processar(self, x: np.ndarray) -> np.ndarray:
        """x: (n,) ou (n, canais). Devolve o mesmo formato, estado preservado.

        Com scipy: `lfilter` com `zi`, que É o estado do filtro -- entra o de
        ontem, sai o de hoje. É por isso que o resultado em cem blocos é
        idêntico ao resultado num bloco só, que é o que o teste cobra.
        """
        if TEM_SCIPY:
            return self._por_scipy(x)
        mono = x.ndim == 1
        y = np.atleast_2d(x.T).T.astype(np.float64, copy=True) if mono \
            else x.astype(np.float64, copy=True)
        if mono:
            y = y.reshape(-1, 1)
        n, c = y.shape
        if self.z1.shape[0] != c:
            self.z1 = np.zeros(c, dtype=np.float64)
            self.z2 = np.zeros(c, dtype=np.float64)
        b0, b1, b2, a1, a2 = self.b0, self.b1, self.b2, self.a1, self.a2
        z1, z2 = self.z1, self.z2
        saida = np.empty_like(y)
        for i in range(n):
            xn = y[i]
            yn = b0 * xn + z1
            z1 = b1 * xn - a1 * yn + z2
            z2 = b2 * xn - a2 * yn
            saida[i] = yn
        self.z1, self.z2 = z1, z2
        return saida[:, 0].astype(np.float32) if mono \
            else saida.astype(np.float32)

    def _por_scipy(self, x: np.ndarray) -> np.ndarray:
        b = np.array([self.b0, self.b1, self.b2], dtype=np.float64)
        a = np.array([1.0, self.a1, self.a2], dtype=np.float64)
        mono = x.ndim == 1
        y = x.reshape(-1, 1) if mono else x
        c = y.shape[1]
        if self.z1.shape[0] != c:
            self.z1 = np.zeros(c, dtype=np.float64)
            self.z2 = np.zeros(c, dtype=np.float64)
        zi = np.stack([self.z1, self.z2])              # (2, canais)
        saida, zf = lfilter(b, a, y.astype(np.float64), axis=0, zi=zi)
        self.z1, self.z2 = zf[0], zf[1]
        saida = saida.astype(np.float32)
        return saida[:, 0] if mono else saida


def _coef_comuns(f: float, taxa: int, q: float) -> Tuple[float, float, float]:
    w0 = 2.0 * math.pi * max(1.0, min(f, taxa * 0.49)) / taxa
    return math.cos(w0), math.sin(w0), math.sin(w0) / (2.0 * max(q, 0.05))


def passa_altas(f: float, taxa: int = TAXA, q: float = 0.707,
                canais: int = 1) -> Biquad:
    cw, _, alfa = _coef_comuns(f, taxa, q)
    a0 = 1 + alfa
    return Biquad((1 + cw) / 2 / a0, -(1 + cw) / a0, (1 + cw) / 2 / a0,
                  (-2 * cw) / a0, (1 - alfa) / a0, canais)


def sino(f: float, ganho_db: float, q: float = 1.0, taxa: int = TAXA,
         canais: int = 1) -> Biquad:
    """EQ de sino: levanta ou baixa uma faixa em volta de `f`."""
    A = 10.0 ** (ganho_db / 40.0)
    cw, _, alfa = _coef_comuns(f, taxa, q)
    a0 = 1 + alfa / A
    return Biquad((1 + alfa * A) / a0, (-2 * cw) / a0, (1 - alfa * A) / a0,
                  (-2 * cw) / a0, (1 - alfa / A) / a0, canais)


def prateleira_alta(f: float, ganho_db: float, taxa: int = TAXA,
                    q: float = 0.707, canais: int = 1) -> Biquad:
    A = 10.0 ** (ganho_db / 40.0)
    cw, _, alfa = _coef_comuns(f, taxa, q)
    d = 2 * math.sqrt(A) * alfa
    a0 = (A + 1) - (A - 1) * cw + d
    return Biquad(A * ((A + 1) + (A - 1) * cw + d) / a0,
                  -2 * A * ((A - 1) + (A + 1) * cw) / a0,
                  A * ((A + 1) + (A - 1) * cw - d) / a0,
                  2 * ((A - 1) - (A + 1) * cw) / a0,
                  ((A + 1) - (A - 1) * cw - d) / a0, canais)


def passa_faixa(f_baixa: float, f_alta: float, taxa: int = TAXA,
                canais: int = 1) -> Tuple[Biquad, Biquad]:
    """Par de filtros que isola uma faixa. O de-esser usa para achar o 'sss'."""
    cw, _, alfa = _coef_comuns(f_alta, taxa, 0.707)
    a0 = 1 + alfa
    baixas = Biquad((1 - cw) / 2 / a0, (1 - cw) / a0, (1 - cw) / 2 / a0,
                    (-2 * cw) / a0, (1 - alfa) / a0, canais)
    return passa_altas(f_baixa, taxa, 0.707, canais), baixas


# ─────────────────────────────────────────────────────────────────────────────
# ENVELOPE — quem mede o quão alto está, com ataque e relaxamento
# ─────────────────────────────────────────────────────────────────────────────

class Envelope:
    """Seguidor de envelope com constantes de tempo separadas.

    Subir rápido e descer devagar é o que faz um compressor soar como
    compressor e não como um portão batendo.
    """

    def __init__(self, ataque_ms: float, relax_ms: float, taxa: int = TAXA):
        self.taxa = taxa
        self.ataque_ms = ataque_ms
        self.relax_ms = relax_ms
        self._ca = self._coef(ataque_ms)
        self._cr = self._coef(relax_ms)
        self.valor = 0.0

    def _coef(self, ms: float) -> float:
        ms = max(0.01, float(ms))
        return float(math.exp(-1.0 / (self.taxa * ms / 1000.0)))

    def processar(self, x: np.ndarray) -> np.ndarray:
        """Envelope amostra a amostra, guardando o valor entre blocos."""
        a = np.abs(np.asarray(x, dtype=np.float64))
        if a.ndim > 1:
            a = a.max(axis=1)
        saida = np.empty(a.shape[0], dtype=np.float64)
        v = self.valor
        ca, cr = self._ca, self._cr
        for i in range(a.shape[0]):
            xi = a[i]
            c = ca if xi > v else cr
            v = xi + c * (v - xi)
            saida[i] = v
        self.valor = v
        return saida


# ─────────────────────────────────────────────────────────────────────────────
# OS BLOCOS DA CADEIA
# ─────────────────────────────────────────────────────────────────────────────

class Portao:
    """Expansor descendente com histerese. Não é um interruptor.

    Um portão que só liga e desliga corta o fim das palavras e faz a sala
    "respirar". Dois cuidados evitam isso: a histerese (abre num nível e só
    fecha num nível 6 dB MAIS BAIXO, então uma sílaba fraca não o fecha) e o
    piso, que atenua em vez de silenciar -- silêncio absoluto no meio da fala
    é mais estranho que um chiado baixinho.
    """

    def __init__(self, limiar_db: float = -42.0, taxa: int = TAXA,
                 piso_db: float = -18.0, segura_ms: float = 120.0):
        self.limiar_db = float(limiar_db)
        self.piso = db_para_ganho(piso_db)
        self.env = Envelope(2.0, 90.0, taxa)
        self.taxa = taxa
        self.segura = int(taxa * segura_ms / 1000.0)
        self._contando = 0
        self._aberto = False
        self._g = 1.0
        self._suave = Envelope(4.0, 110.0, taxa)

    def processar(self, x: np.ndarray) -> Tuple[np.ndarray, float]:
        env = self.env.processar(x)
        abre = db_para_ganho(self.limiar_db)
        fecha = db_para_ganho(self.limiar_db - 6.0)      # histerese de 6 dB
        alvo = np.empty_like(env)
        for i in range(env.shape[0]):
            if env[i] > abre:
                self._aberto = True
                self._contando = self.segura
            elif env[i] < fecha:
                if self._contando > 0:
                    self._contando -= 1
                else:
                    self._aberto = False
            alvo[i] = 1.0 if self._aberto else self.piso
        # o ganho não salta: passa pelo mesmo tipo de suavizador do envelope
        g = self._suave.processar(alvo)
        self._g = float(g[-1]) if g.size else self._g
        if x.ndim > 1:
            g = g[:, None]
        return (x * g).astype(np.float32), float(np.mean(alvo))


class ReducaoRuido:
    """Subtração espectral com perfil de ruído aprendido sozinho.

    COMO ELA APRENDE O QUE É RUÍDO, SEM PEDIR NADA A ELE
    ────────────────────────────────────────────────────
    Ninguém quer clicar em "grave 5 segundos de silêncio" antes de cada live.
    Então o perfil se aprende sozinho: guardo a energia por faixa das janelas
    mais QUIETAS que passaram (percentil baixo, atualizado devagar). O que é
    constante e está sempre lá -- ventilador, geladeira, chiado do pré-amp --
    entra no perfil. Fala não entra, porque fala não é constante.

    A SUBTRAÇÃO TEM DOIS FREIOS, E OS DOIS SÃO CONTRA O MESMO ESTRAGO
    ─────────────────────────────────────────────────────────────────
    Subtrair demais produz "ruído musical": pontinhos metálicos que aparecem
    onde a subtração zerou faixas isoladas. É pior que o chiado original.
      · piso espectral -- nunca reduzo abaixo de uma fração do original
      · suavização entre faixas vizinhas -- tira os pontinhos isolados
    """

    def __init__(self, taxa: int = TAXA, janela: int = 1024):
        self.taxa = taxa
        self.n = int(janela)
        self.salto = self.n // 2
        self.jan = np.hanning(self.n + 1)[:-1].astype(np.float32)
        self._buf = np.zeros(0, dtype=np.float32)
        self._cauda = np.zeros(self.n - self.salto, dtype=np.float32)
        self._perfil: Optional[np.ndarray] = None
        self._mag_suave: Optional[np.ndarray] = None

    @property
    def latencia_amostras(self) -> int:
        return self.n

    def processar(self, x: np.ndarray, forca: float = 0.55) -> np.ndarray:
        """Mono float32. Sobreposição e soma, com estado entre blocos."""
        f = float(np.clip(forca, 0.0, 1.0))
        x = np.asarray(x, dtype=np.float32).reshape(-1)
        self._buf = np.concatenate([self._buf, x])
        saida = []
        while self._buf.shape[0] >= self.n:
            quadro = self._buf[:self.n] * self.jan
            esp = np.fft.rfft(quadro)
            mag = np.abs(esp)
            fase = np.angle(esp)

            # ────────────────────────────────────────────────────────────
            # COMO O PERFIL DE RUÍDO É APRENDIDO: MÍNIMO POR BANDA
            #
            # Tentei duas regras antes desta e as duas comeram a voz:
            #
            #  1ª  "aprenda em qualquer janela que não esteja acima do
            #      perfil". Com um tom contínuo, ela aprendeu O TOM: som
            #      constante é indistinguível de ruído constante para quem
            #      só olha o nível. A voz caiu 19 dB.
            #  2ª  "aprenda nas pausas, mais as primeiras 12 janelas para
            #      arrancar". A fala começava dentro dessas 12 janelas e ia
            #      inteira para o perfil. A voz caiu 19 dB de novo.
            #
            # O que funciona é não perguntar "isto é ruído?" e sim medir o
            # MÍNIMO de cada banda ao longo do tempo. O argumento é simples:
            # nenhuma banda da voz fica alta o tempo todo -- entre sílabas,
            # entre palavras, entre frases, cada banda passa perto do chão. O
            # ventilador, esse sim, fica. Então o mínimo de cada banda numa
            # janela de alguns segundos É o ruído, sem precisar detectar fala.
            #
            #   cai na hora   -> qualquer mínimo novo entra imediatamente
            #   sobe devagar  -> 0,3% por janela, ~2,5 s para dobrar; é o que
            #                    permite acompanhar o ar-condicionado ligando
            #                    sem acompanhar a voz
            #   viés de 1,6x  -> o mínimo subestima o ruído médio; esse fator
            #                    é a correção padrão do método
            #
            # Suavizo a magnitude antes de medir o mínimo porque uma única
            # janela anormalmente baixa travaria o perfil lá embaixo.
            if self._mag_suave is None:
                self._mag_suave = mag.copy()
            else:
                self._mag_suave = self._mag_suave * 0.7 + mag * 0.3

            if self._perfil is None:
                self._perfil = self._mag_suave.copy()
            else:
                self._perfil = np.minimum(self._perfil * 1.003,
                                          self._mag_suave)
            perfil = self._perfil * 1.6

            if f > 0.001:
                sobra = mag - perfil * (1.0 + 2.0 * f)
                piso = mag * (0.10 + 0.25 * (1.0 - f))   # nunca zera a faixa
                limpo = np.maximum(sobra, piso)
                # suaviza entre faixas vizinhas: mata o "ruído musical"
                limpo = np.convolve(limpo, np.array([0.25, 0.5, 0.25],
                                                    dtype=np.float32), "same")
            else:
                limpo = mag

            quadro_limpo = np.fft.irfft(limpo * np.exp(1j * fase),
                                        n=self.n).astype(np.float32)
            quadro_limpo *= self.jan
            pronto = quadro_limpo[:self.salto] + self._cauda[:self.salto]
            self._cauda = np.concatenate([
                quadro_limpo[self.salto:],
                np.zeros(self.salto, dtype=np.float32)])[:self.n - self.salto]
            saida.append(pronto)
            self._buf = self._buf[self.salto:]
        return np.concatenate(saida) if saida else np.zeros(0, dtype=np.float32)


class DeEsser:
    """Comprime só a faixa do 'sss', não a voz inteira.

    Um compressor comum abaixado pelo "sss" abaixa a frase toda -- a voz
    afunda a cada sibilante. Aqui a faixa de 5 a 9 kHz é separada, medida e
    atenuada sozinha, e devolvida ao resto. A voz não se mexe.
    """

    def __init__(self, taxa: int = TAXA, canais: int = 1):
        self.alta, self.baixa = passa_faixa(5000.0, 9000.0, taxa, canais)
        self.env = Envelope(0.5, 35.0, taxa)
        self.taxa = taxa

    def processar(self, x: np.ndarray, forca: float = 0.35) -> np.ndarray:
        f = float(np.clip(forca, 0.0, 1.0))
        if f <= 0.001:
            return x
        faixa = self.baixa.processar(self.alta.processar(x))
        env = self.env.processar(faixa)
        limiar = db_para_ganho(-34.0 + 10.0 * (1.0 - f))
        excesso = np.maximum(env / max(limiar, 1e-9), 1.0)
        reducao = excesso ** (-0.6 * f)            # razão suave, não tijolo
        if x.ndim > 1:
            reducao = reducao[:, None]
        return (x - faixa * (1.0 - reducao)).astype(np.float32)


class Compressor:
    """Nivela: o sussurro sobe, o grito não estoura. Joelho suave.

    Joelho suave e não duro porque a transição abrupta na razão é audível --
    a voz "entra no compressor" de um jeito que se percebe. A curva quadrática
    dentro do joelho é a padrão nos compressores de software bons.
    """

    def __init__(self, taxa: int = TAXA):
        self.env = Envelope(6.0, 140.0, taxa)
        self.taxa = taxa
        self.reducao_db = 0.0

    def processar(self, x: np.ndarray, quantidade: float = 0.5
                  ) -> Tuple[np.ndarray, float]:
        q = float(np.clip(quantidade, 0.0, 1.0))
        if q <= 0.001:
            self.reducao_db = 0.0
            return x, 0.0
        limiar_db = -12.0 - 14.0 * q
        razao = 1.5 + 5.0 * q
        joelho = 6.0

        env = np.maximum(self.env.processar(x), 1e-9)
        nivel = 20.0 * np.log10(env)
        excesso = nivel - limiar_db

        reducao = np.zeros_like(excesso)
        meio = np.abs(excesso) <= joelho / 2
        acima = excesso > joelho / 2
        reducao[acima] = excesso[acima] * (1.0 - 1.0 / razao)
        d = excesso[meio] + joelho / 2
        reducao[meio] = (1.0 - 1.0 / razao) * d * d / (2.0 * joelho)

        # compensação: devolve o que a compressão tirou do volume geral
        ganho_db = -reducao + (limiar_db * (1.0 / razao - 1.0)) * -1.0 * 0.0
        ganho_db += (0.6 * q) * (-limiar_db) * (1.0 - 1.0 / razao) * 0.5
        g = 10.0 ** (ganho_db / 20.0)
        self.reducao_db = float(np.max(reducao)) if reducao.size else 0.0
        if x.ndim > 1:
            g = g[:, None]
        return (x * g).astype(np.float32), self.reducao_db


class Limitador:
    """Teto absoluto, com antecipação. É a última linha e não pode falhar.

    Um limitador sem antecipação já deixou o pico passar quando reage. Por
    isso ele ATRASA o sinal em 3 ms e usa esses 3 ms para baixar o ganho
    ANTES de o pico chegar. É a razão de o teste conseguir exigir "nenhuma
    amostra acima do teto, nunca".
    """

    def __init__(self, taxa: int = TAXA, olhar_ms: float = 3.0):
        self.taxa = taxa
        self.olhar = max(4, int(taxa * olhar_ms / 1000.0))
        self._atraso: Optional[np.ndarray] = None
        self._g = 1.0
        self._relax = math.exp(-1.0 / (taxa * 0.060))

    @property
    def latencia_amostras(self) -> int:
        return self.olhar

    def processar(self, x: np.ndarray, teto_db: float = -1.0) -> np.ndarray:
        teto = db_para_ganho(teto_db)
        x = np.asarray(x, dtype=np.float32)
        canais = 1 if x.ndim == 1 else x.shape[1]
        forma = (self.olhar,) if x.ndim == 1 else (self.olhar, canais)
        if self._atraso is None or self._atraso.shape[1:] != forma[1:]:
            self._atraso = np.zeros(forma, dtype=np.float32)

        junto = np.concatenate([self._atraso, x])
        pico = np.abs(junto) if junto.ndim == 1 else np.abs(junto).max(axis=1)
        n = x.shape[0]

        # o pico dos próximos `olhar` amostras, para cada posição
        if TEM_SCIPY:
            jan = self.olhar + 1
            # origem negativa = janela olhando para a FRENTE, que é o ponto
            desl = maximum_filter1d(pico, size=jan, mode="nearest",
                                    origin=-(jan // 2))
            futuro = desl[:n]
        else:
            futuro = np.array([pico[i:i + self.olhar + 1].max()
                               for i in range(n)], dtype=np.float64)

        alvo = np.where(futuro > teto, teto / np.maximum(futuro, 1e-9), 1.0)

        # A RECURSÃO DO GANHO, EM GRADE DECIMADA
        # ──────────────────────────────────────
        # "cai na hora, sobe devagar" não é linear e não vetoriza. Mas o ganho
        # de um limitador é um sinal lento -- não tem nada acima de ~1 kHz --,
        # então rodo a recursão a cada 16 amostras e interpolo. 16 vezes menos
        # laço, e o ganho fica até mais macio.
        #
        # O que garante que isto não deixa pico passar: em cada grupo eu uso o
        # MENOR ganho do grupo (o mais conservador), a interpolação só pode
        # ficar abaixo do necessário nas bordas, e no fim ainda há o corte
        # duro no teto. O teste exige "nenhuma amostra acima do teto".
        passo = 16
        if n > passo * 2:
            grupos = int(np.ceil(n / passo))
            comp = grupos * passo
            alvo_pad = np.concatenate([alvo, np.repeat(alvo[-1:], comp - n)])
            alvo_g = alvo_pad.reshape(grupos, passo).min(axis=1)
            g_g = np.empty(grupos, dtype=np.float64)
            g_ant = self._g                 # onde o bloco ANTERIOR terminou
            atual = self._g
            relax_g = self._relax ** passo
            for i in range(grupos):
                a = alvo_g[i]
                atual = a if a < atual else a + relax_g * (atual - a)
                g_g[i] = atual
            self._g = atual
            # Os pontos da grade são o FIM de cada grupo, e eu ancoro um ponto
            # extra em x = -1 com o ganho onde o bloco anterior parou. Sem essa
            # âncora a interpolação começava já no valor novo e deixava um
            # degrau na emenda entre blocos -- o teste de continuidade acusou
            # 1,6e-2 de diferença, que é justamente o tamanho desse degrau.
            xs = np.concatenate([[-1.0],
                                 np.arange(grupos, dtype=np.float64) * passo
                                 + (passo - 1)])
            g = np.interp(np.arange(n, dtype=np.float64), xs,
                          np.concatenate([[g_ant], g_g]))
            g = np.minimum(g, alvo)          # nunca acima do que o pico exige
        else:
            g = np.empty(n, dtype=np.float64)
            atual = self._g
            for i in range(n):
                a = alvo[i]
                atual = a if a < atual else a + self._relax * (atual - a)
                g[i] = atual
            self._g = atual

        atrasado = junto[:n]
        self._atraso = junto[n:][-self.olhar:] if junto.shape[0] >= n + self.olhar \
            else np.zeros(forma, dtype=np.float32)
        if atrasado.ndim > 1:
            g = g[:, None]
        return np.clip(atrasado * g, -teto, teto).astype(np.float32)
