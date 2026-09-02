# -*- coding: utf-8 -*-
"""
As contas de imagem — em NumPy puro, com OpenCV só como acelerador.

POR QUE NUMPY PURO
------------------
O embelezamento e o desfoque de fundo são o coração deste software. Se eles
dependessem de OpenCV, uma instalação que falha (e no Windows, com Python novo,
falha bastante) deixaria a live sem nenhum dos dois recursos que ele pediu.

Então tudo aqui tem caminho em NumPy. Quando o OpenCV existe, as mesmas funções
desviam para ele porque é mais rápido — mas o resultado é o mesmo tipo de
imagem, com a mesma forma e a mesma escala. Nenhuma função muda de contrato
conforme a biblioteca instalada.

CONVENÇÃO DE FORMATO
--------------------
Quadro é `ndarray` BGR (a ordem que o OpenCV e o ffmpeg usam), altura × largura
× 3. Internamente as contas rodam em float32 de 0 a 1; a conversão para uint8
só acontece na borda, quando o quadro sai para a tela, para a câmera virtual ou
para o encoder.

O CUSTO IMPORTA
---------------
A 30 quadros por segundo, o orçamento é 33 ms para TUDO. Um borrão de caixa em
1280×720 já come uma fatia disso. Por isso as funções caras (`filtro_guiado`)
têm versão que trabalha em escala reduzida e devolve o resultado em escala
cheia: é a técnica do *fast guided filter*, e é a diferença entre 30 fps e 8.
"""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np

try:  # acelerador opcional — nada aqui exige que ele exista
    import cv2
except Exception:  # pragma: no cover - depende da máquina
    cv2 = None


# ----------------------------------------------------------------------------
# silêncio do OpenCV
# ----------------------------------------------------------------------------
@contextmanager
def silenciar_opencv():
    """Cala o log do OpenCV dentro do bloco.

    Duas operações normais deste software fazem o OpenCV gritar no terminal:
    sondar índice de câmera que não existe (é assim que se descobre quais
    existem) e abrir uma imagem de fundo que a pessoa apagou. Nos dois casos a
    falha é o resultado esperado e já está tratada — o que sobra é linha
    vermelha assustando quem está só configurando a live.
    """
    nivel = None
    try:
        if cv2 is not None:
            nivel = cv2.utils.logging.getLogLevel()
            cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    except Exception:
        nivel = None
    try:
        yield
    finally:
        if nivel is not None:
            try:
                cv2.utils.logging.setLogLevel(nivel)
            except Exception:
                pass


# ----------------------------------------------------------------------------
# conversões
# ----------------------------------------------------------------------------
def para_float(img: np.ndarray) -> np.ndarray:
    """uint8 0..255 -> float32 0..1. Se já for float, só garante o tipo."""
    a = np.asarray(img)
    if a.dtype == np.uint8:
        return a.astype(np.float32) / 255.0
    return a.astype(np.float32, copy=False)


def para_bytes(img: np.ndarray) -> np.ndarray:
    """float 0..1 -> uint8 0..255, com corte nas pontas (sem estourar).

    O caminho do OpenCV faz o mesmo em duas passadas otimizadas em vez das três
    do NumPy (multiplicar, cortar, converter). O `cv2.max` antes NÃO é
    desperdício: `convertScaleAbs` toma o valor ABSOLUTO, então um -0,02 viraria
    5 em vez de 0 — o zero precisa ser garantido antes.
    """
    a = np.asarray(img)
    if a.dtype == np.uint8:
        return a
    if cv2 is not None and a.dtype == np.float32:
        # `cv2.threshold` com THRESH_TOZERO zera o que for negativo numa passada.
        # O caminho óbvio, `cv2.max(a, 0.0)`, tem uma armadilha: num array 1x1x3
        # o OpenCV lê o escalar do Python como Scalar de 4 elementos e devolve
        # (4,1) em vez de (1,1,3). Some em imagem grande e aparece em teste.
        return cv2.convertScaleAbs(cv2.threshold(a, 0.0, 0.0, cv2.THRESH_TOZERO)[1],
                                   alpha=255.0)
    return np.clip(a * 255.0 + 0.5, 0, 255).astype(np.uint8)


