# -*- coding: utf-8 -*-
"""
EXPLICADOR — o consenso dito em português.

O QUE ELE DISSE
---------------
    "não entendo o consenso das ias"

E ele tem razão. A tela mostrava isto:

    [Consenso/votos] 10 ← 1 teorias + 4 padrões (peso 8.555)
    [Consenso/independência] 9 fontes valendo 3.0 independentes
    [Hipóteses] ['ESTAT', 'ANOMALIA', 'SETOR', 'FINAIS', 'HEURISTICA']

Nada ali diz por que o 10 foi escolhido. "Peso 8.555" é número meu, não é
razão. "ESTAT" e "ANOMALIA" são nomes de variável, não explicação. Quem lê
isso fica sabendo que houve uma conta, não o que a conta viu.

Sem entender o consenso, ele não consegue julgar se o software está errando
por azar ou por defeito -- e julgar isso é o trabalho DELE, não meu. Uma tela
que esconde o raciocínio transfere a decisão para mim por omissão.

O QUE ESTE ARQUIVO FAZ
----------------------
Traduz cada fonte para uma frase que diga o que ela viu, e monta a explicação
de cada número escolhido:

    21   três fontes concordaram (valendo 2 vozes de verdade)
         • está há 40 giros sem sair
         • final 1, da família 0-1-3-6 que está saindo mais
         • fica ao lado do 2 na roda, que acabou de sair

Não é enfeite: é a diferença entre um palpite e um palpite que se pode
conferir. Quando o software errar, ele vai poder olhar a razão e dizer "essa
teoria é boba" -- e aí a correção vem dele, que conhece a mesa.
"""
from __future__ import annotations

from typing import Any, Dict, List

# O que cada fonte olha, dito como se explica para uma pessoa.
# A chave é o nome interno; o valor é a frase, sem jargão.
FONTES = {
    "ESTAT": "sai com frequência ou está atrasado nas contas gerais",
    "GAP_CICLO": "está há mais tempo sem sair do que costuma demorar",
    "ANOMALIA": "está muito além do intervalo em que costuma voltar",
    "SETOR": "fica no setor da roda que está saindo mais",
    "RODA_CT": "está atrasado em relação ao próprio ritmo",
    "FINAIS": "tem o final que está aparecendo mais",
    "ATRASO": "está há muito tempo sem sair",
    "HEURISTICA": "veio das regras rápidas da mesa",
    "LSTM": "a rede neural apontou",
    "ANTI_12": "os números baixos estão saindo demais e isso costuma virar",
    "DESCOBERTA": "uma teoria descoberta pela academia apontou",
    "SEQ_MARKOV": "costuma vir depois do que acabou de sair",
    "REGRA_OPERADOR": "é a sua regra: família do final na faixa quente",
    "REGRA_OPERADOR_ESTREITA": "sua regra, na versão mais fechada",
    "REGRA_TRANSICAO": "é a sua tabela: depois deste número costuma vir este",
    "REGRA_FAMILIA_QUENTE": "está na família de finais que mais aparece agora",
    "CT_FREQUENTE": "é o que mais está saindo agora",
    "CT_TRANSICAO": "costuma vir depois do símbolo que acabou de sair",
    "GAP": "está atrasado",
    "VIZINHOS": "fica ao lado, na roda, de um que acabou de sair",
    "FAMILIA": "está na família de finais que você ensinou",
    "REPETE": "vem repetindo em rodadas seguidas",
    "INTENSIDADE": "é o que carrega os maiores multiplicadores",
    "QUENTE": "é o mais sorteado ultimamente",
    "PAGOU": "é onde o top slot casou com a roda",
    "PUXA": "é o que este giro costuma puxar",
    "RITMO": "a seca passou do intervalo típico",
}


# Fontes que devolvem um GRUPO inteiro (metade da mesa, uma dúzia, uma cor).
# Estar dentro de um grupo desses não é ter sido escolhido -- e a tela precisa
# dizer isso, senão preenchimento passa por decisão.
GENERICAS = {"SETOR", "FINAIS", "ANTI_12", "REGRA_FAMILIA_QUENTE", "FAMILIA"}


