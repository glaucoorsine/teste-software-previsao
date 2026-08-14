# -*- coding: utf-8 -*-
"""20 IAs residuais — métodos distintos sobre eventos NÃO EXPLICADOS."""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Dict, List, Set
from .dsl_hipoteses import make_hipotese, legivel
import hashlib

def _id_res(expr, agente, dataset_id, janela):
    # força prefixo residual no id via domínio tag
    h = make_hipotese(expr, agente, dataset_id, f"residual:{dataset_id}", janela)
    h["origem"] = "RESIDUAL"
    h["agente_autor"] = agente
    return h

class RBase:
    id = "R00"
    nome = "BASE"
    orcamento = 3
    def propor(self, residuos: List[dict], hist: List[str], dominio: Set[str], dataset_id: str) -> List[dict]:
        return []

class R01Cobertura(RBase):
    id="R01"; nome="COBERTURA"
    def propor(self, residuos, hist, dominio, dataset_id):
        classes = Counter(r["resultado_observado"] for r in residuos)
        out=[]
        for v,n in classes.most_common(3):
            if n<2: continue
            expr={"op":"gap_since","valor":str(v),"min_gap":5}
            h=_id_res(expr,self.id,dataset_id,40)
            h["descricao"]=f"classe residual frequente {v} n={n}"
            h["residual_n"]=n
            out.append(h)
        return out[:self.orcamento]

class R02Novidade(RBase):
    id="R02"; nome="NOVIDADE"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(hist)<20 or not residuos: return []
        # estados cujo resultado residual não aparece no hist longo
        longs=set(hist[5:40])
        raros=[r["resultado_observado"] for r in residuos if r["resultado_observado"] not in longs]
        if not raros: return []
        v=Counter(raros).most_common(1)[0][0]
        expr={"op":"not","arg":{"op":"count_in_window","valor":str(v),"w":30,"k":1}}
        # candidatos: o próprio raro via gap
        expr={"op":"gap_since","valor":str(v),"min_gap":15}
        h=_id_res(expr,self.id,dataset_id,30)
        h["descricao"]=f"novidade residual {v}"
        return [h]

class R03Divergencia(RBase):
    id="R03"; nome="DIVERGENCIA"
    def propor(self, residuos, hist, dominio, dataset_id):
        # resíduos com alto residual_score
        fortes=[r for r in residuos if float(r.get("residual_score") or 0)>=0.8]
        if len(fortes)<2: return []
        v=Counter(r["resultado_observado"] for r in fortes).most_common(1)[0][0]
        expr={"op":"in_set","set":[str(v)]}
        h=_id_res(expr,self.id,dataset_id,25)
        h["descricao"]=f"alta divergência → {v}"
        h["residual_n"]=len(fortes)
        return [h]

class R04BaixoConsenso(RBase):
    id="R04"; nome="BAIXO_CONSENSO"
    def propor(self, residuos, hist, dominio, dataset_id):
        baixo=[r for r in residuos if float(r.get("consenso_total") or 1)<0.15]
        if len(baixo)<2: return []
        vs=[r["resultado_observado"] for r in baixo]
        top=Counter(vs).most_common(2)
        s=[t[0] for t in top]
        expr={"op":"cooccur","set":s,"w":12}
        h=_id_res(expr,self.id,dataset_id,12)
        h["descricao"]=f"baixo consenso classes {s}"
        return [h]

class R05FronteiraRegime(RBase):
    id="R05"; nome="FRONTEIRA_REGIME"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(hist)<30: return []
        m1=Counter(hist[:10]).most_common(1)[0][0]
        m2=Counter(hist[10:30]).most_common(1)[0][0]
        if m1==m2: return []
        vs=Counter(r["resultado_observado"] for r in residuos).most_common(2)
        if not vs: return []
        expr={"op":"and","args":[
            {"op":"window_diff","valor":str(m1),"w_curta":10,"w_longa":30,"margem":0.03},
            {"op":"in_set","set":[vs[0][0]]},
        ]}
        h=_id_res(expr,self.id,dataset_id,30)
        h["descricao"]=f"resíduo na fronteira {m1}/{m2}→{vs[0][0]}"
        return [h]

class R06RecorrenciaErros(RBase):
    id="R06"; nome="RECORRENCIA_ERROS"
    def propor(self, residuos, hist, dominio, dataset_id):
        # pares de resultados residuais consecutivos no log
        if len(residuos)<4: return []
        pares=Counter()
        for i in range(len(residuos)-1):
            pares[(residuos[i+1]["resultado_observado"], residuos[i]["resultado_observado"])]+=1
        if not pares: return []
        (a,b),n=pares.most_common(1)[0]
        if n<2: return []
        expr={"op":"transition","a":str(a),"b":str(b)}
        h=_id_res(expr,self.id,dataset_id,20)
        h["descricao"]=f"erro recorrente {a}→{b} n={n}"
        h["residual_n"]=n
        return [h]

