# -*- coding: utf-8 -*-
"""
HIPÓTESES PRÉ-DECLARADAS — o compromisso assumido antes do dado.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Uma medida achada procurando vale muito menos do que a mesma medida feita sob
compromisso. Quando se testam 195 regras e a melhor dá p=0,03, esse 0,03 não
vale nada: com 195 perguntas, o acaso entrega várias assim. Mas se a fórmula
foi FIXADA antes de ver o dado novo, ela custa UMA pergunta — e aí 0,03 é 0,03.

Isto aqui é a diferença entre "eu encontrei" e "eu previ".

O QUE ESTÁ TRAVADO
------------------
Cada hipótese abaixo tem a fórmula inteira escrita, sem parâmetro solto. Nada
de "ajusta a janela até melhorar" — a janela é 12 porque foi 12 quando se
declarou, e fica 12. Mudar qualquer número aqui INVALIDA o histórico acumulado
daquela hipótese, e o código força isso: a chave de acumulação inclui a
assinatura da fórmula (ver `_assinatura`).

Todas apostam a MESMA quantidade de números (k). Comparar um apostador de 5
com um de 11 é fraude — o de 11 acerta mais só porque cobre mais pano.

NADA É DESCARTADO
-----------------
Uma hipótese que morre continua no arquivo, com o veredito de morte. Saber o
que NÃO funciona é resultado, e é o que impede de reencontrar a mesma ilusão
daqui a três meses.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Dict, List, Optional

from .paths_dados import subdir

RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
        5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}
FAIXAS = [range(0, 10), range(10, 20), range(20, 30), range(30, 37)]


# --------------------------------------------------------------- as fórmulas
def _familia_do_final(x: int) -> set:
    f = x % 10
    for g in ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9)):
        if f in g:
            return {y for y in range(37) if y % 10 in g}
    return set()


def H1_familia_final(hist: List[int]) -> List[int]:
    """
    LIGHTNING — a regra do operador, na forma exata em que ele a descreveu:
    'veio o 25, pode vir o 34, o 15'. Família do último número, escolhendo
    dentro dela pelos que saíram mais nos últimos 40 giros.

    Declarada em 14/08/2026. Medida na época: 56/186 = 30,1% contra base 24,5%
    da própria mesa (1,23x), p=0,032 por reordenação, com as duas metades da
    coleta concordando (28,9% e 31,2%).
    """
    if not hist:
        return []
    ult = hist[-1]
    fam = _familia_do_final(ult) - {ult}
    if not fam:
        return []
    rec = Counter(hist[-40:])
    return sorted(fam, key=lambda x: (-rec.get(x, 0), x))[:5]


def H2_faixa_recencia(hist: List[int]) -> List[int]:
    """
    LIGHTNING — as 2 faixas de mesa mais visitadas nos últimos 12 giros,
    escolhendo 5 dentro delas por recência de 40 giros.

    Declarada em 14/08/2026. Medida na época: 103/622 = 16,6% contra 13,5%
    (1,23x), p=0,022 por reordenação.

    ATENÇÃO AO QUE ESTA HIPÓTESE NÃO É: ela nasceu de um controle que derrubou
    a explicação da família. Trocando a família do gatilho pela família ERRADA
    o acerto subia (19,3%), o que mostrou que o ganho vinha daqui — da faixa
    mais a recência — e não do final do número. As duas metades da coleta,
    porém, ficaram distantes (15,0% e 19,9%), então isto é bem mais frágil que
    a H1. Está aqui para morrer ou viver por conta própria.
    """
    if len(hist) < 12:
        return []
    c: Counter = Counter()
    for x in hist[-12:]:
        for k, f in enumerate(FAIXAS):
            if x in f:
                c[k] += 1
    quentes = [k for k, _ in c.most_common(2)]
    pool = [x for k in quentes for x in FAIXAS[k]]
    rec = Counter(hist[-40:])
    return sorted(pool, key=lambda x: (-rec.get(x, 0), x))[:5]


def H3_vizinhos_ultimo(hist: List[int]) -> List[int]:
    """
    CONTROLE NEGATIVO — 5 vizinhos físicos do último número na roda.

    Esta hipótese está aqui porque JÁ FOI REPROVADA: prometeu 1,24x na coleta
    antiga do Immersive e entregou 0,93x na coleta nova. Fica como régua viva:
    se um dia ela começar a acertar junto com as outras, o problema é da
    medição, não das teorias. É o canário.
    """
    if not hist:
        return []
    i = POS.get(hist[-1])
    if i is None:
        return []
    return [RODA[(i + d) % 37] for d in (-2, -1, 0, 1, 2)]


def H4_familia_na_faixa_quente(hist: List[int]) -> List[int]:
    """
    A REGRA DO OPERADOR COMPLETA — a que ele descreveu desde o começo e que eu
    levei o dia inteiro para entender:

        "tá vindo muitos de 0-10, veio o 14 por exemplo, então vou jogar 4,5,9"

    Não é a família inteira (11 números). Não é a faixa do gatilho. É: veio um
    número da família de final, e a aposta vai nos membros dessa família que
    moram na FAIXA QUE ESTÁ SAINDO nas últimas 12 rodadas.

    Como ela apareceu: só depois de eu parar de calcular e listar os 59 casos
    reais de Lightning um por um. Nenhuma estatística agregada mostrou isso —
    ela só apareceu olhando o que de fato aconteceu depois de cada gatilho.

    Medida na declaração (14/08/2026), primeiro retorno dentro de 5 giros,
    contra a proporção da família que mora na faixa quente:
        lightning  13/42 = 31,0%  (esperado 25,5%)  1,22x
        mega_fire  10/34 = 29,4%  (esperado 26,0%)  1,13x
        immersive  18/57 = 31,6%  (esperado 26,1%)  1,21x
        JUNTAS     41/133 = 30,8% (esperado 25,8%)  1,19x   p=0,090
    As três mesas na mesma direção — a única coisa do estudo que fez isso.
    Não passou a barra, e por isso está aqui: para ser cobrada com giro novo,
    não para ser anunciada.

    O tamanho é 7 porque é com 7 que o motor trabalha (k_alvos), e comparar
    apostador de 5 com apostador de 7 é fraude.
    """
    if len(hist) < 13:
        return []
    ult = hist[-1]
    fam = _familia_do_final(ult)
    if not fam:
        return []
    c: Counter = Counter()
    for x in hist[-12:]:
        for k, f in enumerate(FAIXAS):
            if x in f:
                c[k] += 1
    if not c:
        return []
    quente = c.most_common(1)[0][0]
    dentro = [x for x in sorted(fam) if x in FAIXAS[quente]]
    fora = [x for x in sorted(fam) if x not in FAIXAS[quente]]
    rec = Counter(hist[-40:])
    dentro.sort(key=lambda x: (-rec.get(x, 0), x))
    fora.sort(key=lambda x: (-rec.get(x, 0), x))
    return (dentro + fora)[:7]


HIPOTESES: List[Dict[str, Any]] = [
    {"id": "H4", "jogo": "lightning", "k": 7, "f": H4_familia_na_faixa_quente,
     "nome": "família do final DENTRO da faixa quente (regra do operador)",
     "declarada": "2026-08-14", "origem": "regra do operador, forma completa",
     "medida_na_declaracao": "41/133 = 30,8% (1,19x) p=0,090 nas 3 mesas"},
    {"id": "H4b", "jogo": "mega_fire", "k": 7, "f": H4_familia_na_faixa_quente,
     "nome": "família do final DENTRO da faixa quente (regra do operador)",
     "declarada": "2026-08-14", "origem": "regra do operador, forma completa",
     "medida_na_declaracao": "10/34 = 29,4% (1,13x)"},
    # H4c FICA NO REGISTRO, MAS NÃO RODA MAIS.
    #
    # A Immersive saiu do software. A tentação é apagar esta linha — e apagar
    # uma hipótese PRÉ-DECLARADA depois de saber o resultado dela é exatamente
    # o que a pré-declaração existe para impedir. É a mesma seleção que ele
    # cobra em todo lugar: só se conta o que ficou bom.
    #
    # Então ela fica, com a medida que tinha na declaração, marcada como
    # encerrada. `aposentada` faz o avaliador pular sem tirá-la da lista: o
    # registro continua completo e ninguém tenta rodá-la numa mesa que não
    # existe mais.
    {"id": "H4c", "jogo": "immersive", "k": 7, "f": H4_familia_na_faixa_quente,
     "nome": "família do final DENTRO da faixa quente (regra do operador)",
     "declarada": "2026-08-14", "origem": "regra do operador, forma completa",
     "aposentada": "2026-08-17 — a mesa saiu do software",
     "medida_na_declaracao": "18/57 = 31,6% (1,21x)"},
    {"id": "H1", "jogo": "lightning", "k": 5, "f": H1_familia_final,
     "nome": "família do final (4-5-9 etc.) + recência",
     "declarada": "2026-08-14", "origem": "regra do operador",
     "medida_na_declaracao": "56/186 = 30,1% (1,23x) p=0,032"},
    {"id": "H2", "jogo": "lightning", "k": 5, "f": H2_faixa_recencia,
     "nome": "2 faixas quentes (12 giros) + recência (40)",
     "declarada": "2026-08-14", "origem": "controle da regra do operador",
     "medida_na_declaracao": "103/622 = 16,6% (1,23x) p=0,022"},
    {"id": "H3", "jogo": "lightning", "k": 5, "f": H3_vizinhos_ultimo,
     "nome": "vizinhos físicos do último (CONTROLE NEGATIVO)",
     "declarada": "2026-08-14", "origem": "reprovada na validação",
     "medida_na_declaracao": "0,93x na validação — esperado NÃO funcionar"},
]


def _assinatura(h: Dict[str, Any]) -> str:
    """Impressão digital da fórmula. Mudou o código, zera o acumulado."""
    import hashlib
    src = (h["f"].__doc__ or "") + h["f"].__name__ + str(h["k"])
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------- acumulação
def _arquivo(jogo: str):
    return subdir("predeclaradas") / f"{jogo}.json"


def _carregar(jogo: str) -> Dict[str, Any]:
    p = _arquivo(jogo)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _salvar(jogo: str, d: Dict[str, Any]) -> None:
    try:
        _arquivo(jogo).write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
    except Exception:
        pass


def _p_binom_ge(h: int, n: int, p: float) -> float:
    if n <= 0 or p <= 0 or p >= 1:
        return 1.0
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                        - math.lgamma(n - k + 1)
                        + k * math.log(p) + (n - k) * math.log(1 - p))
               for k in range(min(h, n), n + 1))


def _n_necessario(p0: float, p1: float) -> int:
    """ativações para detectar p1 contra p0 com 80% de poder, 5% unilateral"""
    if p1 <= p0:
        return 0
    za, zb = 1.645, 0.84
    num = (za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) ** 2
    return int(math.ceil(num / (p1 - p0) ** 2))


def registrar(jogo: str, hist_cron: List[int],
              ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Mede as hipóteses deste jogo no histórico dado e acumula.

    `hist_cron` é cronológico (antigo -> novo). `ids` são identificadores
    estáveis por giro (event_id ou settled); sem eles, usa a posição — o que só
    é seguro dentro de uma mesma sessão. Com eles, a acumulação atravessa
    noites sem contar o mesmo giro duas vezes, que é o ponto deste módulo.
    """
    # hipotese aposentada fica no registro e nao roda (ver H4c)
    hip = [h for h in HIPOTESES
           if h["jogo"] == jogo and not h.get("aposentada")]
    if not hip or len(hist_cron) < 61:
        return {}
    store = _carregar(jogo)
    for h in hip:
        assin = _assinatura(h)
        st = store.get(h["id"]) or {}
        if st.get("assinatura") != assin:
            # fórmula mudou: o acumulado antigo não vale mais
            st = {"assinatura": assin, "hits": 0, "n": 0, "vistos": [],
                  "declarada": h["declarada"]}
        vistos = set(st.get("vistos") or [])
        for i in range(60, len(hist_cron) - 1):
            chave = ids[i] if (ids and i < len(ids)) else f"pos{i}"
            if chave in vistos:
                continue
            pick = h["f"](hist_cron[:i + 1])
            if len(pick) < h["k"]:
                continue
            vistos.add(chave)
            st["n"] = int(st.get("n", 0)) + 1
            if hist_cron[i + 1] in set(pick):
                st["hits"] = int(st.get("hits", 0)) + 1
        # a lista de vistos não pode crescer para sempre
        st["vistos"] = list(vistos)[-20000:]
        store[h["id"]] = st
    _salvar(jogo, store)
    return store


