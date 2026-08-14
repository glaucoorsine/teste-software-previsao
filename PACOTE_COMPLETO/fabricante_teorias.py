# -*- coding: utf-8 -*-
"""
Fabricante de teorias a partir do histórico.
Não fica preso a quente/frio: cria hipóteses, testa em sombra no próprio histórico
e devolve candidatos + texto legível do que "está acontecendo".
"""
from __future__ import annotations
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
MEM_DIR = ROOT  # teorias salvas ao lado do software

# Famílias semeadas (o fabricante pode criar outras além destas)
SEMENTE_FAMILIAS = {
    "finais_0278": {0, 2, 7, 8, 10, 12, 17, 18, 20, 22, 27, 28, 30, 32},
    "finais_136": {1, 3, 6, 11, 13, 16, 21, 23, 26, 31, 33, 36},
    "finais_459": {4, 5, 9, 14, 15, 19, 24, 25, 29, 34, 35},
    "cluster_19": {19, 21, 23, 25, 27, 32},
    "eixo_14_16": {12, 14, 16, 18},
    "faixa_baixa_1_4": {1, 2, 3, 4},
    "triade_6_8_18": {6, 8, 18},
    "pares_30_36": {30, 32, 34, 36},
}


def _final(n: int) -> int:
    return int(n) % 10


def _norm_hist(hist) -> list[int]:
    out = []
    for x in hist or []:
        try:
            out.append(int(x))
        except Exception:
            continue
    return out