class R07Calibracao(RBase):
    id="R07"; nome="CALIBRACAO"
    def propor(self, residuos, hist, dominio, dataset_id):
        # classes com residual alto médio
        by=defaultdict(list)
        for r in residuos:
            by[r["resultado_observado"]].append(float(r.get("residual_score") or 0))
        ranked=sorted(((v,sum(s)/len(s),len(s)) for v,s in by.items() if len(s)>=2), key=lambda x:-x[1])
        out=[]
        for v,media,n in ranked[:2]:
            expr={"op":"count_in_window","valor":str(v),"w":25,"k":1}
            h=_id_res(expr,self.id,dataset_id,25)
            h["descricao"]=f"subestimado residual méd={media:.2f} {v}"
            h["residual_n"]=n
            out.append(h)
        return out

class R08EstadosRaros(RBase):
    id="R08"; nome="ESTADOS_RAROS"
    def propor(self, residuos, hist, dominio, dataset_id):
        # não presume recorrência — só cataloga
        cnt=Counter(r["resultado_observado"] for r in residuos)
        raros=[v for v,n in cnt.items() if n==1]
        if not raros: return []
        expr={"op":"in_set","set":raros[:4]}
        h=_id_res(expr,self.id,dataset_id,50)
        h["descricao"]=f"estados raros residuais {raros[:4]}"
        h["estado"]="candidata"  # never auto-strong
        return [h]

class R09Complemento(RBase):
    id="R09"; nome="COMPLEMENTO"
    def propor(self, residuos, hist, dominio, dataset_id):
        explicados=set(hist[:20])
        res_set=set(r["resultado_observado"] for r in residuos)
        fora=sorted(res_set-explicados)[:5]
        if len(fora)<2: return []
        expr={"op":"cooccur","set":fora,"w":15}
        h=_id_res(expr,self.id,dataset_id,15)
        h["descricao"]=f"complemento estrutural {fora}"
        return [h]

class R10GrafoResiduos(RBase):
    id="R10"; nome="GRAFO_RES"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(residuos)<5: return []
        co=defaultdict(int)
        vals=[r["resultado_observado"] for r in residuos[:30]]
        for i in range(len(vals)):
            for j in range(i+1,min(i+4,len(vals))):
                a,b=sorted([vals[i],vals[j]])
                co[(a,b)]+=1
        fortes=sorted(co.items(), key=lambda x:-x[1])[:5]
        if not fortes or fortes[0][1]<2: return []
        cluster=set(fortes[0][0])
        for (a,b),n in fortes[1:]:
            if n>=2 and (a in cluster or b in cluster):
                cluster.add(a); cluster.add(b)
        expr={"op":"cooccur","set":sorted(cluster),"w":10}
        h=_id_res(expr,self.id,dataset_id,10)
        h["descricao"]=f"grafo residual {sorted(cluster)[:5]}"
        return [h]

class R11Entropia(RBase):
    id="R11"; nome="ENTROPIA"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(hist)<20: return []
        # entropia simples da janela curta
        c=Counter(hist[:12])
        total=sum(c.values()) or 1
        import math
        ent=-sum((n/total)*math.log(n/total+1e-12) for n in c.values())
        v=Counter(r["resultado_observado"] for r in residuos).most_common(1)
        if not v: return []
        expr={"op":"in_set","set":[v[0][0]]}
        h=_id_res(expr,self.id,dataset_id,12)
        h["descricao"]=f"resíduo em entropia={ent:.2f} → {v[0][0]}"
        return [h]

class R12ReprAlternativa(RBase):
    id="R12"; nome="REPR_ALT"
    def propor(self, residuos, hist, dominio, dataset_id):
        # par/ímpar dos resíduos (representação alternativa)
        if not residuos: return []
        pi=Counter(("par" if int(str(r["resultado_observado"]).isdigit() and int(r["resultado_observado"])%2==0) else "impar")
                   for r in residuos if str(r["resultado_observado"]).isdigit())
        if not pi: return []
        modo=pi.most_common(1)[0][0]
        cands=[d for d in dominio if str(d).isdigit() and ((int(d)%2==0)==(modo=="par"))]
        expr={"op":"in_set","set":list(cands)[:8]}
        h=_id_res(expr,self.id,dataset_id,20)
        h["descricao"]=f"repr alternativa residual {modo}"
        return [h]

class R13Temporalidade(RBase):
    id="R13"; nome="TEMPORAL_RES"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(residuos)<3: return []
        # concentração: muitos resíduos recentes
        recent=residuos[-5:]
        v=Counter(r["resultado_observado"] for r in recent).most_common(1)[0][0]
        expr={"op":"count_in_window","valor":str(v),"w":8,"k":1}
        h=_id_res(expr,self.id,dataset_id,8)
        h["descricao"]=f"concentração temporal residual {v}"
        return [h]

