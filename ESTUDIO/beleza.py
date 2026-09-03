# -*- coding: utf-8 -*-
"""
BELEZA — o embelezamento, por separação de frequência, dentro do orçamento.

O QUE ELE PEDIU
───────────────
    "te pedi emebelezamento"

O JEITO ERRADO, QUE É O QUE QUASE TODO SOFTWARE FAZ
───────────────────────────────────────────────────
Passar um borrão na pele. Some a espinha e some também o poro, o fio de barba
e a borda do nariz -- o rosto vira plástico e todo mundo reconhece de longe
que tem filtro ligado. É pior que não ter.

O JEITO CERTO, QUE É O QUE ESTÁ AQUI
────────────────────────────────────
Separação de frequência, como se retoca foto de verdade:

    baixa  = versão suave da pele (bilateral: alisa mantendo as BORDAS)
    alta   = imagem - baixa            -> só textura e manchas
    saída  = baixa + alta * (1 - força)

Reduzir a AMPLITUDE da textura, em vez de apagá-la, mantém pele com cara de
pele. Em 0,45 (o padrão) a mancha fica discreta e o poro continua lá.

As manchas levam tratamento à parte: na camada alta, mancha é pico largo e
forte; textura é miúda. Corto o pico e deixo o miúdo passar inteiro -- é o
que permite tirar mancha SEM subir a força geral.

A PRIMEIRA VERSÃO DISTO CUSTAVA 240 ms/QUADRO. O QUE EU FIZ ERRADO
──────────────────────────────────────────────────────────────────
Escrevi a cadeia toda em float32 sobre a imagem inteira: uma dúzia de arrays
de 2,7 milhões de floats, cada um custando milissegundos. Ficou correto e
inútil -- 4 quadros por segundo.

As três correções, cada uma medida:

  1. MÁSCARA EM BAIXA RESOLUÇÃO. Máscara é campo suave; calcular a 320 de
     largura e ampliar dá o mesmo resultado por 1/12 da conta.
  2. RECORTE. Fora da caixa do rosto a máscara é zero e a saída é IGUAL à
     entrada. Processar o quadro todo era calcular o que eu ia jogar fora.
     Agora processo a caixa e colo de volta -- exato, não aproximado.
  3. A CADEIA INTEIRA NUMA TABELA DE 256 ENTRADAS. Força da pele e corte de
     mancha são função só da amplitude do pixel alto. Isso é uma curva 1D, e
     curva 1D em 8 bits é `cv2.LUT`: 0,3 ms, em vez de `np.where` e
     multiplicação em float na imagem cheia.

Custo de guardar a camada alta em 8 bits: ela fica em passos de 2 níveis. Só
que eu vou justamente REDUZIR essa camada, e o grão do look entra depois em
cima. Não há como ver, e o teste de textura confirma que a textura sobrevive.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

from ia_visual import Rosto, mascara_pele
from visual import misturar

LARGURA_MASCARA = 320       # onde as máscaras são calculadas
MARGEM_ROI = 0.06           # folga do recorte, em fração do lado


# ─────────────────────────────────────────────────────────────────────────────
# MÁSCARAS
# ─────────────────────────────────────────────────────────────────────────────

def mascara_rosto(h: int, w: int, rosto: Optional[Rosto],
                  folga: float = 1.15) -> Optional[np.ndarray]:
    """Elipse suave na caixa do rosto. Suave porque borda dura aparece.

    Corte reto deixa degrau na testa quando o alisamento é forte -- a marca do
    filtro barato. A queda gradual faz a transição desaparecer.
    """
    if rosto is None or not rosto.valido:
        return None
    cx, cy = rosto.centro()
    rx = max(2.0, rosto.w * 0.5 * folga)
    ry = max(2.0, rosto.h * 0.5 * folga * 1.12)   # rosto é mais alto que largo
    yy = (np.arange(h, dtype=np.float32)[:, None] - cy) / ry
    xx = (np.arange(w, dtype=np.float32)[None, :] - cx) / rx
    d = np.sqrt(xx * xx + yy * yy)
    return np.clip((1.25 - d) / 0.5, 0.0, 1.0).astype(np.float32)


def caixa_da_mascara(m: np.ndarray, limiar: float = 0.02,
                     margem: float = MARGEM_ROI) -> Optional[Tuple[int, int, int, int]]:
    """Onde a máscara não é zero. Fora daqui a saída é igual à entrada."""
    linhas = np.flatnonzero(m.max(axis=1) > limiar)
    colunas = np.flatnonzero(m.max(axis=0) > limiar)
    if linhas.size == 0 or colunas.size == 0:
        return None
    h, w = m.shape[:2]
    my, mx = int(h * margem) + 1, int(w * margem) + 1
    return (max(0, int(colunas[0]) - mx), max(0, int(linhas[0]) - my),
            min(w, int(colunas[-1]) + 1 + mx), min(h, int(linhas[-1]) + 1 + my))


# ─────────────────────────────────────────────────────────────────────────────
# A TABELA QUE FAZ O RETOQUE
# ─────────────────────────────────────────────────────────────────────────────

def tabela_alta(pele: float) -> np.ndarray:
    """A curva que reduz a TEXTURA. 256 entradas, cache no chamador.

    Entrada: a camada alta guardada como 8 bits com 128 = zero e passo de 2
    níveis reais. Saída: a mesma coisa, com amplitude reduzida por
    `1 - pele*0,9`. Só isso -- mancha é tratada noutro lugar, e o parágrafo
    abaixo explica por que teve de ser assim.
    """
    d = (np.arange(256, dtype=np.float32) - 128.0) * 2.0      # alta real
    k = 1.0 - float(np.clip(pele, 0.0, 1.0)) * 0.9
    saida = 128.0 + (d * k) * 0.5
    tab = np.clip(saida, 0, 255).astype(np.uint8).reshape(1, 256)
    # três canais IGUAIS. E não com `repeat(...).reshape(1,256,3)`: aquilo
    # reordena a memória e entrega a tabela embaralhada -- foi o defeito que
    # fez a textura AUMENTAR em vez de diminuir, e o teste de textura o pegou.
    return np.stack([tab] * 3, axis=-1)


def tabela_mancha(manchas: float) -> np.ndarray:
    """Quanto corrigir de cada excursão ESCURA, por amplitude. 256 entradas.

    POR QUE MANCHA NÃO SAI PELO MESMO CAMINHO DA TEXTURA
    ────────────────────────────────────────────────────
    Eu tinha resolvido as duas juntas: cortar os picos grandes da camada alta.
    Medi e não funcionou -- a mancha continuava (37 -> 38 níveis de contraste
    com a pele em volta). O motivo é que a camada alta vem de um filtro
    bilateral, e bilateral PRESERVA borda. Uma mancha é uma borda. Ela nunca
    chegava na camada alta para ser cortada; ficava na camada baixa, intacta.

    Então mancha tem mecanismo próprio, e ele usa a única coisa que separa
    mancha de textura de verdade: mancha é mais ESCURA que a pele em volta,
    numa escala de poucos pixels. Comparo com a mediana (que apaga bolha e
    mantém contorno longo) e corrijo só o que ficou escuro demais.

    A curva tem três zonas, e as três importam:

      até ~6 níveis   nada. É textura e sombra de poro; mexer aqui vira plástico.
      6 a ~40         corrige. É a faixa onde mancha, espinha e olheira vivem.
      acima de ~55    solta. É narina, sobrancelha, óculos, barba -- feição, e
                      apagar feição é o que faz filtro parecer máscara.

    A zona de cima é o que protege sobrancelha e cílio, e eu conferi com
    número em vez de confiar: numa sobrancelha o escurecimento medido foi 97
    níveis, bem acima do corte de 58, então o peso lá é zero.

    Cheguei a excluir também a faixa dos olhos inteira por precaução. Tirei:
    a faixa cobria de 24% a 50% da altura do rosto, que é onde vive metade
    das manchas de verdade (maçã do rosto, lado do nariz), e ela estava
    anulando a correção justamente ali. Proteção por amplitude protege o que
    tem de ser protegido sem cobrar esse preço.
    """
    x = np.arange(256, dtype=np.float32)      # o quanto está mais escuro
    mc = float(np.clip(manchas, 0.0, 1.0))
    if mc <= 0.001:
        return np.zeros((1, 256, 3), dtype=np.uint8)
    sobe = np.clip((x - 6.0) / 12.0, 0.0, 1.0)
    desce = np.clip((58.0 - x) / 18.0, 0.0, 1.0)
    peso = np.minimum(sobe, desce)
    peso = peso * peso * (3.0 - 2.0 * peso)                   # smoothstep
    # a saída é o quanto SOMAR de volta: escurecimento * peso * força
    corr = np.clip(x * peso * mc * 0.85, 0, 255).astype(np.uint8).reshape(1, 256)
    return np.stack([corr] * 3, axis=-1)


def _banda_vertical(h: int, y0: float, y1: float, suave: float) -> np.ndarray:
    """Peso 1 entre y0 e y1, caindo a 0 em `suave` pixels de cada lado."""
    y = np.arange(h, dtype=np.float32)
    s = max(1.0, float(suave))
    sobe = np.clip((y - (y0 - s)) / s, 0.0, 1.0)
    desce = np.clip(((y1 + s) - y) / s, 0.0, 1.0)
    return np.minimum(sobe, desce).reshape(h, 1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# A CADEIA
# ─────────────────────────────────────────────────────────────────────────────

class Beleza:
    """Guarda o cache da tabela: refazer 256 entradas por quadro é desperdício."""

    def __init__(self) -> None:
        self._chave: Tuple[float, float] = (-1.0, -1.0)
        self._tab: Optional[np.ndarray] = None
        self._tab_mancha: Optional[np.ndarray] = None

    def _tabelas(self, pele: float, manchas: float) -> Tuple[np.ndarray, np.ndarray]:
        chave = (round(float(pele), 3), round(float(manchas), 3))
        if chave != self._chave or self._tab is None:
            self._tab = tabela_alta(chave[0])
            self._tab_mancha = tabela_mancha(chave[1])
            self._chave = chave
        return self._tab, self._tab_mancha

    def aplicar(self, img: np.ndarray, rosto: Optional[Rosto] = None,
                pele: float = 0.45, manchas: float = 0.35,
                olhos: float = 0.25, dentes: float = 0.20,
                so_no_rosto: bool = True) -> np.ndarray:
        if not TEM_CV or img is None or img.size == 0:
            return img
        if max(pele, manchas, olhos, dentes) <= 0.001:
            return img

        h, w = img.shape[:2]
        k = LARGURA_MASCARA / float(max(1, w))

        # ── 1. máscara, em baixa resolução ────────────────────────────────
        if k < 1.0:
            peq = cv2.resize(img, (LARGURA_MASCARA, max(2, int(h * k))),
                             interpolation=cv2.INTER_AREA)
        else:
            peq, k = img, 1.0
        hp, wp = peq.shape[:2]

        m = mascara_pele(peq)
        if so_no_rosto:
            mr = mascara_rosto(hp, wp, rosto.escalar(k) if rosto else None)
            if mr is not None:
                m = m * mr
        m = cv2.GaussianBlur(m, (0, 0), 2.5)
        if float(m.max()) < 0.02:
            return img                   # não há pele à vista: nada a fazer

        # ── 2. recorte ────────────────────────────────────────────────────
        cx = caixa_da_mascara(m)
        if cx is None:
            return img
        x0 = int(cx[0] / k); y0 = int(cx[1] / k)
        x1 = min(w, int(np.ceil(cx[2] / k))); y1 = min(h, int(np.ceil(cx[3] / k)))
        if x1 - x0 < 8 or y1 - y0 < 8:
            return img
        roi = img[y0:y1, x0:x1]
        rh, rw = roi.shape[:2]
        mr_roi = cv2.resize(m[cx[1]:cx[3], cx[0]:cx[2]], (rw, rh),
                            interpolation=cv2.INTER_LINEAR)[..., None]

        # ── 3. olho e dente: a máscara nasce AQUI, em baixa resolução ──
        # A primeira versão fazia isto na ROI em float32 e custava 70 dos 86
        # ms do módulo -- média, máximo e mínimo por canal em imagem grande,
        # mais um desfoque de sigma 21. Máscara é campo suave: em 320 de
        # largura dá o mesmo mapa por 1/12 da conta.
        ganho_peq = azul_peq = None
        if (olhos > 0.001 or dentes > 0.001) and rosto is not None \
                and rosto.valido:
            ganho_peq, azul_peq = self._mapas_olho_dente(
                peq, m, rosto.escalar(k), olhos, dentes)

        # ── 4. mancha: corrigir o que ficou ESCURO demais ─────────────────
        tab_alta, tab_mancha = self._tabelas(pele, manchas)
        base = roi
        if manchas > 0.001:
            # A ESCALA AQUI NÃO É GOSTO, É O QUE FAZ FUNCIONAR.
            # Medi: uma mancha de 18 px de diâmetro, com mediana em MEIA
            # resolução e núcleo 7, aparece como 0 níveis -- a mediana não
            # remove bolha maior que o próprio núcleo, então não sobra nada
            # para corrigir. Em 1/4 de resolução com o mesmo núcleo aparece
            # como 31 níveis, e o falso positivo na pele lisa continua em 1.
            # Por isso 1/4, e por isso o núcleo acompanha o tamanho do rosto:
            # rosto perto da webcam tem mancha maior em pixels.
            larg = float(rosto.w) if (rosto is not None and rosto.valido) else rw
            k_med = int(np.clip(round(larg / 4.0 * 0.10), 5, 21)) | 1
            pqm = cv2.resize(roi, (max(8, rw // 4), max(8, rh // 4)),
                             interpolation=cv2.INTER_AREA)
            mediana = cv2.resize(cv2.medianBlur(pqm, k_med), (rw, rh),
                                 interpolation=cv2.INTER_LINEAR)
            # subtração que satura em zero: sobra SÓ onde a pele está mais
            # escura que a mediana. O lado claro (brilho, reflexo) não é
            # mancha e não é tocado -- de graça, pela saturação do uint8.
            escuro = cv2.subtract(mediana, roi)
            base = cv2.add(roi, cv2.LUT(escuro, tab_mancha))

        # ── 5. separação de frequência, em 8 bits ─────────────────────────
        pq = cv2.resize(base, (max(8, rw // 2), max(8, rh // 2)),
                        interpolation=cv2.INTER_AREA)
        baixa = cv2.resize(cv2.bilateralFilter(pq, 5, 55, 55), (rw, rh),
                           interpolation=cv2.INTER_LINEAR)
        # alta em 8 bits, 128 = zero:  0,5*(base - baixa) + 128
        alta = cv2.addWeighted(base, 0.5, baixa, -0.5, 128.0)
        alta = cv2.LUT(alta, tab_alta)
        # reconstrói:  baixa + 2*(alta - 128)
        retocado = cv2.addWeighted(baixa, 1.0, alta, 2.0, -256.0)

        # ── 6. olho e dente, com operações do OpenCV e não em float ───────
        f = retocado
        if ganho_peq is not None:
            g = cv2.resize(ganho_peq[cx[1]:cx[3], cx[0]:cx[2]], (rw, rh),
                           interpolation=cv2.INTER_LINEAR)
            f = cv2.multiply(f, cv2.merge([g, g, g]), dtype=cv2.CV_8U)
        if azul_peq is not None:
            a = cv2.resize(azul_peq[cx[1]:cx[3], cx[0]:cx[2]], (rw, rh),
                           interpolation=cv2.INTER_LINEAR)
            # dente amarelado = azul em falta. Puxo o azul para a média de R e
            # G: clareia sem deixar o dente azul de anúncio de pasta de dente.
            canais = list(cv2.split(f))
            rg = cv2.addWeighted(canais[1], 0.5, canais[2], 0.5, 0.0)
            falta = cv2.subtract(rg, canais[0], dtype=cv2.CV_32F)
            canais[0] = cv2.add(canais[0], cv2.multiply(falta, a),
                                dtype=cv2.CV_8U)
            f = cv2.merge(canais)

        saida = img.copy()
        saida[y0:y1, x0:x1] = misturar(f, roi, mr_roi)
        return saida

    @staticmethod
    def _mapas_olho_dente(peq: np.ndarray, m_pele: np.ndarray, rosto: Rosto,
                          olhos: float, dentes: float
                          ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Onde clarear (olho) e onde tirar o amarelo (dente), em baixa res.

        Olho e dente têm a MESMA assinatura -- claro, quase sem cor, cercado
        de pele -- e o que os separa é a ALTURA no rosto. Sem rosto detectado
        quem chama nem chega aqui: clarear "o que é claro e não é pele"
        clarearia a camisa, a parede e o reflexo do óculos dele.
        """
        h, w = peq.shape[:2]
        f = peq.astype(np.float32)
        luz = f.mean(axis=2) / 255.0
        mx = f.max(axis=2)
        mn = f.min(axis=2)
        sat = (mx - mn) / np.maximum(mx, 1e-3)
        branco = (np.clip((luz - 0.28) / 0.45, 0, 1)
                  * np.clip(1.0 - sat / 0.45, 0, 1))

        # cercado de pele: sem isto, parede clara entra
        perto = cv2.GaussianBlur(m_pele, (0, 0), max(1.5, rosto.w / 14.0))
        alvo = (branco * np.clip(perto * 3.0, 0, 1)
                * np.clip(1.0 - m_pele * 1.4, 0, 1))

        ganho = azul = None
        if olhos > 0.001:
            faixa = _banda_vertical(h, rosto.y + rosto.h * 0.24,
                                    rosto.y + rosto.h * 0.52,
                                    max(1.5, rosto.h * 0.06))[..., 0]
            ganho = 1.0 + (alvo * faixa) * (float(np.clip(olhos, 0, 1)) * 0.40)
        if dentes > 0.001:
            faixa = _banda_vertical(h, rosto.y + rosto.h * 0.62,
                                    rosto.y + rosto.h * 0.94,
                                    max(1.5, rosto.h * 0.05))[..., 0]
            azul = (alvo * faixa) * (float(np.clip(dentes, 0, 1)) * 0.55)
        return (None if ganho is None else ganho.astype(np.float32),
                None if azul is None else azul.astype(np.float32))


_PADRAO = Beleza()


def embelezar(img: np.ndarray, rosto: Optional[Rosto] = None, **kw) -> np.ndarray:
    """Atalho para quem não quer guardar a instância (o teste usa isto)."""
    return _PADRAO.aplicar(img, rosto, **kw)
