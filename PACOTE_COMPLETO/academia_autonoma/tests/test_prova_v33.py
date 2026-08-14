# -*- coding: utf-8 -*-
"""Provas explícitas das falhas da auditoria v32."""
from __future__ import annotations
import json
import multiprocessing as mp
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))

from academia_autonoma.memoria_agentes import registrar_ciclo, carregar
from academia_autonoma.residuo_core import congelar_opinioes, avaliar_congeladas, _path as res_path, _opin_path
from academia_autonoma.bus_mensagens import publicar, ler
from academia_autonoma.unica_academia import reset_para_testes


def _mem_worker(args):
    ds, ag, i = args
    try:
        registrar_ciclo(ds, ag, 1, nota=f"w{i}")
        return "ok"
    except Exception as e:
        return str(e)


def _res_worker(args):
    ds, resultado = args
    try:
        avaliar_congeladas(ds, resultado, max_n=5)
        return "ok"
    except Exception as e:
        return str(e)


class TestProvaV33(unittest.TestCase):
    def setUp(self):
        reset_para_testes()

    def test_memoria_8_processos_preserva_8(self):
        ds = f"mem8_{os.getpid()}"
        ag = "A01"
        with mp.Pool(8) as pool:
            res = pool.map(_mem_worker, [(ds, ag, i) for i in range(8)])
        self.assertTrue(all(r == "ok" for r in res), res)
        m = carregar(ds, ag)
        self.assertEqual(int(m.get("ciclos") or 0), 8, m)

    def test_residual_avaliacao_sem_duplicata(self):
        ds = f"resdup_{os.getpid()}"
        r = congelar_opinioes(ds, "e1", "7", {"estatistico": 0.2}, {"estatistico": ["7"]})
        self.assertFalse(r.get("duplicado"))
        with mp.Pool(5) as pool:
            pool.map(_res_worker, [(ds, "9")] * 5)
        lines = []
        p = res_path(ds)
        if p.is_file():
            lines = p.read_text(encoding="utf-8").strip().splitlines()
        ids = []
        for line in lines:
            ids.append(json.loads(line).get("decision_id"))
        self.assertEqual(len(ids), 1, f"duplicados={ids}")
        self.assertEqual(ids[0], r["decision_id"])

    def test_bus_usa_lock_e_preserva(self):
        ds = f"bus_{os.getpid()}"
        for i in range(5):
            publicar(ds, "interface.atualizar", "TEST", {"n": i})
        msgs = ler(ds, limit=20)
        self.assertGreaterEqual(len(msgs), 5)

    def test_adapter_api_completa(self):
        import academia_agentes as aa
        import academia_db as adb
        for name in ("get_academia", "feed_tail", "snapshot_somente_leitura", "PROTOCOLO", "conhecimento_validado_para_motor"):
            self.assertTrue(hasattr(aa, name), name)
        ac = aa.get_academia("mega_fire")
        self.assertTrue(hasattr(ac, "chat"))
        txt = ac.chat("A01", "status?")
        self.assertIn("PROTOCOLO", txt)
        feed = aa.feed_tail("mega_fire", 5)
        if feed:
            for k in ("horario", "jogo", "agente", "etapa", "amostra", "acao", "resultado", "proximo"):
                self.assertIn(k, feed[0], k)
        self.assertTrue(hasattr(adb, "list_hipoteses"))
        self.assertTrue(hasattr(adb, "get_meta"))
        self.assertTrue(hasattr(adb, "conhecimento_validado_para_motor"))
        meta = adb.get_meta("mega_fire")
        self.assertIn("total", meta)

    def test_feed_campos_apos_ciclo(self):
        import academia_agentes as aa
        from academia_autonoma.ciclo_academia import ciclo
        ds = f"feed_{os.getpid()}"
        hist = [str(i % 10) for i in range(20)]
        settled = [str(1000 - i) for i in range(20)]
        aa.get_academia(ds).ciclo(hist, settled=settled)
        feed = aa.feed_tail(ds, 10)
        self.assertGreater(len(feed), 0)
        for k in ("horario", "jogo", "agente", "etapa", "amostra", "acao", "resultado", "proximo"):
            self.assertIn(k, feed[-1], k)


if __name__ == "__main__":
    unittest.main()
