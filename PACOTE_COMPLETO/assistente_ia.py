# -*- coding: utf-8 -*-
"""Assistente conversacional (C) + ordens automáticas para os combos."""
import customtkinter as ctk
import threading
from datetime import datetime
import ia_chat_llm as LLM

class Assistente(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Assistente IA — Chat + Ordens automáticas")
        self.geometry("1000x760")
        ctk.set_appearance_mode("dark")
        self.historico = []
        self.busy = False

        head = ctk.CTkFrame(self)
        head.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(head, text="ASSISTENTE IA", font=ctk.CTkFont(size=20, weight="bold"),
                     text_color="#a78bfa").pack(side="left", padx=8)
        self.lbl_status = ctk.CTkLabel(head, text=LLM.status_backend(), text_color="#94a3b8")
        self.lbl_status.pack(side="left", padx=10)

        cfg = LLM.load_cfg(apply_env=True)
        cfgf = ctk.CTkFrame(self)
        cfgf.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(cfgf, text="Provider:").pack(side="left", padx=4)
        self.prov = ctk.CTkComboBox(cfgf, values=["xai", "openai", "ollama"], width=110,
                                    command=self._on_provider)
        self.prov.set(cfg.get("provider") or "xai")
        self.prov.pack(side="left", padx=4)
        ctk.CTkLabel(cfgf, text="API Key:").pack(side="left", padx=4)
        self.key = ctk.CTkEntry(cfgf, width=260, show="*")
        if cfg.get("_key_from_env"):
            self.key.insert(0, "")  # não exibe nem copia chave do ambiente
            self.key.configure(placeholder_text="(chave via ambiente)")
        else:
            self.key.insert(0, cfg.get("api_key") or "")
        self.key.pack(side="left", padx=4)
        ctk.CTkLabel(cfgf, text="Model:").pack(side="left", padx=4)
        self.model = ctk.CTkEntry(cfgf, width=140)
        self.model.insert(0, cfg.get("model") or "grok-2-latest")
        self.model.pack(side="left", padx=4)
        ctk.CTkButton(cfgf, text="Salvar", width=70, command=self.salvar_cfg).pack(side="left", padx=4)
        ctk.CTkButton(cfgf, text="Melhorar sozinho agora", width=160, fg_color="#0ea5e9",
                      text_color="#111", command=self.auto_melhorar).pack(side="left", padx=6)

        ctk.CTkLabel(self, text="Lê logs dos 4 jogos (Mega, Lightning, Crazy Time, Immersive) · ordens em ordens_ia.json",
                     text_color="#64748b").pack(anchor="w", padx=14)

        self.chat = ctk.CTkTextbox(self, height=440)
        self.chat.pack(fill="both", expand=True, padx=10, pady=8)
        self._say("sistema",
                  "Olá. Posso explicar decisões e **publicar ordens** que os combos aplicam sozinhos.\n"
                  "Sem API key: modo local + ordens automáticas por heurística.\n"
                  "Com chave xAI/OpenAI/Ollama: diálogo completo.\n\n"
                  "Exemplos:\n"
                  "• por que o Mega errou?\n"
                  "• melhora o Crazy Time\n"
                  "• aplica ordem global com janela 3 e mais isol\n"
                  "• como está a taxa do Lightning?")

        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=10, pady=8)
        self.entry = ctk.CTkEntry(row, height=36, placeholder_text="Fale com a Meta-IA...")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.enviar())
        ctk.CTkButton(row, text="Enviar", width=100, fg_color="#7c3aed", command=self.enviar).pack(side="left")
        ctk.CTkButton(row, text="Ver ordens", width=100, command=self.ver_ordens).pack(side="left", padx=6)

        self.lbl_ordens = ctk.CTkLabel(self, text="", text_color="#86efac", wraplength=960, justify="left")
        self.lbl_ordens.pack(anchor="w", padx=14, pady=(0, 8))
        self.after(500, self.ver_ordens)

    def _say(self, quem, texto):
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat.insert("end", f"\n[{ts}] {quem}:\n{texto}\n")
        self.chat.see("end")

    def _on_provider(self, choice=None):
        prov = (choice or self.prov.get() or "xai").strip().lower()
        defaults = {"xai": "grok-2-latest", "openai": "gpt-4o-mini", "ollama": "llama3.2"}
        cur = self.model.get().strip()
        if not cur or cur in defaults.values() or cur.startswith("grok") or cur.startswith("gpt") or cur.startswith("llama"):
            self.model.delete(0, "end")
            self.model.insert(0, defaults.get(prov, "grok-2-latest"))

    def salvar_cfg(self):
        # base = só arquivo (sem misturar env na gravação)
        cfg = LLM.load_cfg(apply_env=False)
        prov = self.prov.get().strip() or "xai"
        cfg["provider"] = prov
        key_txt = self.key.get().strip()
        if key_txt in ("", "(env)", "(ambiente)"):
            # campo vazio = remove chave salva no JSON
            cfg["api_key"] = ""
            cfg["_persist_key"] = True
        else:
            cfg["api_key"] = key_txt
            cfg["_persist_key"] = True
        model = self.model.get().strip()
        # modelos padrão por provedor se o campo ficar genérico/incompatível
        defaults = {
            "xai": "grok-2-latest",
            "openai": "gpt-4o-mini",
            "ollama": "llama3.2",
        }
        if not model or (prov == "openai" and model.startswith("grok")) or (prov == "xai" and model.startswith("gpt")):
            model = defaults.get(prov, model or defaults["xai"])
            self.model.delete(0, "end")
            self.model.insert(0, model)
        cfg["model"] = model
        if prov == "ollama":
            cfg["ollama_model"] = model
        ok = LLM.save_cfg(cfg)
        self.lbl_status.configure(text=LLM.status_backend())
        if ok:
            self._say("sistema", "Config salva. Campo API Key vazio remove a chave do arquivo.")
        else:
            self._say("sistema", "Falha ao gravar llm_config.json (permissão/disco).")

    def ver_ordens(self):
        od = LLM.load_ordens()
        txt = (f"Ordens | mega={od.get('mega_fire')} | light={od.get('lightning')} | "
               f"ct={od.get('crazy_time')} | imm={od.get('immersive')} | atualizado={od.get('atualizado')}")
        self.lbl_ordens.configure(text=txt[:500])

    def auto_melhorar(self):
        def work():
            geradas = LLM.analisar_e_gerar_ordens_auto()
            msg = "Nenhum gatilho forte nos estados." if not geradas else "\n".join(
                f"• {j}: {o.get('motivo')}" for j, o in geradas
            )
            self.after(0, lambda: (self._say("auto", msg), self.ver_ordens(),
                                   self.lbl_status.configure(text=LLM.status_backend())))
        threading.Thread(target=work, daemon=True).start()

    def enviar(self):
        if self.busy: return
        pergunta = self.entry.get().strip()
        if not pergunta: return
        self.entry.delete(0, "end")
        self._say("você", pergunta)
        self.historico.append({"role": "user", "content": pergunta})
        self.busy = True
        self.lbl_status.configure(text="pensando...")

        def work():
            try:
                resp, modo = LLM.conversar(pergunta, self.historico, auto_aplicar_ordens=True)
            except Exception as e:
                resp, modo = f"Erro: {e}", "erro"
            self.historico.append({"role": "assistant", "content": resp})
            self.after(0, lambda: self._fim(resp, modo))
        threading.Thread(target=work, daemon=True).start()

    def _fim(self, resp, modo):
        self.busy = False
        self._say(f"IA ({modo})", resp)
        self.lbl_status.configure(text=LLM.status_backend())
        self.ver_ordens()

if __name__ == "__main__":
    Assistente().mainloop()
