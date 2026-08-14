# v67 — o que mudou, o que está provado, o que não está

## As quatro mudanças

### 1. `meta_supervisora.decidir()` — o bug que travava tudo

Era a origem de "teorias boas sendo descartadas".

`decidir()` consultava o veredito **retrospectivo** do crítico antes da sombra ao
vivo, e o ramo `TESTAR_AGORA` devolvia `em_teste` sem nunca olhar o resultado:

```python
if dest == "em_teste_ativo" or ver == "TESTAR_AGORA":
    return "em_teste"          # ← saía aqui

if dest == "promissora" or ...:   # ← a validação morava aqui embaixo
```

Uma teoria marcada `TESTAR_AGORA` **nunca validava**, por melhor que fosse o
desempenho ao vivo. O sistema mandava testar, a teoria passava no teste, e o
resultado era jogado fora.

A teoria verdadeira do experimento estava presa exatamente aí:

```
5→9   n=8  hits=3  taxa=37,5%  acaso=2,7%  p=0,001  FDR aprovou (q=0,013)
      → decidir() devolvia "em_teste"
```

Agora a sombra ao vivo tem a palavra final (`_sombra_prova`). Estrutura inválida
continua barrando; o retrospectivo volta a servir para priorizar, não para vetar
— que é o desenho da v62.

**Verificado:** mundo com sinal → valida, incluindo a verdadeira. Dois catálogos
de ruído (38 e 317 maduras) → 0 validações. Destrava teoria boa sem abrir a
porta para teoria falsa.

### 2. Memórias contaminadas removidas do pacote

O zip vinha com `memoria_lightning.json` de 480 KB contendo:

```
150 avaliações de um teste antigo (não do usuário)
 50 janelas pendentes penduradas
placar embutido: 64 acertos / 86 erros
modelo_ativo = False   ← para a versão ATUAL do pipeline
```

E em `ia_modulos.py`: `if not modelo_ativo: operavel = False`.

**Toda instalação nova nascia bloqueada**, por um resultado ruim (ganho −0,06)
de um teste que não era do usuário. E o placar da tela já vinha preenchido com
64/86 antes do primeiro giro — forte candidato à origem dos "contadores errados".

Sem os arquivos: `modo=SOMBRA`, `modelo_ativo=True`, `motivo_bloq=[]`. O motor
os recria limpos. Removidos `lightning`, `crazy_time` e `mega_fire`.
`lstm_crazy_time.pt` fica — é modelo treinado, é legítimo.

### 3. Portão final: o consenso pode disparar sozinho

Antes: a sugestão só saía se **LSTM E outra fonte** apontassem o mesmo número.
Interseção vazia zerava tudo. Sem torch instalado, ou com <50 eventos, ou com o
modelo em fallback, **nenhuma previsão saía nunca** — e a tela não dizia o motivo.

Agora há dois caminhos:
1. LSTM treinado concordando com outra fonte (o forte, igual antes)
2. **Consenso sozinho**: número com ≥ `MIN_TEORIAS_SOZINHO` (=2) teorias
   validadas distintas concordando

Não afrouxa o que protege: os números que votam já passaram pela sombra
prospectiva ao vivo e pelo FDR. Uma teoria sozinha não abre gatilho.

E entrou o aviso que faltava:

```
[LSTM] SEM MODELO TREINADO — instale as dependências
(0_INSTALAR_DEPENDENCIAS.bat) e junte ≥50 eventos.
```

### 4. Freio e poda (v66, agora também nos residuais)

Os 12 agentes de descoberta e os 20 residuais param de propor quando a arena
passa de `FILA_MAX=60`. Motivo: a barra do FDR é `k·alpha/m`, com `m` = teorias
em teste simultâneo. Com 1650 na arena, provar um vício real de 55% custa ~23
ativações (~850 giros); com 60, custa ~12 (~444 giros).

Na v66 o freio pegava só os agentes de descoberta, e os residuais vazavam mais
de 1300 teorias sozinhos (R15=368, R14=247, R05=158… contra 26 dos A*).

---

## Verificação

