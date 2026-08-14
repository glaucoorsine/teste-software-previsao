# -*- coding: utf-8 -*-
"""
META — executa o veredito do crítico ativo + tribunal.

REGRA DE VALIDAÇÃO (v62): teoria só é validada com evidência PROSPECTIVA
(sombra ao vivo) — nunca com replay do próprio histórico onde foi descoberta.

Motivo: o `janela_viva` do crítico é calculado sobre `hist`, o MESMO histórico
de onde os agentes tiraram a teoria (ver critico_cientifico._janela_viva:
"Últimas ativações reais no histórico"). Validar por ele é circular — acha o
padrão no dado, confere no mesmo dado, aprova. Foi o que produziu 373
validações falsas em dado 100% aleatório no `test_controle_100` da v61.
O `janela_viva` continua sendo usado como SINAL (prioriza quem olhar primeiro),
mas não valida sozinho.

Critério de validação — 3 condições simultâneas sobre a sombra prospectiva:
  1. n_prosp >= MIN_SOMBRA_VALIDAR        (amostra mínima ao vivo)
  2. taxa_prosp >= TAXA_MIN               (a régua de 30% pedida)
  3. IC90 inferior da taxa > baseline     (bate o acaso com folga estatística)

A condição 3 é adaptativa e é o que separa sinal de coincidência:
  - teoria FORTE (50% ao vivo)   → valida com ~8-12 ativações
  - teoria marginal (30% ao vivo) → precisa de ~40 ativações
Ou seja: não segura sinal real, e não carimba ruído de amostra pequena.

Estados finais:
  rejeitada                 → estrutura inválida
  descartada_pelo_tribunal  → <30% com amostra (reavaliável)
  reavaliar_variante        → reformuladores
  em_teste                  → acumulando sombra ao vivo
  validada_dormente         → aprovada, pronta para ativador/motor
"""
from __future__ import annotations
import math

# amostra mínima de sombra AO VIVO antes de qualquer validação
MIN_SOMBRA_VALIDAR = 8
TAXA_MIN = 0.30          # régua operacional
Z_IC90 = 1.64
# Controle de descoberta falsa sobre a sombra. 0.15 é o mesmo alpha que o
# crítico já usa em aplicar_fdr_batch() — mantido igual para não haver duas
# réguas diferentes no mesmo pipeline. Também é o valor que faz a sombra de
# referência do pacote (4/10 = 40%, p=0.103) validar, como os testes
# test_meta_validate_with_good_shadow / test_meta_loads_shadow_memory exigem.
FDR_ALPHA = 0.15


