# -*- coding: utf-8 -*-
"""O fundo: os três segmentadores, os quatro modos, e nenhum deles derrubando nada."""
from __future__ import annotations

import unittest

import numpy as np

from tests.base import quadro_ruido
from nucleo import fundo as B


class TestEfeito(unittest.TestCase):
    def test_modo_nenhum_devolve_o_quadro_intacto(self):
        q = quadro_ruido()
        motor = B.MotorFundo(B.SegmentadorCentral(), B.EfeitoFundo(modo="nenhum"))
        saida, mascara = motor.aplicar(q)
        np.testing.assert_array_equal(saida, q)
        self.assertIsNone(mascara)

    def test_desfocar_mexe_no_fundo_e_preserva_o_centro(self):
        q = quadro_ruido(120, 200)
        motor = B.MotorFundo(B.SegmentadorCentral(), B.EfeitoFundo(modo="desfocar",
                                                                  intensidade=100))
        saida, mascara = motor.aplicar(q)
        self.assertEqual(saida.shape, q.shape)
        self.assertEqual(saida.dtype, np.uint8)
        self.assertEqual(mascara.shape, q.shape[:2])
        canto = np.abs(saida[:12, :12].astype(int) - q[:12, :12].astype(int)).mean()
        centro = np.abs(saida[54:66, 94:106].astype(int) - q[54:66, 94:106].astype(int)).mean()
        self.assertGreater(canto, centro)

    def test_cor_pinta_o_fundo_da_cor_pedida(self):
        q = quadro_ruido(100, 160)
        motor = B.MotorFundo(B.SegmentadorCentral(),
                             B.EfeitoFundo(modo="cor", cor=(255, 0, 0)))
        saida, _ = motor.aplicar(q)
        canto = saida[:6, :6].reshape(-1, 3).mean(axis=0)
        self.assertGreater(canto[0], 200)      # azul alto (BGR)
        self.assertLess(canto[2], 60)          # vermelho baixo

    def test_imagem_inexistente_nao_derruba_a_live(self):
        q = quadro_ruido()
        motor = B.MotorFundo(B.SegmentadorCentral(),
                             B.EfeitoFundo(modo="imagem", caminho_imagem="/nao/existe.png"))
        saida, mascara = motor.aplicar(q)
        np.testing.assert_array_equal(saida, q)
        self.assertIsNone(mascara)

    def test_validacao_prende_valores(self):
        ef = B.EfeitoFundo(modo="inventado", intensidade=999, recorte_suave=-5,
                           cor=(999, -3, 12)).validar()
        self.assertEqual(ef.modo, "nenhum")
        self.assertEqual(ef.intensidade, 100)
        self.assertEqual(ef.recorte_suave, 0)
        self.assertEqual(ef.cor, (255, 0, 12))


class TestFundoAprendido(unittest.TestCase):
    def test_sem_referencia_a_mascara_e_toda_pessoa(self):
        """Sem fundo memorizado, nada é recortado — melhor que recortar errado."""
        seg = B.SegmentadorFundoAprendido()
        self.assertFalse(seg.pronto())
        self.assertEqual(float(seg.mascara(quadro_ruido()).min()), 1.0)

    def test_cena_igual_ao_fundo_nao_tem_pessoa(self):
        seg = B.SegmentadorFundoAprendido()
        cena = quadro_ruido(120, 200)
        seg.aprender(cena)
        self.assertTrue(seg.pronto())
        self.assertLess(float(seg.mascara(cena).mean()), 0.02)

    def test_objeto_novo_e_encontrado_no_lugar_certo(self):
        seg = B.SegmentadorFundoAprendido()
        cena = quadro_ruido(120, 200)
        seg.aprender(cena)
        com_pessoa = cena.copy()
        com_pessoa[30:90, 60:140] = (20, 220, 20)
        m = seg.mascara(com_pessoa)
        area_real = (60 * 80) / (120 * 200)
        self.assertAlmostEqual(float(m.mean()), area_real, delta=0.05)

    def test_esquecer_volta_ao_estado_inicial(self):
        seg = B.SegmentadorFundoAprendido()
        seg.aprender(quadro_ruido())
        seg.esquecer()
        self.assertFalse(seg.pronto())


class TestSegmentadores(unittest.TestCase):
    def test_central_avisa_que_e_aproximado(self):
        self.assertIn("aproximado", B.SegmentadorCentral().aviso().lower())

    def test_central_da_peso_ao_centro(self):
        m = B.SegmentadorCentral().mascara(quadro_ruido(120, 200))
        alt, larg = m.shape
        self.assertGreater(m[alt // 2, larg // 2], 0.9)
        self.assertLess(m[0, 0], 0.2)

    def test_fabrica_nunca_devolve_nada(self):
        for pedido in ("auto", "mediapipe", "fundo_aprendido", "central", "invento", ""):
            self.assertIsInstance(B.criar_segmentador(pedido), B.Segmentador)

    def test_analise_roda_em_escala_reduzida(self):
        """A máscara sai pequena de propósito: é o que segura o custo em 1080p."""
        m = B.SegmentadorCentral().mascara(quadro_ruido(1080, 1920))
        self.assertLessEqual(m.shape[1], B.LARGURA_ANALISE)


class TestEstabilizador(unittest.TestCase):
    def test_suavizacao_temporal_reduz_o_tremor(self):
        """Máscara que treme faz a borda da pessoa cintilar na live."""
        class Tremida(B.Segmentador):
            def __init__(self):
                self.n = 0

            def mascara(self, quadro):
                self.n += 1
                return np.full((20, 32), 1.0 if self.n % 2 else 0.0, np.float32)

        q = quadro_ruido(80, 128)
        valores = []
        motor = B.MotorFundo(Tremida(), B.EfeitoFundo(modo="desfocar",
                                                      suavizacao_temporal=85))
        for _ in range(8):
            motor.aplicar(q)
            valores.append(float(motor.ultima_mascara.mean()))
        variacao_suave = float(np.abs(np.diff(valores[3:])).mean())

        motor2 = B.MotorFundo(Tremida(), B.EfeitoFundo(modo="desfocar",
                                                       suavizacao_temporal=0))
        valores2 = []
        for _ in range(8):
            motor2.aplicar(q)
            valores2.append(float(motor2.ultima_mascara.mean()))
        variacao_crua = float(np.abs(np.diff(valores2[3:])).mean())
        self.assertLess(variacao_suave, variacao_crua * 0.5)


if __name__ == "__main__":
    unittest.main()
