# LYRA LIVE

Software de transmissão ao vivo para a câmera Lyra: filtros, embelezamento,
desfoque de fundo e uma IA que acompanha a live e avisa quando algo sai do lugar.

```
0_INSTALAR_LYRA.bat     instala tudo
DIAGNOSTICO.bat         diz o que está instalado e o que falta
1_ABRIR_LYRA.bat        abre o painel
```

---

## As duas formas de o YouTube reconhecer este software

Não é preciso escolher — as duas podem ficar ligadas ao mesmo tempo.

### 1. Como codificador de transmissão (RTMP)

É o que "software de live" quer dizer. No YouTube Studio, em **Transmitir ao vivo
→ Configurações da transmissão**, há uma URL de ingestão e uma chave. Cole a
chave no painel, marque *Transmitir para o YouTube* e ligue a câmera. Do lado do
YouTube aparece "recebendo dados" e o botão de transmitir libera.

Não há cadastro, aprovação nem SDK: quem fala RTMP no formato certo é aceito.

### 2. Como câmera do sistema (webcam virtual)

Marque *Publicar como câmera do sistema*. A partir daí **Lyra Live** aparece na
lista de câmeras de qualquer programa — inclusive na opção **Webcam** do YouTube
Studio no navegador, e também no Meet, Zoom e Teams. O que sai por ali é a Lyra
**com** os filtros já aplicados.

Para isso funcionar, o dispositivo virtual precisa existir no sistema:

| Sistema | O que instalar |
|---|---|
| Windows | OBS Studio (uma vez; não precisa abrir depois) |
| macOS | OBS Studio |
| Linux | `sudo modprobe v4l2loopback devices=1 card_label='Lyra Live' exclusive_caps=1` |

---

## Qual é a sua Lyra

O software aceita as duas formas sem você precisar saber qual é a sua:

| Como ela se conecta | O que colocar no campo Câmera |
|---|---|
| Cabo USB (aparece como webcam) | o número: `0`, `1`, `2`… — o botão **Procurar** acha |
| Wi-Fi / rede (RTSP ou HTTP) | a URL inteira: `rtsp://192.168.0.50:554/live` |
| Sem câmera, só para testar | `sintetica` |

Pela linha de comando, `python lyra.py --listar-cameras` mostra os índices que
existem.

---

## Os filtros

**Looks prontos**: `natural`, `estudio`, `quente`, `frio`, `cinema`, `vintage`,
`pb`, ou `nenhum`. A intensidade de cada um vai de 0 a 100.

**Embelezamento** — dois controles, e nenhum deforma o rosto:

- *Suavizar pele*: uniformiza a pele sem apagar os traços. Usa uma máscara de
  pele por crominância (funciona em qualquer tom de pele) e um filtro guiado, que
  preserva borda por construção — cílio, sobrancelha e canto de boca continuam
  nítidos. Parte do detalhe original é devolvida no fim, que é o que impede o
  aspecto de cera.
- *Uniformizar tom*: tira mancha de cor mantendo a sombra que dá volume ao rosto.

**Ajuste fino**: brilho, contraste, saturação, temperatura, nitidez e vinheta.

Em 0, cada efeito devolve o quadro **byte a byte igual** ao que entrou — isso é
testado, não é força de expressão.

---

## O desfoque de fundo

Três formas de achar a pessoa. O software usa a melhor que a sua máquina
permitir, e o painel diz qual está em uso:

1. **mediapipe** — a rede de selfie. Melhor recorte, aceita a câmera se mexendo.
   Só se estiver instalado (`pip install mediapipe`).
2. **Fundo aprendido** — sem rede nenhuma. Você sai do quadro, clica em
   **Aprender fundo**, e o que difere do fundo memorizado passa a ser você. Para
   quem transmite sentado com a câmera parada, recorta tão bem quanto a rede.
   Não mova a câmera depois de aprender.
3. **Central** — último recurso. Desfoca as bordas com uma elipse suave. **Não é
   recorte de pessoa**, e o painel diz isso: fica bom em plano fechado e erra
   quando você anda para o lado.

Além de desfocar, dá para trocar o fundo por uma **imagem** ou por uma **cor**
sólida.

---

## A IA supervisora

Ela acompanha a transmissão do começo ao fim e avisa quando algo muda. A divisão
de trabalho é deliberada e não se inverte:

```
métricas medidas  ->  regras determinísticas  ->  achados  ->  Qwen escreve por cima
```

