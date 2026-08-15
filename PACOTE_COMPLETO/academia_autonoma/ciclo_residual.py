# -*- coding: utf-8 -*-
"""
Ciclo residual + pool dinâmico 0-7 sem quotas.
"""
from __future__ import annotations
from typing import Any, Dict, List
from .residuo_core import congelar_opinioes, avaliar_congeladas, listar_residuos
from .agentes_residuais import AGENTES_R
from .critico_cientifico import revisar, aplicar_fdr_batch
from .meta_supervisora import decidir, motivo
from .ativador_familiaridades import ativar
from .catalogo_persistente import merge, listar, registrar_prospectivo
from .contrato_familiaridade import para_contrato
from .opinioes_modelos import coletar_opinioes
from .integrador_evidencias import convergencia
from .interface_pesquisa import selecionar_cartoes, cartao_texto, candidatos_pesquisa
from .bus_mensagens import publicar
from .schema_eventos import DOMAIN_BY_DATASET

def montar_candidatos_fontes(hist, dominio, cartoes_fam, padroes_cands=None):
    """Congela o que cada fonte previa ANTES do próximo resultado."""
    padroes_cands = padroes_cands or []
    fam_cands = []
    for c in cartoes_fam or []:
        from .dsl_hipoteses import pred_candidatos
        fam_cands.extend(pred_candidatos(c.get("expressao_dsl") or {}, hist, dominio, k=3))
    # dedupe preserve order
    def uniq(xs):
        o=[]
        for x in xs:
            s=str(x)
            if s not in o: o.append(s)
        return o
    return {
        "PADRAO": uniq(padroes_cands)[:5],
        "FAMILIARIDADE": uniq(fam_cands)[:5],
        "ESTATISTICO": uniq([x for x,_ in __import__("collections").Counter(hist[:30]).most_common(5)])[:5],
        "LSTM": uniq(hist[:3] + padroes_cands[:2])[:5],
        "REGIME": uniq([__import__("collections").Counter(hist[:12]).most_common(1)[0][0]] if hist else [])[:5],
        "ANOMALIA": uniq([h for h in hist[:5] if hist[5:30].count(h)==0][:3]) if len(hist)>30 else [],
    }

