# LOTERIA

Software de loteria com três regras que não se dobram: **o acaso é calculado
exato**, **toda afirmação diz o que a derrubaria**, e **garantia só se entregue
provada**.

## Abra o ABRIR.bat. Só esse.

Ele liga o programa e abre a tela no seu navegador. Tudo está lá dentro:

- **as loterias em abas** no topo — Mega-Sena, Quina, Lotofácil e as outras
- **o que fazer na lateral** — seis telas, na ordem em que se usa
- **explicação em cada tela**, dizendo o que aquilo faz e o que aquilo não faz

O programa roda inteiro no seu computador. Nada é enviado para lugar nenhum — o
navegador é só a maneira de desenhar a tela. Para fechar, feche a janela preta
que abre junto.

> **Por que no navegador e não numa janela comum?** Por causa da acessibilidade.
> No navegador funcionam leitor de tela, zoom, contraste alto do Windows e
> navegação só por teclado — tudo testado por milhões de pessoas. Numa janela
> feita à mão, nada disso funciona direito. A tela foi auditada com a ferramenta
> `axe` nas seis seções: **zero violações** de WCAG 2.1 AA.

As seis telas:

| | |
|---|---|
| **1. Começar aqui** | o que é a loteria, o acaso exato, quanto custa cada tamanho de aposta |
| **2. Resultados** | busca os concursos já sorteados e guarda no seu computador |
| **3. Formular jogos** | quatro inteligências montam jogos, cada uma citando o que a autoriza |
| **4. Fechamento** | escolha dezenas no quadro e receba apostas com garantia provada |
| **5. Conferir sorteio** | saiu o resultado? confere as apostas e audita a promessa |
| **6. O que o software sabe** | tudo o que ele afirma, e o que derrubaria cada coisa |

Quem quiser linha de comando encontra tudo na pasta `avancado`.

---

## O que ele faz

```
python JOGAR.py                          as loterias e o acaso de cada uma
python JOGAR.py mega_sena                o acaso e o custo, por tamanho de aposta
python JOGAR.py mega_sena --dezenas "3 7 12 19 24 31 38 45 52 58 11 27" --salvar
                                         o fechamento, com a garantia provada e salva
python JOGAR.py mega_sena --formular     as inteligências formulam jogos citando a base
python JOGAR.py mega_sena --apostas dados/apostas_mega_sena.txt --sorteio "4 18 29 33 47 52"
                                         confere as apostas e AUDITA a promessa
python PUXAR.py mega_sena --ultimo       testa a API com uma chamada só
python PUXAR.py mega_sena                puxa o histórico da API para o disco
python JOGAR.py mega_sena --historico dados/mega_sena.json
                                         mede as crenças de loteria nos seus dados
python PAINEL.py                         a tela (o mesmo que o ABRIR.bat faz)
python JOGAR.py --base                   o que o software sabe, e o que o derruba
```

### O acaso, exato

A chance de uma aposta de 7 dezenas acertar a sena não é estimativa: é
`C(7,6)/C(60,6)`, um número. Isso deixa a régua mais afiada do que qualquer
coisa que eu tenha construído antes — toda teoria pode ser medida contra o
número certo.

E daí sai uma coisa que eu **escrevi errado na primeira versão** e a aritmética
corrigiu: a chance da faixa máxima **por real gasto é rigorosamente constante**
em todo tamanho de aposta — 1,997449e-08 na Mega-Sena, do 6 ao 15. Uma aposta de
k dezenas custa C(k,6) apostas mínimas e concorre com exatamente essas C(k,6)
combinações. Aposta grande não compra vantagem nenhuma; compra outra *forma* de
gastar o mesmo dinheiro. O que cai com k é a chance de ganhar **alguma** coisa.

### O fechamento — a coisa real deste software

> "Escolhi 12 dezenas. Se 5 delas saírem, quantas apostas garantem uma quadra?"

