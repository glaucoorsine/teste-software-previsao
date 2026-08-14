# -*- coding: utf-8 -*-
"""Controle de 100 séries IID incorporado ao pacote."""
from __future__ import annotations
import random
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from academia_autonoma.ciclo_academia import ciclo
from academia_autonoma.catalogo_persistente import listar


class TestControle100(unittest.TestCase):
    def test_100_series_iid_zero_validacoes(self):
        total_val = 0
        total_prop = 0
        n_series = 100
        for s in range(n_series):
            rng = random.Random(12000 + s)
            hist = [rng.randint(0, 36) for _ in range(45)]
            ds = f"ctrl100_{s}"
            out = ciclo(ds, hist)
            teor = listar(ds)
            total_prop += len(teor)
            vals = [t for t in teor if str(t.get("estado", "")).startswith("validada")]
            total_val += len(vals)
        self.assertEqual(total_val, 0, f"falsas validacoes={total_val} propostas~{total_prop}")
        print(f"CTRL100 series={n_series} propostas~{total_prop} validada={total_val}")


if __name__ == "__main__":
    unittest.main()
