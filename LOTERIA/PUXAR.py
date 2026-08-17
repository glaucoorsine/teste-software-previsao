# -*- coding: utf-8 -*-
"""
PUXAR — trazer os resultados da API para o disco dele.

    python PUXAR.py mega_sena              puxa o que falta e guarda
    python PUXAR.py mega_sena --ultimo     só o último concurso — testa a fonte
    python PUXAR.py mega_sena --desde 2500 só de um concurso em diante
    python PUXAR.py --fonte "https://…"    grava o endereço que VOCÊ mandar
    python PUXAR.py --onde                 mostra o endereço em uso agora

DUAS COISAS QUE ESTE PROGRAMA FAZ DE PROPÓSITO
──────────────────────────────────────────────
Começa pelo `--ultimo`. Uma chamada só, e ela mostra o que a fonte devolveu
por extenso. Se o formato não for o que eu esperava, aparece ali — antes de
milhares de chamadas e antes de qualquer estatística.

E mostra o diagnóstico depois de puxar. Ler certo e ler errado têm a mesma cara
quando o programa não conta o que entendeu; então ele conta.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import api                            # noqa: E402
from NUCLEO import historico as HI                # noqa: E402
from NUCLEO import regras as RG                   # noqa: E402


def mostrar_fonte() -> None:
    f = api.carregar_fonte()
    print(f"\n[Fonte] {f.get('nome')}")
    print(f"[Fonte]   último concurso:  {f.get('url')}")
    print(f"[Fonte]   concurso n:       {f.get('url_concurso')}")
    print(f"[Fonte]   conferida de verdade: "
          f"{'sim' if f.get('conferida') else 'NÃO — a primeira puxada confere'}")
    if not (api.ARQUIVO_FONTE.exists()):
        print(f"[Fonte]   (este é o padrão conhecido; para trocar: "
              f"python PUXAR.py --fonte \"https://…\")")


def testar(chave: str) -> int:
    """Uma chamada só, e mostra tudo o que veio. O teste antes do trabalho."""
    url = api.endereco(chave)
    print(f"\n[Teste] chamando {url}")
    dados, erro = api.buscar(url)
    if erro:
        print(f"\n[Teste] não deu: {erro}")
        return 1
    if isinstance(dados, list) and dados:
        dados = dados[0]
    print(f"\n[Teste] a fonte respondeu. Os campos que vieram:\n")
    if isinstance(dados, dict):
        for k in sorted(dados):
            v = dados[k]
            texto = json.dumps(v, ensure_ascii=False)
            if len(texto) > 90:
                texto = texto[:90] + "…"
            print(f"   {k:<28} {texto}")
    else:
        print(f"   (não é um objeto: {type(dados).__name__})")
        return 1

    conc = HI._de_json(json.dumps([dados]), chave)
    print()
    if not conc:
        print("[Teste] MAS eu não consegui extrair o sorteio disso. Os campos "
              "acima estão na tela justamente")
        print("        para isto: me diga qual deles traz as dezenas e eu "
              "ensino o leitor. Não vou adivinhar.")
        return 1
    c = conc[0]
    print(f"[Teste] entendi assim:")
    print(f"        concurso {c['concurso']} de {c['data']} — dezenas "
          f"{c['dezenas']}")
    print(f"        ganhadores {c['ganhadores'] or '(não vieram)'}"
          + (f", faixa lida por {c['faixas_lidas_por']}"
             if c.get("faixas_lidas_por") else ""))
    print(f"        arrecadação {c['arrecadacao']}")
    j = RG.jogo(chave)
    if j and len(c["dezenas"]) != j.sorteadas:
        print(f"\n[Teste] ATENÇÃO: eu declarei que saem {j.sorteadas} dezenas "
              f"em {j.nome} e vieram {len(c['dezenas'])}.")
        print(f"        Ou o leitor pegou o campo errado, ou a minha regra está "
              f"errada. As duas se resolvem olhando esta tela.")
        return 1
    print(f"\n[Teste] confere com as regras de {j.nome if j else chave}. Pode "
          f"puxar o histórico:")
    print(f"        python PUXAR.py {chave}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Puxa os resultados da API.")
    ap.add_argument("jogo", nargs="?", default="")
    ap.add_argument("--ultimo", action="store_true",
                    help="só o último concurso, para conferir a fonte")
    ap.add_argument("--desde", type=int, default=1)
    ap.add_argument("--ate", type=int, default=0)
    ap.add_argument("--pausa", type=float, default=0.15,
                    help="segundos entre chamadas (não martelar a fonte)")
    ap.add_argument("--fonte", default="", help="grava um novo endereço")
    ap.add_argument("--fonte-concurso", default="",
                    help="endereço de UM concurso, com {n} no lugar do número")
    ap.add_argument("--onde", action="store_true")
    a = ap.parse_args()

    print("═" * 72)
    print("PUXAR — os resultados, da fonte para o disco")
    print("═" * 72)

    if a.fonte:
        f = api.gravar_fonte(a.fonte, a.fonte_concurso)
        print(f"\n[Fonte] gravado em {api.ARQUIVO_FONTE}")
        mostrar_fonte()
        print("\n[Fonte] agora teste com uma chamada só:")
        print(f"        python PUXAR.py {a.jogo or 'mega_sena'} --ultimo")
        return 0

    if a.onde or not a.jogo:
        mostrar_fonte()
        if not a.jogo:
            print("\n[Ajuda] python PUXAR.py mega_sena --ultimo   → testa a fonte")
            print("[Ajuda] python PUXAR.py mega_sena            → puxa tudo")
        return 0

    j = RG.jogo(a.jogo)
    if not j:
        print(f"\n[Puxar] não conheço '{a.jogo}'. Conhecidas: "
              f"{', '.join(RG.JOGOS)}")
        return 1

    if a.ultimo:
        return testar(j.chave)

    print()
    r = api.puxar(j.chave, ate=(a.ate or None), desde=a.desde,
                  pausa=a.pausa, aviso=lambda s: print(f"[Puxar] {s}"))
    if not r.get("ok"):
        print(f"\n[Puxar] parou: {r.get('erro')}")
        if r.get("novos"):
            print(f"[Puxar] mas {r['novos']} concursos novos ficaram gravados "
                  f"em {r.get('arquivo')} — rodar de novo continua daqui.")
        return 1

    print(f"\n[Puxar] pronto: {r['total']} concursos em {r['arquivo']} "
          f"({r['novos']} novos)")
    if r.get("falhas"):
        print(f"[Puxar] {len(r['falhas'])} concurso(s) a fonte não tinha: "
              f"{[n for n, _ in r['falhas'][:8]]}")

    h, avisos = HI.de_arquivo(r["arquivo"], j.chave,
                              fonte=f"API: {api.carregar_fonte().get('nome')}")
    if h is None:
        print("[Puxar] gravei, mas não consegui reler o que gravei — isto é "
              "defeito meu, me mostre esta tela.")
        return 1
    print()
    for linha in h.diagnostico():
        print(linha)
    if h.conferido:
        f = api.carregar_fonte()
        f["conferida"] = True
        api.PASTA_DADOS.mkdir(parents=True, exist_ok=True)
        api.ARQUIVO_FONTE.write_text(
            json.dumps(f, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[Puxar] a fonte está conferida contra as regras. Agora:")
        print(f"        python JOGAR.py {j.chave} --historico {r['arquivo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
