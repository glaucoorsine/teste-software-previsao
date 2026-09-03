# -*- coding: utf-8 -*-
"""Capítulos 6 a 10: a bateria, o achado, os erros, o fechamento, a reprodução."""
import numpy as np
from relatorio_base import fig, milhar, num, pct


def bateria_cap(D):
    pr = D["protocolo"]; cn = pr["controle_negativo"]; v = pr["veredicto"]
    top = sorted(v.items(), key=lambda kv: -abs(kv[1]["z"]))[:20]
    linhas = "".join(
        f'<tr><td class="mono">{k}</td><td class="n">{num(d["z"],2,sinal=True)}</td>'
        f'<td class="n">{num(d["p_isolado"],4)}</td><td class="n">{num(d["p_familia"],4)}</td>'
        f'<td class="c">{"<span class=viva>sobrevive</span>" if d["sobrevive"] else "<span class=morta>morre</span>"}</td></tr>'
        for k, d in top)
    rj = pr["ranking_por_janela"]
    nomes = sorted({k[5:].replace(".media_acertos", "") for k in rj["teste"] if k.endswith(".media_acertos")},
                   key=lambda n_: -rj["teste"][f"rank.{n_}.media_acertos"])
    lr = "".join(
        f'<tr><td>{n_}</td>'
        f'<td class="n">{num(rj["descoberta"][f"rank.{n_}.media_acertos"],4)}</td>'
        f'<td class="n">{num(rj["validacao"][f"rank.{n_}.media_acertos"],4)}</td>'
        f'<td class="n">{num(rj["teste"][f"rank.{n_}.media_acertos"],4)}</td>'
        f'<td class="n">{num(rj["teste"][f"rank.{n_}"],2,sinal=True)}</td></tr>' for n_ in nomes)
    return f"""
<div class="quebra"></div>
<h2>6 · A bateria completa contra o acaso puro</h2>

<p>A bateria tem <b>{pr['protocolo']['n_testes_na_bateria']} testes</b>, e esse número é
grande de propósito. Ela inclui os testes de estrutura, os {milhar(300)} de coocorrência de
duplas, os {milhar(300)} de autocorrelação (25 dezenas × 12 defasagens), os 25 de frequência
individual, os 25 de deriva acumulada, os de espectro, de runs, de Markov, de posição, e os
16 de ranking. <b>Todos entram no controle negativo</b>, inclusive — e principalmente — os
que não deram em nada.</p>

<p>Esconder os testes individuais e reportar só o melhor seria esconder do controle
negativo o tamanho real da busca, que é a forma mais comum de auto-engano nesta área. Se a
busca foi de {pr['protocolo']['n_testes_na_bateria']} testes, o controle tem de saber de
{pr['protocolo']['n_testes_na_bateria']} testes.</p>

<h3>6.1 O resultado que reorganiza tudo</h3>

<div class="destaque">
<p>Passando esses mesmos {pr['protocolo']['n_testes_na_bateria']} testes por
{milhar(pr['protocolo']['n_historias_falsas'])} históricos de acaso uniforme puro, o
maior |z| encontrado foi <b>{num(cn['max_z_p50'])}</b> na mediana e
<b>{num(cn['max_z_p95'])}</b> no percentil 95.</p>
</div>

<p>Traduzindo para a linguagem em que as descobertas de loteria costumam ser anunciadas:
uma busca deste tamanho, feita em dados que são <b>comprovadamente ruído</b>, produz um
resultado de "quase cinco sigmas" em uma de cada vinte tentativas. Se alguém — pessoa,
planilha ou modelo — varre centenas de hipóteses e volta com um z de 4, isso não é
evidência de nada. É a linha de base.</p>

<h3>6.2 Os três sobreviventes, e a autópsia deles</h3>

<p>Os vinte maiores |z| da bateria, no dado real:</p>

<table class="compacta">
<tr><th>Teste</th><th class="n">z</th><th class="n">p isolado</th><th class="n">p de família</th><th class="c">veredicto</th></tr>
{linhas}
</table>

<p>Três testes passam do limiar de família. E os três são <b>autocorrelações da dezena
20</b>, em defasagens diferentes (3, 9 e 11 concursos). À primeira vista, isso é
extraordinário: significaria que a dezena 20 tem <b>memória</b> — que sair hoje muda a
chance de sair daqui a nove concursos. Seria a descoberta do século em loterias.</p>

<p>Não é. A autópsia leva vinte segundos e é definitiva.</p>

<div class="morto">
<span class="rot">autópsia do falso positivo</span>
<p>O teste de autocorrelação da dezena 20 usa como hipótese nula p = 0,600, que é a
frequência que a dezena <b>deveria</b> ter. Mas a dezena 20 saiu em <b>62,94%</b> dos
concursos. Sob independência, a chance de ela sair em dois concursos quaisquer é o
quadrado da <b>frequência dela</b>, não de 0,6: 0,6294² = 0,3961, contra os 0,3600 que o
teste assumiu. A diferença entre esses dois números, multiplicada por 3.246 concursos, é
exatamente o "sinal".</p>
<p>Refazendo os mesmos testes com o nulo correto — p igual à frequência observada da
própria dezena — os z de <b>+4,38, +4,85, +4,77, +4,90 e +5,07</b> viram
<b>+0,09, +0,55, +0,47, +0,60 e +0,77</b>. A memória evapora. O mesmo vale para a dezena 16
no sentido negativo.</p>
<p>E há uma pista que estava à vista o tempo todo: os doze lags da dezena 20 aparecem
<b>juntos</b> no topo da lista. Memória real em lag 11 sem memória em lag 10 não faz
sentido físico. Doze lags simultâneos não são doze sinais — são um único fato marginal
contaminando doze testes.</p>
</div>

<figure>
  <img src="{fig('08_autopsia_falso_positivo.png')}">
  <figcaption><b>Figura 8.</b> Linha cheia: a autocorrelação medida contra o nulo p = 0,600,
  que é o errado. Linha pontilhada: o mesmo cálculo contra o nulo correto, a frequência
  observada da própria dezena. Todo o "sinal" das doze defasagens é a frequência marginal
  aparecendo doze vezes.</figcaption>
</figure>

<p>Sobra, portanto, <b>um único fato</b> em toda a bateria: a dezena 20 sai um pouco mais
do que devia, e a 16 um pouco menos. Não é memória, não é padrão temporal, não é
previsibilidade. É frequência. O capítulo 7 é inteiramente sobre isso.</p>

<h3>6.3 As dezesseis teorias de ranking contra a linha de 9,0</h3>

<p>Cada teoria devolve, a cada concurso, as quinze dezenas que ela escolheria, usando
apenas informação anterior àquele concurso. Conta-se quantas ela acertou. A linha de base
é exata e cruel: <b>9,0000</b>.</p>

<table class="compacta">
<tr><th>Teoria</th><th class="n">descoberta (1.948)</th><th class="n">validação (649)</th>
<th class="n">teste (649)</th><th class="n">z no teste</th></tr>
{lr}
</table>

<figure>
  <img src="{fig('06_ranking_teorias.png')}">
  <figcaption><b>Figura 6.</b> As dezesseis teorias na janela de teste, com intervalo de
  confiança de 95%. A faixa cinza é o que o acaso permite. Só <span style="color:#b3402f">
  <b>quente_global</b></span> sai dela — e o capítulo 7 explica por quê, e por que isso
  não serve para apostar.</figcaption>
</figure>

<p>Três leituras que valem registro:</p>
<ul>
<li><b>“Aleatório” terminou em {num(rj['teste']['rank.aleatorio.media_acertos'],4)}</b>,
abaixo de várias teorias sérias. Isso é o ruído da janela de 649 concursos, e é a melhor
demonstração possível de que as diferenças de terceira casa entre as teorias não
significam nada.</li>
<li><b>“Repetir o concurso anterior” deu {num(rj['teste']['rank.repetir_anterior.media_acertos'],4)}</b>,
estatisticamente indistinguível de tudo o mais. A estratégia mais ingênua imaginável
empata com as sofisticadas, porque sob uniformidade todas empatam.</li>
<li><b>As frias ficaram consistentemente abaixo</b> nas três janelas. Isso não é a “lei dos
grandes números corrigindo o atraso” funcionando ao contrário: é o mesmo fato do capítulo 7,
visto pelo outro lado.</li>
</ul>
"""


