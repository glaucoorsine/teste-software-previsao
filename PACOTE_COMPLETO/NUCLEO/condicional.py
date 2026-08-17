# -*- coding: utf-8 -*-
"""
CONDICIONAL — qual teoria serve NESTA situação, e qual serve na outra.

O QUE ELE DESCREVEU
───────────────────
    "perceber, tal teoria funciona aqui mas não funcionou aqui, então só quando
     isso aqui acontecer que eu vou usar ela. Mas tal teoria aqui onde essa não
     funcionou, funcionou, então aqui nesse tipo de situação eu uso essa outra."

    "fazer isso ao vivo ali percebendo, pelos dez últimos dias, o que está
     acontecendo, e aplicar a teoria correta"

    "opa, espera aí, eu errei essa previsão aqui. Ela entrou num consenso, não
     foi num consenso, usei teoria única, usei consenso de vinte teorias
     diferentes, mas as vinte faziam sentido nessa questão"

    "ela tem que ser um humano de QI elevadíssimo ali naquele momento e de uma
     frieza implacável"

ISTO É DIFERENTE DO QUE O AUTOEXAME JÁ FAZ
──────────────────────────────────────────
O autoexame responde "esta teoria erra mais quando a mesa está vazia (d=-0,9)".
Útil, e para aí: é um diagnóstico sobre UMA teoria.

Ele está pedindo a SUBSTITUIÇÃO. Não "a teoria A erra com mesa vazia", mas "com
mesa vazia use a B, que é onde a B rende". Isso exige uma tabela cruzada --
teoria por condição -- e uma escolha feita na condição de agora.

E É AQUI QUE ESTE SOFTWARE PODE SE ENGANAR MAIS DO QUE EM QUALQUER OUTRO LUGAR
─────────────────────────────────────────────────────────────────────────────
Vinte teorias por seis faixas de condição são cento e vinte células. Com
quinhentas janelas fechadas, cada célula tem quatro. Escolher a melhor teoria de
cada célula e depois medir o resultado na MESMA amostra devolve um número
esplêndido e falso -- é literalmente o erro que me pegou duas vezes, em
`situacao.py` (2,70x em dado sorteado ao acaso) e antes dele.

Com a "frieza implacável" que ele pediu, o desenho tem de ser:

    1. a metade ANTIGA da memória ESCOLHE qual teoria usar em cada condição
    2. a metade RECENTE MEDE o que aquela escolha rendeu
    3. o número que vai para a tela é o da etapa 2, nunca o da etapa 1

Se a escolha feita no passado rende na parte que ela não viu, a capacidade é
real. Se não rende, a tabela é decoração -- e o software tem de dizer isso, com
o número, em vez de mostrar a tabela bonita da etapa 1.

AS CONDIÇÕES SÃO POUCAS DE PROPÓSITO
────────────────────────────────────
Duas ou três faixas por eixo, não dez. Cada faixa a mais divide o `n` e dobra o
número de células. Uma tabela detalhada com quatro janelas por célula sabe menos
que uma tabela grosseira com quarenta -- e parece saber mais, que é o perigo.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

# janelas mínimas numa célula (teoria × faixa) antes de dizer algo dela
MIN_CELULA = 12
# e para a escolha valer, a teoria precisa bater a razão do resto por esta margem
MARGEM = 1.15
# QUANTOS DESVIOS PARA DECLARAR QUE O CONTRASTE É REAL, E POR QUE ALTO.
#
# Aqui não se testa uma hipótese, testam-se muitas: cada teoria contra cada eixo.
# Com vinte teorias e cinco eixos são cem comparações, e a 95% de confiança cinco
# delas "dão certo" por sorteio -- eu apresentaria cinco regras condicionais
# inventadas com aparência de medida. Um teste com uma teoria que rendia 40% em
# TODA condição declarou contraste de público com z=2,2, e não havia contraste
# nenhum ali. Z=2,5 corta esse caso e mantém os plantados (z acima de 6).
Z_CONTRASTE = 2.5
# quantos dias de memória entram. Ele falou em dez dias.
DIAS = 10


# ═══════════════════════════════════════════ as condições, poucas e grosseiras
def _faixa_publico(v) -> Optional[str]:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    # os cortes são grosseiros de propósito: mesa vazia, média, cheia
    return "vazia" if v < 600 else ("cheia" if v >= 1100 else "media")


def _faixa_seca(ctx: dict) -> Optional[str]:
    q = ctx.get("seca_quantil")
    if q is not None:
        try:
            return "longa" if float(q) >= 0.75 else "curta"
        except (TypeError, ValueError):
            pass
    return None


def _faixa_densidade(ctx: dict) -> Optional[str]:
    a = ctx.get("acima_do_45")
    if a is None:
        return None
    return "muito_mult" if a else "pouco_mult"


def _faixa_magnitude(ctx: dict) -> Optional[str]:
    m = ctx.get("magnitude")
    return str(m) if m in ("baixos", "normais", "altos") else None


def _faixa_hora(ctx: dict) -> Optional[str]:
    h = ctx.get("em_hora")
    try:
        h = int(h)
    except (TypeError, ValueError):
        return None
    # três blocos, não vinte e quatro: vinte e quatro células de hora com
    # quarenta janelas cada exigiria mil janelas para dizer qualquer coisa
    return "manha" if 5 <= h < 13 else ("tarde" if 13 <= h < 20 else "noite")


EIXOS_COND = {
    "publico": lambda c: _faixa_publico(c.get("publico")),
    "seca": _faixa_seca,
    "densidade": _faixa_densidade,
    "magnitude": _faixa_magnitude,
    "hora": _faixa_hora,
}

ROTULOS = {
    "publico": "quantidade de pessoas", "seca": "seca de multiplicador",
    "densidade": "multiplicados em 500", "magnitude": "magnitude recente",
    "hora": "faixa do dia",
}


def condicoes_de(ctx: Optional[dict]) -> Dict[str, str]:
    """Em que faixa de cada eixo este momento está."""
    ctx = ctx or {}
    out = {}
    for eixo, f in EIXOS_COND.items():
        try:
            v = f(ctx)
        except Exception:
            v = None
        if v:
            out[eixo] = v
    return out


# ═════════════════════════════════════════════════════════════ recorte de tempo
def recentes(registros: Sequence[dict], dias: int = DIAS) -> List[dict]:
    """As janelas dos últimos `dias`.

    Ele falou em dez dias, e o recorte importa: mesa muda. Uma teoria que rendia
    há um mês pode ter parado, e a média das duas coisas não descreve nenhuma.
    Registro sem data entra -- é memória antiga, e descartar memória por falta de
    campo seria jogar fora o que ele acumulou.
    """
    corte = datetime.now() - timedelta(days=max(1, dias))
    saida = []
    for r in registros or []:
        if not isinstance(r, dict):
            continue
        em = r.get("em")
        if not em:
            saida.append(r)
            continue
        try:
            if datetime.fromisoformat(str(em)) >= corte:
                saida.append(r)
        except (ValueError, TypeError):
            saida.append(r)
    return saida


def _acaso(r: dict, n_classes: int) -> Optional[float]:
    k = len(r.get("alvos") or [])
    if not k or not n_classes:
        return None
    return min(1.0, k / float(n_classes))


def _z(k1: int, n1: int, k2: int, n2: int) -> Optional[float]:
    if n1 < 2 or n2 < 2:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se <= 1e-12:
        return None
    return (k1 / n1 - k2 / n2) / se


# ═══════════════════════════════════════════ a tabela: teoria × condição
def tabela(registros: Sequence[dict], n_classes: int) -> Dict[str, Any]:
    """Quanto cada teoria rendeu em cada faixa de cada eixo.

    A razão é sempre contra o acaso da aposta que ELA fez naquelas janelas --
    uma teoria que aposta em dez números acerta mais sem ser melhor.
    """
    celulas: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in registros or []:
        if not isinstance(r, dict):
            continue
        res = r.get("resultado") or {}
        if res.get("acertou") is None:
            continue
        ac = _acaso(r, n_classes)
        if not ac:
            continue
        conds = condicoes_de(r.get("contexto"))
        acertou = 1 if res.get("acertou") else 0
        for teoria in {str(h) for h in (r.get("hips") or [])}:
            for eixo, faixa in conds.items():
                c = celulas.setdefault((teoria, eixo, faixa),
                                       {"n": 0, "ok": 0, "soma_acaso": 0.0})
                c["n"] += 1
                c["ok"] += acertou
                c["soma_acaso"] += ac
    saida: Dict[str, Any] = {}
    for (teoria, eixo, faixa), c in celulas.items():
        if c["n"] < MIN_CELULA:
            continue
        acaso = c["soma_acaso"] / c["n"]
        taxa = c["ok"] / c["n"]
        saida.setdefault(teoria, {}).setdefault(eixo, {})[faixa] = {
            "n": c["n"], "ok": c["ok"], "taxa": round(taxa, 4),
            "acaso": round(acaso, 4),
            "razao": round(taxa / acaso, 3) if acaso else None,
        }
    return saida


def contraste(tab: Dict[str, Any]) -> List[Dict[str, Any]]:
    """As teorias que rendem numa faixa e NÃO rendem na outra do mesmo eixo.

    É exatamente o que ele descreveu: "funciona aqui mas não funcionou aqui". Uma
    teoria que rende igual em todas as faixas não entra -- ela não é condicional,
    é só boa (ou só ruim), e tratá-la como condicional inventaria uma regra.
    """
    saida = []
    for teoria, eixos in tab.items():
        for eixo, faixas in eixos.items():
            comp = [(f, d) for f, d in faixas.items() if d.get("razao")]
            if len(comp) < 2:
                continue
            comp.sort(key=lambda x: -x[1]["razao"])
            boa, ruim = comp[0], comp[-1]
            if boa[1]["razao"] < ruim[1]["razao"] * MARGEM:
                continue
            z = _z(boa[1]["ok"], boa[1]["n"], ruim[1]["ok"], ruim[1]["n"])
            saida.append({
                "teoria": teoria, "eixo": eixo, "rotulo": ROTULOS.get(eixo, eixo),
                "boa_faixa": boa[0], "boa": boa[1],
                "ruim_faixa": ruim[0], "ruim": ruim[1],
                "z": round(z, 2) if z is not None else None,
                "confia": bool(z is not None and z >= Z_CONTRASTE),
            })
    saida.sort(key=lambda x: -(x["boa"]["razao"] or 0))
    return saida


# ══════════════════════ a escolha, e a prova de que ela vale fora da amostra
def escolher(tab: Dict[str, Any], conds: Dict[str, str],
             contrastes: Optional[Sequence[dict]] = None) -> Dict[str, Any]:
    """Nas condições de AGORA, em quais teorias confiar e em quais não.

    SÓ O EIXO QUE COMPROVADAMENTE DIFERENCIA AQUELA TEORIA PESA
    ───────────────────────────────────────────────────────────
    A primeira versão disto tirava a média das razões de TODOS os eixos. Parece
    razoável e está errado: um eixo sem estrutura nenhuma -- a hora, digamos --
    devolve para os dois lados a razão geral da teoria, e essa razão geral entra na
    média afogando o eixo que de fato diferencia.

    No teste plantado o efeito foi total: a teoria A rendia 3,5x com mesa cheia e
    0,5x com vazia, mas somada à hora (2,0x nas duas faixas) o conselho saía
    "confie" nas duas condições. A tabela sabia a coisa certa e o conselho saía
    errado -- e sem um grupo "desconfie" a validação fora da amostra nem podia ser
    calculada.

    Então o peso vem apenas dos eixos em que `contraste` confirmou que ESTA teoria
    se comporta diferente. Sem eixo confirmado, peso 1,0: silêncio, não punição.
    Não saber não é o mesmo que saber que é ruim.
    """
    confirmados = set()
    for c in (contrastes or []):
        if c.get("confia"):
            confirmados.add((str(c.get("teoria")), str(c.get("eixo"))))
    peso: Dict[str, float] = {}
    porque: Dict[str, str] = {}
    for teoria, eixos in tab.items():
        razoes, notas = [], []
        for eixo, faixa in conds.items():
            if contrastes is not None and (teoria, eixo) not in confirmados:
                continue
            d = (eixos.get(eixo) or {}).get(faixa)
            if not d or not d.get("razao"):
                continue
            razoes.append(float(d["razao"]))
            notas.append(f"{ROTULOS.get(eixo, eixo)}={faixa}: {d['razao']}x "
                         f"(n={d['n']})")
        if not razoes:
            continue
        media = sum(razoes) / len(razoes)
        peso[teoria] = round(max(0.4, min(2.0, media)), 3)
        porque[teoria] = "; ".join(notas[:3])
    return {"pesos": peso, "porque": porque, "condicoes": conds}


def validar(registros: Sequence[dict], n_classes: int) -> Dict[str, Any]:
    """A tabela vale fora da amostra que a construiu?

    A METADE ANTIGA ESCOLHE, A METADE RECENTE MEDE
    ──────────────────────────────────────────────
    Sem esta separação o número seria fabricado: escolher a melhor teoria de cada
    célula e medir na mesma célula devolve razão alta em dado puramente sorteado.
    Foi assim que `situacao.py` me deu 2,70x em ruído.

    Aqui a tabela é montada só com a metade ANTIGA. Depois, para cada janela da
    metade RECENTE, olha-se qual teoria a tabela antiga recomendaria naquela
    condição, e mede-se se ela acertou. O número que sai é o que a recomendação
    rendeu no que ela nunca viu.

    `razao_recomendada` acima de 1 quer dizer que houve capacidade condicional
    real. Perto de 1, a tabela não sabe escolher -- e é isso que o software diz.
    """
    fechados = [r for r in (registros or [])
                if isinstance(r, dict) and (r.get("resultado") or {}).get("acertou") is not None]
    if len(fechados) < 4 * MIN_CELULA:
        return {"mediu": False,
                "nota": f"{len(fechados)} janelas fechadas; preciso de "
                        f"{4 * MIN_CELULA} para separar escolha de medida"}
    # `avaliadas` vem em ordem cronológica de fechamento: o fim é o recente
    metade = len(fechados) // 2
    antigo, recente = fechados[:metade], fechados[metade:]
    tab = tabela(antigo, n_classes)
    ctr = contraste(tab)          # os eixos confirmados NA METADE ANTIGA
    if not tab:
        return {"mediu": False,
                "nota": "a metade antiga não tem célula com amostra suficiente"}

    # DOIS GRUPOS DISJUNTOS, E ISSO NÃO É DETALHE
    # ────────────────────────────────────────────
    # A primeira versão disto comparava "as janelas em que a tabela recomendou"
    # contra "todas as janelas recentes" -- e o segundo conjunto CONTÉM o
    # primeiro. Numa mesa com estrutura condicional plantada, os dois números
    # saíram idênticos (2,018x contra 2,018x): eu havia comparado um conjunto
    # consigo mesmo e chamado aquilo de validação fora da amostra.
    #
    # A comparação que responde a pergunta é entre grupos que não se cruzam: as
    # janelas em que a tabela antiga disse CONFIE nesta teoria, contra as em que
    # ela disse DESCONFIE. Se a tabela sabe alguma coisa, o primeiro grupo rende
    # mais que o segundo. Os dois estão na metade que a tabela nunca viu.
    conf_ok = conf_n = 0
    desc_ok = desc_n = 0
    conf_acaso = desc_acaso = 0.0
    for r in recente:
        ac = _acaso(r, n_classes)
        if not ac:
            continue
        conds = condicoes_de(r.get("contexto"))
        if not conds:
            continue
        esc = escolher(tab, conds, ctr)["pesos"]
        minhas = {str(h) for h in (r.get("hips") or [])}
        candidatas = [w for t, w in esc.items() if t in minhas]
        if not candidatas:
            continue
        # a decisão da tabela sobre ESTA volta: o melhor conselho disponível
        conselho = max(candidatas)
        acertou = 1 if (r["resultado"] or {}).get("acertou") else 0
        if conselho > 1.05:
            conf_n += 1
            conf_ok += acertou
            conf_acaso += ac
        elif conselho < 0.95:
            desc_n += 1
            desc_ok += acertou
            desc_acaso += ac
        # entre 0,95 e 1,05 a tabela não tem opinião: fica fora dos dois grupos
    if conf_n < MIN_CELULA or desc_n < MIN_CELULA:
        return {"mediu": False,
                "nota": f"na metade recente a tabela antiga disse CONFIE em "
                        f"{conf_n} janelas e DESCONFIE em {desc_n}; preciso de "
                        f"{MIN_CELULA} de cada para comparar"}
    r_conf = (conf_ok / conf_n) / (conf_acaso / conf_n)
    r_desc = (desc_ok / desc_n) / (desc_acaso / desc_n)
    z = _z(conf_ok, conf_n, desc_ok, desc_n)
    return {"mediu": True,
            "n_confie": conf_n, "n_desconfie": desc_n,
            "n_recentes": len(recente),
            "razao_confie": round(r_conf, 3),
            "razao_desconfie": round(r_desc, 3),
            "z": round(z, 2) if z is not None else None,
            "ganho": round(r_conf / r_desc, 3) if r_desc > 0 else None,
            # tamanho E significância: razão sozinha confirma ruído
            "vale": bool(r_desc > 0 and r_conf >= r_desc * MARGEM
                         and z is not None and z >= 2.0)}


# ═══════════════════════════════════ como a previsão foi formada, e se prestou
def por_formacao(registros: Sequence[dict], n_classes: int) -> Dict[str, Any]:
    """Teoria única rende diferente de consenso de vinte?

        "eu errei essa previsão aqui... ela entrou num consenso, não foi num
         consenso, usei teoria única, usei consenso de vinte teorias diferentes,
         mas as vinte faziam sentido nessa questão"

    A pergunta dele tem duas partes, e as duas são mensuráveis: quantas teorias
    formaram a decisão, e se aquelas teorias eram as adequadas ÀQUELA condição --
    "faziam sentido nessa questão". A segunda é a que interessa: consenso de vinte
    teorias que não servem para o momento é vinte vozes erradas, e conta como
    consenso na tela.
    """
    grupos: Dict[str, Dict[str, float]] = {}
    for r in registros or []:
        if not isinstance(r, dict):
            continue
        res = r.get("resultado") or {}
        if res.get("acertou") is None:
            continue
        ac = _acaso(r, n_classes)
        if not ac:
            continue
        n_t = len({str(h) for h in (r.get("hips") or [])})
        if n_t <= 1:
            rot = "teoria única"
        elif n_t <= 4:
            rot = f"consenso pequeno (2-4)"
        elif n_t <= 10:
            rot = "consenso médio (5-10)"
        else:
            rot = "consenso largo (11+)"
        g = grupos.setdefault(rot, {"n": 0, "ok": 0, "acaso": 0.0})
        g["n"] += 1
        g["ok"] += 1 if res.get("acertou") else 0
        g["acaso"] += ac
        # e o corte que ele pediu: as teorias faziam sentido na condição?
        cab = (r.get("contexto") or {}).get("votantes_em_condicao")
        if cab is not None and n_t > 1:
            try:
                frac = float(cab) / max(1, n_t)
            except (TypeError, ValueError):
                frac = None
            if frac is not None:
                rot2 = ("consenso de teorias que serviam"
                        if frac >= 0.6 else
                        "consenso de teorias que não serviam")
                g2 = grupos.setdefault(rot2, {"n": 0, "ok": 0, "acaso": 0.0})
                g2["n"] += 1
                g2["ok"] += 1 if res.get("acertou") else 0
                g2["acaso"] += ac
    saida = {}
    for rot, g in grupos.items():
        if g["n"] < MIN_CELULA:
            continue
        acaso = g["acaso"] / g["n"]
        taxa = g["ok"] / g["n"]
        saida[rot] = {"n": int(g["n"]), "taxa": round(taxa, 4),
                      "acaso": round(acaso, 4),
                      "razao": round(taxa / acaso, 3) if acaso else None}
    return saida


# ════════════════════════════════════════════════════════════════════ a voz
def ler(registros: Sequence[dict], n_classes: int,
        contexto_agora: Optional[dict] = None,
        dias: int = DIAS) -> Dict[str, Any]:
    regs = recentes(registros, dias)
    tab = tabela(regs, n_classes)
    conds = condicoes_de(contexto_agora)
    ctr = contraste(tab)
    return {"dias": dias, "n_janelas": len(regs),
            "tabela": tab,
            "contraste": ctr,
            "escolha": escolher(tab, conds, ctr) if conds else None,
            "validacao": validar(regs, n_classes),
            "formacao": por_formacao(regs, n_classes)}


def resumo(r: Dict[str, Any], quantas: int = 4) -> List[str]:
    L: List[str] = []
    tab = r.get("tabela") or {}
    if not tab:
        L.append(f"[Condicional] {r.get('n_janelas', 0)} janelas nos últimos "
                 f"{r.get('dias')} dias — nenhuma célula (teoria × condição) tem "
                 f"as {MIN_CELULA} janelas de que preciso; ainda não sei dizer "
                 f"qual teoria serve em qual situação")
        return L

    L.append(f"[Condicional] {len(tab)} teorias × condições nos últimos "
             f"{r.get('dias')} dias ({r.get('n_janelas')} janelas):")
    for c in (r.get("contraste") or [])[:quantas]:
        marca = "" if c["confia"] else "   (dentro do ruído — não uso ainda)"
        L.append(f"[Condicional]   {c['teoria']}: com {c['rotulo']}="
                 f"{c['boa_faixa']} rende {c['boa']['razao']}x (n={c['boa']['n']}); "
                 f"com ={c['ruim_faixa']} rende {c['ruim']['razao']}x "
                 f"(n={c['ruim']['n']}), z={c['z']}{marca}")
    if not (r.get("contraste") or []):
        L.append("[Condicional]   nenhuma teoria rende diferente por condição — "
                 "as que existem são boas ou ruins em toda situação, e tratá-las "
                 "como condicionais inventaria regra")

    esc = r.get("escolha") or {}
    if esc.get("pesos"):
        conds = ", ".join(f"{ROTULOS.get(k, k)}={v}"
                          for k, v in (esc.get("condicoes") or {}).items())
        L.append(f"[Condicional] AGORA ({conds}) — em quem confiar:")
        ordem = sorted(esc["pesos"].items(), key=lambda kv: -kv[1])
        for t, w in ordem[:3]:
            L.append(f"[Condicional]   ↑ {t} peso {w:.2f} — "
                     f"{(esc.get('porque') or {}).get(t, '')}")
        for t, w in [x for x in ordem if x[1] < 0.9][:2]:
            L.append(f"[Condicional]   ↓ {t} peso {w:.2f} — "
                     f"{(esc.get('porque') or {}).get(t, '')}")

    v = r.get("validacao") or {}
    if v.get("mediu"):
        veredito = ("VALE — a escolha feita no passado rendeu no que ela não viu"
                    if v.get("vale") else
                    "NÃO VALE ainda — confiar e desconfiar deu no mesmo")
        L.append(f"[Condicional] fora da amostra: onde a tabela antiga disse "
                 f"CONFIE rendeu {v['razao_confie']}x (n={v['n_confie']}); onde "
                 f"disse DESCONFIE, {v['razao_desconfie']}x (n={v['n_desconfie']}), "
                 f"z={v.get('z')} → {veredito}")
    elif v.get("nota"):
        L.append(f"[Condicional] fora da amostra ainda não é testável — "
                 f"{v['nota']}")

    form = r.get("formacao") or {}
    if form:
        L.append("[Formação] o que rendeu por jeito de decidir:")
        for rot, d in sorted(form.items(), key=lambda kv: -(kv[1]["razao"] or 0)):
            L.append(f"[Formação]   {rot}: {d['taxa']:.0%} contra acaso "
                     f"{d['acaso']:.0%} = {d['razao']}x (n={d['n']})")
    return L
