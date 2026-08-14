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

## CRAZY TIME E MULTIPLICADORES

### T6 — Seca longa puxa multiplicador alto, e vêm mais
> *"depois de uma seca longa aparece um multiplicador alto, e aí vêm mais"*

**Estado:** amostra curta ainda (393 giros). Precisa de mais história.

### T7 — Dois iguais puxam multiplicador
> *"dois números iguais → multiplicador no próximo"*

**Medido:** 0,314 contra 0,277 de acaso — **1,14x, p=0,152**. Não fecha, mas
está na direção certa. É a percepção dele com melhor sinal no Crazy Time.

### T8 — Aglomerado de CashHunt puxa CrazyBonus
> *"cluster de CashHunt → CrazyBonus"*

**Estado:** não medido ainda — precisa de mais bônus no histórico.

### T9 — Número que repete vem multiplicado
> *"número repetindo vem multiplicado"*

**Estado:** não medido isoladamente ainda.

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
