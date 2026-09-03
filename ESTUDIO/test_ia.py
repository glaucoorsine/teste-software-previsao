# -*- coding: utf-8 -*-
"""A IA de imagem: ela tem de melhorar E tem de se conter.

O QUE UMA MALHA DE CORREÇÃO FAZ DE ERRADO QUANDO NINGUÉM COBRA
──────────────────────────────────────────────────────────────
Ela oscila. Mede escuro, clareia demais, mede claro, escurece, e a live fica
pulsando -- o defeito que faz uma câmera automática parecer pior que uma
travada na mão. Os três freios do `ia_visual` (banda morta, passo curto,
suavização da medida) existem contra isso, e este teste os cobra num degrau
de luz, que é o pior caso: ele acende a luminária e a cena muda de uma vez.

    python test_ia.py
"""
from __future__ import annotations
import sys
import numpy as np

from _base_teste import checa, resumo
import ia_visual as IA


def cena(luz: float, cor=(0.72, 0.82, 1.0), tam=(240, 320)):
    """Um retângulo de pele com a luminância pedida."""
    base = np.array(cor, dtype=np.float32)
    base = base / base.mean() * (luz * 255.0)
    img = np.zeros((tam[0], tam[1], 3), np.uint8)
    img[:] = np.clip(base, 0, 255).astype(np.uint8)
    return img


print("\n[1] medir")
m = IA.medir(cena(0.5))
checa(0.4 < m.luz_rosto < 0.6, "luminância medida bate com a cena",
      f"{m.luz_rosto:.2f}")
checa(m.tem_rosto, "acha pele mesmo sem detector de rosto")
claro = IA.medir(cena(0.95))
checa(claro.luz_rosto > m.luz_rosto, "cena mais clara mede mais claro")
estourada = np.full((120, 160, 3), 255, np.uint8)
checa(IA.medir(estourada).estourado > 0.9, "conta o pixel queimado")

print("\n[2] o controlador CONVERGE")
c = IA.Controlador(alvo=0.55, forca=0.6)
escura = cena(0.25)
hist = []
for _ in range(200):
    med = IA.medir(escura)
    # simula a correção sendo de fato aplicada à cena medida
    med.luz_rosto = float(np.clip(0.25 * (2.0 ** c.cor.ev), 0, 1))
    cor = c.passo(med)
    hist.append(med.luz_rosto)
final = hist[-1]
checa(abs(final - 0.55) < 0.06, "chega perto do alvo partindo do escuro",
      f"terminou em {final:.3f}")
checa(c.cor.ev > 0.5, "e chegou lá clareando", f"ev={c.cor.ev:.2f}")

print("\n[3] e NÃO oscila")
passou = [i for i in range(1, len(hist))
          if (hist[i - 1] - 0.55) * (hist[i] - 0.55) < 0]
checa(len(passou) <= 1, "cruza o alvo no máximo uma vez",
      f"cruzou {len(passou)} vezes")
ultimos = hist[-40:]
checa(max(ultimos) - min(ultimos) < 0.02,
      "e fica parado no fim (não fica caçando)",
      f"variação final {max(ultimos)-min(ultimos):.4f}")
checa(c.parada, "e ele SABE que chegou (bandeira de parada)")

print("\n[4] a banda morta impede o tremor")
c2 = IA.Controlador(alvo=0.55, forca=1.0)
m2 = IA.medir(cena(0.55))
m2.luz_rosto = 0.55
for _ in range(20):
    c2.passo(m2)
checa(abs(c2.cor.ev) < 0.01, "já no alvo, não mexe em nada",
      f"ev={c2.cor.ev:.4f}")

print("\n[5] o passo é limitado (nada de salto)")
c3 = IA.Controlador(alvo=0.55, forca=1.0)
m3 = IA.medir(cena(0.02))
m3.luz_rosto = 0.02
antes = c3.cor.ev
c3.passo(m3)
checa(abs(c3.cor.ev - antes) <= IA.MAX_PASSO_EV + 1e-6,
      "mesmo com erro enorme, um passo por quadro",
      f"deu {abs(c3.cor.ev - antes):.4f}")

print("\n[6] cede quando insistir queimaria a imagem")
c4 = IA.Controlador(alvo=0.55)
queimada = IA.Medidas(luz_rosto=0.40, estourado=0.15)
checa(c4.alvo_agora(queimada) < 0.55,
      "com muita alta queimada, o alvo baixa em vez de destruir o resto",
      f"alvo virou {c4.alvo_agora(queimada):.2f}")

print("\n[7] desligada é desligada")
c5 = IA.Controlador()
cor = c5.passo(IA.medir(cena(0.2)), ligada=False)
checa(cor.ev == 0.0 and cor.ganho_b == 1.0 and cor.forca_ruido == 0.0,
      "IA desligada não corrige nada")

print("\n[8] o branco não é medido na pele quando há cinza disponível")
img = cena(0.5)
img[:, :160] = (128, 128, 128)        # metade cinza neutro
m6 = IA.medir(img)
checa(m6.origem_branco == "cinza",
      "com cinza no quadro, mede o branco no cinza", m6.origem_branco)
checa(abs(m6.ganho_b - 1.0) < 0.12 and abs(m6.ganho_r - 1.0) < 0.12,
      "e diz que a luz já é neutra",
      f"b={m6.ganho_b:.2f} r={m6.ganho_r:.2f}")
so_pele = IA.medir(cena(0.5))
checa(so_pele.origem_branco == "pele",
      "só pele no quadro: avisa que mediu pela pele", so_pele.origem_branco)

print("\n[9] o detector de rosto suaviza no tempo")
d = IA.Detector(cada_n=1)
img2 = np.zeros((240, 320, 3), np.uint8)
img2[:] = (60, 65, 70)
img2[60:160, 110:210] = (110, 140, 175)
r1 = d.achar(img2)
checa(r1 is not None and r1.valido, "acha a região de pele")
img3 = img2.copy()
img3[60:160, 110:210] = (60, 65, 70)
img3[60:160, 150:250] = (110, 140, 175)     # o "rosto" pulou 40 px
r2 = d.achar(img3)
checa(abs(r2.x - r1.x) < 40,
      "um salto na detecção NÃO vira um salto na máscara",
      f"{r1.x} -> {r2.x}")

sys.exit(resumo("IA DE IMAGEM"))
