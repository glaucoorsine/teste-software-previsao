# -*- coding: utf-8 -*-
"""v38: processamento > lease não duplica job entre consumidores."""
from __future__ import annotations
import multiprocessing as mp
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))


def _slow_worker(args):
    base, jogo, sleep_s = args
    import academia_servico as srv

    def fp(ds, hist, settled=None, mults=None):
        log = Path(base) / "calls.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write("CALL\n")
            f.flush()
        time.sleep(sleep_s)
        return {"operavel": False, "msgs": []}

    with patch.object(srv, "_inbox_dir", return_value=Path(base)):
        with patch.object(srv, "processar", side_effect=fp):
            # lease bem menor que o sleep → se recover errado, duplica
            return srv._consumir_fila(jogo, lease_sec=0.3)


class TestInboxV38(unittest.TestCase):
    def test_processamento_maior_que_lease_uma_execucao(self):
        base = Path(tempfile.mkdtemp())
        jogo = "mega_fire"
        import academia_servico as srv
        with patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            srv.enfileirar_job(jogo, ["1", "2", "3"], job_id="LONG-1")
        # 2 consumidores; processar demora 1.2s > lease 0.3s
        with mp.Pool(2) as pool:
            results = pool.map(_slow_worker, [(str(base), jogo, 1.2)] * 2)
        # exatamente uma execução bem-sucedida; o outro sai 0 (lock) ou espera e vê vazio
        self.assertEqual(sum(results), 1, f"results={results}")
        log = base / "calls.log"
        n_calls = log.read_text(encoding="utf-8").count("CALL") if log.is_file() else 0
        self.assertEqual(n_calls, 1, f"calls={n_calls}")

    def test_produtor_durante_processamento_longo(self):
        """Produtor (só queue.lock) enfileira enquanto consumer processa."""
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            srv.enfileirar_job("lightning", ["1"], job_id="P0")
            started = mp.Event() if False else None
            import threading
            ev = threading.Event()
            extra = {}

            def slow(ds, hist, settled=None, mults=None):
                ev.set()
                time.sleep(0.4)
                return {"operavel": False, "msgs": []}

            def prod():
                ev.wait(timeout=5)
                extra["id"] = srv.enfileirar_job("lightning", ["9"], job_id="P-DURING")

            with patch.object(srv, "processar", side_effect=slow):
                t = threading.Thread(target=prod)
                t.start()
                n = srv._consumir_fila("lightning", lease_sec=0.1)
                t.join(timeout=5)
            self.assertEqual(n, 1)
            self.assertIn(extra["id"], srv.listar_pendentes("lightning"))


if __name__ == "__main__":
    unittest.main()
