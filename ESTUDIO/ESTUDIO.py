# -*- coding: utf-8 -*-
"""
ESTÚDIO — webcam Hollyland Lyra -> filtros -> YouTube, sem OBS no caminho.

    "um software para minha webcam ly7ra, que conecte diretamente ao youtube,
     um editor de audio com capacidade de melhorar o audio direto na live,
     uma ia basica rodando pra ajudar a melhorar a qualidade da imagem,
     filtros cinematograficos ao estilo camera sony, embelezamento,
     sem a necessidade de passar pelo obs"
    "coloque desfoque de fundo tambem"

    python ESTUDIO.py              abre o estúdio
    python ESTUDIO.py --verificar  confere a montagem inteira SEM abrir janela
                                   e sem webcam (é o que roda no teste)

COMO AS PARTES SE LIGAM
───────────────────────
    camera.py     thread própria, guarda só o quadro mais novo
        |
    motor.py      IA -> ruído -> desfoque de fundo -> beleza -> look ->
        |         acabamento, com governador de tempo
        +-------> preview (reduzido, 20 fps, só para ele ver)
        |
    transmissao.py --- vídeo pela entrada padrão do ffmpeg
                   \\-- som por socket TCP local
    audio.py      microfone -> cadeia de DSP -> PCM -> mesmo socket

A THREAD QUE PROCESSA NÃO É A DA INTERFACE, E ISSO NÃO É DETALHE
────────────────────────────────────────────────────────────────
Ver `tela_segura.py`. Quatro threads mexem em estado que a tela mostra, e o
Tkinter não sobrevive a ser chamado de fora da thread dele.

O ATRASO DO VÍDEO EXISTE DE PROPÓSITO
─────────────────────────────────────
A cadeia de áudio atrasa ~24 ms (janela da redução de ruído + antecipação do
limitador). Se o vídeo fosse enviado sem esse atraso, a voz chegaria ANTES da
imagem e a boca não casaria. Então a fila de vídeo segura os quadros pelo
mesmo tempo. É um detalhe que ninguém nota quando está certo e todo mundo
nota quando está errado.
"""
from __future__ import annotations

import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Optional, Tuple

import numpy as np

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import ajustes as AJ                                          # noqa: E402
import audio as AU                                            # noqa: E402
import camera as CAM                                          # noqa: E402
import dispositivos as DEV                                    # noqa: E402
import motor as MT                                            # noqa: E402
import transmissao as TX                                      # noqa: E402
import visual as V                                            # noqa: E402
from tela_segura import bombear, depois, marcar_thread_ui     # noqa: E402

try:
    import cv2
    TEM_CV = True
except Exception:                                             # pragma: no cover
    TEM_CV = False


# ─────────────────────────────────────────────────────────────────────────────
# O ESTÚDIO — tudo que funciona sem janela nenhuma
# ─────────────────────────────────────────────────────────────────────────────

