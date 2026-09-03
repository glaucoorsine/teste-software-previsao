# -*- coding: utf-8 -*-
"""
VISUAL — os filtros cinematográficos, no estilo das câmeras Sony.

O QUE ELE PEDIU
───────────────
    "te pedi filtros cinematograficos ao estilo camera sony"

O QUE EU NÃO POSSO DAR, DITO ANTES DE ELE PERGUNTAR
───────────────────────────────────────────────────
Os LUTs oficiais da Sony (S-Cinetone, s-Log3 → 709, Venice) são arquivos
proprietários da Sony. Não vêm aqui e eu não vou dizer que vêm. O que está
aqui é EMULAÇÃO: eu reproduzi o comportamento que caracteriza cada perfil --
o joelho suave nas altas, o tom de pele levemente quente, a saturação contida,
a sombra fria -- com curvas e matrizes minhas, ajustadas medindo o resultado.

Fica parecido. Não é o arquivo da Sony. E se ele tiver o `.cube` oficial (a
Sony distribui alguns de graça no site dela), o campo `lut_arquivo` carrega o
dele e ele VENCE o meu -- é para isso que o carregador de `.cube` existe.

A DECISÃO QUE FAZ ISTO RODAR AO VIVO
────────────────────────────────────
Medi as três formas de aplicar cor a 1280x720:

    LUT 3D trilinear em numpy .................. 325 ms/quadro   impossível
    tabela 64³ plana + np.take ................... 5,9 ms/quadro
    matriz 3x3 + curvas 1D ....................... 1,2 ms/quadro

E medi o erro da tabela 64³ contra o trilinear exato: 1,4 nível de 255 em
média, 5 no pior pixel. Invisível, e o grão que ele pediu cobre o resto.

Então TUDO -- exposição do look, contraste, temperatura, saturação, split
tone, e o `.cube` dele -- é assado numa única tabela 64³ quando ele mexe no
controle. Ao vivo, cada quadro paga UM gather de 5,9 ms, não importa quantas
operações o look tenha. Mover o cursor de "força" não custa nada por quadro:
custa uma re-assada de milissegundos, uma vez.

O que NÃO entra na tabela: a correção que a IA muda a cada quadro (exposição e
branco). Essa é uma curva 1D de 256 entradas, reconstruída por quadro, e
custa 0,3 ms com `cv2.LUT`. Assar a tabela 64³ a cada quadro seria jogar o
orçamento todo fora.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import cv2
    TEM_CV = True
except Exception:                                    # pragma: no cover
    TEM_CV = False

# Lado da tabela assada. 64 saiu da medição acima: 32 erra demais, 128 são
# 6 MB e não melhora nada que se veja.
N_TAB = 64


# ─────────────────────────────────────────────────────────────────────────────
# O QUE É UM LOOK
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Look:
    """Um perfil de imagem. Números em escala de cena linear onde faz sentido.

    `nome_na_tela` é o que ele lê; a chave do dicionário é o que fica salvo.
    """
    nome_na_tela: str
    porque: str                       # aparece na tela, para ele escolher sabendo
    ev: float = 0.0                   # exposição, em paradas
    contraste: float = 1.0            # 1 = não mexe
    pivo: float = 0.435               # o cinza médio, onde o contraste gira
    levanta_sombra: float = 0.0       # só as sombras, não a imagem toda
    joelho: float = 0.55              # onde as altas começam a ceder (0..1)
    rolagem: float = 0.5              # quão macia é a cedência
    temp: float = 0.0                 # + quente, - frio
    tinta: float = 0.0                # + magenta, - verde
    saturacao: float = 1.0
    protege_pele: float = 0.5         # segura a saturação na faixa da pele
    cor_sombra: Tuple[float, float, float] = (0.0, 0.0, 0.0)   # BGR, split tone
    cor_alta: Tuple[float, float, float] = (0.0, 0.0, 0.0)


LOOKS: Dict[str, Look] = {
    "s_cinetone": Look(
        "S-Cinetone (emulação)",
        "o padrão das Sony de cinema: pele natural, altas que cedem devagar, "
        "cor contida. É o que mais parece 'câmera boa' numa webcam.",
        ev=0.05, contraste=1.06, levanta_sombra=0.05, joelho=0.50, rolagem=0.62,
        temp=0.05, tinta=0.02, saturacao=0.94, protege_pele=0.7,
        cor_sombra=(0.020, 0.006, -0.010), cor_alta=(-0.006, 0.002, 0.012)),
    "venice": Look(
        "Venice (emulação)",
        "mais peso: preto mais fundo e cor mais rica, para quem quer imagem "
        "de filme e tem luz boa.",
        ev=-0.05, contraste=1.20, levanta_sombra=-0.02, joelho=0.58, rolagem=0.55,
        temp=0.03, tinta=0.03, saturacao=1.10, protege_pele=0.6,
        cor_sombra=(0.030, 0.004, -0.016), cor_alta=(-0.010, 0.000, 0.016)),
    "fx3": Look(
        "FX3 natural (emulação)",
        "quase o que a câmera vê, só arrumado. Bom quando o assunto é a fala "
        "e não a foto.",
        ev=0.0, contraste=1.03, levanta_sombra=0.02, joelho=0.62, rolagem=0.5,
        temp=0.02, saturacao=1.0, protege_pele=0.5),
    "cine4": Look(
        "Cine4 plano (emulação)",
        "de propósito sem graça: guarda detalhe na alta e na sombra para ele "
        "aplicar o LUT dele depois, ou para gravar e tratar em outro dia.",
        ev=0.08, contraste=0.86, levanta_sombra=0.10, joelho=0.72, rolagem=0.35,
        saturacao=0.88, protege_pele=0.4),
    "noite": Look(
        "Noite / luz fraca",
        "para o quarto à noite com pouca luz: levanta a sombra sem deixar "
        "cinzento e evita o verde que a webcam barata puxa no escuro.",
        ev=0.30, contraste=1.10, levanta_sombra=0.14, joelho=0.46, rolagem=0.7,
        temp=0.06, tinta=0.04, saturacao=0.96, protege_pele=0.8,
        cor_sombra=(0.034, 0.000, -0.012), cor_alta=(-0.004, 0.002, 0.010)),
    # `rolagem=0` é o que faz o "cru" ser MESMO a identidade. Com a rolagem
    # padrão (0,5) ele ainda aplicava o joelho nas altas -- o teste pegou: o
    # look chamado "sem filtro" estava filtrando.
    "cru": Look("Cru (sem filtro)",
                "o que a webcam manda, sem eu tocar. Serve para comparar e "
                "para ele ver que o filtro está de fato fazendo algo.",
                rolagem=0.0),
}


# ─────────────────────────────────────────────────────────────────────────────
# AS CONTAS DO LOOK — em float, sobre qualquer array (h,w,3) ou (n,3), BGR 0..1
# ─────────────────────────────────────────────────────────────────────────────

# Peso de luminância BT.709 em ordem BGR (a imagem do OpenCV é BGR).
LUMA_BGR = np.array([0.0722, 0.7152, 0.2126], dtype=np.float32)


def luminancia(x: np.ndarray) -> np.ndarray:
    return (x * LUMA_BGR).sum(axis=-1, keepdims=True)


def _joelho(x: np.ndarray, ponto: float, forca: float) -> np.ndarray:
    """O que faz uma câmera de cinema não estourar a testa e a camisa branca.

    Abaixo do `ponto`, nada muda -- pele e meios ficam onde estão. Acima, a
    curva cede como um freio: aproxima de 1 sem nunca bater, então uma luz
    forte fica clara em vez de virar um bloco branco sem informação.
    """
    ponto = float(np.clip(ponto, 0.05, 0.98))
    forca = float(np.clip(forca, 0.0, 1.0))
    if forca <= 0:
        return np.clip(x, 0.0, None)
    sobra = np.maximum(x - ponto, 0.0)
    espaco = max(1e-4, 1.0 - ponto)
    # k alto = freio curto. Reinhard normalizado para casar em `ponto` com
    # derivada 1: contínuo, sem degrau visível na transição.
    k = 1.0 + 6.0 * forca
    comprimido = espaco * (k * sobra / espaco) / (1.0 + k * sobra / espaco)
    return np.where(x > ponto, ponto + comprimido, np.clip(x, 0.0, None))


def _contraste(x: np.ndarray, c: float, pivo: float) -> np.ndarray:
    """Contraste que gira no cinza médio, não no preto.

    Multiplicar a imagem inteira aumenta contraste E exposição juntas -- foi
    assim que eu deixaria o rosto dele escuro sem perceber. Girando no pivô,
    o cinza médio fica onde está e só o afastamento dele cresce.
    """
    if abs(c - 1.0) < 1e-6:
        return x
    return np.maximum(pivo + (x - pivo) * c, 0.0)


def _levanta_sombra(x: np.ndarray, q: float) -> np.ndarray:
    """Levanta (ou afunda) só o que é sombra. O `(1-x)³` é o que garante isso.

    Em x=0 o efeito é inteiro; em x=0,5 já caiu para 1/8; na alta é zero. Sem
    esse peso, "levantar sombra" lava a imagem toda e vira aquele cinza de
    vídeo de reunião.
    """
    if abs(q) < 1e-6:
        return x
    xs = np.clip(x, 0.0, 1.0)
    return np.maximum(x + q * (1.0 - xs) ** 3, 0.0)


def _ganhos_luz(temp: float, tinta: float) -> np.ndarray:
    """Temperatura e tinta como ganho por canal, em BGR.

    Não é conversão de corpo negro de verdade -- é a aproximação que os
    controles de câmera usam, e é o que responde igual ao que ele espera
    quando arrasta o cursor.
    """
    t = float(np.clip(temp, -1.0, 1.0))
    v = float(np.clip(tinta, -1.0, 1.0))
    b = 1.0 - 0.28 * t
    r = 1.0 + 0.28 * t
    g = 1.0 - 0.20 * v
    return np.array([b, g, r], dtype=np.float32)


def _mascara_pele(x: np.ndarray) -> np.ndarray:
    """Onde a cor PARECE pele, de 0 a 1. Serve para não saturar rosto.

    Pele em BGR tem vermelho acima de verde acima de azul, com distância
    moderada entre eles. Isto acerta pele de qualquer tom (o que muda entre
    tons é o brilho, não essa ordem) e recusa o vermelho puro de uma camisa.
    """
    b, g, r = x[..., 0:1], x[..., 1:2], x[..., 2:3]
    soma = np.maximum(r + g + b, 1e-5)
    rn, gn = r / soma, g / soma
    # mesma calibração medida do `ia_visual.mascara_pele`, inclusive a
    # exigência de cor -- sem ela, cinza neutro pontua 0,69 como pele e a
    # proteção de saturação passaria a proteger a parede
    d = ((rn - 0.425) / 0.058) ** 2 + ((gn - 0.335) / 0.062) ** 2
    m = np.exp(-0.5 * d)
    mx = np.maximum(np.maximum(b, g), r)
    mn = np.minimum(np.minimum(b, g), r)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    return (m * np.clip(sat / 0.09, 0.0, 1.0)).astype(np.float32)


def _saturacao(x: np.ndarray, s: float, protege: float) -> np.ndarray:
    if abs(s - 1.0) < 1e-6:
        return x
    luz = luminancia(x)
    fator = np.float32(s)
    if protege > 0:
        # na pele, puxa o fator de volta para 1: a cor da pele é a última
        # coisa que se quer exagerar, e é a primeira que denuncia filtro.
        m = _mascara_pele(x) * float(np.clip(protege, 0.0, 1.0))
        fator = 1.0 + (s - 1.0) * (1.0 - m)
    return np.maximum(luz + (x - luz) * fator, 0.0)


def _split_tone(x: np.ndarray, sombra, alta) -> np.ndarray:
    """Cor na sombra e cor na alta, separadas. É metade do 'look de cinema'.

    Sombra levemente azul + alta levemente quente é o contraste de cor que o
    olho lê como filme, mesmo quando o contraste de brilho é discreto.
    """
    s = np.asarray(sombra, dtype=np.float32)
    a = np.asarray(alta, dtype=np.float32)
    if not s.any() and not a.any():
        return x
    luz = np.clip(luminancia(x), 0.0, 1.0)
    peso_sombra = (1.0 - luz) ** 2
    peso_alta = luz ** 2
    return np.maximum(x + s * peso_sombra + a * peso_alta, 0.0)


def aplicar_look(x: np.ndarray, lk: Look) -> np.ndarray:
    """O look inteiro, em float 0..1 BGR. A ORDEM aqui é o resultado.

    Luz primeiro (exposição, branco), porque são propriedades da captura.
    Depois a resposta do sensor emulada (sombra, contraste, joelho). Depois a
    cor (saturação, split tone), que é gosto. Inverter isso -- saturar antes
    de comprimir a alta -- é o que deixa a testa rosa-choque quando a luz bate.
    """
    y = np.clip(x, 0.0, None).astype(np.float32, copy=True)
    y *= _ganhos_luz(lk.temp, lk.tinta)
    if abs(lk.ev) > 1e-6:
        y *= np.float32(2.0 ** lk.ev)
    y = _levanta_sombra(y, lk.levanta_sombra)
    y = _contraste(y, lk.contraste, lk.pivo)
    y = _joelho(y, lk.joelho, lk.rolagem)
    y = _saturacao(y, lk.saturacao, lk.protege_pele)
    y = _split_tone(y, lk.cor_sombra, lk.cor_alta)
    return np.clip(y, 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# .CUBE — o LUT dele vence o meu
# ─────────────────────────────────────────────────────────────────────────────

def carregar_cube(caminho: str | Path) -> Tuple[np.ndarray, int]:
    """Lê um LUT 3D .cube (Sony, DaVinci, qualquer um). Devolve (N,N,N,3) RGB.

    Recuso arquivo malformado com mensagem em português, porque a alternativa é
    o software abrir e transmitir com a cor errada sem ninguém entender por quê.
    """
    p = Path(caminho)
    texto = p.read_text(encoding="utf-8", errors="replace")
    n = 0
    dmin = np.zeros(3, dtype=np.float32)
    dmax = np.ones(3, dtype=np.float32)
    valores = []
    for linha in texto.splitlines():
        s = linha.strip()
        if not s or s.startswith("#"):
            continue
        alto = s.upper()
        if alto.startswith("LUT_3D_SIZE"):
            n = int(re.findall(r"\d+", s)[0])
            continue
        if alto.startswith("LUT_1D_SIZE"):
            raise ValueError(f"{p.name} é um LUT 1D; aqui preciso de LUT 3D")
        if alto.startswith("DOMAIN_MIN"):
            dmin = np.array([float(v) for v in s.split()[1:4]], dtype=np.float32)
            continue
        if alto.startswith("DOMAIN_MAX"):
            dmax = np.array([float(v) for v in s.split()[1:4]], dtype=np.float32)
            continue
        if alto.startswith(("TITLE", "LUT_IN", "LUT_OUT")):
            continue
        partes = s.split()
        if len(partes) >= 3:
            try:
                valores.append([float(partes[0]), float(partes[1]),
                                float(partes[2])])
            except ValueError:
                continue
    if n <= 1:
        raise ValueError(f"{p.name} não declara LUT_3D_SIZE")
    if len(valores) != n ** 3:
        raise ValueError(f"{p.name}: LUT_3D_SIZE diz {n} ({n**3} linhas) mas "
                         f"achei {len(valores)}")
    arr = np.asarray(valores, dtype=np.float32)
    # no .cube o VERMELHO varia mais rápido. Reordeno para [r,g,b] indexável.
    arr = arr.reshape(n, n, n, 3)          # [b][g][r] na ordem de leitura
    arr = np.transpose(arr, (2, 1, 0, 3))  # -> [r][g][b]
    if np.any(dmax != 1.0) or np.any(dmin != 0.0):
        arr = (arr - dmin) / np.maximum(dmax - dmin, 1e-6)
    return np.clip(arr, 0.0, 1.0), n


def _amostrar_cube(cube: np.ndarray, n: int, rgb: np.ndarray) -> np.ndarray:
    """Trilinear no LUT dele. Lento e correto -- roda só na assada, uma vez."""
    f = np.clip(rgb, 0.0, 1.0) * (n - 1)
    i0 = np.floor(f).astype(np.int32)
    i1 = np.minimum(i0 + 1, n - 1)
    d = (f - i0).astype(np.float32)
    saida = np.zeros(rgb.shape, dtype=np.float32)
    for br, wr in ((i0[..., 0], 1 - d[..., 0:1]), (i1[..., 0], d[..., 0:1])):
        for bg, wg in ((i0[..., 1], 1 - d[..., 1:2]), (i1[..., 1], d[..., 1:2])):
            for bb, wb in ((i0[..., 2], 1 - d[..., 2:3]), (i1[..., 2], d[..., 2:3])):
                saida += cube[br, bg, bb] * (wr * wg * wb)
    return saida


# ─────────────────────────────────────────────────────────────────────────────
# ASSAR A TABELA
# ─────────────────────────────────────────────────────────────────────────────

def _grade_identidade(n: int = N_TAB) -> np.ndarray:
    """Os n³ pontos de entrada, em BGR 0..1, na ordem do índice plano."""
    e = np.linspace(0.0, 1.0, n, dtype=np.float32)
    # índice = r*n² + g*n + b  =>  r é o eixo mais lento
    r, g, b = np.meshgrid(e, e, e, indexing="ij")
    return np.stack([b, g, r], axis=-1).reshape(-1, 3)


_IDENT_CACHE: Dict[int, np.ndarray] = {}


def identidade(n: int = N_TAB) -> np.ndarray:
    if n not in _IDENT_CACHE:
        _IDENT_CACHE[n] = _grade_identidade(n)
    return _IDENT_CACHE[n]


def assar(look: str = "s_cinetone", forca: float = 1.0,
          lut_arquivo: str = "", n: int = N_TAB) -> Tuple[np.ndarray, str]:
    """A tabela plana (n³,3) uint8 que a live vai usar. E o que ela é, em texto.

    `forca` mistura com a identidade AQUI, não por quadro: a força custa zero
    ao vivo. Mistura na tabela é matematicamente igual a misturar na saída,
    porque as duas pontas passam pelo mesmo pixel.
    """
    ent = identidade(n)
    aviso = ""

    if lut_arquivo and str(lut_arquivo).strip():
        try:
            cube, nc = carregar_cube(lut_arquivo)
            rgb = _amostrar_cube(cube, nc, ent[:, ::-1])   # BGR->RGB p/ o cube
            sai = rgb[:, ::-1]                              # e de volta
            aviso = f"LUT dele: {Path(lut_arquivo).name} ({nc}³)"
        except Exception as e:
            sai = aplicar_look(ent, LOOKS.get(look) or LOOKS["cru"])
            aviso = f"LUT recusado ({e}); usei {look}"
    else:
        lk = LOOKS.get(look)
        if lk is None:
            lk, look = LOOKS["cru"], "cru"
            aviso = "look desconhecido; sem filtro"
        sai = aplicar_look(ent, lk)
        aviso = aviso or lk.nome_na_tela

    f = float(np.clip(forca, 0.0, 1.0))
    if f < 1.0:
        sai = ent * (1.0 - f) + sai * f
    return (np.clip(sai, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), aviso


_DITHER: Dict[Tuple[int, int], np.ndarray] = {}


def _dither(h: int, w: int, passo: int) -> np.ndarray:
    """Ruído de ±meio degrau, sorteado uma vez por tamanho e reaproveitado."""
    chave = (h, w, passo)
    if chave not in _DITHER:
        rng = np.random.default_rng(11)
        _DITHER[chave] = rng.integers(0, passo, (h, w, 3), dtype=np.uint8)
        if len(_DITHER) > 4:
            _DITHER.pop(next(iter(_DITHER)))
    return _DITHER[chave]


_IDX: Dict[Tuple[int, bool], np.ndarray] = {}


def _tabela_indice(n: int, dither: bool) -> np.ndarray:
    """De 0..255 para o ponto de grade mais próximo, já descontando o dither."""
    chave = (n, dither)
    if chave not in _IDX:
        meio = (256.0 / n) / 2.0 if dither else 0.0
        x = np.arange(256, dtype=np.float32) - meio
        idx = np.clip(np.round(x * (n - 1) / 255.0), 0, n - 1)
        _IDX[chave] = idx.astype(np.uint8).reshape(1, 256)
    return _IDX[chave]


def aplicar_tabela(img: np.ndarray, tabela: np.ndarray, n: int = N_TAB,
                   dither: bool = True) -> np.ndarray:
    """O único custo de cor por quadro: um gather. 5,9 ms a 720p, medido.

    O DEGRAU QUE A TABELA CRIA, E POR QUE ELE PRECISA DE RUÍDO
    ─────────────────────────────────────────────────────────
    A tabela tem 64 níveis por canal e a imagem tem 256. Quantizar 256 em 64
    é dividir por 4 -- e num gradiente liso (parede, céu, a sombra na bochecha)
    isso vira uma escada de 4 níveis. Escada em gradiente é FAIXA, o defeito
    de compressão que todo mundo reconhece sem saber nomear, e ela aparece
    justamente nas áreas lisas onde o olho é mais sensível.

    O conserto é somar menos de um degrau de ruído ANTES de quantizar. Cada
    pixel passa a cair de um lado ou do outro da fronteira conforme o sorteio,
    e a média local reconstrói o valor certo: a escada vira granulado fino,
    que o olho lê como textura e não como defeito. É a mesma ideia do
    "dithering" de imagem de 8 bits, e custa uma soma.

    O ruído é sorteado UMA vez por tamanho de imagem, não por quadro -- ruído
    fixo no espaço é invisível; ruído novo a cada quadro cintilaria.
    """
    if TEM_CV and n in (32, 64):
        # O ÍNDICE NÃO PODE SER UM DESLOCAMENTO DE BITS. POR QUÊ:
        # `img >> 2` anda de 4 em 4, mas a grade de 64 pontos anda de
        # 255/63 = 4,048. A diferença é um ganho de +1,2% na imagem inteira.
        # Sem dithering ela ficava escondida, porque o truncamento perdia em
        # média 1,5 nível e os dois erros se cancelavam por coincidência --
        # e o dithering, ao consertar o truncamento, revelou o ganho como um
        # viés de +1,5 nível. Foi o teste de viés que expôs isso.
        #
        # A tabela abaixo faz a conta certa (arredonda para o ponto de grade
        # mais próximo) e ainda desconta o meio-degrau do dithering. Custa
        # uma `cv2.LUT`, 0,3 ms.
        passo = 256 // n
        base = cv2.add(img, _dither(img.shape[0], img.shape[1], passo)) \
            if dither else img
        q = cv2.LUT(base, _tabela_indice(n, dither))
    else:
        q = (img.astype(np.int32) * (n - 1)) // 255
    idx = (q[..., 2].astype(np.int32) * (n * n)
           + q[..., 1].astype(np.int32) * n
           + q[..., 0].astype(np.int32))
    return np.take(tabela, idx, axis=0)


# ─────────────────────────────────────────────────────────────────────────────
# O RESTO DO ACABAMENTO — por quadro, e cada um com seu cache
# ─────────────────────────────────────────────────────────────────────────────

def curva_correcao(ganho_b: float = 1.0, ganho_g: float = 1.0,
                   ganho_r: float = 1.0, ev: float = 0.0,
                   piso_preto: float = 0.0) -> np.ndarray:
    """A curva 1D que a IA reconstrói a cada quadro. 256 entradas, 0,3 ms.

    Devolve no formato (1,256,3) que o `cv2.LUT` quer para imagem de 3 canais.
    """
    x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    p = float(np.clip(piso_preto, 0.0, 0.4))
    if p > 0:
        x = np.clip((x - p) / max(1e-4, 1.0 - p), 0.0, 1.0)
    x = x * np.float32(2.0 ** ev)
    canais = [np.clip(x * g, 0.0, 1.0) for g in (ganho_b, ganho_g, ganho_r)]
    tab = (np.stack(canais, axis=-1) * 255.0 + 0.5).astype(np.uint8)
    return tab.reshape(1, 256, 3)


def misturar(frente: np.ndarray, fundo_: np.ndarray, mascara: np.ndarray
             ) -> np.ndarray:
    """`frente` onde a máscara é 1, `fundo_` onde é 0. Em 8 bits, de propósito.

    A versão em float32 disto custava 6,3 ms por quadro a 720p e aparecia
    duas vezes na cadeia (embelezamento e fundo): 12,6 ms só para misturar,
    de um orçamento de 33. Em 8 bits custa 2,0 ms, e medi o desvio contra a
    versão float: no máximo 2 níveis de 255. Dois níveis não se vê; 25
    quadros por segundo em vez de 16, sim.

    `mascara` pode vir float 0..1 (h,w) ou (h,w,1), ou já uint8.
    """
    m = mascara
    if m.dtype != np.uint8:
        m = np.clip(np.asarray(m, dtype=np.float32) * 255.0 + 0.5, 0, 255) \
            .astype(np.uint8)
    if m.ndim == 3:
        m = m[..., 0]
    if m.shape[:2] != frente.shape[:2]:
        m = cv2.resize(m, (frente.shape[1], frente.shape[0]),
                       interpolation=cv2.INTER_LINEAR)
    m3 = cv2.merge([m, m, m])
    return cv2.add(cv2.multiply(frente, m3, scale=1.0 / 255.0),
                   cv2.multiply(fundo_, cv2.bitwise_not(m3), scale=1.0 / 255.0))


class Acabamento:
    """Vinheta, grão, halação e nitidez — tudo em 8 bits, tudo com cache.

    A PRIMEIRA VERSÃO CUSTAVA 67,6 ms DAS QUATRO JUNTAS. O ERRO ERA O MESMO
    ─────────────────────────────────────────────────────────────────────
    Eu tinha escrito as quatro em float32 sobre a imagem cheia -- `astype`,
    multiplicação, `np.clip`, `astype` de volta, quatro vezes. É o mesmo erro
    que já tinha custado 240 ms no embelezamento, cometido de novo em outro
    arquivo. Anoto isso aqui porque é o padrão que se repete: em processamento
    de vídeo, quem escreve `astype(np.float32)` numa imagem inteira já perdeu.

    Agora cada uma é uma sequência de operações do OpenCV em 8 bits:

      vinheta   máscara uint8 no cache por tamanho, um `multiply`
      grão      ruído sorteado UMA vez; o peso por luminância vira uma tabela
                de 256 entradas aplicada no cinza
      halação   a fórmula do "screen" é  a + b*(255-a)/255, que são três
                operações do OpenCV e dá o resultado EXATO, não aproximado
      nitidez   já era um blur e um addWeighted
    """

    def __init__(self, semente: int = 7):
        self._vinheta: Dict[Tuple[int, int], np.ndarray] = {}
        self._ruido: Optional[np.ndarray] = None
        self._peso_grao: Optional[np.ndarray] = None
        self._rng = np.random.default_rng(semente)

    # ── vinheta ───────────────────────────────────────────────────────────
    def vinheta(self, h: int, w: int, forca: float) -> np.ndarray:
        """A máscara em uint8, no cache. Só refaz quando muda tamanho/força."""
        chave = (h, w, round(float(forca), 3))
        if chave not in self._vinheta:
            yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
            xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
            r2 = (xx * xx + yy * yy) / 2.0
            m = 1.0 - r2 * float(np.clip(forca, 0, 1))
            self._vinheta[chave] = np.clip(m * 255.0 + 0.5, 0, 255) \
                .astype(np.uint8)
            if len(self._vinheta) > 6:
                self._vinheta.pop(next(iter(self._vinheta)))
        return self._vinheta[chave]

    def aplicar_vinheta(self, img: np.ndarray, forca: float) -> np.ndarray:
        if forca <= 0.001 or not TEM_CV:
            return img
        h, w = img.shape[:2]
        m = self.vinheta(h, w, forca)
        return cv2.multiply(img, cv2.merge([m, m, m]), scale=1.0 / 255.0)

    # ── grão ──────────────────────────────────────────────────────────────
    def aplicar_grao(self, img: np.ndarray, forca: float) -> np.ndarray:
        """Grão de filme: mais visível no meio-tom que no preto e no branco.

        O ruído é sorteado uma vez num bloco maior que a imagem; por quadro eu
        só recorto uma janela dele num deslocamento aleatório. Gerar ruído novo
        a cada quadro custava mais que o grade de cor inteiro.
        """
        if forca <= 0.001 or not TEM_CV:
            return img
        h, w = img.shape[:2]
        if (self._ruido is None or self._ruido.shape[0] < h + 16
                or self._ruido.shape[1] < w + 16):
            bruto = self._rng.normal(0.0, 1.0, (h + 16, w + 16))
            self._ruido = np.clip(bruto * 40.0 + 128.0, 0, 255).astype(np.uint8)
        if self._peso_grao is None:
            x = np.arange(256, dtype=np.float32) / 255.0
            # 4*l*(1-l): 0 no preto, 0 no branco, 1 no meio-tom
            self._peso_grao = np.clip(4.0 * x * (1.0 - x) * 255.0, 0, 255) \
                .astype(np.uint8).reshape(1, 256)
        dy = int(self._rng.integers(0, 16))
        dx = int(self._rng.integers(0, 16))
        n = self._ruido[dy:dy + h, dx:dx + w]

        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        peso = cv2.LUT(cinza, self._peso_grao)
        # (n - 128) é o grão com sinal; multiplico pelo peso e pela força
        amp = float(np.clip(forca, 0, 1)) * 14.0 / 128.0
        g = cv2.multiply(cv2.subtract(n, 128, dtype=cv2.CV_16S),
                         peso.astype(np.int16), scale=amp / 255.0,
                         dtype=cv2.CV_16S)
        g3 = cv2.merge([g, g, g])
        return cv2.add(img, g3, dtype=cv2.CV_8U)

    # ── halação ───────────────────────────────────────────────────────────
    def aplicar_halacao(self, img: np.ndarray, forca: float) -> np.ndarray:
        """O brilho que sangra de uma luz forte. Uma lente de vidro faz isso.

        Sem ele, LED em webcam fica com borda de serra. Com ele, a luz tem
        halo -- e é meio caminho para a imagem não parecer webcam.
        """
        if forca <= 0.001 or not TEM_CV:
            return img
        h, w = img.shape[:2]
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # só o que passa de 205 vira halo; abaixo disso é imagem, não luz
        alta = cv2.threshold(cinza, 205, 255, cv2.THRESH_TOZERO)[1]
        if int(alta.max()) <= 205:
            return img                     # não há alta nenhuma: não gasto blur
        pq = cv2.resize(alta, (max(8, w // 4), max(8, h // 4)),
                        interpolation=cv2.INTER_AREA)
        # O alcance do halo é proporcional ao tamanho da imagem, e generoso:
        # com o sigma anterior (w/260) o brilho morria em 8 px e não parecia
        # lente nenhuma -- parecia uma borda mal feita. Halação de verdade se
        # espalha por dezenas de pixels. Como isto roda em 1/4 de resolução,
        # w/120 aqui equivale a ~43 px reais numa imagem de 1280.
        pq = cv2.GaussianBlur(pq, (0, 0), sigmaX=max(2.0, w / 120.0))
        halo = cv2.resize(pq, (w, h), interpolation=cv2.INTER_LINEAR)
        g = float(np.clip(forca, 0, 1)) * 0.75
        # halo levemente quente, em BGR
        canais = [cv2.multiply(halo, 1.0, scale=k * g)
                  for k in (0.75, 0.88, 1.0)]
        halo3 = cv2.merge(canais)
        # "screen" exato:  a + b*(255-a)/255  -- clareia sem estourar
        return cv2.add(img, cv2.multiply(halo3, cv2.bitwise_not(img),
                                         scale=1.0 / 255.0))

    @staticmethod
    def aplicar_nitidez(img: np.ndarray, forca: float) -> np.ndarray:
        """Máscara de desfoque. Por último, sempre.

        Antes do grade, a nitidez cresceria junto com o contraste e viraria
        aquela borda branca de televisão dos anos 2000.
        """
        if forca <= 0.001 or not TEM_CV:
            return img
        borrado = cv2.GaussianBlur(img, (0, 0), sigmaX=1.1)
        f = 1.0 + float(np.clip(forca, 0, 1)) * 1.3
        return cv2.addWeighted(img, f, borrado, 1.0 - f, 0)
