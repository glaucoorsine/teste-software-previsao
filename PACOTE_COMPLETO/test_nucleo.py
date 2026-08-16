# -*- coding: utf-8 -*-
"""Confere o núcleo cuja base de dados são os três estudos dele.

    "desenvolve um do início, onde a base de dados vai ser os três PDFs de
     fato, porque eu acho que ficou muito misturado"

O que este teste cobra é justamente a não-mistura:

  1. a grade dele está fechada -- 960 formulações, 48 famílias, 5 mesas
  2. TODA leitura do núcleo é uma família publicada; nenhuma é invenção minha
  3. cada leitura tem endereço no livro (formulação, página) na mesa certa
  4. as fórmulas fazem o que prometem, em casos plantados de resposta sabida
  5. quem não tem dado se cala, e diz por quê -- inclusive as PENDENTES
  6. a agregação é a IA12 dele: perda normalizada por vigília, ninguém zerado
  7. nada estoura com histórico curto, vazio, sujo ou constante

    python test_nucleo.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import agregacao as A  # noqa: E402
from NUCLEO import base as B  # noqa: E402
from NUCLEO import leituras as L  # noqa: E402

falhas = []
rnd = random.Random(11)


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] a base de dados é o livro dele, e a grade está fechada")

i = B.integridade()
checa(i["formulacoes"] == 960, "as 960 formulações", i["formulacoes"])
checa(i["com_formula"] == 960, "todas com fórmula auditável", i["com_formula"])
checa(not i["puladas"], "nenhuma formulação pulada", i["puladas"][:6])
checa(i["ias"] == 12, "as 12 inteligências", i["ias"])
checa(i["familias"] == 48, "as 48 famílias", i["familias"])
checa(len(i["mesas"]) == 5, "as 5 mesas", sorted(i["mesas"]))
checa(all(v == 192 for v in i["mesas"].values()),
      "192 formulações por mesa, sem sobra nem falta", i["mesas"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] nenhuma leitura é invenção minha")

nomes = [n for n, _f in L.LEITURAS]
publicadas = {f["familia"] for f in B.familias()}
intrusas = [n for n in nomes if n not in publicadas]
checa(not intrusas, "toda leitura é uma família publicada dele", intrusas)

agregadoras = {f["familia"] for f in B.familias() if f["agrega"]}
checa(agregadoras == set(B.FAMILIAS_AGREGADORAS),
      "as agregadoras são F45-F48", sorted(agregadoras))
checa(not (set(nomes) & agregadoras),
      "e nenhuma delas está entre as que leem a mesa",
      sorted(set(nomes) & agregadoras))
checa(len(nomes) == 44, "sobram exatamente 44 leituras", len(nomes))
checa(set(nomes) | agregadoras == publicadas,
      "44 leituras + 4 agregadoras = as 48 famílias",
      sorted(publicadas - (set(nomes) | agregadoras)))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] cada leitura tem endereço no livro, na mesa certa")

for jogo, esperado in (("mega_fire", "MEGA FIRE"), ("lightning", "LIGHTING"),
                       ("immersive", "IMMERSIVE"), ("crazy_time", "CRAZY TIME"),
                       ("crazy_time_a", "CRAZY TIME A")):
    checa(B.mesa_do(jogo) == esperado, f"{jogo} → {esperado}", B.mesa_do(jogo))

# `crazy_time_a` começa com `crazy_time`: sem prefixo mais longo, a mesa A
# citaria a formulação da mesa comum, e citar fonte errada é pior que não citar
checa(B.mesa_do("crazy_time_a_casino") == "CRAZY TIME A",
      "sufixo não faz crazy_time_a cair em crazy_time")
checa(B.classes_de("crazy_time_a_x") == 8, "e leva junto o número de classes",
      B.classes_de("crazy_time_a_x"))

sem_endereco = [n for n, _f in L.LEITURAS if not B.endereco(n, "lightning")]
checa(not sem_endereco, "toda leitura tem endereço no livro", sem_endereco)

n_mf = B.formulacao_de("F01", "mega_fire")
n_lt = B.formulacao_de("F01", "lightning")
checa(n_mf and n_lt and n_mf["n"] != n_lt["n"],
      "mesas diferentes apontam para formulações diferentes",
      (n_mf and n_mf["n"], n_lt and n_lt["n"]))
checa(n_mf and n_mf.get("pagina"), "e a citação traz a página do livro",
      n_mf and n_mf.get("pagina"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] as fórmulas fazem o que prometem")

# F01 · D_t: o que sumiu vai na frente; o que acabou de sair sai do placar
h = [rnd.choice([x for x in range(37) if x != 8]) for _ in range(300)]
h[0] = 21
p, _f = L.f01(h, 37, {})
checa(p and max(p, key=p.get) == "8", "F01 põe o ausente em primeiro",
      sorted(p, key=p.get, reverse=True)[:3])
checa(p.get("21", 0.0) < 0.05, "e tira quem acabou de sair", p.get("21"))

# F13 · transição: depois do 5 vem o 19
h13 = []
for _ in range(400):
    if h13 and h13[-1] == 5 and rnd.random() < 0.8:
        h13.append(19)
    else:
        h13.append(rnd.choice([x for x in range(37) if x != 19]))
h13 = h13[::-1]
h13[0] = 5
p13, _f = L.f13(h13, 37, {})
checa(p13 and max(p13, key=p13.get) == "19", "F13 acha a transição 5→19",
      sorted(p13, key=p13.get, reverse=True)[:3])

# F31 · simetria: setor contíguo plantado tem que ser achado...
SETOR = [5, 24, 16, 33, 1, 20, 14]
viciada = [rnd.randrange(37) for _ in range(500)]
for j in range(0, 500, 3):
    viciada[j] = rnd.choice(SETOR)
p31, f31 = L.f31(viciada, 37, {})
checa(p31, "F31 acha o setor plantado", f31[:52])
checa(p31 and sum(1 for x in p31 if int(x) in SETOR) >= 3,
      "e o que aponta está no setor", sorted(p31)[:6])

# ...e roda honesta NÃO pode acusar vício. Varrer 37 janelas e ficar com a
# maior não é o mesmo que olhar uma; sem o desconto, isto acusava em ~4 de
# cada 10 leituras limpas.
alarmes = 0
for semente in range(100):
    r2 = random.Random(4000 + semente)
    limpa = [r2.randrange(37) for _ in range(250)]
    if L.f31(limpa, 37, {})[0]:
        alarmes += 1
print(f"       alarme falso de vício físico: {alarmes}% em 100 rodas honestas")
checa(alarmes <= 10, "F31 não inventa vício em roda honesta", f"{alarmes}%")

# F37 · hurdle: existência e magnitude são processos separados
h37, m37 = [], []
for _ in range(400):
    x = rnd.randrange(37)
    h37.append(x)
    m37.append(50 if x == 4 else (5000 if x == 9 and rnd.random() < 0.3 else 0))
p37, f37 = L.f37(h37, 37, {"mults": m37})
checa(p37 and "4" in p37 and "9" in p37,
      "F37 enxerga existência (4) e magnitude (9)", sorted(p37)[:8])

# F36 · duplicação: é o erro de captura que mais infla acerto sem aparecer
dup = []
for x in [rnd.randrange(37) for _ in range(150)]:
    dup += [x, x]
_p, f36 = L.f36(dup, 37, {})
checa("duplicado" in f36, "F36 denuncia giro duplicado na captura", f36[:60])
_p, f36b = L.f36([rnd.randrange(37) for _ in range(300)], 37, {})
checa("sem sinal" in f36b, "e fica quieto quando não há duplicação", f36b[:50])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] quem não tem dado se cala, e diz por quê")

ct = [rnd.randrange(8) for _ in range(300)]
r_ct = L.executar(ct, 8, {})
for quem in ("F18", "F19", "F29", "F31"):
    checa(quem not in r_ct["palpites"],
          f"{quem} não opina em mesa sem roda física",
          r_ct["palpites"].get(quem))
checa("F37" not in r_ct["palpites"], "F37 não opina sem multiplicador")
checa(r_ct["apontaram"] >= 8, "mas as demais leem o Crazy Time",
      r_ct["apontaram"])

r_rol = L.executar([rnd.randrange(37) for _ in range(400)], 37, {})
checa(all(r_rol["falas"].get(n) for n, _f in L.LEITURAS),
      "toda leitura deixa uma fala, falando ou calando")
erros = [n for n in r_rol["falas"] if "erro:" in (r_rol["falas"][n] or "")]
checa(not erros, "nenhuma estourou", erros)

# a dívida é declarada, não escondida
for n in L.PENDENTES:
    checa("PENDENTE" in (r_rol["falas"].get(n) or ""),
          f"{n} declara que está pendente em vez de sumir",
          r_rol["falas"].get(n))
checa(set(L.PENDENTES) <= set(dict(L.LEITURAS)),
      "e toda pendente é uma família real", sorted(L.PENDENTES))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] a agregação é a IA12 dele")

checa(A.f45_pesos({}) == {}, "F45 sem histórico não penaliza ninguém")
w = A.f45_pesos({"F01": 0.2, "F05": 0.9, "F13": 0.5}, {"F01": 1, "F05": 1, "F13": 1})
checa(w["F01"] > w["F13"] > w["F05"], "quem erra menos pesa mais",
      {k: round(v, 3) for k, v in w.items()})
checa(all(v > 0 for v in w.values()), "e ninguém é zerado", w)
checa(abs(sum(w.values()) - len(w)) < 1e-6, "a média do peso segue 1,0",
      sum(w.values()))

# F46 · a correção que eu não tinha visto: metade das leituras se cala quase
# sempre. Contar a perda nos giros em que estavam CALADAS puniria prudência.
# Aqui as duas erraram por igual quando falaram, mas uma falou 10x menos.
w46 = A.f45_pesos({"prudente": 2.0, "faladeira": 20.0},
                  {"prudente": 10, "faladeira": 100})
checa(abs(w46["prudente"] - w46["faladeira"]) < 1e-9,
      "quem fala pouco não é punido pelo silêncio (F46)",
      {k: round(v, 4) for k, v in w46.items()})
reg = A.f46_arrependimento({"a": 1.0, "b": 3.0}, {"a": 10, "b": 10})
checa(reg["a"] == 0 and reg["b"] > 0, "o arrependimento é contra o melhor", reg)

# F47 · robustez: concordância entre as leituras que falaram
pl = {"F01": {"7": 1.0}, "F05": {"7": 0.8}, "F13": {"22": 1.0}}
checa(abs(A.f47_robustez(pl, "7") - 2 / 3) < 1e-9,
      "F47 mede quantas concordam com a classe", A.f47_robustez(pl, "7"))

# F48 · memória com dormência: quem some volta a valer, não carrega o erro
mem = A.f48_memoria({}, {"F01": False, "F05": True})
checa(mem["F01"] < 0 < mem["F05"], "F48 registra acerto e erro", mem)
esquecido = A.f48_memoria(mem, {})
checa(abs(esquecido["F01"]) < abs(mem["F01"]),
      "e quem dorme vai esquecendo o erro antigo", (mem["F01"], esquecido["F01"]))

# a perda tem que MUDAR a ponta, senão o peso é enfeite
pl2 = {"F01": {"7": 1.0}, "F05": {"22": 0.95}}
sem = A.consenso(pl2, {}, {})
com = A.consenso(pl2, {"F01": 3.0, "F05": 0.0}, {"F01": 1, "F05": 1})
checa(sem["ordem"][0] == "7", "sem perda vence o peso bruto", sem["ordem"])
checa(com["ordem"][0] == "22", "com perda acumulada a ponta muda", com["ordem"])
checa(com["quem"]["22"] == ["F05"], "e o placar diz quem votou", com["quem"])
checa("robustez" in com and com["robustez"], "e a robustez de cada classe")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] o núcleo inteiro acha o que foi plantado")

m = [rnd.choice([0, 0, 0, 50, 100, 500]) for _ in range(500)]
r = L.executar(viciada, 37, {"mults": m})
ag = A.consenso(r["pesos"], k=12)
achou = sum(1 for x in ag["ordem"] if int(x) in SETOR)
print(f"       setor plantado {SETOR} → top-12 {ag['ordem']}")
checa(achou >= 4, f"pelo menos 4 dos 7 plantados no top-12", achou)

# e em roda honesta o consenso não pode "achar" o mesmo setor
limpa = [rnd.randrange(37) for _ in range(500)]
ag2 = A.consenso(L.executar(limpa, 37, {})["pesos"], k=12)
achou2 = sum(1 for x in ag2["ordem"] if int(x) in SETOR)
checa(achou2 < achou, "e em roda honesta acha menos", (achou, achou2))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] não quebra com dado curto, vazio, sujo ou constante")

for seq, nc in (([], 37), ([1], 37), ([1, 2, 3], 37),
                ([None, "", "x", 5, 5], 37), (list(range(37)), 37),
                ([0] * 300, 8), ([rnd.randrange(8) for _ in range(9)], 8)):
    try:
        rr = L.executar(seq, nc, {"mults": [0, 0]})
        A.consenso(rr["pesos"], k=12)
    except Exception as e:
        checa(False, "aguenta entrada ruim", f"{type(e).__name__} em {seq[:4]}")
        break
    ruins = [n for n in rr["falas"] if "erro:" in (rr["falas"][n] or "")]
    if ruins:
        checa(False, "aguenta entrada ruim", f"{ruins} em {seq[:4]}")
        break
else:
    checa(True, "aguenta histórico curto, vazio, sujo e constante")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("NUCLEO_OK")
