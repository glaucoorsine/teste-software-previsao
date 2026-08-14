# -*- coding: utf-8 -*-
from __future__ import annotations
import os, sys, json, threading, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
TEST_LOG = ROOT / "Logs" / "_test_isolado"
TEST_LOG.mkdir(parents=True, exist_ok=True)

from time_utils import canonical_ts, sort_key_ts
from fluxo_captura import parse_items_roulette, _purge_invalid, salvar_ciclo_ativo, carregar_ciclo_ativo, limpar_ciclo_ativo
import ia_modulos as im

def test_parser_legacy_and_lists():
    formats = [
        [{"data":{"settledAt":"2026-08-11T12:00:00.000Z","result":{"outcome":{"number":17},"luckyNumbersList":[{"number":17,"multiplier":50}]}}}],
        [{"data":{"settledAt":"2026-08-11T12:00:00+00:00","result":{"number":0}}}],
        [{"number":5,"settledAt":"2026-08-11T12:00:00Z"}],
        [{"data":{"settledAt":"2026-08-11T12:00:00Z","results":[{"number":8},{"number":9}]}}],
        [{"id":"e1","data":{"settledAt":"2026-08-11T12:00:00Z","result":{"outcome":{"number":26,"color":"black"}}}}],
    ]
    for i, items in enumerate(formats):
        rows = parse_items_roulette(items)
        assert len(rows) >= 1, f"format {i} empty: {items}"
    assert parse_items_roulette(formats[1])[0]["n"] == 0
    print("OK parser")

def test_zero_purge():
    dirty = [{"n":0,"valor":"0","settled":"2026-08-11T10:00:00+00:00","event_id":"mega_fire|0|2026-08-11T10:00:00+00:00"},
             {"n":99,"valor":"99","settled":"2026-08-11T10:00:00+00:00"}]
    c = _purge_invalid(dirty, "mega_fire")
    assert any(x["n"]==0 for x in c)
    print("OK zero")

def test_no_duplicate_pending():
    path = str(TEST_LOG / f"mem_dedupe_{uuid.uuid4().hex[:6]}.json")
    mem = im.Memoria.__new__(im.Memoria)
    mem.jogo = "test"
    mem.path = path
    mem.d = {"decisoes_pendentes":[],"avaliadas":[],"calib":[],"versoes":[],"modulos":[]}
    a = mem.registrar_decisao([1,2], "SOMBRA", {}, [], 0.5, {}, settled_ref="2026-08-11T10:00:00+00:00", janela=3)
    b = mem.registrar_decisao([1,2], "SOMBRA", {}, [], 0.5, {}, settled_ref="2026-08-11T10:00:00+00:00", janela=3)
    assert a and b and a["id"] == b["id"]
    assert len(mem.d["decisoes_pendentes"]) == 1
    print("OK dedupe pending")

def test_horizon():
    path = str(TEST_LOG / f"mem_h_{uuid.uuid4().hex[:6]}.json")
    mem = im.Memoria.__new__(im.Memoria)
    mem.path = path
    mem.jogo = "t"
    mem.d = {"decisoes_pendentes":[{"id":"t1","alvos":[1,2],"settled_ref":"2026-08-11T10:00:00+00:00","hits":0,"misses":0,"baseline_alvos":[],"spins":[],"resultado":None,"janela":3,"conf":0.2,"dist_sel":{}}],
             "avaliadas":[],"calib":[],"versoes":[],"modulos":[]}
    r = mem.registrar_spin(1, True, settled_result="2026-08-11T10:05:00+00:00", window_done=False)
    assert r.get("open") is True
    assert mem.d["decisoes_pendentes"][0].get("resultado") is None
    print("OK horizon")

