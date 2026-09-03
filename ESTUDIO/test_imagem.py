# -*- coding: utf-8 -*-
"""A cadeia de imagem: máscara de pele, look, embelezamento, fundo.

CADA TESTE AQUI NASCEU DE UM DEFEITO QUE EU COMETI E MEDI
─────────────────────────────────────────────────────────
Não são testes escritos "por garantia". São a prova de defeitos que
aconteceram durante a construção deste software:

  · a máscara de pele dava 0,69 para CINZA NEUTRO, e o embelezamento tratava
    parede clara como rosto (23 ms viraram 43)
  · a tabela do retoque era montada com um reshape que EMBARALHAVA os canais,
    e a textura da pele AUMENTAVA em vez de diminuir
  · a mancha não saía, porque o filtro bilateral preserva bordas e mancha é
    uma borda -- ela nunca chegava na camada que seria tratada
  · a mediana em meia resolução não enxergava a mancha (0 níveis); só em 1/4

    python test_imagem.py
"""
from __future__ import annotations
import sys
import numpy as np

from _base_teste import checa, resumo

try:
    import cv2
except Exception:
    print("OpenCV não instalado — este teste precisa dele")
    sys.exit(1)

import beleza as BEL
import fundo as FUN
import ia_visual as IA
import visual as V


def detalhe(img, x, y, lado=70, sigma=1.5):
    """Quanta textura fina existe num pedaço. É a medida de 'virou plástico'."""
    z = img[y:y + lado, x:x + lado].astype(np.float32)
    return float(np.abs(z - cv2.GaussianBlur(z, (0, 0), sigma)).mean())


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a máscara de pele, tom por tom")
AMOSTRAS_PELE = [("muito clara", (200, 215, 235)), ("clara", (150, 175, 205)),
                 ("média", (110, 140, 175)), ("morena", (75, 100, 140)),
                 ("escura", (45, 60, 90)), ("muito escura", (30, 38, 58))]
NAO_PELE = [("cinza neutro", (128, 128, 128)), ("cinza claro", (190, 190, 190)),
            ("parede branca", (230, 232, 235)), ("camisa vermelha", (40, 40, 200)),
            ("planta verde", (60, 160, 60)), ("céu azul", (200, 150, 90))]

for nome, cor in AMOSTRAS_PELE:
    v = float(IA.mascara_pele(np.full((8, 8, 3), cor, np.uint8)).mean())
    checa(v >= 0.5, f"pele {nome} reconhecida (>=0,50)", f"deu {v:.2f}")
for nome, cor in NAO_PELE:
    v = float(IA.mascara_pele(np.full((8, 8, 3), cor, np.uint8)).mean())
    checa(v <= 0.15, f"{nome} NÃO é pele (<=0,15)", f"deu {v:.2f}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] o look e a tabela 64³")
tab_cru, nome_cru = V.assar("cru", 1.0)
ident = (V.identidade() * 255 + 0.5).astype(np.uint8)
checa(int(np.abs(tab_cru.astype(int) - ident.astype(int)).max()) <= 1,
      "o look 'cru' é a identidade (não mexe em nada)")

tab, nome = V.assar("s_cinetone", 1.0)
checa(tab.shape == (V.N_TAB ** 3, 3) and tab.dtype == np.uint8,
      "a tabela assada tem o formato certo", str(tab.shape))
tab0, _ = V.assar("venice", 0.0)
checa(int(np.abs(tab0.astype(int) - ident.astype(int)).max()) <= 1,
      "força 0 vira identidade (a força é assada, não custa por quadro)")

img = np.random.default_rng(4).integers(0, 256, (64, 96, 3), dtype=np.uint8)
checa(int(np.abs(V.aplicar_tabela(img, tab_cru, dither=False).astype(int)
                 - img.astype(int)).max()) <= 4,
      "a tabela identidade devolve a imagem dentro do degrau da grade (4)")

