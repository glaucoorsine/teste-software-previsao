# -*- coding: utf-8 -*-
"""
SONDA — descobre ate onde da pra puxar o historico desta API.

    python SONDA.py

Testa combinacoes de parametros e mostra quantos giros cada uma devolve, e de
quando ate quando. Nao grava nada, so consulta e imprime.

Rode e me mande a saida.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from api_fetch import fetch_api
from fluxo_captura import API_BY_GAME, HEADERS, parse_items_roulette

API = API_BY_GAME["lightning"]

def puxa(params):
    d, err = fetch_api(API, params, headers=HEADERS, timeout=25, max_retries=1)
    if err:
        return None, err
    if isinstance(d, dict):
        c = d.get("content") or d.get("data") or d.get("results") or []
        total = d.get("totalElements") or d.get("total") or d.get("totalPages")
    elif isinstance(d, list):
        c, total = d, None
    else:
        return None, "resposta inesperada"
    return (c, total), None

print("Sondando o historico da Lightning Roulette...\n")

# 1) o que o servidor diz sobre o total disponivel
print("[1] Uma pagina simples, pra ver o que o servidor informa")
r, err = puxa({"page": 0, "size": 100, "sort": "data.settledAt,desc"})
if err:
    print(f"    FALHOU: {err}")
    print("\n    Sem internet ou a API mudou. Me mande esta saida.")
    raise SystemExit(1)
c, total = r
print(f"    veio {len(c)} itens   |   servidor informa total = {total}")
print()

# 2) o parametro duration muda alguma coisa?
print("[2] Testando o parametro `duration` (e' ele que suspeito estar limitando)")
print(f"    {'duration':>12}  {'itens':>6}  {'mais antigo devolvido':>28}")
print("    " + "-" * 52)
for dur in (None, 90, 720, 1440, 10080, 43200, 525600):
    p = {"page": 0, "size": 100, "sort": "data.settledAt,desc"}
    if dur is not None:
        p["duration"] = dur
    r, err = puxa(p)
    if err:
        print(f"    {str(dur):>12}  {'ERRO':>6}  {err[:28]}")
        continue
    c, _ = r
    linhas = parse_items_roulette(c)
    velho = linhas[-1]["settled"] if linhas else "-"
    print(f"    {str(dur):>12}  {len(c):>6}  {str(velho):>28}")
print()

# 3) a paginacao anda de verdade?
print("[3] Testando se a paginacao avanca (mesma janela, paginas seguidas)")
melhor = None
for dur in (43200, 10080, 1440, None):
    p0 = {"page": 0, "size": 100, "sort": "data.settledAt,desc"}
    p3 = {"page": 3, "size": 100, "sort": "data.settledAt,desc"}
    if dur is not None:
        p0["duration"] = dur; p3["duration"] = dur
    a, e1 = puxa(p0)
    b, e2 = puxa(p3)
    if e1 or e2:
        continue
    la = parse_items_roulette(a[0]); lb = parse_items_roulette(b[0])
    if not la or not lb:
        print(f"    duration={dur}: pagina 3 veio vazia -> nao ha tanto historico")
        continue
    difere = la[0]["settled"] != lb[0]["settled"]
    print(f"    duration={str(dur):>7}: pag0 comeca {la[0]['settled']}  |  "
          f"pag3 comeca {lb[0]['settled']}  |  {'AVANCA' if difere else 'REPETE'}")
    if difere and melhor is None:
        melhor = dur
print()

print("=" * 60)
if melhor is not None:
    print(f"MELHOR AJUSTE ENCONTRADO: duration = {melhor}")
    print("Me mande esta saida que eu ajusto o COLETAR.py.")
else:
    print("A paginacao nao avancou em nenhuma combinacao.")
    print("Provavelmente a API so devolve os giros recentes, e o unico jeito")
    print("de juntar volume e' deixar coletando. Me mande esta saida.")
print("=" * 60)
