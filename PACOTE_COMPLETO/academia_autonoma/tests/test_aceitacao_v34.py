# -*- coding: utf-8 -*-
"""Aceitação v34 — dados genéricos ITEM-A/B, T1/T2."""
from __future__ import annotations
import hashlib
import json
import multiprocessing as mp
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))

from academia_autonoma.stream_seq import apply_new_events, peek_seq, _path as seq_path
from academia_autonoma.event_log import count_new_in_window
from academia_autonoma.memoria_agentes import registrar_ciclo, carregar
from academia_autonoma.residuo_core import congelar_opinioes, avaliar_congeladas, _path as res_path
from academia_autonoma.bus_mensagens import publicar, ler
from academia_autonoma.catalogo_persistente import merge, get, registrar_prospectivo
from academia_autonoma.dsl_hipoteses import make_hipotese
from academia_autonoma.unica_academia import (
    iniciar_ciclo, finalizar_ciclo, reset_para_testes, ciclo_em_curso
)
from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.paths_dados import subdir


def _ev_worker(args):
    ds, hist, settled = args
    try:
        info = count_new_in_window(ds, hist, settled)
        apply_new_events(ds, info["n_novos"], status=info["status"])
        return info["n_novos"]
    except Exception as e:
        return f"err:{e}"


def _mem_worker(args):
    ds, ag, i = args
    registrar_ciclo(ds, ag, 1, nota=f"ITEM-{i}")
    return "ok"


def _res_worker(args):
    ds, resultado = args
    avaliar_congeladas(ds, resultado, max_n=5)
    return "ok"


def _bus_worker(args):
    ds, n = args
    ids = []
    for i in range(n):
        m = publicar(ds, "interface.atualizar", "TEST", {"n": i, "item": "ITEM-A"})
        ids.append(m.get("message_id"))
    return ids


def _sql_worker(args):
    tid, ds = args
    registrar_prospectivo(tid, "ITEM-B", True, dataset_id=ds, candidatos=["ITEM-B"], baseline_hit=False)
    return "ok"