# FAIXA (banding): um gradiente liso não pode virar escada
rampa = np.tile(np.linspace(0, 255, 256).astype(np.uint8), (32, 1))
rampa = cv2.merge([rampa, rampa, rampa])
sem = V.aplicar_tabela(rampa, tab_cru, dither=False)
com = V.aplicar_tabela(rampa, tab_cru, dither=True)
def maior_degrau(a):
    linha = a[16, :, 1].astype(np.int32)
    return int(np.abs(np.diff(linha)).max())
checa(maior_degrau(sem) >= 4,
      "sem dithering a grade de 64 níveis FAZ escada de 4 (é o defeito)",
      f"degrau {maior_degrau(sem)}")
checa(maior_degrau(com) <= maior_degrau(sem),
      "com dithering o degrau não é maior", f"{maior_degrau(com)}")
# O que o dithering compra é a média SEM VIÉS. O desvio que sobra é o próprio
# ruído do dithering e não deve ser cobrado como erro -- a primeira versão
# deste teste media |erro| com desfoque pequeno e reprovava o ruído, não o
# viés. Aqui separo as duas coisas.
suave = cv2.GaussianBlur(com.astype(np.float32), (0, 0), 10.0)[16, :, 1]
cru_s = cv2.GaussianBlur(rampa.astype(np.float32), (0, 0), 10.0)[16, :, 1]
erro = suave[30:226] - cru_s[30:226]
checa(abs(float(erro.mean())) < 0.7,
      "o dithering não desloca a imagem (viés perto de zero)",
      f"viés {float(erro.mean()):+.2f}")
checa(float(np.abs(erro).mean()) < 2.0,
      "e o que sobra é ruído fino, não faixa",
      f"desvio médio {float(np.abs(erro).mean()):.2f}")

escuro = np.full((32, 32, 3), 30, np.uint8)
claro = np.full((32, 32, 3), 240, np.uint8)
tv, _ = V.assar("venice", 1.0)
tc, _ = V.assar("cine4", 1.0)
con_v = float(V.aplicar_tabela(claro, tv).mean() - V.aplicar_tabela(escuro, tv).mean())
con_c = float(V.aplicar_tabela(claro, tc).mean() - V.aplicar_tabela(escuro, tc).mean())
checa(con_v > con_c,
      "Venice tem mais contraste que o Cine4 plano (é a diferença entre eles)",
      f"venice {con_v:.0f} vs cine4 {con_c:.0f}")

alta = np.full((16, 16, 3), 250, np.uint8)
checa(int(V.aplicar_tabela(alta, tab).max()) <= 255,
      "o joelho segura a alta sem estourar o inteiro")

try:
    V.carregar_cube(__file__)
    ok = False
except Exception:
    ok = True
checa(ok, "um .cube inválido é recusado com mensagem, não aceito calado")
_, aviso = V.assar("s_cinetone", 1.0, lut_arquivo=__file__)
checa("recusado" in aviso.lower(),
      "e o software segue com o look de fábrica, avisando", aviso)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] misturar em 8 bits")
a = np.full((32, 32, 3), 200, np.uint8)
b = np.full((32, 32, 3), 40, np.uint8)
checa(int(np.abs(V.misturar(a, b, np.ones((32, 32), np.float32)).astype(int)
                 - 200).max()) <= 1, "máscara 1 devolve a frente")
checa(int(np.abs(V.misturar(a, b, np.zeros((32, 32), np.float32)).astype(int)
                 - 40).max()) <= 1, "máscara 0 devolve o fundo")
