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

# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] a MESA ensina quanto cada eixo vale — o peso não é meu")

# Ele pegou a incoerência: eu dizia "eixos, não regras minhas" e logo abaixo
# decretava hora=1.0, repeticao=0.6. O peso É a regra.
#
# Aqui a plateia é PERSISTENTE (em blocos), como na vida real -- e ela decide o
# prêmio. O software tem de descobrir isso sozinho.
from NUCLEO import forca_dos_eixos as FE  # noqa: E402


def mesa_publico_manda(semente=5, giros=700):
    rnd = random.Random(semente)
    linhas, pub, gente = [], {}, 200
    for i in range(giros):
        if i % 40 == 0:
            gente = rnd.choice([180, 1300])
        hora = (i // 25) % 24
        cheia = gente > 800
        saiu = (rnd.choice(SETOR) if (cheia and rnd.random() < 0.5)
                else rnd.randrange(37))
        paga = rnd.random() < (0.60 if cheia else 0.08)
        fogo = [{"n": n, "x": (100 if (n == saiu and paga) else None)}
                for n in rnd.sample(SETOR + [rnd.randrange(37)], 4)]
        linhas.append({"n": saiu,
                       "settled": f"2026-08-{1+i//96:02d}T{hora:02d}:{i%60:02d}:00Z",
                       "tags": [{"lucky": fogo}], "_g": gente})
    linhas.reverse()
    for i, l in enumerate(linhas):
        pub[i] = l["_g"]
    return linhas, pub


ln7, pb7 = mesa_publico_manda()
r7 = S.ler(ln7, 37, publico_por_giro=pb7, publico_agora=pb7.get(0),
           k_alvos=6, jogo="_teste_eixos")
med = r7.get("medida_eixos") or {}
det = med.get("detalhe") or {}
checa(bool(med.get("aprendeu")), "a mesa ensinou algum peso", med.get("aprendeu"))
for l in FE.resumo("_teste_eixos", med):
    print(f"       {l[:112]}")
dp = (det.get("publico") or {})
checa((dp.get("d") or 0) > 0.8,
      "e o PÚBLICO aparece como eixo forte, porque nesta mesa ele manda",
      dp.get("d"))
checa((dp.get("peso") or 0) > 1.5, "com peso alto, não o 1.0 que eu decretava",
      dp.get("peso"))
checa((dp.get("media_pagou") or 0) > (dp.get("media_nao") or 0),
      "e diz a direção: paga mais com mesa cheia",
      (dp.get("media_pagou"), dp.get("media_nao")))

# amostra pequena não aprende nada -- peso neutro e diz que é neutro
curto7, pc7 = mesa_publico_manda(7, giros=80)
m2 = FE.medir(S.Memoria(curto7, pc7).momentos, curto7, S._mult_do_giro)
checa(all(v.get("peso") == 1.0 for v in (m2.get("detalhe") or {}).values()),
      "com pouca amostra, todo eixo fica no peso neutro",
      {k: v.get("peso") for k, v in (m2.get("detalhe") or {}).items()})
checa(not m2.get("aprendeu"), "e declara que NÃO aprendeu")

# o peso muda a busca de verdade
d_neutro = S.distancia(S.descrever(ln7, 0, pb7), S.descrever(ln7, 200, pb7))
d_apren = S.distancia(S.descrever(ln7, 0, pb7), S.descrever(ln7, 200, pb7),
                      pesos=med.get("pesos"))
checa(d_neutro is not None and d_apren is not None and
      abs(d_neutro - d_apren) > 1e-6,
      "e o peso aprendido muda a distância (senão seria enfeite)",
      (d_neutro, d_apren))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] o SEMÁFORO: é bom momento? e o aviso só no verde")

from NUCLEO import semaforo as SM  # noqa: E402

_forte = {"detalhe": {"publico": {"d": 1.69, "media_pagou": 1263,
                                  "media_nao": 457},
                      "ritmo_mult": {"d": 0.94}}}
