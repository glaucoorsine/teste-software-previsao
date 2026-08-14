# -*- coding: utf-8 -*-
from .ciclo_academia import ciclo
from .ciclo_residual import ciclo_residual
from .relatorio_academico import gerar as relatorio
from .replay_offline import replay
from .detector_regimes import detectar as detectar_regime

__all__ = ["ciclo", "ciclo_residual", "relatorio", "replay", "detectar_regime"]
