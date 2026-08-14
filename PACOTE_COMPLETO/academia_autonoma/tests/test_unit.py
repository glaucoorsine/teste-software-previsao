# -*- coding: utf-8 -*-
from __future__ import annotations
import random
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academia_autonoma.critico_cientifico import fdr_bh
from academia_autonoma.residuo_core import congelar_opinioes, avaliar_congeladas
from academia_autonoma.agentes_residuais import listar_metodos
from academia_autonoma.ciclo_residual import pool_meta_dinamic
from academia_autonoma.meta_supervisora import decidir
from academia_autonoma.ativador_familiaridades import ativar
from academia_autonoma.integrador_evidencias import convergencia
from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.catalogo_persistente import listar, merge
from academia_autonoma.dsl_hipoteses import make_hipotese


class TestPacote(unittest.TestCase):
    def test_import_package(self):
        import academia_autonoma
        self.assertTrue(hasattr(academia_autonoma, "ciclo"))

    def test_20_residual_methods(self):
        ms = listar_metodos()
        self.assertEqual(len(ms), 20)
        self.assertEqual(len({m["classe"] for m in ms}), 20)

    def test_fdr_bh(self):
        qs = fdr_bh([0.001, 0.02, 0.5, 0.8], alpha=0.1)
        self.assertEqual(len(qs), 4)
        self.assertLess(qs[0], qs[2])

    def test_residual_when_predicted(self):
        import time
        ds = f"res_pred_{int(time.time()*1000)%100000}"
        congelar_opinioes(ds, f"e_pred_{ds}", "5", {"PADRAO": 0.8}, {"PADRAO": ["5", "6"]})
        res = avaliar_congeladas(ds, "5", max_n=5)
        self.assertTrue(res)
        self.assertLessEqual(res[0]["residual_score"], 0.85)  # heurística de score pode variar

    def test_residual_when_missed(self):
        import time
        ds = f"res_miss_{int(time.time()*1000)%100000}"
        congelar_opinioes(ds, f"e_miss_{ds}", "7", {"PADRAO": 0.5}, {"PADRAO": ["1", "2", "3"]})
        res = avaliar_congeladas(ds, "9", max_n=5)
        self.assertTrue(res)
        self.assertGreaterEqual(res[0]["residual_score"], 0.5)

    def test_meta_no_validate_without_shadow(self):
        t = {
            "critica_ok": True,
            "prospectivo": {"n": 0, "hits": 0, "misses": 0},
            "retrospectivo": {"replay": {"n": 20, "taxa": 0.4}, "ganho": 0.15, "baseline": {"taxa": 0.2}},
            "evidencia": {"n_ret": 20, "n_prosp": 0, "ganho": 0.15},
            "teste_negativo": {"p_valor_emp": 0.01, "q_valor": 0.02},
            "q_valor": 0.02,
        }
        self.assertEqual(decidir(t), "em_teste")

    def test_meta_rejects_weak_prospectivo(self):
        # 1/8 = 12.5% não valida
        t = {
            "critica_ok": True,
            "prospectivo": {"n": 8, "hits": 1, "misses": 7, "taxa": 0.125},
            "retrospectivo": {"replay": {"n": 20, "taxa": 0.4}, "ganho": 0.15, "baseline": {"taxa": 0.2}},
            "evidencia": {"n_ret": 20, "n_prosp": 8, "ganho": 0.15},
            "teste_negativo": {"p_valor_emp": 0.01, "q_valor": 0.02},
            "q_valor": 0.02,
        }
        self.assertEqual(decidir(t), "em_teste")

    def test_meta_validate_with_good_shadow(self):
        t = {
            "critica_ok": True,
            "prospectivo": {"n": 10, "hits": 4, "misses": 6, "taxa": 0.4},
            "retrospectivo": {"replay": {"n": 20, "taxa": 0.4}, "ganho": 0.15, "baseline": {"taxa": 0.2}},
            "evidencia": {"n_ret": 20, "n_prosp": 10, "ganho": 0.15},
            "teste_negativo": {"p_valor_emp": 0.01, "q_valor": 0.02},
            "q_valor": 0.02,
        }
        self.assertEqual(decidir(t), "validada_dormente")

    def test_ativador_quarentena_sem_sombra(self):
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", "t1", "t1", 20)
        t["estado"] = "em_teste"
        t["prospectivo"] = {"n": 0}
        hist = ["1", "2", "3"]
        t = ativar(t, hist, [str(i) for i in range(37)])
        self.assertEqual(t.get("ativacao"), "QUARENTENA_SOMBRA")

    def test_ativador_no_active_without_shadow(self):
        t = make_hipotese({"op": "in_set", "set": ["1"]}, "A01", "t1", "t1", 20)
        t["estado"] = "validada_dormente"
        t["prospectivo"] = {"n": 0}
        hist = ["1"] + [str(i) for i in range(10)]
        t = ativar(t, hist, [str(i) for i in range(37)])
        self.assertNotEqual(t.get("ativacao"), "ATIVA")

    def test_integrador_sem_sombra(self):
        c = {
            "estado_historico": "validada_dormente",
            "estado_ativacao": "ATIVA",
            "amostra_prospectiva": 0,
            "shadow_n": 0,
            "efeito_vs_baseline": 0.1,
            "p_valor": 0.01,
        }
        r = convergencia(c, [], True)
        self.assertEqual(r["status"], "SEM_EVIDÊNCIA")

    def test_pool_zero_to_seven(self):
        pool = pool_meta_dinamic([], [], [], max_n=7)
        self.assertEqual(pool["n"], 0)

    def test_iid_false_validation_rate(self):
        n_series = 12
        total_val = 0
        for s in range(n_series):
            rng = random.Random(4000 + s)
            hist = [rng.randint(0, 36) for _ in range(50)]
            ciclo(f"ctrl3_{s}", hist)
            vals = [t for t in listar(f"ctrl3_{s}") if str(t.get("estado", "")).startswith("validada")]
            total_val += len(vals)
        self.assertEqual(total_val, 0)

    def test_e2e_shadow_accumulates(self):
        """Vários ciclos com timestamps: sombra deve acumular."""
        from academia_autonoma.ciclo_academia import ciclo
        from academia_autonoma.catalogo_persistente import listar
        ds = "e2e_shadow_ts"
        base = ["1", "2", "3", "4", "1", "2", "3", "4"]
        max_n = 0
        pendentes = 0
        for i in range(25):
            hist = (base * 8)[i:] + [str((i + 5) % 10)]
            hist = hist[:40]
            settled = [str(8000 + i - k) for k in range(len(hist))]
            ciclo(ds, hist, settled=settled)
            for t in listar(ds):
                n_ = int((t.get("prospectivo") or {}).get("n") or 0)
                max_n = max(max_n, n_)
                if (t.get("prospectivo") or {}).get("pendente"):
                    pendentes += 1
        self.assertTrue(
            max_n > 0 or pendentes > 0,
            f"deadlock sombra: max_n={max_n} pendentes_seen={pendentes}",
        )
        vals = [t for t in listar(ds) if str(t.get("estado", "")).startswith("validada")]
        for t in vals:
            self.assertGreaterEqual(int((t.get("prospectivo") or {}).get("n") or 0), 8)
        print(f"E2E shadow max_n={max_n} pendentes_seen={pendentes} validada={len(vals)}")




    def test_qualidade_rejeita_invalido(self):
        from academia_autonoma.schema_eventos import eventos_de_historico
        from academia_autonoma.qualidade_dados import validar
        inv = []
        ev = eventos_de_historico(["1", "999", "2"], "mega_fire", invalidos_out=inv)
        q = validar(ev, "mega_fire", invalidos=inv)
        self.assertFalse(q["ok"])
        self.assertIn("999", inv)
        self.assertTrue(any("entrada_invalida" in str(x) for x in q.get("problemas") or []))

    def test_registrar_exige_dataset(self):
        from academia_autonoma.catalogo_persistente import registrar_prospectivo
        with self.assertRaises(ValueError):
            registrar_prospectivo("x", "1", True, dataset_id=None)

    def test_meta_loads_shadow_memory(self):
        """Proposta nova hidratada com sombra do catálogo antes de decidir."""
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.meta_supervisora import decidir
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", "hyd_ds", "hyd_ds", 20)
        t["estado"] = "em_teste"
        t["critica_ok"] = True
        t["prospectivo"] = {"n": 10, "hits": 4, "misses": 6, "taxa": 0.4}
        t["retrospectivo"] = {"replay": {"n": 20, "taxa": 0.4}, "ganho": 0.15, "baseline": {"taxa": 0.2}}
        t["teste_negativo"] = {"p_valor_emp": 0.01, "q_valor": 0.02}
        t["q_valor"] = 0.02
        merge(t)
        # proposta "nova" sem prosp
        t2 = make_hipotese({"op": "last_is", "valor": "1"}, "A01", "hyd_ds", "hyd_ds", 20)
        t2["critica_ok"] = True
        t2["retrospectivo"] = t["retrospectivo"]
        t2["teste_negativo"] = t["teste_negativo"]
        t2["q_valor"] = 0.02
        old = get(t2["id"], "hyd_ds")
        self.assertIsNotNone(old)
        t2["prospectivo"] = old.get("prospectivo")
        self.assertEqual(decidir(t2), "validada_dormente")

    def test_shadow_repeat_event(self):
        """Com timestamps, 1→1 fecha sombra."""
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        from academia_autonoma.stream_seq import peek_seq
        ds = "rep_shadow_ts"
        hist1 = (["2", "3", "4", "5"] * 8)[:32]
        ts1 = [str(1000 - i) for i in range(32)]
        ciclo(ds, hist1, settled=ts1)
        cur = peek_seq(ds)
        t = make_hipotese({"op": "last_is", "valor": "2"}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        t["critica_ok"] = True
        t["prospectivo"] = {
            "n": 0, "hits": 0, "misses": 0, "hist": [],
            "pendente": {
                "alvos": ["1"],
                "head": hist1[0],
                "hist_fingerprint": ["seq", cur],
                "opened_seq": cur,
            },
        }
        merge(t)
        hist2 = ["1"] + hist1
        ts2 = ["1001"] + ts1
        ciclo(ds, hist2, settled=ts2)
        t2 = get(t["id"], ds)
        n = int((t2.get("prospectivo") or {}).get("n") or 0)
        self.assertGreaterEqual(n, 1, "sombra não fechou no novo evento")

    def test_residual_freeze_idempotent(self):
        from academia_autonoma.residuo_core import congelar_opinioes, avaliar_congeladas
        ds = "idemp_res"
        a = congelar_opinioes(ds, "e1", "7", {"PADRAO": 0.5}, {"PADRAO": ["1", "2"]})
        b = congelar_opinioes(ds, "e1", "7", {"PADRAO": 0.5}, {"PADRAO": ["1", "2"]})
        self.assertEqual(a["decision_id"], b["decision_id"])
        res = avaliar_congeladas(ds, "9", max_n=10)
        ids = [r["decision_id"] for r in res]
        self.assertEqual(len(ids), len(set(ids)))


    def test_paths_portateis(self):
        from academia_autonoma.paths_dados import data_root, subdir
        root = data_root()
        self.assertTrue(root.exists())
        b = subdir("bus")
        r = subdir("residuo")
        self.assertTrue(b.exists())
        self.assertTrue(r.exists())

    def test_detector_regime(self):
        from academia_autonoma.detector_regimes import detectar
        r = detectar(["1"] * 10 + ["2"] * 30)
        self.assertIn("regime", r)

    def test_relatorio(self):
        from academia_autonoma.relatorio_academico import gerar
        from academia_autonoma.ciclo_academia import ciclo
        ciclo("rel_ds", list(range(40)))
        rep = gerar("rel_ds", [str(i) for i in range(40)])
        self.assertIn("total_teorias", rep)

    def test_iid_multiciclo(self):
        """Vários ciclos por série IID — ainda sem validação falsa."""
        n_series = 5
        total_val = 0
        for s in range(n_series):
            rng = random.Random(9000 + s)
            hist = [rng.randint(0, 36) for _ in range(40)]
            ds = f"iid_mc_{s}"
            for step in range(6):
                ciclo(ds, hist[step:] + hist[:step])
            vals = [t for t in listar(ds) if str(t.get("estado", "")).startswith("validada")]
            total_val += len(vals)
        self.assertEqual(total_val, 0, f"falsas validacoes multiciclo={total_val}")


    def test_migracao_legado_nao_avalia(self):
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        ds = "mig_leg"
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        t["prospectivo"] = {
            "n": 0, "hits": 0, "misses": 0, "hist": [],
            "pendente": {"alvos": ["1"], "head": "1", "hist_fingerprint": ["1","2","3"]},  # legado
        }
        merge(t)
        ciclo(ds, ["9","8","7","6","5"])
        t2 = get(t["id"], ds)
        self.assertEqual(int((t2.get("prospectivo") or {}).get("n") or 0), 0)
        self.assertIsNone((t2.get("prospectivo") or {}).get("pendente"))

    def test_baseline_persisted(self):
        from academia_autonoma.catalogo_persistente import merge, get, registrar_prospectivo
        from academia_autonoma.dsl_hipoteses import make_hipotese
        ds = "base_pers"
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        t["prospectivo"] = {"n": 0, "hits": 0, "misses": 0, "hist": [], "pendente": None}
        merge(t)
        registrar_prospectivo(t["id"], "1", True, dataset_id=ds, candidatos=["1"], baseline_hit=True, baseline_alvos=["1"])
        t2 = get(t["id"], ds)
        h = (t2.get("prospectivo") or {}).get("hist") or []
        self.assertTrue(h)
        self.assertTrue(h[-1].get("baseline_hit") is True)
        # segundo merge com mesmo n não pode apagar
        t2["estado"] = "em_teste"
        merge(t2)
        t3 = get(t["id"], ds)
        h3 = (t3.get("prospectivo") or {}).get("hist") or []
        self.assertTrue(h3[-1].get("baseline_hit") is True)

    def test_long_repeat_shadow(self):
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        from academia_autonoma.stream_seq import peek_seq
        ds = "longrep3"
        hist = ["7"] * 10
        ts1 = [f"{i:04d}" for i in range(100, 90, -1)]
        ciclo(ds, hist, settled=ts1)
        t = make_hipotese({"op": "last_is", "valor": "7"}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        t["critica_ok"] = True
        cur = peek_seq(ds)
        t["prospectivo"] = {
            "n": 0, "hits": 0, "misses": 0, "hist": [],
            "pendente": {"alvos": ["7"], "head": "7", "hist_fingerprint": ["seq", cur], "opened_seq": cur},
        }
        merge(t)
        # janela fixa 10x7 com NOVO timestamp na cabeça
        ts2 = [f"{i:04d}" for i in range(101, 91, -1)]
        ciclo(ds, hist, settled=ts2)
        t2 = get(t["id"], ds)
        self.assertGreaterEqual(int((t2.get("prospectivo") or {}).get("n") or 0), 1)

    def test_replay_same_dataset(self):
        from academia_autonoma.replay_offline import replay
        from academia_autonoma.ciclo_academia import ciclo
        ids = []
        def fn(ds, past):
            ids.append(ds)
            return ciclo(ds, past)
        h = [str(i % 10) for i in range(45)]
        out = replay(h, fn, "rp_one", passo_min=30, max_passos=5)
        self.assertEqual(out.get("dataset_id"), "rp_one")
        self.assertTrue(ids)
        self.assertTrue(all(x == "rp_one" for x in ids))
        self.assertGreaterEqual(out.get("passos", 0), 1)

    def test_event_id_stable(self):
        from academia_autonoma.event_log import count_new_in_window
        ds = "idstab_win2"
        ts1 = ["15","14","13","12","11"]
        a = count_new_in_window(ds, ["5", "4", "3", "2", "1"], ts1)
        ts2 = ["16","15","14","13","12"]
        b = count_new_in_window(ds, ["9", "5", "4", "3", "2"], ts2)
        id_a = {v: eid for eid, v in a["paired"]}
        id_b = {v: eid for eid, v in b["paired"]}
        for v in ("5", "4", "3", "2"):
            self.assertEqual(id_a[v], id_b[v], f"instavel {v}: {id_a.get(v)} vs {id_b.get(v)}")


    def test_same_snapshot_no_bump(self):
        from academia_autonoma.stream_seq import observe, peek_seq
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        ds = "snap_same"
        hist = [str(i) for i in range(20)]
        ciclo(ds, hist)
        s1 = peek_seq(ds)
        ciclo(ds, hist)  # same snapshot
        s2 = peek_seq(ds)
        self.assertEqual(s1, s2)

    def test_qualidade_antes_sombra(self):
        from academia_autonoma.stream_seq import peek_seq
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        ds = "qual_first"
        hist = [str(i) for i in range(15)]
        ciclo(ds, hist)
        cur = peek_seq(ds)
        t = make_hipotese({"op": "last_is", "valor": hist[0]}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        t["prospectivo"] = {
            "n": 0, "hits": 0, "misses": 0, "hist": [],
            "pendente": {"alvos": ["0"], "hist_fingerprint": ["seq", cur], "opened_seq": cur},
        }
        merge(t)
        n_before = 0
        out = ciclo(ds, ["999"] + hist)  # invalid
        msgs = " ".join(out.get("msgs") or []).lower()
        self.assertTrue("qualidade" in msgs or "inválid" in msgs or "invalid" in msgs or "rejeit" in msgs)
        t2 = get(t["id"], ds)
        self.assertEqual(int((t2.get("prospectivo") or {}).get("n") or 0), n_before)

    def test_ids_with_timestamps(self):
        from academia_autonoma.event_log import count_new_in_window
        ds = "ts_ids2"
        a = count_new_in_window(ds, ["7"] * 5, ["15","14","13","12","11"])
        b = count_new_in_window(ds, ["7"] * 5, ["16","15","14","13","12"])
        self.assertGreaterEqual(b["n_novos"], 1)
        self.assertNotEqual(a["paired"][0][0], b["paired"][0][0])

    def test_migracao_com_opened_seq_legado(self):
        from academia_autonoma.catalogo_persistente import merge, get
        from academia_autonoma.dsl_hipoteses import make_hipotese
        from academia_autonoma.ciclo_academia import ciclo
        ds = "mig_v27"
        hist = [str(i) for i in range(20)]
        t = make_hipotese({"op": "last_is", "valor": "0"}, "A01", ds, ds, 20)
        t["estado"] = "em_teste"
        # v27: opened_seq presente + fingerprint antigo
        t["prospectivo"] = {
            "n": 0, "hits": 0, "misses": 0, "hist": [],
            "pendente": {
                "alvos": ["0"],
                "opened_seq": 1,
                "hist_fingerprint": [20, "0", ["0"] * 8],
            },
        }
        merge(t)
        ciclo(ds, hist)
        t2 = get(t["id"], ds)
        self.assertEqual(int((t2.get("prospectivo") or {}).get("n") or 0), 0)
        self.assertIsNone((t2.get("prospectivo") or {}).get("pendente"))


    def test_regime_bloqueia_ativa(self):
        from academia_autonoma.ativador_familiaridades import ativar
        from academia_autonoma.dsl_hipoteses import make_hipotese
        t = make_hipotese({"op": "last_is", "valor": "1"}, "A01", "rg", "rg", 20)
        t["estado"] = "validada_dormente"
        t["prospectivo"] = {"n": 10, "hits": 4, "taxa": 0.4}
        hist = ["1"] + [str(i) for i in range(20)]
        t2 = ativar(t, hist, [str(i) for i in range(37)], regime={"mudanca": True, "regime": "TRANSICAO"})
        self.assertNotEqual(t2.get("ativacao"), "ATIVA")
        self.assertEqual(t2.get("ativacao"), "REATIVAÇÃO_EM_TESTE")

    def test_memoria_agente_regioes(self):
        from academia_autonoma.memoria_agentes import registrar_ciclo, carregar
        registrar_ciclo("mem_ds", "A01", 2, regioes=["r1"], rejeicoes=["x"], exprs=["e1"])
        m = carregar("mem_ds", "A01")
        self.assertIn("r1", m.get("regioes_exploradas") or [])
        self.assertGreaterEqual((m.get("stats") or {}).get("rejeicoes", 0), 1)

    def test_relatorio_trilha(self):
        from academia_autonoma.relatorio_academico import gerar
        from academia_autonoma.ciclo_academia import ciclo
        ciclo("rel2", list(range(40)))
        r = gerar("rel2", [str(i) for i in range(40)])
        self.assertIn("trilha_estatistica", r)
        self.assertIn("memoria_agentes", r)


if __name__ == "__main__":
    unittest.main()