def test_stream_tz_not_text():
    path = str(TEST_LOG / f"mem_s_{uuid.uuid4().hex[:6]}.json")
    mem = im.Memoria.__new__(im.Memoria)
    mem.path = path
    mem.jogo = "t"
    # sref as +00:00, event as Z later time
    mem.d = {"decisoes_pendentes":[{
        "id":"t2","alvos":["7"],"settled_ref":"2026-08-11T10:00:00+00:00",
        "hits":0,"misses":0,"baseline_alvos":[],"spins":[],"resultado":None,"janela":2,"conf":0.2,"dist_sel":{}
    }],"avaliadas":[],"calib":[],"versoes":[],"modulos":[]}
    # hist recent first: later event first
    fechadas = mem.avancar_pendentes_stream(
        [7, 3],
        ["2026-08-11T10:10:00Z", "2026-08-11T10:05:00Z"],
    )
    # deve processar eventos Z como posteriores ao ref +00:00
    pend_list = mem.d.get("decisoes_pendentes") or []
    aval = mem.d.get("avaliadas") or []
    alvo = pend_list[0] if pend_list else (aval[-1] if aval else None)
    assert alvo is not None, (fechadas, pend_list, aval)
    spins_n = len(alvo.get("spins") or [])
    hits = int(alvo.get("hits") or 0)
    misses = int(alvo.get("misses") or 0)
    assert spins_n >= 1 or hits + misses >= 1 or alvo.get("resultado"), alvo
    print("OK stream tz", hits, misses, spins_n, bool(alvo.get("resultado")))

def test_concurrent_merge_keeps_both():
    path = str(TEST_LOG / f"mem_c_{uuid.uuid4().hex[:6]}.json")
    Path(path).write_text(json.dumps({
        "decisoes_pendentes":[],"avaliadas":[],"calib":[],"versoes":[],"modulos":[]
    }), encoding="utf-8")
    barrier = threading.Barrier(2)
    def w(pid, alvos):
        barrier.wait()
        m = im.Memoria.__new__(im.Memoria)
        m.path = path
        m.jogo = "c"
        # load disk
        m.d = json.loads(Path(path).read_text(encoding="utf-8"))
        m.registrar_decisao(alvos, "SOMBRA", {}, [], 0.4, {}, settled_ref=f"ref-{pid}", janela=2)
    t1 = threading.Thread(target=w, args=(1, [1,2]))
    t2 = threading.Thread(target=w, args=(2, [3,4]))
    t1.start(); t2.start(); t1.join(); t2.join()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pend = data.get("decisoes_pendentes") or []
    refs = {p.get("settled_ref") for p in pend}
    assert "ref-1" in refs and "ref-2" in refs, refs
    print("OK concurrent both", refs)

def test_nova_janela_all_modules():
    for name in ["mega_fire_combo.py","lightning_combo.py","immersive_combo.py","crazy_time_combo.py"]:
        s = (ROOT/name).read_text()
        assert "salvar_ciclo_ativo(GAME, self.escolhas, self.restantes, False" in s, name
    print("OK nova janela 4/4")

def test_idle_returns_no_put():
    for name in ["mega_fire_combo.py","lightning_combo.py","immersive_combo.py","crazy_time_combo.py"]:
        s = (ROOT/name).read_text()
        assert "sem ciclo: só redesenha" in s or "NÃO consulta motor" in s
    print("OK idle")

def test_does_not_wipe_operational_cycle():
    # sentinel
    salvar_ciclo_ativo("mega_fire", [99], 9, False, 0, 0)
    # run only isolated cleanup
    limpar_ciclo_ativo("test_only")
    c = carregar_ciclo_ativo("mega_fire")
    assert c and c.get("escolhas") == [99], c
    limpar_ciclo_ativo("mega_fire")  # clean sentinel after assert
    print("OK no wipe operational")

if __name__ == "__main__":
    test_parser_legacy_and_lists()
    test_zero_purge()
    test_no_duplicate_pending()
    test_horizon()
    test_stream_tz_not_text()
    test_concurrent_merge_keeps_both()
    test_nova_janela_all_modules()
    test_idle_returns_no_put()
    test_does_not_wipe_operational_cycle()
    print("FLUXO_TESTES_OK")