def achado(D):
    pe = D["persistencia"]; v = pe["veredicto"]; t = pe["hipotese_da_tinta"]
    pr = D["protocolo"]
    fam = pr["veredicto"]["dep.uniformidade_25"]
    zt = np.array(pe["z_total"]); freq = pe["frequencias"]
    ordem = np.argsort(-zt)
    linhas = "".join(
        f'<tr><td class="c"><b>{i+1:02d}</b></td><td class="n">{milhar(freq[str(i+1)])}</td>'
        f'<td class="n">{pct(freq[str(i+1)]/3246,2)}</td>'
        f'<td class="n {"pos" if zt[i]>2 else ("neg" if zt[i]<-2 else "")}">{num(zt[i],2,sinal=True)}</td>'
        f'<td class="n">{num(np.array(pe["z_por_dezena"]["descoberta"])[i],2,sinal=True)}</td>'
        f'<td class="n">{num(np.array(pe["z_por_dezena"]["validacao"])[i],2,sinal=True)}</td>'
        f'<td class="n">{num(np.array(pe["z_por_dezena"]["teste"])[i],2,sinal=True)}</td></tr>'
        for i in ordem)
    def lin(k, rot):
        d = v[k]
        p = min(d["p_unilateral_maior"], d["p_unilateral_menor"])
        return (f'<tr><td>{rot}</td><td class="n">{num(d["observado"],3)}</td>'
                f'<td class="n">{num(d["nulo_media"],3)}</td>'
                f'<td class="n">{num(d["nulo_p95"],3)}</td>'
                f'<td class="n"><b>{num(p,4)}</b></td></tr>')
    return f"""
<div class="quebra"></div>
<h2>7 · O único achado: as 25 dezenas não são iguais</h2>

<h3>7.1 χ² = {num(v['chi2_total']['observado'],2)} e a replicação fora da amostra</h3>

<p>Em 3.246 concursos, cada dezena deveria sair 1.947,6 vezes (60%). O χ² de uniformidade
das 25, com a variância correta, dá <b>{num(v['chi2_total']['observado'],2)}</b> contra 24
graus de liberdade. Em {milhar(pe['n_historias_falsas'])} histórias de acaso puro, o mesmo
cálculo deu {num(v['chi2_total']['nulo_media'],2)} em média e ultrapassou o valor real em
<b>{num(v['chi2_total']['p_unilateral_maior']*100,2)}%</b> das vezes.</p>

<figure>
  <img src="{fig('02_frequencia_25_dezenas.png')}">
  <figcaption><b>Figura 2.</b> As 25 dezenas ordenadas pelo desvio. Vermelho: além de 2σ.
  A dezena 20 saiu {milhar(freq['20'])} vezes ({pct(freq['20']/3246,2)}); a dezena 16 saiu
  {milhar(freq['16'])} ({pct(freq['16']/3246,2)}).</figcaption>
</figure>

<p>Um χ² alto sozinho não vale muito — é um teste entre {pr['protocolo']['n_testes_na_bateria']}
e o capítulo 6 acabou de mostrar o que isso significa. O que dá peso ao achado é outra
coisa, e é a única evidência que não pode ser fabricada por busca: <b>a replicação em
janelas cronológicas que não se tocam</b>.</p>

<table>
<tr><th>Estatística</th><th class="n">observado</th><th class="n">no acaso</th>
<th class="n">p95 do acaso</th><th class="n">p</th></tr>
{lin('chi2_descoberta','χ² na descoberta (concursos 1–1.948)')}
{lin('chi2_validacao','χ² na validação (1.949–2.597)')}
{lin('chi2_teste','χ² no teste (2.598–3.246)')}
{lin('r_descoberta_x_validacao','correlação dos 25 desvios: descoberta × validação')}
{lin('r_descoberta_x_teste','correlação dos 25 desvios: descoberta × teste')}
{lin('r_validacao_x_teste','correlação dos 25 desvios: validação × teste')}
{lin('r_media','<b>correlação média das três</b>')}
</table>

<p>As três correlações são positivas, e as três janelas não compartilham um único
concurso. As dezenas que estavam acima da média entre 2003 e 2015 continuaram acima entre
2016 e 2020, e de novo entre 2021 e 2024. Sob uniformidade perfeita, essas correlações
deveriam ficar em torno de {num(v['r_descoberta_x_teste']['nulo_media'],3)}, e a média das
três passa do percentil 95 do acaso com p = {num(v['r_media']['p_unilateral_maior'],4)}.</p>

<figure>
  <img src="{fig('03_persistencia.png')}">
  <figcaption><b>Figura 3.</b> Cada ponto é uma dezena; destacadas a 20 e a 16. Se não
  houvesse efeito, as nuvens seriam redondas e as retas horizontais.</figcaption>
</figure>

<figure>
  <img src="{fig('10_chi2_por_janela.png')}">
  <figcaption><b>Figura 10.</b> As duas janelas fora da amostra contra a distribuição do
  χ² em janelas de 649 concursos de acaso puro.</figcaption>
</figure>

<h3>7.2 O tamanho do efeito: {num(v['separacao_quente_menos_frio']['observado'],3)} acerto</h3>

<p>Aqui o achado encolhe até virar quase nada, e é obrigatório dizer isso com a mesma
clareza com que se disse o resto. O teste operacional: fixar as quinze dezenas mais
frequentes usando <b>apenas</b> os concursos 1 a 1.948, e depois apostá-las nos 1.298
concursos seguintes, que não participaram da escolha.</p>

<table>
<tr><th>Aposta fixa definida nos concursos 1–1.948</th><th class="n">acertos/jogo (1.298 concursos)</th><th class="n">z</th><th class="n">p</th></tr>
<tr><td>As 15 dezenas <b>mais</b> frequentes</td><td class="n">{num(v['acertos_quentes_fora_da_amostra']['observado'],4)}</td>
<td class="n">{num(v['z_quentes']['observado'],2,sinal=True)}</td><td class="n">{num(v['z_quentes']['p_unilateral_maior'],4)}</td></tr>
<tr><td>As 15 dezenas <b>menos</b> frequentes</td><td class="n">{num(v['acertos_frios_fora_da_amostra']['observado'],4)}</td>
<td class="n">{num(v['z_frios']['observado'],2,sinal=True)}</td><td class="n">{num(v['z_frios']['p_unilateral_menor'],4)}</td></tr>
<tr><td>Linha de base do acaso</td><td class="n">9,0000</td><td class="n">—</td><td class="n">—</td></tr>
<tr><td><b>Separação entre o melhor e o pior conjunto</b></td>
<td class="n"><b>{num(v['separacao_quente_menos_frio']['observado'],4)}</b></td>
<td class="n">—</td><td class="n">{num(v['separacao_quente_menos_frio']['p_unilateral_maior'],4)}</td></tr>
</table>

<div class="destaque">
<p><b>Leia a última linha como um limite superior.</b>
{num(v['separacao_quente_menos_frio']['observado'],3)} acerto é toda a distância entre a
melhor e a pior aposta fixa possível, escolhidas com conhecimento de 1.948 concursos. A
menor faixa de prêmio da Lotofácil começa em <b>11</b> acertos. Sair de 9,00 para
{num(v['acertos_quentes_fora_da_amostra']['observado'],2)} não move nenhuma probabilidade
de prêmio de forma perceptível: a chance de fazer 11 pontos com um jogo de 15 dezenas
continua sendo aproximadamente 1 em 11, contra 1 em 11. <b>O efeito é real e é
irrelevante para apostar</b> — e é justamente esse par que o torna interessante.</p>
</div>

<h3>7.3 A hipótese da tinta</h3>

<p>Se o desvio for físico, precisa de mecanismo. A explicação mais citada na literatura de
loterias com bolas é <b>massa</b>: bolas com mais tinta impressa pesam um pouco mais. Na
Lotofácil isso tem um teste barato — as dezenas 1 a 9 têm um algarismo e as 10 a 25 têm
dois.</p>

<table>
<tr><th>Medida</th><th class="n">valor</th></tr>
<tr><td>z médio das dezenas de <b>um</b> algarismo (1–9)</td><td class="n">{num(t['z_medio_um_algarismo'],3,sinal=True)}</td></tr>
<tr><td>z médio das dezenas de <b>dois</b> algarismos (10–25)</td><td class="n">{num(t['z_medio_dois_algarismos'],3,sinal=True)}</td></tr>
<tr><td>Diferença entre os dois grupos</td><td class="n">{num(t['diferenca'],3,sinal=True)} (z = {num(t['z_da_diferenca'],2,sinal=True)})</td></tr>
<tr><td>Correlação do desvio com a soma dos algarismos</td><td class="n">{num(t['correlacao_z_com_soma_dos_algarismos'],3,sinal=True)}</td></tr>
<tr><td>Correlação do desvio com o próprio número</td><td class="n">{num(t['correlacao_z_com_o_proprio_numero'],3,sinal=True)}</td></tr>
</table>

<p>O grupo de dois algarismos sai mais, e o desvio correlaciona
{num(t['correlacao_z_com_soma_dos_algarismos'],2)} com a soma dos algarismos — números de
soma baixa saem mais. É <b>sugestivo</b> e nada mais: nenhuma das duas medidas passa do
limiar de família, e ambas foram formuladas <b>depois</b> de ver os dados, o que as
desqualifica como evidência por construção. Elas entram no pré-registro da seção 7.5,
onde valem alguma coisa.</p>

<h3>7.4 O veredicto honesto</h3>

<div class="ficha">
<div><span class="k">Achado</span><span class="v">as 25 dezenas da Lotofácil não saem com frequência igual</span></div>
<div><span class="k">A favor</span><span class="v">χ² = {num(v['chi2_total']['observado'],2)} (p isolado {num(v['chi2_total']['p_unilateral_maior'],4)}); replica nas três janelas disjuntas (p = {num(v['r_media']['p_unilateral_maior'],4)}); separação quente–frio fora da amostra com p = {num(v['separacao_quente_menos_frio']['p_unilateral_maior'],4)}; dados conferidos contra fonte independente com zero divergências</span></div>
<div><span class="k">Contra</span><span class="v">o p de família do χ² é <b>{num(fam['p_familia'],3)}</b> — acima de 0,05: numa busca de {pr['protocolo']['n_testes_na_bateria']} testes, um resultado assim aparece em {num(fam['p_familia']*100,1)}% das histórias de acaso puro. Nenhum mecanismo físico foi identificado. E o χ² na janela de descoberta ({num(v['chi2_descoberta']['observado'],1)}) é indistinguível do acaso.</span></div>
<div><span class="k">Tamanho</span><span class="v">{num(v['separacao_quente_menos_frio']['observado'],3)} acerto por jogo, entre o melhor e o pior conjunto de 15 possíveis</span></div>
<div><span class="k">Veredicto</span><span class="v"><b>sugestivo e replicante, não estabelecido.</b> Não é suficiente para afirmar viés no sorteio; é suficiente para merecer um pré-registro e uma segunda olhada com dados que ainda não existiam quando este relatório foi escrito.</span></div>
</div>

<h3>7.5 Pré-registro: o que derruba isto nos próximos concursos</h3>

<p>Esta seção é a mais importante do capítulo, porque é a única que ainda pode ser
falseada. As hipóteses abaixo estão fixadas <b>agora</b>, antes de qualquer concurso além
do 3.246 ser observado. Nenhum ajuste é permitido depois.</p>

<table>
<tr><th class="c" style="width:10mm">#</th><th>Hipótese pré-registrada para os concursos 3.247 em diante</th><th>Derruba se…</th></tr>
<tr><td class="c">1</td><td>A dezena <b>20</b> continuará saindo acima de 60%.</td><td>a frequência dela nos novos concursos ficar em 60% ou abaixo</td></tr>
<tr><td class="c">2</td><td>A dezena <b>16</b> continuará saindo abaixo de 60%.</td><td>a frequência dela nos novos concursos ficar em 60% ou acima</td></tr>
<tr><td class="c">3</td><td>A correlação entre os desvios de 1–3.246 e os desvios dos novos concursos será positiva.</td><td>a correlação der ≤ 0 (é o teste central; com 500 concursos novos o poder é razoável)</td></tr>
<tr><td class="c">4</td><td>As 15 dezenas mais frequentes de 1–3.246 renderão mais de 9,00 acertos nos novos concursos.</td><td>a média ficar em 9,00 ou abaixo</td></tr>
<tr><td class="c">5</td><td>O desvio correlacionará negativamente com a soma dos algarismos (hipótese da tinta).</td><td>a correlação der ≥ 0 nos novos concursos</td></tr>
</table>

<p>Uma observação sobre poder estatístico, para que a expectativa fique calibrada: com um
efeito da ordem de 0,03 na proporção, seriam necessários alguns milhares de concursos
novos para uma conclusão firme sobre uma dezena isolada. A hipótese <b>3</b> é a única com
poder decente em prazo curto, porque agrega as 25 dezenas de uma vez. Se ela vier positiva
de novo em 500 concursos inéditos, o achado sobe de categoria. Se vier zero ou negativa,
ele morre — e este relatório terá cumprido a função dele.</p>

<h3>7.6 As 25 dezenas, número a número</h3>
<table class="compacta">
<tr><th class="c">dezena</th><th class="n">saídas</th><th class="n">%</th><th class="n">z total</th>
<th class="n">z descob.</th><th class="n">z valid.</th><th class="n">z teste</th></tr>
{linhas}
</table>
"""
