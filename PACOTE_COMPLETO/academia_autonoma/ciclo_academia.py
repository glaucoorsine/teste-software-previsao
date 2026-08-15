# -*- coding: utf-8 -*-
"""Orquestra: qualidade → eventos → 12 agentes → crítico → META → catálogo → ativação."""
from __future__ import annotations
from typing import Any, Dict, List
from .schema_eventos import eventos_de_historico, DOMAIN_BY_DATASET, normalizar_valor, ROULETTE_DOMAIN, Evento
from .qualidade_dados import validar
from .agentes_descoberta import AGENTES
from .critico_cientifico import revisar, aplicar_fdr_batch
from .reformuladores import reformular
from .tribunal_revisao import ciclo_tribunal
from .meta_supervisora import decidir, motivo, marcar_fdr_sombra, MIN_SOMBRA_VALIDAR
from .ativador_familiaridades import ativar
from .catalogo_persistente import merge, listar, registrar_prospectivo, get
from .detector_regimes import detectar
from .memoria_agentes import registrar_ciclo
from .stream_seq import apply_new_events, peek_seq
from .event_log import count_new_in_window
from .unica_academia import iniciar_ciclo, finalizar_ciclo
from .dsl_hipoteses import pred_candidatos, eval_cond
from .contrato_familiaridade import para_contrato
from .bus_mensagens import publicar
from .opinioes_modelos import coletar_opinioes
from .integrador_evidencias import convergencia
from .interface_pesquisa import selecionar_cartoes, cartao_texto, candidatos_pesquisa
from .ciclo_residual import ciclo_residual, pool_meta_dinamic
from .agentes_ocorrencia import cacar as cacar_ocorrencias, resumo as resumo_ocorrencias
from .agentes_anomalia import cacar_anomalias, resumo_anomalias
from .regras_do_operador import avaliar as avaliar_regras, resumo as resumo_regras
from .hipoteses_predeclaradas import (registrar as registrar_predeclaradas,
                                      resumo as resumo_predeclaradas,
                                      avisar_mudanca_de_veredito as _avisar_pred)
from .teorias_do_operador_ct import (avaliar_ct as _av_ct,
                                     resumo_ct as _res_ct)
from .agentes_multiplicador import (cacar_multiplicadores as _cacar_mult,
                                   resumo_multiplicadores as _res_mult,
                                   analisar_agregados as _agg_mult)

# Os caçadores são caros (reordenações). Rodar a cada giro seria inviável e
# desnecessário: o retrato deles muda devagar. A cada N ciclos é suficiente.
CACADORES_A_CADA = 15
# O catálogo de relações é mais caro ainda (6000 embaralhamentos no refino) e
# responde sobre a FORMA do histórico, não sobre o último giro — não muda de
# um giro para o outro.
RELACOES_A_CADA = 60
# O crivo relê o histórico inteiro por teoria: caro, e a resposta muda devagar.
CRIVO_A_CADA = 30
_ultimo_cacar = {}
_passo_agg = {}

# Quantas teorias ainda sem amostra suficiente de sombra o catálogo tolera antes
# de os agentes pararem de propor novas. Ver "[Freio] " em _ciclo_body.
#
# Por que 60 e não 300: a barra do FDR para a k-ésima teoria do lote é
# k·alpha/m, com m = quantas estão sendo testadas ao mesmo tempo. Testar 1650
# palpites de uma vez torna a barra tão alta que uma teoria REAL de 55% precisa
# de ~23 ativações (≈850 giros, ~10h de roleta) para se provar; com a arena
# limitada, o mesmo sinal se prova em ~12-14 ativações (~5h). Não é maquiagem
# estatística: a dívida de comparação múltipla é real e a única forma honesta de
# baixá-la é gerar menos hipótese, não esconder teste.
FILA_MAX = 60
# Poda: teoria já testada o bastante e que ficou claramente abaixo do acaso não
# volta a ser reavaliada nem ocupa vaga de sombra — vira histórico.
PODA_MIN_N = 10
PODA_FATOR = 0.75


def ciclo(dataset_id: str, historico, settled=None, mults=None) -> Dict[str, Any]:
    """bruto → normalização → validação → eventos → persistência → processamento"""
    iniciar_ciclo("academia_autonoma")
    try:
        return _ciclo_body(dataset_id, historico, settled=settled, mults=mults)
    finally:
        finalizar_ciclo()

