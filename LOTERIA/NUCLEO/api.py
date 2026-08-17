# -*- coding: utf-8 -*-
"""
API — puxar os resultados direto da fonte, na máquina DELE.

POR QUE ISTO EXISTE, DEPOIS DE EU TER DITO QUE NÃO DAVA
──────────────────────────────────────────────────────
Eu tinha concluído que o histórico só entraria por arquivo, porque daqui a
conexão com a Caixa é recusada. A conclusão estava apressada, e ele me corrigiu:
ele já tinha dado a API.

Fui medir e o quadro é este — daqui, `servicebus2.caixa.gov.br` é recusado, e
`api.tracksino.com` e `api-cs.casino.org` também são. Essas duas últimas são as
APIs do outro software dele, as que funcionam na máquina dele todo dia. Não é a
API que está errada: é o lugar de onde eu tento. Este ambiente alcança GitHub e
repositório de pacote, e mais nada.

E o software não roda aqui — roda na máquina dele. Lá a API responde. Então o
puxador tem de existir, e o que eu não posso é fingir que o testei contra a
fonte real.

COMO ISTO É PROVADO, JÁ QUE A FONTE REAL NÃO RESPONDE PARA MIM
──────────────────────────────────────────────────────────────
Subo um servidor de mentira em 127.0.0.1 que fala o formato da Caixa, e o teste
puxa dele: histórico completo, retomada de onde parou, concurso que não existe,
resposta que não é JSON, servidor fora do ar. Isso prova o CLIENTE.

O que fica por confirmar é se a API de verdade fala exatamente esse formato. Não
dá para eu confirmar daqui, e por isso a primeira execução na máquina dele mostra
o que veio, por extenso, antes de gravar qualquer coisa. Se o formato for outro,
aparece na hora em vez de virar estatística sobre lixo.

O ENDEREÇO NÃO FICA CHUMBADO NO CÓDIGO
──────────────────────────────────────
No outro software eu chutei o endereço de uma mesa e ele teve de me corrigir
("parar de chutar o endereço e ler a página que ele mandou"). Não repito: o
endereço mora em `dados/fonte.json`, ele troca sem mexer no código, e o que está
aqui embaixo é só o padrão conhecido — marcado como NÃO CONFERIDO, porque eu
realmente não pude conferir.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "dados"
ARQUIVO_FONTE = PASTA_DADOS / "fonte.json"

# O padrão conhecido do portal da Caixa. NÃO CONFERIDO por mim — ver o cabeçalho.
# `{slug}` é o nome da loteria como a API a chama; `{n}` é o número do concurso,
# e sem ele a API devolve o mais recente.
FONTE_PADRAO: Dict[str, Any] = {
    "nome": "portal de loterias da Caixa (padrão conhecido, não conferido daqui)",
    "url": "https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}",
    "url_concurso": "https://servicebus2.caixa.gov.br/portaldeloterias/api/{slug}/{n}",
    "slugs": {
        "mega_sena": "megasena", "quina": "quina", "lotofacil": "lotofacil",
        "lotomania": "lotomania", "dupla_sena": "duplasena",
        "timemania": "timemania", "dia_de_sorte": "diadesorte",
        "mais_milionaria": "maismilionaria",
    },
    "conferida": False,
}

CABECALHOS = {
    # alguns portais recusam cliente sem isto, e recusar por falta de cabeçalho
    # daria "a API não responde" quando a API responde muito bem.
    "User-Agent": "Mozilla/5.0 (compatível; software de loteria dele)",
    "Accept": "application/json, text/plain, */*",
}


# ═══════════════════════════════════════════════════ o endereço, dele
def carregar_fonte() -> Dict[str, Any]:
    """A fonte que ele configurou, ou o padrão conhecido."""
    try:
        if ARQUIVO_FONTE.exists():
            d = json.loads(ARQUIVO_FONTE.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("url"):
                base = dict(FONTE_PADRAO)
                base.update(d)
                return base
    except Exception:
        pass
    return dict(FONTE_PADRAO)


def gravar_fonte(url: str, url_concurso: str = "", nome: str = "",
                 slugs: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Guarda o endereço que ELE mandou. Sem isto eu voltaria a chutar."""
    f = carregar_fonte()
    f["url"] = url.strip()
    f["url_concurso"] = (url_concurso.strip()
                         or (url.strip().rstrip("/") + "/{n}"))
    f["nome"] = nome or "endereço que ele mandou"
    if slugs:
        f["slugs"] = dict(f.get("slugs") or {}, **slugs)
    f["conferida"] = False          # só a primeira puxada de verdade confere
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    ARQUIVO_FONTE.write_text(json.dumps(f, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return f


def endereco(chave_jogo: str, concurso: Optional[int] = None,
             fonte: Optional[dict] = None) -> str:
    f = fonte or carregar_fonte()
    slug = (f.get("slugs") or {}).get(chave_jogo, chave_jogo.replace("_", ""))
    if concurso is None:
        return str(f["url"]).format(slug=slug, n="")
    return str(f.get("url_concurso") or f["url"]).format(slug=slug, n=concurso)


# ═══════════════════════════════════════════════════ uma requisição
def buscar(url: str, tempo: float = 20.0,
           tentativas: int = 3) -> Tuple[Optional[Any], str]:
    """Busca um JSON. Devolve (dados, erro) — nunca levanta exceção.

    O ERRO É CLASSIFICADO, E ISSO NÃO É FRESCURA
    ────────────────────────────────────────────
    "não deu para puxar" manda ele conferir a internet quando o problema é o
    endereço, e manda conferir o endereço quando o problema é a rede. Cada
    causa tem um conserto diferente, então cada uma tem uma frase diferente.
    """
    ultimo = ""
    for tentativa in range(1, max(1, tentativas) + 1):
        try:
            req = urllib.request.Request(url, headers=CABECALHOS)
            with urllib.request.urlopen(req, timeout=tempo) as resp:
                bruto = resp.read()
            try:
                return json.loads(bruto.decode("utf-8", "replace")), ""
            except json.JSONDecodeError:
                trecho = bruto[:120].decode("utf-8", "replace").replace("\n", " ")
                return None, (f"o endereço respondeu, mas não com JSON. Começa "
                              f"assim: {trecho!r}. Costuma ser página de erro "
                              f"ou de login no lugar da API.")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, "404"          # concurso inexistente: fim da fila
            ultimo = f"o servidor respondeu {e.code} ({e.reason})"
            if e.code in (403, 407):
                return None, (f"{ultimo}. Se isto aparecer na SUA máquina, o "
                              f"endereço ou o cabeçalho é que estão recusados; "
                              f"aqui no meu ambiente é a política de rede, que "
                              f"recusa tudo menos GitHub e pacote.")
            if e.code < 500:
                return None, ultimo
        except urllib.error.URLError as e:
            motivo = str(getattr(e, "reason", e))
            if "tunnel" in motivo.lower() or "403" in motivo:
                return None, ("a saída de rede DESTE ambiente recusou a conexão "
                              "antes de ela sair (403 no CONNECT). Não é a API: "
                              "as APIs do seu outro software são recusadas aqui "
                              "do mesmo jeito. Na sua máquina isto funciona.")
            ultimo = f"não alcancei o endereço: {motivo}"
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
        if tentativa < tentativas:
            time.sleep(2 ** tentativa)      # 2s, 4s — rede ruim é comum
    return None, ultimo or "falhou sem dizer por quê"


# ═════════════════════════════════════════════ o histórico inteiro
def caminho_cache(chave_jogo: str) -> Path:
    return PASTA_DADOS / f"{chave_jogo}.json"


def carregar_cache(chave_jogo: str) -> List[dict]:
    p = caminho_cache(chave_jogo)
    try:
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
    except Exception:
        pass
    return []


def salvar_cache(chave_jogo: str, registros: List[dict]) -> Path:
    PASTA_DADOS.mkdir(parents=True, exist_ok=True)
    p = caminho_cache(chave_jogo)
    p.write_text(json.dumps(registros, ensure_ascii=False), encoding="utf-8")
    return p


def _numero_do(reg: dict) -> Optional[int]:
    for k in ("numero", "concurso", "numeroConcurso", "id"):
        v = reg.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().isdigit():
            return int(v)
    return None


def puxar(chave_jogo: str, ate: Optional[int] = None, desde: int = 1,
          pausa: float = 0.15, fonte: Optional[dict] = None,
          aviso: Optional[Callable[[str], None]] = None,
          maximo: int = 100_000) -> Dict[str, Any]:
    """Puxa os concursos que faltam e guarda em dados/<jogo>.json.

    RETOMA DE ONDE PAROU, E ISSO NÃO É CONFORTO
    ───────────────────────────────────────────
    A API devolve UM concurso por chamada. Puxar a Mega-Sena inteira são milhares
    de chamadas, e vai levar minutos. Se cair na metade — internet, computador
    dormindo, ele fechando a janela — recomeçar do zero seria castigo. Então o
    que já veio fica gravado, e a próxima execução continua da lacuna.

    Guarda o registro CRU da API, sem recortar campo nenhum. Se um dia eu quiser
    medir algo que hoje eu jogo fora, o dado está lá; e o `historico.py` já sabe
    ler esse formato.
    """
    diga = aviso or (lambda s: None)
    f = fonte or carregar_fonte()
    registros = {n: r for r in carregar_cache(chave_jogo)
                 if (n := _numero_do(r)) is not None}
    tinha = len(registros)

    if ate is None:
        diga(f"perguntando à fonte qual é o último concurso de {chave_jogo}…")
        ultimo, erro = buscar(endereco(chave_jogo, None, f))
        if erro:
            return {"ok": False, "erro": erro, "tinha": tinha, "novos": 0,
                    "registros": list(registros.values())}
        if isinstance(ultimo, list) and ultimo:
            ultimo = ultimo[0]
        if not isinstance(ultimo, dict):
            return {"ok": False, "tinha": tinha, "novos": 0,
                    "erro": "a fonte respondeu algo que não é um concurso: "
                            f"{type(ultimo).__name__}",
                    "registros": list(registros.values())}
        ate = _numero_do(ultimo)
        if ate is None:
            return {"ok": False, "tinha": tinha, "novos": 0,
                    "erro": "não achei o número do concurso na resposta da "
                            f"fonte. Vieram estes campos: "
                            f"{sorted(ultimo.keys())[:12]}",
                    "registros": list(registros.values())}
        # o último já veio nesta chamada: aproveitar em vez de pedir de novo.
        # E ele CONTA como novo -- a primeira versão não contava, e a conta na
        # tela não fechava com o arquivo: "tinha 5, novos 6" com 12 no disco.
        ja_tinha = ate in registros
        registros[ate] = ultimo
        diga(f"o último é o concurso {ate}")
    else:
        ja_tinha = True

    faltam = [n for n in range(max(1, desde), ate + 1) if n not in registros]
    if len(faltam) > maximo:
        faltam = faltam[-maximo:]
    diga(f"faltam {len(faltam)} concursos (já tinha {tinha})")

    novos, falhas = (0 if ja_tinha else 1), []
    for i, n in enumerate(faltam, 1):
        reg, erro = buscar(endereco(chave_jogo, n, f), tentativas=2)
        if erro == "404":
            falhas.append((n, "não existe"))
        elif erro:
            # erro de rede no meio: guarda o que veio e para, em vez de
            # martelar a fonte mil vezes com o mesmo problema
            salvar_cache(chave_jogo, [registros[k] for k in sorted(registros)])
            return {"ok": False, "erro": erro, "tinha": tinha, "novos": novos,
                    "parou_em": n, "arquivo": str(caminho_cache(chave_jogo)),
                    "registros": [registros[k] for k in sorted(registros)]}
        elif isinstance(reg, dict):
            registros[n] = reg
            novos += 1
        if i % 50 == 0:
            salvar_cache(chave_jogo, [registros[k] for k in sorted(registros)])
            diga(f"  {i}/{len(faltam)} — {novos} novos, gravando…")
        if pausa:
            time.sleep(pausa)

    lista = [registros[k] for k in sorted(registros)]
    arq = salvar_cache(chave_jogo, lista)
    return {"ok": True, "tinha": tinha, "novos": novos, "total": len(lista),
            "falhas": falhas, "arquivo": str(arq), "registros": lista,
            "ultimo": ate}
