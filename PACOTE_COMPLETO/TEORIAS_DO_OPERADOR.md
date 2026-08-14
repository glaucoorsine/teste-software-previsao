# As teorias do operador — recuperadas das mensagens

Tudo que ele me ensinou, recuperado das conversas. Cada uma está escrita com o
mecanismo, os exemplos dele nas palavras dele, e o estado da medição.

Isto existe porque teoria que só vive no chat se perde. Aqui ela vira coisa
declarada, com nome, que pode ser testada e cobrada.

---

## ROLETA

### T1 — Família de finais
> *"final 4,5,9 — Exemplo: veio o 25 pode vir tipo o 34 o 15, entendeu?"*

As três famílias, do print do Mega Fire dele:

```
(0, 1, 3, 6)      (0, 2, 7, 8)      (4, 5, 9)
```

Saiu um número, o próximo tende a ter final da mesma família. O zero pertence
a duas famílias — e nos exemplos dele as duas valem.

**Exemplos que ele deu (15/08):**

| veio | depois | família |
|---|---|---|
| 20 | 2 | (0,2,7,8) — final 0 e final 2 |
| 1 | 21 | (0,1,3,6) — final 1 e final 1 |
| 25 | 34, 15 | (4,5,9) |
| 31 | 11, 13, 21, 26 | (0,1,3,6) |

**Medido** (histórico dele, giro seguinte, régua de embaralhamento):

```
immersive   1777 giros   43,3%  acaso 41,0%   1,06x   p=0,021
mega_fire    291 giros   43,0%  acaso 39,7%   1,08x
lightning   1299 giros   40,3%  acaso 40,8%   0,99x
```

**Estado:** é o resultado mais encorajador que apareceu. Não fecha sozinho
depois de corrigir por todos os testes feitos, mas foi declarado antes, não
foi pescado. Merece teste ao vivo.

---

### T2 — A família é o candidato, não a aposta
> *"As famílias são enormes. Mas a análise é da IA. Na mesclagem de teorias há
> o consenso sobre o que jogar."*

A família dá os candidatos; o cruzamento com as outras teorias escolhe quais
jogar. **Não é a IA que corta a família por conta própria — é o consenso.**

**Erro meu, corrigido em 15/08:** eu cortava a família para 7 números pela
"faixa quente" antes da votação. Medido, o corte piorava tudo:

```
             família crua    com o meu corte
immersive       1,06x            1,02x
mega_fire       1,08x            0,92x
```

Agora a família inteira entra na votação e quem estreita é o consenso.

---

### T3 — Contexto de faixa
> *"tá vindo muitos de 0-10, veio o 14 por exemplo, então vou jogar 4,5,9"*

A faixa que está saindo muito informa qual parte da família olhar.

**Estado:** implementado como H4. Medido isoladamente, **piora** o resultado
da família crua. Continua votando como voz separada com peso menor, para dar
para comparar as duas ao vivo — mas hoje a evidência é contra.

---

### T4 — Vizinhos na roda
> *"21 e veio 25 (19 21 23 25 37 32)"*

O próximo cai perto do anterior na ordem FÍSICA do prato, não na mesa.

**Medido:**

```
                    até 2 casas        até 4 casas
lightning              0,89x              1,00x
immersive              0,97x              0,97x
mega_fire              0,75x              0,87x
```

**Estado:** não aparece. Nenhuma mesa acima do acaso.

---

### T5 — Consenso entre as IAs
> *"as ias com todas suas teorias vão chegar no consenso sobre o que realmente
> jogar"*

**Estado:** é a arquitetura do software desde então. Em 15/08 virou o único
critério (`CONSENSO_PURO = True`), por decisão dele.

---

### T10 — A tabela de transições, número por número
> *"Mais alguns que eu percebi, eles vêm com muita frequência, eu sei de
> cabeça, vou te passar. Quando vem um, aí vem o três e o sete, ou três ou
> sete ou um de novo. Quando vem o dois, vem o quatro..."*
> (áudio de 14/08, 00:42)

E a correção de tempo, que ele fez depois e muda tudo:

> *"não vem na hora, no mesmo momento, vem, às vezes vem três, quatro, três
> depois. Não é no mesmo momento, não é um em seguida do outro"*

Por isso cada regra é medida em janela de 1, 3 e 5 giros, não só no giro
seguinte.

| veio | vem | | veio | vem |
|---|---|---|---|---|
| 1 | 3, 7, 1 | | 19 | 19, 21, 23, 32, 27, 30, 25 |
| 2 | 4 | | 22 | 20, 17 |
| 3 | 1, 2, 3 | | 23 | igual ao 19 |
| 4 | 2 | | 24 | 29 |
| 5 | 9 | | 25 | igual ao 19 |
| 6 | 6, 8, 18 | | 26 | 28 |
| 7 | 1 | | 29 | 30 |
| 8 | 6, 8, 18, 0 | | 30 | todos os 30 (30–36) |
| 9 | 5 | | 31 | 33, e os outros 30 |
| 10, 11, 13, 15 | 10, 11, 13, 15 | | 32 | igual ao 19 |
| 12 | 17 | | 33 | igual ao 31 |
| 14 | 16, 18, 12 | | 34 | 36 |
| 16 | 14 | | 35 | todos os 30 |
| 17 | 20, 12 | | 36 | igual ao 34 |
| 18 | 6, 8, 18 | | | |

