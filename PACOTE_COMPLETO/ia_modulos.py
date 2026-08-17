# -*- coding: utf-8 -*-
"""
Pipeline com protocolo de avaliação rigoroso:
- baseline com o MESMO k de saídas
- split cronológico + walk-forward
- decision_id antes do resultado; janela = 1 decisão
- Brier, log-loss, calibração, cobertura, ganho vs baseline + IC
- teste negativo (shuffle)
- SEM EVIDÊNCIA por confiança calibrada
- modelos/memórias por jogo
- versionamento
- percepção como features auditáveis (não voto cego)
- interrompe modelo se não supera baseline
"""
from __future__ import annotations
import os, time, json, math, copy, uuid, hashlib
import numpy as np
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    from pathlib import Path as _Paa
    import sys as _sys_aa
    _root_aa = _Paa(__file__).resolve().parent
    if str(_root_aa) not in _sys_aa.path:
        _sys_aa.path.insert(0, str(_root_aa))
    from academia_autonoma import ciclo as ciclo_academia_autonoma
except Exception as _e_aa:
    ciclo_academia_autonoma = None

try:
    from descoberta_agentes import ciclo_descoberta, candidatos_da_biblioteca, listar_agentes
except Exception as _imp_desc:
    ciclo_descoberta = None
    candidatos_da_biblioteca = None
    listar_agentes = None
    print("[ia_modulos] descoberta_agentes indisponível:", _imp_desc)
try:
    from fabricante_teorias import fabricar_para
except Exception:
    fabricar_para = None

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    HAS_TORCH = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
except ImportError:
    HAS_TORCH = False
    DEVICE = "cpu"

ROOT = Path(__file__).resolve().parent
# Laboratório de percepção externo (features auditáveis)
try:
    import percepcao_lab as PLAB
    HAS_PLAB = True
except Exception:
    PLAB = None
    HAS_PLAB = False
try:
    import estudo_lab as ESTUDO
    HAS_ESTUDO = True
except Exception:
    ESTUDO = None
    HAS_ESTUDO = False
try:
    import academia_agentes as ACADEMIA
    HAS_ACADEMIA = True
except Exception:
    ACADEMIA = None
    HAS_ACADEMIA = False
ORDENS_PATH = ROOT / "ordens_ia.json"
# A VERSAO PRECISA MUDAR QUANDO A DECISAO MUDA.
#
# Ficou em "v21-sombra" enquanto quem escolhe o numero passou a ser outro:
# antes era o consenso sob regua de sombra, agora e o Cacador de
# Multiplicador sem regua. Toda decisao gravada carrega este rotulo, e a
# memoria mistura as duas eras como se fossem a mesma coisa.
#
# Na pratica isso corrompe a medida: decisoes tomadas por um criterio entram
# na mesma taxa de acerto de decisoes tomadas por outro, e nao ha como
# separar depois. O rotulo e o unico lugar onde essa fronteira existe.
PIPELINE_VERSION = "2026.08.17-v121-cacador"
EVAL_PROTOCOL = "eval-2026.08.10-v1"  # estável entre patches
FEATURE_VERSION = "fv4-lab"

WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
VOISINS = {22,18,29,7,28,12,35,3,26,0,32,15,19,4,21,2,25}
TIERS = {27,13,36,11,30,8,23,10,5,24,16,33}
ORPHELINS = {1,20,14,31,9,17,34,6}
CT_SETORES = ["1","2","5","10","CoinFlip","CashHunt","Pachinko","CrazyBonus"]
CT_CICLO = {"1":2.6,"2":4.2,"5":7.7,"10":13.5,"CoinFlip":13.5,"CashHunt":27,"Pachinko":27,"CrazyBonus":54}
# AS 54 FATIAS DA RODA, E O QUE ELAS NAO AUTORIZAM.
#
# Sao 54 fatias muito desiguais -- o "1" ocupa 21, o CrazyBonus ocupa 1. Estes
# numeros existem aqui para o placar poder calcular o acaso da aposta certa, e
# para `gaps_ratio` dividir o atraso pelo ciclo proprio de cada simbolo.
#
# O QUE ELES NAO SERVEM PARA FAZER: escolher por cima da previsao. Eu usei esta
# tabela para dar um empurrao aos simbolos frequentes, e ele desfez o
# argumento na hora:
#
#     "se ele escolheu aqueles dois bonus e porque a previsao dele falava dos
#      bonus, nao falava de outra coisa. Nao e que ele esta escolhendo errado"
#
# Ele tem razao, e era regua redundante ainda por cima: o gap ja vem
# normalizado pelo ciclo, entao a raridade ja estava contabilizada uma vez.
# A tabela mede; quem escolhe e a previsao.
CT_FATIAS = {"1": 21, "2": 13, "5": 7, "10": 4,
             "CoinFlip": 4, "CashHunt": 2, "Pachinko": 2, "CrazyBonus": 1}
CT_TOTAL_FATIAS = 54
CT_P = {s: n / CT_TOTAL_FATIAS for s, n in CT_FATIAS.items()}
MAP_CT_TO_IDX = {s:i for i,s in enumerate(CT_SETORES)}
MAP_IDX_TO_CT = {i:s for i,s in enumerate(CT_SETORES)}

def neigh(n, d=2):
    if n not in WHEEL: return []
    i = WHEEL.index(n)
    out=[]
    for k in range(1,d+1):
        out += [WHEEL[(i-k)%37], WHEEL[(i+k)%37]]
    return out

def setor_do(n):
    if n in VOISINS: return "VOISINS"
    if n in TIERS: return "TIERS"
    if n in ORPHELINS: return "ORPHELINS"
    return "OUTRO"

def cronologico(seq):
    return list(reversed(list(seq)))

def wilson_ci(successes, n, z=1.96):
    if n <= 0: return (0.0, 0.0)
    p = successes / n
    den = 1 + z*z/n
    centre = p + z*z/(2*n)
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (max(0.0, (centre-margin)/den), min(1.0, (centre+margin)/den))

# ---------- ORDENS ----------
def ler_ordens(jogo: str) -> dict:
    base = {"janela": None, "peso_isol": None, "peso_motor": None, "boost_anti": None,
            "prioritizar_atraso": None, "reduzir_12": None, "motivo": None, "_pendente": False}
    if not ORDENS_PATH.is_file():
        return base
    try:
        data = json.loads(ORDENS_PATH.read_text(encoding="utf-8"))
        g = data.get("global") or {}
        j = data.get(jogo) or {}
        merged = {**g, **j}
        pub, apl = merged.get("publicada_em"), merged.get("aplicada_em")
        pendente = bool(pub) and (not apl or str(pub) > str(apl))
        if not pendente:
            return {
                "janela": merged.get("janela"),
                "peso_isol": merged.get("peso_isol"),
                "peso_motor": None,
                "boost_anti": merged.get("boost_anti"),
                "prioritizar_atraso": merged.get("prioritizar_atraso"),
                "reduzir_12": merged.get("reduzir_12"),
                "motivo": merged.get("motivo"),
                "_pendente": False, "_ja_aplicada": True,
            }
        out = {**base, "_pendente": True}
        for k in ("janela","peso_isol","peso_motor","boost_anti","prioritizar_atraso","reduzir_12","motivo"):
            if merged.get(k) is not None:
                out[k] = merged.get(k)
        return out
    except Exception as e:
        return {**base, "motivo": f"erro leitura ordens: {e}"}

def marcar_ordem_aplicada(jogo: str) -> bool:
    """Delega ao ia_chat_llm (lock + RMW atômico). Não grava ordens_ia.json diretamente."""
    try:
        from ia_chat_llm import marcar_ordem_aplicada as _marcar
        return bool(_marcar(jogo))
    except Exception:
        return False

