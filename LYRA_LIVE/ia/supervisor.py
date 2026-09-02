# -*- coding: utf-8 -*-
"""
A IA supervisora: acompanha a live do começo ao fim e avisa quando algo muda.

O CICLO
-------
A cada intervalo (20 s por padrão) ela pega um instantâneo das métricas, passa
pelas regras de `diagnostico.py` e monta um boletim. Quando há problema — e só
quando há — ela pede ao Qwen para transformar os achados numa frase direta.

QUANDO ELA CHAMA O MODELO, E QUANDO NÃO CHAMA
---------------------------------------------
Não a cada ciclo. O modelo é chamado quando o CONJUNTO de problemas muda, ou
quando os mesmos problemas persistem por alguns minutos. Uma live de duas horas
com um problema constante não precisa de cento e vinte parágrafos dizendo a
mesma coisa — e cada chamada come CPU que a transmissão está usando.

Live saudável não chama o modelo nenhuma vez.

O TEXTO DA IA NUNCA SUBSTITUI OS FATOS
--------------------------------------
O boletim carrega os dois: `texto_regras`, que é o achado medido com o número
que o gerou, e `texto_ia`, que é a redação por cima. O painel mostra os fatos em
cima e a leitura da IA embaixo, identificada. Assim, se o modelo escrever
bobagem, dá para ver na hora que o número diz outra coisa — e nenhuma decisão
depende só da frase dele.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .diagnostico import Achado, diagnosticar, resumo_texto, saude_geral
from .qwen import ClienteQwen

INSTRUCAO = """Você acompanha uma transmissão ao vivo e fala com quem está transmitindo.

Recebe a lista de problemas JÁ DETECTADOS pelo sistema de medição.

Regras:
- Responda em português do Brasil, no máximo 2 frases curtas.
- Fale só dos problemas da lista. Não invente outros e não invente números.
- Comece pelo mais grave e diga o que fazer AGORA, em linguagem simples.
- Nada de introdução, nada de lista, nada de markdown. Só as frases."""

SEGUNDOS_PARA_REPETIR = 180.0      # mesmo problema: só volta a comentar depois disto


@dataclass
class Boletim:
    momento: float
    saude: str
    achados: List[Achado] = field(default_factory=list)
    texto_regras: str = ""
    texto_ia: str = ""
    modelo: str = ""
    ia_consultada: bool = False

    @property
    def hora(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.momento))

    def como_dicionario(self) -> Dict:
        return {
            "hora": self.hora,
            "saude": self.saude,
            "achados": [a.como_dicionario() for a in self.achados],
            "texto_regras": self.texto_regras,
            "texto_ia": self.texto_ia,
            "modelo": self.modelo,
            "ia_consultada": self.ia_consultada,
        }


class Supervisor:
    """Roda em thread própria e nunca atrapalha a transmissão."""

    def __init__(self, ler_estado: Callable[[], Dict],
                 cliente: Optional[ClienteQwen] = None,
                 intervalo_s: int = 20,
                 ao_boletim: Optional[Callable[[Boletim], None]] = None,
                 usar_ia: bool = True):
        self._ler_estado = ler_estado
        self.cliente = cliente or ClienteQwen()
        self.intervalo_s = max(5, int(intervalo_s))
        self._ao_boletim = ao_boletim or (lambda _: None)
        self.usar_ia = bool(usar_ia)

        self._parar = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._trava = threading.Lock()
        self._ultimo: Optional[Boletim] = None
        self._historico: List[Boletim] = []
        self._codigos_comentados: tuple = ()
        self._momento_comentario = 0.0
        self.ia_disponivel: Optional[bool] = None

    # -- ciclo de vida ------------------------------------------------------
    def iniciar(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="supervisor", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def _tique_seguro(self) -> Optional[Boletim]:
        """Um ciclo que nunca levanta. É o que o laço de fundo executa.

        Supervisor que derruba a live que ele deveria vigiar seria a pior ironia
        possível — então o erro morre aqui. Separado de `avaliar_agora` porque o
        botão "Analisar agora" QUER ver a falha, e o laço de fundo não pode nem
        parar por causa dela.
        """
        try:
            return self.avaliar_agora()
        except Exception:
            return None

    def _laco(self) -> None:
        while not self._parar.is_set():
            self._tique_seguro()
            self._parar.wait(self.intervalo_s)

    # -- avaliação ----------------------------------------------------------
    def _deve_consultar_ia(self, achados: List[Achado], saude: str) -> bool:
        """Chama o modelo só quando há novidade — ou quando o problema insiste."""
        if not self.usar_ia or saude == "ok" or not achados:
            return False
        codigos = tuple(a.codigo for a in achados)
        if codigos != self._codigos_comentados:
            return True
        return (time.time() - self._momento_comentario) >= SEGUNDOS_PARA_REPETIR

    def avaliar_agora(self) -> Boletim:
        """Um ciclo completo, de forma síncrona. O botão 'Analisar' chama isto."""
        estado = self._ler_estado() or {}
        achados = diagnosticar(estado)
        saude = saude_geral(achados)
        boletim = Boletim(momento=time.time(), saude=saude, achados=achados,
                          texto_regras=resumo_texto(achados),
                          modelo=self.cliente.modelo)

        if self._deve_consultar_ia(achados, saude):
            self.ia_disponivel = self.cliente.disponivel()
            if self.ia_disponivel:
                resposta = self.cliente.perguntar(INSTRUCAO, self._pergunta(achados, estado))
                if resposta:
                    boletim.texto_ia = resposta
                    boletim.ia_consultada = True
                    self._codigos_comentados = tuple(a.codigo for a in achados)
                    self._momento_comentario = time.time()

        with self._trava:
            self._ultimo = boletim
            self._historico.append(boletim)
            if len(self._historico) > 200:
                del self._historico[:-200]
        try:
            self._ao_boletim(boletim)
        except Exception:
            pass
        return boletim

    @staticmethod
    def _pergunta(achados: List[Achado], estado: Dict) -> str:
        """O que o modelo vê. Só os achados prontos e o contexto mínimo."""
        linhas = [f"Transmissão em {estado.get('resolucao', '?')} "
                  f"a {estado.get('fps_alvo', '?')} quadros por segundo.",
                  "", "Problemas detectados pela medição:"]
        for a in achados[:6]:
            linhas.append(f"- ({a.gravidade}) {a.titulo}: {a.detalhe}")
        return "\n".join(linhas)

    # -- leitura ------------------------------------------------------------
    def ultimo(self) -> Optional[Boletim]:
        with self._trava:
            return self._ultimo

    def historico(self, quantos: int = 20) -> List[Boletim]:
        with self._trava:
            return list(self._historico[-quantos:])

    def texto_para_painel(self) -> str:
        """O bloco que o painel mostra: fatos em cima, leitura da IA embaixo."""
        boletim = self.ultimo()
        if boletim is None:
            return "A IA supervisora ainda não fez a primeira leitura."
        partes = [f"[{boletim.hora}] " + {
            "ok": "Tudo certo.", "atencao": "Atenção.", "grave": "Problema sério.",
        }.get(boletim.saude, ""), "", boletim.texto_regras]
        if boletim.texto_ia:
            partes += ["", f"Leitura da IA ({boletim.modelo}):", boletim.texto_ia]
        elif boletim.saude != "ok" and self.usar_ia and self.ia_disponivel is False:
            partes += ["", "(IA sem modelo local — mostrando só a medição. "
                       + self.cliente.instrucao_de_instalacao().split("\n")[0] + ")"]
        return "\n".join(partes)
