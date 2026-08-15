# -*- coding: utf-8 -*-
"""Chat LLM + ordens automáticas para os combos aplicarem."""
from __future__ import annotations
import json, os, re
from pathlib import Path
from datetime import datetime

try:
    import requests
except Exception:
    requests = None

ROOT = Path(__file__).resolve().parent
CFG_PATH = ROOT / "llm_config.json"
ORDENS_PATH = ROOT / "ordens_ia.json"

SYSTEM_PROMPT = """Você é a Meta-IA conversacional e operadora dos softwares Mega Fire, Lightning e Crazy Time.
Fale em português do Brasil, claro e direto.

Obrigações:
1) Explicar decisões do MotorPesado e do Consenso com base nos logs.
2) Analisar acertos, erros, misses e taxa.
3) Quando for melhorar o software, emita uma ORDEM JSON além da explicação.
4) Seja honesta: roleta tem vantagem da casa.

Formato de ORDEM:
```json
{"jogo":"mega_fire","janela":3,"peso_isol":2.5,"peso_motor":3.5,"boost_anti":true,"prioritizar_atraso":true,"reduzir_12":false,"motivo":"..."}
```
jogo: mega_fire | lightning | crazy_time | immersive | global
"""

def load_cfg(apply_env: bool = True):
    """Carrega JSON local. Env vars só no runtime (apply_env=True), não para gravação."""
    cfg = {
        "provider": "xai", "api_key": "", "model": "grok-2-latest",
        "base_url": "https://api.x.ai/v1",
        "openai_base_url": "https://api.openai.com/v1",
        "ollama_url": "http://127.0.0.1:11434", "ollama_model": "llama3.2",
        "max_log_lines": 80, "temperature": 0.4,
    }
    if CFG_PATH.is_file():
        try: cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
        except Exception: pass
    cfg["_key_from_env"] = False
    if apply_env:
        for env_k, cfg_k in [
            ("XAI_API_KEY","api_key"),("GROK_API_KEY","api_key"),("OPENAI_API_KEY","api_key"),
            ("LLM_API_KEY","api_key"),("LLM_PROVIDER","provider"),("LLM_MODEL","model"),
        ]:
            v = os.environ.get(env_k)
            if v:
                cfg[cfg_k] = v
                if cfg_k == "api_key":
                    cfg["_key_from_env"] = True
    return cfg

def save_cfg(cfg: dict) -> bool:
    """Grava só campos persistíveis. Nunca grava chave que veio só do ambiente."""
    try:
        clean = {k: v for k, v in dict(cfg or {}).items() if not str(k).startswith("_")}
        # se a chave em memória veio do env e o caller não passou override explícito, não persiste
        if cfg.get("_key_from_env") and not cfg.get("_persist_key"):
            file_cfg = load_cfg(apply_env=False)
            clean["api_key"] = file_cfg.get("api_key") or ""
        CFG_PATH.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False

def _candidate_log_dirs():
    home = Path.home()
    names = ["Logs", "MegaFire_Logs", "Lightning_Logs", "CrazyTime_Logs", "Immersive_Logs"]
    bases = [Path.cwd(), ROOT, home / "Downloads", home / "Desktop", home / "Downloads" / "teste"]
    out, seen = [], set()
    for b in bases:
        for n in names:
            p = (b / n)
            try:
                rp = str(p.resolve())
            except Exception:
                continue
            if p.is_dir() and rp not in seen:
                seen.add(rp); out.append(p)
        # pasta atual do software se tiver logs
        try:
            if b.is_dir() and (list(b.glob("*_combo_log.txt")) or list(b.glob("*_state.json")) or list(b.glob("memoria_*.json"))):
                rp = str(b.resolve())
                if rp not in seen:
                    seen.add(rp); out.append(b)
        except Exception:
            pass
    return out

def coletar_contexto(max_lines: int = 80) -> str:
    chunks = [f"Agora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"]
    for d in _candidate_log_dirs():
        chunks.append(f"\n## Pasta {d}")
        for f in sorted(d.glob("*.txt"))[-3:]:
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
                tail = lines[-max_lines:]
                chunks.append(f"### {f.name} (últimas {len(tail)})")
                chunks.append("\n".join(tail))
            except Exception as e:
                chunks.append(f"### {f.name} erro: {e}")
        for f in sorted(d.glob("*_state.json")):
            try:
                st = json.loads(f.read_text(encoding="utf-8"))
                chunks.append(
                    f"### estado {f.name}: ok={st.get('ok')} err={st.get('err')} "
                    f"misses={st.get('misses_total')} miss_seq={st.get('miss_seq')}"
                )
            except Exception:
                pass
    for name in ("ia_memoria.json", "biblioteca_padroes.json", "percepcao_mem.json"):
        fp = ROOT / name
        if fp.is_file():
            try:
                chunks.append(f"\n## {name}\n" + fp.read_text(encoding="utf-8", errors="ignore")[:3500])
            except Exception:
                pass
    txt = "\n".join(chunks)
    return txt[-24000:] if len(txt) > 24000 else txt

