# -*- coding: utf-8 -*-
"""
LYRA LIVE — linha de comando.

    python lyra.py --diagnostico              o que está instalado e o que falta
    python lyra.py --listar-cameras           quais câmeras o sistema enxerga
    python lyra.py --teste                    prova a esteira inteira sem câmera
    python lyra.py --camera 0 --transmitir    transmite para o YouTube
    python lyra.py --camera 0 --camera-virtual   publica como webcam do sistema

A chave de transmissão vem de `--chave`, da variável de ambiente `LYRA_CHAVE`
ou do arquivo salvo pelo painel — nessa ordem. Ela nunca é impressa na tela.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from ia.diagnostico import resumo_texto, saude_geral, diagnosticar   # noqa: E402
from ia.qwen import ClienteQwen                                       # noqa: E402
from ia.supervisor import Supervisor                                  # noqa: E402
from nucleo import config as CFG                                      # noqa: E402
from nucleo import youtube as YT                                      # noqa: E402
from nucleo.camera import listar_cameras                              # noqa: E402
from nucleo.filtros import LOOKS                                      # noqa: E402
from nucleo.fundo import MODOS as MODOS_FUNDO                         # noqa: E402
from nucleo.pipeline import Pipeline                                  # noqa: E402


def _cabecalho(titulo: str) -> None:
    print("\n" + "=" * 62)
    print(f"  {titulo}")
    print("=" * 62)


def comando_diagnostico() -> int:
    """O que esta máquina tem, o que falta, e o que cada falta custa.

    Escrito para ser o primeiro comando que alguém roda. Cada linha diz se o
    item é obrigatório ou opcional e o que se perde sem ele — em vez de uma
    lista de "não encontrado" que não ajuda ninguém a decidir o que instalar.
    """
    _cabecalho("LYRA LIVE — diagnóstico da máquina")
    print(f"  Python {sys.version.split()[0]}  ({sys.executable})")
    print(f"  Pasta de dados: {CFG.pasta_dados()}")

    obrigatorios = [
        ("numpy", "numpy", "os filtros não funcionam sem ele"),
        ("ffmpeg", None, "sem ele não há transmissão para o YouTube"),
    ]
    opcionais = [
        ("opencv-python", "cv2", "acelera tudo e abre a câmera; sem ele sobra o motor ffmpeg"),
        ("mediapipe", "mediapipe", "recorte de pessoa de verdade no desfoque de fundo"),
        ("pyvirtualcam", "pyvirtualcam", "publicar como câmera do sistema"),
        ("customtkinter", "customtkinter", "a janela do painel"),
        ("Pillow", "PIL", "a imagem de prévia dentro do painel"),
        ("requests", "requests", "falar com o Qwen local"),
    ]

    print("\n  OBRIGATÓRIOS")
    faltando_obrigatorio = False
    for nome, modulo, porque in obrigatorios:
        if modulo is None:
            existe = shutil.which(nome) is not None
        else:
            try:
                __import__(modulo)
                existe = True
            except Exception:
                existe = False
        print(f"   {'[ok]  ' if existe else '[FALTA]'} {nome:16s} {'' if existe else '- ' + porque}")
        faltando_obrigatorio = faltando_obrigatorio or not existe

    print("\n  OPCIONAIS")
    for nome, modulo, porque in opcionais:
        try:
            __import__(modulo)
            existe = True
        except Exception:
            existe = False
        print(f"   {'[ok]  ' if existe else '[  -  ]'} {nome:16s} {'' if existe else '- ' + porque}")

    cliente = ClienteQwen()
    print("\n  IA SUPERVISORA")
    if cliente.disponivel():
        modelos = cliente.modelos()
        tem = cliente.modelo in modelos
        print(f"   [ok]   servidor em {cliente.endereco}")
        print(f"   {'[ok]  ' if tem else '[FALTA]'} modelo {cliente.modelo}"
              f"{'' if tem else '  ->  ollama pull ' + cliente.modelo}")
        if modelos:
            print(f"          modelos disponíveis: {', '.join(modelos[:6])}")
    else:
        print(f"   [  -  ] nenhum servidor em {cliente.endereco}")
        print("          A supervisão funciona sem ele, só sem o texto explicativo.")
        print(f"          Para ligar: ollama pull {cliente.modelo}")

    print("\n  CÂMERAS")
    achadas = listar_cameras(4)
    if achadas:
        for c in achadas:
            print(f"   [ok]   índice {c['indice']}: {c['largura']}x{c['altura']}")
    else:
        print("   [  -  ] nenhuma webcam encontrada por índice.")
        print("          Se a Lyra é de rede, use a URL: --camera rtsp://IP:554/live")

    print()
    if faltando_obrigatorio:
        print("  Falta item obrigatório — rode 0_INSTALAR_LYRA.bat.\n")
        return 1
    print("  Pronto para transmitir.\n")
    return 0


def comando_listar_cameras() -> int:
    _cabecalho("Câmeras encontradas")
    achadas = listar_cameras(8)
    if not achadas:
        print("  Nenhuma câmera por índice.")
        print("  Lyra por Wi-Fi? Use a URL dela: --camera rtsp://192.168.0.50:554/live\n")
        return 1
    for c in achadas:
        print(f"  --camera {c['indice']}   {c['largura']}x{c['altura']}")
    print()
    return 0


def montar_perfil(args) -> CFG.Perfil:
    """Junta o perfil salvo com o que veio na linha de comando."""
    perfil = CFG.carregar()
    if args.camera is not None:
        perfil.camera.origem = args.camera
    if args.resolucao:
        try:
            larg, _, alt = str(args.resolucao).lower().partition("x")
            perfil.camera.largura, perfil.camera.altura = int(larg), int(alt)
        except Exception:
            print(f"  Resolução inválida: {args.resolucao!r} (use 1280x720)")
    if args.fps:
        perfil.camera.fps = int(args.fps)
    if args.look:
        perfil.ajustes.look = args.look
    if args.embelezamento is not None:
        perfil.ajustes.embelezamento = int(args.embelezamento)
    if args.fundo:
        perfil.fundo.modo = args.fundo
    if args.segmentador:
        perfil.segmentador = args.segmentador
    perfil.camera_virtual = bool(args.camera_virtual)
    perfil.transmitir = bool(args.transmitir)
    perfil.saida.chave = args.chave or CFG.carregar_chave()
    if args.codificador:
        perfil.saida.codificador = args.codificador
    if args.audio:
        perfil.saida.audio_dispositivo = args.audio
    perfil.ajustes.validar()
    perfil.fundo.validar()
    return perfil


def comando_transmitir(args) -> int:
    perfil = montar_perfil(args)

    if perfil.transmitir:
        vale, motivo = YT.validar_chave(perfil.saida.chave)
        if not vale:
            print(f"\n  Não dá para transmitir: {motivo}\n")
            return 2

    _cabecalho("LYRA LIVE")
    print(f"  Câmera .......... {perfil.camera.origem}")
    print(f"  Resolução ....... {perfil.camera.largura}x{perfil.camera.altura} "
          f"a {perfil.camera.fps} fps")
    print(f"  Look ............ {perfil.ajustes.look} "
          f"(embelezamento {perfil.ajustes.embelezamento})")
    print(f"  Fundo ........... {perfil.fundo.modo}")
    print(f"  YouTube ......... {'SIM' if perfil.transmitir else 'não'}")
    print(f"  Câmera virtual .. {'SIM' if perfil.camera_virtual else 'não'}")
    if perfil.transmitir:
        taxa = YT.preset(perfil.camera.altura, perfil.camera.fps)
        print(f"  Taxa de vídeo ... {taxa['video_kbps']} kbps")
    print("\n  Ctrl+C para encerrar.\n")

    esteira = Pipeline(perfil, ao_avisar=lambda t: print(f"  [aviso] {t}"))
    supervisor = Supervisor(
        esteira.estado,
        cliente=ClienteQwen(perfil.ia_endereco, perfil.ia_modelo),
        intervalo_s=perfil.ia_intervalo_s,
        usar_ia=perfil.ia_ativa)
    try:
        esteira.iniciar()
    except Exception as e:
        print(f"\n  Não consegui iniciar: {e}\n")
        return 3

    supervisor.iniciar()
    ultima_saude = ""
    try:
        while True:
            time.sleep(2.0)
            estado = esteira.estado()
            print(f"\r  {estado['fps_saida']:5.1f} fps  |  "
                  f"filtro {estado['ms_processamento']:5.1f} ms  |  "
                  f"descartes {estado['descartes']:4d}  |  "
                  f"{'no ar' if estado['transmitindo'] else 'local'}   ",
                  end="", flush=True)
            boletim = supervisor.ultimo()
            if boletim is not None and boletim.saude != "ok":
                assinatura = f"{boletim.saude}:{','.join(a.codigo for a in boletim.achados)}"
                if assinatura != ultima_saude:
                    ultima_saude = assinatura
                    print("\n" + supervisor.texto_para_painel() + "\n")
    except KeyboardInterrupt:
        print("\n\n  Encerrando...")
    finally:
        supervisor.parar()
        esteira.parar()
    print("  Transmissão encerrada.\n")
    return 0


def comando_teste(args) -> int:
    """Roda a esteira inteira com a câmera sintética e mede o que ela aguenta."""
    _cabecalho("Teste da esteira (sem câmera, sem YouTube)")
    perfil = montar_perfil(args)
    perfil.camera.origem = "sintetica"
    perfil.transmitir = False
    perfil.camera_virtual = False

    esteira = Pipeline(perfil, ao_avisar=lambda t: print(f"  [aviso] {t}"))
    esteira.iniciar()
    segundos = max(2, int(args.segundos))
    for restante in range(segundos, 0, -1):
        print(f"\r  medindo... {restante:2d}s ", end="", flush=True)
        time.sleep(1.0)
    estado = esteira.estado()
    esteira.parar()

    print("\r" + " " * 30)
    print(f"  Resolução ............. {estado['resolucao']}")
    print(f"  Quadros capturados .... {estado['quadros_capturados']}")
    print(f"  Quadros entregues ..... {estado['quadros_enviados']}")
    print(f"  fps de saída .......... {estado['fps_saida']}")
    print(f"  Filtro por quadro ..... {estado['ms_processamento']} ms "
          f"(pico {estado['ms_processamento_pico']} ms, "
          f"orçamento {estado['orcamento_ms']} ms)")
    print(f"  Descartes ............. {estado['descartes']}")
    print(f"  Recorte de fundo ...... {estado['segmentador']}")

    achados = diagnosticar(estado)
    print(f"\n  Diagnóstico: {saude_geral(achados)}")
    print("  " + resumo_texto(achados).replace("\n", "\n  "))
    print()
    return 0 if saude_geral(achados) != "grave" else 1


def principal(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="lyra", description="LYRA LIVE — transmissão com filtros para o YouTube.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--diagnostico", action="store_true", help="o que está instalado")
    p.add_argument("--listar-cameras", action="store_true", help="câmeras visíveis")
    p.add_argument("--teste", action="store_true", help="prova a esteira sem câmera")
    p.add_argument("--segundos", type=int, default=8, help="duração do --teste")
    p.add_argument("--camera", help="índice (0), URL rtsp://... ou 'sintetica'")
    p.add_argument("--resolucao", help="por exemplo 1280x720")
    p.add_argument("--fps", type=int)
    p.add_argument("--chave", help="chave do YouTube (prefira LYRA_CHAVE no ambiente)")
    p.add_argument("--transmitir", action="store_true", help="enviar para o YouTube")
    p.add_argument("--camera-virtual", action="store_true", help="publicar como webcam")
    p.add_argument("--look", choices=LOOKS)
    p.add_argument("--embelezamento", type=int, help="0 a 100")
    p.add_argument("--fundo", choices=MODOS_FUNDO)
    p.add_argument("--segmentador", choices=("auto", "mediapipe", "fundo_aprendido", "central"))
    p.add_argument("--codificador", choices=("auto", "cpu", "nvidia", "intel", "amd", "apple"))
    p.add_argument("--audio", help="nome do microfone; vazio transmite em silêncio")
    args = p.parse_args(argv)

    if args.diagnostico:
        return comando_diagnostico()
    if args.listar_cameras:
        return comando_listar_cameras()
    if args.teste:
        return comando_teste(args)
    if args.camera is None and not args.transmitir and not args.camera_virtual:
        p.print_help()
        print("\n  Comece por:  python lyra.py --diagnostico\n")
        return 0
    return comando_transmitir(args)


if __name__ == "__main__":
    sys.exit(principal())
