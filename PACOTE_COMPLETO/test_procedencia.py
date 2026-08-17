# -*- coding: utf-8 -*-
"""A ligação com os três PDFs — provada quebrando.

    "Conclusão: a ligação aos PDFs é indireta, parcial e não verificável.
     O sistema executa interpretações pré-codificadas e pequenos resumos;
     ele não 'lê os três PDFs' durante a execução."

Ele estava certo. Este teste existe porque a correção só vale se der para
derrubá-la: tira-se o PDF da pasta e as doze inteligências têm de emudecer. Se
alguma continuar falando, a ligação é enfeite de novo.

  1. o leitor abre os três tratados e lê texto com acento
  2. o índice acha as fichas, com página e sha256 de cada uma
  3. a fórmula sai do PDF, não do meu código
  4. o índice é reconstruído quando o PDF muda
  5. COM os PDFs as doze falam; SEM eles, nenhuma
  6. e nada cai para a transcrição por trás

    python test_procedencia.py
"""
from __future__ import annotations

import os
import tempfile

os.environ.setdefault("LAB_MEMORIA_DIR",
                      tempfile.mkdtemp(prefix="lab_memoria_teste_"))

import random  # noqa: E402
import shutil  # noqa: E402
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


from NUCLEO import indice_tratados as IT  # noqa: E402
from NUCLEO import procedencia as P  # noqa: E402
from NUCLEO.leitor_pdf import abrir  # noqa: E402

PDFS = IT.pdfs_presentes()

# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] o leitor abre os tratados sem depender de biblioteca externa")

checa(bool(PDFS), "há PDF em tratados/", [p.name for p in PDFS])
if not PDFS:
    print("\n  Sem os PDFs não há o que testar. Eles fazem parte do pacote.")
    print("FALHAS:", falhas or ["tratados/ vazia"])
    sys.exit(1)

for p in PDFS:
    t = abrir(p)
    pg = t.paginas()
    cheias = sum(1 for x in pg if x.strip())
    print(f"       {p.name[:44]:<44} {len(pg):>5}p  {cheias:>5} com texto")
    checa(t.erro is None, f"{p.name}: abriu sem erro", t.erro)
    checa(len(pg) > 100, f"{p.name}: tem as páginas", len(pg))
    checa(cheias == len(pg), f"{p.name}: TODA página deu texto", cheias)
    checa(len(t.sha256) == 64, f"{p.name}: tem impressão digital")

# o acento é o canário: sem a CMap o texto sai legível MAS sem acento, e isso
# passa desapercebido até alguém procurar uma palavra acentuada
_reg = next((p for p in PDFS if "egua" in p.name.lower()), None)
if _reg:
    _txt = "\n".join(abrir(_reg).paginas()[:12])
    checa("é" in _txt or "ã" in _txt or "í" in _txt,
          "a acentuação sobrevive (sem CMap, 'Régua' virava 'Rgua')",
          _txt[:60])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] o índice acha as fichas, com procedência")

IT.INDICE.unlink(missing_ok=True)
d = IT.carregar(reconstruir=True)
print(IT.resumo(d))
checa(d["total_fichas"] > 500, "achou centenas de fichas", d["total_fichas"])
checa(d["fichas_com_formula"] > 300, "e a maioria com fórmula legível",
      d["fichas_com_formula"])
livro = [f for f in d["fichas"] if f["fonte"] == "livro"]
checa(len(livro) >= 900,
      "o Livro entrega as ~960 formulações que ele descreveu", len(livro))

for f in d["fichas"][:1]:
    checa(f.get("pagina") and f.get("sha256") and f.get("arquivo"),
          "cada ficha diz arquivo, página e hash", f.get("id"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] a fórmula vem do PDF, não do código")

f01 = IT.formula_de(d, "F01", "mega_fire") or IT.formula_de(d, "F01")
checa(f01 is not None, "a família F01 tem ficha")
if f01:
    print(f"       F01 · {f01['arquivo']} p.{f01['pagina']}")
    print(f"       {f01['formula'][:110]}")
    checa(len(f01["formula"]) > 20, "e a fórmula tem conteúdo", f01["formula"])
    # a fórmula do intervalo é a que ele escreveu: D_t = t - max{i<t: Y_i=1}
    checa("D_t" in f01["formula"] or "max" in f01["formula"],
          "é a fórmula do intervalo contextual", f01["formula"][:70])
    # A verificação tem de ser contra o código que CALCULA.
    #
    # A primeira versão deste teste olhava `indice_tratados.py` e falhava --
    # porque a docstring dele CITA essa fórmula como exemplo do formato da
    # ficha. Citar num comentário é o contrário de embutir: é documentar de
    # onde o dado vem. Quem não pode ter a fórmula escrita é quem faz a conta.
    for _arq in ("NUCLEO/leituras.py", "NUCLEO/agregacao.py",
                 "academia_autonoma/inteligencias_livro.py"):
        _src = (RAIZ / _arq)
        if not _src.is_file():
            continue
        _py = _src.read_text(encoding="utf-8")
        checa(f01["formula"][:45] not in _py,
              f"a fórmula não está embutida em {_arq}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] mudar o PDF invalida o índice")

alvo = PDFS[0]
guardado = alvo.read_bytes()
try:
    alvo.write_bytes(guardado + b"\n% um byte a mais\n")
    d2 = IT.carregar()
    sha_antes = next(x["sha256"] for x in d["documentos"]
                     if x["arquivo"] == alvo.name)
    sha_depois = next(x["sha256"] for x in d2["documentos"]
                      if x["arquivo"] == alvo.name)
    checa(sha_antes != sha_depois,
          "PDF alterado gera hash novo e índice reconstruído",
          (sha_antes[:10], sha_depois[:10]))
finally:
    alvo.write_bytes(guardado)
    IT.INDICE.unlink(missing_ok=True)
    IT.carregar(reconstruir=True)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] O TESTE QUE IMPORTA: sem PDF, as doze emudecem")

