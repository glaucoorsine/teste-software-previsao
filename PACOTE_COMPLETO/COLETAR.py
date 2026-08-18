# -*- coding: utf-8 -*-
"""
COLETAR — deixe rodando e ele junta os giros reais das mesas.

    python COLETAR.py                 <- as quatro mesas
    python COLETAR.py lightning       <- so uma
    python COLETAR.py --intervalo 30  <- consulta a cada 30s (padrao 40)

Nao abre janela nenhuma, nao precisa de customtkinter nem de torch. So
`requests`. Pode fechar com Ctrl+C a qualquer momento — nada se perde, ele
grava a cada rodada.

No fim, gere o arquivo pra mandar:

    python COLETAR.py --exportar

Isso escreve `historicos_reais.json` com tudo que foi juntado.
"""
import sys, os, json, time, argparse, signal
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

JOGOS = ["lightning", "mega_fire", "crazy_time", "crazy_time_a", "red_door"]

ap = argparse.ArgumentParser()
ap.add_argument("jogos", nargs="*", default=None)
ap.add_argument("--intervalo", type=int, default=40, help="segundos entre consultas")
ap.add_argument("--exportar", action="store_true", help="so gera o arquivo e sai")
ap.add_argument("--fundo", action="store_true",
                help="puxa TODO o historico disponivel de uma vez e sai (rapido)")
ap.add_argument("--paginas", type=int, default=20, help="profundidade do --fundo (max 20)")
args = ap.parse_args()

alvos = args.jogos or JOGOS
for j in alvos:
    if j not in JOGOS:
        print(f"jogo desconhecido: {j} — use: {', '.join(JOGOS)}")
        raise SystemExit(1)

from fluxo_captura import capturar, buffer_path
from hist_buffer import load, merge as merge_buffer

def carregar(jogo):
    return (load(buffer_path(jogo)) or {}).get("events") or []

