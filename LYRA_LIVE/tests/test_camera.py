# -*- coding: utf-8 -*-
"""Captura: escolher a origem certa, montar o comando certo, reconectar direito."""
from __future__ import annotations

import time
import unittest

import numpy as np

from tests.base import garantir_caminho

garantir_caminho()

from nucleo import camera as C


class TestOrigem(unittest.TestCase):
    def test_numero_em_texto_vira_indice(self):
        self.assertEqual(C.normalizar_origem("0"), 0)
        self.assertEqual(C.normalizar_origem("2"), 2)
        self.assertEqual(C.normalizar_origem(3), 3)

    def test_url_continua_texto(self):
        self.assertEqual(C.normalizar_origem("rtsp://1.2.3.4/live"), "rtsp://1.2.3.4/live")
        self.assertEqual(C.normalizar_origem("  /caminho/v.mp4  "), "/caminho/v.mp4")

    def test_reconhece_stream(self):
        self.assertTrue(C.e_stream("rtsp://1.2.3.4/live"))
        self.assertTrue(C.e_stream("http://1.2.3.4/video"))
        self.assertFalse(C.e_stream(0))
        self.assertFalse(C.e_stream("/caminho/v.mp4"))


class TestComandoFFmpeg(unittest.TestCase):
    def test_rtsp_usa_tcp(self):
        """UDP perde pacote e vira macrobloco verde gravado para sempre."""
        cmd = C.FonteFFmpeg(C.ConfigCamera(origem="rtsp://1.2.3.4/live")).comando()
        self.assertIn("-rtsp_transport", cmd)
        self.assertEqual(cmd[cmd.index("-rtsp_transport") + 1], "tcp")

    def test_saida_e_sempre_bgr_cru_no_tamanho_pedido(self):
        cmd = C.FonteFFmpeg(C.ConfigCamera(origem=0, largura=800, altura=600)).comando()
        self.assertEqual(cmd[cmd.index("-pix_fmt") + 1], "bgr24")
        self.assertIn("scale=800:600", " ".join(cmd))
        self.assertEqual(cmd[-1], "-")

    def test_windows_usa_nome_e_nao_indice(self):
        """No dshow o índice puro não abre nada — tem que virar video=<nome>."""
        antigo = C.SISTEMA
        try:
            C.SISTEMA = "Windows"
            cmd = C.FonteFFmpeg(C.ConfigCamera(origem="Lyra Camera")).comando()
            self.assertIn("dshow", cmd)
            self.assertIn("video=Lyra Camera", cmd)
        finally:
            C.SISTEMA = antigo


class TestFonteSintetica(unittest.TestCase):
    def test_entrega_quadro_no_formato_combinado(self):
        f = C.FonteSintetica(C.ConfigCamera(largura=320, altura=180))
        f.iniciar()
        q = f.ler()
        self.assertEqual(q.shape, (180, 320, 3))
        self.assertEqual(q.dtype, np.uint8)
        f.parar()
        self.assertIsNone(f.ler())

    def test_a_cena_muda_entre_quadros(self):
        f = C.FonteSintetica(C.ConfigCamera(largura=160, altura=90))
        f.iniciar()
        self.assertFalse(np.array_equal(f.ler(), f.ler()))
        f.parar()


class _Instavel(C.Fonte):
    """Fonte de teste: falha as primeiras leituras, depois volta a funcionar."""

    def __init__(self, falhas=3):
        super().__init__(C.ConfigCamera(largura=32, altura=24))
        self.falhas = falhas
        self.aberturas = 0

    def iniciar(self):
        self.aberturas += 1
        self.aberta = True

    def ler(self):
        if self.falhas > 0:
            self.falhas -= 1
            return None
        return np.zeros((24, 32, 3), np.uint8)

    def parar(self):
        self.aberta = False


class TestReconexao(unittest.TestCase):
    def test_reabre_com_espera_crescente(self):
        """Reabrir em laço apertado só queima CPU e enche o log."""
        f = C.FonteResiliente(_Instavel(falhas=99))
        f.iniciar()
        for _ in range(12):
            f.ler()
        self.assertGreaterEqual(f.reconexoes, 1)
        self.assertLess(f.reconexoes, 12)      # não é uma reconexão por leitura

    def test_volta_a_entregar_quando_a_camera_volta(self):
        interna = _Instavel(falhas=1)
        f = C.FonteResiliente(interna)
        f.iniciar()
        self.assertIsNone(f.ler())             # a falha
        for _ in range(20):
            if f.ler() is not None:
                break
            time.sleep(0.05)
        self.assertIsNotNone(f.ler())

    def test_erro_da_fonte_nao_escapa(self):
        class Explosiva(_Instavel):
            def ler(self):
                raise RuntimeError("cabo arrancado")

        f = C.FonteResiliente(Explosiva())
        f.iniciar()
        self.assertIsNone(f.ler())             # devolve None, não levanta
        self.assertIn("cabo", f.ultimo_erro)


class TestFabrica(unittest.TestCase):
    def test_palavra_sintetica_abre_a_fonte_gerada(self):
        f = C.abrir_fonte(C.ConfigCamera(origem="sintetica"))
        self.assertEqual(f.nome_interno, "sintetica")

    def test_backend_explicito_e_respeitado(self):
        self.assertEqual(C.abrir_fonte(C.ConfigCamera(origem=0, backend="ffmpeg")).nome_interno,
                         "ffmpeg")


if __name__ == "__main__":
    unittest.main()
