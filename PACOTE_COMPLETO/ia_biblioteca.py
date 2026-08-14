import os
# -*- coding: utf-8 -*-
"""
Biblioteca compartilhada para Mega Fire, Lightning e Crazy Time.
Padrões, estatísticas, fórmulas e ensemble de 3 IAs.
"""
from collections import Counter, defaultdict
from math import log, exp, sqrt
from datetime import datetime

# ----------------- Roda europeia -----------------
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
WPOS = {n: i for i, n in enumerate(WHEEL)}
REDS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
ENDS_GROUPS = {
    "1-3-6": [1, 3, 6],
    "4-5-9": [4, 5, 9],
    "0-2-7-8": [0, 2, 7, 8],
}
# Associações do usuário (roleta)
ASSOC = {
    0: [8], 1: [3, 7], 2: [4], 3: [1, 7], 4: [2], 5: [9], 6: [8, 18], 7: [1],
    8: [0, 6, 18], 9: [5], 10: [11, 13, 15], 11: [10, 13, 15], 12: [17],
    13: [10, 11, 15], 14: [12, 16, 18], 15: [10, 11, 13], 16: [14],
    17: [12, 20, 22], 18: [6, 8], 19: [21, 25, 27, 32], 20: [17, 22],
    21: [19, 25, 27, 32], 22: [20], 23: [19, 21, 25, 27, 32], 24: [29],
    25: [19, 21, 27, 32], 26: [28], 27: [19, 30, 36], 28: [26, 29],
    29: [24, 7], 30: [27, 34, 36], 31: [33], 32: [19, 21, 25, 27],
    33: [31], 34: [30, 36], 35: list(range(30, 37)), 36: [30, 34],
}

def neigh(n, d=2):
    p = WPOS.get(n)
    if p is None:
        return []
    L = len(WHEEL)
    out = []
    for i in range(1, d + 1):
        out += [WHEEL[(p - i) % L], WHEEL[(p + i) % L]]
    return out


# ---- buffer de comunicação ao vivo (para UI) ----
from collections import deque as _deque_meta
COMUNICACAO_IA = {
    "mega_fire": _deque_meta(maxlen=40),
    "lightning": _deque_meta(maxlen=40),
    "crazy_time": _deque_meta(maxlen=40),
}

def ia_falar(jogo, quem, msg):
    """Registra mensagem de uma IA para aparecer no painel ao vivo."""
    try:
        from datetime import datetime as _dtm
        linha = f"{_dtm.now().strftime('%H:%M:%S')} [{quem}] {msg}"
        if jogo not in COMUNICACAO_IA:
            COMUNICACAO_IA[jogo] = _deque_meta(maxlen=40)
        COMUNICACAO_IA[jogo].appendleft(linha)
        return linha
    except Exception:
        return msg

def ia_ler_comunicacao(jogo, n=20):
    try:
        return list(COMUNICACAO_IA.get(jogo, []))[:n]
    except Exception:
        return []

# ----------------- Fórmulas estatísticas -----------------
def gap(numbers, n, window=80):
    for i, x in enumerate(numbers[:window]):
        if x == n:
            return i
    return min(window, len(numbers))

def freq_map(numbers, window=40):
    return Counter(numbers[:window])

def overdue_score(g, expected=37/1.0):
    """Quanto o atraso passa da média esperada (roleta ~37)."""
    if expected <= 0:
        return 0.0
    return max(0.0, (g / expected) - 1.0)

def softmax_topk(scores, k=8, temp=1.0):
    """Normaliza scores (menor=melhor no nosso motor) em pesos positivos."""
    items = sorted(scores.items(), key=lambda x: x[1])[:k]
    if not items:
        return {}
    # inverter: menor score → maior peso
    inv = {n: exp(-s / max(temp, 0.1)) for n, s in items}
    tot = sum(inv.values()) or 1.0
    return {n: v / tot for n, v in inv.items()}

def entropy(counter):
    tot = sum(counter.values()) or 1
    h = 0.0
    for v in counter.values():
        p = v / tot
        if p > 0:
            h -= p * log(p + 1e-12)
    return h

def zscore(val, mean, std):
    if std <= 1e-9:
        return 0.0
    return (val - mean) / std

# ----------------- Biblioteca de padrões (roleta) -----------------
def padrao_finais(numbers, window=25):
    ends = [n % 10 for n in numbers[:window]]
    c = Counter(ends)
    best = c.most_common(1)[0] if c else (None, 0)
    saturado = best[1] >= 8 if best[0] is not None else False
    return {"counts": dict(c), "dominante": best[0], "saturado": saturado}

def padrao_isolamento(numbers, window=42):
    s = set(numbers[:window])
    return [n for n in range(37) if n not in s]

def padrao_setores_frios(numbers, window=15):
    heat = [0.0] * 37
    for i, x in enumerate(numbers[:window]):
        w = 1.3 - i * 0.05
        heat[x] += 3 * w
        for nb in neigh(x, 2):
            heat[nb] += 1.4 * w
    return sorted(range(37), key=lambda n: heat[n])

def padrao_markov(numbers, depth=50):
    trans = defaultdict(Counter)
    for i in range(min(depth, len(numbers) - 1)):
        trans[numbers[i]][numbers[i + 1]] += 1
    return trans

