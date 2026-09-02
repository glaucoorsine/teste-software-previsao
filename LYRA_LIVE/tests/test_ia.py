# -*- coding: utf-8 -*-
"""A IA: as regras que medem, e o Qwen que só redige por cima delas."""
from __future__ import annotations

import unittest

from tests.base import garantir_caminho

garantir_caminho()

from ia.diagnostico import diagnosticar, resumo_texto, saude_geral
from ia.qwen import ClienteQwen, limpar_resposta
from ia.supervisor import Supervisor

SAUDAVEL = dict(
    rodando=True, fps_alvo=30, fps_captura=30.0, fps_saida=30.0, ms_processamento=12.0,
    ms_processamento_pico=18.0, orcamento_ms=33.3, descartes=0, quadros_capturados=900,
    reconexoes=0, reinicios_encoder=0, encoder={"velocidade": 1.0, "bitrate_kbps": 3000},
    video_kbps_alvo=3000, segundos_no_ar=120.0, brilho_medio=0.5, modo_fundo="nenhum",
    segmentador="mediapipe", segmentador_pronto=True, resolucao="1280x720")


def codigos(estado):
    return {a.codigo for a in diagnosticar(estado)}


class TestRegras(unittest.TestCase):
    def test_live_saudavel_nao_gera_achado(self):
        self.assertEqual(diagnosticar(SAUDAVEL), [])
        self.assertEqual(saude_geral([]), "ok")
        self.assertIn("saudável", resumo_texto([]))

    def test_live_parada_nao_e_analisada(self):
        self.assertEqual(diagnosticar({"rodando": False}), [])
        self.assertEqual(diagnosticar({}), [])

    def test_camera_parada_e_grave(self):
        self.assertIn("camera_parada", codigos({**SAUDAVEL, "fps_captura": 0.0}))

    def test_nao_alarma_nos_primeiros_segundos(self):
        """Abrir webcam demora; acusar 'câmera parada' na hora é alarme falso."""
        self.assertEqual(codigos({**SAUDAVEL, "fps_captura": 0.0, "segundos_no_ar": 1.0}),
                         set())

    def test_filtro_acima_do_orcamento(self):
        self.assertIn("filtro_pesado", codigos({**SAUDAVEL, "ms_processamento": 48.0}))

    def test_filtro_irregular_e_diferente_de_filtro_pesado(self):
        irregular = {**SAUDAVEL, "ms_processamento": 22.0, "ms_processamento_pico": 90.0}
        self.assertIn("filtro_irregular", codigos(irregular))
        self.assertNotIn("filtro_pesado", codigos(irregular))

    def test_descarte_pequeno_e_tolerado(self):
        self.assertNotIn("descarte_de_quadros",
                         codigos({**SAUDAVEL, "descartes": 5, "quadros_capturados": 900}))

    def test_descarte_grande_e_apontado(self):
        self.assertIn("descarte_de_quadros",
                      codigos({**SAUDAVEL, "descartes": 200, "quadros_capturados": 900}))

    def test_encoder_lento_e_grave(self):
        self.assertIn("encoder_atrasado",
                      codigos({**SAUDAVEL, "encoder": {"velocidade": 0.7}}))

    def test_taxa_muito_abaixo_da_configurada(self):
        magro = {**SAUDAVEL, "encoder": {"velocidade": 1.0, "bitrate_kbps": 500}}
        self.assertIn("taxa_abaixo", codigos(magro))

    def test_exposicao_nos_dois_extremos(self):
        self.assertIn("imagem_escura", codigos({**SAUDAVEL, "brilho_medio": 0.05}))
        self.assertIn("imagem_estourada", codigos({**SAUDAVEL, "brilho_medio": 0.95}))

    def test_recorte_aproximado_so_avisa_com_o_fundo_ligado(self):
        com = {**SAUDAVEL, "modo_fundo": "desfocar", "segmentador": "central"}
        sem = {**SAUDAVEL, "modo_fundo": "nenhum", "segmentador": "central"}
        self.assertIn("recorte_aproximado", codigos(com))
        self.assertNotIn("recorte_aproximado", codigos(sem))

    def test_achados_vem_do_pior_para_o_melhor(self):
        achados = diagnosticar({**SAUDAVEL, "ms_processamento": 50.0, "brilho_medio": 0.05})
        self.assertEqual(achados[0].gravidade, "grave")
        self.assertEqual(saude_geral(achados), "grave")

    def test_todo_achado_tem_numero_e_acao(self):
        """Achado sem o número que o gerou é palpite com cara de autoridade."""
        for achado in diagnosticar({**SAUDAVEL, "ms_processamento": 50.0,
                                    "reconexoes": 3, "brilho_medio": 0.05}):
            self.assertTrue(achado.detalhe.strip())
            self.assertTrue(achado.acao.strip())
            self.assertIn(achado.gravidade, ("ok", "atencao", "grave"))

    def test_valores_nulos_nao_derrubam(self):
        diagnosticar({**SAUDAVEL, "fps_captura": None, "encoder": None,
                      "brilho_medio": "abc", "ms_processamento": "x"})