```
suíte oficial ......................... 74/74 OK
test_controle_100 ..................... 100 séries de ruído, ~7098 hipóteses,
                                        0 validadas
test_fluxo_captura .................... FLUXO_TESTES_OK
test_honestidade_gates ................ HONEST_TESTS_OK
compileall ............................ OK
os 4 jogos, ponta a ponta ............. 0 crashes, 0 entradas rejeitadas
   lightning / mega_fire / immersive / crazy_time (domínio de 8 símbolos)
```

---

## O QUE AINDA NÃO ESTÁ RESOLVIDO

Isto aqui é importante e não deve ser lido como pessimismo — é o estado real.

**O sistema ainda não produz previsão na tela nos meus testes.** A cadeia é:

```
poucas teorias validam
  → elas só ficam cabíveis em ~3,5% dos giros
    → duas delas concordando no mesmo número, no mesmo giro ≈ nunca
```

A correção do `decidir` era condição necessária (sem ela era zero validada para
sempre), mas não suficiente.

**A pergunta aberta:** cruzar teorias bate a baseline de frequência (os 7 números
mais quentes dos últimos 40 giros)? Se não bater, o maquinário de teorias não
está acrescentando nada sobre três linhas contando frequência.

Primeira medição, nos giros em que o gatilho está ativo:

```
MUNDO COM SINAL          MUNDO DE RUÍDO
  cruzamento  37,2%        cruzamento  19,4%
  baseline    33,7%        baseline    21,5%
```

O padrão está certo — ganha onde há vício, perde onde não há. Mas são **3
acertos a mais em 86 giros**, p=0,28. Não é conclusão, é indício. Está sendo
refeito com vício mais forte, 1400 giros e teste pareado (McNemar).

---

# v69 — os dois portões que mantinham o software mudo

Verificação que faltava: **quando as condições acontecerem, a previsão aparece?**
Em vez de esperar surgirem, o teste (`teste_funcional.py`) constrói a situação —
duas teorias validadas concordando num número, contexto que ativa as duas — e
confere se a sugestão sai.

Resultado antes: o gatilho abria **280 vezes** e chegavam **zero** previsões.
Havia mais dois bloqueios, ambos DEPOIS do portão corrigido na v67:

```
255x  sem LSTM real
126x  modelo_desativado
```

## 1. `sem LSTM real`

```python
if modo == "GATILHO_OK" and not is_real_lstm:
    operavel = False
```

Um "sem LSTM, não opera" absoluto, que anulava por completo o caminho do
consenso sozinho. Agora só vale quando a sugestão de fato usa o LSTM
(`and not via_consenso`).

## 2. `modelo_desativado`

`modelo_ativo` rastreia se o LSTM vem batendo a baseline, e é desligado quando
não bate. Só que derrubava também sugestões que não passam por ele — uma
instalação cujo LSTM foi desligado alguma vez ficava muda **para sempre**,
mesmo com teorias provadas concordando.

O que **continua** barrando, para os dois caminhos: `ganho<0 vs baseline`,
`taxa~acaso_janela`, Brier alto. Esses medem desempenho real, não componente
ausente.

## Verificação

```
teste_funcional (condições construídas)
   antes:  gatilho 280x -> 0 previsões
   depois: gatilho 280x -> 122 previsões, modo OPERAR

guarda de honestidade (440 ciclos cada, teorias descobertas organicamente)
   ruído puro ...... 0 previsões     <- afrouxar não fez inventar
   com sinal ....... 0 previsões
   sombra do motor:  39,3% no ruído  vs  51,3% com sinal

suíte oficial ........... 74/74
test_fluxo_captura ...... FLUXO_TESTES_OK
test_honestidade_gates .. HONEST_TESTS_OK
```

## O que esperar ao vivo

A máquina está funcional de ponta a ponta — provado. Mas nos 440 giros do teste
orgânico, **duas teorias validadas concordando no mesmo número não aconteceu
nenhuma vez**. Silêncio por horas é resultado possível e não é defeito: o
software só fala quando tem evidência.

---

# v74 — a régua certa, e os aplicadores

Tudo aqui saiu da análise dos 607 giros REAIS coletados pelo usuário
(lightning 158, mega_fire 134, immersive 154, crazy_time 161).

## 1. A validação estava enfrentando o adversário errado

Nos dados reais, comparando teoria contra "apostar nos números mais quentes",
**na mesma quantidade de números e nas mesmas ativações**:

