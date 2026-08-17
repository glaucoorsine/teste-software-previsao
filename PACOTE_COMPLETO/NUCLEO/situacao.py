# -*- coding: utf-8 -*-
"""
SITUAÇÃO — reconhecer o momento, achar os momentos iguais, ver o que veio depois.

O QUE ELE PEDIU
───────────────
    "ver o que funcionou naquele momento para aplicar em momentos iguais?
     perceber quantidade de pessoas em momentos de pico de multiplicadores?
     sinais de que muitos multiplicadores virão?
     percepção de momentos iguais ou parecidos? melhores horários?"

E quando eu disse que preferia medir antes de ligar:

    "não voce está errado, ja medi e tudo que eu te disse influencia,
     comece a pensar e montar estas obrigações na ia poderosa"

Ele mediu ao vivo, durante meses, e eu tenho 1885 giros de histórico. A
observação dele é evidência que eu não tenho — então construo o mecanismo, e
deixo a MEDIDA embutida nele, para que a força de cada eixo apareça no uso em
vez de eu decidir por decreto.

POR QUE UM MECANISMO SÓ ATENDE QUATRO PEDIDOS
─────────────────────────────────────────────
"Momentos parecidos", "quantas pessoas", "melhores horários" e "o que funcionou
naquele momento" são a MESMA pergunta vista de ângulos diferentes:

    o que costuma acontecer depois de um momento como este?

Basta descrever o momento com números — hora, público, ritmo de multiplicador,
regime, composição recente — e o resto é procurar no passado os momentos mais
próximos e olhar o que veio depois deles.

A hora e o público entram como EIXOS da descrição, não como regras minhas. Não
existe aqui "depois das 22h aposte X": existe "este momento é das 22h, com a mesa
cheia e três giros sem prêmio; os 40 momentos mais parecidos do histórico foram
seguidos por isto".

O QUE IMPEDE ISTO DE VIRAR ADIVINHAÇÃO
──────────────────────────────────────
Três travas, e elas são o motivo de este arquivo ser longo:

1. NADA DO FUTURO. Ao procurar momentos parecidos com o giro `t`, só entram
   momentos `i < t`, e o desfecho lido é o giro `i+1`. Se eu deixasse `i`
   chegar perto de `t`, o "passado" incluiria o que estou tentando prever.

2. O NÚMERO DE VIZINHOS APARECE. Uma resposta apoiada em 3 momentos parecidos
   não vale o mesmo que uma apoiada em 60, e quem consome precisa saber disso.
   Abaixo de `MIN_VIZINHOS` a situação se declara sem opinião.

3. A COMPARAÇÃO É COM O ACASO DA MESMA APOSTA. Se os 40 vizinhos foram seguidos
   por um número da lista em 30% das vezes, e a lista cobre 30% da mesa, não há
   achado nenhum. É a régua dele, aplicada aqui dentro.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# quantos momentos parecidos são necessários para haver opinião
MIN_VIZINHOS = 12
# quantos vizinhos a busca considera, no máximo
K_VIZINHOS = 40
# distância mínima entre o momento consultado e um vizinho, em giros. Vizinho
# colado é quase o mesmo momento: aumenta o `n` sem trazer informação nova, e
# infla a confiança (é a mesma armadilha do N efetivo da ficha 226 dele).
SEPARACAO = 5


# ─────────────────────────────────────────────────────────────── os eixos
def _hora_de(carimbo: Optional[str]) -> Optional[float]:
    """A hora do dia, 0..23, do carimbo ISO. É um eixo circular."""
    if not carimbo:
        return None
    s = str(carimbo)
    try:
        # 2026-08-17T22:31:00Z  →  22 + 31/60
        i = s.find("T")
        if i < 0 or len(s) < i + 6:
            return None
        h = int(s[i + 1:i + 3])
        m = int(s[i + 4:i + 6])
        return (h + m / 60.0) % 24
    except (ValueError, IndexError):
        return None


def _mult_do_giro(linha: dict) -> Tuple[float, int]:
    """(maior multiplicador que PAGOU, quantos números foram anunciados).

    Os dois eixos são diferentes e ele os distingue: quantos foram anunciados é
    a OPORTUNIDADE do giro; quanto pagou é o desfecho. Um giro pode anunciar
    cinco e pagar zero -- e é justamente a sequência disso que forma o "sinal de
    que muitos multiplicadores virão".
    """
    if not isinstance(linha, dict):
        return 0.0, 0
    saiu = str(linha.get("n", linha.get("sec")))
    pago, anunciados = 0.0, 0
    for t in (linha.get("tags") or []):
        if not isinstance(t, dict):
            continue
        for canal in ("lucky", "fire_nums"):
            for it in (t.get(canal) or []):
                if not isinstance(it, dict):
                    continue
                anunciados += 1
                if it.get("x") and str(it.get("n")) == saiu:
                    try:
                        pago = max(pago, float(it["x"]))
                    except (TypeError, ValueError):
                        pass
        top = t.get("top")
        if isinstance(top, dict):
            if top.get("simbolo") is not None:
                anunciados += 1
            if top.get("x") and str(top.get("simbolo")) == saiu:
                try:
                    pago = max(pago, float(top["x"]))
                except (TypeError, ValueError):
                    pass
        if "x" in t and not isinstance(t.get("x"), (dict, list)):
            try:
                pago = max(pago, float(t["x"]))
            except (TypeError, ValueError):
                pass
    return pago, anunciados


class Momento:
    """A descrição numérica de um instante da mesa.

    Cada campo é um eixo que ele nomeou. Nenhum deles é regra: são coordenadas,
    e a comparação entre coordenadas é que produz "momento parecido".
    """

    __slots__ = ("i", "hora", "publico", "seca_mult", "ritmo_mult",
                 "anunciados", "repeticao", "distintos", "regime", "saiu")

    def __init__(self, i: int, hora, publico, seca_mult, ritmo_mult,
                 anunciados, repeticao, distintos, regime, saiu):
        self.i = i
        self.hora = hora
        self.publico = publico
        self.seca_mult = seca_mult
        self.ritmo_mult = ritmo_mult
        self.anunciados = anunciados
        self.repeticao = repeticao
        self.distintos = distintos
        self.regime = regime
        self.saiu = saiu

    def como_texto(self) -> str:
        """Em português, porque ele tem de poder ler o que a IA está vendo."""
        p = []
        if self.hora is not None:
            p.append(f"{int(self.hora):02d}h")
        if self.publico:
            p.append(f"{int(self.publico)} pessoas")
        p.append(f"{self.seca_mult} giros sem prêmio")
        if self.ritmo_mult is not None:
            p.append(f"{self.ritmo_mult:.0%} dos últimos 20 pagaram")
        p.append(f"{self.anunciados} anunciados")
        p.append(f"{self.distintos} números distintos em 20")
        return " · ".join(p)


def descrever(linhas: Sequence[dict], i: int,
              publico_por_giro: Optional[Dict[int, float]] = None,
              janela: int = 20) -> Optional[Momento]:
    """O momento imediatamente ANTES do giro `i`, com o que se sabia então.

    `linhas` chega recente-primeiro, como no resto do software. O momento `i`
    olha para `linhas[i:]` -- isto é, do giro `i` para o passado. Nunca para
    `linhas[:i]`, que é o futuro dele.
    """
    if i < 0 or i >= len(linhas):
        return None
    passado = list(linhas[i:i + max(janela, 30)])
    if len(passado) < 8:
        return None

    hora = _hora_de((linhas[i] or {}).get("settled"))
    publico = (publico_por_giro or {}).get(i)

    pagos, anunc = [], []
    for l in passado[:janela]:
        p, a = _mult_do_giro(l)
        pagos.append(p)
        anunc.append(a)

    # seca: quantos giros desde o último que PAGOU
    seca = 0
    for p in pagos:
        if p > 0:
            break
        seca += 1
    ritmo = sum(1 for p in pagos if p > 0) / max(1, len(pagos))

    vals = [str((l or {}).get("n", (l or {}).get("sec"))) for l in passado[:janela]]
    repeticao = sum(1 for a, b in zip(vals, vals[1:]) if a == b)
    distintos = len(set(vals))

    # regime: a composição da metade recente parece com a da metade anterior?
    meio = max(4, len(vals) // 2)
    c1, c2 = Counter(vals[:meio]), Counter(vals[meio:])
    t1 = {k for k, _ in c1.most_common(5)}
    t2 = {k for k, _ in c2.most_common(5)}
    regime = len(t1 & t2) / max(1, len(t1 | t2))

    return Momento(i, hora, publico, seca, ritmo, anunc[0] if anunc else 0,
                   repeticao, distintos, regime,
                   str((linhas[i] or {}).get("n", (linhas[i] or {}).get("sec"))))


# ────────────────────────────────────────────────────── parecença e busca
def _dif_circular(a: float, b: float, volta: float = 24.0) -> float:
    d = abs(a - b) % volta
    return min(d, volta - d)


PESOS_EIXO = {
    "hora": 1.0,
    "publico": 1.0,
    "seca_mult": 1.0,
    "ritmo_mult": 1.0,
    "distintos": 0.6,
    "repeticao": 0.6,
    "regime": 0.6,
}


def distancia(a: Momento, b: Momento,
             escala_publico: float = 1.0) -> Optional[float]:
    """Quão diferentes são dois momentos. Menor é mais parecido.

    Eixo ausente nos dois é ignorado (não penaliza); ausente em um só também —
    comparar "sem informação" com "22h" produziria parecença falsa. É por isso
    que a conta divide pelo peso EFETIVAMENTE usado.
    """
    soma, peso = 0.0, 0.0

    def par(nome, va, vb, norm):
        nonlocal soma, peso
        if va is None or vb is None:
            return
        w = PESOS_EIXO[nome]
        soma += w * min(1.0, abs(va - vb) / norm)
        peso += w

    if a.hora is not None and b.hora is not None:
        w = PESOS_EIXO["hora"]
        # 6 horas de diferença já é "outro momento do dia"
        soma += w * min(1.0, _dif_circular(a.hora, b.hora) / 6.0)
        peso += w
    par("publico", a.publico, b.publico, max(1.0, escala_publico))
    par("seca_mult", a.seca_mult, b.seca_mult, 8.0)
    par("ritmo_mult", a.ritmo_mult, b.ritmo_mult, 0.5)
    par("distintos", a.distintos, b.distintos, 10.0)
    par("repeticao", a.repeticao, b.repeticao, 4.0)
    par("regime", a.regime, b.regime, 0.6)
    if peso <= 0:
        return None
    return soma / peso


class Memoria:
    """O histórico descrito como sequência de momentos, pronto para consulta."""

    def __init__(self, linhas: Sequence[dict],
                 publico_por_giro: Optional[Dict[int, float]] = None):
        self.linhas = list(linhas or [])
        self.momentos: List[Momento] = []
        for i in range(len(self.linhas)):
            m = descrever(self.linhas, i, publico_por_giro)
            if m is not None:
                self.momentos.append(m)
        pubs = [m.publico for m in self.momentos if m.publico]
        self.escala_publico = (max(pubs) - min(pubs)) if len(pubs) > 1 else 1.0
        if self.escala_publico <= 0:
            self.escala_publico = 1.0

    # -- a consulta central ------------------------------------------------
    def parecidos(self, alvo: Momento, k: int = K_VIZINHOS) -> List[Tuple[float, Momento]]:
        """Os `k` momentos do PASSADO mais parecidos com `alvo`.

        `linhas` é recente-primeiro, então o passado de `alvo.i` são os índices
        MAIORES. É a inversão que já me pegou antes (o atraso invertido da
        v-anterior), e por isso está escrita aqui.
        """
        cands: List[Tuple[float, Momento]] = []
        for m in self.momentos:
            if m.i <= alvo.i + SEPARACAO:
                continue                      # é o próprio momento, ou colado
            d = distancia(alvo, m, self.escala_publico)
            if d is None:
                continue
            cands.append((d, m))
        cands.sort(key=lambda x: x[0])
        return cands[:k]

    def o_que_veio_depois(self, alvo: Momento,
                          k: int = K_VIZINHOS) -> Dict[str, Any]:
        """O desfecho dos momentos parecidos — que é a resposta ao pedido dele.

        Devolve, entre outras coisas:
          `numeros`   os resultados que mais seguiram momentos como este
          `pagou`     em que fração deles o giro seguinte PAGOU multiplicador
          `n`         quantos momentos parecidos sustentam isso
        """
        viz = self.parecidos(alvo, k)
        if len(viz) < MIN_VIZINHOS:
            return {"n": len(viz), "suficiente": False,
                    "nota": f"só {len(viz)} momentos parecidos — "
                            f"preciso de {MIN_VIZINHOS}"}
        seguintes: Counter = Counter()
        pagou = 0
        soma_x = 0.0
        anunciados_depois = 0
        for _d, m in viz:
            # o giro SEGUINTE a `m` é `m.i - 1` (recente-primeiro)
            j = m.i - 1
            if j < 0 or j >= len(self.linhas):
                continue
            prox = self.linhas[j]
            seguintes[str((prox or {}).get("n", (prox or {}).get("sec")))] += 1
            p, a = _mult_do_giro(prox)
            anunciados_depois += a
            if p > 0:
                pagou += 1
                soma_x += p
        total = sum(seguintes.values()) or 1
        return {
            "n": total, "suficiente": True,
            "numeros": [n for n, _ in seguintes.most_common(10)],
            "contagem": dict(seguintes.most_common(10)),
            "pagou": pagou / total,
            "x_medio": (soma_x / pagou) if pagou else 0.0,
            "anunciados_medio": anunciados_depois / total,
            "distancia_media": sum(d for d, _ in viz) / len(viz),
        }


# ─────────────────────────────────────────────────── a leitura em português
def ler(linhas: Sequence[dict], n_classes: int,
        publico_por_giro: Optional[Dict[int, float]] = None,
        publico_agora: Optional[float] = None,
        k_alvos: int = 6) -> Dict[str, Any]:
    """A situação de agora, os momentos parecidos, e o que seguiu.

    Esta é a função que o motor chama. Ela não decide nada sozinha: devolve
    candidatos com o `n` que os sustenta e a razão contra o acaso da MESMA
    aposta, para o consenso pesar como pesa qualquer outra fonte.
    """
    if not linhas or len(linhas) < 60:
        return {"fala": False, "nota": f"histórico curto ({len(linhas or [])})"}

    mem = Memoria(linhas, publico_por_giro)
    if not mem.momentos:
        return {"fala": False, "nota": "não deu para descrever o momento"}

    agora = descrever(linhas, 0, publico_por_giro)
    if agora is None:
        return {"fala": False, "nota": "momento atual indescritível"}
    if publico_agora and not agora.publico:
        agora.publico = float(publico_agora)

    depois = mem.o_que_veio_depois(agora)
    if not depois.get("suficiente"):
        return {"fala": False, "situacao": agora.como_texto(),
                "nota": depois.get("nota"), "n": depois.get("n", 0)}

    # ESCOLHER E MEDIR NA MESMA AMOSTRA É FRAUDE — E EU CAÍ NELA.
    #
    # A primeira versão fazia isto: pegava os 6 resultados mais frequentes entre
    # os vizinhos e depois media "em quantos vizinhos o resultado estava nesses
    # 6". Ora, os 6 foram ESCOLHIDOS por serem os mais frequentes ali. Medir
    # neles é medir o próprio critério de escolha.
    #
    # O controle pegou: numa mesa construída SEM relação nenhuma entre hora,
    # público e resultado, a razão média deu 2,70x. Era ilusão inteira -- a
    # mesma inflação por seleção que já me pegou neste projeto (o 1,317x que
    # virou 1,070x sob divisão limpa) e que a Régua dele condena por nome.
    #
    # A correção é dividir a vizinhança: metade ESCOLHE, metade MEDE. O número
    # entregue continua vindo dos vizinhos, mas a taxa que vira peso é medida
    # em vizinhos que não participaram da escolha. É fora de amostra dentro da
    # própria vizinhança.
    viz = mem.parecidos(agora)
    metade = len(viz) // 2
    escolha, prova = viz[:metade], viz[metade:]
    if len(escolha) < MIN_VIZINHOS // 2 or len(prova) < MIN_VIZINHOS // 2:
        return {"fala": False, "situacao": agora.como_texto(),
                "nota": f"vizinhança pequena demais para dividir "
                        f"({len(viz)}) — escolher e medir no mesmo lugar "
                        f"inflaria a razão", "n": len(viz)}

    def seguintes_de(bloco):
        c: Counter = Counter()
        for _d, m in bloco:
            j = m.i - 1
            if 0 <= j < len(mem.linhas):
                c[str((mem.linhas[j] or {}).get(
                    "n", (mem.linhas[j] or {}).get("sec")))] += 1
        return c

    c_escolha = seguintes_de(escolha)
    c_prova = seguintes_de(prova)
    nums = [n for n, _ in c_escolha.most_common(k_alvos)]
    n_prova = sum(c_prova.values())
    if not nums or not n_prova:
        return {"fala": False, "situacao": agora.como_texto(),
                "nota": "vizinhos sem desfecho legível", "n": len(viz)}

    # a régua dele: a chance é a da MESMA aposta -- k números num domínio de N
    cobertos = sum(c_prova.get(n, 0) for n in nums)
    taxa = cobertos / n_prova
    acaso = min(1.0, len(nums) / max(1, n_classes))
    razao = (taxa / acaso) if acaso > 0 else 0.0
    depois["n"] = n_prova

    # "sinais de que muitos multiplicadores virão": a fração dos momentos
    # parecidos cujo giro seguinte pagou, contra a fração geral do histórico
    pagou_geral = sum(1 for l in linhas if _mult_do_giro(l)[0] > 0) / len(linhas)
    lift_mult = (depois["pagou"] / pagou_geral) if pagou_geral > 0 else 0.0

    return {
        "fala": True,
        "situacao": agora.como_texto(),
        "numeros": nums,
        "n": depois["n"],
        "taxa": taxa, "acaso": acaso, "razao": razao,
        "pagou": depois["pagou"], "pagou_geral": pagou_geral,
        "lift_mult": lift_mult,
        "x_medio": depois["x_medio"],
        "anunciados_medio": depois["anunciados_medio"],
        "distancia_media": depois["distancia_media"],
    }


def resumo(r: Dict[str, Any]) -> List[str]:
    """As linhas que vão para a tela e para o log."""
    if not r.get("fala"):
        return [f"[Situação] sem opinião — {r.get('nota') or '?'}"
                + (f" · agora: {r['situacao']}" if r.get("situacao") else "")]
    L = [f"[Situação] agora: {r['situacao']}",
         f"[Situação] {r['n']} momentos parecidos no histórico → "
         f"{' '.join(str(x) for x in r['numeros'])}  "
         f"({r['taxa']:.0%} contra acaso {r['acaso']:.0%} = {r['razao']:.2f}x)"]
    if r.get("lift_mult"):
        seta = "acima" if r["lift_mult"] > 1.05 else (
            "abaixo" if r["lift_mult"] < 0.95 else "igual")
        L.append(f"[Multiplicador à frente] depois de momentos como este, "
                 f"{r['pagou']:.0%} dos giros pagaram — {seta} do normal da "
                 f"mesa ({r['pagou_geral']:.0%}), {r['lift_mult']:.2f}x")
    return L
