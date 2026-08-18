# -*- coding: utf-8 -*-
"""
JOGAR — o software da loteria, para ele usar.

O QUE ESTE PROGRAMA FAZ, EM UMA FRASE CADA
──────────────────────────────────────────
    o acaso        o número exato de cada aposta, sem estimativa
    o custo        quanto cada tamanho de aposta custa e o que ele compra
    o fechamento   as apostas que GARANTEM prêmio se as suas dezenas saírem,
                   com a garantia provada caso a caso antes de gastar um real
    a medida       o que o histórico dele diz sobre cada crença de loteria
    a base         o que o software sabe, e o que derrubaria cada coisa

O QUE ELE NÃO FAZ, E ISSO NÃO VAI MUDAR
───────────────────────────────────────
Não diz quais dezenas vão sair. Num sorteio de bolas honesto isso não existe, e
qualquer tela que fingisse saber estaria mentindo com número — que é a mentira
mais convincente que existe. O que existe de real é o que está na lista acima, e
é bastante: o fechamento é ganho de eficiência PROVADO, e a partilha é ganho de
valor sem prever nada.

COMO SE USA
───────────
    python JOGAR.py                              as loterias e o acaso de cada
    python JOGAR.py mega_sena                    o acaso e o custo, por tamanho
    python JOGAR.py mega_sena --dezenas "3 7 12 19 24 31 38 45 52 58 11 27"
                                                 o fechamento, com a prova
    python JOGAR.py mega_sena --historico dados/mega.csv
                                                 mede as crenças no histórico
    python JOGAR.py --base                       o que o software sabe
"""
from __future__ import annotations

import argparse
import re
import sys
from math import comb
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import base_conhecimento as BC       # noqa: E402
from NUCLEO import conferencia as CO             # noqa: E402
from NUCLEO import fechamento as FE              # noqa: E402
from NUCLEO import formular as FO                # noqa: E402
from NUCLEO import historico as HI               # noqa: E402
from NUCLEO import medidor as MD                 # noqa: E402
from NUCLEO import regras as RG                  # noqa: E402


def _n(x) -> str:
    return f"{x:,.0f}".replace(",", ".")


def _dezenas(texto: str):
    return [int(t) for t in re.split(r"[^\d]+", texto or "") if t]


# ══════════════════════════════════════════════════════ as loterias
def listar() -> None:
    print("\n[Loterias] as que este software conhece:\n")
    for chave, j in RG.JOGOS.items():
        p = j.p_faixa(j.minimo, j.faixas[0])
        acaso = f"1 em {_n(1/p)}" if p > 0 else "—"
        print(f"  {chave:<16} {j.nome:<14} {j.universo} dezenas, saem "
              f"{j.sorteadas}, aposta de {j.minimo} a {j.maximo}")
        print(f"  {'':<16} faixa máxima na aposta mínima: {acaso}")
    print("\n[Loterias] fora deste molde, de propósito:")
    for chave, motivo in RG.FORA_DO_MOLDE.items():
        print(f"  {chave:<16} {motivo}")
    print("\n[Loterias] nenhuma destas regras foi conferida contra a Caixa — "
          "eu as escrevi de memória e este ambiente\n           não alcança o "
          "site dela. Passe o arquivo de resultados com --historico e o "
          "software confere sozinho.")


