# -*- coding: utf-8 -*-
"""
O painel: a janela onde se mexe em tudo com a live no ar.

UMA REGRA DE INTERFACE
----------------------
Nada aqui para a transmissão para aplicar uma mudança. Mexer no embelezamento,
trocar o look, ligar o desfoque de fundo — tudo entra no quadro seguinte, com a
live rodando. Slider que exige reiniciar a transmissão é slider que ninguém usa
durante uma live.

Só três coisas exigem religar, e o botão diz isso: câmera, resolução e taxa de
quadros, porque são elas que definem o formato que o encoder negociou com o
YouTube no começo da transmissão.

A PRÉVIA MOSTRA O QUE VAI AO AR
-------------------------------
A imagem da esquerda é o quadro DEPOIS de todos os filtros — o mesmo array que
foi para o ffmpeg. Não é uma simulação da aparência final: é o quadro final.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

try:
    import customtkinter as ctk
except ImportError:  # pragma: no cover - depende da máquina
    print("O painel precisa do customtkinter:  pip install customtkinter Pillow\n"
          "Sem ele, use a linha de comando:     python lyra.py --diagnostico")
    raise SystemExit(1)

from tkinter import filedialog, messagebox

import numpy as np

from ia.qwen import SUGESTOES, ClienteQwen
from ia.supervisor import Supervisor
from nucleo import config as CFG
from nucleo import youtube as YT
from nucleo.camera import listar_cameras
from nucleo.filtros import LOOKS
from nucleo.fundo import MODOS as MODOS_FUNDO
from nucleo.pipeline import Pipeline

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover - depende da máquina
    Image = ImageTk = None

RESOLUCOES = ["640x360", "854x480", "1280x720", "1920x1080", "2560x1440"]
CORES = {"ok": "#22c55e", "atencao": "#eab308", "grave": "#ef4444", "off": "#64748b"}


class PainelLyra(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LYRA LIVE — transmissão com filtros")
        self.geometry("1320x860")
        self.minsize(1120, 720)
        ctk.set_appearance_mode("dark")

        self.perfil = CFG.carregar()
        self.perfil.saida.chave = CFG.carregar_chave()
        self.esteira: Pipeline | None = None
        self.supervisor: Supervisor | None = None
        self._foto = None                 # referência viva da imagem da prévia
        self._ultimo_aviso = ""

        self._montar()
        self._laco_previa()
        self._laco_estado()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # ------------------------------------------------------------------ UI
    def _montar(self) -> None:
        topo = ctk.CTkFrame(self)
        topo.pack(fill="x", padx=10, pady=(10, 6))
        ctk.CTkLabel(topo, text="LYRA LIVE", font=("Arial", 22, "bold"),
                     text_color="#38bdf8").pack(side="left", padx=10)
        self.rot_estado = ctk.CTkLabel(topo, text="parada", text_color=CORES["off"],
                                       font=("Arial", 13, "bold"))
        self.rot_estado.pack(side="left", padx=12)
        self.bt_ligar = ctk.CTkButton(topo, text="LIGAR CÂMERA", width=150,
                                      fg_color="#16a34a", command=self._alternar)
        self.bt_ligar.pack(side="right", padx=6)
        ctk.CTkButton(topo, text="Salvar perfil", width=110, fg_color="#475569",
                      command=self._salvar_perfil).pack(side="right", padx=6)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=10, pady=4)

        esquerda = ctk.CTkFrame(corpo)
        esquerda.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.tela = ctk.CTkLabel(esquerda, text="A prévia aparece aqui quando a câmera ligar.",
                                 fg_color="#0b1220", corner_radius=8)
        self.tela.pack(fill="both", expand=True, padx=8, pady=8)
        self.rot_metricas = ctk.CTkLabel(esquerda, text="—", font=("Consolas", 12),
                                         text_color="#94a3b8")
        self.rot_metricas.pack(fill="x", padx=10, pady=(0, 8))

        abas = ctk.CTkTabview(corpo, width=430)
        abas.pack(side="right", fill="both")
        for nome in ("Imagem", "Fundo", "YouTube", "IA"):
            abas.add(nome)
        self._aba_imagem(abas.tab("Imagem"))
        self._aba_fundo(abas.tab("Fundo"))
        self._aba_youtube(abas.tab("YouTube"))
        self._aba_ia(abas.tab("IA"))

    def _slider(self, pai, rotulo, de, ate, valor, comando):
        """Um controle com nome, valor visível e o slider — o padrão da janela."""
        linha = ctk.CTkFrame(pai, fg_color="transparent")
        linha.pack(fill="x", padx=8, pady=3)
        ctk.CTkLabel(linha, text=rotulo, width=140, anchor="w").pack(side="left")
        mostrador = ctk.CTkLabel(linha, text=str(int(valor)), width=42,
                                 text_color="#38bdf8")
        mostrador.pack(side="right")

        def ao_mover(v):
            mostrador.configure(text=str(int(float(v))))
            comando(int(float(v)))

        s = ctk.CTkSlider(linha, from_=de, to=ate, command=ao_mover,
                          number_of_steps=int(ate - de))
        s.set(valor)
        s.pack(side="left", fill="x", expand=True, padx=8)
        return s

    def _aba_imagem(self, aba) -> None:
        aj = self.perfil.ajustes
        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(linha, text="Look", width=140, anchor="w").pack(side="left")
        self.sel_look = ctk.CTkOptionMenu(linha, values=list(LOOKS),
                                          command=self._mudou_look)
        self.sel_look.set(aj.look)
        self.sel_look.pack(side="left", fill="x", expand=True, padx=8)

        self._slider(aba, "Intensidade do look", 0, 100, aj.intensidade_look,
                     lambda v: self._ajuste("intensidade_look", v))
        ctk.CTkLabel(aba, text="EMBELEZAMENTO", font=("Arial", 12, "bold"),
                     text_color="#f472b6").pack(anchor="w", padx=10, pady=(10, 0))
        self._slider(aba, "Suavizar pele", 0, 100, aj.embelezamento,
                     lambda v: self._ajuste("embelezamento", v))
        self._slider(aba, "Uniformizar tom", 0, 100, aj.uniformizar_pele,
                     lambda v: self._ajuste("uniformizar_pele", v))
        ctk.CTkLabel(aba, text="AJUSTE FINO", font=("Arial", 12, "bold"),
                     text_color="#f472b6").pack(anchor="w", padx=10, pady=(10, 0))
        for rotulo, campo, de, ate in (("Brilho", "brilho", -100, 100),
                                       ("Contraste", "contraste", -100, 100),
                                       ("Saturação", "saturacao", -100, 100),
                                       ("Temperatura", "temperatura", -100, 100),
                                       ("Nitidez", "nitidez", 0, 100),
                                       ("Vinheta", "vinheta", 0, 100)):
            self._slider(aba, rotulo, de, ate, getattr(aj, campo),
                         lambda v, c=campo: self._ajuste(c, v))

        self.var_espelhar = ctk.BooleanVar(value=aj.espelhar)
        ctk.CTkCheckBox(aba, text="Espelhar (como um espelho)", variable=self.var_espelhar,
                        command=lambda: self._ajuste("espelhar", self.var_espelhar.get())
                        ).pack(anchor="w", padx=12, pady=8)
        ctk.CTkButton(aba, text="Voltar ao padrão", fg_color="#475569",
                      command=self._padrao_imagem).pack(padx=10, pady=6, fill="x")

    def _aba_fundo(self, aba) -> None:
        ef = self.perfil.fundo
        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.pack(fill="x", padx=8, pady=6)
        ctk.CTkLabel(linha, text="Efeito", width=120, anchor="w").pack(side="left")
        self.sel_fundo = ctk.CTkOptionMenu(
            linha, values=list(MODOS_FUNDO), command=self._mudou_fundo)
        self.sel_fundo.set(ef.modo)
        self.sel_fundo.pack(side="left", fill="x", expand=True, padx=8)

        self._slider(aba, "Força do desfoque", 0, 100, ef.intensidade,
                     lambda v: self._fundo("intensidade", v))
        self._slider(aba, "Suavizar borda", 0, 20, ef.recorte_suave,
                     lambda v: self._fundo("recorte_suave", v))
        self._slider(aba, "Estabilizar", 0, 95, ef.suavizacao_temporal,
                     lambda v: self._fundo("suavizacao_temporal", v))

        ctk.CTkButton(aba, text="Escolher imagem de fundo...", fg_color="#475569",
                      command=self._escolher_imagem).pack(padx=10, pady=(10, 4), fill="x")

        ctk.CTkLabel(aba, text="COMO RECORTAR A PESSOA", font=("Arial", 12, "bold"),
                     text_color="#f472b6").pack(anchor="w", padx=10, pady=(12, 0))
        self.sel_segmentador = ctk.CTkOptionMenu(
            aba, values=["auto", "mediapipe", "fundo_aprendido", "central"],
            command=self._mudou_segmentador)
        self.sel_segmentador.set(self.perfil.segmentador)
        self.sel_segmentador.pack(padx=10, pady=6, fill="x")
        ctk.CTkButton(aba, text="Aprender fundo (saia do quadro antes)",
                      fg_color="#7c3aed", command=self._aprender_fundo
                      ).pack(padx=10, pady=4, fill="x")
        self.rot_segmentador = ctk.CTkLabel(aba, text="", wraplength=380, justify="left",
                                            text_color="#94a3b8")
        self.rot_segmentador.pack(anchor="w", padx=12, pady=6)

    def _aba_youtube(self, aba) -> None:
        cam = self.perfil.camera
        ctk.CTkLabel(aba, text="CÂMERA", font=("Arial", 12, "bold"),
                     text_color="#f472b6").pack(anchor="w", padx=10, pady=(8, 0))
        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.pack(fill="x", padx=8, pady=4)
        self.ent_camera = ctk.CTkEntry(linha, placeholder_text="0  ou  rtsp://192.168.0.50/live")
        self.ent_camera.insert(0, str(cam.origem))
        self.ent_camera.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(linha, text="Procurar", width=80, fg_color="#475569",
                      command=self._procurar_cameras).pack(side="left", padx=6)

        linha2 = ctk.CTkFrame(aba, fg_color="transparent")
        linha2.pack(fill="x", padx=8, pady=4)
        self.sel_resolucao = ctk.CTkOptionMenu(linha2, values=RESOLUCOES, width=140)
        self.sel_resolucao.set(f"{cam.largura}x{cam.altura}")
        self.sel_resolucao.pack(side="left")
        self.sel_fps = ctk.CTkOptionMenu(linha2, values=["24", "30", "60"], width=80)
        self.sel_fps.set(str(cam.fps))
        self.sel_fps.pack(side="left", padx=8)
        ctk.CTkLabel(linha2, text="(religar para aplicar)",
                     text_color="#64748b").pack(side="left")

        ctk.CTkLabel(aba, text="CHAVE DE TRANSMISSÃO", font=("Arial", 12, "bold"),
                     text_color="#f472b6").pack(anchor="w", padx=10, pady=(12, 0))
        self.ent_chave = ctk.CTkEntry(aba, show="*",
                                      placeholder_text="xxxx-xxxx-xxxx-xxxx-xxxx")
        self.ent_chave.insert(0, self.perfil.saida.chave)
        self.ent_chave.pack(fill="x", padx=10, pady=4)
        self.ent_chave.bind("<KeyRelease>", lambda _e: self._conferir_chave())
        self.rot_chave = ctk.CTkLabel(aba, text="", wraplength=380, justify="left",
                                      text_color="#94a3b8")
        self.rot_chave.pack(anchor="w", padx=12)
        ctk.CTkLabel(aba, text="YouTube Studio > Transmitir ao vivo > Configurações da "
                              "transmissão. A chave fica gravada só nesta máquina.",
                     wraplength=380, justify="left",
                     text_color="#64748b").pack(anchor="w", padx=12, pady=4)

        self.var_transmitir = ctk.BooleanVar(value=self.perfil.transmitir)
        ctk.CTkCheckBox(aba, text="Transmitir para o YouTube (RTMP)",
                        variable=self.var_transmitir).pack(anchor="w", padx=12, pady=(10, 2))
        self.var_virtual = ctk.BooleanVar(value=self.perfil.camera_virtual)
        ctk.CTkCheckBox(aba, text="Publicar como câmera do sistema (webcam virtual)",
                        variable=self.var_virtual).pack(anchor="w", padx=12, pady=2)

        linha3 = ctk.CTkFrame(aba, fg_color="transparent")
        linha3.pack(fill="x", padx=8, pady=(10, 2))
        ctk.CTkLabel(linha3, text="Codificador", width=100, anchor="w").pack(side="left")
        self.sel_codificador = ctk.CTkOptionMenu(
            linha3, values=["auto", "cpu", "nvidia", "intel", "amd"])
        self.sel_codificador.set(self.perfil.saida.codificador)
        self.sel_codificador.pack(side="left", fill="x", expand=True, padx=8)

        linha4 = ctk.CTkFrame(aba, fg_color="transparent")
        linha4.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(linha4, text="Microfone", width=100, anchor="w").pack(side="left")
        self.ent_audio = ctk.CTkEntry(linha4, placeholder_text="vazio = transmite em silêncio")
        self.ent_audio.insert(0, self.perfil.saida.audio_dispositivo)
        self.ent_audio.pack(side="left", fill="x", expand=True, padx=8)
        self._conferir_chave()

    def _aba_ia(self, aba) -> None:
        ctk.CTkLabel(aba, text="A IA acompanha a live e avisa quando algo sai do lugar.",
                     wraplength=380, justify="left").pack(anchor="w", padx=12, pady=(10, 4))
        self.var_ia = ctk.BooleanVar(value=self.perfil.ia_ativa)
        ctk.CTkCheckBox(aba, text="IA supervisora ligada", variable=self.var_ia
                        ).pack(anchor="w", padx=12, pady=4)

        linha = ctk.CTkFrame(aba, fg_color="transparent")
        linha.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(linha, text="Modelo", width=80, anchor="w").pack(side="left")
        self.sel_modelo = ctk.CTkComboBox(linha, values=list(SUGESTOES))
        self.sel_modelo.set(self.perfil.ia_modelo)
        self.sel_modelo.pack(side="left", fill="x", expand=True, padx=8)

        linha2 = ctk.CTkFrame(aba, fg_color="transparent")
        linha2.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(linha2, text="Servidor", width=80, anchor="w").pack(side="left")
        self.ent_ia = ctk.CTkEntry(linha2)
        self.ent_ia.insert(0, self.perfil.ia_endereco)
        self.ent_ia.pack(side="left", fill="x", expand=True, padx=8)

        ctk.CTkButton(aba, text="Testar conexão com a IA", fg_color="#475569",
                      command=self._testar_ia).pack(padx=10, pady=6, fill="x")
        ctk.CTkButton(aba, text="Analisar agora", fg_color="#7c3aed",
                      command=self._analisar_agora).pack(padx=10, pady=(0, 8), fill="x")

        self.txt_ia = ctk.CTkTextbox(aba, height=300, font=("Consolas", 11), wrap="word")
        self.txt_ia.pack(fill="both", expand=True, padx=10, pady=6)
        self.txt_ia.insert("1.0", "A IA começa a acompanhar quando a câmera ligar.")

    # ------------------------------------------------------- manipuladores
    def _ajuste(self, campo: str, valor) -> None:
        setattr(self.perfil.ajustes, campo, valor)
        self.perfil.ajustes.validar()
        if self.esteira:
            self.esteira.definir_ajustes(self.perfil.ajustes)

    def _fundo(self, campo: str, valor) -> None:
        setattr(self.perfil.fundo, campo, valor)
        self.perfil.fundo.validar()
        if self.esteira:
            self.esteira.definir_fundo(self.perfil.fundo)

    def _mudou_look(self, valor: str) -> None:
        self._ajuste("look", valor)

    def _mudou_fundo(self, valor: str) -> None:
        self._fundo("modo", valor)

    def _mudou_segmentador(self, valor: str) -> None:
        self.perfil.segmentador = valor
        if self.esteira:
            self.esteira.definir_segmentador(valor)

    def _padrao_imagem(self) -> None:
        from nucleo.filtros import Ajustes
        self.perfil.ajustes = Ajustes()
        if self.esteira:
            self.esteira.definir_ajustes(self.perfil.ajustes)
        messagebox.showinfo("Lyra Live", "Ajustes de imagem voltaram ao padrão.\n"
                                         "Reabra o painel para os controles refletirem.")

    def _escolher_imagem(self) -> None:
        caminho = filedialog.askopenfilename(
            title="Imagem de fundo",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.webp"), ("Todos", "*.*")])
        if caminho:
            self._fundo("caminho_imagem", caminho)
            self.sel_fundo.set("imagem")
            self._fundo("modo", "imagem")

    def _aprender_fundo(self) -> None:
        if not self.esteira or not self.esteira.rodando:
            messagebox.showwarning("Lyra Live", "Ligue a câmera primeiro.")
            return
        if self.perfil.segmentador != "fundo_aprendido":
            self.sel_segmentador.set("fundo_aprendido")
            self._mudou_segmentador("fundo_aprendido")
        if self.esteira.aprender_fundo():
            messagebox.showinfo("Lyra Live", "Fundo memorizado. Pode voltar para o quadro.")
        else:
            messagebox.showwarning("Lyra Live", "Não consegui memorizar o fundo agora.")

    def _procurar_cameras(self) -> None:
        achadas = listar_cameras(8)
        if not achadas:
            messagebox.showinfo(
                "Lyra Live",
                "Nenhuma webcam por índice.\n\nSe a Lyra é de rede, escreva a URL dela "
                "no campo, por exemplo:\nrtsp://192.168.0.50:554/live")
            return
        texto = "\n".join(c["descricao"] for c in achadas)
        self.ent_camera.delete(0, "end")
        self.ent_camera.insert(0, str(achadas[0]["indice"]))
        messagebox.showinfo("Lyra Live", f"Encontrei:\n\n{texto}\n\nUsando a primeira.")

    def _conferir_chave(self) -> None:
        chave = self.ent_chave.get().strip()
        if not chave:
            self.rot_chave.configure(text="Sem chave: dá para usar só a câmera virtual.",
                                     text_color="#94a3b8")
            return
        vale, motivo = YT.validar_chave(chave)
        self.rot_chave.configure(text=motivo, text_color="#22c55e" if vale else "#eab308")

    def _testar_ia(self) -> None:
        cliente = ClienteQwen(self.ent_ia.get().strip(), self.sel_modelo.get().strip())
        if not cliente.disponivel():
            messagebox.showwarning("Lyra Live", cliente.instrucao_de_instalacao())
            return
        modelos = cliente.modelos()
        tem = cliente.modelo in modelos
        messagebox.showinfo(
            "Lyra Live",
            f"Servidor respondendo em {cliente.endereco}.\n\n"
            + (f"O modelo {cliente.modelo} está instalado." if tem
               else f"Mas falta o modelo. Rode:\n    ollama pull {cliente.modelo}")
            + (f"\n\nDisponíveis: {', '.join(modelos[:6])}" if modelos else ""))

    def _analisar_agora(self) -> None:
        if not self.supervisor:
            messagebox.showwarning("Lyra Live", "Ligue a câmera primeiro.")
            return
        # numa thread: consultar o modelo leva segundos e não pode congelar a janela
        threading.Thread(target=self.supervisor.avaliar_agora, daemon=True).start()

    # -------------------------------------------------------------- ligar
    def _coletar_perfil(self) -> None:
        cam = self.perfil.camera
        cam.origem = self.ent_camera.get().strip() or "0"
        try:
            larg, _, alt = self.sel_resolucao.get().partition("x")
            cam.largura, cam.altura = int(larg), int(alt)
            cam.fps = int(self.sel_fps.get())
        except Exception:
            pass
        self.perfil.transmitir = bool(self.var_transmitir.get())
        self.perfil.camera_virtual = bool(self.var_virtual.get())
        self.perfil.saida.chave = self.ent_chave.get().strip()
        self.perfil.saida.codificador = self.sel_codificador.get()
        self.perfil.saida.audio_dispositivo = self.ent_audio.get().strip()
        self.perfil.ia_ativa = bool(self.var_ia.get())
        self.perfil.ia_modelo = self.sel_modelo.get().strip()
        self.perfil.ia_endereco = self.ent_ia.get().strip()

    def _alternar(self) -> None:
        if self.esteira and self.esteira.rodando:
            self._desligar()
        else:
            self._ligar()

    def _ligar(self) -> None:
        self._coletar_perfil()
        if self.perfil.transmitir:
            vale, motivo = YT.validar_chave(self.perfil.saida.chave)
            if not vale:
                messagebox.showerror("Lyra Live", f"Não dá para transmitir.\n\n{motivo}")
                return
        self.esteira = Pipeline(self.perfil, ao_avisar=self._registrar_aviso)
        try:
            self.esteira.iniciar()
        except Exception as e:
            self.esteira = None
            messagebox.showerror("Lyra Live", f"Não consegui iniciar:\n\n{e}")
            return
        self.supervisor = Supervisor(
            self.esteira.estado,
            cliente=ClienteQwen(self.perfil.ia_endereco, self.perfil.ia_modelo),
            intervalo_s=self.perfil.ia_intervalo_s, usar_ia=self.perfil.ia_ativa)
        self.supervisor.iniciar()
        self.bt_ligar.configure(text="DESLIGAR", fg_color="#dc2626")

    def _desligar(self) -> None:
        if self.supervisor:
            self.supervisor.parar()
            self.supervisor = None
        if self.esteira:
            self.esteira.parar()
            self.esteira = None
        self.bt_ligar.configure(text="LIGAR CÂMERA", fg_color="#16a34a")
        self.rot_estado.configure(text="parada", text_color=CORES["off"])

    def _registrar_aviso(self, texto: str) -> None:
        self._ultimo_aviso = texto

    def _salvar_perfil(self) -> None:
        self._coletar_perfil()
        ok = CFG.salvar(self.perfil)
        CFG.salvar_chave(self.perfil.saida.chave)
        messagebox.showinfo("Lyra Live",
                            f"Perfil salvo em {CFG.pasta_dados()}" if ok
                            else "Não consegui salvar o perfil.")

    # -------------------------------------------------------------- laços
    def _laco_previa(self) -> None:
        """Redesenha a prévia. Roda sempre, mesmo com a câmera desligada."""
        try:
            if self.esteira and Image is not None:
                quadro = self.esteira.preview()
                if quadro is not None:
                    self._desenhar(quadro)
        except Exception:
            pass                      # prévia é enfeite: nunca derruba a janela
        self.after(33, self._laco_previa)

    def _desenhar(self, quadro: np.ndarray) -> None:
        alvo_l = max(320, self.tela.winfo_width() - 16)
        alvo_a = max(180, self.tela.winfo_height() - 16)
        alt, larg = quadro.shape[:2]
        escala = min(alvo_l / larg, alvo_a / alt)
        nl, na = max(1, int(larg * escala)), max(1, int(alt * escala))
        img = Image.fromarray(quadro[:, :, ::-1]).resize((nl, na))
        self._foto = ImageTk.PhotoImage(img)
        self.tela.configure(image=self._foto, text="")

    def _laco_estado(self) -> None:
        try:
            if self.esteira and self.esteira.rodando:
                e = self.esteira.estado()
                destino = ("no ar no YouTube" if e["transmitindo"]
                           else "câmera virtual" if e["camera_virtual"] else "só prévia")
                self.rot_estado.configure(text=destino, text_color=CORES["ok"])
                self.rot_metricas.configure(
                    text=f"{e['fps_saida']:5.1f} fps   filtro {e['ms_processamento']:5.1f} ms "
                         f"(orçamento {e['orcamento_ms']:.0f})   descartes {e['descartes']}   "
                         f"recorte {e['segmentador']}   {self._ultimo_aviso[:40]}")
                self.rot_segmentador.configure(text=e.get("aviso_segmentador", ""))
                if self.supervisor:
                    boletim = self.supervisor.ultimo()
                    if boletim is not None:
                        self.rot_estado.configure(
                            text=f"{destino} — {boletim.saude}",
                            text_color=CORES.get(boletim.saude, CORES["ok"]))
                        self.txt_ia.delete("1.0", "end")
                        self.txt_ia.insert("1.0", self.supervisor.texto_para_painel())
        except Exception:
            pass
        self.after(1000, self._laco_estado)

    def _ao_fechar(self) -> None:
        try:
            self._desligar()
        finally:
            self.destroy()


def main() -> int:
    PainelLyra().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