```
1553 ativações
  teorias ....... 31,6%
  régua ......... 35,7%
  só teoria acertou 112  |  só régua acertou 175  |  McNemar p=0,0002
```

As teorias estavam **10 pontos abaixo** do trivial, e isso não era sorte.

A causa: `_baseline_prospectivo` comparava a teoria com o **acaso teórico**
(k/|domínio|). A régua real só entrava a partir de 15 ativações
(`MIN_PAREADO_CONFIAVEL`), e 59% das teorias que chegavam ao mínimo de validação
nunca alcançavam isso. Dava pra "validar" perdendo feio pro óbvio.

Agora o baseline pareado entra **desde a primeira ativação**, com encolhimento
para o teórico (peso `PRIOR_PAREADO = 8`) — resolve o ruído de amostra pequena
que motivou o corte de 15, sem ignorar o adversário real:

```
m= 0  -> exige 2,7%   (o acaso)
m= 8  -> exige 20,1%
m=30  -> exige 32,1%  (a régua real)
```

## 2. Aplicadores (`aplicadores.py`)

Cinco lentes sobre o momento atual, votando com autonomia; a mesa exige
`MIN_APLICADORES_CONCORDES` lentes independentes por número.

```
A1 RECENCIA    o que acerta nas últimas ativações, não na vida toda
A2 VANTAGEM    quem está à frente da régua agora
A3 REGIME      desempenho em regimes parecidos com o atual
A4 ESTRUTURA   geometria da roda física (vizinhos, setor, finais)
A5 CONVERGENCIA onde as outras se encontram
A6 RACIOCINIO  o LLM configurado (opcional) — ver abaixo
```

**O registro das teorias NÃO é filtrado pela mesa.** A sombra continua sendo
gravada em toda ativação, para o histórico permanecer não-enviesado. Se a mesa
filtrasse, inflaria a taxa das teorias por construção e nunca se saberia se
escolher bem tem valor.

## 3. A6 e o teste de ruído

O A6 consulta o LLM de `llm_config.json` (Grok/xAI, OpenAI ou Ollama local).

Ele **não tem status especial**. Um LLM constrói explicação plausível inclusive
quando não há o que explicar — é o modo de falha que a sombra, o FDR e a régua
existem para pegar. Por isso ele vota como as outras lentes.

`teste_a6_ruido.py` alimenta o A6 com sequências aleatórias e mede quantas vezes
ele afirma ver padrão. O peso do voto sai daí:

```
até 10%   honesta — voto integral
10 a 30%  confabula às vezes — peso 0,5
acima 30% inventa padrão em ruído — não vota
```

Sem calibração ou sem chave, o A6 não vota. A mesa roda com as outras cinco.

## 4. O que os dados reais disseram sobre tudo isso

Caminhando giro a giro, cada modo contra uma régua **do mesmo tamanho**:

```
                    taxa    RÉGUA   aposta   pareado
lightning  TODAS   20,5%    18,8%    6,41    p=0,81
immersive  TODAS   24,8%    15,0%    6,25    p=0,035  ganha
mega_fire  TODAS   32,6%    17,4%    5,07    p=0,013  ganha
crazy_time TODAS   85,8%    85,8%    5,52    p=1,00

immersive  MESA    27,0%    18,9%    7,00    p=0,15
mega_fire  MESA    11,0%     5,5%    2,53    p=0,29
crazy_time MESA    73,3%    75,0%    3,45    p=0,80
```

**Cruzar todas as teorias cabíveis bateu a régua em 2 das 4 mesas.** Teoria
sozinha perde da régua; o cruzamento delas ganha. O sinal está na convergência.

**A MESA não superou o TODAS em nenhuma mesa.** As lentes, como estão
calibradas, não captam nada que o cruzamento simples já não capte. Precisam de
mais dados para calibrar — ou estão olhando para as coisas erradas.

Ressalva: 4 mesas × 2 modos = 8 comparações. Com correção para múltiplos
testes (0,05/4 = 0,0125), o mega_fire fica na linha e o immersive não
sobrevive. **Promissor, não comprovado.** O que decide é repetir num lote novo:
vício de roda física não some de um dia pro outro.