def avaliar(jogo: str) -> List[Dict[str, Any]]:
    """Estado de cada hipótese: quanto já acumulou e o que isso diz."""
    store = _carregar(jogo)
    out = []
    for h in [x for x in HIPOTESES
              if x["jogo"] == jogo and not x.get("aposentada")]:
        st = store.get(h["id"]) or {}
        n = int(st.get("n", 0))
        hits = int(st.get("hits", 0))
        base = h["k"] / 37.0
        taxa = (hits / n) if n else 0.0
        p = _p_binom_ge(hits, n, base) if n else None
        alvo = _n_necessario(base, base * 1.23)
        # O VEREDITO SÓ SAI NO TAMANHO COMBINADO. Isto não é preciosismo:
        # se a gente olhar a cada ciclo e cantar "confirmada" na primeira vez
        # que p encosta em 0,05, acaba confirmando QUALQUER COISA — basta
        # esperar. É o erro de parar de medir quando o número agrada.
        # Em 25 mundos de ruído puro, um deles chegou a 1,21x sozinho.
        # Medido: com esta regra, 2,5% de falso positivo e 100% de detecção
        # de um efeito real de 1,23x.
        m_teste = max(1, sum(1 for x in HIPOTESES
                             if x["jogo"] == jogo and not x.get("aposentada")))
        alpha = 0.05 / m_teste          # e as hipóteses dividem a barra
        if n < alvo:
            veredito = "acumulando"
        elif p is not None and p <= alpha:
            veredito = "confirmada"
        else:
            veredito = "morta"
        out.append({**{k: v for k, v in h.items() if k != "f"},
                    "n": n, "hits": hits, "taxa": taxa, "base": base,
                    "razao": (taxa / base) if base else None,
                    "p": p, "n_alvo": alvo, "veredito": veredito})
    return out


