# -*- coding: utf-8 -*-
"""YouTube, métricas e encoder — inclusive a chave nunca aparecendo em log."""
from __future__ import annotations

import time
import unittest

from tests.base import garantir_caminho

garantir_caminho()

from nucleo import metricas as M
from nucleo import saida_rtmp as S
from nucleo import youtube as YT

CHAVE = "abcd-efgh-ijkl-mnop-qrst"


class TestChave(unittest.TestCase):
    def test_chave_boa_passa(self):
        self.assertTrue(YT.validar_chave(CHAVE)[0])

    def test_url_colada_no_lugar_da_chave_e_explicada(self):
        vale, motivo = YT.validar_chave("rtmp://a.rtmp.youtube.com/live2")
        self.assertFalse(vale)
        self.assertIn("URL de ingestão", motivo)

    def test_vazia_e_com_espaco_sao_recusadas(self):
        self.assertFalse(YT.validar_chave("")[0])
        self.assertFalse(YT.validar_chave("abcd efgh")[0])
        self.assertFalse(YT.validar_chave("xxxx")[0])

    def test_mascara_esconde_a_chave(self):
        linha = f"ffmpeg -f flv rtmp://a.rtmp.youtube.com/live2/{CHAVE}"
        self.assertNotIn(CHAVE, YT.mascarar_chave(linha))
        self.assertIn("****", YT.mascarar_chave(linha))

    def test_comando_de_log_nunca_traz_a_chave(self):
        """A linha de comando é o que se cola num print pedindo ajuda."""
        cfg = S.ConfigSaida(chave=CHAVE)
        self.assertIn(CHAVE, " ".join(S.montar_comando(cfg)))
        self.assertNotIn(CHAVE, S.comando_para_log(cfg))

    def test_perfil_nao_guarda_a_chave(self):
        self.assertNotIn("chave", S.ConfigSaida(chave=CHAVE).como_dicionario())


class TestIngestao(unittest.TestCase):
    def test_url_primaria(self):
        self.assertEqual(YT.montar_url(CHAVE), f"{YT.INGESTAO_PRIMARIA}/{CHAVE}")

    def test_backup_poe_a_chave_antes_da_interrogacao(self):
        url = YT.montar_url(CHAVE, backup=True)
        self.assertTrue(url.endswith("?backup=1"))
        self.assertIn(f"/{CHAVE}?", url)


class TestTaxas(unittest.TestCase):
    def test_taxa_cresce_com_a_resolucao(self):
        self.assertLess(YT.preset(720, 30)["video_kbps"], YT.preset(1080, 30)["video_kbps"])
        self.assertLess(YT.preset(1080, 30)["video_kbps"], YT.preset(2160, 30)["video_kbps"])

    def test_60fps_pede_mais_que_30fps(self):
        self.assertGreater(YT.preset(1080, 60)["video_kbps"], YT.preset(1080, 30)["video_kbps"])

    def test_altura_fora_da_tabela_usa_a_linha_de_baixo(self):
        self.assertEqual(YT.preset(900, 30)["video_kbps"], YT.preset(720, 30)["video_kbps"])

    def test_quadro_chave_dentro_do_limite_do_youtube(self):
        self.assertLessEqual(YT.preset(1080, 30)["intervalo_quadro_chave"], 4)


