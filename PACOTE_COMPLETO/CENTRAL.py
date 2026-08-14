# -*- coding: utf-8 -*-
"""
CENTRAL — uma janela só, com abas, para tudo.

    CENTRAL.bat        (ou: python CENTRAL.py)

Antes eram oito executáveis e oito janelas: para olhar o Immersive era preciso
caçar qual delas era na barra de tarefas. Aqui as quatro mesas rodam ao mesmo
tempo dentro de uma janela, e a aba escolhe o que aparece.

O QUE MUDA ALÉM DA COMODIDADE
-----------------------------
Com as quatro no mesmo processo, a aba "Todas" mostra o estado das quatro lado
a lado — dá para ver de relance qual está em SOMBRA, qual abriu gatilho e qual
está com a API instável, sem abrir nada.

UMA MESA QUE TRAVA NÃO DERRUBA AS OUTRAS
----------------------------------------
Cada mesa tem seu próprio processo de cérebro e sua própria thread de captura,
com o erro isolado. Quem falha aparece com aviso na aba dela e as demais
seguem. Este era o risco real de juntar tudo, e é por isso que a captura roda
em thread e o cérebro em processo separado — nunca dentro da interface.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import queue as _queue
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


def registrar(msg: str) -> None:
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%d/%m %H:%M:%S} | {msg}\n")
    except OSError:
        pass


def cor_do_numero(v) -> str:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return "#334155"
    if n == 0:
        return "#16a34a"
    return "#dc2626" if n in VERMELHOS else "#1f2937"


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

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(topo, text=rotulo,
                     font=("Arial", 18, "bold")).pack(side="left")
        self.st = ctk.CTkLabel(topo, text="iniciando…", text_color="#a78bfa")
        self.st.pack(side="left", padx=12)

        self.faixa = ctk.CTkLabel(
            self, text="AGUARDANDO", font=("Arial", 15, "bold"),
            text_color="#ef4444")
        self.faixa.pack(anchor="w", padx=14, pady=(2, 6))

        cx = ctk.CTkFrame(self, border_width=2, border_color="#22c55e")
        cx.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(cx, text="SUGESTÃO", font=("Arial", 11),
                     text_color="#94a3b8").pack(anchor="w", padx=8, pady=(6, 0))
        linha = ctk.CTkFrame(cx, fg_color="transparent")
        linha.pack(padx=8, pady=8)
        self.caixas = []
        for _ in range(7):
            b = ctk.CTkLabel(linha, text="—", width=52, height=44,
                             fg_color="#334155", corner_radius=8,
                             font=("Arial", 17, "bold"))
            b.pack(side="left", padx=3)
            self.caixas.append(b)

        self.placar = ctk.CTkLabel(self, text="placar: —", font=("Arial", 13))
        self.placar.pack(anchor="w", padx=14, pady=2)
        self.contadores = ctk.CTkLabel(self, text="", font=("Arial", 11),
                                       text_color="#94a3b8")
        self.contadores.pack(anchor="w", padx=14)
        self.hist = ctk.CTkFrame(self, fg_color="transparent")
        self.hist.pack(fill="x", padx=12, pady=6)
        self.feed = ctk.CTkTextbox(self, height=200)
        self.feed.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.entrada, self.saida = mp.Queue(), mp.Queue()
        self.processo = mp.Process(target=process_cerebro,
                                   args=(self.entrada, self.saida, jogo),
                                   daemon=True)
        self.processo.start()
        self.after(1200 + ordem * ATRASO_ENTRE_MESAS_S * 1000, self.rodar)

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
                             "#ef4444")
                return
            offline = bool(cap.get("offline"))
            mudou = bool(cap.get("novo_head"))
            if offline:
                self._estado("API instável — histórico salvo", "#eab308")
            else:
                self._estado("operacional", "#22c55e")
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

            pendente = self.ultimo_resultado
            self.entrada.put({"nums": [r.get("n") for r in rows],
                              "settled": [r.get("settled") for r in rows],
                              "mults": cap.get("mults") or [],
                              "ok": self.ok, "err": self.err,
                              "last_result": pendente,
                              "active_selection": list(self.escolhas),
                              "head_id": cap.get("head_id")})
            if self.primeira:
                self._estado("preparando o cérebro (primeira volta)", "#a78bfa")
            try:
                sug = self.saida.get(
                    timeout=ESPERA_1A_S if self.primeira else ESPERA_S)
            except _queue.Empty:
                # Não apaga o resultado pendente: a próxima volta reenvia,
                # senão o cérebro perde o retorno daquele giro para sempre.
                self._estado("cérebro sem resposta", "#eab308")
                return
            if self.primeira:
                self.primeira = False
                self._estado("API instável — histórico salvo" if offline
                             else "operacional",
                             "#eab308" if offline else "#22c55e")
            self.ultimo_resultado = None
            if cap.get("head_id"):
                try:
                    marcar_snapshot_processado(self.jogo, cap["head_id"])
                except Exception:
                    pass
            self.after(0, lambda s=sug, r=rows: self._aplicar(s, r))
        except Exception as e:
            registrar(f"{self.jogo}: {type(e).__name__}: {e}")
            self._estado(f"erro: {type(e).__name__}", "#ef4444")
            self.aviso_geral(self.jogo, f"erro: {type(e).__name__}")
        finally:
            self.ocupado = False

    # ------------------------------------------------------------- interface
    def _estado(self, texto, cor):
        self.ultimo_estado = texto
        self.after(0, lambda: self.st.configure(text=texto, text_color=cor))

    def _desenhar_hist(self, rows):
        for w in self.hist.winfo_children():
            w.destroy()
        for r in rows[:14]:
            v = r.get("n")
            ctk.CTkLabel(self.hist, text=str(v), width=34, height=28,
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
            self.faixa.configure(text=f"SINAL — janela {self.restantes}",
                                 text_color="#22c55e")
        else:
            self.faixa.configure(text="AGUARDANDO — evidência insuficiente",
                                 text_color="#ef4444")
        self.placar.configure(text=self._texto_placar(sug))
        c = sug.get("contadores") or {}
        self.contadores.configure(
            text=f"giros {self.ok_num + self.err_num} "
                 f"({self.ok_num} nos alvos) | "
                 f"histórico {c.get('historico_bruto', 0)} | "
                 f"avaliadas {c.get('janelas_avaliadas', 0)} | "
                 f"pendentes {c.get('janelas_pendentes', 0)}")
        self._desenhar_hist(rows)
        self.feed.delete("1.0", "end")
        self.feed.insert("1.0", "\n".join(sug.get("msgs") or []))

    def _texto_placar(self, sug) -> str:
        """Acerto medido contra o acaso da MESMA aposta, não contra 1/37."""
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

    def resumo(self) -> str:
        if self.escolhas:
            n = "SINAL " + " ".join(str(x) for x in self.escolhas)
        else:
            n = "aguardando"
        return (f"{self.rotulo:<12} {self.ultimo_estado:<30} "
                f"{self.ok}✓/{self.err}✗  {n}")

    def encerrar(self):
        self.vivo = False
        try:
            self.entrada.put(None)
            self.processo.join(timeout=2)
        except Exception:
            pass


class Central(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Central — laboratório de mesas ao vivo")
        self.geometry("1080x760")
        ctk.set_appearance_mode("dark")

        self.abas = ctk.CTkTabview(self)
        self.abas.pack(fill="both", expand=True, padx=8, pady=8)
        self.abas.add("Todas")
        self.paineis = {}
        for i, (jogo, rotulo) in enumerate(JOGOS):
            self.abas.add(rotulo)
            p = PainelMesa(self.abas.tab(rotulo), jogo, rotulo, self._aviso,
                           ordem=i)
            p.pack(fill="both", expand=True)
            self.paineis[jogo] = p
        for extra in ("Progresso", "Avisos", "Fontes"):
            self.abas.add(extra)

        self._montar_todas()
        self._montar_progresso()
        self._montar_avisos()
        self._montar_fontes()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self._tick_resumo()

    def _aviso(self, jogo, texto):
        registrar(f"AVISO {jogo}: {texto}")

    def _montar_todas(self):
        t = self.abas.tab("Todas")
        ctk.CTkLabel(t, text="As quatro mesas agora",
                     font=("Arial", 17, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        self.resumo_box = ctk.CTkTextbox(t, height=220, font=("Consolas", 13))
        self.resumo_box.pack(fill="x", padx=12, pady=6)
        ctk.CTkLabel(t, text=("Cada mesa roda no seu próprio processo. Uma que "
                              "falhe aparece com aviso aqui e não derruba as outras."),
                     text_color="#94a3b8", wraplength=900,
                     justify="left").pack(anchor="w", padx=14, pady=8)

    def _montar_progresso(self):
        t = self.abas.tab("Progresso")
        cx = ctk.CTkTextbox(t, font=("Consolas", 12))
        cx.pack(fill="both", expand=True, padx=12, pady=12)

        def atualizar():
            cx.delete("1.0", "end")
            try:
                import io
                import contextlib
                import runpy
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    runpy.run_path(str(RAIZ / "PROGRESSO.py"), run_name="_")
                cx.insert("1.0", buf.getvalue())
            except Exception as e:
                cx.insert("1.0", f"não foi possível montar: {type(e).__name__}: {e}")

        ctk.CTkButton(t, text="Atualizar", command=atualizar).pack(pady=(0, 10))
        atualizar()

    def _montar_avisos(self):
        t = self.abas.tab("Avisos")
        ctk.CTkLabel(t, text="Notificação no celular",
                     font=("Arial", 17, "bold")).pack(anchor="w", padx=14, pady=(12, 4))
        est = ctk.CTkLabel(t, text="", justify="left", wraplength=900)
        est.pack(anchor="w", padx=14, pady=6)

        def ver():
            try:
                import notificador
                c = notificador._cfg()
                est.configure(
                    text=f"canal: {c.get('canal')}\n"
                         f"pronto para enviar: {'sim' if notificador.ativo() else 'não'}")
            except Exception as e:
                est.configure(text=f"{type(e).__name__}: {e}")

        def testar():
            try:
                import notificador
                est.configure(text=notificador.testar())
            except Exception as e:
                est.configure(text=f"{type(e).__name__}: {e}")

        ctk.CTkButton(t, text="Ver configuração", command=ver).pack(anchor="w", padx=14, pady=4)
        ctk.CTkButton(t, text="Enviar teste agora", command=testar).pack(anchor="w", padx=14, pady=4)
        ctk.CTkLabel(t, text=("Para configurar, rode CONFIGURAR_AVISOS.bat — ele "
                              "pergunta o canal, guia o passo a passo do WhatsApp "
                              "e envia um teste na hora."),
                     text_color="#94a3b8", wraplength=900,
                     justify="left").pack(anchor="w", padx=14, pady=10)
        ver()

    def _montar_fontes(self):
        t = self.abas.tab("Fontes")
        cx = ctk.CTkTextbox(t, font=("Consolas", 12))
        cx.pack(fill="both", expand=True, padx=12, pady=12)

        def olhar():
            cx.delete("1.0", "end")
            cx.insert("1.0", "consultando os sites…\n")

            def tarefa():
                linhas = []
                try:
                    from coletor_sites import coletar, resumo
                    for jogo, _ in JOGOS:
                        linhas.append(resumo(coletar(jogo)))
                        linhas.append("")
                except Exception as e:
                    linhas.append(f"{type(e).__name__}: {e}")
                texto = "\n".join(linhas)
                self.after(0, lambda: (cx.delete("1.0", "end"),
                                       cx.insert("1.0", texto)))

            threading.Thread(target=tarefa, daemon=True).start()

        ctk.CTkButton(t, text="Consultar os sites agora",
                      command=olhar).pack(pady=(0, 10))

    def _tick_resumo(self):
        try:
            linhas = [p.resumo() for p in self.paineis.values()]
            self.resumo_box.delete("1.0", "end")
            self.resumo_box.insert("1.0", "\n".join(linhas))
        except Exception:
            pass
        self.after(3000, self._tick_resumo)

    def _fechar(self):
        for p in self.paineis.values():
            p.encerrar()
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
