# ESTÚDIO — sua Hollyland Lyra direto no YouTube

Software que abre sua webcam, trata a imagem e o som ao vivo, e entrega a
transmissão ao YouTube. **Sem OBS.**

    0_INSTALAR.bat      uma vez, instala o que falta
    2_CONFERIR.bat      diz o que esta máquina tem e o que ela aguenta
    1_ESTUDIO.bat       abre o estúdio

---

## O que você pediu, e onde está cada coisa

| Você pediu | Onde está | Estado |
|---|---|---|
| software para a webcam Lyra | `camera.py`, `dispositivos.py` | acha pela palavra "lyra" ou "hollyland", não por número que muda |
| conectar direto no YouTube | `transmissao.py` | RTMP direto, botão TRANSMITIR |
| editor de áudio ao vivo | `audio_dsp.py`, `audio.py` | 7 etapas, aba Áudio |
| IA para melhorar a imagem | `ia_visual.py` | mede e corrige exposição, cor da luz e ruído, quadro a quadro |
| filtros estilo câmera Sony | `visual.py` | 5 looks + o seu `.cube` |
| embelezamento | `beleza.py` | pele, manchas, olhos, dentes |
| desfoque de fundo | `fundo.py` | aba Beleza e fundo |
| sem passar pelo OBS | — | não há câmera virtual, não há cena; é este programa que transmite |

---

## O que este software NÃO faz — leia antes de precisar

**Não escrevi o codificador de vídeo.** A compressão H.264 é feita pelo
`ffmpeg`, que é um programa de linha de comando — sem janela, sem cena, sem
interface. É a mesma peça que o OBS usa por baixo; a diferença é que aqui ela
é chamada por este software, e não por outro que você teria de abrir e
configurar. Escrever um codificador em Python daria uma live inassistível.
Se o ffmpeg não estiver na máquina, o botão TRANSMITIR diz isso e explica.

**Os LUTs não são os da Sony.** Os arquivos oficiais (S-Cinetone, s-Log3,
Venice) são da Sony e não podem ser distribuídos aqui. O que está no software
é *emulação*: reproduzi o comportamento que caracteriza cada perfil — o
joelho suave nas altas, a pele levemente quente, a saturação contida, a
sombra fria — com curvas e matrizes minhas. Fica parecido. Não é o arquivo
deles. Se você tiver o `.cube` oficial, aponte em `lut_arquivo` e ele passa
na frente do meu.

**A "IA" não é rede neural.** Uma rede de melhoria de imagem em CPU leva de
100 ms a vários segundos por quadro; ao vivo o quadro inteiro tem 33 ms.
O que está aqui é percepção + medição + controle em malha fechada: acha o
rosto, mede luminância, cor da luz, ruído e foco, e corrige perseguindo um
alvo, com freios para não oscilar. É o que a "IA de cena" de uma câmera faz,
e melhora a imagem de verdade — mas não inventa detalhe que a webcam não
captou. Nenhuma IA em CPU faz isso ao vivo.

**O recorte de fundo, sem `mediapipe`, é geométrico.** Elipse na cabeça a
partir do rosto detectado, mais o tronco descendo dos ombros, reforçado pela
cor da pele. Funciona para uma pessoa sentada de frente para a webcam. Erra
se alguém passar atrás ou se você levantar o braço para o lado. Com
`pip install mediapipe` vira recorte por pixel e o problema acaba. A tela
mostra qual dos dois está em uso.

**Não busco a chave do YouTube sozinho.** Daria (a API de Live Streaming
existe), mas exigiria você criar um projeto no Google Cloud e passar por uma
tela de consentimento OAuth — mais trabalho para você do que colar a chave
uma vez. A chave não expira.

---

## O ffmpeg em três linhas

Se o `2_CONFERIR.bat` disser que falta:

1. baixe em <https://www.gyan.dev/ffmpeg/builds/> (o pacote "essentials")
2. abra o .zip e ache o `ffmpeg.exe` dentro de `bin`
3. copie o `ffmpeg.exe` para **esta mesma pasta**, ao lado do `ESTUDIO.py`

Só isso. Não precisa instalar nem mexer em PATH.

---

## A chave do YouTube

YouTube Studio → **Criar** → **Transmitir ao vivo** → aba *Configurações do
stream* → **Chave da transmissão** → Copiar.

No estúdio: aba **Transmissão** → cole → **Guardar chave**.

A chave fica em `chave_youtube.txt`, sozinha, fora do arquivo de ajustes e
fora do Git. Na tela ela aparece como `••••••••wxyz`. Se você mandar seus
ajustes para alguém, manda sem a senha da sua live.

---

## Os looks