Resposta medida: **15 apostas**, contra 924 de cobrir tudo. Mesma garantia, 909
apostas de economia. E "garantia" aqui é literal — a prova percorre **todos** os
792 casos possíveis, nunca uma amostra, porque um único caso descoberto derruba a
promessa inteira. Quando não dá para conferir tudo dentro do teto, o software
**recusa** em vez de afirmar.

Isto não aumenta a chance das suas dezenas saírem. Converte acerto parcial em
prêmio com certeza, e dá para verificar antes de gastar um real.

### As inteligências — quem formula, cita

O pedido original: *"as inteligências irem consultando a base pra formular os
jogos"*. São quatro, sobre o mesmo material, e a regra é o portão do outro
software: **inteligência sem item da base que a autorize fica calada** — e item
derrubado pela medida cala quem o citava, na tela, com o motivo.

| | cita | |
|---|---|---|
| **Anti-partilha** | M01, P01 | evita datas e sequências: não muda a chance, muda com quantos divide |
| **Atrasadas** | C01 | só fala se C01 sobreviver à medida; sem histórico, calada |
| **Quentes** | C02 | idem, pelo item dela |
| **Aleatória** | M01 | o controle: pela chance, empata com todas — é a régua delas |

Cada jogo sai com a citação e o estado do item (demonstrado / confirmado / sem
medida / derrubado), a semente para reproduzir, e os avisos no corpo. A chance é
idêntica nos quatro (M01); o que difere é o **motivo**, e o motivo está citado.

### A conferência — onde a promessa encontra o sorteio

