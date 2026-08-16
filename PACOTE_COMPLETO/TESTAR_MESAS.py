# -*- coding: utf-8 -*-
"""
DESCOBRIR CRAZY TIME A — para de adivinhar o endereço e vai procurar.

POR QUE ISTO EXISTE
-------------------
Ele reclamou quatro vezes que a mesa não abre. Eu tentei adivinhar o nome do
endereço três vezes e errei as três — e só descobri que era 404 quando o log
passou a gravar o motivo.

O problema é que EU não posso testar: o ambiente onde escrevo o código bloqueia
o domínio do provedor. A máquina dele não bloqueia. Então quem tem que procurar
é ela.

Este programa varre as grafias plausíveis do nome, diz qual respondeu, e GRAVA
a que funcionou. Depois disso o laboratório usa ela sozinho, para sempre.

    python DESCOBRIR_CRAZY_TIME_A.py
    (ou clique duas vezes em DESCOBRIR_CRAZY_TIME_A.bat)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

BASE_CASINO = "https://api-cs.casino.org/svc-evolution-game-events/api/"
BASE_TRACK = "https://api.trackpotapi.com/api/trackersino/"

# As grafias que valem tentar. Ordem: as mais parecidas com as que funcionam
# nas outras mesas vêm primeiro.
# O PADRAO DOS NOMES, confirmado olhando as mesas que funcionam:
# a pagina /casinoscores/crazy-time/ corresponde ao endpoint /api/crazytime --
# ou seja, tira os hifens. Por isso "crazytimea" era a aposta obvia, e ela deu
# 404. Entao o provedor OU usa outro nome, OU nao publica esta mesa separada e
# os dados dela vem junto com os do Crazy Time, com um campo dizendo a mesa.
#
# A segunda hipotese e testada em `procurar_campo_de_mesa()`, abaixo.
NOMES_CASINO = [
    "crazytimea", "crazytime-a", "crazytimeA", "crazy-time-a", "crazytime2",
    "crazytimeatable", "crazytimeaevolution", "crazy-timea", "crazytime_a",
    "crazytimeslive", "crazytimea-live", "crazytimealive",
]
NOMES_TRACK = [
    "crazy-time-a", "crazytimea", "crazy-time-a-live", "crazytime-a",
    "crazy-time", "crazytime",
]

CABECALHO = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0"),
    "Accept": "application/json",
    "Origin": "https://www.casino.org",
    "Referer": "https://www.casino.org/casinoscores/pt-br/",
}


def _tentar(url, requests):
    """Devolve (ok, descricao). ok=True significa que veio dado de verdade."""
    try:
        r = requests.get(url, headers=CABECALHO,
                         params={"size": 5, "page": 0}, timeout=15)
    except Exception as e:
        return False, f"{type(e).__name__}"
    if r.status_code == 404:
        return False, "404 (este nome não existe)"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    txt = (r.text or "").strip()
    if not txt or txt in ("[]", "{}"):
        return False, "respondeu vazio"
    # tem que trazer algo que pareça resultado
    try:
        d = json.loads(txt)
    except ValueError:
        return False, "respondeu, mas não é JSON"
    n = len(d) if isinstance(d, list) else len(d.get("data") or d.get("items") or [])
    if not n:
        return False, "JSON sem resultados dentro"
    return True, f"OK — {n} resultados, {len(txt)} bytes"


def testar_todas(requests) -> int:
    """Diz, mesa por mesa, se a fonte responde AGORA.

    Ele relatou "crazy time a e immersive nao funcionam" -- e mesa que nao
    funciona pode ser tres coisas muito diferentes: endereco errado, fonte fora
    do ar, ou internet. A tela dele mostra as tres do mesmo jeito ("sem dados"),
    e sem separar isso eu volto a adivinhar.
    """
    from fluxo_captura import enderecos_para, HEADERS
    mesas = ("mega_fire", "lightning", "immersive", "crazy_time", "crazy_time_a")
    print("\n" + "=" * 66)
    print("  AS CINCO MESAS, AGORA")
    print("=" * 66)
    ruins = 0
    for m in mesas:
        urls = enderecos_para(m) or []
        print(f"\n  {m}")
        if not urls:
            print("     sem endereco cadastrado"); ruins += 1; continue
        achou = False
        for u in urls[:6]:
            try:
                r = requests.get(u, headers=HEADERS,
                                 params={"size": 5, "page": 0}, timeout=15)
                cod = r.status_code
                tam = len(r.text or "")
            except Exception as e:
                print(f"     {type(e).__name__:<22} {u[-42:]}")
                continue
            marca = "OK  " if (cod == 200 and tam > 40) else "    "
            print(f"     {marca}HTTP {cod}  {tam:>7} bytes  {u[-42:]}")
            if cod == 200 and tam > 40:
                achou = True
                break
        if not achou:
            ruins += 1
    print("\n" + "=" * 66)
    if ruins:
        print(f"  {ruins} mesa(s) sem fonte respondendo.")
        print("  Me mande esta tela: com ela eu sei se e endereco errado,")
        print("  fonte fora do ar ou a sua internet -- sao consertos diferentes.")
    else:
        print("  Todas as cinco responderam. Se alguma nao aparece na tela,")
        print("  o problema esta depois da captura, e o log vai dizer onde.")
    print("=" * 66 + "\n")
    return 0 if not ruins else 1


def procurar_campo_de_mesa(requests) -> None:
    """E se o Crazy Time A vier junto com o Crazy Time, marcado por um campo?

    A pagina do provedor separa as duas mesas, mas isso nao obriga a API a ter
    dois enderecos. Se a resposta do /crazytime trouxer algo como "tableId" ou
    "table": "A", entao a mesa A ja esta chegando aqui -- misturada -- e o
    conserto e filtrar, nao procurar endereco.
    """
    from fluxo_captura import API_BY_GAME, HEADERS
    print("\n" + "=" * 66)
    print("  E SE AS DUAS MESAS VIEREM NO MESMO ENDERECO?")
    print("=" * 66)
    try:
        r = requests.get(API_BY_GAME["crazy_time"], headers=HEADERS,
                         params={"size": 20, "page": 0}, timeout=20)
        if r.status_code != 200:
            print(f"  o endereco do Crazy Time respondeu HTTP {r.status_code}")
            return
        d = json.loads(r.text)
    except Exception as e:
        print(f"  nao deu para conferir: {type(e).__name__}")
        return
    itens = d if isinstance(d, list) else (d.get("data") or d.get("items") or [])
    if not itens:
        print("  respondeu sem itens dentro")
        return
    # procura qualquer chave que cheire a identificacao de mesa
    achadas = {}

    def varrer(o, prof=0):
        if prof > 4 or not isinstance(o, dict):
            return
        for k, v in o.items():
            if any(p in k.lower() for p in ("table", "mesa", "studio", "room")):
                achadas.setdefault(k, set()).add(str(v)[:30])
            if isinstance(v, dict):
                varrer(v, prof + 1)

    for it in itens[:20]:
        varrer(it if isinstance(it, dict) else {})
    if not achadas:
        print("  Nenhum campo de mesa na resposta. As duas mesas sao mesmo")
        print("  separadas, e o que falta e o endereco certo da segunda.")
    else:
        print("  ACHEI campos que identificam mesa:")
        for k, vs in achadas.items():
            print(f"     {k} = {sorted(vs)[:6]}")
        print()
        print("  Se aparecer mais de um valor ai, as duas mesas ja estao")
        print("  chegando juntas -- e o conserto e filtrar por este campo,")
        print("  nao procurar endereco. Me mande esta tela.")
    print("=" * 66)


def main() -> int:
    try:
        import requests
    except ImportError:
        print("\n  Falta a biblioteca requests. Rode 0_INSTALAR_DEPENDENCIAS.bat\n")
        return 1

    # primeiro o retrato geral: qual mesa responde e qual nao
    testar_todas(requests)

    print("\n" + "=" * 66)
    print("  PROCURANDO O ENDEREÇO DO CRAZY TIME A")
    print("=" * 66)
    print("  Vou tentar cada nome possível e dizer qual responde.")
    print("  Isso leva menos de um minuto.\n")

    alvos = ([(BASE_CASINO + n, n) for n in NOMES_CASINO]
             + [(BASE_TRACK + n + "/history", n) for n in NOMES_TRACK])
    achados = []
    for i, (url, nome) in enumerate(alvos, 1):
        onde = "casino.org" if url.startswith(BASE_CASINO) else "trackpot"
        print(f"  [{i:>2}/{len(alvos)}] {onde:<11} {nome:<22} ", end="", flush=True)
        ok, msg = _tentar(url, requests)
        print(msg)
        if ok:
            achados.append((url, nome, msg))
        time.sleep(0.4)          # sem pressa: nao vale ser bloqueado por afobação

    print("\n" + "=" * 66)
    if not achados:
        procurar_campo_de_mesa(requests)
        print("\n  NENHUM endereço respondeu com dados.")
        print()
        print("  Isso quer dizer que o provedor não publica esta mesa por API,")
        print("  ou publica com um nome que não está na minha lista.")
        print()
        print("  O que fazer: me mande esta tela inteira. Com ela eu sei o que")
        print("  já foi descartado e paro de tentar os mesmos nomes.")
        print("=" * 66 + "\n")
        return 1

    url, nome, msg = achados[0]
    print(f"  ACHEI: {nome}")
    print(f"  {url}")
    print(f"  {msg}")
    if len(achados) > 1:
        print(f"\n  (outros {len(achados)-1} também responderam; fico com o primeiro)")
    try:
        from fluxo_captura import _lembrar_fonte
        _lembrar_fonte("crazy_time_a", url)
        print("\n  Gravado. O laboratório vai usar este endereço a partir de agora,")
        print("  sem procurar de novo.")
    except Exception as e:
        print(f"\n  Não consegui gravar ({type(e).__name__}). Me mande esta tela.")
    print("=" * 66 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
