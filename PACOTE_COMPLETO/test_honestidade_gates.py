
# -*- coding: utf-8 -*-
from metricas_honestas import p_hit_janela, p_alvos_ct, ganho_significativo, texto_placar_acumulado
import ia_modulos as im
from pathlib import Path
import json, uuid, threading

def test_p_acaso_janela_not_spin():
    pe = p_hit_janela(p_alvos_ct(["1","2","5"]), 3)
    assert pe > 0.9, pe
    p_spin = 3/8
    assert pe != p_spin
    print("OK p janela", round(pe,4), "vs spin", p_spin)

def test_ganho_ruido_nao_passa():
    # 20/20 com p_exp=0.99 não é significativo pelo IC
    r = ganho_significativo(20, 20, 0.99)
    assert r["ok"] is False
    print("OK ganho ruido bloqueado")

def test_placar_usa_acumulado():
    # 29 acertos com soma_p alta (1,2,5) vs soma_p baixa
    t1 = texto_placar_acumulado(29, 1, 29*0.99, alvos_ultima=["1","2","5"], janela_ultima=4, is_ct=True)
    t2 = texto_placar_acumulado(29, 1, 29*0.25, alvos_ultima=["CrazyBonus"], janela_ultima=4, is_ct=True)
    assert "acaso≈" in t1 and "Δ=" in t1
    assert "Δ=" in t1 and "Δ=" in t2
    # Δ deve ser bem diferente
    assert t1 != t2
    print("OK placar", t1, "|", t2)

def test_dedupe_order():
    path = f"Logs/_test_isolado/dedupe_{uuid.uuid4().hex[:6]}.json"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mem = im.Memoria.__new__(im.Memoria)
    mem.path = path
    mem.jogo = "t"
    mem.d = {"decisoes_pendentes":[],"avaliadas":[],"calib":[],"versoes":[],"modulos":[]}
    a = mem.registrar_decisao([2,1], "SOMBRA", {}, [], 0.5, {}, settled_ref="2026-08-11T10:00:00Z", janela=3)
    b = mem.registrar_decisao([1,2], "SOMBRA", {}, [], 0.5, {}, settled_ref="2026-08-11T10:00:00+00:00", janela=3)
    assert a["id"] == b["id"]
    assert len(mem.d["decisoes_pendentes"]) == 1
    print("OK dedupe order+tz")

def test_merge_no_resurrect():
    path = f"Logs/_test_isolado/merge_{uuid.uuid4().hex[:6]}.json"
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    disk = {
        "decisoes_pendentes": [{"id":"a1","alvos":[1],"settled_ref":"r1","resultado":{"acertou":True},"spins":[{"x":1}]}],
        "avaliadas": [], "calib": [], "versoes": [], "modulos": [],
        "n_aguardando_total": 1,
        "cobertura_acc": {"soma_y":1,"soma_p":0.5,"n":1},
    }
    local = {
        "decisoes_pendentes": [{"id":"a1","alvos":[1],"settled_ref":"r1","resultado":None,"spins":[]}],
        "avaliadas": [], "calib": [], "versoes": [], "modulos": [],
        "n_aguardando_total": 2,
        "cobertura_acc": {"soma_y":1,"soma_p":0.5,"n":1},
    }
    mem = im.Memoria.__new__(im.Memoria)
    mem.path = path
    m = mem._merge_mem_state(disk, local)
    # a1 fechado não deve voltar a pendentes
    assert all(x.get("id") != "a1" or x.get("resultado") for x in m["decisoes_pendentes"]) or not any(x.get("id")=="a1" for x in m["decisoes_pendentes"])
    assert m["n_aguardando_total"] == 2
    print("OK merge no resurrect", m["decisoes_pendentes"], m["n_aguardando_total"])

def test_concurrent_both_survive():
    path = f"Logs/_test_isolado/conc2_{uuid.uuid4().hex[:6]}.json"
    Path(path).write_text(json.dumps({"decisoes_pendentes":[],"avaliadas":[],"calib":[],"versoes":[],"modulos":[],"n_aguardando_total":0}), encoding="utf-8")
    bar = threading.Barrier(2)
    def w(pid, alvos):
        bar.wait()
        m = im.Memoria.__new__(im.Memoria)
        m.path = path
        m.jogo = "c"
        m.d = json.loads(Path(path).read_text(encoding="utf-8"))
        m.registrar_decisao(alvos, "SOMBRA", {}, [], 0.4, {}, settled_ref=f"ref-{pid}", janela=2)
    t1=threading.Thread(target=w,args=(1,[1,2])); t2=threading.Thread(target=w,args=(2,[3,4]))
    t1.start(); t2.start(); t1.join(); t2.join()
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    refs={p.get("settled_ref") for p in data.get("decisoes_pendentes") or []}
    assert "ref-1" in refs and "ref-2" in refs, refs
    print("OK concurrent", refs)

if __name__ == "__main__":
    test_p_acaso_janela_not_spin()
    test_ganho_ruido_nao_passa()
    test_placar_usa_acumulado()
    test_dedupe_order()
    test_merge_no_resurrect()
    test_concurrent_both_survive()
    print("HONEST_TESTS_OK")
