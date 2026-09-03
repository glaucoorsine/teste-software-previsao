# -*- coding: utf-8 -*-
"""Ajustes e dispositivos: a memória do software e o achador da Lyra.

O que este teste protege, e por que cada um importa:

  1. um arquivo de ajustes CORROMPIDO não pode derrubar o software
  2. um campo com tipo errado não pode arrastar os outros campos junto
  3. a CHAVE não pode entrar no JSON que ele mandaria para alguém
  4. "ly7ra" (como ele escreveu) tem de casar com "Hollyland Lyra"
     (como o dispositivo se chama de verdade)

    python test_ajustes.py
"""
from __future__ import annotations
import json
import sys
import tempfile
from pathlib import Path

from _base_teste import checa, resumo
import ajustes as A
import dispositivos as D

tmp = Path(tempfile.mkdtemp())

print("\n[1] carregar e salvar")
d = A.carregar(tmp / "nao_existe.json")
checa(set(d) == set(A.PADRAO), "arquivo ausente devolve o padrão inteiro")

(tmp / "lixo.json").write_text("{isto não é json", encoding="utf-8")
checa(A.carregar(tmp / "lixo.json") == A.PADRAO,
      "arquivo corrompido volta ao padrão sem estourar")

meu = dict(A.PADRAO)
meu["look"] = "venice"
meu["nitidez"] = 0.9
A.salvar(meu, tmp / "meu.json")
lido = A.carregar(tmp / "meu.json")
checa(lido["look"] == "venice" and abs(lido["nitidez"] - 0.9) < 1e-6,
      "o que ele regulou volta igual")

print("\n[2] campo errado não contamina os outros")
sujo = json.loads((tmp / "meu.json").read_text(encoding="utf-8"))
sujo["nitidez"] = "muito"          # tipo errado
sujo["campo_que_nao_existe"] = 42  # campo desconhecido
sujo["fps"] = 999999               # fora de faixa
(tmp / "sujo.json").write_text(json.dumps(sujo), encoding="utf-8")
s = A.carregar(tmp / "sujo.json")
checa(s["look"] == "venice", "campo válido sobrevive ao campo inválido ao lado")
checa(s["nitidez"] == A.PADRAO["nitidez"], "campo de tipo errado cai no padrão")
checa("campo_que_nao_existe" not in s, "campo desconhecido é ignorado")
checa(s["fps"] == A.FAIXAS["fps"][1], "valor fora de faixa é grampeado")
checa(A.grampear("grao", float("nan")) == A.PADRAO["grao"],
      "NaN não passa (ele atravessa float() e envenena tudo depois)")

print("\n[3] a chave nunca entra no arquivo de ajustes")
com_chave = dict(A.PADRAO)
com_chave["chave"] = "SEGREDO-1234"
com_chave["chave_youtube"] = "SEGREDO-1234"
A.salvar(com_chave, tmp / "c.json")
texto = (tmp / "c.json").read_text(encoding="utf-8")
checa("SEGREDO" not in texto, "chave não vaza para o JSON de ajustes")

A.gravar_chave("abcd-1234-efgh-5678-wxyz", tmp / "chave.txt")
checa(A.chave(tmp / "chave.txt") == "abcd-1234-efgh-5678-wxyz",
      "a chave é lida do arquivo próprio")
m = A.mascara("abcd-1234-efgh-5678-wxyz")
checa("abcd" not in m and m.endswith("wxyz"),
      "a máscara mostra só os 4 últimos", m)
checa(A.mascara("") == "(nenhuma)", "sem chave, diz que não tem")
try:
    A.url_youtube("")
    ok = False
except ValueError:
    ok = True
checa(ok, "montar a URL sem chave é recusado, não silencioso")

print("\n[4] achar a webcam dele pelo nome")
checa(D.parece("Hollyland Lyra", "ly7ra"),
      "'ly7ra' (como ele escreveu) casa com 'Hollyland Lyra'")
checa(D.parece("LY7RA HD Camera", "lyra"), "e o contrário também")
checa(D.parece("Hollyland Lyra", "hollyland"), "casa pelo fabricante")
checa(not D.parece("Integrated Camera", "lyra"),
      "não casa com a câmera do notebook")
checa(not D.parece("Integrated Camera", ""),
      "nome vazio não casa com qualquer coisa")

saida_windows = '''
[dshow @ 0] "Hollyland Lyra" (video)
[dshow @ 0]   Alternative name "@device_pnp_\\\\?\\usb#vid_1bcf"
[dshow @ 0] "Integrated Camera" (video)
[dshow @ 0] "Microfone (Hollyland Lyra)" (audio)
'''
ds = D.ler_dshow(saida_windows)
videos = [x for x in ds if x.tipo == "video"]
audios = [x for x in ds if x.tipo == "audio"]
checa(len(videos) == 2 and len(audios) == 1,
      "a saída real do ffmpeg no Windows é lida certo",
      f"{len(videos)} vídeo, {len(audios)} áudio")
checa(videos[0].nome == "Hollyland Lyra",
      "o nome alternativo (@device_pnp) não vira um dispositivo falso")

d, motivo = D.escolher(videos, "ly7ra")
checa(d.nome == "Hollyland Lyra", "escolhe a Lyra e não a do notebook")
d2, motivo2 = D.escolher(videos, "logitech")
checa("NÃO achei" in motivo2,
      "quando não acha, AVISA em vez de usar outra em silêncio", motivo2)
d3, motivo3 = D.escolher(videos, "ly7ra", indice=1)
checa(d3.indice == 1, "índice fixado por ele vence o nome")
checa(D.escolher([], "x")[0] is None, "lista vazia não estoura")

sys.exit(resumo("AJUSTES E DISPOSITIVOS"))