class Estudio:
    """O motor do software. Não sabe que existe interface -- por isso testável."""

    def __init__(self, aj: Optional[dict] = None):
        self.aj = dict(aj or AJ.carregar())
        self.motor = MT.Motor()
        self.camera: Optional[CAM.Camera] = None
        self.mic: Optional[AU.Microfone] = None
        self.tx = TX.Transmissao()
        self.avisos: list = []
        self.preview: Optional[np.ndarray] = None
        self.rodando = False
        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._atraso: Deque[Tuple[float, np.ndarray]] = deque()
        self._ultimo_preview = 0.0
        self.fps_saida = 0.0
        self._marcas: Deque[float] = deque(maxlen=30)

    # ── dispositivos ──────────────────────────────────────────────────────
    def escolher_camera(self) -> Tuple[int, str]:
        lista = DEV.listar("video")
        d, motivo = DEV.escolher(lista, self.aj.get("camera_nome", "lyra"),
                                 int(self.aj.get("camera_indice", -1)))
        return (d.indice if d else 0), motivo

    def escolher_microfone(self) -> Tuple[int, str]:
        lista = DEV.microfones()
        d, motivo = DEV.escolher(lista, self.aj.get("microfone_nome", ""),
                                 int(self.aj.get("microfone_indice", -1)))
        return (d.indice if d else -1), motivo

    # ── ciclo ─────────────────────────────────────────────────────────────
    def abrir(self, camera_falsa: Optional[np.ndarray] = None) -> Tuple[bool, str]:
        """Abre câmera e microfone. `camera_falsa` é o que o teste usa."""
        self.avisos = []
        if camera_falsa is None:
            indice, motivo = self.escolher_camera()
            self.avisos.append(f"câmera: {motivo}")
            self.camera = CAM.Camera(indice, int(self.aj["largura"]),
                                     int(self.aj["altura"]), int(self.aj["fps"]))
            ok, msg = self.camera.abrir()
            if not ok:
                return False, msg
            self.avisos.append(msg)
            if self.camera.estado.aviso:
                self.avisos.append("atenção: " + self.camera.estado.aviso)
        else:
            self.camera = _CameraFalsa(camera_falsa)
            self.camera.abrir()
            self.avisos.append("câmera de teste (nenhum dispositivo real)")

        if self.aj.get("audio_ligado", True):
            im, motivo_m = self.escolher_microfone()
            self.mic = AU.Microfone(im, AU.TAXA, 1)
            ok, msg = self.mic.abrir()
            self.avisos.append(f"microfone: {motivo_m}" if ok else
                               f"SEM ÁUDIO — {msg}")
            if not ok:
                self.mic = None
            else:
                self.mic.saida = self._audio_pronto

        self._parar.clear()
        self.rodando = True
        self._thread = threading.Thread(target=self._laco, daemon=True,
                                        name="estudio")
        self._thread.start()
        return True, "estúdio aberto"

    def _audio_pronto(self, bloco: np.ndarray) -> None:
        """Chamado pela thread de áudio. Só empurra para o ffmpeg."""
        if self.tx.estado.rodando:
            self.tx.enviar_audio(AU.para_pcm16(bloco))

    @property
    def atraso_video_s(self) -> float:
        """O quanto o vídeo espera para casar com o áudio."""
        if self.mic is None or not self.tx.estado.rodando:
            return 0.0
        return self.mic.cadeia.latencia_ms / 1000.0

    def _laco(self) -> None:
        while not self._parar.is_set():
            quadro = self.camera.pegar() if self.camera else None
            if quadro is None:
                time.sleep(0.002)
                continue
            try:
                pronto = self.motor.processar(quadro, self.aj)
            except Exception as e:
                self.avisos.append(f"erro no processamento: {e}")
                time.sleep(0.05)
                continue

            agora = time.perf_counter()
            self._marcas.append(agora)
            if len(self._marcas) > 5:
                d = self._marcas[-1] - self._marcas[0]
                self.fps_saida = (len(self._marcas) - 1) / d if d > 0 else 0.0

            # preview a 20 fps e reduzido: a tela não precisa de mais, e cada
            # milissegundo gasto desenhando é um milissegundo tirado da live
            if TEM_CV and agora - self._ultimo_preview > 0.05:
                self._ultimo_preview = agora
                h, w = pronto.shape[:2]
                k = 480.0 / max(1, w)
                self.preview = cv2.resize(pronto, (480, max(2, int(h * k))),
                                          interpolation=cv2.INTER_AREA) \
                    if k < 1 else pronto

            if self.tx.estado.rodando:
                self._enviar_com_atraso(pronto, agora)
            else:
                self._atraso.clear()

    def _enviar_com_atraso(self, quadro: np.ndarray, agora: float) -> None:
        """Segura o quadro pelo atraso do áudio, e só então manda."""
        espera = self.atraso_video_s
        if espera <= 0.001:
            self.tx.enviar_video(quadro)
            return
        self._atraso.append((agora, quadro))
        while self._atraso and (agora - self._atraso[0][0]) >= espera:
            _, q = self._atraso.popleft()
            if not self.tx.enviar_video(q):
                break
        # trava de segurança: fila crescendo é sinal de que o ffmpeg não está
        # consumindo. Melhor perder quadro antigo que estourar a memória.
        while len(self._atraso) > 120:
            self._atraso.popleft()
            self.tx.estado.quadros_perdidos += 1

    def transmitir(self) -> Tuple[bool, str]:
        chave = AJ.chave()
        if not chave:
            return False, ("falta a chave de transmissão do YouTube — "
                           "cole em Transmissão e salve")
        if self.camera is None or not self.camera.estado.aberta:
            return False, "a câmera não está aberta"
        e = self.camera.estado
        gravar = ""
        if self.aj.get("gravar_local", True):
            pasta = Path(self.aj.get("pasta_gravacao") or (RAIZ / "gravacoes"))
            pasta.mkdir(parents=True, exist_ok=True)
            gravar = str(pasta / f"live_{time.strftime('%Y-%m-%d_%H-%M-%S')}.mp4")
        return self.tx.iniciar(
            AJ.url_youtube(chave), e.largura, e.altura, int(self.aj["fps"]),
            str(self.aj.get("encoder", "auto")),
            int(self.aj.get("bitrate_video", 4500)),
            int(self.aj.get("bitrate_audio", 160)), 1, gravar)

    def parar_transmissao(self) -> None:
        self.tx.parar()
        self._atraso.clear()

    def fechar(self) -> None:
        self.rodando = False
        self._parar.set()
        self.parar_transmissao()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self.mic is not None:
            self.mic.fechar()
            self.mic = None
        if self.camera is not None:
            self.camera.fechar()
            self.camera = None


