# -*- coding: utf-8 -*-
"""
Os filtros: embelezamento, cor, nitidez e os looks prontos.

O QUE É "EMBELEZAMENTO" AQUI
---------------------------
Não é deformar rosto. É o que uma boa luz faria: uniformizar a pele sem apagar
os traços. A conta tem três partes, e nenhuma delas mexe na geometria da cara:

1. Uma máscara de pele por crominância (Cr/Cb), suave nas bordas. Só o que é
   pele entra na suavização — parede, cabelo, roupa e olhos ficam de fora.
2. `filtro_guiado` alisa dentro dessa máscara. Ele preserva borda por
   construção, então cílio, sobrancelha e canto de boca continuam nítidos.
3. Uma parte do detalhe original volta somando o resíduo com peso. Sem esse
   passo, mesmo o filtro guiado no talo dá aspecto de plástico. Com ele, a pele
   fica lisa e a textura fina continua lá.

A força vai de 0 a 100 e é mistura linear com o quadro original: em 0 o quadro
sai byte a byte igual ao que entrou. Isso é testado.

POR QUE A MÁSCARA DE PELE POR CROMINÂNCIA
-----------------------------------------
Porque funciona em qualquer tom de pele e não custa quase nada. O intervalo
clássico de Cr/Cb separa pele de não-pele pela COR, não pelo brilho — que é
justamente o que varia entre tons de pele claros e escuros. Um limiar por
luminância excluiria pele escura; este não exclui.

O ORÇAMENTO DE 33 MILISSEGUNDOS
-------------------------------
A 30 fps, o quadro inteiro — captura, filtro, fundo, encoder — tem 33 ms. Um
quadro 720p em float32 tem 11 MB; cada operação ponto a ponto sobre ele lê e
escreve umas três vezes isso. Vinte operações assim e a live está em 8 fps.

Por isso este módulo não aplica efeito por efeito. Ele COMPILA os ajustes:

* Brilho, contraste, temperatura e a curva do look são todos funções de um
  canal só. Todas juntas viram UMA tabela de 256 entradas por canal, montada
  quando o slider muda e aplicada com um `cv2.LUT` por quadro. Dez efeitos
  empilhados custam o mesmo que um.
* A saturação e a tinta do look dependem da luminância, então sobram como duas
  passadas em 8 bits — baratas.
* O embelezamento colapsa em `quadro * A + B`, com `A` e `B` calculados em 1/4
  da resolução (máscara de pele inclusive) e ampliados. Duas passadas em escala
  cheia para tudo.
* A vinheta é a mesma matriz sempre; fica em cache por resolução.

O resultado é ~10 passadas por quadro em vez de ~60, sem trocar a qualidade:
tabela de 256 entradas é exata para operação ponto a ponto em 8 bits.
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

LOOKS = ("nenhum", "natural", "estudio", "quente", "frio", "cinema", "vintage", "pb")


@dataclass
class Ajustes:
    """Tudo o que o painel controla. Valores em escala humana, não em float."""
    look: str = "natural"
    intensidade_look: int = 100      # 0..100 — mistura do look com o quadro cru
    embelezamento: int = 35          # 0..100 — suavização de pele
    uniformizar_pele: int = 25       # 0..100 — tira mancha de tom, mantém sombra
    brilho: int = 0                  # -100..100
    contraste: int = 0               # -100..100
    saturacao: int = 0               # -100..100
    temperatura: int = 0             # -100 (frio/azul) .. 100 (quente/âmbar)
    nitidez: int = 20                # 0..100
    vinheta: int = 0                 # 0..100
    espelhar: bool = True            # webcam espelhada é o que todo mundo espera

    def como_dicionario(self) -> Dict:
        return asdict(self)

    @staticmethod
    def de_dicionario(d: Optional[Dict]) -> "Ajustes":
        base = Ajustes()
        for k, v in dict(d or {}).items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base.validar()

    def validar(self) -> "Ajustes":
        """Prende cada valor no intervalo legal. Slider de painel escorrega."""
        def presa(v, lo, hi, padrao=0):
            try:
                return int(max(lo, min(hi, int(v))))
            except Exception:
                return padrao
        self.look = self.look if self.look in LOOKS else "natural"
        self.intensidade_look = presa(self.intensidade_look, 0, 100, 100)
        self.embelezamento = presa(self.embelezamento, 0, 100, 0)
        self.uniformizar_pele = presa(self.uniformizar_pele, 0, 100, 0)
        self.brilho = presa(self.brilho, -100, 100)
        self.contraste = presa(self.contraste, -100, 100)
        self.saturacao = presa(self.saturacao, -100, 100)
        self.temperatura = presa(self.temperatura, -100, 100)
        self.nitidez = presa(self.nitidez, 0, 100, 0)
        self.vinheta = presa(self.vinheta, 0, 100, 0)
        self.espelhar = bool(self.espelhar)
        return self

    def chave(self) -> Tuple:
        """Identidade dos ajustes — o cache das tabelas se apoia nisto."""
        d = self.como_dicionario()
        return tuple(sorted((k, v) for k, v in d.items()))


# ----------------------------------------------------------------------------
# máscara de pele
# ----------------------------------------------------------------------------
def _suave_entre(x: np.ndarray, baixo: float, alto: float, margem: float) -> np.ndarray:
    """Pertinência suave ao intervalo [baixo, alto], com transição `margem`.

    Limiar duro produziria borda serrilhada na máscara de pele, e a suavização
    apareceria como mancha de contorno duro no rosto quando a pessoa se move.
    """
    sobe = np.clip((x - (baixo - margem)) / max(1e-6, margem), 0.0, 1.0)
    desce = np.clip(((alto + margem) - x) / max(1e-6, margem), 0.0, 1.0)
    return np.minimum(sobe, desce)


def mascara_pele(quadro: np.ndarray) -> np.ndarray:
    """Onde há pele, em 0..1. Entrada BGR, saída altura × largura."""
    a = IMG.para_float(quadro)
    b, g, r = a[..., 0], a[..., 1], a[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cr = (r - y) * 0.713 + 0.5
    cb = (b - y) * 0.564 + 0.5

    # intervalo clássico de pele em Cr/Cb (133..173 e 77..127 em escala 0..255)
    m = _suave_entre(cr, 133 / 255, 173 / 255, 12 / 255)
    m *= _suave_entre(cb, 77 / 255, 127 / 255, 12 / 255)
    # sombra profunda não é pele confiável: a crominância ali é ruído puro
    m *= np.clip((y - 0.08) / 0.12, 0.0, 1.0)
    return IMG.suavizar_mascara(m, raio=4)


# ----------------------------------------------------------------------------
# embelezamento
# ----------------------------------------------------------------------------
ESCALA_PELE = 4          # a análise de pele roda em 1/4 da resolução


def coeficientes_embelezamento(quadro: np.ndarray, forca: int, uniformizar: int = 0,
                               escala: int = ESCALA_PELE
                               ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Devolve (A, B) tais que `quadro*A + B` é o quadro embelezado.

    TODA a parte cara mora aqui, em 1/4 da resolução: máscara de pele, filtro
    guiado e a correção de tom. O que sai são dois mapas suaves que, ampliados,
    fazem o trabalho em escala cheia com duas operações.

    Isso é legítimo porque nenhum dos três é detalhe fino: a máscara de pele é
    borrada de propósito, e os coeficientes do filtro guiado variam devagar no
    espaço — é a mesma premissa do *fast guided filter*. Devolve None quando não
    há nada a fazer, e aí o chamador nem toca no quadro.
    """
    forca = max(0, min(100, int(forca)))
    uniformizar = max(0, min(100, int(uniformizar)))
    if forca == 0 and uniformizar == 0:
        return None

    cheio = IMG.para_float(quadro)
    alt, larg = cheio.shape[:2]
    s = max(1, int(escala))
    peq = IMG.redimensionar(cheio, max(8, larg // s), max(8, alt // s)) if s > 1 else cheio

    pele = mascara_pele(peq)[:, :, None]
    f = forca / 100.0

    # filtro guiado direto na escala pequena — já estamos reduzidos
    raio = max(2, 8 // s)
    media_i = IMG.media_caixa(peq, raio)
    variancia = np.maximum(IMG.media_caixa(peq * peq, raio) - media_i * media_i, 0.0)
    ga = variancia / (variancia + (0.004 + 0.020 * f))
    gb = media_i - ga * media_i
    ga = IMG.media_caixa(ga, raio)
    gb = IMG.media_caixa(gb, raio)

    # peso do alisamento: 0,75 é quanto do resíduo de detalhe fica de fora da
    # suavização — o que impede o rosto de virar cera na força máxima
    k = pele * (0.75 * f)
    A = 1.0 - k + ga * k
    B = gb * k

    if uniformizar:
        # Iguala o TOM sem tocar no brilho: separa cor de luminância, puxa a cor
        # para a média local larga e devolve. A sombra que dá volume ao rosto
        # fica; a mancha de cor sai. A correção é de baixa frequência por
        # natureza, então calculá-la aqui embaixo não perde nada visível — o
        # encoder ainda vai subamostrar crominância em 4:2:0 de qualquer jeito.
        u = uniformizar / 100.0
        aplicado = peq * A + B
        lum = IMG.luminancia(aplicado)[:, :, None]
        cor = aplicado - lum
        largo = max(3, int(min(peq.shape[:2]) * 0.05))
        correcao = (IMG.media_caixa(cor, largo) - cor) * (pele * u * 0.6)
        B = B + correcao

    # o fator 255 entra aqui embaixo, onde custa 1/16 do preco: quem aplica
    # recebe B ja na escala de 8 bits do quadro
    B = B * 255.0
    if s > 1:
        A = IMG.redimensionar(A, larg, alt)
        B = IMG.redimensionar(B, larg, alt)
    return A, B


def embelezar(quadro: np.ndarray, forca: int, uniformizar: int = 0) -> np.ndarray:
    """Suaviza a pele preservando os traços. `forca` e `uniformizar` de 0 a 100."""
    coef = coeficientes_embelezamento(quadro, forca, uniformizar)
    a = IMG.para_float(quadro)
    if coef is None:
        return a
    A, B = coef
    return np.clip(a * A + B / 255.0, 0.0, 1.0)


# ----------------------------------------------------------------------------
# a compilação dos ajustes de cor
# ----------------------------------------------------------------------------
def _identidade() -> np.ndarray:
    """Tabela neutra: 256 níveis × 3 canais, em 0..1."""
    v = np.arange(256, dtype=np.float32) / 255.0
    return np.repeat(v[:, None], 3, axis=1)


# Cada look é: o que faz com a curva de cada canal, quanto mexe na saturação, e
# uma tinta opcional que depende da luminância. Tudo o que cabe nessas três
# coisas roda em tempo real; nada mais é aceito aqui.
def _curva_do_look(nome: str, t: np.ndarray) -> np.ndarray:
    """Aplica a curva do look sobre a tabela `t` (256×3, em 0..1), canais BGR."""
    if nome == "natural":
        t = (t - 0.5) * 1.064 + 0.5 + 0.0105
        return t * np.array([1.0 - 0.0144, 1.0, 1.0 + 0.0144], np.float32)
    if nome == "estudio":
        return (t - 0.5) * 1.112 + 0.5 + 0.035
    if nome == "quente":
        return t * np.array([1.0 - 0.063, 1.0, 1.0 + 0.063], np.float32)
    if nome == "frio":
        return t * np.array([1.0 + 0.063, 1.0, 1.0 - 0.063], np.float32)
    if nome == "cinema":
        return (t - 0.5) * 1.12 + 0.5
    if nome == "vintage":
        # preto levantado e ganho sépia por canal: ar de filme velho
        return (t * 0.92 + 0.06) * np.array([0.88, 0.95, 1.05], np.float32)
    if nome == "pb":
        return (t - 0.5) * 1.15 + 0.5
    return t


_SAT_DO_LOOK = {"natural": 8, "estudio": 6, "quente": 12, "frio": 4,
                "cinema": -10, "vintage": -55, "pb": -100, "nenhum": 0}


def _tinta_do_look(nome: str, k: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Tinta por luminância, separada em (soma, subtração), 256 × 3 em 8 bits."""
    if nome != "cinema" or k <= 0:
        return None
    v = np.arange(256, dtype=np.float32) / 255.0
    sombra = np.clip(1.0 - v * 2.0, 0.0, 1.0)[:, None]
    alta = np.clip((v - 0.5) * 2.0, 0.0, 1.0)[:, None]
    tinta = (np.array([0.10, 0.05, -0.04], np.float32) * sombra
             + np.array([-0.06, 0.01, 0.09], np.float32) * alta) * k * 255.0
    mais = np.clip(tinta, 0, 255).astype(np.uint8)
    menos = np.clip(-tinta, 0, 255).astype(np.uint8)
    return mais, menos


class _Compilado:
    """Os ajustes de cor reduzidos ao que custa pouco por quadro."""

    __slots__ = ("tabela", "saturacao", "tinta", "neutro")

    def __init__(self, aj: Ajustes):
        t = _identidade()

        # 1) sliders manuais de brilho, contraste e temperatura
        if aj.brilho:
            t = t + (aj.brilho / 100.0) * 0.35
        if aj.contraste:
            t = (t - 0.5) * (1.0 + (aj.contraste / 100.0) * 0.8) + 0.5
        if aj.temperatura:
            x = aj.temperatura / 100.0
            t = t * np.array([1.0 - 0.18 * x, 1.0, 1.0 + 0.18 * x], np.float32)

        # 2) curva do look, misturada com a identidade pela intensidade
        k = (aj.intensidade_look / 100.0) if aj.look != "nenhum" else 0.0
        if k > 0:
            t = t + (_curva_do_look(aj.look, t) - t) * k

        self.tabela = np.clip(t * 255.0 + 0.5, 0, 255).astype(np.uint8)

        # A saturação do look SOMA com a do slider, e a soma precisa de piso.
        # Em -100 a cor some por completo (é o cinza); abaixo disso o fator fica
        # negativo e a conta passa a INVERTER as cores em vez de tirá-las. O look
        # "pb" já vale -100 sozinho, então bastava a pessoa arrastar o slider de
        # saturação para o fim para a imagem sair em negativo.
        self.saturacao = max(-100.0, min(200.0,
                                         aj.saturacao + _SAT_DO_LOOK.get(aj.look, 0) * k))
        self.tinta = _tinta_do_look(aj.look, k)
        self.neutro = (
            bool(np.array_equal(self.tabela, np.clip(_identidade() * 255.0 + 0.5, 0, 255).astype(np.uint8)))
            and abs(self.saturacao) < 1e-9 and self.tinta is None
        )


_cache_compilado: Dict[Tuple, _Compilado] = {}
_cache_vinheta: Dict[Tuple, np.ndarray] = {}


def compilar(aj: Ajustes) -> _Compilado:
    """Compila (e guarda) as tabelas de cor destes ajustes."""
    chave = aj.chave()
    pronto = _cache_compilado.get(chave)
    if pronto is None:
        pronto = _Compilado(aj)
        if len(_cache_compilado) > 64:       # o painel gera muita variação
            _cache_compilado.clear()
        _cache_compilado[chave] = pronto
    return pronto


# ----------------------------------------------------------------------------
# as passadas em 8 bits
# ----------------------------------------------------------------------------
def _aplicar_tabela(q: np.ndarray, tabela: np.ndarray) -> np.ndarray:
    if cv2 is not None:
        return cv2.LUT(q, tabela.reshape(1, 256, 3))
    out = np.empty_like(q)
    for c in range(3):
        out[..., c] = tabela[:, c][q[..., c]]
    return out


def _cinza(q: np.ndarray) -> np.ndarray:
    if cv2 is not None:
        return cv2.cvtColor(q, cv2.COLOR_BGR2GRAY)
    lum = 0.114 * q[..., 0] + 0.587 * q[..., 1] + 0.299 * q[..., 2]
    return np.clip(lum + 0.5, 0, 255).astype(np.uint8)


def _aplicar_saturacao(q: np.ndarray, saturacao: float) -> np.ndarray:
    if abs(saturacao) < 1e-9:
        return q
    s = 1.0 + saturacao / 100.0
    cinza = _cinza(q)
    if cv2 is not None:
        cinza3 = cv2.cvtColor(cinza, cv2.COLOR_GRAY2BGR)
        return cv2.addWeighted(q, s, cinza3, 1.0 - s, 0.0)
    alvo = cinza[:, :, None].astype(np.int16)
    return np.clip(alvo + (q.astype(np.int16) - alvo) * s, 0, 255).astype(np.uint8)


def _aplicar_tinta(q: np.ndarray, tinta: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """Soma a tinta clara e subtrai a escura, as duas em 8 bits.

    Guardar a tinta com sinal obrigaria o quadro inteiro a passar por int16 —
    duas passadas de 5,5 MB só para poder somar um número negativo. Separada em
    parte positiva e parte negativa, `cv2.add` e `cv2.subtract` fazem o mesmo
    com saturação nativa, em 8 bits.
    """
    mais, menos = tinta
    cinza = _cinza(q)
    if cv2 is not None:
        # `mais[cinza]` parece o caminho óbvio, e é o mais caro da cadeia
        # inteira: indexação avançada em 2,7 milhões de posições é acesso
        # aleatório à memória, pixel por pixel. Repetir o cinza em três canais e
        # passar por `cv2.LUT` faz exatamente a mesma busca de forma sequencial.
        cinza3 = cv2.cvtColor(cinza, cv2.COLOR_GRAY2BGR)
        return cv2.subtract(cv2.add(q, cv2.LUT(cinza3, mais.reshape(1, 256, 3))),
                            cv2.LUT(cinza3, menos.reshape(1, 256, 3)))
    soma = q.astype(np.int16) + mais[cinza] - menos[cinza]
    return np.clip(soma, 0, 255).astype(np.uint8)


def aplicar_nitidez(q: np.ndarray, nitidez: int,
                    mascara: Optional[np.ndarray] = None) -> np.ndarray:
    """Máscara de contraste (unsharp). `mascara` limita o realce à pessoa.

    Sem essa restrição, a nitidez realçaria o fundo que acabamos de desfocar de
    propósito — e granulado no fundo borrado é o que mais chama atenção.
    """
    if not nitidez:
        return q
    peso = (nitidez / 100.0) * 1.2
    if cv2 is not None:
        borrado = cv2.GaussianBlur(q, (0, 0), 1.5, borderType=cv2.BORDER_REFLECT)
    else:
        borrado = IMG.para_bytes(IMG.desfocar(q, raio=3))
    if mascara is None:
        return cv2.addWeighted(q, 1.0 + peso, borrado, -peso, 0.0) if cv2 is not None \
            else np.clip(q.astype(np.float32) * (1 + peso) - borrado * peso, 0, 255).astype(np.uint8)
    m = np.clip(np.asarray(mascara, np.float32), 0.0, 1.0)
    if m.ndim == 3:
        m = m[:, :, 0]
    if m.shape[:2] != q.shape[:2]:
        m = IMG.redimensionar(m, q.shape[1], q.shape[0])
        if m.ndim == 3:
            m = m[:, :, 0]
    if cv2 is not None:
        # o mesmo realce, mas cada etapa é uma passada sequencial do OpenCV em
        # vez da corrente `astype` -> multiplicar -> somar -> `clip` -> `astype`
        # do NumPy, que materializa quatro imagens de 11 MB pelo caminho
        peso_bgr = cv2.cvtColor(np.ascontiguousarray(m * peso, np.float32),
                                cv2.COLOR_GRAY2BGR)
        realce = cv2.multiply(cv2.subtract(q, borrado, dtype=cv2.CV_32F), peso_bgr)
        return cv2.add(q, realce, dtype=cv2.CV_8U)
    realce = (q.astype(np.float32) - borrado) * (peso * m[:, :, None])
    return np.clip(q + realce, 0, 255).astype(np.uint8)


def mapa_vinheta(alt: int, larg: int, vinheta: int) -> np.ndarray:
    """A queda de luz das bordas. Mesma matriz sempre — fica em cache.

    Montar a grade e a raiz quadrada em escala cheia custava mais que o próprio
    efeito, todo quadro, para um resultado que nunca muda.
    """
    chave = (int(alt), int(larg), int(vinheta))
    pronto = _cache_vinheta.get(chave)
    if pronto is None:
        y = np.linspace(-1.0, 1.0, alt, dtype=np.float32)[:, None]
        x = np.linspace(-1.0, 1.0, larg, dtype=np.float32)[None, :]
        raio = np.sqrt(x * x + y * y) / np.sqrt(2.0)
        queda = 1.0 - (vinheta / 100.0) * np.clip((raio - 0.35) / 0.65, 0.0, 1.0) ** 1.6
        pronto = queda[:, :, None].astype(np.float32)
        if len(_cache_vinheta) > 8:
            _cache_vinheta.clear()
        _cache_vinheta[chave] = pronto
    return pronto


def aplicar_vinheta(q: np.ndarray, vinheta: int) -> np.ndarray:
    if not vinheta:
        return q
    mapa = mapa_vinheta(q.shape[0], q.shape[1], vinheta)
    return np.clip(q * mapa, 0, 255).astype(np.uint8)


def espelhar_quadro(q: np.ndarray) -> np.ndarray:
    if cv2 is not None:
        return cv2.flip(q, 1)
    return np.ascontiguousarray(q[:, ::-1])


# ----------------------------------------------------------------------------
# a cadeia inteira
# ----------------------------------------------------------------------------
def aplicar(quadro: np.ndarray, ajustes: Ajustes,
            mascara_pessoa: Optional[np.ndarray] = None) -> np.ndarray:
    """Roda a cadeia na ordem certa e devolve uint8 BGR pronto para transmitir.

    A ORDEM NÃO É ARBITRÁRIA:
    espelho -> pele -> cor -> saturação -> tinta -> nitidez -> vinheta.

    Pele antes da cor, porque suavizar depois de aumentar contraste amplifica o
    ruído que o contraste criou. Nitidez depois da cor, porque realçar antes e
    esticar contraste depois estoura o halo. Vinheta por último, porque é um
    escurecimento de borda e nada deveria ser corrigido em cima dele.
    """
    aj = ajustes.validar() if isinstance(ajustes, Ajustes) else Ajustes.de_dicionario(ajustes)
    q = IMG.para_bytes(quadro)

    if aj.espelhar:
        q = espelhar_quadro(q)
        if mascara_pessoa is not None:
            mascara_pessoa = np.ascontiguousarray(np.asarray(mascara_pessoa)[:, ::-1])

    coef = coeficientes_embelezamento(q, aj.embelezamento, aj.uniformizar_pele)
    if coef is not None:
        A, B = coef
        if cv2 is not None:
            # multiply e add de uma passada cada, com a conversao para 8 bits e
            # a saturacao ja dentro — a versao em numpy encadeia clip e astype
            # sobre 11 MB de float duas vezes a mais
            q = cv2.add(cv2.multiply(q, A, dtype=cv2.CV_32F), B, dtype=cv2.CV_8U)
        else:
            q = np.clip(q * A + B, 0, 255).astype(np.uint8)

    comp = compilar(aj)
    if not comp.neutro:
        q = _aplicar_tabela(q, comp.tabela)
        q = _aplicar_saturacao(q, comp.saturacao)
        if comp.tinta is not None:
            q = _aplicar_tinta(q, comp.tinta)

    q = aplicar_nitidez(q, aj.nitidez, mascara_pessoa)
    q = aplicar_vinheta(q, aj.vinheta)
    return q