# ══════════════════════════════════════════════════ o acaso e o custo
def mostrar_jogo(j: RG.Jogo) -> None:
    print(f"\n[{j.nome}] {j.universo} dezenas, saem {j.sorteadas}. {j.nota}")
    print(f"[{j.nome}] regras conferidas contra a fonte oficial: "
          f"{'sim' if j.conferido else 'NÃO — ver o aviso no fim'}")

    print(f"\n[Acaso] o número exato de cada tamanho de aposta:\n")
    faixa_alta = j.faixas[0]
    cab = (f"  {'aposta':>7} {'custa (apostas mín.)':>21} "
           f"{'faixa máxima':>18} {'chance por real':>17} {'algum prêmio':>14}")
    print(cab)
    print("  " + "─" * (len(cab) - 2))
    base_razao = None
    for k in range(j.minimo, min(j.maximo, j.minimo + 9) + 1):
        custo = comb(k, j.minimo)
        p = j.p_faixa(k, faixa_alta)
        pa = j.p_algum_premio(k)
        razao = p / custo if custo else 0
        if base_razao is None:
            base_razao = razao
        marca = "=" if base_razao and abs(razao/base_razao - 1) < 1e-9 else "≠"
        print(f"  {k:>7} {_n(custo):>21} {'1 em ' + _n(1/p) if p else '—':>18} "
              f"{marca + ' ' + f'{razao:.3e}':>17} {pa:>13.3%}")

    print(f"\n[Acaso] a coluna 'chance por real' é a que importa e ela é "
          f"CONSTANTE: uma aposta de k dezenas")
    print(f"        custa C(k,{j.minimo}) apostas mínimas e concorre com "
          f"exatamente essas C(k,{j.minimo}) combinações.")
    print(f"        Aposta grande não compra vantagem nenhuma por real — "
          f"compra OUTRA FORMA de gastar o mesmo:")
    print(f"        ganha mais vezes pouco, em torno de um núcleo fixo. Repare "
          f"que 'algum prêmio' por real CAI.")
    print(f"\n[Acaso] acertos médios na aposta mínima: "
          f"{j.acertos_esperados(j.minimo):.2f} — é contra este número que toda "
          f"teoria se mede,")
    print(f"        não contra zero. Na Lotofácil, 'acertei 9' é exatamente o "
          f"esperado de quem aposta 15.")
    if not j.conferido:
        print(f"\n[Aviso] estas regras saíram da minha memória e não da Caixa. "
              f"Confira com --historico antes de gastar.")


# ══════════════════════════════════════════════════════ o fechamento
def mostrar_fechamento(j: RG.Jogo, dez, k: int, se: int, garantir: int,
                       salvar: str = "") -> int:
    fora = [d for d in dez if d not in set(j.dezenas())]
    if fora:
        print(f"\n[Fechamento] dezenas fora do universo de {j.nome}: {fora}")
        return 1
    if len(set(dez)) != len(dez):
        print(f"\n[Fechamento] há dezena repetida na sua lista")
        return 1

    print(f"\n[Fechamento] {j.nome} — suas {len(dez)} dezenas: "
          f"{' '.join(f'{d:02d}' for d in sorted(dez))}")
    print(f"[Fechamento] pedido: apostas de {k} dezenas; SE {se} das suas "
          f"saírem, garantir {garantir} acertos numa delas.\n")

    r = FE.montar(sorted(dez), k=k, acertos_previstos=se, garantir=garantir)
    if not r.get("ok"):
        print(f"[Fechamento] não fechou — {r.get('nota')}")
        return 1

    prova = FE.conferir(r["apostas"], sorted(dez), se, garantir)
    for linha in FE.resumo(r, prova):
        print(linha)

    if not prova.get("provado"):
        print("\n[Fechamento] NÃO use estas apostas como garantia: a prova "
              "reprovou. Isto é um conjunto de apostas, e nada mais.")
        return 1

    print(f"\n[Fechamento] as {r['n_apostas']} apostas:\n")
    for i, ap in enumerate(r["apostas"], 1):
        print(f"   {i:>3}.  " + "  ".join(f"{x:02d}" for x in ap))

    custo = r["n_apostas"] * comb(k, j.minimo)
    p_alguma = 1 - (1 - j.p_faixa(k, j.faixas[0])) ** r["n_apostas"]
    print(f"\n[Custo] {r['n_apostas']} apostas de {k} dezenas = "
          f"{_n(custo)} apostas mínimas de {j.nome}.")
    print(f"[Custo] chance de a faixa máxima sair em alguma delas: "
          f"1 em {_n(1/p_alguma) if p_alguma else 0}.")
    print(f"[Custo] a garantia acima NÃO é essa chance. A garantia é "
          f"condicional: ela vale SE {se} das suas")
    print(f"        {len(dez)} dezenas saírem. Que elas saiam é sorteio, e "
          f"sobre isso este software não promete nada.")

    it = BC.por_id("M03")
    if it and BC.autorizada("M03"):
        print(f"\n[Base] o que autoriza isto: {it.id} — {it.afirma}")
        print(f"[Base] e o que derrubaria: {it.derruba}")

    if salvar:
        # a promessa vai gravada JUNTO com as apostas: é ela que permite, no
        # dia do sorteio, auditar se a garantia foi honrada — e me desmentir
        # na tela se não foi
        caminho = CO.escrever_apostas(
            salvar, r["apostas"], j.chave,
            meta={"se": se, "garantir": garantir, "dezenas": sorted(dez)})
        print(f"\n[Salvo] apostas e promessa em {caminho}")
        print(f"[Salvo] no dia do sorteio: python JOGAR.py {j.chave} "
              f"--apostas {caminho} --sorteio \"<as dezenas sorteadas>\"")
    return 0


