# -*- coding: utf-8 -*-
"""
IA VISUAL — a "ia basica rodando pra ajudar a melhorar a qualidade da imagem".

O QUE ELE PEDIU, E O QUE ISSO PODE HONESTAMENTE SER
───────────────────────────────────────────────────
    "te expliquei que queria uma ia basica rodando pra ajudar a melhorar a
     qualidade da imagem"

Poderia significar rede neural de super-resolução ou remoção de ruído por
aprendizado. Não vai ser isso, e o motivo é aritmética, não preguiça: uma
rede desse tipo em CPU leva de 100 ms a vários segundos por quadro. Ao vivo
o quadro inteiro tem 33 ms. Prometer rede neural aqui seria prometer uma live
a 3 quadros por segundo.

O que É uma IA básica e cabe nos 33 ms, e é o que está aqui:

  1. PERCEBER — achar o rosto dele no quadro (três níveis, ver abaixo)
  2. MEDIR — luminância do rosto, cor da luz, ruído, foco, contraste
  3. DECIDIR — um controlador fechado que corrige exposição, branco e ruído
     perseguindo um alvo, quadro a quadro
  4. CONTER-SE — banda morta e limite de velocidade, para não oscilar

Isso é controle por realimentação com percepção, que é exatamente o que a
"IA de cena" das câmeras faz. Melhora a imagem de verdade e a melhora se pode
medir -- os testes medem. O que ela NÃO faz é inventar detalhe que a webcam
não captou. Nenhuma IA em CPU faz isso ao vivo.

Se o `face_detection_yunet_2023mar.onnx` estiver ao lado do software, subo
para a rede de detecção de rosto de verdade (é leve, ~1 ms, roda em CPU).
Baixar é opcional; sem ela nada deixa de funcionar.

OS TRÊS NÍVEIS DE ACHAR O ROSTO, E POR QUE TRÊS
───────────────────────────────────────────────
Descobri instalando: no OpenCV 5 o `CascadeClassifier` não existe mais no
pacote básico, e no OpenCV 4 existe. Eu não controlo qual ele vai ter.

  1. YuNet (`cv2.FaceDetectorYN`) — se o .onnx estiver presente. O melhor.
  2. Cascade de Haar — se o OpenCV dele tiver. Bom o bastante.
  3. Máscara de pele + geometria — sempre. Grosso, mas o embelezamento é
     guiado pela máscara de PELE, não pela caixa do rosto, e a máscara de
     pele existe nos três níveis. Por isso o nível 3 ainda embeleza bem.

O CONTROLADOR NÃO PODE OSCILAR, E É AQUI QUE ISSO SE DECIDE
───────────────────────────────────────────────────────────
Um corretor de exposição ingênuo faz "pisca-pisca": ele mede escuro, clareia
demais, mede claro, escurece, e a live fica pulsando. Três freios:

  banda morta  — erro pequeno não é corrigido. Alvo é faixa, não ponto.
  passo curto  — no máximo `MAX_PASSO_EV` por quadro
  suavização   — média exponencial da medida, não a medida crua

O teste `test_ia_visual.py` cobra os três: leva a IA a um degrau de luz e
exige convergência sem passar do alvo mais de uma vez.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

RAIZ = Path(__file__).resolve().parent
MODELO_YUNET = RAIZ / "face_detection_yunet_2023mar.onnx"

# Freios do controlador. Medidos no teste de degrau, não escolhidos no olho.
BANDA_MORTA = 0.035      # erro de luminância abaixo disto: não mexe
MAX_PASSO_EV = 0.06      # paradas por quadro
LIMITE_EV = (-2.0, 2.5)
MAX_PASSO_GANHO = 0.010  # ganho de branco por quadro
LIMITE_GANHO = (0.75, 1.35)
LARGURA_ANALISE = 320    # medir em imagem pequena: 12x menos conta, mesma média


# ─────────────────────────────────────────────────────────────────────────────
# PERCEBER
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Rosto:
    x: int
    y: int
    w: int
    h: int
    confianca: float = 0.0
    origem: str = "nenhum"

    @property
    def valido(self) -> bool:
        return self.w > 1 and self.h > 1

    def centro(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    def escalar(self, k: float) -> "Rosto":
        return Rosto(int(self.x * k), int(self.y * k), int(self.w * k),
                     int(self.h * k), self.confianca, self.origem)


# Calibração da máscara de pele. Estes cinco números foram MEDIDOS contra uma
# tabela de amostras, não escolhidos no olho -- ver `test_pele.py`.
PELE_CR, PELE_SR = 0.425, 0.058      # centro e largura do vermelho normalizado
PELE_CG, PELE_SG = 0.335, 0.062      # idem para o verde
PELE_SAT = 0.09                      # cor mínima exigida


def mascara_pele(img: np.ndarray) -> np.ndarray:
    """Onde a imagem parece pele, 0..1 float32, no tamanho da imagem.

    A conta é sobre PROPORÇÃO entre canais, não sobre brilho, e isso é de
    propósito: pele clara e pele escura diferem em brilho, não em proporção.
    Um detector calibrado por brilho funcionaria para uns tons e não para
    outros -- a tabela do teste vai de pele muito clara a muito escura e
    cobra 0,5 ou mais em todas.

    A EXIGÊNCIA DE COR, E O DEFEITO QUE ELA CONSERTOU
    ─────────────────────────────────────────────────
    A primeira versão só olhava a proporção, e dava 0,69 para CINZA NEUTRO --
    porque cinza tem proporção 0,333/0,333, que ficava a menos de um desvio
    do centro da pele. Consequência prática, medida: numa cena com parede
    clara o embelezamento tratava a parede inteira como rosto, a região de
    trabalho virava o quadro todo, e o custo subiu de 23 para 43 ms por
    quadro fazendo trabalho que ia ser jogado fora.

    Pele tem cor; cinza, por definição, não tem nenhuma. Exigir uma saturação
    mínima derruba cinza e parede branca para zero e não custa nada à pele --
    nem à pele muito clara, que ainda tem 0,55.
    """
    f = img.astype(np.float32)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    soma = np.maximum(r + g + b, 1e-5)
    rn, gn = r / soma, g / soma
    d = ((rn - PELE_CR) / PELE_SR) ** 2 + ((gn - PELE_CG) / PELE_SG) ** 2
    m = np.exp(-0.5 * d)
    mx = f.max(axis=2)
    sat = (mx - f.min(axis=2)) / np.maximum(mx, 1e-3)
    m *= np.clip(sat / PELE_SAT, 0.0, 1.0)
    # pixel quase preto não tem proporção confiável: divisão por quase nada
    m *= np.clip((soma / 3.0 - 12.0) / 30.0, 0.0, 1.0)
    return m.astype(np.float32)


class Detector:
    """Acha o rosto pelo melhor caminho disponível, e diz qual caminho usou."""

    def __init__(self, cada_n: int = 6, suavizar: float = 0.25):
        self.cada_n = max(1, int(cada_n))
        self.suavizar = float(np.clip(suavizar, 0.05, 1.0))
        self.nivel = "pele"
        self._yunet = None
        self._cascade = None
        self._n = 0
        self._ultimo: Optional[Rosto] = None
        self._suave: Optional[List[float]] = None
        self.sem_rosto_quadros = 0
        self._preparar()

    def _preparar(self) -> None:
        if not TEM_CV:
            self.nivel = "pele"
            return
        if MODELO_YUNET.is_file() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    str(MODELO_YUNET), "", (LARGURA_ANALISE, LARGURA_ANALISE),
                    0.7, 0.3, 5000)
                self.nivel = "yunet"
                return
            except Exception:
                self._yunet = None
        try:
            caminho = Path(cv2.data.haarcascades) / \
                "haarcascade_frontalface_default.xml"
            if hasattr(cv2, "CascadeClassifier") and caminho.is_file():
                c = cv2.CascadeClassifier(str(caminho))
                if not c.empty():
                    self._cascade = c
                    self.nivel = "haar"
                    return
        except Exception:
            self._cascade = None
        self.nivel = "pele"

    # ── nível 3: pele + geometria ──────────────────────────────────────────
    @staticmethod
    def _por_pele(peq: np.ndarray) -> Optional[Rosto]:
        m = mascara_pele(peq)
        if float(m.mean()) < 0.02:
            return None
        # a maior região conexa de pele, pela projeção -- sem findContours,
        # que não existe garantido em toda build do OpenCV
        col = m.sum(axis=0)
        lin = m.sum(axis=1)
        if col.max() <= 0 or lin.max() <= 0:
            return None

        def faixa(v: np.ndarray) -> Tuple[int, int]:
            lim = v.max() * 0.35
            onde = np.flatnonzero(v >= lim)
            return (int(onde[0]), int(onde[-1])) if onde.size else (0, len(v) - 1)

        x0, x1 = faixa(col)
        y0, y1 = faixa(lin)
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if w < 8 or h < 8:
            return None
        return Rosto(x0, y0, w, h, min(1.0, float(m.mean()) * 6.0), "pele")

    def _detectar_peq(self, peq: np.ndarray) -> Optional[Rosto]:
        if self._yunet is not None:
            try:
                h, w = peq.shape[:2]
                self._yunet.setInputSize((w, h))
                _, faces = self._yunet.detect(peq)
                if faces is not None and len(faces):
                    f = max(faces, key=lambda z: float(z[14]))
                    return Rosto(int(f[0]), int(f[1]), int(f[2]), int(f[3]),
                                 float(f[14]), "yunet")
            except Exception:
                pass
        if self._cascade is not None:
            try:
                cinza = cv2.cvtColor(peq, cv2.COLOR_BGR2GRAY)
                cx = self._cascade.detectMultiScale(cinza, 1.15, 5,
                                                    minSize=(40, 40))
                if len(cx):
                    x, y, w, h = max(cx, key=lambda z: z[2] * z[3])
                    return Rosto(int(x), int(y), int(w), int(h), 0.8, "haar")
            except Exception:
                pass
        return self._por_pele(peq)

    def achar(self, img: np.ndarray) -> Optional[Rosto]:
        """O rosto no tamanho da imagem original, já suavizado no tempo.

        Detecto a cada `cada_n` quadros porque detecção é o passo caro e o
        rosto de quem está falando com a câmera não sai voando. Entre
        detecções, uso o último. E o suavizo: caixa pulando faz a máscara de
        embelezamento tremer, e tremer aparece muito mais que errar 3 pixels.
        """
        if img is None or img.size == 0:
            return None
        h, w = img.shape[:2]
        k = LARGURA_ANALISE / float(max(1, w))
        precisa = (self._n % self.cada_n == 0) or self._ultimo is None
        self._n += 1

        if precisa:
            if TEM_CV and k < 1.0:
                peq = cv2.resize(img, (LARGURA_ANALISE, max(2, int(h * k))),
                                 interpolation=cv2.INTER_AREA)
                fator = 1.0 / k
            else:
                peq, fator = img, 1.0
            achado = self._detectar_peq(peq)
            if achado is None:
                self.sem_rosto_quadros += 1
                if self.sem_rosto_quadros > 30:
                    self._ultimo, self._suave = None, None
            else:
                self.sem_rosto_quadros = 0
                grande = achado.escalar(fator)
                alvo = [float(grande.x), float(grande.y), float(grande.w),
                        float(grande.h)]
                if self._suave is None:
                    self._suave = alvo
                else:
                    a = self.suavizar
                    self._suave = [s * (1 - a) + t * a
                                   for s, t in zip(self._suave, alvo)]
                sx, sy, sw, sh = (int(round(v)) for v in self._suave)
                self._ultimo = Rosto(max(0, sx), max(0, sy),
                                     min(sw, w), min(sh, h),
                                     grande.confianca, grande.origem)
        return self._ultimo


# ─────────────────────────────────────────────────────────────────────────────
# MEDIR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Medidas:
    luz_rosto: float = 0.5      # 0..1, luminância média do rosto
    luz_quadro: float = 0.5
    contraste: float = 0.2      # desvio padrão da luminância
    ruido: float = 0.0          # nível estimado de chuvisco, 0..1
    foco: float = 0.0           # variância do laplaciano, normalizada
    ganho_b: float = 1.0        # o que corrigiria o branco (cinza-mundo)
    ganho_g: float = 1.0
    ganho_r: float = 1.0
    tem_rosto: bool = False
    estourado: float = 0.0      # fração de pixels já queimados
    origem_branco: str = "cinza"


def _ganhos_branco(peq: np.ndarray, pele: np.ndarray) -> Tuple[float, float, float, str]:
    """A cor da luz, medida FORA da pele -- e o motivo de ser fora.

    Cinza-mundo diz: na média, uma cena é acinzentada. Verdade razoável para
    parede, mesa, camisa. Mentira para pele: pele é laranja, e um cinza-mundo
    que inclui um rosto grande no quadro conclui que a luz é laranja e joga a
    imagem para o azul -- deixa ele com cara de defunto. Erro clássico, e é o
    que este `1 - pele` evita.

    Quando quase tudo é pele (rosto perto da webcam, que é o caso dele), não
    há cinza para medir. Aí inverto: uso a própria pele, comparando com a cor
    de pele esperada. É menos preciso e por isso volta anotado na medida.
    """
    f = peq.astype(np.float32)
    luz = f.mean(axis=2)
    # descarta o que não informa: preto (ruído) e queimado (sem cor)
    util = ((luz > 25) & (luz < 245)).astype(np.float32)
    # O PESO DO "NÃO É PELE" TEM DE SER SEVERO, E ESTE FOI O DEFEITO.
    # Eu usava `1 - pele`, que é suave demais: um quadro INTEIRO de pele
    # (rosto perto da webcam, que é o caso dele) ainda somava 15% de peso
    # "cinza", passava do corte de 6% e ia pelo caminho do cinza-mundo --
    # justamente no caso em que ele não existe. O teste pegou.
    # Aqui o peso cai a zero já em pele 0,5, então pele não se disfarça de
    # cinza nem um pouco.
    peso_cinza = util * np.clip((0.5 - np.clip(pele, 0, 1)) / 0.3, 0.0, 1.0)
    total = float(peso_cinza.sum())

    if total > peq.shape[0] * peq.shape[1] * 0.06:
        med = [(float((f[..., c] * peso_cinza).sum()) / total) for c in range(3)]
        origem = "cinza"
    else:
        peso_pele = util * np.clip(pele, 0, 1)
        tp = float(peso_pele.sum())
        if tp < 50:
            return 1.0, 1.0, 1.0, "sem dado"
        med = [(float((f[..., c] * peso_pele).sum()) / tp) for c in range(3)]
        # pele neutra esperada em BGR, na proporção medida em amostras
        alvo = np.array([0.72, 0.82, 1.0], dtype=np.float32)
        alvo = alvo / alvo.mean()
        m = float(np.mean(med))
        med = [med[c] / max(alvo[c], 1e-3) * 1.0 for c in range(3)]
        med = [v * (m / max(1e-3, float(np.mean(med)))) for v in med]
        origem = "pele"

    cinza = float(np.mean(med))
    g = [cinza / max(v, 1e-3) for v in med]
    return g[0], g[1], g[2], origem


def medir(img: np.ndarray, rosto: Optional[Rosto] = None) -> Medidas:
    """Tudo que a IA precisa saber do quadro, numa passada em imagem pequena."""
    if img is None or img.size == 0:
        return Medidas()
    h, w = img.shape[:2]
    if TEM_CV and w > LARGURA_ANALISE:
        k = LARGURA_ANALISE / float(w)
        peq = cv2.resize(img, (LARGURA_ANALISE, max(2, int(h * k))),
                         interpolation=cv2.INTER_AREA)
    else:
        k, peq = 1.0, img

    f = peq.astype(np.float32)
    luz = (f[..., 0] * 0.0722 + f[..., 1] * 0.7152 + f[..., 2] * 0.2126) / 255.0
    pele = mascara_pele(peq)

    m = Medidas()
    m.luz_quadro = float(luz.mean())
    m.contraste = float(luz.std())
    m.estourado = float((luz > 0.985).mean())

    if rosto is not None and rosto.valido:
        rx = rosto.escalar(k)
        y0, y1 = max(0, rx.y), min(peq.shape[0], rx.y + rx.h)
        x0, x1 = max(0, rx.x), min(peq.shape[1], rx.x + rx.w)
        if y1 - y0 > 2 and x1 - x0 > 2:
            corte = luz[y0:y1, x0:x1]
            pcorte = pele[y0:y1, x0:x1]
            tp = float(pcorte.sum())
            # dentro da caixa, mede a PELE: cabelo e fundo dentro da caixa
            # puxariam a média e a IA clarearia o rosto além da conta
            m.luz_rosto = (float((corte * pcorte).sum()) / tp) if tp > 20 \
                else float(corte.mean())
            m.tem_rosto = True
    if not m.tem_rosto:
        tp = float(pele.sum())
        if tp > 200:
            m.luz_rosto = float((luz * pele).sum()) / tp
            m.tem_rosto = True
        else:
            m.luz_rosto = m.luz_quadro

    # RUÍDO: alta frequência onde a imagem é lisa. Onde há detalhe verdadeiro
    # a alta frequência é o detalhe, não o ruído -- por isso a máscara de liso.
    if TEM_CV:
        borrado = cv2.GaussianBlur(luz, (0, 0), 1.2)
        alta = np.abs(luz - borrado)
        gx = cv2.Sobel(borrado, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(borrado, cv2.CV_32F, 0, 1, ksize=3)
        grad = np.abs(gx) + np.abs(gy)
        liso = (grad < np.percentile(grad, 40)).astype(np.float32)
        tl = float(liso.sum())
        if tl > 50:
            mad = float((alta * liso).sum()) / tl
            m.ruido = float(np.clip(mad / 0.02, 0.0, 1.0))
        m.foco = float(np.clip(cv2.Laplacian(luz, cv2.CV_32F).var() / 0.004,
                               0.0, 1.0))

    m.ganho_b, m.ganho_g, m.ganho_r, m.origem_branco = _ganhos_branco(peq, pele)
    return m


# ─────────────────────────────────────────────────────────────────────────────
# DECIDIR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Correcao:
    ev: float = 0.0
    ganho_b: float = 1.0
    ganho_g: float = 1.0
    ganho_r: float = 1.0
    forca_ruido: float = 0.0
    piso_preto: float = 0.0
    motivo: str = "parada"


class Controlador:
    """A malha fechada. Um passo por quadro, e cada passo é curto de propósito.

    Guarda estado entre quadros -- é o que diferencia "IA rodando" de "filtro
    aplicado". A cada quadro ela sabe onde estava e para onde ia.
    """

    def __init__(self, alvo: float = 0.55, forca: float = 0.6):
        self.alvo = float(np.clip(alvo, 0.2, 0.9))
        self.forca = float(np.clip(forca, 0.0, 1.0))
        self.cor = Correcao()
        self._luz_suave: Optional[float] = None
        self._passos = 0
        self.parada = False        # o teste usa isto: chegou e ficou

    def alvo_agora(self, m: Medidas) -> float:
        """O alvo cede quando insistir queimaria a imagem.

        Se já há muito pixel estourado, continuar clareando o rosto destrói o
        que estava bom para consertar o que não tem conserto. A câmera boa faz
        essa concessão; a webcam automática não faz, e é por isso que a janela
        atrás dele fica branca.
        """
        a = self.alvo
        if m.estourado > 0.02:
            a -= min(0.12, (m.estourado - 0.02) * 2.0)
        return float(np.clip(a, 0.18, 0.9))

    def passo(self, m: Medidas, ligada: bool = True, exposicao: bool = True,
              branco: bool = True, ruido: bool = True) -> Correcao:
        if not ligada:
            self.cor = Correcao(motivo="IA desligada")
            self.parada = True
            return self.cor
        self._passos += 1

        # suavização da MEDIDA (não da correção): a medida é o que tem ruído
        a = 0.20 + 0.5 * self.forca
        self._luz_suave = m.luz_rosto if self._luz_suave is None else \
            self._luz_suave * (1 - a) + m.luz_rosto * a

        motivos = []
        alvo = self.alvo_agora(m)

        if exposicao:
            erro = alvo - float(self._luz_suave)
            if abs(erro) <= BANDA_MORTA:
                motivos.append("exposição no alvo")
                self.parada = True
            else:
                self.parada = False
                # correção exata em paradas: log2 do quanto falta multiplicar
                falta = math.log2(max(alvo, 1e-3) /
                                  max(float(self._luz_suave), 1e-3))
                passo = float(np.clip(falta * (0.25 + 0.75 * self.forca),
                                      -MAX_PASSO_EV, MAX_PASSO_EV))
                self.cor.ev = float(np.clip(self.cor.ev + passo, *LIMITE_EV))
                motivos.append(f"exposição {'+' if passo > 0 else ''}"
                               f"{passo:+.3f} EV")
        if branco:
            for nome, medido in (("ganho_b", m.ganho_b), ("ganho_g", m.ganho_g),
                                 ("ganho_r", m.ganho_r)):
                atual = getattr(self.cor, nome)
                d = float(np.clip((medido - atual) * (0.2 + 0.6 * self.forca),
                                  -MAX_PASSO_GANHO, MAX_PASSO_GANHO))
                setattr(self.cor, nome,
                        float(np.clip(atual + d, *LIMITE_GANHO)))
            if m.origem_branco != "cinza":
                motivos.append(f"branco pela {m.origem_branco}")
        else:
            self.cor.ganho_b = self.cor.ganho_g = self.cor.ganho_r = 1.0

        if ruido:
            # clarear ruído multiplica ruído: quanto mais EV eu apliquei, mais
            # limpeza a imagem vai precisar. Por isso o EV entra na conta.
            base = m.ruido * (1.0 + 0.5 * max(0.0, self.cor.ev))
            alvo_r = float(np.clip(base * self.forca, 0.0, 1.0))
            self.cor.forca_ruido += (alvo_r - self.cor.forca_ruido) * 0.15
            # ruído alto vem com preto lavado: recuperar o preto devolve
            # contraste sem tocar no rosto
            self.cor.piso_preto = float(np.clip(m.ruido * 0.03, 0.0, 0.06))
            if self.cor.forca_ruido > 0.25:
                motivos.append(f"ruído {self.cor.forca_ruido:.2f}")
        else:
            self.cor.forca_ruido, self.cor.piso_preto = 0.0, 0.0

        self.cor.motivo = " · ".join(motivos) or "sem ajuste necessário"
        return self.cor
