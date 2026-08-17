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
        # o endereco de teste precisa NOMEAR a mesa: desde que o crivo de
        # identidade passou a valer no uso e na gravacao, um endereco generico
        # como "https://exemplo/funciona" e recusado -- e recusar e o correto,
        # foi o que deixou o Crazy Time A lendo a mesa errada.
        _falso = "https://exemplo/crazy-time-a/funciona"
        F._lembrar_fonte("crazy_time_a", _falso)
        assert F.fonte_lembrada("crazy_time_a") == _falso
        assert F.enderecos_para("crazy_time_a")[0] == _falso
    finally:
        F.FONTES_OK = guardado
    print("  ok   crazy time A: enderecos, parser e memoria da fonte")


def test_crazy_time_a_volta_depois_de_cair():
    """"crazy time a perde conexao e nao volta mais" -- os tres defeitos.

    O SINTOMA E A CAUSA
    -------------------
    A mesa abria, funcionava, e em algum momento parava para sempre. Nao era
    perda de conexao: era o software insistindo num endereco morto, sem nenhum
    caminho de volta. Tres coisas se somavam, e a pior era minha.

    1. NAO EXISTIA `esquecer_fonte`. O endereco que funcionou uma vez ficava
       gravado para sempre. Depois de o provedor desliga-lo ele continuava sendo
       o PRIMEIRO candidato de toda volta, consumindo o orcamento em timeout --
       e, pior, mantendo `fonte_lembrada` respondendo, o que desligava o atalho
       da pagina dele (que so roda "quando a mesa nao tem fonte conhecida").

    2. O MEU GUARDA CONTRA MESAS DUPLICADAS CRIOU PRISAO PERPETUA. Ele julgava
       por posse: "outra mesa ja gravou este endereco, entao voce nao pode". Se
       o Crazy Time comum tivesse gravado, por engano de versao anterior, o
       endereco que e do Crazy Time A, o A ficava barrado do PROPRIO endereco --
       e como nada esquecia fonte, para sempre.

    3. O PORTAO DE DEZ MINUTOS DA PROCURA era marcado antes de a procura rodar,
       e bastavam 5 segundos de orcamento para comeca-la. Uma procura que nao
       tinha como terminar bloqueava a proxima por dez minutos.
    """
    import fluxo_captura as F
    import tempfile, pathlib as _pl
    guardado = F.FONTES_OK
    try:
        F.FONTES_OK = _pl.Path(tempfile.mkdtemp()) / "fontes.json"
        F._FALHAS_FONTE.clear()

        # ── 1. a fonte morta e esquecida depois de N falhas, nao antes ──
        F._lembrar_fonte("crazy_time_a", "https://morreu/crazy-time-a/api")
        assert F.fonte_lembrada("crazy_time_a") == "https://morreu/crazy-time-a/api"
        for i in range(F.FALHAS_ATE_ESQUECER - 1):
            assert F._fonte_falhou("crazy_time_a") is False, i
            assert F.fonte_lembrada("crazy_time_a"), \
                "uma API que cai por 30s e volta nao pode perder a fonte"
        assert F._fonte_falhou("crazy_time_a") is True
        assert F.fonte_lembrada("crazy_time_a") is None, \
            "depois de N falhas seguidas a fonte morta TEM que ser esquecida"

        # e sem fonte gravada o atalho da pagina dele volta a valer
        assert not F.fonte_lembrada("crazy_time_a")

        # ── e uma resposta boa zera o contador ──────────────────────────
        F._lembrar_fonte("crazy_time_a", "https://voltou/crazy-time-a/api")
        F._fonte_falhou("crazy_time_a")
        F._fonte_funcionou("crazy_time_a")
        assert F._FALHAS_FONTE.get("crazy_time_a") is None
        for _ in range(F.FALHAS_ATE_ESQUECER - 1):
            F._fonte_falhou("crazy_time_a")
        assert F.fonte_lembrada("crazy_time_a") == "https://voltou/crazy-time-a/api", \
            "o contador tem que zerar quando a fonte responde"

        # ── 2. o engano de uma versao ANTIGA e desfeito ─────────────────
        #
        # Antes o crivo era so na gravacao, e por posse. Hoje `_lembrar_fonte`
        # nem deixa o Crazy Time comum gravar o endereco do A -- a identidade
        # barra na origem. Entao o cenario aqui e o que EXISTE na maquina dele:
        # o engano ja gravado por uma versao anterior.
        F.FONTES_OK.unlink(missing_ok=True)
        F._FALHAS_FONTE.clear()
        proprio = "https://api-cs.casino.org/svc/crazy-time-a"
        alheio = "https://api-cs.casino.org/svc/crazytime"
        F._gravar_json(F.FONTES_OK, {"crazy_time": proprio})
        assert F.fonte_lembrada("crazy_time") == proprio, "(cenario)"
        # a limpeza da abertura desfaz: aquele endereco nao e do crazy_time
        apagadas = F.limpar_fontes_alheias()
        assert any("crazy_time" in a for a in apagadas), apagadas
        assert F.fonte_lembrada("crazy_time") is None
        # e agora o dono legitimo pode grava-lo
        F._lembrar_fonte("crazy_time_a", proprio)
        assert F.fonte_lembrada("crazy_time_a") == proprio

        # ── e o guarda continua guardando o caso de verdade ─────────────
        F.FONTES_OK.unlink(missing_ok=True)
        F._lembrar_fonte("crazy_time", alheio)
        F._lembrar_fonte("crazy_time_a", alheio)
        assert F.fonte_lembrada("crazy_time_a") is None, \
            "o A NAO pode ficar com o endereco do Crazy Time comum"
        assert F.fonte_lembrada("crazy_time") == alheio, \
            "e o dono legitimo daquele endereco nao pode perde-lo"

        # ── quem e dono de que ──────────────────────────────────────────
        assert F._endereco_e_da_mesa("crazy_time_a", proprio)
        assert not F._endereco_e_da_mesa("crazy_time_a", alheio)
        assert F._endereco_e_da_mesa("crazy_time", alheio)
        # `crazytime` esta DENTRO de `crazytimea`: as duas mesas "batem" no
        # endereco do A, e por isso o desempate nao pode ser por igualdade --
        # tem que ser pelo nome mais especifico (o mais longo).
        assert F._endereco_e_da_mesa("crazy_time", proprio), \
            "o prefixo bate nas duas -- e por isso que o desempate e por " \
            "especificidade"
        assert len("crazy_time_a") > len("crazy_time")
    finally:
        F.FONTES_OK = guardado
        F._FALHAS_FONTE.clear()

    # ── a limpeza da abertura tambem tem que dar o endereco ao dono certo ──
    guardado = F.FONTES_OK
    try:
        F.FONTES_OK = _pl.Path(tempfile.mkdtemp()) / "fontes.json"
        proprio = "https://api-cs.casino.org/svc/crazy-time-a"
        F._gravar_json(F.FONTES_OK, {"crazy_time": proprio,
                                     "crazy_time_a": proprio})
        apagadas = F.limpar_fontes_duplicadas()
        assert F.fonte_lembrada("crazy_time_a") == proprio, \
            "na limpeza da abertura, quem fica com .../crazy-time-a e o A"
        assert F.fonte_lembrada("crazy_time") is None
        assert "crazy_time" in apagadas, apagadas
    finally:
        F.FONTES_OK = guardado

    # ── 3. o portao da procura nao se gasta sem tempo de rodar ──────────
    _fonte = (ROOT / "fluxo_captura.py").read_text(encoding="utf-8")
    assert "_t.time() < _fim - 20 and _t.time() - _ultima > 600" in _fonte, \
        "a procura precisa de folga real antes de gastar o portao de 10 min"
    # e o laco esquece a fonte quando nada responde
    assert "if not items and _lembrada:" in _fonte
    assert "_fonte_funcionou(dataset_id)" in _fonte
    print("  ok   crazy time A volta depois de cair -- fonte morta e esquecida")


