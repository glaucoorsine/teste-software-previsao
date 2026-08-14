# -*- coding: utf-8 -*-
"""CENTRAL DAS IAS — consulta agentes PERSISTENTES (SQLite). Não cria cópia isolada."""
import customtkinter as ctk
import threading, traceback
from academia_agentes import get_academia, feed_tail, snapshot_somente_leitura, PROTOCOLO
import academia_db as DB

class CentralIAs(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CENTRAL DAS IAS — Academia compartilhada")
        self.geometry("1280x860")
        ctk.set_appearance_mode("dark")
        self.jogo = ctk.StringVar(value="mega_fire")
        self.agente_sel = None
        self.running = True
        self._build()
        self.after(800, self.refresh_all)
        self.after(5000, self.auto_refresh)

    def _build(self):
        top = ctk.CTkFrame(self); top.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(top, text="CENTRAL DAS IAS", font=("Arial", 22, "bold"), text_color="#38bdf8").pack(side="left", padx=8)
        ctk.CTkLabel(top, text=f"Somente leitura — pesquisa pelo academia_servico | {PROTOCOLO}", text_color="#a3a3a3").pack(side="left", padx=8)
        for j, lab in [("mega_fire","Mega"),("lightning","Lightning"),("crazy_time","Crazy Time"),("immersive","Immersive")]:
            ctk.CTkRadioButton(top, text=lab, variable=self.jogo, value=j, command=self.refresh_all).pack(side="left", padx=6)
        ctk.CTkButton(top, text="Atualizar", width=90, command=self.refresh_all).pack(side="right", padx=4)
        ctk.CTkButton(top, text="Rodar tribunal", width=110, fg_color="#b45309",
                      command=self.cmd_tribunal).pack(side="right", padx=4)
        ctk.CTkButton(top, text="Reavaliar descartadas", width=150, fg_color="#7c3aed",
                      command=self.cmd_reavaliar).pack(side="right", padx=4)
        self.mon = ctk.CTkLabel(top, text="DB compartilhado", text_color="#eab308")
        self.mon.pack(side="right", padx=8)

        body = ctk.CTkFrame(self); body.pack(fill="both", expand=True, padx=10, pady=5)
        left = ctk.CTkScrollableFrame(body, width=720); left.pack(side="left", fill="both", expand=True, padx=(0,6))
        self.cards_host = left
        right = ctk.CTkFrame(body, width=480); right.pack(side="right", fill="both", expand=True)
        ctk.CTkLabel(right, text="Chat com agente persistente", font=("Arial", 14, "bold")).pack(anchor="w", padx=6, pady=4)
        self.chat_title = ctk.CTkLabel(right, text="Selecione um agente", text_color="#93c5fd")
        self.chat_title.pack(anchor="w", padx=6)
        self.chat_box = ctk.CTkTextbox(right, height=280); self.chat_box.pack(fill="both", expand=True, padx=6, pady=4)
        row = ctk.CTkFrame(right); row.pack(fill="x", padx=6, pady=4)
        self.entry = ctk.CTkEntry(row, placeholder_text="Pergunte ao estado real do agente…")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0,6))
        ctk.CTkButton(row, text="Enviar", width=80, command=self.enviar).pack(side="right")
        ctk.CTkLabel(right, text="Feed ao vivo (com jogo)", font=("Arial", 13, "bold")).pack(anchor="w", padx=6, pady=(8,2))
        self.feed_box = ctk.CTkTextbox(right, height=200); self.feed_box.pack(fill="both", expand=True, padx=6, pady=4)
        note = ctk.CTkLabel(
            self, text="4 tribunais isolados (Mega / Lightning / CT / Immersive). ≥30% (3/10) aprova · <30% descarta (reavaliável). Previsão 5–7.",
            text_color="#a3a3a3",
        )
        note.pack(pady=4)



    def _hist_do_jogo(self):
        jogo = self.jogo.get()
        try:
            from fluxo_captura import capturar
            cap = capturar(jogo, page_size=50, max_pages=2)
            rows = cap.get("rows") or []
            nums = [str(r.get("sec") if r.get("sec") is not None else r.get("n")) for r in rows]
            settled = [r.get("settled") for r in rows]
            return nums, settled, cap.get("err")
        except Exception as e:
            return [], [], str(e)

    def cmd_tribunal(self):
        jogo = self.jogo.get()
        self.chat_box.insert("end", "\n⏳ Tribunal isolado de %s — teorias recusadas/observação…\n" % jogo)
        def work():
            try:
                nums, settled, err = self._hist_do_jogo()
                if err and not nums:
                    msg = "sem histórico: %s" % err
                else:
                    ac = get_academia(jogo)
                    out = ac.tribunal_agora(nums, settled)
                    msg = (
                        "jogo=%s julgadas=%s aprovadas=%s reprovadas=%s em_revisao=%s | %s\n"
                        % (
                            jogo,
                            out.get("julgadas"),
                            len(out.get("aprovadas") or []),
                            len(out.get("reprovadas") or []),
                            len(out.get("em_revisao") or []),
                            out.get("regra"),
                        )
                    )
                    for m in (out.get("msgs") or [])[-8:]:
                        msg += str(m)[:120] + "\n"
            except Exception as e:
                msg = "erro: %s\n%s" % (e, traceback.format_exc()[:300])
            self.after(0, lambda: self._cmd_done(msg))
        threading.Thread(target=work, daemon=True).start()

    def cmd_reavaliar(self):
        jogo = self.jogo.get()
        self.chat_box.insert("end", "\n⏳ Reavaliando DESCARTADAS só de %s…\n" % jogo)
        def work():
            try:
                nums, settled, err = self._hist_do_jogo()
                if err and not nums:
                    msg = "sem histórico: %s" % err
                else:
                    ac = get_academia(jogo)
                    out = ac.reavaliar_descartadas_cmd(nums, settled)
                    msg = (
                        "jogo=%s candidatas_descartadas=%s aprovadas=%s reprovadas=%s em_revisao=%s | %s\n"
                        % (
                            jogo,
                            out.get("n_candidatas"),
                            len(out.get("aprovadas") or []),
                            len(out.get("reprovadas") or []),
                            len(out.get("em_revisao") or []),
                            out.get("regra"),
                        )
                    )
                    for m in (out.get("msgs") or [])[-10:]:
                        msg += str(m)[:120] + "\n"
            except Exception as e:
                msg = "erro: %s\n%s" % (e, traceback.format_exc()[:300])
            self.after(0, lambda: self._cmd_done(msg))
        threading.Thread(target=work, daemon=True).start()

    def _cmd_done(self, msg):
        self.chat_box.insert("end", msg + "\n")
        self.chat_box.see("end")
        self.refresh_all()

    def refresh_all(self):
        try:
            snap = snapshot_somente_leitura(self.jogo.get())
            self._render_cards(snap)
            self._render_feed()
            mon = snap.get("monitor") or {}
            try:
                import academia_db as _DB
                mon = _DB.get_monitor(self.jogo.get()) or mon
            except Exception:
                pass
            bib = snap.get("biblioteca") or {}
            self.mon.configure(
                text=f"validadas={bib.get('validadas')} teste={bib.get('em_teste')} rej={bib.get('rejeitadas')} | CPU {mon.get('cpu','—')}"
            )
        except Exception as e:
            self.chat_box.insert("end", f"\n[erro] {e}\n")

    def auto_refresh(self):
        if self.running:
            self.refresh_all()
            self.after(5000, self.auto_refresh)

    def _render_cards(self, snap):
        for w in self.cards_host.winfo_children():
            w.destroy()
        # META + CRÍTICO
        for special in (snap.get("meta") or {}, snap.get("critico") or {}):
            if not special:
                continue
            fr = ctk.CTkFrame(self.cards_host, border_width=1, border_color="#6366f1")
            fr.pack(fill="x", pady=4, padx=4)
            aid = special.get("id") or "?"
            ctk.CTkLabel(fr, text=aid, font=("Arial", 13, "bold"), text_color="#c4b5fd").pack(anchor="w", padx=6, pady=2)
            ctk.CTkLabel(fr, text=f"Estado: {special.get('estado')} | {special.get('ultima_descoberta') or special.get('tarefa')}", wraplength=680).pack(anchor="w", padx=6)
            ctk.CTkButton(fr, text="Conversar", width=100, command=lambda a=aid: self.sel_agente(a)).pack(anchor="e", padx=6, pady=4)

        # TRIBUNAL DE REVISÃO (7 IAs)
        tri = snap.get("tribunal") or {}
        jogo_atual = self.jogo.get()
        nomes = {"mega_fire": "Mega Fire", "lightning": "Lightning", "crazy_time": "Crazy Time", "immersive": "Immersive"}
        ctk.CTkLabel(
            self.cards_host,
            text=f"⚖ TRIBUNAL · {nomes.get(jogo_atual, jogo_atual)} — 7 IAs isoladas deste jogo",
            font=("Arial", 14, "bold"),
            text_color="#fbbf24",
        ).pack(anchor="w", padx=6, pady=(10, 2))
        ctk.CTkLabel(
            self.cards_host,
            text=f"regra: {tri.get('regra') or '3/10'} | julgamentos neste jogo: {tri.get('n_julgamentos', 0)} | arquivo: tribunal_{jogo_atual}.json",
            text_color="#a3a3a3",
        ).pack(anchor="w", padx=6, pady=(0, 4))
        for a in tri.get("agentes") or []:
            voto = (a.get("estado") or "aguardando").lower()
            if voto == "aprova":
                border, cor = "#16a34a", "#bbf7d0"
            elif voto == "reprova":
                border, cor = "#dc2626", "#fecaca"
            else:
                border, cor = "#ca8a04", "#fde68a"
            fr = ctk.CTkFrame(self.cards_host, border_width=2, border_color=border)
            fr.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(fr, text=a.get("nome") or a.get("id"), font=("Arial", 12, "bold"), text_color=cor).pack(anchor="w", padx=6, pady=2)
            ctk.CTkLabel(
                fr,
                text=f"Voto: {voto.upper()} | {a.get('papel')}\nMotivo: {a.get('ultima_descoberta')}\nAmostra: {a.get('amostra')} | modelo={a.get('modelo')}",
                justify="left", wraplength=680,
            ).pack(anchor="w", padx=6)
            ctk.CTkButton(fr, text="Conversar", width=100, command=lambda i=a.get("id"): self.sel_agente(i)).pack(anchor="e", padx=6, pady=3)
        # últimos vereditos
        for u in (tri.get("ultimos") or [])[-5:]:
            fr = ctk.CTkFrame(self.cards_host, border_width=1, border_color="#78716c")
            fr.pack(fill="x", pady=2, padx=8)
            ctk.CTkLabel(
                fr,
                text=f"[{u.get('ts')}] {u.get('veredito')} — {u.get('motivo')}",
                wraplength=660, text_color="#e7e5e4",
            ).pack(anchor="w", padx=6, pady=3)

        ctk.CTkLabel(self.cards_host, text="12 Pesquisadores (descoberta DSL)", text_color="#a3a3a3").pack(anchor="w", padx=6, pady=6)
        for a in snap.get("agentes") or []:
            fr = ctk.CTkFrame(self.cards_host, border_width=1, border_color="#334155")
            fr.pack(fill="x", pady=3, padx=4)
            ctk.CTkLabel(fr, text=a.get("nome") or a.get("id"), font=("Arial", 12, "bold")).pack(anchor="w", padx=6, pady=2)
            ctk.CTkLabel(
                fr,
                text=f"Conjunto: {a.get('conjunto')} | {a.get('estado')} | {a.get('tarefa')}\n"
                     f"Amostra: {a.get('amostra')} | Modelo: {a.get('modelo')} | {a.get('duracao_ms',0):.0f} ms\n"
                     f"Descoberta: {a.get('ultima_descoberta')} | conf={a.get('confianca',0):.3f}",
                justify="left", wraplength=680,
            ).pack(anchor="w", padx=6)
            ctk.CTkButton(fr, text="Conversar", width=100, command=lambda i=a.get("id"): self.sel_agente(i)).pack(anchor="e", padx=6, pady=3)

    def _render_feed(self):
        lines = feed_tail(self.jogo.get(), 50)
        self.feed_box.delete("1.0", "end")
        for L in lines:
            self.feed_box.insert(
                "end",
                f"[{L.get('horario')}] [{L.get('jogo')}] [{L.get('agente')}] [{L.get('etapa')}] "
                f"[n={L.get('amostra')}] [{L.get('acao')}] [{L.get('resultado')}] → {L.get('proximo')}\n"
            )
        self.feed_box.see("end")

    def sel_agente(self, aid):
        self.agente_sel = aid
        self.chat_title.configure(text=f"Conversa: {aid} @ {self.jogo.get()} (DB)")
        self.chat_box.insert("end", f"\n— Conectado ao estado persistente de {aid} —\n")

    def enviar(self):
        q = self.entry.get().strip()
        if not q or not self.agente_sel:
            return
        self.entry.delete(0, "end")
        self.chat_box.insert("end", f"\nVocê: {q}\n… consultando estado e LLM …\n")
        self.chat_box.see("end")
        jogo, aid = self.jogo.get(), self.agente_sel
        def work():
            try:
                ac = get_academia(jogo)
                base_txt = ac.chat(aid, q)
                explicacao = self._llm_explica(aid, q, base_txt)
            except Exception as e:
                explicacao = f"erro: {e}"
            self.after(0, lambda: self._chat_result(explicacao))
        threading.Thread(target=work, daemon=True).start()

    def _chat_result(self, texto):
        self.chat_box.insert("end", str(texto) + "\n")
        self.chat_box.see("end")

    def _llm_explica(self, agente_id, pergunta, estado_auditavel: str) -> str:
        try:
            import json
            from pathlib import Path
            cfg = {}
            cp = Path(__file__).resolve().parent / "llm_config.json"
            if cp.is_file():
                cfg = json.loads(cp.read_text(encoding="utf-8"))
            # tenta OpenAI-compatible se configurado
            api_key = cfg.get("api_key") or cfg.get("openai_api_key")
            prov = (cfg.get("provider") or "xai").lower()
            if prov in ("openai", "gpt"):
                base_url = cfg.get("openai_base_url") or "https://api.openai.com/v1"
                model = cfg.get("model") or "gpt-4o-mini"
            elif prov == "ollama":
                base_url = (cfg.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/") + "/v1"
                # prioriza model da UI/config se existir; fallback ollama_model
                model = cfg.get("model") or cfg.get("ollama_model") or "llama3.2"
            else:
                # xai / default
                base_url = cfg.get("base_url") or "https://api.x.ai/v1"
                model = cfg.get("model") or "grok-2-latest"
            if not api_key and prov not in ("ollama", "local"):
                return estado_auditavel + "\n\n[LLM não configurado em llm_config.json — resposta = estado real do agente]"
            import urllib.request
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content":
                     "Você explica o estado de um agente científico. "
                     "Use APENAS os dados fornecidos. Não invente hipóteses, números ou resultados. "
                     "Se faltar dado, diga SEM EVIDÊNCIA."},
                    {"role": "user", "content":
                     f"Agente: {agente_id}\nPergunta: {pergunta}\nEstado auditável:\n{estado_auditavel}"},
                ],
                "temperature": 0.2,
            }
            req = urllib.request.Request(
                base_url.rstrip("/") + "/chat/completions",
                data=json.dumps(body).encode(),
                headers={**( {"Authorization": f"Bearer {api_key}"} if api_key else {} ), "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            txt = data["choices"][0]["message"]["content"]
            return f"{txt}\n\n---\nFonte (estado real):\n{estado_auditavel}"
        except Exception as e:
            return estado_auditavel + f"\n\n[LLM falhou: {e} — mantido estado real]"

if __name__ == "__main__":
    try:
        CentralIAs().mainloop()
    except Exception:
        open("crash_central.txt","w").write(traceback.format_exc())