meio = float(V.misturar(a, b, np.full((32, 32), 0.5, np.float32)).mean())
checa(abs(meio - 120) <= 2, "máscara 0,5 fica no meio", f"{meio:.1f}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] embelezamento — o que tem de sumir e o que NÃO pode sumir")
rng = np.random.default_rng(3)
cena = np.zeros((720, 1280, 3), np.uint8)
cena[:] = (70, 80, 95)
cv2.ellipse(cena, (640, 360), (150, 200), 0, 0, 360, (120, 150, 190), -1)
cv2.circle(cena, (600, 320), 9, (92, 112, 142), -1)      # mancha
cv2.circle(cena, (660, 430), 7, (95, 115, 145), -1)      # outra
cv2.ellipse(cena, (600, 255), (34, 9), 0, 0, 360, (40, 45, 55), -1)  # sobrancelha
cena = np.clip(cena.astype(np.float32) + rng.normal(0, 4, cena.shape),
               0, 255).astype(np.uint8)
rosto = IA.Rosto(490, 160, 300, 400, 1.0, "teste")
B = BEL.Beleza()
saida = B.aplicar(cena, rosto)


def contraste(img, y, x, ry=300, rx=700):
    return abs(int(img[y, x, 1]) - int(img[ry, rx, 1]))


m1a, m1b = contraste(cena, 320, 600), contraste(saida, 320, 600)
m2a, m2b = contraste(cena, 430, 660), contraste(saida, 430, 660)
checa(m1b < m1a and m2b < m2a, "as manchas ficam menos visíveis",
      f"{m1a}->{m1b} e {m2a}->{m2b}")
sa, sb = contraste(cena, 255, 600), contraste(saida, 255, 600)
checa(sb > sa * 0.9, "a SOBRANCELHA continua lá (não é mancha)", f"{sa}->{sb}")
ta, tb = detalhe(cena, 555, 340), detalhe(saida, 555, 340)
checa(tb < ta, "a textura da pele diminui", f"{ta:.2f}->{tb:.2f}")
checa(tb > ta * 0.35,
      "mas NÃO some — pele sem textura é o rosto de plástico", f"{tb:.2f}")
checa(int(np.abs(saida.astype(int) - cena.astype(int))[0:60, 0:60].max()) == 0,
      "o fundo não é tocado")
zero = B.aplicar(cena, rosto, pele=0, manchas=0, olhos=0, dentes=0)
checa(int(np.abs(zero.astype(int) - cena.astype(int)).max()) == 0,
      "com tudo em zero, a imagem sai EXATAMENTE igual à que entrou")

sem_rosto = B.aplicar(np.full((240, 320, 3), (60, 160, 60), np.uint8), None)
checa(sem_rosto is not None, "cena sem pele nenhuma não estoura")

print("\n[5] a tabela do retoque não pode embaralhar canais")
t = BEL.tabela_alta(0.45)
checa(t.shape == (1, 256, 3), "formato certo para o cv2.LUT", str(t.shape))
checa(int(t[0, 128, 0]) == int(t[0, 128, 1]) == int(t[0, 128, 2]),
      "os três canais são IGUAIS (foi aqui que a textura aumentou)")
t1 = BEL.tabela_alta(0.0)
checa(int(np.abs(t1[0, :, 0].astype(int) - np.arange(256)).max()) <= 1,
      "força 0 é a identidade também na tabela")
tm = BEL.tabela_mancha(0.5)
checa(int(tm[0, 3, 0]) == 0, "escurecimento de 3 níveis é textura: não mexe")
checa(int(tm[0, 25, 0]) > 0, "escurecimento de 25 níveis é mancha: corrige")
checa(int(tm[0, 90, 0]) == 0,
      "escurecimento de 90 níveis é feição (sobrancelha): solta")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] desfoque de fundo")
cena2 = np.zeros((720, 1280, 3), np.uint8)
for i in range(0, 1280, 40):
    cv2.line(cena2, (i, 0), (i, 720), (200, 200, 200), 3)
