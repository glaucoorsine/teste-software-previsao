# -*- coding: utf-8 -*-
"""Golden master resíduo v32 + inbox idempotente."""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "PACOTE_COMPLETO"))

from academia_autonoma.residuo_core import (
    congelar_opinioes, avaliar_congeladas, _score_explicacao, _path as res_path
)
from academia_autonoma.unica_academia import reset_para_testes


def _golden_score_clas(opinioes, cands, resultado):
    """Réplica pura da fórmula v32 (sem I/O)."""
    scores = {}
    ativos = []
    for fonte, lista in cands.items():
        conf = float(opinioes.get(fonte, 0.5))
        sc = _score_explicacao(lista, str(resultado), conf)
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
    return scores, round(consenso, 4), round(residual, 4), clas


class TestResiduoGolden(unittest.TestCase):
    def setUp(self):
        reset_para_testes()

    def test_tres_fixtures_coincidem_v32(self):
        fixtures = [
            (
                {"estatistico": 0.8, "anomalia": 0.1, "familiaridade": 0.2},
                {"estatistico": ["ITEM-A", "ITEM-B"], "anomalia": ["ITEM-C"], "familiaridade": ["ITEM-A"]},
                "ITEM-A",
            ),
            (
                {"estatistico": 0.2, "anomalia": 0.1},
                {"estatistico": ["ITEM-B"], "anomalia": ["ITEM-C"]},
                "ITEM-A",
            ),
            (
                {"A": 0.9},
                {"A": ["ITEM-A"]},
                "ITEM-A",
            ),
        ]
        for i, (op, cands, res) in enumerate(fixtures):
            ds = f"gm_{os.getpid()}_{i}"
            g_scores, g_cons, g_res, g_clas = _golden_score_clas(op, cands, res)
            congelar_opinioes(ds, f"E{i}", "ITEM-H", op, cands)
            out = avaliar_congeladas(ds, res, max_n=5)
            self.assertEqual(len(out), 1, f"fixture {i}")
            r = out[0]
            self.assertEqual(r["classificacao"], g_clas, f"fixture {i} clas")
            self.assertEqual(r["residual_score"], g_res, f"fixture {i} residual")
            self.assertEqual(r["consenso_total"], g_cons, f"fixture {i} consenso")
            for k, v in g_scores.items():
                self.assertIn(k, r, f"fixture {i} field {k}")
                self.assertAlmostEqual(r[k], v, places=5, msg=f"fixture {i} {k}")
            self.assertIn("candidatos_no_congelamento", r)
            self.assertIn("decision_id", r)
            self.assertIn("event_id", r)


class TestInbox(unittest.TestCase):
    def test_mesmo_id_nao_processa_duas_vezes(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            jogo = "mega_fire"
            job = {"id": "JOB-1", "historico": ["1", "2", "3"]}
            inbox = base / f"{jogo}.jsonl"
            # dois claims simulados: grava job, processa, grava de novo
            calls = []

            def fake_processar(ds, hist, settled=None, mults=None):
                calls.append(list(hist))
                return {"operavel": False, "msgs": []}

            with mock.patch.object(srv, "processar", side_effect=fake_processar):
                inbox.write_text(json.dumps(job) + "\n", encoding="utf-8")
                n1 = srv._consumir_fila(jogo)
                inbox.write_text(json.dumps(job) + "\n", encoding="utf-8")
                n2 = srv._consumir_fila(jogo)
            self.assertEqual(n1, 1)
            self.assertEqual(n2, 0)
            self.assertEqual(len(calls), 1)

    def test_excecao_requeue_pendentes(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            (base / "pending").mkdir(parents=True, exist_ok=True)
            jogo = "lightning"
            srv.enfileirar_job(jogo, ["1"], job_id="A")
            srv.enfileirar_job(jogo, ["2"], job_id="B")
            state = {"n": 0}

            def boom(ds, hist, settled=None, mults=None):
                state["n"] += 1
                if state["n"] == 1:
                    raise RuntimeError("falha injetada")
                return {"operavel": False, "msgs": []}

            with mock.patch.object(srv, "processar", side_effect=boom):
                n = srv._consumir_fila(jogo)
            self.assertEqual(n, 0)
            pend = list((base / "pending").glob(f"{jogo}.*.json"))
            text = "".join(f.read_text(encoding="utf-8") for f in pend)
            self.assertIn('"id": "A"', text)
            self.assertIn('"id": "B"', text)

    def test_recupera_claim_abandonado(self):
        import academia_servico as srv
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(srv, "_inbox_dir", return_value=base):
            jogo = "immersive"
            claim = base / f"{jogo}.claim.999.deadbeef.jsonl"
            claim.write_text(json.dumps({"id": "REC-1", "historico": ["9"]}) + "\n", encoding="utf-8")
            import time as _t, os as _os
            old = _t.time() - 500
            _os.utime(claim, (old, old))
            calls = []

            def fake(ds, hist, settled=None, mults=None):
                calls.append(hist)
                return {"operavel": False, "msgs": []}

            with mock.patch.object(srv, "processar", side_effect=fake):
                n = srv._consumir_fila(jogo, lease_sec=120.0)
            self.assertEqual(n, 1)
            self.assertEqual(len(calls), 1)
            self.assertFalse(claim.exists())


if __name__ == "__main__":
    unittest.main()
