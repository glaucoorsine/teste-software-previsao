# -*- coding: utf-8 -*-
"""
A PREVISÃO — as duas fontes juntas, cada uma dizendo de onde veio.

O DESENHO QUE ELE MANDOU
────────────────────────
    "esse novo software tem que ter aquela base que identificava o
     multiplicador... e as outras IAs elas vão trabalhar somente com base no
     que está nos três PDFs"

Então são duas fontes, e só duas:

    RODA     as 44 famílias dele lendo a série de resultados
    CANAL    as mesmas 44 famílias lendo a série anunciada (lucky / fire /
             top slot), que tem de 3 a 5 vezes mais observações

Nenhuma heurística minha entra em nenhuma das duas. O que muda entre elas não
é o método, é o DADO que o método lê -- e o canal só participa depois de
provar, medindo, que prevê o resultado nesta mesa.

POR QUE O CANAL NÃO PESA IGUAL À RODA
─────────────────────────────────────
Porque a pergunta é sobre o resultado, e a roda é o resultado. O canal é uma
segunda testemunha do mesmo processo -- valiosa por ver mais, mas indireta.
O peso dele não é chute meu: sai da FORÇA DO ACOPLAMENTO medida naquela mesa.
Acoplamento de 1,7x pesa mais que acoplamento de 1,1x, e acoplamento ausente
pesa zero porque nem entra.

    peso_do_canal = min(1.0, razão_do_acoplamento - 1.0)

Um canal que prevê 2x melhor que o acaso chega a pesar tanto quanto a roda;
um que prevê 1,05x pesa 0,05. A conta é essa, e ela se ajusta sozinha por
mesa e por semana.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import agregacao as A
from . import base as B
from . import canal_anunciado as C
from . import leituras as L


def prever(historico: List[dict], jogo: str, k: int = 12,
           perdas: Optional[Dict[str, float]] = None,
           acordado: Optional[Dict[str, int]] = None,
           memoria: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """A lista final, com procedência de cada número.

    `historico` chega recente-primeiro, no formato do software: linhas com
    `n` (resultado) e `tags` (o anúncio daquele giro).
    """
    n_classes = B.classes_de(jogo)

    # ── fonte 1: as 44 famílias lendo a roda ────────────────────────────
    serie = C.serie_de_resultados(C.rodadas(historico, jogo))
    mults = _mults_por_giro(historico, jogo)
    roda = L.executar(serie, n_classes, {"mults": mults}, k=k)

    # ── fonte 2: as mesmas 44 lendo o canal anunciado ───────────────────
    canal = C.ler(historico, jogo, n_classes, k=k)

    pesos: Dict[str, Dict[str, float]] = dict(roda["pesos"])
    if canal.get("vota"):
        razao = float((canal.get("acoplamento") or {}).get("razao") or 1.0)
        w = max(0.0, min(1.0, razao - 1.0))
        for nome, peso in (canal.get("pesos") or {}).items():
            pesos[nome] = {c: v * w for c, v in peso.items()}

    ag = A.consenso(pesos, perdas, acordado, memoria, k=k)

    # ── de onde veio cada número, para conferência no livro ─────────────
    procedencia: Dict[str, List[str]] = {}
    for classe in ag["ordem"]:
        fontes = []
        for quem in ag["quem"].get(classe, []):
            fam = quem.replace("CANAL_", "")
            end = B.endereco(fam, jogo)
            marca = "canal" if quem.startswith("CANAL_") else "roda"
            if end:
                fontes.append(f"[{marca}] {end}")
        procedencia[classe] = fontes[:3]

    return {
        "numeros": ag["ordem"],
        "placar": ag["placar"],
        "robustez": ag["robustez"],
        "quem": ag["quem"],
        "procedencia": procedencia,
        "roda": {"apontaram": roda["apontaram"], "total": roda["total"],
                 "falas": roda["falas"]},
        "canal": canal,
        "n_classes": n_classes,
    }


def _mults_por_giro(historico: List[dict], jogo: str) -> List[float]:
    """O maior multiplicador anunciado em cada giro, alinhado com a série."""
    fora: List[float] = []
    for r in C.rodadas(historico, jogo):
        vals = [v for v in (r.get("x") or {}).values() if v]
        fora.append(max(vals) if vals else 0.0)
    return fora


def explicar(r: Dict[str, Any], jogo: str, quantos: int = 5) -> str:
    """A previsão em português, com o endereço de cada número no livro dele."""
    L_ = [f"[Previsão] {' '.join(r['numeros'][:12])}"]
    c = r.get("canal") or {}
    L_.append(f"   roda: {r['roda']['apontaram']} das {r['roda']['total']} "
              f"famílias apontaram")
    if c.get("vota"):
        ac = c.get("acoplamento") or {}
        L_.append(f"   canal: {c.get('apontaram')} das {c.get('total')} — "
                  f"acoplamento {ac.get('razao', 0):.2f}x (p={ac.get('p', 1):.4f})")
    else:
        L_.append(f"   canal: não vota — {c.get('motivo', '')[:64]}")
    L_.append("   de onde veio cada número:")
    for classe in r["numeros"][:quantos]:
        rob = r["robustez"].get(classe, 0)
        L_.append(f"      {classe:>3}  robustez {rob:.0%}  "
                  f"{len(r['quem'].get(classe, []))} leituras")
        for fonte in r["procedencia"].get(classe, [])[:2]:
            L_.append(f"            {fonte[:76]}")
    return "\n".join(L_)
