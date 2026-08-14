# -*- coding: utf-8 -*-
"""
LABORATÓRIO DE ESTUDO INDEPENDENTE
---------------------------------
12 agentes de estudo por jogo, sem decidir aposta.
Publicam percepções em biblioteca_estudos_{jogo}.json
para as IAs de decisão (PipelinePerceptivo) consumirem.

Agentes:
 1 FINAL_DOMINANTE
 2 ATRASADOS
 3 AUSENTES
 4 SETOR_RODA
 5 VIZINHOS
 6 MARKOV
 7 PARES_SEQUENCIA
 8 COLUNA_DUZIA (roleta)
 9 MULTIPLICADOR (roleta)
10 REGIME
11 GAP_CICLO (CT) / FREQUENCIA
12 ANTI_PADRAO
"""
from __future__ import annotations
import os, json, time, math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
CT_SETORES = ["1","2","5","10","CoinFlip","CashHunt","Pachinko","CrazyBonus"]
CT_CICLO = {"1":2.6,"2":4.2,"5":7.7,"10":13.5,"CoinFlip":13.5,"CashHunt":27,"Pachinko":27,"CrazyBonus":54}

def _now():
    return datetime.now().isoformat(timespec="seconds")

def _path(jogo: str) -> Path:
    return ROOT / f"biblioteca_estudos_{jogo}.json"

def carregar(jogo: str) -> dict:
    p = _path(jogo)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"jogo": jogo, "atualizado": None, "estudos": [], "resumo": {}}

def salvar(jogo: str, data: dict):
    data["atualizado"] = _now()
    data["jogo"] = jogo
    _path(jogo).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- 12 agentes roleta ----------
def e01_final(nums):
    fins = Counter([n % 10 for n in nums[:30]])
    e, c = fins.most_common(1)[0]
    return {
        "id": "E01_FINAL", "forca": float(c),
        "nums": [x for x in range(e, 37, 10)],
        "desc": f"Final {e} com {c}/30",
        "tipo": "padrao" if c >= 5 else "hipotese",
    }

def e02_atrasados(nums):
    itens = []
    for n in range(37):
        g = next((i for i,x in enumerate(nums[:80]) if x==n), 80)
        if g >= 25:
            itens.append(n)
    itens = sorted(itens, key=lambda n: -next((i for i,x in enumerate(nums[:80]) if x==n), 80))[:8]
    return {"id":"E02_ATRASADOS","forca":float(len(itens)),"nums":itens,
            "desc":f"{len(itens)} atrasados≥25","tipo":"hipotese"}

def e03_ausentes(nums):
    recent = set(nums[:20])
    aus = [n for n in range(37) if n not in recent][:10]
    return {"id":"E03_AUSENTES","forca":float(len(aus)),"nums":aus,
            "desc":f"{len(aus)} ausentes/20","tipo":"anti"}

def e04_setor(nums):
    heat = [0.0]*37
    for i,x in enumerate(nums[:25]):
        w = 1.2 - i*0.03
        heat[x] += 3*w
        if x in WHEEL:
            p = WHEEL.index(x)
            for d in (1,2):
                heat[WHEEL[(p-d)%37]] += 1.1*w
                heat[WHEEL[(p+d)%37]] += 1.1*w
    quente = sorted(range(37), key=lambda n: -heat[n])[:6]
    frio = sorted(range(37), key=lambda n: heat[n])[:6]
    return [
        {"id":"E04_SETOR_Q","forca":8.0,"nums":quente,"desc":f"setor quente {quente[:4]}","tipo":"padrao"},
        {"id":"E04_SETOR_F","forca":5.0,"nums":frio,"desc":f"setor frio {frio[:4]}","tipo":"anti"},
    ]

def e05_vizinhos(nums):
    if not nums or nums[0] not in WHEEL:
        return None
    p = WHEEL.index(nums[0])
    v = [WHEEL[(p+d)%37] for d in (-2,-1,1,2)]
    return {"id":"E05_VIZ","forca":4.0,"nums":v,"desc":f"vizinhos de {nums[0]}","tipo":"hipotese"}

def e06_markov(nums):
    if len(nums) < 20:
        return None
    tr = defaultdict(Counter)
    for i in range(min(50, len(nums)-1)):
        tr[nums[i]][nums[i+1]] += 1
    ult = nums[0]
    if ult not in tr:
        return None
    top = [n for n,_ in tr[ult].most_common(5)]
    return {"id":"E06_MARKOV","forca":6.0,"nums":top,"desc":f"após {ult} → {top}","tipo":"padrao"}

def e07_pares_seq(nums):
    if len(nums) < 15:
        return None
    pares = Counter((nums[i], nums[i+1]) for i in range(min(40, len(nums)-1)))
    (a,b), c = pares.most_common(1)[0]
    return {"id":"E07_PAR","forca":float(c),"nums":[b],"desc":f"par ({a}→{b}) x{c}","tipo":"hipotese" if c>=3 else "hipotese"}

