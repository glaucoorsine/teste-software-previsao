# -*- coding: utf-8 -*-
"""LABORATÓRIO DE PERCEPÇÃO — alimenta memoria_percepcao.json para os apps combo"""
import threading, requests, time, os, traceback, json
from collections import Counter, defaultdict
from datetime import datetime

try:
    import customtkinter as ctk
    HAS_CTK = True
except Exception:
    HAS_CTK = False

try:
    import ia_biblioteca as IALIB
except Exception:
    IALIB = None

UPDATE = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.casino.org",
    "Referer": "https://www.casino.org/casinoscores/pt-br/",
}
APIS = {
    "mega_fire": "https://api-cs.casino.org/svc-evolution-game-events/api/megafireblazeroulette",
    "lightning": "https://api-cs.casino.org/svc-evolution-game-events/api/lightningroulette",
    "crazy_time": "https://api-cs.casino.org/svc-evolution-game-events/api/crazytime",
}
CT_SETORES = ["1", "2", "5", "10", "CoinFlip", "CashHunt", "Pachinko", "CrazyBonus"]
WHEEL = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

def pasta():
    for d in [os.path.join(os.path.expanduser("~"), "Downloads"), os.getcwd(),
              os.path.dirname(os.path.abspath(__file__))]:
        try:
            p = os.path.join(d, "Percepcao_Logs")
            os.makedirs(p, exist_ok=True)
            return p
        except Exception:
            continue
    return os.getcwd()

PASTA = pasta()

def log(msg):
    try:
        fn = os.path.join(PASTA, f"percepcao_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(fn, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%H:%M:%S')} | {msg}\n")
    except Exception:
        pass

def fetch_roleta(api):
    s = requests.Session(); s.headers.update(HEADERS)
    for params in [{"page":0,"size":80,"sort":"data.settledAt,desc","duration":90},
                   {"page":0,"size":50,"sort":"data.settledAt,desc","duration":45}]:
        try:
            r = s.get(api, params=params, timeout=20)
            if r.status_code != 200:
                continue
            data = r.json(); nums = []
            for it in data:
                try:
                    nums.append(int(it["data"]["result"]["outcome"]["number"]))
                except Exception:
                    continue
            if len(nums) >= 20:
                return nums
        except Exception as e:
            log(f"fetch_roleta {e}")
        time.sleep(0.3)
    return []

