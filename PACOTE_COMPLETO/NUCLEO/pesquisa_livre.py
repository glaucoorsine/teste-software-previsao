# -*- coding: utf-8 -*-
"""
PESQUISA LIVRE — busca soluções na internet e as traz como PROPOSTA ESCRITA.

O QUE ELE PEDIU
───────────────
    "auto melhoria com capacidade de pesquisa livre em Internet sobre soluções"
    "auto de aplicação de tudo que for bom"

O QUE EU FAÇO, E O QUE EU NÃO FAÇO — DITO ANTES DE QUALQUER LINHA
─────────────────────────────────────────────────────────────────
Pesquisar: sim. Trazer o texto, guardar a fonte, separar o que parece técnico do
que é propaganda de cassino: sim.

Aplicar sozinho o que veio da internet: não, e não é preguiça minha. A leitura
literal de "aplicação de tudo que for bom" junto de "pesquisa livre" é: o
software baixa um texto e passa a agir por ele. Quem escreve a página passa a
mandar no que ele recebe no celular. E as páginas que este software leria são
exatamente as piores para isso -- fóruns de apostas, blogs de "método infalível",
comentários. Boa parte daquele conteúdo existe para convencer alguém a apostar de
um jeito específico. Um caminho automático da página até a decisão é um caminho
automático do vendedor até a decisão dele.

Então o desenho é este:

    internet → texto → PROPOSTA registrada no lar → ELE lê e libera → aplica

O elo "ele lê e libera" é o que separa um software que aprende de um software que
obedece a estranhos. É um elo curto -- uma linha na tela e um sim -- e é o único
que não tem volta se eu tirar.

O QUE JÁ EXISTE E É AUTOMÁTICO DE VERDADE
─────────────────────────────────────────
A melhoria automática que ele pediu ACONTECE, em `automelhoria.py`: propor,
ensaiar em sombra, medir contra o titular nas mesmas janelas, aplicar o que
ganhou, desfazer o que piorou. Aquilo é auto-execução real, e é segura porque o
que muda são números dentro de faixas declaradas, medidos na mesa DELE. A
diferença é a origem: o que sai da medida da mesa dele pode entrar sozinho; o que
sai de uma página escrita por um desconhecido, não.

SOBRE ESTA MÁQUINA
──────────────────
Eu não consigo testar a busca daqui: o proxy deste ambiente nega os domínios de
que este arquivo precisa. Então o que eu garanto por teste é o comportamento sem
rede e com respostas simuladas: que ele não trava, não repete proposta, guarda a
fonte, e nunca executa nada do que baixou. A busca de verdade roda na máquina
dele.

E A BUSCA NÃO PODE ATRAPALHAR O QUE IMPORTA
───────────────────────────────────────────
A captura das mesas tem orçamento de tempo por volta -- foi o que resolveu o
travamento de 13 minutos que ele fotografou. Uma pesquisa na internet no meio do
laço de captura traria o travamento de volta por outra porta. Então esta pesquisa
roda em thread própria, com orçamento próprio, e no máximo uma vez por
`INTERVALO_HORAS`. Se não der tempo, ela desiste e tenta na volta seguinte.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence

ARQ = "pesquisa_internet.json"

TIMEOUT = 12
ORCAMENTO_S = 40.0
INTERVALO_HORAS = 6.0
MAX_POR_VOLTA = 6

CABECA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
          "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}

# O QUE ELA PROCURA.
#
# Assuntos, não "como ganhar na roleta". A pergunta útil é técnica: como se mede
# viés num sorteio, como se detecta desvio numa sequência, como se evita achar
# padrão onde não há. Isso é o que pode melhorar o software. "Método infalível"
# não melhora nada e é o que mais aparece se a busca for ingênua.
ASSUNTOS = [
    "detecção de viés em roleta análise estatística",
    "teste de aleatoriedade sequência resultados método",
    "roulette wheel bias detection statistical test",
    "como evitar overfitting seleção de padrões amostra pequena",
    "multiple comparisons problem false discovery pattern",
    "live casino API dados históricos rodadas",
]

# O QUE DESQUALIFICA UM RESULTADO NA HORA.
#
# Estes termos não são censura de assunto: são a marca de página que existe para
# vender aposta. Se o texto traz isso, ele não vai ensinar a medir nada.
LIXO = ("método infalível", "metodo infalivel", "ganhe sempre", "lucro garantido",
        "bônus de cadastro", "cadastre-se", "aposte agora", "sinais vip",
        "grupo vip", "robô de sinais", "banca garantida", "100% de acerto")

# marcas de conteúdo que vale ler
TECNICO = ("chi-quadrado", "chi-square", "p-valor", "p-value", "desvio padrão",
           "standard deviation", "intervalo de confiança", "confidence interval",
           "amostra", "sample size", "bias", "viés", "overfitting", "bootstrap",
           "hipótese", "hypothesis", "regressão", "aleatoriedade", "randomness",
           "distribuição", "distribution", "correlação", "significância")


# ═════════════════════════════════════════════════════════ o estado no lar
def carregar() -> Dict[str, Any]:
    try:
        from NUCLEO import lar
        d = lar.ler_json(ARQ, None)
    except Exception:
        d = None
    if not isinstance(d, dict):
        d = {}
    d.setdefault("propostas", [])       # o que ela trouxe, esperando ele
    d.setdefault("liberadas", [])       # o que ele liberou
    d.setdefault("recusadas", [])       # o que ele recusou -- não traz de novo
    d.setdefault("ultima_busca", 0.0)
    d.setdefault("vistos", [])          # endereços já trazidos
    return d


def gravar(d: Dict[str, Any]) -> bool:
    d["propostas"] = (d.get("propostas") or [])[-40:]
    d["vistos"] = (d.get("vistos") or [])[-400:]
    try:
        from NUCLEO import lar
        return lar.gravar_json(ARQ, d)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════ a busca
def _buscar_duckduckgo(termo: str, prazo: float) -> List[Dict[str, str]]:
    """Resultados de busca sem chave de API.

    O html.duckduckgo.com devolve a página de resultados sem exigir chave nem
    JavaScript, o que é o que dá para fazer daqui sem inventar uma dependência
    que ele teria de instalar e configurar.
    """
    if time.time() >= prazo:
        return []
    url = ("https://html.duckduckgo.com/html/?q="
           + urllib.parse.quote(termo))
    try:
        req = urllib.request.Request(url, headers=CABECA)
        resto = max(1.0, min(TIMEOUT, prazo - time.time()))
        with urllib.request.urlopen(req, timeout=resto) as r:
            html = r.read(400_000).decode("utf-8", "ignore")
    except Exception:
        return []
    saida = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                         html, re.S):
        href, titulo = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        # o duckduckgo embrulha o destino real num redirecionador
        if "uddg=" in href:
            try:
                href = urllib.parse.unquote(
                    re.search(r"uddg=([^&]+)", href).group(1))
            except Exception:
                pass
        saida.append({"url": href, "titulo": titulo.strip()})
        if len(saida) >= 10:
            break
    return saida


def _texto_da_pagina(url: str, prazo: float) -> str:
    if time.time() >= prazo:
        return ""
    try:
        req = urllib.request.Request(url, headers=CABECA)
        resto = max(1.0, min(TIMEOUT, prazo - time.time()))
        with urllib.request.urlopen(req, timeout=resto) as r:
            bruto = r.read(600_000).decode("utf-8", "ignore")
    except Exception:
        return ""
    # tira script e style ANTES de tirar as tags: senão o código deles vira texto
    bruto = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", bruto)
    txt = re.sub(r"(?s)<[^>]+>", " ", bruto)
    txt = re.sub(r"&[a-z]+;|&#\d+;", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _julgar_texto(txt: str) -> Dict[str, Any]:
    """Isto vale ler, ou é propaganda?"""
    baixo = txt.lower()
    lixo = [t for t in LIXO if t in baixo]
    tec = [t for t in TECNICO if t in baixo]
    return {"lixo": lixo, "tecnico": tec,
            "presta": bool(len(tec) >= 3 and not lixo)}


def _trecho_util(txt: str, limite: int = 700) -> str:
    """O pedaço do texto onde a parte técnica está, não o começo da página."""
    baixo = txt.lower()
    melhor, pos = 0, 0
    passo = 300
    for i in range(0, max(1, len(txt) - limite), passo):
        janela = baixo[i:i + limite]
        conta = sum(1 for t in TECNICO if t in janela)
        if conta > melhor:
            melhor, pos = conta, i
    return txt[pos:pos + limite]


def pesquisar(assuntos: Optional[Sequence[str]] = None,
              orcamento_s: float = ORCAMENTO_S,
              buscador=None, leitor=None) -> Dict[str, Any]:
    """Uma rodada de pesquisa. Devolve o que achou; NÃO aplica nada.

    `buscador` e `leitor` existem para o teste poder rodar sem rede -- e para eu
    poder provar, sem internet, que nada do que vem de fora é executado.
    """
    prazo = time.time() + max(5.0, orcamento_s)
    d = carregar()
    vistos = set(str(x) for x in (d.get("vistos") or []))
    recusados = {str(x.get("url")) for x in (d.get("recusadas") or [])}
    busca = buscador or _buscar_duckduckgo
    ler = leitor or _texto_da_pagina

    novas, olhados, descartados = [], 0, 0
    falhas: List[str] = []
    for termo in (assuntos or ASSUNTOS):
        if time.time() >= prazo or len(novas) >= MAX_POR_VOLTA:
            break
        # UM ASSUNTO QUE FALHA NÃO PODE DERRUBAR A RODADA.
        #
        # `_buscar_duckduckgo` trata os próprios erros, mas um buscador que
        # levante -- um erro de DNS numa camada mais funda, uma resposta que quebre
        # o decode, ou um buscador diferente amanhã -- matava a rodada inteira aqui
        # e as outras buscas nem eram tentadas. O teste sem rede mostrou isso.
        try:
            achados = busca(termo, prazo) or []
        except Exception as e:
            falhas.append(f"{termo[:24]}: {type(e).__name__}")
            continue
        for r in achados:
            if time.time() >= prazo or len(novas) >= MAX_POR_VOLTA:
                break
            url = str((r or {}).get("url") or "")
            if not url.startswith("http") or url in vistos or url in recusados:
                continue
            vistos.add(url)
            olhados += 1
            try:
                txt = ler(url, prazo) or ""
            except Exception as e:
                falhas.append(f"{url[:32]}: {type(e).__name__}")
                continue
            if len(txt) < 400:
                continue
            j = _julgar_texto(txt)
            if not j["presta"]:
                descartados += 1
                continue
            novas.append({
                "url": url, "titulo": r.get("titulo") or "",
                "assunto": termo,
                "trecho": _trecho_util(txt),
                "marcas": j["tecnico"][:6],
                "em": time.strftime("%Y-%m-%d %H:%M"),
                "estado": "esperando você liberar",
                # DITO NO PRÓPRIO REGISTRO, para não haver dúvida depois:
                "aplicado": False,
                "nota": "texto trazido da internet — NÃO é executado nem aplicado "
                        "por conta própria",
            })
    d["vistos"] = sorted(vistos)
    d["ultima_busca"] = time.time()
    d["propostas"] = (d.get("propostas") or []) + novas
    gravar(d)
    return {"novas": novas, "olhados": olhados, "descartados": descartados,
            "falhas": falhas, "estado": d}


def hora_de_pesquisar(d: Optional[Dict[str, Any]] = None) -> bool:
    d = d or carregar()
    try:
        ultima = float(d.get("ultima_busca") or 0.0)
    except (TypeError, ValueError):
        ultima = 0.0
    return (time.time() - ultima) >= INTERVALO_HORAS * 3600


def pesquisar_em_thread(registrar=None) -> Optional[threading.Thread]:
    """Dispara a pesquisa fora do laço de captura.

    A captura tem orçamento de tempo por volta -- foi o que resolveu o
    travamento de 13 minutos. Pesquisar dentro daquele laço traria o travamento
    de volta por outra porta.
    """
    if not hora_de_pesquisar():
        return None

    def alvo():
        try:
            r = pesquisar()
            if registrar:
                for L in resumo(r["estado"], r):
                    registrar(L)
        except Exception as e:
            if registrar:
                registrar(f"[Pesquisa] {type(e).__name__}: {e}")

    t = threading.Thread(target=alvo, name="pesquisa_livre", daemon=True)
    t.start()
    return t


# ══════════════════════════════════════════════ liberar / recusar (ele decide)
def liberar(indice: int, nota: str = "") -> bool:
    """ELE aprova uma proposta. Só a partir daqui ela vale alguma coisa."""
    d = carregar()
    props = d.get("propostas") or []
    if not (0 <= indice < len(props)):
        return False
    p = dict(props.pop(indice))
    p["estado"] = "liberada por você"
    p["nota_dele"] = nota
    p["liberada_em"] = time.strftime("%Y-%m-%d %H:%M")
    d.setdefault("liberadas", []).append(p)
    d["propostas"] = props
    return gravar(d)


def recusar(indice: int, nota: str = "") -> bool:
    """ELE recusa. O endereço não volta a ser trazido."""
    d = carregar()
    props = d.get("propostas") or []
    if not (0 <= indice < len(props)):
        return False
    p = dict(props.pop(indice))
    p["estado"] = "recusada por você"
    p["nota_dele"] = nota
    d.setdefault("recusadas", []).append(p)
    d["propostas"] = props
    return gravar(d)


def resumo(d: Optional[Dict[str, Any]] = None,
           rodada: Optional[dict] = None) -> List[str]:
    d = d or carregar()
    L: List[str] = []
    if rodada:
        L.append(f"[Pesquisa] olhei {rodada.get('olhados', 0)} páginas, "
                 f"descartei {rodada.get('descartados', 0)} por propaganda, "
                 f"trouxe {len(rodada.get('novas') or [])}"
                 + (f" — {len(rodada.get('falhas') or [])} busca(s) falharam: "
                    f"{', '.join((rodada.get('falhas') or [])[:3])}"
                    if rodada.get("falhas") else ""))
    props = d.get("propostas") or []
    if props:
        L.append(f"[Pesquisa] {len(props)} proposta(s) esperando você liberar "
                 f"(nada foi aplicado por conta própria):")
        for i, p in enumerate(props[-4:]):
            L.append(f"[Pesquisa]   [{len(props)-4+i if len(props) > 4 else i}] "
                     f"{(p.get('titulo') or '')[:70]}")
            L.append(f"[Pesquisa]       {', '.join(p.get('marcas') or [])} — "
                     f"{p.get('url', '')[:80]}")
    lib = d.get("liberadas") or []
    if lib:
        L.append(f"[Pesquisa] {len(lib)} liberada(s) por você até agora")
    if not L:
        L.append("[Pesquisa] nada novo — próxima busca em "
                 f"{INTERVALO_HORAS:.0f}h")
    return L
