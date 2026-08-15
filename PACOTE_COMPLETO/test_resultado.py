# -*- coding: utf-8 -*-
"""Confere a conta do RESULTADO com logs montados à mão.

A conta que importa é o `acaso`: se ela estiver errada, o relatório vai dizer
"acima do acaso" quando não está, que é pior do que não ter relatório nenhum.

    python test_resultado.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import RESULTADO as R  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


def escrever(linhas) -> Path:
    p = Path(tempfile.mkdtemp()) / "central_log.txt"
    p.write_text("\n".join(f"14/08 20:0{i%10}:00 | {t}"
                           for i, t in enumerate(linhas)), encoding="utf-8")
    return p


print("\n[1] a chance é a da aposta, não 1/37 fixo")
def cj(k, giros, jogo="lightning"):
    return R.chance_janela(R.chance_por_giro(jogo, [str(i) for i in range(k)], k),
                           giros)
checa(abs(cj(1, 1) - 1/37) < 1e-9, "1 número, 1 giro")
checa(abs(cj(7, 1) - 7/37) < 1e-9, "7 números, 1 giro")
c3 = cj(2, 3)
checa(abs(c3 - (1 - (35/37)**3)) < 1e-9, "2 números em 3 giros", c3)
checa(0.15 < c3 < 0.16, "que dá ~15% — errar 85% ali é o esperado", f"{c3:.3f}")
checa(R.chance_janela(0.0, 3) == 0.0, "aposta vazia não tem chance")
checa(R.chance_janela(3/37, 0) == 0.0, "sem giro, sem chance")
checa(abs(R.chance_por_giro("crazy_time", ["CrazyTime"], 1) - 1/54) < 1e-9,
      "Crazy Time usa 54 casas, não 37")

print("\n[2] reconstrói as janelas do log")
log = escrever([
    "lightning NOVA_JANELA [4, 5, 9] OPERAR",
    "lightning MISS 30 restam=2",
    "lightning HIT 5 restam=1",
    "lightning MISS 33 restam=0",
    "lightning JANELA OK ok=1 err=0",
    "lightning NOVA_JANELA [1, 2] OPERAR",
    "lightning MISS 11 restam=1",
    "lightning MISS 12 restam=0",
    "lightning JANELA ERRO ok=1 err=1",
])
d = R.ler(log)
j = d["lightning"]["janelas"]
checa(len(j) == 2, "duas janelas fechadas", len(j))
checa(j[0]["k"] == 3 and j[0]["giros"] == 3, "primeira: 3 números, 3 giros", j[0])
checa(j[0]["acertos"] == 1 and j[0]["fechou_bem"] is True, "primeira acertou")
checa(j[1]["k"] == 2 and j[1]["fechou_bem"] is False, "segunda errou", j[1])

print("\n[3] as outras mesas não se misturam")
log2 = escrever([
    "lightning NOVA_JANELA [1] OPERAR",
    "crazy_time NOVA_JANELA [1, 2] OPERAR",
    "crazy_time HIT 1 restam=1",
    "crazy_time MISS 5 restam=0",
    "crazy_time JANELA OK ok=1 err=0",
    "lightning MISS 7 restam=0",
    "lightning JANELA ERRO ok=0 err=1",
])
d2 = R.ler(log2)
checa(len(d2["crazy_time"]["janelas"]) == 1 and len(d2["lightning"]["janelas"]) == 1,
      "cada mesa com a sua janela, mesmo intercaladas")
checa(d2["crazy_time"]["janelas"][0]["acertos"] == 1, "acerto foi para o Crazy Time")
checa(d2["mega_fire"]["janelas"] == [], "mesa sem entrada fica vazia")

print("\n[4] janela herdada de antes do log não inventa tamanho")
log3 = escrever([
    "immersive HIT 7 restam=1",
    "immersive MISS 9 restam=0",
    "immersive JANELA OK ok=1 err=0",
])
d3 = R.ler(log3)
j3 = d3["immersive"]["janelas"]
checa(len(j3) == 1 and j3[0]["k"] is None,
      "guardada sem tamanho, em vez de chutar um", j3)
saida = "\n".join(R.relatar("immersive", d3["immersive"]))
checa("nenhuma janela fechada com aposta registrada" in saida,
      "e o relatório não a usa na conta", saida)

print("\n[5] o veredito segue a conta, não a impressão")
# 10 janelas de 2 números em 3 giros: acaso ~15,4%. 5 acertos = 32% -> ~2,1x
linhas = []
for i in range(10):
    linhas += [f"mega_fire NOVA_JANELA [1, 2] OPERAR",
               f"mega_fire {'HIT' if i < 5 else 'MISS'} 1 restam=2",
               f"mega_fire MISS 30 restam=1",
               f"mega_fire MISS 31 restam=0",
               f"mega_fire JANELA {'OK' if i < 5 else 'ERRO'} ok=0 err=0"]
d4 = R.ler(escrever(linhas))
txt = "\n".join(R.relatar("mega_fire", d4["mega_fire"]))
print("       " + txt.replace("\n", "\n       "))


def razao_da_linha(texto, rotulo):
    """Pega a razão da linha certa. Procurar o número solto no texto inteiro
    casa com a 'aposta média 2.0' e o teste passa por engano."""
    for ln in texto.splitlines():
        if rotulo in ln and "x" in ln:
            for pedaco in ln.split():
                if pedaco.endswith("x"):
                    return float(pedaco[:-1])
    return None


esperado = 0.5 / (1 - (35 / 37) ** 3)          # 50% sobre a chance real
checa("5 certas de 10" in txt, "conta as janelas certas", txt)
checa(abs(razao_da_linha(txt, "janelas") - esperado) < 0.02,
      f"razão bate com a conta ({esperado:.2f}x)", razao_da_linha(txt, "janelas"))
checa("pouco para concluir" in txt,
      "mas avisa que 10 janelas não concluem nada")

# mesmo caso, com aposta de 7 números: 32% ali EMPATA com o acaso
linhas7 = []
for i in range(10):
    linhas7 += ["immersive NOVA_JANELA [1, 2, 3, 4, 5, 6, 7] OPERAR",
                f"immersive {'HIT' if i < 5 else 'MISS'} 1 restam=0",
                f"immersive JANELA {'OK' if i < 5 else 'ERRO'} ok=0 err=0"]
d5 = R.ler(escrever(linhas7))
txt5 = "\n".join(R.relatar("immersive", d5["immersive"]))
print("       " + txt5.replace("\n", "\n       "))
checa("50.0%" in txt5, "50% de acerto com 7 números")
esperado7 = 0.5 / (7 / 37)
checa(abs(razao_da_linha(txt5, "janelas") - esperado7) < 0.02,
      f"comparado com o acaso DAQUELA aposta: {esperado7:.2f}x",
      razao_da_linha(txt5, "janelas"))
# a mesma taxa vale coisas diferentes conforme o tamanho da aposta
checa(razao_da_linha(txt, "janelas") > razao_da_linha(txt5, "janelas"),
      "50% com 2 números vale mais que 50% com 7 — é esse o ponto do relatório")

print("\n[6] log inexistente ou sujo não quebra")
checa(R.ler(Path("/nao/existe/central_log.txt"))["lightning"]["janelas"] == [],
      "arquivo ausente devolve vazio")
sujo = escrever(["lixo sem formato", "lightning NOVA_JANELA [] OPERAR",
                 "lightning JANELA OK", ""])
d6 = R.ler(sujo)
checa(isinstance(d6["lightning"]["janelas"], list), "linha estragada é ignorada")
saida6 = "\n".join(R.relatar("lightning", d6["lightning"]))
checa("nenhuma janela fechada" in saida6, "aposta vazia não vira estatística")



print("\n[7] no Crazy Time cada símbolo vale um número de casas")
checa(abs(R.chance_por_giro("crazy_time", ["1"], 1) - 21/54) < 1e-9,
      "o 1 ocupa 21 das 54 casas — 38,9%, não 1,9%",
      R.chance_por_giro("crazy_time", ["1"], 1))
checa(abs(R.chance_por_giro("crazy_time", ["5"], 1) - 7/54) < 1e-9,
      "o 5 vale 13,0%", R.chance_por_giro("crazy_time", ["5"], 1))
checa(abs(R.chance_por_giro("crazy_time", ["CrazyTime"], 1) - 1/54) < 1e-9,
      "o CrazyTime é o único que vale 1/54")
checa(abs(R.chance_por_giro("crazy_time", ["5", "10"], 1) - 11/54) < 1e-9,
      "dois símbolos somam as casas dos dois",
      R.chance_por_giro("crazy_time", ["5", "10"], 1))
checa(abs(R.chance_por_giro("lightning", ["4", "5"], 2) - 2/37) < 1e-9,
      "na roleta continua sendo k/37")
checa(R.chance_por_giro("crazy_time", [], 2) > 0,
      "sem alvos registrados não quebra a conta")

# o caso do log dele: apostou ['5'] e a janela tinha 3 giros
p1 = R.chance_por_giro("crazy_time", ["5"], 1)
jan = R.chance_janela(p1, 3)
checa(0.33 < jan < 0.35, "apostar o 5 por 3 giros acerta ~34% por sorte pura",
      f"{jan:.3f}")
antigo = 1 - (1 - 1/54) ** 3
checa(jan > 6 * antigo,
      "a conta antiga (1/54) subestimava o acaso em mais de 6x — "
      "era isso que virava '5,32x acima do acaso'",
      f"certo {jan:.3f} vs antigo {antigo:.3f}")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("RESULTADO_OK")