def load_ordens():
    base = {
        "versao": 1, "atualizado": None, "origem": "assistente",
        "mega_fire": {}, "lightning": {}, "crazy_time": {}, "immersive": {}, "global": {},
        "historico_ordens": [], "resultados": [],
    }
    if ORDENS_PATH.is_file():
        try:
            base.update(json.loads(ORDENS_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return base

def _acquire_ordens_lock(timeout_s: float = 3.0):
    """Obtém lock exclusivo. None se falhar. Remove lock órfão (>30s)."""
    import time
    lock = Path(str(ORDENS_PATH) + ".lock")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}:{time.time()}".encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                raw = lock.read_text(encoding="utf-8", errors="ignore")
                ts = float(raw.split(":")[-1]) if ":" in raw else 0.0
                if ts and (time.time() - ts) > 30:
                    lock.unlink(missing_ok=True)
                    continue
            except Exception:
                pass
            time.sleep(0.05)
        except Exception:
            return None
    return None

def _save_ordens_unlocked(data: dict) -> bool:
    """Escrita atômica SEM adquirir lock (caller já segura o lock)."""
    try:
        clean = {k: v for k, v in dict(data or {}).items() if not str(k).startswith("_")}
        tmp = Path(str(ORDENS_PATH) + ".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(ORDENS_PATH)
        return True
    except Exception:
        return False

def save_ordens(data: dict) -> bool:
    """Adquire lock → grava → libera. Se não obtiver lock, NÃO grava."""
    lock = _acquire_ordens_lock()
    if lock is None:
        return False
    try:
        return _save_ordens_unlocked(data)
    finally:
        try:
            # só remove se for o nosso lock (mesmo pid)
            raw = lock.read_text(encoding="utf-8", errors="ignore")
            if raw.startswith(str(os.getpid()) + ":"):
                lock.unlink(missing_ok=True)
        except Exception:
            try:
                lock.unlink(missing_ok=True)
            except Exception:
                pass

def with_ordens_lock(mutator):
    """Ciclo atômico ler→alterar→gravar sob o mesmo lock.
    mutator(data) -> data
    Retorna (ok: bool, data: dict).
    """
    lock = _acquire_ordens_lock()
    if lock is None:
        return False, load_ordens()
    try:
        data = load_ordens()
        try:
            data = mutator(data) or data
        except Exception:
            return False, data
        ok = _save_ordens_unlocked(data)
        return ok, data
    finally:
        try:
            raw = lock.read_text(encoding="utf-8", errors="ignore")
            if raw.startswith(str(os.getpid()) + ":"):
                lock.unlink(missing_ok=True)
        except Exception:
            try:
                lock.unlink(missing_ok=True)
            except Exception:
                pass

def validar_ordem(ordem: dict) -> dict:
    """Campos e limites rígidos antes de publicar. Motor usa janela 2–3."""
    o = {}
    if not isinstance(ordem, dict):
        return o
    if "janela" in ordem and ordem["janela"] is not None:
        try:
            j = int(ordem["janela"])
            o["janela"] = max(2, min(3, j))
        except Exception:
            pass
    for k in ("peso_isol", "peso_motor"):
        if k in ordem and ordem[k] is not None:
            try:
                v = float(ordem[k])
                o[k] = max(0.5, min(5.0, v))
            except Exception:
                pass
    for k in ("boost_anti", "prioritizar_atraso", "reduzir_12"):
        if k in ordem and ordem[k] is not None:
            o[k] = bool(ordem[k])
    if "motivo" in ordem and ordem["motivo"] is not None:
        o["motivo"] = str(ordem["motivo"])[:200]
    return o

def _norm_jogo(jogo: str) -> str:
    j = (jogo or "global").strip().lower().replace(" ", "_")
    if j in ("megafire", "mega"): return "mega_fire"
    if j in ("ct", "crazy"): return "crazy_time"
    if j in ("light",): return "lightning"
    if j in ("immersive_roulette", "imr", "immersive_roulette_live"): return "immersive"
    return j

def publicar_ordem(jogo: str, ordem: dict, origem: str = "assistente"):
    jogo = _norm_jogo(jogo)
    ordem = validar_ordem(dict(ordem or {}))
    if not ordem:
        data = load_ordens()
        data["_pub_status"] = {"ok": False, "rejeitada": False, "jogo": jogo, "motivo": "ordem vazia ou inválida"}
        return data

    ordem["publicada_em"] = datetime.now().isoformat(timespec="seconds")
    ordem["origem"] = origem
    ordem["aplicada_em"] = None
    JOGOS = ("mega_fire", "lightning", "crazy_time", "immersive")

    def _mutate(data):
        if jogo == "global":
            data["global"] = {**(data.get("global") or {}), **ordem}
            for j in JOGOS:
                data[j] = {**(data.get(j) or {}), **ordem}
            data["atualizado"] = ordem["publicada_em"]
            data["origem"] = origem
            hist = data.get("historico_ordens") or []
            hist.append({"jogo": jogo, "ordem": ordem, "em": data["atualizado"]})
            data["historico_ordens"] = hist[-40:]
            data["_pub_status"] = {"ok": True, "rejeitada": False, "jogo": jogo, "motivo": ordem.get("motivo")}
        elif jogo in JOGOS:
            data[jogo] = {**(data.get(jogo) or {}), **ordem}
            data["atualizado"] = ordem["publicada_em"]
            data["origem"] = origem
            hist = data.get("historico_ordens") or []
            hist.append({"jogo": jogo, "ordem": ordem, "em": data["atualizado"]})
            data["historico_ordens"] = hist[-40:]
            data["_pub_status"] = {"ok": True, "rejeitada": False, "jogo": jogo, "motivo": ordem.get("motivo")}
        else:
            ordem["rejeitada"] = True
            ordem["motivo_rejeicao"] = f"jogo desconhecido: {jogo}"
            hist = data.get("historico_ordens") or []
            hist.append({"jogo": jogo, "ordem": ordem, "em": ordem["publicada_em"], "rejeitada": True})
            data["historico_ordens"] = hist[-80:]
            data["_pub_status"] = {"ok": False, "rejeitada": True, "jogo": jogo, "motivo": ordem["motivo_rejeicao"]}
        return data

    ok, data = with_ordens_lock(_mutate)
    if not ok:
        st = data.get("_pub_status") or {}
        if not st.get("rejeitada"):
            data["_pub_status"] = {"ok": False, "rejeitada": False, "jogo": jogo, "motivo": "falha ao gravar ordens_ia.json (lock/disco)"}
    return data

def registrar_resultado(jogo: str, ok: int, err: int, misses: int, nota: str = "") -> bool:
    item = {
        "jogo": jogo, "ok": ok, "err": err, "misses": misses,
        "taxa": round((ok / (ok + err) * 100), 1) if (ok + err) else None,
        "nota": nota, "em": datetime.now().isoformat(timespec="seconds"),
    }
    def _mutate(data):
        res = data.get("resultados") or []
        res.append(item)
        data["resultados"] = res[-100:]
        return data
    ok_save, _ = with_ordens_lock(_mutate)
    return ok_save

def marcar_ordem_aplicada(jogo: str) -> bool:
    jogo = _norm_jogo(jogo)
    now = datetime.now().isoformat(timespec="seconds")
    def _mutate(data):
        if jogo in data and isinstance(data[jogo], dict):
            data[jogo]["aplicada_em"] = now
        g = data.get("global")
        if isinstance(g, dict) and g.get("publicada_em"):
            # não marca global como aplicada por um único jogo
            pass
        return data
    ok_save, _ = with_ordens_lock(_mutate)
    return ok_save

def _jogo_from_state_name(fname: str):
    """Identifica o jogo pelo nome do arquivo de estado (não pela pasta Logs)."""
    n = (fname or "").lower()
    if "mega_fire" in n or n.startswith("mega"):
        return "mega_fire"
    if "lightning" in n or n.startswith("light"):
        return "lightning"
    if "crazy_time" in n or "crazy" in n:
        return "crazy_time"
    if "immersive" in n:
        return "immersive"
    return None

def analisar_e_gerar_ordens_auto():
    """Lê *state.json em pastas Logs (compartilhada) e identifica o jogo pelo NOME DO ARQUIVO."""
    ordens = []
    vistos = set()  # evita processar o mesmo jogo duas vezes
    for d in _candidate_log_dirs():
        for f in list(d.glob("*state.json")) + list(d.glob("*_state.json")):
            jogo = _jogo_from_state_name(f.name)
            if not jogo or jogo in vistos:
                continue
            ok = err = misses = 0
            try:
                st = json.loads(f.read_text(encoding="utf-8"))
                ok = int(st.get("ok") or 0)
                err = int(st.get("err") or 0)
                misses = int(st.get("misses_total") or 0)
            except Exception:
                continue
            vistos.add(jogo)
            total = ok + err
            taxa = (ok / total * 100) if total else None
            ordem = {"motivo": "auto"}
            if taxa is not None and taxa < 30 and total >= 5:
                ordem.update({
                    "peso_isol": 2.8, "peso_motor": 3.6, "prioritizar_atraso": True,
                    "boost_anti": True, "janela": 3,
                    "motivo": f"auto: taxa {taxa:.0f}% < 30% ({ok}/{total})",
                })
                if str(jogo).startswith("crazy_time"):
                    ordem["reduzir_12"] = True
            elif taxa is not None and taxa >= 40 and total >= 5:
                ordem.update({"peso_motor": 3.2, "janela": 3, "motivo": f"auto: taxa boa {taxa:.0f}%"})
            elif misses >= 8 and err == 0:
                ordem.update({"janela": 3, "motivo": f"auto: misses={misses} sem erro de janela — apertar"})
            if len(ordem) > 1:
                publicar_ordem(jogo, ordem, origem="auto")
                ordens.append((jogo, ordem))
                registrar_resultado(jogo, ok, err, misses, nota=ordem.get("motivo", ""))
    return ordens

def _extrair_json_ordem(texto: str):
    if not texto: return None
    m = re.search(r"```json\s*(\{.*?\})\s*```", texto, re.S)
    if not m:
        m = re.search(r"(\{[^{}]*\"(janela|peso_isol|peso_motor|reduzir_12|boost_anti)\"[^{}]*\})", texto, re.S)
    if not m: return None
    try: return json.loads(m.group(1))
    except Exception: return None

def _chat_openai_compatible(base_url, api_key, model, messages, temperature=0.4):
    if requests is None: raise RuntimeError("requests não instalado")
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    r = requests.post(url, headers=headers, json={
        "model": model, "messages": messages, "temperature": temperature, "stream": False,
    }, timeout=90)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]

def _chat_ollama(ollama_url, model, messages, temperature=0.4):
    if requests is None: raise RuntimeError("requests não instalado")
    r = requests.post(ollama_url.rstrip("/") + "/api/chat", json={
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": temperature},
    }, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
    return (r.json().get("message") or {}).get("content") or ""

def status_backend() -> str:
    cfg = load_cfg()
    prov = (cfg.get("provider") or "xai").lower()
    key = (cfg.get("api_key") or "").strip()
    if prov == "ollama":
        return f"Ollama @ {cfg.get('ollama_url')} model={cfg.get('ollama_model')}"
    if key:
        return f"{prov} model={cfg.get('model')} | chave OK"
    return f"{prov} | SEM CHAVE → modo local + ordens auto"

def explicador_local(pergunta: str, contexto: str) -> str:
    p = (pergunta or "").lower()
    linhas = contexto.splitlines()
    acertos = [l for l in linhas if "ACERTOU" in l]
    erros = [l for l in linhas if "ERROU" in l]
    misses = [l for l in linhas if "MISS |" in l]
    sels = [l for l in linhas if "NOVA_JANELA" in l or "Consenso" in l or "MotorPesado" in l]
    motivos = [l for l in linhas if "MOTIVO_ERRO" in l]
    res = ["### Explicação (modo local)",
           f"Logs: acertos≈{len(acertos)} | erros_janela≈{len(erros)} | misses≈{len(misses)}.",
           "",
           "**Decisão:** MotorPesado (núcleo) + votos Conservadora/Momentum/Estrutural/Caçadora/Lab → Consenso Ponderado fecha os alvos. Meta só ajusta pesos.",
           ""]
    if any(w in p for w in ("por que", "porque", "explica", "escolhe")):
        res.append("**Por que esses alvos:** pontuação ponderada; MotorPesado pesa mais. Lab/isol sobem se a taxa cai.")
        if sels:
            res.append("Sinais recentes:")
            res.extend(f"- `{s[-170:]}`" for s in sels[-4:])
        res.append("")
    if any(w in p for w in ("erro", "errou", "miss")):
        res.append("**Erros/misses:** Miss = fora da sugestão (janela aberta). Erro = janela fechou sem acerto.")
        if motivos:
            res.extend(f"- {m[-190:]}" for m in motivos[-4:])
        elif erros:
            res.extend(f"- {e[-170:]}" for e in erros[-4:])
        else:
            res.append("- Pouco erro de janela ainda; se misses sobem e erros não, a cobertura acerta antes de fechar.")
        res.append("")
    if any(w in p for w in ("melhor", "otimiz", "o que fazer", "libera", "sozinh", "aplica", "ordem")):
        res.append("**Ordens que posso publicar:** janela, peso_isol, peso_motor, boost_anti, priorizar_atraso, reduzir_12 (CT).")
        geradas = analisar_e_gerar_ordens_auto()
        if geradas:
            res.append("**Publicadas agora:**")
            for j, o in geradas:
                res.append(f"- {j}: {o.get('motivo')} → {o}")
        else:
            res.append("_Sem gatilho forte nos estados; peça 'aplica ordem no mega_fire' ou deixe mais ciclos._")
        res.append("")
    if len(res) < 6:
        res.append("Exemplos: 'por que errou?', 'melhora o lightning', 'aplica ordem global'.")
    res.append("")
    res.append("_Com API key as respostas ficam mais ricas; ordens JSON do LLM também são publicadas automaticamente._")
    return "\n".join(res)

def conversar(pergunta: str, historico: list | None = None, auto_aplicar_ordens: bool = True):
    cfg = load_cfg()
    contexto = coletar_contexto(int(cfg.get("max_log_lines") or 80))
    try:
        od = load_ordens()
        contexto += "\n\n## Ordens atuais\n" + json.dumps({
            "mega_fire": od.get("mega_fire"), "lightning": od.get("lightning"), "immersive": od.get("immersive"),
            "crazy_time": od.get("crazy_time"), "global": od.get("global"),
            "resultados_tail": (od.get("resultados") or [])[-8:],
        }, ensure_ascii=False, indent=2)
    except Exception:
        pass

    historico = historico or []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": "Contexto logs/ordens:\n" + contexto},
    ]
    for h in historico[-12:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": pergunta})

    prov = (cfg.get("provider") or "xai").lower()
    key = (cfg.get("api_key") or "").strip()
    temp = float(cfg.get("temperature") or 0.4)
    try:
        if prov == "ollama":
            txt = _chat_ollama(cfg.get("ollama_url") or "http://127.0.0.1:11434",
                               cfg.get("ollama_model") or "llama3.2", messages, temp)
            modo = "llm-ollama"
        elif not key:
            txt = explicador_local(pergunta, contexto)
            modo = "local"
        else:
            if prov in ("openai", "gpt"):
                baseu = cfg.get("openai_base_url") or "https://api.openai.com/v1"
                model = cfg.get("model") or "gpt-4o-mini"
            else:
                baseu = cfg.get("base_url") or "https://api.x.ai/v1"
                model = cfg.get("model") or "grok-2-latest"
            txt = _chat_openai_compatible(baseu, key, model, messages, temp)
            modo = f"llm-{prov}"
    except Exception as e:
        txt = f"[Falha LLM: {e}]\n\nFallback:\n" + explicador_local(pergunta, contexto)
        modo = "local-fallback"

    if auto_aplicar_ordens:
        ordem = _extrair_json_ordem(txt)
        if ordem:
            jogo = ordem.pop("jogo", "global")
            data_pub = publicar_ordem(jogo, ordem, origem=f"chat:{modo}")
            st = (data_pub or {}).get("_pub_status") or {}
            if st.get("ok"):
                txt += f"\n\n✅ Ordem publicada para **{st.get('jogo', jogo)}** (combos aplicam no próximo ciclo)."
            elif st.get("rejeitada"):
                txt += f"\n\n⚠️ Ordem **rejeitada**: {st.get('motivo', 'jogo desconhecido')}."
            else:
                txt += f"\n\n⚠️ Ordem **não gravada**: {st.get('motivo', 'falha desconhecida')}."
        pl = (pergunta or "").lower()
        if any(w in pl for w in ("melhorar", "otimizar", "ajustar sozinho", "aplica", "liberada", "ordem")):
            geradas = analisar_e_gerar_ordens_auto()
            if geradas:
                txt += "\n\n⚙️ Ordens automáticas:\n" + "\n".join(f"- {j}: {o.get('motivo')}" for j, o in geradas)
    return txt, modo
