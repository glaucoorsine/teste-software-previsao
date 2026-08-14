# v80 — o que mudou, e por quê

## O defeito que estava por baixo de tudo

Em modo SOMBRA, com o gatilho em AGUARDANDO (o estado normal enquanto não há
teoria validada), o software **avaliava o baseline de frequência em vez do
consenso**. Medido nos 205 giros reais de Lightning: 128 de 144 ciclos, ou
88,9%.

A cascata que causava isso:

```python
sombra_alvos = list(alvos) if alvos else list(base_alvos)[:k]   # linha ~1749
...
cand_sombra = list(alvos) if alvos else []
if not cand_sombra:
    cand_sombra = list(sombra_alvos or [])                      # já era baseline
```

Consequências, todas na mesma direção:

- o consenso era calculado, aparecia no log e era descartado;
- a evidência acumulada em cada teoria vinha de janelas do baseline, e depois
  era comparada contra o próprio baseline — media-se uma coisa contra ela mesma;
- qualquer melhoria no cruzamento não mexia um dígito no resultado, porque não
  chegava ao que estava sendo medido.

**Correção:** `aprovados` (o consenso) entra na fila antes do baseline. O
baseline continua como último recurso, que é o papel dele.

Depois: sombra testa baseline 0%, consenso 91,7%. E o consenso, agora medido
de verdade, dá **1,03x o acaso** (28/144 contra 18,9%). Não é vitória — é a
primeira medição verdadeira que este software produziu.

## Por que nenhuma teoria nunca validava

Não era bug. Para validar é preciso `ic90_low > baseline` (18,9%). O que isso
exige na prática:

| n   | taxa mínima que passa | = quantas vezes o acaso |
|-----|-----------------------|-------------------------|
| 8   | 50,0%                 | 2,65x                   |
| 30  | 33,3%                 | 1,76x                   |
| 120 | 25,0%                 | 1,32x                   |
| 300 | 22,7%                 | 1,20x                   |

Vício de roleta real é 1,2x a 1,4x. Com `MIN_SOMBRA_VALIDAR = 8` só passaria
um vício de 2,65x, que não existe em mesa funcionando. E como **só teoria
validada podia votar**, o consenso ficava com zero teorias para sempre.

**Correção:** a evidência virou contínua. Vota também quem está acumulando
acima do baseline, com peso proporcional (`academia_agentes._peso_evidencia`):

```
n=8   a 1,32x  ->  voto 0,068
n=30  a 1,32x  ->  voto 0,161
n=120 a 1,30x  ->  voto 0,241
validada       ->  voto cheio
abaixo do baseline -> não vota
```

Isto não afrouxa a barra: quem decide o número é o consenso, e o consenso pesa.
O que muda é a evidência deixar de ser um carimbo que nunca vem.

Importa em particular porque o gate "consenso dispara sozinho com 2+ teorias
concordando" **nunca podia disparar** com zero teorias votando.

## A regra do operador entrou na votação

Estava sendo medida por fora, como auditoria. Conhecimento que não vota não
cruza com nada. Agora é uma voz com peso 2,0.

A regra, na forma que ele descreveu desde o começo e que levou o dia para ser
entendida: *"tá vindo muitos de 0-10, veio o 14, então vou jogar 4,5,9"* — não
é a família inteira nem a faixa do gatilho; é a família do final **dentro da
faixa que está saindo**.

Medida na declaração, 7 números contra 18,9%:

```
lightning  36/144 = 25,0%  1,32x  p=0,043
immersive  30/137 = 21,9%  1,16x
mega_fire  17/92  = 18,5%  0,98x
```

Ela apareceu só depois de listar os 59 casos reais um por um. Nenhuma
estatística agregada tinha mostrado, porque a pergunta vinha sendo feita errada
três vezes seguidas (marginal em vez de condicional; lag 1 em vez de janela;
família inteira em vez de família filtrada pela região).

## Coleta

- **HTTP 500 agora repete.** Era o erro mais comum da API e o único da família
  fora da lista de retry: um 500 passageiro derrubava a captura na primeira
  tentativa e a tela pintava "API offline".
- **API caindo não apaga mais a mesa.** O histórico salvo em disco passa a ser
  servido, com aviso amarelo "API instável — analisando histórico salvo", em vez
  de devolver lista vazia e parar de analisar.