class _CameraFalsa:
    """Uma câmera que devolve sempre o mesmo quadro. Só o teste usa."""

    def __init__(self, quadro: np.ndarray):
        self._q = quadro
        self.estado = CAM.EstadoCamera(aberta=True, largura=quadro.shape[1],
                                       altura=quadro.shape[0], fps_pedido=30,
                                       formato="TESTE")

    def abrir(self):
        return True, "câmera de teste"

    def pegar(self):
        time.sleep(0.005)
        return self._q.copy()

    def fechar(self):
        self.estado.aberta = False


# ─────────────────────────────────────────────────────────────────────────────
# A JANELA
# ─────────────────────────────────────────────────────────────────────────────

def abrir_janela() -> int:                                     # pragma: no cover
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as e:
        print(f"sem interface gráfica disponível: {e}")
        return 2
    try:
        import customtkinter as ctk
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        BASE, TEM_CTK = ctk.CTk, True
    except Exception:
        BASE, TEM_CTK, ctk = tk.Tk, False, None
    try:
        from PIL import Image, ImageTk
        TEM_PIL = True
    except Exception:
        TEM_PIL = False

    aj = AJ.carregar()
    est = Estudio(aj)

    janela = BASE()
    janela.title("ESTÚDIO — Hollyland Lyra para o YouTube")
    janela.geometry("1180x760")
    marcar_thread_ui()

    Frame = ctk.CTkFrame if TEM_CTK else ttk.Frame
    Label = ctk.CTkLabel if TEM_CTK else ttk.Label
    Botao = ctk.CTkButton if TEM_CTK else ttk.Button

    esq = Frame(janela)
    esq.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    tela = tk.Label(esq, bg="#101010", text="abrindo a câmera...",
                    fg="#dddddd")
    tela.pack(fill="both", expand=True)
    barra = Label(esq, text="—", anchor="w", justify="left")
    barra.pack(fill="x", pady=(6, 0))

    dir_ = Frame(janela, width=380)
    dir_.pack(side="right", fill="y", padx=8, pady=8)
    dir_.pack_propagate(False)

    controles: dict = {}

    def cursor(pai, campo: str, rotulo: str, de: float, ate: float) -> None:
        linha = Frame(pai)
        linha.pack(fill="x", pady=2)
        texto = Label(linha, text=rotulo, width=210 if TEM_CTK else 24,
                      anchor="w")
        texto.pack(side="left")
        var = tk.DoubleVar(value=float(est.aj.get(campo, 0.0)))

        def mudou(valor=None) -> None:
            est.aj[campo] = AJ.grampear(campo, var.get())
        if TEM_CTK:
            c = ctk.CTkSlider(linha, from_=de, to=ate, variable=var,
                              command=lambda _v: mudou(), width=140)
        else:
            c = ttk.Scale(linha, from_=de, to=ate, variable=var,
                          command=lambda _v: mudou())
        c.pack(side="right", fill="x", expand=True)
        controles[campo] = var

    def marca(pai, campo: str, rotulo: str) -> None:
        var = tk.BooleanVar(value=bool(est.aj.get(campo, True)))

        def mudou() -> None:
            est.aj[campo] = bool(var.get())
        if TEM_CTK:
            c = ctk.CTkSwitch(pai, text=rotulo, variable=var, command=mudou)
        else:
            c = ttk.Checkbutton(pai, text=rotulo, variable=var, command=mudou)
        c.pack(anchor="w", pady=2)
        controles[campo] = var

    caderno = ttk.Notebook(dir_)
    caderno.pack(fill="both", expand=True)

    # ── aba imagem ────────────────────────────────────────────────────────
    ab_img = Frame(caderno)
    caderno.add(ab_img, text="Imagem")
    Label(ab_img, text="Filtro cinematográfico", anchor="w").pack(fill="x")
    look_var = tk.StringVar(value=str(est.aj.get("look", "s_cinetone")))
    nomes = {k: v.nome_na_tela for k, v in V.LOOKS.items()}

    def trocou_look(_e=None) -> None:
        for k, n in nomes.items():
            if n == look_var.get() or k == look_var.get():
                est.aj["look"] = k
                lk = V.LOOKS[k]
                porque.configure(text=lk.porque)
                return
    if TEM_CTK:
        cx = ctk.CTkOptionMenu(ab_img, values=list(nomes.values()),
                               variable=look_var, command=trocou_look)
    else:
        cx = ttk.Combobox(ab_img, values=list(nomes.values()),
                          textvariable=look_var, state="readonly")
        cx.bind("<<ComboboxSelected>>", trocou_look)
    cx.pack(fill="x", pady=3)
    look_var.set(nomes.get(est.aj.get("look", "s_cinetone"), "Cru (sem filtro)"))
    porque = Label(ab_img, text=V.LOOKS.get(est.aj.get("look", "s_cinetone"),
                                            V.LOOKS["cru"]).porque,
                   anchor="w", justify="left",
                   wraplength=340 if TEM_CTK else 340)
    porque.pack(fill="x", pady=(0, 6))
    for campo, rot, a, b in (("look_forca", "força do filtro", 0, 1),
                             ("nitidez", "nitidez", 0, 1),
                             ("grao", "grão de filme", 0, 1),
                             ("vinheta", "vinheta", 0, 1),
                             ("halacao", "halação (brilho da luz)", 0, 1)):
        cursor(ab_img, campo, rot, a, b)
    Label(ab_img, text="IA de imagem", anchor="w").pack(fill="x", pady=(10, 0))
    for campo, rot in (("ia_ligada", "IA ligada"),
                       ("ia_exposicao", "corrige claro/escuro"),
                       ("ia_branco", "corrige a cor da luz"),
                       ("ia_ruido", "reduz chuvisco")):
        marca(ab_img, campo, rot)
    cursor(ab_img, "ia_alvo_rosto", "brilho alvo do rosto", 0.2, 0.9)
    cursor(ab_img, "ia_forca", "rapidez da correção", 0.0, 1.0)

    # ── aba beleza e fundo ────────────────────────────────────────────────
    ab_bel = Frame(caderno)
    caderno.add(ab_bel, text="Beleza e fundo")
    marca(ab_bel, "beleza_ligada", "embelezamento ligado")
    for campo, rot in (("beleza_pele", "alisar pele"),
                       ("beleza_manchas", "reduzir manchas"),
                       ("beleza_olhos", "clarear olhos"),
                       ("beleza_dentes", "clarear dentes")):
        cursor(ab_bel, campo, rot, 0.0, 1.0)
    marca(ab_bel, "beleza_so_no_rosto", "só dentro do rosto")
    Label(ab_bel, text="Desfoque de fundo", anchor="w").pack(fill="x",
                                                             pady=(10, 0))
    est.aj.setdefault("desfoque_fundo", 0.0)
    est.aj.setdefault("desfoque_brilho", 0.25)
    cursor(ab_bel, "desfoque_fundo", "quanto desfocar", 0.0, 1.0)
    cursor(ab_bel, "desfoque_brilho", "brilho das luzes ao fundo", 0.0, 1.0)
    nivel_fundo = Label(ab_bel, text="", anchor="w", justify="left",
                        wraplength=340)
    nivel_fundo.pack(fill="x", pady=(4, 0))

    # ── aba áudio ─────────────────────────────────────────────────────────
    ab_au = Frame(caderno)
    caderno.add(ab_au, text="Áudio")
    marca(ab_au, "audio_ligado", "áudio ligado")
    for campo, rot, a, b in (("au_ganho_db", "ganho de entrada (dB)", -24, 24),
                             ("au_corte_graves", "corte de graves (Hz)", 0, 300),
                             ("au_ruido", "reduzir chiado", 0, 1),
                             ("au_portao", "portão de ruído (dBFS)", -90, 0),
                             ("au_ess", "domar o 'sss'", 0, 1),
                             ("au_eq_corpo", "corpo (200 Hz)", -12, 12),
                             ("au_eq_medio", "tirar o abafado (900 Hz)", -12, 12),
                             ("au_eq_presenca", "presença (4 kHz)", -12, 12),
                             ("au_compressor", "nivelar volume", 0, 1),
                             ("au_teto_db", "teto do limitador (dB)", -12, 0)):
        cursor(ab_au, campo, rot, a, b)
    medidor = Label(ab_au, text="—", anchor="w", justify="left",
                    wraplength=340)
    medidor.pack(fill="x", pady=(10, 0))

    # ── aba transmissão ───────────────────────────────────────────────────
    ab_tx = Frame(caderno)
    caderno.add(ab_tx, text="Transmissão")
    Label(ab_tx, text="Chave de transmissão do YouTube", anchor="w") \
        .pack(fill="x")
    ent = (ctk.CTkEntry(ab_tx, show="•") if TEM_CTK
           else ttk.Entry(ab_tx, show="•"))
    ent.pack(fill="x", pady=3)
    estado_chave = Label(ab_tx, text=f"guardada: {AJ.mascara(AJ.chave())}",
                         anchor="w")
    estado_chave.pack(fill="x")

    def salvar_chave() -> None:
        v = ent.get().strip()
        if v:
            AJ.gravar_chave(v)
            ent.delete(0, "end")
        estado_chave.configure(text=f"guardada: {AJ.mascara(AJ.chave())}")
    Botao(ab_tx, text="Guardar chave", command=salvar_chave).pack(fill="x",
                                                                  pady=3)
    for campo, rot, a, b in (("bitrate_video", "qualidade do vídeo (kbps)",
                              500, 12000),
                             ("bitrate_audio", "qualidade do som (kbps)",
                              64, 320)):
        cursor(ab_tx, campo, rot, a, b)
    marca(ab_tx, "gravar_local", "gravar cópia no computador")
    estado_tx = Label(ab_tx, text="parado", anchor="w", justify="left",
                      wraplength=340)
    estado_tx.pack(fill="x", pady=(8, 0))

    def ligar() -> None:
        ok, msg = est.transmitir()
        estado_tx.configure(text=msg)
        botao_tx.configure(text="PARAR" if ok else "TRANSMITIR")

    def desligar() -> None:
        est.parar_transmissao()
        estado_tx.configure(text="parado")
        botao_tx.configure(text="TRANSMITIR")

    def alternar() -> None:
        (desligar if est.tx.estado.rodando else ligar)()
    botao_tx = Botao(ab_tx, text="TRANSMITIR", command=alternar)
    botao_tx.pack(fill="x", pady=8)

    def salvar_tudo() -> None:
        AJ.salvar(est.aj)
        estado_tx.configure(text="ajustes salvos")
    Botao(dir_, text="Salvar ajustes", command=salvar_tudo).pack(fill="x",
                                                                 pady=(6, 0))

    # ── o desenho ─────────────────────────────────────────────────────────
    guardar_imagem: dict = {}

    def pintar() -> None:
        img = est.preview
        if img is not None and TEM_PIL and TEM_CV:
            try:
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                foto = ImageTk.PhotoImage(Image.fromarray(rgb))
                guardar_imagem["ref"] = foto      # sem isto o Tk descarta
                tela.configure(image=foto, text="")
            except Exception:
                pass
        d = est.motor.diag
        cam = est.camera.estado if est.camera else None
        partes = [f"{d.fps:4.1f} fps processados ({d.ms_quadro:.0f} ms)"]
        if cam:
            partes.append(f"câmera {cam.largura}x{cam.altura} "
                          f"{cam.formato} {cam.fps_real:.0f} fps")
        partes.append(f"rosto por {d.nivel_rosto}"
                      + ("" if d.tem_rosto else " (não achei rosto)"))
        if d.desligados:
            partes.append("DESLIGADO para caber no tempo: "
                          + ", ".join(d.desligados))
        if est.tx.estado.rodando:
            partes.append(f"NO AR {int(est.tx.estado.segundos_no_ar)}s "
                          f"· {est.tx.estado.encoder}")
        if est.tx.estado.erro:
            partes.append("ffmpeg: " + est.tx.estado.erro)
        barra.configure(text="  ·  ".join(partes))
        nivel_fundo.configure(text=f"recorte por: {d.nivel_fundo or '—'}")

        if est.mic is not None:
            m = est.mic.cadeia.medidores
            est.mic.ajustes.update(
                ganho_db=est.aj["au_ganho_db"], forca_ruido=est.aj["au_ruido"],
                ess=est.aj["au_ess"], compressor=est.aj["au_compressor"],
                teto_db=est.aj["au_teto_db"])
            est.mic.cadeia.ajustar(est.aj["au_corte_graves"],
                                   est.aj["au_eq_corpo"], est.aj["au_eq_medio"],
                                   est.aj["au_eq_presenca"], est.aj["au_portao"])
            medidor.configure(
                text=(f"pico {m.pico_db:6.1f} dBFS   rms {m.rms_db:6.1f} dBFS\n"
                      f"compressor segurando {m.reducao_db:4.1f} dB   "
                      f"portão {'aberto' if m.portao_aberto > 0.5 else 'fechado'}\n"
                      f"atraso da cadeia {m.latencia_ms:.0f} ms   "
                      f"blocos perdidos {m.descartes}"))
        depois(janela, pintar, 50)

    def fechar() -> None:
        try:
            AJ.salvar(est.aj)
        except Exception:
            pass
        est.fechar()
        janela.destroy()
    janela.protocol("WM_DELETE_WINDOW", fechar)

    ok, msg = est.abrir()
    barra.configure(text=msg if ok else f"NÃO ABRIU: {msg}")
    for a in est.avisos:
        print(a)
    bombear(janela, 33)
    depois(janela, pintar, 100)
    janela.mainloop()
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICAÇÃO SEM JANELA
# ─────────────────────────────────────────────────────────────────────────────