# ══════════════════════════════════════════════════ medir no histórico
def medir(chave: str, caminho: str):
    """Devolve (código, histórico) — o histórico segue para quem formular."""
    print(f"\n[Histórico] lendo {caminho} …")
    h, avisos = HI.de_arquivo(caminho, chave)
    for a in avisos:
        print(f"[Histórico]   ({a})")
    if h is None:
        print("[Histórico] não deu para ler. Nada foi medido, e nada foi "
              "gravado na base.")
        return 1, None
    print()
    for linha in h.diagnostico():
        print(linha)
    print("\n[Histórico] confira as linhas acima com o arquivo aberto ao lado. "
          "Se o que eu li não for o que está")
    print("            lá, pare aqui: toda medida abaixo sairia de leitura "
          "errada, e sairia com cara de certa.\n")

    ok, motivo = h.pronto_para_medir()
    if not ok:
        print(f"[Medidor] não vou medir: {motivo}")
        return 1, h

    med = MD.medir_tudo(h, gravar=True)
    for linha in MD.resumo(med):
        print(linha)
    print(f"\n[Regras] as regras de {chave} agora estão "
          f"{'CONFERIDAS' if RG.jogo(chave).conferido else 'ainda não conferidas'} "
          f"contra os sorteios reais deste arquivo.")
    return 0, h


# ═══════════════════════════════════════════════ formular e conferir
def mostrar_formulacao(j: RG.Jogo, a, h) -> int:
    c = FO.conselho(j.chave, quantas=(a.tamanho or None), hist=h,
                    semente=(a.semente if a.semente else None))
    print()
    for linha in FO.resumo(c):
        print(linha)
    return 0 if c.get("ok") else 1


def mostrar_conferencia(j: RG.Jogo, a) -> int:
    if not a.apostas:
        print("\n[Conferência] falta dizer onde estão as apostas: "
              "--apostas dados/apostas_" + j.chave + ".txt")
        return 1
    apostas, meta, avisos = CO.ler_apostas(a.apostas, j)
    for av in avisos:
        print(f"[Conferência] ({av})")
    if not apostas:
        print("[Conferência] nenhuma aposta válida no arquivo — nada a "
              "conferir.")
        return 1
    r = CO.conferir(j, apostas, _dezenas(a.sorteio))
    auditoria = None
    if r.get("ok") and meta:
        auditoria = CO.auditar_garantia(meta, apostas, r["sorteio"])
    print()
    for linha in CO.resumo(j, r, auditoria):
        print(linha)
    if auditoria and auditoria.get("honrada") is False:
        return 1        # garantia falhando é defeito meu, e sai como erro
    return 0 if r.get("ok") else 1


