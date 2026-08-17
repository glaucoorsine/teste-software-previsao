# -*- coding: utf-8 -*-
"""As obrigações de aprendizado que ele mandou montar.

    "ver o que funcionou naquele momento para aplicar em momentos iguais?
     perceber quantidade de pessoas em momentos de pico de multiplicadores?
     sinais de que muitos multiplicadores virão?
     percepção de momentos iguais ou parecidos? melhores horários?"

    "não voce está errado, ja medi e tudo que eu te disse influencia,
     comece a pensar e montar estas obrigações na ia poderosa"

Ele mediu ao vivo. O que este teste cobra não é se a percepção dele é
verdadeira -- é se o MECANISMO a enxerga quando ela existe e se cala quando não
existe. Se ele achar sinal numa mesa construída sem sinal, não serve para nada.

  1. o momento é descrito com os eixos que ele nomeou (hora, público, ritmo)
  2. momentos parecidos são achados no PASSADO, nunca no futuro
  3. numa mesa com o padrão dele plantado, o mecanismo vê
  4. numa mesa SEM padrão, não inventa  ← o que reprovou a primeira versão
  5. o público chega até o motor (antes morria na tela)
  6. e a Situação entra no consenso como fonte, com o n que a sustenta

    python test_situacao.py
"""
from __future__ import annotations

import os
import statistics
import tempfile

os.environ.setdefault("LAB_MEMORIA_DIR", tempfile.mkdtemp())

import random  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


from NUCLEO import situacao as S  # noqa: E402

SETOR = [5, 24, 16, 33, 1, 20, 14]


def mesa(semente: int, viciada: bool, giros: int = 600):
    """Uma mesa com ou sem a percepção dele plantada.

    Viciada: das 20h às 23h a mesa enche E os multiplicadores vêm em rajada E o
    setor sai mais. Honesta: nada disso tem relação com hora nem com público.
    """
    rnd = random.Random(semente)
    linhas, pub = [], {}
    for i in range(giros):
        hora = (i // 25) % 24
        pico = 20 <= hora <= 23
        if viciada:
            saiu = (rnd.choice(SETOR) if (pico and rnd.random() < 0.55)
                    else rnd.randrange(37))
            paga = rnd.random() < (0.55 if pico else 0.12)
        else:
            saiu = rnd.randrange(37)
            paga = rnd.random() < 0.30
        fogo = [{"n": n, "x": (100 if (n == saiu and paga) else None)}
                for n in rnd.sample(SETOR + [rnd.randrange(37)], 4)]
        linhas.append({"n": saiu,
                       "settled": f"2026-08-{1 + i//96:02d}T{hora:02d}:{i%60:02d}:00Z",
                       "tags": [{"lucky": fogo}]})
    linhas.reverse()                                  # recente primeiro
    for i in range(len(linhas)):
        h = S._hora_de(linhas[i]["settled"])
        pub[i] = (rnd.randint(900, 1400) if (viciada and h and 20 <= h <= 23)
                  else rnd.randint(120, 1400))
    return linhas, pub


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] o momento é descrito com os eixos que ele nomeou")

linhas, pub = mesa(11, True)
m = S.descrever(linhas, 0, pub)
checa(m is not None, "descreve o momento de agora")
if m:
    print(f"       {m.como_texto()}")
    checa(m.hora is not None, "tem HORA do dia", m.hora)
    checa(m.publico, "tem PÚBLICO", m.publico)
    checa(m.seca_mult is not None, "tem seca de multiplicador", m.seca_mult)
    checa(m.ritmo_mult is not None, "tem ritmo de multiplicador", m.ritmo_mult)
checa(abs((S._hora_de("2026-08-17T22:30:00Z") or 0) - 22.5) < 0.01,
      "a hora é lida do carimbo", S._hora_de("2026-08-17T22:30:00Z"))
# a hora é circular: 23h e 00h são vizinhas, não opostas
checa(S._dif_circular(23.5, 0.5) == 1.0,
      "23h30 e 00h30 distam 1 hora, não 23", S._dif_circular(23.5, 0.5))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] momentos parecidos vêm do PASSADO, nunca do futuro")

mem = S.Memoria(linhas, pub)
alvo = S.descrever(linhas, 100, pub)
viz = mem.parecidos(alvo)
checa(bool(viz), "acha vizinhos", len(viz))
# recente-primeiro: o passado de `i` são os índices MAIORES
checa(all(v.i > alvo.i for _d, v in viz),
      "TODO vizinho é anterior ao momento consultado (nada de futuro)",
      [v.i for _d, v in viz[:4]])
