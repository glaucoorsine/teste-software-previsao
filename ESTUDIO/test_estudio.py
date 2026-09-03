# -*- coding: utf-8 -*-
"""O software INTEIRO montado, sem janela, sem webcam, sem internet.

Os outros testes provam as peças. Este prova a montagem: câmera -> motor ->
preview -> transmissão, com as threads de verdade rodando. É o teste que
pega o defeito que só aparece quando tudo está ligado junto -- a peça que
sozinha funciona e no conjunto trava.

    python test_estudio.py
"""
from __future__ import annotations
import sys
import time
import numpy as np

from _base_teste import checa, resumo
import ajustes as A
import motor as MT

try:
    import cv2
except Exception:
    print("OpenCV não instalado")
    sys.exit(1)

import ESTUDIO


def cena_teste():
    q = np.zeros((720, 1280, 3), np.uint8)
    for i in range(0, 1280, 40):
        cv2.line(q, (i, 0), (i, 720), (190, 190, 190), 3)
    cv2.ellipse(q, (640, 340), (150, 195), 0, 0, 360, (120, 150, 190), -1)
    cv2.rectangle(q, (430, 530), (850, 720), (120, 150, 190), -1)
    return q


print("\n[1] o motor de imagem, quadro a quadro")
aj = dict(A.PADRAO)
aj["desfoque_fundo"] = 0.6
m = MT.Motor()
q = cena_teste()
saida = m.processar(q.copy(), aj)
checa(saida.shape == q.shape and saida.dtype == q.dtype,
      "o quadro sai do mesmo tamanho e tipo que entrou")
checa(not np.array_equal(saida, q), "e sai diferente (os filtros agem)")
checa(m.diag.look != "", "o motor diz qual look aplicou", m.diag.look)

tudo_zero = dict(A.PADRAO)
for k in ("look_forca", "grao", "vinheta", "halacao", "nitidez"):
    tudo_zero[k] = 0.0
tudo_zero.update(beleza_ligada=False, ia_ligada=False, desfoque_fundo=0.0)
m2 = MT.Motor()
igual = m2.processar(q.copy(), tudo_zero)
checa(int(np.abs(igual.astype(int) - q.astype(int)).max()) <= 4,
      "com tudo desligado, a imagem passa praticamente intacta",
      f"máx {int(np.abs(igual.astype(int)-q.astype(int)).max())}")

print("\n[2] o governador de desempenho")
m3 = MT.Motor()
m3.orcamento_ms = 0.001            # orçamento impossível: tem de desligar tudo
for _ in range(200):
    m3.processar(q.copy(), aj)
checa(len(m3.diag.desligados) >= 4,
      "orçamento impossível faz o governador desligar efeitos",
      f"desligou {len(m3.diag.desligados)}")
checa(m3.diag.desligados == [rot for ch, rot in MT.SACRIFICIO
                             if ch in m3._desligados],
      "e a lista mostrada é a que ele realmente desligou")
primeiro = MT.SACRIFICIO[0][1]
checa(primeiro in m3.diag.desligados,
      f"o primeiro sacrificado é o enfeite ('{primeiro}'), não o pedido dele")

m4 = MT.Motor()
m4.orcamento_ms = 100000.0         # orçamento folgado: não desliga nada
for _ in range(60):
    m4.processar(q.copy(), aj)
checa(not m4.diag.desligados, "com folga, não desliga nada")

print("\n[3] o estúdio inteiro, com as threads rodando")
aj2 = dict(A.PADRAO)
aj2["audio_ligado"] = False
aj2["desfoque_fundo"] = 0.5
est = ESTUDIO.Estudio(aj2)
ok, msg = est.abrir(camera_falsa=cena_teste())
checa(ok, "abre", msg)
time.sleep(2.0)
checa(est.preview is not None, "gera o preview para a tela")
checa(est.motor.diag.fps > 0, "processa quadros de verdade",
      f"{est.motor.diag.fps:.1f} fps")
checa(est.preview.shape[1] <= 480,
      "e o preview é reduzido (a tela não rouba tempo da live)")

print("\n[4] não transmite sem chave, e não trava tentando")
ok_tx, msg_tx = est.transmitir()
checa(not ok_tx and "chave" in msg_tx.lower(),
      "sem chave, recusa com motivo claro", msg_tx)
checa(not est.tx.estado.rodando, "e nada fica meio ligado")

print("\n[5] fecha limpo")
t0 = time.perf_counter()
est.fechar()
levou = time.perf_counter() - t0
checa(levou < 5.0, "fecha em tempo razoável", f"{levou:.1f} s")
checa(est.camera is None and est.mic is None, "e solta os dispositivos")

print("\n[6] o verificador embutido")
checa(ESTUDIO.verificar() == 0, "python ESTUDIO.py --verificar passa")

sys.exit(resumo("ESTÚDIO"))
