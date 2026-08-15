# -*- coding: utf-8 -*-
"""
12 pesquisadores distintos — geram expressões DSL, não só parâmetros de uma função.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set
from .dsl_hipoteses import make_hipotese, legivel

JANELAS = [3, 5, 8, 12, 20, 30, 50, 80, 120, 200, 350, 500, 1000]

def _vals(eventos) -> List[str]:
    return [e.valor if hasattr(e, "valor") else str(e) for e in eventos]

class AgenteBase:
    id = "A00"
    nome = "BASE"
    orcamento = 8

    def propor(self, eventos, dataset_id: str, dominio: Set[str]) -> List[dict]:
        raise NotImplementedError

def _dom_list(dominio: Set[str]) -> List[str]:
    return sorted(dominio)

class A01ComposicaoSimbolica(AgenteBase):
    id = "A01"; nome = "COMPOSICAO_SIMBOLICA"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        if len(h) < 15:
            return []
        out = []
        # compõe AND de last_is + count_in_window
        for w in [w for w in JANELAS if 5 <= w <= 80][:6]:
            top = [x for x, _ in Counter(h[:w]).most_common(3)]
            if len(top) < 2:
                continue
            expr = {
                "op": "and",
                "args": [
                    {"op": "count_in_window", "valor": top[0], "w": w, "k": 2},
                    {"op": "in_set", "set": top[:3]},
                ],
            }
            out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, w,
                                     descricao=legivel(expr)))
            if len(out) >= self.orcamento:
                break
        return out

class A02SequenciaOrdemVariavel(AgenteBase):
    id = "A02"; nome = "SEQUENCIA_ORDEM_VAR"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        out = []
        # transições de ordem 1..3 (não só pares)
        for ordem in (1, 2, 3):
            if len(h) < ordem + 5:
                continue
            ctr = Counter()
            for i in range(len(h) - ordem - 1):
                # contexto = h[i+1 : i+1+ordem] (mais recente primeiro no slice invertido)
                ctx = tuple(h[i + 1: i + 1 + ordem])
                nxt = h[i]
                ctr[(ctx, nxt)] += 1
            for (ctx, nxt), n in ctr.most_common(5):
                if n < 2:
                    continue
                if ordem == 1:
                    expr = {"op": "transition", "a": ctx[0], "b": nxt}
                else:
                    expr = {"op": "subseq", "seq": list(reversed(ctx)) + [nxt]}
                    # subseq antiga→nova; ativação usa seq sem último como contexto
                    expr = {"op": "subseq", "seq": list(reversed(ctx))}
                    # candidatos via transition do último do ctx
                    expr = {
                        "op": "and",
                        "args": [
                            {"op": "subseq", "seq": list(reversed(ctx))},
                            {"op": "transition", "a": ctx[0], "b": nxt},
                        ],
                    }
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 20 + ordem * 5,
                                         descricao=f"ordem{ordem} {ctx}→{nxt} n={n}"))
                if len(out) >= self.orcamento:
                    return out
        return out

class A03MotivosSubseq(AgenteBase):
    id = "A03"; nome = "MOTIVOS_SUBSEQ"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        out = []
        for L in (2, 3, 4):
            if len(h) < L + 8:
                continue
            ctr = Counter()
            for i in range(len(h) - L):
                # cronológico antigo→novo dentro da janela invertida
                seq = tuple(reversed(h[i:i + L]))
                ctr[seq] += 1
            for seq, n in ctr.most_common(6):
                if n < 2:
                    continue
                expr = {"op": "subseq", "seq": list(seq)}
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 30,
                                         descricao=f"motivo{L} {seq} n={n}"))
                if len(out) >= self.orcamento:
                    return out
        return out

class A04Recorrencia(AgenteBase):
    id = "A04"; nome = "RECORRENCIA"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        out = []
        for v, c in Counter(h[:40]).most_common(8):
            gaps = []
            last = None
            for i, x in enumerate(h):
                if x == v:
                    if last is not None:
                        gaps.append(i - last)
                    last = i
            if len(gaps) < 2:
                continue
            med = sorted(gaps)[len(gaps) // 2]
            expr = {"op": "gap_since", "valor": v, "min_gap": max(3, int(med * 0.8))}
            out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 40,
                                     descricao=f"gap {v} med={med}"))
            expr2 = {"op": "run_length", "valor": v, "min_run": 2}
            out.append(make_hipotese(expr2, self.id, dataset_id, dataset_id, 15,
                                     descricao=f"eco potencial {v}"))
            if len(out) >= self.orcamento:
                break
        return out[: self.orcamento]

class A05GrafoCoocorrencia(AgenteBase):
    id = "A05"; nome = "GRAFO_COO"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        if len(h) < 20:
            return []
        co = defaultdict(int)
        for w in [w for w in JANELAS if 8 <= w <= 50][:5]:
            for i in range(0, min(len(h) - w, 40)):
                u = sorted(set(h[i:i + w]))
                for a_i in range(len(u)):
                    for b_i in range(a_i + 1, len(u)):
                        co[(u[a_i], u[b_i])] += 1
        fortes = sorted(co.items(), key=lambda x: -x[1])[:15]
        if not fortes:
            return []
        # comunidade greedy
        cluster = set(fortes[0][0])
        for (a, b), n in fortes[1:]:
            if n < 3:
                continue
            if a in cluster or b in cluster:
                cluster.add(a); cluster.add(b)
            if len(cluster) >= 6:
                break
        if len(cluster) < 3:
            return []
        expr = {"op": "cooccur", "set": sorted(cluster), "w": 10}
        return [make_hipotese(expr, self.id, dataset_id, dataset_id, 10,
                              descricao=f"comunidade {sorted(cluster)[:5]}")]

class A06RegimesMultiescala(AgenteBase):
    id = "A06"; nome = "REGIMES"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        out = []
        # mudança de moda entre janelas
        for w1, w2 in [(a,b) for a in JANELAS for b in JANELAS if 8<=a<b<=200][:8]:
            if len(h) < w2:
                continue
            m1 = Counter(h[:w1]).most_common(1)[0][0]
            m2 = Counter(h[w1:w2]).most_common(1)[0][0]
            if m1 == m2:
                continue
            expr = {
                "op": "and",
                "args": [
                    {"op": "window_diff", "valor": m1, "w_curta": w1, "w_longa": w2, "margem": 0.04},
                    {"op": "in_set", "set": [m1]},
                ],
            }
            out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, w2,
                                     descricao=f"regime {m1} vs {m2} w{w1}/{w2}"))
        return out[: self.orcamento]

class A07Interacoes(AgenteBase):
    id = "A07"; nome = "INTERACOES"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        if len(h) < 20:
            return []
        out = []
        top = [x for x, _ in Counter(h[:25]).most_common(4)]
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                expr = {
                    "op": "and",
                    "args": [
                        {"op": "count_in_window", "valor": top[i], "w": 15, "k": 2},
                        {"op": "count_in_window", "valor": top[j], "w": 15, "k": 1},
                        {"op": "transition", "a": top[i], "b": top[j]},
                    ],
                }
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 15,
                                         descricao=f"interação {top[i]}&{top[j]}"))
                if len(out) >= self.orcamento:
                    return out
        return out

class A08Temporalidade(AgenteBase):
    id = "A08"; nome = "TEMPORALIDADE"
    def propor(self, eventos, dataset_id, dominio):
        # sem timestamps → declara indisponibilidade via hipótese vazia marcada
        ts = [e.ts for e in eventos if getattr(e, "ts", None)]
        if len(ts) < 10:
            return []  # sem evidência temporal
        # com ts: agrupa por "sessão" simples (mesma hora se ISO)
        out = []
        horas = []
        for e in eventos[:40]:
            if e.ts and "T" in str(e.ts):
                horas.append(str(e.ts).split("T")[1][:2])
        if len(horas) >= 8:
            moda = Counter(horas).most_common(1)[0][0]
            # usa last values como proxy — temporal puro limitado
            top = [x for x, _ in Counter(_vals(eventos)[:20]).most_common(2)]
            if top:
                expr = {"op": "in_set", "set": top}
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 20,
                                         descricao=f"sessão hora~{moda} top={top}"))
        return out

class A09EstadosSemelhantes(AgenteBase):
    id = "A09"; nome = "ESTADOS_SEMELHANTES"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        if len(h) < 30:
            return []
        alvo = tuple(h[:5])
        out = []
        # busca trechos passados com overlap
        for i in range(5, min(len(h) - 6, 60)):
            trecho = tuple(h[i:i + 5])
            inter = len(set(alvo) & set(trecho))
            if inter >= 3:
                # o que veio depois daquele trecho (mais recente que i é h[i-1])
                nxt = h[i - 1]
                expr = {
                    "op": "and",
                    "args": [
                        {"op": "cooccur", "set": list(alvo), "w": 5},
                        {"op": "transition", "a": h[1] if len(h) > 1 else h[0], "b": nxt},
                    ],
                }
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 25,
                                         descricao=f"estado~{list(alvo)[:3]}→{nxt}"))
                if len(out) >= self.orcamento:
                    break
        return out

class A10RepresentacaoLatente(AgenteBase):
    id = "A10"; nome = "LATENTE"
    def propor(self, eventos, dataset_id, dominio):
        # representação bag-of-symbols em janelas; cluster por jaccard
        h = _vals(eventos)
        if len(h) < 40:
            return []
        windows = [set(h[i:i + 8]) for i in range(0, min(40, len(h) - 8), 4)]
        if len(windows) < 4:
            return []
        # encontra par de janelas mais similar e extrai união como set
        best = (0, 0, 0)
        for i in range(len(windows)):
            for j in range(i + 1, len(windows)):
                u = windows[i] | windows[j]
                inter = windows[i] & windows[j]
                jacc = len(inter) / max(len(u), 1)
                if jacc > best[0]:
                    best = (jacc, i, j)
        if best[0] < 0.4:
            return []
        sset = sorted(windows[best[1]] & windows[best[2]])
        if len(sset) < 2:
            sset = sorted(windows[best[1]] | windows[best[2]])[:5]
        expr = {"op": "cooccur", "set": sset, "w": 8}
        return [make_hipotese(expr, self.id, dataset_id, dataset_id, 8,
                              descricao=f"latente jacc={best[0]:.2f} {sset[:4]}")]

class A11Residuos(AgenteBase):
    id = "A11"; nome = "RESIDUOS"
    def __init__(self):
        self.catalog_ref = None
    def propor(self, eventos, dataset_id, dominio):
        # analisa o que o top-freq erra
        h = _vals(eventos)
        if len(h) < 25:
            return []
        top = [x for x, _ in Counter(h[1:21]).most_common(5)]
        residuos = [h[0]] if h[0] not in top else []
        # valores que saem após erro de top-freq
        out = []
        for i in range(min(30, len(h) - 1)):
            past_top = [x for x, _ in Counter(h[i + 1:i + 16]).most_common(3)]
            if h[i] not in past_top:
                residuos.append(h[i])
        res_ctr = Counter(residuos)
        for v, n in res_ctr.most_common(4):
            if n < 2:
                continue
            expr = {
                "op": "and",
                "args": [
                    {"op": "not", "arg": {"op": "in_set", "set": top[:3]}},
                    {"op": "gap_since", "valor": v, "min_gap": 5},
                ],
            }
            # candidatos: o resíduo
            expr = {"op": "gap_since", "valor": v, "min_gap": 8}
            out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 30,
                                     descricao=f"resíduo {v} n={n}"))
        return out[: self.orcamento]

class A12ExploradorNovidade(AgenteBase):
    id = "A12"; nome = "NOVIDADE"
    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        out = []
        # explora combinações NOT + transition pouco óbvias
        rare = [x for x, c in Counter(h[:50]).items() if c == 1][:5]
        common = [x for x, _ in Counter(h[:30]).most_common(3)]
        for r in rare:
            for c in common:
                expr = {
                    "op": "and",
                    "args": [
                        {"op": "not", "arg": {"op": "count_in_window", "valor": r, "w": 20, "k": 2}},
                        {"op": "transition", "a": c, "b": r},
                    ],
                }
                out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, 25,
                                         descricao=f"novidade {c}→raro {r}"))
                if len(out) >= self.orcamento:
                    return out
        # janelas atípicas
        for w in [w for w in JANELAS if w in (5,50,120,200,350,500)][:6]:
            if len(h) < w:
                continue
            v = Counter(h[:w]).most_common(1)[0][0]
            expr = {"op": "count_in_window", "valor": v, "w": w, "k": max(2, w // 10)}
            out.append(make_hipotese(expr, self.id, dataset_id, dataset_id, w,
                                     descricao=f"novidade escala w={w} v={v}"))
        return out[: self.orcamento]

class A13Finais(AgenteBase):
    """O agente que faltava: descobrir no mundo dos FINAIS.

    Ele perguntou por que as IAs não descobrem o que ele descobre. Fui ver, e
    a resposta era simples e feia: `final_in` existia no vocabulário, mas
    NENHUM dos doze descobridores propunha uma hipótese de final. Elas não
    achavam a teoria dele porque não sabiam dizer aquela palavra.

    Este agente olha o final do último número e pergunta se algum grupo de
    finais vem atrás com força. Ele não recebe as famílias dele prontas: monta
    os grupos a partir do que está saindo, para poder achar famílias que ele
    ainda não percebeu — inclusive alguma que contradiga as três conhecidas.
    """
    id = "A13"; nome = "FINAIS"

    def propor(self, eventos, dataset_id, dominio):
        h = _vals(eventos)
        if len(h) < 30:
            return []
        out = []
        # o que vem depois de cada final, medido no próprio histórico
        depois = defaultdict(Counter)
        for a, b in zip(h[1:], h):          # h vem do mais novo para o mais velho
            try:
                depois[str(a)[-1]][str(b)[-1]] += 1
            except Exception:
                continue
        for fin, cont in depois.items():
            if sum(cont.values()) < 12:
                continue
            grupo = [f for f, _ in cont.most_common(3)]
            expr = {"op": "and", "args": [
                {"op": "final_in", "finais": [fin]},
                {"op": "in_set", "valores": sorted(
                    x for x in dominio if str(x)[-1] in set(grupo))},
            ]}
            out.append(make_hipotese(
                expr, self.id, dataset_id, dataset_id, 30,
                descricao=f"final {fin} → finais {','.join(grupo)}"))
            if len(out) >= self.orcamento:
                break
        # e a forma pura: o final se repete
        for fin, _ in Counter(str(x)[-1] for x in h[:60] if x).most_common(3):
            expr = {"op": "final_in", "finais": [fin]}
            out.append(make_hipotese(
                expr, self.id, dataset_id, dataset_id, 40,
                descricao=f"final {fin} chama final {fin}"))
            if len(out) >= self.orcamento:
                break
        return out[: self.orcamento]


AGENTES = [
    A01ComposicaoSimbolica(), A02SequenciaOrdemVariavel(), A03MotivosSubseq(),
    A04Recorrencia(), A05GrafoCoocorrencia(), A06RegimesMultiescala(),
    A07Interacoes(), A08Temporalidade(), A09EstadosSemelhantes(),
    A10RepresentacaoLatente(), A11Residuos(), A12ExploradorNovidade(),
    A13Finais(),
]
