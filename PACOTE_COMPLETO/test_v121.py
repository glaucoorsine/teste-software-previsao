# -*- coding: utf-8 -*-
"""As falhas que ele auditou na v119 — uma checagem por defeito.

Ele não reclamou: auditou, numerou e apontou arquivo e linha. A maioria dos
defeitos era invisível — o dado morria, a resposta chegava do giro errado, o
processo caía e ninguém perguntava. Nenhum deles aparecia como erro na tela.

Este arquivo existe para que nenhum volte sem ser notado.

  1. RESULTADO: crazy_time_a em JOGOS e fora de N_CLASSES  → KeyError
  2. captura: setores da Crazy Time A voltando a virar inteiro
  3. buffer: releitura pobre apagando o anúncio já capturado
  4. filas: resposta atrasada aplicada ao giro seguinte
  5. página HTML: assinatura curta e giro sem identidade
  6. fonte HTML: `"data"` aceitando qualquer array da página
  7. consenso: o primeiro colocado servindo de fiador para a lista inteira
  8. IA12: a agregação dele existia e nunca era chamada
  9. tela: `depois()` tocando no Tk de uma thread de fundo
 10. MESMA_APOSTA: a lista comparada consigo mesma
 11. o Caçador decidindo também nas janelas avulsas e no PREVER

    python test_v121.py
"""
from __future__ import annotations

# Os testes constroem o pipeline direto, com historico sintetico. Sem isto
# eles gravam decisoes, acertos e calibragem nos MESMOS arquivos que o
# software usa ao vivo -- e essas decisoes falsas entram no placar real.
import os, tempfile
os.environ.setdefault("LAB_MEMORIA_DIR",
                      tempfile.mkdtemp(prefix="lab_memoria_teste_"))


import random
import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


# ─────────────────────────────────────────────────────────────────────────────
print("\n[1] RESULTADO conhece todas as mesas que ele lista")

import RESULTADO as R  # noqa: E402

for jogo in R.JOGOS:
    checa(jogo in R.N_CLASSES, f"{jogo} tem tamanho de mesa declarado",
          sorted(R.N_CLASSES))
checa("immersive" not in R.JOGOS, "e a Immersive saiu daqui também", R.JOGOS)
# o caso exato: a primeira janela fechada da Crazy Time A derrubava tudo
checa(abs(R.chance_por_giro("crazy_time_a", ["1"], 1) - 21 / 54) < 1e-9,
      "Crazy Time A usa as casas desiguais, como a Crazy Time",
      R.chance_por_giro("crazy_time_a", ["1"], 1))
checa(R.chance_por_giro("mesa_que_nao_existe", ["1"], 1) == 0.0,
      "e mesa desconhecida devolve 0 em vez de derrubar o relatório")

# aposta repetida é espera, não janela nova
import tempfile  # noqa: E402

_p = Path(tempfile.mkdtemp()) / "central_log.txt"
_p.write_text("\n".join(f"14/08 20:0{i} | {t}" for i, t in enumerate([
    "lightning NOVA_JANELA ['5', '9'] OPERAR",
    "lightning MISS 30 restam=1",
    "lightning MISS 31 restam=0",
    "lightning JANELA ERRO ok=0 err=1",
    "lightning NOVA_JANELA ['5', '9'] OPERAR REPETICAO",
    "lightning HIT 5 restam=0",
    "lightning JANELA OK ok=1 err=1",
])), encoding="utf-8")
_d = R.ler(_p)["lightning"]["janelas"]
checa(len(_d) == 1, "a reabertura da MESMA aposta vira uma janela só", len(_d))
checa(_d[0]["giros"] == 3, "com os giros das duas somados", _d and _d[0])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[2] a Crazy Time A entrega símbolo, não inteiro")

import fluxo_captura as F  # noqa: E402

_ev = [{"n": "5", "valor": "5", "settled": "2026-08-17T10:00:00Z"},
       {"n": "CoinFlip", "valor": "CoinFlip", "settled": "2026-08-17T10:01:00Z"},
       {"n": "10", "valor": "10", "settled": "2026-08-17T10:02:00Z"}]
for mesa in ("crazy_time", "crazy_time_a"):
    _r = F._purge_invalid([dict(e) for e in _ev], mesa)
    checa(len(_r) == 3, f"{mesa}: os três giros passam", len(_r))
    checa(all(isinstance(x["n"], str) for x in _r),
          f"{mesa}: e todos saem como texto, como as inteligências esperam",
          [type(x["n"]).__name__ for x in _r])