def ciclo_residual(dataset_id: str, hist: List[str], cartoes_fam=None, padroes_cands=None, event_id=None, novo_evento: bool = True, stream_n: int = 0) -> Dict[str, Any]:
    msgs=[]
    from .schema_eventos import ROULETTE_DOMAIN
    dominio=sorted(DOMAIN_BY_DATASET.get(dataset_id, ROULETTE_DOMAIN))
    if not hist:
        return {"msgs":["SEM_DADOS"], "cartoes_residuais":[], "candidatos":[]}

    if not novo_evento:
        return {
            "msgs": ["[Residual] snapshot repetido — sem avaliar/congelar"],
            "cartoes_residuais": [],
            "candidatos": [],
        }


    # fecha sombras residuais (fingerprint)
    from .stream_seq import peek_seq
    from collections import Counter
    cur_seq = peek_seq(dataset_id)
    for t in listar(dataset_id):
        if not str(t.get("autor", "")).startswith("R"):
            continue
        pend = (t.get("prospectivo") or {}).get("pendente")
        if not pend:
            continue
        opened_seq = pend.get("opened_seq")
        fp_aberto = pend.get("hist_fingerprint")
        is_legacy = not (isinstance(fp_aberto, (list, tuple)) and fp_aberto and fp_aberto[0] == "seq")
        if opened_seq is None and is_legacy:
            t["prospectivo"] = t.get("prospectivo") or {}
            t["prospectivo"]["pendente"] = None
            merge(t)
            continue
        if opened_seq is not None and int(opened_seq) >= cur_seq:
            continue
        alvos = pend.get("alvos") or []
        hit = str(hist[0]) in [str(x) for x in alvos]
        freq = Counter([str(x) for x in hist[1:31]])
        base_alvos = [x for x, _ in freq.most_common(max(1, len(alvos)))]
        registrar_prospectivo(
            t["id"], hist[0], hit, dataset_id=dataset_id,
            candidatos=alvos, fingerprint=["seq", cur_seq],
            baseline_hit=(str(hist[0]) in base_alvos), baseline_alvos=base_alvos,
        )

    # 1) avalia congeladas anteriores com resultado atual (hist[0])
    novos = avaliar_congeladas(dataset_id, hist[0], max_n=3)
    for r in novos:
        msgs.append(
            f"[Resíduo] {r.get('classificacao')} score={r.get('residual_score')} "
            f"saiu={r.get('resultado_observado')} consenso={r.get('consenso_total')}"
        )
        try:
            publicar(dataset_id, "sombra.avaliada", "RESIDUAL", r)
        except Exception as _ignore:
            _ = _ignore  # ignorado de forma explícita

    # 2) congela opiniões atuais para o PRÓXIMO evento (ainda sem saber t+1)
    cands_fontes = montar_candidatos_fontes(hist, dominio, cartoes_fam, padroes_cands)
    opin = {k: (0.6 if v else 0.1) for k,v in cands_fontes.items()}
    from .stream_seq import peek_seq as _ps
    _eid = event_id or f"{dataset_id}:{hist[0]}:seq{_ps(dataset_id)}"
    fr = congelar_opinioes(dataset_id, _eid, hist[0], opin, cands_fontes)
    msgs.append(f"[Congelar] decision_id={fr['decision_id'][:8]}… fontes={list(cands_fontes.keys())}")

    # 3) banco residual
    residuos = listar_residuos(dataset_id, only_nao_explicado=True, limit=80)
    msgs.append(f"[Banco residual] n={len(residuos)}")

    # 4) 20 agentes
    #
    # FREIO: mesmo freio do ciclo principal, que aqui faltava. Sem ele, o freio
    # dos 12 agentes de descoberta não adiantava quase nada — medido na v66, com
    # o freio principal disparando em 369 de 370 ciclos, os residuais sozinhos
    # encheram a arena com mais de 1300 teorias (R15=368, R14=247, R05=158…,
    # contra 26 dos agentes A*). Como o m do FDR conta TODAS as teorias em teste
    # simultâneo, esse vazamento mantinha a barra alta e encarecia provar um
    # vício real: ~20 ativações em vez de ~14.
    from .ciclo_academia import FILA_MAX as _FILA_MAX
    _arena_res = [
        t for t in listar(dataset_id)
        if (t.get("estado") or "") not in ("descartada_pelo_tribunal", "arquivada")
        and not (t.get("estado") or "").startswith("validada")
    ]
    _descobrir_res = len(_arena_res) < _FILA_MAX
    if not _descobrir_res:
        msgs.append(
            f"[Freio/residual] arena={len(_arena_res)} ≥ {_FILA_MAX} — "
            f"agentes residuais pausados neste ciclo"
        )

    propostas=[]
    for ag in (AGENTES_R if _descobrir_res else []):
        try:
            found=ag.propor(residuos, hist, set(dominio), dataset_id) or []
            try:
                from .memoria_agentes import registrar_ciclo
                regs = []
                for ft in found:
                    d = str(ft.get("descricao") or ft.get("id") or "")[:40]
                    if d:
                        regs.append(d)
                registrar_ciclo(
                    dataset_id, ag.id, len(found),
                    nota="residual",
                    regioes=regs,
                    exprs=[str((ft.get("expr") or {}))[:80] for ft in found],
                )
            except Exception as _e:
                msgs.append(f"[{ag.id}] mem:{_e}")
            if found:
                msgs.append(f"[{ag.id} {ag.nome}] {len(found)} hipóteses residuais")
            propostas.extend(found)
        except Exception as e:
            msgs.append(f"[{ag.id}] erro: {e}")

    # dedupe
    seen=set(); uniq=[]
    for t in propostas:
        if t["id"] in seen: continue
        seen.add(t["id"]); uniq.append(t)

    # 5) crítico + meta (mesmo pipeline; dataset residual separado por tag no dominio)
    val=teste=rej=0
    contratos_res=[]
    revisadas=[]
    for t in uniq:
        t["dataset_id"]=dataset_id
        t=revisar(t, hist, dominio)
        if t.get("exige_nulo") and float((t.get("teste_negativo") or {}).get("p_valor_emp") or 1)>0.2:
            t["critica_ok"]=False
            t["motivo_critica"]=(t.get("motivo_critica") or "")+"; nulo_residual_falhou"
        revisadas.append(t)
    # aplicar_fdr_batch() perdeu o parâmetro `alpha` quando o crítico foi
    # reescrito (agora o alpha é fixo dentro da função). Esta chamada não
    # acompanhou a mudança e crashava com TypeError.
    uniq=aplicar_fdr_batch(revisadas)
    # hidratar sombra residual do mesmo dataset antes da META
    from .catalogo_persistente import get as _get
    for t in uniq:
        old = _get(t["id"], dataset_id)
        if old:
            t["prospectivo"] = old.get("prospectivo") or t.get("prospectivo") or {}
            t["episodios_ativacao"] = old.get("episodios_ativacao") or []
            t["criado_em"] = old.get("criado_em")
    # mesmo controle de lote do ciclo principal: sem isso, este caminho
    # decidia teoria a teoria e escapava do FDR sobre a sombra.
    from .meta_supervisora import marcar_fdr_sombra as _marcar_fdr
    _marcar_fdr(uniq)
    for t in uniq:
        estado = decidir(t)
        # residual: quarentena extra SÓ se ainda não tem sombra suficiente
        n_sh = int((t.get("prospectivo") or {}).get("n") or 0)
        if estado.startswith("validada") and n_sh < 12:
            estado = "em_teste"
        t["estado"] = estado
        t["origem"]="RESIDUAL"
        from .detector_regimes import detectar as _det
        t=ativar(t, hist, dominio, regime=_det(hist))
        merge(t)
        if estado=="em_teste": teste+=1
        elif estado.startswith("validada"): val+=1
        else: rej+=1
        # sombra residual: mesma regra de quarentena
        from .dsl_hipoteses import eval_cond, pred_candidatos
        if (t.get("ativacao") in ("ATIVA", "REATIVAÇÃO_EM_TESTE", "QUARENTENA_SOMBRA")
                or t.get("estado") == "em_teste") and eval_cond(t.get("expr") or {}, hist):
            cs = pred_candidatos(t.get("expr") or {}, hist, dominio, k=5)
            t["prospectivo"] = t.get("prospectivo") or {}
            if not t["prospectivo"].get("pendente") and cs:
                from .stream_seq import peek_seq as _peek
                _cs = _peek(dataset_id)
                t["prospectivo"]["pendente"] = {
                    "alvos": cs[:5],
                    "head": hist[0],
                    "hist_fingerprint": ["seq", _cs],
                    "opened_seq": _cs,
                }
                merge(t)
        c=para_contrato(t)
        c["categoria"]="RESIDUAL"
        opinioes=coletar_opinioes(hist, c, dominio)
        conv=convergencia(c, opinioes, True)
        c["_convergencia"]=conv
        c["_opinioes"]=opinioes
        contratos_res.append(c)

    msgs.append(f"[META residual] teste={teste} rej={rej} (val direta bloqueada — quarentena)")

    cartoes=selecionar_cartoes(contratos_res, max_n=7)
    for c in cartoes:
        msgs.append("[Cartão RESIDUAL]\n"+cartao_texto(c, c.get("_opinioes"), c.get("_convergencia")))

    cands=candidatos_pesquisa(cartoes, hist, dominio, max_n=7)
    return {
        "msgs": msgs,
        "cartoes_residuais": cartoes,
        "candidatos": cands,
        "n_residuos_banco": len(residuos),
        "n_propostas": len(uniq),
    }

