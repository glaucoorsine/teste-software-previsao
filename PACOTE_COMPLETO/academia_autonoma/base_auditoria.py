# -*- coding: utf-8 -*-
"""
BASE DE AUDITORIA — os cinco estudos dele viram material de trabalho.

DE ONDE VEIO
------------
Glauco mandou cinco auditorias retrospectivas que ele mesmo encomendou, uma por
mesa, e pediu que servissem "de base aos caçadores, descobridores, entendedores
de padrões, familiaridade, teorias e afins":

    MEGA FIRE      197 resultados (4 capturas sobrepostas), 16 multiplicadores
    LIGHTNING      162 resultados (1 captura 18x9), 12 destaques
    IMMERSIVE      162 resultados (1 captura 18x9), 0 destaques
    CRAZY TIME     100 resultados, 26 ícones
    CRAZY TIME A   100 resultados, 15 ícones

Cada documento cataloga até 56 famílias de hipótese e diz, para aquela amostra,
o que cada família mostrou. Isso é exatamente o que faltava para os caçadores:
até aqui eles procuravam no escuro, sem saber o que já tinha sido procurado.

POR QUE ISSO MUDA O TRABALHO DELES
----------------------------------
Um caçador que "descobre" hoje que o Lightning tem 77 vermelhos e 80 pretos não
descobriu nada — isso já foi medido, deu p=0,873, e está escrito. O valor da
base é negativo e positivo ao mesmo tempo:

    o que JÁ FOI OLHADO e deu nada     não vale gastar tentativa de novo, e se
                                       vier "achado" ali, o limiar tem que ser
                                       muito mais duro do que o de sempre
    o que ficou EM ABERTO              é onde a busca rende: as famílias
                                       marcadas exploratória / requer
                                       pré-registro nunca foram concluídas
    o que é CONTROLE NEGATIVO          tem que dar nada. Se der, o defeito é do
                                       caçador, não da mesa
    o RETRATO da mesa                  a referência para comparar: entropia,
                                       equilíbrios, taxa de destaque medidos

O LIMIAR QUE O PRÓPRIO ESTUDO EXIGE
-----------------------------------
A família H52 escreve a conta: 56 hipóteses testadas ⇒ limiar 0,05/56 ≈ 0,00089.
É por isso que ALFA_MULTIPLO existe aqui e não é 0,05. E a H53 diz a coisa mais
importante do documento inteiro: essas capturas são DESCOBERTA, não prova. Nada
medido nelas vale como validação — vale como hipótese a ser testada adiante.

OS DOIS ÚNICOS SINAIS ABERTOS
-----------------------------
De 56 famílias × 5 mesas, dois pontos ficaram abaixo de 0,05 (e nenhum abaixo
de 0,00089 — ou seja, nenhum sobrevive à correção, e nenhum é prova):

    LIGHTNING H07 paridade      60 ímpares × 97 pares em 157, p=0,004
    CRAZY TIME H28 regime       taxa de ícone muda entre quartis, p=0,036

Estão registrados aqui com horizonte e critério congelados, como o documento
exige, para poderem ser medidos adiante em dado que não os gerou.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --------------------------------------------------------------- constantes
# H52 - Correção de múltiplos testes: "limiar conservador aproximado 0,05/56".
N_FAMILIAS = 56
ALFA_MULTIPLO = round(0.05 / N_FAMILIAS, 5)      # 0.00089

# H53 - Separação descoberta/teste. Escrito como bandeira porque é a regra que
# mais se quebra sozinha: a amostra que sugeriu a ideia vira prova dela sem
# ninguém decidir isso.
AMOSTRA_E_DESCOBERTA = True

PROTECOES = (
    ("separação temporal",
     "descoberta, calibração e teste final em períodos que não se misturam"),
    ("controle de múltiplos testes",
     f"dezenas de agentes tentando muitas regras ⇒ limiar {ALFA_MULTIPLO}"),
    ("baseline equivalente",
     "comparar cada teoria com seleções aleatórias do MESMO tamanho e horizonte"),
    ("registro de falhas",
     "guardar as teorias descartadas; guardar só vencedoras distorce a evidência"),
    ("explicação congelada",
     "a justificativa tem que existir antes do período avaliado"),
)

# --------------------------------------------------------- retrato das mesas
# Os números medidos em cada estudo. É contra ISTO que um achado novo deve ser
# comparado, e não contra uma uniforme teórica que a mesa nunca prometeu.
RETRATO: Dict[str, Dict[str, Any]] = {
    "mega_fire": {
        "n": 197, "fonte": "4 capturas sobrepostas", "entropia_norm": 0.976,
        "p_uniformidade": 0.713, "vermelho": 98, "preto": 95,
        "impar": 91, "par": 102, "baixo": 93, "alto": 100, "zeros": 4,
        "repeticao_imediata": 8, "n_transicoes": 196, "pares_distintos": 185,
        "mult_taxa": 0.081, "mult_n": 16, "mult_faixa": (34, 162),
        "mult_media": 78.6, "mi_lag1_p": 0.609, "finais_p": 0.558,
        "duzias_p": 0.560, "regime_cor_p": 0.570,
        "maior_lag_abs": ("lag 1", -0.100),
    },
    "lightning": {
        "n": 162, "fonte": "captura 18x9", "entropia_norm": 0.963,
        "p_uniformidade": 0.056, "vermelho": 77, "preto": 80,
        "impar": 60, "par": 97, "baixo": 89, "alto": 68, "zeros": 5,
        "repeticao_imediata": 2, "n_transicoes": 161, "pares_distintos": 153,
        "mult_taxa": 0.074, "mult_n": 12, "mult_faixa": (50, 400),
        "mult_mediana": 100, "mi_lag1_p": 0.716, "finais_p": 0.054,
        "duzias_p": 0.100, "colunas_p": 0.074, "regime_cor_p": 0.964,
        "maior_lag_abs": ("lag 4", 0.146),
    },
    "immersive": {
        "n": 162, "fonte": "captura 18x9", "entropia_norm": 0.966,
        "p_uniformidade": 0.375, "vermelho": 77, "preto": 80,
        "impar": 74, "par": 83, "baixo": 78, "alto": 79,
        "repeticao_imediata": 7, "mult_taxa": 0.0, "mult_n": 0,
    },
    "crazy_time": {
        "n": 100, "fonte": "captura de 100 células", "entropia_norm": 0.874,
        "categorias": {"1": 30, "2": 27, "5": 12, "10": 5,
                       "moeda": 10, "espiral": 5, "alvo": 6, "chave": 5},
        "numericos": 74, "icones": 26, "repeticao_imediata": 23,
        "maior_faixa_igual": 5, "maior_faixa_tipo": 13,
        "mi_lag1": 0.389, "mi_lag1_p": 0.451,
        "regime_completo_p": 0.199, "regime_icone_p": 0.036,
        "placas_amarelas": 26, "amarela_faixa": (3, 200), "amarela_mediana": 30.0,
        "etiquetas_brancas": 12, "branca_faixa": (2, 20), "branca_mediana": 3.5,
    },
    "crazy_time_a": {
        "n": 100, "fonte": "captura de 100 células", "entropia_norm": 0.779,
        "categorias": {"1": 41, "2": 27, "5": 8, "10": 9,
                       "moeda": 5, "espiral": 5, "alvo": 3, "chave": 2},
        "numericos": 85, "icones": 15, "repeticao_imediata": 23,
    },
}

# ------------------------------------------------------------- os estados
# O que cada estado MANDA o caçador fazer. Sem esta tradução o catálogo seria
# leitura bonita e nada mudaria no comportamento da máquina.
CONDUTA = {
    "SEM_EVIDENCIA": "já medido e deu nada — só reabrir com limiar duro e dado novo",
    "DESCRITIVA": "descreve o histórico; não é previsão nem deve virar sinal sozinha",
    "EXPLORATORIA": "vale caçar aqui, mas o achado nasce sem valor de prova",
    "SINAL": "ficou abaixo de 0,05 nesta amostra — medir adiante, em dado que não o gerou",
    "PRE_REGISTRO": "só é falsificável com horizonte e critério fixados ANTES",
    "AMOSTRA_INSUFICIENTE": "a amostra não sustenta; juntar mais história antes de tentar",
    "ALTO_RISCO": "definição flexível demais — qualquer achado aqui exige limiar muito duro",
    "CONTROLE_NEGATIVO": "TEM que dar nada. Se der achado, o defeito é do caçador",
    "NAO_TESTAVEL": "a fonte não traz a variável; não há como testar com o que temos",
}

# ------------------------------------------------------ catálogo das roletas
# (código, nome, o que procura, estado, leitura da amostra)
CATALOGO_ROLETA = [
    ("H01", "uniformidade marginal", "compara os 37 valores como conjunto",
     "SEM_EVIDENCIA", "qui-quadrado p=0,056 (lightning) e p=0,713 (mega fire)"),
    ("H02", "cobertura integral", "ausências completas no recorte",
     "DESCRITIVA", "36/37 valores apareceram ao menos uma vez"),
    ("H03", "amplitude de frequência", "distância entre o mais e o menos frequente",
     "DESCRITIVA", "amplitude 10; 34 valores com duas ou mais aparições"),
    ("H04", "quentes e frios locais", "concentração pontual em valores",
     "SEM_EVIDENCIA", "extremos locais existem, mas não superam 37 comparações"),
    ("H05", "equilíbrio de cores", "vermelho x preto, excluindo zero",
     "SEM_EVIDENCIA", "77x80 p=0,873"),
    ("H06", "dominância local de cor", "blocos temporais de uma cor",
     "SEM_EVIDENCIA", "maior faixa 8; varredura p=0,407"),
    ("H07", "paridade", "ímpares x pares",
     "SINAL", "lightning 60x97 p=0,004 — o único abaixo de 0,01 em 56 famílias"),
    ("H08", "faixas baixa e alta", "1-18 x 19-36",
     "SEM_EVIDENCIA", "89x68 p=0,110"),
    ("H09", "dúzias", "1-12, 13-24, 25-36",
     "SEM_EVIDENCIA", "65/46/46 p=0,100"),
    ("H10", "colunas", "as três colunas numéricas",
     "SEM_EVIDENCIA", "50/42/65 p=0,074"),
    ("H11", "algarismos finais", "concentração por terminação",
     "SEM_EVIDENCIA", "p=0,054 no lightning; p=0,558 no mega fire"),
    ("H12", "frequência do zero", "o zero como estado separado",
     "DESCRITIVA", "5 em 162 (3,1%)"),
    ("H13", "intervalos entre zeros", "regularidade das lacunas",
     "AMOSTRA_INSUFICIENTE", "mediana 29; faixa 3 a 58"),
    ("H14", "primos", "propriedade aritmética",
     "EXPLORATORIA", "35 ocorrências; agrupamento definido depois da captura"),
    ("H15", "múltiplos de três", "classe modular simples",
     "EXPLORATORIA", "65 em 162; sobrepõe-se às colunas"),
    ("H16", "soma dos dígitos", "famílias com mesma soma decimal",
     "ALTO_RISCO", "muitas famílias possíveis inflam coincidência"),
    ("H17", "repetição imediata", "resultados iguais consecutivos",
     "DESCRITIVA", "2 em 161 (lightning); 8 em 196 (mega fire)"),
    ("H18", "consecutivos numéricos", "saltos de magnitude 1",
     "DESCRITIVA", "7 passagens com diferença 1"),
    ("H19", "eco de terminação", "mesma terminação em passagens seguidas",
     "EXPLORATORIA", "10 de 161 preservaram a terminação"),
    ("H20", "tamanho do salto", "saltos pequenos x grandes",
     "DESCRITIVA", "diferença média 12,85; mediana 11"),
    ("H21", "pares espelhados", "pares consecutivos cuja soma é 37",
     "AMOSTRA_INSUFICIENTE", "1 ocorrência"),
    ("H22", "dígitos invertidos", "relações ab/ba no domínio",
     "AMOSTRA_INSUFICIENTE", "0 passagens satisfizeram a regra estrita"),
    ("H23", "faixas de cor", "maior bloco monocromático",
     "SEM_EVIDENCIA", "maior faixa 8; varredura p=0,407"),
    ("H24", "alternância de cor", "trocas vermelho/preto",
     "DESCRITIVA", "67 trocas em 156 passagens não-zero"),
    ("H25", "faixas de paridade", "maior bloco par ou ímpar",
     "SEM_EVIDENCIA", "maior faixa 12; varredura p=0,133"),
    ("H26", "persistência baixo/alto", "permanência na mesma metade",
     "PRE_REGISTRO", "exige referência definida antes"),
    ("H27", "persistência de dúzia", "permanência ou salto entre dúzias",
     "PRE_REGISTRO", "o tipo de salto precisa ser congelado antes"),
    ("H28", "persistência de coluna", "transições dentro da mesma coluna",
     "PRE_REGISTRO", "três estados, muitas transições, suporte curto"),
    ("H29", "correlação lag 1", "cada valor com o seguinte",
     "SEM_EVIDENCIA", "r=-0,042"),
    ("H30", "correlação lag 2-3", "ecos curtos atrasados",
     "SEM_EVIDENCIA", "r2=-0,022; r3=-0,035"),
    ("H31", "ecos lag 4-10", "atrasos mais longos",
     "SEM_EVIDENCIA", "maior |r| em lag 4: +0,146"),
    ("H32", "informação mútua", "dependência não linear de 1ª ordem",
     "SEM_EVIDENCIA", "MI=2,738 bits; permutação p=0,716"),
    ("H33", "diversidade de transições", "quantos pares dirigidos distintos",
     "DESCRITIVA", "153 pares distintos em 161 passagens"),
    ("H34", "colisões de arestas", "repetição dos mesmos pares dirigidos",
     "EXPLORATORIA", "6 tipos repetiram; máximo 3"),
    ("H35", "reciprocidade", "A→B e B→A como família",
     "ALTO_RISCO", "escolher reciprocidades depois do fato infla coincidência"),
    ("H36", "motivos de ordem 2+", "dois ou mais estados como contexto",
     "AMOSTRA_INSUFICIENTE", "contextos crescem rápido e o suporte cai"),
    ("H37", "eco em janela", "retorno dentro de atraso fixo",
     "PRE_REGISTRO", "só é falsificável com tamanho e critério definidos antes"),
    ("H38", "regime de cor", "quatro blocos temporais",
     "SEM_EVIDENCIA", "quartis p=0,964"),
    ("H39", "regime de dúzias", "dúzias em quatro blocos",
     "SEM_EVIDENCIA", "quartis p=0,948"),
    ("H40", "rotação de quentes/frios", "troca dos mais frequentes ao longo",
     "PRE_REGISTRO", "precisa de janelas fixas e penalização pela busca"),
    ("H41", "entropia móvel", "períodos de maior ou menor diversidade",
     "AMOSTRA_INSUFICIENTE", "falta série mais longa para separar regimes"),
    ("H42", "ponto de mudança", "uma quebra única na distribuição",
     "PRE_REGISTRO", "sem horário ou evento externo, a quebra é só estatística"),
    ("H43", "efeito de linha da grade", "se as linhas visuais diferem",
     "CONTROLE_NEGATIVO", "linha é paginação da interface, não variável causal"),
    ("H44", "efeito de coluna da grade", "alinhamentos verticais da captura",
     "CONTROLE_NEGATIVO", "o layout de 9 colunas fabrica padrão artificial"),
    ("H45", "taxa de destaques", "proporção de células marcadas",
     "DESCRITIVA", "12/162 = 7,4%"),
    ("H46", "intensidade dos destaques", "magnitude das marcas",
     "DESCRITIVA", "faixa 50x a 400x; mediana 100x"),
    ("H47", "perfil dos destaques", "categorias das células marcadas",
     "DESCRITIVA", "1 zero, 4 vermelhos e 7 pretos"),
    ("H48", "agrupamento de destaques", "intervalos entre marcas",
     "AMOSTRA_INSUFICIENTE", "mediana 11; faixa 3 a 27"),
    ("H49", "consenso de agentes", "convergência entre modelos diferentes",
     "PRE_REGISTRO", "concordância interna não substitui dado independente"),
    ("H50", "anomalia residual", "estrutura após remover efeitos simples",
     "EXPLORATORIA", "resíduo pode ser sinal ou o vencedor de muitas tentativas"),
    ("H51", "padrão de não padrão", "a quebra da regularidade como evento",
     "ALTO_RISCO", "sem regra anterior, qualquer desvio se explica depois"),
    ("H52", "correção de múltiplos testes", "ajustar o limiar às 56 hipóteses",
     "PRE_REGISTRO", f"limiar {ALFA_MULTIPLO} — indispensável"),
    ("H53", "separação descoberta/teste", "não criar e provar na mesma amostra",
     "PRE_REGISTRO", "estas capturas são descoberta, não prova — indispensável"),
    ("H54", "estabilidade por reamostragem", "se a conclusão sobrevive a subconjuntos",
     "PRE_REGISTRO", "com 162 eventos, estimativas raras têm grande incerteza"),
    ("H55", "variáveis físicas ocultas", "condições mecânicas não capturadas",
     "NAO_TESTAVEL", "a fonte não traz velocidade, posição, operador nem horário"),
    ("H56", "mecanismo quântico", "ligação causal física mensurável",
     "NAO_TESTAVEL", "sequências e associações não demonstram mecanismo físico"),
]

# ------------------------------------------------- catálogo do crazy time
CATALOGO_CRAZY = [
    ("H01", "frequência por categoria", "as oito classes visuais",
     "DESCRITIVA", "1=30 2=27 5=12 10=5 moeda=10 espiral=5 alvo=6 chave=5"),
    ("H02", "números versus ícones", "numéricos x bônus",
     "DESCRITIVA", "74 numéricos e 26 ícones"),
    ("H03", "predomínio do 1", "concentração na classe 1",
     "DESCRITIVA", "30% na captura; 41% no crazy time a"),
    ("H04", "predomínio do 2", "concentração na classe 2",
     "DESCRITIVA", "27% nas duas mesas"),
    ("H05", "classes 5 e 10", "as duas classes numéricas menos comuns",
     "DESCRITIVA", "5=12 e 10=5; juntas 17"),
    ("H06", "taxa total de ícones", "presença de eventos de ícone",
     "DESCRITIVA", "26/100 no crazy time; 15/100 no crazy time a"),
    ("H07", "perfil dos ícones", "as quatro famílias de ícone",
     "DESCRITIVA", "moeda 10, espiral 5, alvo 6, chave 5"),
    ("H08", "ícone dominante", "concentração numa família visual",
     "EXPLORATORIA", "maior contagem entre ícones foi 10 (moeda)"),
    ("H09", "entropia de categorias", "diversidade das oito classes",
     "DESCRITIVA", "2,622 bits = 87,4% do máximo (77,9% no crazy time a)"),
    ("H10", "concentração numérica", "distribuição dentro de 1/2/5/10",
     "DESCRITIVA", "entre 74 números, 1 e 2 somam 57"),
    ("H11", "repetição exata", "categorias iguais consecutivas",
     "DESCRITIVA", "23 repetições em 99 passagens — nas duas mesas"),
    ("H12", "maior faixa exata", "maior bloco da mesma categoria",
     "DESCRITIVA", "faixa máxima 5, na categoria 2"),
    ("H13", "faixa de tipo", "blocos numéricos x blocos de ícones",
     "SEM_EVIDENCIA", "maior faixa 13; permutação p=0,364"),
    ("H14", "intervalos entre ícones", "quantos resultados separam ícones",
     "DESCRITIVA", "mediana 1,0; média 2,64"),
    ("H15", "faixa extrema sem ícone", "ausência prolongada de bônus",
     "EXPLORATORIA", "maior intervalo interno 13 resultados"),
    ("H16", "ícones adjacentes", "dois ícones seguidos",
     "DESCRITIVA", "8 passagens ícone→ícone"),
    ("H17", "agrupamento de ícones", "blocos locais de eventos especiais",
     "PRE_REGISTRO", "varrer muitos tamanhos de janela exige correção"),
    ("H18", "alternância número/ícone", "padrão binário alternado",
     "SEM_EVIDENCIA", "há trechos alternados e homogêneos; sem excesso robusto"),
    ("H19", "repetição de ícone específico", "o mesmo ícone em curto intervalo",
     "AMOSTRA_INSUFICIENTE", "contagens por ícone são pequenas"),
    ("H20", "rotação entre ícones", "ordem recorrente entre as quatro famílias",
     "AMOSTRA_INSUFICIENTE", "poucos eventos por família"),
    ("H21", "transições categoria→categoria", "o seguinte pela classe atual",
     "EXPLORATORIA", "39 pares distintos em 99 passagens"),
    ("H22", "colisões de transição", "pares dirigidos repetidos",
     "DESCRITIVA", "23 tipos repetiram; máximo 11"),
    ("H23", "informação mútua", "dependência não linear de 1ª ordem",
     "SEM_EVIDENCIA", "MI=0,389 bits; permutação p=0,451"),
    ("H24", "transições recíprocas", "A→B e B→A",
     "ALTO_RISCO", "escolher recíprocos depois cria coincidência"),
    ("H25", "motivos de ordem 2+", "duas categorias anteriores como contexto",
     "AMOSTRA_INSUFICIENTE", "até 64 contextos para 100 observações"),
    ("H26", "eco atrasado", "repetição em lag fixo",
     "PRE_REGISTRO", "o atraso precisa ser escolhido antes"),
    ("H27", "regime completo", "as oito categorias em quatro quartis",
     "SEM_EVIDENCIA", "qui-quadrado temporal p=0,199"),
    ("H28", "regime número/ícone", "a taxa de ícones em quatro quartis",
     "SINAL", "p=0,036 — a taxa de bônus não parece constante no tempo"),
    ("H29", "regime do 1", "mudança temporal na classe mais frequente",
     "EXPLORATORIA", "classe dominante oscila mesmo sem mudança estrutural"),
    ("H30", "regime de 5/10", "concentração temporal das classes altas",
     "AMOSTRA_INSUFICIENTE", "poucas ocorrências limitam a potência"),
    ("H31", "regime por ícone", "cada família especial ao longo do tempo",
     "AMOSTRA_INSUFICIENTE", "quartis com zero ocorrências"),
    ("H32", "ponto de mudança", "uma quebra única na distribuição",
     "PRE_REGISTRO", "sem horário ou evento externo é só estatística"),
    ("H33", "multiplicadores amarelos", "as placas inclinadas",
     "DESCRITIVA", "26 placas; faixa 3x-200x; mediana 30x"),
    ("H34", "etiquetas brancas", "os rótulos retangulares",
     "DESCRITIVA", "12 etiquetas; faixa 2x-20x; mediana 3,5x"),
    ("H35", "intensidade amarela", "magnitude das placas",
     "DESCRITIVA", "média 45,8x; extremos puxam a média"),
    ("H36", "intensidade branca", "magnitude das etiquetas",
     "AMOSTRA_INSUFICIENTE", "média 5,3x em apenas 12 rótulos"),
    ("H37", "dupla marcação", "célula com etiqueta e placa",
     "AMOSTRA_INSUFICIENTE", "há exemplos, mas poucos para condicional"),
    ("H38", "multiplicador por ícone", "intensidades entre famílias especiais",
     "AMOSTRA_INSUFICIENTE", "atribuições poucas e heterogêneas"),
    ("H39", "agrupamento de intensidades", "multiplicadores altos próximos",
     "PRE_REGISTRO", "definir 'alto' depois de ver os dados é sobreajuste"),
    ("H40", "regime de multiplicadores", "intensidades ao longo do recorte",
     "NAO_TESTAVEL", "faltam observações e as regras de geração das marcas"),
    ("H41", "efeito de linha da grade", "diferenças entre linhas visuais",
     "CONTROLE_NEGATIVO", "linha é paginação de 9 colunas, não estado causal"),
    ("H42", "efeito de coluna da grade", "alinhamentos verticais",
     "CONTROLE_NEGATIVO", "o layout fabrica colunas sem relação temporal"),
    ("H43", "borda da captura", "efeito do começo e fim visíveis",
     "NAO_TESTAVEL", "a captura não traz horário nem continuidade externa"),
    ("H44", "painel ao vivo separado", "não misturar o atual com o histórico",
     "CONTROLE_NEGATIVO", "o painel acima da grade fica fora da série"),
    ("H45", "consenso de agentes", "várias famílias de modelos",
     "PRE_REGISTRO", "concordância interna não substitui amostra independente"),
    ("H46", "anomalia residual", "estrutura após remover frequências simples",
     "EXPLORATORIA", "resíduo pode ser sinal ou seleção"),
]

CRAZY = ("crazy_time", "crazy_time_a")


def catalogo(mesa: str) -> List[tuple]:
    return CATALOGO_CRAZY if str(mesa) in CRAZY else CATALOGO_ROLETA


# ------------------------------------------------------ os sinais em aberto
# Congelados como a H53 manda: horizonte e critério escritos ANTES de medir,
# e a medição tem que acontecer em história que não gerou a hipótese.
SINAIS_ABERTOS = [
    {
        "mesa": "lightning", "familia": "H07", "nome": "paridade",
        "observado": "60 ímpares × 97 pares em 157 não-zero",
        "p": 0.004, "razao": 97 / 78.5,
        "sobrevive_correcao": False,     # 0,004 > 0,00089
        "criterio": "proporção de pares entre resultados não-zero",
        "horizonte": "bloco fixo de 200 giros, medido inteiro, sem parar antes",
        "por_que_importa": "é o único ponto abaixo de 0,01 nas 5 mesas × 56 famílias",
    },
    {
        "mesa": "crazy_time", "familia": "H28", "nome": "regime número/ícone",
        "observado": "taxa de ícone difere entre os quatro quartis",
        "p": 0.036, "razao": None,
        "sobrevive_correcao": False,
        "criterio": "taxa de ícone por quarto de amostra, quatro blocos iguais",
        "horizonte": "bloco fixo de 200 giros dividido em 4",
        "por_que_importa": ("bate com a percepção dele de que a mesa muda de "
                            "humor conforme a hora — e é medível"),
    },
]

def controles_negativos(mesa: str) -> tuple:
    """Quais códigos são controle negativo NESTA mesa.

    Lido do próprio catálogo em vez de escrito à mão: os códigos não coincidem
    entre as roletas (H43/H44) e o Crazy Time (H41/H42/H44), e uma lista fixa
    ia acusar a família errada na mesa errada.
    """
    return tuple(x[0] for x in catalogo(mesa) if x[3] == "CONTROLE_NEGATIVO")


# --------------------------------------------------------------- consultas
def _achar(mesa: str, codigo: str) -> Optional[tuple]:
    cod = str(codigo).strip().upper()
    for linha in catalogo(mesa):
        if linha[0] == cod:
            return linha
    return None


def estado(mesa: str, codigo: str) -> Optional[str]:
    linha = _achar(mesa, codigo)
    return linha[3] if linha else None


def limiar(mesa: str, codigo: str = None) -> float:
    """O p exigido de um achado nesta família.

    Família de alto risco de ajuste tem o limiar apertado mais uma vez: se a
    definição é flexível, o número de tentativas escondidas é maior que o que
    a conta das 56 famílias já cobre.
    """
    if codigo and estado(mesa, codigo) == "ALTO_RISCO":
        return ALFA_MULTIPLO / 10
    return ALFA_MULTIPLO


def _palavras(txt: str) -> set:
    import re
    t = (txt or "").lower()
    t = (t.replace("á", "a").replace("ã", "a").replace("â", "a")
          .replace("é", "e").replace("ê", "e").replace("í", "i")
          .replace("ó", "o").replace("ô", "o").replace("õ", "o")
          .replace("ú", "u").replace("ç", "c"))
    return {p for p in re.split(r"[^a-z0-9]+", t) if len(p) > 3}


# O VOCABULÁRIO DE CADA FAMÍLIA.
#
# Só comparar palavra a palavra não bastava: o caçador escreve "o par sai mais
# que o ímpar" e a família se chama "paridade" — zero palavras em comum, e o
# aviso não saía justamente no caso mais provável. Aqui cada família declara
# como ela costuma ser dita.
CHAVES_ROLETA = {
    "H01": ("uniforme", "uniformidade", "todos os numeros"),
    # sem "sai mais": expressão genérica demais, engolia paridade, cor e dúzia
    "H04": ("quente", "quentes", "frio", "frios",
            "mais frequente", "menos frequente"),
    "H05": ("vermelho", "preto", "cor", "cores"),
    "H07": ("par", "pares", "impar", "impares", "paridade"),
    "H08": ("baixo", "baixos", "alto", "altos", "metade"),
    "H09": ("duzia", "duzias"),
    "H10": ("coluna", "colunas"),
    "H11": ("final", "finais", "terminacao", "termina", "algarismo"),
    "H12": ("zero",),
    "H14": ("primo", "primos"),
    "H15": ("multiplo de tres", "multiplos de tres"),
    "H16": ("soma dos digitos", "soma digital"),
    "H17": ("repete", "repeticao", "repetiu", "mesmo numero seguido"),
    "H18": ("vizinho", "consecutivo", "consecutivos", "numero seguinte"),
    "H19": ("eco de final", "mesmo final", "final igual"),
    "H21": ("espelho", "espelhado", "soma 37"),
    "H23": ("faixa de cor", "sequencia de cor", "bloco de cor"),
    "H25": ("faixa de paridade", "sequencia de pares"),
    "H26": ("persiste", "persistencia", "continua na metade"),
    "H29": ("correlacao", "lag 1", "atraso 1"),
    "H31": ("lag", "atraso", "eco atrasado"),
    "H32": ("informacao mutua", "dependencia"),
    "H34": ("transicao", "transicoes", "par dirigido", "leva ao", "puxa o"),
    "H35": ("reciproco", "reciprocidade", "volta para"),
    "H36": ("contexto", "dois anteriores", "ordem 2"),
    "H37": ("janela", "dentro de", "horizonte"),
    "H38": ("regime de cor", "muda ao longo"),
    "H40": ("rotacao", "troca de quentes"),
    "H43": ("linha", "linhas", "grade"),
    "H44": ("coluna da grade", "vertical", "alinhamento"),
    "H45": ("destaque", "destaques", "multiplicador", "raio"),
    "H49": ("consenso", "concordam", "varias teorias"),
    "H50": ("residual", "residuo", "anomalia", "sobra"),
    "H51": ("nao padrao", "quebra de padrao"),
}
CHAVES_CRAZY = {
    "H01": ("categoria", "categorias", "classe", "classes"),
    "H02": ("numero", "numeros", "icone", "icones", "bonus"),
    "H03": ("classe 1", "o um", "predominio"),
    "H05": ("cinco", "dez", "classe 5", "classe 10"),
    "H06": ("taxa de icone", "taxa de bonus", "frequencia de bonus"),
    "H07": ("moeda", "espiral", "alvo", "chave", "pachinko", "cash hunt"),
    "H11": ("repete", "repeticao", "mesma categoria seguida"),
    "H13": ("faixa", "bloco", "sequencia"),
    "H15": ("sem icone", "sem bonus", "seca", "atraso do bonus"),
    "H17": ("agrupamento", "cluster", "juntos"),
    "H21": ("transicao", "transicoes", "leva ao", "puxa o"),
    "H24": ("reciproco", "reciprocidade"),
    "H26": ("lag", "atraso", "eco"),
    "H28": ("regime", "muda ao longo do tempo", "horario", "quartil",
            "conforme a hora", "hora do dia", "depende do horario"),
    "H33": ("placa", "amarelo", "multiplicador"),
    "H34": ("etiqueta", "branca", "rotulo"),
    "H39": ("multiplicador alto", "intensidade"),
    "H41": ("linha", "linhas", "grade"),
    "H42": ("coluna", "vertical"),
    "H45": ("consenso", "concordam"),
    "H46": ("residual", "residuo", "anomalia"),
}


def _chaves(mesa: str) -> Dict[str, tuple]:
    return CHAVES_CRAZY if str(mesa) in CRAZY else CHAVES_ROLETA


def familia_parecida(mesa: str, descricao: str) -> Optional[tuple]:
    """A qual família auditada esta ideia nova corresponde, se a alguma.

    Primeiro pelo vocabulário declarado de cada família; se nada casar, cai na
    comparação de palavras com o nome e o objeto da família.

    Grosseira de propósito: serve para AVISAR o caçador de que o terreno já foi
    pisado, não para barrar nada. Ele foi explícito — "não critique e nem barre".
    """
    if not (descricao or "").strip():
        return None
    import re
    bruto = (descricao or "").lower()
    for ch, para in (("á", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"),
                     ("í", "i"), ("ó", "o"), ("ô", "o"), ("õ", "o"),
                     ("ú", "u"), ("ç", "c")):
        bruto = bruto.replace(ch, para)
    tokens = set(re.split(r"[^a-z0-9]+", bruto))
    # a família que casar com a expressão MAIS ESPECÍFICA ganha. Pegar a
    # primeira que casa fazia "sem bonus há muitos giros" cair em "números
    # versus ícones" só porque a palavra bônus aparece nas duas.
    melhor_cod, melhor_tam = None, 0
    for cod, palavras in _chaves(mesa).items():
        for p in palavras:
            casou = (p in bruto) if " " in p else (p in tokens)
            if casou and len(p) > melhor_tam:
                melhor_cod, melhor_tam = cod, len(p)
    if melhor_cod:
        achou = _achar(mesa, melhor_cod)
        if achou:
            return achou
    alvo = _palavras(descricao)
    melhor, nota = None, 0
    for linha in catalogo(mesa):
        base = _palavras(linha[1] + " " + linha[2])
        comum = len(alvo & base)
        if comum > nota:
            melhor, nota = linha, comum
    return melhor if nota >= 2 else None


def veredito(mesa: str, descricao: str) -> Dict[str, Any]:
    """O que os estudos dele já dizem sobre uma ideia que a máquina trouxe.

    Nunca devolve "descartado". Devolve o que já se sabe e o quanto o achado
    precisa ser forte para valer alguma coisa em cima disso.
    """
    fam = familia_parecida(mesa, descricao)
    if not fam:
        return {"conhecida": False, "limiar": ALFA_MULTIPLO,
                "aviso": "terreno não coberto pelas auditorias — caçada livre"}
    cod, nome, procura, est, leitura = fam
    return {
        "conhecida": True, "familia": cod, "nome": nome, "estado": est,
        "conduta": CONDUTA.get(est, ""), "leitura": leitura,
        "limiar": limiar(mesa, cod),
        "controle_negativo": cod in controles_negativos(mesa),
        "aviso": f"{cod} — {nome}: {CONDUTA.get(est, '')} (auditoria: {leitura})",
    }


def por_estado(mesa: str, est: str) -> List[tuple]:
    return [x for x in catalogo(mesa) if x[3] == est]


def onde_cavar(mesa: str) -> List[tuple]:
    """As famílias que ficaram em aberto — é onde a busca ainda rende."""
    abertos = ("EXPLORATORIA", "SINAL", "PRE_REGISTRO")
    return [x for x in catalogo(mesa) if x[3] in abertos]


def controle_negativo_grade(seq: List[Any], colunas: int = 9,
                            embaralhos: int = 2000,
                            semente: int = 7) -> Dict[str, Any]:
    """H43/H44 — a linha e a coluna da grade não podem prever nada.

    O histórico do site é desenhado em 9 colunas porque cabe na tela, e mais
    nada. Se a máquina "descobre" que a coluna 3 é especial, o defeito é dela:
    inventou uma variável a partir do layout.

    Este é o teste que um caçador honesto tem que passar antes de ser levado a
    sério — e é o único da base que TEM que dar nada. Um controle que nunca
    acusa também não vale: por isso `test_base_auditoria` planta um efeito
    artificial de coluna e exige que ele seja pego.
    """
    import random
    vals = []
    for x in seq or []:
        try:
            vals.append(float(x))
        except (TypeError, ValueError):
            continue
    n = len(vals)
    if n < colunas * 4:
        return {"n": n, "p_coluna": None, "p_linha": None,
                "leitura": "amostra curta demais para o controle"}

    def disp(v, tamanho):
        grupos: Dict[int, List[float]] = {}
        for i, x in enumerate(v):
            grupos.setdefault(i % tamanho if tamanho == colunas
                              else i // colunas, []).append(x)
        media = sum(v) / len(v)
        return sum(len(g) * (sum(g) / len(g) - media) ** 2
                   for g in grupos.values() if g)

    obs_c = disp(vals, colunas)
    obs_l = disp(vals, 0)
    rnd = random.Random(semente)
    copia = list(vals)
    mais_c = mais_l = 0
    for _ in range(embaralhos):
        rnd.shuffle(copia)
        if disp(copia, colunas) >= obs_c:
            mais_c += 1
        if disp(copia, 0) >= obs_l:
            mais_l += 1
    p_c = (mais_c + 1) / (embaralhos + 1)
    p_l = (mais_l + 1) / (embaralhos + 1)
    limpo = (p_c > ALFA_MULTIPLO and p_l > ALFA_MULTIPLO)
    return {
        "n": n, "colunas": colunas, "p_coluna": round(p_c, 5),
        "p_linha": round(p_l, 5), "limiar": ALFA_MULTIPLO, "limpo": limpo,
        "leitura": ("a grade não prevê nada, como tem que ser"
                    if limpo else
                    "A GRADE APARECEU COMO SE FOSSE SINAL — o caçador está "
                    "achando padrão no layout da tela"),
    }


def resumo(mesa: str) -> str:
    r = RETRATO.get(mesa) or {}
    cat = catalogo(mesa)
    from collections import Counter
    c = Counter(x[3] for x in cat)
    L = [f"[Auditoria] {mesa}: {len(cat)} famílias já catalogadas"
         + (f" sobre {r.get('n')} resultados" if r.get("n") else "")]
    if r.get("entropia_norm"):
        L.append(f"   retrato: entropia {r['entropia_norm']:.1%}"
                 + (f" · uniformidade p={r['p_uniformidade']}"
                    if r.get("p_uniformidade") is not None else "")
                 + (f" · {r['repeticao_imediata']} repetições imediatas"
                    if r.get("repeticao_imediata") is not None else ""))
    L.append("   " + " · ".join(f"{k.lower()} {v}" for k, v in c.most_common()))
    cav = onde_cavar(mesa)
    L.append(f"   onde ainda vale cavar ({len(cav)}): "
             + ", ".join(f"{x[0]} {x[1]}" for x in cav[:6]))
    sin = [s for s in SINAIS_ABERTOS if s["mesa"] == mesa]
    for s in sin:
        L.append(f"   >> SINAL {s['familia']} {s['nome']}: {s['observado']} "
                 f"(p={s['p']}) — não sobrevive à correção de {ALFA_MULTIPLO}, "
                 f"medir em {s['horizonte']}")
    L.append(f"   limiar exigido pelo próprio estudo: p < {ALFA_MULTIPLO} "
             f"(0,05 ÷ {N_FAMILIAS} famílias)")
    return "\n".join(L)
