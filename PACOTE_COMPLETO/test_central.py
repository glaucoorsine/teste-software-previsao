# -*- coding: utf-8 -*-
"""Exercita a CENTRAL sem Tk: os widgets viram bonecos que só guardam texto.

O que interessa testar aqui não é o desenho, é o que decide: se a janela anda
e fecha na hora certa, se o `last_result` sai para o cérebro, se o estado
sobrevive a fechar e reabrir, e se a tela de abertura salva o canal certo.

    python test_central.py
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))


class Boneco:
    """Widget de mentira: aceita tudo, guarda o que foi configurado.

    Anota também a ordem em que foi empacotado dentro do pai, porque é disso
    que depende um botão aparecer ou sumir na borda da tela.
    """

    def __init__(self, master=None, *a, **k):
        self.cfg = dict(k)
        self.texto = ""
        self.filhos = []
        self.master = master
        self.empacotado = None
        self.abas_criadas = {}
        if isinstance(master, Boneco):
            master.filhos.append(self)

    def pack(self, **k):
        self.empacotado = k

    def __getattr__(self, _):
        return lambda *a, **k: None

    def configure(self, **k):
        self.cfg.update(k)

    def delete(self, *a):
        self.texto = ""

    def insert(self, _pos, txt=""):
        self.texto += str(txt)

    def get(self, *a):
        return self.texto

    def winfo_children(self):
        return list(self.filhos)

    def tab(self, nome):
        # Nada de hasattr aqui: o __getattr__ acima responde a qualquer nome,
        # então toda checagem de existência daria verdadeiro.
        return self.abas_criadas.setdefault(nome, Boneco())


class Variavel:
    def __init__(self, value=""):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


ctk = types.ModuleType("customtkinter")
for nome in ("CTk", "CTkFrame", "CTkLabel", "CTkButton", "CTkTextbox",
             "CTkTabview", "CTkRadioButton", "CTkEntry", "CTkOptionMenu",
             "CTkToplevel", "CTkScrollableFrame"):
    setattr(ctk, nome, type(nome, (Boneco,), {}))
ctk.StringVar = Variavel
ctk.set_appearance_mode = lambda *a: None
sys.modules["customtkinter"] = ctk

import CENTRAL  # noqa: E402

falhas = []


def checa(cond, nome, detalhe=""):
    print(("  ok   " if cond else "  FALHA ") + nome
          + ("" if cond else f"   [{detalhe}]"))
    if not cond:
        falhas.append(nome)


class MesaFalsa(CENTRAL.PainelMesa):
    """Mesma mesa, sem tela e sem processo de cérebro."""

    def __init__(self, jogo):
        self.jogo = jogo
        self.rotulo = jogo
        self.aviso_geral = lambda *a: None
        self.ordem = 0
        self.primeira = True
        self.ok = self.err = self.ok_num = self.err_num = 0
        self.escolhas = []
        self.restantes = 0
        self.vistos = set()
        self.janela_hit = False
        self.ultima_janela = 0
        self.ultimas_escolhas = []
        self.soma_p = 0.0
        self.ultimo_resultado = None
        self.seq_giro = 0
        self.ocupado = False
        self.vivo = True
        self.ultimo_estado = "teste"
        self.arquivo = CENTRAL.PASTA / CENTRAL.ESTADO[jogo]
        for n in ("faixa", "placar", "placar_num", "contadores", "hist",
                  "feed", "st", "academia", "publico"):
            setattr(self, n, Boneco())
        self.caixas = [Boneco() for _ in range(7)]
        self.hist_col = [{"topo": Boneco(), "mult": Boneco(),
                          "num": Boneco(), "marca": Boneco()}
                         for _ in range(16)]
        self.acertos_keys = set()
        self.erros_keys = set()
        self.lendo_academia = False
        self.fontes_da_janela = {}
        self.jogadores = None
        self.mesa_cheia = None
        self.ultimo_publico = 9e18      # nunca consulta no teste
        self.faixa_publico = {}
        self._carregar()

    def after(self, ms, fn=None, *a):
        if callable(fn):
            fn(*a)

    def _academia(self):
        pass                       # lê banco; testado à parte


class ConfigFalsa(CENTRAL.TelaConfig):
    def __init__(self, canal):
        self.entrou = False
        self.ao_terminar = lambda: setattr(self, "entrou", True)
        self.canal = canal
        self.topico = CENTRAL.topico_novo()
        self.var = Variavel(canal)
        self.area = Boneco()
        self.aviso = Boneco()
        self.bt_testar = Boneco()
        self.e_top = Boneco()
        self.e_top.insert(0, self.topico)
        self.e_tel = Boneco()
        self.e_key = Boneco()
        self.e_tok = Boneco()
        self.e_cid = Boneco()

    def after(self, ms, fn=None, *a):
        if callable(fn):
            fn(*a)


# ═══════════════════════════════════════════════════════════ a janela da mesa
print("\n[1] janela de 3 giros, acerto no segundo")
CENTRAL.PASTA.mkdir(parents=True, exist_ok=True)
CENTRAL.ESTADO["lightning"] = "teste_central_state.json"
alvo = CENTRAL.PASTA / "teste_central_state.json"
alvo.unlink(missing_ok=True)

m = MesaFalsa("lightning")
m._aplicar({"pad5": [4, 5, 9, 14, 15, 24, 25], "modo": "OPERAR", "janela": 3},
           [{"n": 7, "settled": "t0"}])
checa(m.escolhas == [4, 5, 9, 14, 15, 24, 25], "sinal entrou")
checa(m.restantes == 3, "janela de 3", m.restantes)

m.validar({"n": 30, "settled": "t1"})
checa(m.restantes == 2 and not m.janela_hit, "erro faz a janela andar", m.restantes)
checa(m.ultimo_resultado == {"saiu": 30, "acertou": False, "settled": "t1",
                             "window_done": False}, "resultado do erro vai ao cérebro")

m.validar({"n": 5, "settled": "t2"})
checa(m.restantes == 1 and m.janela_hit, "acerto marca a janela")
checa(m.ok == 0, "não fecha antes da hora")

m.validar({"n": 33, "settled": "t3"})
checa(m.restantes <= 0 and m.ok == 1 and m.err == 0,
      "fecha como ACERTO (houve acerto dentro)", f"ok={m.ok} err={m.err}")
checa(m.escolhas == [], "libera para o próximo sinal")
checa(m.ultimo_resultado["window_done"] is True, "avisa fim de janela")
checa(m.ok_num == 1 and m.err_num == 2, "contagem por giro",
      f"{m.ok_num}/{m.err_num}")

print("\n[2] janela que erra os três")
m._aplicar({"pad5": [1, 2, 3], "modo": "OPERAR", "janela": 3},
           [{"n": 7, "settled": "t3"}])
for i, n in enumerate((11, 12, 13)):
    m.validar({"n": n, "settled": f"u{i}"})
checa(m.ok == 1 and m.err == 1, "fecha como ERRO", f"ok={m.ok} err={m.err}")

print("\n[3] o mesmo giro não conta duas vezes")
m._aplicar({"pad5": [8], "modo": "OPERAR", "janela": 2},
           [{"n": 7, "settled": "x"}])
antes = m.restantes
m.validar({"n": 8, "settled": "rep"})
m.validar({"n": 8, "settled": "rep"})
checa(m.restantes == antes - 1, "mesmo horário conta uma vez", m.restantes)

print("\n[4] dois giros iguais SEM horário contam os dois")
alvo.unlink(missing_ok=True)
m2 = MesaFalsa("lightning")
m2._aplicar({"pad5": [8], "modo": "OPERAR", "janela": 3},
            [{"n": 7, "settled": None}])
m2.validar({"n": 8, "settled": None})
m2.validar({"n": 8, "settled": None})
checa(m2.restantes == 1, "a janela andou duas vezes", m2.restantes)

print("\n[5] fechar e reabrir mantém placar e janela")
m2._salvar()
esperado = (m2.ok, m2.err, m2.restantes, list(m2.escolhas))
m3 = MesaFalsa("lightning")
checa((m3.ok, m3.err, m3.restantes, list(m3.escolhas)) == esperado,
      "estado retomado", str((m3.ok, m3.err, m3.restantes, m3.escolhas)))
checa(m3.janela_hit == m2.janela_hit, "marca de acerto retomada")

print("\n[6] AGUARDANDO continua existindo quando não há sinal")
m4 = MesaFalsa("mega_fire")
m4.escolhas, m4.restantes = [], 0
m4._aplicar({"pad5": [], "modo": "AGUARDANDO", "janela": 0},
            [{"n": 7, "settled": "z"}])
checa(m4.escolhas == [], "sem evidência, nada é inventado")
checa("AGUARDANDO" in m4.faixa.cfg.get("text", ""), "faixa diz AGUARDANDO",
      m4.faixa.cfg.get("text"))
checa(all(b.cfg.get("text") == "—" for b in m4.caixas), "caixas vazias")

print("\n[7] sinal novo não atropela janela aberta")
m5 = MesaFalsa("immersive")
m5.escolhas, m5.restantes, m5.ultimas_escolhas = [1, 2], 2, [1, 2]
m5._aplicar({"pad5": [30, 31, 32], "modo": "OPERAR", "janela": 4},
            [{"n": 7, "settled": "w"}])
checa(m5.escolhas == [1, 2] and m5.restantes == 2,
      "janela aberta é respeitada", f"{m5.escolhas} {m5.restantes}")

print("\n[8] placar sai no formato honesto")
m6 = MesaFalsa("lightning")
m6.ok, m6.err = 12, 30
m6.ultimas_escolhas, m6.ultima_janela = [4, 5, 9, 14, 15, 24, 25], 4
txt = m6._texto_placar({"mem_stats": {}})
print("       ", txt)
checa(isinstance(txt, str) and len(txt) > 10, "placar montado")

novo = MesaFalsa("mega_fire")
novo.ok = novo.err = 0
t0 = novo._texto_placar({"mem_stats": {}})
print("       ", t0)
checa("nenhuma fechada ainda" in t0,
      "sem janela fechada, diz isso em vez de 'acaso_última≈0%'", t0)
checa("≈0%" not in t0, "e não mostra número que confunde")

print("\n[9] o placar de NÚMEROS aparece, e é diferente do de janelas")
m7 = MesaFalsa("lightning")
m7.ok_num, m7.err_num = 9, 21
m7.ok, m7.err = 7, 3
m7._aplicar({"pad5": [], "modo": "AGUARDANDO"}, [{"n": 5, "settled": "q"}])
alvo_num = m7.placar_num.cfg.get("text", "")
print("       ", alvo_num)
checa("acertos 9" in alvo_num and "erros 21" in alvo_num,
      "mostra acerto e erro por número", alvo_num)
checa("30%" in alvo_num, "e a taxa deles", alvo_num)
checa(m7.placar.cfg.get("text") != alvo_num,
      "não é o mesmo texto do placar de janelas")
zerado = MesaFalsa("immersive")
zerado.ok_num = zerado.err_num = 0
checa("acertos 0" in zerado._texto_numeros(),
      "com zero giros ainda aparece, em vez de sumir",
      zerado._texto_numeros())

print("\n[9b] resumo alimenta o cartão do Painel")
r = m5.resumo()
checa(set(r) == {"rotulo", "estado", "escolhas", "restantes", "ok", "err",
                 "ok_num", "err_num"},
      "resumo tem tudo que o cartão precisa", sorted(r))

# ═════════════════════════════════════════════════ a tela antes de abrir
print("\n[10] tópico sorteado é seguro de digitar")
tops = {CENTRAL.topico_novo() for _ in range(300)}
checa(len(tops) == 300, "não repete", len(tops))
juntos = "".join(tops)
checa(not any(c in juntos for c in "0O1lIi"),
      "sem caractere que se confunde ao digitar")
checa(all(t.startswith("mesa-") and len(t) > 16 for t in tops),
      "formato reconhecível e longo o bastante")

print("\n[11] a tela de abertura salva o canal certo")
import notificador  # noqa: E402
notificador.CFG = Path(tempfile.mkdtemp()) / "notificacoes.json"

c = ConfigFalsa("ntfy")
cfg = c.salvar()
checa(cfg["canal"] == "ntfy" and cfg["topico"] == c.topico,
      "ntfy salva o tópico mostrado na tela", cfg)
gravado = json.loads(notificador.CFG.read_text(encoding="utf-8"))
checa(gravado == cfg, "gravou em disco igualzinho")
checa(notificador.ativo(), "notificador reconhece como pronto")

c2 = ConfigFalsa("whatsapp")
c2.e_tel.insert(0, "+55 (31) 99999-8888")
c2.e_key.insert(0, " 123456 ")
cfg2 = c2.salvar()
checa(cfg2["telefone"] == "5531999998888",
      "telefone vira só dígitos", cfg2["telefone"])
checa(cfg2["apikey"] == "123456", "apikey sem espaço sobrando", cfg2["apikey"])

c3 = ConfigFalsa("nenhum")
cfg3 = c3.salvar()
checa(cfg3["canal"] == "nenhum", "dá para entrar sem aviso")
checa(not notificador.ativo(), "e o notificador fica desligado")

print("\n[12] entrar leva ao laboratório")
c4 = ConfigFalsa("ntfy")
c4._entrar()
checa(c4.entrou, "o botão Entrar chama a abertura do laboratório")

print("\n[13] erro de rede não é confundido com erro de configuração")
checa(CENTRAL.erro_de_rede("ProxyError: HTTPSConnectionPool..."), "proxy")
checa(CENTRAL.erro_de_rede("ConnectionError: falhou"), "conexão")
checa(CENTRAL.erro_de_rede("ReadTimeout: demorou"), "tempo esgotado")
checa(not CENTRAL.erro_de_rede("HTTPError: 403 Forbidden"),
      "403 é configuração, não rede")
checa(not CENTRAL.erro_de_rede(""), "sem erro nenhum")

print("\n[14] só pergunta o canal quando faz sentido")
notificador.CFG.write_text(json.dumps({"canal": "nenhum"}), encoding="utf-8")
checa(CENTRAL.precisa_configurar(), "canal desligado: pergunta")
notificador.CFG.write_text(json.dumps({"canal": "ntfy", "topico": "abc"}),
                           encoding="utf-8")
checa(not CENTRAL.precisa_configurar(), "já configurado: entra direto")

print("\n[15] a Conversa fica legível")
ev = {"horario": "2026-08-14T18:58:28", "agente": "ESTATISTICO",
      "etapa": "modelo.opiniao", "resultado": "modelo.opiniao",
      "acao": "pendente", "amostra": 0}
ln = CENTRAL.linha_do_feed(ev)
checa("18:58:28" in ln and "ESTATISTICO" in ln, "hora e agente na linha", ln)
checa(ln.count("modelo.opiniao") == 1,
      "não repete a etapa como se fosse resultado", ln)
checa("pendente" in ln, "mostra a ação, que é o que acrescenta", ln)

com_desc = dict(ev, resultado="gap 10 med=25", amostra=32)
ln2 = CENTRAL.linha_do_feed(com_desc)
checa("gap 10 med=25" in ln2, "resultado de verdade aparece", ln2)
checa("n=32" in ln2, "amostra aparece — é ela que diz se tem peso", ln2)

# o feed real cicla os agentes, então o repetido não vem colado
ciclo = []
for _ in range(6):
    for ag in ("ESTATISTICO", "ANOMALIA", "REGIME", "SEQ_MARKOV"):
        ciclo.append(("2026-08-14T18:58:28", "Immersive", dict(ev, agente=ag)))
texto = CENTRAL.juntar_repetidas(ciclo)
linhas_c = [x for x in texto.splitlines() if x.strip()]
checa(len(linhas_c) == 4, "24 registros viram 4 linhas", len(linhas_c))
checa(all("×6" in x for x in linhas_c), "cada uma diz que aconteceu 6 vezes")
checa(all(x.startswith("Immersive") for x in linhas_c), "a mesa fica visível")

variado = [("2026-08-14T18:58:28", "Lightning", dict(ev, agente="A")),
           ("2026-08-14T18:58:29", "Lightning", dict(ev, agente="A"))]
t2 = CENTRAL.juntar_repetidas(variado)
checa(len([x for x in t2.splitlines() if x.strip()]) == 2,
      "segundos diferentes não são juntados", t2)
checa("×" not in t2, "e nada de contador onde não houve repetição")

print("\n[16] o histórico mostra número, acerto e multiplicador")
mh = MesaFalsa("lightning")
antes_ids = [id(c["num"]) for c in mh.hist_col]
giros = [{"n": 1, "settled": "a", "tags": [{"x": 100}]},
         {"n": 0, "settled": "b", "tags": []},
         {"n": 32, "settled": "c", "tags": [{"x": 50}]},
         {"n": 5, "settled": "d", "tags": []}]
mh.acertos_keys = {"a", "c"}
mh.erros_keys = {"b"}
mh._desenhar_hist(giros)
checa([id(c["num"]) for c in mh.hist_col] == antes_ids,
      "os mesmos widgets continuam lá — nada é destruído")
checa(mh.hist_col[0]["num"].cfg.get("text") == "1", "primeiro giro desenhado",
      mh.hist_col[0]["num"].cfg.get("text"))
checa(mh.hist_col[1]["num"].cfg.get("fg_color") == "#16a34a",
      "o zero fica verde", mh.hist_col[1]["num"].cfg.get("fg_color"))

checa(mh.hist_col[0]["mult"].cfg.get("text") == "×100",
      "multiplicador de 100 aparece", mh.hist_col[0]["mult"].cfg.get("text"))
checa(mh.hist_col[2]["mult"].cfg.get("text") == "×50",
      "e o de 50 também", mh.hist_col[2]["mult"].cfg.get("text"))
checa(mh.hist_col[1]["mult"].cfg.get("text") == "",
      "giro sem multiplicador fica limpo",
      mh.hist_col[1]["mult"].cfg.get("text"))

checa(mh.hist_col[0]["marca"].cfg.get("text") == "✓",
      "giro que caiu na aposta leva ✓", mh.hist_col[0]["marca"].cfg.get("text"))
checa(mh.hist_col[1]["marca"].cfg.get("text") == "✗",
      "giro conferido e errado leva ✗", mh.hist_col[1]["marca"].cfg.get("text"))
checa(mh.hist_col[3]["marca"].cfg.get("text") == "",
      "giro nunca conferido não leva marca nenhuma — senão o placar visual "
      "ficaria pior que o real", mh.hist_col[3]["marca"].cfg.get("text"))

mh._desenhar_hist([{"n": 1, "settled": "a"}])
checa(mh.hist_col[1]["num"].cfg.get("text") == "",
      "e some ao encurtar o histórico", mh.hist_col[1]["num"].cfg.get("text"))
checa(mh.hist_col[1]["mult"].cfg.get("text") == "",
      "o multiplicador some junto")

print("\n[16b] o multiplicador é lido dos dois formatos de captura")
checa(CENTRAL.texto_multiplicador({"n": 7, "tags": [{"x": 7}]}) == "×7",
      "formato do Crazy Time")
checa(CENTRAL.texto_multiplicador(
    {"n": 13, "tags": [{"lucky": [{"n": 13, "x": 500}]}]}) == "×500",
    "formato lucky da roleta")
checa(CENTRAL.texto_multiplicador(
    {"n": 13, "tags": [{"lucky": [{"n": 20, "x": 500}]}]}) == "",
    "lucky de OUTRO número não é o multiplicador deste giro")
checa(CENTRAL.texto_multiplicador({"n": 5, "tags": [{"x": 3}, {"x": 50}]})
      == "×50", "com mais de um, mostra o maior")
checa(CENTRAL.texto_multiplicador({"n": 5}) == "", "sem tags, nada")
checa(CENTRAL.texto_multiplicador({"n": 5, "tags": [{"x": "abc"}]}) == "",
      "valor estragado não quebra a tela")

print("\n[16c] as marcas sobrevivem a fechar e reabrir")
alvo.unlink(missing_ok=True)
ms = MesaFalsa("lightning")
ms._aplicar({"pad5": [8, 9], "modo": "OPERAR", "janela": 2},
            [{"n": 7, "settled": "z0"}])
ms.validar({"n": 8, "settled": "z1"})       # acerto
ms.validar({"n": 30, "settled": "z2"})      # erro
checa("z1" in ms.acertos_keys and "z2" in ms.erros_keys,
      "conferência marcou os dois giros")
ms2 = MesaFalsa("lightning")
checa("z1" in ms2.acertos_keys, "o ✓ voltou depois de reabrir")
checa("z2" in ms2.erros_keys, "o ✗ voltou também")

print("\n[17] leitura da academia não empilha")


class MesaLenta(MesaFalsa):
    """Mesa cuja leitura de banco demora — o caso que empilhava threads."""

    def __init__(self, jogo):
        super().__init__(jogo)
        self.leituras = 0

    def _academia(self):
        # cópia fiel da trava real, sem tocar no banco
        if self.lendo_academia:
            return
        self.lendo_academia = True
        self.leituras += 1


ml = MesaLenta("lightning")
for _ in range(5):
    ml._academia()          # nenhuma termina: a trava fica presa de propósito
checa(ml.leituras == 1, "cinco voltas seguidas leem uma vez só", ml.leituras)
ml.lendo_academia = False   # a leitura terminou
ml._academia()
checa(ml.leituras == 2, "liberada, volta a ler", ml.leituras)

print("\n[18] botão de ação não fica escondido embaixo da caixa")


class LabFalso(CENTRAL.Laboratorio):
    """Só as abas — sem mesas, sem cérebro."""

    def __init__(self):
        self.abas = Boneco()

    def after(self, ms, fn=None, *a):
        if callable(fn) and ms < 1000:
            fn(*a)


def botao_visivel(aba) -> bool:
    """Um botão empacotado depois de uma caixa que come a altura toda vai
    parar na borda de baixo e some da vista. Se houver botão, ele tem que
    aparecer antes do primeiro widget com expand."""
    vistos = []
    for w in aba.filhos:
        if w.empacotado is None:
            continue
        vistos.append((type(w).__name__, w.empacotado.get("expand")))
    primeiro_expand = next((i for i, (_, ex) in enumerate(vistos) if ex), None)
    botoes = [i for i, (tipo, _) in enumerate(vistos) if tipo == "CTkButton"]
    if not botoes or primeiro_expand is None:
        return True
    return min(botoes) < primeiro_expand


lab = LabFalso()
lab._fontes()
lab._progresso()
for nome in ("Fontes", "Progresso"):
    aba = lab.abas.tab(nome)
    checa(botao_visivel(aba), f"aba {nome}: botão antes da caixa que expande",
          [(type(w).__name__, w.empacotado) for w in aba.filhos])



print("\n[19] eco de janela já fechada não vira aposta nova")
# aponta a mesa para o arquivo de teste: sem isso ela carrega o estado REAL
# do immersive, que pode ter janela aberta, e o teste mede outra coisa
CENTRAL.ESTADO["immersive"] = "teste_central_state.json"
alvo.unlink(missing_ok=True)
me = MesaFalsa("immersive")
me._aplicar({"pad5": ["29", "24"], "modo": "OPERAR", "janela": 3},
            [{"n": 7, "settled": "e0"}])
checa(me.escolhas == ["29", "24"], "a decisão real abre a janela", me.escolhas)
for i, n in enumerate((36, 21, 30)):
    me.validar({"n": n, "settled": f"e{i+1}"})
checa(me.escolhas == [] and me.err == 1, "janela fecha como erro",
      f"{me.escolhas} err={me.err}")

# é isto que acontecia no log dele: o cérebro devolve a mesma aposta
# como JANELA_ATIVA logo depois de fechar
me._aplicar({"pad5": ["29", "24"], "modo": "JANELA_ATIVA", "janela": 3},
            [{"n": 7, "settled": "e4"}])
checa(me.escolhas == [], "o eco não reabre a aposta velha", me.escolhas)
checa(me.err == 1, "e não gera janela nova para errar de novo", me.err)

# mas o eco de uma janela que AINDA está aberta não pode apagá-la
me._aplicar({"pad5": ["1", "2"], "modo": "OPERAR", "janela": 3},
            [{"n": 7, "settled": "e5"}])
me.validar({"n": 33, "settled": "e6"})
antes = (list(me.escolhas), me.restantes)
me._aplicar({"pad5": ["1", "2"], "modo": "JANELA_ATIVA", "janela": 3},
            [{"n": 7, "settled": "e7"}])
checa((list(me.escolhas), me.restantes) == antes,
      "janela em andamento continua intacta", (me.escolhas, me.restantes))

# uma decisão de verdade depois do eco continua entrando
me.escolhas, me.restantes = [], 0
me._aplicar({"pad5": ["7", "8"], "modo": "OPERAR", "janela": 3},
            [{"n": 7, "settled": "e8"}])
checa(me.escolhas == ["7", "8"], "OPERAR novo entra normalmente", me.escolhas)



print("\n[20] o acerto é reconhecido mesmo com tipos diferentes")
checa(CENTRAL.esta_na_aposta(29, ["29", "24"]),
      "roleta manda int, aposta vem em texto — ERA AQUI O DEFEITO")
checa(CENTRAL.esta_na_aposta("29", [29, 24]), "e o contrário também")
checa(CENTRAL.esta_na_aposta(29, [29, 24]), "int com int")
checa(CENTRAL.esta_na_aposta("1", ["1", "2"]), "texto com texto")
checa(CENTRAL.esta_na_aposta("Pachinko", ["10", "Pachinko"]),
      "símbolo do Crazy Time, que não vira número")
checa(CENTRAL.esta_na_aposta(0, ["0"]), "o zero, que é fácil de perder")
checa(not CENTRAL.esta_na_aposta(30, ["29", "24"]), "erro continua erro")
checa(not CENTRAL.esta_na_aposta(2, ["29", "24"]),
      "2 não casa com 29 — nada de comparar por pedaço")
checa(not CENTRAL.esta_na_aposta(7, []), "sem aposta, não há acerto")
checa(not CENTRAL.esta_na_aposta(7, None), "aposta nula não quebra")

print("\n[20b] a janela da roleta agora fecha como acerto")
CENTRAL.ESTADO["immersive"] = "teste_central_state.json"
alvo.unlink(missing_ok=True)
mt = MesaFalsa("immersive")
# exatamente o caso do log: aposta em texto, giro em inteiro
mt._aplicar({"pad5": ["29", "24"], "modo": "OPERAR", "janela": 3},
            [{"n": 7, "settled": "t0"}])
mt.validar({"n": 36, "settled": "t1"})
mt.validar({"n": 29, "settled": "t2"})       # este é acerto
checa(mt.janela_hit, "o 29 foi reconhecido como acerto")
checa(mt.ok_num == 1, "e contou no placar de números", mt.ok_num)
mt.validar({"n": 30, "settled": "t3"})
checa(mt.ok == 1 and mt.err == 0, "a janela fechou como ACERTO",
      f"ok={mt.ok} err={mt.err}")
checa("t2" in mt.acertos_keys, "e o giro leva ✓ no histórico")



print("\n[21] Crazy Time: top slot, resultado e multiplicador")
giro = {"n": "2", "settled": "c1",
        "tags": [{"top": {"simbolo": "5", "x": 3}}, {"x": 2}]}
t = CENTRAL.top_slot(giro)
checa(t["simbolo"] == "5" and t["x"] == 3, "lê o símbolo e o multiplicador do slot", t)
checa(t["bateu"] is False, "sorteou 5, a roda parou no 2 — não bateu")
checa(CENTRAL.texto_top_slot(giro) == "5 ×3 miss",
      "e a linha diz miss", CENTRAL.texto_top_slot(giro))
# o 3 do top slot NAO e o multiplicador aplicado: no print dele,
# "5 3X | 2 | 2X" quer dizer slot 5 a 3X, roda no 2, aplicado 2X
checa(CENTRAL.texto_multiplicador(giro) == "×2",
      "o multiplicador aplicado é o do giro, não o do slot",
      CENTRAL.texto_multiplicador(giro))

bateu = {"n": "2", "settled": "c2",
         "tags": [{"top": {"simbolo": "2", "x": 10}}, {"x": 10}]}
tb = CENTRAL.top_slot(bateu)
checa(tb["bateu"] is True, "top slot no 2 e roda no 2 — bateu")
checa(CENTRAL.texto_top_slot(bateu) == "2 ×10",
      "quando bate, não escreve miss", CENTRAL.texto_top_slot(bateu))

sem = {"n": "1", "settled": "c3", "tags": [{"x": 1}]}
checa(CENTRAL.texto_top_slot(sem) == "", "giro sem top slot fica em branco")
checa(CENTRAL.top_slot({"n": "1"})["simbolo"] is None, "sem tags não quebra")

bonus = {"n": "CashHunt", "settled": "c4",
         "tags": [{"top": {"simbolo": "CashHunt", "x": 5}}]}
checa(CENTRAL.top_slot(bonus)["bateu"] is True,
      "bônus também casa por nome, não só número")
checa(CENTRAL.texto_top_slot(bonus) == "CashHunt ×5", "e aparece por extenso")

print("\n[21b] o desenho põe cada coisa na sua linha")
CENTRAL.ESTADO["crazy_time"] = "teste_central_state.json"
alvo.unlink(missing_ok=True)
mc = MesaFalsa("crazy_time")
mc._desenhar_hist([giro, bateu, sem])
checa(mc.hist_col[0]["topo"].cfg.get("text") == "5 ×3 miss",
      "primeira coluna: o top slot", mc.hist_col[0]["topo"].cfg.get("text"))
checa(mc.hist_col[0]["num"].cfg.get("text") == "2",
      "o resultado real embaixo dele", mc.hist_col[0]["num"].cfg.get("text"))
checa(mc.hist_col[0]["mult"].cfg.get("text") == "×2",
      "e o multiplicador aplicado", mc.hist_col[0]["mult"].cfg.get("text"))
checa(mc.hist_col[1]["topo"].cfg.get("text_color") == "#38bdf8",
      "top slot que bateu fica aceso",
      mc.hist_col[1]["topo"].cfg.get("text_color"))
checa(mc.hist_col[0]["topo"].cfg.get("text_color") == CENTRAL.FRACO,
      "e o miss fica apagado")
checa(mc.hist_col[5]["topo"].cfg.get("text") == "",
      "coluna sobrando fica limpa")

alvo.unlink(missing_ok=True)
print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("CENTRAL_TESTES_OK")
