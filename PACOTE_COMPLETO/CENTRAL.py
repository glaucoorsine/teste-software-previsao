# -*- coding: utf-8 -*-
"""
CENTRAL — o laboratório inteiro em uma janela.

    CENTRAL.bat        (ou: python CENTRAL.py)

Abre pedindo como você quer ser avisado no celular, porque descobrir que o
aviso não estava configurado depois de três horas de mesa é o pior jeito de
descobrir. Configurado isso, entra no laboratório: as quatro mesas rodando ao
mesmo tempo, os agentes da academia, e o que as IAs estão conversando — tudo
em abas, uma janela só.

O QUE CADA ABA MOSTRA
---------------------
Painel      as quatro mesas lado a lado: sinal, placar e estado
uma mesa    a sugestão, a janela aberta, o histórico e o que as IAs disseram
IAs         os agentes da academia daquela mesa, um a um, com o que acharam
Conversa    o que as quatro estão fazendo agora, em tempo real
Progresso   quanto histórico já foi juntado
Fontes      o que cada site está devolvendo
Avisos      o canal de notificação, e um teste na hora

UMA MESA QUE TRAVA NÃO DERRUBA AS OUTRAS
----------------------------------------
Cada mesa tem seu próprio processo de cérebro e sua própria thread de captura,
com o erro isolado. Quem falha aparece com aviso na aba dela e as demais
seguem. Este é o risco real de juntar tudo, e é por isso que a captura roda em
thread e o cérebro em processo separado — nunca dentro da interface.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue as _queue
import secrets
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from worker_process import process_cerebro

RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / "Logs"
LOG = PASTA / "central_log.txt"
JOGOS = [("lightning", "Lightning"), ("mega_fire", "Mega Fire"),
         ("immersive", "Immersive"), ("crazy_time", "Crazy Time")]

# Mesmo arquivo que o combo daquela mesa usa: o placar que ele já acumulou
# continua de onde parou, em vez de zerar por trocar de janela.
ESTADO = {"lightning": "lightning_combo_state.json",
          "mega_fire": "mega_fire_combo_state.json",
          "immersive": "immersive_combo_state.json",
          "crazy_time": "crazy_time_state.json"}

VERMELHOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
PERIODO_S = 10          # de quanto em quanto cada mesa consulta

# A primeira resposta de um cérebro é cara: ele carrega a academia, as teorias
# e os modelos daquela mesa. Medido, sozinho, dá ~70s numa roleta; com quatro
# subindo juntas passa fácil de 90s. Depois disso cada volta leva ~0,3s. Por
# isso a primeira espera é larga e as demais são curtas, e as mesas sobem
# escalonadas em vez de disputarem o processador todas no mesmo instante.
ESPERA_1A_S = 300
ESPERA_S = 90
ATRASO_ENTRE_MESAS_S = 20

# Sem vogais parecidas nem 0/O, 1/l: o tópico do ntfy vai ser digitado à mão
# no celular, e um caractere ambíguo vira uma hora procurando por que o aviso
# não chega.
ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"

FUNDO = "#0b1220"
CARTAO = "#111c2e"
BORDA = "#1e293b"
TEXTO = "#e2e8f0"
FRACO = "#94a3b8"
VERDE = "#22c55e"
VERMELHO = "#ef4444"
AMARELO = "#eab308"
ROXO = "#a78bfa"
AZUL = "#38bdf8"


def registrar(msg: str) -> None:
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%d/%m %H:%M:%S} | {msg}\n")
    except OSError:
        pass


def topico_novo() -> str:
    """Nome que ninguém adivinha — no ntfy o tópico é a senha.

    O prefixo também sai do alfabeto seguro: "lab-" parece inofensivo, mas o
    `l` é justamente o que se confunde com `1` na hora de digitar no celular.
    """
    return "mesa-" + "-".join(
        "".join(secrets.choice(ALFABETO) for _ in range(5)) for _ in range(3))


def cor_do_numero(v) -> str:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return "#334155"
    if n == 0:
        return "#16a34a"
    return "#dc2626" if n in VERMELHOS else "#1f2937"


def precisa_configurar() -> bool:
    """Primeira vez, ou canal desligado: vale perguntar antes de entrar."""
    try:
        import notificador
        return (notificador._cfg().get("canal") or "nenhum").lower() == "nenhum"
    except Exception:
        return True


def linha_do_feed(e: dict, largura_agente: int = 18) -> str:
    """Uma linha legível do que um agente fez.

    O registro traz `etapa` e `resultado`, e muitas vezes os dois são a mesma
    palavra — imprimir os dois lado a lado enche a tela de "modelo.opiniao
    modelo.opiniao", que não conta nada. Aqui o segundo campo só aparece
    quando acrescenta informação, e a amostra entra porque é ela que diz se
    aquilo já tem peso ou ainda é palpite de dois casos.
    """
    hora = str(e.get("horario") or "")[11:19]
    agente = str(e.get("agente") or "")[:largura_agente]
    etapa = str(e.get("etapa") or "")
    resultado = str(e.get("resultado") or "")
    acao = str(e.get("acao") or "")
    detalhe = ""
    if resultado and resultado != etapa:
        detalhe = resultado
    elif acao and acao != etapa:
        detalhe = acao
    amostra = e.get("amostra") or 0
    if amostra:
        detalhe = (detalhe + f"  (n={amostra})").strip()
    return f"{hora}  {agente:<{largura_agente}} {etapa[:26]:<26} {detalhe[:40]}"


def juntar_repetidas(itens, limite: int = 200) -> str:
    """Monta a Conversa juntando os registros iguais do mesmo instante.

    A academia grava a opinião de cada agente a cada volta, e no mesmo segundo
    os quatro se revezam — ESTATISTICO, ANOMALIA, REGIME, SEQ_MARKOV, e de
    novo. Não são linhas repetidas em seguida, é um ciclo que se repete, então
    juntar só o que vem colado não resolve: a tela continua uma parede.
    Aqui o agrupamento é pelo evento inteiro (hora, mesa, agente, etapa), que
    é o que realmente identifica "isto é a mesma coisa outra vez".
    """
    ordem: list = []
    conta: dict = {}
    exemplo: dict = {}
    for hora, rotulo, e in itens:
        chave = (hora, rotulo, e.get("agente"), e.get("etapa"),
                 e.get("resultado"), e.get("acao"))
        if chave not in conta:
            if len(ordem) >= limite:
                continue
            ordem.append(chave)
            conta[chave] = 0
            exemplo[chave] = (rotulo, e)
        conta[chave] += 1
    saida = []
    for chave in ordem:
        rotulo, e = exemplo[chave]
        n = conta[chave]
        saida.append(f"{rotulo:<11} " + linha_do_feed(e)
                     + (f"   ×{n}" if n > 1 else ""))
    return "\n".join(saida)


def erro_de_rede(msg: str) -> bool:
    """Falha de conexão não é falha de configuração.

    Sem separar as duas, o aviso manda procurar defeito no aplicativo quando
    o problema era a internet.
    """
    return any(p in (msg or "") for p in
               ("ProxyError", "ConnectionError", "Timeout", "SSLError",
                "NameResolution", "ConnectTimeout", "MaxRetry"))


# ══════════════════════════════════════════════════════════ tela de abertura
class TelaConfig(ctk.CTkFrame):
    """Como você quer ser avisado — perguntado antes de abrir o laboratório."""

    def __init__(self, master, ao_terminar):
        super().__init__(master, fg_color=FUNDO)
        self.ao_terminar = ao_terminar
        self.canal = "ntfy"
        self.topico = topico_novo()

        ctk.CTkLabel(self, text="Antes de começar",
                     font=("Arial", 26, "bold"), text_color=TEXTO
                     ).pack(anchor="w", padx=36, pady=(34, 2))
        ctk.CTkLabel(self, text="Como você quer receber o aviso quando "
                                "aparecer uma entrada?",
                     font=("Arial", 14), text_color=FRACO
                     ).pack(anchor="w", padx=36, pady=(0, 18))

        escolha = ctk.CTkFrame(self, fg_color="transparent")
        escolha.pack(anchor="w", padx=36)
        self.var = ctk.StringVar(value="ntfy")
        opcoes = [("ntfy", "ntfy — o mais simples: instale o app e pronto. "
                           "Sem cadastro, sem bot, sem apikey."),
                  ("whatsapp", "WhatsApp — chega junto com suas mensagens, "
                               "mas depende do CallMeBot autorizar."),
                  ("telegram", "Telegram — precisa criar um bot no @BotFather."),
                  ("nenhum", "Agora não — entrar sem aviso no celular.")]
        for valor, texto in opcoes:
            ctk.CTkRadioButton(escolha, text=texto, variable=self.var,
                               value=valor, font=("Arial", 13),
                               text_color=TEXTO, command=self._trocar
                               ).pack(anchor="w", pady=5)

        self.area = ctk.CTkFrame(self, fg_color=CARTAO, border_width=1,
                                 border_color=BORDA, corner_radius=10)
        self.area.pack(fill="x", padx=36, pady=18)

        self.aviso = ctk.CTkLabel(self, text="", font=("Arial", 13),
                                  justify="left", wraplength=820,
                                  text_color=FRACO)
        self.aviso.pack(anchor="w", padx=36)

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(anchor="w", padx=36, pady=20)
        self.bt_testar = ctk.CTkButton(rodape, text="Testar agora",
                                       width=150, command=self._testar)
        self.bt_testar.pack(side="left", padx=(0, 10))
        ctk.CTkButton(rodape, text="Entrar no laboratório  →", width=220,
                      fg_color=VERDE, hover_color="#16a34a",
                      text_color="#052e16", font=("Arial", 14, "bold"),
                      command=self._entrar).pack(side="left")

        self._trocar()

    # ------------------------------------------------------------------ meio
    def _limpar(self):
        for w in self.area.winfo_children():
            w.destroy()

    def _trocar(self):
        self.canal = self.var.get()
        self._limpar()
        self.aviso.configure(text="")
        if self.canal == "ntfy":
            self._campos_ntfy()
        elif self.canal == "whatsapp":
            self._campos_whatsapp()
        elif self.canal == "telegram":
            self._campos_telegram()
        else:
            ctk.CTkLabel(self.area, text="Você pode ligar o aviso depois, "
                                         "pela aba Avisos.",
                         text_color=FRACO, font=("Arial", 13)
                         ).pack(anchor="w", padx=16, pady=16)

    def _campos_ntfy(self):
        ctk.CTkLabel(self.area, text="1.  No celular, instale o aplicativo  "
                                     "ntfy  (Android ou iPhone)",
                     font=("Arial", 14), text_color=TEXTO
                     ).pack(anchor="w", padx=16, pady=(16, 4))
        ctk.CTkLabel(self.area, text="2.  Abra o app, toque no  +  e assine "
                                     "exatamente este tópico:",
                     font=("Arial", 14), text_color=TEXTO
                     ).pack(anchor="w", padx=16, pady=(6, 8))
        cx = ctk.CTkFrame(self.area, fg_color="#0b1220", corner_radius=8)
        cx.pack(anchor="w", padx=16, pady=(0, 8))
        self.e_top = ctk.CTkEntry(cx, width=430, font=("Consolas", 18),
                                  fg_color="#0b1220", border_width=0,
                                  text_color=VERDE)
        self.e_top.insert(0, self.topico)
        self.e_top.pack(side="left", padx=10, pady=8)
        ctk.CTkButton(cx, text="sortear outro", width=120,
                      fg_color="#1f2937", hover_color="#334155",
                      command=self._sortear).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(self.area,
                     text=("Copie letra por letra. Esse nome é a senha: quem "
                           "souber, recebe os seus avisos.\n"
                           "O ntfy tem dois lados — trocar o nome aqui NÃO muda "
                           "o que o aplicativo escuta. Se você não assinar no "
                           "app, nada chega e nada avisa que falhou."),
                     font=("Arial", 12), text_color=FRACO, justify="left",
                     wraplength=780).pack(anchor="w", padx=16, pady=(0, 16))

    def _campos_whatsapp(self):
        ctk.CTkLabel(self.area,
                     text=("1.  Salve nos contatos:   +34 644 51 95 23\n"
                           "2.  Mande a ele, por WhatsApp, exatamente:\n"
                           "        I allow callmebot to send me messages\n"
                           "3.  Ele responde com uma apikey. Cole abaixo."),
                     font=("Arial", 13), text_color=TEXTO, justify="left"
                     ).pack(anchor="w", padx=16, pady=(16, 10))
        linha = ctk.CTkFrame(self.area, fg_color="transparent")
        linha.pack(anchor="w", padx=16, pady=(0, 16))
        self.e_tel = ctk.CTkEntry(linha, width=260,
                                  placeholder_text="telefone, ex 5531999998888")
        self.e_tel.pack(side="left", padx=(0, 8))
        self.e_key = ctk.CTkEntry(linha, width=200, placeholder_text="apikey")
        self.e_key.pack(side="left")

    def _campos_telegram(self):
        ctk.CTkLabel(self.area,
                     text=("1.  No Telegram, fale com @BotFather e mande /newbot\n"
                           "2.  Ele devolve um token\n"
                           "3.  Mande qualquer mensagem para o SEU bot\n"
                           "4.  Abra  api.telegram.org/botSEU_TOKEN/getUpdates  "
                           "e procure  \"chat\":{\"id\":NUMERO"),
                     font=("Arial", 13), text_color=TEXTO, justify="left"
                     ).pack(anchor="w", padx=16, pady=(16, 10))
        linha = ctk.CTkFrame(self.area, fg_color="transparent")
        linha.pack(anchor="w", padx=16, pady=(0, 16))
        self.e_tok = ctk.CTkEntry(linha, width=300, placeholder_text="token")
        self.e_tok.pack(side="left", padx=(0, 8))
        self.e_cid = ctk.CTkEntry(linha, width=180, placeholder_text="chat_id")
        self.e_cid.pack(side="left")

    def _sortear(self):
        self.topico = topico_novo()
        self.e_top.delete(0, "end")
        self.e_top.insert(0, self.topico)

    # ----------------------------------------------------------------- saída
    def montar_cfg(self) -> dict:
        c = {"canal": self.canal, "topico": "", "token": "", "chat_id": "",
             "telefone": "", "apikey": ""}
        if self.canal == "ntfy":
            c["topico"] = self.e_top.get().strip()
        elif self.canal == "whatsapp":
            c["telefone"] = "".join(ch for ch in self.e_tel.get() if ch.isdigit())
            c["apikey"] = self.e_key.get().strip()
        elif self.canal == "telegram":
            c["token"] = self.e_tok.get().strip()
            c["chat_id"] = self.e_cid.get().strip()
        return c

    def salvar(self) -> dict:
        cfg = self.montar_cfg()
        try:
            import notificador
            notificador.CFG.write_text(
                json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError as e:
            registrar(f"config: {e}")
        return cfg

    def _testar(self):
        cfg = self.salvar()
        if cfg["canal"] == "nenhum":
            self.aviso.configure(text="Nenhum canal escolhido — não há o que "
                                      "testar.", text_color=FRACO)
            return
        self.bt_testar.configure(state="disabled", text="enviando…")

        def tarefa():
            try:
                import importlib
                import notificador
                importlib.reload(notificador)
                if not notificador.ativo():
                    msg, cor = ("Faltou preencher algum campo — o canal ficou "
                                "incompleto.", VERMELHO)
                else:
                    err = notificador._enviar(
                        "Laboratorio - teste",
                        "Se você está lendo isto no celular, os avisos de "
                        "entrada vão chegar.")
                    if not err:
                        msg, cor = ("Enviado. Olhe o celular agora. Se não "
                                    "chegou, o app não está assinando este "
                                    "tópico.", VERDE)
                    elif erro_de_rede(err):
                        msg, cor = (f"Isto foi a conexão, não a sua "
                                    f"configuração: o computador não "
                                    f"conseguiu falar com o servidor. ({err})",
                                    AMARELO)
                    else:
                        msg, cor = (f"Não foi: {err}", VERMELHO)
            except Exception as e:
                msg, cor = (f"{type(e).__name__}: {e}", VERMELHO)
            self.after(0, lambda: (self.aviso.configure(text=msg, text_color=cor),
                                   self.bt_testar.configure(
                                       state="normal", text="Testar agora")))

        threading.Thread(target=tarefa, daemon=True).start()

    def _entrar(self):
        self.salvar()
        self.ao_terminar()


# ═══════════════════════════════════════════════════════════════ uma mesa
class PainelMesa(ctk.CTkFrame):
    """Uma mesa: captura, cérebro, e o que aparece na tela."""

    def __init__(self, master, jogo: str, rotulo: str, aviso_geral, ordem=0):
        super().__init__(master, fg_color="transparent")
        self.jogo = jogo
        self.rotulo = rotulo
        self.aviso_geral = aviso_geral
        self.ordem = ordem
        self.primeira = True
        self.ok = self.err = 0
        self.ok_num = self.err_num = 0
        self.escolhas: list = []
        self.restantes = 0
        self.vistos: set = set()
        self.janela_hit = False
        self.ultima_janela = 0
        self.ultimas_escolhas: list = []
        self.soma_p = 0.0
        self.ultimo_resultado = None
        self.seq_giro = 0
        self.ocupado = False
        self.vivo = True
        self.ultimo_estado = "iniciando"
        self.arquivo = PASTA / ESTADO[jogo]
        self._carregar()
        self._montar()

        self.entrada, self.saida = mp.Queue(), mp.Queue()
        self.processo = mp.Process(target=process_cerebro,
                                   args=(self.entrada, self.saida, jogo),
                                   daemon=True)
        self.processo.start()
        self.after(1200 + ordem * ATRASO_ENTRE_MESAS_S * 1000, self.rodar)

    # ------------------------------------------------------------- interface
    def _montar(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(topo, text=self.rotulo, font=("Arial", 22, "bold"),
                     text_color=AZUL).pack(side="left")
        self.st = ctk.CTkLabel(topo, text="iniciando…", text_color=ROXO,
                               font=("Arial", 13))
        self.st.pack(side="left", padx=14)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=16, pady=6)
        esq = ctk.CTkFrame(corpo, fg_color="transparent")
        esq.pack(side="left", fill="both", expand=True)
        dir_ = ctk.CTkFrame(corpo, fg_color=CARTAO, border_width=1,
                            border_color=BORDA, corner_radius=10, width=380)
        dir_.pack(side="right", fill="both", padx=(12, 0))
        dir_.pack_propagate(False)

        self.faixa = ctk.CTkLabel(esq, text="AGUARDANDO",
                                  font=("Arial", 16, "bold"),
                                  text_color=VERMELHO)
        self.faixa.pack(anchor="w", pady=(2, 8))

        cx = ctk.CTkFrame(esq, fg_color=CARTAO, border_width=2,
                          border_color=VERDE, corner_radius=10)
        cx.pack(fill="x")
        ctk.CTkLabel(cx, text="SUGESTÃO", font=("Arial", 11, "bold"),
                     text_color=FRACO).pack(anchor="w", padx=12, pady=(10, 0))
        linha = ctk.CTkFrame(cx, fg_color="transparent")
        linha.pack(padx=12, pady=10)
        self.caixas = []
        for _ in range(7):
            b = ctk.CTkLabel(linha, text="—", width=56, height=48,
                             fg_color="#334155", corner_radius=8,
                             font=("Arial", 19, "bold"))
            b.pack(side="left", padx=3)
            self.caixas.append(b)

        # Dois placares, e eles não medem a mesma coisa. O de cima conta
        # JANELAS (a janela acertou se o número saiu em algum giro dela); o de
        # baixo conta NÚMERO A NÚMERO, um por giro. Encolher os dois numa linha
        # só, como eu tinha feito, escondeu justamente o segundo.
        self.placar = ctk.CTkLabel(esq, text="janelas: —", font=("Arial", 14),
                                   text_color=TEXTO)
        self.placar.pack(anchor="w", pady=(10, 2))
        self.placar_num = ctk.CTkLabel(esq, text="NÚMEROS   acertos 0 | erros 0",
                                       font=("Arial", 14, "bold"),
                                       text_color=AMARELO)
        self.placar_num.pack(anchor="w", pady=(0, 2))
        self.contadores = ctk.CTkLabel(esq, text="", font=("Arial", 11),
                                       text_color=FRACO)
        self.contadores.pack(anchor="w")

        ctk.CTkLabel(esq, text="últimos giros", font=("Arial", 11, "bold"),
                     text_color=FRACO).pack(anchor="w", pady=(12, 4))
        self.hist = ctk.CTkFrame(esq, fg_color="transparent")
        self.hist.pack(fill="x")

        ctk.CTkLabel(esq, text="o que as IAs disseram nesta volta",
                     font=("Arial", 11, "bold"), text_color=FRACO
                     ).pack(anchor="w", pady=(14, 4))
        self.feed = ctk.CTkTextbox(esq, height=170, fg_color=CARTAO,
                                   font=("Consolas", 11))
        self.feed.pack(fill="both", expand=True)

        ctk.CTkLabel(dir_, text="ACADEMIA — ao vivo",
                     font=("Arial", 12, "bold"), text_color=FRACO
                     ).pack(anchor="w", padx=12, pady=(12, 6))
        self.academia = ctk.CTkTextbox(dir_, fg_color="#0b1220",
                                       font=("Consolas", 10))
        self.academia.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # --------------------------------------------------------------- estado
    def _carregar(self):
        """Retoma placar e janela aberta de onde a mesa parou."""
        try:
            if self.arquivo.is_file():
                st = json.loads(self.arquivo.read_text(encoding="utf-8"))
                self.ok = int(st.get("ok") or 0)
                self.err = int(st.get("err") or 0)
                self.ok_num = int(st.get("ok_num") or 0)
                self.err_num = int(st.get("err_num") or 0)
                self.vistos = set(st.get("vistos") or [])
                self.ultima_janela = int(st.get("last_janela_size") or 0)
                self.ultimas_escolhas = list(st.get("last_escolhas") or [])
                self.soma_p = float(st.get("soma_p_esperado") or 0.0)
                if st.get("escolhas") and int(st.get("restantes") or 0) > 0:
                    self.escolhas = list(st["escolhas"])
                    self.restantes = int(st["restantes"])
                    self.janela_hit = bool(st.get("janela_hit"))
        except (OSError, ValueError, TypeError) as e:
            registrar(f"{self.jogo} estado: {e}")
        try:
            from fluxo_captura import carregar_ciclo_ativo
            cyc = carregar_ciclo_ativo(self.jogo)
            if cyc and cyc.get("escolhas") and int(cyc.get("restantes") or 0) > 0:
                self.escolhas = list(cyc["escolhas"])
                self.restantes = int(cyc["restantes"])
                self.janela_hit = bool(cyc.get("janela_hit"))
                registrar(f"{self.jogo} CICLO_RESTAURADO {self.escolhas} "
                          f"rest={self.restantes}")
        except Exception as e:
            registrar(f"{self.jogo} ciclo: {e}")

    def _salvar(self):
        try:
            PASTA.mkdir(parents=True, exist_ok=True)
            dados = {"ok": self.ok, "err": self.err,
                     "ok_num": self.ok_num, "err_num": self.err_num,
                     "vistos": list(self.vistos)[-200:],
                     "escolhas": list(self.escolhas),
                     "restantes": int(self.restantes),
                     "janela_hit": bool(self.janela_hit),
                     "last_janela_size": int(self.ultima_janela),
                     "last_escolhas": list(self.ultimas_escolhas),
                     "soma_p_esperado": float(self.soma_p)}
            tmp = str(self.arquivo) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False)
            os.replace(tmp, str(self.arquivo))
        except OSError as e:
            registrar(f"{self.jogo} salvar: {e}")

    # ------------------------------------------------------------ conferência
    def validar(self, r) -> None:
        """Confere o giro que acabou de sair contra a janela aberta.

        É daqui que sai o `last_result` mandado ao cérebro. Sem ele o motor
        nunca fica sabendo se acertou, e a taxa de acerto não anda — por isso
        esta parte não é enfeite de tela, é a realimentação do aprendizado.
        """
        n = r.get("n")
        ts = r.get("settled")
        if ts:
            chave = str(ts)
        else:
            # Sem horário, dois giros iguais colidiriam e o segundo sumiria:
            # a janela deixaria de andar. O contador dá chave própria a cada um.
            self.seq_giro += 1
            chave = f"{n}#s{self.seq_giro}"
        if chave in self.vistos:
            return
        self.vistos.add(chave)
        if not self.escolhas:
            self._salvar()
            return

        self.restantes -= 1
        hit = n in self.escolhas
        if hit:
            self.ok_num += 1
        else:
            self.err_num += 1
        registrar(f"{self.jogo} {'HIT' if hit else 'MISS'} {n} "
                  f"restam={self.restantes}")

        if self.restantes <= 0:
            fechou_bem = bool(self.janela_hit or hit)
            if fechou_bem:
                self.ok += 1
            else:
                self.err += 1
            try:
                from metricas_honestas import p_esperado_para
                self.soma_p += p_esperado_para(
                    self.ultimas_escolhas or self.escolhas,
                    int(self.ultima_janela or 4),
                    is_ct=(self.jogo == "crazy_time"))
            except Exception:
                pass
            self.ultimo_resultado = {"saiu": n, "acertou": fechou_bem,
                                     "settled": ts, "window_done": True}
            registrar(f"{self.jogo} JANELA {'OK' if fechou_bem else 'ERRO'} "
                      f"ok={self.ok} err={self.err}")
            self.escolhas = []
            self.janela_hit = False
        else:
            if hit:
                self.janela_hit = True
            self.ultimo_resultado = {"saiu": n, "acertou": hit,
                                     "settled": ts, "window_done": False}
        self._salvar()

    # ---------------------------------------------------------------- ciclo
    def rodar(self):
        if not self.vivo:
            return
        if not self.ocupado:
            threading.Thread(target=self._trabalhar, daemon=True).start()
        self.after(PERIODO_S * 1000, self.rodar)

    def _trabalhar(self):
        self.ocupado = True
        try:
            from fluxo_captura import (capturar, limpar_ciclo_ativo,
                                       marcar_snapshot_processado,
                                       salvar_ciclo_ativo)
            cap = capturar(self.jogo, page_size=50, max_pages=2)
            rows = cap.get("rows") or []
            if not rows:
                self._estado(f"sem dados: {str(cap.get('err') or '')[:34]}",
                             VERMELHO)
                return
            offline = bool(cap.get("offline"))
            mudou = bool(cap.get("novo_head"))
            if offline:
                self._estado("API instável — histórico salvo", AMARELO)
            else:
                self._estado("operacional", VERDE)
            if not mudou:
                # Mesmo giro de antes: só redesenha. Reenviar ao cérebro
                # contaria o mesmo evento duas vezes e sujaria o placar.
                self.after(0, lambda r=rows: self._desenhar_hist(r))
                return

            self.validar(rows[0])
            if self.escolhas and self.restantes > 0:
                salvar_ciclo_ativo(self.jogo, self.escolhas, self.restantes,
                                   self.janela_hit, self.ok, self.err)
            else:
                limpar_ciclo_ativo(self.jogo)

            self.entrada.put({"nums": [r.get("n") for r in rows],
                              "settled": [r.get("settled") for r in rows],
                              "mults": cap.get("mults") or [],
                              "ok": self.ok, "err": self.err,
                              "last_result": self.ultimo_resultado,
                              "active_selection": list(self.escolhas),
                              "head_id": cap.get("head_id")})
            if self.primeira:
                self._estado("preparando o cérebro (primeira volta)", ROXO)
            try:
                sug = self.saida.get(
                    timeout=ESPERA_1A_S if self.primeira else ESPERA_S)
            except _queue.Empty:
                # Não apaga o resultado pendente: a próxima volta reenvia,
                # senão o cérebro perde o retorno daquele giro para sempre.
                self._estado("cérebro sem resposta", AMARELO)
                return
            if self.primeira:
                self.primeira = False
                self._estado("API instável — histórico salvo" if offline
                             else "operacional", AMARELO if offline else VERDE)
            self.ultimo_resultado = None
            if cap.get("head_id"):
                try:
                    marcar_snapshot_processado(self.jogo, cap["head_id"])
                except Exception:
                    pass
            self.after(0, lambda s=sug, r=rows: self._aplicar(s, r))
        except Exception as e:
            registrar(f"{self.jogo}: {type(e).__name__}: {e}")
            self._estado(f"erro: {type(e).__name__}", VERMELHO)
            self.aviso_geral(self.jogo, f"erro: {type(e).__name__}")
        finally:
            self.ocupado = False

    # ------------------------------------------------------------- desenho
    def _estado(self, texto, cor):
        self.ultimo_estado = texto
        self.after(0, lambda: self.st.configure(text=texto, text_color=cor))

    def _desenhar_hist(self, rows):
        for w in self.hist.winfo_children():
            w.destroy()
        for r in rows[:16]:
            v = r.get("n")
            ctk.CTkLabel(self.hist, text=str(v), width=34, height=30,
                         fg_color=cor_do_numero(v), corner_radius=6,
                         font=("Arial", 12, "bold")).pack(side="left", padx=2)

    def _aplicar(self, sug, rows):
        modo = sug.get("modo") or ""
        pad = sug.get("pad5") or []
        if pad and not (self.escolhas and self.restantes > 0):
            self.escolhas = list(pad)[:7]
            self.restantes = int(sug.get("janela") or 3)
            self.ultima_janela = self.restantes
            self.ultimas_escolhas = list(self.escolhas)
            self.janela_hit = False
            self._salvar()
            registrar(f"{self.jogo} NOVA_JANELA {self.escolhas} {modo}")
            try:
                from notificador import notificar_sinal
                tx = sug.get("taxa_acerto")
                ac = sug.get("acaso_k")
                extra = ""
                if tx is not None:
                    extra = f"acerto {tx:.0%}"
                    if ac:
                        extra += f" vs acaso {ac:.0%} ({tx/ac:.2f}x)"
                notificar_sinal(self.jogo, self.escolhas, modo=modo,
                                janela=self.restantes, extra=extra,
                                log_fn=registrar)
            except Exception as e:
                registrar(f"{self.jogo} notificacao: {e}")
        elif not pad and not self.escolhas:
            self.escolhas = []

        for i, b in enumerate(self.caixas):
            v = self.escolhas[i] if i < len(self.escolhas) else None
            b.configure(text=str(v) if v is not None else "—",
                        fg_color=cor_do_numero(v) if v is not None else "#334155")
        if self.escolhas:
            self.faixa.configure(text=f"SINAL — janela de {self.restantes} giros",
                                 text_color=VERDE)
        else:
            self.faixa.configure(text="AGUARDANDO — evidência insuficiente",
                                 text_color=VERMELHO)
        self.placar.configure(text=self._texto_placar(sug))
        self.placar_num.configure(text=self._texto_numeros())
        c = sug.get("contadores") or {}
        self.contadores.configure(
            text=f"histórico {c.get('historico_bruto', 0)} | "
                 f"avaliadas {c.get('janelas_avaliadas', 0)} | "
                 f"pendentes {c.get('janelas_pendentes', 0)}")
        self._desenhar_hist(rows)
        self.feed.delete("1.0", "end")
        self.feed.insert("1.0", "\n".join(sug.get("msgs") or []))
        self._academia()

    def _academia(self):
        """O que os agentes desta mesa fizeram nas últimas voltas."""
        def tarefa():
            try:
                from academia_agentes import feed_tail
                linhas = [linha_do_feed(e) for e in feed_tail(self.jogo, 60)]
                texto = "\n".join(reversed(linhas)) or "(sem registro ainda)"
            except Exception as e:
                texto = f"{type(e).__name__}: {e}"
            self.after(0, lambda: (self.academia.delete("1.0", "end"),
                                   self.academia.insert("1.0", texto)))

        threading.Thread(target=tarefa, daemon=True).start()

    def _texto_numeros(self) -> str:
        """Um giro, um voto: o número que saiu estava entre os sugeridos?

        Mede coisa diferente do placar de janelas, e por isso vale ver os dois:
        uma janela de 4 giros pode fechar como acerto com 1 acerto e 3 erros.
        """
        a, e = self.ok_num, self.err_num
        tot = a + e
        txt = f"NÚMEROS   acertos {a} | erros {e}"
        if tot:
            txt += f"   taxa {a / tot:.0%}"
        return txt

    def _texto_placar(self, sug) -> str:
        """Acerto medido contra o acaso da MESMA aposta, não contra 1/37."""
        if self.ok + self.err == 0:
            # Sem janela fechada, o texto de sempre virava
            # "Janelas 0|0 acaso_última≈0% (cobertura ≠ edge)", que não diz
            # nada a quem está olhando e parece defeito.
            return "JANELAS   nenhuma fechada ainda"
        mem = sug.get("mem_stats") or {}
        soma = mem.get("soma_p_esperado")
        try:
            from metricas_honestas import texto_placar_acumulado
            return texto_placar_acumulado(
                self.ok, self.err,
                float(soma if soma is not None else self.soma_p),
                alvos_ultima=self.ultimas_escolhas or self.escolhas,
                janela_ultima=int(self.ultima_janela or 4),
                is_ct=(self.jogo == "crazy_time"),
                exp_acertos=int(mem.get("acertos_aval") or 0),
                exp_erros=int(mem.get("erros_aval") or 0))
        except Exception:
            return f"janelas {self.ok} certas | {self.err} erradas"

    def resumo(self) -> dict:
        return {"rotulo": self.rotulo, "estado": self.ultimo_estado,
                "escolhas": list(self.escolhas), "restantes": self.restantes,
                "ok": self.ok, "err": self.err,
                "ok_num": self.ok_num, "err_num": self.err_num}

    def encerrar(self):
        self.vivo = False
        try:
            self.entrada.put(None)
            self.processo.join(timeout=2)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════ o laboratório
class Laboratorio(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=FUNDO)
        self.abas = ctk.CTkTabview(self, fg_color=FUNDO)
        self.abas.pack(fill="both", expand=True, padx=8, pady=8)
        self.abas.add("Painel")
        self.paineis = {}
        for i, (jogo, rotulo) in enumerate(JOGOS):
            self.abas.add(rotulo)
            p = PainelMesa(self.abas.tab(rotulo), jogo, rotulo, self._aviso,
                           ordem=i)
            p.pack(fill="both", expand=True)
            self.paineis[jogo] = p
        for extra in ("IAs", "Conversa", "Progresso", "Fontes", "Avisos"):
            self.abas.add(extra)

        self._painel()
        self._ias()
        self._conversa()
        self._progresso()
        self._fontes()
        self._avisos()
        self._tick()

    def _aviso(self, jogo, texto):
        registrar(f"AVISO {jogo}: {texto}")

    # ---------------------------------------------------------------- painel
    def _painel(self):
        t = self.abas.tab("Painel")
        ctk.CTkLabel(t, text="As quatro mesas agora",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(t, text="Cada mesa roda no seu próprio processo. Uma que "
                             "falhe aparece com aviso aqui e não derruba as "
                             "outras.",
                     font=("Arial", 12), text_color=FRACO
                     ).pack(anchor="w", padx=18, pady=(0, 12))
        grade = ctk.CTkFrame(t, fg_color="transparent")
        grade.pack(fill="both", expand=True, padx=14)
        self.cartoes = {}
        for i, (jogo, rotulo) in enumerate(JOGOS):
            c = ctk.CTkFrame(grade, fg_color=CARTAO, border_width=1,
                             border_color=BORDA, corner_radius=12)
            c.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="nsew")
            ctk.CTkLabel(c, text=rotulo, font=("Arial", 17, "bold"),
                         text_color=AZUL).pack(anchor="w", padx=14, pady=(12, 0))
            est = ctk.CTkLabel(c, text="iniciando…", font=("Arial", 11),
                               text_color=ROXO)
            est.pack(anchor="w", padx=14)
            faixa = ctk.CTkLabel(c, text="AGUARDANDO",
                                 font=("Arial", 14, "bold"),
                                 text_color=VERMELHO)
            faixa.pack(anchor="w", padx=14, pady=(8, 4))
            nums = ctk.CTkLabel(c, text="—", font=("Consolas", 20, "bold"),
                                text_color=TEXTO)
            nums.pack(anchor="w", padx=14)
            plac = ctk.CTkLabel(c, text="", font=("Arial", 12),
                                text_color=FRACO)
            plac.pack(anchor="w", padx=14, pady=(6, 0))
            pnum = ctk.CTkLabel(c, text="", font=("Arial", 12, "bold"),
                                text_color=AMARELO)
            pnum.pack(anchor="w", padx=14, pady=(0, 14))
            self.cartoes[jogo] = {"estado": est, "faixa": faixa, "nums": nums,
                                  "placar": plac, "placar_num": pnum}
        for col in (0, 1):
            grade.grid_columnconfigure(col, weight=1)
        for lin in (0, 1):
            grade.grid_rowconfigure(lin, weight=1)

    def _tick(self):
        try:
            for jogo, p in self.paineis.items():
                r = p.resumo()
                c = self.cartoes[jogo]
                c["estado"].configure(text=r["estado"])
                if r["escolhas"]:
                    c["faixa"].configure(
                        text=f"SINAL — janela de {r['restantes']}",
                        text_color=VERDE)
                    c["nums"].configure(
                        text="  ".join(str(x) for x in r["escolhas"]))
                else:
                    c["faixa"].configure(text="AGUARDANDO",
                                         text_color=VERMELHO)
                    c["nums"].configure(text="—")
                tot = r["ok"] + r["err"]
                taxa = (f"  ({r['ok'] / tot:.0%})" if tot else "")
                c["placar"].configure(
                    text=f"janelas {r['ok']} certas · {r['err']} erradas{taxa}")
                totn = r["ok_num"] + r["err_num"]
                taxan = (f"  taxa {r['ok_num'] / totn:.0%}" if totn else "")
                c["placar_num"].configure(
                    text=f"números {r['ok_num']} · {r['err_num']}{taxan}")
        except Exception:
            pass
        self.after(3000, self._tick)

    # ------------------------------------------------------------------- IAs
    def _ias(self):
        t = self.abas.tab("IAs")
        topo = ctk.CTkFrame(t, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(14, 6))
        ctk.CTkLabel(topo, text="Os agentes da academia",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(side="left")
        self.ia_jogo = ctk.StringVar(value=JOGOS[0][0])
        ctk.CTkOptionMenu(topo, values=[j for j, _ in JOGOS],
                          variable=self.ia_jogo, width=150,
                          command=lambda _=None: self._ver_ias()
                          ).pack(side="left", padx=14)
        ctk.CTkButton(topo, text="Atualizar", width=110,
                      command=self._ver_ias).pack(side="left")
        self.ia_box = ctk.CTkTextbox(t, fg_color=CARTAO,
                                     font=("Consolas", 11))
        self.ia_box.pack(fill="both", expand=True, padx=16, pady=(6, 16))
        self._ver_ias()

    def _ver_ias(self):
        jogo = self.ia_jogo.get()
        self.ia_box.delete("1.0", "end")
        self.ia_box.insert("1.0", "consultando a academia…")

        def tarefa():
            try:
                from academia_agentes import snapshot_somente_leitura
                snap = snapshot_somente_leitura(jogo)
                ags = snap.get("agentes") or []
                L = [f"{len(ags)} agentes em {jogo}", ""]
                L.append(f"{'id':<5}{'nome':<26}{'tipo':<14}"
                         f"{'estado':<10}{'amostra':>8}  o que achou")
                L.append("─" * 116)
                for a in ags:
                    L.append(f"{str(a.get('id'))[:4]:<5}"
                             f"{str(a.get('nome'))[:25]:<26}"
                             f"{str(a.get('tipo'))[:13]:<14}"
                             f"{str(a.get('estado'))[:9]:<10}"
                             f"{a.get('amostra', 0):>8}  "
                             f"{str(a.get('ultima_descoberta') or '—')[:48]}")
                trib = snap.get("tribunal")
                if trib:
                    L += ["", "TRIBUNAL", str(trib)[:900]]
                crit = snap.get("critico")
                if crit:
                    L += ["", "CRÍTICO", str(crit)[:900]]
                texto = "\n".join(L)
            except Exception as e:
                texto = f"não foi possível ler a academia: {type(e).__name__}: {e}"
            self.after(0, lambda: (self.ia_box.delete("1.0", "end"),
                                   self.ia_box.insert("1.0", texto)))

        threading.Thread(target=tarefa, daemon=True).start()

    # -------------------------------------------------------------- conversa
    def _conversa(self):
        t = self.abas.tab("Conversa")
        ctk.CTkLabel(t, text="O que as IAs estão fazendo agora",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(anchor="w", padx=18, pady=(14, 2))
        ctk.CTkLabel(t, text="As quatro mesas juntas, do mais recente para o "
                             "mais antigo. Atualiza sozinho a cada 5 segundos.",
                     font=("Arial", 12), text_color=FRACO
                     ).pack(anchor="w", padx=18, pady=(0, 8))
        self.conversa_box = ctk.CTkTextbox(t, fg_color=CARTAO,
                                           font=("Consolas", 11))
        self.conversa_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._tick_conversa()

    def _tick_conversa(self):
        def tarefa():
            try:
                from academia_agentes import feed_tail
                tudo = []
                for jogo, rotulo in JOGOS:
                    for e in feed_tail(jogo, 25):
                        tudo.append((e.get("horario") or "", rotulo, e))
                tudo.sort(key=lambda x: x[0], reverse=True)
                texto = (juntar_repetidas(tudo[:400])
                         or "(a academia ainda não registrou nada)")
            except Exception as e:
                texto = f"{type(e).__name__}: {e}"
            self.after(0, lambda: (self.conversa_box.delete("1.0", "end"),
                                   self.conversa_box.insert("1.0", texto)))

        threading.Thread(target=tarefa, daemon=True).start()
        self.after(5000, self._tick_conversa)

    # ------------------------------------------------------------- progresso
    def _progresso(self):
        t = self.abas.tab("Progresso")
        topo = ctk.CTkFrame(t, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(14, 8))
        ctk.CTkLabel(topo, text="Quanto já foi juntado",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(side="left")
        bt = ctk.CTkButton(topo, text="Atualizar", width=130)
        bt.pack(side="left", padx=16)
        cx = ctk.CTkTextbox(t, fg_color=CARTAO, font=("Consolas", 11))
        cx.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        def atualizar():
            cx.delete("1.0", "end")
            cx.insert("1.0", "montando…")

            def tarefa():
                # Em processo separado, e não com redirect_stdout: aquele troca
                # a saída do processo INTEIRO, não só desta thread. Rodando ao
                # fundo, ele engolia o que qualquer outra parte imprimisse
                # enquanto o relatório era montado.
                try:
                    import subprocess
                    r = subprocess.run([sys.executable, str(RAIZ / "PROGRESSO.py")],
                                       cwd=str(RAIZ), capture_output=True,
                                       text=True, timeout=180,
                                       encoding="utf-8", errors="replace")
                    texto = r.stdout or r.stderr or "(sem saída)"
                except Exception as e:
                    texto = f"não foi possível montar: {type(e).__name__}: {e}"
                self.after(0, lambda: (cx.delete("1.0", "end"),
                                       cx.insert("1.0", texto)))

            threading.Thread(target=tarefa, daemon=True).start()

        bt.configure(command=atualizar)
        atualizar()

    # ---------------------------------------------------------------- fontes
    def _fontes(self):
        t = self.abas.tab("Fontes")
        topo = ctk.CTkFrame(t, fg_color="transparent")
        topo.pack(fill="x", padx=18, pady=(14, 8))
        ctk.CTkLabel(topo, text="O que cada site está devolvendo",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(side="left")
        # O botão fica ao lado do título, não embaixo da caixa: com a caixa
        # ocupando a altura toda, um botão no rodapé some na borda da tela e a
        # aba parece um retângulo preto sem nada para fazer.
        bt = ctk.CTkButton(topo, text="Consultar os sites agora", width=210)
        bt.pack(side="left", padx=16)
        cx = ctk.CTkTextbox(t, fg_color=CARTAO, font=("Consolas", 11))
        cx.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        cx.insert("1.0", "Clique em “Consultar os sites agora”.\n\n"
                         "Cada mesa é consultada em sequência e a resposta de "
                         "cada site aparece aqui — o que veio, quantos giros, "
                         "e o que não respondeu.\nLeva alguns segundos.")

        def olhar():
            bt.configure(state="disabled", text="consultando…")
            cx.delete("1.0", "end")
            cx.insert("1.0", "consultando os sites…")

            def tarefa():
                linhas = []
                try:
                    from coletor_sites import coletar, resumo
                    for jogo, rotulo in JOGOS:
                        try:
                            linhas += [resumo(coletar(jogo)), ""]
                        except Exception as e:
                            # Um site fora do ar não pode esconder os outros
                            # três: cada mesa responde por si.
                            linhas += [f"{rotulo}: {type(e).__name__}: {e}", ""]
                except Exception as e:
                    linhas.append(f"{type(e).__name__}: {e}")
                texto = "\n".join(linhas) or "(nenhum site respondeu)"
                self.after(0, lambda: (cx.delete("1.0", "end"),
                                       cx.insert("1.0", texto),
                                       bt.configure(
                                           state="normal",
                                           text="Consultar os sites agora")))

            threading.Thread(target=tarefa, daemon=True).start()

        bt.configure(command=olhar)

    # ---------------------------------------------------------------- avisos
    def _avisos(self):
        t = self.abas.tab("Avisos")
        ctk.CTkLabel(t, text="Notificação no celular",
                     font=("Arial", 22, "bold"), text_color=TEXTO
                     ).pack(anchor="w", padx=18, pady=(14, 8))
        self.av_box = ctk.CTkLabel(t, text="", justify="left", wraplength=880,
                                   font=("Consolas", 13), text_color=TEXTO)
        self.av_box.pack(anchor="w", padx=18, pady=6)
        linha = ctk.CTkFrame(t, fg_color="transparent")
        linha.pack(anchor="w", padx=16, pady=10)
        ctk.CTkButton(linha, text="Ver configuração", width=170,
                      command=self._ver_avisos).pack(side="left", padx=(0, 10))
        ctk.CTkButton(linha, text="Enviar teste agora", width=170,
                      command=self._testar_aviso).pack(side="left", padx=(0, 10))
        ctk.CTkButton(linha, text="Trocar canal", width=150, fg_color="#1f2937",
                      hover_color="#334155",
                      command=self._trocar_canal).pack(side="left")
        self._ver_avisos()

    def _trocar_canal(self):
        try:
            self.master.reconfigurar()
        except Exception as e:
            self.av_box.configure(text=f"{type(e).__name__}: {e}")

    def _ver_avisos(self):
        try:
            import notificador
            c = notificador._cfg()
            canal = (c.get("canal") or "nenhum").lower()
            L = [f"canal: {canal}"]
            if canal == "ntfy":
                # O tópico é o que mais dá problema: se o que está aqui não for
                # igualzinho ao assinado no app, nada chega e nada avisa.
                L.append(f"tópico: {c.get('topico') or '(vazio)'}")
                L.append("o app do celular precisa estar assinando exatamente "
                         "esse nome")
            elif canal == "telegram":
                L.append(f"chat_id: {c.get('chat_id') or '(vazio)'}")
            elif canal == "whatsapp":
                L.append(f"telefone: {c.get('telefone') or '(vazio)'}")
            L.append("pronto para enviar: "
                     + ("sim" if notificador.ativo() else "não"))
            self.av_box.configure(text="\n".join(L))
        except Exception as e:
            self.av_box.configure(text=f"{type(e).__name__}: {e}")

    def _testar_aviso(self):
        def tarefa():
            try:
                import notificador
                txt = notificador.testar()
            except Exception as e:
                txt = f"{type(e).__name__}: {e}"
            self.after(0, lambda: self.av_box.configure(text=txt))

        threading.Thread(target=tarefa, daemon=True).start()

    def encerrar(self):
        for p in self.paineis.values():
            p.encerrar()


# ══════════════════════════════════════════════════════════════════ janela
class Central(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Laboratório — as quatro mesas ao vivo")
        self.geometry("1280x860")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=FUNDO)
        self.lab = None
        self.config_tela = None
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        if precisa_configurar():
            self._abrir_config()
        else:
            self._abrir_lab()

    def _abrir_config(self):
        if self.lab is not None:
            return                       # laboratório já rodando: nunca derruba
        self.config_tela = TelaConfig(self, self._abrir_lab)
        self.config_tela.pack(fill="both", expand=True)

    def _abrir_lab(self):
        if self.config_tela is not None:
            self.config_tela.destroy()
            self.config_tela = None
        if self.lab is None:
            self.lab = Laboratorio(self)
            self.lab.pack(fill="both", expand=True)

    def reconfigurar(self):
        """Trocar canal com o laboratório aberto.

        Os cérebros já estão rodando: derrubar a tela para reconfigurar mataria
        as quatro mesas. Por isso a troca acontece numa janela à parte.
        """
        topo = ctk.CTkToplevel(self)
        topo.title("Trocar canal de aviso")
        topo.geometry("900x620")
        topo.configure(fg_color=FUNDO)

        def fechar():
            topo.destroy()
            if self.lab is not None:
                self.lab._ver_avisos()

        TelaConfig(topo, fechar).pack(fill="both", expand=True)

    def _fechar(self):
        if self.lab is not None:
            self.lab.encerrar()
        self.destroy()


def main():
    mp.freeze_support()
    try:
        Central().mainloop()
    except Exception:
        (RAIZ / "crash_central.txt").write_text(traceback.format_exc(),
                                                encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
