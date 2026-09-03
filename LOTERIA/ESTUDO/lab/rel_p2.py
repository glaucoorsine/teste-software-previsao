# -*- coding: utf-8 -*-
"""Capítulos 1 a 4: o material, o método, o acaso exato, a assertividade."""
from relatorio_base import fig, milhar, num, pct


def material(D):
    it = D["protocolo"]["integridade"]
    return f"""
<div class="quebra"></div>
<h2>1 · O material</h2>

<p>Três mil duzentos e quarenta e seis concursos, do primeiro (setembro de 2003) ao
3.246 (novembro de 2024). Quinze dezenas sorteadas de um universo de vinte e cinco, em
todos eles, sem exceção. É a série mais longa e mais densa que qualquer loteria brasileira
oferece: a Mega-Sena tem menos concursos e muito menos informação por concurso — seis
dezenas de sessenta contra quinze de vinte e cinco.</p>

<h3>1.1 Procedência, integridade e o concurso 2425</h3>

<p>A API oficial da Caixa não é alcançável do ambiente onde este estudo rodou — a política
de rede bloqueia o domínio. Os dados vieram de um espelho público que replica os
resultados oficiais por rotina automática diária. Isso obriga a conferir mais, não menos,
e a conferência está descrita na seção seguinte.</p>

<div class="ficha">
<div><span class="k">Concursos</span><span class="v">{milhar(it['n_concursos'])}, do {it['primeiro']} ao {it['ultimo']}</span></div>
<div><span class="k">Faltando</span><span class="v">{len(it['concursos_faltando'])} — a série é contínua, sem um único buraco</span></div>
<div><span class="k">Dezenas/conc.</span><span class="v">{it['tamanhos_distintos']} em todos — nenhum concurso com número errado de bolas</span></div>
<div><span class="k">Fora do universo</span><span class="v">{len(it['dezenas_fora_do_universo'])} — nenhuma dezena fora de 1–25</span></div>
<div><span class="k">Repetidas</span><span class="v">{it['concursos_com_dezena_repetida']} — nenhum concurso com dezena duplicada</span></div>
<div><span class="k">Ordem de saída</span><span class="v">preservada: as dezenas vêm na ordem em que saíram do globo</span></div>
</div>

<p>A última linha da ficha merece parágrafo próprio, porque é uma dimensão que quase
nenhum estudo de loteria usa. A fonte publica as quinze dezenas <b>na ordem de extração</b>,
não ordenadas. Um conjunto {{1, 2, 3}} apaga a informação de qual bola saiu primeiro; se
existisse desgaste, diferença de peso, ou qualquer efeito mecânico, seria <b>na ordem</b>
que ele apareceria — e ele some quando se ordena. A Teoria do Eco Posicional (seção 5.2)
existe só por causa dessa coluna.</p>

<div class="destaque">
<p><b>Um concurso está diferente dos outros 3.245.</b> A verificação de integridade
procurou concursos cuja lista já viesse ordenada em ordem crescente. Sob ordem real de
sorteio, a chance de isso acontecer é 1 em 15! — cerca de {num(it['esperado_ordenados_por_acaso']*1e9,3)}
em um bilhão por concurso, ou {num(it['esperado_ordenados_por_acaso'],9)} em toda a série.
Apareceu <b>um</b>: o <b>concurso 2425</b>, com as dezenas
1, 3, 4, 5, 6, 10, 11, 13, 15, 19, 20, 21, 22, 24, 25 em ordem perfeita. Isso não é
coincidência astronômica: é a fonte não tendo a ordem daquele concurso e gravando o
conjunto ordenado. O conjunto dele é válido; a <b>ordem</b> não é. Por isso o concurso 2425
foi <b>excluído de toda a bateria posicional</b> e mantido em todas as outras. Um único
registro contaminado em 3.246 é irrelevante para a conclusão, mas registrá-lo é o que
separa uma auditoria de uma apresentação.</p>
</div>

<h3>1.2 Conferência cruzada contra fonte independente</h3>

<p>Base errada não dá erro: dá número plausível e falso, que é pior. Por isso os dados
foram conferidos contra uma <b>segunda fonte, de origem diferente</b> — um conjunto de
planilhas de resultados que percorreu outro caminho até chegar aqui, cobrindo os concursos
1 a 2.696.</p>

<table>
<tr><th>Verificação</th><th class="n">Divergências</th><th>Leitura</th></tr>
<tr><td>Conjuntos de 15 dezenas, concursos 1–2696</td><td class="n">0</td><td>as duas fontes concordam em todos</td></tr>
<tr><td>Ordem de extração, concursos 1–2696</td><td class="n">0</td><td>concordam inclusive na ordem das bolas</td></tr>
<tr><td>Frequência acumulada das 25 dezenas</td><td class="n">0</td><td>vetores idênticos</td></tr>
</table>

<p>Zero divergências em 2.696 concursos, incluindo a ordem. É a conferência mais forte
disponível sem acesso direto à Caixa, e ela importa muito para o capítulo 7: o único
achado do estudo é uma diferença de frequência de poucos centésimos, e um erro de
transcrição em uma dúzia de concursos bastaria para fabricá-la. Não há erro desse tipo.</p>
"""