def verificar() -> int:
    """Monta o estúdio inteiro com uma câmera falsa e confere que ele anda.

    Sem janela, sem webcam, sem microfone, sem internet -- é o que permite
    este software ter teste automático de verdade, e não só de peças soltas.
    """
    print("VERIFICAÇÃO DO ESTÚDIO (sem janela, sem webcam)")
    falha = []

    quadro = np.zeros((720, 1280, 3), dtype=np.uint8)
    if TEM_CV:
        for i in range(0, 1280, 40):
            cv2.line(quadro, (i, 0), (i, 720), (190, 190, 190), 3)
        cv2.ellipse(quadro, (640, 340), (150, 195), 0, 0, 360,
                    (120, 150, 190), -1)

    aj = dict(AJ.PADRAO)
    aj["audio_ligado"] = False          # não há microfone no verificador
    aj["desfoque_fundo"] = 0.6
    est = Estudio(aj)
    ok, msg = est.abrir(camera_falsa=quadro)
    print(f"  abrir: {msg}")
    if not ok:
        return 1

    time.sleep(2.5)
    d = est.motor.diag
    print(f"  processou a {d.fps:.1f} fps ({d.ms_quadro:.0f} ms/quadro)")
    print(f"  look: {d.look}")
    print(f"  rosto por: {d.nivel_rosto} | fundo por: {d.nivel_fundo}")
    print(f"  IA: {d.motivo_ia}")
    if d.desligados:
        print(f"  governador desligou: {', '.join(d.desligados)}")
    if est.preview is None:
        falha.append("o preview não foi gerado")
    if d.fps <= 0:
        falha.append("nenhum quadro processado")

    ok_tx, msg_tx = est.transmitir()
    print(f"  transmitir sem chave: {msg_tx}")
    if ok_tx:
        falha.append("transmitiu sem chave configurada")
    est.fechar()

    print("  VERIFICAÇÃO OK" if not falha else "  FALHAS: " + "; ".join(falha))
    return 1 if falha else 0


if __name__ == "__main__":
    sys.exit(verificar() if "--verificar" in sys.argv else abrir_janela())
