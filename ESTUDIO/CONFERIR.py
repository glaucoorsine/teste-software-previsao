# -*- coding: utf-8 -*-
"""CONFERIR — o que esta máquina tem, o que falta, e o que fazer.

Rode isto ANTES da primeira live. Ele responde as perguntas que só aparecem
na hora errada: a webcam está sendo vista? o ffmpeg existe? tem placa de
vídeo para codificar? o computador aguenta a 30 quadros?

    python CONFERIR.py
"""
from __future__ import annotations
import os
import platform

# antes de importar o cv2: os avisos dele durante a varredura de câmeras são
# esperados, e em inglês no meio desta tela pareceriam defeito
os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))


def linha(rotulo, valor, ok=None):
    marca = "   " if ok is None else (" ok" if ok else "  !")
    print(f"{marca}  {rotulo:<34s} {valor}")


print("=" * 70)
print("ESTÚDIO — conferência da máquina")
print("=" * 70)
print(f"\n{platform.system()} {platform.release()} · Python "
      f"{sys.version.split()[0]}")

print("\nBIBLIOTECAS")
faltando = []
for mod, para_que, essencial in (
        ("numpy", "contas", True),
        ("cv2", "câmera e filtros", True),
        ("sounddevice", "ler o microfone", False),
        ("scipy", "áudio rápido (sem ele: 15x mais lento)", False),
        ("customtkinter", "aparência da janela", False),
        ("PIL", "desenhar o preview", False),
        ("mediapipe", "recorte de pessoa para o desfoque", False)):
    try:
        m = __import__(mod)
        linha(mod, f"{getattr(m, '__version__', 'ok')}  — {para_que}", True)
    except Exception:
        linha(mod, f"FALTA — {para_que}", False)
        if essencial:
            faltando.append(mod)

print("\nFFMPEG (é o que entrega a live ao YouTube)")
try:
    import transmissao as T
    exe = T.achar_ffmpeg()
    if exe:
        linha("ffmpeg", exe, True)
        encs = T.encoders_disponiveis(exe)
        if encs:
            esc, motivo = T.escolher_encoder("auto", encs)
            linha("codificadores", ", ".join(encs), True)
            linha("vai usar", motivo, True)
        else:
            linha("codificadores", "não consegui listar", False)
    else:
        linha("ffmpeg", "NÃO ENCONTRADO — ver LEIA_PRIMEIRO.md", False)
except Exception as e:
    linha("ffmpeg", f"erro: {e}", False)

print("\nCÂMERAS")
try:
    import dispositivos as D
    import ajustes as A
    cams = D.listar("video")
    if cams:
        for c in cams:
            linha(f"[{c.indice}]", f"{c.nome}  (por {c.origem})")
        d, motivo = D.escolher(cams, A.carregar().get("camera_nome", "lyra"))
        linha("vai usar", motivo, "NÃO achei" not in motivo)
    else:
        linha("câmeras", "nenhuma encontrada", False)
except Exception as e:
    linha("câmeras", f"erro: {e}", False)

print("\nMICROFONES")
try:
    mics = D.microfones()
    for m in mics[:6]:
        linha(f"[{m.indice}]", m.nome)
    if not mics:
        linha("microfones", "nenhum encontrado", False)
except Exception as e:
    linha("microfones", f"erro: {e}", False)

print("\nDESEMPENHO (o quanto esta máquina aguenta)")
try:
    import numpy as np
    import cv2
    import motor as MT
    import ajustes as A
    aj = dict(A.PADRAO)
    aj["desfoque_fundo"] = 0.6
    q = np.zeros((720, 1280, 3), np.uint8)
    for i in range(0, 1280, 40):
        cv2.line(q, (i, 0), (i, 720), (190, 190, 190), 3)
    cv2.ellipse(q, (640, 340), (150, 195), 0, 0, 360, (120, 150, 190), -1)
    m = MT.Motor()
    m.orcamento_ms = 1e9
    for _ in range(5):
        m.processar(q.copy(), aj)
    t = time.perf_counter()
    for _ in range(20):
        m.processar(q.copy(), aj)
    ms = (time.perf_counter() - t) / 20 * 1000
    linha("cadeia completa a 1280x720", f"{ms:.0f} ms/quadro = {1000/ms:.0f} fps",
          ms < 33)
    if ms > 33:
        print("      -> o governador vai desligar efeitos para segurar os 30 fps.")
        print("         Para ter tudo ligado: baixe para 960x540 nos ajustes.")
    print("      etapas:", {k: round(v) for k, v in m.diag.etapas_ms.items()})
except Exception as e:
    linha("desempenho", f"erro: {e}", False)

print("\n" + "=" * 70)
if faltando:
    print(f"FALTAM ESSENCIAIS: {', '.join(faltando)} — rode 0_INSTALAR.bat")
else:
    print("O essencial está aqui.")
print("=" * 70)
