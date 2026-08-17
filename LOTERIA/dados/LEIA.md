# Os resultados dos sorteios

Há dois caminhos, e o primeiro é o bom.

## 1. Puxar da API (o caminho normal)

```
python PUXAR.py mega_sena --ultimo     testa a fonte com UMA chamada
python PUXAR.py mega_sena              puxa o histórico e grava aqui
```

Comece pelo `--ultimo`. Ele faz uma chamada só e mostra na tela **todos os
campos que a fonte devolveu**, e o que eu entendi deles. Se o formato não for o
que eu esperava, aparece ali — antes de milhares de chamadas e antes de qualquer
estatística.

O puxador **retoma de onde parou**. A API devolve um concurso por chamada, então
o histórico inteiro leva minutos; se cair no meio (internet, computador
dormindo, você fechando a janela), o que já veio fica gravado e a próxima
execução continua da lacuna.

### Se o endereço for outro

O endereço não está chumbado no código. Para trocar:

```
python PUXAR.py --fonte "https://o/endereco/que/voce/tem/{slug}"
```

Use `{slug}` onde entra o nome da loteria e `{n}` onde entra o número do
concurso. Se o seu endereço tiver outra forma, me mostre um exemplo dele que eu
ajusto.

**Eu não consegui testar contra a API de verdade.** A rede do ambiente onde eu
escrevo o código recusa a saída — e recusa também as APIs do seu outro software,
as mesmas que funcionam na sua máquina todo dia. Então o cliente foi provado
contra um servidor local que fala o formato do portal da Caixa: histórico
inteiro, retomada, concurso inexistente, resposta que não é JSON, servidor fora
do ar. O que falta confirmar é se a API real fala exatamente esse formato, e é a
sua primeira execução que diz.

## 2. Arquivo baixado (se preferir, ou se a API não responder)

Largue aqui um arquivo de resultados e rode:

```
python JOGAR.py mega_sena --historico dados/o_seu_arquivo.csv
```

Serve CSV com colunas `Bola1`…`Bola6` (o formato mais comum), JSON de API, ou
texto solto com uma linha por concurso. Se vierem as colunas de
`Ganhadores N acertos` e `Arrecadacao`, melhor: são elas que permitem medir a
partilha do prêmio (P01) — o único item capaz de aumentar o que você recebe sem
prever nada.

## Nos dois casos: confira o diagnóstico

A primeira coisa que aparece é o que eu entendi: quantos concursos, quantas
dezenas por concurso, de quanto a quanto, o primeiro e o último por extenso, e
de onde saiu cada faixa de prêmio. Bata o olho com o arquivo do lado.

O erro que eu temo não é o barulhento — é o mudo: ler a coluna errada, não
reclamar, e produzir estatística bonita sobre lixo.
