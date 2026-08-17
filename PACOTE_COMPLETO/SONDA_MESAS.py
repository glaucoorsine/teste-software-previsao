# -*- coding: utf-8 -*-
"""
SONDA DAS MESAS — mostra a resposta CRUA da API, para acabar com o chute.

POR QUE ESTE ARQUIVO EXISTE, DITO SEM ENFEITE
─────────────────────────────────────────────
Ele contou dezoito versões com o mesmo erro, e está certo. A razão é uma só e é
minha: eu nunca vi uma resposta desta API. O proxy do ambiente onde eu rodo nega
`casino.org` por política — confirmado, com o 403 no CONNECT registrado. Então
toda vez que faltou um nome de campo eu ADIVINHEI: `fireNumbers`, `blazeNumbers`,
`superBoost`, `crazytimea`, `crazytime-a`, `crazytimeA`, `crazytime2`. Cada
palpite virou uma versão, cada versão voltou com o mesmo defeito de outra cor.

Adivinhar de novo seria repetir o método que já falhou dezoito vezes.

Esta sonda inverte isso. Ela roda na máquina DELE — onde a API responde — e
grava um arquivo pequeno com a resposta de verdade. Com esse arquivo, os
defeitos que hoje dependem de sorte viram leitura:

    1. QUAL É O ENDEREÇO DA CRAZY TIME A. A sonda lista os endereços que a
       página da mesa cita nos scripts (o log dele mostrou 17) e diz o que cada
       um respondeu. Se o endereço existe, ele está nessa lista.

    2. ONDE ESTÁ O MULTIPLICADOR QUE PAGOU. Ele mostrou a mesa: giro 10 com
       "Multip. 40X" e o software escrevendo "×4". O software está lendo o Top
       Slot (4X) e chamando de multiplicador; quem pagou foi 40X. O mesmo vale
       no Lightning e no Mega Fire. Com o JSON cru na mão eu vejo qual campo é
       qual, em vez de tentar mais um nome.

    3. SE DUAS MESAS SÃO A MESMA. A sonda compara os giros que cada endereço
       devolveu. Dois endereços com a mesma sequência são a mesma mesa, tenham
       o nome que tiverem — e essa é a prova que não depende de grafia nenhuma.

O QUE ELA NÃO FAZ
─────────────────
Não muda nada. Não grava fonte, não mexe no histórico, não escreve na memória.
Só lê e relata. Rodar isto não pode piorar o que já está rodando.

E O ARQUIVO É PEQUENO DE PROPÓSITO
──────────────────────────────────
No máximo três giros por endereço. O que eu preciso é a FORMA da resposta — os
nomes dos campos e onde o valor mora. Trezentos giros não me dizem mais que três
sobre isso, e um arquivo grande é um arquivo que ele não vai conseguir mandar.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

SAIDA = RAIZ / "Logs" / "sonda_mesas.json"
MAX_GIROS = 3
TIMEOUT = 20

MESAS = ("lightning", "mega_fire", "crazy_time", "crazy_time_a")


def _linha(txt: str = "") -> None:
    print(txt, flush=True)


def _encolher(obj: Any, fundo: int = 0) -> Any:
    """Corta listas longas mantendo a FORMA. É a forma que me interessa."""
    if fundo > 8:
        return "…"
    if isinstance(obj, dict):
        return {k: _encolher(v, fundo + 1) for k, v in list(obj.items())[:40]}
    if isinstance(obj, list):
        return [_encolher(x, fundo + 1) for x in obj[:MAX_GIROS]]
    if isinstance(obj, str) and len(obj) > 300:
        return obj[:300] + "…"
    return obj


def _buscar(url: str) -> Dict[str, Any]:
    """Uma consulta, com o que voltou e o que deu errado."""
    import urllib.request
    cab = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept": "application/json,text/plain,*/*"}
    alvo = url + ("&" if "?" in url else "?") + "size=5&page=0"
    t0 = time.time()
    try:
        req = urllib.request.Request(alvo, headers=cab)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            bruto = r.read(400_000).decode("utf-8", "ignore")
            codigo = r.status
    except Exception as e:
        return {"url": url, "erro": f"{type(e).__name__}: {e}"[:160],
                "segundos": round(time.time() - t0, 1)}
    fora: Dict[str, Any] = {"url": url, "http": codigo,
                            "segundos": round(time.time() - t0, 1),
                            "bytes": len(bruto)}
    try:
        fora["json"] = _encolher(json.loads(bruto))
    except Exception:
        fora["nao_e_json"] = bruto[:400]
    return fora


def _valores(resposta: Dict[str, Any]) -> List[str]:
    """Os giros que este endereço devolveu, para comparar mesas.

    Usa o parser do próprio software: se ele não conseguir ler, isso também é
    informação — quer dizer que o formato mudou.
    """
    try:
        import fluxo_captura as F
        bruto = resposta.get("json")
        if bruto is None:
            return []
        itens = bruto if isinstance(bruto, list) else (
            bruto.get("data") or bruto.get("items") or bruto.get("results") or [])
        if not isinstance(itens, list):
            return []
        linhas = F.parse_items_ct(itens) or F.parse_items_roulette(itens)
        return [f"{l.get('n')}@{l.get('settled')}" for l in linhas[:MAX_GIROS]]
    except Exception:
        return []


def sondar() -> Dict[str, Any]:
    import fluxo_captura as F

    relatorio: Dict[str, Any] = {
        "quando": time.strftime("%Y-%m-%d %H:%M:%S"),
        "para_que": ("mostrar a resposta CRUA da API. Sem isto eu adivinho nome "
                     "de campo, e adivinhar foi o que falhou dezoito vezes."),
        "mesas": {},
    }

    for mesa in MESAS:
        _linha("")
        _linha("=" * 68)
        _linha(f"  {mesa}")
        _linha("=" * 68)
        item: Dict[str, Any] = {"enderecos": [], "paginas": []}

        # ── 1. o que a PÁGINA da mesa cita nos scripts ────────────────────
        try:
            from descobridor_pela_pagina import enderecos_citados
            for pag in F.enderecos_html(mesa)[:1]:
                _linha(f"  lendo a página {pag}")
                try:
                    citados = enderecos_citados(pag) or []
                except Exception as e:
                    citados = []
                    _linha(f"    (não deu: {type(e).__name__})")
                item["paginas"].append({"pagina": pag,
                                        "citados": [str(c) for c in citados[:40]]})
                _linha(f"    {len(citados)} endereço(s) citados na página")
                for c in citados[:40]:
                    _linha(f"      {c}")
        except Exception as e:
            item["erro_pagina"] = f"{type(e).__name__}: {e}"

        # ── 2. o que cada endereço RESPONDE ──────────────────────────────
        candidatos = list(F.enderecos_para(mesa))
        # junta os que a página citou e que ninguém tentaria por conta própria
        for p in item["paginas"]:
            for c in p.get("citados") or []:
                if c.startswith("http") and c not in candidatos:
                    candidatos.append(c)
        for url in candidatos[:14]:
            _linha(f"  consultando {url}")
            r = _buscar(url)
            r["giros_lidos"] = _valores(r)
            item["enderecos"].append(r)
            marca = (f"HTTP {r.get('http')}" if r.get("http")
                     else r.get("erro", "?"))
            _linha(f"    {marca}  {r.get('bytes', 0)}b  "
                   f"giros: {r['giros_lidos'][:2]}")
        relatorio["mesas"][mesa] = item

    # ── 3. duas mesas com a MESMA sequência são a mesma mesa ─────────────
    #
    # Esta é a prova que não depende de grafia. Eu venho tentando decidir de
    # quem é o endereço pelo NOME dele; o nome pode enganar e a sequência não.
    iguais = []
    assinatura: Dict[str, str] = {}
    for mesa, dados in relatorio["mesas"].items():
        for e in dados["enderecos"]:
            g = e.get("giros_lidos") or []
            if len(g) >= 2:
                assinatura[f"{mesa} ← {e['url']}"] = "|".join(g[:MAX_GIROS])
    chaves = list(assinatura)
    for i, a in enumerate(chaves):
        for b in chaves[i + 1:]:
            if assinatura[a] and assinatura[a] == assinatura[b]:
                iguais.append([a, b])
    relatorio["mesmas_sequencias"] = iguais

    _linha("")
    _linha("=" * 68)
    if iguais:
        _linha("  ENDEREÇOS QUE DEVOLVERAM A MESMA SEQUÊNCIA (são a mesma mesa):")
        for a, b in iguais:
            _linha(f"    {a}")
            _linha(f"    {b}")
            _linha("")
    else:
        _linha("  nenhum par de endereços devolveu a mesma sequência")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(relatorio, ensure_ascii=False, indent=1,
                                default=str), encoding="utf-8")
    _linha("=" * 68)
    _linha(f"  arquivo gravado: {SAIDA}")
    _linha("")
    _linha("  MANDE ESTE ARQUIVO. Com ele eu vejo:")
    _linha("    · qual é o endereço real da Crazy Time A")
    _linha("    · em que campo mora o multiplicador que PAGOU (o 40X, não o 4X)")
    _linha("    · se duas mesas estão lendo a mesma coisa")
    _linha("")
    _linha("  Sem ele eu volto a adivinhar, e adivinhar foi o que falhou.")
    return relatorio


if __name__ == "__main__":
    try:
        sondar()
    except KeyboardInterrupt:
        _linha("\n  interrompido")
    input("\n  Enter para fechar...")
