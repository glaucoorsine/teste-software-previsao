from api_fetch import fetch_api

def _load_logo_image(jogo):
    """Carrega logo do diretório logos/ ao lado do script."""
    try:
        from pathlib import Path as _P
        from PIL import Image
        import customtkinter as ctk
        root = _P(__file__).resolve().parent / "logos"
        for name in (f"{jogo}_logo.png", f"{jogo}_logo.jpg", f"{jogo}_0.jpg", f"{jogo}_1.jpg"):
            fp = root / name
            if fp.is_file():
                img = Image.open(fp)
                img.thumbnail((120, 48))
                return ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
    except Exception:
        return None
    return None

# -*- coding: utf-8 -*-
"""MEGA FIRE — settled+mults+last_result no worker | placar acertos/erros | horizonte fixo | previsibilidade acadêmica."""
import customtkinter as ctk
import threading, requests, time, os, json, traceback
import multiprocessing as mp
from worker_process import process_cerebro

GAME = "mega_fire"
API = "https://api-cs.casino.org/svc-evolution-game-events/api/megafireblazeroulette"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Origin": "https://www.casino.org",
    "Referer": "https://www.casino.org/casinoscores/pt-br/",
}
PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logs")
os.makedirs(PASTA, exist_ok=True)
STATE_FILE = os.path.join(PASTA, f"{GAME}_combo_state.json")
LOG_FILE = os.path.join(PASTA, f"{GAME}_combo_log.txt")
VERMELHOS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def cor_num(n):
    if n == 0: return "#16a34a"
    return "#dc2626" if n in VERMELHOS else "#111827"

def log(msg):
    try:
        from datetime import datetime
        open(LOG_FILE,"a",encoding="utf-8").write(f"{datetime.now().strftime('%d/%m %H:%M:%S')} | {msg}\n")
    except Exception: pass

