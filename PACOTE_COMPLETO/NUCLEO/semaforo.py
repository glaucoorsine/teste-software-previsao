# -*- coding: utf-8 -*-
"""
SEMÁFORO — "é bom momento?", com os porquês, e o aviso só quando for verde.

O QUE ELE PEDIU, EM QUATRO MENSAGENS SEGUIDAS
─────────────────────────────────────────────
    "a ia tem que saber, olha aqui é um momento bom por isso por isso por isso,
     ai ela preve e da sinal verde. senão ela fica dando sinal e eu nunca saberei
     se é bom momento ou nao"

    "bom momento é quantidade maior de pessoas por exemplo, existem muitos
     multiplicadores no historico, e muitas outras informações que ela tem que
     ver, analisar, medir, saber e opinar"

    "ela tem que olhar, porque errei tanto? o que influenciou? o momento é mesmo
     pra usar aquelas regras? quais outras deixei de usar?"

    "perceber a sugestao, está repetindo demais? sim? porque? e mudar ou nao"

    "só deve ser enviado o sinal para o ntfy quando for verde, pode ficar
     prevendo, mas só envia quando for verde"

O PEDIDO É PRECISO E RESOLVE UM PROBLEMA REAL: uma tela que sempre mostra número
não distingue "achei algo" de "não achei nada e mostrei o melhor que tinha". O
semáforo é o que faltava para a previsão significar alguma coisa.

A REGRA QUE IMPEDE ISTO DE VIRAR ASTROLOGIA
───────────────────────────────────────────
"Mesa cheia" só é motivo para verde se, NESTA mesa, o público tiver separado
acerto de erro na medição (`forca_dos_eixos`). Se o público não separa aqui, ele
não vira razão — nem que esteja lotada.

Isso é o oposto de eu escrever "mesa cheia = bom". Cada motivo carrega a medida
que o autoriza, e um motivo sem medida entra como observação, não como razão.
Assim o verde não é opinião minha nem promessa: é a lista do que a própria mesa
já mostrou que importa, presente agora.

E O VERDE NÃO PROMETE ACERTO
────────────────────────────
Verde quer dizer "as condições que esta mesa associou a acerto estão presentes,
e há base para dizer isso". Não quer dizer que vai acertar. A diferença importa
porque ele vai receber isso no celular e agir.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

VERDE, AMARELO, VERMELHO = "VERDE", "AMARELO", "VERMELHO"

# quantos motivos medidos são necessários para o verde
MIN_MOTIVOS_VERDE = 2
# `d` mínimo para um eixo poder virar motivo (abaixo disso ele quase não separa)
D_MINIMO = 0.25
# quantas repetições da mesma aposta antes de reclamar
REPETE_DEMAIS = 4


def _forte(medida: Optional[dict], eixo: str) -> Optional[float]:
    """O `d` medido deste eixo NESTA mesa, ou None se não foi medido."""
    if not medida:
        return None
    d = ((medida.get("detalhe") or {}).get(eixo) or {}).get("d")
    try:
        return float(d) if d is not None else None
    except (TypeError, ValueError):
        return None


def avaliar(situacao: Optional[dict] = None,
            publico: Optional[float] = None,
            pico_publico: Optional[float] = None,
            ritmo_agora: Optional[float] = None,
            ritmo_normal: Optional[float] = None,
            ultimas_sugestoes: Optional[Sequence[Sequence[Any]]] = None,
            placar_recente: Optional[dict] = None,
            regime: Optional[dict] = None) -> Dict[str, Any]:
    """A cor do momento, com o porquê de cada coisa.

    Nada aqui inventa: cada motivo cita a medida que o sustenta, e o que não tem
    medida entra como observação sem virar razão.

    `regime` é o que `regime_multiplicador.ler()` mediu -- a densidade em 500, o
    limiar 45 dele, a magnitude recente, a inversão e a seca. Ele chamou a versão
    anterior deste arquivo de superficial e tinha razão: a cor saía de quatro
    checagens minhas, e as observações DELE, que têm número e direção, não
    entravam. Agora entram, e entram sob a mesma regra de todo o resto -- só vira
    razão o que a própria mesa confirmou.
    """
    medida = (situacao or {}).get("medida_eixos")
    motivos: List[str] = []          # o que PUXA para o verde, com medida
    contra: List[str] = []           # o que segura
    observacoes: List[str] = []      # visto, mas sem medida que autorize

    # ── quantidade de pessoas ────────────────────────────────────────────
    d_pub = _forte(medida, "publico")
    if publico is not None:
        cheia = bool(pico_publico and publico >= pico_publico)
        if d_pub is not None and d_pub >= D_MINIMO:
            det = (medida.get("detalhe") or {}).get("publico") or {}
            paga_mais_cheia = (det.get("media_pagou") or 0) > (det.get("media_nao") or 0)
            if cheia and paga_mais_cheia:
                motivos.append(
                    f"mesa cheia: {int(publico)} pessoas (o ponto dele é "
                    f"{int(pico_publico)}) — e AQUI o público separa "
                    f"(d={d_pub:.2f}: paga com {int(det.get('media_pagou') or 0)}, "
                    f"não paga com {int(det.get('media_nao') or 0)})")
            elif not cheia and paga_mais_cheia:
                contra.append(
                    f"mesa vazia: {int(publico)} pessoas, e nesta mesa o prêmio "
                    f"vem com plateia (d={d_pub:.2f})")
        else:
            observacoes.append(
                f"{int(publico)} pessoas — mas nesta mesa o público ainda NÃO "
                f"separou acerto de erro"
                + (f" (d={d_pub:.2f}, fraco)" if d_pub is not None
                   else " (sem medida ainda)")
                + ", então não conta como razão")

    # ── multiplicadores no histórico ─────────────────────────────────────
    d_rit = _forte(medida, "ritmo_mult")
    if ritmo_agora is not None and ritmo_normal:
        acima = ritmo_agora > ritmo_normal * 1.2
        if d_rit is not None and d_rit >= D_MINIMO:
            if acima:
                motivos.append(
                    f"muito multiplicador agora: {ritmo_agora:.0%} dos últimos "
                    f"giros pagaram contra {ritmo_normal:.0%} do normal desta "
                    f"mesa — e o ritmo separa aqui (d={d_rit:.2f})")
            else:
                contra.append(
                    f"multiplicador escasso: {ritmo_agora:.0%} contra "
                    f"{ritmo_normal:.0%} do normal (o ritmo importa aqui, "
                    f"d={d_rit:.2f})")
        elif acima:
            observacoes.append(
                f"{ritmo_agora:.0%} dos últimos giros pagaram (normal "
                f"{ritmo_normal:.0%}) — sem medida que autorize virar razão")

    # ── o que os momentos parecidos dizem ────────────────────────────────
    if situacao and situacao.get("fala"):
        n = int(situacao.get("n") or 0)
        raz = float(situacao.get("razao") or 0)
        lift = float(situacao.get("lift_mult") or 0)
        if raz >= 1.3 and n >= 15:
            motivos.append(
                f"{n} momentos parecidos no histórico concordam: "
                f"{raz:.2f}x acima do acaso da mesma aposta")
        elif raz < 0.9 and n >= 15:
            contra.append(
                f"os {n} momentos parecidos deram {raz:.2f}x — abaixo do acaso")
        else:
            observacoes.append(
                f"momentos parecidos: {raz:.2f}x com n={n} — nem confirma nem nega")
        if lift >= 1.5:
            motivos.append(
                f"depois de momentos como este, {situacao.get('pagou', 0):.0%} "
                f"dos giros pagaram — {lift:.2f}x o normal da mesa")
        elif lift and lift < 0.7:
            contra.append(
                f"depois de momentos como este o prêmio some ({lift:.2f}x)")
    elif situacao is not None:
        contra.append(f"sem momentos parecidos suficientes — "
                      f"{situacao.get('nota') or 'sem base'}")

    # ── as observações DELE, medidas ─────────────────────────────────────
    _regime_em_motivos(regime, medida, motivos, contra, observacoes)

    # ── a repetição da sugestão ──────────────────────────────────────────
    rep = _repeticao(ultimas_sugestoes)
    if rep["repetiu"] >= REPETE_DEMAIS:
        contra.append(
            f"a sugestão está repetindo: a mesma lista há {rep['repetiu']} "
            f"voltas. {rep['porque']}")

    # ── a autocrítica: por que errei tanto ───────────────────────────────
    critica = _autocritica(placar_recente)

    # ── a cor ────────────────────────────────────────────────────────────
    if contra and not motivos:
        cor = VERMELHO
    elif len(motivos) >= MIN_MOTIVOS_VERDE and not _grave(contra):
        cor = VERDE
    elif motivos:
        cor = AMARELO
    else:
        cor = AMARELO if observacoes else VERMELHO

    return {"cor": cor, "motivos": motivos, "contra": contra,
            "observacoes": observacoes, "repeticao": rep,
            "autocritica": critica,
            "avisar": cor == VERDE}


def _regime_em_motivos(regime: Optional[dict], medida: Optional[dict],
                       motivos: List[str], contra: List[str],
                       observacoes: List[str]) -> None:
    """As três observações dele viram razão, contra-razão ou observação.

    A REGRA, IGUAL PARA AS TRÊS
    ───────────────────────────
    A observação dele diz o QUE olhar. Se ela vira RAZÃO para o verde depende de a
    própria mesa tê-la confirmado com número -- e `regime_multiplicador` já traz
    esse veredito junto da medida, com o `n` e o teste de ruído.

    Isto não é desconfiar dele. É o contrário: é o único jeito de a observação
    dele valer alguma coisa quando confirmar. Se eu deixasse "acima de 45" virar
    verde sem medir, o verde não distinguiria mesa em que o limiar funciona de
    mesa em que não funciona -- e ele estaria recebendo aviso no celular pelos dois.
    """
    if not regime:
        return

    # ── 1. a densidade em 500, e o ponto 45 dele ─────────────────────────
    d = regime.get("densidade") or {}
    lim = regime.get("limiar") or {}
    if d:
        quantos = d.get("quantos", 0)
        alvo = quantos if d.get("completa") else d.get("projetado_500")
        marca = "" if d.get("completa") else " (projetado)"
        acima = bool(d.get("acima_do_limiar"))
        if lim.get("confirma"):
            if acima:
                motivos.append(
                    f"muito número multiplicado: {alvo} em 500{marca}, acima do "
                    f"ponto {d.get('limiar_dele')} dele — e NESTA mesa o ponto se "
                    f"confirma ({lim['taxa_depois_de_acima']:.1%} pagaram depois "
                    f"de blocos acima contra {lim['taxa_depois_de_abaixo']:.1%}, "
                    f"{lim.get('razao')}x, n={lim['n_acima']}/{lim['n_abaixo']} "
                    f"blocos)")
            else:
                contra.append(
                    f"pouco número multiplicado: {alvo} em 500{marca}, abaixo do "
                    f"ponto {d.get('limiar_dele')} — e aqui o ponto vale "
                    f"({lim.get('razao')}x)")
        elif lim.get("mediu"):
            observacoes.append(
                f"{alvo} em 500{marca} "
                f"({'acima' if acima else 'abaixo'} do ponto "
                f"{d.get('limiar_dele')} dele) — mas nesta mesa o ponto NÃO se "
                f"confirmou ({lim.get('razao')}x, t={lim.get('t')}), então não "
                f"conta como razão")
        else:
            observacoes.append(
                f"{alvo} em 500{marca} "
                f"({'acima' if acima else 'abaixo'} do ponto "
                f"{d.get('limiar_dele')} dele) — ainda não deu para testar o "
                f"ponto aqui: {lim.get('nota') or 'sem base'}")

    # ── 2. magnitude recente e a inversão ────────────────────────────────
    mg = regime.get("magnitude") or {}
    c = regime.get("ciclo") or {}
    if mg.get("mediu"):
        faixa = mg.get("faixa")
        if c.get("confirma"):
            if faixa == "baixos":
                motivos.append(
                    f"os {mg['n_recentes']} últimos prêmios vieram BAIXOS "
                    f"(média {mg['media_recente']} contra mediana "
                    f"{mg['mediana_da_mesa']}) — e nesta mesa a inversão que ele "
                    f"descreveu se confirma: depois de baixos, "
                    f"{c['alto_depois_de_baixo']:.0%} vieram altos contra "
                    f"{c['alto_depois_de_alto']:.0%} depois de altos "
                    f"(n={c['n_baixo']}/{c['n_alto']}, z={c.get('z')})")
            elif faixa == "altos":
                contra.append(
                    f"os últimos prêmios vieram ALTOS (média "
                    f"{mg['media_recente']}) e aqui a inversão vale — depois de "
                    f"altos só {c['alto_depois_de_alto']:.0%} seguem altos")
        else:
            observacoes.append(
                f"os {mg['n_recentes']} últimos prêmios são {faixa} "
                f"(média {mg['media_recente']}, mediana da mesa "
                f"{mg['mediana_da_mesa']}) — a inversão "
                + ("não se confirmou nesta mesa" if c.get("mediu")
                   else f"ainda não é testável: {c.get('nota') or 'sem base'}")
                + ", então a faixa não vira razão")

    # ── 3. a seca ────────────────────────────────────────────────────────
    s = regime.get("seca") or {}
    d_seca = _forte(medida, "seca_mult")
    if s.get("mediu"):
        if d_seca is not None and d_seca >= D_MINIMO:
            det = (medida.get("detalhe") or {}).get("seca_mult") or {}
            # a mesa paga depois de seca longa, ou depois de seca curta?
            paga_com_seca = (det.get("media_pagou") or 0) > (det.get("media_nao") or 0)
            if s.get("longa") and paga_com_seca:
                motivos.append(
                    f"seca longa: {s['agora']} giros sem prêmio, quantil "
                    f"{s['quantil']:.0%} desta mesa (mediana {s['mediana']}) — e "
                    f"aqui a seca separa (d={d_seca:.2f}: paga com "
                    f"{det.get('media_pagou')}, não paga com {det.get('media_nao')})")
            elif s.get("longa") and not paga_com_seca:
                contra.append(
                    f"seca de {s['agora']} giros (quantil {s['quantil']:.0%}) — e "
                    f"nesta mesa o prêmio vem no ritmo, não depois da seca "
                    f"(d={d_seca:.2f})")
        elif s.get("longa"):
            observacoes.append(
                f"seca de {s['agora']} giros, quantil {s['quantil']:.0%} desta "
                f"mesa (mediana {s['mediana']}, maior já vista "
                f"{s['maior_do_historico']}) — mas a seca ainda não separou "
                f"acerto de erro aqui"
                + (f" (d={d_seca:.2f}, fraco)" if d_seca is not None
                   else " (sem medida ainda)"))


def _grave(contra: List[str]) -> bool:
    """Há algo que impede o verde mesmo com motivos a favor?"""
    for c in contra:
        if "abaixo do acaso" in c or "sem momentos parecidos" in c:
            return True
    return False


def _repeticao(ultimas: Optional[Sequence[Sequence[Any]]]) -> Dict[str, Any]:
    """A sugestão está repetindo demais? E por quê?

    Ele perguntou exatamente assim: "está repetindo demais? sim? porque? e mudar
    ou nao". A resposta ao "por quê" importa mais que o aviso: repetir porque a
    mesa está travada num atrasado é legítimo pelo critério dele; repetir porque
    só uma fonte está falando é pobreza de evidência, e aí a lista devia mudar.
    """
    hist = [list(x or []) for x in (ultimas or []) if x]
    if len(hist) < 2:
        return {"repetiu": 0, "porque": "", "mudar": False}
    atual = set(str(x) for x in hist[-1])
    repetiu = 0
    for anterior in reversed(hist[:-1]):
        if set(str(x) for x in anterior) == atual:
            repetiu += 1
        else:
            break
    if repetiu < REPETE_DEMAIS:
        return {"repetiu": repetiu, "porque": "", "mudar": False}
    distintas = len({tuple(sorted(str(x) for x in h)) for h in hist})
    if distintas <= 2:
        porque = ("quase toda volta devolve a mesma lista — sinal de que poucas "
                  "fontes estão falando, não de convicção")
        mudar = True
    else:
        porque = ("a mesa segue no mesmo estado; pelo critério dele, insistir no "
                  "atrasado está certo enquanto ele não vier")
        mudar = False
    return {"repetiu": repetiu, "porque": porque, "mudar": mudar}


def _autocritica(placar: Optional[dict]) -> List[str]:
    """"Por que errei tanto? O momento é mesmo pra usar aquelas regras?"

    Sem inventar diagnóstico: compara o acerto recente com o acaso da mesma
    aposta e diz o que isso permite concluir -- inclusive "não permite nada".
    """
    if not placar:
        return []
    n = int(placar.get("n") or 0)
    ok = int(placar.get("ok") or 0)
    acaso = float(placar.get("acaso") or 0)
    if n < 8:
        return [f"só {n} janelas fechadas — ainda não dá para dizer por que "
                f"errei; nesse tamanho sorte e erro têm a mesma cara"]
    taxa = ok / n
    raz = (taxa / acaso) if acaso else 0.0
    L = [f"últimas {n} janelas: {taxa:.0%} contra acaso {acaso:.0%} "
         f"= {raz:.2f}x"]
    if raz < 0.8:
        L.append("está ABAIXO do acaso — as regras em uso não servem para este "
                 "momento; o certo é encolher a aposta ou calar, não insistir")
    elif raz < 1.05:
        L.append("empatando com o acaso — nada do que está sendo usado está "
                 "ajudando; vale trocar as fontes que decidem")
    else:
        L.append("acima do acaso com este conjunto de regras — mantê-las")
    return L


def resumo(s: Dict[str, Any]) -> List[str]:
    """As linhas da tela: a cor e os porquês, em português."""
    cor = s.get("cor")
    marca = {VERDE: "🟢", AMARELO: "🟡", VERMELHO: "🔴"}.get(cor, "?")
    L = [f"[Momento] {marca} {cor}"
         + ("  — aviso enviado" if s.get("avisar") else "  — sem aviso")]
    for m in s.get("motivos") or []:
        L.append(f"[Momento] ✓ {m}")
    for c in s.get("contra") or []:
        L.append(f"[Momento] ✗ {c}")
    for o in (s.get("observacoes") or [])[:2]:
        L.append(f"[Momento] · {o}")
    for a in s.get("autocritica") or []:
        L.append(f"[Autocrítica] {a}")
    return L


def texto_curto(s: Dict[str, Any]) -> str:
    """Uma linha para o alto da tela."""
    cor = s.get("cor")
    marca = {VERDE: "🟢", AMARELO: "🟡", VERMELHO: "🔴"}.get(cor, "")
    m = s.get("motivos") or []
    c = s.get("contra") or []
    if cor == VERDE:
        return f"{marca} BOM MOMENTO — {m[0][:64]}" if m else f"{marca} BOM MOMENTO"
    if cor == VERMELHO:
        return f"{marca} MOMENTO RUIM — {c[0][:64]}" if c else f"{marca} MOMENTO RUIM"
    return (f"{marca} momento comum — {(m or c or ['sem sinal claro'])[0][:60]}")