# ---------- QUALIDADE ----------
class QualidadeDados:
    def validar(self, nums, settled_list=None, is_ct=False):
        report = {"n": len(nums or []), "duplicados": 0, "invalidos": 0,
                  "ordem_ok": True, "ordem_corrigida": False, "ausentes_flag": False, "interrompeu": False}
        clean, clean_set = [], []
        seen = set(); prev_ts = None; inversions = 0
        for i, n in enumerate(nums or []):
            if is_ct:
                if n not in CT_SETORES:
                    report["invalidos"] += 1; continue
            else:
                if not isinstance(n, int) or not (0 <= n <= 36):
                    report["invalidos"] += 1; continue
            st = None
            if settled_list and i < len(settled_list):
                st = settled_list[i]
                if st and st in seen:
                    report["duplicados"] += 1; continue
                if st:
                    seen.add(st)
                    if prev_ts is not None and st > prev_ts:
                        inversions += 1
                    prev_ts = st
            clean.append(n); clean_set.append(st)
        if inversions > max(2, len(clean)//10):
            report["ordem_ok"] = False
            pairs = [(clean[i], clean_set[i]) for i in range(len(clean))]
            if any(p[1] for p in pairs):
                pairs.sort(key=lambda x: x[1] or "", reverse=True)
                clean = [p[0] for p in pairs]; clean_set = [p[1] for p in pairs]
                report["ordem_corrigida"] = True
            elif inversions > len(clean)//5:
                report["interrompeu"] = True
        if len(clean) < (8 if is_ct else 10):
            report["ausentes_flag"] = True
        return clean, clean_set, report

# ---------- CONTEXTO / PERCEPÇÃO (features auditáveis) ----------
class Contexto:
    def fatias(self, seq):
        return {"curta": seq[:10], "media": seq[:30], "longa": seq[:80]}
    def mudanca_regime(self, seq):
        if len(seq) < 25: return False, 1.0, "poucos dados"
        c1, c2 = Counter(seq[:12]), Counter(seq[12:36])
        t1 = set(k for k,_ in c1.most_common(6))
        t2 = set(k for k,_ in c2.most_common(6))
        ov = len(t1 & t2) / max(len(t1 | t2), 1)
        return ov < 0.34, ov, f"overlap={ov:.2f}"

class Percepcao:
    """Produtor de características auditáveis — não é voto final."""
    def roleta(self, nums, mults=None):
        fr = Counter(nums[:40])
        atr = {n: next((i for i,x in enumerate(nums) if x==n), len(nums)) for n in range(37)}
        finais = Counter([n%10 for n in nums[:30]])
        setores = Counter([setor_do(n) for n in nums[:30]])
        last = nums[0] if nums else None
        media = max(len(nums[:40])/37.0, 0.01)
        anom = [n for n,c in fr.items() if (c-media)/math.sqrt(media) >= 2.0]
        mult_hits = Counter()
        if mults:
            for m in mults[:40]:
                if isinstance(m, dict) and m.get("n") is not None:
                    mult_hits[int(m["n"])] += float(m.get("x") or 1)
        features = {
            "freq": dict(fr), "atrasos": atr,
            "finais_top": [e for e,_ in finais.most_common(3)],
            "setor_quente": setores.most_common(1)[0][0] if setores else None,
            "setores": dict(setores),
            "vizinhos": neigh(last, 2) if isinstance(last, int) else [],
            "ultimo": last, "anomalias": anom, "mult_hits": dict(mult_hits),
            "feature_version": FEATURE_VERSION,
        }
        return features

    def ct(self, secs):
        last = {s: len(secs) for s in CT_SETORES}
        for s in CT_SETORES:
            for i,x in enumerate(secs):
                if x==s: last[s]=i; break
        fr = Counter(secs[:35])
        gaps = {s: last[s]/max(CT_CICLO.get(s,8),1) for s in CT_SETORES}
        # a sequencia crua vai junto: sem ela, TODAS as fontes do crazy time
        # leriam o mesmo `gaps_ratio` -- quatro vozes e uma evidencia so
        return {"last": last, "freq": dict(fr), "gaps_ratio": gaps,
                "seq": list(secs[:200]), "feature_version": FEATURE_VERSION}

class ModeloEstatistico:
    def rank_roleta(self, feats, prior_atraso=False, w_isol=1.0):
        sc = defaultdict(float)
        for n,c in Counter(feats.get("freq") or {}).most_common(15):
            sc[n] += c * 0.5
        atr_w = 0.12 if prior_atraso else 0.08
        for n,a in (feats.get("atrasos") or {}).items():
            sc[n] += min(a, 40) * atr_w * max(1.0, w_isol)
        for n,x in (feats.get("mult_hits") or {}).items():
            sc[n] += min(x, 50) * 0.05
        ranked = sorted(sc, key=lambda n: -sc[n])
        total = sum(sc.values()) or 1
        conf = (sc[ranked[0]]/total) if ranked else 0
        return ranked[:10], sc, conf

    def rank_ct(self, feats, prior_atraso=False, w_isol=1.0):
        sc = defaultdict(float)
        # O ATRASO CONTINUA COM O PESO QUE SEMPRE TEVE.
        #
        # Eu tinha baixado de 2.0 para 1.0, posto um teto no gap e somado um
        # bonus para quem tem mais fatias. Ele reclamou, e com razao: "se ele
        # escolheu aqueles dois bonus e porque a previsao dele falava dos
        # bonus". Aquilo era regua minha decidindo por fora que o simbolo
        # frequente merece mais voz -- exatamente o que ele mandou parar de
        # fazer desde o comeco.
        #
        # E era regua redundante ainda por cima: `gaps_ratio` ja divide o
        # atraso pelo CICLO de cada simbolo (54 giros para o CrazyBonus, 2,6
        # para o "1"). A normalizacao pela raridade ja esta feita ali. Somar
        # a chance da fatia por cima era corrigir duas vezes a mesma coisa,
        # e no sentido errado.
        # o peso do atraso segue o objetivo escolhido (ver CT_OBJETIVO)
        gap_w = (2.4 if prior_atraso else 2.0) * CT_PESO_ATRASO.get(
            CT_OBJETIVO, 1.0)
        for s,g in (feats.get("gaps_ratio") or {}).items():
            sc[s] += float(g) * gap_w * max(1.0, w_isol)
        # A FREQUENCIA ENTRA NORMALIZADA, SENAO ELA MANDA NO PLACAR.
        #
        # Era `sc[s] += c * 0.3` com a CONTAGEM CRUA. Medido num historico de
        # 170 giros:
        #
        #     termo de frequencia   1,2 a 18,0
        #     termo de atraso       0,0 a  6,0
        #
        # A frequencia crua pesava tres vezes mais que o atraso -- e a roda tem
        # 54 fatias desiguais, entao o "1" (21 fatias) recebia 18 pontos so por
        # ser comum, enquanto o CrazyBonus (1 fatia) recebia 1,2 por ser raro.
        # O placar virava um ranking de quem sai mais, que e o oposto do que ele
        # mandou: "sinal para o crazy time e somente o que ta muito tempo sem
        # vir".
        #
        # Agora entra como RAZAO sobre o esperado da propria fatia -- 1,0 e o
        # normal do simbolo, e so o excedente conta. Fica na mesma escala do
        # atraso, e o atraso volta a mandar, que e o que ele pediu.
        _n_ct = sum((feats.get("freq") or {}).values()) or 1
        for s,c in (feats.get("freq") or {}).items():
            _esp = _n_ct * CT_P.get(s, 1.0 / len(CT_P))
            if _esp > 0:
                sc[s] += max(0.0, c / _esp - 1.0) * 0.3
        ranked = sorted(sc, key=lambda s: -sc[s])
        total = sum(sc.values()) or 1
        conf = (sc[ranked[0]]/total) if ranked else 0
        return ranked, sc, conf

class ModeloAnomalia:
    def rank_roleta(self, feats, boost=False):
        a = list(feats.get("anomalias") or [])[:8]
        conf = min(1.0, len(a)/5.0) * (1.2 if boost else 1.0)
        return a, min(1.0, conf)
    def rank_ct(self, feats, boost=False):
        a = [s for s,g in (feats.get("gaps_ratio") or {}).items() if g>=2.5][:5]
        conf = min(1.0, len(a)/3.0) * (1.2 if boost else 1.0)
        return a, min(1.0, conf)

class ModeloSetor:
    def rank_roleta(self, feats):
        sq = feats.get("setor_quente")
        pool = list(VOISINS) if sq=="VOISINS" else list(TIERS) if sq=="TIERS" else list(ORPHELINS) if sq=="ORPHELINS" else []
        fr = Counter(feats.get("freq") or {})
        pool = sorted(pool, key=lambda n: -fr.get(n,0))
        viz = feats.get("vizinhos") or []
        out = list(dict.fromkeys(pool[:8]+viz))[:10]
        return out, sq, 0.7 if pool else 0.2
    def rank_ct(self, feats):
        """Antes esta funcao devolvia uma LISTA CONSTANTE.

            return sorted(["CoinFlip","CashHunt","Pachinko","CrazyBonus"], ...)

        Os mesmos quatro nomes, em todo giro, em qualquer situacao. Isso nao e
        previsao -- e uma constante com aparencia de opiniao, e era a principal
        razao da mesa ficar "travada no 5".

        A diferenca importa, e ele apontou isso: quando a previsao escolhe um
        bonus, a escolha e dela e tem que ser respeitada. O que nao pode e a
        fonte ser incapaz de dizer outra coisa.

        Agora ela ordena os OITO simbolos pelo atraso de cada um -- e o atraso
        ja vem dividido pelo ciclo proprio do simbolo, entao o CrazyBonus (54
        giros de ciclo) e o "1" (2,6) sao comparados em pe de igualdade. Se os
        quatro bonus estiverem na frente, eles saem na frente.
        """
        gr = feats.get("gaps_ratio") or {}
        ordem = sorted(CT_SETORES, key=lambda s: -float(gr.get(s, 0)))
        return ordem, "RODA_CT", 0.6

class BaselineFrequencia:
    """Baseline simples: top-k por frequência no passado — mesmo k do modelo."""
    def prever(self, hist_recente_primeiro, k, is_ct=False):
        c = Counter(hist_recente_primeiro[:40])
        return [x for x,_ in c.most_common(k)]

class GeradorHipoteses:
    def roleta(self, feats, ranks):
        hips=[]
        est,_,_ = ranks["estat"]
        hips.append({"nome":"ESTAT","nums":est,"peso":1.3})
        anom,_ = ranks["anom"]
        if anom: hips.append({"nome":"ANOMALIA","nums":anom,"peso":1.5})
        setor_nums, sq, _ = ranks["setor"]
        if setor_nums: hips.append({"nome":"SETOR","nums":setor_nums,"peso":2.0})
        ends = feats.get("finais_top") or []
        fnums = [n for e in ends for n in range(e,37,10)]
        if fnums: hips.append({"nome":"FINAIS","nums":fnums[:10],"peso":1.4})
        return hips
    def ct(self, feats, ranks):
        """As fontes do Crazy Time eram QUATRO ECOS DA MESMA VOZ.

        Medido no historico real dele (215 giros): GAP_CICLO, ANOMALIA, SETOR e
        HEURISTICA -- todas derivadas do mesmo `gaps_ratio`. A mesa travou no
        Pachinko 15 voltas seguidas, do mesmo jeito que antes travava no 5.

        E o mecanismo se alimenta sozinho: o simbolo que nao sai fica com o
        maior atraso, e escolhido, erra, o atraso CRESCE, e e escolhido de novo.
        Quanto mais erra, mais favorito fica.

        E a ficha 226 do compendio dele -- "muitas respostas iguais podem ser
        copias da mesma evidencia". O conserto nao e calar o atraso: e dar ao
        consenso outra coisa para cruzar. As duas fontes abaixo leem o que o
        atraso nao ve -- quem esta saindo agora, e o que costuma vir depois do
        que acabou de sair.
        """
        hips=[]
        fr_ct = Counter(feats.get("freq") or {})
        if fr_ct:
            quentes = [s for s, _ in fr_ct.most_common(4)]
            if quentes:
                # AS VOZES DE FREQUENCIA SEGUEM O OBJETIVO DA MESA.
                #
                # Ele foi explicito e repetiu: "sinal para o crazy time e
                # somente o que ta muito tempo sem vir". Com CT_OBJETIVO em
                # "atraso", uma voz que aponta os simbolos MAIS COMUNS esta
                # puxando contra a regra dele. Medido: CT_FREQUENTE votava "1"
                # e "2" em 13 de 14 historicos -- as duas maiores fatias da
                # roda, 21 e 13 de 54.
                #
                # Nao e podada (ele mandou nao barrar): pesa menos quando o
                # objetivo e atraso, e volta ao peso cheio se ele trocar o
                # objetivo para "acerto".
                _w_freq = 1.8 * (0.45 if CT_OBJETIVO == "atraso" else 1.0)
                hips.append({"nome": "CT_FREQUENTE", "nums": quentes,
                             "peso": _w_freq})
        seq = feats.get("seq") or []
        if len(seq) >= 40:
            atual = str(seq[0])
            segue = Counter()
            for i in range(1, min(len(seq), 200)):
                if str(seq[i]) == atual:
                    segue[str(seq[i - 1])] += 1
            if segue:
                hips.append({"nome": "CT_TRANSICAO",
                             "nums": [s for s, _ in segue.most_common(3)],
                             "peso": 1.8})
        # o peso das fontes de ATRASO segue o objetivo escolhido
        _wa = CT_PESO_ATRASO.get(CT_OBJETIVO, 1.0)
        est,_,_ = ranks["estat"]
        hips.append({"nome":"GAP_CICLO","nums":est[:5],"peso":2.2*_wa})
        anom,_ = ranks["anom"]
        if anom: hips.append({"nome":"ANOMALIA","nums":anom,"peso":1.8*_wa})
        setor_nums,_,_ = ranks["setor"]
        if setor_nums: hips.append({"nome":"SETOR","nums":setor_nums,"peso":1.6*_wa})
        # ANTI_12: A FONTE QUE TRAVAVA A MESA.
        #
        # Ela dispara quando o "1" e o "2" aparecem muito -- so que os dois
        # juntos sao 34 das 54 fatias, 63% da roda. Em 35 giros isso da umas 22
        # ocorrencias POR CONSTRUCAO, e o gatilho era 12. Ou seja: ela disparava
        # em praticamente todo giro, com o MAIOR peso da mesa (2.5), votando
        # sempre nos raros. Era um veto permanente contra os dois simbolos mais
        # provaveis -- a causa do "crazy time travado no 5" que ele relatou.
        #
        # A ideia por tras dela nao e boba: 1 e 2 pagam pouco. Mas este software
        # mede ACERTO, e nessa conta excluir 63% da roda e sabotagem. Agora ela
        # so fala quando os dois estao MESMO acima do proprio esperado, e com
        # peso de voz normal em vez do maior da mesa.
        fr = Counter(feats.get("freq") or {})
        _n_jan = max(1, sum(fr.values()))
        _esperado_12 = (CT_P["1"] + CT_P["2"]) * _n_jan
        if fr.get("1", 0) + fr.get("2", 0) >= _esperado_12 * 1.25:
            gr = feats.get("gaps_ratio") or {}
            bonus = [s for s in ("CashHunt", "Pachinko", "CrazyBonus", "10", "5")
                     if gr.get(s, 0) >= 1.0]
            if bonus:
                hips.append({"nome": "ANTI_12", "nums": bonus, "peso": 1.4})
        return hips

class Critico:
    # quantas TEORIAS distintas precisam concordar para um número entrar sozinho
    # (sem apoio de padrão/LSTM). É a "maioria" da votação entre teorias.
    MIN_VOTOS_TEORIA = 3

    @staticmethod
    def _familia(nome: str) -> str:
        """
        Agrupa fontes CORRELACIONADAS para não inflarem o placar entre si
        (LAB_*/ESTAT/ANOMALIA vêm da mesma percepção, então contam como uma).

        Teorias da academia são a exceção: cada uma é uma familiaridade
        independente, descoberta e validada por conta própria, então cada uma
        vota como fonte distinta. Antes todas viravam a família "ACADEMIA", e
        como consenso() exige 2 famílias, 18 teorias concordando no mesmo
        número contavam como 1 voto e o número nunca era aprovado.
        """
        n = nome or "?"
        if n.startswith("LAB_") or n.startswith("ESTUDO_") or n in ("ESTAT", "ANOMALIA", "FINAIS", "ATRASO", "HEURISTICA"):
            return "PERCEPCAO"
        if n in ("SETOR", "GAP_CICLO", "ANTI_12"):
            return "ESTRUTURA"
        if n == "LSTM":
            return "LSTM"
        if n.startswith("ACADEMIA_"):
            return "TEORIA:" + n[len("ACADEMIA_"):]
        if n == "REGRA_OPERADOR":
            # A regra do operador é uma teoria como as outras: declarada antes
            # de medir, com mecanismo próprio (família do final na faixa
            # quente), independente das familiaridades da academia. Ela já
            # votava com peso, mas caía aqui no `return n` e virava uma família
            # comum — então não entrava na contagem que abre o gatilho. Pesava
            # e não contava, que é o pior dos dois mundos.
            #
            # Continua não abrindo gatilho sozinha: são precisas duas teorias
            # distintas concordando. O que muda é que ela pode ser uma delas.
            return "TEORIA:REGRA_OPERADOR"
        return n

    @staticmethod
    def _eh_teoria(fam: str) -> bool:
        return str(fam or "").startswith("TEORIA:")

    def consenso(self, hips, n_classes, k_alvos, minimo=2):
        """
        Votação: cada hipótese vota nos seus números, com peso próprio e
        decaimento por posição (1º número da lista vale mais que o 5º).

        Um número entra na sugestão por QUALQUER um dos dois caminhos:
          a) >= MIN_VOTOS_TEORIA teorias distintas concordando  (maioria entre teorias)
          b) >= `minimo` famílias distintas                     (teoria + padrão + LSTM)
        Os mais votados ficam no topo — a ordem é por peso total acumulado.
        """
        # O NÚMERO É A CHAVE, E PRECISA SER SEMPRE A MESMA CHAVE.
        #
        # Umas fontes mandam o número como texto ('4') e outras como inteiro
        # (4). Sem normalizar, o mesmo número vira DOIS candidatos e os votos
        # dele são partidos ao meio. Visto num ciclo real do Mega Fire:
        #
        #     4 <- 0 teorias + 2 padrões (peso 3.400)
        #     4 <- 1 teorias + 1 padrões (peso 2.769)
        #
        # Somados dariam 6,17 — o primeiro lugar. Partidos, o 4 aparecia duas
        # vezes na sugestão, gastava duas das sete vagas, e mesmo assim ficava
        # atrás de quem tinha menos apoio. Um voto perdido é voto contado para
        # o lado errado.
        score=defaultdict(float); fontes=defaultdict(set); fontes_raw=defaultdict(set)
        for h in hips:
            w=float(h.get("peso",1))
            # QUEM APONTA MEIA MESA NAO ESTA APONTANDO NADA.
            #
            # Visto na tela dele: a sugestao saiu 1,2,3...,20. Nao era consenso
            # de coisa nenhuma -- era a fonte "alto/baixo" votando no grupo
            # BAIXO inteiro, que sao os numeros 1 a 18. Com as 20 vagas que a
            # cobertura larga abriu, o grupo coube todo e virou "a aposta".
            #
            # Antes isso ficava escondido: com 7 vagas, um grupo de 18 so
            # entrava em parte e parecia escolha. O defeito nao nasceu com as
            # 20 vagas -- elas so o deixaram visivel.
            #
            # A correcao e a que os proprios estudos dele exigem: "comparar cada
            # teoria com selecoes aleatorias do MESMO tamanho". Apontar 3
            # numeros entre 37 carrega log(37/3) = 2,5 de informacao; apontar 18
            # carrega log(37/18) = 0,7. Entao o voto vale pela informacao que
            # traz, e o palpite generico pesa um terco do especifico.
            #
            # Ninguem e excluido -- e exatamente o que ele pediu. Quem fala de
            # meia mesa continua votando, so para de mandar sozinho.
            _nums_h = h.get("nums") or []
            if _nums_h:
                # A REFERENCIA TEM QUE SER DO TAMANHO DA MESA.
                #
                # Eu tinha fixado a base em 3 numeros, pensando nos 37 da
                # roleta. No Crazy Time, que tem 8 simbolos, isso inflava em
                # 2,12x quem aponta UM simbolo -- e a fonte ANOMALIA aponta
                # exatamente um. Medido no historico real dele: Pachinko com
                # score 3,04 contra 1,63 do "1", mesa travada 15 voltas.
                #
                # Agora a referencia e um terco da mesa e a curva e raiz em vez
                # de log: mais suave, sem premiar demais a fonte mais estreita.
                _k = max(1, min(len(_nums_h), n_classes - 1))
                _ref = max(2.0, n_classes / 3.0)
                w *= math.sqrt(_ref / _k)
            fam = self._familia(h.get("nome","?"))
            # O DECAIMENTO POR POSICAO SO VALE QUANDO A ORDEM SIGNIFICA ALGO.
            #
            # ESTA E A RAIZ DO "1,2,3...,12" QUE ELE VIU NA TELA DUAS VEZES.
            #
            # O decaimento existe para respeitar a preferencia de uma fonte: o
            # primeiro nome da lista dela pesa mais que o quinto. Isso e certo
            # para uma fonte que RANQUEIA.
            #
            # Mas varias fontes devolvem um GRUPO, nao um ranking: alto/baixo
            # devolve [1..18], duzia devolve [1..12], cor devolve os vermelhos.
            # A ordem ali e acidental -- e a ordem do `range`, nao uma opiniao.
            # Com o decaimento, o "1" ganhava o peso cheio, o "2" um pouco
            # menos, o "3" menos ainda... e a lista final saia em ordem
            # numerica. A tela mostrava 1,2,3,...,12 e parecia que ninguem
            # tinha decidido nada -- porque, de fato, ninguem tinha.
            #
            # Agora: lista grande e tratada como GRUPO (todos com o mesmo peso)
            # e quem desempata sao as outras fontes. Lista curta continua sendo
            # ranking, e a preferencia dela e respeitada.
            _nums_ord = h.get("nums") or []
            _e_grupo = len(_nums_ord) > max(6, n_classes // 6)
            for i,n in enumerate(_nums_ord):
                chave = str(n).strip()
                score[chave]+= w if _e_grupo else w/(1+i*0.15)
                fontes[chave].add(fam)
                fontes_raw[chave].add(h.get("nome","?"))
        # FICHA 226 ONDE ELA DECIDE: NO PESO, NAO SO NUMA LINHA DA TELA.
        #
        # Quatro fontes que leem o mesmo numero nao sao quatro confirmacoes. O
        # apoio de cada candidato passa a ser dividido pela inflacao das fontes
        # que o sustentam. Nada e barrado -- o numero fica na lista, so para de
        # ser inflado por repeticao.
        try:
            from academia_autonoma.biblioteca_teorias import n_efetivo as _nef
            for _n in list(score.keys()):
                _ap = {h.get("nome", "?"): (h.get("nums") or [])
                       for h in hips
                       if _n in [str(x).strip() for x in (h.get("nums") or [])]}
                if len(_ap) > 1:
                    _inf = float((_nef(_ap) or {}).get("inflacao", 1.0) or 1.0)
                    if _inf > 1.0:
                        score[_n] /= _inf
        except Exception:
            pass
        total=sum(score.values()) or 1.0
        probs={k:v/total for k,v in score.items()}
        votos_teoria={n:sum(1 for f in fs if self._eh_teoria(f)) for n,fs in fontes.items()}
        ordenados=[n for n,_ in sorted(score.items(), key=lambda x: -x[1])]
        if CONSENSO_PURO:
            # O CRUZAMENTO É QUEM ESCOLHE.
            #
            # Nada é barrado por não ter concordância mínima, mas também nada
            # dispara sozinho: todas as teorias votam, os pesos somam, e ficam
            # os mais votados. Um número apontado por quatro teorias sobe
            # acima de um apontado por uma só, sem que ninguém precise ser
            # excluído da votação para isso acontecer.
            #
            # Baixar o mínimo para 1 fazia cada teoria disparar por conta
            # própria, que é o contrário do consenso — foi o que ele corrigiu.
            # CONSENSO PURO NAO PODE VIRAR SEMPRE-SIM.
            #
            # Ele relatou: "as roletas estao dando numeros toda hora". Medido
            # no log dele: uma janela nova a cada 3,5 giros, com janelas de 3 a
            # 4 giros -- ou seja, a mesa NUNCA ficava sem aposta. Assim que uma
            # fechava, outra abria.
            #
            # A causa estava aqui: `aprovados = ordenados` aceitava qualquer
            # numero que tivesse recebido voto, mesmo de uma fonte so. Bastava
            # alguem falar para a janela abrir, e sempre tem alguem falando.
            #
            # O criterio que faz isso virar consenso de verdade e o DELE: "a IA
            # tem que fazer o consenso", e a ficha 226 do compendio -- o numero
            # precisa de vozes INDEPENDENTES, nao de repeticoes da mesma
            # evidencia. Se o mais votado e sustentado por menos de duas vozes
            # independentes, nao houve cruzamento: houve uma fonte falando.
            #
            # Isso nao e regua estatistica minha barrando teoria. E a definicao
            # de consenso aplicada a si mesma. Quando nao ha, a tela diz
            # AGUARDANDO -- que e resposta, nao falha.
            # E A CONTA PRECISA SER FEITA PARA CADA CANDIDATO, NAO SO PARA O
            # PRIMEIRO.
            #
            # Estava assim: pegava `ordenados[0]`, media as vozes dele, e se
            # passasse aprovava a lista INTEIRA. Ou seja, um numero bem
            # sustentado no topo servia de fiador para todos os outros -- e os
            # que vinham atras entravam na aposta sem ninguem ter perguntado
            # quantas vozes independentes eles tinham. Numa lista de dez, o
            # criterio valia para um.
            #
            # E o inverso tambem estragava: o primeiro colocado sustentado por
            # uma fonte so zerava a lista inteira, jogando fora numeros abaixo
            # dele que TINHAM cruzamento.
            #
            # Agora cada candidato responde por si. Quem nao tem vozes
            # independentes sai; quem tem, fica. Se nenhum tiver, a lista sai
            # vazia -- e a tela diz AGUARDANDO, que e resposta.
            # SÃO DUAS PERGUNTAS DIFERENTES, E HAVIA UMA RESPOSTA SÓ.
            #
            # (1) "esta mesa tem cruzamento suficiente para abrir aposta?"  —
            #     é a pergunta do primeiro colocado, e o limiar dela é
            #     MIN_VOZES_INDEPENDENTES. É ela que impede a mesa de estar
            #     sempre com aposta aberta, que foi o que ele reclamou ("as
            #     roletas estao dando numeros toda hora").
            #
            # (2) "este número aqui tem mais de uma voz, ou é uma fonte só
            #     falando?" — é a pergunta de CADA candidato.
            #
            # Só a (1) era feita, e a resposta dela era aplicada à lista
            # inteira: o primeiro colocado servia de fiador para todos os
            # outros, e números sustentados por uma fonte única entravam na
            # aposta sem que ninguém perguntasse nada sobre eles.
            #
            # Fazer a (2) com o limiar da (1) seria trocar um erro por outro:
            # `n_efetivo` desconta correlação, então 2,0 só é alcançável com
            # três ou mais fontes -- duas fontes honestas e quase disjuntas dão
            # 1,67. Cobrar 2,0 de cada candidato esvaziaria a lista quase
            # sempre, e isso seria régua minha, não critério dele.
            #
            # Então cada pergunta com o seu limiar. A (1) continua igual --
            # nada muda em quando a mesa abre. A (2) cobra o que o defeito
            # pedia: mais de uma voz, e vozes que não sejam a mesma evidência
            # repetida (é isso que o efetivo > 1 quer dizer).
            aprovados = ordenados
            try:
                from academia_autonoma.biblioteca_teorias import (
                    n_efetivo as _nef_ap)

                def _vozes_de(_cand):
                    _ap_c = {h.get("nome", "?"): (h.get("nums") or [])
                             for h in hips
                             if _cand in [str(x).strip()
                                          for x in (h.get("nums") or [])]}
                    return float((_nef_ap(_ap_c) or {}).get("efetivo", 0))

                _vozes = {c: _vozes_de(c)
                          for c in ordenados[:max(k_alvos * 3, 12)]}
                # (1) a mesa abre se EXISTE cruzamento — não se ele calhou de
                #     ficar em primeiro. Perguntar só ao primeiro colocado
                #     tinha um efeito perverso: uma fonte solitária e barulhenta
                #     que subisse ao topo fechava a mesa inteira, jogando fora
                #     números abaixo dela que TINHAM cruzamento de verdade. O
                #     critério é a existência de cruzamento; quem o traz é
                #     detalhe.
                if not any(v >= MIN_VOZES_INDEPENDENTES for v in _vozes.values()):
                    aprovados = []
                else:
                    # (2) e entra quem tem mais de uma voz — cada um por si
                    aprovados = [c for c in ordenados
                                 if _vozes.get(c, 0) > MIN_VOZES_POR_NUMERO]
            except Exception:
                pass
        else:
            aprovados=[
                n for n in ordenados
                if len(fontes[n])>=minimo or votos_teoria.get(n,0)>=self.MIN_VOTOS_TEORIA
            ]
        p0 = k_alvos / max(n_classes,1)
        sig={}
        for n in aprovados[:k_alvos]:
            nf=len(fontes[n]); p=1.0
            for _ in range(nf):
                p *= min(1.0, k_alvos/max(n_classes,1))
            sig[n]={
                "fontes":nf,"familias":list(fontes[n]),"raw":list(fontes_raw[n]),
                "p_approx":round(p,5),"significativo":p<0.15,
                "votos_teoria":votos_teoria.get(n,0),
                "votos_outros":nf-votos_teoria.get(n,0),
                "peso_total":round(score[n],3),
            }
        return aprovados, probs, {k:list(v) for k,v in fontes_raw.items()}, score, sig, p0

# ---------- MÉTRICAS ----------
class Metricas:
    @staticmethod
    def brier_janela(calib):
        """Brier no horizonte da JANELA: p = P(hit na janela), y = hit na janela."""
        rows=[c for c in calib if c.get("tipo")=="janela"]
        if len(rows)<3: return None
        return sum((float(c["p"])-float(c["y"]))**2 for c in rows)/len(rows)

    @staticmethod
    def logloss_janela(calib):
        rows=[c for c in calib if c.get("tipo")=="janela"]
        if len(rows)<3: return None
        s=0.0
        for c in rows:
            p=min(max(float(c["p"]),1e-6),1-1e-6)
            y=float(c["y"])
            s += -(y*math.log(p)+(1-y)*math.log(1-p))
        return s/len(rows)

    @staticmethod
    def cobertura(n_emitidas, n_total_ciclos):
        """Cobertura = decisões emitidas / (emitidas + AGUARDANDO)."""
        if not n_total_ciclos: return None
        return n_emitidas / n_total_ciclos

    @staticmethod
    def taxa_e_ic(avaliadas):
        if not avaliadas: return None, (0,0), 0
        hits = sum(1 for a in avaliadas if (a.get("resultado") or {}).get("acertou"))
        n=len(avaliadas)
        return hits/n, wilson_ci(hits, n), n

    @staticmethod
    def ganho_baseline_janela(avaliadas):
        """Acerto do modelo vs baseline NA JANELA. Backfill baseline_acertou se registro antigo."""
        rows=[]
        for a in avaliadas:
            if a.get("baseline_alvos") is None or not a.get("resultado"):
                continue
            res = a["resultado"]
            if "baseline_acertou" not in res:
                # legado: reconstrói a partir dos spins ou do saiu final
                base = set(a.get("baseline_alvos") or [])
                spins = a.get("spins") or []
                if spins:
                    res["baseline_acertou"] = any(s.get("saiu") in base for s in spins)
                else:
                    res["baseline_acertou"] = res.get("saiu") in base
            rows.append(a)
        if len(rows)<3: return None, None, None
        m = sum(1 for a in rows if a["resultado"].get("acertou"))
        b = sum(1 for a in rows if a["resultado"].get("baseline_acertou"))
        n=len(rows)
        return m/n, b/n, (m/n - b/n)

# ---------- MEMÓRIA ----------

def _ts_key(v):
    """Chave temporal comparável (UTC). Evita comparar ISO como texto."""
    try:
        from time_utils import sort_key_ts
        return sort_key_ts(v)
    except Exception:
        return str(v) if v is not None else None

def _ts_le(a, b):
    """True se a <= b em tempo real."""
    if a is None or b is None:
        return False
    try:
        return _ts_key(a) <= _ts_key(b)
    except Exception:
        return str(a) <= str(b)

class Memoria:
    def __init__(self, jogo: str):
        self.jogo = jogo
        # RODAR O TESTE NAO PODE SUJAR A MEMORIA DE VERDADE.
        #
        # Este caminho era fixo em `ROOT`, entao `test_cacador_decide.py` e
        # `test_v121.py` -- que constroem o pipeline direto, com historico
        # sintetico -- gravavam decisoes, acertos, erros e calibragem nos
        # MESMOS arquivos que o software usa ao vivo.
        #
        # O resultado ficou no pacote: os `memoria_*.json` chegaram na maquina
        # dele com decisoes pendentes datadas do dia em que a suite rodou,
        # apontando numeros que nenhuma mesa sorteou. Essas decisoes vao ser
        # avaliadas contra giros reais e entrar no placar como erro. Ou seja: o
        # teste piorava a taxa de acerto medida do software.
        #
        # Com LAB_MEMORIA_DIR, o teste escreve numa pasta temporaria e some com
        # ela. Sem a variavel, nada muda para quem esta rodando ao vivo.
        _dir = os.environ.get("LAB_MEMORIA_DIR")
        _base = Path(_dir) if _dir else ROOT
        try:
            _base.mkdir(parents=True, exist_ok=True)
        except OSError:
            _base = ROOT
        self.path = str(_base / f"memoria_{jogo}.json")
        self.d = {
            "decisoes_pendentes": [], "avaliadas": [], "novidades": [], "modulos": [], "calib": [],
            "versoes": [], "negativo": {}, "modelo_ativo": True, "modelo_ativo_v": {}, "n_aguardando_total": 0, "ultimo_aguardando_settled": None,
        }
        if os.path.isfile(self.path):
            try: self.d.update(json.loads(open(self.path, encoding="utf-8").read()))
            except Exception: pass
        for k in ("modulos","decisoes_pendentes","avaliadas","calib","versoes"):
            if not isinstance(self.d.get(k), list):
                self.d[k]=[]

    def save(self):
        """Lock + reload + merge + escrita atômica (não sobrescreve estado paralelo)."""
        import os, time
        path = self.path
        lock = path + ".lock"
        tmp = path + ".tmp"
        got = False
        for _ in range(40):
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                got = True
                break
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(lock) > 20:
                        os.unlink(lock)
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
            except OSError:
                time.sleep(0.05)
        if not got:
            return
        try:
            disk = {}
            if os.path.isfile(path):
                try:
                    disk = json.loads(open(path, encoding="utf-8").read())
                except Exception:
                    disk = {}
            merged = self._merge_mem_state(disk, self.d)
            self.d = merged
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                if os.path.isfile(tmp):
                    os.unlink(tmp)
            except OSError:
                pass
        finally:
            try:
                os.unlink(lock)
            except OSError:
                pass

    def _merge_mem_state(self, disk: dict, local: dict) -> dict:
        """Combina listas por id — não descarta o que só existe no disco ou no local."""
        out = dict(disk or {})
        for k, v in (local or {}).items():
            if k not in ("decisoes_pendentes", "avaliadas", "calib", "versoes", "modulos"):
                # escalares: preferir local se definido
                if v is not None:
                    out[k] = v
        def by_id(items):
            d = {}
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                iid = it.get("id") or id(it)
                d[iid] = it
            return d
        for key in ("decisoes_pendentes", "avaliadas"):
            a = by_id(out.get(key))
            b = by_id(local.get(key))
            for iid, it in b.items():
                if iid not in a:
                    a[iid] = it
                else:
                    old, new = a[iid], it
                    if old.get("resultado") and not new.get("resultado"):
                        continue
                    if new.get("resultado") and not old.get("resultado"):
                        a[iid] = new
                        continue
                    if len(new.get("spins") or []) >= len(old.get("spins") or []):
                        a[iid] = new
            items = list(a.values())
            if key == "decisoes_pendentes":
                # fechados não ficam pendentes; também dedupe semântico
                abertos = []
                seen_sem = set()
                for it in items:
                    if it.get("resultado") is not None:
                        continue
                    try:
                        from time_utils import canonical_ts as _cts
                        ref = _cts(it.get("settled_ref")) or str(it.get("settled_ref"))
                    except Exception:
                        ref = str(it.get("settled_ref"))
                    sem = (ref, tuple(sorted(str(x) for x in (it.get("alvos") or []))))
                    if sem in seen_sem:
                        continue
                    seen_sem.add(sem)
                    abertos.append(it)
                out[key] = abertos[-50:]
            else:
                out[key] = items[-150:]
        # contadores: max para não perder incremento paralelo
        for ck in ("n_aguardando_total",):
            out[ck] = max(int((disk or {}).get(ck) or 0), int((local or {}).get(ck) or 0))
        # cobertura_acc: soma componentes
        def _acc(d):
            c = (d or {}).get("cobertura_acc") or {}
            return float(c.get("soma_y") or 0), float(c.get("soma_p") or 0), int(c.get("n") or 0)
        y1,p1,n1 = _acc(disk); y2,p2,n2 = _acc(local)
        # se um contém o outro (n maior e soma >=), pegar o maior n
        if n2 >= n1 and y2 >= y1 - 1e-9:
            out["cobertura_acc"] = {"soma_y": y2, "soma_p": p2, "n": n2}
        elif n1 >= n2 and y1 >= y2 - 1e-9:
            out["cobertura_acc"] = {"soma_y": y1, "soma_p": p1, "n": n1}
        else:
            # paralelo verdadeiro: soma (pode inflar levemente se overlap — preferível a perder)
            out["cobertura_acc"] = {"soma_y": y1 + y2, "soma_p": p1 + p2, "n": n1 + n2}
        # CONCATENAR AQUI DOBRAVA A CALIBRAGEM A CADA SAVE.
        #
        # `out` começa como cópia do DISCO. E `self.d` já é o disco, porque no
        # fim de `save()` está escrito `self.d = merged` — a memória em RAM
        # passa a conter tudo o que foi gravado. Então `disco + local` soma o
        # mesmo conteúdo com ele mesmo.
        #
        # Medido: uma entrada de calibragem virou 1 → 2 → 4 → 8 em quatro
        # saves seguidos, sem nenhum giro novo acontecer.
        #
        # E calibragem duplicada não é ruído: o Brier e o log-loss são MÉDIAS
        # sobre estas amostras. Duplicar não muda a média — mas muda o `n`, e
        # o `n` é o que decide se há amostra suficiente para concluir. O
        # software passaria a se declarar calibrado com 25 observações reais
        # contadas como 200.
        #
        # As entradas de `calib` já carregam o `id` da decisão que as gerou.
        # Bastava usá-lo.
        for key in ("calib", "versoes", "modulos"):
            vistos = set()
            juntos = []
            for it in list(out.get(key) or []) + list(local.get(key) or []):
                if isinstance(it, dict):
                    chave = it.get("id")
                    if chave is None:
                        try:
                            chave = json.dumps(it, sort_keys=True,
                                               ensure_ascii=False, default=str)
                        except (TypeError, ValueError):
                            chave = repr(it)
                    # `id` da decisão + tipo: a mesma decisão pode render uma
                    # linha de janela e outra de giro, e as duas valem
                    chave = (str(chave), str(it.get("tipo") or ""))
                else:
                    chave = ("_", repr(it))
                if chave in vistos:
                    continue
                vistos.add(chave)
                juntos.append(it)
            out[key] = juntos[-200:]
        return out

    def registrar_decisao(self, alvos, modo, probs, hips_nomes, conf, dist_sel,
                          baseline_alvos=None, features_hash=None, settled_ref=None, janela=None):
        # SOMBRA com alvos registra pendente; AGUARDANDO/vazio não
        if modo == "AGUARDANDO" or (not alvos):
            self.d["n_aguardando_total"] = int(self.d.get("n_aguardando_total") or 0) + 1
            nv = self.d.setdefault("n_aguardando_total_v", {})
            if not isinstance(nv, dict):
                nv = {}; self.d["n_aguardando_total_v"] = nv
            nv[PIPELINE_VERSION] = int(nv.get(PIPELINE_VERSION) or 0) + 1
            self.d.setdefault("aguardando_log", []).append({
                "em": datetime.now().isoformat(timespec="seconds"), "modo": modo,
                "pipeline_version": PIPELINE_VERSION,
            })
            self.d["aguardando_log"] = self.d.get("aguardando_log", [])[-30:]
            self.save()
            return None
        # Idempotência: mesmo settled_ref + mesmos alvos + ainda aberto → não duplica
        alvos_key = tuple(sorted(str(a) for a in (alvos or [])))
        for pend in self.d.get("decisoes_pendentes") or []:
            if pend.get("resultado") is not None:
                continue
            try:
                from time_utils import canonical_ts as _cts
                same_ref = (_cts(pend.get("settled_ref")) or str(pend.get("settled_ref"))) == (_cts(settled_ref) or str(settled_ref))
            except Exception:
                same_ref = str(pend.get("settled_ref")) == str(settled_ref)
            if same_ref and tuple(sorted(str(a) for a in (pend.get("alvos") or []))) == alvos_key:
                return pend
        item = {
            "id": str(uuid.uuid4())[:8],
            "em": datetime.now().isoformat(timespec="seconds"),
            "pipeline_version": PIPELINE_VERSION,
            "eval_protocol": EVAL_PROTOCOL,
            "feature_version": FEATURE_VERSION,
            "features_hash": features_hash,
            "alvos": alvos, "baseline_alvos": baseline_alvos,
            "modo": modo, "conf": conf, "dist_sel": dist_sel,
            "top_probs": dict(list(sorted((probs or {}).items(), key=lambda x: -x[1]))[:8]),
            "hips": hips_nomes, "resultado": None,
            "settled_ref": settled_ref, "hits": 0, "misses": 0, "janela": janela, "spins": [],
        }
        self.d["decisoes_pendentes"].append(item)
        self.d["decisoes_pendentes"] = self.d["decisoes_pendentes"][-50:]
        self.d.setdefault("versoes", []).append({
            "id": item["id"], "pipeline": PIPELINE_VERSION, "features": FEATURE_VERSION, "em": item["em"]
        })
        self.d["versoes"] = self.d["versoes"][-100:]
        self.save()
        return item

    def registrar_spin(self, saiu, acertou, settled_result=None, window_done=False):
        for ult in reversed(self.d.get("decisoes_pendentes") or []):
            if ult.get("resultado") is not None or not ult.get("alvos"):
                continue
            sref = ult.get("settled_ref")
            if sref and settled_result and _ts_le(settled_result, sref):
                return {"ignored": True, "reason": "resultado_nao_posterior"}
            if acertou:
                ult["hits"] = int(ult.get("hits") or 0) + 1
            else:
                ult["misses"] = int(ult.get("misses") or 0) + 1
            # baseline: acerto se saiu em baseline_alvos em QUALQUER spin da janela
            if saiu in (ult.get("baseline_alvos") or []):
                ult["baseline_hits"] = int(ult.get("baseline_hits") or 0) + 1
            ult.setdefault("spins", []).append({"saiu": saiu, "acertou": bool(acertou), "settled": settled_result})
            ult["spins"] = ult["spins"][-20:]
            # Horizonte fixo: NÃO fecha no primeiro acerto — só com window_done
            if not window_done:
                self.save()
                return {"open": True, "id": ult.get("id"), "hits": ult.get("hits"), "misses": ult.get("misses")}
            # UMA avaliação por janela (modelo e baseline)
            acertou_janela = bool(ult.get("hits", 0) > 0 or acertou)
            baseline_acertou = bool(ult.get("baseline_hits", 0) > 0)
            ult["resultado"] = {
                "saiu": saiu, "acertou": acertou_janela, "baseline_acertou": baseline_acertou,
                "settled": settled_result, "hits": ult.get("hits"), "misses": ult.get("misses"),
                "baseline_hits": ult.get("baseline_hits", 0),
                "spins_n": len(ult.get("spins") or []),
            }
            # p_janela: approx 1-(1-p_sel)^J se J conhecido, senão usa massa calibrada
            dist = ult.get("dist_sel") or {}
            p_sel = sum(float(v) for v in dist.values()) if dist else float(ult.get("conf") or 0)
            p_sel = min(max(p_sel, 1e-6), 1-1e-6)
            J = max(1, int(ult.get("janela") or len(ult.get("spins") or []) or 1))
            p_janela = 1.0 - (1.0 - p_sel)**J
            p_janela = min(max(p_janela, 1e-6), 1-1e-6)
            self.d.setdefault("calib", []).append({
                "p": p_janela, "y": 1.0 if acertou_janela else 0.0,
                "tipo": "janela", "id": ult.get("id"), "J": J, "p_sel": p_sel,
                "pipeline_version": PIPELINE_VERSION,
                "eval_protocol": EVAL_PROTOCOL,
                "p_nota": "approx_indep",
            })
            self.d["calib"] = self.d["calib"][-200:]
            self.d.setdefault("avaliadas", []).append(copy.deepcopy(ult))
            self.d["avaliadas"] = self.d["avaliadas"][-100:]
            # acumula p_esperado da JANELA que fechou (mesma escala de y)
            try:
                from metricas_honestas import p_esperado_para
                is_ct = str(self.jogo).startswith("crazy_time")
                pe = p_esperado_para(ult.get("alvos") or [], int(ult.get("janela") or 3), is_ct=is_ct)
                y = 1.0 if acertou_janela else 0.0
                acc = self.d.setdefault("cobertura_acc", {"soma_y": 0.0, "soma_p": 0.0, "n": 0})
                acc["soma_y"] = float(acc.get("soma_y") or 0.0) + y
                acc["soma_p"] = float(acc.get("soma_p") or 0.0) + float(pe)
                acc["n"] = int(acc.get("n") or 0) + 1
                ult["p_esperado_janela"] = pe
            except Exception:
                pass
            self.save()
            return ult
        return None

    def avaliar_ultima(self, saiu, acertou, settled_result=None, window_done=False):
        return self.registrar_spin(saiu, acertou, settled_result, window_done=window_done)

    def avancar_pendentes_stream(self, hist, settled):
        """Fecha janelas SOMBRA/OPERAR só com o stream (sem depender da UI/pad5).
        hist/settled: mais recente primeiro. Eventos com settled > settled_ref são posteriores.
        """
        if not hist:
            return []
        settled = list(settled or [None] * len(hist))
        if len(settled) < len(hist):
            settled = list(settled) + [None] * (len(hist) - len(settled))
        fechadas = []
        # trabalha sobre cópia da lista de pendentes
        for ult in list(self.d.get("decisoes_pendentes") or []):
            if ult.get("resultado") is not None or not ult.get("alvos"):
                continue
            sref = ult.get("settled_ref")
            janela = max(1, int(ult.get("janela") or 3))
            alvos = set(str(a) for a in (ult.get("alvos") or []))
            base_alvos = set(str(a) for a in (ult.get("baseline_alvos") or []))
            spins = list(ult.get("spins") or [])
            known = set()
            for s in spins:
                if not isinstance(s, dict) or s.get("settled") is None:
                    continue
                known.add(str(s.get("settled")))
                try:
                    from time_utils import canonical_ts as _cts
                    c = _cts(s.get("settled"))
                    if c:
                        known.add(c)
                except Exception:
                    pass
            # pares posteriores em ordem cronológica (antigo → novo)
            posteriores = []
            for n, s in zip(hist, settled):
                if s is None:
                    continue
                if sref is not None:
                    try:
                        if _ts_key(s) <= _ts_key(sref):
                            continue
                    except Exception:
                        if str(s) <= str(sref):
                            continue
                posteriores.append((n, s))
            posteriores.sort(key=lambda x: _ts_key(x[1]) if x[1] is not None else x[1])
            mudou = False
            for n, s in posteriores:
                try:
                    from time_utils import canonical_ts as _cts
                    sk = _cts(s) or str(s)
                except Exception:
                    sk = str(s)
                if sk in known or str(s) in known:
                    continue
                acertou = str(n) in alvos
                if acertou:
                    ult["hits"] = int(ult.get("hits") or 0) + 1
                else:
                    ult["misses"] = int(ult.get("misses") or 0) + 1
                if str(n) in base_alvos:
                    ult["baseline_hits"] = int(ult.get("baseline_hits") or 0) + 1
                spins.append({"saiu": n, "acertou": acertou, "settled": s})
                known.add(str(s))
                mudou = True
                # janela FIXA de J spins (sem early-stop) — baseline e modelo no mesmo horizonte
                if len(spins) >= janela:
                    break
            if not mudou:
                continue
            ult["spins"] = spins[-20:]
            if len(spins) < janela:
                self.save()
                continue
            # fechar janela
            acertou_janela = int(ult.get("hits") or 0) > 0
            baseline_acertou = int(ult.get("baseline_hits") or 0) > 0
            last_spin = spins[-1] if spins else {}
            ult["resultado"] = {
                "saiu": last_spin.get("saiu"), "acertou": acertou_janela,
                "baseline_acertou": baseline_acertou,
                "settled": last_spin.get("settled"),
                "hits": ult.get("hits"), "misses": ult.get("misses"),
                "baseline_hits": ult.get("baseline_hits", 0),
                "spins_n": len(spins),
            }
            dist = ult.get("dist_sel") or {}
            p_sel = sum(float(v) for v in dist.values()) if dist else float(ult.get("conf") or 0)
            p_sel = min(max(p_sel, 1e-6), 1 - 1e-6)
            J = max(1, int(ult.get("janela") or len(spins) or 1))
            p_janela = min(max(1.0 - (1.0 - p_sel) ** J, 1e-6), 1 - 1e-6)
            self.d.setdefault("calib", []).append({
                "p": p_janela, "y": 1.0 if acertou_janela else 0.0,
                "tipo": "janela", "id": ult.get("id"), "J": J, "p_sel": p_sel,
                "pipeline_version": PIPELINE_VERSION,
                "eval_protocol": EVAL_PROTOCOL,
                "p_nota": "approx_indep",
            })
            self.d["calib"] = self.d["calib"][-200:]
            self.d.setdefault("avaliadas", []).append(copy.deepcopy(ult))
            self.d["avaliadas"] = self.d["avaliadas"][-100:]
            # remove dos pendentes
            self.d["decisoes_pendentes"] = [
                d for d in (self.d.get("decisoes_pendentes") or []) if d.get("id") != ult.get("id")
            ]
            fechadas.append(ult)
        if fechadas:
            self.save()
        return fechadas


    def novidade(self, hist):
        seq = [str(x) for x in hist[:12]]
        cnt = Counter(seq)
        prev = self.d.get("novidades") or []
        best = 0.0
        for p in prev[-25:]:
            old_seq = p.get("seq") or []
            match = sum(1 for i in range(min(len(seq), len(old_seq))) if seq[i]==old_seq[i])
            pos_sim = match / max(len(seq), 1)
            old_c = Counter(old_seq)
            multi_sim = sum((cnt & old_c).values()) / max(sum((cnt | old_c).values()), 1)
            best = max(best, 0.6*pos_sim + 0.4*multi_sim)
        is_new = best < 0.5
        self.d.setdefault("novidades", []).append({"seq": seq, "em": datetime.now().isoformat(timespec="seconds"), "sim_max": best})
        self.d["novidades"] = self.d["novidades"][-40:]
        self.save()
        return is_new, best

    def log_modulo(self, nome, conf, dt_ms, extra=""):
        self.d.setdefault("modulos", []).append({
            "nome": nome, "conf": float(conf), "dt_ms": round(float(dt_ms),2),
            "extra": str(extra)[:120], "em": datetime.now().isoformat(timespec="seconds"),
        })
        self.d["modulos"] = self.d["modulos"][-80:]
        self.save()

    def _so_versao_atual(self, rows):
        """Só registros desta PIPELINE_VERSION."""
        return [r for r in (rows or []) if r.get("eval_protocol") == EVAL_PROTOCOL]

    def modelo_ativo_atual(self):
        mv = self.d.get("modelo_ativo_v")
        if isinstance(mv, dict) and PIPELINE_VERSION in mv:
            return bool(mv[PIPELINE_VERSION])
        # 3 — se legado desativou, NÃO herda: v12 começa ativo
        return True

    def set_modelo_ativo(self, ativo: bool):
        mv = self.d.setdefault("modelo_ativo_v", {})
        if not isinstance(mv, dict):
            mv = {}; self.d["modelo_ativo_v"] = mv
        mv[PIPELINE_VERSION] = bool(ativo)
        self.d["modelo_ativo"] = bool(ativo)  # espelho
        self.save()

    def relatorio_metricas(self):
        av = self._so_versao_atual(self.d.get("avaliadas") or [])
        cal = [c for c in (self.d.get("calib") or []) if c.get("pipeline_version") == PIPELINE_VERSION]
        taxa, ic, n = Metricas.taxa_e_ic(av)
        brier = Metricas.brier_janela(cal)
        ll = Metricas.logloss_janela(cal)
        nv = self.d.get("n_aguardando_total_v")
        if isinstance(nv, dict):
            n_ag = int(nv.get(PIPELINE_VERSION) or 0)
        else:
            n_ag = int(self.d.get("n_aguardando_total") or 0)
        cob = Metricas.cobertura(n, n + n_ag)
        tm, tb, ganho = Metricas.ganho_baseline_janela(av)
        # Ganho separado por tipo de decisão: a sombra aposta um conjunto largo
        # e o OPERAR um estreito. Somando os dois num número só, o desempenho de
        # um vetava o outro — populações diferentes, comparação sem sentido.
        av_op = [a for a in av if a.get("modo") == "OPERAR"]
        tm_op, tb_op, ganho_op = Metricas.ganho_baseline_janela(av_op)
        return {
            "n": n, "taxa": taxa, "ic95": ic, "brier": brier, "logloss": ll,
            "cobertura": cob, "taxa_modelo": tm, "taxa_baseline": tb, "ganho": ganho,
            "n_operar": len(av_op), "taxa_operar": tm_op,
            "taxa_baseline_operar": tb_op, "ganho_operar": ganho_op,
            "modelo_ativo": self.modelo_ativo_atual(),
            "n_aguardando": n_ag,
            "protocolo": PIPELINE_VERSION,
            "n_legado_ignorado": len(self.d.get("avaliadas") or []) - n,
        }

    def teste_negativo(self, k=5):
        """Embaralha spins de cada janela — somente protocolo atual."""
        av = copy.deepcopy([a for a in (self.d.get("avaliadas") or []) if a.get("eval_protocol") == EVAL_PROTOCOL])
        if len(av) < 8:
            return {"ok": False, "motivo": "poucas avaliadas"}
        hits_real = sum(1 for a in av if (a.get("resultado") or {}).get("acertou"))
        # pool de todos os saídos observados nas janelas
        pool = []
        for a in av:
            spins = a.get("spins") or []
            if spins:
                pool.extend([s.get("saiu") for s in spins])
            else:
                pool.append((a.get("resultado") or {}).get("saiu"))
        rng = np.random.default_rng(42)
        hits_shuf = 0
        for a in av:
            spins = a.get("spins") or []
            J = max(1, len(spins) or int(a.get("janela") or 1))
            # amostra J resultados aleatórios do pool
            if len(pool) >= J:
                fake = list(rng.choice(pool, size=J, replace=False))
            else:
                fake = list(rng.choice(pool, size=J, replace=True)) if pool else []
            if any(s in (a.get("alvos") or []) for s in fake):
                hits_shuf += 1
        n = len(av)
        self.d["negativo"] = {
            "taxa_real": hits_real/n, "taxa_shuffle": hits_shuf/n,
            "n": n, "em": datetime.now().isoformat(timespec="seconds"),
        }
        self.save()
        suspeito = (hits_shuf/n) >= (hits_real/n) - 0.02 and (hits_real/n) > 0.35
        return {"ok": True, "taxa_real": hits_real/n, "taxa_shuffle": hits_shuf/n, "suspeito_leak": suspeito}

# ---------- LSTM ----------
if HAS_TORCH:
    class RedeSeq(nn.Module):
        def __init__(self, n):
            super().__init__()
            self.lstm = nn.LSTM(n, 64, 2, batch_first=True, dropout=0.2)
            self.fc = nn.Linear(64, n)
        def forward(self, x):
            o,_ = self.lstm(x)
            return self.fc(o[:,-1,:])

class MotorLSTM:
    def __init__(self, jogo: str, is_ct=False):
        self.jogo = jogo
        self.is_ct = is_ct
        self.n = 8 if is_ct else 37
        # o topo do LSTM trabalha sempre com o teto da faixa dele; quem apara a
        # lista para 5-10 (roleta) ou 1-3 (crazy time) e o corte por apoio
        self.k_alvos = K_MAX_CT if is_ct else K_MAX_ROLETA
        self.device = DEVICE
        self.has = HAS_TORCH
        self.limiar = 0.08 if not is_ct else 0.12
        self.treinado = False
        self.weights_path = str(ROOT / f"lstm_{jogo}.pt")
        self.temperature = 1.0
        self.load_error = None
        self.last_holdout = {}
        if self.has:
            self.m = RedeSeq(self.n).to(self.device)
            self.opt = optim.Adam(self.m.parameters(), lr=0.005)
            self.loss = nn.CrossEntropyLoss()
            self._load()

    def _load(self):
        self.load_error = None
        if self.has and os.path.isfile(self.weights_path):
            try:
                import json as _json
                man_path = self.weights_path + ".manifest.json"
                if not os.path.isfile(man_path):
                    self.load_error = "manifesto ausente — pesos ignorados (salve de novo para criar)"
                    self.treinado = False
                    return
                try:
                    man = _json.loads(open(man_path, encoding="utf-8").read())
                except Exception as e:
                    self.load_error = f"manifesto inválido: {e}"
                    self.treinado = False
                    return
                if man.get("version") and man.get("version") != PIPELINE_VERSION:
                    self.load_error = f"manifesto legado version={man.get('version')} — ignorado"
                    self.treinado = False
                    return
                st = torch.load(self.weights_path, map_location=self.device)
                ver = st.get("version")
                if ver != PIPELINE_VERSION:
                    self.load_error = f"pesos legado version={ver} (atual={PIPELINE_VERSION}) — ignorados"
                    self.treinado = False
                    return
                self.m.load_state_dict(st["model"])
                self.limiar = st.get("limiar", self.limiar)
                self.temperature = float(st.get("temperature", 1.0))
                self.treinado = True
                self._clamp_limiar()
            except Exception as e:
                self.load_error = str(e)
                self.treinado = False

    def _save(self):
        if not self.has: return
        try:
            torch.save({
                "model": self.m.state_dict(), "limiar": self.limiar,
                "temperature": self.temperature, "version": PIPELINE_VERSION,
            }, self.weights_path)
            # manifesto exigido para carga seguinte
            import json as _json
            from pathlib import Path as _P
            man = {
                "weights_path": self.weights_path,
                "jogo": getattr(self, "jogo", None),
                "version": PIPELINE_VERSION,
                "limiar": float(self.limiar),
                "temperature": float(getattr(self, "temperature", 1.0) or 1.0),
                "device": str(DEVICE) if "DEVICE" in dir() else "cpu",
            }
            _P(self.weights_path + ".manifest.json").write_text(
                _json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            # não esconder a causa
            try:
                msgs_attr = getattr(self, "_last_save_err", None)
                self._last_save_err = f"{type(e).__name__}: {e}"
            except Exception:
                pass

    def _clamp_limiar(self):
        self.limiar = float(min(0.16, max(0.04, float(self.limiar or 0.08))))

    def ajustar(self, d):
        self.limiar = max(0.04, min(0.16, self.limiar+d))


    def _enc(self, h):
        if self.is_ct: return [MAP_CT_TO_IDX[x] for x in h if x in MAP_CT_TO_IDX]
        return [x for x in h if isinstance(x,int) and 0<=x<=36]

    def _xy(self, seq, w=10):
        X,Y=[],[]
        for i in range(len(seq)-w):
            t=np.zeros((w,self.n),np.float32)
            for j,v in enumerate(seq[i:i+w]): t[j,v]=1
            X.append(t); Y.append(seq[i+w])
        if not X: return None,None
        return torch.tensor(np.array(X)).to(self.device), torch.tensor(Y,dtype=torch.long).to(self.device)

    def _otimizar_temperatura(self, logits_val, y_val):
        if logits_val is None or len(y_val)==0: return
        best_t, best_nll = 1.0, 1e9
        for t in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5]:
            p = torch.softmax(logits_val/t, dim=1)
            nll = 0.0
            for i,yi in enumerate(y_val.tolist()):
                nll += -math.log(float(p[i, yi].clamp(min=1e-8)))
            nll /= len(y_val)
            if nll < best_nll:
                best_nll, best_t = nll, t
        self.temperature = best_t

    def _reiniciar_rede(self):
        """Reinicia pesos para avaliação independente (sem herdar .pt com futuro)."""
        self.m = RedeSeq(self.n).to(self.device)
        self.opt = optim.Adam(self.m.parameters(), lr=0.005)
        self.temperature = 1.0

    def walk_forward(self, hist_recente_primeiro):
        """
        Walk-forward sem sobreposição de testes:
        blocos [train|val|test] contíguos e test de um corte não reaparece no próximo.
        Val mínima exigida; T do modelo salvo calibrada em holdout puro (últimos 10%).
        """
        if not self.has: return "sem torch", 0.0, 0.0
        d = self._enc(cronologico(hist_recente_primeiro))
        if len(d) < 50: return "dados<50", 0.0, 0.0
        w = 10
        # blocos NÃO sobrepostos: avança ponteiro
        hits_ia, hits_b, total = 0, 0, 0
        cursor = max(int(len(d)*0.35), w+15)
        fold = 0
        while cursor < int(len(d)*0.92):
            # train: tudo antes de cursor-val_size
            val_size = max(8, int((cursor) * 0.15))
            train_end = cursor - val_size
            if train_end < w+8:
                cursor += max(8, int(len(d)*0.08))
                continue
            train = d[:train_end]
            val = d[train_end:cursor]
            test_len = max(6, int(len(d)*0.08))
            test_seg = d[cursor:cursor+test_len]
            if len(test_seg) < 3:
                break
            if len(val) < w+2:
                # 2 — val pequena demais: pula calibração T fina, usa T=1.0
                temp_ok = False
            else:
                temp_ok = True
            self._reiniciar_rede()
            Xt,Yt = self._xy(train, w=w)
            if Xt is None or len(Xt)<5:
                cursor += test_len
                continue
            loader = DataLoader(TensorDataset(Xt,Yt), batch_size=16, shuffle=True)
            self.m.train()
            for _ in range(6):
                for bx,by in loader:
                    self.opt.zero_grad(); self.loss(self.m(bx),by).backward(); self.opt.step()
            self.m.eval()
            with torch.no_grad():
                if temp_ok:
                    Xv,Yv = self._xy(val, w=w)
                    if Xv is not None and len(Yv)>=3:
                        self._otimizar_temperatura(self.m(Xv), Yv)
                    else:
                        self.temperature = 1.0
                else:
                    self.temperature = 1.0
            base = [k for k,_ in Counter(train).most_common(self.k_alvos)]
            for i in range(len(test_seg)):
                past = d[:cursor] + test_seg[:i]
                if len(past) < w: continue
                seq = past[-w:]
                tarr = np.zeros((1,w,self.n), np.float32)
                for j,v in enumerate(seq): tarr[0,j,v]=1
                X = torch.tensor(tarr).to(self.device)
                with torch.no_grad():
                    pr = torch.softmax(self.m(X)[0]/max(self.temperature,1e-3), dim=0)
                    _, idx = torch.topk(pr, self.k_alvos)
                    pred = [int(x) for x in idx.tolist()]
                y = test_seg[i]
                total += 1
                if y in pred: hits_ia += 1
                if y in base: hits_b += 1
            fold += 1
            cursor += test_len  # 5 — avança sem reutilizar test
        if total == 0:
            return "WF sem pontos", 0.0, 0.0
        taxa_ia = hits_ia/total
        taxa_b = hits_b/total
        # 3/5 — holdout puro para T; se série curta, aumenta fração (até 25%) para ter >= w+3
        self._reiniciar_rede()
        hold_frac = 0.10
        if len(d) < 100:
            # garante holdout mínimo ~ w+3 pontos
            need = w + 5
            hold_frac = min(0.25, max(0.10, need / max(len(d), 1)))
        hold = int(len(d) * (1.0 - hold_frac))
        hold = min(hold, len(d) - (w + 3)) if len(d) > w + 5 else int(len(d)*0.85)
        hold = max(hold, w + 8)
        train_op = d[:hold]
        holdout = d[hold:]
        Xt,Yt = self._xy(train_op, w=w)
        if Xt is not None and len(Xt)>=5:
            loader = DataLoader(TensorDataset(Xt,Yt), batch_size=16, shuffle=True)
            self.m.train()
            for _ in range(8):
                for bx,by in loader:
                    self.opt.zero_grad(); self.loss(self.m(bx),by).backward(); self.opt.step()
            self.m.eval()
            with torch.no_grad():
                if len(holdout) > w+2:
                    Xh,Yh = self._xy(holdout, w=w)
                    if Xh is not None and len(Yh)>=2:
                        self._otimizar_temperatura(self.m(Xh), Yh)
                    else:
                        self.temperature = 1.0
                else:
                    self.temperature = 1.0
        self.treinado = True
        self._save()
        self.last_holdout = {"ia": taxa_ia, "baseline": taxa_b, "k": self.k_alvos, "T": self.temperature, "pontos": total, "folds": fold}
        return f"WF({total}pts,{fold}folds,reinit,no-overlap) IA {taxa_ia*100:.1f}% vs base {taxa_b*100:.1f}% T={self.temperature:.2f}", taxa_ia, taxa_b


    def prever_dist(self, hist_recente_primeiro):
        if not self.has or not self.treinado:
            c=Counter(hist_recente_primeiro[:30])
            tops=[k for k,_ in c.most_common(self.k_alvos)]
            return tops, 0.05, {t:0.05 for t in tops}, "FALLBACK_NAO_LSTM", {"is_lstm": False}
        d=self._enc(cronologico(hist_recente_primeiro))
        if len(d)<10: return [], 0.0, {}, "curto", {"is_lstm": False}
        seq=d[-10:]
        t=np.zeros((1,10,self.n),np.float32)
        for j,v in enumerate(seq): t[0,j,v]=1
        X=torch.tensor(t).to(self.device)
        self.m.eval()
        with torch.no_grad():
            logits = self.m(X)[0]
            probs = torch.softmax(logits/max(self.temperature,1e-3), dim=0)
            pmax=float(torch.max(probs))
            influ_steps=[]
            base_top=pmax
            for step in range(10):
                t2=t.copy(); t2[0,step,:]=0
                pr2=torch.softmax(self.m(torch.tensor(t2).to(self.device))[0]/max(self.temperature,1e-3), dim=0)
                influ_steps.append(round(base_top-float(torch.max(pr2)),4))
            if pmax < self.limiar:
                dist={(MAP_IDX_TO_CT[i] if self.is_ct else i): float(probs[i]) for i in range(self.n)}
                return [], pmax, dist, f"SEM EVIDÊNCIA ({pmax*100:.1f}%<{self.limiar*100:.1f}%)", {"steps":influ_steps,"is_lstm":True}
            pv, idx = torch.topk(probs, self.k_alvos)
            alvos=[]; dist={}
            for i in range(self.k_alvos):
                ix=idx[i].item()
                a = MAP_IDX_TO_CT[ix] if self.is_ct else ix
                alvos.append(a); dist[a]=float(pv[i])
            return alvos, pmax, dist, f"LSTM OK {pmax*100:.1f}% T={self.temperature:.2f}", {"steps":influ_steps,"top":dist,"is_lstm":True}

class MetaSupervisora:
    def __init__(self):
        self._last_total = -1
    def educar(self, ok, err, brier=None, limiar_atual=0.08, ganho=None, n_avaliadas=0, modelo_ativo=True, taxa_janela=None):
        # unidade principal = JANELA (taxa_janela / n_avaliadas); ok/err só auxiliar
        cmd={"limiar_delta":0.0,"janela_mod":0,"desativar_modelo":False,"reativar_modelo":False}
        if taxa_janela is not None and n_avaliadas > 0:
            taxa = taxa_janela * 100
            msg = f"Taxa janela {taxa:.1f}% (n={n_avaliadas})."
            ref_n = n_avaliadas
        else:
            # `ok` e `err` sao CONTAGENS, mas nem todo chamador tem essa
            # disciplina -- um deles passava o sucesso da captura (booleano) e
            # a mensagem de erro (None). `True + None` estoura, e o estouro
            # levava o ciclo inteiro da mesa junto.
            ok = int(ok or 0) if not isinstance(ok, bool) else int(ok)
            err = int(err or 0) if not isinstance(err, bool) else int(err)
            total = ok + err
            taxa = (ok/total*100) if total else 100.0
            msg = f"Taxa evento {taxa:.1f}% ({ok}/{total}) [provisório]."
            ref_n = total
        novos = ref_n > self._last_total
        if not novos:
            msg += " sem novas janelas — estável."
            return cmd, msg
        self._last_total = ref_n
        if ref_n>=5 and taxa<30:
            msg+=" CRÍTICO <30%."
            if limiar_atual < 0.15: cmd["limiar_delta"]=0.01
            cmd["janela_mod"]=-1
        elif ref_n>=5 and taxa>=45:
            msg+=" Acima da meta."; cmd["limiar_delta"]=-0.01; cmd["janela_mod"]=1
        if brier is not None and brier>0.25 and limiar_atual < 0.15:
            cmd["limiar_delta"]+=0.01; msg+=f" Brier~janela {brier:.2f} (approx)."
        if ganho is not None and ganho < -0.03 and n_avaliadas >= 20 and modelo_ativo:
            msg += f" ganho {ganho:.3f} n={n_avaliadas} — desativar."
            cmd["desativar_modelo"] = True
        if ganho is not None and ganho > 0.0 and n_avaliadas >= 20 and not modelo_ativo:
            msg += f" ganho {ganho:.3f} — reativar."
            cmd["reativar_modelo"] = True
        # reativação exploratória a cada 30 janelas mesmo com ganho levemente negativo
        if not modelo_ativo and n_avaliadas >= 30 and n_avaliadas % 30 == 0:
            msg += " reativação exploratória periódica."
            cmd["reativar_modelo"] = True
        return cmd, msg

# ═══════════════════════════════════════════════════ MODO CONSENSO PURO
#
# Decisão do operador, 15/08/2026: a sugestão sai do CRUZAMENTO DAS TEORIAS e
# de mais nada. As guardas estatísticas que eu tinha posto por cima — ganho
# contra o baseline, calibração do LSTM, taxa medida contra o acaso — deixam de
# poder calar o consenso.
#
# O que NÃO some, porque não é régua minha e sim o próprio consenso:
#   - o número precisa de MIN_TEORIAS_CONSENSO teorias distintas concordando
#   - sem esse acordo, a tela continua dizendo AGUARDANDO
# Sem isso não existiria consenso, existiria palpite de uma fonte só.
#
# O que continua rodando por trás, sem bloquear: a sombra prospectiva, que mede
# cada teoria ao vivo. Ela deixa de ser porteiro e passa a ser só medida — é o
# que permite dizer depois quais teorias estão puxando o resultado para cima.
#
# PARA VOLTAR ATRÁS: troque para False nesta linha e pronto. Nada foi apagado;
# as guardas continuam escritas logo abaixo e voltam a valer inteiras. Rode o
# RESULTADO.bat antes e depois para comparar as duas com o mesmo critério.
# O CACADOR DE MULTIPLICADOR DECIDE SOZINHO, SEM REGUA.
#
#     "deixar somente o Cacador de Multiplicador escolhendo os numeros para
#      todos os jogos, sem regua para ele"
#
# Decisao dele, tomada com dado na mao: foi o Cacador que ele viu acertando
# ("o cacador de multiplicador esta acertando bastante"), e as 18 previsoes
# reais da maquina dele deram 8 acertos contra acaso de 22,2%.
#
# Com isto ligado, os numeros da tela saem DIRETO das sete IAs de
# multiplicador. Nao passam pelo consenso, nem pelo minimo de vozes
# independentes, nem pelo corte por apoio, nem por nenhum gate meu. Ele foi
# explicito: sem regua para ele.
#
# O resto continua sendo calculado e aparecendo no log -- as leituras do
# Tratado, os especialistas, a academia. Elas informam, mas nao mandam mais.
CACADOR_DECIDE = True

CONSENSO_PURO = True

# QUANTAS VOZES INDEPENDENTES ABREM UMA JANELA.
#
# Nao e quantas fontes falaram -- e quantas OPINIOES DIFERENTES existem entre
# elas (ficha 226 do compendio dele). Quatro fontes que leem o mesmo atraso
# valem uma voz, e uma voz nao e consenso.
#
# Com 2.0, a mesa passa a ficar em AGUARDANDO quando so ha eco. Foi o que
# faltava: medido no log dele, o software abria janela a cada 3,5 giros com
# janelas de 3 a 4 -- nunca parava de apostar.
MIN_VOZES_INDEPENDENTES = 2.0

# E o mínimo por NÚMERO, que é outra pergunta.
#
# O acima decide se a mesa abre aposta; este decide se um número específico
# entra nela. Antes só o primeiro colocado era conferido, e a aprovação dele
# valia para a lista inteira — números com uma fonte única entravam de carona.
#
# O valor é 1.0 e não 2.0 porque `n_efetivo` desconta correlação: duas fontes
# honestas com listas quase disjuntas dão 1,67, não 2. Cobrar 2,0 de cada
# candidato esvaziaria a lista quase sempre. Acima de 1,0 quer dizer o que o
# defeito pedia: mais de uma voz, e vozes que não sejam a mesma evidência
# contada duas vezes.
MIN_VOZES_POR_NUMERO = 1.0

# Teto da janela de apostas. Era 3, fixo no meio do código; ele pediu 5.
JANELA_MAX = 5

# QUANTOS NÚMEROS SAEM POR MESA — a faixa é dele.
#
#     "a partir de agora é de 5 a 10 números na roleta"
#     "os dois crazy times são de 1 a 3 opções"
#
# Dentro da faixa quem decide é o apoio na votação: entra quem tem peso
# comparável ao primeiro colocado (FRACAO_APOIO). Assim uma noite de consenso
# forte sai com lista curta e uma de consenso espalhado sai mais larga, sem
# ninguém arbitrar um número redondo por fora.
K_MIN_ROLETA, K_MAX_ROLETA = 5, 10
K_MIN_CT, K_MAX_CT = 1, 3
FRACAO_APOIO = 0.5

# ─────────────────────────────────────────── o piso de acerto que ele pediu
#
#     "deixe o mínimo de acerto de numeros e janelas em 53%"
#
# As duas metades desse pedido têm respostas diferentes, e a conta é curta:
#
#   JANELA  o número sair em ALGUM giro da janela. Chance = 1-(1-k/37)^j.
#           Com janela de 5, seis números já dão 58,7%. Cabe folgado na faixa
#           de 5 a 10 que ele fixou, então o software passa a garantir isso
#           sozinho: escolhe o menor k que alcança o piso.
#
#   NÚMERO  o número sair NAQUELE giro. Chance = k/37, e não tem jeito de
#           contornar: 53% exige 20 números dos 37. Com os 10 do teto dele o
#           máximo possível é 27%, e chegar a 53% pediria vantagem de 1,96x
#           sobre o acaso — a melhor já medida no log real foi 1,09x.
#
# Por isso o piso de janela é automático e o de número é uma ESCOLHA dele,
# desligada por padrão. Ligar COBERTURA_LARGA sobe a roleta para 20 números e
# entrega os 53% de acerto por giro — sabendo que o que muda é o tamanho da
# aposta, não a pontaria. O placar continua mostrando os dois números lado a
# lado, e é a razão contra o acaso que diz se houve ganho.
ALVO_ACERTO_JANELA = 0.53

# ─────────────────────────────────────────── o que o Crazy Time deve perseguir
#
# MEDIDO NOS LOGS DELE, e os numeros contam a historia toda:
#
#     v104   apostou no "5" em 58 de 60 janelas   ->  0,99x
#     v105   apostou em CoinFlip/Pachinko/CashHunt ->  0,89x
#
# Eu consertei o travamento no "5" e a mesa travou nos bonus. Trocou de preso,
# nao soltou -- porque a causa e a mesma nos dois casos: o eixo do ATRASO
# domina, e numa roda de 54 fatias desiguais quem tem poucas fatias esta quase
# sempre "atrasado".
#
# Aqui eu paro de escolher por ele. Sao dois objetivos legitimos e diferentes,
# e a conta de cada um e esta:
#
#   "acerto"   o software persegue ACERTAR. O peso do atraso cai e as fontes
#              que leem o que esta saindo mandam mais. A mesa vai sugerir 1 e 2
#              com frequencia -- que sao 63% da roda e pagam pouco.
#
#   "bonus"    o software persegue os MULTIPLICADORES GRANDES. O atraso manda,
#              como estava. Vai errar muito -- Pachinko sai 3,7% das vezes --
#              em troca de estar la quando sair.
#
# Nenhum dos dois e "certo". O que estava errado era eu decidir isso por fora
# sem dizer que estava decidindo.
# ELE DISSE, E E ELE QUEM SABE:
#
#     "sinal para o crazy time e somente o que ta muito tempo sem vir"
#
# Entao o atraso MANDA nesta mesa, e para de ser discussao. Eu tinha deixado
# em "acerto" achando que fazia sentido porque o placar mede acerto -- mas o
# criterio de quem olha a mesa vale mais que a coerencia do meu placar.
CT_OBJETIVO = "atraso"
CT_PESO_ATRASO = {"acerto": 0.55, "atraso": 1.0, "bonus": 1.0}

# O PISO DE ACERTO DE NÚMERO, TAMBÉM EM 53% — ele reafirmou o pedido.
#
# Aqui não há margem de esperteza: acerto de número por giro é k/37, e 53%
# exige 20 números. Foi o que ele decidiu depois de ver a conta, então está
# LIGADO. A roleta passa a jogar com 20 números.
#
# O que isso é, dito sem rodeio: cobertura, não pontaria. O acerto por giro vai
# a ~54% e o de janela a ~98%, e nenhum dos dois significa que o software
# aprendeu algo — significa que a aposta ficou larga. Quem responde "estamos
# ganhando?" continua sendo a razão contra o acaso da MESMA aposta, que o
# placar mostra do lado, e que é 1,00x quando não há vantagem nenhuma.
#
# PARA VOLTAR À FAIXA DE 5 A 10: troque para False nesta linha. Nada mais
# precisa mudar; o piso de janela continua valendo e a lista volta a ser curta.
COBERTURA_LARGA = True
ALVO_ACERTO_NUMERO = 0.53

# ELE VIU 20 NA TELA E DECIDIU 12.
#
#     "Mas 20 números é demais, deixe até 12"
#
# É decisão dele, e a conta muda junto -- 12 números nao alcancam os 53% de
# acerto POR GIRO (12/37 = 32,4%), so os de JANELA:
#
#     acerto de NUMERO por giro       32,4%
#     acerto de JANELA em 3 giros     69,2%
#     acerto de JANELA em 5 giros     85,9%
#
# O piso de janela continua cumprido com folga. O de numero deixou de ser
# alcancavel, e isso esta dito aqui em vez de fingido no placar.
K_COBERTURA_LARGA = 12


def k_para_alvo_numero(alvo: float, n_classes: int) -> int:
    """Quantos números o acerto POR GIRO exige. Sem janela, sem conversa."""
    import math
    return max(1, min(n_classes, math.ceil(alvo * n_classes)))


def k_para_alvo(janela: int, alvo: float, n_classes: int, teto: int) -> int:
    """O menor k cuja janela alcança o alvo. Nunca passa do teto."""
    j = max(1, int(janela or 1))
    for k in range(1, teto + 1):
        if 1.0 - (1.0 - k / max(1, n_classes)) ** j >= alvo:
            return k
    return teto


def cortar_por_apoio(ordenados, score, k_min, k_max):
    """Quantos números a votação sustenta, dentro da faixa que ele fixou.

    Nada é barrado: o corte só decide onde a lista termina. Abaixo de k_min
    completa com os próximos mais votados — lista curta demais devolveria uma
    faixa que ele não pediu.
    """
    ordenados = list(ordenados or [])
    if not ordenados:
        return []
    topo = float((score or {}).get(ordenados[0], 0) or 0)
    if topo <= 0:
        return ordenados[:k_max]
    fortes = [n for n in ordenados[:k_max]
              if float((score or {}).get(n, 0) or 0) >= topo * FRACAO_APOIO]
    if len(fortes) < k_min:
        for n in ordenados[:k_max]:
            if n not in fortes:
                fortes.append(n)
            if len(fortes) >= k_min:
                break
    return fortes[:k_max]

# As famílias de finais que ele ensinou: 0,1,3,6 · 0,2,7,8 · 4,5,9.
# O zero pertence a duas, e nos exemplos dele as duas valem — "veio 20 e logo
# depois o 2" usa (0,2,7,8), "veio 1 e logo depois 21" usa (0,1,3,6). Por isso
# a união, e não a primeira que casar.
FAMILIAS_FINAIS = ((0, 1, 3, 6), (0, 2, 7, 8), (4, 5, 9))


def _familia_completa(x: int) -> list:
    """Todos os números da mesa cujo final está na família do final de `x`."""
    try:
        f = int(x) % 10
    except (TypeError, ValueError):
        return []
    finais = set()
    for g in FAMILIAS_FINAIS:
        if f in g:
            finais |= set(g)
    if not finais:
        return []
    return sorted(y for y in range(37) if y % 10 in finais)


class PipelinePerceptivo:
    # Quantas teorias DISTINTAS precisam concordar para o número entrar.
    #
    # Decisão dele, 15/08: "não critique e nem barre". Uma teoria declarada
    # basta. As regras dele — família de finais e a tabela de transições —
    # disparam sozinhas, sem precisar que outra fonte concorde antes.
    #
    # Quem tiver mais concordância continua vindo na frente, porque o consenso
    # ordena por peso somado. O que muda é que ninguém fica de fora esperando
    # companhia.
    MIN_TEORIAS_SOZINHO = 1

    def __init__(self, jogo: str = "mega_fire"):
        self.jogo = jogo
        self.is_ct = str(jogo).startswith("crazy_time")
        self.qual = QualidadeDados()
        self.ctx = Contexto()
        self.perc = Percepcao()
        self.m_est = ModeloEstatistico()
        self.m_anom = ModeloAnomalia()
        self.m_setor = ModeloSetor()
        self.baseline = BaselineFrequencia()
        self.ger = GeradorHipoteses()
        self.crit = Critico()
        self.mem = Memoria(jogo)
        self.lstm = MotorLSTM(jogo, is_ct=self.is_ct)
        self.meta = MetaSupervisora()
        self.ciclos = 0
        self.n_classes = 8 if self.is_ct else 37
        # QUANTOS NÚMEROS SAEM — E QUEM DECIDE ISSO.
        #
        # Ele fixou a faixa: "de 5 a 10 números na roleta", "os dois crazy
        # times são de 1 a 3 opções". Dentro da faixa quem decide é o apoio da
        # votação, não um número redondo meu: entra quem tem peso comparável ao
        # primeiro colocado. Consenso apertado sai enxuto, consenso largo sai
        # largo, e o acaso da aposta é recalculado com o k que de fato saiu —
        # senão aumentar a lista viraria "melhora" de mentira no placar.
        self.k_min = K_MIN_CT if self.is_ct else K_MIN_ROLETA
        self.k_max = K_MAX_CT if self.is_ct else K_MAX_ROLETA
        # cobertura larga: escolha dele, desligada por padrao (ver o comentario
        # em COBERTURA_LARGA). So faz sentido na roleta -- no crazy time sao 8
        # simbolos e cobrir 20 nao existe.
        if COBERTURA_LARGA and not self.is_ct:
            # o k que o piso de acerto POR GIRO exige (53% -> 20 de 37)
            # o teto e o dele; k_para_alvo_numero fica como referencia do que
            # os 53% por giro exigiriam (20), para o placar poder dizer.
            self.k_min = self.k_max = K_COBERTURA_LARGA
        self.k_alvos = self.k_max
        self.prefs = {"peso_isol":1.0,"boost_anti":False,"prioritizar_atraso":False,"reduzir_12":False,"janela":None}

    @staticmethod
    def _mult_por_giro(linhas, quantos: int) -> list:
        """O multiplicador QUE PAGOU em cada giro, alinhado giro a giro.

        DOIS FORMATOS COM O MESMO NOME.
        -------------------------------
        `mults`, como a captura monta, é a lista de ANÚNCIOS: um item por
        número anunciado, `{"n": 12, "x": 50}`, com tamanho variável e sem
        relação de posição com os giros — um giro pode anunciar cinco números
        e o seguinte nenhum.

        Só que a IA de intensidade do tratado dele faz `zip(seq, mults)` e
        `float(m)`. Ela espera o outro formato: um valor por giro, na mesma
        ordem dos giros, zero quando não pagou.

        Com o formato errado, o `zip` casava o giro 0 com o anúncio 0 (que
        pode ser de qualquer giro), e o `float()` de um dicionário estourava e
        era engolido pelo `except`. A metade da magnitude do modelo hurdle
        ficava sempre vazia, e a metade da existência contava sobre um
        denominador que não era o número de giros. Nada disso aparecia: a
        inteligência simplesmente devolvia pouco, como se a mesa fosse pobre.

        Aqui o valor sai das `linhas`, que é onde a informação realmente está:
        para cada giro, o maior multiplicador cujo número anunciado é o número
        que saiu. Anúncio que não bateu vale 0 — porque não pagou.
        """
        saida = []
        for r in (linhas or [])[:quantos]:
            if not isinstance(r, dict):
                saida.append(0.0)
                continue
            saiu = str(r.get("n", r.get("sec")))
            melhor = 0.0
            for t in (r.get("tags") or []):
                if not isinstance(t, dict):
                    continue
                for canal in ("lucky", "fire_nums"):
                    for it in (t.get(canal) or []):
                        if (isinstance(it, dict) and it.get("x")
                                and str(it.get("n")) == saiu):
                            try:
                                melhor = max(melhor, float(it["x"]))
                            except (TypeError, ValueError):
                                pass
                # o top slot do Crazy Time só paga quando o símbolo bate
                top = t.get("top")
                if isinstance(top, dict) and top.get("x") and \
                        str(top.get("simbolo")) == saiu:
                    try:
                        melhor = max(melhor, float(top["x"]))
                    except (TypeError, ValueError):
                        pass
                if not (t.keys() - {"x"}) and t.get("x"):
                    try:
                        melhor = max(melhor, float(t["x"]))
                    except (TypeError, ValueError):
                        pass
            saida.append(melhor)
        return saida

    def _perda_do_tratado(self, saiu) -> None:
        """Cobra de cada inteligência o palpite que ela deu na volta passada.

        A perda é a de log restrita ao palpite: quem apontou o número que saiu
        paga pouco, quem não apontou paga o teto. É a mesma escala para todas,
        então `exp(-η·Loss)` compara laranja com laranja.

        Nada é cobrado de quem calou -- a inteligência que não opinou naquela
        volta não errou nela. (É a F46 dele: vigília. Perda só conta quando a
        fonte estava acordada.)
        """
        if saiu is None:
            return
        palpites = getattr(self, "_palpites_tratado", None) or {}
        if not palpites:
            return
        alvo = str(saiu)
        perdas = getattr(self, "_perdas_tratado", None)
        if perdas is None:
            perdas = self._perdas_tratado = {}
        for nome, nums in palpites.items():
            lista = [str(x) for x in (nums or [])]
            if not lista:
                continue
            if alvo in lista:
                # acertou: paga o preço de ter apontado k números em vez de um
                perdas[nome] = perdas.get(nome, 0.0) + math.log(len(lista))
            else:
                perdas[nome] = perdas.get(nome, 0.0) + math.log(
                    max(2, self.n_classes))
        self._palpites_tratado = {}

    def processar(self, historico, ok, err, settled=None, mults=None, last_result=None, active_selection=None, linhas=None):
        # zera o palpite do Cacador a cada volta: sem isto ele repetiria o da
        # volta anterior quando a captura nao trouxesse linhas, e a tela
        # mostraria numero velho como se fosse novo
        self._cacador_consenso = []
        self._cacador_por_ia = {}
        t0=time.time(); msgs=[]
        # limiar nunca permanece inflado de sessões antigas
        try:
            self.lstm.limiar = float(min(0.16, max(0.04, float(self.lstm.limiar or 0.08))))
        except Exception:
            self.lstm.limiar = 0.08
        msgs.append(f"[Versão] pipeline={PIPELINE_VERSION} features={FEATURE_VERSION} jogo={self.jogo}")

        
        # --- 12 agentes de descoberta → Crítico → META → Biblioteca ---
        fab_res = {"candidatos": [], "msgs": [], "n_propostas": 0}
        self._fab_cands = []
        try:
            if ciclo_academia_autonoma is not None:
                _hist_fab = historico if historico is not None else []
                _ar = ciclo_academia_autonoma(self.jogo, _hist_fab, settled=settled, mults=mults)
                for _m in _ar.get("msgs") or []:
                    msgs.append(_m)
                self._fab_cands = list(_ar.get("candidatos") or [])
            elif False and ciclo_descoberta is not None:
                # legado desativado (stub); autoridade = academia_autonoma
                pass
            elif fabricar_para is not None:
                _hist_fab = historico if historico is not None else []
                # prefixo, não igualdade: a Crazy Time A pegava 7 alvos numa
                # mesa de 8 símbolos -- quase a roda inteira
                _maxk = 3 if self.is_ct else 7
                fr = fabricar_para(self.jogo, _hist_fab, mults=mults, max_k=_maxk)
                for _m in fr.get("msgs") or []:
                    msgs.append(_m)
                self._fab_cands = list(fr.get("candidatos") or [])
        except Exception as _e:
            msgs.append(f"[Descoberta] erro: {_e}")
            self._fab_cands = []
        except Exception as _e:
            msgs.append(f"[Fabricante] erro: {_e}")
            self._fab_cands = []


        ordens = ler_ordens(self.jogo)
        if ordens.get("_pendente"):
            msgs.append(f"[Ordens] NOVA={ {k:ordens[k] for k in ('janela','peso_isol','peso_motor','boost_anti','prioritizar_atraso','reduzir_12','motivo') if ordens.get(k) is not None} }")
            if not marcar_ordem_aplicada(self.jogo):
                msgs.append("[Ordens] aviso: não foi possível marcar aplicada (lock/disco)")
            if ordens.get("peso_motor") is not None:
                try: self.lstm.limiar = max(0.04, min(0.16, self.lstm.limiar - 0.01*float(ordens["peso_motor"])/3))
                except Exception: pass
        elif ordens.get("_ja_aplicada"):
            msgs.append(f"[Ordens] estáveis motivo={ordens.get('motivo')}")

        for key in ("peso_isol","boost_anti","prioritizar_atraso","reduzir_12","janela"):
            if ordens.get(key) is not None:
                self.prefs[key] = ordens[key]
        w_isol = float(self.prefs.get("peso_isol") or 1.0)
        boost_anti = bool(self.prefs.get("boost_anti"))
        prior_atraso = bool(self.prefs.get("prioritizar_atraso"))

        if last_result is not None:
            window_done = bool(last_result.get("window_done"))  # NÃO usar acertou — horizonte fixo
            aval = self.mem.avaliar_ultima(
                last_result.get("saiu"), last_result.get("acertou"),
                settled_result=last_result.get("settled"), window_done=window_done,
            )
            if isinstance(aval, dict) and aval.get("ignored"):
                msgs.append(f"[Memória] anti-leak: {aval.get('reason')}")
            elif isinstance(aval, dict) and aval.get("open"):
                msgs.append(f"[Memória] janela aberta id={aval.get('id')} h={aval.get('hits')} m={aval.get('misses')}")
            elif aval:
                msgs.append(f"[Memória] FECHOU id={aval.get('id')} acertou={(aval.get('resultado') or {}).get('acertou')}")
            # A PERDA DE CADA INTELIGÊNCIA — é o que a IA12 dele precisa.
            #
            # A décima segunda inteligência do tratado é a agregação:
            # w_(j,t) ∝ exp(-η·Loss_j). Ela não lê a mesa, ela pesa as outras
            # onze pelo que cada uma acumulou de erro. Sem contar essa perda,
            # `pesos_ia12` devolve peso igual para todas e a fórmula dele vira
            # média simples -- que é exatamente o que ela existe para não ser.
            self._perda_do_tratado(last_result.get("saiu"))

        hist, hist_set, rep = self.qual.validar(historico, settled, is_ct=self.is_ct)
        msgs.append(f"[Qualidade] n={rep['n']} dup={rep['duplicados']} inv={rep['invalidos']} ordem_ok={rep['ordem_ok']} corr={rep['ordem_corrigida']}")
        if rep.get("interrompeu"):
            return self._aguardar(msgs, "ordem temporal inválida", settled=settled, n_hist=len(historico or []))
        # Sombra/OPERAR: encerra janelas no motor (não depende de pad5/UI)
        try:
            fechadas = self.mem.avancar_pendentes_stream(hist, hist_set or settled)
            for u in fechadas:
                r = u.get("resultado") or {}
                msgs.append(
                    f"[Memória/stream] FECHOU id={u.get('id')} modo={u.get('modo')} "
                    f"acertou={r.get('acertou')} spins={r.get('spins_n')}"
                )
        except Exception as e:
            msgs.append(f"[Memória/stream] erro: {e}")
        if len(hist) < (8 if self.is_ct else 10):
            return self._aguardar(msgs, "dados insuficientes", settled=settled, n_hist=len(hist) if hist is not None else len(historico or []))

        rel = self.mem.relatorio_metricas()
        ganho = rel.get("ganho")
        cmd, msg_m = self.meta.educar(
            ok, err, rel.get("brier"), self.lstm.limiar, ganho,
            n_avaliadas=int(rel.get("n") or 0),
            modelo_ativo=bool(self.mem.modelo_ativo_atual()),
            taxa_janela=rel.get("taxa"),
        )
        self.lstm.ajustar(cmd["limiar_delta"])
        # A REATIVAÇÃO EXPLORATÓRIA PRECISA DE UMA JANELA PARA EXISTIR.
        #
        # As duas regras se anulavam: a exploratória religava o modelo a cada
        # 30 janelas, e a regra de ganho negativo o desligava no ciclo
        # seguinte, antes de qualquer medição nova. Medido nos 205 giros reais
        # de Lightning: o modelo desativou em n=118 e ficou desligado nos 144
        # ciclos, com ZERO trocas de estado. A válvula de escape existia no
        # papel e nunca produziu um único dado.
        #
        # Agora a reativação vem com carência: por CARENCIA_CICLOS ciclos o
        # desligamento fica suspenso, e o modelo tem chance de mostrar o que
        # faz. Isso não afrouxa o critério — passada a carência, se o ganho
        # continuar negativo ele desliga de novo, agora com medição de
        # verdade por trás. O que muda é a decisão passar a ser tomada sobre
        # dado novo em vez de sobre a lembrança do dado velho.
        # 12 e nao 25: a reativacao vem a cada 30 janelas, entao carencia de 25
        # deixaria o modelo ligado ~83% do tempo mesmo perdendo -- consertar a
        # valvula nao pode desligar a protecao junto. Com 12, ele ganha um teste
        # real de 12 janelas e passa a maior parte do tempo fora quando perde.
        # A carência precisa de par: sem QUARENTENA, o desligado voltava rápido
        # demais. Medido: com carência 12 e reativação a cada 30 janelas, o
        # modelo ficava fora em só 13% dos ciclos, ou seja publicava 87% do
        # tempo perdendo para o baseline. O desligamento pegava num ciclo
        # isolado e a próxima reativação vinha logo em seguida.
        #
        # Com o par, o ciclo fica honesto: fora por QUARENTENA, dentro por
        # CARENCIA para provar, e então julgado de novo. Perdendo, passa a
        # maior parte do tempo fora; melhorando, o teste vem de qualquer jeito.
        CARENCIA_CICLOS = 12
        QUARENTENA_CICLOS = 30
        _carencia = int(getattr(self, "_carencia_modelo", 0) or 0)
        _quarentena = int(getattr(self, "_quarentena_modelo", 0) or 0)
        if _quarentena > 0:
            self._quarentena_modelo = _quarentena - 1
            cmd["reativar_modelo"] = False      # ainda cumprindo pena
        if cmd.get("reativar_modelo"):
            self.mem.set_modelo_ativo(True)
            self._carencia_modelo = CARENCIA_CICLOS
            msgs.append(f"[Meta] MODELO REATIVADO — carência de {CARENCIA_CICLOS} "
                        f"ciclos para provar")
        elif cmd.get("desativar_modelo"):
            if _carencia > 0:
                self._carencia_modelo = _carencia - 1
                msgs.append(f"[Meta] ganho negativo, mas em carência "
                            f"({_carencia} ciclos restantes) — segue ativo")
            else:
                self.mem.set_modelo_ativo(False)
                self._quarentena_modelo = QUARENTENA_CICLOS
                msgs.append(f"[Meta] MODELO DESATIVADO — ganho negativo n>=20, "
                            f"quarentena de {QUARENTENA_CICLOS} ciclos")
        elif _carencia > 0:
            self._carencia_modelo = _carencia - 1
        msgs.append(f"[Meta] {msg_m} limiar={self.lstm.limiar:.3f}")

        # métricas no feed
        if rel.get("n"):
            ic = rel.get("ic95") or (0,0)
            msgs.append(
                f"[Métricas] n={rel['n']} taxa={None if rel['taxa'] is None else round(rel['taxa']*100,1)}% "
                f"IC95=[{ic[0]*100:.1f}%,{ic[1]*100:.1f}%] "
                f"Brier={rel.get('brier')} logloss={rel.get('logloss')} "
                f"cob={None if rel.get('cobertura') is None else round(rel['cobertura']*100,1)}% "
                f"base={rel.get('taxa_baseline')} ganho={rel.get('ganho')} ag={rel.get('n_aguardando')}"
            )

        fat=self.ctx.fatias(hist)
        mudou, ov, info = self.ctx.mudanca_regime(hist)
        msgs.append(f"[Contexto] c={len(fat['curta'])} m={len(fat['media'])} l={len(fat['longa'])} regime={mudou} ({info})")
        is_new, sim = self.mem.novidade(hist)
        msgs.append(f"[Novidade] nova={is_new} sim={sim:.2f}")

        self.ciclos += 1
        lstm_vs_base=None
        precisa = self.lstm.has and ((not self.lstm.treinado) or (self.ciclos % 5 == 0))
        if precisa:
            t1=time.time()
            msg_tr,tia,tb = self.lstm.walk_forward(hist)
            lstm_vs_base = tia-tb
            self.mem.log_modulo("LSTM_WF", tia, (time.time()-t1)*1000, msg_tr)
            msgs.append(f"[WalkForward] {msg_tr}")
            if self.ciclos % 15 == 0:
                neg = self.mem.teste_negativo(self.k_alvos)
                msgs.append(f"[TesteNegativo] {neg}")

        t1=time.time()
        if self.is_ct:
            feats=self.perc.ct(hist)
            t_e=time.time(); est=self.m_est.rank_ct(feats, prior_atraso, w_isol); self.mem.log_modulo("ESTAT", est[2], (time.time()-t_e)*1000)
            t_a=time.time(); anom=self.m_anom.rank_ct(feats, boost_anti); self.mem.log_modulo("ANOMALIA", anom[1], (time.time()-t_a)*1000)
            t_s=time.time(); setor=self.m_setor.rank_ct(feats); self.mem.log_modulo("SETOR", setor[2], (time.time()-t_s)*1000)
            ranks={"estat":est,"anom":anom,"setor":setor}
            hips=self.ger.ct(feats, ranks)
        else:
            feats=self.perc.roleta(hist, mults=mults)
            t_e=time.time(); est=self.m_est.rank_roleta(feats, prior_atraso, w_isol); self.mem.log_modulo("ESTAT", est[2], (time.time()-t_e)*1000)
            t_a=time.time(); anom=self.m_anom.rank_roleta(feats, boost_anti); self.mem.log_modulo("ANOMALIA", anom[1], (time.time()-t_a)*1000)
            t_s=time.time(); setor=self.m_setor.rank_roleta(feats); self.mem.log_modulo("SETOR", setor[2], (time.time()-t_s)*1000)
            ranks={"estat":est,"anom":anom,"setor":setor}
            hips=self.ger.roleta(feats, ranks)
            if mudou:
                for h in hips:
                    if h["nome"]=="ESTAT": h["peso"]*=0.7
        self.mem.log_modulo("Percepcao", 1.0, (time.time()-t1)*1000, feats.get("feature_version"))
        msgs.append(f"[Features] version={feats.get('feature_version')} keys={list(feats.keys())[:8]}")

        # 6 — percepcao_lab como produtor de features/hipóteses AUDITÁVEIS (peso moderado)
        lab_items = []
        if HAS_PLAB:
            try:
                if self.is_ct:
                    for fn in (getattr(PLAB, "ag_ct_atraso", None), getattr(PLAB, "ag_ct_quente", None)):
                        if callable(fn):
                            lab_items.extend(PLAB.normaliza(fn(hist)))
                else:
                    for fn_name in ("ag_final_dominante", "ag_atrasados", "ag_ausentes", "ag_setor_roda", "ag_vizinhos_ultimo", "ag_markov"):
                        fn = getattr(PLAB, fn_name, None)
                        if callable(fn):
                            lab_items.extend(PLAB.normaliza(fn(hist)))
                pad, hip, anti = PLAB.classificar(lab_items)
                lab_items = (pad + hip + anti)[:12]
                msgs.append(f"[LabExterno] itens={len(lab_items)} nomes={[it.get('nome') for it in lab_items[:6]]}")
            except Exception as e:
                msgs.append(f"[LabExterno] erro: {e}")
                lab_items = []
        else:
            msgs.append("[LabExterno] percepcao_lab indisponível")

        # ESTUDO INDEPENDENTE (12 agentes) → biblioteca → hipóteses de entrada
        estudo_items = []
        if HAS_ESTUDO:
            try:
                ESTUDO.estudar(self.jogo, hist, mults=mults if not self.is_ct else None)
                estudo_items = ESTUDO.ler_estudos(self.jogo)
                msgs.append(
                    f"[EstudoIndep] publicados={len(estudo_items)} "
                    f"ids={[it.get('id') for it in estudo_items[:6]]}"
                )
            except Exception as e:
                msgs.append(f"[EstudoIndep] erro: {e}")
                estudo_items = []
        else:
            msgs.append("[EstudoIndep] estudo_lab indisponível")

        # Academia: pesquisadores → crítico → META → biblioteca validada → motor
        validado = []
        if HAS_ACADEMIA:
            try:
                # Pipeline NÃO executa ciclo — somente consulta (serviço acadêmico é a autoridade)
                # reaproveita CT_SETORES (já definido no topo do arquivo) em vez de
                # redigitar a lista — evitava o typo "CrazyTime" (nome errado; o
                # setor bônus real se chama "CrazyBonus", igual a schema_eventos.CT_DOMAIN)
                dominio_ac = (
                    list(CT_SETORES) if self.is_ct else [str(i) for i in range(37)]
                )
                hist_ac = [str(x) for x in (hist or [])]
                validado = ACADEMIA.conhecimento_validado_para_motor(
                    self.jogo, hist=hist_ac, dominio=dominio_ac
                )
                import academia_db as _ADB
                n_teste = len(_ADB.list_hipoteses(self.jogo, "em_teste"))
                n_rej = len(_ADB.list_hipoteses(self.jogo, "rejeitada"))
                mon = _ADB.get_monitor(self.jogo) or {}
                meta = _ADB.get_meta(self.jogo) or {}
                msgs.append(
                    f"[Academia/consulta] validados={len(validado)} em_teste={n_teste} "
                    f"rejeitadas={n_rej} meta={meta.get('ultima') or meta.get('estado')} "
                    f"monitor_ms={mon.get('ultimo_ms')}"
                )
                if validado:
                    msgs.append(f"[Academia] top validado={[v.get('hipotese') for v in validado[-3:]]}")
                else:
                    msgs.append("[Academia] sem conhecimento validado — motor sem tip acadêmico")
            except Exception as e:
                msgs.append(f"[Academia] erro consulta: {e}")
        else:
            msgs.append("[Academia] academia_agentes indisponível")


        # lab/estudo NÃO entram no motor — só Academia validada
        if lab_items:
            msgs.append(f"[LabExterno] {len(lab_items)} percepções (auditoria; fora do motor)")
        if estudo_items:
            msgs.append(f"[EstudoIndep] {len(estudo_items)} estudos (auditoria; fora do motor)")

        # Somente conhecimento VALIDADO pela META entra no motor.
        # TODAS votam (antes só as 5 últimas, `validado[-5:]`, o que jogava fora
        # a maioria dos votos quando havia muitas teorias ativas).
        # Peso = quanto a teoria JÁ PROVOU ao vivo: margem do IC90 inferior da
        # sombra sobre o baseline daquela teoria (evidencia_sombra vem da META).
        # Teoria que só empata com o acaso vota fraco; com margem sólida, forte.
        # "nums" só vem preenchido quando eval_cond(expr, hist) é verdadeiro,
        # ou seja: só vota a teoria CABÍVEL para a situação ao vivo deste giro.
        # As demais continuam validadas, apenas dormentes agora.
        _n_teorias_votando = 0
        for v in validado:
            nums = v.get("nums") or []
            if not nums:
                continue
            ev = v.get("evidencia_sombra") or {}
            try:
                margem = float(ev.get("ic90_low") or 0.0) - float(ev.get("baseline") or 0.0)
            except (TypeError, ValueError):
                margem = 0.0
            # Peso do voto. A margem pelo ic90 é a medida dura e continua
            # valendo para quem já validou. Mas ela é ZERO para toda teoria
            # ainda acumulando — e como só validadas votavam, o consenso ficava
            # sempre com zero teorias. Agora quem ainda acumula entra com o
            # peso contínuo da evidência (academia_agentes._peso_evidencia),
            # que é pequeno de propósito: uma teoria de 1,3x com 30 ativações
            # vota com 0,16, contra 1,0 de uma percepção comum. Ela não manda
            # sozinha em nada — ela só deixa de ser silenciada.
            peso_ev = 0.0
            try:
                peso_ev = float(v.get("peso_evidencia") or 0.0)
            except (TypeError, ValueError):
                peso_ev = 0.0
            if v.get("validada"):
                peso = 1.0 + 4.0 * max(0.0, margem)  # 1.0 sem margem … ~2.2 com +30pp
            else:
                peso = max(0.15, peso_ev)            # acumulando: voz pequena, mas voz
            nome_ag = str(v.get("agente") or "?")
            uid = str(v.get("id") or nome_ag)[:8]
            hips.append({
                "nome": f"ACADEMIA_{nome_ag}:{uid}",   # identidade própria = voto próprio
                "nums": list(nums)[:8],
                "peso": round(peso, 3),
                "desc": v.get("hipotese"),
            })
            _n_teorias_votando += 1
        _n_padroes = sum(1 for h in hips if not str(h.get("nome","")).startswith("ACADEMIA_"))
        msgs.append(
            f"[Consenso] cabíveis agora: {_n_teorias_votando} teorias "
            f"({sum(1 for _v in validado if _v.get('validada'))} validadas, "
            f"{sum(1 for _v in validado if not _v.get('validada'))} acumulando) "
            f"+ {_n_padroes} padrões"
        )

        for h in hips:
            if prior_atraso and h.get("nome") in ("ESTAT","GAP_CICLO"):
                h["peso"]=float(h.get("peso",1))*max(1.0,w_isol)
            if boost_anti and h.get("nome") in ("ANOMALIA","ANTI_12","FINAIS"):
                h["peso"]=float(h.get("peso",1))*1.35

        # baseline mesmo k
        base_alvos = self.baseline.prever(hist, self.k_alvos, self.is_ct)

        t1=time.time()
        alvos_l, conf, dist_l, msg_l, influ = self.lstm.prever_dist(hist)
        self.mem.log_modulo("LSTM", conf, (time.time()-t1)*1000, msg_l)
        msgs.append(f"[LSTM] {msg_l}")
        if getattr(self.lstm, "load_error", None):
            msgs.append(f"[LSTM] ERRO pesos: {self.lstm.load_error}")
        if influ.get("steps"):
            ranked_steps = sorted(enumerate(influ["steps"]), key=lambda x: -x[1])[:3]
            msgs.append("[Explicabilidade] oclusão " + ", ".join(f"t-{10-i}:{d}" for i,d in ranked_steps))

        is_real_lstm = bool((influ or {}).get("is_lstm")) and "FALLBACK" not in msg_l and "curto" not in msg_l
        modelo_ativo = self.mem.modelo_ativo_atual()
        if alvos_l and is_real_lstm and modelo_ativo:
            hips.append({"nome":"LSTM","nums":alvos_l,"peso":2.6})
        elif alvos_l and not is_real_lstm:
            hips.append({"nome":"HEURISTICA","nums":alvos_l,"peso":1.0})
            msgs.append("[LSTM] fallback — não conta como LSTM")
        elif not modelo_ativo:
            msgs.append("[LSTM] modelo desativado (não supera baseline) — só hipóteses clássicas")

        # hipóteses do fabricante (teorias criadas do histórico)
        fab_c = list(getattr(self, "_fab_cands", None) or [])
        if fab_c:
            hips.append({"nome": "DESCOBERTA", "nums": fab_c[: self.k_alvos], "peso": 2.4})
            msgs.append(f"[Descoberta→consenso] {fab_c[:self.k_alvos]}")

        # MESA DOS APLICADORES — as 6 lentes sobre o momento atual entram no
        # consenso como mais uma fonte. Sem isto elas ficavam no pacote sem
        # nunca serem chamadas (a auditoria de integração pegou isso).
        try:
            from academia_autonoma.aplicadores import mesa as _mesa
            _cab = [x for x in (validado or []) if x.get("nums")]
            if _cab:
                _rm = _mesa(self.jogo, [str(h) for h in hist],
                            [str(i) for i in range(self.n_classes)], _cab)
                if _rm.get("numeros"):
                    hips.append({"nome": "APLICADORES", "nums": _rm["numeros"], "peso": 2.2})
                    msgs.append(f"[Aplicadores] {_rm['motivo'][:110]}")
        except Exception as _e:
            msgs.append(f"[Aplicadores] erro: {type(_e).__name__}: {_e}")

        # A REGRA DO OPERADOR ENTRA NA VOTAÇÃO.
        # Ela vinha sendo medida por fora, como se fosse auditoria. Mas a tese
        # dele é que o CRUZAMENTO decide — e um conhecimento que não vota não
        # cruza com nada. Aqui ela vira mais uma voz, com peso 2.0: acima da
        # estatística crua (1.3) e abaixo do LSTM (2.6), porque tem evidência
        # medida mas ainda não fechada.
        #
        # Medida na declaração (14/08/2026), 7 números contra 18,9%:
        #     lightning 36/144 = 25,0%  1,32x  p=0,043
        #     immersive 30/137 = 21,9%  1,16x
        #     mega_fire 17/92  = 18,5%  0,98x
        # Não está confirmada. Entra como voz, não como veredito — se estiver
        # errada, as outras fontes a superam na votação, que é o ponto de ter
        # votação em vez de uma regra mandando sozinha.
        if not self.is_ct:
            try:
                from academia_autonoma.hipoteses_predeclaradas import (
                    H4_familia_na_faixa_quente as _h4)
                _cron = []
                for _x in reversed(hist):
                    try:
                        _cron.append(int(_x))
                    except (TypeError, ValueError):
                        pass
                # A FAMÍLIA INTEIRA VOTA, sem eu cortar antes.
                #
                # Eu vinha entregando só 7 números, escolhidos pela "faixa
                # quente". Medido no histórico dele, esse corte é que estraga:
                #
                #     immersive   família crua 1,06x   com meu corte 1,02x
                #     mega_fire   família crua 1,08x   com meu corte 0,92x
                #
                # A tese dele nunca foi que a família toda é a aposta — foi que
                # a família é o CANDIDATO e o cruzamento com as outras teorias
                # decide o que jogar. Quem tem que estreitar é o consenso, que
                # olha o que as outras fontes dizem, não um filtro meu decidindo
                # sozinho antes da votação começar.
                #
                # A ordem aqui é a numérica, de propósito: o peso decai por
                # posição, e eu não tenho evidência de qual número da família
                # merece vir na frente. Ordenar por palpite seria refazer o
                # mesmo erro em outro lugar.
                _fam = _familia_completa(_cron[-1]) if _cron else []
                if _fam:
                    hips.append({"nome": "REGRA_OPERADOR",
                                 "nums": [str(x) for x in _fam],
                                 "peso": 2.0})
                    msgs.append(f"[Regra do operador] família de {_cron[-1]} "
                                f"({len(_fam)} números) entra na votação; "
                                f"quem estreita é o consenso")
                _nums_op = _h4(_cron)
                if _nums_op:
                    # a versão estreitada continua votando, como voz separada,
                    # para dar para comparar as duas ao vivo na sombra
                    hips.append({"nome": "REGRA_OPERADOR_ESTREITA",
                                 "nums": [str(x) for x in _nums_op],
                                 "peso": 1.0})

                # A TABELA DE TRANSIÇÕES QUE ELE DITOU TAMBÉM VOTA.
                #
                # Ela existia no pacote e era avaliada pela academia, mas os
                # candidatos dela passavam pelo mesmo filtro de validação que
                # engolia todo o resto — nunca chegavam à votação ao vivo. Era
                # conhecimento dele guardado numa gaveta.
                #
                # Medida em 3367 giros somados das três mesas: a tabela inteira
                # dá no acaso (1,00x no lightning e no immersive, que juntos têm
                # 2667 ativações). Mas UMA regra se destaca — 29→[30] a 3,52x
                # com p=0,0020, e decaindo certo conforme a janela cresce
                # (3,52x / 2,26x / 1,77x), que é o formato de efeito real e não
                # de ruído. Não sobrevive à correção por 96 testes, então entra
                # como voz e não como veredito: se estiver errada, as outras
                # fontes a superam na votação.
                try:
                    from academia_autonoma.regras_do_operador import TRANSICOES
                    _alvo_tr = TRANSICOES.get(_cron[-1]) if _cron else None
                    if _alvo_tr:
                        hips.append({"nome": "REGRA_TRANSICAO",
                                     "nums": [str(x) for x in _alvo_tr],
                                     "peso": 1.6})
                        msgs.append(f"[Transição ditada] {_cron[-1]} → "
                                    f"{_alvo_tr}")
                except Exception as _e:
                    msgs.append(f"[Transição ditada] erro: {type(_e).__name__}")

                # A FAMÍLIA QUENTE, e dentro dela os que menos saíram.
                #
                # Percepção dele olhando a tela do Mega Fire, 15/08: "elas não
                # olharam o histórico anterior. Dificilmente viria um número
                # repetido assim; ela colocou 10 e 11, mas o 10 e o 11 já
                # tinham ali. Se fossem se basear pelo 0-1-3-6, que é o que
                # mais está aparecendo, teria colocado 21." E o 21 saiu.
                #
                # São duas coisas juntas, e é o cruzamento delas que ele
                # descreve: QUAL família está quente (não a família do último
                # número, que era o que eu já tinha), e DENTRO dela preferir
                # quem ainda não saiu na janela.
                #
                # Medido no histórico dele, 1364 a 1929 ativações por mesa:
                #     lightning  1,02x  ·  immersive  1,03x  ·  mega_fire 1,06x
                # Sete das nove medições acima do acaso. Pouco para afirmar,
                # consistente demais para ignorar — então entra como voz.
                try:
                    _jan = _cron[-20:] if len(_cron) >= 20 else _cron
                    _c = {}
                    for _x in _jan:
                        for _nm, _f in (("0-1-3-6", (0, 1, 3, 6)),
                                        ("0-2-7-8", (0, 2, 7, 8)),
                                        ("4-5-9", (4, 5, 9))):
                            if _x % 10 in _f:
                                _c[_nm] = _c.get(_nm, 0) + 1
                    if _c:
                        _quente = max(_c, key=lambda k: _c[k])
                        _fins = {"0-1-3-6": (0, 1, 3, 6),
                                 "0-2-7-8": (0, 2, 7, 8),
                                 "4-5-9": (4, 5, 9)}[_quente]
                        _pool = [x for x in range(37) if x % 10 in _fins]
                        _vistos = {}
                        for _x in _jan:
                            _vistos[_x] = _vistos.get(_x, 0) + 1
                        # os que menos saíram vêm primeiro: o peso decai por
                        # posição, então a ordem é a preferência dele
                        _ordem = sorted(_pool, key=lambda x: (_vistos.get(x, 0), x))
                        hips.append({"nome": "REGRA_FAMILIA_QUENTE",
                                     "nums": [str(x) for x in _ordem],
                                     "peso": 1.8})
                        msgs.append(f"[Família quente] {_quente} "
                                    f"({_c[_quente]} nos últimos {len(_jan)}) "
                                    f"→ menos vistos: {_ordem[:7]}")
                except Exception as _e:
                    msgs.append(f"[Família quente] erro: {type(_e).__name__}")
            except Exception as _e:
                msgs.append(f"[Regra do operador] erro: {type(_e).__name__}: {_e}")

        # O CONSERTO, ANTES DE VOTAR.
        #
        # Pergunta dele: "após as IAs se perguntarem o porquê dos erros, elas
        # consertam e voltam a emitir sinais?". É aqui que a resposta é sim: a
        # autópsia das janelas fechadas devolve um multiplicador por fonte, ele
        # entra no peso do voto, e o ciclo segue emitindo normalmente.
        #
        # Ninguém é excluído: o multiplicador tem piso, então a teoria que vem
        # errando continua na mesa, só falando mais baixo até voltar a acertar.
        try:
            from academia_autonoma.autopsia import correcao as _corrigir
            _aj = _corrigir(self.jogo)
            if _aj:
                _mexeu = []
                for _h in hips:
                    _m = _aj.get(_h.get("nome"))
                    if _m:
                        _h["peso"] = float(_h.get("peso", 1)) * float(_m)
                        _mexeu.append(f"{_h.get('nome')}×{_m}")
                if _mexeu:
                    msgs.append("[Autópsia→conserto] peso ajustado pelo que "
                                "cada fonte vem acertando: " + ", ".join(_mexeu[:6]))
        except Exception as _e:
            msgs.append(f"[Autópsia→conserto] indisponível: {type(_e).__name__}")

        # OS ESPECIALISTAS NOS PDFS DELE.
        #
        #     "coloque 15 IAs especialistas nos meus dois pdfs opinando sobre
        #      os numeros de previsao com todo o PDF como base de consulta"
        #
        # Sao 17 no fim, porque 15 deixavam 40 conceitos orfaos -- os eixos de
        # IA/validacao e de fisica. Cada um e dono de uma faixa das fichas e
        # consulta `dados_teorias.json` de verdade, na hora.
        #
        # Nem todos apontam numero, e isso e de proposito: borda, calibracao,
        # complexidade e medicao opinam sobre a CONFIANCA dos outros. Um
        # especialista que fala sempre e um que nao sabe do que fala.
        if not self.is_ct:
            try:
                from academia_autonoma.especialistas_pdf import consultar as _esp
                _ctx_e = {"jogo": self.jogo,
                          "taxa_acerto": locals().get("_taxa_acerto"),
                          "acaso_k": locals().get("_acaso_k"),
                          "tem_tempo": bool(settled), "tem_mult": bool(mults)}
                _r = _esp(hist, self.n_classes, _ctx_e)
                for _nome, _nums in (_r.get("palpites") or {}).items():
                    hips.append({"nome": _nome, "nums": _nums, "peso": 1.7})
                msgs.append(f"[Especialistas] {_r.get('opinaram')} dos "
                            f"{_r.get('total')} opinaram sobre os números")
                # os que se calaram tambem informam -- e as vezes mais
                for _n, _fala in (_r.get("falas") or {}).items():
                    if _n not in (_r.get("palpites") or {}) and _fala:
                        msgs.append(f"   {_n}: {_fala[:96]}")
            except Exception as _e:
                msgs.append(f"[Especialistas] {type(_e).__name__}")

        # AS DOZE INTELIGENCIAS DO TRATADO DELE.
        #
        #     "agora, que todas as ias do software trabalham minhas teorias dos
        #      3 pdfs para entregar previsoes atraves de consenso"
        #
        # O terceiro estudo nao e catalogo, e ESPECIFICACAO: 960 formulacoes,
        # 12 inteligencias x 48 familias x 5 mesas, formula auditavel em todas.
        # Aqui as onze que LEEM a mesa entram no consenso. A decima segunda --
        # a agregacao por perda acumulada, w ∝ exp(-eta*Loss) -- e o proprio
        # consenso, e vive em `consenso_ia12`.
        #
        # Estas votam com peso ALTO (2.4). Nao e favoritismo meu: sao as unicas
        # cuja matematica ele publicou fechada, com contraditorio escrito na
        # propria ficha. As minhas heuristicas eu inventei; estas ele derivou.
        try:
            from academia_autonoma.inteligencias_livro import (
                consultar as _tratado, formula_de as _formula,
                texto_citacao as _citar)
            # NO CRAZY TIME OS SIMBOLOS PRECISAM VIRAR INDICE, E VOLTAR.
            #
            # As leituras trabalham com classes 0..N-1. Passando os simbolos
            # crus, o `int()` delas descartava CoinFlip, CashHunt, Pachinko e
            # CrazyBonus -- que nao sao numeros -- e o "10" caia fora do
            # dominio de 8 classes. Sobravam 1, 2 e 5, e as inteligencias
            # votavam em "0", "3", "4": indices que a mesa NAO TEM.
            #
            # Foi visto medindo quem vota: IA01_TEMPO apontando 0, 3 e 4 em dez
            # de dez historicos. Voto em simbolo inexistente nao aparece na
            # tela -- ele some no consenso e leva junto o peso 2,4 daquela
            # leitura. Silencioso, que e o pior tipo.
            _hist_leitura = ([MAP_CT_TO_IDX[x] for x in hist
                              if x in MAP_CT_TO_IDX] if self.is_ct else hist)
            # o tratado quer um valor POR GIRO, não a lista de anúncios
            _mg = self._mult_por_giro(linhas, len(_hist_leitura))
            _ctx_t = {"mults": _mg if any(_mg) else None, "jogo": self.jogo}
            _rt = _tratado(_hist_leitura, self.n_classes, _ctx_t)
            # A IA12 DELE NÃO ESTAVA SENDO CHAMADA.
            #
            # As onze votavam com peso 2,4 fixo, todas iguais. Mas a décima
            # segunda inteligência do tratado é justamente o contrário disso:
            # `w_(j,t) ∝ exp(-η·Loss_j)` -- quem vem errando fala mais baixo.
            # Ela existia no arquivo, tinha teste, e nenhum caminho do software
            # ao vivo passava por ela. O peso fixo é a média simples que a
            # fórmula dele existe para NÃO ser.
            from academia_autonoma.inteligencias_livro import (
                consenso_ia12 as _ia12)
            _perdas = dict(getattr(self, "_perdas_tratado", {}) or {})
            _ag12 = _ia12(_rt.get("pesos") or {}, _perdas,
                          k=max(6, self.k_max))
            _w12 = _ag12.get("pesos_ia") or {}
            _guardar = {}
            for _nome, _nums in (_rt.get("palpites") or {}).items():
                if self.is_ct:
                    _nums = [MAP_IDX_TO_CT[int(x)] for x in _nums
                             if str(x).isdigit() and int(x) in MAP_IDX_TO_CT]
                    if not _nums:
                        continue
                _guardar[_nome] = list(_nums)
                # o peso do tratado agora é o peso 2,4 MODULADO pela IA12
                _w = float(_w12.get(_nome, 1.0))
                hips.append({"nome": _nome, "nums": _nums,
                             "peso": round(2.4 * max(0.25, min(2.0, _w)), 3)})
            # e a agregação dela entra como voz própria, com o nome dela
            _ord12 = list(_ag12.get("ordem") or [])
            if self.is_ct:
                _ord12 = [MAP_IDX_TO_CT[int(x)] for x in _ord12
                          if str(x).isdigit() and int(x) in MAP_IDX_TO_CT]
            if _ord12:
                hips.append({"nome": "IA12_AGREGACAO",
                             "nums": _ord12[:self.k_max], "peso": 2.4})
            # guardado para cobrar a perda quando o resultado deste giro vier
            self._palpites_tratado = _guardar
            msgs.append(f"[Tratado] {_rt.get('opinaram')} das "
                        f"{_rt.get('total')} inteligências leram a mesa"
                        + (f" · IA12 agrega com {len(_perdas)} perda(s) "
                           f"acumulada(s)" if _perdas else
                           " · IA12 agrega (ainda sem perda acumulada)"))
            # de onde saiu cada leitura -- previsao sem fonte nao e auditavel
            for _nome in (_rt.get("palpites") or {}):
                _c = _citar(_nome, self.jogo)
                if _c:
                    msgs.append(f"   {_nome}: {_c[:92]}")
            for _n, _fala in (_rt.get("falas") or {}).items():
                if _n not in (_rt.get("palpites") or {}) and _fala:
                    msgs.append(f"   {_n} ({_formula(_n)[:28]}): {_fala[:72]}")
        except Exception as _e:
            msgs.append(f"[Tratado] {type(_e).__name__}: {_e}")

        # AS PRATICAS DE PREVISAO DO COMPENDIO DELE, VOTANDO.
        #
        # Cobranca dele, e justa: "e pra ler todos meus dois pdfs, pegar todas
        # as praticas de previsao que estao ali, ensinar todas as ias dos
        # softwares, porque voce nao fez isso?".
        #
        # Eu tinha extraido as 400 fichas e aplicado CINCO -- e quatro delas
        # eram regras de metodo (nao seja enganado), nao de previsao. Usei o
        # compendio como manual de seguranca e ignorei o resto como fonte de
        # ideia, que e para o que ele escreveu o documento.
        #
        # Agora cada conceito que descreve um MECANISMO OBSERVAVEL virou uma IA
        # com o numero da ficha no nome, votando como qualquer outra fonte:
        # sobredispersao, subdispersao, autocorrelacao, mudanca de regime,
        # memoria longa, reversao a media, agrupamento de raridades, renovacao,
        # periodicidade, informacao mutua e recorrencia dinamica.
        if not self.is_ct:
            try:
                from academia_autonoma.previsores_compendio import (
                    opinar as _opinar_comp)
                _oc = _opinar_comp(hist, self.n_classes)
                for _nome, _nums in _oc.items():
                    hips.append({"nome": _nome, "nums": _nums, "peso": 1.5})
                if _oc:
                    msgs.append(f"[Compêndio→consenso] {len(_oc)} práticas de "
                                f"previsão dos PDFs dele votando")
            except Exception as _e:
                msgs.append(f"[Compêndio→consenso] {type(_e).__name__}")

        # AS SETE IAS DE MULTIPLICADOR PASSAM A VOTAR NA ESCOLHA.
        #
        # Ele reparou primeiro: "a teoria de multiplicador no cash hunt esta
        # prevendo bonus perfeitamente, utilize ela nao somente nele, mas em
        # todos os jogos".
        #
        # Ate aqui elas so MARCAVAM, depois da escolha feita, quais numeros
        # podiam vir com fogo. Trabalho jogado fora: elas leem o sorteio de
        # lucky/fire/top slot, que acontece de 1 a 5 vezes por giro, saindo ou
        # nao o numero -- muito mais observacao por hora do que o outro lado do
        # problema tem. Nao usar isso na escolha era desperdicio.
        #
        # Cada uma entra como fonte propria, com o nome dela, entao a autopsia
        # e o N efetivo continuam podendo separa-las. E o peso segue a MEDIDA
        # de cada uma contra o acaso da mesma lista: quem esta acima de 1,00x
        # fala mais alto, quem esta abaixo fala mais baixo -- ninguem e calado.
        if linhas:
            try:
                from academia_autonoma.previsores_multiplicador import (
                    prever as _prev_mult, medir as _medir_mult,
                    tem_multiplicador as _tem_mult)
                if _tem_mult(self.jogo):
                    _pm = _prev_mult(self.jogo, linhas)
                    # guardado para a escolha final quando CACADOR_DECIDE
                    self._cacador_consenso = list(_pm.get("consenso") or [])
                    self._cacador_por_ia = dict(_pm.get("por_ia") or {})
                    _med = (_medir_mult(self.jogo, linhas) or {}).get("por_ia") or {}
                    for _nome, _palpite in (_pm.get("por_ia") or {}).items():
                        if not _palpite:
                            continue
                        _r = (_med.get(_nome) or {}).get("razao")
                        # sem medida ainda: entra com voz normal, nao com voz
                        # de quem ja provou
                        # OPINIAO FORTE, como ele pediu: "pegar as tecnicas
                        # dos multiplicadores, deixar como opiniao forte pros
                        # numeros sugestivos".
                        #
                        # 2.6 e o maior peso base da mesa -- acima das teorias
                        # da academia (2.4) e do gap (2.2). O motivo nao e
                        # gosto: estas IAs leem o sorteio de lucky/fire/top
                        # slot, que acontece de 1 a 5 vezes por giro SAINDO OU
                        # NAO o numero. Elas veem varias vezes mais evidencia
                        # por hora que qualquer outra fonte daqui.
                        _peso = 2.6 * (min(1.8, max(0.6, float(_r)))
                                       if _r else 1.0)
                        hips.append({"nome": f"MULT_{_nome}",
                                     "nums": [str(x) for x in _palpite],
                                     "peso": round(_peso, 3)})
                    # OS QUINZE AGENTES ESTATISTICOS, que ate a v119 so
                    # viravam texto de relatorio em ciclo_academia.py. Eles
                    # apontam numero com selo de significancia; agora o que
                    # eles acham entra na votacao com o nome de cada um.
                    for _nome, _d in (_pm.get("por_agente") or {}).items():
                        if not _d.get("alvos"):
                            continue
                        hips.append({"nome": f"CACA_{_nome}",
                                     "nums": [str(x) for x in _d["alvos"]],
                                     "peso": round(2.6 * float(_d["peso"]), 3)})
                    if _pm.get("por_ia"):
                        _nag = len(_pm.get("por_agente") or {})
                        msgs.append(f"[Multiplicador→consenso] "
                                    f"{len(_pm['por_ia'])} IAs de multiplicador "
                                    f"+ {_nag} agente(s) caçador(es) "
                                    f"votando na escolha")
            except Exception as _e:
                msgs.append(f"[Multiplicador→consenso] {type(_e).__name__}")

        aprovados, probs, fontes, score, sig, p0 = self.crit.consenso(hips, self.n_classes, self.k_alvos, minimo=2)
        msgs.append(f"[Hipóteses] {[h['nome'] for h in hips]}")
        msgs.append(f"[Crítico] multi-fonte={aprovados[:8]} p0={p0:.3f}")
        # placar da votação: por que cada número entrou
        if sig:
            _linhas = []
            for _n in aprovados[:self.k_alvos]:
                _s = sig.get(_n) or {}
                _linhas.append(
                    f"{_n} ← {_s.get('votos_teoria',0)} teorias"
                    + (f" + {_s.get('votos_outros',0)} padrões" if _s.get('votos_outros') else "")
                    + f" (peso {_s.get('peso_total',0)})"
                )
            msgs.append("[Consenso/votos] " + " | ".join(_linhas))
        # A MESMA COISA, EM PORTUGUES.
        #
        # Ele disse: "nao entendo o consenso das ias". A linha acima e minha,
        # nao dele: "peso 8.555" e numero de programa, nao razao. Sem entender
        # por que o numero entrou, ele nao consegue julgar se o software errou
        # por azar ou por defeito -- e esse julgamento e o trabalho dele.
        try:
            from explicador import explicar as _explicar
            _fpn = {}
            for _h in hips:
                for _x in (_h.get("nums") or []):
                    _fpn.setdefault(str(_x).strip(), []).append(_h.get("nome", "?"))
            _txt = _explicar(aprovados[:self.k_alvos], _fpn,
                             n_efetivo=locals().get("_ef"))
            if _txt:
                msgs.append("")
                msgs.extend(_txt.split("\n"))
                msgs.append("")
        except Exception as _e:
            msgs.append(f"[Explicação] indisponível: {type(_e).__name__}")
        # FICHA 226 DO COMPÊNDIO DELE — CONSENSO ILUSÓRIO.
        #
        #   "Muitos agentes derivados do mesmo código podem parecer
        #    independentes. Muitas respostas iguais podem ser cópias da mesma
        #    evidência, portanto unanimidade aparente não multiplica informação."
        #
        # Dizer "21 ← 4 teorias" sugere quatro confirmações independentes. Se as
        # quatro leem a mesma evidência, é UMA confirmação repetida quatro vezes,
        # e a confiança que ele lê na tela está inflada por construção. O número
        # efetivo mede isso pela sobreposição real entre as listas.
        try:
            from academia_autonoma.biblioteca_teorias import (
                n_efetivo as _n_ef, texto_n_efetivo as _txt_ef)
            _votos_fonte = {h.get("nome", "?"): (h.get("nums") or [])
                            for h in hips if h.get("nums")}
            _pesos_fonte = {h.get("nome", "?"): float(h.get("peso", 1))
                            for h in hips}
            _ef = _n_ef(_votos_fonte, _pesos_fonte)
            if _ef.get("nominal"):
                msgs.append("[Consenso/independência] " + _txt_ef(_ef))
                if _ef.get("pares"):
                    msgs.append("   quase a mesma voz: " + ", ".join(
                        f"{a}~{b} ({r:.0%})" for a, b, r in _ef["pares"]))
        except Exception as _e:
            msgs.append(f"[Consenso/independência] indisponível: {type(_e).__name__}")
        top_p = sorted(probs.items(), key=lambda x: -x[1])[:8]
        msgs.append("[Probs] " + ", ".join(f"{k}:{v:.3f}" for k,v in top_p))
        msgs.append(f"[Baseline] top{self.k_alvos}={base_alvos}")

        # De onde veio o gatilho. Os bloqueios que existem por causa do LSTM
        # (abaixo) não podem derrubar uma sugestão que não usou o LSTM.
        via_consenso = False
        # Caminho 1 (mais forte): LSTM treinado concordando com outra fonte.
        inter=[]
        if is_real_lstm and modelo_ativo:
            for a in (alvos_l or []):
                fs = fontes.get(a, [])
                if any(f not in ("LSTM","HEURISTICA") for f in fs):
                    inter.append(a)
        if inter:
            alvos=list(dict.fromkeys(inter))[:self.k_max]
            for a in aprovados:
                if is_real_lstm and a in (alvos_l or []) and a not in alvos:
                    alvos.append(a)
                if len(alvos)>=self.k_max: break
            alvos = cortar_por_apoio(alvos, score, self.k_min, self.k_max)
            modo="GATILHO_OK"
        else:
            # Caminho 2: o CONSENSO DISPARA SOZINHO.
            #
            # Antes, interseção vazia zerava tudo — o LSTM era porteiro, não
            # votante. Com isso, máquina sem torch (ou com <50 eventos, ou com
            # o modelo em fallback) nunca mostrava previsão nenhuma, e a tela
            # não dizia o motivo. Não era rigor: era travamento por um
            # componente ausente. Quem protege a qualidade aqui é a sombra
            # prospectiva ao vivo mais o portão do FDR, e esses continuam
            # inteiros — só entram números que JÁ passaram por eles.
            #
            # A exigência que substitui o LSTM é acordo entre teorias
            # INDEPENDENTES: pelo menos MIN_TEORIAS_SOZINHO teorias validadas
            # distintas apontando o mesmo número. Uma teoria sozinha não abre
            # gatilho.
            if CONSENSO_PURO:
                # O cruzamento já ordenou por peso somado: os mais votados
                # estão na frente. A entrada é o topo dessa lista — não uma
                # teoria isolada que passou de um limiar.
                so_teorias = list(aprovados)
            else:
                so_teorias = [
                    a for a in aprovados
                    if int((sig.get(a) or {}).get("votos_teoria", 0)) >= self.MIN_TEORIAS_SOZINHO
                ]
            if so_teorias:
                # a faixa dele (5-10 na roleta, 1-3 no crazy time) com o corte
                # decidido pelo apoio de cada número na votação
                alvos = cortar_por_apoio(list(dict.fromkeys(so_teorias)),
                                         score, self.k_min, self.k_max)
                modo = "GATILHO_OK"
                via_consenso = True
                _det = ", ".join(
                    f"{a}({int((sig.get(a) or {}).get('votos_teoria', 0))}t"
                    f"+{int((sig.get(a) or {}).get('votos_outros', 0))}p)"
                    for a in alvos
                )
                msgs.append(
                    f"[Gatilho] consenso das IAs — {len(alvos)} número(s) mais "
                    f"votados no cruzamento: {_det}"
                )
                if not is_real_lstm:
                    msgs.append(
                        "[LSTM] sem modelo treinado — a votação das teorias decidiu sozinha"
                    )
            else:
                alvos=[]; modo="AGUARDANDO"
                if not is_real_lstm:
                    msgs.append(
                        "[LSTM] SEM MODELO TREINADO — instale as dependências "
                        "(0_INSTALAR_DEPENDENCIAS.bat) e junte ≥50 eventos. "
                        "Enquanto isso, só sai previsão se "
                        f"≥{self.MIN_TEORIAS_SOZINHO} teorias validadas concordarem."
                    )

        if self.is_ct and alvos:
            fr=Counter(hist[:25])
            forcar = bool(self.prefs.get("reduzir_12")) or (fr.get("1",0)+fr.get("2",0)>=14)
            if forcar:
                filtrados=[a for a in alvos if a not in ("1","2")]
                if not filtrados:
                    filtrados=[a for a in aprovados if a not in ("1","2")][:self.k_alvos]
                    msgs.append("[CT] anti-1/2 recuperação")
                else:
                    msgs.append("[CT] anti-fixação 1/2")
                alvos=list(dict.fromkeys(filtrados))[:self.k_alvos]

        if not alvos:
            modo="AGUARDANDO"

        # confiança calibrada insuficiente → SEM EVIDÊNCIA operacional
        #
        # `conf` é a confiança calibrada DO LSTM. É a régua certa quando os
        # números vieram dele. Quando vieram do consenso das teorias, ele não
        # opinou sobre esses números — vetar por uma confiança que não é sobre
        # eles calava o consenso sempre que o LSTM estivesse fraco ou desligado.
        #
        # Medido no histórico dele: o gatilho ABRIA ("consenso sozinho — 3
        # números com ≥2 teorias concordando") e morria na linha seguinte, em
        # 160 de 160 voltas. Zero sugestões em todo o histórico.
        # ═══ O CACADOR DECIDE, SEM REGUA ═══════════════════════════════
        #
        #     "deixar somente o Cacador de Multiplicador escolhendo os numeros
        #      para todos os jogos, sem regua para ele"
        #
        # Aqui os numeros da tela passam a sair direto das sete IAs de
        # multiplicador. Nao ha consenso, nem minimo de vozes independentes,
        # nem corte por apoio, nem gate meu de especie nenhuma -- ele foi
        # explicito.
        #
        # Tudo o mais continua rodando e aparecendo no log. Informa, nao manda.
        if CACADOR_DECIDE:
            _cc = list(getattr(self, "_cacador_consenso", []) or [])
            if _cc:
                alvos = _cc[:self.k_max]
                modo = "CACADOR"
                msgs.append(f"[Caçador decide] {' '.join(str(x) for x in alvos)}"
                            f"  — sem régua, por ordem dele")
            elif self.jogo != "immersive":
                msgs.append("[Caçador decide] sem palpite do Caçador nesta "
                            "volta — a tela fica sem número em vez de cair "
                            "para outra fonte")
                alvos = []

        sombra_alvos = list(alvos) if alvos else []
        if (modo == "GATILHO_OK" and conf < self.lstm.limiar
                and not via_consenso and not CONSENSO_PURO):
            # guarda candidatos experimentais antes de limpar orientação pública
            sombra_alvos = list(alvos) if alvos else list(base_alvos or [])[:self.k_alvos]
            alvos=[]; modo="AGUARDANDO"
            msgs.append("[Gatilho] SEM EVIDÊNCIA calibrada — conf < limiar")
        elif modo == "GATILHO_OK" and conf < self.lstm.limiar and via_consenso:
            msgs.append("[Gatilho] confiança do LSTM baixa, mas os números "
                        "vieram do consenso das teorias — não veta")

        # ========== POLÍTICA CONSERVADORA ==========
        # rel_n = janelas de DECISÃO já avaliadas (métrica científica)
        # n_hist = giros disponíveis no histórico (amostra operacional)
        rel_n = int(rel.get("n") or 0)
        n_hist = len(hist)
        ganho = rel.get("ganho")
        taxa_m = rel.get("taxa")
        taxa_b = rel.get("taxa_baseline")
        brier = rel.get("brier")
        operavel = True
        motivo_bloq = []
        modelo_ativo = bool(self.mem.modelo_ativo_atual())

        # Amostra operacional: precisa de giros no histórico, NÃO de janelas avaliadas.
        # Exigir 20 janelas avaliadas antes da 1ª previsão criava deadlock (nunca previa → nunca avaliava).
        MIN_HIST = 12 if self.is_ct else 15
        if n_hist < MIN_HIST:
            operavel = False
            motivo_bloq.append(f"histórico insuficiente ({n_hist}<{MIN_HIST})")

        # Métricas científicas só bloqueiam DEPOIS de ter amostra de avaliação
        MIN_JANELAS_METRICAS = 20

        # 2/3 — ganho ≤ 0 vs baseline (só após MIN_JANELAS_METRICAS)
        #
        # Cada tipo de decisão é julgado pelo desempenho DAQUELE tipo. SOMBRA e
        # OPERAR não apostam a mesma coisa: a sombra usa um conjunto largo (a
        # união das hipóteses), o OPERAR usa só o que passou no consenso. Num
        # número só, o desempenho do conjunto largo vetava o estreito — e como
        # esta instalação nunca saiu de SOMBRA, a conta que barrava o consenso
        # era 100% sobre outra coisa. Enquanto não houver MIN_JANELAS_METRICAS
        # janelas de OPERAR fechadas não existe evidência contra operar, e
        # exigi-la antes de deixar operar é o mesmo laço já desfeito no
        # histórico mínimo.
        _ganho_op = rel.get("ganho_operar")
        _n_op = int(rel.get("n_operar") or 0)
        if _n_op >= MIN_JANELAS_METRICAS and _ganho_op is not None and _ganho_op < -0.02:
            operavel = False
            motivo_bloq.append(f"ganho<0 vs baseline em OPERAR "
                               f"({_ganho_op:.3f}) n_operar={_n_op}")
        elif ganho is not None and ganho < -0.02 and rel_n >= MIN_JANELAS_METRICAS:
            msgs.append(f"[Métricas] a sombra está {abs(ganho):.1%} abaixo do "
                        f"baseline (n={rel_n}) — anotado, mas ela aposta um "
                        f"conjunto mais largo que o consenso, então não veta")
        elif ganho is not None and abs(ganho) <= 0.02 and rel_n >= MIN_JANELAS_METRICAS:
            msgs.append(f"[Métricas] ganho≈0 vs baseline ({ganho:.3f}) — empate, não bloqueia por ganho")

        # 2 — modelo desativado
        #
        # `modelo_ativo` rastreia se o LSTM vem batendo a baseline; ele é
        # desligado quando não bate. Isso é motivo legítimo para não confiar
        # numa sugestão DO LSTM — mas não diz nada sobre teorias validadas na
        # sombra ao vivo, que não passam por ele. Sem esta ressalva, uma
        # instalação cujo LSTM foi desligado ficava muda para sempre, mesmo com
        # teorias provadas concordando.
        if not modelo_ativo and not via_consenso:
            operavel = False
            motivo_bloq.append("modelo_desativado")
        elif not modelo_ativo and via_consenso:
            msgs.append("[Métricas] LSTM desativado, mas a sugestão veio das teorias — não bloqueia")

        # 1 — taxa ~ acaso POR JANELA (não por giro)
        try:
            from metricas_honestas import p_alvos_ct, p_alvos_roleta, p_hit_janela
            _al_ref = list(alvos or sombra_alvos or [])
            _p1 = p_alvos_ct(_al_ref) if self.is_ct else p_alvos_roleta(_al_ref)
            # janela_base ainda não definida aqui — usar 3 conservador alinhado ao default abaixo
            _j_ref = 3
            p_acaso_janela = p_hit_janela(_p1, _j_ref) if _al_ref else (self.k_alvos / max(self.n_classes, 1))
        except Exception:
            p_acaso_janela = self.k_alvos / max(self.n_classes, 1)
        if taxa_m is not None and rel_n >= MIN_JANELAS_METRICAS and taxa_m <= p_acaso_janela * 1.05:
            operavel = False
            motivo_bloq.append(f"taxa~acaso_janela ({taxa_m:.3f}≤{p_acaso_janela*1.05:.3f}) n_aval={rel_n}")

        # 7 — Brier ruim → sobe limiar e bloqueia
        #
        # Terceira métrica DO LSTM que vetava a sugestão das teorias. O Brier
        # mede a calibração das probabilidades que o modelo emite; se os números
        # não saíram dele, o Brier dele não fala sobre eles. Medido no histórico
        # dele: 0,2803 contra um teto de 0,28 — bloqueio por três milésimos, em
        # toda volta, sobre uma sugestão que o modelo nem produziu. O limiar
        # continua subindo, porque isso sim é sobre o LSTM.
        if brier is not None and brier > 0.28:
            self.lstm.limiar = min(0.16, self.lstm.limiar + 0.01)
            if not via_consenso:
                operavel = False
                motivo_bloq.append(f"Brier alto {brier:.3f}")
            else:
                msgs.append(f"[Métricas] Brier do LSTM alto ({brier:.3f}), mas "
                            "a sugestão veio das teorias — não bloqueia")

        # 7 — teste negativo suspeito
        neg = self.mem.d.get("negativo") or {}
        if neg.get("suspeito_leak") and neg.get("n", 0) >= 8:
            operavel = False
            motivo_bloq.append("teste_negativo suspeito")

        # 5 — janela menor e menos alvos
        janela_base = 3  # default conservador 2–3
        if conf < 0.15:
            k_use = max(2, self.k_alvos - 2) if not self.is_ct else 2
        elif conf < 0.25:
            k_use = max(2, self.k_alvos - 1) if not self.is_ct else 2
        else:
            k_use = self.k_alvos if not self.is_ct else min(3, self.k_alvos)
        if alvos:
            alvos = list(alvos)[:k_use]

        # 6 — lab nunca abre gatilho sozinho (já famílias).
        #
        # Antes, isto era "sem LSTM real não opera", ponto — e ficava DEPOIS do
        # portão, anulando o caminho do consenso sozinho. Medido: o gatilho
        # abria 280 vezes e nenhuma previsão chegava à tela.
        #
        # Um bloqueio por causa do LSTM só faz sentido sobre uma sugestão que
        # USA o LSTM. Quando quem decidiu foram teorias validadas na sombra ao
        # vivo, a ausência do modelo não diz nada sobre a qualidade delas.
        # Os freios que medem DESEMPENHO REAL (taxa~acaso, Brier, ganho vs
        # baseline abaixo) continuam valendo para os dois caminhos.
        if modo == "GATILHO_OK" and not is_real_lstm and not via_consenso:
            operavel = False
            motivo_bloq.append("sem LSTM real")

        
        # Honestidade: cobertura alta de acaso bloqueia, salvo ganho vs acaso SIGNIFICATIVO (IC95)
        try:
            from metricas_honestas import p_alvos_ct, p_alvos_roleta, p_hit_janela, ganho_significativo
            _al = list(alvos or sombra_alvos or [])
            _p1 = p_alvos_ct(_al) if self.is_ct else p_alvos_roleta(_al)
            _pe = p_hit_janela(_p1, janela_base)
            msgs.append(f"[Honestidade] P(hit|acaso)≈{_pe:.1%} k={len(_al)} J={janela_base}")
            # acumulado na memória
            cov = self.mem.d.get("cobertura_acc") or {}
            n_acc = int(cov.get("n") or 0)
            y_acc = float(cov.get("soma_y") or 0.0)
            p_acc = float(cov.get("soma_p") or 0.0)
            p_med = (p_acc / n_acc) if n_acc > 0 else _pe
            sig = ganho_significativo(int(y_acc), n_acc, p_med) if n_acc >= 20 else {"ok": False, "motivo": "n<20"}
            msgs.append(f"[Honestidade] ganho_sig={sig.get('ok')} ({sig.get('motivo')}) n={n_acc}")
            if _pe >= 0.85 and not sig.get("ok"):
                operavel = False
                motivo_bloq.append(f"cobertura_acaso_alta({_pe:.1%}) sem ganho significativo")
        except Exception as e:
            msgs.append(f"[Honestidade] indisponível: {e}")

# SOMBRA no aquecimento: registra experimental SEM orientação pública
        # Usa alvos do gatilho OU candidatos guardados (sombra_alvos/baseline)
        # candidatos experimentais: alvos atuais → sombra_alvos → baseline → critic multi-fonte
        cand_sombra = list(alvos) if alvos else []
        # O CONSENSO VEM ANTES DO BASELINE.
        #
        # Aqui estava o defeito mais caro do software. Com o gatilho em
        # AGUARDANDO — que é o estado normal enquanto não há teoria validada —
        # `alvos` fica vazio, e a cascata caía direto em `sombra_alvos`, que a
        # linha ~1749 já havia preenchido com `base_alvos`. Resultado medido
        # nos 205 giros reais de Lightning do operador: em 128 de 144 ciclos
        # (88,9%) a sombra avaliava o BASELINE DE FREQUÊNCIA, não o consenso.
        #
        # As consequências eram todas na mesma direção:
        #   - o consenso era calculado, aparecia no log e era descartado;
        #   - a evidência que se acumulava nas teorias vinha de janelas do
        #     baseline, e depois era comparada contra o próprio baseline;
        #   - qualquer melhoria no cruzamento (regra do operador votando,
        #     teorias acumulando votando) não mexia um dígito no resultado,
        #     porque não chegava ao que estava sendo medido.
        #
        # O baseline continua na fila — mas como último recurso, que é o papel
        # dele. O que a sombra tem que provar é o consenso.
        if not cand_sombra:
            cand_sombra = [a for a in (aprovados or [])][:self.k_alvos]
        if not cand_sombra:
            cand_sombra = list(sombra_alvos or [])
        if not cand_sombra:
            cand_sombra = list(base_alvos or [])[:self.k_alvos]
        if not cand_sombra and getattr(self, "_fab_cands", None):
            cand_sombra = list(self._fab_cands)[:self.k_alvos]
        if not cand_sombra:
            # crítico / hips
            try:
                pool = []
                for h in (hips or []):
                    for n in (h.get("nums") or h.get("numeros") or []):
                        if n not in pool:
                            pool.append(n)
                cand_sombra = pool[:self.k_alvos]
            except Exception:
                cand_sombra = []
        cand_sombra = list(dict.fromkeys(str(x) if self.is_ct else x for x in cand_sombra))[:self.k_alvos]
        # SOMBRA continua DEPOIS de 20 avaliadas se não houver OPERAR público
        pode_sombra = bool(cand_sombra) and n_hist >= MIN_HIST
        # `modelo_ativo` diz que o LSTM vem batendo a baseline. É a condição
        # certa para confiar numa sugestão DELE. Quando os números vieram do
        # consenso das teorias ele não participou — exigi-lo aqui reimpunha, na
        # decisão final, exatamente o veto que as ressalvas de cima já tinham
        # tirado. A sombra e o portão do FDR continuam valendo; o que muda é de
        # quem se cobra a régua.
        _modelo_ok = modelo_ativo or via_consenso
        if CONSENSO_PURO:
            # Consenso puro: houve acordo entre teorias, então é entrada. Não
            # se exige janelas avaliadas, nem modelo ativo, nem ganho contra
            # baseline. O acordo é o critério.
            status_op = "OPERAR" if (modo == "GATILHO_OK" and alvos) else "NAO_OPERAR"
            if status_op == "OPERAR" and motivo_bloq:
                msgs.append("[Consenso puro] as teorias concordaram — "
                            "seguindo apesar de: " + "; ".join(motivo_bloq))
        else:
            status_op = "OPERAR" if (operavel and modo == "GATILHO_OK" and alvos and rel_n >= MIN_JANELAS_METRICAS and _modelo_ok) else "NAO_OPERAR"
        if status_op == "OPERAR":
            modo_out = "OPERAR"
            msgs.append(f"[Conservador] OPERAR k={len(alvos)} janela≤{janela_base} conf={conf:.3f}")
        elif pode_sombra:
            # O CACADOR NAO E TROCADO PELA SOMBRA.
            #
            # `cand_sombra` e a lista alternativa que o modo de observacao usa.
            # Com CACADOR_DECIDE ligado, trocar os numeros dele por outra lista
            # e regua -- e ele mandou que nao houvesse regua para o Cacador.
            if not (CACADOR_DECIDE and getattr(self, "_cacador_consenso", None)):
                alvos = list(cand_sombra)[:self.k_alvos]
            modo_out = "SOMBRA"
            status_op = "SOMBRA"
            fase = "aquecimento" if rel_n < MIN_JANELAS_METRICAS else "monitor"
            # O motivo do bloqueio precisa aparecer AQUI. Sem ele, a mensagem
            # dizia que estava em sombra sem dizer por quê, e achar a causa
            # exigia instrumentar o código por fora — foi o que aconteceu.
            _pq = "; ".join(motivo_bloq) if motivo_bloq else (
                "gatilho não abriu" if modo != "GATILHO_OK"
                else "sem alvos" if not alvos else "—")
            msgs.append(
                f"[Sombra/{fase}] k={len(alvos)} hist={n_hist} avaliadas={rel_n} (mín. {MIN_JANELAS_METRICAS}) "
                f"modelo_ativo={modelo_ativo} — sem orientação pública | motivo: {_pq}"
            )
        elif modo == "AGUARDANDO":
            modo_out = "AGUARDANDO"
            msgs.append("[Conservador] NAO_OPERAR — AGUARDANDO/SEM EVIDÊNCIA")
        else:
            modo_out = "NAO_OPERAR"
            msgs.append(f"[Conservador] NAO_OPERAR — {'; '.join(motivo_bloq) or modo}")

        msgs.append(f"[Gatilho] {modo}" + (f" → {alvos}" if alvos else " — LSTM real ∩ outra fonte"))
        msgs.append(f"[Baseline] top{self.k_alvos}={base_alvos} | ganho={ganho} taxa_m={taxa_m} taxa_b={taxa_b}")


        # JANELA ATÉ 5, e não travada em 3.
        #
        # Ele diagnosticou sozinho: "pega ela pra aplicar uma vez, não veio o
        # número, já era. Ou pra uma janela pequena de três — se tivesse
        # colocado de cinco, estava inserido, acertado, e não teria descartado."
        #
        # Estava travada em 3 por um `min(3, ...)` no código: nem se o cérebro
        # quisesse 5 ele conseguia. Medido no histórico dele, sobre 7.949
        # ativações no lightning e 11.233 no immersive, a janela maior melhora
        # a razão contra o acaso:
        #
        #     lightning   janela 3: 0,57x    janela 5: 0,63x
        #     immersive   janela 3: 0,37x    janela 5: 0,41x
        #
        # A melhora é modesta e não resolve o problema de fundo, mas é real e a
        # decisão é dele. O teto agora é 5, e a preferência do operador manda.
        janela = max(2, min(JANELA_MAX, janela_base + cmd["janela_mod"]))
        if self.prefs.get("janela") is not None:
            try:
                janela = max(2, min(JANELA_MAX, int(self.prefs["janela"])))
            except Exception:
                pass

        # O PISO DE 53% DE ACERTO DE JANELA — o pedido dele.
        #
        # So aqui, porque so agora a janela e conhecida: o k necessario depende
        # dela (janela 5 pede 6 numeros; janela 3 pede 9). Tentar isto antes de
        # `janela` existir foi um NameError que o test_lint pegou -- o mesmo
        # tipo de erro que derrubou a v102.
        #
        # Completa com os proximos mais votados, na ordem do consenso: quem
        # entra para fechar o piso entra por apoio, nao por sorteio.
        # O PISO NAO PODE TROCAR A FONTE NO MEIO DO CAMINHO.
        #
        # Quando o Cacador decide, completar a lista dele com os proximos mais
        # votados do consenso geral e' entregar numeros de OUTRA fonte sob o
        # nome dele. O piso de 53% e' uma conta sobre o tamanho da aposta, nao
        # uma licenca para trocar quem escolheu.
        if (alvos and not self.is_ct and not COBERTURA_LARGA
                and not (CACADOR_DECIDE and getattr(self, "_cacador_consenso", None))
                and locals().get("aprovados")):
            _kalvo = k_para_alvo(janela, ALVO_ACERTO_JANELA,
                                 self.n_classes, self.k_max)
            if len(alvos) < _kalvo:
                for _a in aprovados:
                    if _a not in alvos:
                        alvos.append(_a)
                    if len(alvos) >= _kalvo:
                        break
                msgs.append(f"[Piso 53%] janela de {janela} giros pede "
                            f"{_kalvo} numeros — lista completada com os "
                            f"proximos mais votados")

        dist_sel = {str(a): float(dist_l.get(a, probs.get(a, 0))) for a in alvos}
        sel_ui = list(active_selection or [])
        if sel_ui:
            msgs.append(f"[Memória] janela UI ativa {sel_ui} — sem nova decisão")
            alvos = list(sel_ui)
            modo = "JANELA_ATIVA"
            modo_out = "JANELA_ATIVA"
            status_op = "OPERAR"
        elif alvos and locals().get("modo_out") in ("OPERAR", "SOMBRA"):
            fh = hashlib.md5(json.dumps(feats, sort_keys=True, default=str).encode()).hexdigest()[:10]
            modo_reg = "OPERAR" if locals().get("modo_out") == "OPERAR" else "SOMBRA"
            item = self.mem.registrar_decisao(
                alvos, modo_reg, probs, [h["nome"] for h in hips], conf, dist_sel,
                baseline_alvos=base_alvos, features_hash=fh,
                settled_ref=(settled[0] if settled else None), janela=janela,
            )
            if item:
                msgs.append(f"[Memória] decisão {modo_reg} id={item['id']} baseline={base_alvos}")
        elif alvos and modo == "GATILHO_OK":
            msgs.append("[Memória] gatilho sem OPERAR/SOMBRA — abstenção")
        elif modo == "AGUARDANDO":
            settled0 = settled[0] if settled else None
            if settled0 and settled0 == self.mem.d.get("ultimo_aguardando_settled"):
                msgs.append("[Memória] AGUARDANDO duplicado (mesmo settled) — não conta de novo")
            else:
                self.mem.d["ultimo_aguardando_settled"] = settled0
                self.mem.registrar_decisao([], modo, {}, [], 0.0, {})

        sols=[]
        _st = locals().get("status_op") or "NAO_OPERAR"
        _rn = int(rel.get("n") or 0)
        if modo == "AGUARDANDO" or _st == "NAO_OPERAR":
            sols.append("NÃO APOSTAR — aguardar OPERAR")
        if rel.get("ganho") is not None and rel["ganho"] <= 0:
            sols.append("Ganho≤0 vs baseline — não usar modelo")
        if rel.get("brier") and rel["brier"] > 0.25:
            sols.append("Calibração fraca — mais SEM EVIDÊNCIA")
        if _rn < 20:
            sols.append(f"Amostra {_rn}/20 — só observar")
        if not sols:
            sols.append("Operar só com OPERAR + ganho>0 + amostra≥20")
        msgs.append("[Soluções práticas] " + " | ".join(sols))
        msgs.append(f"[Metacognição] conf={conf:.3f} limiar={self.lstm.limiar:.3f} T={self.lstm.temperature:.2f} ativo={self.mem.modelo_ativo_atual()} | p_janela=1-(1-p_sel)^J (approx, assume indep.)")
        msgs.append(f"[Monitor] {(time.time()-t0)*1000:.0f}ms device={self.lstm.device}")

        av_v = self.mem._so_versao_atual(self.mem.d.get("avaliadas") or [])
        cal_v = [c for c in (self.mem.d.get("calib") or []) if c.get("pipeline_version") == PIPELINE_VERSION]
        pend_v = [d for d in (self.mem.d.get("decisoes_pendentes") or [])
                  if d.get("resultado") is None and d.get("alvos") and (
                      d.get("eval_protocol") == EVAL_PROTOCOL
                      or d.get("pipeline_version") == PIPELINE_VERSION)]
        acertos_aval = sum(1 for a in av_v if (a.get("resultado") or {}).get("acertou"))
        erros_aval = max(0, len(av_v) - acertos_aval)
        cov = self.mem.d.get("cobertura_acc") or {}
        mem_stats = {
            "avaliadas": len(av_v),
            "pendentes": len(pend_v),
            "calib": len(cal_v),
            "treinado": bool(self.lstm.treinado),
            "metricas": rel,
            "protocolo": PIPELINE_VERSION,
            "eval_protocol": EVAL_PROTOCOL,
            "legado_avaliadas": len(self.mem.d.get("avaliadas") or []) - len(av_v),
            "acertos_aval": acertos_aval,
            "erros_aval": erros_aval,
            "soma_p_esperado": float(cov.get("soma_p") or 0.0),
            "soma_y_cobertura": float(cov.get("soma_y") or 0.0),
            "n_cobertura": int(cov.get("n") or 0),
        }
        msgs.append(
            f"[Aprendizado] protocolo={PIPELINE_VERSION} avaliadas={mem_stats['avaliadas']} "
            f"pend={mem_stats['pendentes']} calib={mem_stats['calib']} legado_ign={mem_stats['legado_avaliadas']}"
        )

        try:
            _modo_final = modo_out
        except NameError:
            _modo_final = modo
        try:
            _status = status_op
        except NameError:
            _status = "NAO_OPERAR"
        try:
            _motivos = list(motivo_bloq)
        except NameError:
            _motivos = []
        # AGUARDANDO É RESPOSTA, NÃO FALHA.
        #
        # Este software não prevê o tempo todo: ele procura o MOMENTO de
        # prever. A sombra roda ao fundo aprendendo, e a previsão só sai
        # quando o gatilho reconhece a hora. Publicar a cada giro transforma
        # previsão em ruído com número, e destrói o único filtro que existe
        # entre "o consenso calculou algo" e "vale a pena olhar".
        #
        # (Esta linha já foi quebrada uma vez: eu li o "AGUARDANDO" perpétuo
        # como defeito de entrega e liberei a saída em todo giro. O defeito
        # nunca foi o aviso — era o momento certo não chegar nunca, porque
        # nenhuma teoria votava e o caminho do consenso não podia abrir.
        # Conserta-se o gatilho, não a etiqueta.)
        if CACADOR_DECIDE and getattr(self, "_cacador_consenso", None):
            # SEM REGUA: o numero do Cacador vai para a tela em qualquer modo.
            #
            # Este bloco e a ultima regua do caminho -- ele segurava a saida
            # ate o consenso "merecer" aparecer, e era ele que deixava a tela
            # vazia mesmo com o Cacador tendo palpite. Medido: o Cacador
            # apontava 16 24 5 20 1 31 e a tela mostrava nada.
            #
            # Ele decidiu que o Cacador escolhe sozinho e sem regua. Entao a
            # unica condicao aqui e ter palpite.
            #
            # E A LISTA VEM DO CACADOR, NAO DE `alvos`.
            #
            # `alvos` parece a lista dele, mas nao e: entre a decisao do
            # Cacador e esta linha, ela passa por quatro lugares que a
            # modificam --
            #
            #   . a lista de sombra, montada com fontes que nao sao o Cacador
            #   . a regua do LSTM, que pode encurtar
            #   . o "piso de 53%", que COMPLETA a lista com os proximos mais
            #     votados do consenso geral quando ela e' curta demais
            #   . `active_selection`, que substitui tudo pela janela aberta
            #
            # Ou seja: a tela mostrava numeros do Cacador MISTURADOS com
            # numeros de outras fontes, sob o rotulo "Cacador decide". Os tres
            # primeiros costumavam ser dele e o resto nao -- e nao havia como
            # distinguir olhando.
            #
            # Se o Cacador aponta cinco e o piso pede nove, a resposta certa e'
            # entregar os cinco dele. Completar com voto alheio nao e' cumprir
            # o piso: e' trocar a fonte no meio do caminho e nao contar.
            pad_ui = [str(x) for x in self._cacador_consenso][:self.k_max]
        elif _modo_final == "JANELA_ATIVA":
            pad_ui = list(alvos)
        elif _modo_final == "OPERAR" and _status == "OPERAR":
            pad_ui = list(alvos)
        else:
            pad_ui = []
        # A taxa de acerto acompanha a previsão em todo lugar: tela, log e
        # notificação. É o número que o operador cobra, e ele não pode ficar
        # escondido dentro de um painel de estatística separado.
        try:
            _ac = int((mem_stats or {}).get("acertos_aval") or 0)
            _er = int((mem_stats or {}).get("erros_aval") or 0)
        except (TypeError, ValueError, AttributeError):
            _ac = _er = 0
        _tot_aval = _ac + _er
        _taxa_acerto = (_ac / _tot_aval) if _tot_aval else None
        # O ACASO TEM QUE SER O DA MESMA APOSTA.
        # O placar conta JANELA: o número sair em até `janela` giros. Comparar
        # isso contra k/37 (que é a chance de UM giro) infla tudo: com 7
        # números em 3 giros o acaso já é 46,5%, não 18,9%. Um placar de 54,5%
        # lido contra 18,9% pareceria 2,9x de vantagem quando é 1,17x.
        _k = len(pad_ui) or self.k_alvos
        _j = max(1, int(janela or 1))
        _acaso_k = 1.0 - (1.0 - _k / max(1, self.n_classes)) ** _j
        if _tot_aval:
            msgs.append(
                f"[Placar] {_ac}/{_tot_aval} = {_ac/_tot_aval:.1%} | "
                f"acaso ({_k} números em {_j} giros) = {_acaso_k:.1%} | "
                f"{(_ac/_tot_aval)/_acaso_k:.2f}x"
            )
        return {
            "taxa_acerto": _taxa_acerto, "acertos_aval": _ac, "erros_aval": _er,
            "acaso_k": _acaso_k,
            "pad5": pad_ui, "anti5": [], "janela": janela, "msgs": msgs,
            "device": str(self.lstm.device), "modo": _modo_final, "conf": conf,
            "probs": {str(k): round(float(v),4) for k,v in top_p},
            "solucoes": sols, "mem_stats": mem_stats, "baseline": base_alvos,
            "version": PIPELINE_VERSION, "eval_protocol": EVAL_PROTOCOL,
            "operavel": _modo_final == "OPERAR" and _status == "OPERAR",
            "alvos_auditoria": list(alvos) if alvos else [], "motivo_bloq": _motivos,
            "sombra": _modo_final == "SOMBRA",
            # O que CADA fonte propôs, antes do corte das sete vagas.
            #
            # Sem isto a autópsia não tem como responder a pergunta dele —
            # "por que erraram?" — porque não dá para saber se o número que
            # saiu foi ignorado na votação ou se ninguém tinha visto ele.
            # São diagnósticos opostos: um pede ajuste de peso, o outro pede
            # teoria nova.
            "fontes_nums": {str(h.get("nome", "?")): [str(x) for x in (h.get("nums") or [])]
                            for h in (hips or [])},
            "contadores": {
                "historico_bruto": n_hist if 'n_hist' in dir() else len(hist),
                "janelas_avaliadas": rel_n if 'rel_n' in dir() else 0,
                "janelas_pendentes": mem_stats.get("pendentes", 0),
                "min_avaliadas": 20,
                "legado_ignorado": mem_stats.get("legado_avaliadas", 0),
            },
        }

    def _aguardar(self, msgs, motivo, settled=None, n_hist=0):
        msgs.append(f"[Gatilho] AGUARDANDO — {motivo}")
        msgs.append("[Soluções práticas] Aguardar dados/condição mínima")
        settled0 = settled[0] if settled else None
        key = f"{motivo}|{settled0}"
        if key == self.mem.d.get("ultimo_aguardar_key"):
            msgs.append("[Memória] _aguardar duplicado (mesmo motivo+settled) — não conta")
        else:
            self.mem.d["ultimo_aguardar_key"] = key
            self.mem.registrar_decisao([], "AGUARDANDO", {}, [], 0.0, {})
        try:
            rel = self.mem.relatorio_metricas()
            av_v = self.mem._so_versao_atual(self.mem.d.get("avaliadas") or [])
            # mesma regra do caminho normal: abertas, com alvos, protocolo atual
            pend_v = [
                d for d in (self.mem.d.get("decisoes_pendentes") or [])
                if d.get("resultado") is None
                and d.get("alvos")
                and (
                    d.get("eval_protocol") == EVAL_PROTOCOL
                    or d.get("pipeline_version") == PIPELINE_VERSION
                )
            ]
            acertos_aval = sum(1 for a in av_v if (a.get("resultado") or {}).get("acertou"))
            erros_aval = max(0, len(av_v) - acertos_aval)
            contadores = {
                "historico_bruto": int(n_hist or 0),
                "janelas_avaliadas": len(av_v),
                "janelas_pendentes": len(pend_v),
                "min_avaliadas": 20,
                "legado_ignorado": max(0, len(self.mem.d.get("avaliadas") or []) - len(av_v)),
            }
            mem_stats = {
                "avaliadas": len(av_v), "pendentes": len(pend_v),
                "acertos_aval": acertos_aval, "erros_aval": erros_aval,
                "protocolo": PIPELINE_VERSION, "eval_protocol": EVAL_PROTOCOL,
                "metricas": rel,
            }
        except Exception:
            contadores = {
                "historico_bruto": int(n_hist or 0),
                "janelas_avaliadas": 0, "janelas_pendentes": 0,
                "min_avaliadas": 20, "legado_ignorado": 0,
            }
            mem_stats = {"avaliadas": 0, "pendentes": 0, "acertos_aval": 0, "erros_aval": 0}
        return {
            "pad5": [], "anti5": [], "janela": 3, "msgs": msgs,
            "device": str(DEVICE), "modo": "AGUARDANDO", "conf": 0.0, "probs": {},
            "solucoes": ["Aguardar"], "version": PIPELINE_VERSION,
            "eval_protocol": EVAL_PROTOCOL, "operavel": False, "sombra": False,
            "alvos_auditoria": [], "motivo_bloq": [motivo],
            "contadores": contadores, "mem_stats": mem_stats, "baseline": [],
        }
