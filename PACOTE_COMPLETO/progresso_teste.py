# -*- coding: utf-8 -*-
"""
BARRA DE PROGRESSO DOS TESTES — percentual e tempo restante.

    "quando estiver em testes, me mostre o percentual de evolução e tempo
     restante"

Justo: uma suíte que fica dez minutos calada não dá para distinguir de uma
suíte travada, e a única saída é matar o processo e perder tudo.

A conta do tempo restante é honesta com o que sabe, de dois jeitos:

    sem pesos    usa o tempo médio das etapas já terminadas
    com pesos    o chamador declara o custo típico de cada etapa e a conta vai
                 pelo custo que falta, reajustado pelo ritmo real da máquina

O segundo existe porque o primeiro mente quando as etapas têm tamanhos muito
diferentes — onze testes de segundos e um de meia hora fazem a média anunciar
"falta 4s" com quarenta minutos pela frente.

Enquanto há pouca observação a estimativa aparece com "~" na frente, porque é
isso que ela é — um chute que melhora sozinho a cada etapa.
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
                 saida=None, pesos=None):
        self.total = max(1, int(total))
        self.titulo = titulo
        self.largura = largura
        self.saida = saida or sys.stdout
        self.feito = 0
        self.t0 = time.time()
        self.duracoes = []
        self.ultimo_nome = ""
        # ETAPAS DE TAMANHOS MUITO DIFERENTES.
        #
        # Numa suíte em que onze testes levam segundos e um leva meia hora, a
        # média das etapas terminadas mente feio: depois de onze rápidos ela
        # anuncia "falta 4s" com meia hora pela frente. Quando o chamador sabe
        # o custo aproximado de cada etapa, a conta passa a ser por PESO
        # restante, e a estimativa deixa de ser piada.
        self.pesos = list(pesos) if pesos else None
        if self.pesos and len(self.pesos) != self.total:
            self.pesos = None
        self.peso_total = float(sum(self.pesos)) if self.pesos else 0.0

    # ------------------------------------------------------------ desenho
    def _linha(self, nome: str = "") -> str:
        frac = self.feito / self.total
        cheio = int(frac * self.largura)
        barra = "█" * cheio + "·" * (self.largura - cheio)
        gasto = time.time() - self.t0
        if self.pesos:
            falto = sum(self.pesos[self.feito:])
            gasto_peso = self.peso_total - falto
            if self.duracoes and gasto_peso > 0:
                # reajusta a previsão pelo ritmo real desta máquina
                ritmo = gasto / gasto_peso
                restante = falto * ritmo
                certeza = "" if self.feito >= 3 else "~"
            else:
                restante = falto
                certeza = "~"
            falta = f"falta {certeza}{_mmss(restante)}"
        elif self.duracoes:
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
        if self.pesos:
            falto = sum(self.pesos[self.feito:])
            gasto_peso = self.peso_total - falto
            if self.duracoes and gasto_peso > 0:
                return falto * ((time.time() - self.t0) / gasto_peso)
            return float(falto)
        if not self.duracoes:
            return None
        media = sum(self.duracoes) / len(self.duracoes)
        return media * (self.total - self.feito)