import ia_modulos as M  # noqa: E402

rnd = random.Random(7)
SETOR = [5, 24, 16, 33, 1, 20, 14]
linhas = []
for i in range(240):
    v = rnd.choice(SETOR) if rnd.random() < 0.3 else rnd.randrange(37)
    lk = [{"n": (rnd.choice(SETOR) if rnd.random() < 0.3 else rnd.randrange(37)),
           "x": 50} for _ in range(rnd.randint(1, 4))]
    linhas.append({"n": v, "settled": f"2026-08-17T{i//60:02d}:{i%60:02d}:00Z",
                   "tags": [{"lucky": lk}]})


def quantas_falam():
    """Quantas das doze entraram no consenso nesta volta."""
    P._UNICA = None
    IT.INDICE.unlink(missing_ok=True)
    aut = P.autoridade(recarregar=True)
    out = M.PipelinePerceptivo("lightning").processar(
        [l["n"] for l in linhas], 0, 0,
        settled=[l["settled"] for l in linhas], linhas=linhas) or {}
    hip = next((m for m in (out.get("msgs") or [])
                if m.startswith("[Hipóteses]")), "")
    n = len([x for x in hip.split("'") if x.startswith("IA")])
    return n, aut.placar("lightning"), out


com, pl_com, _ = quantas_falam()
print(f"       COM os PDFs:  {pl_com['fichas']} fichas · "
      f"{len(pl_com['autorizadas'])}/12 autorizadas · {com} no consenso")
checa(com >= 8, "com os tratados presentes, as inteligências falam", com)

_temp = tempfile.mkdtemp()
for f in list(IT.PASTA_PDFS.glob("*.pdf")):
    shutil.move(str(f), _temp)
try:
    sem, pl_sem, out_sem = quantas_falam()
    print(f"       SEM os PDFs:  {pl_sem['fichas']} fichas · "
          f"{len(pl_sem['autorizadas'])}/12 autorizadas · {sem} no consenso")
    checa(sem == 0,
          "SEM os tratados, NENHUMA fala — a ligação é falsificável", sem)
    checa(len(pl_sem["caladas"]) == 12, "e todas as doze constam como caladas",
          len(pl_sem["caladas"]))
    diz = [m for m in (out_sem.get("msgs") or []) if "Procedência" in m]
    checa(any("tratados/ está vazia" in m for m in diz),
          "e o log explica por quê, em vez de calar calado", diz[:1])
    # o ponto central: nada caiu para a transcrição por trás
    checa(not any("IA01" in m and "calada" not in m for m in diz),
          "nenhuma rodou pela transcrição antiga")
finally:
    for f in os.listdir(_temp):
        shutil.move(os.path.join(_temp, f), IT.PASTA_PDFS)

volta, pl_v, _ = quantas_falam()
print(f"       DEVOLVIDOS:   {pl_v['fichas']} fichas · "
      f"{len(pl_v['autorizadas'])}/12 autorizadas · {volta} no consenso")
checa(volta == com, "devolvendo os PDFs, tudo religa", (com, volta))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] o que NÃO vem de tratado continua rotulado como meu")

aut = P.autoridade(recarregar=True)
for nome in ("ESTAT", "ANOMALIA", "HEURISTICA"):
    checa(aut.autorizada(nome), f"{nome} roda (é heurística do software)")
    checa("heurística" in aut.motivo(nome),
          f"{nome} declarado como heurística, não como teoria dele",
          aut.motivo(nome))

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("PROCEDENCIA_OK")