class R14ErroConjunto(RBase):
    id="R14"; nome="ERRO_CONJUNTO"
    def propor(self, residuos, hist, dominio, dataset_id):
        # todos os scores de explicação baixos
        conj=[r for r in residuos if all(float(r.get(k) or 0)<0.2 for k in r if k.startswith("explicacao_"))]
        if len(conj)<2: return []
        v=Counter(r["resultado_observado"] for r in conj).most_common(1)[0][0]
        expr={"op":"transition","a":hist[1] if len(hist)>1 else hist[0],"b":str(v)} if hist else {"op":"in_set","set":[str(v)]}
        h=_id_res(expr,self.id,dataset_id,20)
        h["descricao"]=f"erro conjunto → {v}"
        h["modelos_que_nao_explicaram"]=["LSTM","PADRAO","FAMILIARIDADE"]
        return [h]

class R15Combinacoes(RBase):
    id="R15"; nome="COMBINACOES"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(hist)<15 or not residuos: return []
        v=residuos[0]["resultado_observado"]
        expr={"op":"and","args":[
            {"op":"not","arg":{"op":"in_set","set":hist[:3]}},
            {"op":"gap_since","valor":str(v),"min_gap":6},
        ]}
        h=_id_res(expr,self.id,dataset_id,25)
        h["descricao"]=f"combinação não explorada → {v}"
        return [h]

class R16FalsoNegativo(RBase):
    id="R16"; nome="FALSO_NEG"
    def propor(self, residuos, hist, dominio, dataset_id):
        # residual médio (quase explicado)
        quase=[r for r in residuos if 0.4<=float(r.get("residual_score") or 0)<=0.7]
        if not quase: return []
        v=Counter(r["resultado_observado"] for r in quase).most_common(1)[0][0]
        expr={"op":"count_in_window","valor":str(v),"w":15,"k":1}
        h=_id_res(expr,self.id,dataset_id,15)
        h["descricao"]=f"falso negativo / quase explicado {v}"
        return [h]

class R17ControleNulo(RBase):
    id="R17"; nome="CONTROLE_NULO"
    def propor(self, residuos, hist, dominio, dataset_id):
        # não propõe tip — marca necessidade de nulo no crítico
        if len(residuos)<3: return []
        v=Counter(r["resultado_observado"] for r in residuos).most_common(1)[0][0]
        expr={"op":"in_set","set":[str(v)]}
        h=_id_res(expr,self.id,dataset_id,40)
        h["descricao"]=f"controle nulo obrigatório para {v}"
        h["exige_nulo"]=True
        return [h]

class R18ClustersEpisodios(RBase):
    id="R18"; nome="CLUSTERS_EP"
    def propor(self, residuos, hist, dominio, dataset_id):
        vals=[r["resultado_observado"] for r in residuos]
        if len(vals)<6: return []
        # blocos consecutivos iguais
        runs=[]
        i=0
        while i<len(vals):
            j=i
            while j<len(vals) and vals[j]==vals[i]:
                j+=1
            if j-i>=2:
                runs.append(vals[i])
            i=j
        if not runs: return []
        v=Counter(runs).most_common(1)[0][0]
        expr={"op":"run_length","valor":str(v),"min_run":2}
        h=_id_res(expr,self.id,dataset_id,20)
        h["descricao"]=f"cluster episódios residual {v}"
        return [h]

class R19MemoriaReentrada(RBase):
    id="R19"; nome="REENTRADA"
    def propor(self, residuos, hist, dominio, dataset_id):
        if len(residuos)<6: return []
        ant=Counter(r["resultado_observado"] for r in residuos[:-3])
        rec=Counter(r["resultado_observado"] for r in residuos[-3:])
        re=[v for v in rec if v in ant]
        if not re: return []
        v=re[0]
        expr={"op":"gap_since","valor":str(v),"min_gap":3}
        h=_id_res(expr,self.id,dataset_id,30)
        h["descricao"]=f"reentrada residual {v}"
        return [h]

class R20Diversidade(RBase):
    id="R20"; nome="DIVERSIDADE"
    def propor(self, residuos, hist, dominio, dataset_id):
        # explora final digit dos resíduos (se numérico)
        fins=Counter()
        for r in residuos:
            s=str(r["resultado_observado"])
            if s.isdigit():
                fins[int(s)%10]+=1
        if not fins: return []
        f,n=fins.most_common(1)[0]
        cands=[d for d in dominio if str(d).isdigit() and int(d)%10==f]
        expr={"op":"in_set","set":cands[:8]}
        h=_id_res(expr,self.id,dataset_id,35)
        h["descricao"]=f"diversidade residual final={f}"
        return [h]

AGENTES_R = [
    R01Cobertura(), R02Novidade(), R03Divergencia(), R04BaixoConsenso(),
    R05FronteiraRegime(), R06RecorrenciaErros(), R07Calibracao(), R08EstadosRaros(),
    R09Complemento(), R10GrafoResiduos(), R11Entropia(), R12ReprAlternativa(),
    R13Temporalidade(), R14ErroConjunto(), R15Combinacoes(), R16FalsoNegativo(),
    R17ControleNulo(), R18ClustersEpisodios(), R19MemoriaReentrada(), R20Diversidade(),
]

def listar_metodos():
    return [{"id": a.id, "nome": a.nome, "classe": a.__class__.__name__} for a in AGENTES_R]
