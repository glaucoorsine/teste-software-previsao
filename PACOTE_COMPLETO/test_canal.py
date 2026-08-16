# -*- coding: utf-8 -*-
"""Confere o canal anunciado — a base da v103 virada para números.

    "descoberta de multiplicador que estava na 103... eu quero que você use no
     sentido de qual foi a base que você utilizou"

A base daquela técnica é uma observação sobre o jogo, não uma fórmula: o
sorteio de multiplicador é ANUNCIADO a cada rodada, saindo ou não o número.
Isso dá de 3 a 5 observações por giro contra 1 do resultado.

O teste cobra as cinco coisas que fazem essa ideia valer ou não valer:

  1. o canal é MESMO mais denso que o resultado -- se não for, não há base
  2. onde o viés é compartilhado, o acoplamento aparece e o canal vota
  3. onde a mesa é honesta, o acoplamento NÃO aparece e o canal se cala
  4. mesa sem anúncio (Immersive) não recebe pergunta sem objeto
  5. captura quebrada é DENUNCIADA -- foi o defeito que quase matou a v103

    python test_canal.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import canal_anunciado as C  # noqa: E402

falhas = []
rnd = random.Random(3)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


SETOR = [5, 24, 16, 33, 1, 20, 14]


def mesa(n=400, vies=0.0, anuncios=(1, 5), vies_anuncio=None):
    """Fabrica histórico. `vies` puxa a roda para o setor; `vies_anuncio`, o anúncio."""
    va = vies if vies_anuncio is None else vies_anuncio
    h = []
    for _ in range(n):
        saiu = rnd.choice(SETOR) if rnd.random() < vies else rnd.randrange(37)
        lucky = [{"n": (rnd.choice(SETOR) if rnd.random() < va
                        else rnd.randrange(37)),
                  "x": rnd.choice([50, 100, 500])}
                 for _ in range(rnd.randint(*anuncios))]
        h.append({"n": saiu, "tags": [{"lucky": lucky}]})
    return h


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a base: o canal é mais denso que o resultado")

h = mesa(400, vies=0.34)
rds = C.rodadas(h, "lightning")
d = C.densidade(rds)
checa(d["giros"] == 400, "leu os 400 giros", d["giros"])
checa(d["por_giro"] >= 2.5,
      "o canal dá 3x mais observações por giro que o resultado",
      round(d["por_giro"], 2))
canal = C.serie_do_canal(rds)
res = C.serie_de_resultados(rds)
checa(len(canal) > len(res) * 2,
      "a série do canal é mais que o dobro da de resultados",
      (len(canal), len(res)))
checa(all(0 <= x <= 36 for x in canal),
      "e vive no MESMO domínio do resultado (0..36)")

# a vantagem tem que valer para o Mega Fire também, que usa outra chave
hmf = [{"n": rnd.randrange(37),
        "tags": [{"fire_nums": [{"n": rnd.randrange(37), "x": 100}
                                for _ in range(2)]}]} for _ in range(100)]
checa(len(C.serie_do_canal(C.rodadas(hmf, "mega_fire"))) == 200,
      "lê fire_nums do Mega Fire, não só lucky do Lightning")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] onde o viés é compartilhado, o canal prova e vota")

r = C.ler(h, "lightning", 37)
ac = r.get("acoplamento") or {}
print(f"       acoplamento: {ac.get('motivo','')}")
checa(ac.get("existe"), "o acoplamento é detectado", ac.get("motivo"))
checa(ac.get("razao", 0) > 1.2, "e é forte", round(ac.get("razao", 0), 2))
checa(ac.get("p", 1) < 0.05, "e significativo", ac.get("p"))
checa(r.get("vota"), "então o canal vota")
checa(r.get("apontaram", 0) >= 10,
      "e várias famílias dele leem o canal", r.get("apontaram"))
checa(all(n.startswith("CANAL_") for n in r["palpites"]),
      "os votos vêm marcados como do canal, não misturados",
      list(r["palpites"])[:3])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] onde a mesa é honesta, o canal se cala")

honesta = mesa(400, vies=0.0)
r2 = C.ler(honesta, "lightning", 37)
ac2 = r2.get("acoplamento") or {}
print(f"       acoplamento: {ac2.get('motivo','')}")
checa(not ac2.get("existe"), "nenhum acoplamento em mesa honesta",
      ac2.get("motivo"))
checa(not r2.get("vota"), "e o canal NÃO vota")
checa(not r2["palpites"], "não empurra palpite nenhum", len(r2["palpites"]))

# o caso que separa ideia boa de medida: anúncio viciado, roda honesta.
# O canal é denso e tem estrutura, mas ela não se transfere para o giro.
so_anuncio = mesa(400, vies=0.0, vies_anuncio=0.5)
r3 = C.ler(so_anuncio, "lightning", 37)
checa(not r3.get("vota"),
      "anúncio viciado com roda honesta também não vota",
      (r3.get("acoplamento") or {}).get("motivo"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] mesa sem anúncio não recebe pergunta sem objeto")

checa(not C.tem_canal("immersive"), "Immersive não tem canal")
checa(C.tem_canal("lightning") and C.tem_canal("crazy_time"),
      "as outras têm")
ri = C.ler([{"n": 1}] * 200, "immersive", 37)
checa(not ri.get("vota") and "não tem anúncio" in ri.get("motivo", ""),
      "e o núcleo diz isso em vez de inventar", ri.get("motivo"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] captura quebrada é denunciada, não ignorada")

# Foi o defeito que quase matou a v103: a captura só guardava o anúncio quando
# ele calhava de ser o número sorteado -- 10 registros de umas 600 premiações.
quebrada = [{"n": x, "tags": [{"lucky": [{"n": x, "x": 50}]}] if i % 20 == 0
             else []}
            for i, x in enumerate(rnd.randrange(37) for _ in range(400))]
rq = C.ler(quebrada, "lightning", 37)
checa(not rq.get("vota"), "canal magro não vota")
checa("captura" in rq.get("motivo", ""),
      "e o motivo aponta a captura, que é onde está o defeito",
      rq.get("motivo", "")[:70])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] não quebra com entrada ruim")

for hh in ([], [{}], [{"n": None}], [{"n": 5, "tags": None}],
           [{"n": 5, "tags": [{"lucky": [{"n": "x"}]}]}],
           [{"n": 5, "tags": [{"lucky": None}]}], ["lixo", 42]):
    try:
        C.ler(hh, "lightning", 37)
        C.rodadas(hh, "crazy_time")
    except Exception as e:
        checa(False, "aguenta histórico malformado", f"{type(e).__name__} em {hh}")
        break
else:
    checa(True, "aguenta histórico vazio, nulo e malformado")

print("\n[7] o painel cabe na tela")
print("       " + C.resumo(h, "lightning", 37).replace("\n", "\n       "))

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("CANAL_OK")