def redimensionar_bytes(img: np.ndarray, largura: int, altura: int) -> np.ndarray:
    """Reamostra mantendo 8 bits do começo ao fim.

    `redimensionar` promove para float porque quase todo mundo aqui faz conta
    depois. Quem só precisa esticar uma imagem que já está pronta — o fundo
    borrado, por exemplo — economiza a ida e a volta usando esta.
    """
    largura, altura = max(1, int(largura)), max(1, int(altura))
    a = para_bytes(img)
    if a.shape[0] == altura and a.shape[1] == largura:
        return a
    if cv2 is not None:
        modo = cv2.INTER_AREA if (largura < a.shape[1] or altura < a.shape[0]) else cv2.INTER_LINEAR
        return cv2.resize(a, (largura, altura), interpolation=modo)
    return para_bytes(_bilinear(a.astype(np.float32) / 255.0, largura, altura))


def luminancia(img: np.ndarray) -> np.ndarray:
    """Brilho perceptual de um quadro BGR, em float 0..1 (altura × largura)."""
    a = para_float(img)
    if a.ndim == 2:
        return a
    return 0.114 * a[..., 0] + 0.587 * a[..., 1] + 0.299 * a[..., 2]


# ----------------------------------------------------------------------------
# redimensionamento
# ----------------------------------------------------------------------------
def _bilinear(a: np.ndarray, largura: int, altura: int) -> np.ndarray:
    """Interpolação bilinear em NumPy, com amostragem no centro do pixel.

    O `+ 0.5 ... - 0.5` não é enfeite: sem ele a imagem reduzida escorrega meio
    pixel para o canto, e uma máscara de fundo calculada em escala pequena volta
    desalinhada da pessoa ao ser ampliada.
    """
    plano = a.ndim == 2
    if plano:
        a = a[:, :, None]
    alt, larg = a.shape[:2]
    a = a.astype(np.float32, copy=False)

    y = (np.arange(altura, dtype=np.float32) + 0.5) * (alt / altura) - 0.5
    x = (np.arange(largura, dtype=np.float32) + 0.5) * (larg / largura) - 0.5
    y0 = np.floor(y).astype(np.int32)
    x0 = np.floor(x).astype(np.int32)
    wy = (y - y0).astype(np.float32)[:, None, None]
    wx = (x - x0).astype(np.float32)[None, :, None]
    y1 = np.clip(y0 + 1, 0, alt - 1)
    x1 = np.clip(x0 + 1, 0, larg - 1)
    y0 = np.clip(y0, 0, alt - 1)
    x0 = np.clip(x0, 0, larg - 1)

    # Separável de propósito: interpola primeiro nas linhas, depois nas colunas.
    # A forma direta (`a[np.ix_(y0, x0)]`, quatro vezes) é indexação avançada em
    # duas dimensões e materializa quatro arrays do tamanho final. Em dois
    # passos são quatro `take` num eixo só, sobre um intermediário menor — mesma
    # conta, mesmo resultado, uma fração do tempo. Ampliar a máscara de
    # segmentação até a resolução da live vive neste caminho, quadro a quadro.
    linhas = a.take(y0, axis=0) * (1.0 - wy) + a.take(y1, axis=0) * wy
    out = linhas.take(x0, axis=1) * (1.0 - wx) + linhas.take(x1, axis=1) * wx
    return out[:, :, 0] if plano else out


def redimensionar(img: np.ndarray, largura: int, altura: int) -> np.ndarray:
    """Reamostra para o tamanho pedido. Devolve float32."""
    largura = max(1, int(largura))
    altura = max(1, int(altura))
    a = para_float(img)
    if a.shape[0] == altura and a.shape[1] == largura:
        return a
    if cv2 is not None:
        # INTER_AREA encolhe sem serrilhar; INTER_LINEAR amplia sem borrar demais
        modo = cv2.INTER_AREA if (largura < a.shape[1] or altura < a.shape[0]) else cv2.INTER_LINEAR
        return cv2.resize(a, (largura, altura), interpolation=modo)
    return _bilinear(a, largura, altura)


