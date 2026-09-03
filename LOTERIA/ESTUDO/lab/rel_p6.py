# -*- coding: utf-8 -*-
"""Capítulo 8: as outras loterias — o teste que decide."""
from relatorio_base import fig, milhar, num, pct


def outras(D):
    o = D["outras_loterias"]
    mods = o["modalidades"]; fi = o["fisher"]; ss = o["super_sete"]
    lin = "".join(
        f'<tr><td><b>{m["nome"]}</b></td><td class="c">{m["N"]}/{m["k"]}</td>'
        f'<td class="n">{milhar(m["T_sorteios"])}</td>'
        f'<td class="n">{num(m["chi2"],1)}</td><td class="n">{m["df"]}</td>'
        f'<td class="n {"pos" if m["p_chi2"]<0.05 else ""}">{num(m["p_chi2"],4)}</td>'
        f'<td class="n">{num(m["r_media"],3,sinal=True)}</td>'
        f'<td class="n {"pos" if m["p_r"]<0.05 else ""}">{num(m["p_r"],4)}</td>'
        f'<td class="n">{pct(m["resolucao_relativa"],2)}</td></tr>' for m in mods)
    return f"""
<div class="quebra"></div>
<h2>8 · As outras oito loterias: o teste que decide</h2>

<p>O capítulo 7 deixou uma pergunta em aberto com duas respostas possíveis, e elas fazem
previsões <b>diferentes e verificáveis</b>:</p>

<table>
<tr><th style="width:30mm">Se for física</th><td>alguma coisa no equipamento — bola, globo, carregamento.
Então as <b>outras</b> loterias da Caixa, que usam globos e bolas de fabricação semelhante,
deveriam mostrar algo análogo.</td></tr>
<tr><th style="width:30mm">Se for coincidência</th><td>o desvio é o extremo esperado de uma busca grande.
Então as outras loterias não mostrarão nada.</td></tr>
</table>

<p>Este é o tipo de teste que vale mais do que qualquer p-valor a mais na mesma base: a
previsão foi feita <b>depois</b> do achado, e testada em dados que não participaram de
gerá-lo. Rodei em todas as oito modalidades que cabem no molde “escolher <i>k</i> de
<i>N</i>” exatamente a mesma medida da Lotofácil — χ² de uniformidade com a variância
binomial correta, e a correlação dos desvios entre três janelas cronológicas disjuntas —
cada uma com seu próprio controle negativo de {milhar(o['n_falsas'])} histórias falsas.</p>

<h3>8.1 As oito modalidades, lado a lado</h3>

<table>
<tr><th>Modalidade</th><th class="c">N/k</th><th class="n">sorteios</th><th class="n">χ²</th>
<th class="n">gl</th><th class="n">p(χ²)</th><th class="n">persist. r</th><th class="n">p(r)</th>
<th class="n">resolução</th></tr>
{lin}
</table>

<p>E a Super Sete, que não cabe no molde (sete colunas independentes de 0 a 9), foi medida
com molde próprio: χ² = {num(ss['chi2'],1)} com {ss['df']} graus,
p = {num(ss['p_chi2'],4)} — perfeitamente uniforme.</p>

<figure>
  <img src="{fig('11_outras_loterias.png')}">
  <figcaption><b>Figura 11.</b> Esquerda: a persistência do desvio entre janelas; os traços
  verticais marcam o percentil 95 do acaso para cada base. Centro: o χ² dividido pelos graus
  de liberdade (1,0 = uniformidade perfeita). Direita: o menor desvio relativo por dezena que
  cada base consegue enxergar — quanto menor a barra, mais sensível o teste.</figcaption>
</figure>

<h3>8.2 O que apareceu</h3>

<p>Três modalidades mostram persistência positiva além do acaso, e cinco não mostram nada:</p>

<ul>
<li><b>Lotofácil</b> — persistência r = {num(mods[0]['r_media'],3)} (p = {num(mods[0]['p_r'],4)});
χ² p &lt; {num(1/o['n_falsas'],4)}.</li>
<li><b>Quina</b> — persistência r = {num(mods[2]['r_media'],3)} (p = {num(mods[2]['p_r'],4)}),
em 6.584 sorteios, a maior base disponível.</li>
<li><b>Mega-Sena</b> — χ² p = {num(mods[1]['p_chi2'],4)}; persistência r = {num(mods[1]['r_media'],3)}
(p = {num(mods[1]['p_r'],4)}).</li>
<li><b>Lotomania, Dupla Sena, Timemania, Dia de Sorte, +Milionária e Super Sete</b> — nada.</li>
</ul>

<h3>8.3 O teste confirmatório, sem a Lotofácil</h3>

<p>A Lotofácil é a amostra de descoberta e não pode entrar na confirmação — usá-la seria
contar o mesmo dado duas vezes. Combinando os p-valores das <b>sete outras</b> modalidades
pelo método de Fisher, que é o teste correto para “vários estudos independentes apontam na
mesma direção?”:</p>

<table>
<tr><th>Combinação de Fisher</th><th class="n">X²</th><th class="n">gl</th><th class="n">p</th></tr>
<tr><td>As 8 modalidades — persistência</td><td class="n">{num(fi['todas_persistencia']['X2'],2)}</td>
<td class="n">{fi['todas_persistencia']['df']}</td><td class="n">{num(fi['todas_persistencia']['p'],5)}</td></tr>
<tr><td>As 8 modalidades — uniformidade</td><td class="n">{num(fi['todas_uniformidade']['X2'],2)}</td>
<td class="n">{fi['todas_uniformidade']['df']}</td><td class="n">{num(fi['todas_uniformidade']['p'],5)}</td></tr>
<tr><td><b>As 7 outras (sem a Lotofácil) — persistência</b></td><td class="n">{num(fi['sem_lotofacil_persistencia']['X2'],2)}</td>
<td class="n">{fi['sem_lotofacil_persistencia']['df']}</td><td class="n"><b>{num(fi['sem_lotofacil_persistencia']['p'],5)}</b></td></tr>
<tr><td><b>As 7 outras (sem a Lotofácil) — uniformidade</b></td><td class="n">{num(fi['sem_lotofacil_uniformidade']['X2'],2)}</td>
<td class="n">{fi['sem_lotofacil_uniformidade']['df']}</td><td class="n"><b>{num(fi['sem_lotofacil_uniformidade']['p'],5)}</b></td></tr>
</table>

<div class="achado">
<span class="rot">o resultado mais forte deste relatório</span>
<p>Excluindo inteiramente a base onde o achado nasceu, as <b>outras sete loterias da Caixa
ainda apontam na mesma direção</b>: p = {num(fi['sem_lotofacil_persistencia']['p'],4)} para a
persistência do desvio e p = {num(fi['sem_lotofacil_uniformidade']['p'],4)} para a
uniformidade. É confirmação independente — fraca, nos dois casos logo abaixo de 0,05, mas
independente, e feita sobre uma previsão registrada antes de olhar.</p>
<p>Os dados da Mega-Sena (concursos 1–2.549) e da Quina (1–6.032) também foram conferidos
contra a mesma fonte independente da seção 1.2, com <b>zero divergências</b> em ambas.</p>
</div>

<h3>8.4 Por que as cinco que deram nada não derrubam o achado</h3>

<p>A leitura ingênua seria: “cinco de oito não mostraram nada, logo não há efeito”. A
coluna <b>resolução</b> da tabela 8.1 desmonta essa leitura, e é por isso que ela está lá.</p>

<p>A resolução é o menor desvio <i>relativo</i> por dezena que cada base consegue enxergar —
formalmente, o erro padrão da frequência estimada dividido pela própria frequência,
√((1−p)/(T·p)). Ela depende de quantos sorteios existem <b>e</b> de qual a chance de cada
dezena sair. Na Lotofácil, p = 0,60 e T = 3.246: a base resolve
<b>{pct(mods[0]['resolucao_relativa'],2)}</b>. Nas outras, p é muito menor, e a mesma
quantidade de sorteios compra muito menos precisão:</p>

<table>
<tr><th>Modalidade</th><th class="n">resolução</th><th class="n">quantas vezes menos sensível que a Lotofácil</th></tr>
{''.join(f'<tr><td>{m["nome"]}</td><td class="n">{pct(m["resolucao_relativa"],2)}</td>'
         f'<td class="n">{num(m["quantas_vezes_menos_sensivel_que_a_lotofacil"],1)}×</td></tr>' for m in mods)}
</table>

<div class="destaque">
<p>Um viés relativo de, digamos, 2% por dezena seria <b>visível na Lotofácil</b> (resolução
1,43%) e <b>invisível em todas as outras</b> (resolução de 3,7% a 19,2%). As cinco
modalidades que não acusaram nada não são evidência contra o efeito: elas simplesmente não
teriam como vê-lo. E as duas que acusaram — Quina e Mega-Sena — são justamente as de maior
base entre as restantes.</p>
<p>Isso não prova que o efeito seja físico. Prova que a ausência de sinal nas outras
<b>não é argumento</b>, o que é uma coisa diferente e igualmente importante de dizer.</p>
</div>

<h3>8.5 O que isto muda no veredicto do capítulo 7</h3>

<p>Muda de categoria, mas não até o ponto de virar afirmação. O achado passa de “um desvio
numa base, que pode ser o extremo da busca” para “um desvio que replica dentro da base
<b>e</b> aparece de forma independente, na mesma direção, em outras duas modalidades, com
as demais sem poder para julgar”. Continua sendo insuficiente para afirmar viés no sorteio,
por três razões que ficam registradas:</p>

<ol>
<li><b>Os p-valores confirmatórios ficam logo abaixo de 0,05.</b> Isso é fraco, e a
literatura de replicação é clara sobre o que costuma acontecer com achados nessa faixa.</li>
<li><b>Nenhum mecanismo físico foi identificado.</b> A hipótese da tinta (seção 7.3) é
sugestiva e post-hoc; sem cruzar com o registro de qual globo e qual conjunto de bolas foi
usado em cada concurso, ela não sai do lugar.</li>
<li><b>O efeito é pequeno demais para qualquer uso.</b> Continua valendo
{num(D['persistencia']['veredicto']['separacao_quente_menos_frio']['observado'],3)} acerto
por jogo na Lotofácil, e menos ainda nas outras.</li>
</ol>

<p>O que isto <b>faz</b> é dar ao pré-registro da seção 7.5 um alvo muito melhor: em vez de
esperar concursos novos só da Lotofácil, dá para testar as três modalidades ao mesmo tempo
e ganhar poder de imediato. A hipótese pré-registrada passa a ser: <b>a persistência
combinada das oito modalidades continuará positiva nos concursos posteriores aos desta
base</b>. Uma correlação combinada nula ou negativa derruba o achado inteiro, e derruba de
uma vez.</p>
"""