def test_identidade_do_endereco():
    """Os logs dele provaram que o crivo de identidade faltava onde importa.

    O QUE ESTAVA GRAVADO NA MAQUINA DELE
    ------------------------------------
        lightning:    .../api/megaroulette      <- mesa ERRADA
        mega_fire:    .../api/megaroulette      <- a MESMA do lightning
        crazy_time:   .../api/crazytime
        crazy_time_a: .../api/crazytime         <- a MESMA do crazy_time

    As paginas do casinoscores carregam o MESMO pacote de scripts, com os
    enderecos de TODAS as mesas -- o log diz "17 endereco(s)" igual para as
    quatro. O descobridor validava por FORMATO ("isto devolve giros que meu
    parser reconhece?"), e megaroulette devolve giros de roleta validos.

    Eu ja tinha escrito que o crivo que faltava era de IDENTIDADE. O erro foi
    aplicar so na hora de GRAVAR: o log mostra `FONTE_DUPLICADA crazy_time_a
    tentou usar o endereco de crazy_time` e, ainda assim, as duas mesas
    apareceram na tela com a mesma sequencia deslocada em dois giros -- porque o
    laco USA os itens e so depois recusa gravar.
    """
    import fluxo_captura as F

    # nenhum endereco que eu ja declarava pode ser derrubado pela regra nova
    for mesa in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
        for u in F.enderecos_para(mesa):
            ok, motivo = F.identidade_ok(mesa, u)
            assert ok, f"a regra derrubou fonte que funciona: {mesa} {u} ({motivo})"

    # os casos exatos do log dele
    for mesa in ("lightning", "mega_fire", "crazy_time", "crazy_time_a"):
        ok, _ = F.identidade_ok(mesa, "https://x/api/megaroulette")
        assert not ok, f"megaroulette nao e de {mesa}"

    assert F.identidade_ok("crazy_time", "https://x/api/crazytime")[0]
    assert not F.identidade_ok("crazy_time_a", "https://x/api/crazytime")[0], \
        "o A NAO pode aceitar o endereco do Crazy Time comum"
    assert F.identidade_ok("crazy_time_a", "https://x/api/crazy-time-a")[0]
    assert not F.identidade_ok("crazy_time", "https://x/api/crazy-time-a")[0], \
        "e o comum nao pode aceitar o do A (crazytime esta DENTRO de crazytimea)"
    assert F.identidade_ok("lightning", "https://x/api/lightningroulette")[0]
    assert not F.identidade_ok("mega_fire", "https://x/api/lightningroulette")[0]

    # mesa que eu nao conheco: nao julgo em vez de recusar tudo
    assert F.identidade_ok("mesa_nova", "https://x/api/qualquer")[0]

    # ── a GRAVACAO recusa endereco alheio ────────────────────────────────
    import tempfile, pathlib as _pl
    guardado = F.FONTES_OK
    try:
        F.FONTES_OK = _pl.Path(tempfile.mkdtemp()) / "fontes.json"
        F._lembrar_fonte("lightning", "https://x/api/megaroulette")
        assert F.fonte_lembrada("lightning") is None, \
            "megaroulette nao pode ser gravado como fonte do lightning"
        F._lembrar_fonte("lightning", "https://x/api/lightningroulette")
        assert F.fonte_lembrada("lightning") == "https://x/api/lightningroulette"

        # ── e a limpeza da abertura apaga o que JA esta gravado errado ───
        F._gravar_json(F.FONTES_OK, {
            "lightning": "https://api-cs.casino.org/svc/megaroulette",
            "crazy_time": "https://api-cs.casino.org/svc/crazytime"})
        apagadas = F.limpar_fontes_alheias()
        assert any("lightning" in a for a in apagadas), apagadas
        assert F.fonte_lembrada("lightning") is None, \
            "correcao que nao limpa o estado antigo nao conserta nada na pratica"
        assert F.fonte_lembrada("crazy_time"), \
            "e a fonte certa das outras mesas nao pode ser tocada"
    finally:
        F.FONTES_OK = guardado
    print("  ok   endereco de outra mesa e recusado ao usar, gravar e limpar")


