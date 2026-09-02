# -*- coding: utf-8 -*-
"""
O cliente do Qwen leve — local, pequeno e opcional.

QUAL MODELO
-----------
O padrão é `qwen2.5:0.5b`: meio bilhão de parâmetros, ~400 MB, roda em CPU sem
GPU nenhuma e responde em um ou dois segundos. É deliberadamente pequeno. A
tarefa dele aqui não é raciocinar sobre a live — as regras em `diagnostico.py`
já fizeram isso — é transformar achados prontos em uma frase que a pessoa lê
sem precisar entender de codec. Para isso, meio bilhão de parâmetros sobra.

Quem quiser mais qualidade de texto troca no painel por `qwen2.5:1.5b` ou
`qwen3:0.6b`. Nada no software depende do tamanho do modelo.

COMO INSTALAR (a forma mais simples)
------------------------------------
    ollama pull qwen2.5:0.5b

Com o Ollama rodando, este cliente acha sozinho em 127.0.0.1:11434. Também
funciona com qualquer servidor que fale a API da OpenAI — llama.cpp, LM Studio,
vLLM — bastando apontar o endereço no painel.

O QUE ACONTECE QUANDO NÃO TEM MODELO
------------------------------------
Nada quebra. `disponivel()` responde False, `perguntar()` devolve None, e o
supervisor mostra o boletim das regras sem o texto da IA. Um modelo de
linguagem ausente não pode derrubar uma transmissão ao vivo, e o acompanhamento
continua inteiro sem ele — a IA aqui é a camada de redação, não a de medição.
"""
from __future__ import annotations

from typing import List, Optional

try:
    import requests
except Exception:  # pragma: no cover - depende da máquina
    requests = None

MODELO_PADRAO = "qwen2.5:0.5b"
ENDERECO_PADRAO = "http://127.0.0.1:11434"
SUGESTOES = ("qwen2.5:0.5b", "qwen3:0.6b", "qwen2.5:1.5b", "qwen2.5:3b")


class ClienteQwen:
    """Conversa com um Qwen local. Nunca levanta exceção para fora."""

    def __init__(self, endereco: str = ENDERECO_PADRAO, modelo: str = MODELO_PADRAO,
                 timeout: float = 20.0, protocolo: str = "auto"):
        self.endereco = (endereco or ENDERECO_PADRAO).rstrip("/")
        self.modelo = modelo or MODELO_PADRAO
        self.timeout = float(timeout)
        self.protocolo = protocolo          # auto | ollama | openai
        self.ultimo_erro = ""
        self._detectado: Optional[str] = None

    # -- descoberta ---------------------------------------------------------
    def _detectar(self) -> Optional[str]:
        """Descobre se do outro lado tem um Ollama ou uma API estilo OpenAI."""
        if self.protocolo in ("ollama", "openai"):
            return self.protocolo
        if self._detectado:
            return self._detectado
        if requests is None:
            self.ultimo_erro = "A biblioteca requests não está instalada."
            return None
        for nome, caminho in (("ollama", "/api/tags"), ("openai", "/v1/models")):
            try:
                r = requests.get(self.endereco + caminho, timeout=3.0)
                if r.status_code == 200:
                    self._detectado = nome
                    return nome
            except Exception as e:
                self.ultimo_erro = str(e)
        return None

    def disponivel(self) -> bool:
        return self._detectar() is not None

    def modelos(self) -> List[str]:
        """Os modelos que o servidor tem. Serve para o painel oferecer a lista."""
        proto = self._detectar()
        if proto is None or requests is None:
            return []
        try:
            if proto == "ollama":
                r = requests.get(self.endereco + "/api/tags", timeout=5.0)
                return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]
            r = requests.get(self.endereco + "/v1/models", timeout=5.0)
            return [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
        except Exception as e:
            self.ultimo_erro = str(e)
            return []

    def instrucao_de_instalacao(self) -> str:
        return (f"Para ligar a IA supervisora, instale o Ollama e rode:\n"
                f"    ollama pull {self.modelo}\n"
                f"São cerca de 400 MB e roda no processador, sem placa de vídeo.")

    # -- a pergunta ---------------------------------------------------------
    def perguntar(self, sistema: str, usuario: str, max_tokens: int = 220,
                  temperatura: float = 0.3) -> Optional[str]:
        """Manda a pergunta e devolve o texto, ou None se não deu.

        Temperatura baixa de propósito: aqui não se quer criatividade, se quer a
        mesma leitura para o mesmo problema. Um supervisor que descreve a mesma
        falha de um jeito diferente a cada vez é impossível de acompanhar.
        """
        proto = self._detectar()
        if proto is None or requests is None:
            return None
        try:
            if proto == "ollama":
                r = requests.post(
                    self.endereco + "/api/chat",
                    json={"model": self.modelo, "stream": False,
                          "messages": [{"role": "system", "content": sistema},
                                       {"role": "user", "content": usuario}],
                          "options": {"temperature": temperatura,
                                      "num_predict": int(max_tokens)}},
                    timeout=self.timeout)
                r.raise_for_status()
                texto = (r.json().get("message") or {}).get("content", "")
            else:
                r = requests.post(
                    self.endereco + "/v1/chat/completions",
                    json={"model": self.modelo, "temperature": temperatura,
                          "max_tokens": int(max_tokens),
                          "messages": [{"role": "system", "content": sistema},
                                       {"role": "user", "content": usuario}]},
                    timeout=self.timeout)
                r.raise_for_status()
                escolhas = r.json().get("choices") or []
                texto = (escolhas[0].get("message") or {}).get("content", "") if escolhas else ""
            self.ultimo_erro = ""
            return limpar_resposta(texto)
        except Exception as e:
            self.ultimo_erro = str(e)
            return None


def limpar_resposta(texto: str, limite: int = 700) -> Optional[str]:
    """Tira cerca de código, marcação e sobra. Modelo pequeno enfeita demais.

    Um 0.5B às vezes devolve a resposta dentro de ```markdown, às vezes repete a
    pergunta antes, às vezes emenda um parágrafo a mais. Nada disso pode ir para
    o painel do jeito que veio.
    """
    if not texto:
        return None
    limpo = str(texto).strip()
    if "```" in limpo:
        partes = [p for p in limpo.split("```") if p.strip()]
        # blocos ímpares são o conteúdo cercado; fica o maior pedaço de prosa
        limpo = max(partes, key=len).strip() if partes else limpo
        if limpo.split("\n", 1)[0].strip().lower() in ("markdown", "texto", "text", "json"):
            limpo = limpo.split("\n", 1)[-1].strip()
    limpo = limpo.replace("**", "").replace("##", "").strip()
    if len(limpo) > limite:
        corte = limpo[:limite]
        ponto = corte.rfind(".")
        limpo = (corte[:ponto + 1] if ponto > limite * 0.4 else corte).strip() + " […]"
    return limpo or None
