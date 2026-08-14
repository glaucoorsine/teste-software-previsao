# -*- coding: utf-8 -*-
"""ADAPTADOR — descoberta legada desativada; API mínima para imports."""
from academia_autonoma.agentes_descoberta import AGENTES, JANELAS

def listar_agentes():
    return [{"id": a.id, "nome": getattr(a, "nome", a.id)} for a in AGENTES]

def ciclo_descoberta(*a, **k):
    """Legado desativado. Retorna vazio — a autoridade é academia_autonoma.ciclo."""
    return {"candidatos": [], "msgs": ["[Descoberta legada] desativada — use academia_autonoma"], "n_propostas": 0}

def candidatos_da_biblioteca(*a, **k):
    return []
