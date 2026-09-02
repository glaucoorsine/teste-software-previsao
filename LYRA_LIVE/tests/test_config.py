# -*- coding: utf-8 -*-
"""Perfil: sobrevive a ida e volta, a arquivo corrompido, e não vaza a chave."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.base import garantir_caminho

garantir_caminho()

from nucleo import config as C
from nucleo.filtros import Ajustes

CHAVE = "abcd-efgh-ijkl-mnop-qrst"


class TestPerfil(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())

    def test_ida_e_volta_preserva_tudo(self):
        p = C.Perfil()
        p.ajustes.embelezamento = 77
        p.ajustes.look = "cinema"
        p.fundo.modo = "desfocar"
        p.camera.origem = "rtsp://1.2.3.4/live"
        p.camera.largura, p.camera.altura = 1920, 1080
        p.ia_modelo = "qwen3:0.6b"
        self.assertTrue(C.salvar(p, self.pasta))

        lido = C.carregar(self.pasta)
        self.assertEqual(lido.ajustes.embelezamento, 77)
        self.assertEqual(lido.ajustes.look, "cinema")
        self.assertEqual(lido.fundo.modo, "desfocar")
        self.assertEqual(lido.camera.origem, "rtsp://1.2.3.4/live")
        self.assertEqual((lido.camera.largura, lido.camera.altura), (1920, 1080))
        self.assertEqual(lido.ia_modelo, "qwen3:0.6b")

    def test_arquivo_corrompido_vira_padrao_e_nao_excecao(self):
        """Queda de energia no meio da gravação não pode impedir o software de abrir."""
        (self.pasta / C.NOME_PERFIL).write_text("{isto nao e json", encoding="utf-8")
        self.assertEqual(C.carregar(self.pasta).ajustes.embelezamento,
                         Ajustes().embelezamento)

    def test_perfil_ausente_vira_padrao(self):
        self.assertIsInstance(C.carregar(self.pasta), C.Perfil)

    def test_valores_absurdos_no_json_sao_presos(self):
        (self.pasta / C.NOME_PERFIL).write_text(
            json.dumps({"ajustes": {"embelezamento": 5000, "look": "inventado"}}),
            encoding="utf-8")
        lido = C.carregar(self.pasta)
        self.assertEqual(lido.ajustes.embelezamento, 100)
        self.assertEqual(lido.ajustes.look, "natural")


class TestChaveSeparada(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        for v in ("LYRA_CHAVE", "YOUTUBE_STREAM_KEY"):
            os.environ.pop(v, None)

    def tearDown(self):
        for v in ("LYRA_CHAVE", "YOUTUBE_STREAM_KEY"):
            os.environ.pop(v, None)

    def test_a_chave_nao_entra_no_perfil(self):
        """Perfil é o arquivo que se manda para outra pessoa copiar a configuração."""
        p = C.Perfil()
        p.saida.chave = CHAVE
        C.salvar(p, self.pasta)
        bruto = (self.pasta / C.NOME_PERFIL).read_text(encoding="utf-8")
        self.assertNotIn(CHAVE, bruto)
        self.assertNotIn("chave", json.loads(bruto)["saida"])

    def test_grava_e_le_a_chave(self):
        self.assertTrue(C.salvar_chave(CHAVE, self.pasta))
        self.assertEqual(C.carregar_chave(self.pasta), CHAVE)

    def test_ambiente_tem_prioridade_sobre_o_arquivo(self):
        C.salvar_chave(CHAVE, self.pasta)
        os.environ["LYRA_CHAVE"] = "zzzz-yyyy-xxxx-wwww-vvvv"
        self.assertEqual(C.carregar_chave(self.pasta), "zzzz-yyyy-xxxx-wwww-vvvv")

    def test_chave_vazia_apaga_o_arquivo(self):
        C.salvar_chave(CHAVE, self.pasta)
        C.salvar_chave("", self.pasta)
        self.assertFalse((self.pasta / C.NOME_CHAVE).exists())
        self.assertEqual(C.carregar_chave(self.pasta), "")

    @unittest.skipIf(os.name == "nt", "permissão de arquivo não se aplica no Windows")
    def test_arquivo_da_chave_e_so_do_dono(self):
        C.salvar_chave(CHAVE, self.pasta)
        modo = oct((self.pasta / C.NOME_CHAVE).stat().st_mode)[-3:]
        self.assertEqual(modo, "600")


if __name__ == "__main__":
    unittest.main()
