# -*- coding: utf-8 -*-
"""As contas de imagem batem com a definição delas, com e sem OpenCV."""
from __future__ import annotations

import unittest

import numpy as np

from tests.base import quadro_ruido
from nucleo import imagem as IMG


class TestMediaCaixa(unittest.TestCase):
    def test_bate_com_a_media_ingenua(self):
        """A imagem integral tem que dar o mesmo que somar a janela na mão."""
        r = np.random.RandomState(3)
        a = r.rand(18, 22, 3).astype(np.float32)
        raio = 3
        esperado = np.zeros_like(a)
        for y in range(18):
            for x in range(22):
                ys = np.clip(np.arange(y - raio, y + raio + 1), 0, 17)
                xs = np.clip(np.arange(x - raio, x + raio + 1), 0, 21)
                esperado[y, x] = a[np.ix_(ys, xs)].mean(axis=(0, 1))
        np.testing.assert_allclose(IMG.media_caixa(a, raio), esperado, atol=1e-5)

    def test_preserva_area_constante(self):
        """Borrar algo uniforme não pode mudar o valor — nem na borda."""
        a = np.full((30, 40, 3), 0.42, np.float32)
        np.testing.assert_allclose(IMG.media_caixa(a, 5), a, atol=1e-6)

    def test_raio_zero_nao_mexe(self):
        a = np.random.RandomState(1).rand(10, 12, 3).astype(np.float32)
        np.testing.assert_allclose(IMG.media_caixa(a, 0), a)


class TestRedimensionar(unittest.TestCase):
    def test_bilinear_amostra_no_centro(self):
        """Reduzir e ampliar de volta não pode deslocar a imagem para o canto.

        É o erro de meio pixel que desalinha a máscara de fundo da pessoa.
        """
        a = np.zeros((64, 64), np.float32)
        a[28:36, 28:36] = 1.0
        ida = IMG._bilinear(a, 32, 32)
        volta = IMG._bilinear(ida, 64, 64)
        cy, cx = np.argwhere(volta > 0.4).mean(axis=0)
        self.assertAlmostEqual(cy, 31.5, delta=0.6)
        self.assertAlmostEqual(cx, 31.5, delta=0.6)

    def test_tamanho_pedido_e_respeitado(self):
        a = quadro_ruido()
        self.assertEqual(IMG.redimensionar(a, 77, 33).shape[:2], (33, 77))
        self.assertEqual(IMG.redimensionar_bytes(a, 77, 33).shape[:2], (33, 77))
        self.assertEqual(IMG.redimensionar_bytes(a, 77, 33).dtype, np.uint8)

    def test_enquadrar_preenche_e_cabe(self):
        a = quadro_ruido(60, 200)          # bem panorâmico
        self.assertEqual(IMG.enquadrar(a, 100, 100).shape[:2], (100, 100))
        self.assertEqual(IMG.enquadrar(a, 100, 100, "caber").shape[:2], (100, 100))
        # "caber" deixa barra preta; "preencher" não deixa nenhuma
        self.assertGreater((IMG.enquadrar(a, 100, 100, "caber") == 0).mean(), 0.2)


class TestComposicao(unittest.TestCase):
    def test_mascara_cheia_devolve_a_frente(self):
        f, g = quadro_ruido(semente=1), quadro_ruido(semente=2)
        saida = IMG.compor(f, g, np.ones(f.shape[:2], np.float32))
        self.assertLessEqual(int(np.abs(saida.astype(int) - f).max()), 1)

    def test_mascara_vazia_devolve_o_fundo(self):
        f, g = quadro_ruido(semente=1), quadro_ruido(semente=2)
        saida = IMG.compor(f, g, np.zeros(f.shape[:2], np.float32))
        self.assertLessEqual(int(np.abs(saida.astype(int) - g).max()), 1)

    def test_mascara_menor_e_ampliada(self):
        f, g = quadro_ruido(), quadro_ruido(semente=9)
        saida = IMG.compor(f, g, np.ones((10, 16), np.float32))
        self.assertEqual(saida.shape, f.shape)

    def test_saida_e_sempre_8_bits(self):
        f, g = quadro_ruido(), quadro_ruido(semente=4)
        self.assertEqual(IMG.compor(f, g, np.full(f.shape[:2], 0.5, np.float32)).dtype,
                         np.uint8)


class TestConversao(unittest.TestCase):
    def test_para_bytes_corta_nas_pontas(self):
        a = np.array([[[-0.5, 0.5, 1.5]]], np.float32)
        np.testing.assert_array_equal(IMG.para_bytes(a), np.array([[[0, 128, 255]]], np.uint8))

    def test_ida_e_volta(self):
        a = quadro_ruido()
        np.testing.assert_array_equal(IMG.para_bytes(IMG.para_float(a)), a)


class TestSemOpenCV(unittest.TestCase):
    """O caminho NumPy puro tem que dar o mesmo resultado do caminho OpenCV.

    É o que garante que quem não conseguiu instalar o OpenCV vê a mesma imagem,
    só mais devagar.
    """

    def setUp(self):
        self.cv2_real = IMG.cv2

    def tearDown(self):
        IMG.cv2 = self.cv2_real

    def _comparar(self, funcao, tolerancia=2):
        if self.cv2_real is None:
            self.skipTest("OpenCV não está instalado — só existe um caminho")
        com = funcao()
        IMG.cv2 = None
        sem = funcao()
        com_f = IMG.para_float(com) if com.dtype == np.uint8 else com
        sem_f = IMG.para_float(sem) if sem.dtype == np.uint8 else sem
        self.assertLess(float(np.abs(com_f - sem_f).max()) * 255, tolerancia)

    def test_media_caixa_igual(self):
        a = IMG.para_float(quadro_ruido())
        self._comparar(lambda: IMG.media_caixa(a, 4))

    def test_compor_igual(self):
        f, g = quadro_ruido(semente=1), quadro_ruido(semente=2)
        m = np.random.RandomState(5).rand(*f.shape[:2]).astype(np.float32)
        self._comparar(lambda: IMG.compor(f, g, m))

    def test_para_bytes_igual(self):
        a = (np.random.RandomState(6).rand(40, 50, 3)).astype(np.float32)
        self._comparar(lambda: IMG.para_bytes(a))


if __name__ == "__main__":
    unittest.main()