**Medido** — tabela inteira, por mesa:

```
              janela 1        janela 3        janela 5
lightning     1,01x           1,00x           0,97x
immersive     1,00x           0,96x           0,92x
mega_fire     1,24x           1,05x           0,97x
```

No Lightning e no Immersive juntos são 2667 ativações — amostra de sobra. A
tabela **como um todo** dá no acaso ali. O Mega Fire dá 1,24x, mas com 247
ativações e p=0,060.

**Medido — regra por regra**, nos 3367 giros somados das três mesas:

```
regra           janela  acertos    taxa   acaso   razão        p
29 → 30            1     8/84      9,5%    2,7%   3,52x   0,0020
29 → 30            3    15/84     17,9%    7,9%   2,26x   0,0023
29 → 30            5    19/84     22,6%   12,8%   1,77x   0,0090
19 → 19,21,23…     1    22/79     27,8%   18,9%   1,47x   0,034
10 → 10,11,13,15   5    51/96     53,1%   43,6%   1,22x   0,038
9 → 5              1     6/93      6,5%    2,7%   2,39x   0,041
17 → 20,12         3    20/89     22,5%   15,4%   1,46x   0,048
16 → 14            5    16/91     17,6%   12,8%   1,37x   0,116
```

**O achado:** `29 → 30`. Ela aparece nas três janelas e **decai na ordem
certa** — 3,52x, 2,26x, 1,77x. É o formato de efeito real: quanto mais perto
do gatilho, mais forte. Ruído não costuma se comportar assim.

Depois de corrigir por 96 testes (32 regras × 3 janelas), nenhuma fecha
sozinha. Mas a média da tabela esconder as boas é exatamente por isso que se
testa regra por regra.

**Estado:** a tabela passou a votar no consenso ao vivo em 15/08, com peso
1,6. Ela existia no pacote desde antes, era avaliada pela academia, mas os
candidatos dela nunca chegavam à votação — passavam pelo filtro de validação
que engolia tudo. Era conhecimento dele guardado numa gaveta.

---

## CRAZY TIME E MULTIPLICADORES

As quatro, nas palavras dele (14/08):

> *"No crazy time quando demora pra vir o 10 e de repente vem, logo depois ele
> sai de novo. Quando vem dois 10 ou dois bônus juntos, logo depois sai mais.
> Eu usando vem muito CashHunt junto logo vem crazy time. Quando fica saindo
> muito um número, normalmente ele vem multiplicado. São muitas que já
> percebi."*

### T6 — O 10 que demora, quando vem, sai de novo
> *"quando demora pra vir o 10 e de repente vem, logo depois ele sai de novo"*

Não é sobre multiplicador: é sobre o **símbolo 10** voltar logo depois de
quebrar uma seca longa.

**Estado:** não medido ainda — 393 giros de Crazy Time é pouco para isolar as
secas do 10.

### T6b — Seca longa puxa multiplicador alto, e vêm mais
> *"depois de uma seca longa aparece um multiplicador alto, e aí vêm mais"*

**Estado:** amostra curta ainda (393 giros).

### T7 — Dois 10 ou dois bônus juntos puxam mais
> *"Quando vem dois 10 ou dois bônus juntos, logo depois sai mais"*
> *"dois números iguais → multiplicador no próximo"*

**Medido:** 0,314 contra 0,277 de acaso — **1,14x, p=0,152**. Não fecha, mas
está na direção certa. É a percepção dele com melhor sinal no Crazy Time.

### T8 — CashHunt junto puxa Crazy Time
> *"vem muito CashHunt junto logo vem crazy time"*

**Estado:** não medido — precisa de mais bônus no histórico. Com 393 giros há
poucos CashHunt para formar aglomerado.

### T9 — Número que sai muito vem multiplicado
> *"Quando fica saindo muito um número, normalmente ele vem multiplicado"*

**Estado:** não medido isoladamente ainda. É das mais testáveis assim que
houver histórico — basta cruzar frequência recente do símbolo com o
multiplicador do giro.

> *"São muitas que já percebi"* — ele disse. Então esta lista ainda não está
> fechada.

---

## O QUE FALTA MEDIR

- **T6, T8, T9** — dependem de mais histórico de Crazy Time.
- **Top slot** — quantas vezes bate, e em qual símbolo. O símbolo passou a ser
  guardado em 15/08; antes ia fora. Dado virgem.
- **Casino Scores** — o site traz Setor, Vizinhos de Zero e Dúzia prontos, com
  411 giros em 6 horas numa mesa. Não estamos minerando.

---

## COMO UMA TEORIA VIRA APOSTA AQUI

1. Ele descreve. Eu escrevo o mecanismo **antes** de olhar o resultado.
2. Mede-se no histórico, com a régua certa: embaralhamento para hipótese de
   sequência, sorteio de roda justa para hipótese de contagem.
3. Corrige-se pelo número total de hipóteses testadas.
4. O que sobrevive vai para a sombra ao vivo, sem valer aposta.
5. Só depois vira voto no consenso.

O passo 3 existe porque procurando o bastante sempre se acha alguma coisa. O
passo 4 existe porque achado em histórico é candidato, não conclusão.