| Look | Para quê |
|---|---|
| **S-Cinetone** | o padrão. Pele natural, altas que cedem devagar, cor contida. O que mais faz uma webcam parecer câmera boa. |
| **Venice** | mais peso: preto fundo, cor rica. Precisa de luz boa. |
| **FX3 natural** | quase o que a câmera vê, só arrumado. |
| **Cine4 plano** | de propósito sem graça, para você aplicar seu próprio LUT depois. |
| **Noite / luz fraca** | quarto à noite: levanta a sombra sem lavar e evita o verde da webcam barata. |
| **Cru** | sem filtro. Serve para comparar. |

Um `.cube` seu no campo `lut_arquivo` vence qualquer um deles.

---

## O áudio, na ordem em que acontece

    1. corte de graves      tira ronco de mesa e de ar-condicionado
    2. redução de ruído     aprende o chiado sozinho e subtrai
    3. portão               silêncio vira silêncio
    4. de-esser             doma o "sss" sem afundar a voz
    5. equalização          corpo · tira o abafado · presença
    6. compressor           sussurro e grito na mesma altura
    7. limitador            teto que nada ultrapassa

A ordem não é gosto: comprimir antes de limpar amplifica o chiado nas pausas,
e dar presença antes do de-esser é pedir para o "sss" estourar.

A cadeia atrasa **24 ms** (janela da redução de ruído + antecipação do
limitador). O vídeo é atrasado no mesmo tanto, senão a voz chega antes da
imagem e a boca não casa.

A redução de ruído aprende o que é chiado medindo o **mínimo de cada faixa**
ao longo do tempo: nenhuma faixa da voz fica alta o tempo todo, mas o
ventilador fica. Medido: **−16,5 dB de chiado custando 3,4 dB de voz.**

---

## Desempenho — os números medidos, não os prometidos

Medido a 1280x720 numa máquina fraca de propósito (4 núcleos, 2,1 GHz):

    embelezamento      23 ms        desfoque de fundo    10 ms
    filtro (tabela)     7 ms        ruído temporal        6 ms
    acabamento          7 ms        IA (a cada 3 quadros) 2 ms
    ------------------------------------------------------------
    tudo ligado        ~60 ms  =  ~16 quadros por segundo
    áudio completo      74 ms de CPU por SEGUNDO de som (7% de um núcleo)

Numa máquina de mesa comum (8 núcleos, 3,5 GHz) isso cai para perto de 25 ms
e os 30 quadros cabem com folga. **Na sua não sei, e não vou fingir que sei.**

Por isso o software **mede o próprio tempo** e, se não couber, desliga efeito
— na ordem `grão → halação → vinheta → nitidez → embelezamento reduzido →
desfoque → embelezamento → filtro` — e **escreve na barra de baixo o que
desligou**. Enfeite cai primeiro; o que você pediu cai por último.

Se aparecer coisa desligada e você quiser tudo: baixe para **960x540** nos
ajustes, ou instale o ffmpeg com placa de vídeo (o `2_CONFERIR.bat` diz se
você tem NVENC/QuickSync — isso libera CPU tirando a codificação dela).

---

## Quando der problema

| Sintoma | Causa provável |
|---|---|
| "não achei 'lyra'" na barra | a webcam não está conectada, ou o nome dela é outro. `2_CONFERIR.bat` lista os nomes reais; copie o nome para `camera_nome`. |
| taxa de quadros baixa e a barra diz o formato "YUY2" | a câmera não entrou em MJPG. Em USB 2.0, 720p cru não cabe no cabo e ela cai para 5–10 fps sozinha. Tente outra porta USB (de preferência USB 3, azul). |
| a live não sobe, e a barra mostra "403 Forbidden" | chave errada ou live não criada no YouTube Studio. |
| a imagem trava mas o som continua | outro programa pegou a webcam. Feche Teams/Meet/Zoom. |
| a voz chega antes da imagem | não deveria — o vídeo é atrasado de propósito. Se acontecer, me diga: é defeito meu. |
| o áudio está estalando | a barra mostra "blocos perdidos". Máquina no limite: baixe a resolução do vídeo, que é quem está comendo a CPU. |

---

## Para conferir que ainda está tudo de pé

    python RODAR_TESTES.py

Sete arquivos, ~19 segundos. Entre outras coisas, eles cobram:

- que o áudio processado em cem blocos seja **idêntico** ao processado em um
  (senão são 47 cliques por segundo)
- que o limitador **nunca** deixe passar do teto
- que o embelezamento reduza a textura da pele **sem zerá-la** (rosto de
  plástico é defeito, não recurso)
- que a sobrancelha **não** seja confundida com mancha
- que a máscara de pele funcione em **seis tons**, de muito clara a muito
  escura, e que cinza neutro **não** seja pele
- que a chave do YouTube **não apareça** em nenhum log ou comando
- que a IA convirja **sem oscilar** num degrau de luz