_rol = F._purge_invalid([{"n": "17", "valor": "17",
                          "settled": "2026-08-17T10:00:00Z"}], "lightning")
checa(_rol and isinstance(_rol[0]["n"], int),
      "na roleta continua sendo inteiro", _rol)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[3] releitura pobre não apaga o anúncio já capturado")

import hist_buffer as H  # noqa: E402

_dir = Path(tempfile.mkdtemp()) / "buf.json"
_rico = [{"n": "7", "settled": "2026-08-17T10:00:00Z",
          "tags": [{"fire_nums": [{"n": 7, "x": 100}, {"n": 12, "x": 50}]}]}]
H.merge(_dir, "mega_fire", _rico)
# o MESMO giro, relido de uma fonte que não traz o anúncio
_pobre = [{"n": "7", "settled": "2026-08-17T10:00:00Z", "tags": []}]
_r = H.merge(_dir, "mega_fire", _pobre)
_tags = (_r["events"][0].get("tags") or [])
checa(bool(_tags), "o anúncio sobrevive à releitura sem tags", _tags)
checa(any("fire_nums" in t for t in _tags if isinstance(t, dict)),
      "e é o fire_nums mesmo, não outra coisa", _tags)
# e marca nova soma em vez de substituir
H.merge(_dir, "mega_fire", [{"n": "7", "settled": "2026-08-17T10:00:00Z",
                             "tags": [{"x": 100}]}])
_tags2 = (H.load(_dir)["events"][0].get("tags") or [])
checa(len(_tags2) == 2, "marca nova entra sem derrubar a antiga", _tags2)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[4] resposta atrasada não é aplicada ao giro seguinte")

import queue as _q  # noqa: E402

from fila_cerebro import novo_pedido, resposta_de  # noqa: E402


class Dono:
    pass


_dono = Dono()
_fila = _q.Queue()
_p1 = novo_pedido(_dono, "lightning")
_p2 = novo_pedido(_dono, "lightning")
checa(_p1 != _p2, "cada volta tem o seu número de pedido", (_p1, _p2))
# o cérebro respondeu ao pedido 1 tarde demais, e agora estamos no 2
_fila.put({"pad5": ["velho"], "req_id": _p1})
_fila.put({"pad5": ["novo"], "req_id": _p2})
_r = resposta_de(_dono, _fila, 2)
checa(_r and _r["pad5"] == ["novo"],
      "a resposta atrasada é descartada e a certa é usada", _r)
# sem nada que sirva, devolve None em vez de aceitar qualquer coisa
_fila2 = _q.Queue()
_fila2.put({"pad5": ["velho"], "req_id": _p1})
checa(resposta_de(_dono, _fila2, 0.5) is None,
      "e só a atrasada não vira resposta", "aceitou a velha")

from worker_process import _carimbo  # noqa: E402

checa(_carimbo({"head_id": "h1", "req_id": "r1"}) == {"head_id": "h1",
                                                     "req_id": "r1"},
      "o worker devolve o carimbo do pedido")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[5] a página HTML tem digital inteira e giro com identidade")

F._ids_html.clear()
F._seq_html.clear()
_pag = [{"n": "1"}, {"n": "1"}, {"n": "1"}, {"n": "2"}, {"n": "1"},
        {"n": "1"}, {"n": "5"}, {"n": "1"}, {"n": "1"}, {"n": "2"},
        {"n": "1"}, {"n": "1"}, {"n": "CoinFlip"}]
_h1, _i1 = F._identidade_html("crazy_time_a", _pag)
# a mesma página com mudança DEPOIS da décima segunda posição: com a
# assinatura curta as duas eram idênticas e o giro sumia
_pag_b = [dict(x) for x in _pag[:12]] + [{"n": "Pachinko"}]
_h2, _ = F._identidade_html("crazy_time_a", _pag_b)
checa(_h1 != _h2, "mudança além da 12ª posição muda a digital", (_h1, _h2))