def e08_coluna_duzia(nums):
    cols = {1:[],2:[],3:[]}
    duz = {1:[],2:[],3:[]}
    for n in nums[:30]:
        if n==0: continue
        cols[((n-1)%3)+1].append(n)
        duz[1 if n<=12 else 2 if n<=24 else 3].append(n)
    cq = max(cols, key=lambda k: len(cols[k]))
    dq = max(duz, key=lambda k: len(duz[k]))
    nums_c = [n for n in range(1,37) if ((n-1)%3)+1==cq][:6]
    return {"id":"E08_COL_DUZ","forca":float(len(cols[cq])),"nums":nums_c,
            "desc":f"col {cq} / dúzia {dq} quentes","tipo":"padrao"}

def e09_mult(nums, mults=None):
    if not mults:
        return {"id":"E09_MULT","forca":0,"nums":[],"desc":"sem mults","tipo":"hipotese"}
    hits = Counter()
    for m in mults[:40]:
        if isinstance(m, dict) and m.get("n") is not None:
            hits[int(m["n"])] += float(m.get("x") or 1)
    top = [n for n,_ in hits.most_common(5)]
    return {"id":"E09_MULT","forca":float(sum(hits.values())),"nums":top,
            "desc":f"mult hits {top}","tipo":"padrao" if top else "hipotese"}

def e10_regime(nums):
    if len(nums) < 30:
        return {"id":"E10_REGIME","forca":0,"nums":[],"desc":"poucos dados","tipo":"hipotese"}
    c1, c2 = Counter(nums[:12]), Counter(nums[12:36])
    t1 = set(k for k,_ in c1.most_common(6))
    t2 = set(k for k,_ in c2.most_common(6))
    ov = len(t1 & t2) / max(len(t1|t2),1)
    mudou = ov < 0.34
    return {"id":"E10_REGIME","forca":float(1-ov),"nums":list(t1)[:5],
            "desc":f"regime_mudou={mudou} ov={ov:.2f}","tipo":"padrao" if mudou else "hipotese"}

def e11_freq(nums):
    fr = Counter(nums[:40])
    top = [n for n,_ in fr.most_common(6)]
    return {"id":"E11_FREQ","forca":float(fr.most_common(1)[0][1] if fr else 0),"nums":top,
            "desc":f"freq top {top}","tipo":"padrao"}

def e12_anti(nums):
    fr = Counter(nums[:40])
    media = max(len(nums[:40])/37.0, 0.01)
    frios = [n for n in range(37) if fr.get(n,0) <= media*0.4][:8]
    return {"id":"E12_ANTI","forca":float(len(frios)),"nums":frios,
            "desc":f"anti-freq {frios[:5]}","tipo":"anti"}

# ---------- CT agents ----------
def c01_gap(secs):
    out=[]
    for s, cic in CT_CICLO.items():
        g = next((i for i,x in enumerate(secs) if x==s), len(secs))
        ratio = g/max(cic,1)
        if ratio >= 1.2:
            out.append({"id":f"C01_GAP_{s}","forca":float(ratio),"nums":[s],
                        "desc":f"{s} gap {g} (~{cic})","tipo":"padrao"})
    return out

def c02_quente(secs):
    fr = Counter(secs[:25])
    out=[]
    for s,c in fr.most_common(4):
        if c>=3:
            out.append({"id":f"C02_HOT_{s}","forca":float(c),"nums":[s],
                        "desc":f"{s} {c}x/25","tipo":"padrao"})
    return out

def c03_anti12(secs):
    fr = Counter(secs[:25])
    if fr.get("1",0)+fr.get("2",0) >= 12:
        alvos = [s for s in CT_SETORES if s not in ("1","2")]
        return {"id":"C03_ANTI12","forca":9.0,"nums":alvos,
                "desc":"1/2 dominam → fora","tipo":"anti"}
    return None

def c04_bonus_atraso(secs):
    out=[]
    for s in ("CoinFlip","CashHunt","Pachinko","CrazyBonus"):
        g = next((i for i,x in enumerate(secs) if x==s), len(secs))
        if g >= CT_CICLO.get(s,20)*1.3:
            out.append({"id":f"C04_BONUS_{s}","forca":float(g/10),"nums":[s],
                        "desc":f"bônus {s} gap {g}","tipo":"hipotese"})
    return out

def c05_markov_ct(secs):
    if len(secs)<15: return None
    tr=defaultdict(Counter)
    for i in range(min(40,len(secs)-1)):
        tr[secs[i]][secs[i+1]]+=1
    ult=secs[0]
    if ult not in tr: return None
    top=[s for s,_ in tr[ult].most_common(4)]
    return {"id":"C05_MARKOV","forca":5.0,"nums":top,"desc":f"após {ult}→{top}","tipo":"padrao"}

def c06_regime_ct(secs):
    if len(secs)<20: return None
    c1,c2=Counter(secs[:10]),Counter(secs[10:30])
    t1=set(c1); t2=set(c2)
    ov=len(t1&t2)/max(len(t1|t2),1)
    return {"id":"C06_REGIME","forca":float(1-ov),"nums":list(t1)[:4],
            "desc":f"ov={ov:.2f}","tipo":"hipotese"}