**As regras são quem mede.** Elas comparam números contra limites: fps abaixo do
alvo, filtro estourando o orçamento de 33 ms por quadro, quadros descartados,
codificador atrasado, taxa de envio abaixo da configurada, câmera reconectando,
imagem escura ou estourada. Cada achado carrega o número que o gerou e o que
fazer a respeito.

**O Qwen só redige.** Ele recebe os achados já prontos — nunca métrica solta — e
transforma em uma ou duas frases diretas. Ele não mede, não decide gravidade e
não tem como inventar problema, porque não vê os dados crus.

**Sem o Qwen instalado, a supervisão continua inteira**, só sem o texto
explicativo. O painel mostra os fatos em cima e a leitura da IA embaixo,
identificada — se o modelo escrever bobagem, dá para ver na hora que o número diz
outra coisa.

Para ligar o modelo (opcional):

```
ollama pull qwen2.5:0.5b
```

São cerca de 400 MB e roda no processador, sem placa de vídeo. O modelo é
pequeno de propósito: a tarefa dele é redigir, não raciocinar sobre a live.
Dá para trocar por `qwen3:0.6b` ou `qwen2.5:1.5b` no painel. Qualquer servidor
que fale a API da OpenAI (llama.cpp, LM Studio, vLLM) também serve — basta
apontar o endereço.

---

## Linha de comando

```
python lyra.py --diagnostico                    o que está instalado
python lyra.py --listar-cameras                 câmeras visíveis
python lyra.py --teste                          prova a esteira sem câmera
python lyra.py --camera 0 --transmitir          transmite para o YouTube
python lyra.py --camera 0 --camera-virtual      publica como webcam
python lyra.py --camera rtsp://IP/live --transmitir --look cinema --embelezamento 60
```

A chave vem de `--chave`, da variável de ambiente `LYRA_CHAVE` ou do arquivo
salvo pelo painel — nessa ordem. **Ela nunca é impressa na tela nem gravada em
log**: a linha de comando do ffmpeg que aparece em mensagem de erro sai com a
chave mascarada, porque é exatamente esse tipo de linha que se cola num print
pedindo ajuda.

---

## Onde ficam as configurações

`Documentos/LyraLive/`

- `perfil.json` — todos os ajustes de imagem, câmera e IA.
- `chave_transmissao.txt` — a chave, sozinha, com permissão restrita ao dono.

A chave fica **fora** do perfil de propósito: perfil é o arquivo que se manda
para outra pessoa quando se quer copiar uma configuração de imagem, e mandar a
chave junto é entregar o canal.

---

## Desempenho

O orçamento é 33 ms por quadro a 30 fps — para tudo: captura, filtros, fundo e
codificação. Para caber:

- Todo o ajuste de cor (brilho, contraste, temperatura, saturação, look) é
  **compilado numa tabela de 256 níveis** quando o slider muda, e aplicado com um
  `LUT` por quadro. Dez efeitos empilhados custam o mesmo que um.
- O embelezamento colapsa em `quadro * A + B`, com `A` e `B` calculados em 1/4 da
  resolução — máscara de pele inclusive — e ampliados.
- O fundo é borrado em 1/4 da resolução e a composição é feita em 8 bits.
- A vinheta é a mesma matriz sempre; fica em cache.

`TESTAR_SEM_CAMERA.bat` mede o que a sua máquina aguenta e já diz o diagnóstico.

Se o painel acusar *"Os filtros não cabem no tempo de um quadro"*, na ordem:
baixe a resolução, reduza o embelezamento, escolha o codificador da placa de
vídeo (NVENC/QuickSync), troque o recorte de fundo por *fundo aprendido*.

---

## Quando alguma coisa não funciona

| Sintoma | Causa mais comum |
|---|---|
| YouTube não recebe dados | chave expirada — gere outra no Studio e cole de novo |
| "Operation not permitted" | mesma coisa: chave recusada |
| Câmera não abre | outro programa (Meet, Zoom, OBS) já está com ela; só um por vez |
| Live engasgando | upload da internet; configure a taxa em até 70% do upload medido |
| Imagem travando periodicamente | antivírus varrendo ou navegador com muitas abas |
| Câmera virtual não aparece | falta instalar o OBS Studio (Windows/macOS) |
| Fundo desfocado recortando errado | modo aproximado — instale o mediapipe ou use *Aprender fundo* |

---

## Testes

```
python RODAR_TESTES.py          (ou 2_RODAR_TESTES.bat)
```

134 testes. A suíte **não** precisa de câmera, ffmpeg, internet nem do Qwen:
tudo o que depende do mundo externo é testado pela forma do comando que seria
executado, ou por uma fonte de vídeo gerada em memória. Um teste que só passa na
máquina certa não prova nada sobre as outras.