F._ids_html.clear()
F._seq_html.clear()
_a = [{"n": "5"}, {"n": "1"}, {"n": "2"}]
_h, _ida = F._identidade_html("crazy_time", _a)
_b = [{"n": "CoinFlip"}] + [dict(x) for x in _a]
_h_b, _idb = F._identidade_html("crazy_time", _b)
checa(_idb[1:] == _ida, "giro antigo mantém o identificador dele", (_ida, _idb))
checa(_idb[0] not in _ida, "e o que entrou ganha um novo", _idb[0])
_h_c, _idc = F._identidade_html("crazy_time", [dict(x) for x in _b])
checa(_idc == _idb and _h_c == _h_b,
      "reler a mesma página não inventa giro", (_idb, _idc))
checa(len(set(_idb)) == len(_idb), "sem identificador repetido", _idb)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[6] a fonte HTML confere se o array é histórico desta mesa")

from fonte_gamblingcounting import extrair_resultados  # noqa: E402

_lixo = '{"data": [10231, 88123, 40021, 99110, 70233, 11002, 55001]}'
checa(extrair_resultados(_lixo, "lightning") == [],
      "array de ids não vira histórico de roleta",
      extrair_resultados(_lixo, "lightning"))
_bom = '{"results": [{"result": 17}, {"result": 0}, {"result": 36}, ' \
       '{"result": 5}, {"result": 22}, {"result": 9}]}'
checa(extrair_resultados(_bom, "lightning") == ["17", "0", "36", "5", "22", "9"],
      "e o histórico de verdade passa inteiro",
      extrair_resultados(_bom, "lightning"))
# a página traz os dois: o de verdade tem de ganhar
_dois = '{"data": [10231, 88123, 40021, 99110, 70233, 11002, 55001], ' \
        '"results": [{"result": 17}, {"result": 0}, {"result": 36}, ' \
        '{"result": 5}, {"result": 22}, {"result": 9}]}'
checa(extrair_resultados(_dois, "lightning") == ["17", "0", "36", "5", "22", "9"],
      "com os dois na página, o histórico ganha do lixo",
      extrair_resultados(_dois, "lightning"))
_ct = '{"history": ["1", "CoinFlip", "5", "Pachinko", "2", "1"]}'
checa(extrair_resultados(_ct, "crazy_time_a") ==
      ["1", "CoinFlip", "5", "Pachinko", "2", "1"],
      "e o Crazy Time A aceita os símbolos dele",
      extrair_resultados(_ct, "crazy_time_a"))
checa(extrair_resultados(_ct, "lightning") == [],
      "símbolo de Crazy Time não entra em roleta")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[7] no consenso, cada número responde por si")

from ia_modulos import (MIN_VOZES_INDEPENDENTES, MIN_VOZES_POR_NUMERO,  # noqa: E402
                        Critico)

_c = Critico()
# as três apontam o 7 e no resto não se repetem: é cruzamento de verdade, e o
# `n_efetivo` só passa de 2,0 quando as fontes de fato não são a mesma coisa
_ap, _, _, _sc, _, _ = _c.consenso(
    [{"nome": "TEORIA_A", "nums": ["7", "1", "2"], "peso": 2.0},
     {"nome": "TEORIA_B", "nums": ["7", "19", "28"], "peso": 2.0},
     {"nome": "TEORIA_C", "nums": ["7", "31", "4"], "peso": 2.0},
     {"nome": "SOZINHA", "nums": ["33"], "peso": 3.0}],
    n_classes=37, k_alvos=10)
checa("7" in _ap, "número com várias vozes entra", _ap)
checa("33" not in _ap,
      "e o de fonte única não entra de carona no aprovado do topo", _ap)
checa(MIN_VOZES_POR_NUMERO < MIN_VOZES_INDEPENDENTES,
      "abrir a mesa e entrar na lista são perguntas com limiares próprios",
      (MIN_VOZES_POR_NUMERO, MIN_VOZES_INDEPENDENTES))
# e a pergunta do topo continua fechando a mesa quando não há cruzamento
_ap2, _, _, _, _, _ = _c.consenso(
    [{"nome": "UNICA", "nums": ["9", "4"], "peso": 3.0}],
    n_classes=37, k_alvos=10)
checa(_ap2 == [], "uma fonte sozinha não abre aposta nenhuma", _ap2)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] a IA12 dele é chamada de verdade")

import ia_modulos as M  # noqa: E402

rnd = random.Random(11)
SETOR = [5, 24, 16, 33, 1, 20, 14]
_linhas = []
for i in range(240):
    v = rnd.choice(SETOR) if rnd.random() < 0.3 else rnd.randrange(37)
    _linhas.append({"n": v, "settled": f"2026-08-17T{i//60:02d}:{i%60:02d}:00Z",
                    "tags": [{"lucky": [{"n": rnd.randrange(37), "x": 50}]}]})
