# ESTUDO — A Lotofácil sob controle negativo

Auditoria estatística de 3.246 concursos da Lotofácil (setembro/2003 a novembro/2024),
com o mesmo protocolo aplicado depois às outras oito loterias da Caixa.

**Entrega:** `RELATORIO_Lotofacil_sob_controle_negativo.pdf` — 57 páginas.

## A ideia central, em um parágrafo

Procurar padrão em 3.246 concursos com centenas de testes **encontra alguma coisa**, mesmo
que não exista nada. Então este estudo roda a bateria inteira — os 689 testes — em 1.000
históricos que ele mesmo gera por acaso uniforme puro, e guarda o maior |z| de cada um.
Isso dá a distribuição do *melhor achado possível num mundo sem padrão nenhum*, e é contra
ela que tudo é medido.

O número que sai disso: **num mundo comprovadamente sem padrão, esta busca produz um |z| de
4,83 em uma de cada vinte tentativas.** Qualquer descoberta de loteria abaixo disso, vinda
de uma busca deste tamanho, é ruído.

## O que deu

| | |
|---|---|
| Teorias populares medidas (quente, frio, atrasada, soma, paridade, moldura, espelho…) | 16, todas nulas |
| Teorias inéditas criadas para o estudo | 7, todas nulas |
| Regras estruturais com probabilidade exata por enumeração | 51, ganho = 1,000 em todas |
| Testes que sobrevivem ao controle negativo | 3 — e os 3 são artefato de nulo errado |
| **O que sobrou** | as 25 dezenas não saem com frequência igual: χ² = 56,38 (gl 24), replicando em três janelas disjuntas |
| **Tamanho disso** | 0,18 acerto por jogo — irrelevante para apostar (prêmio começa em 11) |
| Confirmação nas outras 7 loterias (sem a Lotofácil) | p = 0,047 (persistência), p = 0,030 (uniformidade) |

Não é sistema de aposta e não indica dezenas. É auditoria, e a conclusão principal é
**a favor** da lisura do sorteio: todas as formas estruturais batem com o exato na terceira
casa decimal.

## Como rodar

```
python3 lab/protocolo.py        # corte cronológico + controle negativo   -> resultados/protocolo.json
python3 lab/assertividade.py    # enumera as 3.268.760 combinações        -> resultados/assertividade.json
python3 lab/inovacoes.py        # as sete teorias inéditas                -> resultados/inovacoes.json
python3 lab/persistencia.py     # o achado do capítulo 7                  -> resultados/persistencia.json
python3 lab/outras_loterias.py  # o teste confirmatório do capítulo 8     -> resultados/outras_loterias.json
python3 lab/figuras.py          # as onze figuras                         -> figuras/*.png
python3 lab/relatorio.py        # o PDF
```

Sementes fixas (`20260903`). Rodando de novo, os números saem iguais até a última casa.
Precisa de `numpy`, `scipy` (só para conferência), `matplotlib` e do Chromium para o PDF.

## Onde estão as coisas

```
lab/base.py            dados, conferência de integridade, nulos exatos, gerador de histórias falsas
lab/teorias.py         estatísticas estruturais e distribuições exatas
lab/bateria.py         os 689 testes — a mesma função serve ao dado real e ao falso
lab/protocolo.py       o corte cronológico e o controle negativo
lab/assertividade.py   enumeração completa e o catálogo de regras ("livro de padrões")
lab/inovacoes.py       complemento, eco posicional, inércia, atrito, núcleo, maré, espelho
lab/persistencia.py    o achado e as tentativas de matá-lo
lab/outras_loterias.py o mesmo protocolo nas oito modalidades
lab/rel_*.py           o texto do relatório
dados/                 a base e a procedência dela
```

## Procedência dos dados

A API da Caixa está bloqueada pela política de rede deste ambiente. Os dados vieram de um
espelho público (`github.com/guilhermeasn/loteria.json`) e foram conferidos contra uma
**segunda fonte independente** presente no mesmo repositório (planilhas asloterias):
**zero divergências** em 2.696 concursos da Lotofácil, inclusive na ordem de extração das
bolas — e zero também na Mega-Sena (1–2.549) e na Quina (1–6.032). Ver `dados/PROCEDENCIA.txt`.

Um único registro está marcado como suspeito: o **concurso 2425**, cuja lista veio ordenada
em ordem crescente (chance de 1 em 15! sob ordem real). Ele foi excluído da bateria
posicional e mantido em todas as outras.

## O que fazer a seguir

O capítulo 7.5 do relatório contém um **pré-registro**: cinco hipóteses fixadas antes de
qualquer concurso posterior ao 3.246 ser observado, cada uma com o resultado que a derruba.
A base termina em novembro de 2024 porque a rotina da fonte parou ali; há quase dois anos de
concursos novos disponíveis, e testar o pré-registro contra eles é a coisa mais valiosa e
mais barata a fazer com este código.
