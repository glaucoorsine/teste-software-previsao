# -*- coding: utf-8 -*-
"""Os filtros: neutro é neutro, força é monotônica, valor absurdo não passa."""
from __future__ import annotations

import unittest

import numpy as np

from tests.base import quadro_cena, quadro_ruido
from nucleo import filtros as F


NEUTRO = dict(look="nenhum", intensidade_look=0, embelezamento=0, uniformizar_pele=0,
              brilho=0, contraste=0, saturacao=0, temperatura=0, nitidez=0,
              vinheta=0, espelhar=False)


class TestNeutralidade(unittest.TestCase):
    def test_tudo_em_zero_devolve_o_quadro_intacto(self):
        """A promessa do módulo: em 0, o quadro sai byte a byte igual."""
        q = quadro_ruido()
        np.testing.assert_array_equal(F.aplicar(q, F.Ajustes(**NEUTRO)), q)

    def test_espelhar_e_reversivel(self):
        q = quadro_ruido()
        aj = F.Ajustes(**{**NEUTRO, "espelhar": True})
        np.testing.assert_array_equal(F.aplicar(F.aplicar(q, aj), aj), q)

    def test_intensidade_zero_anula_o_look(self):
        q = quadro_ruido()
        aj = F.Ajustes(**{**NEUTRO, "look": "cinema", "intensidade_look": 0})
        np.testing.assert_array_equal(F.aplicar(q, aj), q)


class TestValidacao(unittest.TestCase):
    def test_valores_fora_da_faixa_sao_presos(self):
        aj = F.Ajustes(embelezamento=500, brilho=-900, nitidez=-3, vinheta=1e9).validar()
        self.assertEqual((aj.embelezamento, aj.brilho, aj.nitidez, aj.vinheta),
                         (100, -100, 0, 100))

    def test_look_desconhecido_vira_natural(self):
        self.assertEqual(F.Ajustes(look="sepia_maluca").validar().look, "natural")

    def test_lixo_nao_derruba(self):
        aj = F.Ajustes(embelezamento="muito", contraste=None).validar()
        self.assertIsInstance(aj.embelezamento, int)
        self.assertIsInstance(aj.contraste, int)

    def test_dicionario_ida_e_volta(self):
        aj = F.Ajustes(look="cinema", embelezamento=42, vinheta=7)
        self.assertEqual(F.Ajustes.de_dicionario(aj.como_dicionario()).como_dicionario(),
                         aj.como_dicionario())

    def test_todos_os_looks_produzem_imagem_valida(self):
        q = quadro_ruido()
        for look in F.LOOKS:
            saida = F.aplicar(q, F.Ajustes(look=look))
            self.assertEqual(saida.shape, q.shape)
            self.assertEqual(saida.dtype, np.uint8)


class TestPele(unittest.TestCase):
    def test_mascara_acha_a_pele_e_ignora_o_resto(self):
        q = quadro_cena()
        m = F.mascara_pele(q)
        alt, larg = q.shape[:2]
        dentro = m[int(alt * 0.4):int(alt * 0.7), int(larg * 0.4):int(larg * 0.6)].mean()
        fora = m[:int(alt * 0.15), :int(larg * 0.15)].mean()
        self.assertGreater(dentro, 0.7)
        self.assertLess(fora, 0.2)

    def test_mascara_fica_entre_zero_e_um(self):
        m = F.mascara_pele(quadro_ruido())
        self.assertGreaterEqual(float(m.min()), 0.0)
        self.assertLessEqual(float(m.max()), 1.0)

    def test_embelezar_alisa_mais_conforme_a_forca(self):
        """Mais força tem que alisar mais — medido pela variação local na pele."""
        q = quadro_cena()
        ruido = np.random.RandomState(11).normal(0, 9, q.shape)
        q = np.clip(q.astype(np.float32) + ruido, 0, 255).astype(np.uint8)
        alt, larg = q.shape[:2]
        recorte = (slice(int(alt * 0.4), int(alt * 0.7)), slice(int(larg * 0.4), int(larg * 0.6)))

        def aspereza(forca):
            saida = F.embelezar(q, forca)
            g = saida[recorte].mean(axis=2)
            return float(np.abs(np.diff(g, axis=1)).mean())

        self.assertGreater(aspereza(0), aspereza(50))
        self.assertGreater(aspereza(50), aspereza(100))

    def test_embelezar_em_zero_nao_mexe(self):
        q = quadro_cena()
        np.testing.assert_allclose(F.embelezar(q, 0), q.astype(np.float32) / 255.0, atol=1e-6)
        # sem nada a fazer, nem os coeficientes são calculados
        self.assertIsNone(F.coeficientes_embelezamento(q, 0, 0))


class TestCorEDesempenho(unittest.TestCase):
    def test_brilho_clareia_e_escurece(self):
        q = np.full((20, 20, 3), 128, np.uint8)
        claro = F.aplicar(q, F.Ajustes(**{**NEUTRO, "brilho": 60}))
        escuro = F.aplicar(q, F.Ajustes(**{**NEUTRO, "brilho": -60}))
        self.assertGreater(claro.mean(), q.mean() + 10)
        self.assertLess(escuro.mean(), q.mean() - 10)

    def test_saturacao_minima_deixa_cinza(self):
        q = quadro_ruido()
        cinza = F.aplicar(q, F.Ajustes(**{**NEUTRO, "saturacao": -100}))
        canais = cinza.astype(np.int16)
        self.assertLessEqual(int(np.abs(canais[..., 0] - canais[..., 2]).max()), 2)

    def test_temperatura_quente_puxa_o_vermelho(self):
        q = np.full((20, 20, 3), 128, np.uint8)
        quente = F.aplicar(q, F.Ajustes(**{**NEUTRO, "temperatura": 80}))
        self.assertGreater(quente[..., 2].mean(), quente[..., 0].mean())

    def test_vinheta_escurece_o_canto_e_nao_o_centro(self):
        q = np.full((60, 60, 3), 200, np.uint8)
        saida = F.aplicar(q, F.Ajustes(**{**NEUTRO, "vinheta": 90}))
        self.assertLess(saida[0, 0].mean(), saida[30, 30].mean() - 20)

    def test_tabela_de_cor_fica_em_cache(self):
        aj = F.Ajustes(look="cinema", brilho=11)
        self.assertIs(F.compilar(aj), F.compilar(F.Ajustes(look="cinema", brilho=11)))

    def test_mapa_de_vinheta_fica_em_cache(self):
        self.assertIs(F.mapa_vinheta(40, 50, 30), F.mapa_vinheta(40, 50, 30))


if __name__ == "__main__":
    unittest.main()