class TestAceitacaoV34(unittest.TestCase):
    def setUp(self):
        reset_para_testes()

    def test_bootstrap_persiste(self):
        ds = f"boot_{os.getpid()}"
        r1 = apply_new_events(ds, 0, status="BOOTSTRAP")
        self.assertEqual(r1["status"], "BOOTSTRAP")
        self.assertTrue(seq_path(ds).is_file())
        h1 = hashlib.sha256(seq_path(ds).read_bytes()).hexdigest()
        s1 = peek_seq(ds)
        r2 = apply_new_events(ds, 0, status="OK")
        self.assertEqual(r2["status"], "BOOTSTRAP")  # não muta
        self.assertEqual(peek_seq(ds), s1)
        h2 = hashlib.sha256(seq_path(ds).read_bytes()).hexdigest()
        self.assertEqual(h1, h2)
        r3 = apply_new_events(ds, 0, status="OK")
        self.assertEqual(peek_seq(ds), s1)
        self.assertEqual(hashlib.sha256(seq_path(ds).read_bytes()).hexdigest(), h1)

    def test_log_oito_processos_um_evento(self):
        ds = f"log8_{os.getpid()}"
        hist = ["ITEM-A", "ITEM-B"]
        settled = ["T2", "T1"]
        # bootstrap
        count_new_in_window(ds, hist, settled)
        apply_new_events(ds, 0, status="BOOTSTRAP")
        hist2 = ["ITEM-A", "ITEM-A", "ITEM-B"]
        settled2 = ["T3", "T2", "T1"]
        with mp.Pool(8) as pool:
            res = pool.map(_ev_worker, [(ds, hist2, settled2)] * 8)
        novos = [r for r in res if r == 1 or (isinstance(r, int) and r > 0)]
        self.assertGreaterEqual(len(novos), 1)
        # seq advances by total unique events once
        self.assertGreaterEqual(peek_seq(ds), 1)

    def test_memoria_8(self):
        ds = f"m8_{os.getpid()}"
        with mp.Pool(8) as pool:
            res = pool.map(_mem_worker, [(ds, "AG", i) for i in range(8)])
        self.assertTrue(all(r == "ok" for r in res))
        self.assertEqual(int(carregar(ds, "AG").get("ciclos") or 0), 8)

    def test_residuo_8(self):
        ds = f"r8_{os.getpid()}"
        r = congelar_opinioes(ds, "E1", "ITEM-A", {"estatistico": 0.5}, {"estatistico": ["ITEM-A"]})
        with mp.Pool(8) as pool:
            pool.map(_res_worker, [(ds, "ITEM-B")] * 8)
        lines = res_path(ds).read_text(encoding="utf-8").strip().splitlines() if res_path(ds).is_file() else []
        ids = [json.loads(x).get("decision_id") for x in lines]
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0], r["decision_id"])

    def test_bus_200(self):
        ds = f"b200_{os.getpid()}"
        with mp.Pool(8) as pool:
            all_ids = pool.map(_bus_worker, [(ds, 25)] * 8)
        flat = [i for sub in all_ids for i in sub]
        self.assertEqual(len(flat), 200)
        self.assertEqual(len(set(flat)), 200)
        msgs = ler(ds, limit=500)
        self.assertGreaterEqual(len(msgs), 200)

    def test_sqlite_8(self):
        ds = f"sql8_{os.getpid()}"
        t = make_hipotese({"op": "last_is", "valor": "ITEM-A"}, "A01", ds, ds, 10)
        t["estado"] = "em_teste"
        t["prospectivo"] = {"n": 0, "hits": 0, "misses": 0, "hist": [], "pendente": None}
        merge(t)
        with mp.Pool(8) as pool:
            res = pool.map(_sql_worker, [(t["id"], ds)] * 8)
        self.assertTrue(all(r == "ok" for r in res))
        t2 = get(t["id"], ds)
        self.assertEqual(int((t2.get("prospectivo") or {}).get("n") or 0), 8)
        self.assertEqual(len((t2.get("prospectivo") or {}).get("hist") or []), 8)

    def test_ciclo_excecao_libera(self):
        reset_para_testes()
        iniciar_ciclo("academia_autonoma")
        self.assertTrue(ciclo_em_curso())
        try:
            raise RuntimeError("injetada")
        except RuntimeError:
            finalizar_ciclo()
        self.assertFalse(ciclo_em_curso())
        # nova execução aceita
        iniciar_ciclo("academia_autonoma")
        finalizar_ciclo()

    def test_exclusividade_sobreposto(self):
        reset_para_testes()
        iniciar_ciclo("academia_autonoma")
        with self.assertRaises(RuntimeError):
            iniciar_ciclo("academia_autonoma")
        finalizar_ciclo()
        iniciar_ciclo("academia_autonoma")
        finalizar_ciclo()

    def test_qualidade_sem_arquivos(self):
        ds = f"qinv_{os.getpid()}"
        before = set(subdir("stream_seq").glob(f"*{ds}*")) if subdir("stream_seq").exists() else set()
        out = ciclo(ds, ["INVALID-XXX", "YYY"])
        self.assertFalse(out.get("operavel", True))
        after = set(subdir("stream_seq").glob(f"*{ds}*")) if subdir("stream_seq").exists() else set()
        self.assertEqual(before, after)
        self.assertFalse(seq_path(ds).is_file())

    def test_adaptadores(self):
        import academia_agentes as aa
        import academia_db as adb
        ac = aa.get_academia("mega_fire")
        self.assertTrue(callable(ac.chat))
        feed = aa.feed_tail("mega_fire", 3)
        for row in feed:
            for k in ("horario", "jogo", "agente", "etapa", "amostra", "acao", "resultado", "proximo"):
                self.assertIn(k, row)
        self.assertIsInstance(adb.list_hipoteses("mega_fire"), list)
        self.assertIn("total", adb.get_meta("mega_fire"))
        self.assertIsInstance(adb.conhecimento_validado_para_motor("mega_fire"), list)
        self.assertIsInstance(ac.conhecimento_validado_para_motor(), list)


if __name__ == "__main__":
    unittest.main()
