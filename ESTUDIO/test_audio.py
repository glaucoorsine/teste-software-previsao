# -*- coding: utf-8 -*-
"""O áudio ao vivo. O primeiro teste é o que decide se o resto vale algo.

CONTINUIDADE ENTRE BLOCOS
─────────────────────────
Ao vivo o som chega em blocos de 1024 amostras. Um filtro que zera o estado a
cada bloco produz um clique a cada 21 ms -- 47 por segundo. É inaudível num
teste de um bloco só, passa despercebido em qualquer inspeção de código, e
destrói a live.

Este teste processa o MESMO sinal de duas formas -- num bloco só, e em blocos
de 1024 -- e exige resultado idêntico. Se der diferente, há clique.

    python test_audio.py
"""
from __future__ import annotations
import sys
import time
import numpy as np

from _base_teste import checa, resumo
import audio as AU
import audio_dsp as D

TAXA = 48000
N = TAXA
t = np.arange(N) / TAXA
rng = np.random.default_rng(7)

voz = ((0.30 * np.sin(2 * np.pi * 180 * t) + 0.15 * np.sin(2 * np.pi * 1200 * t))
       * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)


def por_blocos(fabrica, x, tam=1024, **kw):
    o = fabrica()
    partes = [np.atleast_1d(o.processar(x[i:i + tam], **kw))
              for i in range(0, len(x), tam)]
    return np.concatenate([p for p in partes if p.size])


print("\n[1] CONTINUIDADE — o teste que impede 47 cliques por segundo")
for nome, fab in (("passa-altas 80 Hz", lambda: D.passa_altas(80, TAXA)),
                  ("EQ sino 4 kHz", lambda: D.sino(4000, 3.0, 1.0, TAXA)),
                  ("prateleira 6 kHz", lambda: D.prateleira_alta(6000, 3.0, TAXA))):
    inteiro = np.atleast_1d(fab().processar(voz))
    picado = por_blocos(fab, voz)
    n = min(len(inteiro), len(picado))
    dif = float(np.abs(inteiro[:n] - picado[:n]).max())
    checa(dif < 1e-5, f"{nome}: um bloco == cem blocos", f"diferença {dif:.2e}")

lim_int = D.Limitador(TAXA).processar(voz * 3, -1.0)
lim_bl = por_blocos(lambda: D.Limitador(TAXA), voz * 3, teto_db=-1.0)
n = min(len(lim_int), len(lim_bl))
dif = float(np.abs(lim_int[:n] - lim_bl[:n]).max())
checa(dif < 1e-3, "limitador: um bloco == cem blocos", f"diferença {dif:.2e}")

print("\n[2] o limitador é um TETO, não uma sugestão")
for teto in (-1.0, -3.0, -6.0):
    saida = por_blocos(lambda: D.Limitador(TAXA), voz * 5, teto_db=teto)
    g = D.db_para_ganho(teto)
    pico = float(np.abs(saida).max())
    checa(pico <= g + 1e-6, f"nada passa de {teto} dB",
          f"pico {20*np.log10(max(pico,1e-9)):.2f} dB")
checa(float(np.abs(por_blocos(lambda: D.Limitador(TAXA), voz * 0.1,
                              teto_db=-1.0)).max()) > 0.02,
      "e sinal baixo passa intacto (não é um portão)")

