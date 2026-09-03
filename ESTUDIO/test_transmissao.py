# -*- coding: utf-8 -*-
"""A transmissão. Aqui o defeito é caro: ele só descobre no ar.

Transmitir de verdade exige internet, chave e webcam, e nada disso cabe num
teste automático. Mas o que mais quebra numa transmissão não é a rede: é a
LINHA DE COMANDO. Um parâmetro errado e o YouTube recusa, ou aceita e a live
fica sem som, ou com quadro-chave espaçado demais e o espectador vê tela
preta por segundos.

Então testo a linha de comando inteira, sem transmitir nada. E testo o que
mais importa depois disso: que a CHAVE não aparece em lugar nenhum.

    python test_transmissao.py
"""
from __future__ import annotations
import sys

from _base_teste import checa, resumo
import ajustes as A
import transmissao as T

CHAVE = "abcd-1234-efgh-5678-wxyz"
DESTINO = f"rtmp://a.rtmp.youtube.com/live2/{CHAVE}"

cmd = T.montar_comando("ffmpeg", 1280, 720, 30, 54321, DESTINO, "libx264",
                       4500, 160, 48000, 1, "C:/lives/copia.mp4")
texto = " ".join(cmd)

print("\n[1] as duas entradas chegam no ffmpeg")
checa("-i" in cmd and cmd.count("-i") == 2, "duas entradas: vídeo e som")
checa("pipe:0" in cmd, "vídeo pela entrada padrão")
checa("tcp://127.0.0.1:54321" in cmd, "som pelo socket local")
checa("127.0.0.1" in texto and "0.0.0.0" not in texto,
      "o socket é só local — nada disso sai da máquina dele")
checa(cmd.index("-f") < cmd.index("pipe:0"), "o formato vem antes da entrada")
checa(texto.count("-use_wallclock_as_timestamps 1") == 2,
      "as duas entradas usam o relógio de parede (é o que casa boca e voz)")

print("\n[2] o que o YouTube exige")
g = cmd[cmd.index("-g") + 1]
checa(g == "60", "quadro-chave a cada 2 s a 30 fps (o YouTube pede isso)", g)
checa(cmd[cmd.index("-g", cmd.index("-g") + 1) if False else
          cmd.index("-keyint_min") + 1] == "60", "e o mínimo é o mesmo")
checa("yuv420p" in cmd, "formato de cor que todo player entende")
checa(cmd[cmd.index("-c:a") + 1] == "aac", "som em AAC")
checa(cmd[cmd.index("-ac", cmd.index("-c:a")) + 1] == "2",
      "som entregue em estéreo, mesmo captando mono")
checa("flv" in cmd, "empacotamento FLV, que é o que o RTMP quer")
checa(cmd[-1].endswith(".mp4"), "a cópia local é o último destino")
checa("copy" in cmd, "a cópia local reaproveita o vídeo já codificado")
checa("+faststart" in texto, "e abre em qualquer player")

for fps, esperado in ((24, "48"), (30, "60"), (60, "120")):
    o = T.opcoes_qualidade("libx264", 4500, fps)
    checa(o[o.index("-g") + 1] == esperado,
          f"a {fps} fps o quadro-chave é {esperado}", o[o.index("-g") + 1])

print("\n[3] A CHAVE NÃO PODE APARECER")
visivel = T.comando_visivel(cmd)
checa(CHAVE not in visivel, "a chave não aparece no comando mostrado")
checa("abcd" not in visivel, "nem o começo dela")
checa(visivel.endswith("copia.mp4") and "•••" in visivel,
      "mas o resto do comando aparece inteiro, para ele conferir")
checa("wxyz" in visivel,
      "com os 4 últimos, que é o que permite conferir SE é a chave certa")

print("\n[4] escolha do codificador")
checa(T.escolher_encoder("auto", ["h264_nvenc", "libx264"])[0] == "h264_nvenc",
      "com placa de vídeo disponível, usa a placa")
checa(T.escolher_encoder("auto", ["libx264"])[0] == "libx264",
      "sem placa, usa o processador")
esc, motivo = T.escolher_encoder("h264_qsv", ["libx264"])
checa(esc == "libx264" and "não existe" in motivo,
      "pedido impossível cai no que existe E explica", motivo)
checa(T.escolher_encoder("auto", [])[0] == "libx264",
      "sem lista nenhuma, ainda tenta o mais compatível")
for enc in ("h264_nvenc", "h264_qsv", "h264_amf", "libx264"):
    o = T.opcoes_qualidade(enc, 4500, 30)
    checa(o[1] == enc and "-b:v" in o, f"{enc} tem parâmetros próprios")

print("\n[5] recusa de partida — o erro TEM de vir com motivo")
tx = T.Transmissao()
tx.ffmpeg = ""
ok, msg = tx.iniciar("rtmp://x/y", 1280, 720, 30)
checa(not ok and "ffmpeg" in msg.lower(),
      "sem ffmpeg, diz exatamente o que falta", msg)
tx.ffmpeg = "ffmpeg"
ok2, msg2 = tx.iniciar("http://nao-e-rtmp", 1280, 720, 30)
checa(not ok2 and "inválido" in msg2, "endereço que não é RTMP é recusado", msg2)
checa(not tx.estado.rodando, "e nada fica meio ligado")

print("\n[6] a URL do YouTube")
checa(A.url_youtube(CHAVE) == DESTINO, "monta o endereço certo")
checa(A.url_youtube(CHAVE).startswith(A.RTMP_YOUTUBE),
      "no servidor de entrada do YouTube")

sys.exit(resumo("TRANSMISSÃO"))