def pool_meta_dinamic(
    padroes: List[dict],
    familiaridades: List[dict],
    residuais: List[dict],
    max_n: int = 7,
) -> Dict[str, Any]:
    """
    Pool único sem quotas. Diversidade por penalização de redundância.
    Retorna 0..7 itens.
    """
    pool=[]
    for p in padroes or []:
        p=dict(p); p["categoria"]=p.get("categoria") or "PADRAO"; pool.append(p)
    for f in familiaridades or []:
        f=dict(f); f["categoria"]=f.get("categoria") or "FAMILIARIDADE"; pool.append(f)
    for r in residuais or []:
        r=dict(r); r["categoria"]="RESIDUAL"; pool.append(r)

    # score
    def score(item):
        conv=(item.get("_convergencia") or {})
        st=conv.get("status")
        base=0.5 if st=="CONVERGENTE" else 0.25 if st=="FRACO" else 0.1
        ativ=item.get("estado_ativacao") or ""
        if ativ=="ATIVA": base+=0.3
        elif ativ=="REATIVAÇÃO_EM_TESTE": base+=0.15
        n=int(item.get("amostra_prospectiva") or item.get("shadow_n") or 0)
        base+=min(0.2, n/100)
        ganho=item.get("efeito_vs_baseline")
        if ganho is not None:
            base+=max(0, min(0.2, float(ganho)*3))
        return base

    pool.sort(key=score, reverse=True)

    # diversidade sem quotas
    selected=[]
    descs=[]
    for it in pool:
        if score(it)<0.25 and it.get("categoria")!="RESIDUAL":
            # residual pode entrar com score um pouco menor se ATIVA
            if it.get("estado_ativacao") not in ("ATIVA","REATIVAÇÃO_EM_TESTE"):
                continue
        desc=(it.get("descricao") or "")[:40]
        if desc in descs:
            continue
        # candidatos internos similares
        selected.append(it)
        descs.append(desc)
        if len(selected)>=max_n:
            break

    return {
        "itens": selected,
        "n": len(selected),
        "composicao": {
            "PADRAO": sum(1 for x in selected if x.get("categoria")=="PADRAO"),
            "FAMILIARIDADE": sum(1 for x in selected if x.get("categoria")=="FAMILIARIDADE"),
            "RESIDUAL": sum(1 for x in selected if x.get("categoria")=="RESIDUAL"),
        },
    }
