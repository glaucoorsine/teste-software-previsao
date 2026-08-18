# -*- coding: utf-8 -*-
"""
CONFERÊNCIA — o sorteio saiu; o que as apostas dele fizeram?

POR QUE ISTO FECHA O CICLO
──────────────────────────
Todo o resto do software fala do futuro condicional: "se sair, garante". Este
arquivo é onde a promessa encontra o sorteio de verdade — e onde ela pode ser
DESMENTIDA. Se um fechamento prometeu quadra com 5 acertos entre as dezenas
dele, cada concurso em que a condição acontecer é um teste da promessa, com
dinheiro em cima. A auditoria daqui diz "a garantia previa X, aconteceu Y" — e
se algum dia Y < X, isso é defeito PROVADO no meu fechamento, na tela, sem
desculpa possível.

É o mesmo desenho do teste destrutivo, levado para a produção: um verificador
que só sabe aprovar não verifica nada.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import regras

# a linha de cabeçalho que EMPACOTA a promessa junto com as apostas.
# Fica no arquivo porque a promessa longe das apostas não audita nada.
_META = re.compile(r"#\s*fechamento\s+se=(\d+)\s+garantir=(\d+)\s+"
                   r"dezenas=([\d\s]+)")


def escrever_apostas(caminho, apostas: Sequence[Sequence[int]],
                     jogo_chave: str,
                     meta: Optional[Dict[str, Any]] = None) -> Path:
    """Grava as apostas — e a promessa, se houver — num texto simples.

    Texto simples de propósito: ele abre no bloco de notas, confere no volante,
    e o leitor de histórico já sabe ler este formato. Nada de formato que só o
    software entende.
    """
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    linhas = [f"# apostas de {jogo_chave}"]
    if meta:
        linhas.append(f"# fechamento se={meta['se']} garantir={meta['garantir']} "
                      f"dezenas=" + " ".join(str(d) for d in meta["dezenas"]))
    for a in apostas:
        linhas.append(" ".join(f"{d:02d}" for d in sorted(a)))
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return p


def ler_apostas(caminho, jogo: regras.Jogo
                ) -> Tuple[List[List[int]], Optional[Dict[str, Any]], List[str]]:
    """Lê as apostas e a promessa. Devolve (apostas, meta, avisos)."""
    avisos: List[str] = []
    p = Path(caminho)
    if not p.exists():
        return [], None, [f"não achei o arquivo de apostas: {p}"]
    meta: Optional[Dict[str, Any]] = None
    apostas: List[List[int]] = []
    for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        t = linha.strip()
        if not t:
            continue
        m = _META.match(t)
        if m:
            meta = {"se": int(m.group(1)), "garantir": int(m.group(2)),
                    "dezenas": sorted(int(x) for x in m.group(3).split())}
            continue
        if t.startswith("#"):
            continue
        nums = [int(x) for x in re.split(r"[^\d]+", t) if x]
        if not nums:
            continue
        ok, motivo = jogo.valida_aposta(nums)
        if not ok:
            # aposta inválida não entra calada: ela seria recusada no guichê,
            # e conferir o que não foi jogado é conferir fantasia
            avisos.append(f"linha {n} ignorada — {motivo}")
            continue
        apostas.append(sorted(nums))
    return apostas, meta, avisos


def conferir(jogo: regras.Jogo, apostas: Sequence[Sequence[int]],
             sorteio: Sequence[int]) -> Dict[str, Any]:
    """Cada aposta contra o sorteio: acertos, e se paga alguma faixa.

    O sorteio é validado ANTES: conferir apostas contra um "sorteio" com 5
    dezenas ou com dezena fora do universo produziria acertos plausíveis e
    falsos — o erro mudo de sempre, no lugar mais caro possível.
    """
    s = sorted(set(int(x) for x in sorteio))
    if len(s) != jogo.sorteadas:
        return {"ok": False,
                "nota": f"um sorteio de {jogo.nome} tem {jogo.sorteadas} "
                        f"dezenas distintas; este tem {len(s)}"}
    fora = [x for x in s if x not in set(jogo.dezenas())]
    if fora:
        return {"ok": False,
                "nota": f"dezenas fora do universo de {jogo.nome}: {fora}"}
    if not apostas:
        return {"ok": False, "nota": "nenhuma aposta para conferir"}

    alvo = set(s)
    resultados: List[Dict[str, Any]] = []
    por_faixa: Dict[int, int] = {}
    for a in apostas:
        acertos = len(alvo & set(a))
        paga = acertos in jogo.faixas       # a Lotomania paga 0 — e isto cobre
        resultados.append({"aposta": sorted(a), "acertos": acertos,
                           "paga": paga})
        if paga:
            por_faixa[acertos] = por_faixa.get(acertos, 0) + 1
    melhor = max(r["acertos"] for r in resultados)
    return {"ok": True, "sorteio": s, "resultados": resultados,
            "por_faixa": dict(sorted(por_faixa.items(), reverse=True)),
            "melhor": melhor,
            "premiadas": sum(1 for r in resultados if r["paga"])}


def auditar_garantia(meta: Dict[str, Any], apostas: Sequence[Sequence[int]],
                     sorteio: Sequence[int]) -> Dict[str, Any]:
    """A promessa do fechamento, contra o que o sorteio fez de verdade.

    Três saídas possíveis, e as três são ditas por extenso:
      a condição não aconteceu   → a garantia não prometia nada hoje
      aconteceu e foi honrada    → a promessa valeu, com os números
      aconteceu e FALHOU         → defeito provado no meu fechamento; a tela
                                   manda me mostrar, porque isso não pode ser
    """
    dez = set(meta["dezenas"])
    saiu = len(dez & set(sorteio))
    se, garantir = int(meta["se"]), int(meta["garantir"])
    if saiu < se:
        return {"aplicavel": False, "saiu": saiu, "se": se,
                "garantir": garantir, "honrada": None,
                "nota": f"das suas {len(dez)} dezenas saíram {saiu}; a "
                        f"garantia só prometia algo a partir de {se}. Hoje ela "
                        f"não prometia nada — e não falhou nada."}
    melhor = max((len(set(a) & set(sorteio)) for a in apostas), default=0)
    honrada = melhor >= garantir
    if honrada:
        nota = (f"saíram {saiu} das suas dezenas (≥ {se}): a garantia prometia "
                f"{garantir} acertos em alguma aposta, e a melhor fez {melhor}. "
                f"PROMESSA HONRADA.")
    else:
        nota = (f"saíram {saiu} das suas dezenas (≥ {se}), a garantia prometia "
                f"{garantir} acertos e a melhor aposta fez só {melhor}. A "
                f"GARANTIA FALHOU — isso é defeito provado no meu fechamento. "
                f"Me mostre esta tela: ou as apostas do arquivo não são as do "
                f"fechamento, ou a prova mentiu, e eu preciso saber qual dos "
                f"dois.")
    return {"aplicavel": True, "saiu": saiu, "se": se, "garantir": garantir,
            "melhor": melhor, "honrada": honrada, "nota": nota}


def resumo(jogo: regras.Jogo, r: Dict[str, Any],
           auditoria: Optional[Dict[str, Any]] = None) -> List[str]:
    if not r.get("ok"):
        return [f"[Conferência] {r.get('nota')}"]
    L = [f"[Conferência] {jogo.nome} — sorteio: "
         + "  ".join(f"{d:02d}" for d in r["sorteio"])]
    for res in r["resultados"]:
        marca = "★" if res["paga"] else " "
        L.append(f"[Conferência]  {marca} "
                 + "  ".join(f"{d:02d}" for d in res["aposta"])
                 + f"   → {res['acertos']} acertos"
                 + ("  (paga)" if res["paga"] else ""))
    if r["por_faixa"]:
        faixas = ", ".join(f"{q}× {f} acertos"
                           for f, q in r["por_faixa"].items())
        L.append(f"[Conferência] premiadas: {r['premiadas']} de "
                 f"{len(r['resultados'])} — {faixas}")
    else:
        L.append(f"[Conferência] nenhuma aposta premiada; a melhor fez "
                 f"{r['melhor']} acertos")
    if auditoria is not None:
        L.append(f"[Conferência] {auditoria['nota']}")
    return L