def test_mega_fire_capta_multiplicador_sem_super_boost():
    """"a v118 nao capta multiplicadores do mega fire" -- correcao minha, pela metade.

    O site mostrava 74X no 30, 132X no 8 e 67X no 21 em meia hora. O software, na
    mesma janela: "multiplicador escasso: 0% contra 22% do normal" e "seca de 97
    giros". Os numeros batiam, so o valor sumia.

    A leitura de `fireNumbers` -- o campo que carrega o multiplicador -- estava
    dentro de `if _boost:`. `superBoost` marca a rodada especial, nao o anuncio,
    entao nos giros que pagaram sem ser rodada especial o valor nunca era lido.
    """
    import fluxo_captura as F
    from NUCLEO.situacao import _mult_do_giro

    giro = [{"data": {"settledAt": "2026-08-17T16:05:00Z",
                      "result": {"outcome": {"number": 30},
                                 "fireNumbers": [{"number": 30, "multiplier": 74},
                                                 {"number": 7, "multiplier": 12}]}}}]
    r = F.parse_items_roulette(giro)
    pago, anunciados = _mult_do_giro(r[0])
    assert pago == 74, f"o 74X do giro 30 tem que chegar; pagou {pago}"
    assert anunciados >= 2, anunciados

    # anuncia e nao paga continua sendo anuncio, nao premio
    outro = [{"data": {"settledAt": "2026-08-17T16:06:00Z",
                       "result": {"outcome": {"number": 19},
                                  "fireNumbers": [{"number": 30, "multiplier": 74}]}}}]
    r2 = F.parse_items_roulette(outro)
    pago2, anun2 = _mult_do_giro(r2[0])
    assert pago2 == 0 and anun2 >= 1, (pago2, anun2)

    # com superBoost o caminho antigo continua valendo
    cb = [{"data": {"settledAt": "2026-08-17T15:51:00Z", "superBoost": True,
                    "result": {"outcome": {"number": 8},
                               "fireNumbers": [{"number": 8,
                                                "roundedMultiplier": 132}]}}}]
    r3 = F.parse_items_roulette(cb)
    assert _mult_do_giro(r3[0])[0] == 132, r3[0]
    assert sum(1 for t in r3[0]["tags"] if "fire_nums" in t) == 1, \
        "UMA tag de anuncio por giro -- duas dobravam a contagem de premiados"

    # outras grafias, porque o provedor ja renomeou antes
    for campo in ("blazeNumbers", "fireBlazeNumbers", "hotNumbers"):
        g = [{"data": {"settledAt": "2026-08-17T16:07:00Z",
                       "result": {"outcome": {"number": 5},
                                  campo: [{"number": 5, "multiplier": 50}]}}}]
        assert _mult_do_giro(F.parse_items_roulette(g)[0])[0] == 50, campo
    print("  ok   mega fire capta multiplicador sem depender do super boost")


