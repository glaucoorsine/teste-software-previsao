# -*- coding: utf-8 -*-
"""v37: enfileirar oficial, produtor durante consumo/requeue, IDs processados|pendentes."""
from __future__ import annotations
import json
import multiprocessing as mp
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]

def _two_cons_worker(args):
    b, j = args
    import academia_servico as s2
    from unittest.mock import patch
    import time
    from pathlib import Path

    def fp(ds, hist, settled=None, mults=None):
        log = Path(b) / "calls.log"
        with open(log, "a") as f:
            f.write("C\n")
        time.sleep(0.2)
        return {"operavel": False, "msgs": []}

    with patch.object(s2, "_inbox_dir", return_value=Path(b)):
        with patch.object(s2, "processar", side_effect=fp):
            return s2._consumir_fila(j, lease_sec=3600.0)


sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))


def _consumer_worker(args):
    base, jogo = args
    import academia_servico as srv
    from unittest.mock import patch

    def fp(ds, hist, settled=None, mults=None):
        time.sleep(0.15)
        return {"operavel": False, "msgs": []}

    with patch.object(srv, "_inbox_dir", return_value=Path(base)):
        # pending fica sob base/pending
        with patch.object(srv, "processar", side_effect=fp):
            return srv._consumir_fila(jogo, lease_sec=3600.0)


class TestInboxV37(unittest.TestCase):
    def test_enfileirar_e_consumir(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            jid = srv.enfileirar_job("mega_fire", ["1", "2", "3"], job_id="JOB-A")
            self.assertEqual(jid, "JOB-A")
            self.assertIn("JOB-A", srv.listar_pendentes("mega_fire"))
            with mock.patch.object(srv, "processar", return_value={"operavel": False, "msgs": []}):
                n = srv._consumir_fila("mega_fire", lease_sec=3600.0)
            self.assertEqual(n, 1)
            st = srv.status_fila("mega_fire")
            self.assertIn("JOB-A", st["processados_sample"] or list(srv._load_processed_unlocked("mega_fire")))
            self.assertEqual(st["n_pendentes"], 0)

    def test_produtor_durante_consumo(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            ids_sent = []
            for i in range(3):
                jid = srv.enfileirar_job("lightning", [str(i)], job_id=f"PRE-{i}")
                ids_sent.append(jid)

            started = threading.Event()
            extra_id = {}

            def slow_proc(ds, hist, settled=None, mults=None):
                started.set()
                time.sleep(0.3)
                return {"operavel": False, "msgs": []}

            def producer():
                started.wait(timeout=5)
                extra_id["id"] = srv.enfileirar_job(
                    "lightning", ["99"], job_id="DURING-1"
                )

            with mock.patch.object(srv, "processar", side_effect=slow_proc):
                t = threading.Thread(target=producer)
                t.start()
                n = srv._consumir_fila("lightning", lease_sec=3600.0)
                t.join(timeout=5)
            # pré-enfileirados processados
            self.assertEqual(n, 3)
            # o enfileirado durante deve ficar pendente
            pend = srv.listar_pendentes("lightning")
            proc = srv._load_processed_unlocked("lightning")
            self.assertIn(extra_id["id"], pend)
            self.assertNotIn(extra_id["id"], proc)
            for jid in ids_sent:
                self.assertIn(jid, proc)

    def test_produtor_durante_requeue(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            srv.enfileirar_job("immersive", ["1"], job_id="R1")
            srv.enfileirar_job("immersive", ["2"], job_id="R2")
            state = {"n": 0}
            during = {}

            def boom(ds, hist, settled=None, mults=None):
                state["n"] += 1
                if state["n"] == 1:
                    during["id"] = srv.enfileirar_job(
                        "immersive", ["7"], job_id="RQ-DURING"
                    )
                    raise RuntimeError("falha")
                return {"operavel": False, "msgs": []}

            with mock.patch.object(srv, "processar", side_effect=boom):
                n = srv._consumir_fila("immersive", lease_sec=3600.0)
            self.assertEqual(n, 0)
            pend = set(srv.listar_pendentes("immersive"))
            # R1 e R2 requeued + RQ-DURING
            self.assertIn("R1", pend)
            self.assertIn("R2", pend)
            self.assertIn(during["id"], pend)

    def test_dois_consumidores_uma_chamada(self):
        base = Path(tempfile.mkdtemp())
        jogo = "crazy_time"
        import academia_servico as srv
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            srv.enfileirar_job(jogo, ["1", "2"], job_id="ONLY-ONE")
        with mp.Pool(2) as pool:
            results = pool.map(_two_cons_worker, [(str(base), jogo)] * 2)
        self.assertEqual(sum(results), 1, results)
        n_calls = (base / "calls.log").read_text().count("C") if (base / "calls.log").is_file() else 0
        self.assertEqual(n_calls, 1)


    def test_ids_processados_ou_pendentes(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            sent = [srv.enfileirar_job("mega_fire", [str(i)], job_id=f"S{i}") for i in range(5)]
            with mock.patch.object(srv, "processar", return_value={"operavel": False, "msgs": []}):
                srv._consumir_fila("mega_fire", lease_sec=3600.0)
            # enfileira mais um sem consumir
            extra = srv.enfileirar_job("mega_fire", ["x"], job_id="SX")
            sent.append(extra)
            proc = srv._load_processed_unlocked("mega_fire")
            pend = set(srv.listar_pendentes("mega_fire"))
            for jid in sent:
                self.assertTrue(jid in proc or jid in pend, f"{jid} sumiu")


if __name__ == "__main__":
    unittest.main()
