# -*- coding: utf-8 -*-
"""Esqueleto, tipografia e utilitários do relatório."""
from __future__ import annotations
import json, base64
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from base import FIGURAS, RESULTADOS, RAIZ

def carregar_tudo():
    d = {}
    for n in ("protocolo", "persistencia", "assertividade", "inovacoes",
              "fechamento", "premios", "outras_loterias",
              "catalogo_controle"):
        p = RESULTADOS / f"{n}.json"
        d[n] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return d

def fig(nome: str) -> str:
    p = FIGURAS / nome
    b = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/png;base64,{b}"

def num(x, casas=2, sinal=False):
    if x is None: return "—"
    s = f"{x:+.{casas}f}" if sinal else f"{x:.{casas}f}"
    return s.replace(".", ",")

def milhar(n):
    return f"{int(n):,}".replace(",", ".")

def pct(x, casas=2):
    return num(x * 100, casas) + "%"

CSS = """
@page { size: A4; margin: 20mm 17mm 18mm 17mm;
  @bottom-center { content: counter(page); font-size: 8pt; color: #8a949c; } }
* { box-sizing: border-box; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 9.6pt; line-height: 1.52;
  color: #1c2833; margin: 0; hyphens: auto; text-align: justify; }
h1,h2,h3,h4 { font-family: "DejaVu Sans", Helvetica, sans-serif; color:#101820;
  line-height:1.22; text-align:left; }
h1 { font-size: 19pt; margin: 0 0 4mm 0; letter-spacing:-0.3px; }
h2 { font-size: 13.4pt; margin: 9mm 0 3mm 0; padding-bottom: 1.6mm;
  border-bottom: 1.6px solid #1c2833; page-break-after: avoid; }
h3 { font-size: 10.8pt; margin: 6mm 0 2mm 0; page-break-after: avoid; color:#233b4d; }
h4 { font-size: 9.6pt; margin: 4.5mm 0 1.5mm 0; page-break-after: avoid; color:#3d4f5c;
  text-transform: uppercase; letter-spacing: 0.6px; font-size:8.4pt; }
p { margin: 0 0 2.4mm 0; }
.quebra { page-break-before: always; }
.evitar { page-break-inside: avoid; }
code, .mono { font-family: "DejaVu Sans Mono", monospace; font-size: 8.4pt; }

.capa { height: 247mm; display: flex; flex-direction: column; justify-content: space-between;
  page-break-after: always; }
.capa .topo { border-top: 3.5px solid #1c2833; padding-top: 6mm; }
.capa .selo { font-family:"DejaVu Sans",sans-serif; font-size:8pt; letter-spacing:2.4px;
  text-transform:uppercase; color:#7a858d; }
.capa h1 { font-size: 30pt; line-height:1.08; margin: 8mm 0 5mm 0; letter-spacing:-1px; }
.capa .sub { font-size: 12.4pt; color:#3d4f5c; font-family:"DejaVu Sans",sans-serif;
  line-height:1.42; max-width: 132mm; }
.capa .rodape { font-size: 8.6pt; color:#5a6b78; border-top:1px solid #cfd6db; padding-top:4mm; }
.capa .rodape b { color:#1c2833; }

.aviso { border:1.4px solid #b3402f; padding: 4mm 5mm; margin: 5mm 0; background:#fdf6f4;
  font-size: 9pt; }
.aviso b { color:#b3402f; }
.destaque { border-left: 3.5px solid #1c2833; padding: 2.5mm 0 2.5mm 5mm; margin: 4mm 0;
  background:#f6f8f9; }
.achado { border:1.4px solid #3d7a52; background:#f4f9f5; padding:4mm 5mm; margin:5mm 0; }
.achado .rot { font-family:"DejaVu Sans",sans-serif; font-size:7.6pt; letter-spacing:1.6px;
  text-transform:uppercase; color:#3d7a52; font-weight:bold; display:block; margin-bottom:1.6mm; }
.morto { border:1.4px solid #b3402f; background:#fdf6f4; padding:4mm 5mm; margin:5mm 0; }
.morto .rot { font-family:"DejaVu Sans",sans-serif; font-size:7.6pt; letter-spacing:1.6px;
  text-transform:uppercase; color:#b3402f; font-weight:bold; display:block; margin-bottom:1.6mm; }

table { width:100%; border-collapse: collapse; margin: 3.5mm 0; font-size: 8.2pt;
  font-family:"DejaVu Sans",sans-serif; }
th { background:#1c2833; color:#fff; padding: 1.5mm 2mm; text-align:left; font-weight:600;
  font-size: 7.6pt; letter-spacing:0.2px; }
td { padding: 1.1mm 2mm; border-bottom: 0.5px solid #dfe4e8; }
tr:nth-child(even) td { background:#f7f9fa; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; }
td.c, th.c { text-align: center; }
table.compacta { font-size: 7.2pt; table-layout: fixed; }
table.compacta td { padding: 0.7mm 1.2mm; overflow: hidden; }
table.compacta td.mono { white-space: normal; word-break: break-all; font-size: 6.6pt; line-height:1.25; }
table.compacta th { padding: 1.2mm 1.2mm; }
.pos { color:#3d7a52; font-weight:bold; } .neg { color:#b3402f; font-weight:bold; }
.viva { color:#3d7a52; font-weight:bold; } .morta { color:#96a0a8; }

figure { margin: 5mm 0; page-break-inside: avoid; }
figure img { width:100%; display:block; }
figcaption { font-family:"DejaVu Sans",sans-serif; font-size:7.8pt; color:#5a6b78;
  margin-top:1.8mm; line-height:1.4; text-align:left; }

.sumario { font-family:"DejaVu Sans",sans-serif; font-size:9pt; }
.sumario .lin { display:flex; justify-content:space-between; padding: 1.1mm 0;
  border-bottom:0.5px dotted #cfd6db; }
.sumario .lin b { font-weight:600; }
.sumario .p2 { padding-left: 6mm; color:#4a5a66; font-size:8.4pt; }
.ficha { font-family:"DejaVu Sans",sans-serif; font-size:8.4pt; margin:3mm 0;
  border:1px solid #cfd6db; }
.ficha div { display:flex; border-bottom:1px solid #e5eaed; }
.ficha div:last-child { border-bottom:none; }
.ficha .k { width:26mm; flex:none; background:#eef2f4; padding:1.6mm 2.4mm; font-weight:600;
  font-size:7.6pt; text-transform:uppercase; letter-spacing:0.4px; color:#3d4f5c; }
.ficha .v { padding:1.6mm 2.4mm; }
ul, ol { margin: 0 0 2.6mm 0; padding-left: 5.5mm; }
li { margin-bottom: 1.2mm; }
.duas { column-count: 2; column-gap: 7mm; }
"""

def documento(titulo: str, corpo: str) -> str:
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>{titulo}</title><style>{CSS}</style></head><body>{corpo}</body></html>"""
