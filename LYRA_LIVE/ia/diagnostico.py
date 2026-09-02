# -*- coding: utf-8 -*-
"""
As regras: o que os números da live querem dizer.

ESTE MÓDULO É A PARTE QUE NÃO ERRA
----------------------------------
Aqui não há modelo de linguagem nenhum. São comparações contra limites, sobre
as métricas medidas em `nucleo/metricas.py`. Cada achado nasce de um número
específico e diz qual foi.

A DIVISÃO DE TRABALHO COM O QWEN
--------------------------------
Um modelo de linguagem é ótimo para explicar e péssimo para medir: dado um
punhado de números, ele produz uma narrativa convincente — inclusive quando os
números não dizem nada. Se a IA fosse quem decide se a live está bem, ela
inventaria problema em live saudável e tranquilizaria numa que está caindo.

Então a ordem é fixa e não se inverte:

    métricas -> ESTAS REGRAS -> achados -> Qwen escreve por cima

O Qwen recebe os achados prontos. Ele não vê métrica solta, não inventa número
e não decide gravidade. Se ele não estiver instalado, os achados aparecem no
painel do mesmo jeito, com o texto que está escrito aqui — a supervisão
continua funcionando inteira sem modelo nenhum.

OS LIMITES
----------
Cada limite tem motivo declarado no código da regra. Um limite sem motivo é
um número mágico, e número mágico é onde o diagnóstico começa a mentir.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List

GRAVIDADES = ("ok", "atencao", "grave")
_PESO = {"ok": 0, "atencao": 1, "grave": 2}


@dataclass
class Achado:
    codigo: str
    gravidade: str          # ok | atencao | grave
    titulo: str
    detalhe: str            # o número que gerou o achado
    acao: str               # o que fazer a respeito

    def como_dicionario(self) -> Dict:
        return asdict(self)


def _n(valor, padrao: float = 0.0) -> float:
    try:
        if valor is None:
            return padrao
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def diagnosticar(estado: Dict) -> List[Achado]:
    """Lê um instantâneo da live e devolve o que está errado, do pior ao melhor."""
    achados: List[Achado] = []
    if not estado or not estado.get("rodando"):
        return achados

    alvo = max(1.0, _n(estado.get("fps_alvo"), 30))
    fps_cap = _n(estado.get("fps_captura"))
    ms = _n(estado.get("ms_processamento"))
    pico = _n(estado.get("ms_processamento_pico"))
    orcamento = _n(estado.get("orcamento_ms"), 33.3)
    enc = dict(estado.get("encoder") or {})
    segundos = _n(estado.get("segundos_no_ar"))

    # --- câmera ------------------------------------------------------------
    # Dois segundos de tolerância: abrir webcam demora, e acusar "câmera parada"
    # no primeiro instante da live seria alarme falso garantido.
    if fps_cap <= 0.1 and segundos > 2.0:
        achados.append(Achado(
            "camera_parada", "grave", "A câmera parou de entregar imagem",
            f"{fps_cap:.1f} quadros por segundo capturados nos últimos segundos.",
            "Verifique o cabo USB da Lyra, ou se outro programa (Meet, Zoom, OBS) "
            "tomou a câmera. Só um programa por vez consegue abrir a mesma webcam."))
    elif fps_cap < alvo * 0.8 and segundos > 3.0:
        achados.append(Achado(
            "fps_baixo", "atencao", "A câmera entrega menos quadros que o pedido",
            f"{fps_cap:.1f} fps capturados contra {alvo:.0f} fps configurados.",
            "Em ambiente escuro a câmera aumenta o tempo de exposição e cai de "
            "cadência sozinha — acenda uma luz. Se não for isso, tente uma "
            "resolução menor ou outra porta USB (de preferência USB 3.0)."))

    reconexoes = _n(estado.get("reconexoes"))
    if reconexoes > 0:
        achados.append(Achado(
            "camera_reconectou",
            "grave" if reconexoes >= 3 else "atencao",
            "A câmera caiu e precisou ser reaberta",
            f"{int(reconexoes)} reconexão(ões) desde o início da live.",
            "Cabo ou porta com mau contato costuma ser a causa. Numa Lyra por "
            "Wi-Fi, é sinal do enlace oscilando — aproxime do roteador."))

    # --- processamento -----------------------------------------------------
    # O orçamento por quadro é 1000/fps. Passar dele significa que o filtro
    # sozinho já não cabe na cadência, e a partir daí a fila só descarta.
    if ms > orcamento:
        achados.append(Achado(
            "filtro_pesado", "grave", "Os filtros não cabem no tempo de um quadro",
            f"{ms:.0f} ms por quadro para um orçamento de {orcamento:.0f} ms.",
            "Reduza o embelezamento e o 'uniformizar pele', ou baixe a resolução "
            "para 720p. Desfoque de fundo com mediapipe também pesa: o modo "
            "'fundo aprendido' custa bem menos."))
    elif pico > orcamento * 1.5 and ms > orcamento * 0.6:
        achados.append(Achado(
            "filtro_irregular", "atencao", "Os filtros travam de vez em quando",
            f"Mediana {ms:.0f} ms, mas os piores 5% levam {pico:.0f} ms "
            f"(orçamento {orcamento:.0f} ms).",
            "Feche programas pesados em segundo plano. Engasgo periódico costuma "
            "ser antivírus varrendo ou navegador com muitas abas."))

    descartes = _n(estado.get("descartes"))
    capturados = _n(estado.get("quadros_capturados"), 1)
    if descartes > 0 and capturados > 0:
        proporcao = descartes / max(1.0, capturados)
        if proporcao > 0.02:      # 2% já é visível como engasgo na imagem
            achados.append(Achado(
                "descarte_de_quadros",
                "grave" if proporcao > 0.10 else "atencao",
                "Quadros estão sendo descartados",
                f"{int(descartes)} de {int(capturados)} quadros ({proporcao * 100:.1f}%).",
                "O computador não está acompanhando. É o mesmo remédio: menos "
                "embelezamento, resolução menor, ou codificação pela placa de vídeo."))

    # --- encoder e rede ----------------------------------------------------
    if "velocidade" in enc:
        vel = _n(enc.get("velocidade"), 1.0)
        # velocidade 1.0x significa codificar um segundo de vídeo por segundo.
        # Abaixo disso a transmissão atrasa mais a cada minuto que passa.
        if vel < 0.95 and segundos > 5.0:
            achados.append(Achado(
                "encoder_atrasado",
                "grave" if vel < 0.85 else "atencao",
                "O codificador não acompanha o tempo real",
                f"Velocidade {vel:.2f}x (precisa ser 1,00x ou mais).",
                "Troque o codificador para a placa de vídeo (NVENC/QuickSync) no "
                "painel, ou baixe a resolução. Em CPU, 1080p exige muito núcleo."))

    if "bitrate_kbps" in enc and segundos > 10.0:
        taxa = _n(enc.get("bitrate_kbps"))
        alvo_taxa = _n(estado.get("video_kbps_alvo"))
        if alvo_taxa > 0 and 0 < taxa < alvo_taxa * 0.6:
            achados.append(Achado(
                "taxa_abaixo", "atencao", "A taxa enviada está bem abaixo da configurada",
                f"{taxa:.0f} kbps enviados contra {alvo_taxa:.0f} kbps configurados.",
                "Normalmente é o upload da internet não dando conta. Faça um teste "
                "de velocidade e configure a taxa em até 70% do upload medido."))

    perdidos = _n(enc.get("quadros_perdidos"))
    if perdidos > 0:
        achados.append(Achado(
            "encoder_perdeu_quadros",
            "grave" if perdidos > 30 else "atencao",
            "O codificador descartou quadros",
            f"{int(perdidos)} quadros perdidos pelo ffmpeg.",
            "Sintoma de CPU no limite ou upload saturado. Reduza a taxa de vídeo."))

    reinicios = _n(estado.get("reinicios_encoder"))
    if reinicios > 0:
        achados.append(Achado(
            "transmissao_reiniciou", "grave", "A transmissão caiu e voltou",
            f"{int(reinicios)} reinício(s) do envio para o YouTube.",
            "A live teve buracos. Se repetir, troque Wi-Fi por cabo de rede — é a "
            "causa mais comum de queda no meio da transmissão."))

    # --- imagem ------------------------------------------------------------
    brilho = estado.get("brilho_medio")
    if brilho is not None and segundos > 5.0:
        b = _n(brilho)
        if b < 0.18:
            achados.append(Achado(
                "imagem_escura", "atencao", "A imagem está escura",
                f"Brilho médio {b * 100:.0f}% do máximo.",
                "Acenda uma luz de frente para você. Compensar no slider de brilho "
                "levanta o ruído junto e a live fica granulada."))
        elif b > 0.85:
            achados.append(Achado(
                "imagem_estourada", "atencao", "A imagem está estourada de claro",
                f"Brilho médio {b * 100:.0f}% do máximo.",
                "Tem luz forte demais ou janela atrás. Baixe o brilho no painel e "
                "evite fonte de luz atrás de você."))

    # --- recorte de fundo --------------------------------------------------
    modo_fundo = str(estado.get("modo_fundo") or "nenhum")
    if modo_fundo != "nenhum":
        seg = str(estado.get("segmentador") or "")
        if seg == "central":
            achados.append(Achado(
                "recorte_aproximado", "atencao", "O recorte de fundo está no modo aproximado",
                "Sem mediapipe instalado e sem fundo memorizado.",
                "Instale o mediapipe (pip install mediapipe) para recorte de pessoa "
                "de verdade, ou use o botão 'Aprender fundo' com a câmera parada."))
        elif seg == "fundo_aprendido" and not estado.get("segmentador_pronto"):
            achados.append(Achado(
                "fundo_nao_aprendido", "atencao", "O fundo ainda não foi memorizado",
                "O modo 'fundo aprendido' está escolhido, mas sem referência.",
                "Saia do quadro e clique em 'Aprender fundo'. Sem isso o desfoque "
                "não tem como saber onde você está."))

    achados.sort(key=lambda a: -_PESO.get(a.gravidade, 0))
    return achados


def saude_geral(achados: List[Achado]) -> str:
    """A pior gravidade entre os achados. Sem achados, a live está bem."""
    pior = "ok"
    for a in achados:
        if _PESO.get(a.gravidade, 0) > _PESO.get(pior, 0):
            pior = a.gravidade
    return pior


def resumo_texto(achados: List[Achado]) -> str:
    """O boletim sem IA nenhuma. É o que aparece quando o Qwen não está lá."""
    if not achados:
        return "Transmissão saudável: nenhum problema detectado nas métricas."
    linhas = []
    for a in achados:
        marca = {"grave": "[GRAVE]", "atencao": "[ATENÇÃO]", "ok": "[ok]"}.get(a.gravidade, "")
        linhas.append(f"{marca} {a.titulo}\n    {a.detalhe}\n    O que fazer: {a.acao}")
    return "\n".join(linhas)
