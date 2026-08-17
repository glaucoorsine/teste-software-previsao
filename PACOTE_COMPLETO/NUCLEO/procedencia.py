# -*- coding: utf-8 -*-
"""
PROCEDÊNCIA — o portão que torna a ligação com os PDFs falsificável.

O PROBLEMA COM "ESTÁ LIGADO AOS PDFS"
─────────────────────────────────────
Ler os tratados e montar um índice não prova nada por si só. Eu poderia ler os
PDFs, montar um índice bonito, e continuar calculando pela minha transcrição —
com o índice ali do lado, decorativo. Foi exatamente a crítica dele sobre o
outro pacote: `_distill_from_pdfs()` que não destilava nada.

Uma alegação só vale se der para quebrá-la. Então:

    cada família do motor declara QUAL ficha do PDF ela implementa,
    e se essa ficha não existir no índice, a família NÃO RODA.

Isso é testável destruindo: tire o PDF da pasta, e as famílias emudecem. Troque
um byte do PDF, e o índice é reconstruído. Renomeie uma família, e ela cai.
Nenhum desses caminhos deixa a conta antiga rodar por trás — e é essa a
diferença entre ligação e enfeite.

E O QUE ACONTECE QUANDO O PDF NÃO ESTÁ LÁ
─────────────────────────────────────────
A tela fica sem número. Isso vai parecer defeito, e não é: é o software dizendo
que não tem autoridade para calcular aquilo. O contrário — cair para a
transcrição — é o que ele passou o projeto inteiro me cobrando por fazer.

O silêncio aqui é o mesmo silêncio que a Régua dele exige: SEM EVIDÊNCIA é
resultado legítimo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import indice_tratados as IT

# ─────────────────────────────────────────────────────────────────────────────
# O CONTRATO: família do motor → ficha do tratado.
#
# À esquerda o nome que o código usa. À direita a família como o PDF a escreve,
# e a fonte. Quem não está aqui não depende de PDF (são as minhas heurísticas, e
# elas continuam declaradas como minhas — ver `SEM_TRATADO`).
#
# Este mapa é a parte conferível: pega-se a família, acha-se a ficha no índice,
# lê-se a fórmula que o PDF traz, e compara-se com o que o código faz. Dá para
# me pegar errando, o que antes não dava.
CONTRATO: Dict[str, Tuple[str, str]] = {
    # as doze inteligências do Livro, por família de formulação
    "IA01_TEMPO":          ("F01", "livro"),
    "IA02_RECENCIA":       ("F02", "livro"),
    "IA03_MOTIVOS":        ("F03", "livro"),
    "IA04_TRANSICAO":      ("F04", "livro"),
    "IA05_VIZINHANCA":     ("F05", "livro"),
    "IA06_RAJADA":         ("F06", "livro"),
    "IA07_REGIME":         ("F07", "livro"),
    "IA08_GEOMETRIA":      ("F08", "livro"),
    "IA09_SURPRESA":       ("F09", "livro"),
    "IA10_INTENSIDADE":    ("F10", "livro"),
    "IA11_FAMILIARIDADE":  ("F11", "livro"),
    "IA12_AGREGACAO":      ("F12", "livro"),
}

# Heurísticas minhas, que NÃO vêm de tratado. Ficam declaradas para que ninguém
# — inclusive eu, daqui a três meses — as confunda com teoria dele.
SEM_TRATADO = {
    "ESTAT", "ANOMALIA", "SETOR", "FINAIS", "HEURISTICA", "GAP",
    "LSTM", "DESCOBERTA", "SOMBRA",
}


class Autoridade:
    """Quem pode falar, e com base em qual página de qual arquivo."""

    def __init__(self, dados: Optional[Dict[str, Any]] = None):
        self.dados = dados if dados is not None else IT.carregar()
        self._cache: Dict[str, Optional[Dict[str, Any]]] = {}

    # -- consulta -----------------------------------------------------------
    def ficha(self, nome_motor: str,
              mesa: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """A ficha do tratado que autoriza esta família, ou None."""
        chave = f"{nome_motor}|{mesa or '-'}"
        if chave in self._cache:
            return self._cache[chave]
        alvo = CONTRATO.get(nome_motor)
        f = None
        if alvo:
            familia, fonte = alvo
            candidatas = [x for x in IT.por_familia(self.dados, familia, mesa)
                          if x.get("fonte") == fonte and x.get("formula")]
            # prefere a ficha da MESA pedida; depois qualquer uma da família
            f = next((x for x in candidatas if x.get("mesa") == mesa), None) \
                or (candidatas[0] if candidatas else None)
        self._cache[chave] = f
        return f

    def autorizada(self, nome_motor: str, mesa: Optional[str] = None) -> bool:
        """Esta família pode rodar?

        Quem não está no contrato é heurística minha e continua rodando — mas
        rotulada. Quem está no contrato PRECISA da ficha.
        """
        if nome_motor not in CONTRATO:
            return True
        return self.ficha(nome_motor, mesa) is not None

    def motivo(self, nome_motor: str, mesa: Optional[str] = None) -> str:
        """Por que ela fala, ou por que se cala — em português, para o log."""
        if nome_motor not in CONTRATO:
            base = "heurística do software (não é teoria dos PDFs)"
            return base
        f = self.ficha(nome_motor, mesa)
        if f is None:
            fam, fonte = CONTRATO[nome_motor]
            if not IT.pdfs_presentes():
                return (f"calada: {fam} não pode ser conferida — não há PDF em "
                        f"tratados/")
            return (f"calada: nenhuma ficha {fam} com fórmula legível no "
                    f"{fonte}")
        return (f"{f['familia']}/{f.get('ia') or '-'} · {f['arquivo']} "
                f"p.{f['pagina']} · sha {str(f.get('sha256'))[:10]}")

    # -- relatório ----------------------------------------------------------
    def placar(self, mesa: Optional[str] = None) -> Dict[str, Any]:
        vivas, mudas = [], []
        for nome in CONTRATO:
            (vivas if self.autorizada(nome, mesa) else mudas).append(nome)
        return {
            "com_tratado": len(CONTRATO),
            "autorizadas": vivas, "caladas": mudas,
            "pdfs": [d["arquivo"] for d in (self.dados.get("documentos") or [])],
            "fichas": self.dados.get("total_fichas", 0),
            "fichas_com_formula": self.dados.get("fichas_com_formula", 0),
        }

    def linhas(self, mesa: Optional[str] = None) -> List[str]:
        p = self.placar(mesa)
        L = [f"[Procedência] {len(p['autorizadas'])}/{p['com_tratado']} "
             f"famílias autorizadas pelos tratados "
             f"({p['fichas_com_formula']} fórmulas lidas de "
             f"{len(p['pdfs'])} PDF(s))"]
        if p["caladas"]:
            L.append(f"[Procedência] caladas por falta de ficha: "
                     f"{', '.join(p['caladas'][:6])}")
        if not p["pdfs"]:
            L.append("[Procedência] tratados/ está vazia — as famílias do "
                     "Livro não rodam. Isto é o portão funcionando, não erro.")
        return L


_UNICA: Optional[Autoridade] = None


def autoridade(recarregar: bool = False) -> Autoridade:
    """Uma instância por processo: o índice é lido do disco, não a cada giro."""
    global _UNICA
    if _UNICA is None or recarregar:
        _UNICA = Autoridade()
    return _UNICA