# ══════════════════════════════════════════════════════ a base
def mostrar_base(chave: str = "") -> None:
    print()
    for linha in BC.resumo(chave or None):
        print(linha)
    print("\n[Base] cada item guarda o que o derrubaria — é isso que faz a "
          "confirmação valer alguma coisa quando")
    print("       ela vier. Item sem isso não entra, e item derrubado pela "
          "medida não justifica mais nenhum jogo.")
    print("[Base] para acrescentar uma teoria sua, ela precisa das mesmas "
          "quatro partes: o que afirma, como medir,")
    print("       o que a derrubaria, e de onde veio. Me diga a teoria e eu "
          "escrevo as quatro com você.")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Loteria: acaso exato, fechamento provado e medida honesta.",
        add_help=True)
    ap.add_argument("jogo", nargs="?", default="",
                    help="mega_sena, quina, lotofacil, …")
    ap.add_argument("--dezenas", default="",
                    help="as suas dezenas fixas, entre aspas")
    ap.add_argument("--k", type=int, default=0,
                    help="dezenas por aposta (padrão: a aposta mínima)")
    ap.add_argument("--se", type=int, default=0,
                    help="quantas das suas dezenas você supõe que saiam")
    ap.add_argument("--garantir", type=int, default=0,
                    help="acertos a garantir numa aposta")
    ap.add_argument("--historico", default="",
                    help="arquivo de resultados baixado da Caixa")
    ap.add_argument("--base", action="store_true",
                    help="mostra a base de conhecimento")
    ap.add_argument("--formular", action="store_true",
                    help="as inteligências formulam jogos citando a base")
    ap.add_argument("--tamanho", type=int, default=0,
                    help="dezenas por jogo formulado (padrão: a aposta mínima)")
    ap.add_argument("--semente", type=int, default=0,
                    help="repete uma formulação anterior")
    ap.add_argument("--salvar", nargs="?", const="AUTO", default="",
                    help="grava as apostas do fechamento (e a promessa) num arquivo")
    ap.add_argument("--sorteio", default="",
                    help="as dezenas sorteadas, para conferir as apostas")
    ap.add_argument("--apostas", default="",
                    help="o arquivo de apostas gravado com --salvar")
    a = ap.parse_args()

    print("═" * 72)
    print("LOTERIA — acaso exato, garantia provada, e nada de previsão")
    print("═" * 72)

    if not a.jogo and not a.base:
        listar()
        print("\n[Ajuda] python JOGAR.py mega_sena          → o acaso e o custo")
        print("[Ajuda] python JOGAR.py mega_sena --dezenas \"3 7 12 19 24 31 "
              "38 45 52 58\"  → o fechamento")
        print("[Ajuda] python JOGAR.py mega_sena --historico dados/mega.csv"
              "     → mede no histórico")
        return 0

    if a.base and not a.jogo:
        mostrar_base()
        return 0

    j = RG.jogo(a.jogo)
    if not j:
        motivo = RG.FORA_DO_MOLDE.get(a.jogo.strip().lower())
        if motivo:
            print(f"\n[Loterias] {a.jogo} está fora deste software de "
                  f"propósito: {motivo}.")
            print("[Loterias] forçá-la no molde de 'escolher k dezenas em n' "
                  "daria probabilidade errada com cara de certa.")
            return 1
        print(f"\n[Loterias] não conheço '{a.jogo}'. As que eu conheço:")
        listar()
        return 1

    if a.sorteio:
        return mostrar_conferencia(j, a)

    if a.historico:
        codigo, h = medir(j.chave, a.historico)
        if a.formular:
            # mede primeiro, formula depois: as inteligências consultam a base
            # JÁ com os vereditos dos dados dele — que é o pedido original
            return mostrar_formulacao(j, a, h if codigo == 0 else None)
        return codigo

    if a.formular:
        return mostrar_formulacao(j, a, None)

    if a.dezenas:
        dez = _dezenas(a.dezenas)
        k = a.k or j.minimo
        se = a.se or min(len(dez), j.sorteadas - 1)
        garantir = a.garantir or max(1, min(k, j.faixas[-1]))
        salvar = a.salvar
        if salvar == "AUTO":
            salvar = str(RAIZ / "dados" / f"apostas_{j.chave}.txt")
        return mostrar_fechamento(j, dez, k, se, garantir, salvar)

    mostrar_jogo(j)
    if a.base:
        mostrar_base(j.chave)
    return 0


if __name__ == "__main__":
    sys.exit(main())