def enquadrar(img: np.ndarray, largura: int, altura: int, modo: str = "preencher") -> np.ndarray:
    """Ajusta o quadro à resolução da transmissão.

    "preencher" corta as sobras para ocupar a tela inteira (padrão: barra preta
    em live parece defeito). "caber" reduz e deixa barras, preservando tudo.
    """
    a = para_float(img)
    alt, larg = a.shape[:2]
    if (larg, alt) == (largura, altura):
        return a

    escala_x, escala_y = largura / larg, altura / alt
    if modo == "caber":
        escala = min(escala_x, escala_y)
        nl, na = max(1, int(round(larg * escala))), max(1, int(round(alt * escala)))
        redim = redimensionar(a, nl, na)
        tela = np.zeros((altura, largura, a.shape[2] if a.ndim == 3 else 1), np.float32)
        if a.ndim == 2:
            tela = tela[:, :, 0]
        y = (altura - na) // 2
        x = (largura - nl) // 2
        tela[y:y + na, x:x + nl] = redim
        return tela

    escala = max(escala_x, escala_y)
    nl, na = max(largura, int(round(larg * escala))), max(altura, int(round(alt * escala)))
    redim = redimensionar(a, nl, na)
    y = (na - altura) // 2
    x = (nl - largura) // 2
    return redim[y:y + altura, x:x + largura]


# ----------------------------------------------------------------------------
# borrões
# ----------------------------------------------------------------------------
def media_caixa(img: np.ndarray, raio: int) -> np.ndarray:
    """Média numa janela quadrada de lado 2*raio+1, normalizada na borda.

    Feita por imagem integral: o custo não depende do raio. Um borrão de fundo
    com raio 40 sai pelo mesmo preço de um com raio 4 — o que permite desfoque
    realmente forte sem perder quadro.
    """
    raio = int(raio)
    if raio < 1:
        return para_float(img)
    a = para_float(img)
    if cv2 is not None:
        # BORDER_REPLICATE, e não REFLECT, para casar exatamente com o `np.pad`
        # de modo "edge" do caminho NumPy logo abaixo. As duas implementações
        # precisam entregar o MESMO pixel, borda inclusive — é isso que um
        # acelerador opcional significa.
        k = 2 * raio + 1
        return cv2.blur(a, (k, k), borderType=cv2.BORDER_REPLICATE)

    plano = a.ndim == 2
    if plano:
        a = a[:, :, None]
    alt, larg = a.shape[:2]

    # A borda é estendida por réplica ANTES da integral, e não corrigida depois
    # dividindo por uma contagem variável. Parece detalhe, e é a diferença
    # entre 300 ms e 20 ms num quadro 720p: com a moldura pronta, as quatro
    # esquinas da janela são fatias contíguas do array, sem indexação avançada.
    k = 2 * raio + 1
    moldura = np.pad(a, ((raio, raio), (raio, raio), (0, 0)), mode="edge")
    integral = np.zeros((alt + k, larg + k, a.shape[2]), np.float32)
    np.cumsum(np.cumsum(moldura, axis=0, dtype=np.float32), axis=1, out=integral[1:, 1:])

    soma = (integral[k:, k:] - integral[:alt, k:]
            - integral[k:, :larg] + integral[:alt, :larg])
    out = soma / np.float32(k * k)
    return out[:, :, 0] if plano else out


def desfocar(img: np.ndarray, raio: int, passes: int = 3) -> np.ndarray:
    """Borrão suave. Três médias de caixa seguidas convergem para gaussiana.

    É o teorema central do limite aplicado a pixel: a caixa repetida vira sino.
    Uma caixa só deixa quadradinho visível no fundo desfocado — três não.
    """
    raio = int(raio)
    if raio < 1:
        return para_float(img)
    if cv2 is not None:
        sigma = max(0.8, raio / 2.0)
        k = int(2 * round(sigma * 2) + 1)
        return cv2.GaussianBlur(para_float(img), (k, k), sigma,
                                borderType=cv2.BORDER_REPLICATE)
    r = max(1, int(round(raio / max(1, passes) * 1.4)))
    out = para_float(img)
    for _ in range(max(1, passes)):
        out = media_caixa(out, r)
    return out