MULT = {
    "QUENTE": "vem sendo sorteado para multiplicador ultimamente",
    "ATRASO": "está há mais tempo sem ser sorteado para multiplicador",
    "VIZINHOS": "fica ao lado, na roda, dos últimos sorteados para multiplicador",
    "FAMILIA": "está na família de finais dos últimos multiplicados",
    "REPETE": "vem repetindo como sorteado em rodadas seguidas",
    "SETOR": "está no setor da roda onde os multiplicadores se concentram",
    "INTENSIDADE": "é quem carrega os maiores multiplicadores",
    "PAGOU": "é onde o top slot casou com a roda e pagou",
    "PUXA": "é o que este giro costuma puxar para o top slot",
    "RITMO": "a seca de multiplicador passou do intervalo típico",
}


def frase_da_fonte(nome: str) -> str:
    """A frase desta fonte. Nomes de teoria da academia viram texto genérico."""
    n = str(nome or "").strip()
    if n.startswith("C0") or n.startswith("C1"):
        # as praticas de previsao do compendio dele: a frase vem do proprio
        # modulo, para a tela nao repetir o que o codigo ja sabe dizer
        try:
            from academia_autonoma.previsores_compendio import descricao
            d = descricao(n)
            if d:
                return f"(ficha {n[1:4]} do seu compêndio) {d}"
        except Exception:
            pass
    if n.startswith("MULT_"):
        # as sete IAs de multiplicador, que agora votam na escolha
        base = n[len("MULT_"):]
        return "multiplicador — " + MULT.get(base, f"a IA {base} apontou")
    if n in FONTES:
        return FONTES[n]
    if n.startswith("ACADEMIA_") or n.startswith("TEORIA:"):
        return "uma teoria que a academia validou apontou este número"
    if n.startswith("LAB_") or n.startswith("ESTUDO_"):
        return "um estudo do laboratório apontou este número"
    return f"a fonte {n} apontou"


def explicar(escolhidos: List[Any], fontes_por_numero: Dict[str, List[str]],
             n_efetivo: Dict[str, Any] = None, limite_por_numero: int = 3,
             limite_numeros: int = 6) -> str:
    """Por que cada número entrou, em português.

    `fontes_por_numero` é {numero: [nomes das fontes que votaram nele]} — o
    mesmo dicionário que a autópsia já usa.
    """
    if not escolhidos:
        return ""
    L = ["POR QUE ESTES NÚMEROS"]
    for n in list(escolhidos)[:limite_numeros]:
        chave = str(n).strip()
        quem = [f for f in (fontes_por_numero or {}).get(chave, []) if f]
        if not quem:
            L.append(f"   {chave:<4} COMPLETANDO a lista — nenhuma fonte "
                     f"apontou este número")
            continue
        if len(quem) == 1 and quem[0] in GENERICAS:
            # entrou dentro de um grupo grande (cor, dúzia, metade), sem
            # ninguém apontar ELE. Dizer "uma fonte concordou" aqui seria
            # vender preenchimento como escolha.
            L.append(f"   {chave:<4} COMPLETANDO — só está dentro de um grupo "
                     f"grande ({frase_da_fonte(quem[0])})")
            continue
        L.append(f"   {chave:<4} {len(quem)} "
                 + ("fonte concordou" if len(quem) == 1 else "fontes concordaram"))
        vistas = []
        for f in quem[:limite_por_numero]:
            fr = frase_da_fonte(f)
            if fr not in vistas:
                vistas.append(fr)
                L.append(f"          • {fr}")
        if len(quem) > limite_por_numero:
            L.append(f"          • e mais {len(quem) - limite_por_numero}")
    if len(escolhidos) > limite_numeros:
        L.append(f"   (+{len(escolhidos) - limite_numeros} números com menos apoio)")
    # a ficha 226 dita de um jeito que se entende
    if n_efetivo and n_efetivo.get("nominal"):
        inf = float(n_efetivo.get("inflacao") or 1.0)
        if inf >= 1.25:
            L.append("")
            L.append(f"   Atenção: votaram {n_efetivo['nominal']} fontes, mas "
                     f"muitas olham a MESMA coisa —")
            L.append(f"   na prática valem {n_efetivo['efetivo']:.0f} opiniões "
                     f"independentes. Concordância entre")
            L.append("   fontes parecidas não é confirmação, é repetição.")
    return "\n".join(L)


def explicar_vazio(motivos: List[str] = None) -> str:
    """Quando não há sinal, dizer por quê também é resposta."""
    L = ["SEM SINAL AGORA — e isso é resposta, não falha",
         "   O software não tenta adivinhar todo giro: ele espera as fontes",
         "   concordarem. Quando nenhuma concordância aparece, ficar quieto",
         "   vale mais que inventar número."]
    for m in (motivos or [])[:3]:
        L.append(f"   • {m}")
    return "\n".join(L)
