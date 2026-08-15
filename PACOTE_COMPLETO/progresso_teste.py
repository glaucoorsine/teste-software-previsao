# -*- coding: utf-8 -*-
"""
BARRA DE PROGRESSO DOS TESTES — percentual e tempo restante.

    "quando estiver em testes, me mostre o percentual de evolução e tempo
     restante"

Justo: uma suíte que fica dez minutos calada não dá para distinguir de uma
suíte travada, e a única saída é matar o processo e perder tudo.

A conta do tempo restante é honesta com o que sabe: usa o tempo médio das
etapas JÁ terminadas. Enquanto houver poucas, a estimativa aparece como "~"
porque é isso que ela é — um chute que melhora sozinho a cada etapa.
"""
from __future__ import annotations

import sys
import time
from typing import Optional


def _mmss(seg: float) -> str:
    seg = max(0, int(seg))
    if seg < 60:
        return f"{seg}s"
    if seg < 3600:
        return f"{seg // 60}min {seg % 60:02d}s"
    return f"{seg // 3600}h {(seg % 3600) // 60:02d}min"


class Progresso:
    """Acompanha N etapas e desenha uma linha que se atualiza no lugar."""

    def __init__(self, total: int, titulo: str = "testes", largura: int = 26,
                 saida=None):
        self.total = max(1, int(total))
        self.titulo = titulo
        self.largura = largura
        self.saida = saida or sys.stdout
        self.feito = 0
        self.t0 = time.time()
        self.duracoes = []
        self.ultimo_nome = ""

    # ------------------------------------------------------------ desenho
    def _linha(self, nome: str = "") -> str:
        frac = self.feito / self.total
        cheio = int(frac * self.largura)
        barra = "█" * cheio + "·" * (self.largura - cheio)
        gasto = time.time() - self.t0
        if self.duracoes:
            media = sum(self.duracoes) / len(self.duracoes)
            restante = media * (self.total - self.feito)
            certeza = "" if len(self.duracoes) >= 3 else "~"
            falta = f"falta {certeza}{_mmss(restante)}"
        else:
            falta = "falta —"
        return (f"\r  [{barra}] {frac:5.1%}  "
                f"{self.feito}/{self.total}  "
                f"{gasto:.0f}s corridos · {falta}   {nome[:28]:<28}")

    def mostrar(self, nome: str = "") -> None:
        try:
            self.saida.write(self._linha(nome))
            self.saida.flush()
        except Exception:
            pass

    # ------------------------------------------------------------- etapas
    def comecou(self, nome: str) -> None:
        self.ultimo_nome = nome
        self._t_etapa = time.time()
        self.mostrar(f"→ {nome}")

    def terminou(self, nome: str = "", ok: bool = True) -> None:
        agora = time.time()
        self.duracoes.append(agora - getattr(self, "_t_etapa", agora))
        self.feito += 1
        self.mostrar(("ok " if ok else "FALHOU ") + (nome or self.ultimo_nome))

    def fim(self, nota: str = "") -> str:
        gasto = time.time() - self.t0
        try:
            self.saida.write("\r" + " " * 110 + "\r")
            self.saida.flush()
        except Exception:
            pass
        txt = f"  {self.titulo}: {self.feito}/{self.total} em {_mmss(gasto)}"
        if nota:
            txt += f" — {nota}"
        return txt

    # ---------------------------------------------------------- estimativa
    def restante_s(self) -> Optional[float]:
        if not self.duracoes:
            return None
        media = sum(self.duracoes) / len(self.duracoes)
        return media * (self.total - self.feito)