_pipe = M.PipelinePerceptivo("lightning")
_out = _pipe.processar([x["n"] for x in _linhas], 0, 0,
                       settled=[x["settled"] for x in _linhas],
                       linhas=_linhas) or {}
_msgs = _out.get("msgs") or []
checa(any("IA12 agrega" in m for m in _msgs),
      "a agregação aparece no log da volta",
      [m for m in _msgs if "Tratado" in m][:1])
_hips = [m for m in _msgs if m.startswith("[Hipóteses]")]
checa(_hips and "IA12_AGREGACAO" in _hips[0],
      "e ela vota com o nome dela", _hips[:1])

# a perda só é cobrada de quem opinou, e move o peso
_pipe._palpites_tratado = {"IA01_TEMPO": ["7"], "IA02_RECENCIA": ["19"]}
_pipe._perda_do_tratado("7")
_perdas = getattr(_pipe, "_perdas_tratado", {})
checa(set(_perdas) == {"IA01_TEMPO", "IA02_RECENCIA"},
      "as duas que opinaram pagam", _perdas)
checa(_perdas["IA01_TEMPO"] < _perdas["IA02_RECENCIA"],
      "quem acertou paga menos que quem errou", _perdas)
_pipe._palpites_tratado = {"IA01_TEMPO": ["7"]}
_antes = dict(_perdas)
_pipe._perda_do_tratado("7")
checa(getattr(_pipe, "_perdas_tratado")["IA02_RECENCIA"]
      == _antes["IA02_RECENCIA"],
      "quem calou não paga nada (F46: vigília)",
      getattr(_pipe, "_perdas_tratado"))

# ─────────────────────────────────────────────────────────────────────────────
print("\n[9] thread de fundo não toca no Tk")

import tela_segura as T  # noqa: E402


class Janela:
    def __init__(self):
        self.thread_do_after = None

    def winfo_exists(self):
        return 1

    def after(self, ms, fn):
        self.thread_do_after = threading.get_ident()
        fn()
        return "after#1"


T.registrar_thread_da_tela()
_j = Janela()
_feito = []
_t = threading.Thread(target=lambda: T.depois(_j, 0, lambda: _feito.append("x")))
_t.start()
_t.join()
checa(_j.thread_do_after is None,
      "a thread de fundo NÃO chamou o after", _j.thread_do_after)
checa(_feito == [], "e o trabalho ficou pendente em vez de rodar lá", _feito)
while not T._pendentes.empty():
    _w, _fn = T._pendentes.get_nowait()
    T._executar(_w, _fn)
checa(_feito == ["x"], "a interface é quem executa", _feito)
T.depois(_j, 0, lambda: _feito.append("y"))
checa(_j.thread_do_after == threading.get_ident() and _feito == ["x", "y"],
      "da própria thread da interface continua direto", _feito)
# e todas as janelas precisam LIGAR a bomba, senão a fila enche e nada roda
for _arq in ("CENTRAL.py", "central_ias.py", "mega_fire_combo.py",
             "lightning_combo.py", "crazy_time_combo.py"):
    _t4 = (RAIZ / _arq).read_text(encoding="utf-8")
    checa("bombear(self)" in _t4, f"{_arq}: liga a bomba da interface")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[10] o Caçador decide também fora da CENTRAL")

_fonte = (RAIZ / "mega_fire_combo.py").read_text(encoding="utf-8")
for arq in ("mega_fire_combo.py", "lightning_combo.py", "crazy_time_combo.py"):
    _t2 = (RAIZ / arq).read_text(encoding="utf-8")
    checa('"linhas": rows[:200]' in _t2,
          f"{arq}: manda as linhas cruas (sem elas o Caçador fica mudo)")
    checa("_novo_pedido(self, GAME)" in _t2,
          f"{arq}: carimba o pedido")
    checa("_resposta_de(" in _t2 and "out_q.get(timeout=45)" not in _t2,
          f"{arq}: confere o carimbo da resposta")
    checa("maxsize=" in _t2, f"{arq}: fila com teto")
    checa("_garantir_cerebro(" in _t2, f"{arq}: supervisiona o cérebro")
    checa('open("crash_log.txt"' not in _t2,
          f"{arq}: não escreve mais num crash_log compartilhado")

