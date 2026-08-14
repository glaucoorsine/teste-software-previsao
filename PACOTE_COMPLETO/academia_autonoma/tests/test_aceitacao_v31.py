# -*- coding: utf-8 -*-
from __future__ import annotations
import hashlib
import multiprocessing as mp
import os
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.catalogo_persistente import listar, get, merge, registrar_prospectivo
from academia_autonoma.stream_seq import peek_seq, apply_new_events
from academia_autonoma.event_log import count_new_in_window
from academia_autonoma.unica_academia import reset_para_testes, iniciar_ciclo, finalizar_ciclo, academia_ativa
from academia_autonoma.dsl_hipoteses import make_hipotese
from academia_autonoma.ciclo_residual import ciclo_residual

def _worker_reg(tid, ds):
    try:
        registrar_prospectivo(tid, "1", True, dataset_id=ds, candidatos=["1"], baseline_hit=False)
        return "ok"
    except Exception as e:
        return str(e)


class TestAceitacaoV31(unittest.TestCase):
    def setUp(self):
        reset_para_testes()

    def test_unica_academia(self):
        iniciar_ciclo("academia_autonoma")
        with self.assertRaises(RuntimeError):
            iniciar_ciclo("outra")
        finalizar_ciclo()
        self.assertEqual(academia_ativa(), "academia_autonoma")

    def test_snapshot_dez_vezes_inalterado(self):
        ds = "snap10"
        hist = [str(i % 10) for i in range(30)]
        ciclo(ds, hist)
        s0 = peek_seq(ds)
        n0 = len(listar(ds))
        # hash of catalog payloads
        def snap():
            return hashlib.sha256(
                "".join(sorted(str(t.get("id")) + str((t.get("prospectivo") or {}).get("n")) for t in listar(ds))).encode()
            ).hexdigest()
        h0 = snap()
        for _ in range(10):
            ciclo(ds, hist)
        self.assertEqual(peek_seq(ds), s0)
        self.assertEqual(snap(), h0)

    def test_invalido_sem_mutacao(self):
        ds = "inv_mut"
        hist = [str(i) for i in range(20)]
        ciclo(ds, hist)
        s0 = peek_seq(ds)
        n0 = len(listar(ds))
        out = ciclo(ds, ["999"] + hist)
        self.assertFalse(out.get("operavel"))
        self.assertEqual(peek_seq(ds), s0)
        self.assertEqual(len(listar(ds)), n0)

    def test_residual_idempotente(self):
        ds = "res_idemp"
        hist = [str(i) for i in range(20)]
        r1 = ciclo_residual(ds, hist, event_id="e1:s1", novo_evento=True, stream_n=1)
        r2 = ciclo_residual(ds, hist, event_id="e1:s1", novo_evento=False, stream_n=1)
        self.assertIn("snapshot repetido", " ".join(r2.get("msgs") or []))

    def test_n_novos_com_timestamps(self):
        ds = "nev"
        hist = ["1", "2", "3", "4", "5"]
        ts = ["10", "9", "8", "7", "6"]
        a = count_new_in_window(ds, hist, ts)
        self.assertIn(a["status"], ("OK", "BOOTSTRAP", "BOOTSTRAP_SEM_TS"))
        # second same
        b = count_new_in_window(ds, hist, ts)
        self.assertEqual(b["n_novos"], 0)
        # new head with ts
        hist2 = ["0"] + hist[:-1]
        ts2 = ["11"] + ts[:-1]
        c = count_new_in_window(ds, hist2, ts2)
        self.assertGreaterEqual(c["n_novos"], 1)

    def test_concorrencia_registrar(self):
        ds = "conc_reg_" + str(os.getpid())
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", ds, ds, 10)
        t["estado"] = "em_teste"
        t["prospectivo"] = {"n": 0, "hits": 0, "misses": 0, "hist": [], "pendente": None}
        merge(t)
        tid = t["id"]
        N = 20
        with mp.Pool(8) as pool:
            res = pool.starmap(_worker_reg, [(tid, ds)] * N)
        self.assertTrue(all(r == "ok" for r in res), res)
        t2 = get(tid, ds)
        self.assertEqual(int((t2.get("prospectivo") or {}).get("n") or 0), N)


    def test_congelar_sem_duplicata(self):
        from academia_autonoma.residuo_core import congelar_opinioes, _opin_path
        ds = "cong_dup"
        r1 = congelar_opinioes(ds, "e1", "7", {"A": 0.5}, {"A": ["7"]})
        r2 = congelar_opinioes(ds, "e1", "7", {"A": 0.5}, {"A": ["7"]})
        self.assertTrue(r2.get("duplicado"))
        lines = _opin_path(ds).read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)

    def test_adapter_api(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "PACOTE_COMPLETO") if False else str(ROOT.parent / "PACOTE_COMPLETO") if (ROOT.parent / "PACOTE_COMPLETO").exists() else str(ROOT / "PACOTE_COMPLETO") if (ROOT / "PACOTE_COMPLETO").exists() else ".")
        # path: artifacts/PACOTE_COMPLETO
        import importlib.util
        root = ROOT  # artifacts
        path = root / "PACOTE_COMPLETO" / "academia_agentes.py"
        if not path.is_file():
            path = root.parent / "PACOTE_COMPLETO" / "academia_agentes.py"
        self.assertTrue(path.is_file(), str(path))
        sys.path.insert(0, str(path.parent))
        import academia_agentes as aa
        self.assertTrue(hasattr(aa, "get_academia"))
        self.assertTrue(hasattr(aa, "feed_tail"))
        self.assertTrue(hasattr(aa, "snapshot_somente_leitura"))
        self.assertTrue(hasattr(aa, "PROTOCOLO"))


if __name__ == "__main__":
    unittest.main()