cv2.ellipse(cena2, (640, 330), (150, 190), 0, 0, 360, (120, 150, 190), -1)
cv2.rectangle(cena2, (430, 520), (850, 720), (120, 150, 190), -1)
F = FUN.Fundo()
r2 = IA.Rosto(490, 140, 300, 380, 1.0, "teste")
for _ in range(3):
    borrada, nivel = F.aplicar(cena2, r2, forca=0.7)
d_fundo_a, d_fundo_b = detalhe(cena2, 80, 80), detalhe(borrada, 80, 80)
checa(d_fundo_b < d_fundo_a * 0.5, "o fundo perde detalhe",
      f"{d_fundo_a:.2f}->{d_fundo_b:.2f}")
d_p_a = detalhe(cena2, 600, 300, lado=40)
d_p_b = detalhe(borrada, 600, 300, lado=40)
checa(d_p_b >= d_p_a * 0.8, "a pessoa NÃO é borrada",
      f"{d_p_a:.2f}->{d_p_b:.2f}")
checa(int(np.abs(F.aplicar(cena2, r2, forca=0)[0].astype(int)
                 - cena2.astype(int)).max()) == 0, "força 0 é identidade")
checa(F.aplicar(cena2, None, forca=0.7)[1] != "",
      "sem rosto, diz o motivo em vez de borrar tudo")

print("\n[7] acabamento")
A = V.Acabamento()
plano = np.full((200, 300, 3), 128, np.uint8)
checa(np.array_equal(A.aplicar_vinheta(plano, 0.0), plano),
      "vinheta 0 não mexe")
v = A.aplicar_vinheta(plano, 0.6)
checa(int(v[100, 150].mean()) > int(v[5, 5].mean()),
      "vinheta escurece o canto e não o centro")
checa(np.array_equal(A.aplicar_grao(plano, 0.0), plano), "grão 0 não mexe")
g = A.aplicar_grao(plano, 0.8)
checa(float(g.astype(np.float32).std()) > 1.0, "grão 0,8 adiciona variação")
preto = np.zeros((60, 60, 3), np.uint8)
gp = A.aplicar_grao(preto, 1.0)
checa(int(gp.max()) <= 6, "no preto quase não há grão (como no filme real)",
      f"max {int(gp.max())}")
checa(np.array_equal(A.aplicar_halacao(plano, 0.5), plano),
      "sem luz forte na cena, a halação nem gasta o desfoque")
# num quadro do tamanho real: o alcance do halo é proporcional à largura
com_luz = np.full((720, 1280, 3), 128, np.uint8)
cv2.circle(com_luz, (400, 360), 40, (255, 255, 255), -1)
h = A.aplicar_halacao(com_luz, 0.8)
# 185 fica 15 px FORA da borda do círculo (centro 150, raio 20). Eu tinha
# medido em 135, que está dentro da luz -- lá não há o que sangrar.
checa(int(h[360, 455].mean()) > int(com_luz[360, 455].mean()),
      "com luz forte, o brilho sangra para FORA da luz (15 px)",
      f"{int(com_luz[360,455].mean())} -> {int(h[360,455].mean())}")
checa(int(h[360, 500].mean()) > int(com_luz[360, 500].mean()),
      "e alcança 60 px, como lente de verdade — não uma borda de 8 px",
      f"{int(com_luz[360,500].mean())} -> {int(h[360,500].mean())}")
checa(int(h.max()) <= 255, "e não passa de 255")

print("\n[8] a curva de correção da IA")
c = V.curva_correcao()
checa(c.shape == (1, 256, 3), "formato para o cv2.LUT", str(c.shape))
checa(int(np.abs(c[0, :, 0].astype(int) - np.arange(256)).max()) <= 1,
      "sem correção, é a identidade")
mais = V.curva_correcao(ev=1.0)
checa(int(mais[0, 100, 0]) > int(c[0, 100, 0]), "+1 EV clareia")
checa(int(mais[0, 250, 0]) <= 255, "e o topo não dá a volta no inteiro")

sys.exit(resumo("IMAGEM"))
