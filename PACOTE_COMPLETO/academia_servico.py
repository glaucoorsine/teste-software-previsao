# -*- coding: utf-8 -*-
"""
Serviço Academia — fila oficial.

API pública de escrita:
    enfileirar_job(jogo, historico, settled=None, mults=None, job_id=None)

NÃO escreva diretamente em data_inbox/{jogo}.jsonl.
Use apenas enfileirar_job (ou arquivos em data_inbox/pending/ via a API).

Caminho ao vivo (combos → worker → pipeline) NÃO usa esta fila.
"""
from __future__ import annotations
import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.locks import file_lock

JOGOS = ("mega_fire", "lightning", "immersive", "crazy_time")
CLAIM_LEASE_SEC = 120.0


def processar(dataset_id, historico, settled=None, mults=None):
    return ciclo(dataset_id, historico, settled=settled, mults=mults)


def _inbox_dir() -> Path:
    d = Path(__file__).resolve().parent / "data_inbox"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pending_dir() -> Path:
    d = _inbox_dir() / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _queue_lock_path(jogo: str) -> Path:
    """Lock curto: enfileirar, claim, recover, requeue (operações rápidas)."""
    return _inbox_dir() / f"{jogo}.queue.lock"


def _consumer_lock_path(jogo: str) -> Path:
    """Lock longo: um consumidor por jogo durante todo o _consumir_fila (inclui processar)."""
    return _inbox_dir() / f"{jogo}.consumer.lock"


def _processed_path(jogo: str) -> Path:
    return _inbox_dir() / f"{jogo}.processed_ids.json"


def _processed_lock_path(jogo: str) -> Path:
    return _inbox_dir() / f"{jogo}.processed.lock"


def _load_processed_unlocked(jogo: str) -> set:
    p = _processed_path(jogo)
    if not p.is_file():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return set(data if isinstance(data, list) else data.get("ids") or [])
    except (OSError, json.JSONDecodeError) as e:
        print(f"[academia_servico] processed load: {e}")
        return set()