def padrao_coluna_duzia(numbers, window=25):
    mid = [x for x in numbers[:window] if x != 0]
    col = [0, 0, 0]
    doz = [0, 0, 0]
    for x in mid:
        col[(x - 1) % 3] += 1
        doz[(x - 1) // 12] += 1
    return {
        "col_fria": col.index(min(col)) if mid else 0,
        "doz_fria": doz.index(min(doz)) if mid else 0,
        "col": col,
        "doz": doz,
    }

def padrao_paridade(numbers, window=25):
    mid = [x for x in numbers[:window] if x != 0]
    pares = sum(1 for x in mid if x % 2 == 0)
    return {"pares": pares, "impares": len(mid) - pares, "n": len(mid)}

# ----------------- Crazy Time padrões -----------------
CT_SETORES = ["1", "2", "5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"]
CT_CICLO = {"1": 3.5, "2": 3.5, "5": 7.0, "10": 13.5,
            "CoinFlip": 13.5, "CashHunt": 27, "Pachinko": 27, "CrazyBonus": 54}

def ct_last_pos(sectors):
    last = {}
    for i, s in enumerate(sectors):
        if s not in last:
            last[s] = i
    return last

def ct_atraso_scores(sectors):
    last = ct_last_pos(sectors)
    n = len(sectors)
    out = {}
    for a, ciclo in CT_CICLO.items():
        gap = last.get(a, n)
        out[a] = overdue_score(gap, ciclo)
    return out

# ----------------- 3 IAs (ensemble) -----------------
class IABase:
    nome = "base"
    def votar_roleta(self, numbers, fire=None, ap_peso=None):
        """Retorna dict {numero: score} menor = melhor."""
        return {i: 0.0 for i in range(37)}
    def votar_ct(self, sectors, full=None, ap_peso=None):
        """Retorna dict {setor: forca} maior = melhor."""
        return {s: 0.0 for s in CT_SETORES}

class IAConservadora(IABase):
    """Isolamento, atraso, anti-saturação, poucos alvos."""
    nome = "Conservadora"
    def votar_roleta(self, numbers, fire=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        sc = {i: 0.0 for i in range(37)}
        isol = padrao_isolamento(numbers, 45)
        for n in isol:
            sc[n] -= 3.5 * ap_peso("Isolamento")
        for n in range(37):
            g = gap(numbers, n, 70)
            sc[n] -= overdue_score(g, 37) * 3.0 * ap_peso("Atraso")
        for i, x in enumerate(numbers[:10]):
            sc[x] += (12 - i) * 2.0  # penaliza recente
        pf = padrao_finais(numbers)
        if pf["saturado"] and pf["dominante"] is not None:
            for n in range(37):
                if n % 10 == pf["dominante"]:
                    sc[n] += 2.0  # evita saturado
        frios = padrao_setores_frios(numbers, 15)[:12]
        for n in frios:
            sc[n] -= 1.5 * ap_peso("Setor_Frio")
        # associações do usuário + colunas/dúzias frias
        try:
            cd = padrao_coluna_duzia(numbers, 25)
            for n in range(1, 37):
                if (n - 1) % 3 == cd["col_fria"]:
                    sc[n] -= 1.2 * ap_peso("Coluna_Fria")
                if (n - 1) // 12 == cd["doz_fria"]:
                    sc[n] -= 1.2 * ap_peso("Duzia_Fria")
            if numbers:
                last = numbers[0]
                for a in ASSOC.get(last, []):
                    if 0 <= a <= 36:
                        sc[a] -= 2.0 * ap_peso("Assoc_User")
        except Exception:
            pass
        # curiosidade: números quase nunca votados no recente longo
        fr40 = Counter(numbers[:40]) if numbers else Counter()
        for n in range(37):
            if fr40.get(n, 0) == 0:
                sc[n] -= 0.8 * ap_peso("Curiosidade_Ausente")
        return sc

    def votar_ct(self, sectors, full=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        atr = ct_atraso_scores(sectors)
        out = {s: atr.get(s, 0) * 3.0 * ap_peso("Atraso_Ciclo") for s in CT_SETORES}
        # não força bônus sem atraso forte
        for b in ("CashHunt", "Pachinko", "CrazyBonus"):
            if atr.get(b, 0) < 1.2:
                out[b] *= 0.4
        return out

class IAMomentum(IABase):
    """O que está saindo agora, streaks, eco."""
    nome = "Momentum"
    def votar_roleta(self, numbers, fire=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        sc = {i: 0.0 for i in range(37)}
        trans = padrao_markov(numbers, 50)
        if numbers:
            ult = numbers[0]
            if ult in trans:
                tot = sum(trans[ult].values()) or 1
                for nxt, cnt in trans[ult].most_common(8):
                    sc[nxt] -= (cnt / tot) * 4 * ap_peso("Transicoes")
            for nb in neigh(ult, 2):
                sc[nb] -= 1.2 * ap_peso("Vizinho")
        if fire:
            for f in fire:
                for nb in neigh(f, 2):
                    sc[nb] -= 1.8 * ap_peso("VizinhoDeFogo")
        for a, alvos in ASSOC.items():
            if numbers and numbers[0] == a:
                for t in alvos:
                    if 0 <= t <= 36:
                        sc[t] -= 1.5 * ap_peso("Assoc_Usuario")
        return sc

    def votar_ct(self, sectors, full=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        out = {s: 0.0 for s in CT_SETORES}
        for i, s in enumerate(sectors[:10]):
            if s in out:
                out[s] += (2.5 - i * 0.2) * ap_peso("Recente")
        # 2↔5
        q2 = sum(1 for s in sectors[:10] if s == "2")
        q5 = sum(1 for s in sectors[:10] if s == "5")
        if q2 >= 3:
            out["5"] += 2.0 * ap_peso("Liga_2_5")
            out["2"] += 1.0
        if q5 >= 2:
            out["2"] += 1.8 * ap_peso("Liga_2_5")
        # 10 eco
        p10 = next((i for i, s in enumerate(sectors) if s == "10"), None)
        if p10 is not None and p10 <= 3:
            out["10"] += 2.5 * ap_peso("Repete_10")
        return out

class IAEstrutural(IABase):
    """Finais, colunas, dúzias, paridade, biblioteca clássica."""
    nome = "Estrutural"
    def votar_roleta(self, numbers, fire=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        sc = {i: 0.0 for i in range(37)}
        cd = padrao_coluna_duzia(numbers, 25)
        for n in range(1, 37):
            if (n - 1) % 3 == cd["col_fria"]:
                sc[n] -= 1.4 * ap_peso("Coluna_Fria")
            if (n - 1) // 12 == cd["doz_fria"]:
                sc[n] -= 1.4 * ap_peso("Duzia_Fria")
        pf = padrao_finais(numbers, 25)
        for gname, ends in ENDS_GROUPS.items():
            pts = sum(1 for n in numbers[:22] if n % 10 in ends)
            if 4 <= pts < 8:
                for e in ends:
                    for n in range(e, 37, 10):
                        sc[n] -= 1.2 * ap_peso("Finais")
        par = padrao_paridade(numbers, 25)
        if par["n"] >= 15:
            if par["pares"] >= par["n"] * 0.62:
                for n in range(1, 37):
                    if n % 2 == 1:
                        sc[n] -= 1.3
            elif par["impares"] >= par["n"] * 0.62:
                for n in range(1, 37):
                    if n % 2 == 0:
                        sc[n] -= 1.3
        # frequência baixa
        fr = freq_map(numbers, 40)
        for n in range(37):
            if fr.get(n, 0) == 0:
                sc[n] -= 2.0 * ap_peso("Ausentes")
            elif fr.get(n, 0) <= 1:
                sc[n] -= 1.0
        return sc

    def votar_ct(self, sectors, full=None, ap_peso=None):
        ap_peso = ap_peso or (lambda t: 1.0)
        out = {s: 0.0 for s in CT_SETORES}
        atr = ct_atraso_scores(sectors)
        for s, v in atr.items():
            out[s] += v * 2.0 * ap_peso("Atraso_Ciclo")
        freq = Counter(sectors[:15])
        # equilíbrio: setores sumidos ganham
        for s in CT_SETORES:
            if freq.get(s, 0) == 0:
                out[s] += 1.5
        if full:
            tops = [x.get("top", "") for x in full[:12]]
            for s in CT_SETORES:
                if tops.count(s) >= 2:
                    out[s] += 1.6 * ap_peso("TopSlot")
        return out


def ensemble_roleta(numbers, fire=None, ap_peso=None, n_alvos=7):
    """
    3 IAs votam. Retorna seleção, detalhe por IA, consenso.
    """
    ias = [IAConservadora(), IAMomentum(), IAEstrutural()]
    votos = Counter()
    detalhes = {}
    score_mix = {i: 0.0 for i in range(37)}
    for ia in ias:
        sc = ia.votar_roleta(numbers, fire, ap_peso)
        detalhes[ia.nome] = sc
        ranked = sorted(sc.keys(), key=lambda n: (sc[n], n))[:12]
        for i, n in enumerate(ranked):
            w = (12 - i) / 12.0
            votos[n] += w
            score_mix[n] += sc[n]
    # consenso: aparece no top de ≥2 IAs
    tops = {}
    for nome, sc in detalhes.items():
        tops[nome] = set(sorted(sc.keys(), key=lambda n: (sc[n], n))[:10])
    consenso = []
    for n in range(37):
        cnt = sum(1 for s in tops.values() if n in s)
        if cnt >= 2:
            consenso.append(n)
            score_mix[n] -= 2.0 * cnt
            votos[n] += 0.8 * cnt
    ranked = sorted(range(37), key=lambda n: (score_mix[n], -votos[n], n))
    # tamanho por consenso
    if len(consenso) >= 6:
        n_alvos = min(9, max(n_alvos, 7))
    elif len(consenso) <= 2:
        n_alvos = min(n_alvos, 5)
    sel = []
    for n in consenso + ranked:
        if n not in sel:
            sel.append(n)
        if len(sel) >= n_alvos:
            break
    return {
        "sel": sorted(sel[:n_alvos]),
        "n_alvos": n_alvos,
        "consenso": consenso,
        "votos": votos,
        "score_mix": score_mix,
        "ias": [ia.nome for ia in ias],
        "tops_ia": {k: sorted(list(v))[:8] for k, v in tops.items()},
        "opiniao": (
            f"3 IAs ({', '.join(ia.nome for ia in ias)}). "
            f"Consenso (≥2 IAs): {consenso[:8] or 'fraco'}. "
            f"Top por IA: " + "; ".join(f"{k}={sorted(list(v))[:5]}" for k, v in tops.items())
        ),
    }


def ensemble_ct(sectors, full=None, ap_peso=None):
    ias = [IAConservadora(), IAMomentum(), IAEstrutural()]
    forca = Counter()
    tops = {}
    for ia in ias:
        sc = ia.votar_ct(sectors, full, ap_peso)
        ranked = sorted(sc.keys(), key=lambda s: -sc[s])
        tops[ia.nome] = ranked[:4]
        for i, s in enumerate(ranked):
            forca[s] += sc[s] * ((len(ranked) - i) / len(ranked))
    # ANTI_MONOPOLIO_CT
    q12 = sum(1 for s in sectors[:12] if s in ("1", "2"))
    if q12 >= 8:
        forca["1"] *= 0.5
        forca["2"] *= 0.5
        for s in ("5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"):
            forca[s] += 2.5
    try:
        forca, _u = aplicar_sugestoes_usuario_ct(forca)
    except Exception:
        pass
    try:
        forca, seq_ap = aplicar_seq_ct(forca, sectors)
        if seq_ap:
            _feed(f"SEQ CT influenciou: {seq_ap}", "SEQ")
    except Exception:
        pass
    # limita 1/2
    forca["1"] = forca.get("1", 0) * 0.25
    forca["2"] = forca.get("2", 0) * 0.25
    for b in ("CoinFlip", "CashHunt", "Pachinko", "CrazyBonus", "10"):
        forca[b] = forca.get(b, 0) * 1.35 + 1.5
    ranking = sorted(CT_SETORES, key=lambda s: -forca[s])
    top2 = []
    for s in ranking:
        if len(top2) >= 2:
            break
        if s in ("1", "2") and any(x in ("1", "2") for x in top2):
            continue
        top2.append(s)
    while len(top2) < 2:
        for s in ranking:
            if s not in top2:
                top2.append(s)
                break

    # consenso se ≥2 IAs colocaram no top4
    consenso = []
    for s in CT_SETORES:
        if sum(1 for t in tops.values() if s in t) >= 2:
            consenso.append(s)
    return {
        "top2": top2,
        "forca": forca,
        "ranking": ranking,
        "consenso": consenso,
        "tops_ia": tops,
        "ias": [ia.nome for ia in ias],
        "opiniao": (
            f"3 IAs → TOP2 a SAIR em 5 rodadas: {top2[0]} e {top2[1]}. "
            f"Consenso: {consenso}. "
            + "; ".join(f"{k}:{v}" for k, v in tops.items())
        ),
    }


# ----------------- Enriquecimento extra -----------------
def padrao_repeticao_imediata(numbers, window=20):
    """Conta repetições consecutivas e números que voltam em até 3 giros."""
    rep = Counter()
    for i in range(min(window, len(numbers)-1)):
        if numbers[i] == numbers[i+1]:
            rep[numbers[i]] += 2
        if i+2 < len(numbers) and numbers[i] == numbers[i+2]:
            rep[numbers[i]] += 1
        if i+3 < len(numbers) and numbers[i] == numbers[i+3]:
            rep[numbers[i]] += 0.5
    return rep

def padrao_espelho_roda(n):
    """Número aproximadamente oposto na roda (18 casas)."""
    p = WPOS.get(n)
    if p is None:
        return None
    return WHEEL[(p + 18) % len(WHEEL)]

def padrao_terceiros_roda(numbers, window=20):
    """Distribuição em 3 arcos da roda."""
    arcs = [0, 0, 0]
    for x in numbers[:window]:
        p = WPOS.get(x, 0)
        arcs[min(2, p * 3 // len(WHEEL))] += 1
    frio = arcs.index(min(arcs))
    return {"arcs": arcs, "arco_frio": frio}

def formula_kelly_fracionado(prob_estimada, odd_liquida=35.0, fracao=0.25):
    """Kelly fracionado só como referência de tamanho (não garante edge)."""
    p = max(0.0, min(1.0, prob_estimada))
    q = 1 - p
    b = odd_liquida
    if b <= 0:
        return 0.0
    k = (b * p - q) / b
    return max(0.0, k * fracao)

def formula_prob_cobertura(n_numeros, total=37):
    """Probabilidade de acertar pelo menos 1 em 1 giro com n números."""
    if n_numeros <= 0:
        return 0.0
    return min(1.0, n_numeros / total)

def formula_prob_em_janela(p_um_giro, janela=5):
    """Prob de pelo menos um acerto em N giros independentes."""
    p = max(0.0, min(1.0, p_um_giro))
    return 1.0 - (1.0 - p) ** janela


# ----------------- Busca web de conhecimento (só temas dos 3 jogos) -----------------
import json as _json
import os as _os
import re as _re
import time as _time

_WEB_CACHE_NAME = "biblioteca_web_cache.json"
_LAST_FETCH = [0.0]
_FETCH_INTERVAL = 3600  # no máximo 1x por hora

def _cache_path():
    bases = []
    for p in [
        r"C:\Downloads\teste",
        _os.path.join(_os.path.expanduser("~"), "Downloads", "teste"),
        _os.path.dirname(_os.path.abspath(__file__)),
        _os.getcwd(),
    ]:
        try:
            _os.makedirs(p, exist_ok=True)
            bases.append(p)
        except Exception:
            continue
    return _os.path.join(bases[0] if bases else _os.getcwd(), _WEB_CACHE_NAME)

def carregar_cache_web():
    try:
        path = _cache_path()
        if _os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return {"fontes": [], "formulas": [], "conceitos": [], "atualizado": None}

def salvar_cache_web(data):
    try:
        path = _cache_path()
        data["atualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        return path
    except Exception:
        return None

def _extrair_snippets(texto, limite=8):
    if not texto:
        return []
    # limpa html básico
    t = _re.sub(r"<script[\s\S]*?</script>", " ", texto, flags=_re.I)
    t = _re.sub(r"<style[\s\S]*?</style>", " ", t, flags=_re.I)
    t = _re.sub(r"<[^>]+>", " ", t)
    t = _re.sub(r"\s+", " ", t)
    # frases com palavras-chave dos jogos
    keys = [
        "roulette", "roleta", "probability", "probabilidade", "martingale",
        "neighbor", "vizinho", "sector", "wheel", "markov", "frequency",
        "crazy time", "lightning", "multiplier", "house edge", "variance",
        "law of large numbers", "regression", "overdue", "hot number", "cold number",
    ]
    frases = _re.split(r"(?<=[.!?])\s+", t)
    out = []
    for fr in frases:
        low = fr.lower()
        if any(k in low for k in keys) and 40 <= len(fr) <= 280:
            out.append(fr.strip())
        if len(out) >= limite:
            break
    return out

def buscar_conhecimento_web(forcar=False):
    _feed("Iniciando busca web de conhecimento (roleta/CT/fórmulas)", "WEB")
    """
    Busca pública relacionada a roleta / Crazy Time / Lightning.
    Resultado vai para cache local; as IAs usam como conceitos auxiliares.
    Não inventa edge — só material de referência.
    """
    agora = _time.time()
    if not forcar and agora - _LAST_FETCH[0] < _FETCH_INTERVAL:
        return carregar_cache_web()
    cache = carregar_cache_web()
    try:
        import requests
    except Exception:
        return cache

    urls = [
        "https://en.wikipedia.org/wiki/Roulette",
        "https://en.wikipedia.org/wiki/Martingale_(betting_system)",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Roulette",
        "https://en.wikipedia.org/api/rest_v1/page/summary/Law_of_large_numbers",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; GameLabBot/1.0; +local-research)",
        "Accept": "text/html,application/json",
    }
    novos_conceitos = list(cache.get("conceitos") or [])
    fontes = list(cache.get("fontes") or [])
    formulas = list(cache.get("formulas") or [])

    # fórmulas clássicas sempre disponíveis
    base_formulas = [
        {"nome": "p_cobertura", "expr": "n/37", "uso": "prob de acerto em 1 giro com n números"},
        {"nome": "p_janela", "expr": "1-(1-p)^k", "uso": "pelo menos 1 acerto em k giros"},
        {"nome": "house_edge_eu", "expr": "1/37 ≈ 2.7%", "uso": "edge da roleta europeia"},
        {"nome": "atraso_esperado", "expr": "gap/(37)", "uso": "razão de atraso vs média"},
    ]
    for f in base_formulas:
        if f not in formulas and f["nome"] not in [x.get("nome") for x in formulas]:
            formulas.append(f)

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            ctype = r.headers.get("content-type", "")
            if "json" in ctype:
                data = r.json()
                extract = data.get("extract") or data.get("description") or ""
                for sn in _extrair_snippets(extract, 4):
                    if sn not in novos_conceitos:
                        novos_conceitos.append(sn)
            else:
                for sn in _extrair_snippets(r.text, 5):
                    if sn not in novos_conceitos:
                        novos_conceitos.append(sn)
            if url not in fontes:
                fontes.append(url)
        except Exception:
            continue

    # limita tamanho
    cache = {
        "fontes": fontes[-20:],
        "conceitos": novos_conceitos[-60:],
        "formulas": formulas[-30:],
        "atualizado": None,
    }
    salvar_cache_web(cache)
    _LAST_FETCH[0] = agora
    _feed(f"Busca web ok — {len(cache.get('conceitos') or [])} conceitos, {len(cache.get('formulas') or [])} fórmulas", "WEB")
    return cache

def conhecimento_para_ias():
    """Resumo curto para as IAs aplicarem com peso baixo (referência)."""
    cache = carregar_cache_web()
    # tenta atualizar em background interval
    try:
        buscar_conhecimento_web(forcar=False)
        cache = carregar_cache_web()
    except Exception:
        pass
    return {
        "n_conceitos": len(cache.get("conceitos") or []),
        "n_formulas": len(cache.get("formulas") or []),
        "formulas": cache.get("formulas") or [],
        "conceitos_sample": (cache.get("conceitos") or [])[:5],
        "atualizado": cache.get("atualizado"),
    }

def aplicar_conhecimento_web_roleta(score_dict):
    """
    Ajuste leve com base em fórmulas clássicas (sem fingir edge).
    score_dict: menor = melhor (como nos motores).
    """
    info = conhecimento_para_ias()
    # usa p_cobertura só como meta de tamanho — não altera ranking agressivamente
    return score_dict, info


# ----------------- Memória compartilhada entre apps e 3 IAs -----------------
_SHARED_NAME = "memoria_compartilhada_ias.json"

def _shared_path():
    for d in [
        r"C:\Downloads\teste",
        _os.path.join(_os.path.expanduser("~"), "Downloads", "teste"),
        _os.path.dirname(_os.path.abspath(__file__)),
        _os.getcwd(),
    ]:
        try:
            _os.makedirs(d, exist_ok=True)
            return _os.path.join(d, _SHARED_NAME)
        except Exception:
            continue
    return _SHARED_NAME

def carregar_memoria_compartilhada():
    try:
        p = _shared_path()
        if _os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return {
        "miss_seguidos": 0,
        "hit_seguidos": 0,
        "teorias_ruins": {},
        "teorias_boas": {},
        "ultimos_resultados": [],
        "vereditos": [],
        "aprendizados": [],
    }

def salvar_memoria_compartilhada(data):
    try:
        p = _shared_path()
        data["atualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
        return p
    except Exception:
        return None

def registrar_outcome_compartilhado(ok, saiu, alvos, tecs=None, app="roleta", anterior=None):
    _feed(f"{app}: {'ACERTO' if ok else 'ERRO'} saiu={saiu} alvos={alvos} tecs={list(tecs or [])[:5]}", "APRENDIZADO")
    try:
        jogo = "crazytime" if "crazy" in str(app).lower() else "roleta"
        if anterior is not None:
            reforcar_sequencia_acerto(anterior, saiu, jogo, ok=ok)
    except Exception:
        pass
    """Todas as ferramentas alimentam a mesma memória."""
    mem = carregar_memoria_compartilhada()
    if ok:
        mem["hit_seguidos"] = int(mem.get("hit_seguidos", 0)) + 1
        mem["miss_seguidos"] = 0
        for t in (tecs or []):
            bag = mem.setdefault("teorias_boas", {})
            bag[str(t)] = int(bag.get(str(t), 0)) + 1
    else:
        mem["miss_seguidos"] = int(mem.get("miss_seguidos", 0)) + 1
        mem["hit_seguidos"] = 0
        for t in (tecs or []):
            bag = mem.setdefault("teorias_ruins", {})
            bag[str(t)] = int(bag.get(str(t), 0)) + 1
    ult = mem.setdefault("ultimos_resultados", [])
    ult.insert(0, {"saiu": saiu, "ok": ok, "alvos": alvos, "app": app})
    mem["ultimos_resultados"] = ult[:80]
    # se muitos misses, marca modo migracao
    if mem["miss_seguidos"] >= 4:
        mem["modo"] = "migrar_teoria"
        mem.setdefault("aprendizados", []).append(
            f"{datetime.now().strftime('%H:%M')} miss_seguidos={mem['miss_seguidos']} → migrar teoria / olhar mesa agora"
        )
    elif mem["hit_seguidos"] >= 2:
        mem["modo"] = "reforcar"
    else:
        mem["modo"] = "normal"
    mem["aprendizados"] = (mem.get("aprendizados") or [])[-40:]
    salvar_memoria_compartilhada(mem)
    return mem

def deve_migrar_teoria():
    mem = carregar_memoria_compartilhada()
    return mem.get("modo") == "migrar_teoria" or int(mem.get("miss_seguidos", 0)) >= 4

def peso_tecnica_compartilhado(nome, base=1.0):
    mem = carregar_memoria_compartilhada()
    boas = int((mem.get("teorias_boas") or {}).get(str(nome), 0))
    ruins = int((mem.get("teorias_ruins") or {}).get(str(nome), 0))
    tot = boas + ruins
    if tot < 5:
        return base
    taxa = boas / tot
    # técnicas ruins perdem peso; boas ganham
    return max(0.35, min(1.8, base * (0.5 + taxa)))

def veredito_3_ias_roleta(numbers, fire=None):
    _feed("3 IAs consultando biblioteca + mesa (roleta)", "CONSULTA")
    try:
        if numbers:
            registrar_contexto_sequencial(numbers[:50], "roleta")
            _feed(resumo_sequencias("roleta", numbers[0]), "SEQ")
    except Exception:
        pass
    """Cada IA opina; depois consenso e veredito final."""
    mem = carregar_memoria_compartilhada()
    migrar = deve_migrar_teoria()

    def peso(t):
        return peso_tecnica_compartilhado(t, 1.0)

    ias = [IAConservadora(), IAMomentum(), IAEstrutural()]
    opinioes = {}
    tops = {}
    score_mix = {i: 0.0 for i in range(37)}
    votos = Counter()

    for ia in ias:
        sc = ia.votar_roleta(numbers, fire, peso)
        # se migrar: invert soft bias — penaliza top antigo saturado
        if migrar:
            recent = set(numbers[:8])
            for n in recent:
                sc[n] = sc.get(n, 0) + 4.0  # piora recente (menor=melhor, então +)
            isol = padrao_isolamento(numbers, 30)
            for n in isol[:10]:
                sc[n] = sc.get(n, 0) - 3.0
        ranked = sorted(range(37), key=lambda n: (sc.get(n, 0), n))[:10]
        tops[ia.nome] = ranked
        opinioes[ia.nome] = {
            "top": ranked[:6],
            "comentario": (
                f"{ia.nome}: prioriza {ranked[:5]}"
                + (" | MODO MIGRAÇÃO (muitos erros)" if migrar else "")
            ),
        }
        for i, n in enumerate(ranked):
            votos[n] += (10 - i) / 10.0
            score_mix[n] += sc.get(n, 0)

    consenso = [n for n in range(37) if sum(1 for t in tops.values() if n in t[:8]) >= 2]
    # olhar mesa AGORA: se número saiu 2x nos últimos 6, não priorizar
    fr6 = Counter(numbers[:6])
    for n, c in fr6.items():
        if c >= 2:
            score_mix[n] += 5.0

    try:
        score_mix, _user_ap = aplicar_sugestoes_usuario_roleta(score_mix)
    except Exception:
        pass
    try:
        score_mix, seq_ap = aplicar_seq_roleta(score_mix, numbers)
        for n in seq_ap:
            votos[n] += 1.2
        if seq_ap:
            _feed(f"SEQ influenciou números: {seq_ap[:8]}", "SEQ")
    except Exception:
        seq_ap = []
    # alimenta com caçadora
    try:
        for n in CACADORA.nums_sugeridos(8):
            score_mix[n] -= 2.0
            votos[n] += 1.2
    except Exception:
        pass
    ranked = sorted(range(37), key=lambda n: (score_mix[n], -votos[n], n))

    # CORREÇÃO LOGS: migração NÃO deve cortar para 5 e grudar.
    # Problema real: consenso tinha o número que saiu, mas seleção truncava.
    # Regra nova:
    #  1) entra TODO número com voto de ≥2 IAs (consenso)
    #  2) garante ≥2 exclusivos do Momentum (anti-Conservadora)
    #  3) garante ≥2 isolados (fora dos últimos 15)
    #  4) em migração AMPLIA (8–10), não reduz
    try:
        meta = meta_por_jogo("lightning")
        base_n = int(meta.n_alvos_recomendado(8 if migrar else 7))
    except Exception:
        base_n = 9 if migrar else 7
    n_alvos = max(7, min(11, base_n))
    if migrar:
        n_alvos = max(n_alvos, 9)

    recent15 = set(numbers[:15])
    recent6 = set(numbers[:6])
    mom = list(tops.get("Momentum") or [])
    cons = list(tops.get("Conservadora") or [])
    est = list(tops.get("Estrutural") or [])

    sel = []
    # 1) consenso completo (não truncar cedo)
    for n in sorted(consenso, key=lambda x: (score_mix.get(x, 0), -votos.get(x, 0))):
        if n not in sel:
            sel.append(n)

    # 2) exclusivos Momentum (aparecem no top Momentum e não no top Conservadora)
    exclusivos_mom = [n for n in mom[:8] if n not in cons[:5]]
    for n in exclusivos_mom:
        if n not in sel:
            sel.append(n)
        if sum(1 for x in sel if x in exclusivos_mom) >= 2 and len(sel) >= n_alvos:
            break

    # 3) isolados (gap alto)
    isol = []
    for n in range(37):
        if n in recent15:
            continue
        g = 40
        for i, x in enumerate(numbers[:40]):
            if x == n:
                g = i
                break
        isol.append((g, n))
    isol.sort(reverse=True)
    n_iso = 0
    for g, n in isol:
        if n not in sel:
            sel.append(n)
            n_iso += 1
        if n_iso >= 3:
            break

    # 4) completa por score até n_alvos
    for n in ranked:
        if n in recent6 and len(sel) >= max(5, n_alvos - 2):
            continue
        if n not in sel:
            sel.append(n)
        if len(sel) >= n_alvos:
            break
    sel = sel[:n_alvos]

    # veredito textual
    linhas = [opinioes[k]["comentario"] for k in opinioes]
    if consenso:
        veredito = (
            f"VEREDITO: consenso {consenso[:10]} → sel {sel} "
            f"(mom_excl {exclusivos_mom[:3]} | isol { [n for g,n in isol[:3]] })"
        )
    else:
        veredito = f"VEREDITO: consenso fraco → sel {sel}"
    if migrar:
        veredito = "MIGRAÇÃO (ampliada, não cortada). " + veredito

    mem.setdefault("vereditos", []).insert(0, {
        "veredito": veredito,
        "sel": list(sel),
        "consenso": consenso,
        "migrar": migrar,
    })
    mem["vereditos"] = mem["vereditos"][:30]
    salvar_memoria_compartilhada(mem)

    _feed(veredito, "VEREDITO")
    for nome, op in opinioes.items():
        _feed(str(op.get("comentario", op))[:180] if isinstance(op, dict) else f"{nome}: {op}", "VOTO")
    return {
        "sel": list(sel),
        "n_alvos": n_alvos,
        "consenso": consenso,
        "opinioes": opinioes,
        "veredito": veredito,
        "migrar": migrar,
        "miss_seguidos": int(mem.get("miss_seguidos", 0)),
        "opiniao": veredito + " | " + " / ".join(linhas),
        "tops_ia": tops,
    }


def veredito_3_ias_ct(sectors, full=None):
    _feed("3 IAs consultando biblioteca + mesa (Crazy Time)", "CONSULTA")
    try:
        if sectors:
            registrar_contexto_sequencial(sectors[:50], "crazytime")
            _feed(resumo_sequencias("crazytime", sectors[0]), "SEQ")
    except Exception:
        pass
    mem = carregar_memoria_compartilhada()
    migrar = deve_migrar_teoria()

    def peso(t):
        return peso_tecnica_compartilhado(t, 1.0)

    ias = [IAConservadora(), IAMomentum(), IAEstrutural()]
    forca = Counter()
    opinioes = {}
    tops = {}
    for ia in ias:
        sc = ia.votar_ct(sectors, full, peso)
        if migrar:
            # foge do que está saturado nos últimos 5
            sat = Counter(sectors[:5])
            for s, c in sat.items():
                if s in sc and c >= 2:
                    sc[s] *= 0.4
            atr = ct_atraso_scores(sectors)
            for s, v in atr.items():
                if v >= 1.5:
                    sc[s] = sc.get(s, 0) + 2.5
        ranked = sorted(sc.keys(), key=lambda s: -sc[s])
        tops[ia.nome] = ranked[:4]
        opinioes[ia.nome] = f"{ia.nome}: {ranked[:3]}"
        for i, s in enumerate(ranked):
            forca[s] += sc[s] * ((len(ranked) - i) / max(1, len(ranked)))
    # ANTI_MONOPOLIO_CT
    q12 = sum(1 for s in sectors[:12] if s in ("1", "2"))
    if q12 >= 8:
        forca["1"] *= 0.5
        forca["2"] *= 0.5
        for s in ("5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"):
            forca[s] += 2.5
    try:
        forca, _u = aplicar_sugestoes_usuario_ct(forca)
    except Exception:
        pass
    try:
        forca, seq_ap = aplicar_seq_ct(forca, sectors)
        if seq_ap:
            _feed(f"SEQ CT influenciou: {seq_ap}", "SEQ")
    except Exception:
        pass
    # limita 1/2
    forca["1"] = forca.get("1", 0) * 0.25
    forca["2"] = forca.get("2", 0) * 0.25
    for b in ("CoinFlip", "CashHunt", "Pachinko", "CrazyBonus", "10"):
        forca[b] = forca.get(b, 0) * 1.35 + 1.5
    ranking = sorted(CT_SETORES, key=lambda s: -forca[s])
    top2 = []
    for s in ranking:
        if len(top2) >= 2:
            break
        if s in ("1", "2") and any(x in ("1", "2") for x in top2):
            continue
        top2.append(s)
    while len(top2) < 2:
        for s in ranking:
            if s not in top2:
                top2.append(s)
                break

    consenso = [s for s in CT_SETORES if sum(1 for t in tops.values() if s in t) >= 2]
    veredito = f"VEREDITO CT próximas 5: {top2[0]} e {top2[1]} | consenso {consenso}"
    if migrar:
        veredito = "MIGRAÇÃO. " + veredito
    _feed(veredito, "VEREDITO")
    for nome, op in opinioes.items():
        _feed(f"{nome}: {op}", "VOTO")
    return {
        "top2": top2,
        "ranking": ranking,
        "forca": forca,
        "consenso": consenso,
        "opinioes": opinioes,
        "veredito": veredito,
        "opiniao": veredito + " | " + " / ".join(opinioes.values()),
        "tops_ia": tops,
        "migrar": migrar,
    }


# ----------------- Feed ao vivo da biblioteca -----------------
_FEED = []
_FEED_MAX = 80

def _feed(msg, tipo="info"):
    try:
        ts = datetime.now().strftime("%H:%M:%S")
        _FEED.insert(0, {"ts": ts, "tipo": tipo, "msg": str(msg)[:240]})
        del _FEED[_FEED_MAX:]
    except Exception:
        pass

def feed_texto(limite=25):
    if not _FEED:
        return "Biblioteca quieta — aguardando ciclo das IAs..."
    linhas = []
    for e in _FEED[:limite]:
        linhas.append(f"[{e['ts']}] ({e['tipo']}) {e['msg']}")
    return "\n".join(linhas)

def feed_status_completo():
    """Texto rico para o painel Biblioteca ao vivo."""
    mem = carregar_memoria_compartilhada()
    web = conhecimento_para_ias()
    linhas = []
    linhas.append("════ BIBLIOTECA AO VIVO ════")
    linhas.append(f"Atualização: {datetime.now().strftime('%H:%M:%S')}")
    linhas.append("")
    linhas.append("── INTERNET / CONHECIMENTO ──")
    linhas.append(f"Conceitos em cache: {web.get('n_conceitos', 0)}")
    linhas.append(f"Fórmulas em cache: {web.get('n_formulas', 0)}")
    linhas.append(f"Última busca web: {web.get('atualizado') or 'ainda não'}")
    for f in (web.get("formulas") or [])[:4]:
        if isinstance(f, dict):
            linhas.append(f"  fórmula: {f.get('nome')} = {f.get('expr')} ({f.get('uso','')})")
    for s in (web.get("conceitos_sample") or [])[:2]:
        linhas.append(f"  conceito: {str(s)[:120]}")
    linhas.append("")
    linhas.append("── MEMÓRIA COMPARTILHADA (3 apps) ──")
    linhas.append(f"Miss seguidos: {mem.get('miss_seguidos', 0)} | Hit seguidos: {mem.get('hit_seguidos', 0)}")
    linhas.append(f"Modo: {mem.get('modo', 'normal')}")
    boas = mem.get("teorias_boas") or {}
    ruins = mem.get("teorias_ruins") or {}
    if boas:
        topb = sorted(boas.items(), key=lambda x: -x[1])[:4]
        linhas.append("Técnicas que mais acertam: " + ", ".join(f"{k}({v})" for k, v in topb))
    if ruins:
        topr = sorted(ruins.items(), key=lambda x: -x[1])[:4]
        linhas.append("Técnicas que mais erram: " + ", ".join(f"{k}({v})" for k, v in topr))
    aprend = mem.get("aprendizados") or []
    if aprend:
        linhas.append("Últimos aprendizados:")
        for a in aprend[-3:]:
            linhas.append(f"  • {a}")
    linhas.append("")
    linhas.append("── ANTES / DEPOIS (SEQUÊNCIAS) ──")
    try:
        linhas.append(resumo_sequencias("roleta"))
        linhas.append(resumo_sequencias("crazytime"))
        sr = carregar_sequencias()
        # amostra de um símbolo frequente
        for jogo in ("roleta", "crazytime"):
            bag = sr.get(jogo) or {}
            if bag:
                chave = max(bag.keys(), key=lambda k: int(bag[k].get("n", 0)))
                linhas.append(f"{jogo} exemplo [{chave}]: depois={top_depois(chave, jogo, 4)} antes={top_antes(chave, jogo, 3)}")
    except Exception as e:
        linhas.append(f"seq: {e}")
    linhas.append("")
    linhas.append("── DIÁLOGO / SUGESTÕES DO USUÁRIO ──")
    try:
        linhas.append(texto_dialogo_recente(6))
    except Exception:
        pass
    linhas.append("")
    linhas.append("── ATIVIDADE EM TEMPO REAL ──")
    linhas.append(feed_texto(18))
    return "\n".join(linhas)


# ----------------- Antes / Depois (base de conhecimento sequencial) -----------------
_SEQ_FILE = "base_sequencias.json"

def _seq_path():
    for d in [
        r"C:\Downloads\teste",
        _os.path.join(_os.path.expanduser("~"), "Downloads", "teste"),
        _os.path.dirname(_os.path.abspath(__file__)),
        _os.getcwd(),
    ]:
        try:
            _os.makedirs(d, exist_ok=True)
            return _os.path.join(d, _SEQ_FILE)
        except Exception:
            continue
    return _SEQ_FILE

def carregar_sequencias():
    try:
        p = _seq_path()
        if _os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return {"roleta": {}, "crazytime": {}, "atualizado": None}

def salvar_sequencias(data):
    try:
        data["atualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(_seq_path(), "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _bump(bag, chave, alvo, peso=1):
    """Incrementa contagem alvo sob chave (string)."""
    node = bag.setdefault(str(chave), {"antes": {}, "depois": {}, "n": 0})
    node["n"] = int(node.get("n", 0)) + 1
    sub = node.setdefault(alvo, {})
    # alvo is 'antes' or handled by caller
    return node

def registrar_contexto_sequencial(historico, jogo="roleta"):
    """
    historico: lista do mais recente para o mais antigo (index 0 = último que saiu).
    Para cada ocorrência, registra o que veio ANTES (mais antigo na sequência temporal
    imediatamente anterior) e o que veio DEPOIS (o seguinte no tempo = índice menor).

    Ex: hist = [5, 20, 1, 14]  → saiu 5 agora; antes do 5 foi 20; depois do 20 foi 5.
    Aprende pares (X → Y) de forma cumulativa.
    """
    if not historico or len(historico) < 2:
        return
    data = carregar_sequencias()
    bag = data.setdefault(jogo, {})
    # Transição: historico[i+1] saiu, depois veio historico[i]
    # "antes" de historico[i] = historico[i+1]
    # "depois" de historico[i+1] = historico[i]
    pares_novos = []
    for i in range(min(len(historico) - 1, 40)):
        depois = historico[i]      # mais recente neste par
        antes = historico[i + 1]   # imediatamente anterior
        ka, kd = str(antes), str(depois)
        # depois de `antes` veio `depois`
        na = bag.setdefault(ka, {"antes": {}, "depois": {}, "n": 0})
        na["n"] = int(na.get("n", 0)) + 1
        na["depois"][kd] = int(na["depois"].get(kd, 0)) + 1
        # antes de `depois` veio `antes`
        nd = bag.setdefault(kd, {"antes": {}, "depois": {}, "n": 0})
        nd["n"] = int(nd.get("n", 0)) + 1
        nd["antes"][ka] = int(nd["antes"].get(ka, 0)) + 1
        pares_novos.append(f"{ka}→{kd}")
    salvar_sequencias(data)
    if pares_novos:
        _feed(f"SEQ {jogo}: aprendeu {len(pares_novos)} pares (ex: {', '.join(pares_novos[:4])})", "SEQ")
    return data

def top_depois(valor, jogo="roleta", k=6):
    data = carregar_sequencias()
    node = (data.get(jogo) or {}).get(str(valor)) or {}
    depois = node.get("depois") or {}
    return sorted(depois.items(), key=lambda x: -int(x[1]))[:k]

def top_antes(valor, jogo="roleta", k=6):
    data = carregar_sequencias()
    node = (data.get(jogo) or {}).get(str(valor)) or {}
    antes = node.get("antes") or {}
    return sorted(antes.items(), key=lambda x: -int(x[1]))[:k]

def prever_por_sequencia(ultimo, jogo="roleta", k=8):
    """
    Dado o último resultado, sugere os que mais costumam VIR DEPOIS dele.
    Combina memória persistida + reforço.
    """
    tops = top_depois(ultimo, jogo, k=k)
    out = []
    for val, cnt in tops:
        cnt = int(cnt)
        # score cresce com evidência, mas com saturação
        score = min(6.0, 1.2 + (cnt ** 0.55))
        out.append((val, score, cnt))
    _feed(
        f"SEQ previsão após {ultimo}: " + ", ".join(f"{v}(n={c})" for v, _, c in out[:5]),
        "SEQ",
    )
    return out

def reforcar_sequencia_acerto(anterior, saiu, jogo="roleta", ok=True):
    """Quando a previsão acerta/erra o 'depois', reforça ou enfraquece o par."""
    data = carregar_sequencias()
    bag = data.setdefault(jogo, {})
    ka, kd = str(anterior), str(saiu)
    na = bag.setdefault(ka, {"antes": {}, "depois": {}, "n": 0, "acertos_depois": {}, "erros_depois": {}})
    if ok:
        na.setdefault("acertos_depois", {})[kd] = int(na.get("acertos_depois", {}).get(kd, 0)) + 1
        na.setdefault("depois", {})[kd] = int(na.get("depois", {}).get(kd, 0)) + 2  # reforço extra
        _feed(f"SEQ reforço ACERTO {ka}→{kd}", "SEQ")
    else:
        na.setdefault("erros_depois", {})[kd] = int(na.get("erros_depois", {}).get(kd, 0)) + 1
        # não apaga o par, só reduz um pouco se muito erro
        if int(na.get("depois", {}).get(kd, 0)) > 1:
            na["depois"][kd] = max(1, int(na["depois"][kd]) - 1)
        _feed(f"SEQ ajuste ERRO par {ka}→{kd}", "SEQ")
    salvar_sequencias(data)

def aplicar_seq_roleta(score_dict, numbers):
    """Ajusta scores da roleta (menor=melhor) com base no que costuma vir DEPOIS do último."""
    if not numbers:
        return score_dict, []
    ultimo = numbers[0]
    # sempre alimenta a base com o histórico atual
    registrar_contexto_sequencial(numbers[:50], "roleta")
    prevs = prever_por_sequencia(ultimo, "roleta", k=10)
    aplicados = []
    for val, sc, cnt in prevs:
        try:
            n = int(val)
        except Exception:
            continue
        if 0 <= n <= 36:
            # evidência mínima
            if cnt >= 2:
                score_dict[n] = score_dict.get(n, 0.0) - sc
                aplicados.append(n)
    # também: o que costuma vir ANTES do último ajuda a entender o ciclo (peso menor)
    for val, cnt in top_antes(ultimo, "roleta", k=4):
        try:
            n = int(val)
            if 0 <= n <= 36 and int(cnt) >= 3:
                score_dict[n] = score_dict.get(n, 0.0) - 0.4
        except Exception:
            pass
    return score_dict, aplicados

def aplicar_seq_ct(forca_dict, sectors):
    """Ajusta forças CT (maior=melhor) com o que costuma vir depois do último setor."""
    if not sectors:
        return forca_dict, []
    registrar_contexto_sequencial(sectors[:50], "crazytime")
    ultimo = sectors[0]
    prevs = prever_por_sequencia(ultimo, "crazytime", k=8)
    aplicados = []
    for val, sc, cnt in prevs:
        if val in forca_dict or val in CT_SETORES:
            if cnt >= 2:
                forca_dict[val] = forca_dict.get(val, 0.0) + sc
                aplicados.append(val)
    return forca_dict, aplicados

def resumo_sequencias(jogo="roleta", ultimo=None):
    data = carregar_sequencias()
    bag = data.get(jogo) or {}
    linhas = [f"Base sequencial {jogo}: {len(bag)} símbolos | atualizado {data.get('atualizado')}"]
    if ultimo is not None:
        linhas.append(f"Após {ultimo} costuma vir: " + ", ".join(f"{v}×{c}" for v, c in top_depois(ultimo, jogo, 6)))
        linhas.append(f"Antes de {ultimo} costuma: " + ", ".join(f"{v}×{c}" for v, c in top_antes(ultimo, jogo, 5)))
    return " | ".join(linhas)


# ----------------- Sugestões e diálogo do usuário com as IAs -----------------
_USER_FILE = "dialogo_usuario_ias.json"

def _user_path():
    for d in [
        r"C:\Downloads\teste",
        _os.path.join(_os.path.expanduser("~"), "Downloads", "teste"),
        _os.path.dirname(_os.path.abspath(__file__)),
        _os.getcwd(),
    ]:
        try:
            _os.makedirs(d, exist_ok=True)
            return _os.path.join(d, _USER_FILE)
        except Exception:
            continue
    return _USER_FILE

def carregar_dialogo():
    try:
        p = _user_path()
        if _os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return {"sugestoes": [], "mensagens": [], "numeros_sugeridos": {}, "aprendizados_user": []}

def salvar_dialogo(data):
    try:
        data["atualizado"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        with open(_user_path(), "w", encoding="utf-8") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def registrar_sugestao_usuario(texto, numeros=None, app="geral"):
    """
    Usuário sugere possibilidades. IAs NÃO são obrigadas a acatar,
    mas a info entra no aprendizado e pode influenciar com peso baixo.
    """
    data = carregar_dialogo()
    item = {
        "ts": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "app": app,
        "texto": str(texto)[:400],
        "numeros": list(numeros or []),
        "usada": False,
    }
    data.setdefault("sugestoes", []).insert(0, item)
    data["sugestoes"] = data["sugestoes"][:80]
    for n in (numeros or []):
        k = str(n)
        data.setdefault("numeros_sugeridos", {})[k] = int(data["numeros_sugeridos"].get(k, 0)) + 1
    data.setdefault("aprendizados_user", []).append(
        f"{item['ts']} sugestão [{app}]: {texto[:120]} nums={numeros}"
    )
    data["aprendizados_user"] = data["aprendizados_user"][-60:]
    salvar_dialogo(data)
    _feed(f"USER sugestão ({app}): {texto[:100]} | nums={numeros}", "USER")
    return item

def registrar_mensagem_usuario(texto, app="geral"):
    data = carregar_dialogo()
    msg = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "de": "voce",
        "app": app,
        "texto": str(texto)[:500],
    }
    data.setdefault("mensagens", []).insert(0, msg)
    data["mensagens"] = data["mensagens"][:100]
    salvar_dialogo(data)
    _feed(f"USER disse: {texto[:120]}", "USER")
    return msg

def resposta_ias_dialogo(texto, app="geral", contexto=None):
    """
    Resposta simples das 3 IAs ao diálogo — não é chat GPT,
    usa estado da biblioteca + sugestões.
    """
    contexto = contexto or {}
    data = carregar_dialogo()
    mem = carregar_memoria_compartilhada()
    txt = (texto or "").lower()
    partes = []
    partes.append(f"[Conservadora] Li sua mensagem. Modo atual={mem.get('modo','normal')}, miss seguidos={mem.get('miss_seguidos',0)}.")
    if any(k in txt for k in ("1 e 2", "só 1", "sempre 1", "travad")):
        partes.append("[Momentum] Vou reduzir monopólio de 1/2 e olhar atrasados/sequências.")
    if any(k in txt for k in ("antes", "depois", "sequên", "historico", "histórico")):
        partes.append("[Estrutural] Base antes/depois ativa — reforçando pares do histórico.")
    if any(k in txt for k in ("bonus", "bônus", "cash", "pachinko", "10")):
        partes.append("[Momentum] Anotei foco em bônus/10 — uso se o atraso e a sequência confirmarem.")
    if any(k in txt for k in ("fogo", "lightning", "multi")):
        partes.append("[Conservadora] Multiplicadores: priorizo vizinhos e não só o número em fogo.")
    # números citados
    import re as _re
    nums = [int(x) for x in _re.findall(r"\b([0-9]|[12][0-9]|3[0-6])\b", texto or "")]
    nums = [n for n in nums if 0 <= n <= 36]
    if nums:
        partes.append(f"[Consenso] Números que você citou {nums}: entram como sugestão leve (não obrigatória).")
        registrar_sugestao_usuario(texto, nums, app)
    else:
        registrar_sugestao_usuario(texto, [], app)
    if mem.get("modo") == "migrar_teoria":
        partes.append("[Veredito] Estamos em MIGRAÇÃO — sua ideia ajuda a sair do padrão que está errando.")
    else:
        partes.append("[Veredito] Vamos considerar no próximo ciclo se cruzar com consenso; senão fica só no aprendizado.")
    resp = " | ".join(partes)
    data = carregar_dialogo()
    data.setdefault("mensagens", []).insert(0, {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "de": "ias",
        "app": app,
        "texto": resp[:600],
    })
    data["mensagens"] = data["mensagens"][:100]
    salvar_dialogo(data)
    _feed(f"IAs responderam: {resp[:140]}", "DIALOGO")
    return resp

def aplicar_sugestoes_usuario_roleta(score_dict, peso=0.9):
    """Influência leve — não obriga."""
    data = carregar_dialogo()
    usados = []
    for n, cnt in (data.get("numeros_sugeridos") or {}).items():
        try:
            ni = int(n)
            if 0 <= ni <= 36 and int(cnt) >= 1:
                score_dict[ni] = score_dict.get(ni, 0.0) - peso * min(2.0, 0.4 * int(cnt))
                usados.append(ni)
        except Exception:
            pass
    # últimas sugestões textuais recentes (1h mental — só top 5)
    for s in (data.get("sugestoes") or [])[:5]:
        for n in s.get("numeros") or []:
            try:
                ni = int(n)
                if 0 <= ni <= 36:
                    score_dict[ni] = score_dict.get(ni, 0.0) - peso
                    if ni not in usados:
                        usados.append(ni)
            except Exception:
                pass
    if usados:
        _feed(f"Sugestões do usuário consideradas (leve): {usados[:10]}", "USER")
    return score_dict, usados

def aplicar_sugestoes_usuario_ct(forca_dict, peso=1.0):
    data = carregar_dialogo()
    usados = []
    mapa = {"1": "1", "2": "2", "5": "5", "10": "10",
            "cash": "CashHunt", "hunt": "CashHunt", "coin": "CoinFlip",
            "pachinko": "Pachinko", "crazy": "CrazyBonus", "bonus": "CrazyBonus"}
    for s in (data.get("sugestoes") or [])[:8]:
        t = (s.get("texto") or "").lower()
        for k, alvo in mapa.items():
            if k in t and alvo in forca_dict or alvo in CT_SETORES:
                forca_dict[alvo] = forca_dict.get(alvo, 0.0) + peso
                usados.append(alvo)
    if usados:
        _feed(f"Sugestões user CT (leve): {usados}", "USER")
    return forca_dict, usados

def texto_dialogo_recente(n=12):
    data = carregar_dialogo()
    linhas = []
    for m in (data.get("mensagens") or [])[:n]:
        quem = "Você" if m.get("de") == "voce" else "IAs"
        linhas.append(f"[{m.get('ts')}] {quem}: {m.get('texto','')}")
    return "\n".join(linhas) if linhas else "Nenhum diálogo ainda. Escreva abaixo."


# ----------------- IA Caçadora de Padrões (sempre ativa) -----------------
class CacadoraPadroes:
    """
    IA que fica varrendo o histórico, NOMEIA padrões e alimenta a memória
    compartilhada para as outras 3 IAs usarem.
    """
    def __init__(self):
        self.status = "iniciando..."
        self.trabalhando = False
        self.ultimo_ciclo = None
        self.padroes_vivos = []  # lista de dicts nomeados
        self.log_trabalho = []
        self.ciclos = 0

    def _nomear(self, tipo, detalhe):
        ts = datetime.now().strftime("%H:%M:%S")
        nome = f"{tipo}_{detalhe}"
        return nome, ts

    def analisar(self, numbers, fire=None):
        """Varre a roleta e devolve padrões nomeados + status de trabalho."""
        self.trabalhando = True
        self.ciclos += 1
        self.status = f"ciclo {self.ciclos}: varrendo histórico..."
        encontrados = []
        n = list(numbers or [])
        if len(n) < 5:
            self.status = "aguardando mais resultados..."
            self.trabalhando = False
            return []

        # 1) Sequência de finais
        fins = [x % 10 for x in n[:12]]
        from collections import Counter
        cf = Counter(fins)
        for end, cnt in cf.most_common(3):
            if cnt >= 4:
                nome, ts = self._nomear("FINAL", f"{end}x{cnt}")
                encontrados.append({
                    "nome": nome, "tipo": "final", "forca": cnt,
                    "nums": [x for x in range(end, 37, 10)],
                    "desc": f"Final {end} apareceu {cnt}x nos últimos 12",
                    "ts": ts,
                })

        # 2) Grupo de finais do usuário
        for gname, ends in ENDS_GROUPS.items():
            pts = sum(1 for x in n[:20] if x % 10 in ends)
            if pts >= 6:
                nome, ts = self._nomear("GRUPO", gname.replace("-", ""))
                encontrados.append({
                    "nome": nome, "tipo": "grupo_finais", "forca": pts,
                    "nums": [x for e in ends for x in range(e, 37, 10) if x <= 36],
                    "desc": f"Grupo {gname} com {pts} aparições",
                    "ts": ts,
                })

        # 3) Setor da roda quente/frio
        heat = [0.0] * 37
        for i, x in enumerate(n[:15]):
            w = 1.4 - i * 0.06
            heat[x] += 3 * w
            for nb in neigh(x, 2):
                heat[nb] += 1.3 * w
        quentes = sorted(range(37), key=lambda x: -heat[x])[:5]
        frios = sorted(range(37), key=lambda x: heat[x])[:5]
        if heat[quentes[0]] >= 5:
            nome, ts = self._nomear("SETOR_QUENTE", str(quentes[0]))
            encontrados.append({
                "nome": nome, "tipo": "setor_quente", "forca": heat[quentes[0]],
                "nums": quentes, "desc": f"Setor quente em torno de {quentes}",
                "ts": ts,
            })
        nome, ts = self._nomear("SETOR_FRIO", str(frios[0]))
        encontrados.append({
            "nome": nome, "tipo": "setor_frio", "forca": 3.0,
            "nums": frios, "desc": f"Setor frio: {frios}",
            "ts": ts,
        })

        # 4) Eco / repetição rápida
        for dist in (1, 2, 3):
            ecos = []
            for i in range(min(20, len(n) - dist)):
                if n[i] == n[i + dist]:
                    ecos.append(n[i])
            if len(ecos) >= 2:
                nome, ts = self._nomear("ECO", f"d{dist}")
                encontrados.append({
                    "nome": nome, "tipo": "eco", "forca": len(ecos),
                    "nums": list(dict.fromkeys(ecos)),
                    "desc": f"Eco distância {dist}: {ecos[:6]}",
                    "ts": ts,
                })

        # 5) Associações do usuário batendo
        hits_assoc = Counter()
        for i in range(min(25, len(n) - 1)):
            a = n[i]
            b = n[i + 1]
            if b in ASSOC.get(a, []):
                hits_assoc[(a, b)] += 1
        for (a, b), cnt in hits_assoc.most_common(4):
            if cnt >= 1:
                nome, ts = self._nomear("ASSOC", f"{a}para{b}")
                encontrados.append({
                    "nome": nome, "tipo": "associacao", "forca": cnt + 1,
                    "nums": [b], "desc": f"Associação {a}→{b} ({cnt}x)",
                    "ts": ts,
                })

        # 6) Atrasados extremos
        atrasados = []
        for num in range(37):
            g = gap(n, num, 80)
            if g >= 45:
                atrasados.append((num, g))
        atrasados.sort(key=lambda x: -x[1])
        if atrasados:
            top = [a[0] for a in atrasados[:6]]
            nome, ts = self._nomear("ATRASO", f"{top[0]}g{atrasados[0][1]}")
            encontrados.append({
                "nome": nome, "tipo": "atraso", "forca": atrasados[0][1] / 20,
                "nums": top, "desc": f"Atrasados: {atrasados[:4]}",
                "ts": ts,
            })

        # 7) Fogo / vizinhos de fogo
        if fire:
            viz = []
            for f in fire:
                viz += neigh(f, 2)
            nome, ts = self._nomear("FOGO_VIZ", str(fire[:3]))
            encontrados.append({
                "nome": nome, "tipo": "fogo_vizinho", "forca": 3.5,
                "nums": list(dict.fromkeys(viz))[:10],
                "desc": f"Vizinhos de fogo {fire}",
                "ts": ts,
            })

        # 8) Paridade / cor desequilíbrio
        mid = [x for x in n[:20] if x]
        if mid:
            pares = sum(1 for x in mid if x % 2 == 0)
            if pares >= 14 or pares <= 6:
                lado = "pares" if pares >= 14 else "impares"
                nome, ts = self._nomear("PARIDADE", lado)
                nums = [x for x in range(1, 37) if (x % 2 == 0) == (lado != "pares")]
                encontrados.append({
                    "nome": nome, "tipo": "paridade", "forca": abs(pares - 10) / 3,
                    "nums": nums[:12], "desc": f"Excesso de {('pares' if pares>=14 else 'ímpares')} ({pares}/20)",
                    "ts": ts,
                })

        # ordena por força
        encontrados.sort(key=lambda p: -float(p.get("forca", 0)))
        
        # --- descoberta extra: repetições, pares, ritmo temporal ---
        try:
            # pares consecutivos frequentes
            pares = Counter()
            for i in range(min(30, len(n)-1)):
                pares[(n[i], n[i+1])] += 1
            for (a, b), cnt in pares.most_common(4):
                if cnt >= 2:
                    nome, ts = self._nomear("PAR", f"{a}-{b}x{cnt}")
                    encontrados.append({
                        "nome": nome, "tipo": "par_seq", "forca": cnt * 2,
                        "nums": [a, b],
                        "desc": f"Par {a}→{b} repetiu {cnt}x",
                        "ts": ts,
                    })
            # números que "voltam" após gap curto
            for x in set(n[:20]):
                pos = [i for i, v in enumerate(n[:25]) if v == x]
                if len(pos) >= 2 and pos[1] - pos[0] <= 6:
                    nome, ts = self._nomear("RETORNO", f"{x}g{pos[1]-pos[0]}")
                    encontrados.append({
                        "nome": nome, "tipo": "retorno_rapido", "forca": 5,
                        "nums": [x],
                        "desc": f"{x} voltou em {pos[1]-pos[0]} giros",
                        "ts": ts,
                    })
            # curiosidade: setor da roda quase ignorado
            if frios:
                nome, ts = self._nomear("EXPLORAR_FRIO", str(frios[0]))
                encontrados.append({
                    "nome": nome, "tipo": "exploracao_fria", "forca": 3,
                    "nums": frios[:3],
                    "desc": f"Curiosidade: setor frio {frios[:3]} — testar",
                    "ts": ts,
                })
        except Exception:
            pass

        self.padroes_vivos = encontrados

        self.padroes_vivos = encontrados[:12]
        self.ultimo_ciclo = datetime.now().strftime("%H:%M:%S")
        self.status = (
            f"[{self.ultimo_ciclo}] trabalhando — {len(self.padroes_vivos)} padrões ativos | "
            + ", ".join(p["nome"] for p in self.padroes_vivos[:4])
        )
        self.log_trabalho.insert(0, self.status)
        self.log_trabalho = self.log_trabalho[:30]

        # alimenta memória compartilhada
        try:
            mem = carregar_memoria_compartilhada()
            mem["padroes_cacadora"] = [
                {"nome": p["nome"], "tipo": p["tipo"], "nums": p["nums"][:8], "desc": p["desc"]}
                for p in self.padroes_vivos[:8]
            ]
            mem["cacadora_status"] = self.status
            mem.setdefault("aprendizados", []).insert(
                0, f"{self.ultimo_ciclo} Cacadora: " + ", ".join(p["nome"] for p in self.padroes_vivos[:5])
            )
            mem["aprendizados"] = mem["aprendizados"][:40]
            salvar_memoria_compartilhada(mem)
        except Exception:
            pass

        self.trabalhando = False
        return self.padroes_vivos

    def nums_sugeridos(self, top=10):
        """Números que a caçadora recomenda às outras IAs."""
        sc = Counter()
        for p in self.padroes_vivos:
            w = float(p.get("forca", 1))
            for num in p.get("nums") or []:
                if 0 <= int(num) <= 36:
                    sc[int(num)] += w
        return [n for n, _ in sc.most_common(top)]

    def texto_caixa(self):
        linhas = [
            f"🔍 IA CAÇADORA DE PADRÕES — {'TRABALHANDO' if self.trabalhando else 'ativa'}",
            f"Status: {self.status}",
            f"Ciclos: {self.ciclos}",
            "-" * 40,
        ]
        if not self.padroes_vivos:
            linhas.append("Nenhum padrão nomeado ainda.")
        for p in self.padroes_vivos[:8]:
            linhas.append(f"• {p['nome']}: {p['desc']}")
        sug = self.nums_sugeridos(8)
        if sug:
            linhas.append("-" * 40)
            linhas.append(f"Alimentando outras IAs com: {sug}")
        return "\n".join(linhas)



    def analisar_ct(self, sectors, full=None):
        """Caça padrões no Crazy Time (setores 1,2,5,10 e bônus)."""
        self.trabalhando = True
        self.ciclos += 1
        self.status = f"ciclo {self.ciclos}: varrendo Crazy Time..."
        r = list(sectors or [])
        encontrados = []
        if len(r) < 5:
            self.status = "CT: aguardando mais resultados..."
            self.trabalhando = False
            return []

        from collections import Counter
        # 1) domínio 1/2
        c12 = sum(1 for s in r[:12] if s in ("1", "2"))
        if c12 >= 7:
            nome, ts = self._nomear("CT_REGIME", "12dominante")
            encontrados.append({
                "nome": nome, "tipo": "regime_12", "forca": c12 / 2,
                "setores": ["1", "2"], "desc": f"1 e 2 dominam ({c12}/12)", "ts": ts,
            })
        # 2) atraso por ciclo
        last = {}
        for i, s in enumerate(r):
            if s not in last:
                last[s] = i
        for a, ciclo in CT_CICLO.items():
            g = last.get(a, len(r))
            raz = g / ciclo
            if raz >= 1.6:
                nome, ts = self._nomear("CT_ATRASO", a.replace(" ", ""))
                encontrados.append({
                    "nome": nome, "tipo": "atraso_ct", "forca": raz,
                    "setores": [a], "desc": f"{a} atrasado gap={g} (ciclo~{ciclo})", "ts": ts,
                })
        # 3) liga 2-5
        q2 = sum(1 for s in r[:10] if s == "2")
        q5 = sum(1 for s in r[:10] if s == "5")
        if q2 >= 3 or q5 >= 2:
            nome, ts = self._nomear("CT_LIGA", "2e5")
            encontrados.append({
                "nome": nome, "tipo": "liga_2_5", "forca": 2 + q2 + q5,
                "setores": ["2", "5"], "desc": f"Liga 2↔5 (2={q2},5={q5} em 10)", "ts": ts,
            })
        # 4) eco 10
        idxs = [i for i, s in enumerate(r[:40]) if s == "10"]
        if len(idxs) >= 2 and idxs[1] - idxs[0] >= 10:
            nome, ts = self._nomear("CT_ECO", "10")
            encontrados.append({
                "nome": nome, "tipo": "eco_10", "forca": 3.5,
                "setores": ["10"], "desc": f"10 eco distância {idxs[1]-idxs[0]}", "ts": ts,
            })
        elif idxs and idxs[0] <= 3:
            nome, ts = self._nomear("CT_10", "recente")
            encontrados.append({
                "nome": nome, "tipo": "10_recente", "forca": 2.5,
                "setores": ["10"], "desc": "10 saiu há pouco — observar repetição", "ts": ts,
            })
        # 5) bônus cluster
        bonus_hits = [s for s in r[:15] if s in ("CoinFlip", "CashHunt", "Pachinko", "CrazyBonus")]
        if len(bonus_hits) >= 2:
            nome, ts = self._nomear("CT_BONUS", "cluster")
            encontrados.append({
                "nome": nome, "tipo": "bonus_cluster", "forca": len(bonus_hits) + 1,
                "setores": list(dict.fromkeys(bonus_hits)),
                "desc": f"Cluster de bônus recente: {bonus_hits}", "ts": ts,
            })
        # 6) matched 1x/2x
        if full:
            m1 = sum(1 for x in full[:10] if x.get("sector") == "1" and x.get("matched"))
            m2 = sum(1 for x in full[:10] if x.get("sector") == "2" and x.get("matched"))
            if m1 >= 2:
                nome, ts = self._nomear("CT_MULT", "1x")
                encontrados.append({
                    "nome": nome, "tipo": "mult_1", "forca": m1 + 1,
                    "setores": ["1"], "desc": f"1x matched {m1}x nos últimos 10", "ts": ts,
                })
            if m2 >= 2:
                nome, ts = self._nomear("CT_MULT", "2x")
                encontrados.append({
                    "nome": nome, "tipo": "mult_2", "forca": m2 + 1,
                    "setores": ["2"], "desc": f"2x matched {m2}x nos últimos 10", "ts": ts,
                })
        # 7) streak
        streak = 0
        for s in r:
            if s in ("1", "2"):
                streak += 1
            else:
                break
        if streak >= 5:
            nome, ts = self._nomear("CT_STREAK", f"{streak}")
            encontrados.append({
                "nome": nome, "tipo": "streak", "forca": streak / 2,
                "setores": ["1", "2", "5", "10"], "desc": f"Streak 1/2 de {streak}", "ts": ts,
            })

        encontrados.sort(key=lambda p: -float(p.get("forca", 0)))
        self.padroes_vivos = encontrados[:12]
        self.ultimo_ciclo = datetime.now().strftime("%H:%M:%S")
        self.status = (
            f"[{self.ultimo_ciclo}] CT trabalhando — {len(self.padroes_vivos)} padrões | "
            + ", ".join(p["nome"] for p in self.padroes_vivos[:4])
        )
        self.log_trabalho.insert(0, self.status)
        self.log_trabalho = self.log_trabalho[:30]
        try:
            mem = carregar_memoria_compartilhada()
            mem["padroes_cacadora_ct"] = [
                {"nome": p["nome"], "tipo": p["tipo"], "setores": p.get("setores", []), "desc": p["desc"]}
                for p in self.padroes_vivos[:8]
            ]
            mem["cacadora_status_ct"] = self.status
            mem.setdefault("aprendizados", []).insert(0, f"{self.ultimo_ciclo} CacadoraCT: " + ", ".join(p["nome"] for p in self.padroes_vivos[:5]))
            mem["aprendizados"] = mem["aprendizados"][:40]
            salvar_memoria_compartilhada(mem)
        except Exception:
            pass
        self.trabalhando = False
        return self.padroes_vivos

    def setores_sugeridos(self, top=4):
        sc = Counter()
        for p in self.padroes_vivos:
            w = float(p.get("forca", 1))
            for s in p.get("setores") or []:
                sc[s] += w
        return [s for s, _ in sc.most_common(top)]

    def texto_caixa_ct(self):
        linhas = [
            f"🔍 IA CAÇADORA CT — {'TRABALHANDO' if self.trabalhando else 'ativa'}",
            f"Status: {self.status}",
            f"Ciclos: {self.ciclos}",
            "-" * 40,
        ]
        if not self.padroes_vivos:
            linhas.append("Nenhum padrão CT nomeado ainda.")
        for p in self.padroes_vivos[:8]:
            linhas.append(f"• {p['nome']}: {p['desc']}")
        sug = self.setores_sugeridos(4)
        if sug:
            linhas.append("-" * 40)
            linhas.append(f"Alimentando outras IAs com setores: {sug}")
        return "\n".join(linhas)

# instância global reutilizável
CACADORA = CacadoraPadroes()


# =====================================================================
# META-IA SUPERVISORA — acima das 3 IAs de ensemble + Caçadora
# Lê desempenho, diagnostica erros, corrige pesos e políticas das outras.
# Meta operacional: taxa de acerto da seleção acima de 30% (por giro
# quando n_alvos permite; senão maximiza taxa de janela).
# Não altera o RNG da roleta — só a política de escolha das IAs subordinadas.
# =====================================================================

import os as _os_meta
import json as _json_meta
from datetime import datetime as _dt_meta

_META_FILE = "meta_ia_supervisor.json"
_META_PATHS = [
    _os_meta.path.join(_os_meta.path.dirname(_os_meta.path.abspath(__file__)), _META_FILE),
    _os_meta.path.join(_os_meta.getcwd(), _META_FILE),
    _os_meta.path.join(_os_meta.path.expanduser("~"), "Downloads", _META_FILE),
]


class MetaSupervisora:
    """
    IA de nível superior.
    - Observa acertos/erros de cada jogo
    - Compara técnicas usadas em hits vs misses
    - Detecta fixação (ex.: só 1 e 2 no Crazy Time)
    - Ajusta pesos de técnicas, tamanho de lista, isolados, migração
    - Publica correções na memória compartilhada para as 3 apps
    """

    META_ALVO = 0.30  # 30%
    JANELA_DIAG = 40  # últimas N decisões para diagnóstico

    def __init__(self, jogo="generico"):
        self.jogo = jogo
        self.historico = []  # {ok, alvos, tecs, saiu, ts, bloco, hora}
        self.correcoes = []
        self.pesos_tecnicas = {}  # tec -> multiplicador 0.2..3.0
        self.politica = {
            "n_alvos_min": 5,
            "n_alvos_max": 10,
            "forcar_isolados": 3,
            "migracao_apos_misses": 4,
            "anti_fixacao": True,
            "boost_bonus_atrasado": True,
            "penalizar_consenso_saturado": True,
            "janela_padrao": 9,
            "janela_isolados": 14,
            "curiosidade": 1.0,  # 0.5..3.0 — força explorar técnicas pouco usadas
            "explorar_novas": True,
        }
        self.diagnostico_atual = "Meta-IA iniciando observação..."
        self.status = "ativa"
        self.taxa_recente = 0.0
        self.taxa_global = 0.0
        self.ciclos = 0
        self.ultimas_acoes = []
        # horário: quantos acertos/tentativas por hora do dia (0-23)
        self.por_hora = {h: {"ok": 0, "n": 0} for h in range(24)}
        # ondas: sequência recente de ok/erro
        self.regime = "NEUTRO"  # VERDE | VERMELHO | NEUTRO
        self.regime_msg = "observando ondas de acerto/erro..."
        self.descobertas = []  # percepções nomeadas pela Meta
        self.curiosidade_log = []
        self._carregar()

    # ---------- persistência ----------
    def _path(self):
        for p in _META_PATHS:
            d = _os_meta.path.dirname(p)
            if d and not _os_meta.path.isdir(d):
                try:
                    _os_meta.makedirs(d, exist_ok=True)
                except Exception:
                    continue
            return p
        return _META_PATHS[0]

    def _carregar(self):
        p = self._path()
        if not _os_meta.path.isfile(p):
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = _json_meta.load(f)
            bloco = data.get(self.jogo) or data.get("generico") or {}
            self.historico = list(bloco.get("historico") or [])[-500:]
            self.pesos_tecnicas = dict(bloco.get("pesos_tecnicas") or {})
            self.politica.update(bloco.get("politica") or {})
            self.correcoes = list(bloco.get("correcoes") or [])[-100:]
            self.ciclos = int(bloco.get("ciclos") or 0)
            ph = bloco.get("por_hora") or {}
            for h in range(24):
                if str(h) in ph:
                    self.por_hora[h] = {"ok": int(ph[str(h)].get("ok", 0)), "n": int(ph[str(h)].get("n", 0))}
                elif h in ph:
                    self.por_hora[h] = {"ok": int(ph[h].get("ok", 0)), "n": int(ph[h].get("n", 0))}
            self.descobertas = list(bloco.get("descobertas") or [])[-40:]
            self.regime = bloco.get("regime") or "NEUTRO"
            self.regime_msg = bloco.get("regime_msg") or self.regime_msg
            self._recalcular_taxas()
            self._atualizar_regime()
        except Exception:
            pass

    def salvar(self):
        p = self._path()
        data = {}
        if _os_meta.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = _json_meta.load(f)
            except Exception:
                data = {}
        data[self.jogo] = {
            "historico": self.historico[-500:],
            "por_hora": {str(h): dict(getattr(self, "por_hora", {}).get(h, {"ok": 0, "n": 0})) for h in range(24)},
            "regime": getattr(self, "regime", "NEUTRO"),
            "regime_msg": getattr(self, "regime_msg", ""),
            "descobertas": list(getattr(self, "descobertas", []) or [])[-40:],
            "pesos_tecnicas": self.pesos_tecnicas,
            "politica": self.politica,
            "correcoes": self.correcoes[-100:],
            "ciclos": self.ciclos,
            "taxa_recente": self.taxa_recente,
            "taxa_global": self.taxa_global,
            "diagnostico": self.diagnostico_atual,
            "atualizado": _dt_meta.now().isoformat(timespec="seconds"),
        }
        try:
            with open(p, "w", encoding="utf-8") as f:
                _json_meta.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        # espelha correções na memória compartilhada
        try:
            mem = carregar_memoria_compartilhada()
            mem.setdefault("meta_supervisor", {})[self.jogo] = {
                "taxa": self.taxa_recente,
                "politica": self.politica,
                "pesos": dict(list(self.pesos_tecnicas.items())[:30]),
                "diagnostico": self.diagnostico_atual,
                "acoes": self.ultimas_acoes[-8:],
            }
            salvar_memoria_compartilhada(mem)
        except Exception:
            pass

    def _recalcular_taxas(self):
        if not self.historico:
            self.taxa_recente = 0.0
            self.taxa_global = 0.0
            return
        ok_g = sum(1 for h in self.historico if h.get("ok"))
        self.taxa_global = ok_g / max(1, len(self.historico))
        recent = self.historico[-self.JANELA_DIAG:]
        ok_r = sum(1 for h in recent if h.get("ok"))
        self.taxa_recente = ok_r / max(1, len(recent))

    # ---------- observação ----------
    def registrar_rodada(self, ok, saiu, alvos, tecs=None, extra=None):
        """Chamado pelas apps após cada validação."""
        agora = _dt_meta.now()
        hora = agora.hour
        entry = {
            "ok": bool(ok),
            "saiu": saiu,
            "alvos": list(alvos or [])[:15],
            "tecs": list(tecs or [])[:20],
            "ts": agora.isoformat(timespec="seconds"),
            "hora": hora,
        }
        if extra and isinstance(extra, dict):
            entry.update({k: extra[k] for k in ("bloco", "padrao", "isolados", "consenso", "modo") if k in extra})
        self.historico.append(entry)
        if len(self.historico) > 500:
            self.historico = self.historico[-500:]
        # horário
        if hora not in self.por_hora:
            self.por_hora[hora] = {"ok": 0, "n": 0}
        self.por_hora[hora]["n"] += 1
        if ok:
            self.por_hora[hora]["ok"] += 1
        self._recalcular_taxas()
        self._atualizar_regime()
        self.ciclos += 1
        # diagnóstico mais frequente quando em regime ruim
        passo = 3 if self.regime == "VERMELHO" else (4 if self.regime == "VERDE" else 5)
        if self.ciclos % passo == 0:
            self.diagnosticar_e_corrigir()
        else:
            self.salvar()

    # ---------- diagnóstico ----------
    def _taxa_por_tecnica(self):
        hit = Counter()
        use = Counter()
        for h in self.historico[-self.JANELA_DIAG:]:
            for t in h.get("tecs") or []:
                use[t] += 1
                if h.get("ok"):
                    hit[t] += 1
        rates = {}
        for t, u in use.items():
            rates[t] = hit[t] / max(1, u)
        return rates, use

    def _fixacao_alvos(self):
        """Detecta se os mesmos números/setores dominam demais."""
        c = Counter()
        for h in self.historico[-25:]:
            for a in h.get("alvos") or []:
                c[str(a)] += 1
        if not c:
            return None, 0.0
        top, cnt = c.most_common(1)[0]
        frac = cnt / max(1, sum(c.values()))
        return top, frac

    def _miss_streak(self):
        s = 0
        for h in reversed(self.historico):
            if h.get("ok"):
                break
            s += 1
        return s


    def _atualizar_regime(self):
        """Ondas de acerto/erro → sinal VERDE / VERMELHO / NEUTRO."""
        h = self.historico[-20:]
        if len(h) < 6:
            self.regime = "NEUTRO"
            self.regime_msg = "dados insuficientes para onda"
            return
        recent8 = h[-8:]
        mid8 = h[-16:-8] if len(h) >= 16 else h[:len(h)//2]
        t_r = sum(1 for x in recent8 if x.get("ok")) / max(1, len(recent8))
        t_m = sum(1 for x in mid8 if x.get("ok")) / max(1, len(mid8)) if mid8 else t_r
        streak_miss = 0
        for x in reversed(h):
            if x.get("ok"):
                break
            streak_miss += 1
        streak_hit = 0
        for x in reversed(h):
            if not x.get("ok"):
                break
            streak_hit += 1
        if t_r >= 0.35 or streak_hit >= 3 or (t_r > t_m + 0.15 and t_r >= 0.25):
            self.regime = "VERDE"
            self.regime_msg = f"SINAL VERDE — janela quente (taxa 8={t_r*100:.0f}%, hits seguidos={streak_hit})"
        elif t_r <= 0.12 or streak_miss >= 5 or (t_r + 0.15 < t_m and t_r < 0.20):
            self.regime = "VERMELHO"
            self.regime_msg = f"SINAL VERMELHO — janela fria (taxa 8={t_r*100:.0f}%, misses seguidos={streak_miss})"
        else:
            self.regime = "NEUTRO"
            self.regime_msg = f"NEUTRO — oscilando (taxa 8={t_r*100:.0f}%)"

    def melhores_horarios(self, min_n=5):
        ranks = []
        for h, d in self.por_hora.items():
            n = int(d.get("n") or 0)
            if n < min_n:
                continue
            ok = int(d.get("ok") or 0)
            ranks.append((ok / n, h, ok, n))
        ranks.sort(reverse=True)
        return ranks

    def curiosidade_explorar(self):
        """
        Força a Meta a 'perguntar': quais técnicas quase não usamos?
        Aumenta peso de técnicas subexploradas para descobrir se funcionam.
        """
        use = Counter()
        for h in self.historico[-60:]:
            for t in h.get("tecs") or []:
                use[t] += 1
        if not use:
            return []
        media = sum(use.values()) / max(1, len(use))
        sub = [t for t, u in use.items() if u < media * 0.45]
        acoes = []
        cur = float(self.politica.get("curiosidade", 1.0))
        for t in sub[:5]:
            w = float(self.pesos_tecnicas.get(t, 1.0))
            novo = min(2.8, max(w, 1.0) * (1.0 + 0.2 * cur))
            self.pesos_tecnicas[t] = round(novo, 3)
            acoes.append(f"curiosidade↑ {t} (pouco usada, testar)")
            self.curiosidade_log.append({"ts": _dt_meta.now().isoformat(timespec="seconds"), "tec": t, "peso": novo})
        if sub:
            self.descobertas.append({
                "ts": _dt_meta.now().isoformat(timespec="seconds"),
                "tipo": "exploracao",
                "msg": f"Explorando {len(sub)} técnicas subusadas: {', '.join(sub[:4])}",
            })
        return acoes

    def diagnosticar_e_corrigir(self):
        self.status = "diagnosticando"
        rates, use = self._taxa_por_tecnica()
        top_fix, frac_fix = self._fixacao_alvos()
        streak = self._miss_streak()
        acoes = []
        problemas = []

        # 1) Taxa abaixo da meta
        if self.taxa_recente < self.META_ALVO and len(self.historico) >= 12:
            problemas.append(f"taxa recente {self.taxa_recente*100:.1f}% < meta {self.META_ALVO*100:.0f}%")
            # amplia cobertura e isolados
            self.politica["n_alvos_min"] = min(8, self.politica.get("n_alvos_min", 5) + 1)
            self.politica["n_alvos_max"] = min(12, max(self.politica["n_alvos_min"] + 2, self.politica.get("n_alvos_max", 10)))
            self.politica["forcar_isolados"] = min(5, self.politica.get("forcar_isolados", 3) + 1)
            self.politica["janela_isolados"] = min(18, self.politica.get("janela_isolados", 14) + 1)
            acoes.append("↑ cobertura + isolados (taxa baixa)")

        # 2) Taxa boa → pode apertar lista
        if self.taxa_recente >= self.META_ALVO + 0.05 and len(self.historico) >= 20:
            self.politica["n_alvos_max"] = max(6, self.politica.get("n_alvos_max", 10) - 1)
            acoes.append("↓ n_alvos_max (taxa confortável)")

        # 3) Técnicas ruins perdem peso; boas ganham
        for t, r in rates.items():
            u = use.get(t, 0)
            if u < 4:
                continue
            cur = float(self.pesos_tecnicas.get(t, 1.0))
            if r < 0.12:
                novo = max(0.25, cur * 0.7)
                self.pesos_tecnicas[t] = round(novo, 3)
                acoes.append(f"peso↓ {t} ({r*100:.0f}% hit)")
                problemas.append(f"técnica fraca: {t}")
            elif r >= 0.35:
                novo = min(3.0, cur * 1.15)
                self.pesos_tecnicas[t] = round(novo, 3)
                acoes.append(f"peso↑ {t} ({r*100:.0f}% hit)")

        # 4) Fixação
        if top_fix and frac_fix >= 0.22:
            problemas.append(f"fixação em alvo {top_fix} ({frac_fix*100:.0f}% das menções)")
            self.politica["anti_fixacao"] = True
            # Crazy Time: setores 1 e 2
            if str(top_fix) in ("1", "2") and self.jogo == "crazy_time":
                self.pesos_tecnicas["setor_1"] = 0.35
                self.pesos_tecnicas["setor_2"] = 0.35
                self.pesos_tecnicas["bonus_atrasado"] = min(3.0, float(self.pesos_tecnicas.get("bonus_atrasado", 1.0)) * 1.4)
                acoes.append("CT: penaliza 1/2, boost bônus atrasado")
            else:
                self.pesos_tecnicas[f"alvo_{top_fix}"] = 0.4
                acoes.append(f"penaliza repetição do alvo {top_fix}")

        # 5) Sequência de misses → migração mais cedo + mais isolados
        if streak >= 4:
            problemas.append(f"sequência de {streak} misses")
            self.politica["migracao_apos_misses"] = max(3, min(5, streak - 1))
            self.politica["forcar_isolados"] = min(5, self.politica.get("forcar_isolados", 3) + 1)
            self.politica["penalizar_consenso_saturado"] = True
            acoes.append("migração antecipada + mais isolados")

        # 6) Se muitas técnicas com uso alto e hit baixo → forçar diversidade de métodos
        fracas = [t for t, r in rates.items() if use.get(t, 0) >= 5 and r < 0.15]
        if len(fracas) >= 3:
            problemas.append(f"{len(fracas)} técnicas sistematicamente fracas")
            self.politica["penalizar_consenso_saturado"] = True
            acoes.append("modo diversidade: consenso saturado penalizado")

        # 7) Ondas + curiosidade (busca ativa de soluções)
        self._atualizar_regime()
        if self.regime == "VERMELHO":
            problemas.append(self.regime_msg)
            self.politica["curiosidade"] = min(3.0, float(self.politica.get("curiosidade", 1.0)) + 0.25)
            self.politica["forcar_isolados"] = min(5, self.politica.get("forcar_isolados", 3) + 1)
            self.politica["migracao_apos_misses"] = 3
            acoes.append("regime VERMELHO → curiosidade↑ + migração cedo")
            acoes.extend(self.curiosidade_explorar()[:3])
        elif self.regime == "VERDE":
            problemas.append(self.regime_msg)
            self.politica["curiosidade"] = max(0.6, float(self.politica.get("curiosidade", 1.0)) - 0.1)
            acoes.append("regime VERDE → manter o que está funcionando")
        else:
            if self.politica.get("explorar_novas", True) and self.ciclos % 10 == 0:
                acoes.extend(self.curiosidade_explorar()[:2])

        # 8) Percepção de horário
        tops_h = self.melhores_horarios(min_n=4)
        if tops_h:
            best = tops_h[0]
            worst = tops_h[-1] if len(tops_h) > 1 else None
            msg_h = f"melhor horário {best[1]:02d}h ({best[0]*100:.0f}% em {best[3]} rodadas)"
            problemas.append(msg_h)
            self.descobertas.append({
                "ts": _dt_meta.now().isoformat(timespec="seconds"),
                "tipo": "horario",
                "msg": msg_h,
            })
            if worst and worst[0] + 0.15 < best[0]:
                acoes.append(f"horário fraco {worst[1]:02d}h ({worst[0]*100:.0f}%) — cautela")

        # 9) Publicar correção legível
        if not problemas:
            problemas.append("sem anomalia grave — observação contínua")
        if not acoes:
            acoes.append("nenhuma correção necessária neste ciclo")

        self.diagnostico_atual = (
            f"[{_dt_meta.now().strftime('%H:%M:%S')}] "
            f"Taxa recente {self.taxa_recente*100:.1f}% | global {self.taxa_global*100:.1f}% | "
            f"Regime: {self.regime} | "
            f"Problemas: {'; '.join(problemas[:4])} | "
            f"Ações: {'; '.join(acoes[:5])}"
        )
        self.ultimas_acoes = acoes[-10:]
        self.correcoes.append({
            "ts": _dt_meta.now().isoformat(timespec="seconds"),
            "taxa": self.taxa_recente,
            "problemas": problemas[:5],
            "acoes": acoes[:6],
        })
        self.status = "corrigiu" if any("↑" in a or "↓" in a or "penaliza" in a or "migração" in a for a in acoes) else "monitorando"
        self.salvar()
        return self.diagnostico_atual

    # ---------- interface para as IAs subordinadas ----------
    def peso_tecnica(self, nome, default=1.0):
        return float(self.pesos_tecnicas.get(nome, default))

    def aplicar_pesos_em_votos(self, votos: Counter, mapa_tec_para_nums=None):
        """
        Ajusta Counter de votos usando pesos da Meta.
        mapa_tec_para_nums: opcional {tec: [nums]}
        """
        if not mapa_tec_para_nums:
            return votos
        for tec, nums in mapa_tec_para_nums.items():
            w = self.peso_tecnica(tec, 1.0)
            if abs(w - 1.0) < 0.05:
                continue
            for n in nums:
                if w < 1:
                    votos[n] = max(0.0, votos[n] - (1.0 - w))
                else:
                    votos[n] += (w - 1.0)
        return votos

    def n_alvos_recomendado(self, base=7):
        mn = int(self.politica.get("n_alvos_min", 5))
        mx = int(self.politica.get("n_alvos_max", 10))
        if self.taxa_recente < self.META_ALVO:
            return max(mn, min(mx, max(base, mn + 1)))
        return max(mn, min(mx, base))

    def isolados_obrigatorios(self):
        return int(self.politica.get("forcar_isolados", 3))

    def misses_para_migrar(self):
        return int(self.politica.get("migracao_apos_misses", 4))

    def deve_penalizar_consenso(self):
        return bool(self.politica.get("penalizar_consenso_saturado", True))

    def filtrar_fixacao(self, candidatos, max_rep=1):
        """Remove excesso do alvo mais repetido nas últimas escolhas."""
        if not self.politica.get("anti_fixacao", True):
            return list(candidatos)
        top, frac = self._fixacao_alvos()
        if not top or frac < 0.18:
            return list(candidatos)
        out = []
        rep = 0
        for c in candidatos:
            if str(c) == str(top):
                rep += 1
                if rep > max_rep:
                    continue
            out.append(c)
        return out

    def texto_painel(self):
        reg_icon = {"VERDE": "🟢", "VERMELHO": "🔴", "NEUTRO": "⚪"}.get(getattr(self, "regime", "NEUTRO"), "⚪")
        linhas = [
            f"🧠 META-IA SUPERVISORA — {self.jogo} — {self.status}",
            f"Meta: ≥ {self.META_ALVO*100:.0f}% | Recente: {self.taxa_recente*100:.1f}% | Global: {self.taxa_global*100:.1f}%",
            f"Ciclos: {self.ciclos} | Histórico: {len(self.historico)} | Curiosidade ×{float(self.politica.get('curiosidade',1)):.1f}",
            f"{reg_icon} REGIME: {getattr(self,'regime','NEUTRO')} — {getattr(self,'regime_msg','')}",
            "-" * 48,
            self.diagnostico_atual,
            "-" * 48,
            f"Política: alvos {self.politica.get('n_alvos_min')}-{self.politica.get('n_alvos_max')} | "
            f"isolados={self.politica.get('forcar_isolados')} | migrar@{self.politica.get('migracao_apos_misses')} misses",
        ]
        try:
            tops_h = self.melhores_horarios(min_n=3)
            if tops_h:
                linhas.append("Horários com mais acerto:")
                for taxa, h, ok, n in tops_h[:4]:
                    linhas.append(f"  • {h:02d}h → {taxa*100:.0f}% ({ok}/{n})")
        except Exception:
            pass
        if self.ultimas_acoes:
            linhas.append("Últimas correções / buscas:")
            for a in self.ultimas_acoes[-6:]:
                linhas.append(f"  • {a}")
        if self.pesos_tecnicas:
            top = sorted(self.pesos_tecnicas.items(), key=lambda x: -abs(x[1]-1.0))[:6]
            linhas.append("Pesos ajustados:")
            for t, w in top:
                linhas.append(f"  • {t}: ×{w:.2f}")
        for d in list(getattr(self, "descobertas", []) or [])[-3:]:
            linhas.append(f"  ✦ {d.get('msg','')[:100]}")
        linhas.append("-" * 48)
        linhas.append("Meta busca soluções: ondas, horário, técnicas pouco usadas.")
        return chr(10).join(linhas)





# ========== SINAL HORÁRIO + ONDA (uso pelos apps) ==========
def sinal_horario_e_onda(jogo="mega_fire"):
    """Retorna dict com regime, cor, mensagem e melhores horários — para UI dos apps."""
    try:
        m = meta_por_jogo(jogo)
        m._atualizar_regime()
        tops = m.melhores_horarios(min_n=3)
        hora_agora = _dt_meta.now().hour
        taxa_hora = None
        ph = getattr(m, "por_hora", {}).get(hora_agora) or {"ok": 0, "n": 0}
        if int(ph.get("n") or 0) >= 3:
            taxa_hora = int(ph["ok"]) / max(1, int(ph["n"]))
        # sinal por HORÁRIO atual
        if taxa_hora is not None:
            if taxa_hora >= 0.30:
                sinal_hora = "VERDE"
                msg_hora = f"Horário {hora_agora:02d}h costuma acertar ({taxa_hora*100:.0f}%)"
            elif taxa_hora <= 0.12:
                sinal_hora = "VERMELHO"
                msg_hora = f"Horário {hora_agora:02d}h costuma errar ({taxa_hora*100:.0f}%)"
            else:
                sinal_hora = "NEUTRO"
                msg_hora = f"Horário {hora_agora:02d}h misto ({taxa_hora*100:.0f}%)"
        else:
            sinal_hora = "NEUTRO"
            msg_hora = f"Horário {hora_agora:02d}h — poucos dados ainda"
        return {
            "regime_onda": m.regime,
            "msg_onda": m.regime_msg,
            "sinal_hora": sinal_hora,
            "msg_hora": msg_hora,
            "hora": hora_agora,
            "melhores_horarios": [(h, t, ok, n) for t, h, ok, n in (tops or [])[:5]],
            "taxa_recente": m.taxa_recente,
            "taxa_global": m.taxa_global,
            "curiosidade": float(m.politica.get("curiosidade", 1.0)),
            "painel": m.texto_painel(),
        }
    except Exception as e:
        return {
            "regime_onda": "NEUTRO", "msg_onda": str(e)[:80],
            "sinal_hora": "NEUTRO", "msg_hora": "—", "hora": 0,
            "melhores_horarios": [], "taxa_recente": 0, "taxa_global": 0,
            "curiosidade": 1.0, "painel": "",
        }




# ========== MEMÓRIA DE PERCEPÇÃO (lab → apps) ==========
class MemoriaPercepcao:
    """Recebe descobertas do lab de percepção e expõe para as IAs dos apps."""
    def __init__(self):
        self.por_jogo = {
            "mega_fire": {"padroes": [], "hipoteses": [], "descartes": [], "atualizado": None},
            "lightning": {"padroes": [], "hipoteses": [], "descartes": [], "atualizado": None},
            "crazy_time": {"padroes": [], "hipoteses": [], "descartes": [], "atualizado": None},
        }
        self._load()

    def _path(self):
        for d in [
            _os_meta.path.dirname(_os_meta.path.abspath(__file__)),
            _os_meta.getcwd(),
            _os_meta.path.join(_os_meta.path.expanduser("~"), "Downloads"),
        ]:
            try:
                p = _os_meta.path.join(d, "memoria_percepcao.json")
                return p
            except Exception:
                continue
        return "memoria_percepcao.json"

    def _load(self):
        p = self._path()
        if not _os_meta.path.isfile(p):
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = _json_meta.load(f)
            for k in self.por_jogo:
                if k in data:
                    self.por_jogo[k] = data[k]
        except Exception:
            pass

    def salvar(self):
        p = self._path()
        try:
            with open(p, "w", encoding="utf-8") as f:
                _json_meta.dump(self.por_jogo, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def publicar(self, jogo, padroes=None, hipoteses=None, descartes=None):
        j = self.por_jogo.setdefault(jogo, {"padroes": [], "hipoteses": [], "descartes": [], "atualizado": None})
        if padroes:
            j["padroes"] = list(padroes)[-40:]
        if hipoteses:
            j["hipoteses"] = list(hipoteses)[-40:]
        if descartes:
            j["descartes"] = list(descartes)[-30:]
        j["atualizado"] = _dt_meta.now().isoformat(timespec="seconds")
        self.salvar()

    def ler(self, jogo):
        return dict(self.por_jogo.get(jogo) or {})

    def nums_sugeridos_por_percepcao(self, jogo, modo="padrao"):
        """Extrai números/setores citados nas percepções ativas."""
        data = self.ler(jogo)
        cnt = Counter()
        chave = "padroes" if modo == "padrao" else ("hipoteses" if modo == "mediano" else "descartes")
        for item in data.get("padroes", []) + (data.get("hipoteses", []) if modo != "anti" else []):
            for n in item.get("nums") or []:
                try:
                    cnt[int(n) if str(n).isdigit() else n] += int(item.get("forca", 1))
                except Exception:
                    cnt[n] += 1
        if modo == "anti":
            # anti: números pouco citados nos padrões
            alln = set(range(37)) if "crazy" not in jogo else set()
            return cnt  # caller inverts
        return cnt


MEMORIA_PERCEPCAO = MemoriaPercepcao()

def percepcao_publicar(jogo, padroes=None, hipoteses=None, descartes=None):
    MEMORIA_PERCEPCAO.publicar(jogo, padroes, hipoteses, descartes)

def percepcao_ler(jogo):
    return MEMORIA_PERCEPCAO.ler(jogo)


# instâncias por jogo
META_MEGA = MetaSupervisora("mega_fire")
META_LIGHT = MetaSupervisora("lightning")
META_CRAZY = MetaSupervisora("crazy_time")

def meta_por_jogo(nome):
    n = (nome or "").lower()
    if "crazy" in n:
        return META_CRAZY
    if "light" in n:
        return META_LIGHT
    return META_MEGA


def resumo_meta_ui(jogo):
    """Texto compacto da Meta para o painel."""
    try:
        meta = meta_por_jogo(jogo)
        lines = []
        # regime
        if hasattr(meta, 'regime_sinal'):
            lines.append(f"Regime: {meta.regime_sinal()}")
        elif hasattr(meta, 'sinal_regime'):
            lines.append(f"Regime: {meta.sinal_regime()}")
        # hour
        if hasattr(meta, 'melhor_horario_txt'):
            lines.append(meta.melhor_horario_txt())
        elif hasattr(meta, 'hits_by_hour'):
            try:
                h = meta.hits_by_hour
                if h:
                    best = max(h.items(), key=lambda kv: kv[1].get('ok',0)/(kv[1].get('ok',0)+kv[1].get('err',0)+1e-9) if isinstance(kv[1], dict) else kv[1])
                    lines.append(f"Hora forte observada: {best[0]}h")
            except Exception:
                pass
        # last decision
        if hasattr(meta, 'ultima_decisao'):
            lines.append(f"Última decisão Meta: {meta.ultima_decisao}")
        if hasattr(meta, 'msg'):
            lines.append(str(meta.msg)[:160])
        return " | ".join(lines) if lines else "Meta online — coordenando"
    except Exception as e:
        return f"Meta: {e}"


# =============================================================================
# MOTOR PESADO — CPU multi-core + GPU (torch) quando disponível
# =============================================================================
import concurrent.futures as _fut_pesado
try:
    import numpy as _np_pesado
except Exception:
    _np_pesado = None
try:
    import torch as _torch_pesado
    _TORCH_OK = True
    _DEVICE = _torch_pesado.device("cuda" if _torch_pesado.cuda.is_available() else "cpu")
except Exception:
    _torch_pesado = None
    _TORCH_OK = False
    _DEVICE = "cpu"

def _info_compute():
    gpu = False
    gpu_name = ""
    if _TORCH_OK:
        gpu = _torch_pesado.cuda.is_available()
        if gpu:
            try:
                gpu_name = _torch_pesado.cuda.get_device_name(0)
            except Exception:
                gpu_name = "CUDA"
    return {
        "numpy": _np_pesado is not None,
        "torch": _TORCH_OK,
        "device": str(_DEVICE),
        "gpu": gpu,
        "gpu_name": gpu_name,
        "cpu_workers": max(2, (os.cpu_count() or 4)),
    }

def _freq_score(nums, n_alvos=10):
    if not nums:
        return []
    if _np_pesado is None:
        from collections import Counter
        c = Counter(nums[:40])
        return [n for n, _ in c.most_common(n_alvos)]
    arr = _np_pesado.array(nums[:60], dtype=_np_pesado.int16)
    # pesos exponenciais no tempo (mais recente = maior)
    w = _np_pesado.exp(-_np_pesado.linspace(0, 2.5, len(arr)))
    scores = _np_pesado.zeros(37, dtype=_np_pesado.float64)
    for i, n in enumerate(arr):
        if 0 <= int(n) <= 36:
            scores[int(n)] += float(w[i])
    return list(_np_pesado.argsort(-scores)[:n_alvos].astype(int))

def _atraso_score(nums, n_alvos=10):
    scores = []
    for n in range(37):
        g = next((i for i, x in enumerate(nums[:80]) if x == n), 80)
        scores.append((g, n))
    scores.sort(reverse=True)
    return [n for _, n in scores[:n_alvos]]

def _markov_score(nums, n_alvos=8):
    if len(nums) < 12:
        return []
    if _np_pesado is not None:
        trans = _np_pesado.zeros((37, 37), dtype=_np_pesado.float64)
        for a, b in zip(nums[1:50], nums[:49]):
            if 0 <= a <= 36 and 0 <= b <= 36:
                trans[int(a), int(b)] += 1.0
        # suavização
        trans += 0.05
        row = trans[int(nums[0])]
        row = row / row.sum()
        return list(_np_pesado.argsort(-row)[:n_alvos].astype(int))
    from collections import Counter, defaultdict
    tr = defaultdict(Counter)
    for a, b in zip(nums[1:50], nums[:49]):
        tr[a][b] += 1
    return [n for n, _ in tr[nums[0]].most_common(n_alvos)]

def _final_score(nums, n_alvos=10):
    from collections import Counter
    fins = Counter([x % 10 for x in nums[:30]])
    top_f = [f for f, _ in fins.most_common(3)]
    cands = []
    for f in top_f:
        cands.extend([n for n in range(f, 37, 10)])
    # rank by recent absence among candidates
    ranked = sorted(cands, key=lambda n: next((i for i, x in enumerate(nums[:40]) if x == n), 40), reverse=True)
    return ranked[:n_alvos]

def _setor_score(nums, n_alvos=10):
    W = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
    heat = [0.0] * 37
    for i, x in enumerate(nums[:25]):
        w = 1.4 - i * 0.04
        if x in W:
            p = W.index(x)
            heat[x] += 3 * w
            for d in (1, 2, 3):
                heat[W[(p - d) % 37]] += (1.2 - 0.2 * d) * w
                heat[W[(p + d) % 37]] += (1.2 - 0.2 * d) * w
    return sorted(range(37), key=lambda n: -heat[n])[:n_alvos]

def _isol_score(nums, n_alvos=10):
    recent = set(nums[:20])
    return [n for n in range(37) if n not in recent][:n_alvos] or list(range(n_alvos))

def _torch_sequence_bias(nums, n_alvos=10):
    """Usa torch (GPU se houver) para bias de sequência por embedding simples."""
    if not _TORCH_OK or len(nums) < 20:
        return []
    try:
        device = _DEVICE
        seq = _torch_pesado.tensor([n for n in nums[:64] if 0 <= n <= 36], dtype=_torch_pesado.long, device=device)
        if seq.numel() < 10:
            return []
        # one-hot suave via embedding
        emb = _torch_pesado.nn.functional.one_hot(seq, num_classes=37).float()
        # pesos decrescentes
        w = _torch_pesado.exp(-_torch_pesado.linspace(0, 2.0, emb.size(0), device=device))
        scored = (emb * w.unsqueeze(1)).sum(dim=0)
        # transição local: último -> distribuição
        last = seq[0].item()
        mask = (seq[1:] == last)
        if mask.any():
            nxt = seq[:-1][mask]
            for v in nxt.tolist():
                scored[v] += 1.5
        top = _torch_pesado.topk(scored, k=min(n_alvos, 37)).indices.tolist()
        return [int(x) for x in top]
    except Exception:
        return []

class MotorPesado:
    """Ensemble pesado: várias técnicas em paralelo na CPU + torch GPU/CPU."""

    def __init__(self):
        self.info = _info_compute()
        self.ultimo_relatorio = ""

    def rodar_roleta(self, nums, fire=None, n_alvos=10):
        fire = fire or []
        workers = self.info.get("cpu_workers", 4)
        tasks = {
            "freq": lambda: _freq_score(nums, n_alvos),
            "atraso": lambda: _atraso_score(nums, n_alvos),
            "markov": lambda: _markov_score(nums, n_alvos),
            "finais": lambda: _final_score(nums, n_alvos),
            "setor": lambda: _setor_score(nums, n_alvos),
            "isol": lambda: _isol_score(nums, n_alvos),
            "torch": lambda: _torch_sequence_bias(nums, n_alvos),
        }
        resultados = {}
        with _fut_pesado.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fn): nome for nome, fn in tasks.items()}
            for fut in _fut_pesado.as_completed(futs):
                nome = futs[fut]
                try:
                    resultados[nome] = fut.result() or []
                except Exception as e:
                    resultados[nome] = []
                    resultados[nome + "_err"] = str(e)

        # votação ponderada
        pesos = {
            "freq": 1.2, "atraso": 1.4, "markov": 1.3, "finais": 1.1,
            "setor": 1.25, "isol": 1.0, "torch": 1.6 if self.info.get("torch") else 0.0,
        }
        score = {n: 0.0 for n in range(37)}
        for nome, lista in resultados.items():
            if nome.endswith("_err"):
                continue
            w = pesos.get(nome, 1.0)
            for i, n in enumerate(lista):
                if isinstance(n, int) and 0 <= n <= 36:
                    score[n] += w * (1.0 / (1 + i * 0.15))
        for n in fire:
            try:
                score[int(n)] += 2.0
            except Exception:
                pass

        ranked = sorted(range(37), key=lambda n: (-score[n], n))
        sel = ranked[:n_alvos]
        isol = resultados.get("isol") or ranked[-8:]
        consenso = []
        # números que aparecem em >= 3 técnicas
        from collections import Counter
        cnt = Counter()
        for nome, lista in resultados.items():
            if nome.endswith("_err"):
                continue
            for n in lista[:8]:
                if isinstance(n, int):
                    cnt[n] += 1
        consenso = [n for n, c in cnt.most_common(12) if c >= 3]

        device = self.info.get("device", "cpu")
        gpu = self.info.get("gpu")
        self.ultimo_relatorio = (
            f"MotorPesado device={device} gpu={gpu} workers={workers} | "
            f"técnicas={list(resultados.keys())} | consenso={consenso[:6]} | sel={sel}"
        )
        return {
            "sel": sel,
            "isol": list(isol)[:8],
            "consenso": consenso,
            "votos": {k: v for k, v in resultados.items() if not k.endswith("_err")},
            "veredito": self.ultimo_relatorio,
            "msg": self.ultimo_relatorio,
            "tops": resultados,
            "device": device,
            "gpu": gpu,
        }

    def rodar_ct(self, setores, n_alvos=3):
        # paraleliza scores simples de setores CT
        ordem = ["1", "2", "5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"]
        ciclo = {"10": 13.5, "CoinFlip": 13.5, "CashHunt": 27, "Pachinko": 27, "CrazyBonus": 54}

        def gap_score():
            out = {}
            for s in ordem:
                g = next((i for i, x in enumerate(setores) if x == s), len(setores))
                esp = ciclo.get(s, 8)
                out[s] = g / max(esp, 1)
            return out

        def freq_score():
            from collections import Counter
            c = Counter(setores[:30])
            return {s: c.get(s, 0) for s in ordem}

        with _fut_pesado.ThreadPoolExecutor(max_workers=4) as ex:
            f1 = ex.submit(gap_score)
            f2 = ex.submit(freq_score)
            gaps = f1.result()
            freqs = f2.result()

        score = {}
        for s in ordem:
            score[s] = gaps.get(s, 0) * 4 + freqs.get(s, 0) * 0.8
        ranked = sorted(ordem, key=lambda s: -score[s])
        self.ultimo_relatorio = f"MotorPesado CT device={self.info.get('device')} | ranked={ranked}"
        return {
            "sel": ranked[:n_alvos],
            "ranked": ranked,
            "score": score,
            "veredito": self.ultimo_relatorio,
            "device": self.info.get("device"),
            "gpu": self.info.get("gpu"),
        }

MOTOR_PESADO = MotorPesado()

def ensemble_roleta_pesado(nums, fire=None, n_alvos=10):
    return MOTOR_PESADO.rodar_roleta(nums, fire=fire, n_alvos=n_alvos)

def ensemble_ct_pesado(setores, n_alvos=3):
    return MOTOR_PESADO.rodar_ct(setores, n_alvos=n_alvos)

def compute_info():
    return _info_compute()
