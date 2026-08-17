# -*- coding: utf-8 -*-
"""
DESCOBRIDOR — acha sozinho o endereço de uma mesa, em vez de eu chutar.

O PROBLEMA, QUE JÁ DURA SEMANAS
───────────────────────────────
    "crazy time a, e immersive nao funcionam"

Minha resposta até agora foi escrever à mão uma lista de endereços plausíveis
e torcer. Oito palpites para o Crazy Time A. Se o provedor chamar a mesa de
qualquer outra coisa, a mesa não abre e eu não tenho como descobrir daqui --
o proxy deste ambiente bloqueia os dois domínios, então quem consegue testar
é sempre a máquina dele.

Pior: `coletor_sites.py`, que é a fonte alternativa, NÃO TINHA ENTRADA para
`crazy_time_a`. A segunda fonte nunca era tentada nessa mesa. O software tinha
duas fontes e usava zero.

O QUE MUDA AQUI
───────────────
Em vez de uma lista escrita à mão, as grafias são GERADAS a partir do nome da
mesa, cobrindo as convenções que esses provedores usam:

    "Crazy Time A"  →  crazytimea · crazy-time-a · crazy_time_a · crazytime-a
                       crazytimeA · crazy-time-a-live · crazytime2 · ...

São dezenas por mesa em vez de oito, e a geração é a mesma para qualquer mesa
nova que ele queira acrescentar depois.

E TESTAR É DE VERDADE
─────────────────────
Responder 200 não basta: muita API devolve página de erro com código 200, ou
uma lista vazia. Um endereço só é aceito quando devolve GIROS RECONHECÍVEIS --
número de roleta em 0..36, ou segmento de Crazy Time. Sem isso, o software
"acha" uma fonte e passa a prever sobre lixo.

O que funcionar fica gravado em `Logs/fontes_que_funcionam.json`, e daí em
diante é tentado primeiro. A descoberta acontece uma vez.
"""
from __future__ import annotations

import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent
MEMORIA = RAIZ / "Logs" / "fontes_que_funcionam.json"

TEMPO_LIMITE = 8            # por tentativa; são muitas, e em paralelo
PARALELAS = 6
MIN_GIROS = 5               # abaixo disso não dá para dizer que a fonte serve

# Os dois provedores, com o lugar do slug marcado.
MOLDES = (
    "https://api-cs.casino.org/svc-evolution-game-events/api/{}",
    "https://api.trackpotapi.com/api/trackersino/{}/history",
)

# O nome de cada mesa como um humano escreveria. É daqui que as grafias saem.
NOMES: Dict[str, List[str]] = {
    "mega_fire": ["Mega Fire Blaze Roulette", "Mega Fire Blaze",
                  "Fire Blaze Roulette"],
    "lightning": ["Lightning Roulette"],
    "crazy_time": ["Crazy Time"],
    "crazy_time_a": ["Crazy Time A", "Crazy Time 2", "Crazy Time A Live",
                     "Crazy Time Alt", "Crazy TimeA"],
}

SEGMENTOS_CT = {"1", "2", "5", "10", "coinflip", "coin flip", "cashhunt",
                "cash hunt", "pachinko", "crazytime", "crazy time"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def grafias(nome: str) -> List[str]:
    """As formas plausíveis de escrever este nome numa URL.

    Cobre o que esses provedores realmente usam: tudo junto, com hífen, com
    sublinhado, e a última palavra colada ou separada -- que é justamente onde
    o "A" do Crazy Time A costuma se perder.
    """
    limpo = _sem_acento(nome).strip()
    partes = [p for p in re.split(r"\s+", limpo) if p]
    if not partes:
        return []
    baixo = [p.lower() for p in partes]

    fora = [
        "".join(baixo),                       # crazytimea
        "-".join(baixo),                      # crazy-time-a
        "_".join(baixo),                      # crazy_time_a
        "".join(baixo[:-1]) + "-" + baixo[-1],   # crazytime-a
        "-".join(baixo[:-1]) + baixo[-1],        # crazy-timea
        "".join(baixo[:-1]) + partes[-1],        # crazytimeA (última como veio)
    ]
    # sem a palavra "roulette", que às vezes some do slug
    if len(baixo) > 1 and baixo[-1] == "roulette":
        curto = baixo[:-1]
        fora += ["".join(curto), "-".join(curto)]
    # e com ela acrescentada, quando não está
    if "roulette" not in baixo:
        fora += ["".join(baixo) + "roulette", "-".join(baixo) + "-roulette"]
    # sem espaços duplicados nem vazios, preservando a ordem
    vistos, saida = set(), []
    for g in fora:
        g = re.sub(r"-{2,}", "-", g).strip("-_")
        if g and g not in vistos:
            vistos.add(g)
            saida.append(g)
    return saida


def candidatos(jogo: str) -> List[str]:
    """Todos os endereços a experimentar para esta mesa, sem repetir."""
    urls, vistos = [], set()
    for nome in NOMES.get(jogo, []):
        for g in grafias(nome):
            for molde in MOLDES:
                u = molde.format(g)
                if u not in vistos:
                    vistos.add(u)
                    urls.append(u)
    return urls


# ═══════════════════════════════════════════════ a validação, que é o ponto

def _numeros_de(obj: Any, e_ct: bool, achados: List[str], fundo: int = 0) -> None:
    """Varre a resposta atrás de giros reconhecíveis, seja qual for o formato.

    Os dois provedores usam desenhos diferentes e mudam de tempos em tempos.
    Em vez de casar com um formato, procura o CONTEÚDO: números de roleta ou
    nomes de segmento, onde quer que estejam.
    """
    if fundo > 6 or len(achados) >= 60:
        return
    if isinstance(obj, dict):
        for chave in ("result", "outcome", "number", "n", "value", "slot",
                      "winner", "sector", "symbol"):
            v = obj.get(chave)
            if v is None:
                continue
            if e_ct and isinstance(v, str):
                if v.strip().lower().replace("_", "") in SEGMENTOS_CT:
                    achados.append(v.strip())
            elif not e_ct:
                try:
                    n = int(v)
                    if 0 <= n <= 36:
                        achados.append(str(n))
                except (TypeError, ValueError):
                    pass
        for v in obj.values():
            _numeros_de(v, e_ct, achados, fundo + 1)
    elif isinstance(obj, list):
        for v in obj[:200]:
            _numeros_de(v, e_ct, achados, fundo + 1)


def experimentar(url: str, jogo: str) -> Tuple[bool, str, int]:
    """Este endereço entrega giros de verdade? Devolve (serve, motivo, quantos)."""
    import urllib.error
    import urllib.request

    e_ct = str(jogo).startswith("crazy_time")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
            bruto = r.read(400_000)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}", 0
    except Exception as e:
        return False, type(e).__name__, 0
    try:
        dados = json.loads(bruto.decode("utf-8", "replace"))
    except Exception:
        return False, "resposta não é JSON", 0
    achados: List[str] = []
    _numeros_de(dados, e_ct, achados)
    if len(achados) < MIN_GIROS:
        return False, f"respondeu, mas só {len(achados)} giros reconhecíveis", len(achados)
    return True, f"{len(achados)} giros — ex: {' '.join(achados[:6])}", len(achados)


