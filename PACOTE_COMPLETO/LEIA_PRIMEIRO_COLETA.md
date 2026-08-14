# Como rodar e me mandar os dados

## 1. Instalar (só na primeira vez)

```
DIAGNOSTICO.bat              acha o Python e instala o essencial
0_INSTALAR_DEPENDENCIAS.bat  o resto (torch é opcional, pode falhar sem problema)
```

Se o Python não for encontrado, o `DIAGNOSTICO.bat` diz exatamente o que fazer.

## 2. Semear com histórico (opcional, 1 minuto)

```
PUXAR_HISTORICO.bat
```

Traz o que a API tiver de giros passados, para o software já começar com
contexto em vez de do zero. Não é obrigatório — só acelera.

## 3. Rodar

```
ABRIR_TUDO.bat
```

Abre as quatro mesas, a academia, o assistente e a central.

**Cada jogo coleta os giros sozinho enquanto roda.** Não existe coletor
separado: a captura é parte do ciclo normal de cada combo. Deixe as janelas
abertas o tempo que quiser.

O que olhar em cada janela:

```
[Academia/consulta] validados=N     teorias que já se provaram ao vivo
[Consenso] cabíveis agora: N        quantas se aplicam ao giro atual
[Gatilho] consenso sozinho          o caminho novo disparou
[LSTM] SEM MODELO TREINADO          normal sem torch, não bloqueia nada
```

## 4. No fim, me mandar

Feche as janelas e rode:

```
EXPORTAR.bat
```

Gera `coleta_completa.zip` com três coisas:

```
historicos_reais.json    os giros
motor/                   cada previsão + acertou/errou + o que a régua faria
academia/                as teorias e a sombra ao vivo de cada uma
```

Mande esse zip.

---

## Quanto tempo vale a pena deixar

Uma mesa gira a cada ~45 segundos: ~80 giros por hora, ~320 por hora com as
quatro abertas. O buffer guarda até 20.000 por mesa, então dá pra rodar dias
sem perder o começo.

Com 607 giros (a primeira coleta), o cruzamento de teorias bateu a régua de
frequência em 2 das 4 mesas — mas com margem que ainda cabe na sorte. O que
transforma isso em resultado é **repetir num lote novo**. Algumas horas a mais
mudam a conclusão de "promissor" para "comprovado" ou "era sorte".

## Se quiser ligar a sexta lente (A6)

Ponha sua chave em `llm_config.json` e rode uma vez:

```
python teste_a6_ruido.py
```

Ele mede quantas vezes o LLM afirma ver padrão em sequência aleatória, e o peso
do voto dele sai daí. Sem isso, ele não vota e a mesa roda com as outras cinco.