checa(all(v.i >= alvo.i + S.SEPARACAO for _d, v in viz),
      "e nenhum está colado (vizinho colado infla o n sem informar)",
      min((v.i - alvo.i) for _d, v in viz))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] com o padrão dele plantado, o mecanismo VÊ")

r = S.ler(linhas, 37, publico_por_giro=pub, publico_agora=pub.get(0), k_alvos=6)
for l in S.resumo(r):
    print(f"       {l[:104]}")
checa(r.get("fala"), "opina", r.get("nota"))
checa((r.get("lift_mult") or 0) > 1.5,
      "e vê o sinal de multiplicador à frente", r.get("lift_mult"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] sem padrão, NÃO inventa — o controle que reprovou a 1ª versão")

# A primeira versão escolhia os números pelos vizinhos e media a taxa NOS
# MESMOS vizinhos. Numa mesa sem relação alguma, dava 2,70x de razão média:
# ilusão inteira, a mesma inflação por seleção que a Régua dele condena.
# Agora metade da vizinhança escolhe e a outra metade mede.
def mede(viciada: bool, sementes=range(6)):
    rs, lifts = [], []
    for s in sementes:
        ln, pb = mesa(100 + s, viciada)
        x = S.ler(ln, 37, publico_por_giro=pb, publico_agora=pb.get(0), k_alvos=6)
        if x.get("fala"):
            rs.append(x["razao"])
            lifts.append(x["lift_mult"])
    return rs, lifts


r_h, l_h = mede(False)
r_v, l_v = mede(True)
print(f"       honesta   razão {statistics.mean(r_h):.2f}x  "
      f"(min {min(r_h):.2f} max {max(r_h):.2f})   mult {statistics.mean(l_h):.2f}x")
print(f"       viciada   razão {statistics.mean(r_v):.2f}x  "
      f"(min {min(r_v):.2f} max {max(r_v):.2f})   mult {statistics.mean(l_v):.2f}x")
checa(statistics.mean(r_h) < 1.5,
      "em mesa honesta a razão fica perto de 1 (era 2.70x antes da correção)",
      statistics.mean(r_h))
checa(min(r_h) < 1.0,
      "e as sessões honestas passam por baixo de 1 — oscila, não puxa",
      min(r_h))
checa(statistics.mean(r_v) > statistics.mean(r_h),
      "e a viciada fica ACIMA da honesta", (statistics.mean(r_v),
                                            statistics.mean(r_h)))
checa(statistics.mean(l_h) < 1.2 and statistics.mean(l_v) > 2.0,
      "o sinal de multiplicador separa com folga",
      (statistics.mean(l_h), statistics.mean(l_v)))

# histórico curto não opina
curto, pc = mesa(3, True, giros=40)
checa(not S.ler(curto, 37, publico_por_giro=pc).get("fala"),
      "com histórico curto se cala em vez de chutar")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] o público chega até o motor")

# Antes ele era coletado, mostrado e gravado na autópsia -- e `jogadores` não
# aparecia UMA vez em ia_modulos.py. A percepção dele estava sendo registrada
# e ignorada.
_ia = (RAIZ / "ia_modulos.py").read_text(encoding="utf-8")
_ce = (RAIZ / "CENTRAL.py").read_text(encoding="utf-8")
_wk = (RAIZ / "worker_process.py").read_text(encoding="utf-8")
checa("jogadores=None" in _ia, "processar() aceita jogadores")
checa('"jogadores": self.jogadores' in _ce, "a CENTRAL manda o número")
checa('jogadores=dados.get("jogadores")' in _wk, "o worker repassa")
checa("publico_agora=jogadores" in _ia, "e a Situação usa")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] a Situação entra no consenso como fonte")

import ia_modulos as M  # noqa: E402

ln, pb = mesa(21, True)
out = M.PipelinePerceptivo("lightning").processar(
    [l["n"] for l in ln], 0, 0,
    settled=[l["settled"] for l in ln], linhas=ln,
    jogadores=pb.get(0)) or {}
msgs = out.get("msgs") or []
diz = [m for m in msgs if "Situação" in m or "Multiplicador à frente" in m]
checa(bool(diz), "a Situação aparece no log da volta", diz[:1])
for d in diz[:3]:
    print(f"       {d[:100]}")
hip = next((m for m in msgs if m.startswith("[Hipóteses]")), "")
checa("SITUACAO" in hip, "e vota junto das outras fontes", hip[:90])

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("SITUACAO_OK")