class FabricanteTeorias:
    """
    A cada ciclo:
      1) observa histórico
      2) fabrica/atualiza teorias
      3) testa no próprio passado (sombra offline)
      4) escolhe 1..max_k candidatos pelo consenso das teorias ativas
    """

    def __init__(self, jogo: str = "mega_fire", max_teorias: int = 120):
        self.jogo = jogo
        self.max_teorias = max_teorias
        self.path = MEM_DIR / f"teorias_{jogo}.json"
        self.d = self._load()

    def _load(self) -> dict:
        base = {"teorias": {}, "log": [], "atualizado": None}
        if self.path.is_file():
            try:
                base.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return base

    def _save(self):
        try:
            self.d["atualizado"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            # limita log
            self.d["log"] = (self.d.get("log") or [])[-200:]
            # limita teorias
            teor = self.d.get("teorias") or {}
            if len(teor) > self.max_teorias:
                # mantém as de maior score_sombra
                ranked = sorted(teor.items(), key=lambda kv: float(kv[1].get("score_sombra") or 0), reverse=True)
                self.d["teorias"] = dict(ranked[: self.max_teorias])
            self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _upsert(self, tid: str, payload: dict):
        teor = self.d.setdefault("teorias", {})
        old = teor.get(tid) or {}
        merged = {**old, **payload}
        merged["id"] = tid
        merged["visto_em"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        teor[tid] = merged

    def _log(self, msg: str):
        self.d.setdefault("log", []).append(f"{time.strftime('%H:%M:%S')} | {msg}")

    # ---------- mineração ----------
    def _minerar_transicoes(self, hist: list[int], janela: int = 40) -> list[dict]:
        """A→B: quando sai A, o que mais segue."""
        h = hist[:janela]
        if len(h) < 8:
            return []
        # hist[0] = mais recente; transição é hist[i+1] → hist[i]
        pares = defaultdict(Counter)
        for i in range(len(h) - 1):
            a, b = h[i + 1], h[i]  # a saiu antes, b depois (mais recente)
            pares[a][b] += 1
        teorias = []
        for a, ctr in pares.items():
            total = sum(ctr.values())
            if total < 2:
                continue
            top = ctr.most_common(3)
            for b, c in top:
                if c < 2:
                    continue
                taxa = c / total
                if taxa < 0.25 and c < 3:
                    continue
                tid = f"trans_{a}_para_{b}"
                teorias.append({
                    "id": tid,
                    "tipo": "transicao",
                    "nome": f"Após {a} → costuma {b}",
                    "ancora": a,
                    "candidatos": [b],
                    "evidencia": f"{c}/{total} ({taxa:.0%}) nos últimos {len(h)}",
                    "forca": min(1.0, taxa + 0.1 * c),
                    "n": total,
                })
        return teorias

    def _minerar_ecos(self, hist: list[int], janela: int = 50) -> list[dict]:
        """Número repetido em seguida (eco)."""
        h = hist[:janela]
        ecos = 0
        exemplos = []
        for i in range(len(h) - 1):
            if h[i] == h[i + 1]:
                ecos += 1
                exemplos.append(h[i])
        teorias = []
        if ecos >= 2:
            # teoria: ecos estão "na moda" → vigiar repetição do último
            ultimo = h[0] if h else None
            tid = "eco_repeticao_ativa"
            teorias.append({
                "id": tid,
                "tipo": "eco",
                "nome": f"Ecos ativos ({ecos} no trecho) — vigiar repetir {ultimo}",
                "ancora": ultimo,
                "candidatos": [ultimo] if ultimo is not None else [],
                "evidencia": f"{ecos} ecos; exemplos={exemplos[:6]}",
                "forca": min(1.0, 0.3 + 0.1 * ecos),
                "n": ecos,
            })
        # eco recente imediato
        if len(h) >= 2 and h[0] == h[1]:
            tid = f"eco_agora_{h[0]}"
            teorias.append({
                "id": tid,
                "tipo": "eco_imediato",
                "nome": f"Acabou de ecoar {h[0]}×2",
                "ancora": h[0],
                "candidatos": [h[0]],
                "evidencia": "dois iguais consecutivos no topo",
                "forca": 0.7,
                "n": 2,
            })
        return teorias

    def _minerar_familias(self, hist: list[int], janela: int = 20) -> list[dict]:
        h = hist[:janela]
        if len(h) < 6:
            return []
        teorias = []
        for nome, membros in SEMENTE_FAMILIAS.items():
            hits = [x for x in h if x in membros]
            taxa = len(hits) / len(h)
            esperado = len(membros) / 37.0
            if taxa < esperado * 1.4 and len(hits) < 4:
                continue
            # candidatos = membros que ainda não saíram nos últimos 5
            recent = set(h[:5])
            cands = [n for n in sorted(membros) if n not in recent]
            if not cands:
                cands = sorted(membros)[:5]
            tid = f"fam_{nome}"
            teorias.append({
                "id": tid,
                "tipo": "familia",
                "nome": f"Família {nome} ativa",
                "ancora": hits[0] if hits else None,
                "candidatos": cands[:7],
                "evidencia": f"{len(hits)}/{len(h)} ({taxa:.0%}) vs esp {esperado:.0%}",
                "forca": min(1.0, (taxa / max(esperado, 0.01)) / 3),
                "n": len(hits),
            })
        return teorias

    def _minerar_finais_corridos(self, hist: list[int], janela: int = 15) -> list[dict]:
        """Finais dominantes no trecho curto (ex.: muito 0/1/3/6)."""
        h = hist[:janela]
        if len(h) < 5:
            return []
        fins = Counter(_final(x) for x in h)
        teorias = []
        top = fins.most_common(3)
        for f, c in top:
            if c < 3:
                continue
            taxa = c / len(h)
            if taxa < 0.25:
                continue
            cands = [n for n in range(37) if _final(n) == f]
            # prioriza os que não saíram nos últimos 3
            recent = set(h[:3])
            cands = [n for n in cands if n not in recent] or cands
            tid = f"final_dominante_{f}"
            teorias.append({
                "id": tid,
                "tipo": "final",
                "nome": f"Final {f} dominando o trecho",
                "ancora": f,
                "candidatos": cands[:7],
                "evidencia": f"{c}/{len(h)} terminam em {f}",
                "forca": min(1.0, taxa),
                "n": c,
            })
        return teorias

    def _minerar_vizinho_fire(self, hist: list[int], mults: list | None, janela: int = 30) -> list[dict]:
        """
        Números que saíram com multiplicador (fire): vigiar vizinhos de mesa (±1,±2)
        e o próprio número.
        """
        if not mults:
            return []
        fires = []
        for m in mults[:janela]:
            try:
                n = int(m.get("n"))
                x = float(m.get("x") or 0)
                if x and x >= 2:
                    fires.append(n)
            except Exception:
                continue
        if not fires:
            return []
        # vizinhos de mesa (não roda): n-2..n+2
        viz = set()
        for n in fires[:8]:
            for d in (-2, -1, 1, 2):
                v = n + d
                if 0 <= v <= 36:
                    viz.add(v)
            viz.add(n)
        recent = set(hist[:5]) if hist else set()
        cands = [n for n in sorted(viz) if n not in recent] or sorted(viz)
        return [{
            "id": "vizinhos_de_fire",
            "tipo": "fire_vizinho",
            "nome": "Batidas perto de números com fire/mult",
            "ancora": fires[0],
            "candidatos": cands[:7],
            "evidencia": f"fires recentes={fires[:8]}",
            "forca": 0.55,
            "n": len(fires),
        }]

    def _minerar_anti_obvios(self, hist: list[int], janela: int = 40) -> list[dict]:
        """
        Números que o histórico recente NÃO está pedindo (baixa frequência + fora das famílias ativas).
        Úteis como 1–2 'anti' que o público não coloca.
        """
        h = hist[:janela]
        if len(h) < 15:
            return []
        cnt = Counter(h)
        raros = [n for n in range(37) if cnt.get(n, 0) == 0]
        if len(raros) < 2:
            raros = [n for n, _ in sorted(cnt.items(), key=lambda kv: kv[1])[:5]]
        # pega 2 do meio da lista de raros (não os extremos óbvios de sempre)
        mid = len(raros) // 2
        cands = raros[max(0, mid - 1): mid + 2][:3]
        return [{
            "id": "anti_obvio",
            "tipo": "anti",
            "nome": "Números fora do óbvio do trecho",
            "ancora": None,
            "candidatos": cands,
            "evidencia": f"ausentes/raros no top {janela}: {raros[:10]}",
            "forca": 0.35,
            "n": len(raros),
        }]

    def _testar_sombra_transicao(self, hist: list[int], ancora: int, alvo: int, min_evt: int = 3) -> dict:
        """No passado: após ancora, quantas vezes o próximo foi alvo."""
        # hist[0] recente
        hits = total = 0
        for i in range(len(hist) - 1):
            if hist[i + 1] == ancora:
                total += 1
                if hist[i] == alvo:
                    hits += 1
        if total < min_evt:
            return {"score_sombra": 0.0, "hits": hits, "total": total, "status": "amostra_baixa"}
        taxa = hits / total
        base = 1 / 37
        ganho = taxa - base
        return {
            "score_sombra": max(0.0, min(1.0, 0.5 + ganho * 5)),
            "hits": hits,
            "total": total,
            "taxa": taxa,
            "ganho_vs_uniforme": ganho,
            "status": "ativa" if ganho > 0.05 and total >= min_evt else "fraca",
        }

    def fabricar(self, historico, mults=None, max_k: int = 7) -> dict:
        hist = _norm_hist(historico)
        msgs = []
        geradas = []
        geradas += self._minerar_transicoes(hist)
        geradas += self._minerar_ecos(hist)
        geradas += self._minerar_familias(hist)
        geradas += self._minerar_finais_corridos(hist)
        geradas += self._minerar_vizinho_fire(hist, mults)
        geradas += self._minerar_anti_obvios(hist)

        # testa sombra e grava
        ativas = []
        for t in geradas:
            st = {"score_sombra": float(t.get("forca") or 0), "status": "observando"}
            if t["tipo"] == "transicao" and t.get("ancora") is not None and t.get("candidatos"):
                st = self._testar_sombra_transicao(hist, int(t["ancora"]), int(t["candidatos"][0]))
            t["score_sombra"] = float(st.get("score_sombra") or t.get("forca") or 0)
            t["status_sombra"] = st.get("status")
            t["sombra_detalhe"] = st
            self._upsert(t["id"], t)
            if t["score_sombra"] >= 0.35 or st.get("status") in ("ativa", "observando"):
                ativas.append(t)

        # ranking
        ativas.sort(key=lambda x: float(x.get("score_sombra") or 0), reverse=True)
        top = ativas[:12]

        # consenso: números que aparecem em várias teorias
        votos = Counter()
        peso = defaultdict(float)
        for t in top:
            w = float(t.get("score_sombra") or 0.3)
            for c in t.get("candidatos") or []:
                try:
                    c = int(c)
                except Exception:
                    continue
                votos[c] += 1
                peso[c] += w

        # ordena por peso * votos
        ranked = sorted(peso.keys(), key=lambda n: (peso[n] * (1 + 0.3 * votos[n])), reverse=True)

        # tamanho variável 1..max_k conforme força do consenso
        if not ranked:
            k = 0
            cands = []
        else:
            forte = sum(1 for t in top if float(t.get("score_sombra") or 0) >= 0.55)
            if forte >= 4:
                k = min(max_k, 7)
            elif forte >= 2:
                k = min(max_k, 5)
            elif votos:
                k = min(max_k, 3)
            else:
                k = min(max_k, 2)
            # inclui 1 anti se existir teoria anti
            cands = ranked[:k]
            for t in top:
                if t.get("tipo") == "anti":
                    for a in t.get("candidatos") or []:
                        if a not in cands and len(cands) < max_k:
                            cands.append(int(a))
                    break

        # mensagens humanas
        msgs.append(f"[Fabricante] {len(geradas)} teorias geradas | {len(top)} em observação | k={len(cands)}")
        for t in top[:6]:
            msgs.append(
                f"  · {t.get('nome')} | {t.get('evidencia')} | "
                f"sombra={t.get('score_sombra', 0):.2f} ({t.get('status_sombra')}) | "
                f"cand={t.get('candidatos')}"
            )
        if cands:
            msgs.append(f"[Consenso teorias] → {cands} (votos={dict(votos.most_common(7))})")
        else:
            msgs.append("[Consenso teorias] sem candidatos fortes — só sombra/observação")

        self._log(f"ciclo hist={len(hist)} geradas={len(geradas)} cands={cands}")
        self._save()

        return {
            "candidatos": cands,
            "msgs": msgs,
            "teorias_top": top[:8],
            "n_teorias": len(self.d.get("teorias") or {}),
            "k": len(cands),
        }


# singleton leve por jogo
_FAB = {}

def get_fabricante(jogo: str) -> FabricanteTeorias:
    if jogo not in _FAB:
        _FAB[jogo] = FabricanteTeorias(jogo=jogo)
    return _FAB[jogo]


def fabricar_para(jogo: str, historico, mults=None, max_k: int = 7) -> dict:
    return get_fabricante(jogo).fabricar(historico, mults=mults, max_k=max_k)