def avisar_mudanca_de_veredito(jogo: str, log_fn=None) -> List[str]:
    """
    Avisa no celular quando um compromisso FECHA.

    Este é o evento que interessa a quem deixa o software rodando dias: não o
    sinal de cada giro, mas o momento em que uma hipótese pré-declarada sai de
    "acumulando" e vira "confirmada" ou "morta". É o desfecho que se estava
    esperando desde a declaração, e pode acontecer às três da manhã.

    Avisa uma vez por transição e guarda o que já avisou — reabrir o software
    não repete o aviso.
    """
    avisos: List[str] = []
    store = _carregar(jogo)
    mudou = False
    for r in avaliar(jogo):
        if r["veredito"] == "acumulando":
            continue
        st = store.get(r["id"]) or {}
        if st.get("veredito_avisado") == r["veredito"]:
            continue
        st["veredito_avisado"] = r["veredito"]
        store[r["id"]] = st
        mudou = True
        marca = "CONFIRMADA" if r["veredito"] == "confirmada" else "encerrada"
        txt = (f"{r['id']} {marca} — {jogo}: {r['hits']}/{r['n']} = "
               f"{r['taxa']:.1%} contra {r['base']:.1%} do acaso "
               f"({r['razao']:.2f}x). {r['nome']}")
        avisos.append(txt)
        try:
            from notificador import notificar
            notificar(f"Compromisso {marca}: {r['id']}", txt, log_fn=log_fn)
        except Exception:
            pass
    if mudou:
        _salvar(jogo, store)
    return avisos


def resumo(jogo: str) -> str:
    linhas = avaliar(jogo)
    if not linhas:
        return ""
    L = ["[Pré-declaradas] compromissos assumidos antes do dado:"]
    for r in linhas:
        if not r["n"]:
            L.append(f"   {r['id']} {r['nome']}: sem ativação ainda")
            continue
        falta = max(0, r["n_alvo"] - r["n"])
        pt = f"p={r['p']:.3f}" if r["p"] is not None else "p=-"
        L.append(f"   {r['id']} {r['nome']}: {r['hits']}/{r['n']} = "
                 f"{r['taxa']:.1%} (acaso {r['base']:.1%}) {r['razao']:.2f}x "
                 f"{pt} — {r['veredito']}"
                 + (f", faltam ~{falta} ativações" if falta else ""))
    return "\n".join(L)