# ----------------------------------------------------------------------------
# filtro guiado — o suavizador que preserva borda
# ----------------------------------------------------------------------------
def filtro_guiado(img: np.ndarray, raio: int = 8, eps: float = 0.01,
                  subamostra: int = 4) -> np.ndarray:
    """Suaviza sem derreter contorno. É a base do embelezamento de pele.

    O truque do filtro guiado: dentro da janela, aproxima a saída por uma reta
    `a*entrada + b` ajustada por mínimos quadrados. Onde a variância local é
    baixa (pele), `a` vai a zero e o resultado é a média — alisa. Onde é alta
    (olho, boca, contorno do rosto), `a` vai a um e o resultado é a própria
    entrada — não mexe. Um desfoque comum não sabe fazer essa distinção e
    entrega aquele rosto de cera que denuncia filtro barato.

    `subamostra` calcula os coeficientes em escala reduzida e só depois amplia:
    é o *fast guided filter*, ~16x mais barato com 4, e a olho nu o resultado é
    o mesmo, porque `a` e `b` variam devagar no espaço.
    """
    entrada = para_float(img)
    alt, larg = entrada.shape[:2]
    s = max(1, int(subamostra))

    if s > 1:
        peq = redimensionar(entrada, max(1, larg // s), max(1, alt // s))
        r_peq = max(1, int(raio) // s)
    else:
        peq, r_peq = entrada, max(1, int(raio))

    media_i = media_caixa(peq, r_peq)
    media_ii = media_caixa(peq * peq, r_peq)
    variancia = np.maximum(media_ii - media_i * media_i, 0.0)

    a = variancia / (variancia + float(eps))
    b = media_i - a * media_i

    a = media_caixa(a, r_peq)
    b = media_caixa(b, r_peq)
    if s > 1:
        a = redimensionar(a, larg, alt)
        b = redimensionar(b, larg, alt)
    return a * entrada + b


# ----------------------------------------------------------------------------
# máscaras
# ----------------------------------------------------------------------------
def suavizar_mascara(mascara: np.ndarray, raio: int = 6) -> np.ndarray:
    """Borra a borda da máscara (feather) e prende o resultado em 0..1.

    Sem isso a troca de fundo fica com recorte de tesoura em volta da pessoa —
    o defeito que mais entrega segmentação ruim em live.
    """
    m = np.clip(np.asarray(mascara, np.float32), 0.0, 1.0)
    if raio > 0:
        m = desfocar(m, raio)
    return np.clip(m, 0.0, 1.0)


def limpar_mascara(mascara: np.ndarray, raio: int = 3, corte: float = 0.5) -> np.ndarray:
    """Tira sal-e-pimenta da máscara: média de caixa seguida de limiar.

    Aproxima uma abertura+fechamento morfológico usando só o que já existe
    aqui. Pontinhos isolados não sobrevivem à média; a silhueta sobrevive.
    """
    m = np.clip(np.asarray(mascara, np.float32), 0.0, 1.0)
    if raio > 0:
        m = media_caixa(m, raio)
    return (m >= float(corte)).astype(np.float32)


def compor(frente: np.ndarray, fundo: np.ndarray, mascara: np.ndarray) -> np.ndarray:
    """frente*m + fundo*(1-m). Devolve uint8, com a máscara ajustada ao quadro.

    `cv2.blendLinear` é exatamente esta conta numa passada só, direto em 8 bits.
    A versão em float fazia seis passadas sobre 11 MB cada — era o item mais
    caro do desfoque de fundo, mais caro que o próprio borrão.
    """
    m = np.clip(np.asarray(mascara, np.float32), 0.0, 1.0)
    if m.ndim == 3:
        m = m[:, :, 0]
    f8 = para_bytes(frente)
    g8 = para_bytes(fundo)
    if m.shape[:2] != f8.shape[:2]:
        m = redimensionar(m, f8.shape[1], f8.shape[0])
        if m.ndim == 3:
            m = m[:, :, 0]
    m = np.ascontiguousarray(m, np.float32)
    if cv2 is not None:
        return cv2.blendLinear(f8, g8, m, 1.0 - m)
    m3 = m[:, :, None]
    return para_bytes((f8 * m3 + g8 * (1.0 - m3)) / 255.0)
