# -*- coding: utf-8 -*-
"""
AUTOMELHORIA — propor, ENSAIAR medindo, aplicar o que melhorou, desfazer o que
piorou. E guardar tudo no lar, para não recomeçar a cada versão.

O QUE ELE PEDIU
───────────────
    "inteligência capaz de auto analise, auto correção, auto crítica e sempre em
     busca de acertividade de numeros e bonus"
    "auto executoriedade de melhorias"
    "auto sugestão para acertividade"
    "auto percepções novas"
    "auto de aplicação de tudo que for bom"

O QUE "AUTO-EXECUTORIEDADE" PRECISA SIGNIFICAR PARA NÃO SER PIOR QUE NADA
────────────────────────────────────────────────────────────────────────
Uma inteligência que muda a si mesma sem medir não está melhorando, está
passeando. E o passeio tem uma direção previsível: com dezenas de parâmetros e
poucas janelas, mexer sempre "melhora" no curtíssimo prazo, porque o ruído
concorda com quem mexeu. Depois de vinte mudanças assim o software está pior e
cada mudança tem um registro dizendo que foi boa.

Então aqui a auto-execução tem quatro etapas, e nenhuma pode ser saltada:

    1. PROPOR    a mudança sai de uma medida, não de um palpite meu
    2. ENSAIAR   candidato e titular ALTERNAM volta a volta
    3. JULGAR    compara os dois placares, que cresceram no mesmo período
    4. EXECUTAR  aplica se ganhou além do ruído; devolve o titular se perdeu

A etapa 3 é a que dá sentido às outras, e a alternância da etapa 2 é o que a torna
possível. Comparar o candidato de hoje com o titular de ontem é comparar mesas
diferentes, e aí ganha quem pegou a mesa mais fácil. Alternando volta a volta, os
dois placares crescem na mesma mesa, nas mesmas horas, com o mesmo público -- e a
diferença passa a ser da mudança.

(A primeira versão deste arquivo dizia "nas mesmas janelas" e deixava o candidato
ativo o tempo todo. Assim o titular não rodava em lugar nenhum e o placar dele
ficava em zero para sempre: o ensaio nunca teria sido julgado, ou seria julgado
contra nada. Está descrito onde foi corrigido, em `virar_lado`.)

E TEM QUE PODER DESFAZER
────────────────────────
Toda mudança aplicada fica registrada com o valor anterior. Se a medida virar
contra ela depois -- e vira, porque mesa muda -- o valor antigo volta. Sem isso,
"auto melhoria" seria um caminho de mão única: cada passo irreversível, e o
software preso na soma de todos os passos.

O QUE ESTE ARQUIVO NÃO FAZ, E POR QUE EU NÃO VOU FAZER
──────────────────────────────────────────────────────
Não reescreve o próprio código. Ele pediu "auto melhoria com capacidade de
pesquisa livre em Internet sobre soluções" e "auto de aplicação de tudo que for
bom", e a combinação literal disso -- baixar da internet e aplicar sozinho --
entrega o software a quem escrever a página. Qualquer fórum, qualquer comentário
numa página de cassino, passaria a mandar no que ele recebe no celular.

O que faz sentido, e é o que está aqui: a automelhoria mexe em NÚMEROS
declarados, dentro de faixas declaradas, medindo. A pesquisa na internet
(`pesquisa_livre.py`) vira PROPOSTA escrita, para ele ler e liberar. A diferença
entre as duas coisas é a diferença entre um software que aprende e um software
que obedece a estranhos.

OS PARÂMETROS QUE ELA PODE MEXER, E A FAIXA DE CADA UM
──────────────────────────────────────────────────────
Faixa declarada por parâmetro, sempre. Um limite de busca que pode ir a zero
desliga a busca; um peso que pode ir a mil cala todo o resto. A faixa é o que
impede a automelhoria de se destruir tentando melhorar.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

ARQ = "automelhoria.json"

# quantas janelas o candidato precisa fechar antes de ser julgado
MIN_ENSAIO = 25
# a margem que o candidato precisa ter para tomar o lugar do titular
MARGEM_MINIMA = 1.10
# e além do ruído: diferença de proporções em desvios
Z_MINIMO = 1.8
# quantos ensaios ao mesmo tempo. Mais que isto e o vencedor é o mais sortudo:
# testar dez coisas de uma vez e ficar com a melhor é escolher ruído.
MAX_ENSAIOS = 2

# ─────────────────────────────────────── o que ela pode mexer, e até onde
#
# `passo` é o quanto ela move por vez. Passo grande chega rápido e passa do
# ponto; passo pequeno nunca sai do lugar. Estes valores movem ~10% da faixa.
AJUSTAVEIS: Dict[str, Dict[str, Any]] = {
    "semaforo.MIN_MOTIVOS_VERDE": {
        "faixa": (1, 4), "passo": 1, "inteiro": True,
        "porque": "quantas razões medidas o verde exige"},
    "semaforo.D_MINIMO": {
        "faixa": (0.15, 0.60), "passo": 0.05,
        "porque": "o quanto um eixo precisa separar para virar razão"},
    "semaforo.REPETE_DEMAIS": {
        "faixa": (3, 8), "passo": 1, "inteiro": True,
        "porque": "quantas repetições antes de reclamar da sugestão"},
    "situacao.K_VIZINHOS": {
        "faixa": (20, 80), "passo": 10, "inteiro": True,
        "porque": "quantos momentos parecidos entram na conta"},
    "situacao.SEPARACAO": {
        "faixa": (3, 12), "passo": 1, "inteiro": True,
        "porque": "distância mínima entre momentos para não contar o mesmo duas vezes"},
    "regime_multiplicador.LIMIAR_DELE": {
        "faixa": (30, 70), "passo": 5, "inteiro": True,
        "porque": "o ponto dele nos multiplicados em 500 — ela pode achar o ponto DESTA mesa"},
    "autoexame.D_MINIMO": {
        "faixa": (0.30, 0.80), "passo": 0.05,
        "porque": "o quanto um eixo precisa separar para ser apontado como causa do erro"},
}


def _limitar(nome: str, valor: float) -> float:
    reg = AJUSTAVEIS.get(nome) or {}
    lo, hi = reg.get("faixa", (valor, valor))
    v = max(lo, min(hi, valor))
    return int(round(v)) if reg.get("inteiro") else round(float(v), 4)


def _z(k1: int, n1: int, k2: int, n2: int) -> Optional[float]:
    if n1 < 2 or n2 < 2:
        return None
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se <= 1e-12:
        return None
    return (k1 / n1 - k2 / n2) / se


# ═══════════════════════════════════════════════════════════ o estado no lar
def carregar() -> Dict[str, Any]:
    try:
        from NUCLEO import lar
        d = lar.ler_json(ARQ, None)
    except Exception:
        d = None
    if not isinstance(d, dict):
        d = {}
    d.setdefault("aplicados", {})     # nome -> {valor, antes, em, ganho}
    d.setdefault("ensaios", [])       # candidatos em teste
    d.setdefault("historico", [])     # tudo que já foi tentado, com desfecho
    d.setdefault("percepcoes", [])    # o que ela notou e ainda não virou nada
    return d


def gravar(d: Dict[str, Any]) -> bool:
    d["historico"] = (d.get("historico") or [])[-200:]
    d["percepcoes"] = (d.get("percepcoes") or [])[-60:]
    try:
        from NUCLEO import lar
        return lar.gravar_json(ARQ, d)
    except Exception:
        return False


# ─────────────────────────────── de que lado esta volta está: A ou B
#
# UM DEFEITO DO MEU PRÓPRIO DESENHO, QUE EU ACHEI ESCREVENDO O RESTO
# ──────────────────────────────────────────────────────────────────
# Eu escrevi acima que a comparação é "nas mesmas janelas". Não era: eu deixava o
# valor do candidato ATIVO durante o ensaio, o que quer dizer que o titular não
# rodava em lugar nenhum -- não havia placar dele para comparar. O `tit_ok` só
# subiria se alguém o alimentasse, e ninguém alimentava.
#
# A correção é alternar. Uma volta usa o titular, a seguinte usa o candidato, e
# assim por diante. Os dois placares crescem entrelaçados no MESMO período, na
# mesma mesa, nas mesmas horas, com o mesmo público -- que é o que a comparação
# precisa. Não é literalmente a mesma janela (isso exigiria rodar dois softwares),
# mas é a mesma mesa no mesmo tempo, e a diferença deixa de ser "quem pegou a
# mesa mais fácil".
_lado_atual = "titular"


def virar_lado(d: Optional[Dict[str, Any]] = None) -> str:
    """Alterna o lado desta volta. Chamado uma vez por volta, antes de decidir."""
    global _lado_atual
    _lado_atual = "candidato" if _lado_atual == "titular" else "titular"
    return _lado_atual


def lado() -> str:
    return _lado_atual


def valores_ativos(lado_desta_volta: Optional[str] = None) -> Dict[str, float]:
    """Os ajustes que valem AGORA.

    O que já foi aplicado vale sempre -- passou pelo ensaio. O que está em ensaio
    vale só nas voltas do lado "candidato", que é o que faz o ensaio ser um
    ensaio e não uma troca disfarçada.
    """
    d = carregar()
    out = {}
    for nome, reg in (d.get("aplicados") or {}).items():
        if nome in AJUSTAVEIS and isinstance(reg, dict) and reg.get("valor") is not None:
            out[nome] = _limitar(nome, float(reg["valor"]))
    if (lado_desta_volta or _lado_atual) == "candidato":
        for e in (d.get("ensaios") or []):
            nome = e.get("nome")
            if nome in AJUSTAVEIS and e.get("valor") is not None and e.get("ativo"):
                out[nome] = _limitar(nome, float(e["valor"]))
    return out


def valor(nome: str, padrao: float) -> float:
    """O número que vale agora para este parâmetro: o dela, ou o meu padrão."""
    v = valores_ativos().get(nome)
    return padrao if v is None else v


# ══════════════════════════════════════════════════════ 1. PROPOR, medindo
def propor(autoexame: Optional[dict] = None,
           semaforo_placar: Optional[dict] = None,
           regime: Optional[dict] = None,
           eixos: Optional[dict] = None) -> List[Dict[str, Any]]:
    """As mudanças que as medidas de agora justificam.

    Cada proposta cita a medida que a motivou. Uma proposta sem medida atrás não
    é auto-melhoria, é eu chutando com outro nome.
    """
    p: List[Dict[str, Any]] = []

    # ── o verde está exigindo demais, ou de menos? ───────────────────────
    if semaforo_placar:
        n_verde = int(semaforo_placar.get("n_verde") or 0)
        n_total = int(semaforo_placar.get("n_total") or 0)
        taxa_verde = semaforo_placar.get("taxa_verde")
        taxa_resto = semaforo_placar.get("taxa_resto")
        if n_total >= 40 and n_verde == 0:
            # nunca deu verde: a exigência pode estar alta demais para esta mesa,
            # e um semáforo que nunca abre não informa nada
            p.append(_prop("semaforo.MIN_MOTIVOS_VERDE", -1,
                           f"em {n_total} voltas o verde nunca abriu — com a "
                           f"exigência atual esta mesa não produz sinal"))
        elif (n_verde >= 15 and taxa_verde is not None and taxa_resto
              and taxa_verde <= taxa_resto):
            # deu verde e o verde não rendeu mais que o resto: exigir mais
            p.append(_prop("semaforo.MIN_MOTIVOS_VERDE", +1,
                           f"o verde rendeu {taxa_verde:.0%} contra "
                           f"{taxa_resto:.0%} fora dele em {n_verde} verdes — "
                           f"não está separando nada"))

    # ── o ponto 45 dele é o ponto DESTA mesa? ────────────────────────────
    lim = (regime or {}).get("limiar") or {}
    if lim.get("mediu") and not lim.get("confirma") and lim.get("razao"):
        # o ponto declarado não se confirmou aqui; vale procurar o ponto da mesa
        direcao = +1 if float(lim.get("razao") or 1) < 1 else -1
        p.append(_prop("regime_multiplicador.LIMIAR_DELE", direcao * 5,
                       f"o ponto atual deu {lim.get('razao')}x (t={lim.get('t')}) "
                       f"nesta mesa — procurando o ponto que ela tem"))

    # ── a vizinhança está pequena para o que a mesa oferece? ─────────────
    if autoexame:
        sit = next((e for e in (autoexame.get("exames") or [])
                    if e.get("teoria") == "SITUACAO" and e.get("sabe")), None)
        if sit and sit.get("razao") and sit["razao"] < 1.0 and sit.get("n", 0) >= 30:
            p.append(_prop("situacao.K_VIZINHOS", +10,
                           f"SITUACAO rendeu {sit['razao']:.2f}x em {sit['n']} "
                           f"janelas — vizinhança maior dá base mais firme"))

    # ── a autocrítica não está achando causa nenhuma? ────────────────────
    if autoexame:
        sabidas = [e for e in (autoexame.get("exames") or []) if e.get("sabe")]
        com_erro = [e for e in sabidas
                    if e.get("acertos", 0) >= 5 and e.get("erros", 0) >= 5]
        sem_causa = [e for e in com_erro if not e.get("causas")]
        if len(com_erro) >= 4 and len(sem_causa) == len(com_erro):
            p.append(_prop("autoexame.D_MINIMO", -0.05,
                           f"nenhuma das {len(com_erro)} teorias com erro "
                           f"suficiente teve causa apontada — a exigência de "
                           f"separação pode estar cega"))

    # ── eixo que não separa nada em lugar nenhum ─────────────────────────
    if eixos:
        det = (eixos.get("detalhe") or {})
        medidos = [v for v in det.values() if v.get("d") is not None]
        if len(medidos) >= 4 and all(v["d"] < 0.15 for v in medidos):
            p.append(_prop("semaforo.D_MINIMO", -0.05,
                           f"nenhum dos {len(medidos)} eixos medidos passa de "
                           f"d=0.15 nesta mesa — nada viraria razão nunca"))
    return p


def _prop(nome: str, delta: float, porque: str) -> Dict[str, Any]:
    reg = AJUSTAVEIS[nome]
    return {"nome": nome, "delta": delta, "porque": porque,
            "para_que": reg["porque"]}


# ═══════════════════════════════════════════════════════ 2. e 3. ENSAIAR
def abrir_ensaio(d: Dict[str, Any], proposta: Dict[str, Any],
                 padroes: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Põe um candidato em sombra. Devolve o ensaio, ou None se não couber."""
    nome = proposta.get("nome")
    if nome not in AJUSTAVEIS:
        return None
    vivos = [e for e in (d.get("ensaios") or []) if e.get("ativo")]
    if len(vivos) >= MAX_ENSAIOS:
        return None
    if any(e.get("nome") == nome for e in vivos):
        return None
    atual = valores_ativos().get(nome, padroes.get(nome))
    if atual is None:
        return None
    novo = _limitar(nome, float(atual) + float(proposta["delta"]))
    if novo == _limitar(nome, float(atual)):
        return None                       # já está no fim da faixa
    ensaio = {"nome": nome, "antes": _limitar(nome, float(atual)), "valor": novo,
              "porque": proposta.get("porque"), "ativo": True,
              "aberto_em": time.strftime("%Y-%m-%d %H:%M"),
              # o placar do candidato e o do titular, nas MESMAS janelas
              "cand_ok": 0, "cand_n": 0, "tit_ok": 0, "tit_n": 0}
    d.setdefault("ensaios", []).append(ensaio)
    return ensaio