class _QwenFalso(ClienteQwen):
    def __init__(self, responde=True):
        super().__init__()
        self.chamadas = 0
        self._responde = responde

    def disponivel(self):
        return True

    def perguntar(self, sistema, usuario, **k):
        self.chamadas += 1
        self.ultima_pergunta = usuario
        return "Baixe o embelezamento para 720p." if self._responde else None


class TestSupervisor(unittest.TestCase):
    def test_nao_chama_o_modelo_com_a_live_saudavel(self):
        q = _QwenFalso()
        Supervisor(lambda: SAUDAVEL, cliente=q).avaliar_agora()
        self.assertEqual(q.chamadas, 0)

    def test_chama_uma_vez_por_conjunto_de_problemas(self):
        """Live de duas horas com o mesmo problema não precisa de 360 parágrafos."""
        q = _QwenFalso()
        ruim = {**SAUDAVEL, "ms_processamento": 50.0}
        sup = Supervisor(lambda: ruim, cliente=q)
        for _ in range(5):
            sup.avaliar_agora()
        self.assertEqual(q.chamadas, 1)

    def test_problema_novo_gera_nova_consulta(self):
        q = _QwenFalso()
        estado = {"atual": {**SAUDAVEL, "ms_processamento": 50.0}}
        sup = Supervisor(lambda: estado["atual"], cliente=q)
        sup.avaliar_agora()
        estado["atual"] = {**estado["atual"], "reconexoes": 3}
        sup.avaliar_agora()
        self.assertEqual(q.chamadas, 2)

    def test_o_modelo_so_recebe_achados_prontos(self):
        """Ele não vê métrica solta: não tem como inventar diagnóstico."""
        q = _QwenFalso()
        Supervisor(lambda: {**SAUDAVEL, "ms_processamento": 50.0},
                   cliente=q).avaliar_agora()
        self.assertIn("Problemas detectados", q.ultima_pergunta)
        self.assertIn("filtros não cabem", q.ultima_pergunta)

    def test_sem_modelo_o_boletim_continua_inteiro(self):
        sup = Supervisor(lambda: {**SAUDAVEL, "ms_processamento": 50.0},
                         cliente=_QwenFalso(responde=False))
        boletim = sup.avaliar_agora()
        self.assertEqual(boletim.saude, "grave")
        self.assertTrue(boletim.texto_regras)
        self.assertEqual(boletim.texto_ia, "")
        self.assertIn("orçamento", sup.texto_para_painel())

    def test_ia_desligada_nunca_consulta(self):
        q = _QwenFalso()
        Supervisor(lambda: {**SAUDAVEL, "ms_processamento": 50.0},
                   cliente=q, usar_ia=False).avaliar_agora()
        self.assertEqual(q.chamadas, 0)

    def test_estado_quebrado_nao_derruba_o_supervisor(self):
        def explode():
            raise RuntimeError("sem pipeline")
        sup = Supervisor(explode, cliente=_QwenFalso())
        with self.assertRaises(RuntimeError):
            sup.avaliar_agora()          # o botão "Analisar agora" quer ver a falha
        self.assertIsNone(sup._tique_seguro())   # o laço de fundo engole e segue

    def test_historico_acumula(self):
        sup = Supervisor(lambda: SAUDAVEL, cliente=_QwenFalso())
        for _ in range(3):
            sup.avaliar_agora()
        self.assertEqual(len(sup.historico()), 3)
        self.assertIsNotNone(sup.ultimo())


class TestLimpezaDeResposta(unittest.TestCase):
    def test_tira_cerca_de_codigo(self):
        self.assertEqual(limpar_resposta("```markdown\nA live está boa.\n```"),
                         "A live está boa.")

    def test_tira_marcacao(self):
        self.assertEqual(limpar_resposta("## Título\ntexto **forte**"),
                         "Título\ntexto forte")

    def test_vazio_vira_none(self):
        self.assertIsNone(limpar_resposta(""))
        self.assertIsNone(limpar_resposta(None))

    def test_corta_resposta_longa_demais(self):
        longo = limpar_resposta("Frase. " + "x" * 2000)
        self.assertLess(len(longo), 760)
        self.assertTrue(longo.endswith("[…]"))


class TestClienteSemServidor(unittest.TestCase):
    def test_sem_ollama_degrada_em_silencio(self):
        c = ClienteQwen("http://127.0.0.1:59999")
        self.assertFalse(c.disponivel())
        self.assertIsNone(c.perguntar("s", "u"))
        self.assertEqual(c.modelos(), [])
        self.assertIn("ollama pull", c.instrucao_de_instalacao())


if __name__ == "__main__":
    unittest.main()
