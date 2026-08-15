# -*- coding: utf-8 -*-
"""
AUTÓPSIA — por que erramos, e por que acertamos.

O QUE ELE PEDIU
---------------
    "Uma outra coisa que as IAs têm que se perguntar, todas: por que que está
     errando tanto? O que que está acontecendo que elas não estão vendo?"
    "As IAs têm que aprender por que que erraram e por que que acertaram."

A PERGUNTA TEM RESPOSTA MECÂNICA
--------------------------------
Quando a janela erra, o número que saiu não veio do nada — ele estava, ou não,
na lista de alguma das fontes que votaram. Isso separa o erro em dois tipos, e
cada um pede uma correção diferente:

    CEGUEIRA    nenhuma fonte tinha aquele número. O software não errou a
                escolha: ele não enxergou aquilo. É o caso que pede teoria
                nova — e é o que o captador existe para resolver.

    VOTAÇÃO     alguma fonte TINHA o número, mas ele ficou de fora das sete
                vagas. Aqui o software viu e descartou: o problema é peso, não
                falta de teoria. Se isso for a maioria, mexer nos pesos rende
                mais que inventar teoria nova.

Confundir os dois manda o trabalho para o lado errado — por isso eles são
separados e contados.

E o acerto também é dissecado: QUAL fonte tinha o número que saiu. Sem isso não
dá para saber quem está puxando o resultado, e a tendência é dar crédito para
quem fala mais alto, não para quem acerta.

E DEPOIS DE PERGUNTAR, ELA CONSERTA
-----------------------------------
    "após as IAs se perguntarem o porquê dos erros, elas consertam e voltam
     a emitir sinais?"

Agora sim. Diagnóstico que não vira correção é desabafo. `correcao()` transforma
os laudos em um número por fonte: quantas vezes aquela fonte tinha o número que
saiu, dividido pelo quanto uma fonte média desta mesa acerta. Quem vem
acertando passa a votar mais alto; quem vem errando, mais baixo — e o motor
segue emitindo sinal no ciclo seguinte, com os pesos já ajustados.

Três limites, de propósito:

    PISO 0.7     ninguém é zerado nem excluído. Ele foi explícito: "não
                 critique e nem barre" — teoria que parece morta hoje pode ser
                 só o momento. Baixar o peso é diferente de podar.
    TETO 1.6     nem a fonte mais certeira vira dona da votação sozinha; o
                 consenso continua sendo cruzamento.
    12 JANELAS   abaixo disso o peso não se mexe. Corrigir com 3 janelas é
                 corrigir ruído, e o conserto fica pior que o defeito.

O que a correção NÃO resolve é a cegueira: se ninguém tinha o número, não há
peso que salve — ali falta teoria, e o caminho é o captador. Por isso os dois
tipos continuam separados.

ONDE FICA
---------
Logs/autopsia_<mesa>.jsonl, uma linha por janela fechada. É acumulativo de
propósito: a resposta só fica boa com dezenas de janelas.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "Logs"
MIN_PARA_CONCLUIR = 15

# --- limites do conserto automático (ver o cabeçalho) ---
MIN_JANELAS_FONTE = 12     # abaixo disso o peso não se mexe
PISO = 0.7                 # ninguém é zerado: baixar peso ≠ podar
TETO = 1.6                 # ninguém vira dono da votação sozinho


def _arquivo(jogo: str) -> Path:
    return PASTA / f"autopsia_{jogo}.jsonl"


def registrar(jogo: str, escolhidos: List, saiu: Any, acertou: bool,
              candidatos_por_fonte: Dict[str, List] = None,
              giros: int = 0, jogadores: int = None,
              mesa_cheia: bool = None, faixa: str = None) -> Dict[str, Any]:
    """Disseca uma janela fechada e guarda o laudo.

    `candidatos_por_fonte` é o que cada teoria propôs ANTES do corte das sete
    vagas — é ele que permite dizer se o número que saiu foi ignorado ou nem
    chegou a ser visto.
    """
    alvo = str(saiu).strip()
    escolhidos_s = [str(x).strip() for x in (escolhidos or [])]
    fontes = candidatos_por_fonte or {}
    quem_tinha = [nome for nome, nums in fontes.items()
                  if alvo in [str(x).strip() for x in (nums or [])]]

    if acertou:
        tipo = "acerto"
    elif quem_tinha:
        tipo = "votacao"          # alguém viu e o consenso deixou de fora
    else:
        tipo = "cegueira"         # ninguém tinha

    laudo = {
        "quando": time.time(), "saiu": alvo, "acertou": bool(acertou),
        "escolhidos": escolhidos_s, "giros": int(giros or 0),
        "tipo": tipo, "quem_tinha": quem_tinha, "n_fontes": len(fontes),
        # QUEM VOTOU, não só quem acertou. Sem o denominador, "essa fonte
        # tinha o número 4 vezes" não quer dizer nada -- 4 em 5 janelas é
        # ótimo e 4 em 200 é ruído. É esta lista que permite corrigir peso.
        "fontes": sorted(fontes.keys()),
        # quantas pessoas estavam na mesa quando esta janela correu.
        # Sem guardar isto, a percepcao dele -- "com mais gente online a
        # previsao fica mais facil" -- nao teria como ser medida depois.
        "jogadores": jogadores, "mesa_cheia": mesa_cheia,
        "faixa": faixa,
    }
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        with _arquivo(jogo).open("a", encoding="utf-8") as f:
            f.write(json.dumps(laudo, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return laudo


def ler(jogo: str, ultimos: int = 400) -> List[dict]:
    p = _arquivo(jogo)
    if not p.is_file():
        return []
    saida = []
    try:
        for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
            linha = linha.strip()
            if not linha:
                continue
            try:
                saida.append(json.loads(linha))
            except ValueError:
                continue
    except OSError:
        return []
    return saida[-ultimos:]


def diagnostico(jogo: str, ultimos: int = 400) -> Dict[str, Any]:
    """O que os laudos, somados, dizem sobre o motivo dos erros."""
    laudos = ler(jogo, ultimos)
    if not laudos:
        return {"n": 0}
    erros = [x for x in laudos if not x.get("acertou")]
    acertos = [x for x in laudos if x.get("acertou")]
    tipos = Counter(x.get("tipo") for x in erros)
    # quem tinha o número certo nos ACERTOS: quem está puxando o resultado
    puxando = Counter()
    for x in acertos:
        for nome in (x.get("quem_tinha") or []):
            puxando[nome] += 1
    # quem tinha o número certo nos ERROS: quem está sendo ignorado
    ignorados = Counter()
    for x in erros:
        for nome in (x.get("quem_tinha") or []):
            ignorados[nome] += 1
    # A PERCEPCAO DELE, medida, nas TRES faixas que ele pediu.
    por_faixa = {}
    for nome in ("vazia", "media", "cheia"):
        g = [x for x in laudos if x.get("faixa") == nome]
        if g:
            por_faixa[nome] = {
                "n": len(g),
                "taxa": sum(1 for x in g if x.get("acertou")) / len(g),
            }
    cheia = [x for x in laudos if x.get("mesa_cheia") is True]
    vazia = [x for x in laudos if x.get("mesa_cheia") is False]
    taxa_cheia = (sum(1 for x in cheia if x.get("acertou")) / len(cheia)
                  if cheia else None)
    taxa_vazia = (sum(1 for x in vazia if x.get("acertou")) / len(vazia)
                  if vazia else None)

    n_err = len(erros) or 1
    return {
        "por_faixa": por_faixa,
        "n_cheia": len(cheia), "n_vazia": len(vazia),
        "taxa_cheia": taxa_cheia, "taxa_vazia": taxa_vazia,
        "n": len(laudos), "acertos": len(acertos), "erros": len(erros),
        "cegueira": tipos.get("cegueira", 0),
        "votacao": tipos.get("votacao", 0),
        "p_cegueira": tipos.get("cegueira", 0) / n_err,
        "p_votacao": tipos.get("votacao", 0) / n_err,
        "puxando": puxando.most_common(6),
        "ignorados": ignorados.most_common(6),
    }


def correcao(jogo: str, ultimos: int = 400) -> Dict[str, float]:
    """O conserto: quanto o peso de cada fonte deve mudar na próxima votação.

    A conta é uma só, e é justa porque compara igual com igual:

        taxa da fonte   = janelas em que ela tinha o número que saiu
                          ÷ janelas em que ela votou
        taxa da mesa    = a mesma coisa, somando todas as fontes
        correção        = taxa da fonte ÷ taxa da mesa

    Uma fonte que só vota quando tem certeza e uma que vota em tudo aparecem
    lado a lado nessa divisão — o denominador é o voto dela, não o total de
    janelas. Devolve `{}` enquanto não houver laudo suficiente, e nesse caso o
    motor roda com os pesos originais, sem nenhuma mexida.
    """
    laudos = [x for x in ler(jogo, ultimos) if x.get("fontes")]
    if not laudos:
        return {}
    votos: Counter = Counter()
    certeiros: Counter = Counter()
    for x in laudos:
        tinha = set(x.get("quem_tinha") or [])
        for f in (x.get("fontes") or []):
            votos[f] += 1
            if f in tinha:
                certeiros[f] += 1
    total_v = sum(votos.values())
    base = (sum(certeiros.values()) / total_v) if total_v else 0.0
    if base <= 0:
        # nenhuma fonte pegou nada ainda: não há o que corrigir, e inventar
        # um ajuste aqui seria mexer no motor por conta de nada
        return {}
    ajuste: Dict[str, float] = {}
    for f, v in votos.items():
        if v < MIN_JANELAS_FONTE:
            continue
        m = (certeiros[f] / v) / base
        m = min(TETO, max(PISO, m))
        if abs(m - 1.0) >= 0.05:      # mudança irrelevante não vira ruído
            ajuste[f] = round(m, 3)
    return ajuste


def texto_correcao(jogo: str, ultimos: int = 400) -> str:
    """A frase que aparece na tela quando o conserto entra em vigor."""
    a = correcao(jogo, ultimos)
    if not a:
        return ""
    sobe = sorted([x for x in a.items() if x[1] > 1], key=lambda x: -x[1])[:3]
    desce = sorted([x for x in a.items() if x[1] < 1], key=lambda x: x[1])[:3]
    partes = []
    if sobe:
        partes.append("sobe " + ", ".join(f"{n}×{m}" for n, m in sobe))
    if desce:
        partes.append("desce " + ", ".join(f"{n}×{m}" for n, m in desce))
    return "[Autópsia→conserto] " + " · ".join(partes)


def resumo(jogo: str, ultimos: int = 400) -> str:
    d = diagnostico(jogo, ultimos)
    if not d.get("n"):
        return f"[Autópsia] {jogo}: nenhuma janela dissecada ainda"
    L = [f"[Autópsia] {jogo}: {d['n']} janelas · "
         f"{d['acertos']} acertos · {d['erros']} erros"]
    if d["erros"]:
        L.append(f"   NÃO VIMOS o número     {d['cegueira']:>4} "
                 f"({d['p_cegueira']:.0%} dos erros) — pede teoria nova")
        L.append(f"   VIMOS e descartamos    {d['votacao']:>4} "
                 f"({d['p_votacao']:.0%} dos erros) — pede peso, não teoria")
    if d["puxando"]:
        L.append("   quem tinha o número nos ACERTOS: "
                 + ", ".join(f"{n}({c})" for n, c in d["puxando"]))
    if d["ignorados"]:
        L.append("   quem tinha o número nos ERROS e foi ignorado: "
                 + ", ".join(f"{n}({c})" for n, c in d["ignorados"]))
    pf = d.get("por_faixa") or {}
    if pf:
        rot = {"vazia": "vazia (não jogar)", "media": "média (talvez)",
               "cheia": "cheia (bom para jogar)"}
        L.append("   por público — a percepção dele, medida:")
        for nome in ("vazia", "media", "cheia"):
            if nome in pf:
                L.append(f"      {rot[nome]:<26} {pf[nome]['taxa']:>5.0%} "
                         f"em {pf[nome]['n']} janelas")
    tc = texto_correcao(jogo, ultimos)
    if tc:
        L.append("   " + tc + "  (já valendo no próximo sinal)")
    if d["n"] < MIN_PARA_CONCLUIR:
        L.append(f"   ⚠ só {d['n']} janelas — ainda é cedo para concluir")
    elif d.get("p_votacao", 0) > 0.4:
        L.append("   >> a maioria dos erros é de VOTAÇÃO: o número estava na "
                 "mesa e perdeu a vaga. Mexer nos pesos rende mais que "
                 "inventar teoria nova.")
    elif d.get("p_cegueira", 0) > 0.7:
        L.append("   >> a maioria dos erros é CEGUEIRA: ninguém tinha o "
                 "número. É teoria que falta, não peso — o captador é o "
                 "caminho.")
    return "\n".join(L)