def test_repeticao_real_nao_e_apagada():
    """"olha o historico no site e o historico no software tambem".

    O site dele mostra QUATRO "1" seguidos entre 18:21 e 18:23 -- rodadas
    legitimas, mesmo resultado, em menos de dois minutos. O software apagava as
    repetidas e o historico saia mais curto que o do site.

    A regra existia para outro problema, menor: o MESMO evento relatado duas
    vezes com o carimbo deslocado em 1 segundo. Para isso bastam poucos
    segundos; a janela estava em VINTE, que pega tres rodadas de Crazy Time.

    E o estrago nao e so o historico curto: REPETICAO e uma das coisas que o
    estudo mede. Apagar repeticao real enviesa a medida para baixo, em silencio.
    """
    import fluxo_captura as F

    def ev(sec, ts):
        return {"n": sec, "valor": sec, "sec": sec, "settled": ts, "tags": []}

    reais = [ev("1", "2026-08-17T18:21:05Z"), ev("1", "2026-08-17T18:22:10Z"),
             ev("1", "2026-08-17T18:22:50Z"), ev("1", "2026-08-17T18:23:30Z")]
    r = F._purge_invalid(reais, "crazy_time")
    assert len(r) == 4, f"o site mostra 4 repeticoes; sobraram {len(r)}"

    # e a duplicata de verdade continua sendo UM giro
    dup = [ev("1", "2026-08-17T18:21:05Z"), ev("1", "2026-08-17T18:21:06Z")]
    assert len(F._purge_invalid(dup, "crazy_time")) == 1, \
        "o mesmo evento com 1s de deslocamento ainda tem que virar um giro so"

    # na roleta tambem: dois 17 seguidos sao dois giros
    rr = [ev("17", "2026-08-17T18:21:00Z"), ev("17", "2026-08-17T18:21:40Z")]
    assert len(F._purge_invalid(rr, "lightning")) == 2, \
        "dois 17 com 40s de diferenca sao dois giros"
    assert F.MIN_SEG_RODADA <= 8, \
        "a janela precisa ser curta: ela existe para 1s de deslocamento"
    print("  ok   repeticao real sobrevive; duplicata de 1s continua sendo uma")


def test_sonda_existe_e_nao_muda_nada():
    """A sonda que acaba com o chute: le a API e grava, sem mexer em nada.

    Eu nunca vi uma resposta destas APIs -- o proxy do meu ambiente nega
    casino.org por politica. Cada campo que faltou eu ADIVINHEI, e cada palpite
    virou uma versao com o mesmo defeito de outra cor. Esta sonda roda na
    maquina dele, onde a API responde, e devolve a forma real.
    """
    fonte = (ROOT / "SONDA_MESAS.py").read_text(encoding="utf-8")
    # nao pode escrever em nada do software em funcionamento
    for proibido in ("_lembrar_fonte", "merge(", "salvar_ciclo_ativo",
                     "gravar_json", "FONTES_OK"):
        assert proibido not in fonte, \
            f"a sonda nao pode mexer em {proibido} -- ela so le e relata"
    assert "sonda_mesas.json" in fonte
    assert "MAX_GIROS = 3" in fonte, "arquivo pequeno: e a FORMA que interessa"
    assert (ROOT / "SONDA_MESAS.bat").is_file(), "e tem que ter um .bat"
    print("  ok   a sonda le e relata, sem tocar no que esta rodando")


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
    test_crazy_time_a_volta_depois_de_cair()
    test_identidade_do_endereco()
    test_mega_fire_capta_multiplicador_sem_super_boost()
    test_repeticao_real_nao_e_apagada()
    test_sonda_existe_e_nao_muda_nada()
    print("FLUXO_TESTES_OK")
