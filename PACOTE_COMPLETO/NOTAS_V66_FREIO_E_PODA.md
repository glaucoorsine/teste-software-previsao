# v66 — freio de produção, poda e reavaliação das maduras

Alvo desta versão: **assertividade**. Não "achar mais teoria" — parar de validar
teoria que não existe, e chegar mais rápido na que existe.

Só mexe em `academia_autonoma/ciclo_academia.py`. O critério de validação
continua o mesmo: **quem valida é a sombra prospectiva ao vivo**, com o portão
do FDR no lugar. Nada aqui afrouxa isso.

---

## O que estava acontecendo

Medido na v64, com fluxo sintético de 340 giros (≈4h de roleta):

```
catálogo ......................... 1354 teorias
validadas ........................    1
com ZERO amostra de sombra ....... 62% delas — nunca testadas nem uma vez
com n>=8 (mínimo p/ validar) .....  2,8%
amostra média por teoria .........  0,96
ciclo da academia ................ 1,4s no início → 9-12s por volta do giro 380
```

Os 12 agentes propunham ~80 teorias novas **por ciclo**. Todas disputando o mesmo
recurso escasso: giros em que o gatilho delas dispara. Um `transition a→b`
dispara em ~1/37 dos giros, então juntar as 8 amostras mínimas custa ~300 giros.
Com 80 concorrentes novas a cada ciclo, a fração do catálogo que amadurece nunca
sobe. O gargalo nunca foi falta de ideia — era falta de teste.

E isso custa assertividade por um caminho que não é óbvio. A barra do
Benjamini-Hochberg para a k-ésima teoria do lote é `k·alpha/m`, com `m` =
quantas estão sendo testadas ao mesmo tempo:

```
teorias no lote (m)   n necessário p/ provar um vício de 55%   ~giros   ~horas
        1650                      23                             851     10,6h
         269                      20                             740      9,2h
         120                      16                             592      7,4h
          60                      14                             518      6,5h
          40                      12                             444      5,5h
```

Não é maquiagem estatística baixar esse `m`: a dívida de comparação múltipla é
real, e a única forma honesta de reduzi-la é **gerar menos hipótese**, não
esconder teste.

---

## As três mudanças

### 1. Freio de produção (`FILA_MAX = 60`)

Antes dos agentes proporem, conta a **arena** — tudo que não é validada nem
arquivada. Passou de 60, os agentes pulam o ciclo e o tempo vai testar quem já
está na fila.

Conta a arena inteira, não só as imaturas: contando só imaturas, a fila esvazia
conforme elas amadurecem, a descoberta volta e o catálogo infla do mesmo jeito
(medido: 1562 teorias mesmo com o freio ligado). Quem libera vaga é a poda, não
o tempo.

### 2. Reavaliação das maduras

Teoria que bateu o mínimo de amostra entra na rodada da META **mesmo sem ter sido
reproposta** naquele ciclo.

Sem isso, uma teoria só era reavaliada quando algum agente por acaso a propunha
de novo — ~20 de 95 por ciclo, ou seja **uma volta a cada ~68 ciclos**. Ela podia
bater a amostra mínima com taxa boa e ficar horas esperando alguém olhar.

Não custa permutação: `decidir()` lê a sombra, e a crítica retrospectiva dessas
teorias já está gravada no catálogo.

### 3. Poda (`PODA_MIN_N = 10`, `PODA_FATOR = 0.75`)

Teoria com amostra suficiente e desempenho claramente abaixo do acaso vira
`arquivada`: sai das varreduras de contrato e sombra, solta a vaga na arena e
para de contar no `m` do FDR. Ela já respondeu — não é "ainda em teste".

---

## Resultado medido

Dois mundos, 370 ciclos cada, mesmo fluxo:
- **sinal**: vício plantado — depois do 5 vem 9 em 55% das vezes
- **ruído**: roleta IID limpa, sem vício nenhum

```
                catálogo   validadas   o que validou
v64  sinal ...... 12.133        2       5→9 (88%)  +  uma FALSA (33%)
v64  ruído ...... 12.417        1       34→5 (38%)  ← vício em roleta LIMPA
v66  sinal ....... 1.398        1       5→9 (60%)   só a verdadeira
v66  ruído ....... 1.385        0       nada
```

O ganho não é achar mais — é **parar de achar o que não existe**. A v64 declarou
um vício em roleta limpa; a v66 ficou calada.

Fluidez, de quebra: **ciclo de ~9s para ~1,4s**.

Ressalva: os braços da v64 foram interrompidos antes de completar os 370 ciclos,
então a comparação "2 contra 1 no mesmo número de ciclos" não está fechada. O
falso positivo no ruído aconteceu e vale; a contagem exata ainda será refeita.

---

## Verificação

```
suíte oficial ......................... 74/74 OK
test_controle_100 ..................... 100 séries de ruído, ~7098 hipóteses,
                                        0 validadas
test_fluxo_captura .................... FLUXO_TESTES_OK
test_honestidade_gates ................ HONEST_TESTS_OK
compileall ............................ OK
sintaxe dos 4 combos + central + assistente ... OK
```

## Onde ainda tem porcentagem para ganhar

O freio cala os 12 agentes de descoberta, mas **os agentes residuais continuam
produzindo**. No teste, sozinhos, mais de 1300 teorias:

```
R15  368      R14  247      R05  158      R09   96   ...
A04   26  ← os agentes de descoberta, que o freio calou
```

Estender o freio ao `ciclo_residual` deve baixar o `m` do FDR de ~300 para ~60,
o que pela tabela acima encurta de ~20 para ~14 ativações o custo de provar um
vício real. É o próximo passo.
