# -*- coding: utf-8 -*-
"""Concorrência inbox: um consumidor, processed_ids atômico."""
from __future__ import annotations
import json
import multiprocessing as mp
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))


def _two_consumer_worker(args):
    base, jogo = args
    import academia_servico as srv
    from unittest.mock import patch

    def fp(ds, hist, settled=None, mults=None):
        log = Path(base) / "calls.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write("CALL\n")
            f.flush()
        time.sleep(0.25)
        return {"operavel": False, "msgs": []}

    with patch.object(srv, "_inbox_dir", return_value=Path(base)):
        with patch.object(srv, "processar", side_effect=fp):
            return srv._consumir_fila(jogo, lease_sec=3600.0)


def _processed_worker(args):
    base, jogo, jid = args
    import academia_servico as srv
    with mock.patch.object(srv, "_inbox_dir", return_value=Path(base)):
        try:
            srv._merge_processed(jogo, {jid})
            return "ok"
        except Exception as e:
            return f"err:{type(e).__name__}:{e}"


class TestInboxV36(unittest.TestCase):
    def test_dois_consumidores_uma_execucao(self):
        base = Path(tempfile.mkdtemp())
        jogo = "mega_fire"
        job = {"id": "JOB-ONE", "historico": ["1", "2", "3"]}
        (base / f"{jogo}.jsonl").write_text(json.dumps(job) + "\n", encoding="utf-8")
        with mp.Pool(2) as pool:
            results = pool.map(_two_consumer_worker, [(str(base), jogo)] * 2)
        self.assertEqual(sum(results), 1, f"results={results}")
        log = base / "calls.log"
        n_calls = log.read_text(encoding="utf-8").count("CALL") if log.is_file() else 0
        self.assertEqual(n_calls, 1, f"calls={n_calls}")

    def test_claim_ativo_nao_recuperado(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        jogo = "lightning"
        claim = base / f"{jogo}.claim.111.alive.jsonl"
        claim.write_text(json.dumps({"id": "LIVE", "historico": ["9"]}) + "\n", encoding="utf-8")
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            srv._recuperar_claims_abandonados(jogo, lease_sec=120.0)
        self.assertTrue(claim.exists())

    def test_claim_velho_recuperado(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        jogo = "immersive"
        claim = base / f"{jogo}.claim.222.old.jsonl"
        claim.write_text(json.dumps({"id": "OLD", "historico": ["8"]}) + "\n", encoding="utf-8")
        old = time.time() - 500
        os.utime(claim, (old, old))
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            srv._recuperar_claims_abandonados(jogo, lease_sec=120.0)
        self.assertFalse(claim.exists())
        # v37+: recover vai para pending/
        pend_files = list((base / "pending").glob(f"{jogo}.*.json")) if (base / "pending").exists() else []
        text = "".join(f.read_text(encoding="utf-8") for f in pend_files)
        self.assertIn("OLD", text)

    def test_processed_16_processos(self):
        base = Path(tempfile.mkdtemp())
        jogo = "crazy_time"
        ids = [f"ID-{i}" for i in range(16)]
        with mp.Pool(16) as pool:
            res = pool.map(_processed_worker, [(str(base), jogo, i) for i in ids])
        self.assertTrue(all(r == "ok" for r in res), res)
        import academia_servico as srv
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            final = srv._load_processed_unlocked(jogo)
        self.assertEqual(len(final), 16, final)
        self.assertEqual(set(ids), final)


if __name__ == "__main__":
    unittest.main()
