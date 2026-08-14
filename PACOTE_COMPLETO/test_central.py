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
    """Widget de mentira: aceita tudo, guarda o que foi configurado."""

    def __init__(self, *a, **k):
        self.cfg = dict(k)
        self.texto = ""
        self.filhos = []

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
        return self.filhos_por_nome.setdefault(nome, Boneco())

    filhos_por_nome: dict = {}


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
        for n in ("faixa", "placar", "contadores", "hist", "feed", "st",
                  "academia"):
            setattr(self, n, Boneco())
        self.caixas = [Boneco() for _ in range(7)]
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

print("\n[9] resumo alimenta o cartão do Painel")
r = m5.resumo()
checa(set(r) == {"rotulo", "estado", "escolhas", "restantes", "ok", "err"},
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

alvo.unlink(missing_ok=True)
print()
if falhas:
    print("FALHAS:", falhas)
    sys.exit(1)
print("CENTRAL_TESTES_OK")