# ---------- exportar e sair ----------
if args.exportar:
    # Leva TUDO que so existe porque o software ficou ligado. So os giros nao
    # bastam: as previsoes, os acertos e as sombras das teorias nao dao pra
    # reconstruir depois a partir dos numeros.
    import zipfile, shutil, tempfile

    pacote = {"gerado_em": datetime.now(timezone.utc).isoformat(), "jogos": {}}
    tot = 0
    print("giros coletados:")
    for j in JOGOS:
        evs = carregar(j)
        pacote["jogos"][j] = {"dataset_id": j, "n": len(evs), "events": evs}
        tot += len(evs)
        print(f"  {j:<12} {len(evs):>6}")

    hist_json = ROOT / "historicos_reais.json"
    hist_json.write_text(json.dumps(pacote, ensure_ascii=False, indent=1), encoding="utf-8")

    saida = ROOT / "coleta_completa.zip"
    n_mem = n_cat = n_log = 0
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(hist_json, "historicos_reais.json")

        # 1) previsoes e seus resultados (o placar de verdade)
        print("\nprevisões e resultados:")
        for f in sorted(ROOT.glob("memoria_*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                av = d.get("avaliadas") or []
                ok = sum(1 for a in av if (a.get("resultado") or {}).get("acertou"))
                print(f"  {f.name:<28} {len(av):>5} entradas avaliadas  ({ok} acertos)")
            except Exception:
                print(f"  {f.name:<28} (ilegível)")
            z.write(f, f"motor/{f.name}")
            n_mem += 1
        if not n_mem:
            print("  nenhuma — o software com interface não chegou a rodar?")

        # 2) catalogo de teorias + sombras ao vivo
        try:
            from academia_autonoma.paths_dados import data_root
            raiz_dados = data_root()
            print(f"\nteorias e sombras:  {raiz_dados}")
            for p in raiz_dados.rglob("*"):
                if p.is_file() and p.stat().st_size < 200 * 1024 * 1024:
                    z.write(p, f"academia/{p.relative_to(raiz_dados)}")
                    n_cat += 1
            print(f"  {n_cat} arquivos do catálogo")
        except Exception as e:
            print(f"  [aviso] não consegui empacotar o catálogo: {e}")

        # 3) logs de captura (dedupe, snapshots) — ajudam a auditar
        logs = ROOT / "Logs"
        if logs.is_dir():
            for p in logs.rglob("*"):
                if p.is_file() and p.stat().st_size < 50 * 1024 * 1024:
                    z.write(p, f"logs/{p.relative_to(logs)}")
                    n_log += 1

    mb = saida.stat().st_size / (1024 * 1024)
    print(f"\n{'='*54}")
    print(f"{tot} giros | {n_mem} arquivos de previsões | {n_cat} do catálogo | {n_log} logs")
    print(f"-> {saida.name}  ({mb:.1f} MB)")
    print("\nMANDE O coleta_completa.zip (não só o .json).")
    raise SystemExit(0)

# ---------- puxar o historico fundo de uma vez ----------
# O usuario tem razao: um giro de 1h atras e' o mesmo dado que um giro capturado
# agora. Puxar o historico da a mesma coisa em um minuto, em vez de esperar
# 45s por giro. A coleta continua so serve pra ir alem do que a API guarda.
if args.fundo:
    pags = max(1, min(int(args.paginas), 20))
    print(f"Puxando o historico ate {pags} paginas x 100 giros por mesa.\n")
    tot = 0
    for j in alvos:
        antes = len(carregar(j))
        try:
            r = capturar(j, page_size=100, max_pages=pags, duration=3600)
            if r.get("err") and not r.get("rows"):
                print(f"  {j:<12} FALHOU: {r['err']}")
                continue
        except Exception as e:
            print(f"  {j:<12} ERRO: {type(e).__name__}: {str(e)[:70]}")
            continue
        depois = len(carregar(j))
        tot += depois - antes
        print(f"  {j:<12} {depois:>6} giros  (+{depois-antes})")
    print(f"\n{tot} giros novos.")
    print("\nAgora rode:  python COLETAR.py --exportar")
    print("Se quiser acumular mais, rode este mesmo comando de novo mais tarde")
    print("ou deixe `python COLETAR.py` rodando pra pegar os giros novos.")
    raise SystemExit(0)

# ---------- coleta continua ----------
parar = False
def _sair(*a):
    global parar
    parar = True
    print("\n\nparando... (o que ja foi coletado esta salvo)")
signal.signal(signal.SIGINT, _sair)

print(f"Coletando {', '.join(alvos)} a cada {args.intervalo}s.")
print("Deixe esta janela aberta. Ctrl+C para parar.\n")

inicio = {j: len(carregar(j)) for j in alvos}
for j in alvos:
    print(f"  {j:<12} comecando com {inicio[j]} giros ja guardados")
print()

rodada = 0
erros_seguidos = 0
while not parar:
    rodada += 1
    linha = []
    houve_erro = False
    for j in alvos:
        if parar:
            break
        try:
            r = capturar(j, page_size=50, max_pages=2, duration=120)
            if r.get("err") and not r.get("rows"):
                houve_erro = True
                linha.append(f"{j}=!")
                continue
            # capturar() ja mescla no buffer; so leio o total
            n = len(carregar(j))
            ganho = n - inicio[j]
            linha.append(f"{j}={n}(+{ganho})")
        except Exception as e:
            houve_erro = True
            linha.append(f"{j}=ERRO")
            if rodada <= 2:
                print(f"  [{j}] {type(e).__name__}: {str(e)[:80]}")
    erros_seguidos = erros_seguidos + 1 if houve_erro else 0
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"  {agora}  rodada {rodada:>4}  " + "  ".join(linha))
    if erros_seguidos >= 10:
        print("\n  10 rodadas seguidas com erro — verifique a internet.")
        print("  Continuo tentando; e' so deixar aberto.")
        erros_seguidos = 0
    for _ in range(args.intervalo):
        if parar:
            break
        time.sleep(1)

print()
tot_novo = 0
for j in alvos:
    n = len(carregar(j))
    g = n - inicio[j]
    tot_novo += g
    print(f"  {j:<12} {n:>6} giros  (+{g} nesta sessao)")
print(f"\n{tot_novo} giros novos coletados.")
print("Agora rode:  python COLETAR.py --exportar")