def anotar_janela(d: Dict[str, Any], acertou: bool,
                  lado_da_janela: Optional[str] = None) -> None:
    """Credita uma janela fechada ao lado que estava valendo quando ela abriu.

    O lado tem de vir da JANELA, não do momento em que ela fecha. Uma janela
    aberta numa volta do candidato só fecha três giros depois, quando o lado atual
    já virou -- creditar pelo lado de agora trocaria os placares e a automelhoria
    passaria a aplicar exatamente o que piorou.
    """
    l = str(lado_da_janela or _lado_atual)
    for e in (d.get("ensaios") or []):
        if not e.get("ativo"):
            continue
        if l == "candidato":
            e["cand_n"] = int(e.get("cand_n") or 0) + 1
            if acertou:
                e["cand_ok"] = int(e.get("cand_ok") or 0) + 1
        else:
            e["tit_n"] = int(e.get("tit_n") or 0) + 1
            if acertou:
                e["tit_ok"] = int(e.get("tit_ok") or 0) + 1


def julgar(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fecha os ensaios maduros: aplica quem ganhou, devolve o titular a quem não.

    "Empatou" não aplica. Trocar por empate é mexer por ruído -- e vinte trocas
    por ruído levam o software para longe sem nenhum passo parecer errado.
    """
    fechados = []
    for e in list(d.get("ensaios") or []):
        # amostra nos DOIS lados: com a alternancia, cada um recebe metade das
        # janelas, e julgar com um lado vazio seria comparar contra nada
        if (not e.get("ativo") or int(e.get("cand_n") or 0) < MIN_ENSAIO
                or int(e.get("tit_n") or 0) < MIN_ENSAIO):
            continue
        cn, ck = int(e["cand_n"]), int(e["cand_ok"])
        tn, tk = int(e["tit_n"]), int(e["tit_ok"])
        tc = ck / cn if cn else 0.0
        tt = tk / tn if tn else 0.0
        z = _z(ck, cn, tk, tn)
        razao = (tc / tt) if tt > 0 else (2.0 if tc > 0 else 1.0)
        ganhou = bool(razao >= MARGEM_MINIMA and z is not None and z >= Z_MINIMO)
        perdeu = bool(z is not None and z <= -Z_MINIMO)
        e["ativo"] = False
        e["fechado_em"] = time.strftime("%Y-%m-%d %H:%M")
        e["taxa_candidato"] = round(tc, 4)
        e["taxa_titular"] = round(tt, 4)
        e["razao"] = round(razao, 3)
        e["z"] = round(z, 2) if z is not None else None
        if ganhou:
            e["desfecho"] = "aplicado"
            d.setdefault("aplicados", {})[e["nome"]] = {
                "valor": e["valor"], "antes": e["antes"],
                "em": e["fechado_em"], "razao": e["razao"], "z": e["z"],
                "porque": e.get("porque")}
        elif perdeu:
            e["desfecho"] = "descartado — piorou"
        else:
            e["desfecho"] = "descartado — empatou"
        d["historico"] = (d.get("historico") or []) + [dict(e)]
        fechados.append(e)
    d["ensaios"] = [e for e in (d.get("ensaios") or []) if e.get("ativo")]
    return fechados


def desfazer(d: Dict[str, Any], nome: str, porque: str = "") -> bool:
    """Devolve um ajuste aplicado ao valor anterior.

    Existe porque mesa muda. Um ajuste que era bom em mesa cheia pode ser ruim em
    mesa vazia, e sem caminho de volta o software fica preso na soma de todas as
    decisões que já pareceram boas.
    """
    reg = (d.get("aplicados") or {}).get(nome)
    if not reg:
        return False
    d["historico"] = (d.get("historico") or []) + [{
        "nome": nome, "desfecho": "desfeito", "valor": reg.get("antes"),
        "antes": reg.get("valor"), "porque": porque,
        "fechado_em": time.strftime("%Y-%m-%d %H:%M")}]
    del d["aplicados"][nome]
    return True


# ═══════════════════════════════════════════ percepções novas, sem executar
def perceber(d: Dict[str, Any], texto: str, medida: Optional[dict] = None) -> None:
    """Guarda uma percepção que ainda não virou mudança.

        "auto percepções novas"

    Nem tudo que ela nota tem um parâmetro correspondente para mexer. "O público
    às terças é metade do resto" é uma percepção verdadeira e útil que não vira
    ajuste de número nenhum. Guardar em vez de descartar é o que permite que
    depois de vinte horas exista uma lista do que ESTA mesa tem de particular --
    e ele pediu percepção, não só ajuste.
    """
    t = str(texto).strip()
    if not t:
        return
    ja = {str(x.get("texto")) for x in (d.get("percepcoes") or [])}
    if t in ja:
        return
    d.setdefault("percepcoes", []).append({
        "texto": t, "em": time.strftime("%Y-%m-%d %H:%M"),
        "medida": medida or {}})


# ══════════════════════════════════════════════════════════════ a voz
def resumo(d: Dict[str, Any], propostas: Optional[Sequence[dict]] = None,
           fechados: Optional[Sequence[dict]] = None) -> List[str]:
    """O que ela mudou, o que está ensaiando e o que ainda é só suspeita."""
    L: List[str] = []
    ap = d.get("aplicados") or {}
    if ap:
        L.append(f"[Automelhoria] {len(ap)} ajuste(s) que ela mesma aplicou e "
                 f"que sobrevivem à próxima versão:")
        for nome, reg in list(ap.items())[:5]:
            L.append(f"[Automelhoria]   {nome}: {reg.get('antes')} → "
                     f"{reg.get('valor')}  ({reg.get('razao')}x, "
                     f"z={reg.get('z')}, em {reg.get('em')})")
    for e in (fechados or []):
        L.append(f"[Automelhoria] ensaio fechado — {e['nome']} "
                 f"{e['antes']}→{e['valor']}: {e.get('desfecho')} "
                 f"(candidato {e.get('taxa_candidato', 0):.0%} contra titular "
                 f"{e.get('taxa_titular', 0):.0%} em {e.get('cand_n')}/"
                 f"{e.get('tit_n')} janelas alternadas, {e.get('razao')}x, "
                 f"z={e.get('z')})")
    vivos = [e for e in (d.get("ensaios") or []) if e.get("ativo")]
    for e in vivos:
        L.append(f"[Automelhoria] ensaiando {e['nome']} {e['antes']}→{e['valor']} "
                 f"— candidato {e.get('cand_n', 0)}/{MIN_ENSAIO}, titular "
                 f"{e.get('tit_n', 0)}/{MIN_ENSAIO} (voltas alternadas). "
                 f"Motivo: {e.get('porque')}")
    for p in (propostas or [])[:3]:
        if not any(v.get("nome") == p.get("nome") for v in vivos):
            L.append(f"[Automelhoria] proposta em fila: {p['nome']} "
                     f"({p['para_que']}) — {p['porque']}")
    perc = d.get("percepcoes") or []
    if perc:
        L.append(f"[Percepções] {len(perc)} percepção(ões) guardada(s); as "
                 f"últimas:")
        for x in perc[-3:]:
            L.append(f"[Percepções]   {x.get('texto')}")
    if not L:
        L.append("[Automelhoria] nada a mudar ainda — nenhuma medida atual "
                 "justifica mexer em parâmetro, e mexer sem medida é passear")
    return L


def girar(autoexame: Optional[dict] = None,
          semaforo_placar: Optional[dict] = None,
          regime: Optional[dict] = None,
          eixos: Optional[dict] = None,
          padroes: Optional[Dict[str, float]] = None) -> Tuple[Dict[str, Any], List[str]]:
    """Uma volta completa: julga o que amadureceu, propõe, abre ensaio, grava.

    Devolve o estado e as linhas para o log. Quem chama não precisa saber a ordem
    das etapas -- e a ordem importa: julgar ANTES de propor, senão um ensaio
    maduro fica esperando enquanto outro é aberto no mesmo parâmetro.
    """
    d = carregar()
    fechados = julgar(d)
    props = propor(autoexame, semaforo_placar, regime, eixos)
    for p in props:
        abrir_ensaio(d, p, padroes or {})
    gravar(d)
    return d, resumo(d, props, fechados)