# ═══════════════════════════════════════════════════════════ a memória

def lembradas() -> Dict[str, str]:
    try:
        return json.loads(MEMORIA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def lembrar(jogo: str, url: str) -> None:
    try:
        MEMORIA.parent.mkdir(parents=True, exist_ok=True)
        d = lembradas()
        if d.get(jogo) == url:
            return
        d[jogo] = url
        MEMORIA.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════ a descoberta

def descobrir(jogo: str, ao_vivo=None) -> Optional[str]:
    """Procura o endereço desta mesa e grava o que funcionar.

    `ao_vivo(texto)` recebe o andamento, para a tela dele acompanhar em vez de
    ficar parada durante a procura.
    """
    def diz(t: str) -> None:
        if ao_vivo:
            try:
                ao_vivo(t)
            except Exception:
                pass

    ja = lembradas().get(jogo)
    if ja:
        serve, motivo, _ = experimentar(ja, jogo)
        if serve:
            diz(f"[{jogo}] fonte conhecida responde — {motivo}")
            return ja
        diz(f"[{jogo}] a fonte gravada parou ({motivo}); procurando de novo")

    urls = [u for u in candidatos(jogo) if u != ja]
    diz(f"[{jogo}] experimentando {len(urls)} endereços")

    # EM LEVAS, PARA PARAR ASSIM QUE ACHAR.
    #
    # A primeira versão usava `pool.map` sobre a lista inteira: o `break`
    # encerrava o laço, mas as 68 requisições já tinham sido despachadas.
    # Contra o provedor de verdade isso é uma rajada inútil toda vez que a
    # mesa cai. Em levas do tamanho do paralelismo, o custo máximo depois de
    # achar é a leva corrente.
    achado: Optional[str] = None
    with ThreadPoolExecutor(max_workers=PARALELAS) as pool:
        for i in range(0, len(urls), PARALELAS):
            leva = urls[i:i + PARALELAS]
            for url, (serve, motivo, _n) in zip(
                    leva, pool.map(lambda u: experimentar(u, jogo), leva)):
                if serve:
                    diz(f"[{jogo}] ACHOU: {url}\n         {motivo}")
                    achado = url
                    break
            if achado:
                break
    if achado:
        lembrar(jogo, achado)
    else:
        diz(f"[{jogo}] nenhum dos {len(urls)} endereços entregou giros. "
            f"Ou a mesa mudou de nome, ou o provedor não a publica.")
    return achado


def relatorio(jogos: Optional[List[str]] = None) -> str:
    """Passa por todas as mesas e diz o que achou. É o diagnóstico dele."""
    jogos = jogos or list(NOMES)
    linhas = ["", "  Procurando o endereço de cada mesa.",
              "  Só vale endereço que entregue giros reconhecíveis.", ""]
    ok = 0
    for j in jogos:
        linhas.append(f"  ── {j}")
        achou = descobrir(j, ao_vivo=lambda t: linhas.append("     " + t))
        if achou:
            ok += 1
    linhas += ["", f"  {ok} de {len(jogos)} mesas com fonte confirmada.",
               f"  Gravado em {MEMORIA}", ""]
    return "\n".join(linhas)


if __name__ == "__main__":
    import sys
    print(relatorio(sys.argv[1:] or None))