def fetch_ct():
    s = requests.Session(); s.headers.update(HEADERS)
    try:
        r = s.get(APIS["crazy_time"], params={"page":0,"size":80,"sort":"data.settledAt,desc","duration":90}, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        for it in r.json():
            try:
                sec = str((it["data"]["result"]["outcome"].get("wheelResult") or {}).get("wheelSector") or "")
                if sec in CT_SETORES:
                    out.append(sec)
            except Exception:
                continue
        return out
    except Exception as e:
        log(f"fetch_ct {e}")
        return []

def ag_final_dominante(nums):
    fins = Counter([x % 10 for x in nums[:30]])
    e, c = fins.most_common(1)[0]
    if c >= 6:
        return {"nome": f"FINAL_{e}_quente", "forca": c, "nums": [x for x in range(e, 37, 10)],
                "desc": f"Final {e} saiu {c}x/30", "tipo": "padrao"}
    return None

def ag_grupo_finais(nums):
    grupos = {"136": [1, 3, 6], "459": [4, 5, 9], "0278": [0, 2, 7, 8]}
    out = []
    for g, ends in grupos.items():
        c = sum(1 for x in nums[:25] if x % 10 in ends)
        if c >= 8:
            out.append({"nome": f"GRUPO_{g}", "forca": c,
                        "nums": [n for e in ends for n in range(e, 37, 10) if n <= 36],
                        "desc": f"Grupo {g} com {c}/25", "tipo": "padrao"})
    return out

def ag_setor_roda(nums):
    heat = [0.0] * 37
    for i, x in enumerate(nums[:20]):
        w = 1.3 - i * 0.05
        heat[x] += 3 * w
        if x in WHEEL:
            p = WHEEL.index(x)
            for d in (1, 2):
                heat[WHEEL[(p - d) % 37]] += 1.2 * w
                heat[WHEEL[(p + d) % 37]] += 1.2 * w
    q = sorted(range(37), key=lambda n: -heat[n])[:5]
    f = sorted(range(37), key=lambda n: heat[n])[:5]
    return [
        {"nome": "SETOR_QUENTE", "forca": 8, "nums": q, "desc": f"Setor quente {q}", "tipo": "padrao"},
        {"nome": "SETOR_FRIO", "forca": 5, "nums": f, "desc": f"Setor frio {f}", "tipo": "hipotese"},
    ]

def ag_atrasados(nums):
    out = []
    for n in range(37):
        g = next((i for i, x in enumerate(nums[:60]) if x == n), 60)
        if g >= 28:
            out.append({"nome": f"ATRASO_{n}", "forca": min(12, g // 4), "nums": [n],
                        "desc": f"{n} atrasado {g} giros", "tipo": "hipotese"})
    out.sort(key=lambda x: -x["forca"])
    return out[:6]

def ag_ausentes(nums):
    recent = set(nums[:25])
    aus = [n for n in range(37) if n not in recent]
    if len(aus) >= 8:
        return {"nome": "AUSENTES_25", "forca": 4, "nums": aus[:8],
                "desc": f"{len(aus)} ausentes nos 25", "tipo": "anti"}
    return None

def ag_markov(nums):
    if len(nums) < 15:
        return None
    trans = defaultdict(Counter)
    for i in range(min(40, len(nums) - 1)):
        trans[nums[i]][nums[i + 1]] += 1
    ult = nums[0]
    if ult not in trans:
        return None
    top = [n for n, _ in trans[ult].most_common(5)]
    return {"nome": f"MARKOV_APOS_{ult}", "forca": 6, "nums": top,
            "desc": f"Após {ult} costuma {top}", "tipo": "padrao"}

def ag_par_seq(nums):
    pares = Counter((nums[i], nums[i + 1]) for i in range(min(35, len(nums) - 1)))
    out = []
    for (a, b), c in pares.most_common(5):
        if c >= 2:
            out.append({"nome": f"PAR_{a}_{b}", "forca": c * 3, "nums": [a, b],
                        "desc": f"{a}→{b} x{c}", "tipo": "padrao"})
    return out

def ag_vizinhos_ultimo(nums):
    if not nums or nums[0] not in WHEEL:
        return None
    p = WHEEL.index(nums[0])
    v = [WHEEL[(p + d) % 37] for d in (-2, -1, 1, 2)]
    return {"nome": "VIZ_ULTIMO", "forca": 4, "nums": v, "desc": f"Vizinhos de {nums[0]}", "tipo": "hipotese"}


def fetch_stats_roleta(api):
    try:
        s = requests.Session(); s.headers.update(HEADERS)
        r = s.get(api + "/stats", params={"duration": 90}, timeout=20)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

def ag_stats_atraso(stats):
    if not stats: return []
    out=[]
    for it in stats.get("aggStatsRouletteNumbers") or []:
        try:
            n=int(it["number"]); g=int(it.get("lastSeenBefore") or 0)
            if g >= 20:
                out.append({"nome": f"TRACK_ATRASO_{n}", "forca": min(12, g//3), "nums":[n],
                            "desc": f"Tracker: {n} atrasado {g}", "tipo":"hipotese"})
        except Exception:
            continue
    out.sort(key=lambda x: -x["forca"])
    return out[:8]

def ag_stats_lightning(stats):
    if not stats: return []
    out=[]
    for it in stats.get("aggStatsLightningNumbers") or []:
        try:
            n=int(it["number"]); avg=float(it.get("average") or 0)
            if avg >= 120:
                out.append({"nome": f"TRACK_LIGHT_AVG_{n}", "forca": min(10, int(avg/30)), "nums":[n],
                            "desc": f"Lightning avg x{avg:.0f} no {n}", "tipo":"padrao"})
        except Exception:
            continue
    out.sort(key=lambda x: -x["forca"])
    return out[:6]

def ag_stats_ct(stats):
    if not stats: return []
    out=[]
    for it in stats.get("aggStats") or []:
        try:
            s=str(it.get("wheelResult")); g=int(it.get("lastSeenBefore") or 0)
            hot=float(it.get("hotFrequencyPercentage") or 0)
            if g >= 15 or abs(hot) >= 3:
                out.append({"nome": f"TRACK_CT_{s}", "forca": max(3, int(g/4)+int(abs(hot))), "nums":[s],
                            "desc": f"{s} gap {g} hot {hot:+.1f}%", "tipo":"padrao" if hot>0 or g>=20 else "hipotese"})
        except Exception:
            continue
    return out[:10]



# ---- Motor pesado no lab (CPU multi-core + GPU torch se houver) ----
def ag_motor_pesado_roleta(nums):
    """Usa MotorPesado da biblioteca: paralelo CPU + torch."""
    if IALIB is None:
        return []
    out = []
    try:
        if hasattr(IALIB, "ensemble_roleta_pesado"):
            r = IALIB.ensemble_roleta_pesado(nums, fire=None, n_alvos=12)
            sel = r.get("sel") or []
            consenso = r.get("consenso") or []
            isol = r.get("isol") or []
            device = r.get("device", "?")
            gpu = r.get("gpu", False)
            out.append({
                "nome": f"PESADO_SEL_{device}",
                "forca": 10,
                "nums": [int(x) for x in sel[:10] if isinstance(x, int)],
                "desc": f"MotorPesado sel device={device} gpu={gpu}: {sel[:8]}",
                "tipo": "padrao",
            })
            if consenso:
                out.append({
                    "nome": "PESADO_CONSENSO",
                    "forca": 9,
                    "nums": [int(x) for x in consenso[:8] if isinstance(x, int)],
                    "desc": f"Consenso ≥3 técnicas: {consenso[:8]}",
                    "tipo": "padrao",
                })
            if isol:
                out.append({
                    "nome": "PESADO_ISOL",
                    "forca": 6,
                    "nums": [int(x) for x in isol[:8] if isinstance(x, int)],
                    "desc": f"Isolados pesados: {isol[:8]}",
                    "tipo": "anti",
                })
            # técnicas individuais dos votos
            votos = r.get("votos") or r.get("tops") or {}
            for tec, lista in list(votos.items())[:6]:
                if not lista or tec.endswith("_err"):
                    continue
                nums_t = [int(x) for x in lista[:6] if isinstance(x, int)]
                if nums_t:
                    out.append({
                        "nome": f"PESADO_{tec.upper()}",
                        "forca": 5,
                        "nums": nums_t,
                        "desc": f"Técnica {tec}: {nums_t}",
                        "tipo": "hipotese",
                    })
    except Exception as e:
        out.append({
            "nome": "PESADO_ERRO",
            "forca": 1,
            "nums": [],
            "desc": f"MotorPesado falhou: {e}",
            "tipo": "hipotese",
        })
    return out

def ag_motor_pesado_ct(sec):
    if IALIB is None or not hasattr(IALIB, "ensemble_ct_pesado"):
        return []
    try:
        r = IALIB.ensemble_ct_pesado(sec, n_alvos=4)
        ranked = r.get("ranked") or r.get("sel") or []
        return [{
            "nome": f"PESADO_CT_{r.get('device','cpu')}",
            "forca": 9,
            "nums": list(ranked[:5]),
            "desc": r.get("veredito") or str(ranked[:5]),
            "tipo": "padrao",
        }]
    except Exception as e:
        return [{"nome": "PESADO_CT_ERRO", "forca": 1, "nums": [], "desc": str(e), "tipo": "hipotese"}]

def ag_torch_bias_lab(nums):
    """Torch direto no lab se disponível."""
    try:
        import torch
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        seq = [n for n in nums[:64] if isinstance(n, int) and 0 <= n <= 36]
        if len(seq) < 12:
            return None
        t = torch.tensor(seq, dtype=torch.long, device=device)
        emb = torch.nn.functional.one_hot(t, num_classes=37).float()
        w = torch.exp(-torch.linspace(0, 2.2, emb.size(0), device=device))
        scored = (emb * w.unsqueeze(1)).sum(dim=0)
        top = torch.topk(scored, k=8).indices.tolist()
        return {
            "nome": f"TORCH_BIAS_{device}",
            "forca": 8,
            "nums": [int(x) for x in top],
            "desc": f"torch {device} top={top}",
            "tipo": "padrao",
        }
    except Exception as e:
        return {"nome": "TORCH_OFF", "forca": 1, "nums": [], "desc": str(e), "tipo": "hipotese"}


AGENTES_ROLETA = [ag_final_dominante, ag_grupo_finais, ag_setor_roda, ag_atrasados,
                  ag_ausentes, ag_markov, ag_par_seq, ag_vizinhos_ultimo]

def ag_ct_atraso(sec):
    out = []
    ciclo = {"1": 4, "2": 4, "5": 7, "10": 14, "CoinFlip": 14, "CashHunt": 27, "Pachinko": 27, "CrazyBonus": 54}
    for s, esp in ciclo.items():
        g = next((i for i, x in enumerate(sec) if x == s), len(sec))
        if g >= esp * 1.3:
            out.append({"nome": f"CT_ATRASO_{s}", "forca": int(g / esp * 4), "nums": [s],
                        "desc": f"{s} gap {g} (esp~{esp})", "tipo": "padrao"})
    return out

def ag_ct_quente(sec):
    fr = Counter(sec[:20])
    out = []
    for s, c in fr.most_common(3):
        if c >= 4:
            out.append({"nome": f"CT_QUENTE_{s}", "forca": c * 2, "nums": [s],
                        "desc": f"{s} {c}x/20", "tipo": "padrao"})
    return out

def ag_ct_1_2_dominio(sec):
    c = sum(1 for x in sec[:15] if x in ("1", "2"))
    if c >= 10:
        return [{"nome": "CT_12_DOMINA", "forca": 5, "nums": ["5", "10", "Pachinko"],
                 "desc": "1/2 dominam → olhar fora", "tipo": "anti"}]
    return []

AGENTES_CT = [ag_ct_atraso, ag_ct_quente, ag_ct_1_2_dominio]

def normaliza(items):
    """Aceita None, dict único ou lista de dicts."""
    if items is None:
        return []
    if isinstance(items, dict):
        return [items]
    out = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, dict):
            out.append(it)
        elif isinstance(it, list):
            for sub in it:
                if isinstance(sub, dict):
                    out.append(sub)
    return out

def classificar(items):
    pad, hip, anti = [], [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        t = it.get("tipo", "hipotese")
        if t == "padrao":
            pad.append(it)
        elif t == "anti":
            anti.append(it)
        else:
            hip.append(it)
    pad.sort(key=lambda x: -float(x.get("forca", 0) or 0))
    hip.sort(key=lambda x: -float(x.get("forca", 0) or 0))
    anti.sort(key=lambda x: -float(x.get("forca", 0) or 0))
    return pad, hip, anti

def ciclo_jogo(jogo):
    linhas = [f"===== {jogo.upper()} ====="]
    try:
        if str(jogo).startswith("crazy_time"):
            sec = fetch_ct()
            if len(sec) < 15:
                return f"{jogo}: poucos dados ({len(sec)})\n"
            itens = []
            for ag in AGENTES_CT:
                try:
                    itens.extend(normaliza(ag(sec)))
                except Exception as e:
                    log(f"{jogo} {ag.__name__} {e}")
            st = fetch_stats_roleta(APIS["crazy_time"])
            try:
                itens.extend(normaliza(ag_stats_ct(st)))
            except Exception as e:
                log(f"{jogo} stats_ct {e}")
            try:
                itens.extend(normaliza(ag_motor_pesado_ct(sec)))
            except Exception as e:
                log(f"{jogo} pesado_ct {e}")
            linhas.append(f"Hist: {' → '.join(sec[:12])}")
        else:
            nums = fetch_roleta(APIS[jogo])
            if len(nums) < 20:
                return f"{jogo}: poucos dados ({len(nums)})\n"
            itens = []
            for ag in AGENTES_ROLETA:
                try:
                    itens.extend(normaliza(ag(nums)))
                except Exception as e:
                    log(f"{jogo} {ag.__name__} {e}")
            st = fetch_stats_roleta(APIS[jogo])
            for ag in (ag_stats_atraso, ag_stats_lightning):
                try:
                    itens.extend(normaliza(ag(st)))
                except Exception as e:
                    log(f"{jogo} stats {ag.__name__} {e}")
            # Motor pesado CPU/GPU
            try:
                itens.extend(normaliza(ag_motor_pesado_roleta(nums)))
            except Exception as e:
                log(f"{jogo} motor_pesado {e}")
            try:
                itens.extend(normaliza(ag_torch_bias_lab(nums)))
            except Exception as e:
                log(f"{jogo} torch_lab {e}")
            linhas.append(f"Hist: {' → '.join(str(x) for x in nums[:12])}")
        pad, hip, anti = classificar(itens)
        pesado_n = sum(1 for x in pad+hip+anti if "PESADO" in str(x.get("nome","")) or "TORCH" in str(x.get("nome","")))
        linhas.append(f"Agentes: padrões={len(pad)} hipóteses={len(hip)} anti={len(anti)} | pesado/torch={pesado_n}")
        try:
            if IALIB and hasattr(IALIB, "compute_info"):
                ci = IALIB.compute_info()
                linhas.append("Compute: device={} gpu={} numpy={} torch={} workers={}".format(ci.get("device"), ci.get("gpu"), ci.get("numpy"), ci.get("torch"), ci.get("cpu_workers")))
        except Exception:
            pass
        for titulo, lista in [("PADRÕES", pad[:6]), ("HIPÓTESES", hip[:6]), ("ANTI", anti[:5])]:
            linhas.append(f"--- {titulo} ---")
            for it in lista:
                linhas.append(f"  [{it.get('forca', 0)}] {it.get('nome')}: {it.get('desc')}")
        if IALIB and hasattr(IALIB, "percepcao_publicar"):
            try:
                IALIB.percepcao_publicar(jogo, padroes=pad[:15], hipoteses=hip[:15], descartes=anti[:10])
                linhas.append("→ publicado na biblioteca")
            except Exception as e:
                linhas.append(f"→ falha publicar: {e}")
                log(traceback.format_exc())
        log(f"{jogo} | pad={len(pad)} hip={len(hip)} anti={len(anti)}")
    except Exception as e:
        tb = traceback.format_exc()
        log(tb)
        linhas.append(f"ERRO no ciclo: {e}")
        # últimas 2 linhas do traceback para leitura rápida na tela
        tail = [ln for ln in tb.strip().splitlines() if ln.strip()][-2:]
        for ln in tail:
            linhas.append("  " + ln.strip())
    return "\n".join(linhas) + "\n\n"

if HAS_CTK:
    class App(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("LABORATÓRIO DE PERCEPÇÃO")
            self.geometry("920x680")
            ctk.set_appearance_mode("dark")
            self.busy = False
            self.running = True
            head = ctk.CTkFrame(self)
            head.pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(head, text="LAB PERCEPÇÃO", font=ctk.CTkFont(size=20, weight="bold"),
                         text_color="#a78bfa").pack(side="left", padx=8)
            dev = "cpu"
            try:
                if IALIB and hasattr(IALIB, "compute_info"):
                    ci = IALIB.compute_info()
                    dev = "{} gpu={} workers={}".format(ci.get("device"), ci.get("gpu"), ci.get("cpu_workers"))
            except Exception:
                pass
            ctk.CTkLabel(head, text=f"Motor: {dev}", text_color="#94a3b8").pack(side="left", padx=8)
            self.st = ctk.CTkLabel(head, text="Status: —")
            self.st.pack(side="left", padx=10)
            self.body = ctk.CTkTextbox(self, font=ctk.CTkFont(size=12))
            self.body.pack(fill="both", expand=True, padx=8, pady=8)
            ctk.CTkButton(self, text="RODAR AGORA", height=36, fg_color="#a855f7", text_color="#111",
                          command=self.manual).pack(fill="x", padx=8, pady=6)
            ctk.CTkLabel(self, text=f"Logs: {PASTA}", text_color="#64748b").pack(anchor="w", padx=10)
            self.after(800, self.loop)

        def escrever(self, txt):
            self.body.delete("1.0", "end")
            self.body.insert("1.0", txt)

        def worker(self):
            if self.busy:
                return
            self.busy = True
            try:
                self.after(0, lambda: self.st.configure(text="Status: varrendo...", text_color="#eab308"))
                txt = ""
                for j in ("mega_fire", "lightning", "crazy_time"):
                    txt += ciclo_jogo(j)
                txt += f"\nLogs: {PASTA}\n"
                self.after(0, lambda: (self.st.configure(text="Status: ok", text_color="#22c55e"), self.escrever(txt)))
            except Exception:
                log(traceback.format_exc())
                self.after(0, lambda: self.st.configure(text="Erro grave", text_color="#ef4444"))
            finally:
                self.busy = False

        def manual(self):
            threading.Thread(target=self.worker, daemon=True).start()

        def loop(self):
            if not self.running:
                return
            threading.Thread(target=self.worker, daemon=True).start()
            self.after(UPDATE * 1000, self.loop)

    if __name__ == "__main__":
        App().mainloop()
else:
    def _modo_console():
        print("customtkinter não instalado. Rode: pip install customtkinter")
        print("Modo console: 1 ciclo")
        for j in ("mega_fire", "lightning", "crazy_time"):
            print(ciclo_jogo(j))

    if __name__ == "__main__":
        _modo_console()