class TestComandoEncoder(unittest.TestCase):
    def test_quadro_chave_a_cada_dois_segundos(self):
        cmd = S.montar_comando(S.ConfigSaida(chave=CHAVE, fps=60))
        self.assertEqual(cmd[cmd.index("-g") + 1], "120")
        self.assertEqual(cmd[cmd.index("-keyint_min") + 1], "120")

    def test_formato_de_cor_universal(self):
        cmd = S.montar_comando(S.ConfigSaida(chave=CHAVE))
        self.assertEqual(cmd[cmd.index("-pix_fmt", cmd.index("-c:v")) + 1], "yuv420p")
        self.assertEqual(cmd[cmd.index("-f", cmd.index("-c:a")) + 1], "flv")

    def test_sem_microfone_gera_silencio(self):
        """O YouTube recusa transmissão sem faixa de áudio."""
        cmd = S.montar_comando(S.ConfigSaida(chave=CHAVE))
        self.assertIn("anullsrc", " ".join(cmd))
        self.assertIn("-c:a", cmd)

    def test_microfone_escolhido_entra_como_dshow(self):
        cmd = S.entrada_de_audio(S.ConfigSaida(audio_dispositivo="Mic", audio_backend="dshow"))
        self.assertIn("audio=Mic", cmd)
        self.assertIn("-thread_queue_size", cmd)

    def test_buffer_e_o_dobro_da_taxa(self):
        cmd = S.montar_comando(S.ConfigSaida(chave=CHAVE, video_kbps=3000))
        self.assertEqual(cmd[cmd.index("-b:v") + 1], "3000k")
        self.assertEqual(cmd[cmd.index("-bufsize") + 1], "6000k")

    def test_progresso_estruturado_esta_ligado(self):
        """Sem isto não há métrica real de velocidade e taxa."""
        self.assertIn("-progress", S.montar_comando(S.ConfigSaida(chave=CHAVE)))


class TestDiagnosticoDeRede(unittest.TestCase):
    def test_traduz_chave_recusada(self):
        self.assertIn("chave", YT.diagnostico_conexao("Operation not permitted").lower())

    def test_traduz_queda(self):
        self.assertIn("caiu", YT.diagnostico_conexao("Broken pipe").lower())

    def test_texto_desconhecido_nao_inventa(self):
        self.assertIsNone(YT.diagnostico_conexao("algo totalmente diferente"))
        self.assertIsNone(YT.diagnostico_conexao(""))


class TestMetricas(unittest.TestCase):
    def test_taxa_precisa_de_duas_marcas(self):
        m = M.Metricas(30)
        self.assertEqual(m.instantaneo()["fps_captura"], 0.0)
        m.marcar_captura()
        self.assertEqual(m.instantaneo()["fps_captura"], 0.0)

    def test_taxa_medida_bate_com_o_ritmo_real(self):
        m = M.Metricas(30)
        for _ in range(6):
            m.marcar_captura()
            time.sleep(0.02)                    # ~50 por segundo
        self.assertGreater(m.instantaneo()["fps_captura"], 25)

    def test_mediana_e_pico_do_processamento(self):
        # 90 quadros rápidos e 10 travados: a mediana ignora os picos, o p95 não.
        # É essa diferença que separa "dá para manter a cadência" de "trava às vezes".
        m = M.Metricas(30)
        for v in [10] * 90 + [200] * 10:
            m.marcar_processamento(v)
        i = m.instantaneo()
        self.assertEqual(i["ms_processamento"], 10.0)
        self.assertEqual(i["ms_processamento_pico"], 200.0)

    def test_orcamento_vem_do_fps_alvo(self):
        self.assertAlmostEqual(M.Metricas(30).instantaneo()["orcamento_ms"], 33.3, places=1)
        self.assertAlmostEqual(M.Metricas(60).instantaneo()["orcamento_ms"], 16.7, places=1)

    def test_contadores_somam(self):
        m = M.Metricas(30)
        m.marcar_descarte(3)
        m.marcar_descarte()
        m.marcar_reconexao()
        i = m.instantaneo()
        self.assertEqual(i["descartes"], 4)
        self.assertEqual(i["reconexoes"], 1)


class TestProgressoFFmpeg(unittest.TestCase):
    def test_le_velocidade_taxa_e_perdas(self):
        self.assertEqual(M.analisar_progresso("speed=0.92x"), {"velocidade": 0.92})
        self.assertEqual(M.analisar_progresso("bitrate=2045.3kbits/s"),
                         {"bitrate_kbps": 2045.3})
        self.assertEqual(M.analisar_progresso("drop_frames=7"), {"quadros_perdidos": 7.0})

    def test_linha_estranha_nao_derruba(self):
        for lixo in ("", "sem igual", "speed=N/Ax", "bitrate=N/A", "fps=abc"):
            self.assertEqual(M.analisar_progresso(lixo), {})


if __name__ == "__main__":
    unittest.main()
