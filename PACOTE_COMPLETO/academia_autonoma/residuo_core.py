# -*- coding: utf-8 -*-
"""Resíduo: congelamento e avaliação — lógica funcional v32 + locks concorrentes."""
from __future__ import annotations
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from .paths_dados import subdir
from .locks import file_lock, atomic_write_text


def _path(dataset_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    d = subdir("residuos")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.jsonl"


def _opin_path(dataset_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset_id)
    d = subdir("opinioes_congeladas")
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.jsonl"


def decision_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def congelar_opinioes(
    dataset_id: str,
    event_id: str,
    hist_head: str,
    opinioes: Dict[str, Any],
    candidatos_por_fonte: Dict[str, List[str]],
) -> dict:
    """Congela opiniões; mesma decision_id não grava de novo."""
    did = decision_id({"e": event_id, "h": hist_head, "o": opinioes, "c": candidatos_por_fonte})
    rec = {
        "decision_id": did,
        "dataset_id": dataset_id,
        "event_id": event_id,
        "hist_head_no_momento": hist_head,
        "opinioes": opinioes,
        "candidatos_por_fonte": candidatos_por_fonte,
        "congelado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "avaliado": False,
        "resultado_observado": None,
    }
    path = _opin_path(dataset_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path.with_suffix(".lock")):
        existing = set()
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    existing.add(json.loads(line).get("decision_id"))
                except json.JSONDecodeError:
                    continue
        if did in existing:
            rec["duplicado"] = True
            return rec
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _score_explicacao(candidatos: List[str], resultado: str, conf: float = 0.5) -> float:
    if not candidatos:
        return 0.0
    if resultado in [str(x) for x in candidatos]:
        try:
            pos = [str(x) for x in candidatos].index(resultado)
        except ValueError:
            pos = len(candidatos)
        return min(1.0, conf * (1.0 - pos / max(len(candidatos), 1)))
    return 0.0


def avaliar_congeladas(dataset_id: str, resultado_observado: str, max_n: int = 5) -> List[dict]:
    """
    Lógica funcional idêntica à v32 (scores/classificação/campos).
    Proteção concorrente: locks + anti-duplicata de decision_id no resíduo.
    """
    opin_p = _opin_path(dataset_id)
    res_p = _path(dataset_id)
    if not opin_p.is_file():
        return []
    with file_lock(opin_p.with_suffix(".lock")):
        with file_lock(res_p.with_suffix(".lock")):
            lines = opin_p.read_text(encoding="utf-8").splitlines()
            already_res = set()
            if res_p.is_file():
                for line in res_p.read_text(encoding="utf-8").splitlines():
                    try:
                        already_res.add(json.loads(line).get("decision_id"))
                    except json.JSONDecodeError:
                        continue
            out_res = []
            rewritten = []
            avaliados = 0
            for line in lines:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("avaliado"):
                    rewritten.append(rec)
                    continue
                if avaliados >= max_n:
                    rewritten.append(rec)
                    continue
                did = rec.get("decision_id")
                if did in already_res:
                    rec = dict(rec)
                    rec["avaliado"] = True
                    rewritten.append(rec)
                    continue

                cands = rec.get("candidatos_por_fonte") or {}
                scores = {}
                ativos = []
                for fonte, lista in cands.items():
                    conf = float((rec.get("opinioes") or {}).get(fonte, 0.5))
                    sc = _score_explicacao(lista, str(resultado_observado), conf)
                    scores[f"explicacao_{str(fonte).lower()}"] = sc
                    if lista:
                        ativos.append(sc)
                if ativos:
                    consenso = sum(ativos) / len(ativos)
                    melhor = max(ativos)
                    residual = max(0.0, min(1.0, (1.0 - consenso) * (1.0 - 0.7 * melhor)))
                    if melhor >= 0.4:
                        residual = min(residual, 1.0 - melhor)
                else:
                    consenso = 0.0
                    residual = 1.0
                vals_sc = list(scores.values()) or [0.0]
                if residual >= 0.75:
                    clas = "NAO_EXPLICADO"
                elif residual >= 0.45:
                    clas = "PARCIALMENTE_EXPLICADO"
                elif max(vals_sc) >= 0.5 and sum(1 for x in vals_sc if x >= 0.3) >= 2:
                    clas = "EXPLICADO_MULTIFONTE"
                elif scores.get("explicacao_familiaridade", 0) >= 0.4:
                    clas = "EXPLICADO_FAMILIARIDADE"
                elif scores.get("explicacao_padrao", 0) >= 0.4 or scores.get("explicacao_estatistico", 0) >= 0.4:
                    clas = "EXPLICADO_PADRAO"
                elif scores.get("explicacao_anomalia", 0) >= 0.5:
                    clas = "RUPTURA"
                else:
                    clas = "PARCIALMENTE_EXPLICADO"

                residual_rec = {
                    "event_id": rec.get("event_id"),
                    "decision_id": did,
                    "dataset_id": dataset_id,
                    "resultado_observado": str(resultado_observado),
                    **scores,
                    "consenso_total": round(consenso, 4),
                    "residual_score": round(residual, 4),
                    "classificacao": clas,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "candidatos_no_congelamento": cands,
                }
                res_p.parent.mkdir(parents=True, exist_ok=True)
                with res_p.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(residual_rec, ensure_ascii=False) + "\n")
                already_res.add(did)
                out_res.append(residual_rec)
                rec = dict(rec)
                rec["avaliado"] = True
                rec["resultado_observado"] = str(resultado_observado)
                rec["residual"] = residual_rec
                rewritten.append(rec)
                avaliados += 1

            atomic_write_text(
                opin_p,
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rewritten[-2000:]),
            )
            return out_res


def listar_residuos(dataset_id: str, only_nao_explicado: bool = True, limit: int = 100) -> List[dict]:
    p = _path(dataset_id)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines()[-limit * 2:]:
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if only_nao_explicado and r.get("classificacao") not in (
            "NAO_EXPLICADO", "PARCIALMENTE_EXPLICADO", "RUPTURA"
        ):
            continue
        out.append(r)
    return out[-limit:]