print("\n[3] o portão")
silencio_fala = np.concatenate([
    (rng.normal(0, 0.002, TAXA // 2)).astype(np.float32), voz[:TAXA // 2]])
P = D.Portao(-42.0, TAXA)
saida = np.concatenate([P.processar(silencio_fala[i:i + 1024])[0]
                        for i in range(0, len(silencio_fala), 1024)])
ruido_db = 20 * np.log10(max(float(np.abs(saida[4000:20000]).max()), 1e-9))
fala_db = 20 * np.log10(max(float(np.abs(saida[26000:]).max()), 1e-9))
checa(ruido_db < -50, "o chiado do silêncio é abafado", f"{ruido_db:.1f} dBFS")
checa(fala_db > -15, "e a fala passa inteira", f"{fala_db:.1f} dBFS")

print("\n[4] o compressor nivela")
C1, C2 = D.Compressor(TAXA), D.Compressor(TAXA)
alto = C1.processar(voz * 2.0, 0.7)[0]
baixo = C2.processar(voz * 0.1, 0.7)[0]
antes = 20 * np.log10(np.abs(voz * 2.0).max() / max(np.abs(voz * 0.1).max(), 1e-9))
depois = 20 * np.log10(np.abs(alto).max() / max(np.abs(baixo).max(), 1e-9))
checa(depois < antes - 3, "a distância entre alto e baixo diminui",
      f"{antes:.1f} dB -> {depois:.1f} dB")
igual = D.Compressor(TAXA).processar(voz, 0.0)[0]
checa(float(np.abs(igual - voz).max()) < 1e-6, "em zero, não toca no som")

print("\n[5] redução de ruído: mata o chiado sem matar a voz")
fala = np.zeros(N * 3, np.float32)
t3 = np.arange(N * 3) / TAXA
for ini in range(4000, N * 3 - 8000, 14000):
    d = 7000
    env = np.hanning(d).astype(np.float32)
    fala[ini:ini + d] = ((0.35 * np.sin(2 * np.pi * 440 * t3[ini:ini + d])
                          + 0.2 * np.sin(2 * np.pi * 880 * t3[ini:ini + d]))
                         * env).astype(np.float32)
sujo = (fala + rng.normal(0, 0.03, N * 3)).astype(np.float32)
R = D.ReducaoRuido(TAXA)
limpo = np.concatenate([R.processar(sujo[i:i + 1024], 0.7)
                        for i in range(0, N * 3, 1024)])


def banda(x, f0, f1, a, b):
    seg = x[a:b]
    X = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(len(seg), 1 / TAXA)
    return float(X[(fr >= f0) & (fr < f1)].mean())


atraso = 1024
v_antes = banda(sujo, 400, 480, 60000, 66000)
v_depois = banda(limpo, 400, 480, 60000 - atraso, 66000 - atraso)
c_antes = banda(sujo, 8000, 12000, 70000, 76000)
c_depois = banda(limpo, 8000, 12000, 70000 - atraso, 76000 - atraso)
checa(c_depois < c_antes * 0.35, "o chiado cai bastante",
      f"{c_antes:.3f} -> {c_depois:.3f}")
checa(v_depois > v_antes * 0.55, "e a VOZ sobrevive",
      f"{v_antes:.1f} -> {v_depois:.1f}")
ganho = (20 * np.log10(v_antes / max(v_depois, 1e-9))
         - 20 * np.log10(c_antes / max(c_depois, 1e-9)))
checa(ganho < -6, "o saldo é a favor da voz (mais chiado que voz removidos)",
      f"{-ganho:.1f} dB de melhora")

print("\n[6] a cadeia inteira")
cad = AU.Cadeia(TAXA, 1)
cad.ajustar(80, 1.5, -2.0, 3.0, -42)
saida = np.concatenate([cad.processar(sujo[i:i + 1024], teto_db=-1.0)
                        for i in range(0, N, 1024)])
checa(saida.size > 0, "produz som")
checa(float(np.abs(saida).max()) <= D.db_para_ganho(-1.0) + 1e-6,
      "e respeita o teto no fim da cadeia")
checa(np.isfinite(saida).all(), "sem NaN nem infinito")
checa(20 < cad.latencia_ms < 40, "declara a latência que tem",
      f"{cad.latencia_ms:.1f} ms")

print("\n[7] custo")
cad2 = AU.Cadeia(TAXA, 1)
cad2.ajustar(80, 1.5, -2.0, 3.0, -42)
t0 = time.perf_counter()
for i in range(0, N, 1024):
    cad2.processar(sujo[i:i + 1024])
ms = (time.perf_counter() - t0) * 1000
checa(ms < 250, "1 segundo de áudio custa menos de 250 ms de CPU",
      f"{ms:.0f} ms")
print(f"        (medido: {ms:.0f} ms por segundo de som = {ms/10:.1f}% de um núcleo)")

print("\n[8] PCM de 16 bits")
b = AU.para_pcm16(np.array([1.5, -1.5, 0.0, 0.5], np.float32))
v = np.frombuffer(b, "<i2")
checa(v[0] == 32767 and v[1] == -32767,
      "sinal fora de faixa é CORTADO, não dá a volta no inteiro", str(v))
checa(abs(int(v[3]) - 16383) <= 2, "e o resto converte certo", str(v[3]))
checa(len(b) == 8, "dois bytes por amostra")

sys.exit(resumo("ÁUDIO"))