_fraco = {"detalhe": {"publico": {"d": 0.05, "media_pagou": 700,
                                  "media_nao": 690}}}

verde = SM.avaliar(
    situacao={"fala": True, "n": 40, "razao": 2.1, "lift_mult": 2.4,
              "pagou": .18, "pagou_geral": .05, "medida_eixos": _forte},
    publico=1300, pico_publico=800, ritmo_agora=.18, ritmo_normal=.05)
checa(verde["cor"] == SM.VERDE, "mesa cheia + prêmio em rajada = VERDE",
      verde["cor"])
checa(verde["avisar"], "e o aviso sai")
checa(any("público separa" in m for m in verde["motivos"]),
      "e o motivo cita a MEDIDA que o autoriza", verde["motivos"][:1])

# A REGRA CENTRAL: mesa cheia só é razão se o público separar NESTA mesa.
igual = SM.avaliar(
    situacao={"fala": True, "n": 40, "razao": 1.0, "lift_mult": 1.0,
              "pagou": .05, "pagou_geral": .05, "medida_eixos": _fraco},
    publico=1300, pico_publico=800, ritmo_agora=.05, ritmo_normal=.05)
checa(igual["cor"] != SM.VERDE,
      "mesa cheia SEM medida que separe NÃO dá verde (isso é o que impede "
      "virar astrologia)", igual["cor"])
checa(not igual["avisar"], "e o celular fica calado")
checa(any("separou" in o.lower() for o in igual["observacoes"]),
      "mas o público aparece como observação, não é escondido",
      igual["observacoes"][:1])

ruim = SM.avaliar(
    situacao={"fala": True, "n": 40, "razao": 0.7, "lift_mult": 0.5,
              "pagou": .02, "pagou_geral": .05, "medida_eixos": _forte},
    publico=200, pico_publico=800,
    placar_recente={"n": 22, "ok": 3, "acaso": 0.30})
checa(ruim["cor"] == SM.VERMELHO, "abaixo do acaso = VERMELHO", ruim["cor"])
checa(any("não servem para este momento" in a for a in ruim["autocritica"]),
      "e a autocrítica diz o que fazer, não só que errou",
      ruim["autocritica"][-1:])

# "está repetindo demais? sim? porque? e mudar ou nao"
rep = SM.avaliar(situacao={"fala": False, "nota": "só 4 momentos parecidos"},
                 ultimas_sugestoes=[["5", "9"]] * 7)
checa(rep["repeticao"]["repetiu"] >= SM.REPETE_DEMAIS,
      "conta a repetição da sugestão", rep["repeticao"]["repetiu"])
checa(bool(rep["repeticao"]["porque"]), "diz POR QUE está repetindo",
      rep["repeticao"]["porque"][:60])
checa(rep["repeticao"]["mudar"] is True,
      "e opina se deve mudar a lista")
# repetição por mesa travada é legítima pelo critério dele, e não pede mudança
variando = SM.avaliar(situacao={"fala": False, "nota": "x"},
                      ultimas_sugestoes=[["1"], ["2"], ["3"], ["4"], ["5", "9"],
                                         ["5", "9"], ["5", "9"], ["5", "9"],
                                         ["5", "9"]])
checa(variando["repeticao"]["mudar"] is False,
      "mas se a lista variou antes, insistir no atrasado é o critério DELE")

# o aviso só no verde, e a CENTRAL respeita
_ce2 = (RAIZ / "CENTRAL.py").read_text(encoding="utf-8")
checa("_NaoAvisar" in _ce2 and 'raise _NaoAvisar()' in _ce2,
      "a CENTRAL tranca a notificação fora do verde")
checa("SEM_AVISO cor=" in _ce2,
      "e registra no log que ficou calada, com a cor e o motivo")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("SITUACAO_OK")