def _ciclo_body(dataset_id: str, historico, settled=None, mults=None) -> Dict[str, Any]:
    """bruto → normalização → validação → eventos → persistência → processamento"""
    msgs: List[str] = []

    settled = list(settled or [])
    dom = DOMAIN_BY_DATASET.get(dataset_id, ROULETTE_DOMAIN)
    raw = list(historico or [])
    invalidos = []
    vals = []
    for r in raw:
        v = normalizar_valor(r, dom)
        if v is None:
            invalidos.append(str(r))
        else:
            vals.append(v)
    if invalidos:
        msgs.append(f"[Qualidade] rejeitada entrada_invalida:{invalidos[:5]}")
        return {
            "msgs": msgs + ["SEM EVIDÊNCIA — qualidade rejeitada antes de persistir"],
            "candidatos": [],
            "operavel": False,
        }

    eventos_tmp = [
        Evento(valor=v, ts=settled[i] if i < len(settled) else None, event_id=f"tmp:{i}:{v}")
        for i, v in enumerate(vals)
    ]
    q = validar(eventos_tmp, dataset_id, invalidos=None)
    msgs.append(f"[Qualidade] ok={q['ok']} n={q['n']} {q.get('problemas')}")
    if not q.get("ok", True):
        return {
            "msgs": msgs + [f"SEM EVIDÊNCIA — qualidade rejeitada: {q.get('problemas')}"],
            "candidatos": [],
            "operavel": False,
        }

    info = count_new_in_window(dataset_id, vals, settled if any(x is not None for x in settled) else None)
    obs = apply_new_events(dataset_id, info["n_novos"], status=info["status"])
    stream_n = int(obs["seq"])
    msgs.append(
        f"[Stream] seq={stream_n} n_novos={obs.get('n_novos')} "
        f"novo={obs['novo_evento']} status={obs.get('status')}"
    )
    paired = info.get("paired") or []
    eventos = []
    for i, v in enumerate(vals):
        eid = paired[i][0] if i < len(paired) else f"{dataset_id}:{v}:tmp{i}"
        eventos.append(Evento(valor=v, ts=settled[i] if i < len(settled) else None, event_id=eid))
    hist = [e.valor for e in eventos]

    from collections import Counter
    for t in listar(dataset_id):
        pend = (t.get("prospectivo") or {}).get("pendente")
        if not pend:
            continue
        fp_aberto = pend.get("hist_fingerprint")
        opened_seq = pend.get("opened_seq")
        legacy = not (
            isinstance(fp_aberto, (list, tuple))
            and len(fp_aberto) >= 1
            and str(fp_aberto[0]) == "seq"
        )
        if legacy:
            t["prospectivo"] = t.get("prospectivo") or {}
            t["prospectivo"]["pendente"] = None
            t["prospectivo"]["migracao_pendente_invalidada"] = True
            merge(t)
            msgs.append(f"[Migração] pendente legado invalidado id={str(t.get('id'))[:8]}")
            continue
        if not obs["novo_evento"]:
            continue
        if opened_seq is not None and int(opened_seq) >= stream_n:
            continue
        alvos = pend.get("alvos") or []
        hit = str(hist[0]) in [str(x) for x in alvos]
        freq = Counter([str(x) for x in hist[1:31]])
        k = max(1, len(alvos))
        base_alvos = [x for x, _ in freq.most_common(k)]
        base_hit = str(hist[0]) in base_alvos
        registrar_prospectivo(
            t["id"], hist[0], hit, dataset_id=dataset_id,
            candidatos=alvos, fingerprint=["seq", stream_n],
            baseline_hit=base_hit, baseline_alvos=base_alvos,
        )
        msgs.append(
            f"[Sombra] {str(t.get('descricao'))[:40]}: "
            f"{'HIT' if hit else 'MISS'} saiu={hist[0]} seq={stream_n}"
        )
    if not obs["novo_evento"] and obs.get("status") not in ("BOOTSTRAP_SEM_TS", "BOOTSTRAP"):
        # já inicializado e snapshot idêntico → não reprocessa agentes
        msgs.append("[Stream] snapshot repetido — sem avaliar sombra")
        return {
            "msgs": msgs + ["SEM EVIDÊNCIA — snapshot inalterado"],
            "candidatos": [],
            "operavel": False,
            "same_snapshot": True,
        }
    if not obs["novo_evento"]:
        msgs.append("[Stream] snapshot sem evento novo — processa descoberta, sem sombra")

    if q["n"] < 8:
        return {"msgs": msgs + ["SEM EVIDÊNCIA — amostra curta"], "candidatos": [], "operavel": False}

    dominio = sorted(DOMAIN_BY_DATASET.get(dataset_id, ROULETTE_DOMAIN))

    # --- FREIO DE PRODUÇÃO ---------------------------------------------
    # Uma teoria só valida com sombra prospectiva, e sombra só acumula quando o
    # gatilho dela dispara ao vivo. Isso é um recurso ESCASSO: um gatilho
    # `transition a→b` dispara em ~1/37 dos giros, então juntar as 8 amostras
    # mínimas custa ~300 giros. Enquanto isso os 12 agentes propõem ~80 teorias
    # NOVAS por ciclo, todas disputando os mesmos giros. Resultado medido sem o
    # freio: 1354 teorias no catálogo, 62% delas com ZERO amostra, 1 validada.
    # O gargalo não é falta de ideia, é falta de teste. Quando a fila de
    # imaturas satura, os agentes calam a boca e o ciclo gasta o tempo testando
    # o que já está na fila.
    cat_atual_freio = listar(dataset_id)
    # Conta a ARENA inteira (madura + imatura), não só a fila de imaturas: é o
    # total simultâneo que entra no m do FDR. Contando só imaturas, a fila
    # esvaziava conforme elas amadureciam, a descoberta voltava, e o catálogo
    # inflava do mesmo jeito — medido: 1562 teorias mesmo com o freio ligado.
    # Só validada e arquivada saem da conta: a primeira já se provou, a segunda
    # já respondeu. Quem libera vaga é a poda, não o tempo.
    _arena = [
        t for t in cat_atual_freio
        if (t.get("estado") or "") not in (
            "descartada_pelo_tribunal", "arquivada",
        ) and not (t.get("estado") or "").startswith("validada")
    ]
    descobrir = len(_arena) < FILA_MAX
    if not descobrir:
        msgs.append(
            f"[Freio] arena={len(_arena)} ≥ {FILA_MAX} — descoberta pausada, "
            f"ciclo dedicado a testar quem já está na arena"
        )

    propostas = []
    for ag in (AGENTES if descobrir else []):
        try:
            found = ag.propor(eventos, dataset_id, set(dominio)) or []
            msgs.append(f"[{ag.id} {ag.nome}] {len(found)} hipóteses DSL")
            propostas.extend(found)
            try:
                registrar_ciclo(
                    dataset_id, ag.id, len(found),
                    regioes=[str(f.get("descricao") or "")[:40] for f in found],
                    exprs=[str(f.get("expr") or "")[:80] for f in found],
                )
            except Exception as e:
                msgs.append(f"[{ag.id}] mem: {e}")
        except Exception as e:
            msgs.append(f"[{ag.id}] erro: {e}")

    # dedupe por id
    seen = set()
    uniq = []
    for t in propostas:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        uniq.append(t)

    msgs.append(f"[Crítico] revisando {len(uniq)}…")
    val = teste = rej = 0
    # Crítico em 2 estágios. Motivo: o p-valor empírico (permutação) tem piso
    # 1/(n_perm+1); com N_PERM_RAPIDO=50 esse piso é 0,0196 — matematicamente
    # incapaz de sobreviver ao corte de Benjamini-Hochberg (FDR) contra o lote
    # inteiro de candidatas por ciclo (~40-90), mesmo pra uma regra 100%
    # determinística (confirmado por teste: q≈0,25-0,81 sempre >0,10). Rodar
    # N_PERM_PRECISO pra TODAS as candidatas seria ~20x mais lento por ciclo.
    # Solução: 50 permutações pra descartar o óbvio (barato, aplicado a todas);
    # só quem sobra da triagem — na prática poucas — é recalculada com muito
    # mais permutações, dando piso de p-valor fino o bastante pra ter chance
    # real de sobreviver ao FDR quando o sinal é de fato real.
    N_PERM_RAPIDO = 50
    N_PERM_PRECISO = 2000
    revisadas = []
    for t in uniq:
        revisadas.append(revisar(t, hist, dominio, n_perm=N_PERM_RAPIDO))
    # Crítico observacional: não joga fora por p-valor; só estrutura inválida sai
    vivas = [t for t in revisadas if not t.get("rejeicao_dura")]
    promissoras = [t for t in vivas if t.get("critica_ok") or t.get("destino_critico") == "promissora"]
    a_reformular = [t for t in vivas if t.get("destino_critico") in ("reavaliar_variante", "reprovar_enviar_tribunal")]
    msgs.append(
        f"[Crítico observacional] total={len(revisadas)} vivas={len(vivas)} "
        f"promissoras={len(promissoras)} reformular={len(a_reformular)}"
    )
    if promissoras:
        refinadas_por_id = {}
        for t in promissoras:
            refinadas_por_id[t["id"]] = revisar(t, hist, dominio, n_perm=N_PERM_PRECISO)
        revisadas = [refinadas_por_id.get(t["id"], t) for t in revisadas]
    novas_var = []
    for t in a_reformular[:6]:
        try:
            novas_var.extend(reformular(t, hist, dominio, max_var=6) or [])
        except Exception as e:
            msgs.append(f"[Reformuladores] erro {t.get('id')}: {e}")
    if novas_var:
        msgs.append(f"[Reformuladores] {len(novas_var)} variantes (R1–R7)")
        for v in novas_var:
            revisadas.append(revisar(v, hist, dominio, n_perm=N_PERM_RAPIDO))
    revisadas = aplicar_fdr_batch(revisadas)
    uniq = revisadas
    # As teorias JÁ MADURAS do catálogo entram na rodada da META mesmo sem terem
    # sido repropostas neste ciclo. Sem isso uma teoria só é reavaliada quando
    # algum agente por acaso a propõe de novo (~20 de 95 por ciclo, ou seja uma
    # volta a cada ~68 ciclos) — ela pode bater a amostra mínima e ficar horas
    # esperando alguém olhar. Não custa permutação: `decidir` lê a sombra, e a
    # crítica retrospectiva delas já está gravada.
    _ja = {t["id"] for t in uniq}
    _maduras = [
        t for t in cat_atual_freio
        if t.get("id") not in _ja
        and int((t.get("prospectivo") or {}).get("n") or 0) >= MIN_SOMBRA_VALIDAR
        and (t.get("estado") or "") not in ("descartada_pelo_tribunal", "arquivada")
    ]
    if _maduras:
        uniq = uniq + _maduras
        msgs.append(f"[META/maduras] +{len(_maduras)} teorias do catálogo reavaliadas (sem repropor)")
    # hidrata a sombra persistida ANTES da META (a decisão depende dela)
    for t in uniq:
        old = get(t["id"], dataset_id)
        if old:
            t["prospectivo"] = old.get("prospectivo") or t.get("prospectivo") or {}
            t["episodios_ativacao"] = old.get("episodios_ativacao") or []
            t["versoes_anteriores"] = old.get("versoes_anteriores") or []
            if old.get("retrospectivo") and not t.get("retrospectivo"):
                t["retrospectivo"] = old["retrospectivo"]
            t["criado_em"] = old.get("criado_em")
    # FDR sobre a sombra prospectiva do lote inteiro: controla o efeito de
    # avaliar centenas de teorias ao mesmo tempo (sem ele, algumas passam por
    # sorte só pelo volume). Ver meta_supervisora.marcar_fdr_sombra.
    marcar_fdr_sombra(uniq)
    _com_sombra = sum(1 for t in uniq if (t.get("evidencia_sombra") or {}).get("p_sombra") is not None)
    if _com_sombra:
        msgs.append(f"[Sombra/FDR] {_com_sombra} teorias com sombra suficiente avaliadas no lote")
    for t in uniq:
        estado = decidir(t)
        t["estado"] = estado
        t["motivo_meta"] = motivo(t, estado)
        t = ativar(t, hist, dominio, regime=detectar(hist))
        merge(t)
        if estado.startswith("validada"):
            val += 1
        elif estado == "em_teste":
            teste += 1
        else:
            rej += 1
        msgs.append(
            f"[META] {t['id'][:8]}… {t.get('descricao')[:40]} → {estado}/{t.get('ativacao')} "
            f"| {t.get('motivo_critica')}"
        )

    # --- DESCANSO (era PODA) ---------------------------------------------
    #
    # Decisão dele, 15/08: "da forma que você colocou ela retira teorias que
    # muitas vezes aparentam não funcionar devido ao momento, e logo poda elas.
    # Concordo com uma régua, mas não naqueles moldes extremos."
    #
    # Ele está certo. Uma teoria que vai mal agora pode ir bem daqui a uma
    # hora — a mesa muda de mão, de ritmo, de crupiê. Arquivar era jogar fora
    # o que só estava dormindo, e teoria arquivada não voltava nunca: ela saía
    # das varreduras de contrato e de sombra dos ciclos seguintes.
    #
    # Agora ela DESCANSA em vez de morrer. Sai da fila enquanto está ruim, mas
    # continua no catálogo, continua sendo reavaliada, e volta sozinha quando
    # o desempenho recente melhora. Nada é apagado.
    descansando = acordadas = 0
    for t in uniq:
        if (t.get("estado") or "").startswith("validada"):
            continue
        s = t.get("evidencia_sombra") or {}
        n = int(s.get("n") or 0)
        taxa = s.get("taxa")
        base = s.get("baseline")
        estado = t.get("estado") or ""
        if n >= PODA_MIN_N and taxa is not None and base and taxa < base * PODA_FATOR:
            if estado != "descansando":
                t["estado"] = "descansando"
                t["motivo_meta"] = (f"descansando: {taxa:.0%} em {n} ativações "
                                    f"vs acaso {base:.0%} — volta se melhorar")
                merge(t)
                descansando += 1
        elif estado == "descansando" and taxa is not None and base and taxa >= base:
            # voltou a acompanhar o acaso: acorda e disputa vaga de novo
            t["estado"] = "em_teste"
            t["motivo_meta"] = f"acordou: {taxa:.0%} vs acaso {base:.0%}"
            merge(t)
            acordadas += 1
    # --- CRIVO RETROSPECTIVO ----------------------------------------------
    # Regra dele: toda teoria passa pelo crivo do histórico, e quem acerta umas
    # duas ou três vezes vale o dia. A barra é baixa de propósito, porque quem
    # decide o número final é o consenso -- uma teoria fraca não manda em nada,
    # só acrescenta um voto. O peso de cada voto sai daqui.
    try:
        if stream_n % CRIVO_A_CADA == 0 and len(hist) >= 200:
            from .crivo_retrospectivo import peneirar as _peneirar, resumo as _res_crivo
            _vivas = [t for t in cat_atual_freio
                      if (t.get("estado") or "") not in ("descartada_pelo_tribunal",)]
            _cr = _peneirar(_vivas, hist, sorted(dom))
            for _l in _res_crivo(_cr).split("\n"):
                msgs.append(_l)
            for _t in (_cr.get("aptas") or []):
                _t["apta_hoje"] = True
                _t["peso_crivo"] = (_t.get("crivo") or {}).get("peso", 1.0)
                merge(_t)
            for _t in (_cr.get("fora") or []):
                if _t.get("apta_hoje"):
                    _t["apta_hoje"] = False
                    merge(_t)
    except Exception as e:
        msgs.append(f"[Crivo] erro: {type(e).__name__}: {e}")

    if descansando:
        msgs.append(f"[Descanso] {descansando} teorias postas para descansar "
                    f"(continuam no catálogo e voltam se melhorarem)")
    if acordadas:
        msgs.append(f"[Descanso] {acordadas} teorias ACORDARAM e voltaram à fila")

    # --- CAÇADORES DE OCORRÊNCIA E DE ANOMALIA ---------------------------
    # Eles não propõem teoria na DSL: varrem atributos do resultado (finais,
    # setor, Voisins, salto, rajada…) e o que foge do padrão. Entram aqui para
    # que os candidatos deles cheguem ao consenso junto com as teorias.
    cand_cacadores = []
    _n = _ultimo_cacar.get(dataset_id, 0)
    _ultimo_cacar[dataset_id] = _n + 1
    if _n % CACADORES_A_CADA == 0 and len(hist) >= 60:
        try:
            _roc = cacar_ocorrencias(hist)
            for _l in resumo_ocorrencias(_roc).split("\n"):
                msgs.append(_l)
            cand_cacadores.extend(str(x) for x in (_roc.get("candidatos") or []))
        except Exception as e:
            msgs.append(f"[Ocorrências] erro: {type(e).__name__}: {e}")
        # regras ditadas pelo operador — conjunto PRÉ-DECLARADO, medido igual
        # a qualquer outra hipótese. Vale mais que varredura cega: 35 perguntas
        # declaradas contra 1369 transições possíveis.
        try:
            _rr = avaliar_regras(hist)
            for _l in resumo_regras(_rr).split("\n"):
                msgs.append(_l)
            cand_cacadores.extend(str(x) for x in (_rr.get("candidatos") or []))
        except Exception as e:
            msgs.append(f"[Regras do operador] erro: {type(e).__name__}: {e}")
        # A14 — o GERADOR de relações. Não é um catálogo que eu escrevi: as
        # relações são montadas cruzando atributos do número (final, dezena,
        # posição na roda, dúzia, coluna, cor, paridade, soma dos dígitos) com
        # comparadores (igual, difere de k, perto de k na roda, somam k). Dá
        # 135 relações, e nelas cabe coisa que não me ocorreria — foi assim que
        # o teste achou "posição na roda anda 9 casas", que eu nunca escrevi.
        #
        # Roda de vez em quando porque a régua é cara e o que ela responde não
        # muda a cada giro: é sobre a forma do histórico, não sobre o último
        # número.
        try:
            if _n % RELACOES_A_CADA == 0:
                from .gerador_relacoes import varrer as _varrer, resumo as _res_rel
                _rel = _varrer(hist)
                for _l in _res_rel(_rel).split("\n"):
                    msgs.append(_l)
        except Exception as e:
            msgs.append(f"[Relações] erro: {type(e).__name__}: {e}")
        try:
            _ran = cacar_anomalias(hist)
            for _l in resumo_anomalias(_ran).split("\n"):
                msgs.append(_l)
            cand_cacadores.extend(str(x) for x in (_ran.get("candidatos") or []))
        except Exception as e:
            msgs.append(f"[Anomalias] erro: {type(e).__name__}: {e}")
        # Hipoteses PRE-DECLARADAS: formula travada antes do dado novo. Nao
        # entram como candidatas a sugestao -- entram como compromisso sendo
        # cobrado. O `settled` serve de identidade estavel do giro, para a
        # contagem atravessar noites sem contar o mesmo giro duas vezes.
        try:
            _cron, _ids = [], []
            for _k in range(len(hist) - 1, -1, -1):
                try:
                    _cron.append(int(hist[_k]))
                except (TypeError, ValueError):
                    continue
                _ids.append(str(settled[_k]) if (settled and _k < len(settled))
                            else f"p{_k}")
            if len(_cron) >= 61:
                registrar_predeclaradas(dataset_id, _cron, _ids)
                _lp = resumo_predeclaradas(dataset_id)
                if _lp:
                    for _l in _lp.split("\n"):
                        msgs.append(_l)
                # o desfecho pode cair as tres da manha: avisa no celular
                for _av in (_avisar_pred(dataset_id) or []):
                    msgs.append(f"[Pre-declaradas] >>> {_av}")
        except Exception as e:
            msgs.append(f"[Pre-declaradas] erro: {type(e).__name__}: {e}")
        # As quatro teorias que o operador ditou para o Crazy Time. Falam de
        # eventos raros (o CrazyBonus sai 1 vez em 54 giros), entao passam
        # muito tempo em "amostra pequena" -- e e' exatamente por isso que
        # ficam registradas: a mesa roda todo dia e o contador nao esquece.
        # os quinze do multiplicador: so onde existe multiplicador
        if dataset_id in ("lightning", "mega_fire"):
            try:
                _evs = []
                try:
                    from fluxo_captura import buffer_path, _purge_invalid
                    import json as _json
                    _d = _json.loads(buffer_path(dataset_id).read_text(encoding="utf-8"))
                    _evs = sorted(_purge_invalid(_d.get("events") or [], dataset_id),
                                  key=lambda e: e.get("settled") or "")
                except Exception:
                    _evs = []
                if _evs:
                    for _l in _res_mult(_cacar_mult(_evs)).split("\n"):
                        msgs.append(_l)
                # agregados dos sites: milhares de premiacoes ja contadas,
                # respondem sozinhos o que a coleta ao vivo levaria semanas
                _n_agg = _passo_agg.get(dataset_id, 0)
                _passo_agg[dataset_id] = _n_agg + 1
                if _n_agg % 60 == 0:
                    try:
                        from coletor_sites import buscar_agregados
                        _agg, _err = buscar_agregados(dataset_id)
                        if _agg:
                            _lista = _agg_mult(_agg)
                            _m = sum(1 for a in _lista if a.get("p") is not None)
                            for a in _lista:
                                if a.get("p") is None or a["p"] > 0.10:
                                    continue
                                msgs.append(f"[Sites] {a['achado']}: "
                                            f"{a['hits']}/{a['n']} p={a['p']:.4f}")
                        elif _err:
                            msgs.append(f"[Sites] agregados: {_err}")
                    except Exception as _e:
                        msgs.append(f"[Sites] erro: {type(_e).__name__}")
            except Exception as e:
                msgs.append(f"[Multiplicadores] erro: {type(e).__name__}: {e}")
        if dataset_id == "crazy_time":
            try:
                _rct = _av_ct([str(x) for x in reversed(hist)])
                _l = _res_ct(_rct)
                if _l:
                    for _x in _l.split("\n"):
                        msgs.append(_x)
            except Exception as e:
                msgs.append(f"[Teorias do operador] erro: {type(e).__name__}: {e}")

    regime = detectar(hist)
    msgs.append(f"[Regime] {regime.get('regime')} dist={regime.get('js')} ")
    msgs.append(f"[Catálogo] ciclo val={val} teste={teste} rej={rej} total_ds={len(listar(dataset_id))}")

    cycle_id = None
    try:
        cycle_id = publicar(dataset_id, "meta.decisao", "META", {
            "val": val, "teste": teste, "rej": rej,
        })["cycle_id"]
    except Exception as e:
        msgs.append(f"[Bus] erro: {e}")

    
    # --- TRIBUNAL DE REVISÃO (7 IAs) + META ---
    # Reavalia o que o crítico não validou. Regra: >=3 acertos em 10 ativações.
    try:
        cat_atual = listar(dataset_id)
        tri = ciclo_tribunal(dataset_id, hist, dominio, cat_atual, merge_fn=merge, max_julgamentos=12)
        msgs.extend(tri.get("msgs") or [])
        msgs.append(
            f"[Tribunal] julgadas={tri.get('julgadas')} "
            f"aprovadas={len(tri.get('aprovadas') or [])} "
            f"reprovadas={len(tri.get('reprovadas') or [])} "
            f"em_revisao={len(tri.get('em_revisao') or [])} | regra={tri.get('regra')}"
        )
    except Exception as e:
        msgs.append(f"[Tribunal] erro: {e}")

    # Contratos + opiniões independentes + integrador
    contratos = []
    cartoes_info = []
    for t in listar(dataset_id):
        if (t.get("estado") or "") in ("arquivada", "descartada_pelo_tribunal"):
            continue
        if t.get("ativacao") not in (
            "ATIVA", "REATIVAÇÃO_EM_TESTE", "QUARENTENA_SOMBRA", "DORMENTE", "DEGRADADA"
        ):
            if not (t.get("estado") or "").startswith("validada") and t.get("estado") not in ("em_teste", "reativada", "candidata", "em_observacao_viva", "reavaliar_variante", "em_revisao_tribunal", "validada_dormente", "promissora"):
                continue
        contrato = para_contrato(t)
        opinioes = coletar_opinioes(hist, contrato, dominio)
        for op in opinioes:
            try:
                publicar(dataset_id, "modelo.opiniao", op.get("modelo"), op, cycle_id=cycle_id)
            except Exception as _e:
                msgs.append(f"[warn] {_e}")
        conv = convergencia(contrato, opinioes, qualidade_ok=q.get("ok", False))
        contrato["_convergencia"] = conv
        contrato["_opinioes"] = opinioes
        contratos.append(contrato)
        # Sombra: ATIVA, reativação OU quarentena (em_teste com contexto)
        # Quebra o deadlock: em_teste + contexto → abre 1ª sombra
        pode_sombra = t.get("ativacao") in (
            "ATIVA", "REATIVAÇÃO_EM_TESTE", "QUARENTENA_SOMBRA"
        ) or (
            t.get("estado") == "em_teste" and eval_cond(t.get("expr") or {}, hist)
        )
        if pode_sombra and eval_cond(t.get("expr") or {}, hist):
            cs = pred_candidatos(t.get("expr") or {}, hist, dominio, k=7)
            t["prospectivo"] = t.get("prospectivo") or {}
            if not t["prospectivo"].get("pendente") and cs:
                cur = peek_seq(dataset_id)
                t["prospectivo"]["pendente"] = {
                    "alvos": cs[:7],
                    "head": hist[0],
                    "hist_fingerprint": ["seq", cur],
                    "opened_seq": cur,
                }
                merge(t)
                try:
                    publicar(dataset_id, "sombra.registrada", "SOMBRA", {
                        "familiaridade_id": t.get("id"), "alvos": cs[:7],
                    }, cycle_id=cycle_id)
                except Exception as _e:
                    msgs.append(f"[warn] {_e}")

    cartoes = selecionar_cartoes(contratos, max_n=7)
    for c in cartoes:
        txt = cartao_texto(c, c.get("_opinioes"), c.get("_convergencia"))
        msgs.append("[Cartão]\n" + txt)
        cartoes_info.append({"contrato": c, "texto": txt})

    cands = candidatos_pesquisa(cartoes, hist, dominio, max_n=7)
    if not cartoes:
        msgs.append("[Interface] SEM EVIDÊNCIA — nenhuma familiaridade ativa com validação suficiente.")
    else:
        msgs.append(f"[Interface] {len(cartoes)} familiaridade(s) | candidatos_pesquisa={cands}")

    try:
        publicar(dataset_id, "interface.atualizar", "INTERFACE", {
            "n_cartoes": len(cartoes), "candidatos": cands,
        }, cycle_id=cycle_id)
    except Exception as _e:
        msgs.append(f"[warn] {_e}")

    # operavel só se integrador CONVERGENTE em pelo menos 1
    operavel = any(
        (c.get("_convergencia") or {}).get("status") == "CONVERGENTE"
        for c in cartoes
    )
    # --- Academia Residual ---

    try:
        head_eid = eventos[0].event_id if eventos else f"{dataset_id}:x"
        res = ciclo_residual(
            dataset_id, hist,
            cartoes_fam=[c for c in cartoes],
            padroes_cands=cands,
            event_id=f"{head_eid}:s{stream_n}",
            novo_evento=bool(obs.get("novo_evento")),
            stream_n=stream_n,
        )
        msgs.extend(res.get("msgs") or [])
        cartoes_res = res.get("cartoes_residuais") or []
    except Exception as e:
        msgs.append(f"[Residual] erro: {e}")
        cartoes_res = []
        res = {"candidatos": []}

    # contratos fam para pool
    fam_contratos = [c for c in cartoes]
    pad_items = []
    if cands:
        pad_items.append({
            "categoria": "PADRAO", "descricao": f"padrao/consenso {cands[:5]}",
            "estado_ativacao": "ATIVA" if operavel else "SEM_EVIDÊNCIA",
            "estado_historico": "em_teste",
            "amostra_prospectiva": 0, "efeito_vs_baseline": None,
            "expressao_dsl": {"op": "in_set", "set": cands[:5]},
            "_convergencia": {"status": "FRACO" if cands else "SEM_EVIDÊNCIA", "indice": 0.2},
        })

    pool = pool_meta_dinamic(pad_items, fam_contratos, cartoes_res, max_n=7)
    msgs.append(
        f"[META pool] n={pool['n']} composicao={pool['composicao']} "
        f"(sem quotas fixas)"
    )
    if pool["n"] == 0:
        msgs.append("[Interface] SEM EVIDÊNCIA — nenhuma análise atingiu os requisitos neste ciclo.")

    # candidatos finais do pool (pesquisa)
    cands_final = []
    # candidatos dos caçadores entram primeiro: eles vêm de varredura com régua
    # própria e são independentes das teorias da DSL
    for x in cand_cacadores[:4]:
        if x not in cands_final:
            cands_final.append(x)
    for it in pool["itens"]:
        for x in pred_candidatos(it.get("expressao_dsl") or {}, hist, dominio, k=3):
            if x not in cands_final:
                cands_final.append(x)
        if len(cands_final) >= 7:
            break

    out = {
        "msgs": msgs,
        "candidatos": cands_final[:7],
        "operavel": operavel and pool["n"] > 0,
        "n_propostas": len(uniq),
        "n_catalogo": len(listar(dataset_id)),
        "cartoes": cartoes_info,
        "n_cartoes": pool["n"],
        "pool": pool,
        "residuais": res if isinstance(res, dict) else {},
    }
    return out