import PREVER as P  # noqa: E402

_pv = P.prever(_linhas, "lightning", 5)
checa(bool(_pv.get("cacador")), "PREVER diz de onde veio o número",
      _pv.get("cacador"))
checa(len(_pv.get("numeros_pdfs") or []) == 5,
      "e os PDFs seguem calculando a lista deles", _pv.get("numeros_pdfs"))
_sem = P.prever([{"n": i % 37, "event_id": f"z{i}"} for i in range(200)],
                "lightning", 5)
checa(_sem["numeros"] == [],
      "sem rodada de multiplicador não sai número — nem lista de reserva",
      _sem["numeros"])

# ─────────────────────────────────────────────────────────────────────────────
print("\n[11] o multiplicador da Mega Fire aparece na tela")

sys.modules.setdefault("customtkinter", None)
import importlib.util as _il  # noqa: E402

_spec = _il.spec_from_file_location("_c_ml", RAIZ / "CENTRAL.py")
# CENTRAL importa Tk; a função é lida do arquivo, como nos outros testes
_src = (RAIZ / "CENTRAL.py").read_text(encoding="utf-8")
_i = _src.index("def texto_multiplicador")
_j2 = _src.index("\ndef cor_do_numero")
_ns: dict = {}
exec(_src[_i:_j2], _ns)
_txt = _ns["texto_multiplicador"]
checa(_txt({"n": 7, "tags": [{"fire_nums": [{"n": 7, "x": 100}]}]}) == "×100",
      "fire_nums que pagou aparece",
      _txt({"n": 7, "tags": [{"fire_nums": [{"n": 7, "x": 100}]}]}))
checa(_txt({"n": "7", "tags": [{"fire_nums": [{"n": 7, "x": 100}]}]}) == "×100",
      "e a comparação é por texto (7 == '7' era falso)")
checa(_txt({"n": 7, "tags": [{"fire_nums": [{"n": 12, "x": 500}]}]}) == "",
      "anúncio que não bateu não vira multiplicador pago")
checa(_txt({"n": 20, "tags": [{"lucky": [{"n": 20, "x": 500}]}]}) == "×500",
      "e o lucky continua funcionando")

# ─────────────────────────────────────────────────────────────────────────────
print("\n[12] o multiplicador chega no formato que cada consumidor espera")

# a IA de intensidade do tratado faz zip(giros, mults) e float(m): ela quer um
# valor POR GIRO. A captura monta a lista de ANÚNCIOS, {"n":.., "x":..}. Passar
# um pelo outro deixava a metade da magnitude do modelo hurdle sempre vazia.
_lin = [{"n": 7, "tags": [{"fire_nums": [{"n": 7, "x": 100},
                                         {"n": 12, "x": 50}]}]},
        {"n": 3, "tags": [{"fire_nums": [{"n": 9, "x": 200}]}]},
        {"n": 20, "tags": [{"lucky": [{"n": 20, "x": 500}]}]},
        {"n": 5, "tags": []},
        {"n": "CoinFlip", "tags": [{"top": {"simbolo": "CoinFlip", "x": 7}}]},
        {"n": "1", "tags": [{"top": {"simbolo": "5", "x": 3}}]}]
_mg = M.PipelinePerceptivo._mult_por_giro(_lin, 6)
checa(_mg == [100.0, 0.0, 500.0, 0.0, 7.0, 0.0],
      "um valor por giro, e só o que PAGOU", _mg)
checa(len(_mg) == len(_lin), "alinhado giro a giro", (len(_mg), len(_lin)))

# e a lista de anúncios não conta o mesmo prêmio duas vezes
_ev = [{"n": 20, "settled": "2026-08-17T10:00:00Z",
        "tags": [{"x": 500}, {"lucky": [{"n": 20, "x": 500}]}]}]
_vistos, _mults = set(), []
for _e2 in _ev:
    _vistos.clear()
    for _t3 in _e2["tags"]:
        if "x" in _t3 and not isinstance(_t3["x"], (dict, list)):
            _k = (str(_e2["n"]), int(_t3["x"]))
            if _k not in _vistos:
                _vistos.add(_k)
                _mults.append({"n": _e2["n"], "x": int(_t3["x"])})
        for _c2 in ("lucky", "fire_nums"):
            for _it2 in (_t3.get(_c2) or []):
                _k = (str(_it2["n"]), int(_it2["x"]))
                if _k not in _vistos:
                    _vistos.add(_k)
                    _mults.append({"n": _it2["n"], "x": int(_it2["x"])})