def _merge_processed(jogo: str, new_ids) -> set:
    p = _processed_path(jogo)
    with file_lock(_processed_lock_path(jogo), timeout=60.0):
        cur = _load_processed_unlocked(jogo)
        cur |= set(new_ids)
        lst = list(cur)[-5000:]
        tmp = p.with_name(f"{p.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(p))
        return set(lst)


def _job_id(job: dict) -> str:
    if job.get("id"):
        return str(job["id"])
    return json.dumps(
        {
            "historico": job.get("historico") or job.get("hist") or [],
            "settled": job.get("settled"),
            "mults": job.get("mults"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def enfileirar_job(
    jogo: str,
    historico: List[Any],
    settled: Optional[List[Any]] = None,
    mults: Optional[List[Any]] = None,
    job_id: Optional[str] = None,
) -> str:
    """
    Única forma suportada de colocar trabalho na fila.

    Grava um arquivo imutável em data_inbox/pending/{jogo}.{id}.json
    sob o lock curto da fila do jogo.
    """
    if jogo not in JOGOS:
        raise ValueError(f"jogo inválido: {jogo}; use um de {JOGOS}")
    if not historico:
        raise ValueError("historico vazio")
    jid = str(job_id) if job_id else uuid.uuid4().hex
    job = {
        "id": jid,
        "historico": list(historico),
        "settled": list(settled) if settled is not None else None,
        "mults": list(mults) if mults is not None else None,
        "enfileirado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    pending = _pending_dir()
    dest = pending / f"{jogo}.{jid}.json"
    with file_lock(_queue_lock_path(jogo), timeout=30.0):
        if dest.exists():
            # mesmo id já enfileirado — idempotente
            return jid
        tmp = pending / f"{jogo}.{jid}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(dest))
    return jid


def listar_pendentes(jogo: str) -> List[str]:
    """IDs ainda em pending/ (não claimados)."""
    out = []
    for p in sorted(_pending_dir().glob(f"{jogo}.*.json")):
        # ignora .tmp
        if p.name.endswith(".tmp"):
            continue
        # nome: jogo.id.json
        parts = p.name.split(".")
        if len(parts) >= 3 and parts[0] == jogo:
            out.append(".".join(parts[1:-1]))
    return out


def _claim_age_sec(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0.0


def _recuperar_claims_abandonados(jogo: str, lease_sec: float = CLAIM_LEASE_SEC) -> None:
    """Reinsere .claim antigos de volta em pending/ (não no JSONL legado)."""
    base = _inbox_dir()
    pending = _pending_dir()
    for claim in sorted(base.glob(f"{jogo}.claim.*.jsonl")):
        age = _claim_age_sec(claim)
        if age < lease_sec:
            continue
        try:
            jobs = []
            for line in claim.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    jobs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            for job in jobs:
                jid = _job_id(job)
                dest = pending / f"{jogo}.{jid}.json"
                if not dest.exists():
                    tmp = pending / f"{jogo}.{jid}.{uuid.uuid4().hex}.tmp"
                    tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
                    os.replace(str(tmp), str(dest))
            claim.unlink(missing_ok=True)
            print(f"[academia_servico] claim abandonado → pending {claim.name} age={age:.0f}s")
        except OSError as e:
            print(f"[academia_servico] falha recover {claim.name}: {e}")


def _migrar_jsonl_legado(jogo: str) -> None:
    """Se ainda existir {jogo}.jsonl, move jobs para pending/ uma vez."""
    src = _inbox_dir() / f"{jogo}.jsonl"
    if not src.is_file():
        return
    try:
        text = src.read_text(encoding="utf-8")
    except OSError:
        return
    pending = _pending_dir()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            continue
        jid = _job_id(job)
        job["id"] = jid
        dest = pending / f"{jogo}.{jid}.json"
        if dest.exists():
            continue
        tmp = pending / f"{jogo}.{jid}.{uuid.uuid4().hex}.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(dest))
    src.unlink(missing_ok=True)


def _consumir_fila(jogo: str, lease_sec: float = CLAIM_LEASE_SEC) -> int:
    """
    consumer.lock durante TODO o consumo (inclui processar longo).
    queue.lock só nas operações rápidas (migrar/recover/claim/requeue).
    Produtores usam só queue.lock e podem enfileirar em paralelo.
    Segundo consumidor bloqueia no consumer.lock — não recupera claim ativo.
    """
    try:
        cons_cm = file_lock(_consumer_lock_path(jogo), timeout=5.0)
        cons_cm.__enter__()
    except TimeoutError:
        print(f"[academia_servico] {jogo}: outro consumidor ativo — saindo")
        return 0
    claim = None
    jobs = []
    n = 0
    try:
        # --- operações rápidas sob queue.lock ---
        with file_lock(_queue_lock_path(jogo), timeout=60.0):
            _migrar_jsonl_legado(jogo)
            _recuperar_claims_abandonados(jogo, lease_sec=lease_sec)
            pending = _pending_dir()
            files = sorted(
                p for p in pending.glob(f"{jogo}.*.json") if not p.name.endswith(".tmp")
            )
            if not files:
                return 0
            claim = _inbox_dir() / f"{jogo}.claim.{os.getpid()}.{uuid.uuid4().hex}.jsonl"
            claimed_paths = []
            for fp in files:
                try:
                    job = json.loads(fp.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as e:
                    print(f"[academia_servico] pending inválido {fp.name}: {e}")
                    continue
                jobs.append(job)
                claimed_paths.append(fp)
            if not jobs:
                return 0
            claim.write_text(
                "".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs),
                encoding="utf-8",
            )
            for fp in claimed_paths:
                fp.unlink(missing_ok=True)
        # --- processar COM consumer.lock ainda segurado (pode > lease) ---
        processed = _load_processed_unlocked(jogo)
        pendentes = []
        novos_ok = set()
        try:
            for idx, job in enumerate(jobs):
                jid = _job_id(job)
                if jid in processed or jid in novos_ok:
                    continue
                hist = job.get("historico") or job.get("hist") or []
                if not hist:
                    novos_ok.add(jid)
                    continue
                try:
                    out = processar(
                        jogo, hist, settled=job.get("settled"), mults=job.get("mults")
                    )
                    print(
                        f"[academia_servico] {jogo} processado id={jid[:12]} "
                        f"n={len(hist)} operavel={out.get('operavel')}"
                    )
                    novos_ok.add(jid)
                    n += 1
                except Exception as e:
                    print(f"[academia_servico] erro job {jid[:40]}: {e}")
                    pendentes.append(job)
                    pendentes.extend(jobs[idx + 1 :])
                    break
        finally:
            if novos_ok:
                _merge_processed(jogo, novos_ok)
            if pendentes:
                with file_lock(_queue_lock_path(jogo), timeout=30.0):
                    for job in pendentes:
                        jid = _job_id(job)
                        dest = _pending_dir() / f"{jogo}.{jid}.json"
                        if dest.exists():
                            continue
                        tmp = _pending_dir() / f"{jogo}.{jid}.{uuid.uuid4().hex}.tmp"
                        tmp.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
                        os.replace(str(tmp), str(dest))
            if claim is not None:
                done = _inbox_dir() / f"{jogo}.done.{os.getpid()}.{uuid.uuid4().hex}.jsonl"
                try:
                    if claim.exists():
                        os.rename(str(claim), str(done))
                except OSError:
                    claim.unlink(missing_ok=True)
        return n
    finally:
        cons_cm.__exit__(None, None, None)


def status_fila(jogo: str) -> Dict[str, Any]:
    pend = listar_pendentes(jogo)
    proc = _load_processed_unlocked(jogo)
    return {
        "jogo": jogo,
        "pendentes": pend,
        "n_pendentes": len(pend),
        "n_processados": len(proc),
        "processados_sample": list(proc)[-10:],
    }


def main():
    ap = argparse.ArgumentParser(description="Academia serviço — fila oficial")
    ap.add_argument("--jogo", default="all", choices=list(JOGOS) + ["all"])
    ap.add_argument("--intervalo", type=float, default=15.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    jogos = list(JOGOS) if args.jogo == "all" else [args.jogo]
    print(f"[academia_servico] jogos={jogos} inbox={_inbox_dir()}")
    print("[academia_servico] Use academia_servico.enfileirar_job(...) — não escreva JSONL direto.")
    if args.once:
        total = sum(_consumir_fila(j) for j in jogos)
        print(f"[academia_servico] once: jobs_processados={total}")
        return
    try:
        while True:
            total = sum(_consumir_fila(j) for j in jogos)
            print(f"[academia_servico] heartbeat {time.strftime('%H:%M:%S')} processados={total}")
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("[academia_servico] encerrado")


if __name__ == "__main__":
    main()