def metodo(D):
    pr = D["protocolo"]; cn = pr["controle_negativo"]; c = pr["protocolo"]["cortes"]
    return f"""
<div class="quebra"></div>
<h2>2 · O método</h2>

<h3>2.1 Por que o corte é cronológico</h3>

<p>Os 3.246 concursos foram partidos em três blocos, na ordem do tempo e nunca ao acaso:</p>

<table>
<tr><th>Bloco</th><th class="n">Concursos</th><th class="n">Quantidade</th><th>Para quê</th></tr>
<tr><td><b>Descoberta</b></td><td class="n">1 – 1.948</td><td class="n">1.948 (60%)</td><td>garimpar à vontade; nada aqui vale como prova</td></tr>
<tr><td><b>Validação</b></td><td class="n">1.949 – 2.597</td><td class="n">649 (20%)</td><td>primeira confirmação independente</td></tr>
<tr><td><b>Teste</b></td><td class="n">2.598 – 3.246</td><td class="n">649 (20%)</td><td>a última, olhada uma única vez</td></tr>
</table>

<p>O corte é cronológico porque a pergunta é sobre o <b>futuro</b>. Um corte aleatório
deixaria o modelo enxergar 2024 para "prever" 2015, e isso infla qualquer resultado. É o
vazamento temporal, e é o erro que mais produz "inteligência artificial que acerta loteria"
na internet: quase sempre o modelo foi treinado e testado no mesmo período embaralhado.</p>

<h3>2.2 O controle negativo — a ideia central do estudo</h3>

<p>Procurando padrão em 3.246 concursos com centenas de testes diferentes, <b>encontra-se
alguma coisa</b>. Não porque exista, mas porque centenas de testes num ruído produzem, por
construção, alguns extremos. É assim que quase toda teoria de loteria nasce: alguém
procurou muito e encontrou o inevitável.</p>

<p>A defesa usual é a correção de Bonferroni, e ela não serve aqui. Bonferroni corrige o
número de testes que o pesquisador <b>declara</b> ter feito, e ninguém declara honestamente
quantos olhou — inclusive os que não deram em nada, os que foram descartados no meio, as
variações de parâmetro. A defesa que este estudo usa é outra, e é empírica:</p>

<div class="destaque">
<p>Gerar <b>{milhar(pr['protocolo']['n_historias_falsas'])} históricos falsos</b> — 3.246
concursos cada, sorteados aqui por acaso uniforme, onde a resposta certa é sabidamente
"não há padrão" — e passar por eles <b>a bateria inteira, idêntica</b>. Guardar, de cada
um, o maior |z| que a bateria produziu. Isso dá a distribuição do <b>melhor achado
possível num mundo sem padrão nenhum</b>.</p>
</div>

<p>Daí em diante a pergunta deixa de ser "o z de 4,2 é grande?" — pergunta que não tem
resposta sem contexto — e passa a ser: <b>"num mundo comprovadamente sem padrão, com que
frequência esta mesma bateria produz um z de 4,2?"</b>. Se a resposta for "em 60% das
histórias falsas", o achado morre, e morre com número, não com opinião.</p>

<table>
<tr><th>O que a bateria de {pr['protocolo']['n_testes_na_bateria']} testes produz no acaso puro</th><th class="n">maior |z|</th></tr>
<tr><td>na história falsa mediana</td><td class="n">{num(cn['max_z_p50'])}</td></tr>
<tr><td>no percentil 95</td><td class="n">{num(cn['max_z_p95'])}</td></tr>
<tr><td>no percentil 99</td><td class="n">{num(cn['max_z_p99'])}</td></tr>
<tr><td>no pior caso entre as {milhar(pr['protocolo']['n_historias_falsas'])}</td><td class="n">{num(cn['max_z_maximo'])}</td></tr>
</table>

<p>Leia a segunda linha devagar. <b>Uma em cada vinte buscas deste tamanho, em dados que
são puro ruído, entrega um resultado de {num(cn['max_z_p95'])} desvios-padrão.</b> Em um
teste isolado, {num(cn['max_z_p95'])} sigmas corresponderiam a p ≈ 0,0000014 — o tipo de
número que se apresenta como descoberta definitiva. Aqui, é o esperado.</p>

<h3>2.3 Os dois p-valores: isolado e de família</h3>

<p>Cada um dos {pr['protocolo']['n_testes_na_bateria']} testes recebe dois p-valores, e a
distância entre eles é a lição inteira deste relatório:</p>

<table>
<tr><th style="width:26mm">p isolado</th><td>com que frequência <b>este</b> teste específico produz um |z| assim
no acaso. É o p-valor que todo mundo publica.</td></tr>
<tr><th style="width:26mm">p de família</th><td>com que frequência a bateria <b>inteira</b> produz um |z| assim
em <b>algum</b> de seus {pr['protocolo']['n_testes_na_bateria']} testes, no acaso. É o p-valor
honesto de quem procurou em {pr['protocolo']['n_testes_na_bateria']} lugares.</td></tr>
</table>

<p>Um achado com p isolado de 0,0004 parece ouro. Se o p de família dele for 0,93, ele é
exatamente o que se esperava encontrar procurando tanto — e apresentá-lo como descoberta
seria fraude estatística, mesmo sem má-fé nenhuma. Este relatório reporta os dois, sempre,
inclusive quando o segundo mata o primeiro.</p>

<h3>2.4 A régua exata da Lotofácil</h3>

<p>Há uma coincidência aritmética que organiza o estudo todo e que vale enunciar antes de
qualquer medida. Na Lotofácil saem 15 de 25. Uma <b>aposta</b> de 15 dezenas é, portanto,
matematicamente o mesmo objeto que um <b>concurso</b>. Logo:</p>

<div class="destaque">
<p>Sob acaso, <b>qualquer</b> conjunto de 15 dezenas acerta, em média, exatamente
<b>15 × 15 / 25 = 9,000</b> acertos. As quentes, as frias, as atrasadas, as do aniversário
da avó, as sorteadas ontem — todas, exatamente 9. O desvio-padrão é
{num(1.2247,4)}, e a distribuição é hipergeométrica H(25, 15, 15), sem aproximação
nenhuma.</p>
</div>

<p>Isso torna toda a família de testes de previsão limpa de um jeito raro: o alvo não
precisa ser estimado, é um número fechado. Uma teoria de escolha de dezenas existe se, e
somente se, passar de 9,000 de um jeito que o controle negativo não reproduza. E há um
corolário desconfortável para o folclore: <b>apostar exatamente o resultado do concurso
anterior</b> é uma estratégia tão boa quanto qualquer outra, e igualmente inútil.</p>
"""