- **Duplicata com carimbo deslocado.** O `event_id` é `jogo|valor|settled`, então
  o mesmo giro relatado duas vezes com 1 segundo de diferença entrava como giro
  novo — sempre com o valor repetido, porque é o mesmo giro. Inflava exatamente
  a medida de repetição. Nos 691 giros de Crazy Time, 21 duplicatas levaram a
  repetição de 27,5% a 29,7% e transformaram p=0,089 (nada) em p=0,0010 (o que
  parecia o achado mais forte do estudo). Na coleta seguinte apareceram mais 6.

## Réguas corrigidas

- **`regras_do_operador`**: a base era a chance teórica k/37. Se a mesa andou
  soltando muito 4-5-9, toda regra que aponte para 4-5-9 parecia forte sem o
  gatilho ter nada a ver. Caso real, mega_fire: 1,10x com a base teórica, 1,00x
  com a base real da mesa. Agora é a taxa observada do alvo naquela mesa.
- **`agentes_anomalia`**: os 12 agentes assumem 37 casas e `int(x)` derrubava
  CoinFlip/CashHunt/Pachinko/CrazyBonus, deixando uma sequência mutilada lida
  como roleta — 3 "confirmados" em cima de nada. Agora o Crazy Time tem caminho
  próprio, com a roda real (54 fatias). As perguntas de geometria não são feitas
  porque não têm equivalente ali.
- **`teorias_do_operador_ct` (novo)**: as quatro teorias ditadas para o Crazy
  Time. A T3 usava teste binomial com janelas de gatilho sobrepostas e dava 10%
  de confirmação falsa; passou para régua de reordenação e caiu para 2,5%.

## Módulos novos

- `academia_autonoma/hipoteses_predeclaradas.py` — compromissos com fórmula
  travada, medidos sozinhos. Veredito só sai no tamanho de amostra combinado,
  nunca na primeira vez que o número agrada. Calibração: 0/90 falso positivo,
  15/15 detecção de efeito real de 1,23x.
- `academia_autonoma/teorias_do_operador_ct.py` — as quatro teorias de Crazy
  Time, com a conta de quantas horas de mesa cada uma precisa (66 a 1088).
- `relatorio_visual.py` — gera uma página com todas as medidas na mesma régua,
  centrada no acaso.

---

# v81 ULTIMATO — o que muda para rodar dias

Esta versão não acrescenta teoria nenhuma. Ela existe para o software aguentar
ficar ligado sem ninguém olhando, que é um problema diferente de funcionar por
uma noite.

## O bus enchia a memória

O barramento de eventos era append-only, sem poda, e o `ler()` carregava o
arquivo INTEIRO na memória a cada consulta. Medido: 1.279 ciclos de uma mesa
geraram 7,5 MB.

```
3 dias, 4 mesas  ->  ~42 MB
30 dias          -> ~420 MB
```

O disco aguentaria. A leitura não: depois de um mês, cada consulta carregaria
420 MB para devolver 200 linhas. O software travaria de lentidão exatamente em
quem deixa rodando — o uso para o qual ele existe.

Correção: rotação por tamanho (teto de 8 MB, corta para 4 MB) e leitura só da
cauda do arquivo. Medido depois: o arquivo oscila entre 4 e 8 MB para sempre,
30.000 publicações levam 2,0 s, e as mensagens mais novas nunca se perdem.

O corte é por BYTES, não por número de linhas. Cortar por linhas parece
equivalente e não é: com mensagens de ~700 bytes, guardar 20.000 linhas dá
13,6 MB — acima do teto — e o arquivo passava a rotacionar a cada publicação,
lendo e reescrevendo 13 MB de cada vez.

## Aviso quando um compromisso fecha

Quem deixa rodando não quer aviso de cada giro; quer saber o momento em que uma
hipótese pré-declarada sai de "acumulando" e vira "confirmada" ou "morta". Isso
pode acontecer às três da manhã.

`hipoteses_predeclaradas.avisar_mudanca_de_veredito()` dispara a notificação uma
única vez por transição e guarda o que já avisou — reabrir o software não
repete o aviso.

## PROGRESSO.py

Uma tela só, sem log: giros por mesa, duplicatas descartadas, horas de coleta,
o estado de cada compromisso com barra de progresso e quantas ativações faltam,
as quatro teorias de Crazy Time, e o catálogo da academia.

```
python PROGRESSO.py        (ou PROGRESSO.bat)
```
