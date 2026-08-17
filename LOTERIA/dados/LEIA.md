# Onde largar o histórico dos sorteios

O software lê os resultados **de arquivo**, não da internet. O motivo é chato e
honesto: o ambiente onde eu rodo tem a saída de rede fechada por política, e a
conexão com o site da Caixa é recusada antes mesmo de sair da máquina (403 no
CONNECT, registrado pelo próprio proxy). Não é a Caixa fora do ar e não adianta
tentar de novo.

Isso acabou virando uma vantagem: o arquivo fica no seu disco, igual todas as
vezes. Duas medições sobre o mesmo arquivo dão o mesmo número, e o veredito de
cada item guarda a soma de verificação do arquivo de onde ele saiu. Se você
trocar o arquivo, a soma muda e a medição antiga deixa de valer para o novo.

## O que baixar

No portal de loterias da Caixa há o download dos resultados completos por
loteria. Serve qualquer um destes formatos:

- **CSV / planilha exportada** com colunas `Bola1`…`Bola6` (é o formato mais
  comum). Se vierem junto as colunas de `Ganhadores N acertos` e de
  `Arrecadacao`, melhor: são elas que permitem medir a partilha do prêmio (P01),
  que é o único item capaz de aumentar o que você recebe sem prever nada.
- **JSON** de API, com `dezenas` e `premiacoes`.
- **Texto solto**, uma linha por concurso, só os números.

Largue o arquivo aqui dentro e rode:

```
python JOGAR.py mega_sena --historico dados/o_seu_arquivo.csv
```

## Confira o que eu li

A primeira coisa que aparece é o **diagnóstico**: quantos concursos, quantas
dezenas por concurso, de que valor a que valor, o primeiro e o último lido por
extenso. Bata o olho nisso com o arquivo aberto do lado.

Eu não consegui baixar o arquivo da Caixa, logo não conheço o formato exato dele
— escrevi o leitor para as formas que eu conheço. Se ele pegar a coluna errada,
o diagnóstico denuncia na hora ("li 6 dezenas indo de 1 a 2701" mostra que ele
pegou o número do concurso junto). O erro que eu temo é o mudo: ler errado, não
reclamar, e produzir estatística bonita sobre lixo.

Se o formato do seu arquivo for outro, me mostre as primeiras linhas dele que eu
ensino o leitor. É melhor do que eu adivinhar.