AGENTES_ROULETTE = [e01_final,e02_atrasados,e03_ausentes,e04_setor,e05_vizinhos,e06_markov,
                    e07_pares_seq,e08_coluna_duzia,e09_mult,e10_regime,e11_freq,e12_anti]

def c07_freq_longo(secs):
    fr = Counter(secs[:50])
    return {"id":"C07_FREQ_L","forca":float(fr.most_common(1)[0][1] if fr else 0),
            "nums":[s for s,_ in fr.most_common(4)],"desc":"freq longa","tipo":"padrao"}

def c08_ausentes(secs):
    recent=set(secs[:15]); aus=[s for s in CT_SETORES if s not in recent]
    return {"id":"C08_AUS","forca":float(len(aus)),"nums":aus,"desc":f"ausentes {aus}","tipo":"anti"}

def c09_transicao_bonus(secs):
    if len(secs)<10: return None
    bonus={"CoinFlip","CashHunt","Pachinko","CrazyBonus"}
    after=[]
    seq=list(reversed(secs[:30]))
    for i in range(len(seq)-1):
        if seq[i] in bonus:
            after.append(seq[i+1])
    fr=Counter(after)
    top=[s for s,_ in fr.most_common(3)]
    return {"id":"C09_AFTER_BONUS","forca":float(sum(fr.values())),"nums":top,"desc":f"após bônus {top}","tipo":"hipotese"}

def c10_entropia(secs):
    fr=Counter(secs[:40]); tot=sum(fr.values()) or 1
    import math
    ent=-sum((c/tot)*math.log(c/tot+1e-12) for c in fr.values())
    return {"id":"C10_ENT","forca":float(ent),"nums":[s for s,_ in fr.most_common(3)],
            "desc":f"entropia={ent:.2f}","tipo":"hipotese"}

def c11_streak(secs):
    if not secs: return None
    u=secs[0]; n=1
    for x in secs[1:15]:
        if x==u: n+=1
        else: break
    return {"id":"C11_STREAK","forca":float(n),"nums":[u],"desc":f"streak {u}x{n}","tipo":"padrao" if n>=3 else "hipotese"}

def c12_meta_ct(secs):
    fr=Counter(secs[:25]); top=[s for s,_ in fr.most_common(3)]
    gaps=[]
    for s in CT_SETORES:
        g=next((i for i,x in enumerate(secs) if x==s), len(secs))
        gaps.append((s, g/max(CT_CICLO.get(s,10),1)))
    gaps.sort(key=lambda x: -x[1])
    nums=[gaps[0][0]]+top
    return {"id":"C12_META_CT","forca":5.0,"nums":list(dict.fromkeys(nums))[:4],
            "desc":"meta gap+freq","tipo":"hipotese"}

AGENTES_CT = [c01_gap,c02_quente,c03_anti12,c04_bonus_atraso,c05_markov_ct,c06_regime_ct,c07_freq_longo,c08_ausentes,c09_transicao_bonus,c10_entropia,c11_streak,c12_meta_ct]

def _norm(x):
    if x is None: return []
    if isinstance(x, dict): return [x]
    if isinstance(x, list):
        out=[]
        for i in x:
            if isinstance(i, dict): out.append(i)
            elif isinstance(i, list): out.extend([j for j in i if isinstance(j, dict)])
        return out
    return []

def estudar(jogo: str, historico: list, mults=None) -> dict:
    """Roda os 12 estudos e grava na biblioteca do jogo."""
    is_ct = jogo == "crazy_time"
    itens = []
    if is_ct:
        for fn in AGENTES_CT:
            try:
                itens.extend(_norm(fn(historico)))
            except Exception:
                continue
        # completar até ~12 com variantes de gap/freq
        while len(itens) < 8:
            itens.append({"id":"C_PAD","forca":1,"nums":[],"desc":"pad","tipo":"hipotese"})
            break
    else:
        for fn in AGENTES_ROULETTE:
            try:
                if fn is e09_mult:
                    itens.extend(_norm(fn(historico, mults)))
                else:
                    itens.extend(_norm(fn(historico)))
            except Exception:
                continue

    itens = [it for it in itens if it.get("nums")]
    itens.sort(key=lambda x: -float(x.get("forca") or 0))
    itens = itens[:16]

    data = carregar(jogo)
    # histórico curto de publicações
    pub = {
        "em": _now(),
        "n_hist": len(historico),
        "estudos": itens,
        "ids": [it.get("id") for it in itens],
    }
    data.setdefault("historico_pub", []).append(pub)
    data["historico_pub"] = data["historico_pub"][-40:]
    data["estudos"] = itens  # snapshot atual para o pipeline
    data["resumo"] = {
        "n_estudos": len(itens),
        "padroes": sum(1 for i in itens if i.get("tipo")=="padrao"),
        "hipoteses": sum(1 for i in itens if i.get("tipo")=="hipotese"),
        "anti": sum(1 for i in itens if i.get("tipo")=="anti"),
        "top": [i.get("id") for i in itens[:5]],
    }
    salvar(jogo, data)
    return data

def ler_estudos(jogo: str) -> list:
    """API para o pipeline de decisão."""
    data = carregar(jogo)
    return list(data.get("estudos") or [])