`--salvar` grava as apostas do fechamento **junto com a promessa** ("se 5
saírem, garanto 4"). No dia do sorteio, `--sorteio` confere cada aposta e
**audita a garantia**: a condição aconteceu? a promessa foi honrada? Se algum
dia a resposta for "não", isso é defeito provado no meu fechamento, dito na
tela — o auditor sabe desmentir, e o teste prova que sabe.

### A medida — o que os seus dados dizem

Cada crença de loteria (atrasadas, quentes, soma, par/ímpar, partilha) é medida
**andando para frente**: em cada concurso, o atraso e a frequência saem só dos
concursos anteriores, e a aposta é conferida no seguinte. Usar a amostra inteira
para escolher e depois medir na mesma amostra faz qualquer coisa parecer que
funciona.

São três respostas possíveis, e a terceira é a que mais me custou aprender:

| | |
|---|---|
| **confirmado** | a medida excluiu o acaso |
| **derrubado** | aconteceu o que o próprio item declarou como sua queda |
| **sem base** | o `n` não dá para dizer nem uma coisa nem outra |

No outro software eu escrevia "não se sustentou" com pouco dado — e com pouco
dado o intervalo é largo, engole o acaso quase sempre, e o software "derruba"
tudo o que olha. Não medir e não achar viravam a mesma tela. Agora, antes de
derrubar, o medidor pergunta se o `n` daria para **notar** o efeito. Se nem
isso, a resposta é *sem base*.

---

## O que ele não faz, e não vai fazer

**Não diz quais dezenas vão sair.** Num sorteio de bolas honesto isso não existe,
e uma tela que fingisse saber estaria mentindo com número — que é a mentira mais
convincente que existe.

O que existe de real é o fechamento (eficiência **provada**) e a partilha do
prêmio (P01: dezenas pouco jogadas não mudam a chance de acertar, mudam com
quantos você divide). Essas duas eu construo com prazer.

---

## O estado honesto, hoje

**As regras não foram conferidas contra a Caixa.** Escrevi as oito loterias de
memória, e não pude conferir de onde eu escrevo o código: a rede de lá recusa a
saída. E não é sobre a Caixa — as APIs do seu outro software (`api.tracksino.com`,
`api-cs.casino.org`), que funcionam na sua máquina todo dia, são recusadas do
mesmo jeito. De lá só passam GitHub e repositório de pacote.

O software, porém, roda na **sua** máquina, e lá a API responde. Por isso o
puxador existe (`PUXAR.py`) e foi provado contra um servidor local que fala o
formato do portal da Caixa. O que eu não pude provar é que a API real fala esse
mesmo formato — e é a sua primeira execução com `--ultimo` que mostra isso, em
uma chamada, antes de gravar nada.

Por isso nenhum jogo nasce `conferido`, e o software confere sozinho assim que
você passar um arquivo com `--historico`. Regra errada não dá erro — dá número
plausível e falso, que é pior.

**Nenhum item foi medido nos seus dados ainda**, pelo mesmo motivo: não há dados
ainda. O que está provado é que o **medidor** funciona, e isso foi provado dos
dois lados:

- num sorteio uniforme que eu gerei, ele **não** acha vantagem em atrasada,
  quente, soma nem par/ímpar — como não pode achar;
- num sorteio que eu **viciei de propósito**, ele acha: 0,2439 contra 0,1000 de
  acaso, intervalo inteiro acima.

A segunda metade é a que importa. Um medidor que só sabe dizer "não" acerta em
sorteio honesto por acidente, e o "não se sustentou" dele não vale nada.

E há uma trava contra mim mesmo: **histórico sintético nunca grava veredito na
base**. Os meus testes fabricam sorteios; sem essa trava, um deles poderia
escrever "C01 confirmado" na sua base com número que eu inventei, e você leria
como achado nos seus dados. Seria uma mentira de boa-fé, que é como as piores
acontecem.

---

## Como sair daqui

1. `python PUXAR.py mega_sena --ultimo` — uma chamada só. Ela mostra todos os
   campos que a fonte devolveu e o que eu entendi deles. Se o endereço for
   outro, `python PUXAR.py --fonte "https://…"` e tente de novo.
2. `python PUXAR.py mega_sena` — puxa o histórico (leva minutos; retoma de onde
   parar se cair).
3. **Confira o diagnóstico.** Se o que eu li não for o que está na fonte, pare:
   toda medida depois sairia de leitura errada, e sairia com cara de certa.
4. `python JOGAR.py mega_sena --historico dados/mega_sena.json` — as regras
   ficam conferidas e os cinco itens ganham veredito nos **seus** dados.

Depois disso, as suas teorias entram na base. A exigência é a mesma de todas as
outras — dizer o que as derrubaria. Não é desconfiança da sua teoria: é o que faz
a **confirmação** valer alguma coisa quando ela vier. Uma afirmação que nada pode
derrubar também não pode ser confirmada; ela só pode ser repetida.

---

## Os arquivos

| | |
|---|---|
| `ABRIR.bat` | **o que você abre** |
| `PAINEL.py` | a tela, e o servidor que roda só na sua máquina |
| `painel/` | o desenho da tela (HTML, estilo, comportamento) |
| `JOGAR.py` | o mesmo software por linha de comando |
| `NUCLEO/regras.py` | as oito loterias e a probabilidade exata |
| `NUCLEO/fechamento.py` | as apostas com garantia, e a prova exaustiva |
| `NUCLEO/base_conhecimento.py` | o que o software sabe, e o que derruba cada coisa |
| `PUXAR.py` | puxa os resultados da API e guarda no disco |
| `NUCLEO/api.py` | o cliente da fonte, com o endereço configurável |
| `NUCLEO/historico.py` | a porta de entrada dos sorteios reais |
| `NUCLEO/estatistica.py` | a régua: Wilson, qui-quadrado, permutação |
| `NUCLEO/medidor.py` | mede cada item, andando para frente |
| `NUCLEO/formular.py` | as inteligências que formulam citando a base |
| `NUCLEO/conferencia.py` | confere apostas e audita a promessa do fechamento |
| `test_loteria.py` | 12 seções, 137 checagens, incluindo as destrutivas |