def acaso_exato(D):
    d = D["assertividade"]["distribuicoes_exatas"]
    return f"""
<div class="quebra"></div>
<h2>3 · O acaso exato: enumerando as 3.268.760 combinações</h2>

<p>C(25,15) = <b>3.268.760</b>. Esse número cabe na memória de um computador comum, e essa
é uma propriedade rara e valiosa: significa que na Lotofácil <b>não é preciso estimar</b> a
probabilidade de nenhuma afirmação estrutural. Basta contar.</p>

<p>Para saber a chance de "a soma das quinze dezenas ficar entre 166 e 224", não se simula:
percorre-se as 3.268.760 combinações, conta-se quantas satisfazem, divide-se. O resultado
é exato, reproduzível e não tem barra de erro. Na Mega-Sena o mesmo truque custaria 50
milhões de combinações por pergunta; na Lotomania, 5 × 10²⁰ e seria impossível.
<b>A Lotofácil é pequena o bastante para ser resolvida e grande o bastante para ser
interessante</b> — é a loteria certa para um estudo assim, e vale registrar isso como
argumento de escolha metodológica do projeto.</p>

<h3>3.1 Dois teoremas que caem só de contar</h3>

<p>A enumeração completa entrega, de graça, duas afirmações que valem <b>100% dos
concursos passados e de todos os futuros</b>, e que costumam ser vendidas por aí como
padrões descobertos:</p>

<div class="achado">
<span class="rot">Teorema 1 · repetição mínima forçada</span>
<p><b>Dois concursos consecutivos da Lotofácil sempre repetem pelo menos 5 dezenas.</b>
Demonstração: são 15 escolhidas de 25, sobrando 10 fora. Se o concurso seguinte pudesse
evitar 11 ou mais das anteriores, precisaria de 11 dezenas entre as 10 que sobraram.
Impossível. Logo a interseção é ≥ 15 − 10 = 5, sempre.</p>
<p>Consequência prática: quem observa "sempre repetem várias dezenas!" está observando
aritmética, não comportamento do globo. A média é 9 e o mínimo é 5, por contagem.</p>
</div>

<div class="achado">
<span class="rot">Teorema 2 · vizinhança mínima forçada</span>
<p><b>Todo sorteio da Lotofácil contém pelo menos 4 pares de dezenas vizinhas</b> (n e n+1).
Demonstração: as 10 ausentes cortam a fila de 1 a 25 em no máximo 11 blocos de dezenas
presentes. Com 15 dezenas em no máximo 11 blocos, o número de vizinhanças é ≥ 15 − 11 = 4.</p>
<p>Confirmado por enumeração: das 3.268.760 combinações, <b>nenhuma</b> tem menos de 4.
A regra "sempre saem números seguidos" tem 100% de acerto — e zero conteúdo.</p>
</div>

<h3>3.2 As distribuições exatas, medidas contra o real</h3>

<p>A tabela abaixo é a comparação central da auditoria de aleatoriedade: para cada forma
do sorteio, o valor <b>exato</b> vindo da enumeração e o valor <b>medido</b> nos 3.246
concursos.</p>

<table>
<tr><th>Característica</th><th class="n">Média exata</th><th class="n">Média medida</th><th class="n">Diferença</th></tr>
{_linhas_medias(D)}
</table>

<p>As diferenças estão todas na terceira casa decimal. Um mecanismo manipulado, viciado
ou mal calibrado quase inevitavelmente entorta alguma dessas formas — e nenhuma está
torta. <b>Esta tabela é a evidência mais forte deste relatório, e ela é a favor da
lisura do sorteio</b>, não contra.</p>

<figure>
  <img src="{fig('07_distribuicoes_estruturais.png')}">
  <figcaption><b>Figura 7.</b> Quatro formas do sorteio. Azul: o exato, obtido percorrendo
  as 3.268.760 combinações. Vermelho: o medido em 3.246 concursos reais. Não há espaço
  entre as duas leituras.</figcaption>
</figure>

<figure>
  <img src="{fig('04_repeticoes.png')}">
  <figcaption><b>Figura 4.</b> Quantas dezenas se repetem de um concurso para o seguinte.
  A distribuição exata é hipergeométrica H(25,15,15) e nunca desce abaixo de 5
  (Teorema 1). A média medida em 3.245 pares é {num(D['inovacoes']['III_inercia']['media'],4)},
  contra 9,0000 exatos.</figcaption>
</figure>
"""


def _linhas_medias(D):
    import numpy as np
    d = D["assertividade"]["distribuicoes_exatas"]
    nomes = {"soma": "Soma das 15 dezenas", "pares": "Quantidade de dezenas pares",
             "primos": "Quantidade de primos", "moldura": "Dezenas na moldura do volante",
             "consecutivos": "Pares de dezenas vizinhas",
             "fibonacci": "Dezenas de Fibonacci"}
    out = []
    for k, nome in nomes.items():
        ex = np.array(d[k]["exato"]); me = np.array(d[k]["medido"])
        v = np.arange(len(ex))
        mex = float((v * ex).sum()); mme = float((v * me).sum())
        out.append(f'<tr><td>{nome}</td><td class="n">{num(mex,4)}</td>'
                   f'<td class="n">{num(mme,4)}</td>'
                   f'<td class="n">{num(mme-mex,4,sinal=True)}</td></tr>')
    out.append('<tr><td>Repetições do concurso anterior</td><td class="n">9,0000</td>'
               f'<td class="n">{num(D["inovacoes"]["III_inercia"]["media"],4)}</td>'
               f'<td class="n">{num(D["inovacoes"]["III_inercia"]["media"]-9,4,sinal=True)}</td></tr>')
    return "".join(out)
