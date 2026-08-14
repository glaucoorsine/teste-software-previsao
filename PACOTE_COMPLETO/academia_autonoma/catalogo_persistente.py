# -*- coding: utf-8 -*-
"""Catálogo SQLite com transações BEGIN IMMEDIATE e UPSERT."""
from __future__ import annotations
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from .paths_dados import subdir

def _db_path() -> Path:
    env = os.environ.get("ACADEMIA_CATALOGO_DB")
    if env:
        p = Path(env)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    p = subdir("sqlite") / "catalogo_familiaridades.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


DB_PATH = None  # legado; use db_path()

def db_path() -> Path:
    """Resolve em cada chamada — respeita env alterado em testes."""
    return _db_path()


def _conn():
    c = sqlite3.connect(str(db_path()), timeout=60, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=FULL")
    except sqlite3.Error:
        pass
    return c


def init_db():
    c = _conn()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("""
        CREATE TABLE IF NOT EXISTS teorias (
            id TEXT NOT NULL,
            dataset_id TEXT NOT NULL,
            dominio TEXT,
            autor TEXT,
            estado TEXT,
            ativacao TEXT,
            janela INTEGER,
            horizonte INTEGER,
            payload TEXT NOT NULL,
            criado_em TEXT,
            atualizado_em TEXT,
            PRIMARY KEY (id, dataset_id)
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_teorias_ds ON teorias(dataset_id)")
        c.execute("COMMIT")
    except sqlite3.Error:
        try:
            c.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        c.close()


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _retry(fn, tries=8):
    delay = 0.02
    last = None
    for _ in range(tries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last = e
            if "locked" not in str(e).lower():
                raise
            time.sleep(delay)
            delay = min(0.5, delay * 1.6)
    raise last  # type: ignore


def get(tid: str, dataset_id: str = None) -> Optional[dict]:
    init_db()

    def _do():
        c = _conn()
        try:
            if dataset_id:
                row = c.execute(
                    "SELECT payload FROM teorias WHERE id=? AND dataset_id=?",
                    (tid, dataset_id),
                ).fetchone()
            else:
                row = c.execute(
                    "SELECT payload FROM teorias WHERE id=? LIMIT 1", (tid,)
                ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])
        finally:
            c.close()

    return _retry(_do)


def listar(dataset_id: str, estados: Optional[List[str]] = None) -> List[dict]:
    init_db()

    def _do():
        c = _conn()
        try:
            rows = c.execute(
                "SELECT payload FROM teorias WHERE dataset_id=?", (dataset_id,)
            ).fetchall()
            out = [json.loads(r["payload"]) for r in rows]
        finally:
            c.close()
        if estados:
            out = [t for t in out if t.get("estado") in estados]
        return out

    return _retry(_do)


def merge(teoria: dict) -> dict:
    """UPSERT atômico preservando prospectivo/hist/episódios."""
    init_db()
    tid = (teoria or {}).get("id")
    ds = (teoria or {}).get("dataset_id")
    if not tid or not ds:
        # antes disso: KeyError cru (teoria sem "id"/"dataset_id") ou
        # sqlite3.IntegrityError (dataset_id=None) — erro mais claro pra quem
        # for depurar um chamador que monta a teoria errado.
        raise ValueError(
            f"merge() exige teoria com 'id' e 'dataset_id' não-vazios (recebido id={tid!r} dataset_id={ds!r})"
        )
    now = _now()

    def _do():
        c = _conn()
        try:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT payload FROM teorias WHERE id=? AND dataset_id=?",
                (tid, ds),
            ).fetchone()
            if row is None:
                teoria.setdefault("criado_em", now)
                teoria["atualizado_em"] = now
                payload = json.dumps(teoria, ensure_ascii=False)
                c.execute(
                    """INSERT INTO teorias(id,dataset_id,dominio,autor,estado,ativacao,janela,horizonte,payload,criado_em,atualizado_em)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(id,dataset_id) DO UPDATE SET
                         dominio=excluded.dominio, autor=excluded.autor, estado=excluded.estado,
                         ativacao=excluded.ativacao, janela=excluded.janela, horizonte=excluded.horizonte,
                         payload=excluded.payload, atualizado_em=excluded.atualizado_em
                    """,
                    (
                        tid, ds, teoria.get("dominio"), teoria.get("autor"),
                        teoria.get("estado"), teoria.get("ativacao"), teoria.get("janela"),
                        teoria.get("horizonte"), payload, teoria["criado_em"], teoria["atualizado_em"],
                    ),
                )
                c.execute("COMMIT")
                return teoria

            old = json.loads(row["payload"])
            merged = dict(old)
            if json.dumps(old.get("expr"), sort_keys=True) != json.dumps(teoria.get("expr"), sort_keys=True):
                merged.setdefault("versoes_anteriores", []).append({
                    "versao": old.get("versao"), "expr": old.get("expr"), "em": now,
                })
                merged["versao"] = int(old.get("versao") or 1) + 1

            preservados = {
                "prospectivo", "episodios_ativacao", "versoes_anteriores", "criado_em",
                "teste_negativo", "retrospectivo", "baseline",
            }
            for k, v in teoria.items():
                if k in preservados:
                    continue
                merged[k] = v

            p_old = dict(old.get("prospectivo") or {})
            p_new = dict(teoria.get("prospectivo") or {})
            prosp = dict(p_old)
            n_old = int(p_old.get("n") or 0)
            n_new = int(p_new.get("n") or 0)
            if n_new > n_old:
                prosp["n"] = n_new
                prosp["hits"] = p_new.get("hits", p_old.get("hits"))
                prosp["misses"] = p_new.get("misses", p_old.get("misses"))
                prosp["taxa"] = p_new.get("taxa")
                hist_new = list(p_new.get("hist") or [])
                hist_old = list(p_old.get("hist") or [])
                prosp["hist"] = hist_new if len(hist_new) >= len(hist_old) else hist_old + hist_new[len(hist_old):]
            else:
                hist_old = list(p_old.get("hist") or [])
                hist_new = list(p_new.get("hist") or [])
                if hist_new and len(hist_new) >= len(hist_old):
                    merged_hist = []
                    for i in range(len(hist_new)):
                        if i < len(hist_old):
                            e = dict(hist_old[i])
                            e.update({k: v for k, v in hist_new[i].items() if v is not None})
                            if "baseline_hit" in hist_new[i]:
                                e["baseline_hit"] = hist_new[i]["baseline_hit"]
                            if "baseline_alvos" in hist_new[i]:
                                e["baseline_alvos"] = hist_new[i]["baseline_alvos"]
                            if "candidatos" in hist_new[i]:
                                e["candidatos"] = hist_new[i]["candidatos"]
                            merged_hist.append(e)
                        else:
                            merged_hist.append(dict(hist_new[i]))
                    prosp["hist"] = merged_hist
                prosp["n"] = max(n_old, n_new)
                for k in ("hits", "misses", "taxa"):
                    if p_new.get(k) is not None and n_new >= n_old:
                        prosp[k] = p_new[k]
                    elif k in p_old:
                        prosp[k] = p_old[k]
            if "pendente" in p_new:
                prosp["pendente"] = p_new["pendente"]
            elif "pendente" in p_old and n_new <= n_old:
                prosp["pendente"] = p_old.get("pendente")
            merged["prospectivo"] = prosp

            if teoria.get("episodios_ativacao"):
                eps = list(old.get("episodios_ativacao") or [])
                for e in teoria["episodios_ativacao"]:
                    if e not in eps:
                        eps.append(e)
                merged["episodios_ativacao"] = eps

            for k in ("teste_negativo", "retrospectivo", "baseline", "evidencia"):
                if teoria.get(k):
                    merged[k] = {**(old.get(k) or {}), **(teoria.get(k) or {})}

            merged["atualizado_em"] = now
            merged.setdefault("criado_em", old.get("criado_em") or now)
            payload = json.dumps(merged, ensure_ascii=False)
            c.execute(
                """UPDATE teorias SET dominio=?, autor=?, estado=?, ativacao=?, janela=?, horizonte=?,
                   payload=?, atualizado_em=? WHERE id=? AND dataset_id=?""",
                (
                    merged.get("dominio"), merged.get("autor"), merged.get("estado"),
                    merged.get("ativacao"), merged.get("janela"), merged.get("horizonte"),
                    payload, merged["atualizado_em"], tid, ds,
                ),
            )
            c.execute("COMMIT")
            return merged
        except Exception:
            try:
                c.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            c.close()

    return _retry(_do)


def registrar_prospectivo(
    tid: str,
    saiu: str,
    hit: bool,
    dataset_id: str = None,
    candidatos=None,
    fingerprint=None,
    baseline_hit=None,
    baseline_alvos=None,
) -> Optional[dict]:
    if not dataset_id:
        raise ValueError("registrar_prospectivo exige dataset_id")
    init_db()

    def _do():
        c = _conn()
        try:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT payload FROM teorias WHERE id=? AND dataset_id=?",
                (tid, dataset_id),
            ).fetchone()
            if not row:
                c.execute("COMMIT")
                return None
            t = json.loads(row["payload"])
            p = t.setdefault("prospectivo", {"n": 0, "hits": 0, "misses": 0, "taxa": None, "hist": []})
            p["n"] = int(p.get("n") or 0) + 1
            if hit:
                p["hits"] = int(p.get("hits") or 0) + 1
            else:
                p["misses"] = int(p.get("misses") or 0) + 1
            p["taxa"] = p["hits"] / p["n"] if p["n"] else None
            entry = {"saiu": saiu, "hit": hit}
            if candidatos is not None:
                entry["candidatos"] = list(candidatos)
            if baseline_hit is not None:
                entry["baseline_hit"] = bool(baseline_hit)
            if baseline_alvos is not None:
                entry["baseline_alvos"] = list(baseline_alvos)
            if fingerprint is not None:
                entry["fingerprint"] = list(fingerprint) if not isinstance(fingerprint, list) else fingerprint
            p.setdefault("hist", []).append(entry)
            p["pendente"] = None
            t["prospectivo"] = p
            t["atualizado_em"] = _now()
            payload = json.dumps(t, ensure_ascii=False)
            c.execute(
                "UPDATE teorias SET payload=?, atualizado_em=? WHERE id=? AND dataset_id=?",
                (payload, t["atualizado_em"], tid, dataset_id),
            )
            c.execute("COMMIT")
            return t
        except Exception:
            try:
                c.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            c.close()

    return _retry(_do)


def count(dataset_id: str = None) -> int:
    init_db()

    def _do():
        c = _conn()
        try:
            if dataset_id:
                return c.execute(
                    "SELECT COUNT(*) FROM teorias WHERE dataset_id=?", (dataset_id,)
                ).fetchone()[0]
            return c.execute("SELECT COUNT(*) FROM teorias").fetchone()[0]
        finally:
            c.close()

    return _retry(_do)