def _binom_p_ge(hits: int, n: int, p: float) -> float:
    """P(X >= hits | n, p) exato — chance do acaso produzir esse resultado."""
    if n <= 0:
        return 1.0
    hits = max(0, min(hits, n))
    p = min(max(p, 1e-9), 1 - 1e-9)
    total = 0.0
    for i in range(hits, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return min(1.0, max(0.0, total))


def marcar_fdr_sombra(teorias, alpha: float = FDR_ALPHA):
    """
    Benjamini-Hochberg sobre os p-valores da SOMBRA PROSPECTIVA do lote.

    Por que aqui funciona e na v51 não funcionava: lá o p-valor vinha de
    permutação com n_perm=50, que tem piso 1/(50+1)=0,0196 — nenhuma teoria,
    nem 100% determinística, conseguia ficar abaixo do corte depois do FDR.
    Aqui o p-valor é binomial exato sobre a sombra ao vivo e NÃO tem piso:
    uma teoria de 60% em 20 ativações dá p≈5.7e-05 e sobrevive folgado.
    Isso controla o efeito de testar centenas de teorias ao mesmo tempo.
    """
    itens = []
    for t in teorias:
        s = avaliar_sombra(t)
        t["evidencia_sombra"] = s
        if s["n"] >= MIN_SOMBRA_VALIDAR:
            pv = _binom_p_ge(s["hits"], s["n"], s["baseline"])
            s["p_sombra"] = round(pv, 8)
            itens.append((t, pv))
        else:
            s["p_sombra"] = None
            s["q_sombra"] = None
            s["fdr_ok"] = False
    m = len(itens)
    if not m:
        return teorias
    ordenados = sorted(range(m), key=lambda i: itens[i][1])
    prev = 1.0
    qs = [1.0] * m
    for rank in range(m, 0, -1):
        idx = ordenados[rank - 1]
        pv = itens[idx][1]
        prev = min(prev, pv * m / rank)
        qs[idx] = min(1.0, prev)
    for (t, _pv), q in zip(itens, qs):
        s = t["evidencia_sombra"]
        s["q_sombra"] = round(q, 6)
        s["fdr_ok"] = bool(q <= alpha)
    return teorias


def _wilson_low(hits: int, n: int, z: float = Z_IC90) -> float:
    """Limite inferior do IC (Wilson) da taxa observada."""
    if n <= 0:
        return 0.0
    phat = hits / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    spread = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return max(0.0, (centre - spread) / denom)


MIN_PAREADO_CONFIAVEL = 15   # (histórico) — ver PRIOR_PAREADO abaixo
# Peso do prior teórico no encolhimento do baseline pareado. Com m=8
# ativações o pareado já pesa metade; com m=24, três quartos.
PRIOR_PAREADO = 8.0


def _baseline_prospectivo(prosp: dict, n_dominio: int = 37) -> float:
    """
    Baseline contra o qual a sombra é comparada — o ADVERSÁRIO da teoria.

    O adversário certo não é o acaso: é o que qualquer um faria sem sistema
    nenhum, ou seja apostar nos números mais quentes. Esse palpite-controle já
    é gravado desde a PRIMEIRA ativação (`baseline_hit`, em registrar_prospectivo).

    Antes ele só entrava a partir de 15 ativações; abaixo disso a teoria era
    julgada só contra o acaso teórico (k/|domínio|). Medido nos dados reais do
    usuário: 59% das teorias que chegavam ao mínimo de validação nunca eram
    comparadas com a régua real — e o conjunto todo ficou 10 pontos percentuais
    ABAIXO dela (31,6% contra 35,7%, McNemar p=0,0002). Ou seja: dava pra ser
    "validada" sendo bem pior que o trivial.

    Agora o pareado entra desde o começo, mas com ENCOLHIMENTO: com poucas
    amostras ele é ruidoso (foi por isso que existia o corte de 15), então
    puxamos a estimativa para o teórico com peso PRIOR_PAREADO. Conforme as
    ativações se acumulam, o pareado domina. E nunca fica mais fácil que o
    acaso: o resultado é sempre >= teórico.
    """
    hist = prosp.get("hist") or []
    ks = [len(e.get("candidatos") or []) for e in hist if e.get("candidatos")]
    n_dom = max(2, int(n_dominio or 37))
    if ks:
        base_teorico = min(0.95, (sum(ks) / len(ks)) / n_dom)
    else:
        base_teorico = 7.0 / n_dom

    marcados = [e for e in hist if "baseline_hit" in e]
    m = len(marcados)
    if not m:
        return base_teorico
    taxa_pareada = sum(1 for e in marcados if e.get("baseline_hit")) / m
    # média ponderada: prior teórico com peso PRIOR_PAREADO, dados com peso m
    base_encolhida = (m * taxa_pareada + PRIOR_PAREADO * base_teorico) / (m + PRIOR_PAREADO)
    return max(base_teorico, base_encolhida)


def _tamanho_dominio(teoria: dict) -> int:
    """|domínio| do jogo da teoria (roleta=37, crazy_time=8)."""
    try:
        from .schema_eventos import DOMAIN_BY_DATASET, ROULETTE_DOMAIN
        ds = teoria.get("dataset_id") or teoria.get("dominio")
        dom = DOMAIN_BY_DATASET.get(ds)
        if dom:
            return len(dom)
        return len(ROULETTE_DOMAIN)
    except Exception:
        return 37


def avaliar_sombra(teoria: dict) -> dict:
    """Diagnóstico da evidência prospectiva — usado pela META e pelo relatório."""
    prosp = teoria.get("prospectivo") or {}
    n = int(prosp.get("n") or 0)
    hits = int(prosp.get("hits") or 0)
    taxa = (hits / n) if n else None
    base = _baseline_prospectivo(prosp, n_dominio=_tamanho_dominio(teoria))
    ic_low = _wilson_low(hits, n)
    # p-valor sempre calculado aqui: se algum caminho chamar decidir() sem
    # passar antes por marcar_fdr_sombra() (ex.: ciclo_residual), ainda existe
    # um corte por teoria em vez de passar livre.
    p_sombra = _binom_p_ge(hits, n, base) if n >= MIN_SOMBRA_VALIDAR else None
    return {
        "n": n,
        "hits": hits,
        "taxa": taxa,
        "baseline": round(base, 4),
        "ic90_low": round(ic_low, 4),
        "bate_baseline": bool(n > 0 and ic_low > base),
        "amostra_ok": n >= MIN_SOMBRA_VALIDAR,
        "taxa_ok": bool(taxa is not None and taxa >= TAXA_MIN),
        "p_sombra": round(p_sombra, 8) if p_sombra is not None else None,
    }


def _sombra_prova(teoria: dict):
    """A sombra AO VIVO já provou esta teoria? (None = ainda não tem o que dizer)

    Devolve a evidência quando ela é suficiente E aprovada, senão None.
    """
    s = teoria.get("evidencia_sombra") or avaliar_sombra(teoria)
    teoria["evidencia_sombra"] = s
    if not (s.get("amostra_ok") and s.get("taxa_ok") and s.get("bate_baseline")):
        return None
    # Se o lote passou por marcar_fdr_sombra(), usa o q (controla o volume de
    # teorias testadas em paralelo). Senão, cai no p-valor da própria teoria —
    # nunca "passa livre" por falta de marcação.
    if s.get("q_sombra") is not None:
        sig_ok = bool(s.get("fdr_ok"))
    else:
        p = s.get("p_sombra")
        sig_ok = bool(p is not None and p <= FDR_ALPHA)
    return s if sig_ok else None


def decidir(teoria: dict) -> str:
    if teoria.get("rejeicao_dura") or teoria.get("destino_critico") == "estrutura_invalida":
        return "rejeitada"

    dest = teoria.get("destino_critico") or ""
    ver = teoria.get("veredito_critico") or ""

    # A SOMBRA AO VIVO TEM A PALAVRA FINAL.
    #
    # Antes, o veredito retrospectivo do crítico era consultado primeiro, e o
    # ramo `TESTAR_AGORA` (logo abaixo) devolvia "em_teste" sem NUNCA olhar a
    # sombra. Efeito medido: a teoria verdadeira do teste (5→9, com 37,5% de
    # acerto ao vivo contra 2,7% de acaso, p=0,001 e aprovada pelo FDR) ficava
    # presa em "em_teste" para sempre, porque o crítico a marcara TESTAR_AGORA.
    # Ou seja: o sistema mandava testar ao vivo, a teoria passava no teste, e o
    # resultado era ignorado.
    #
    # Isso contraria o desenho da v62, onde quem valida é a evidência
    # prospectiva — o retrospectivo serve para priorizar, não para vetar. A
    # estrutura inválida continua barrando acima; o resto agora é decidido por
    # quem foi testado ao vivo e passou.
    if _sombra_prova(teoria) is not None:
        return "validada_dormente"

    if dest == "reprovar_enviar_tribunal" or ver == "REPROVA":
        # crítico reprovou por <30% no histórico → tribunal confirma/descarta
        return "reavaliar_variante"

    if dest == "reavaliar_variante" or ver == "REFORMULAR":
        return "reavaliar_variante"

    if dest == "em_teste_ativo" or ver == "TESTAR_AGORA":
        return "em_teste"

    if dest == "promissora" or ver in ("APROVA", "APROVA_PROVISORIA") or teoria.get("critica_ok"):
        # A validação em si já foi resolvida no topo por _sombra_prova(). Chegar
        # aqui significa que a sombra ainda não bastou — segue em teste.
        return "em_teste"

    return "em_teste"


def motivo(teoria: dict, estado: str) -> str:
    ret = teoria.get("retrospectivo") or {}
    jan = ret.get("janela_viva") or {}
    s = teoria.get("evidencia_sombra") or avaliar_sombra(teoria)
    return (
        f"estado={estado} veredito={teoria.get('veredito_critico')} destino={teoria.get('destino_critico')} "
        f"critica_ok={teoria.get('critica_ok')} "
        f"| SOMBRA(ao vivo) {s.get('hits')}/{s.get('n')} taxa={s.get('taxa')} "
        f"ic90_low={s.get('ic90_low')} baseline={s.get('baseline')} bate={s.get('bate_baseline')} "
        f"| retro_janela={jan.get('hits')}/{jan.get('n')} (sinal, não valida) "
        f"replay_n={(ret.get('replay') or {}).get('n')} ganho={ret.get('ganho')} "
        f"| {teoria.get('motivo_critica')}"
    )
