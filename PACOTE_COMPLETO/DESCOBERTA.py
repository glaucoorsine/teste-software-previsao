# -*- coding: utf-8 -*-
"""
DESCOBERTA — testa métodos novos no histórico, com as regras declaradas antes.

    DESCOBERTA.bat        (ou: python DESCOBERTA.py)

POR QUE AS HIPÓTESES SÃO DECLARADAS ANTES
-----------------------------------------
Procurando o bastante, sempre se acha alguma coisa. Testando 50 ideias num
histórico, umas 2 ou 3 parecem ótimas só por sorte — e é assim que nasce uma
teoria que funciona no papel e perde dinheiro na mesa.

Aqui as hipóteses estão escritas no código, com nome e mecanismo, antes de
olhar o resultado. O número delas é contado e a correção de Holm é aplicada
sobre esse total. Uma delas (H4) é um CONTROLE: a crença de que número
atrasado "está devendo". Se ela passar, o teste está frouxo e o resto do
relatório não vale.

A RÉGUA
-------
Para hipótese que depende da ORDEM dos giros, comparar com a fórmula do acaso
não serve: janelas que se sobrepõem não são independentes e a conta mente.
Então a régua é embaralhar. O mesmo histórico, reordenado mil vezes, dá a
distribuição do que aparece por acaso naquela sequência exata. O p-valor é a
fração de embaralhamentos que igualou ou bateu o resultado real.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
BUFFERS = RAIZ / "Logs" / "hist_buffers"
EMBARALHAMENTOS = 1000
SEMENTE = 20260815

# Ordem FÍSICA das casas na roda europeia — vizinho na roda, não na mesa.
# É essa ordem que importa para viés de fabricação: a bola cai numa região
# do prato, não num intervalo de números.
RODA = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23,
        10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
POS = {n: i for i, n in enumerate(RODA)}


def carregar(jogo: str):
    """Giros do mais antigo para o mais novo, com o multiplicador junto."""
    p = BUFFERS / f"{jogo}.json"
    if not p.is_file():
        return [], []
    ev = (json.loads(p.read_text(encoding="utf-8")) or {}).get("events") or []
    ev = sorted(ev, key=lambda e: str(e.get("settled") or ""))
    nums, mults = [], []
    for e in ev:
        nums.append(str(e.get("n")).strip())
        x = 0
        for t in (e.get("tags") or []):
            if isinstance(t, dict) and t.get("x"):
                try:
                    x = max(x, int(t["x"]))
                except (TypeError, ValueError):
                    pass
        mults.append(x)
    return nums, mults


def inteiros(nums):
    saida = []
    for x in nums:
        try:
            saida.append(int(x))
        except (TypeError, ValueError):
            pass
    return saida


def p_por_embaralhamento(seq, medir, maior_e_melhor=True, n=EMBARALHAMENTOS):
    """Compara o real com o mesmo histórico reordenado n vezes."""
    real = medir(seq)
    if real is None:
        return None, None, None
    rng = random.Random(SEMENTE)
    copia = list(seq)
    batidas = 0
    soma = 0.0
    for _ in range(n):
        rng.shuffle(copia)
        v = medir(copia)
        if v is None:
            continue
        soma += v
        if (v >= real) if maior_e_melhor else (v <= real):
            batidas += 1
    return real, soma / n, (batidas + 1) / (n + 1)


# ─────────────────────────────────────────────────────────── as hipóteses
def H1_setor_fisico(nums):
    """Viés de fabricação: alguma região do prato sai mais que as outras.

    Divide a roda em 6 fatias de 6 casas na ORDEM FÍSICA e mede o desvio da
    fatia mais quente.

    ATENÇÃO À RÉGUA: esta contagem NÃO depende da ordem dos giros, então
    embaralhar o histórico devolve exatamente o mesmo número e o p-valor sai
    1.000 sempre — foi o que aconteceu na primeira versão deste arquivo. Para
    hipótese de contagem a régua certa é sortear giros novos de uma roda
    justa, e é isso que `p_por_sorteio` faz.
    """
    ns = [n for n in inteiros(nums) if n in POS]
    if len(ns) < 200:
        return None
    fatia = Counter(POS[n] * 6 // len(RODA) for n in ns)
    esperado = len(ns) / 6
    return max(fatia.values()) / esperado if esperado else None


def H1b_numero_quente(nums):
    """O número mais frequente sai mais do que a roda justa permitiria.

    O sinal mais direto de roda viciada: uma casa específica, não uma região.
    Também é contagem, então usa a mesma régua de sorteio.
    """
    ns = [n for n in inteiros(nums) if n in POS]
    if len(ns) < 200:
        return None
    return max(Counter(ns).values()) / (len(ns) / 37)


def p_por_sorteio(seq, medir, n=EMBARALHAMENTOS):
    """Régua para hipótese de CONTAGEM: sorteia giros de uma roda justa.

    Embaralhar não serve aqui — reordenar não muda quantas vezes cada número
    apareceu. O que responde "isso seria normal numa roda sem defeito?" é
    gerar histórico novo do mesmo tamanho, com todas as casas equiprováveis.
    """
    real = medir(seq)
    if real is None:
        return None, None, None
    ns = [x for x in inteiros(seq) if x in POS]
    rng = random.Random(SEMENTE)
    batidas = 0
    soma = 0.0
    for _ in range(n):
        falso = [str(rng.choice(RODA)) for _ in ns]
        v = medir(falso)
        if v is None:
            continue
        soma += v
        if v >= real:
            batidas += 1
    return real, soma / n, (batidas + 1) / (n + 1)


def H2_vizinho_na_roda(nums):
    """Assinatura do crupiê: o giro seguinte cai perto do anterior NA RODA.

    "Perto" é até 3 casas de distância no prato, para cada lado — 7 das 37
    casas, ou 18,9% por acaso.
    """
    ns = [n for n in inteiros(nums) if n in POS]
    if len(ns) < 100:
        return None
    perto = 0
    for a, b in zip(ns, ns[1:]):
        d = abs(POS[a] - POS[b])
        d = min(d, len(RODA) - d)
        if d <= 3:
            perto += 1
    return perto / (len(ns) - 1)


def H3_repete_o_mesmo(nums):
    """O mesmo número sai duas vezes seguidas mais que o acaso."""
    ns = inteiros(nums)
    if len(ns) < 100:
        return None
    return sum(1 for a, b in zip(ns, ns[1:]) if a == b) / (len(ns) - 1)


def H4_atrasado_esta_devendo(nums):
    """CONTROLE — a crença de que número ausente há muito tempo vai sair.

    Isto é falso numa roda justa, e é falso também numa viciada: lá o número
    quente sai MAIS, não o frio. Se passar no teste, a régua está frouxa e o
    resto deste relatório não vale nada.
    """
    ns = inteiros(nums)
    if len(ns) < 300:
        return None
    ultimo = {}
    acertos = tentativas = 0
    for i, n in enumerate(ns):
        if i >= 200:
            atrasados = [x for x in range(37)
                         if i - ultimo.get(x, -74) > 74]     # 2x o esperado
            if atrasados:
                tentativas += 1
                if n in atrasados[:7]:
                    acertos += 1
        ultimo[n] = i
    return acertos / tentativas if tentativas else None


def H5_multiplicador_chama_multiplicador(nums, mults):
    """Percepção dele: depois de um multiplicador alto, vêm outros.

    Mede a chance de aparecer multiplicador alto nos 5 giros seguintes a um
    alto, contra a chance geral de aparecer alto em 5 giros quaisquer.
    """
    altos = [i for i, x in enumerate(mults) if x >= 50]
    if len(altos) < 8:
        return None
    depois = 0
    for i in altos:
        if any(x >= 50 for x in mults[i + 1:i + 6]):
            depois += 1
    return depois / len(altos)


def H6_top_slot_bate(nums, tops):
    """O top slot bate no símbolo que a roda para, mais que o acaso."""
    pares = [(s, n) for s, n in zip(tops, nums) if s]
    if len(pares) < 100:
        return None
    return sum(1 for s, n in pares if s == n) / len(pares)


def H7_dois_iguais_puxam_multiplicador(nums, mults):
    """Percepção dele: dois resultados iguais seguidos → multiplicador."""
    gatilhos = [i for i in range(1, len(nums) - 1) if nums[i] == nums[i - 1]]
    if len(gatilhos) < 15:
        return None
    return sum(1 for i in gatilhos if mults[i + 1] >= 5) / len(gatilhos)


def H8_seca_longa_puxa_alto(nums, mults):
    """Percepção dele: depois de uma seca longa vem um multiplicador alto."""
    secas, atual = [], 0
    for i, x in enumerate(mults):
        if x >= 20:
            if atual >= 25:
                secas.append(i)
            atual = 0
        else:
            atual += 1
    if len(secas) < 8:
        return None
    return sum(1 for i in secas if mults[i] >= 50) / len(secas)


def holm(pvalores):
    """Corrige por quantas hipóteses foram testadas, sem ser cego como o
    Bonferroni puro: ordena e exige mais só de quem está na frente."""
    itens = sorted((p, i) for i, p in enumerate(pvalores) if p is not None)
    m = len(itens)
    saida = [None] * len(pvalores)
    maior = 0.0
    for k, (p, i) in enumerate(itens):
        aj = min(1.0, max(maior, p * (m - k)))
        maior = aj
        saida[i] = aj
    return saida


def main() -> int:
    print()
    print("=" * 74)
    print(" DESCOBERTA — métodos novos, com as regras declaradas antes")
    print("=" * 74)

    linhas, ps = [], []

    for jogo in ("lightning", "mega_fire", "crazy_time", "crazy_time_a", "red_door"):
        nums, mults = carregar(jogo)
        if not nums:
            continue
        print(f"\n  {jogo.upper()} — {len(nums)} giros")
        # contagem → régua de sorteio; sequência → régua de embaralhamento
        for nome, fn, regua in (
                ("H1 setor físico da roda", H1_setor_fisico, p_por_sorteio),
                ("H1b número quente", H1b_numero_quente, p_por_sorteio),
                ("H2 vizinho na roda (crupiê)", H2_vizinho_na_roda, p_por_embaralhamento),
                ("H3 repete o mesmo número", H3_repete_o_mesmo, p_por_embaralhamento),
                ("H4 atrasado 'devendo' (CONTROLE)", H4_atrasado_esta_devendo, p_por_embaralhamento)):
            real, acaso, p = regua(nums, fn)
            if real is None:
                print(f"     {nome:<34} amostra curta")
                continue
            print(f"     {nome:<34} {real:.3f}  acaso {acaso:.3f}  "
                  f"{real/acaso if acaso else 0:.2f}x  p={p:.3f}")
            linhas.append((jogo, nome, real, acaso, p))
            ps.append(p)

    nums, mults = carregar("crazy_time")
    if nums:
        print(f"\n  CRAZY_TIME — {len(nums)} giros")
        for nome, fn in (
                ("H5 multiplicador chama multiplicador",
                 lambda s: H5_multiplicador_chama_multiplicador(s, mults)),
                ("H7 dois iguais puxam multiplicador",
                 lambda s: H7_dois_iguais_puxam_multiplicador(s, mults)),
                ("H8 seca longa puxa alto",
                 lambda s: H8_seca_longa_puxa_alto(s, mults))):
            real, acaso, p = p_por_embaralhamento(nums, fn, True)
            if real is None:
                print(f"     {nome:<34} amostra curta ainda")
                continue
            print(f"     {nome:<34} {real:.3f}  acaso {acaso:.3f}  "
                  f"{real/acaso if acaso else 0:.2f}x  p={p:.3f}")
            linhas.append(("crazy_time", nome, real, acaso, p))
            ps.append(p)
        print(f"     {'H6 top slot bate':<34} sem dado ainda — o símbolo do "
              f"top slot passou a ser guardado agora")

    print()
    print("=" * 74)
    aj = holm(ps)
    sobreviveram = [(l, a) for l, a in zip(linhas, aj) if a is not None and a < 0.05]
    print(f" {len(ps)} hipóteses testadas. Corrigindo por esse total (Holm):")
    print()
    for (jogo, nome, real, acaso, p), a in zip(linhas, aj):
        marca = "SOBREVIVEU" if (a is not None and a < 0.05) else "—"
        print(f"   {marca:<11} {jogo:<11} {nome:<34} p={p:.3f}  ajustado={a:.3f}")
    print()
    controles = [l for l, a in zip(linhas, aj)
                 if "CONTROLE" in l[1] and a is not None and a < 0.05]
    if controles:
        print(" ⚠ O CONTROLE PASSOU. A régua está frouxa — ignore o resto.")
    elif sobreviveram:
        print(" O que sobreviveu merece virar teoria e ser testado AO VIVO,")
        print(" na sombra, antes de valer aposta. Achado em histórico é")
        print(" candidato, não conclusão.")
    else:
        print(" Nada sobreviveu à correção. Não é fracasso: é o histórico")
        print(" dizendo que essas ideias, nesta amostra, não se distinguem")
        print(" do acaso. Mais giros podem mudar isso.")
    print("=" * 74)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
