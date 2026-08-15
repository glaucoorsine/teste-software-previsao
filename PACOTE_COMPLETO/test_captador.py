# -*- coding: utf-8 -*-
"""Confere que o captador nao repete pergunta -- que foi o que ele pediu.

    python test_captador.py
"""
import sys, shutil, tempfile, pathlib
RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from academia_autonoma import captador as C
C.CADERNO = pathlib.Path(tempfile.mkdtemp())

falhas=[]
def checa(c,n,d=""):
    print(("  ok   " if c else "  FALHA ")+n+("" if c else f"   [{d}]")); 
    if not c: falhas.append(n)

rel=[{"chave":"posição na roda:dist=9","descricao":"posição na roda a 9 de distância",
      "lag":3,"taxa":0.33,"acaso":0.054,"razao":6.08,"p":0.0002,"n":1200},
     {"chave":"final:igual","descricao":"mesmo final","lag":1,
      "taxa":0.13,"acaso":0.10,"razao":1.30,"p":0.01,"n":1200},
     {"chave":"cor:igual","descricao":"mesma cor","lag":1,
      "taxa":0.50,"acaso":0.49,"razao":1.02,"p":0.3,"n":1200}]
cat=[{"descricao":"posição na roda a 9 de distância — 3 giro(s) depois"}]

print("\n[1] oferece só o que vale, e não o que ele já ensinou")
n1=C.oferecer("teste", rel, [], catalogo=[])
tit=[x["titulo"] for x in n1]
print("      ", tit)
checa(any("9 de distância" in t for t in tit), "oferece o achado forte")
checa(not any("mesmo final" in t for t in tit),
      "NÃO oferece 'mesmo final' — é regra que ele já ensinou", tit)
checa(not any("mesma cor" in t for t in tit),
      "NÃO oferece 1,02x — ruído com nome bonito", tit)

print("\n[2] não repete o que já foi oferecido")
n2=C.oferecer("teste", rel, [], catalogo=[])
checa(n2==[], "segunda chamada não traz nada", [x['titulo'] for x in n2])

print("\n[3] não oferece o que já está no catálogo")
C.CADERNO.joinpath("captador_outro.json").unlink(missing_ok=True)
n3=C.oferecer("outro", rel, [], catalogo=cat)
checa(not any("9 de distância" in x["titulo"] for x in n3),
      "o que a academia já catalogou não é oferecido de novo",
      [x['titulo'] for x in n3])

print("\n[4] as respostas dele são guardadas")
ch=n1[0]["chave"]
C.responder("teste", ch, "aceita", nota="ja tinha reparado")
a=C.aceitas("teste")
checa(len(a)==1 and a[0]["chave"]==ch, "a aceita fica marcada", a)
checa(a[0].get("nota")=="ja tinha reparado", "e a nota dele fica junto")

print("\n[5] recusada nunca mais volta")
C.CADERNO.joinpath("captador_r.json").unlink(missing_ok=True)
n5=C.oferecer("r", rel, [], catalogo=[])
C.responder("r", n5[0]["chave"], "recusada")
n6=C.oferecer("r", rel, [], catalogo=[])
checa(not any(x["chave"]==n5[0]["chave"] for x in n6),
      "o que ele recusou não é reoferecido")

print("\n[6] 'vou observar' volta depois, não no mesmo dia")
C.CADERNO.joinpath("captador_o.json").unlink(missing_ok=True)
n7=C.oferecer("o", rel, [], catalogo=[])
k=n7[0]["chave"]
C.responder("o", k, "observando")
n8=C.oferecer("o", rel, [], catalogo=[])
checa(not any(x["chave"]==k for x in n8), "no mesmo dia não volta")
d=C.caderno("o"); d[k]["quando"] -= 2*86400; C._gravar("o", d)
n9=C.oferecer("o", rel, [], catalogo=[])
checa(any(x["chave"]==k for x in n9), "passados dois dias, volta a perguntar")

print()
if falhas: print("FALHAS:", falhas); sys.exit(1)
print("CAPTADOR_OK")
