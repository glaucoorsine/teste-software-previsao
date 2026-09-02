# -*- coding: utf-8 -*-
"""
O fundo: separar a pessoa e desfocar, trocar ou pintar o que está atrás dela.

TRÊS MANEIRAS DE ACHAR A PESSOA, E POR QUE TRÊS
-----------------------------------------------
Desfocar fundo exige saber onde a pessoa termina. A forma certa é uma rede de
segmentação, e é a primeira opção aqui. Mas o MediaPipe não instala em toda
versão de Python no Windows — e quando não instala, um software que só tivesse
esse caminho simplesmente não teria o recurso que ele pediu.

Então há três, e o software usa o melhor que a máquina permitir:

1. `SegmentadorMediaPipe` — a rede de selfie do MediaPipe. Melhor recorte,
   aceita a câmera se mexendo, custa poucos milissegundos. Usa se instalado.

2. `SegmentadorFundoAprendido` — sem rede nenhuma. A pessoa sai de quadro, o
   software fotografa o fundo vazio, e a partir daí o que difere do fundo é a
   pessoa. Para quem transmite sentado com a câmera parada — que é o caso de
   quase toda live — isso recorta tão bem quanto a rede, e não depende de nada
   além do NumPy. Exige o gesto de aprender o fundo, e é por isso que não é o
   padrão automático.

3. `SegmentadorCentral` — o último recurso honesto. Assume que a pessoa está no
   meio do quadro e desfoca as bordas com uma elipse suave. NÃO é recorte de
   pessoa e o painel diz isso com todas as letras: é um desfoque de borda que
   fica bom em plano fechado e erra quando a pessoa anda para o lado.

O ESTABILIZADOR TEMPORAL
------------------------
Qualquer máscara treme entre quadros. Tremida, a borda da pessoa cintila e o
olho pega na hora — é o defeito que mais denuncia fundo falso em live. Por isso
toda máscara passa por uma média exponencial com a do quadro anterior
(`suavizacao_temporal`). Custa um array e resolve o problema.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple

import numpy as np

from . import imagem as IMG

try:
    import cv2
except Exception:  # pragma: no cover - depende da máquina
    cv2 = None

MODOS = ("nenhum", "desfocar", "imagem", "cor")
LARGURA_ANALISE = 256      # a máscara é calculada nesta largura, não na da live


@dataclass
class EfeitoFundo:
    """O que fazer com o fundo depois de encontrá-lo."""
    modo: str = "nenhum"             # nenhum | desfocar | imagem | cor
    intensidade: int = 70            # 0..100 — força do desfoque
    cor: Tuple[int, int, int] = (16, 92, 32)   # BGR, usado no modo "cor"
    caminho_imagem: str = ""         # usado no modo "imagem"
    suavizacao_temporal: int = 60    # 0..100 — quanto do quadro anterior fica
    recorte_suave: int = 6           # raio do feather na borda da máscara

    def como_dicionario(self) -> Dict:
        return asdict(self)

    @staticmethod
    def de_dicionario(d: Optional[Dict]) -> "EfeitoFundo":
        base = EfeitoFundo()
        for k, v in dict(d or {}).items():
            if hasattr(base, k):
                setattr(base, k, v)
        if isinstance(base.cor, list):
            base.cor = tuple(base.cor)
        return base.validar()

    def validar(self) -> "EfeitoFundo":
        self.modo = self.modo if self.modo in MODOS else "nenhum"
        for campo, lo, hi in (("intensidade", 0, 100), ("suavizacao_temporal", 0, 100),
                              ("recorte_suave", 0, 40)):
            try:
                setattr(self, campo, int(max(lo, min(hi, int(getattr(self, campo))))))
            except Exception:
                setattr(self, campo, lo)
        try:
            self.cor = tuple(int(max(0, min(255, c))) for c in tuple(self.cor)[:3])
        except Exception:
            self.cor = (16, 92, 32)
        self.caminho_imagem = str(self.caminho_imagem or "")
        return self


# ----------------------------------------------------------------------------
# segmentadores
# ----------------------------------------------------------------------------
class Segmentador:
    """Contrato: recebe um quadro BGR e devolve a máscara da PESSOA em 0..1.

    A máscara sai na resolução de análise (não na da live) — quem compõe amplia.
    Devolver pequeno é de propósito: é o que mantém o custo constante quando a
    transmissão sobe de 720p para 1080p.
    """

    nome = "base"
    qualidade = "desconhecida"

    def mascara(self, quadro: np.ndarray) -> np.ndarray:  # pragma: no cover - abstrato
        raise NotImplementedError

    def pronto(self) -> bool:
        return True

    def aviso(self) -> str:
        """Frase curta para o painel quando este segmentador tem limitação."""
        return ""


class SegmentadorMediaPipe(Segmentador):
    """A rede de selfie do MediaPipe. Melhor recorte disponível sem GPU."""

    nome = "mediapipe"
    qualidade = "boa"

    def __init__(self, modelo: int = 1):
        import mediapipe as mp  # importado só aqui: é dependência opcional
        self._seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=modelo)

    def mascara(self, quadro: np.ndarray) -> np.ndarray:
        peq = IMG.para_bytes(_reduzir(quadro))
        rgb = peq[:, :, ::-1] if cv2 is None else cv2.cvtColor(peq, cv2.COLOR_BGR2RGB)
        saida = self._seg.process(np.ascontiguousarray(rgb))
        if saida is None or saida.segmentation_mask is None:
            return np.ones(peq.shape[:2], np.float32)
        return np.clip(np.asarray(saida.segmentation_mask, np.float32), 0.0, 1.0)


class SegmentadorFundoAprendido(Segmentador):
    """Compara com uma foto do fundo vazio. Sem rede, sem download, sem GPU.

    Funciona pela diferença: o que mudou em relação ao fundo memorizado é a
    pessoa. A comparação é feita em CROMINÂNCIA além do brilho, porque sombra
    projetada muda o brilho do fundo sem mudar a cor dele — comparar só o
    brilho recortaria a própria sombra da pessoa como se fosse a pessoa.
    """

    nome = "fundo_aprendido"
    qualidade = "boa_com_camera_parada"

    def __init__(self, limiar: float = 0.10):
        self._fundo: Optional[np.ndarray] = None
        self._limiar = float(limiar)

    def aprender(self, quadro: np.ndarray) -> None:
        """Memoriza o fundo vazio. Chamado pelo botão do painel."""
        self._fundo = _reduzir(quadro).astype(np.float32)

    def esquecer(self) -> None:
        self._fundo = None

    def pronto(self) -> bool:
        return self._fundo is not None

    def aviso(self) -> str:
        if not self.pronto():
            return "Saia do quadro e clique em 'Aprender fundo' para ativar o recorte."
        return "Recorte por fundo memorizado: não mova a câmera."

    def mascara(self, quadro: np.ndarray) -> np.ndarray:
        peq = _reduzir(quadro).astype(np.float32)
        if self._fundo is None or self._fundo.shape != peq.shape:
            return np.ones(peq.shape[:2], np.float32)

        dif = peq - self._fundo
        # diferença de brilho e diferença de cor pesadas separadamente
        d_brilho = np.abs(dif.mean(axis=2))
        d_cor = np.abs(dif - dif.mean(axis=2, keepdims=True)).mean(axis=2)
        pontuacao = d_brilho * 0.6 + d_cor * 2.0

        crua = np.clip((pontuacao - self._limiar) / max(1e-6, self._limiar), 0.0, 1.0)
        return IMG.limpar_mascara(crua, raio=2, corte=0.4)


class SegmentadorCentral(Segmentador):
    """Elipse suave no meio do quadro. Não é recorte de pessoa — e avisa isso."""

    nome = "central"
    qualidade = "aproximada"

    def __init__(self, largura_rel: float = 0.62, altura_rel: float = 0.95):
        self._lr = float(largura_rel)
        self._ar = float(altura_rel)
        self._cache: Dict[Tuple[int, int], np.ndarray] = {}

    def aviso(self) -> str:
        return ("Modo aproximado: desfoca as bordas, não recorta a pessoa. "
                "Instale o mediapipe ou use 'Aprender fundo' para recorte de verdade.")

    def mascara(self, quadro: np.ndarray) -> np.ndarray:
        peq = _reduzir(quadro)
        alt, larg = peq.shape[:2]
        pronto = self._cache.get((alt, larg))
        if pronto is None:
            y = np.linspace(-1.0, 1.0, alt, dtype=np.float32)[:, None] / self._ar
            x = np.linspace(-1.0, 1.0, larg, dtype=np.float32)[None, :] / self._lr
            r = np.sqrt(x * x + y * y)
            pronto = np.clip((1.25 - r) / 0.45, 0.0, 1.0).astype(np.float32)
            self._cache = {(alt, larg): pronto}
        return pronto


def _reduzir(quadro: np.ndarray) -> np.ndarray:
    """Leva o quadro para a largura de análise, preservando a proporção."""
    alt, larg = quadro.shape[:2]
    if larg <= LARGURA_ANALISE:
        return IMG.para_float(quadro)
    nova_alt = max(8, int(round(alt * LARGURA_ANALISE / larg)))
    return IMG.redimensionar(quadro, LARGURA_ANALISE, nova_alt)


def criar_segmentador(preferencia: str = "auto") -> Segmentador:
    """Devolve o melhor segmentador que esta máquina consegue rodar.

    `preferencia` pode ser "auto", "mediapipe", "fundo_aprendido" ou "central".
    Pedido explícito que não pode ser atendido cai para o próximo, nunca
    derruba o software: perder o desfoque de fundo é ruim, perder a live é pior.
    """
    preferencia = (preferencia or "auto").strip().lower()
    if preferencia in ("auto", "mediapipe"):
        try:
            return SegmentadorMediaPipe()
        except Exception:
            if preferencia == "mediapipe":
                pass  # pedido explícito falhou: segue para os alternativos
    if preferencia == "fundo_aprendido":
        return SegmentadorFundoAprendido()
    if preferencia == "central":
        return SegmentadorCentral()
    return SegmentadorCentral()


# ----------------------------------------------------------------------------
# o efeito
# ----------------------------------------------------------------------------
class MotorFundo:
    """Junta segmentador, estabilizador temporal e efeito num objeto só."""

    def __init__(self, segmentador: Optional[Segmentador] = None,
                 efeito: Optional[EfeitoFundo] = None):
        self.segmentador = segmentador or criar_segmentador("auto")
        self.efeito = (efeito or EfeitoFundo()).validar()
        self._anterior: Optional[np.ndarray] = None
        self._imagem_cache: Tuple[str, Optional[np.ndarray]] = ("", None)
        self.ultima_mascara: Optional[np.ndarray] = None

    def definir_efeito(self, efeito: EfeitoFundo) -> None:
        self.efeito = efeito.validar()

    def definir_segmentador(self, seg: Segmentador) -> None:
        self.segmentador = seg
        self._anterior = None

    def _mascara_estavel(self, quadro: np.ndarray) -> np.ndarray:
        crua = self.segmentador.mascara(quadro)
        a = self.efeito.suavizacao_temporal / 100.0
        if self._anterior is not None and self._anterior.shape == crua.shape and a > 0:
            crua = self._anterior * a + crua * (1.0 - a)
        self._anterior = crua
        return IMG.suavizar_mascara(crua, raio=self.efeito.recorte_suave)

    def _fundo_para(self, quadro: np.ndarray) -> Optional[np.ndarray]:
        """A imagem que vai ficar atrás da pessoa, em uint8 no tamanho do quadro.

        Sai em 8 bits de propósito: é o que `compor` consome, e converter aqui
        (onde a imagem ainda é pequena, no caso do borrão) custa uma fração do
        que custaria converter o resultado em escala cheia.
        """
        alt, larg = quadro.shape[:2]
        modo = self.efeito.modo

        if modo == "desfocar":
            # Borra em escala reduzida e amplia: um desfoque de raio 40 em 720p
            # sai pelo preço de um raio 10 em 180p, e ninguém distingue borrão
            # forte feito em 1/4 de resolução de borrão forte feito inteiro.
            forca = self.efeito.intensidade / 100.0
            pequeno = IMG.redimensionar(quadro, max(16, larg // 4), max(16, alt // 4))
            raio = max(1, int(round(2 + 14 * forca)))
            borrado = IMG.para_bytes(IMG.desfocar(pequeno, raio))
            return IMG.redimensionar_bytes(borrado, larg, alt)

        if modo == "cor":
            tela = np.empty((alt, larg, 3), np.uint8)
            tela[:, :] = self.efeito.cor
            return tela

        if modo == "imagem":
            img = self._carregar_imagem(self.efeito.caminho_imagem)
            if img is None:
                return None
            return IMG.para_bytes(IMG.enquadrar(img, larg, alt, modo="preencher"))

        return None

    def _carregar_imagem(self, caminho: str) -> Optional[np.ndarray]:
        if not caminho:
            return None
        if self._imagem_cache[0] == caminho:
            return self._imagem_cache[1]
        img = None
        try:
            if cv2 is not None:
                with IMG.silenciar_opencv():
                    lido = cv2.imread(caminho, cv2.IMREAD_COLOR)
                if lido is not None:
                    img = IMG.para_float(lido)
            if img is None:
                from PIL import Image  # dependência opcional
                with Image.open(caminho) as arq:
                    rgb = np.asarray(arq.convert("RGB"))
                img = IMG.para_float(rgb[:, :, ::-1])   # PIL entrega RGB, aqui é BGR
        except Exception:
            img = None
        self._imagem_cache = (caminho, img)
        return img

    def aplicar(self, quadro: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Devolve (quadro com o fundo tratado, máscara da pessoa em escala cheia).

        A máscara volta junto porque a nitidez lá em `filtros` a usa para não
        realçar o fundo que acabou de ser borrado aqui.
        """
        if self.efeito.modo == "nenhum":
            self.ultima_mascara = None
            return IMG.para_bytes(quadro), None

        fundo = self._fundo_para(quadro)
        if fundo is None:
            # modo "imagem" sem imagem válida: segue sem efeito em vez de travar
            self.ultima_mascara = None
            return IMG.para_bytes(quadro), None

        mascara = self._mascara_estavel(quadro)
        alt, larg = quadro.shape[:2]
        cheia = IMG.redimensionar(mascara, larg, alt)
        if cheia.ndim == 3:
            cheia = cheia[:, :, 0]
        self.ultima_mascara = cheia
        return IMG.compor(quadro, fundo, cheia), cheia
