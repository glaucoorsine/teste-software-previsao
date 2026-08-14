from __future__ import annotations
import sys, random
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from academia_autonoma.agentes_residuais import listar_metodos, AGENTES_R
from academia_autonoma.residuo_core import congelar_opinioes, avaliar_congeladas, listar_residuos
from academia_autonoma.ciclo_residual import pool_meta_dinamic, ciclo_residual
from academia_autonoma.ciclo_academia import ciclo

def test_20_metodos_distintos():
    ms = listar_metodos()
    assert len(ms) == 20
    assert len({m["classe"] for m in ms}) == 20
    print("OK 20 metodos", len(ms))

def test_congelar_antes_resultado():
    hist_head = "7"
    fr = congelar_opinioes("res_mf_test", "e1", hist_head, {"PADRAO": 0.5}, {"PADRAO": ["1","2","3"]})
    assert fr["avaliado"] is False
    assert fr["resultado_observado"] is None
    # revela 9
    res = avaliar_congeladas("res_mf_test", "9", max_n=5)
    assert any(r.get("resultado_observado") == "9" for r in res)
    # residual alto se 9 nao estava nos candidatos
    r0 = res[0]
    assert r0["residual_score"] >= 0.5
    print("OK residual apos congelar", r0["classificacao"], r0["residual_score"])

def test_explicado_nao_nao_explicado():
    ds = "res_light_explained"
    congelar_opinioes(ds, "e2", "5", {"PADRAO": 0.8}, {"PADRAO": ["5","6"]})
    res = avaliar_congeladas(ds, "5", max_n=5)
    assert res
    # pega o residual deste decision (o mais recente com resultado 5 e PADRAO)
    hit = [r for r in res if r.get("resultado_observado") == "5" and r.get("explicacao_padrao", 0) >= 0.4]
    assert hit, res
    assert hit[0]["residual_score"] < 0.75, hit[0]
    print("OK explicado residual baixo", hit[0]["residual_score"])

def test_sem_quotas():
    pool = pool_meta_dinamic([], [], [], max_n=7)
    assert pool["n"] == 0
    items = [
        {"categoria": "RESIDUAL", "descricao": f"r{i}", "estado_ativacao": "ATIVA",
         "estado_historico": "em_teste", "amostra_prospectiva": 10+i,
         "efeito_vs_baseline": 0.05, "expressao_dsl": {"op":"in_set","set":[str(i)]},
         "_convergencia": {"status": "CONVERGENTE", "indice": 0.4}}
        for i in range(5)
    ]
    pool = pool_meta_dinamic([], [], items, max_n=7)
    assert pool["composicao"]["RESIDUAL"] == pool["n"]  # pode ser só residual
    assert pool["n"] <= 7
    print("OK sem quotas", pool["composicao"])

def test_nao_completa_sete():
    pool = pool_meta_dinamic([], [], [
        {"categoria":"RESIDUAL","descricao":"so um","estado_ativacao":"ATIVA",
         "estado_historico":"em_teste","amostra_prospectiva":20,"efeito_vs_baseline":0.1,
         "expressao_dsl":{"op":"in_set","set":["1"]},
         "_convergencia":{"status":"CONVERGENTE","indice":0.5}}
    ], max_n=7)
    assert pool["n"] == 1
    print("OK nao completa sete")

def test_ciclo_integrado():
    hist = [str(i % 37) for i in range(45)]
    r = ciclo("res_mf_test", hist)
    assert "n_cartoes" in r
    assert 0 <= r["n_cartoes"] <= 7
    print("OK ciclo integrado n_cartoes", r["n_cartoes"], "pool", (r.get("pool") or {}).get("composicao"))

if __name__ == "__main__":
    test_20_metodos_distintos()
    test_congelar_antes_resultado()
    test_explicado_nao_nao_explicado()
    test_sem_quotas()
    test_nao_completa_sete()
    test_ciclo_integrado()
    print("RESIDUAL_OK")