checa(len(_mults) == 1,
      "a tag solta e a lista descrevem o MESMO sorteio: conta uma vez", _mults)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[13] os quinze agentes caçadores rodam com o dado REAL")

from academia_autonoma.agentes_multiplicador import extrair  # noqa: E402
from academia_autonoma.previsores_multiplicador import (  # noqa: E402
    votos_dos_agentes)


def _hist_viciado(semente, alvo, n=300):
    """No formato que a CAPTURA entrega: `n`/`sec`, sem `valor`."""
    r = random.Random(semente)
    return [{"n": r.randrange(37), "sec": None,
             "tags": [{"lucky": [{"n": alvo if r.random() < 0.5
                                  else r.randrange(37), "x": 50}
                                 for _ in range(r.randint(1, 4))]}]}
            for _ in range(n)]


# `extrair` só lia a chave `valor`. As linhas da captura não têm `valor`:
# str(None) vira "None", nada é numérico, e TODO evento era pulado. Os quinze
# funcionavam nos testes (que montam `valor` na mão) e nunca na máquina dele.
_nums, _bat, _rod = extrair([{"n": 7, "tags": [{"lucky": [{"n": 7, "x": 100}]}]},
                             {"sec": 12, "tags": []},
                             {"valor": "3", "tags": []}])
checa(_nums == [7, 12, 3], "lê o giro venha ele como n, sec ou valor", _nums)
checa(_bat[0] == 100, "e o multiplicador que bateu continua saindo", _bat)

_va = votos_dos_agentes(_hist_viciado(1, 5), chave="lightning")
_vb = votos_dos_agentes(_hist_viciado(2, 22), chave="lightning")
checa(bool(_va), "com o formato da captura, os agentes falam", _va)
checa(_va != _vb, "e históricos diferentes não compartilham resposta",
      ({k: v["alvos"] for k, v in _va.items()},
       {k: v["alvos"] for k, v in _vb.items()}))
checa(any("5" in v["alvos"] for v in _va.values()),
      "cada um acha o vício do SEU histórico",
      {k: v["alvos"] for k, v in _va.items()})
checa(any("22" in v["alvos"] for v in _vb.values()),
      "e o do outro também", {k: v["alvos"] for k, v in _vb.items()})

# ao vivo o histórico cresce pela frente: a cauda não muda, e o guardado serve
import time as _time  # noqa: E402

_vivo = _hist_viciado(1, 5)
_t0 = _time.time()
for _ in range(30):
    _vivo.insert(0, {"n": random.randrange(37), "tags": []})
    votos_dos_agentes(_vivo, chave="lightning")
_gasto = _time.time() - _t0
checa(_gasto < 6.0, f"trinta voltas ao vivo em {_gasto:.1f}s (os quinze são "
                    f"caros e não podem rodar a cada giro)", _gasto)

# ─────────────────────────────────────────────────────────────────────────────
print("\n[14] erro engolido deixa rastro")

from engolido import ARQUIVO, engolido as _eng  # noqa: E402

_antes_tam = ARQUIVO.stat().st_size if ARQUIVO.is_file() else 0
try:
    raise ValueError("defeito de mentira, para o teste")
except ValueError as _e3:
    _eng("teste_v121/rastro", _e3)
checa(ARQUIVO.is_file() and ARQUIVO.stat().st_size > _antes_tam,
      "o erro engolido foi para o arquivo", ARQUIVO)
_texto = ARQUIVO.read_text(encoding="utf-8", errors="replace")
checa("teste_v121/rastro" in _texto and "ValueError" in _texto,
      "com o local e o tipo do erro")
# e a repetição não enche o disco
_tam = ARQUIVO.stat().st_size
for _ in range(50):
    _eng("teste_v121/rastro", ValueError("de novo"))
checa(ARQUIVO.stat().st_size == _tam,
      "o mesmo local não repete a cada volta do laço")

import fluxo_captura as _F2  # noqa: E402

checa("engolido" in (RAIZ / "fluxo_captura.py").read_text(encoding="utf-8"),
      "e o caminho da captura usa isso — era lá que o dado morria calado")

print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("V121_OK")
