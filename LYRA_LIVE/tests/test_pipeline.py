# -*- coding: utf-8 -*-
"""A esteira inteira, com a câmera sintética: ritmo, descarte e parada limpa."""
from __future__ import annotations

import threading
import time
import unittest

import numpy as np

from tests.base import garantir_caminho

garantir_caminho()

from nucleo.camera import ConfigCamera
from nucleo.config import Perfil
from nucleo.filtros import Ajustes
from nucleo.fundo import EfeitoFundo
from nucleo.pipeline import Pipeline, _por_ultimo


def perfil_de_teste(**kw) -> Perfil:
    p = Perfil(camera=ConfigCamera(origem="sintetica", largura=320, altura=180, fps=30),
               ajustes=Ajustes(look="natural", embelezamento=20),
               fundo=EfeitoFundo(modo="nenhum"), segmentador="central")
    p.transmitir = False
    p.camera_virtual = False
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class TestFilaQueDescartaOVelho(unittest.TestCase):
    def test_fila_cheia_joga_fora_o_antigo(self):
        """Em live, quadro atrasado não vale nada — o novo é que importa."""
        import queue
        fila = queue.Queue(maxsize=2)
        contagem = {"n": 0}
        for i in range(5):
            _por_ultimo(fila, i, lambda: contagem.__setitem__("n", contagem["n"] + 1))
        restantes = [fila.get_nowait() for _ in range(fila.qsize())]
        self.assertEqual(restantes, [3, 4])       # ficaram os mais novos
        self.assertEqual(contagem["n"], 3)        # e três foram contados como descarte


class TestEsteira(unittest.TestCase):
    def setUp(self):
        self.esteira = None

    def tearDown(self):
        if self.esteira is not None:
            self.esteira.parar()

    def test_roda_no_ritmo_pedido_sem_descartar(self):
        """Sem o relógio da captura, a fonte sintética correria a 100 fps."""
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(3.0)
        e = self.esteira.estado()
        self.assertAlmostEqual(e["fps_captura"], 30, delta=4)
        self.assertAlmostEqual(e["fps_saida"], 30, delta=4)
        self.assertLess(e["descartes"], max(3, e["quadros_capturados"] * 0.05))

    def test_a_previa_e_o_quadro_que_vai_ao_ar(self):
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(0.6)
        previa = self.esteira.preview()
        self.assertIsNotNone(previa)
        self.assertEqual(previa.shape, (180, 320, 3))
        self.assertEqual(previa.dtype, np.uint8)

    def test_ajuste_entra_com_a_live_no_ar(self):
        """Slider que exige reiniciar a transmissão é slider que ninguém usa."""
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(0.5)
        antes = self.esteira.preview().copy()
        self.esteira.definir_ajustes(Ajustes(look="pb", saturacao=-100, embelezamento=0))
        time.sleep(0.6)
        depois = self.esteira.preview()
        # em preto e branco os canais se encontram; antes, não
        dif_depois = float(np.abs(depois[..., 0].astype(int) - depois[..., 2]).mean())
        dif_antes = float(np.abs(antes[..., 0].astype(int) - antes[..., 2]).mean())
        self.assertLess(dif_depois, dif_antes)

    def test_troca_de_fundo_com_a_live_no_ar(self):
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(0.4)
        self.esteira.definir_fundo(EfeitoFundo(modo="cor", cor=(255, 0, 0)))
        time.sleep(0.6)
        canto = self.esteira.preview()[:8, :8].reshape(-1, 3).mean(axis=0)
        self.assertGreater(canto[0], 150)

    def test_para_sem_deixar_thread_viva(self):
        antes = threading.active_count()
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(0.5)
        self.assertGreater(threading.active_count(), antes)
        self.esteira.parar()
        self.esteira = None
        time.sleep(0.3)
        self.assertLessEqual(threading.active_count(), antes + 1)

    def test_quadro_que_explode_no_filtro_nao_derruba_a_live(self):
        """Melhor a imagem sem efeito por um instante que a transmissão morta."""
        avisos = []
        self.esteira = Pipeline(perfil_de_teste(), ao_avisar=avisos.append)
        original = self.esteira.motor_fundo.aplicar
        estado = {"quebrar": True}

        def quebrado(quadro):
            if estado["quebrar"]:
                estado["quebrar"] = False
                raise RuntimeError("falha de propósito")
            return original(quadro)

        self.esteira.motor_fundo.aplicar = quebrado
        self.esteira.iniciar()
        time.sleep(1.0)
        self.assertTrue(self.esteira.rodando)
        self.assertGreater(self.esteira.estado()["quadros_enviados"], 5)
        self.assertTrue(any("processar" in a for a in avisos))

    def test_estado_traz_tudo_que_o_painel_e_a_ia_usam(self):
        self.esteira = Pipeline(perfil_de_teste())
        self.esteira.iniciar()
        time.sleep(0.5)
        e = self.esteira.estado()
        for chave in ("rodando", "transmitindo", "camera_virtual", "fps_captura",
                      "fps_saida", "ms_processamento", "ms_processamento_pico",
                      "orcamento_ms", "descartes", "reconexoes", "quadros_capturados",
                      "quadros_enviados", "encoder", "segmentador", "segmentador_pronto",
                      "aviso_segmentador", "modo_fundo", "resolucao", "video_kbps_alvo",
                      "reinicios_encoder", "fps_alvo", "segundos_no_ar"):
            self.assertIn(chave, e, f"o painel precisa de {chave!r}")

    def test_quadro_de_tamanho_diferente_e_reenquadrado(self):
        """A câmera pode ignorar a resolução pedida; o encoder não perdoa isso."""
        p = perfil_de_teste()
        p.camera.largura, p.camera.altura = 256, 144
        self.esteira = Pipeline(p)
        self.esteira.iniciar()
        time.sleep(0.5)
        self.assertEqual(self.esteira.preview().shape, (144, 256, 3))


if __name__ == "__main__":
    unittest.main()
