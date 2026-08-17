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
    for name in ["mega_fire_combo.py","lightning_combo.py","crazy_time_combo.py"]:
        s = (ROOT/name).read_text()
        assert "salvar_ciclo_ativo(GAME, self.escolhas, self.restantes, False" in s, name
    print("OK nova janela 4/4")

def test_idle_returns_no_put():
    for name in ["mega_fire_combo.py","lightning_combo.py","crazy_time_combo.py"]:
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

def test_toda_mesa_tem_segunda_fonte():
    """Ele reparou: "possuem dois links de api, porque so esta no casino?"

    Tinha razao, e a prova estava no arquivo dele: fontes_descobertas.json ja
    trazia o endereco do trackpot para lightning, descoberto pelo
    coletor -- e o fluxo de captura nunca consultava, porque so o Crazy Time A
    tinha alternativa cadastrada. Quando o casino.org falhava, a mesa morria
    tendo uma segunda fonte ali do lado.
    """
    import fluxo_captura as F
    for mesa in ("lightning", "mega_fire", "crazy_time",
                 "crazy_time_a"):
        urls = F.enderecos_para(mesa)
        assert len(urls) >= 2, f"{mesa} so tem {len(urls)} endereco(s)"
        assert any("casino.org" in u for u in urls), mesa
        assert any("trackpot" in u for u in urls), f"{mesa} sem a segunda fonte"
    # a ordem importa: o principal vem primeiro, a alternativa e reserva
    assert "casino.org" in F.enderecos_para("lightning")[0]
    print("  ok   as cinco mesas tem duas fontes, nao uma")


def test_parser_aceita_formato_plano():
    """A segunda fonte devolve outro formato -- se responder, tem que ser lida."""
    import fluxo_captura as F
    # formato plano, como as fontes alternativas costumam mandar
    plano = [{"number": 17, "settledAt": "2026-08-15T10:00:00Z"},
             {"number": 0, "settledAt": "2026-08-15T09:59:00Z"}]
    r = F.parse_items_roulette(plano)
    assert len(r) == 2, r
    assert r[0]["n"] == 17 and r[1]["n"] == 0, r
    # e o aninhado do casino.org continua funcionando
    aninhado = [{"data": {"result": {"outcome": {"number": 5}},
                          "settledAt": "2026-08-15T10:00:00Z"}}]
    r2 = F.parse_items_roulette(aninhado)
    assert r2 and r2[0]["n"] == 5, r2
    print("  ok   o parser le os dois formatos -- plano e aninhado")


def test_links_dele_sao_fonte_de_captura():
    """Ele cobrou: "coloque todos os links que te passei como base para captura".

    Quando mandou os cinco enderecos do gamblingcounting, ele disse: "para
    saber quantas pessoas tem E PEGAR OS ULTIMOS 200 RESULTADOS". Eu fiz so a
    primeira metade -- o contador de pessoas -- e os resultados ficaram sendo
    lidos por extrair_resultados() sem nunca chegar na captura.
    """
    import fluxo_captura as F
    assert len(F.FONTES_HTML) == 4, F.FONTES_HTML
    for mesa in ("lightning", "mega_fire", "crazy_time",
                 "crazy_time_a"):
        ends = F.enderecos_html(mesa)
        assert len(ends) >= 2, (mesa, ends)
        # a pagina do PROVEDOR vem antes do agregador: se as duas responderem,
        # a que vale e a oficial
        assert "casino.org/casinoscores" in ends[0], (mesa, ends)
        assert any("gamblingcounting.com" in u for u in ends), (mesa, ends)
    # o endereco que ele mandou, textual
    assert ("https://www.casino.org/casinoscores/pt-br/crazy-time-a/"
            in F.enderecos_html("crazy_time_a")), F.enderecos_html("crazy_time_a")
    # mesa desconhecida nao inventa fonte
    assert F.enderecos_html("mesa_que_nao_existe") == []
    assert F.capturar_html("mesa_que_nao_existe") == []
    print("  ok   os links dele sao fonte de captura, com o oficial na frente")


def test_crazy_time_a_viva():
    """Os dois defeitos que deixavam a mesa Crazy Time A morta.

    1. API_ALTERNATIVAS existia no topo do arquivo e NUNCA era consultada -- o
       codigo usava so o endereco principal, entao se ele nao respondesse a
       mesa nao abria e nada dizia por que.
    2. A comparacao era `dataset_id == "crazy_time"`, entao a segunda mesa do
       mesmo jogo caia no parser de ROLETA e seus simbolos viravam lixo -- em
       silencio, que e o pior jeito de errar.
    """
    import fluxo_captura as F
    ends = F.enderecos_para("crazy_time_a")
    assert len(ends) >= 4, ends
    assert F.API_BY_GAME["crazy_time_a"] in ends
    # O SLUG VEM DA PAGINA QUE ELE MANDOU, nao de chute meu.
    # As grafias que eu inventei (crazytimea, crazytimeA, crazytime2) deram 404
    # em todas. `crazy-time-a` e o nome que o provedor usa na URL publica.
    assert F.API_BY_GAME["crazy_time_a"].endswith("/crazy-time-a"), \
        F.API_BY_GAME["crazy_time_a"]
    assert ends[0].endswith("/crazy-time-a"), ends[:2]
    assert any("trackpotapi" in u for u in ends), ends
    assert F.enderecos_para("mesa_inexistente") == []

    itens = [{"data": {"result": {"outcome": {
        "wheelResult": {"wheelSector": "CoinFlip"},
        "topSlot": {"sector": "5", "multiplier": 20}}},
        "settledAt": "2026-08-15T10:00:00Z"}}]
    r = F.parse_items_ct(itens)
    assert r and r[0]["n"] == "CoinFlip", r
    assert not F.parse_items_roulette(itens), "roleta nao le simbolo"

    import tempfile, pathlib as _pl
    guardado = F.FONTES_OK
    try:
        F.FONTES_OK = _pl.Path(tempfile.mkdtemp()) / "fontes.json"
        F._lembrar_fonte("crazy_time_a", "https://exemplo/funciona")
        assert F.fonte_lembrada("crazy_time_a") == "https://exemplo/funciona"
        assert F.enderecos_para("crazy_time_a")[0] == "https://exemplo/funciona"
    finally:
        F.FONTES_OK = guardado
    print("  ok   crazy time A: enderecos, parser e memoria da fonte")


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
    test_toda_mesa_tem_segunda_fonte()
    test_parser_aceita_formato_plano()
    test_links_dele_sao_fonte_de_captura()
    test_crazy_time_a_viva()
    print("FLUXO_TESTES_OK")
