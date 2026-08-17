# -*- coding: utf-8 -*-
"""As quatro falhas que ele encontrou e rastreou até a linha.

Ele não reclamou — ele auditou, e apontou arquivo e linha de cada uma. As
quatro eram reais, e três estavam invisíveis: o dado morria antes de chegar na
tela, sem erro nenhum aparecer.

  1. `hist_buffer.DOMAIN` sem `crazy_time_a` → o filtro apagava a mesa inteira
  2. o fallback HTML declarava `novo_head=True` sempre → o mesmo "5" virava
     giro novo a cada consulta
  3. `agentes_multiplicador.extrair()` lia só `lucky` → a Mega Fire, que grava
     `fire_nums`, chegava vazia no Caçador
  4. `capturar()` montava `mults` só das tags `x` → o anúncio inteiro sumia

    python test_quatro_falhas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import fluxo_captura as F  # noqa: E402
from academia_autonoma.agentes_multiplicador import extrair  # noqa: E402
from hist_buffer import DOMAIN  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] o domínio de cada mesa — sem ele o filtro apaga tudo")

MESAS = ("mega_fire", "lightning", "crazy_time", "crazy_time_a")
for m in MESAS:
    checa(m in DOMAIN, f"{m} tem domínio declarado", sorted(DOMAIN))
    checa(bool(DOMAIN.get(m)), f"  e o domínio não é vazio", DOMAIN.get(m))

# o teste que pega a regressão: eventos válidos têm de sobreviver ao filtro
ct = [{"n": "5", "valor": "5", "settled": "2026-08-17T10:00:00Z"},
      {"n": "CoinFlip", "valor": "CoinFlip", "settled": "2026-08-17T10:01:00Z"},
      {"n": "Pachinko", "valor": "Pachinko", "settled": "2026-08-17T10:02:00Z"}]
for m in ("crazy_time", "crazy_time_a"):
    r = F._purge_invalid([dict(e) for e in ct], m)
    checa(len(r) == 3, f"{m}: os 3 giros sobrevivem ao filtro", len(r))

rol = [{"n": "17", "valor": "17", "settled": "2026-08-17T10:00:00Z"}]
checa(len(F._purge_invalid(list(rol), "lightning")) == 1,
      "roleta continua passando")
# e o filtro tem de continuar filtrando o que é lixo de verdade
lixo = [{"n": "CoinFlip", "valor": "CoinFlip", "settled": "2026-08-17T10:00:00Z"}]
checa(len(F._purge_invalid(list(lixo), "lightning")) == 0,
      "símbolo de Crazy Time não entra em roleta")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] a mesma página HTML não pode virar giro novo")

# A página do gamblingcounting não traz horário nem identificador. O código
# declarava `novo_head=True` sempre, e a tela inventava 5#s1, 5#s2, 5#s3...
guardados = (F.capturar_html, F.fetch_paginas, F.enderecos_para)
try:
    F._ultimo_head_html.clear()
    pagina = [{"n": "5", "sec": "5", "settled": None, "tags": []},
              {"n": "1", "sec": "1", "settled": None, "tags": []}]
    F.capturar_html = lambda ds: [dict(x) for x in pagina]
    F.fetch_paginas = lambda *a, **k: ([], "HTTP 404")
    F.enderecos_para = lambda ds: ["http://inexistente"]
    import descobridor_endereco as D
    d_orig = D.descobrir
    D.descobrir = lambda *a, **k: None
    try:
        c1 = F.capturar("crazy_time_a", duration=1)
        c2 = F.capturar("crazy_time_a", duration=1)
        c3 = F.capturar("crazy_time_a", duration=1)
        checa(c1["novo_head"], "a primeira leitura é giro novo")
        checa(not c2["novo_head"] and not c3["novo_head"],
              "reler a MESMA página não é giro novo",
              (c2["novo_head"], c3["novo_head"]))
        checa(c1["head_id"] and c1["head_id"] == c2["head_id"],
              "e o identificador é estável", (c1["head_id"], c2["head_id"]))
        checa(c1["head_id"] is not None,
              "a fonte HTML passa a ter identificador", c1["head_id"])

        pagina.insert(0, {"n": "CoinFlip", "sec": "CoinFlip",
                          "settled": None, "tags": []})
        c4 = F.capturar("crazy_time_a", duration=1)
        checa(c4["novo_head"], "página que MUDOU é giro novo")
        checa(c4["head_id"] != c1["head_id"], "com identificador diferente")
    finally:
        D.descobrir = d_orig
finally:
    F.capturar_html, F.fetch_paginas, F.enderecos_para = guardados

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] o Caçador enxerga fire_nums, não só lucky")

evs = [{"valor": "7", "tags": [{"fire_nums": [{"n": 7, "x": 100},
                                              {"n": 12, "x": 50}]}]},
       {"valor": "20", "tags": [{"lucky": [{"n": 20, "x": 500}]}]},
       {"valor": "3", "tags": []},
       {"valor": "9", "tags": [{"fire_nums": [{"n": 4, "x": 200}]}]}]
nums, batido, rodada = extrair(evs)
checa(nums == [7, 20, 3, 9], "lê os números", nums)
checa(rodada[0] and len(rodada[0]) == 2,
      "a rodada de fire_nums chega inteira (era vazia)", rodada[0])
checa(rodada[1] and rodada[1][0]["n"] == 20,
      "e lucky continua funcionando", rodada[1])
checa(batido[0] == 100,
      "o multiplicador que BATEU sai do fire_nums", batido[0])
checa(batido[1] == 500, "e do lucky", batido[1])
checa(batido[2] == 0, "rodada sem marca dá zero", batido[2])
checa(batido[3] == 0,
      "anúncio que não bateu não vira multiplicador pago", batido[3])
checa(rodada[3] and rodada[3][0]["n"] == 4,
      "mas o anúncio fica registrado mesmo sem pagar", rodada[3])

# o caso que motivou tudo: 254 rodadas de Mega Fire chegando vazias
so_fire = [{"valor": str(i % 37), "tags": [{"fire_nums": [{"n": i % 37, "x": 50}]}]}
           for i in range(254)]
_n, _b, _r = extrair(so_fire)
cheias = sum(1 for x in _r if x)
checa(cheias == 254, f"as 254 rodadas de Mega Fire chegam cheias", cheias)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] `mults` da captura leva o anúncio inteiro")

linhas = [{"n": 7, "settled": "2026-08-17T10:00:00Z",
           "tags": [{"fire_nums": [{"n": 7, "x": 100}, {"n": 12, "x": 50}]}]},
          {"n": 20, "settled": "2026-08-17T10:01:00Z",
           "tags": [{"x": 500}, {"lucky": [{"n": 20, "x": 500}]}]}]
mults = []
for e in linhas:
    for t in (e.get("tags") or []):
        if "x" in t:
            mults.append({"n": e.get("n"), "x": t["x"]})
        for ch in ("lucky", "fire_nums"):
            for it in (t.get(ch) or []):
                if isinstance(it, dict) and it.get("x"):
                    mults.append({"n": int(it["n"]), "x": int(it["x"])})
checa(any(m["n"] == 12 for m in mults),
      "o número anunciado que NÃO saiu também entra em mults", mults)
checa(len(mults) >= 3, "e o anúncio inteiro chega", len(mults))

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("QUATRO_FALHAS_OK")