## Verificação

```
suíte oficial ........... 74/74 OK
test_controle_100 ....... OK (100 séries de ruído, 0 validações falsas)
compileall .............. OK
mesa sem LLM ............ roda normal
A6 sem chave ............ não vota, não derruba o ciclo
```

---

# v77 — caçadores de ocorrência e de anomalia

Dois times novos, com disciplina própria, nascidos de percepções do usuário.

## 19 CAÇADORES DE OCORRÊNCIA (`agentes_ocorrencia.py`)

Análise condicional — "dado que aconteceu X, a chance de Y muda?".

```
sequência (régua: reordenar, que desfaz a ordem e mantém a composição)
  O01 sucessor   O02 finais    O03 dúzia    O04 coluna   O05 cor
  O06 paridade   O07 setor     O08 salto    O09 espelho  O10 retorno
  O11 par ordenado   O12 vizinhos   O15 Voisins/Tiers/Orphelins
  O16 alto-baixo     O17 sextos     O18 quadras
  O20 rajada (sobredispersão)   O21 improvável que volta

roda desnivelada (régua: binomial contra a uniforme)
  O13 viés de número   O14 viés de setor   O19 viés de família da roda

canários (sem mecanismo físico — existem para denunciar falso positivo)
  C90 primo   C91 soma dos dígitos   C92 múltiplo de 3
```

### Três bugs meus que os testes pegaram

**1. Régua tornava aprovação impossível.** Com 300 reordenações o menor
p-valor é 1/301; o FDR sobre ~50 perguntas exige p≤0,002. Nada passava nunca —
o mesmo bug do piso de permutação já corrigido no crítico, repetido aqui.
Resolvido com triagem barata + refino fundo (4000) só para quem sobra.

**2. Só enxergavam sequência.** Vício de roda desnivelada é MARGINAL: certos
números saem mais no total. Reordenar preserva isso, então a régua do
embaralhamento é cega para o vício fisicamente mais plausível. Daí a segunda
família (O13/O14/O19) com régua binomial.

**3. Janela somada diluía o efeito.** Somar os 5 giros seguintes num número só
divide por 5 um efeito que age no giro imediatamente posterior. Detectava vício
plantado de 55% em apenas 16% dos mundos. Medindo cada distância (lag)
separadamente: detecta e ainda diz em qual distância.

### Crazy Time produzia lixo

`_ints()` descartava CoinFlip/CashHunt/Pachinko e sobrava uma sequência
mutilada de 1/2/5/10 que os agentes de roleta interpretavam como números,
aplicando setor e Voisins. **48 "achados" em 179 perguntas.**

Agora tem caminho próprio que conhece a roda real — 54 fatias, o "1" com 21
delas, o CrazyBonus com 1 — e cobra cada símbolo contra a fatia dele:

```
Crazy Time limpo ....... 0 achados   (antes: 48 falsos)
Crazy Time com vício ... CrazyBonus 2,83x  CashHunt 2,09x
```

## 12 CAÇADORES DO FORA DO PADRÃO (`agentes_anomalia.py`)

```
X01 surpresa         X02 deslocamento    X03 frio que acorda
X04 quebra           X05 improvável      X06 vazio
X07 salto anômalo    X08 contra maré     X09 órfão
X10 ruptura          X11 entropia        X12 silêncio quebrado
```

**X11 não usa p-valor nenhum** — entropia de Shannon e compressibilidade. É
outra forma de olhar, independente da máquina probabilística.

### DESCOBERTA ≠ CONFIRMAÇÃO

Defeito real do desenho anterior: com centenas de perguntas e FDR, um efeito
verdadeiro mas modesto era enterrado e sumia sem deixar registro. A correção
estatística estava sendo usada como carrasco.

Agora nada é descartado. Cada achado recebe um selo:

```
confirmado     sobreviveu à régua e ao controle de volume — pode virar sugestão
em_observação  aparece, ainda sem força — guardado
indício        tênue — guardado também
```

Ideia fraca hoje pode estar só esperando dado.

### O bug do aniversário

