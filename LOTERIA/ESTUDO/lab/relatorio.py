# -*- coding: utf-8 -*-
"""Monta o relatório em HTML e imprime em PDF pelo Chromium."""
from __future__ import annotations
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from relatorio_base import carregar_tudo, documento
import rel_p1, rel_p2, rel_p3, rel_p4, rel_p5, rel_p6
from base import RAIZ

CHROMIUM = "/opt/pw-browsers/chromium"


def montar() -> str:
    D = carregar_tudo()
    corpo = "".join([
        rel_p1.capa(D),
        rel_p1.aviso(),
        rel_p1.sumario(),
        rel_p1.sumario_executivo(D),
        rel_p2.material(D),
        rel_p2.metodo(D),
        rel_p2.acaso_exato(D),
        rel_p3.assertividade(D),
        rel_p3.teorias_novas(D),
        rel_p4.bateria_cap(D),
        rel_p4.achado(D),
        rel_p6.outras(D),
        rel_p5.erros(D),
        rel_p5.capacidade_real(D),
        rel_p5.reproducao(D),
        rel_p5.apendices(D),
    ])
    return documento("A Lotofácil sob controle negativo", corpo)


def main():
    html = montar()
    ph = RAIZ / "RELATORIO.html"
    ph.write_text(html, encoding="utf-8")
    pp = RAIZ / "RELATORIO_Lotofacil_sob_controle_negativo.pdf"
    cmd = [CHROMIUM, "--headless", "--disable-gpu", "--no-sandbox",
           "--no-pdf-header-footer", "--virtual-time-budget=30000",
           f"--print-to-pdf={pp}", ph.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not pp.exists():
        print("FALHOU:", r.stdout[-2000:], r.stderr[-2000:]); sys.exit(1)
    print(f"HTML: {ph}  ({len(html)/1024:.0f} KB)")
    print(f"PDF : {pp}  ({pp.stat().st_size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
