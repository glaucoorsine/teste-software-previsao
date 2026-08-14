# Por onde começar

## Abra um arquivo só: `CENTRAL.bat`

Na primeira vez ele pergunta **como você quer ser avisado no celular**, antes
de abrir qualquer coisa. Escolhe, testa ali mesmo, e entra. Da segunda vez em
diante vai direto pro laboratório.

Depois disso, tudo está em uma janela: as quatro mesas rodando ao mesmo tempo,
os agentes da academia e o que as IAs estão conversando. A aba de cima escolhe
o que aparece.

### As abas

| Aba | O que tem |
|---|---|
| **Painel** | As quatro mesas em cartões: sinal, placar e estado. É a tela pra bater o olho e ver onde tem entrada. |
| **Lightning / Mega Fire / Immersive / Crazy Time** | A mesa inteira: sugestão, janela aberta, placar, histórico, o que as IAs disseram nesta volta e a academia daquela mesa ao vivo. |
| **IAs** | Os agentes da academia, um a um: tipo, estado, tamanho da amostra e o que cada um achou. Troca de mesa no menu. |
| **Conversa** | O que as quatro estão fazendo agora, mais recente primeiro. Atualiza sozinho a cada 5 segundos. |
| **Progresso** | Quanto histórico já foi juntado e o que as teorias estão acumulando. |
| **Fontes** | O que cada site está devolvendo. |
| **Avisos** | O canal configurado, um teste na hora, e o botão de trocar de canal. |

### Sobre o aviso no celular

O **ntfy** é o mais simples: instale o app, assine o tópico, pronto. Sem
cadastro, sem bot, sem apikey. O tópico é sorteado pra você — e o alfabeto
não tem `0/O` nem `1/l`, porque você vai digitar esse nome à mão e um
caractere ambíguo ali vira uma hora procurando por que o aviso não chega.

O ntfy tem **dois lados**: trocar o nome no software não muda o que o
aplicativo escuta. Se você não assinar no app, nada chega e nada avisa que
falhou. Por isso a tela de abertura manda um teste de verdade — se chegou no
celular, está provado.

### A primeira volta demora

Cada mesa carrega academia, teorias e modelos antes da primeira resposta:
cerca de um minuto por mesa, e elas sobem escalonadas pra não brigarem pelo
processador. Da segunda volta em diante é instantâneo. Enquanto isso a aba
mostra *"preparando o cérebro (primeira volta)"* — é isso, não é travamento.

### AGUARDANDO não é defeito

Quando a faixa diz **AGUARDANDO — evidência insuficiente**, é o software
dizendo que naquele momento não vale entrar. Ele procura o *momento* de
prever; não é pra mostrar número toda hora. A sombra segue rodando por trás
medindo tudo — o que chega na tela é só o que passou no corte.

### Antes da primeira vez

1. `0_INSTALAR_DEPENDENCIAS.bat` — uma vez só.
2. `CENTRAL.bat` — ele cuida do resto, inclusive do aviso no celular.

Os `.bat` numerados continuam funcionando, caso você queira abrir uma mesa
sozinha num monitor. Pro dia a dia, `CENTRAL.bat` resolve.

### Conferindo se está tudo de pé

```
python test_central.py       a janela, a conferência de acerto, a tela de abertura
python test_notificador.py   o aviso saindo com números, janela e taxa
python test_fluxo_captura.py a captura e o histórico
```