class App(ctk.CTk):
    def __init__(self, in_q, out_q):
        super().__init__()
        self.in_q, self.out_q = in_q, out_q
        self.title("MEGA FIRE — Pipeline 24reqs")
        self.geometry("1120x820")
        ctk.set_appearance_mode("dark")
        self.ok=0; self.err=0; self.restantes=0
        self.escolhas=[]; self.vistos=set()
        self._acertos_keys=set(); self._erros_keys=set()
        # contador POR NUMERO (cada giro), separado do por-janela (self.ok/err)
        self.ok_num=0; self.err_num=0
        self._seq_giro=0   # desempate p/ giros sem timestamp
        self.last_result=None
        self.running=True; self.busy=False
        self._carregar_estado()
        try:
            from fluxo_captura import carregar_ciclo_ativo
            cyc = carregar_ciclo_ativo(GAME)
            if cyc and cyc.get("escolhas") and int(cyc.get("restantes") or 0) > 0:
                self.escolhas = list(cyc["escolhas"])
                self.restantes = int(cyc["restantes"])
                self._janela_hit = bool(cyc.get("janela_hit"))
                log(f"CICLO_RESTAURADO | {self.escolhas} | rest={self.restantes}")
        except Exception as e:
            log(f"ciclo restore: {e}")
        # SEMPRE monta UI e inicia ciclo (não depende do except)
        self.build_ui()
        self.loop()

    def build_ui(self):
        h=ctk.CTkFrame(self); h.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(h, text="MEGA FIRE", font=("Arial",20,"bold"), text_color="#38bdf8").pack(side="left", padx=10)
        self.st=ctk.CTkLabel(h, text="Aguardando...", text_color="#a78bfa"); self.st.pack(side="left", padx=10)
        self.lbl_device=ctk.CTkLabel(h, text="HW: —", text_color="#eab308"); self.lbl_device.pack(side="right", padx=10)
        # Logo
        try:
            self._logo_img = _load_logo_image("mega_fire")
            if self._logo_img:
                ctk.CTkLabel(self, image=self._logo_img, text="").pack(pady=(6,0))
        except Exception:
            pass
        # Sinal operacional no topo
        self.sinal_frame = ctk.CTkFrame(self, fg_color="#7f1d1d", corner_radius=8)
        self.sinal_frame.pack(fill="x", padx=10, pady=(0,6))
        self.cnt_lbl = ctk.CTkLabel(self, text="Hist:0 | Sombra:— | Pend:0 | Aval:0/20 | Legado:0",
                               font=ctk.CTkFont(size=11), text_color="#94a3b8")
        self.cnt_lbl.pack(pady=(0,4))
        self.sinal_lbl = ctk.CTkLabel(
            self.sinal_frame,
            text="⛔ NÃO JOGUE POR AGORA",
            font=("Arial", 22, "bold"),
            text_color="#fecaca",
        )
        self.sinal_lbl.pack(pady=12)

        p=ctk.CTkFrame(self, fg_color="#0f172a"); p.pack(fill="x", padx=10, pady=5)
        # placar em duas linhas: JANELAS em cima, NUMEROS embaixo.
        # Sao contagens diferentes e antes ficavam na mesma linha, o que
        # fazia 4 marcas ✗ no historico parecerem contradizer "Erros 1".
        pcol=ctk.CTkFrame(p, fg_color="transparent"); pcol.pack(side="left", padx=10, pady=6)
        self.placar=ctk.CTkLabel(pcol, text=f"JANELAS   Acertos {self.ok} | Erros {self.err}",
                                 font=("Arial",20,"bold"), anchor="w", justify="left")
        self.placar.pack(anchor="w")
        self.placar_num=ctk.CTkLabel(pcol, text=f"NÚMEROS   Acertos {self.ok_num} | Erros {self.err_num}",
                                     font=("Arial",15,"bold"), anchor="w", justify="left",
                                     text_color="#93c5fd")
        self.placar_num.pack(anchor="w")
        self.janela_lbl=ctk.CTkLabel(p, text="Janela: —", font=("Arial",16,"bold"), text_color="#fbbf24")
        self.janela_lbl.pack(side="right", padx=10)
        mid=ctk.CTkFrame(self, fg_color="transparent"); mid.pack(fill="x", padx=10, pady=5)
        f1=ctk.CTkFrame(mid, fg_color="#1e293b", border_width=2, border_color="#22c55e")
        f1.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(f1, text="SUGESTÃO (LSTM ∩ outra fonte)", text_color="#22c55e", font=("Arial",13,"bold")).pack(pady=5)
        bx1=ctk.CTkFrame(f1, fg_color="transparent"); bx1.pack(pady=10)
        self.labs_p=[]
        for _ in range(7):
            l=ctk.CTkLabel(bx1, text="—", width=50, height=50, corner_radius=10, fg_color="#334155", font=("Arial",18,"bold"))
            l.pack(side="left", padx=5); self.labs_p.append(l)
        hist_box=ctk.CTkFrame(mid, fg_color="#1e293b", border_width=1, border_color="#475569")
        hist_box.pack(side="left", fill="both", expand=True, padx=(6,0))
        ctk.CTkLabel(hist_box, text="HISTÓRICO + MULTIPLICADORES", font=("Arial",13,"bold")).pack(pady=(6,2))
        self.hist_scroll=ctk.CTkScrollableFrame(hist_box, height=130, orientation="horizontal")
        self.hist_scroll.pack(fill="both", expand=True, padx=6, pady=6)
        self.res=ctk.CTkLabel(self, text="Última: —", font=("Arial",14,"bold")); self.res.pack(anchor="w", padx=14, pady=2)
        ctk.CTkLabel(self, text="Auditoria completa", font=("Arial",13,"bold")).pack(anchor="w", padx=15, pady=(10,0))
        self.feed_box=ctk.CTkTextbox(self, height=220); self.feed_box.pack(fill="both", expand=True, padx=10, pady=6)

    def _carregar_estado(self):
        try:
            if os.path.isfile(STATE_FILE):
                st=json.load(open(STATE_FILE,encoding="utf-8"))
                self.ok=int(st.get("ok",0)); self.err=int(st.get("err",0))
                self.vistos=set(st.get("vistos") or [])
                self._acertos_keys=set(st.get("acertos_keys") or [])
                self._erros_keys=set(st.get("erros_keys") or [])
                self.ok_num=int(st.get("ok_num") or 0)
                self.err_num=int(st.get("err_num") or 0)
                # restaura ciclo em andamento do state principal
                if st.get("escolhas") and int(st.get("restantes") or 0) > 0:
                    self.escolhas=list(st.get("escolhas") or [])
                    self.restantes=int(st.get("restantes") or 0)
                    self._janela_hit=bool(st.get("janela_hit"))
                self._last_janela_size=int(st.get("last_janela_size") or 0)
                self._last_escolhas=list(st.get("last_escolhas") or [])
                self._soma_p_esperado=float(st.get("soma_p_esperado") or 0.0)
        except Exception: pass

    def _salvar_estado(self):
        try:
            data={"ok":self.ok,"err":self.err,"vistos":list(self.vistos)[-200:],
                  "acertos_keys":list(self._acertos_keys)[-200:],"erros_keys":list(self._erros_keys)[-200:],
                  "ok_num":int(getattr(self,"ok_num",0) or 0),"err_num":int(getattr(self,"err_num",0) or 0),
                  "escolhas":list(getattr(self,"escolhas",[]) or []),
                  "restantes":int(getattr(self,"restantes",0) or 0),
                  "janela_hit":bool(getattr(self,"_janela_hit",False)),
                  "last_janela_size":int(getattr(self,"_last_janela_size",0) or 0),
                  "last_escolhas":list(getattr(self,"_last_escolhas",[]) or []),
                  "soma_p_esperado":float(getattr(self,"_soma_p_esperado",0.0) or 0.0)}
            tmp=STATE_FILE+".tmp"
            open(tmp,"w",encoding="utf-8").write(json.dumps(data, ensure_ascii=False))
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            log(f"ERRO_SALVAR_ESTADO: {e}")

    def desenhar_hist(self, rows):
        for w in self.hist_scroll.winfo_children(): w.destroy()
        for r in rows[:18]:
            n=r["n"]; key=str(r.get("settled") or n)
            c=ctk.CTkFrame(self.hist_scroll, fg_color="#0f172a"); c.pack(side="left", padx=4, pady=4)
            ctk.CTkLabel(c, text=str(n), width=42, height=42, corner_radius=20, fg_color=cor_num(n),
                         text_color="#fff", font=("Arial",15,"bold")).pack(side="left", padx=3, pady=4)
            extra=""
            for t in (r.get("tags") or []):
                if t.get("x"): extra += f"×{t['x']} "
                elif t.get("fire"): extra += "🔥 "
            if extra:
                ctk.CTkLabel(c, text=extra.strip(), text_color="#fbbf24", font=("Arial",11,"bold")).pack(side="left")
            if key in self._acertos_keys:
                ctk.CTkLabel(c, text="✓", text_color="#22c55e", font=("Arial",16,"bold")).pack(side="left", padx=2)
            elif key in self._erros_keys:
                ctk.CTkLabel(c, text="✗", text_color="#ef4444", font=("Arial",16,"bold")).pack(side="left", padx=2)

    def validar(self, r):
        """Só estado — UI na thread principal."""
        n=r["n"]
        # Sem timestamp a chave virava so o numero, entao dois giros iguais
        # colidiam e o 2o era DESCARTADO (a janela nao andava). Agora giro
        # sem settled recebe um contador proprio, mantendo o dedupe real
        # para giros COM timestamp.
        _ts=r.get("settled")
        if _ts:
            key=str(_ts)
        else:
            self._seq_giro=int(getattr(self,"_seq_giro",0))+1
            key=f"{n}#s{self._seq_giro}"
        if key in self.vistos: return False
        self.vistos.add(key)
        self._ui_validacao = None
        if not self.escolhas: return True
        self.restantes -= 1
        hit = n in self.escolhas
        if hit:
            self._acertos_keys.add(key)
            self.ok_num += 1     # contador POR NUMERO
            log(f"HIT na janela | {n} | restam={self.restantes}")
        else:
            self._erros_keys.add(key)
            self.err_num += 1    # contador POR NUMERO
            log(f"MISS na janela | {n} | restam={self.restantes}")
        # horizonte fixo: só encerra quando restantes == 0
        if self.restantes <= 0:
            # fecha janela: acerto se houve pelo menos um hit nesta janela
            # usa flag _janela_hit
            janela_hit = bool(getattr(self, "_janela_hit", False) or hit)
            if janela_hit:
                self.ok += 1
                try:
                    from metricas_honestas import p_esperado_para
                    pe=p_esperado_para(getattr(self,"_last_escolhas",[]) or [], int(getattr(self,"_last_janela_size",4) or 4), is_ct=(GAME=="crazy_time"))
                    self._soma_p_esperado=float(getattr(self,"_soma_p_esperado",0.0) or 0.0)+pe
                except Exception:
                    pass
                self.last_result={"saiu": n, "acertou": True, "settled": r.get("settled"), "window_done": True}
                self._ui_validacao = ("ok", n, 0)
                log(f"JANELA OK | último={n} | ok={self.ok} err={self.err}")
            else:
                self.err += 1
                try:
                    from metricas_honestas import p_esperado_para
                    pe=p_esperado_para(getattr(self,"_last_escolhas",[]) or [], int(getattr(self,"_last_janela_size",4) or 4), is_ct=(GAME=="crazy_time"))
                    self._soma_p_esperado=float(getattr(self,"_soma_p_esperado",0.0) or 0.0)+pe
                except Exception:
                    pass
                self.last_result={"saiu": n, "acertou": False, "settled": r.get("settled"), "window_done": True}
                self._ui_validacao = ("err_fim", n, 0)
                log(f"JANELA ERRO | último={n} | ok={self.ok} err={self.err}")
            self.escolhas=[]
            self._janela_hit = False
        else:
            if hit:
                self._janela_hit = True
            self.last_result={"saiu": n, "acertou": hit, "settled": r.get("settled"), "window_done": False}
            self._ui_validacao = ("hit" if hit else "err", n, self.restantes)
        self._salvar_estado(); return True

    def _aplicar_validacao_ui(self):
        v = getattr(self, "_ui_validacao", None)
        if not v: return
        tipo, n, rest = v
        # placar público (escolhas) + placar científico (avaliadas sombra/operar)
        av = 0; er = 0
        try:
            ms = getattr(self, "_last_mem_stats", None) or {}
            av = int(ms.get("acertos_aval") or 0)
            er = int(ms.get("erros_aval") or 0)
        except Exception:
            pass
        try:
            from metricas_honestas import texto_placar_acumulado
            is_ct = (GAME == "crazy_time")
            j_use = int(getattr(self, "_last_janela_size", 0) or 0) or 4
            soma_p = float(getattr(self, "_soma_p_esperado", 0.0) or 0.0)
            # se motor enviou cobertura_acc, prefere
            ms = getattr(self, "_last_mem_stats", None) or {}
            if ms.get("soma_p_esperado") is not None:
                soma_p = float(ms.get("soma_p_esperado") or 0.0)
            txt = texto_placar_acumulado(
                self.ok, self.err, soma_p,
                alvos_ultima=getattr(self, "_last_escolhas", []) or getattr(self, "escolhas", []),
                janela_ultima=j_use, is_ct=is_ct, exp_acertos=av, exp_erros=er,
            )
            self.placar.configure(text=txt)
            self._atualizar_placar_num()
        except Exception:
            self.placar.configure(text=f"Janelas {self.ok}|{self.err}  (cobertura ≠ edge)")
            self._atualizar_placar_num()
        if tipo == "ok":
            self.res.configure(text=f"✅ JANELA ACERTO | último {n}", text_color="#22c55e")
            self.janela_lbl.configure(text="Janela: —")
        elif tipo == "err_fim":
            self.res.configure(text=f"❌ JANELA ERRO | último {n}", text_color="#ef4444")
            self.janela_lbl.configure(text="Janela: —")
        elif tipo == "hit":
            self.res.configure(text=f"✅ HIT {n} — restam {rest}", text_color="#86efac")
            self.janela_lbl.configure(text=f"Janela: {rest}")
        else:
            self.res.configure(text=f"❌ MISS {n} — restam {rest}", text_color="#fca5a5")
            self.janela_lbl.configure(text=f"Janela: {rest}")
        self._ui_validacao = None

    def _atualizar_sinal(self, modo, operavel=False, motivos=None):
        """Verde = apto para jogar | Vermelho = não jogue por agora."""
        apto = (modo == "OPERAR" and operavel) or (modo == "JANELA_ATIVA" and self.escolhas and self.restantes > 0)
        if apto:
            self.sinal_frame.configure(fg_color="#14532d")
            self.sinal_lbl.configure(text="✅ APTO PARA JOGAR", text_color="#bbf7d0")
        else:
            self.sinal_frame.configure(fg_color="#7f1d1d")
            extra = ""
            if motivos:
                extra = " — " + ", ".join(str(m) for m in motivos[:2])
            elif modo in ("AGUARDANDO", "NAO_OPERAR"):
                extra = f" — {modo}"
            elif modo:
                extra = f" — {modo}"
            self.sinal_lbl.configure(text=f"⛔ NÃO JOGUE POR AGORA{extra}", text_color="#fecaca")


    def _atualizar_placar_num(self):
        """Linha 2: contagem por NUMERO que saiu (1 por giro avaliado)."""
        try:
            a=int(getattr(self,'ok_num',0) or 0); e=int(getattr(self,'err_num',0) or 0)
            tot=a+e
            txt=f"NÚMEROS   Acertos {a} | Erros {e}"
            if tot:
                txt += f"   taxa={a/tot*100:.0f}%"
            self.placar_num.configure(text=txt)
        except Exception:
            pass

    def _texto_sombra(self, av, er):
        """av/er sao CONTAGEM REAL de sombra avaliada (nao "esperado" -- o
        rotulo antigo estava errado). Mostra a taxa observada junto do acaso
        calculado (soma_p_esperado/n_cobertura, ja produzido por ia_modulos),
        pra dar a comparacao que interessa em vez de dois numeros soltos."""
        n = int(av) + int(er)
        if n <= 0:
            return "sombra: sem janelas avaliadas"
        taxa = av / n
        txt = f"sombra(real) {av}|{er} taxa={taxa*100:.0f}%"
        try:
            ms = getattr(self, "_last_mem_stats", None) or {}
            n_cob = int(ms.get("n_cobertura") or 0)
            soma_p = float(ms.get("soma_p_esperado") or 0.0)
            if n_cob > 0:
                p_esp = soma_p / n_cob
                txt += f"  acaso\u2248{p_esp*100:.0f}%  \u0394={(taxa-p_esp)*100:+.0f}pp"
        except Exception:
            pass
        return txt

    def aplicar(self, sug):
        modo=sug.get("modo") or ""
        # NÃO apaga seleção se janela ainda está ativa
        if self.escolhas and self.restantes > 0:
            self.janela_lbl.configure(text=f"Janela: {self.restantes} | {modo or 'ATIVA'}", text_color="#fbbf24")
            for i,l in enumerate(self.labs_p):
                l.configure(text=str(self.escolhas[i]) if i < len(self.escolhas) else "—",
                            fg_color="#16a34a" if i < len(self.escolhas) else "#334155")
        elif not sug.get("pad5"):
            self.escolhas=[]; self.restantes=0
            self.janela_lbl.configure(text="AGUARDANDO — evidência insuficiente", text_color="#ef4444")
            for l in self.labs_p: l.configure(text="—", fg_color="#334155")
        else:
            self.escolhas=list(sug["pad5"])[:7]
            self._janela_hit = False
            self.restantes=int(sug.get("janela") or 4)
            self._last_janela_size=int(self.restantes)
            self._last_escolhas=list(self.escolhas)
            self._janela_hit = False
            log(f"NOVA_JANELA | {self.restantes} | {self.escolhas} | {modo}")
            # aviso no celular — em thread propria, nunca trava a interface
            try:
                from notificador import notificar_sinal
                _q = ""
                for _m in (sug.get("msgs") or []):
                    if _m.startswith("[Gatilho] consenso sozinho"):
                        _q = _m.split("—", 1)[-1].strip()[:90]
                        break
                notificar_sinal(GAME, self.escolhas, modo=modo,
                                janela=self.restantes, extra=_q, log_fn=log)
            except Exception as _e:
                log(f"notificacao: {_e}")
            try:
                from fluxo_captura import salvar_ciclo_ativo
                salvar_ciclo_ativo(GAME, self.escolhas, self.restantes, False, self.ok, self.err)
            except Exception as e:
                log(f"ciclo save: {e}")
            self.janela_lbl.configure(text=f"Janela: {self.restantes} | {modo}", text_color="#fbbf24")
            for i,l in enumerate(self.labs_p):
                l.configure(text=str(self.escolhas[i]) if i < len(self.escolhas) else "—",
                            fg_color="#16a34a" if i < len(self.escolhas) else "#334155")
        if "device" in sug: self.lbl_device.configure(text=f"HW: {str(sug['device']).upper()}")
        modo = sug.get("modo") or ""
        if modo in ("NAO_OPERAR", "AGUARDANDO") and not (self.escolhas and self.restantes > 0):
            self.res.configure(text=f"⛔ {modo} — NÃO APOSTAR", text_color="#ef4444")
            self.janela_lbl.configure(text=modo, text_color="#ef4444")
        elif modo == "OPERAR":
            self.res.configure(text=f"✅ SINAL ATIVO {sug.get('pad5')}", text_color="#22c55e")
        self.feed_box.delete("1.0","end"); self.feed_box.insert("1.0","\n".join(sug.get("msgs") or []))
        self._last_mem_stats = dict(sug.get("mem_stats") or {})
        cnt = sug.get("contadores") or {}
        try:
            av = int(self._last_mem_stats.get("acertos_aval") or 0)
            er = int(self._last_mem_stats.get("erros_aval") or 0)
            # placar visual só — NÃO gravar em self.ok/err (evita contaminar motor/estado)
            if av or er:
                self.placar.configure(
                    text=f"Acertos {self.ok} | Erros {self.err}   · {self._texto_sombra(av, er)}"
                )
            else:
                self.placar.configure(text=f"JANELAS   Acertos {self.ok} | Erros {self.err}")
                self._atualizar_placar_num()
        except Exception:
            pass
        if hasattr(self, "cnt_lbl"):
            self.cnt_lbl.configure(
                text=(f"Histórico bruto: {cnt.get('historico_bruto',0)} | "
                      f"Sombra: {'sim' if sug.get('sombra') else 'não'} | "
                      f"Pendentes: {cnt.get('janelas_pendentes',0)} | "
                      f"Avaliadas: {cnt.get('janelas_avaliadas',0)} (mín. recomendado {cnt.get('min_avaliadas',20)}) | "
                      f"Legado: {cnt.get('legado_ignorado',0)}")
            )
        self._atualizar_sinal(
            sug.get("modo") or "",
            operavel=bool(sug.get("operavel")),
            motivos=sug.get("motivo_bloq") or [],
        )


    def worker(self):
        if self.busy: return
        self.busy=True
        try:
            self.after(0, lambda: self.st.configure(text="Capturando...", text_color="#eab308"))
            from fluxo_captura import capturar, marcar_snapshot_processado, salvar_ciclo_ativo, limpar_ciclo_ativo
            cap = capturar(GAME, page_size=50, max_pages=2)
            if cap.get("err") and not cap.get("rows"):
                log(f"API offline: {cap['err']}")
                self.after(0, lambda e=cap["err"]: self.st.configure(text=f"API: {e}"[:80], text_color="#ef4444"))
                return
            rows = cap.get("rows") or []
            mults = cap.get("mults") or []
            # API caiu mas o buffer tem historico: seguimos analisando o que ja
            # foi coletado, avisando com honestidade que nao ha giro novo.
            _off = bool(cap.get("offline"))
            if _off:
                log(f"API instavel ({cap.get('err')}) - seguindo com historico salvo")
                self.after(0, lambda: self.st.configure(
                    text="API instável — analisando histórico salvo",
                    text_color="#eab308"))
            if not rows:
                self.after(0, lambda: self.st.configure(text="Sem dados", text_color="#ef4444")); return

            # Idempotência: mesmo head já processado → só redesenha, não reenvia ao motor
            head_id = cap.get("head_id")
            if not cap.get("novo_head") and self.escolhas and self.restantes > 0:
                # ainda atualiza UI do histórico, mas não valida de novo o mesmo evento
                self.after(0, lambda: (self.st.configure(text=("API instável — histórico salvo" if _off else "Operacional (mesmo snapshot)"), text_color=("#eab308" if _off else "#22c55e")), self.desenhar_hist(rows)))
                return
            if not cap.get("novo_head") and not self.escolhas:
                # mesmo snapshot, sem ciclo: só redesenha — NÃO consulta motor de novo
                self.after(0, lambda: (self.st.configure(text=("API instável — histórico salvo" if _off else "Operacional"), text_color=("#eab308" if _off else "#22c55e")), self.desenhar_hist(rows)))
                return

            mudou = bool(cap.get("novo_head"))
            if mudou:
                self.validar(rows[0])

            # persiste ciclo em andamento
            if self.escolhas and self.restantes > 0:
                salvar_ciclo_ativo(GAME, self.escolhas, self.restantes, getattr(self, "_janela_hit", False), self.ok, self.err)
            else:
                limpar_ciclo_ativo(GAME)

            pending_lr = self.last_result if mudou else None
            payload={
                "nums": [x["n"] for x in rows],
                "settled": [x.get("settled") for x in rows],
                "mults": mults,
                "ok": self.ok, "err": self.err,
                "last_result": pending_lr,
                "active_selection": list(getattr(self, "escolhas", None) or []),
                "head_id": head_id,
            }
            # evita reenvio do mesmo head sem ciclo: grava poll head antes do put
            if head_id and not mudou:
                self._last_poll_head = head_id
            self.in_q.put(payload)
            sug=None
            try:
                import queue as _queue
                sug=self.out_q.get(timeout=45)
            except _queue.Empty:
                # timeout: NÃO apaga last_result — próxima tentativa reenvia
                self.after(0, lambda: self.st.configure(text="Timeout motor", text_color="#ef4444"))
                return
            except Exception as e:
                err=str(e)[:60]
                self.after(0, lambda err=err: self.st.configure(text=f"Falha fila: {err}", text_color="#ef4444"))
                return
            if not sug:
                self.after(0, lambda: self.st.configure(text="Resposta vazia do motor", text_color="#ef4444"))
                # NÃO marca snapshot — permite reprocessar
            else:
                if mudou and head_id:
                    try:
                        marcar_snapshot_processado(GAME, head_id)
                    except Exception as e:
                        log(f"snap mark: {e}")
                if mudou:
                    self.last_result = None  # só após sucesso
                self.after(0, lambda: (self._aplicar_validacao_ui(), self.st.configure(text="Operacional", text_color="#22c55e"), self.aplicar(sug), self.desenhar_hist(rows)))
        except Exception as e:
            log(f"Falha worker: {type(e).__name__}: {e}")
            self.after(0, lambda err=str(e): self.st.configure(text=f"Falha: {err}"[:80], text_color="#ef4444"))
        finally:
            self.busy=False

    def loop(self):
        if self.running:
            threading.Thread(target=self.worker, daemon=True).start()
            self.after(10000, self.loop)

def main():
    mp.freeze_support()
    in_q, out_q = mp.Queue(), mp.Queue()
    p=mp.Process(target=process_cerebro, args=(in_q, out_q, "mega_fire"), daemon=True); p.start()
    try: App(in_q, out_q).mainloop()
    except Exception:
        open("crash_log.txt","w").write(traceback.format_exc())
    finally:
        in_q.put(None); p.join(timeout=2)

if __name__ == "__main__":
    main()
