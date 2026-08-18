# -*- coding: utf-8 -*-
"""
PREVER — a previsão na tela ANTES da próxima rodada, e a acertividade contando.

    python PREVER.py lightning
    python PREVER.py mega_fire --k 8
    python PREVER.py crazy_time

O QUE ELE COBROU, E É O QUE IMPORTA
───────────────────────────────────
    "é a previsão que importa, é a entrega de cinco a dez [números]...
     acertividade. E mostrar a previsão antes da próxima rodada."

Tudo o mais neste projeto — as 48 famílias, os controles, a régua — existe
para que estas duas linhas sejam verdadeiras:

    1. os números aparecem ANTES do giro, não depois
    2. o placar de acertos é medido, não declarado

COMO O "ANTES" É GARANTIDO
──────────────────────────
A previsão é carimbada com o `head_id` do último giro conhecido no momento em
que foi feita. Quando o giro seguinte chega, o programa confere que o alvo é
POSTERIOR ao carimbo. Se não for — se a captura trouxe um giro que já existia
quando a previsão saiu — aquela rodada não conta para o placar e a tela diz
por quê.

Sem esse carimbo, bastaria um atraso na captura para o software "acertar"
prevendo o que já tinha saído. É o vazamento que a F36 do Tratado dele
descreve, e é o erro que mais infla acertividade sem ninguém perceber.

O PLACAR
────────
Contra o acaso do MESMO tamanho da lista: apostar 10 números acerta mais que
apostar 5 por construção, não por mérito. A tela mostra a razão — 1,00 é o
acaso — e o intervalo, porque taxa sem intervalo em 20 rodadas não quer dizer
nada.

E o placar alimenta de volta a agregação dele: a perda de cada família entra
na F45 (peso por perda acumulada), com a vigília da F46 (só conta quando a
família falou). Quem erra encolhe sozinho, sem eu podar ninguém.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from NUCLEO import agregacao as A  # noqa: E402
from NUCLEO import base as B  # noqa: E402
from NUCLEO import canal_anunciado as C  # noqa: E402
from NUCLEO import leituras as L  # noqa: E402
from NUCLEO import veto as V  # noqa: E402

MESAS = ("mega_fire", "lightning", "crazy_time", "crazy_time_a", "red_door")
DIARIO = RAIZ / "Logs" / "nucleo_previsoes.jsonl"


# ═══════════════════════════════════════════════════════════ o placar

class Placar:
    """Acertos contra o acaso do mesmo tamanho, com intervalo."""

    def __init__(self, n_classes: int):
        self.n_classes = n_classes
        self.acertos = 0
        self.rodadas = 0
        self.esperado = 0.0
        self.descartadas = 0
        self.previsoes: List[List[str]] = []
        self.emitiu: List[bool] = []
        self.certos: List[bool] = []
        self.perdas: Dict[str, float] = defaultdict(float)
        self.vigilia: Dict[str, int] = defaultdict(int)
        self.memoria: Dict[str, float] = {}

    def registrar(self, previsao: List[str], alvo: str,
                  palpites_por_familia: Dict[str, List[str]]):
        """`palpites_por_familia` é FAMÍLIA → classes que ela apontou.

        Passar aqui o mapa invertido (classe → famílias) faz o acerto comparar
        o número sorteado contra nomes de família, que nunca casam: a perda vai
        para chaves erradas e a agregação dele fica cega. Já aconteceu.
        """
        self.rodadas += 1
        self.esperado += len(set(previsao)) / self.n_classes
        acertou = str(alvo) in previsao
        self.previsoes.append(list(previsao))
        self.emitiu.append(bool(previsao))
        self.certos.append(acertou)
        if acertou:
            self.acertos += 1
        # a perda de cada família, só nos giros em que ela falou (F46)
        certos = {}
        for fam, classes in (palpites_por_familia or {}).items():
            self.vigilia[fam] += 1
            ok = str(alvo) in classes
            self.perdas[fam] += 0.0 if ok else 1.0
            certos[fam] = ok
        self.memoria = A.f48_memoria(self.memoria, certos)
        return acertou

    @property
    def acaso(self) -> float:
        return self.esperado / self.rodadas if self.rodadas else 0.0

    @property
    def taxa(self) -> float:
        return self.acertos / self.rodadas if self.rodadas else 0.0

    @property
    def razao(self) -> float:
        return self.taxa / self.acaso if self.acaso else 0.0

    def intervalo(self) -> tuple:
        """Wilson 90% — taxa sem intervalo em 20 rodadas não diz nada."""
        n = self.rodadas
        if not n:
            return (0.0, 1.0)
        z = 1.645
        p = self.taxa
        d = 1 + z * z / n
        c = p + z * z / (2 * n)
        r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))

    def constituicao(self) -> Dict[str, Any]:
        """A família 12 da Régua dele, aplicada ao placar desta sessão.

        R12-VET-05 decide; as outras quatro alimentam a decisão. É a trava que
        me faltava: eu vinha concluindo a partir do placar, e o placar sozinho
        não tem direito de concluir.
        """
        pe = V.previsoes_efetivas(self.previsoes)
        # o suporte efetivo é o MENOR entre rodadas independentes e previsões
        # distintas: 200 rodadas de uma previsão só não são 200 testes
        ne_acertos = V.tamanho_efetivo([1.0 if c else 0.0 for c in self.certos])
        ne = {"n_eff": min(ne_acertos["n_eff"], pe["n_eff"]),
              "motivo": pe["motivo"] + " · " + ne_acertos["motivo"]}

        portas = {
            "sem rodada descartada em excesso":
                self.descartadas <= max(2, self.rodadas // 10),
            "previsões não são uma só":
                pe["distintas"] >= 3 or self.rodadas < 5,
        }
        integr = V.porta_de_integridade(portas)

        # o controle obrigatório da R12-VET-03: o envelope é o próprio acaso
        # binomial do tamanho apostado, simulado
        env = []
        if self.rodadas >= 5:
            import random as _r
            rnd = _r.Random(20260816)
            p_acaso = self.acaso
            for _ in range(200):
                h = sum(1 for _ in range(self.rodadas) if rnd.random() < p_acaso)
                env.append((h / self.rodadas) / p_acaso if p_acaso else 0.0)
        ctrl = V.controle_negativo_obrigatorio(self.razao, env)

        sil = V.direito_de_silencio(self.certos, self.emitiu)
        d = V.decisao(integr, ctrl, ne, n_eff_minimo=30.0)
        return {"decisao": d, "integridade": integr, "controle": ctrl,
                "suporte": ne, "previsoes": pe, "silencio": sil}

    def veredito(self) -> str:
        """A frase que impede a razão de ser lida como vitória.

        Ele avisou, e com razão: "cuidado com essas suas métricas aí que já
        atrapalhou antes". Três vezes uma régua minha produziu achado que
        evaporou depois. O problema não é só a conta — é que "1,20x" na tela
        PARECE resultado, e quem lê não tem como saber que o intervalo cobre
        o acaso inteiro.

        Então a tela não mostra só o número. Mostra o que ele significa, e o
        critério é o intervalo, não a razão: enquanto o IC90 contiver o acaso,
        não há nada a comemorar, por mais bonita que esteja a razão.
        """
        if self.rodadas < 20:
            return (f"AINDA NÃO DÁ PARA DIZER — {self.rodadas} rodadas. "
                    f"Antes de 20 a taxa é ruído.")
        lo, hi = self.intervalo()
        if lo > self.acaso:
            return "ACIMA DO ACASO — o intervalo inteiro está acima."
        if hi < self.acaso:
            return "ABAIXO DO ACASO — o intervalo inteiro está abaixo."
        return ("INDISTINGUÍVEL DO ACASO — o intervalo cobre o acaso, "
                "então a razão acima não é resultado.")

    def linha_constitucional(self) -> str:
        """O veredito da família 12 dele, que manda mais que o intervalo."""
        if self.rodadas < 5:
            return ""
        c = self.constituicao()
        d = c["decisao"]
        return (f"  régua (R12-VET-05): {d['decisao']} — {d['porque'][:76]}\n"
                f"  suporte efetivo: {c['previsoes']['motivo'][:74]}")

    def linha(self) -> str:
        if not self.rodadas:
            return "  placar: primeira rodada ainda não fechou"
        lo, hi = self.intervalo()
        s = (f"  placar: {self.acertos}/{self.rodadas} = {self.taxa:.1%}  "
             f"(acaso {self.acaso:.1%})  {self.razao:.2f}x  "
             f"IC90 {lo:.1%}–{hi:.1%}")
        if self.descartadas:
            s += f"  · {self.descartadas} descartadas por carimbo"
        extra = self.linha_constitucional()
        return s + "\n  " + self.veredito() + (("\n" + extra) if extra else "")


# ═══════════════════════════════════════════════════════ a previsão

def _cacador(historico: List[dict], jogo: str, k: int) -> tuple:
    """O palpite do Caçador de Multiplicador — a única fonte que decide.

    Devolve `(numeros, nota)`. Lista vazia quando ele não fala: mesa sem
    multiplicador, histórico sem rodada de sorteio, ou nenhum voto. Nesses
    casos a previsão fica vazia mesmo, e a nota diz por quê.
    """
    try:
        from academia_autonoma.previsores_multiplicador import (
            prever as _pm, tem_multiplicador as _tem)
    except Exception as e:
        return [], f"Caçador indisponível ({type(e).__name__})"
    if not _tem(jogo):
        return [], "esta mesa não tem multiplicador"
    try:
        r = _pm(jogo, historico, k=k) or {}
    except Exception as e:
        return [], f"Caçador falhou ({type(e).__name__})"
    nums = [str(x) for x in (r.get("consenso") or [])][:k]
    if not nums:
        return [], (r.get("nota") or "o Caçador não votou nesta volta")
    return nums, (f"{len(r.get('por_ia') or {})} IAs + "
                  f"{len(r.get('por_agente') or {})} agentes, "
                  f"{r.get('n_rodadas', 0)} rodadas de sorteio lidas")


def prever(historico: List[dict], jogo: str, k: int,
           placar: Optional[Placar] = None) -> Dict[str, Any]:
    """Os k números, com quem votou em cada um."""
    n_classes = B.classes_de(jogo)
    serie = C.serie_de_resultados(C.rodadas(historico, jogo))
    mults = [max([v for v in (r.get("x") or {}).values() if v] or [0.0])
             for r in C.rodadas(historico, jogo)]

    roda = L.executar(serie, n_classes, {"mults": mults}, k=k)
    pesos = dict(roda["pesos"])

    canal = C.ler(historico, jogo, n_classes, k=k)
    if canal.get("vota"):
        razao = float((canal.get("acoplamento") or {}).get("razao") or 1.0)
        w = max(0.0, min(1.0, razao - 1.0))
        for nome, peso in (canal.get("pesos") or {}).items():
            pesos[nome] = {c: v * w for c, v in peso.items()}

    ag = A.consenso(pesos,
                    dict(placar.perdas) if placar else None,
                    dict(placar.vigilia) if placar else None,
                    dict(placar.memoria) if placar else None,
                    k=k)
    # O QUE CADA FAMILIA APONTOU -- indexado por FAMILIA.
    #
    # `ag["quem"]` e o inverso: classe -> familias que votaram nela. Serve para
    # a tela ("quem escolheu este numero"), e nao serve para o placar. Eu estava
    # passando um pelo outro, e ai `Placar.registrar` comparava o numero sorteado
    # contra uma lista de NOMES DE FAMILIA -- nunca casava. A perda ia parar em
    # chaves erradas e a F45/F46/F48 ficavam cegas: o peso nunca se movia.
    palpites = {f: list(v) for f, v in (roda.get("palpites") or {}).items()}
    if canal.get("vota"):
        palpites.update({f: list(v)
                         for f, v in (canal.get("palpites") or {}).items()})

    # ─────────────────────────────────────────────────────────────────────
    # QUEM ESCOLHE É O CAÇADOR — AQUI TAMBÉM.
    #
    # Este arquivo nasceu do pedido de fazer os três PDFs serem a base, e ele
    # faz: as leituras F01–F44 rodam, o canal anunciado vota, a agregação F45
    # pesa. Só que a decisão final dele saía por conta própria, enquanto a
    # tela ao vivo já entregava o número do Caçador.
    #
    # Isso é o software com duas respostas para a mesma pergunta. Se ele
    # olhasse as duas no mesmo giro, veria listas diferentes e nenhuma forma
    # de saber qual é "a" previsão. A ordem foi uma só: "somente o Caçador de
    # Multiplicador escolhendo os números para todos os jogos".
    #
    # Então o consenso dos PDFs continua sendo calculado inteiro — ele é quem
    # dá o "quem votou", a robustez e a entropia — mas o número entregue é o
    # do Caçador. Quando o Caçador não fala, aqui também não sai número: cair
    # para a lista dos PDFs seria régua reserva, que é exatamente o que ele
    # mandou tirar.
    do_cacador, nota_cacador = _cacador(historico, jogo, k)
    return {
        "numeros": do_cacador if do_cacador else [],
        "numeros_pdfs": ag["ordem"][:k],
        "cacador": nota_cacador,
        # o placar bruto do consenso -- e sobre ele que a entropia da
        # R04-UNC-04 e medida, para saber se a concentracao e genuina ou se
        # pegar o topo seria ordenacao arbitraria de empate
        "placar": ag["placar"],
        "quem": ag["quem"],
        "palpites": palpites,
        "robustez": ag["robustez"],
        "roda": roda,
        "canal": canal,
        "n_classes": n_classes,
        "n_giros": len(serie),
    }


def mostrar(p: Dict[str, Any], jogo: str, k: int) -> None:
    agora = datetime.now().strftime("%H:%M:%S")
    print()
    print("═" * 66)
    print(f"  {jogo.upper()}   {agora}   {p['n_giros']} giros lidos")
    print("═" * 66)
    print()
    if not p["numeros"]:
        print(f"  PRÓXIMO GIRO — sem número.")
        print(f"      o Caçador não votou: {p.get('cacador') or '?'}")
        print(f"      (os PDFs apontariam {p.get('numeros_pdfs') or []}, mas")
        print(f"       quem decide é o Caçador — sem ele não há aposta)")
        print()
    else:
        print(f"  PRÓXIMO GIRO — {k} números  ·  Caçador de Multiplicador:")
        print()
        linha = "   ".join(f"{n:>2}" for n in p["numeros"])
        print(f"      {linha}")
        print()
        print(f"      {p.get('cacador') or ''}")
        _pdfs = p.get("numeros_pdfs") or []
        _junto = [n for n in p["numeros"] if n in _pdfs]
        print(f"      os PDFs concordam em {len(_junto)} de {len(p['numeros'])}"
              f"  ({' '.join(str(x) for x in _junto) if _junto else '—'})")
    print()
    for n in (p.get("numeros_pdfs") or [])[:3]:
        rob = p["robustez"].get(n, 0)
        quem = p["quem"].get(n, [])
        fam = quem[0].replace("CANAL_", "") if quem else ""
        end = B.endereco(fam, jogo) if fam else ""
        print(f"      {n:>2}  {len(quem):2d} leituras · robustez {rob:.0%}"
              + (f"  ·  {end[:44]}" if end else ""))
    print()
    r = p["roda"]
    print(f"  roda: {r['apontaram']}/{r['total']} famílias falaram", end="")
    c = p["canal"]
    if c.get("vota"):
        ac = c.get("acoplamento") or {}
        print(f"   ·   canal: {c.get('apontaram')}/{c.get('total')} "
              f"(acoplamento {ac.get('razao', 0):.2f}x)")
    else:
        print(f"   ·   canal: fora — {(c.get('motivo') or '')[:40]}")


def anotar(reg: Dict[str, Any]) -> None:
    try:
        DIARIO.parent.mkdir(parents=True, exist_ok=True)
        with DIARIO.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════ o laço

def main() -> int:
    ap = argparse.ArgumentParser(description="Previsão do núcleo, antes do giro.")
    ap.add_argument("mesa", choices=MESAS)
    ap.add_argument("--k", type=int, default=10,
                    help="quantos números (ele pediu de 5 a 10; padrão 10)")
    ap.add_argument("--intervalo", type=int, default=20,
                    help="segundos entre leituras da captura")
    ap.add_argument("--rodadas", type=int, default=0,
                    help="parar depois de N rodadas fechadas (0 = sem limite)")
    a = ap.parse_args()
    k = max(1, min(a.k, 20))

    from fluxo_captura import capturar

    print(f"\n  Núcleo — {a.mesa}, {k} números por rodada.")
    print("  A previsão sai ANTES do giro; o placar conta só o que fechou depois.")
    print(B.resumo())

    placar = Placar(B.classes_de(a.mesa))
    pendente: Optional[Dict[str, Any]] = None

    while True:
        try:
            cap = capturar(a.mesa, duration=60)
        except Exception as e:
            print(f"  [captura] {type(e).__name__}: {e}")
            time.sleep(a.intervalo)
            continue

        rows = cap.get("rows") or []
        if cap.get("err"):
            print(f"  [captura] {cap['err']}")
        if not rows:
            time.sleep(a.intervalo)
            continue

        topo = str(rows[0].get("event_id") or rows[0].get("id") or "")

        # ── fecha a previsão anterior, se o giro é MESMO posterior ─────
        if pendente and topo and topo != pendente["carimbo"]:
            alvo = rows[0].get("n", rows[0].get("sec"))
            ids = [str(r.get("event_id") or r.get("id") or "") for r in rows]
            # o carimbo tem que estar no histórico, e DEPOIS do alvo
            if pendente["carimbo"] in ids[1:]:
                acertou = placar.registrar(pendente["numeros"], str(alvo),
                                           pendente["palpites"])
                print(f"\n  → saiu {alvo}   {'ACERTOU' if acertou else 'errou'}")
                print(placar.linha())
                anotar({"t": datetime.now().isoformat(timespec="seconds"),
                        "mesa": a.mesa, "previsao": pendente["numeros"],
                        "alvo": str(alvo), "acertou": acertou,
                        "k": k, "n_classes": placar.n_classes,
                        "acertos": placar.acertos, "rodadas": placar.rodadas,
                        "razao": round(placar.razao, 4)})
            else:
                placar.descartadas += 1
                print(f"\n  → giro {alvo} descartado: não é posterior ao "
                      f"carimbo da previsão (F36 — vazamento)")
            pendente = None
            if a.rodadas and placar.rodadas >= a.rodadas:
                break

        # ── faz a próxima previsão, e carimba ──────────────────────────
        if pendente is None:
            p = prever(rows, a.mesa, k, placar)
            if p["numeros"]:
                mostrar(p, a.mesa, k)
                if placar.rodadas:
                    print(placar.linha())
                pendente = {"numeros": p["numeros"],
                            "palpites": p["palpites"],
                            "carimbo": topo}
            else:
                print(f"  aguardando histórico ({p['n_giros']} giros)")

        time.sleep(a.intervalo)

    print("\n" + placar.linha())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