X05 "confirmava" que uma trinca apareceu 2x — nas TRÊS mesas reais. Era erro
meu: em 300 giros há 298 trincas sorteadas de 37³, e o esperado de repetições é
~0,88. **Ver uma trinca repetida é o normal.** Dava 0,63 confirmação falsa por
mundo de ruído. Corrigido para medir EXCESSO de repetições sobre o aniversário:
agora 0 falsos em 30 mundos.

## Leitura dos dados reais do usuário (963 giros)

```
              ocorrência          anomalia
mega_fire     360 perguntas, 0    0 confirmados, 8 indícios guardados
lightning     em processamento    0 confirmados, 1 em observação
immersive     em processamento    0 confirmados, 7 indícios guardados
```

Nada confirmado até agora — e os indícios ficam no banco, esperando volume.

## Verificação

```
suíte oficial ................... 74/74 OK
ruído puro, ocorrência .......... 12% de falso positivo
ruído puro, anomalia ............ 0 confirmado falso em 30 mundos
vício plantado de finais ........ detectado, com a distância certa
vício de bônus no Crazy Time .... detectado
canário no ruído ................ canta em ~1/6, funcionando como termômetro
entrada estranha ................ não quebra
```

---

# v78 — integração, e dois módulos que estavam desligados

## O que a auditoria de integração pegou

Os testes de unidade passavam. Os módulos funcionavam isolados. E **dois times
inteiros não estavam plugados em nada**:

```
31 caçadores (ocorrência + anomalia)  →  no pacote, nunca chamados
6 aplicadores (a mesa das lentes)     →  no pacote, nunca chamados
```

Rodariam inertes. Teste de unidade não pega isso — só teste de ligação pega.
Daí `auditoria_integracao.py`, que confere seis camadas: as famílias existem,
estão importadas por quem roda, falam durante um ciclo real, a META carimba,
o bus circula, e o motor recebe o que a academia produz.

Agora:
```
caçadores  → rodam a cada 15 ciclos, candidatos entram no pool final
aplicadores→ entram no consenso do motor como fonte própria (peso 2,2)
```

## Três "falhas" que eram do teste, não do software

A auditoria acusou `[Consenso]`, `[Hipóteses]` e `[Metacognição]` ausentes. Era
o teste passando STRING para o motor de roleta, que espera INT — ele saía por
"dados insuficientes" antes de chegar lá:

```
com STRING → ['Gatilho']                                      modo AGUARDANDO
com INT    → ['Consenso','Hipóteses','Metacognição','Gatilho'] modo SOMBRA
```

Mesmo erro que já tinha aparecido antes neste projeto. Corrigido, com o
comentário no código para não haver terceira vez.

## Os caçadores do fora do padrão: acham mesmo?

Faltava metade do teste. Estava provado que não inventam (0 falso em 30 mundos
de ruído) — não estava provado que acham. Um detector sempre calado também tem
0 falso positivo.

```
X01 surpresa concentrada .......... 25/25 (100%)
X02 deslocamento na roda .......... 25/25 (100%)
X07 salto dominante ............... 25/25 (100%)
X05 trincas além do aniversário ... 25/25 (100%)
X11 entropia baixa ................  0/25   (0%)  ← estava quebrado
```

**X11 media e calava.** Ele calculava a entropia certo, mas não tinha como
dizer "baixa demais": uma entropia de 5,12 não significa nada sozinha, porque
nem sequência uniforme de 300 giros atinge o máximo de 5,21.

Ganhou régua própria — a distribuição empírica da entropia em sequências
uniformes do mesmo tamanho, por simulação. Continua sem teste de hipótese, que
era o ponto dele:

```
ruído puro ......................... 12% (fica calado)
entropia baixa (8 números) ......... 100%
entropia moderada (20 números) ..... 100%
```

## Verificação final

```
suíte oficial ..................... 74/74 OK
fluxo de captura .................. FLUXO_TESTES_OK
portões de honestidade ............ HONEST_TESTS_OK
4 jogos ponta a ponta ............. 0 crash, 0 entrada rejeitada
auditoria de integração ........... 0 falhas, 1 aviso
   (o aviso é "nenhuma teoria validada" — correto em ruído puro)
bus ............................... 4 tipos de mensagem circulando
detecção dos caçadores ............ 100% nos 5 vícios plantados
falso positivo em ruído ........... 0 a 12% conforme o agente
```
