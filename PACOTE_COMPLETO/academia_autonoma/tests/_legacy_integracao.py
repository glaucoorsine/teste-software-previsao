# -*- coding: utf-8 -*-
from __future__ import annotations
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.catalogo_persistente import listar, merge, get
from academia_autonoma.contrato_familiaridade import para_contrato
from academia_autonoma.interface_pesquisa import selecionar_cartoes, candidatos_pesquisa
from academia_autonoma.opinioes_modelos import coletar_opinioes
from academia_autonoma.integrador_evidencias import convergencia
from academia_autonoma.bus_mensagens import ler
from academia_autonoma.dsl_hipoteses import make_hipotese

def test_nao_completa_sete():
    cards = selecionar_cartoes([], max_n=7)
    assert cards == []
    # 1 contrato fraco
    c = {
        "familiaridade_id": "x", "estado_historico": "em_teste",
        "estado_ativacao": "ATIVA", "agente_autor": "A01",
        "descricao": "t1", "horizonte_avaliacao": 1,
        "amostra_prospectiva": 2, "efeito_vs_baseline": 0.01, "p_valor": 0.5,
    }
    cards = selecionar_cartoes([c], max_n=7)
    assert len(cards) <= 1
    print("OK nao_completa_sete", len(cards))

def test_lstm_nao_altera_teoria():
    expr = {"op": "transition", "a": "1", "b": "2"}
    t = make_hipotese(expr, "A01", "mega_fire", "mega_fire", 20)
    t["estado"] = "validada_ativa"
    t["ativacao"] = "ATIVA"
    c = para_contrato(t)
    before = str(c["expressao_dsl"])
    hist = [str(i % 37) for i in range(30)]
    coletar_opinioes(hist, c, [str(i) for i in range(37)])
    assert str(c["expressao_dsl"]) == before
    print("OK lstm_nao_altera")

def test_integrador_nao_promove():
    c = {
        "estado_historico": "candidata", "estado_ativacao": "ATIVA",
        "amostra_prospectiva": 50, "efeito_vs_baseline": 0.2, "p_valor": 0.01,
    }
    r = convergencia(c, [], True)
    assert r["status"] == "SEM_EVIDÊNCIA"
    print("OK integrador_nao_promove")

def test_dataset_isolamento_bus():
    ciclo("mega_fire", [i % 37 for i in range(35)])
    msgs_mf = ler("mega_fire", limit=50)
    for m in msgs_mf:
        assert m["dataset_id"] == "mega_fire"
    print("OK bus_dataset", len(msgs_mf))

def test_cartoes_zero_a_sete():
    r = ciclo("mega_fire", [i % 37 for i in range(50)])
    n = r.get("n_cartoes", 0)
    assert 0 <= n <= 7
    assert len(r.get("candidatos") or []) <= 7
    print("OK cartoes", n, "cands", r.get("candidatos"))

def test_sombra_nao_zera():
    expr = {"op": "transition", "a": "3", "b": "5"}
    t = make_hipotese(expr, "A02", "mega_fire", "mega_fire", 20)
    t["estado"] = "em_teste"
    t["ativacao"] = "REATIVAÇÃO_EM_TESTE"
    t["prospectivo"] = {"n": 40, "hits": 9, "misses": 31, "taxa": 9/40, "hist": []}
    merge(t)
    t2 = get(t["id"])
    assert t2["prospectivo"]["n"] == 40
    # merge vazio não zera
    t3 = make_hipotese(expr, "A02", "mega_fire", "mega_fire", 20)
    t3["estado"] = "em_teste"
    t3["prospectivo"] = {"n": 0, "hits": 0, "misses": 0, "taxa": None, "hist": []}
    merged = merge(t3)
    assert merged["prospectivo"]["n"] == 40
    print("OK sombra_preservada")

if __name__ == "__main__":
    test_nao_completa_sete()
    test_lstm_nao_altera_teoria()
    test_integrador_nao_promove()
    test_sombra_nao_zera()
    test_dataset_isolamento_bus()
    test_cartoes_zero_a_sete()
    print("INTEGRACAO_OK")
