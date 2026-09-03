# -*- coding: utf-8 -*-
"""Capítulo 4 (assertividade) e capítulo 5 (as sete teorias inéditas)."""
from relatorio_base import fig, milhar, num, pct


def assertividade(D):
    cc = D.get("catalogo_controle", {})
    regras = [r for r in D["assertividade"]["regras"] if r["janela"] == "historico_todo"]
    teste = {r["regra"]: r for r in D["assertividade"]["regras"] if r["janela"] == "apenas_teste"}
    linhas = []
    for r in sorted(regras, key=lambda x: -x["assertividade_exata"]):
        t = teste[r["regra"]]
        linhas.append(
            f'<tr><td>{r["afirma"]}</td>'
            f'<td class="n">{milhar(r["combinacoes_no_espaco"])}</td>'
            f'<td class="n">{pct(r["assertividade_exata"])}</td>'
            f'<td class="n">{pct(r["assertividade_medida"])}</td>'
            f'<td class="n">{pct(t["assertividade_medida"])}</td>'
            f'<td class="n">{num(r["ganho"],3)}</td>'
            f'<td class="n">{num(r["z"],2,sinal=True)}</td></tr>')
    comb = [r for r in regras if "cinturao" in r["regra"]]
    lc = []
    for r in comb:
        ind = r.get("assertividade_se_fossem_independentes", 0)
        lc.append(f'<tr><td>{r["afirma"]}</td>'
                  f'<td class="n">{pct(ind)}</td>'
                  f'<td class="n">{pct(r["assertividade_exata"])}</td>'
                  f'<td class="n">{num(r["assertividade_exata"]/ind if ind else 0,2)}×</td>'
                  f'<td class="n">{milhar(r["combinacoes_no_espaco"])}</td></tr>')
    n_regras = len(regras)
    cc_real, cc_p50 = num(cc.get("max_z_real", 0), 2), num(cc.get("nulo_p50", 0), 2)
    cc_p95, cc_max = num(cc.get("nulo_p95", 0), 2), num(cc.get("nulo_max", 0), 2)
    cc_pfam, cc_n = num(cc.get("p_familia", 0), 3), milhar(cc.get("n_falsas", 0))
    cc_nr = cc.get("n_regras", 0)
    return f"""
<div class="quebra"></div>
<h2>4 · Assertividade: onde ela existe e por que não é vantagem</h2>

<p>Este capítulo responde diretamente ao pedido que originou o estudo: <i>“não quero o
padrão que ganha, mas o que tiver uma taxa de assertividade boa”</i>. O pedido é bom e tem
resposta. Mas a resposta tem duas metades, e separá-las é o resultado mais útil de todo
este trabalho.</p>

<table>
<tr><th style="width:30mm">Assertividade</th><td>com que frequência a regra acerta.</td></tr>
<tr><th style="width:30mm">Ganho</th><td>quanto ela acerta <b>acima do que o próprio tamanho dela já garantiria</b>.</td></tr>
</table>

<h3>4.1 O teorema do ganho igual a um</h3>

<div class="achado">
<span class="rot">Teorema 3 · assertividade é tamanho</span>
<p>Se os sorteios são uniformes sobre as 3.268.760 combinações, então para <b>qualquer</b>
regra estrutural R:</p>
<p style="text-align:center;font-size:11pt;margin:3mm 0">
assertividade(R) = fração do espaço ocupada por R &nbsp;&nbsp;⟹&nbsp;&nbsp; ganho(R) = 1,000</p>
<p>Uma regra que acerta 95% dos concursos acerta porque <b>ocupa</b> 95% do espaço. Não
existe regra estrutural com assertividade alta e espaço pequeno — a menos que os sorteios
não sejam uniformes. E é exatamente isso que a tabela seguinte mede.</p>
</div>

<h3>4.2 O catálogo: {n_regras} regras, medidas uma a uma</h3>

<p>Este é o <b>livro de padrões</b> propriamente dito. Reuni tudo que circula como teoria
de Lotofácil — soma, paridade, primos, moldura, miolo, vizinhança, sequências, linhas,
colunas, terminações, altas e baixas, Fibonacci, múltiplos de 3 e de 5, extremos do volante
— e calculei a probabilidade <b>exata</b> de cada uma percorrendo as 3.268.760 combinações.
Nenhum número da coluna “exata” é estimado.</p>

<p>Cada linha é uma afirmação sobre o próximo concurso. As duas colunas seguintes são a
taxa de acerto observada: no histórico completo, e depois só na janela de teste, que
nenhuma regra viu ao ser escrita.</p>

<table class="compacta">
<tr><th>A regra afirma que…</th><th class="n">combinações</th><th class="n">exata</th>
<th class="n">medida (3.246)</th><th class="n">só no teste (649)</th><th class="n">ganho</th><th class="n">z</th></tr>
{''.join(linhas)}
</table>

<div class="destaque">
<p><b>O catálogo passou pelo mesmo controle negativo.</b> O maior |z| entre as
{cc_nr} regras simples do catálogo (os três cinturões, por serem combinações das
outras, ficam de fora para não contar o mesmo dado duas vezes) foi <b>{cc_real}</b> (a regra “a maior sequência corrida
tem no máximo 5 dezenas”). Rodando o catálogo inteiro em {cc_n} histórias de acaso puro, o
maior |z| deu {cc_p50} na mediana e {cc_p95} no percentil 95, chegando a {cc_max}. O
p de família do melhor achado do catálogo é <b>{cc_pfam}</b> — nada sobrevive. Nem mesmo a
regra que, isolada, teria p ≈ 0,003.</p>
</div>

<figure>
  <img src="{fig('05_ganho_igual_um.png')}">
  <figcaption><b>Figura 5.</b> Cada ponto é uma das {n_regras} regras do catálogo. Eixo horizontal: a
  fração das 3.268.760 combinações que a regra aceita. Eixo vertical: a fração dos 3.246
  concursos que ela acertou. A reta tracejada é ganho = 1. Nenhuma regra sai dela.</figcaption>
</figure>

<h3>4.3 Cinturões: por que multiplicar as probabilidades erra</h3>

<p>Filtros de loteria costumam ser empilhados — “soma central <i>e</i> paridade equilibrada
<i>e</i> moldura na faixa” — e a probabilidade do conjunto costuma ser calculada
multiplicando as individuais. <b>Isso está errado</b>, e o erro é sempre no mesmo sentido:
faz o filtro parecer muito mais seletivo do que é.</p>

<p>A razão é que as regras não são independentes: somas centrais tendem a vir com paridade
equilibrada, porque as duas coisas medem o mesmo equilíbrio por caminhos diferentes.
Enumerando, conta-se a interseção de verdade:</p>

<table>
<tr><th>Cinturão</th><th class="n">se fossem independentes</th><th class="n">real (enumerado)</th>
<th class="n">erro</th><th class="n">combinações restantes</th></tr>
{''.join(lc)}
</table>

<p>O cinturão pesado — os seis filtros populares ao mesmo tempo — parece deixar passar
menos de metade do que realmente deixa. Quem calcula assim acredita ter reduzido o espaço
muito mais do que reduziu, e a superestimação da seletividade é a origem de boa parte da
sensação de que “o filtro está funcionando”.</p>

<h3>4.4 O que “boa taxa de assertividade” significa de verdade</h3>

<p>Existem, na Lotofácil, afirmações sobre o próximo concurso com taxa de acerto altíssima
e absolutamente confiáveis. Elas são reais, são úteis para um projeto científico, e não
servem para apostar. Três exemplos, todos exatos:</p>

<table>
<tr><th>Afirmação sobre o próximo concurso</th><th class="n">acerta</th><th>por quê</th></tr>
<tr><td>Repetirá ao menos 5 dezenas do concurso anterior</td><td class="n">100,000%</td><td>Teorema 1 — aritmética</td></tr>
<tr><td>Terá ao menos 4 pares de dezenas vizinhas</td><td class="n">100,000%</td><td>Teorema 2 — aritmética</td></tr>
<tr><td>Repetirá entre 7 e 11 dezenas do anterior</td><td class="n">93,7%</td><td>hipergeométrica exata</td></tr>
<tr><td>Terá soma entre 166 e 224</td><td class="n">89,7%</td><td>ocupa 89,7% do espaço</td></tr>
</table>

<div class="destaque">
<p><b>A leitura correta.</b> Uma regra com 89,7% de assertividade não dá 89,7% de chance de
prêmio: ela recorta 89,7% das combinações, e dentro desse recorte a chance de cada
combinação continua sendo exatamente 1 em 3.268.760. O que a regra faz é <b>descrever</b>
o sorteio, não <b>prever</b>. Para o projeto, isso vale como a definição operacional que
faltava: <i>assertividade sem ganho é descrição; só assertividade com ganho maior que 1
seria previsão</i>. E ganho maior que 1 não apareceu em nenhuma das {n_regras}.</p>
</div>
"""


def _ficha(nome, origem, afirma, derruba, medida, veredicto, morto=True):
    cls = "morto" if morto else "achado"
    rot = "derrubada pelos dados" if morto else "sobreviveu"
    return f"""
<div class="{cls}">
<span class="rot">{rot}</span>
<div class="ficha" style="margin-top:0">
<div><span class="k">Teoria</span><span class="v"><b>{nome}</b> — origem: {origem}</span></div>
<div><span class="k">Afirma</span><span class="v">{afirma}</span></div>
<div><span class="k">Derruba</span><span class="v">{derruba}</span></div>
<div><span class="k">Medida</span><span class="v">{medida}</span></div>
<div><span class="k">Veredicto</span><span class="v">{veredicto}</span></div>
</div></div>"""


def teorias_novas(D):
    I = D["inovacoes"]
    c, e, i, a, n, m, s = (I["I_complemento"], I["II_eco_posicional"], I["III_inercia"],
                           I["IV_atrito"], I["V_nucleo"], I["VI_mare"], I["VII_espelho"])
    nj = n["janelas"]
    return f"""
<div class="quebra"></div>
<h2>5 · As sete teorias inéditas</h2>

<p>O pedido foi explícito: <i>“não quero nada conhecido, quero que você inove”</i>. As sete
teorias deste capítulo não vieram do folclore de loteria nem dos volumes já existentes do
projeto. Cada uma nasceu de uma pergunta que ninguém parecia estar fazendo, e o critério
para entrar aqui foi um só: <b>olhar para uma dimensão que as outras análises jogam
fora</b>. Todas as sete carregam, como exige a base de conhecimento do projeto, a
declaração do que as derrubaria — escrita antes de a medida ser feita.</p>

<p>Adianto o resultado para não construir suspense falso: <b>as sete morreram</b>. Duas
delas pareceram vivas por algumas horas, até que o nulo correto fosse aplicado, e essas
duas viraram o capítulo 8, que é provavelmente a parte mais aproveitável deste relatório
para o projeto.</p>

<h3>5.1 I — Teoria do Complemento (as dez ausentes)</h3>

<p>Todo mundo estuda as 15 dezenas que saíram. Esta teoria estuda as <b>10 que não
saíram</b>, e a escolha tem uma justificativa técnica, não estética: pelo Teorema 1, duas
listas de 15 têm interseção mínima <b>forçada</b> de 5, o que comprime qualquer sinal
contra um piso aritmético. As listas de 10 ausentes têm interseção mínima <b>zero</b> —
o complemento tem mais liberdade, e um sinal do mesmo tamanho aparece nele com mais
contraste.</p>

{_ficha("Complemento", "minha",
  "as 10 ausentes carregam estrutura que as 15 sorteadas diluem — em particular, ausências que se repetem de um concurso para o outro",
  "a interseção das ausências seguir exatamente H(25,10,10), de média 4,0, e a contagem de blocos bater com o nulo",
  f"interseção média medida <b>{num(c['intersecao_media_medida'],4)}</b> contra <b>{num(c['intersecao_media_exata'],4)}</b> exatos "
  f"(z = {num(c['z_media'],2,sinal=True)}); χ² da distribuição inteira: z = {num(c['chi2_z'],2,sinal=True)}. "
  f"As 10 ausentes formam {num(c['blocos_media'],2)} blocos em média, com {num(c['isoladas_media'],2)} isoladas.",
  "morta. O complemento é tão sem memória quanto o conjunto sorteado. A dimensão extra de liberdade não revelou nada — o que, invertendo o argumento, <b>reforça</b> a conclusão de uniformidade.")}

<h3>5.2 II — Teoria do Eco Posicional (a ordem do globo)</h3>

<p>Esta é a única bateria do estudo capaz, em princípio, de detectar viés <b>mecânico</b>.
Todas as outras olham o conjunto, e o conjunto é invariante a qualquer coisa que a máquina
faça na ordem de extração. Se uma bola fosse mais pesada, mais gasta, ou carregada por
último, isso apareceria na <b>posição</b> em que ela sai — e desapareceria por completo ao
ordenar as quinze dezenas.</p>

{_ficha("Eco Posicional", "minha",
  "a ordem de saída do globo carrega informação física que o conjunto ordenado destrói; e sair cedo prediz sair de novo no concurso seguinte",
  "a tabela dezena × posição bater com o nulo, a posição média de cada dezena não se separar de 8,0, e a posição não prever repetição",
  f"tabela 25×15: χ² = {num(e['chi2_dezena_x_posicao'],1)} com {e['df']} graus (z = {num(e['chi2_z'],2,sinal=True)}). "
  f"Maior desvio de posição média entre as 25 dezenas: {num(e['maior_z_posicao'],2)} (dezena {e['dezena_do_maior_z']}). "
  f"Primeira bola do globo, uniforme sobre as 25: z = {num(e['z_primeira_bola'],2,sinal=True)}. "
  f"Diferença de posição média entre as que repetem e as que não repetem: "
  f"{num(e['diferenca_posicao_repete_menos_nao_repete'],4,sinal=True)} posição (z = {num(e['z_eco'],2,sinal=True)}, em {milhar(e['n_pares_usados'])} pares).",
  "morta, e este é o resultado mais tranquilizador do relatório. A ordem de extração é a testemunha mais sensível de vício mecânico que existe nesta base, e ela não acusa nada.")}

<h3>5.3 III — Teoria da Inércia de Repetição</h3>

<p>Em princípio, a teoria mais promissora das sete. A quantidade de repetições é a única
grandeza da Lotofácil que <b>liga dois concursos por construção</b>. Se houvesse memória em
algum lugar, o caminho mais curto até ela passaria por aqui: concursos que repetem muito
seriam seguidos por concursos que repetem muito, como se o sorteio "esquentasse" numa
vizinhança do espaço de combinações.</p>

{_ficha("Inércia de Repetição", "minha",
  "a quantidade de repetições tem inércia: depois de um concurso que repetiu muito, o seguinte também repete muito",
  "a matriz de transição entre faixas de repetição ser indistinguível do produto das marginais, e a autocorrelação de lag 1 ser nula",
  f"autocorrelação de lag 1 da série de repetições: <b>{num(i['autocorr_lag1'],4,sinal=True)}</b> "
  f"(z = {num(i['z_autocorr'],2,sinal=True)} em {milhar(i['n'])} pares). "
  f"Matriz de transição 11×11: z do χ² = {num(i['chi2_z'],2,sinal=True)}. "
  f"Média de repetições medida: {num(i['media'],4)} contra 9,0000 exatos.",
  f"morta. A autocorrelação de {num(i['autocorr_lag1'],4,sinal=True)} rende z = {num(i['z_autocorr'],2)}, "
  f"que num teste isolado passaria por significativo — e que fica bem abaixo do "
  f"{num(D['protocolo']['controle_negativo']['max_z_p50'],2)} que a bateria produz na história falsa <i>mediana</i>. "
  f"É o exemplo didático perfeito do capítulo 2.")}

<h3>5.4 IV — Teoria do Atrito de Pares (a rede das 300 duplas)</h3>

<p>Em vez de tratar as 300 duplas de dezenas como 300 contagens soltas, esta teoria as
trata como uma <b>rede</b>: cada dezena é um nó, cada coocorrência é um peso de aresta. A
pergunta passa a ser estrutural — a rede tem comunidades, agrupamentos, dezenas que
"andam juntas" além do acaso?</p>

{_ficha("Atrito de Pares", "minha",
  "algumas duplas de dezenas saem juntas além do acaso, e a rede de coocorrência tem modularidade acima da de uma rede aleatória",
  "a modularidade cair dentro da faixa que histórias falsas produzem, e o maior |z| das 300 duplas idem",
  f"maior z entre as 300 duplas: <b>{num(a['maior_z'],2,sinal=True)}</b> (dupla {a['duplas_mais_juntas'][0]['dupla']}); "
  f"menor: {num(a['menor_z'],2,sinal=True)} (dupla {a['duplas_mais_separadas'][0]['dupla']}). "
  f"Duplas acima de 2σ: <b>{a['duplas_acima_de_2sigma']}</b>, contra {num(a['esperado_acima_de_2sigma'],1)} esperadas. "
  f"Modularidade da rede: {num(a['modularidade'],5)} (rede aleatória: ~0).",
  "morta — mas só depois de uma investigação, e por um motivo que virou seção própria. Ver abaixo.")}

<div class="destaque">
<p><b>A investigação que esta teoria exigiu.</b> {a['duplas_acima_de_2sigma']} duplas acima
de 2σ contra {num(a['esperado_acima_de_2sigma'],1)} esperadas é um excesso de três vezes, e
o desvio-padrão dos 300 z's deu <b>1,389</b> onde deveria dar 1,0. Em histórias falsas o
mesmo cálculo dá {num(0.994,3)} e o maior |z| não passa de {num(2.95,2)} em média. Parecia
achado grande.</p>
<p>Não era. Olhando <b>quais</b> duplas: das dez mais “juntas”, sete contêm a <b>dezena
20</b>; das dez mais “separadas”, cinco contêm a <b>dezena 16</b>. Não é efeito de dupla —
é efeito de dezena isolada, contaminando todas as 24 duplas de que ela participa. A rede
não tem comunidades: tem dois nós com frequência marginal um pouco fora do lugar. Esse fio
levou ao capítulo 7, que é o único achado do estudo.</p>
</div>

<h3>5.5 V — Teoria do Núcleo Persistente</h3>

<p>A ideia popular do "núcleo" — um grupo de dezenas que aparece em quase todos os
concursos de uma sequência — é interessante porque tem um nulo exato e nada intuitivo.
Com 60% de chance por dezena por concurso, a interseção de <i>w</i> concursos tem
25 · (3/5)<sup>w</sup> dezenas esperadas. Para w = 5, isso já dá <b>1,94 dezenas</b>.</p>

{_ficha("Núcleo Persistente", "minha",
  "existe um grupo de dezenas que persiste por janelas longas além do que a sobreposição forçada de 60% já explica",
  "a contagem de dezenas presentes em todos os w concursos bater com o valor exato 25·(3/5)^w",
  "".join(f"janela de {k.split('_')[1]}: medido {num(v['media_medida'],3)}, exato {num(v['media_exata'],3)}"
          + ("" if v.get("aproximacao_normal_valida", True) else " <i>(esperado &lt; 5: aproximação normal inválida, z sem sentido)</i>")
          + f", z = {num(v['z'],2,sinal=True)}. " for k, v in nj.items()),
  "morta. E ela entrega de brinde uma correção de leitura: quem vê duas dezenas presentes nos últimos cinco concursos e chama isso de núcleo está descrevendo <b>a média</b> (1,94), não uma descoberta.")}

<h3>5.6 VI — Teoria da Maré (deriva em 21 anos)</h3>

<p>Vinte e um anos de operação envolvem troca de globo, de lote de bolas e de máquina. A
teoria da maré procura o rastro disso: não um padrão de curto prazo, mas uma <b>deriva
lenta</b> na frequência de algumas dezenas ao longo das décadas.</p>

{_ficha("Maré", "minha",
  "troca de globo, de lote de bolas e de máquina deixam deriva lenta na frequência de algumas dezenas ao longo de 21 anos",
  "a tabela dezena × época bater com o nulo, e o maior desvio acumulado padronizado ficar dentro do controle negativo",
  f"tabela 8 épocas × 25 dezenas: χ² corrigido = {num(m['chi2'],1)} com {m['df']} graus, z = {num(m['chi2_z'],2,sinal=True)}. "
  f"Maior desvio acumulado padronizado ao longo da série: {num(m['maior_ponte'],2)} (dezena {m['dezena_da_maior_ponte']}).",
  "morta — mas só depois de eu corrigir um erro meu que a fazia parecer <b>fortemente</b> anômala no sentido oposto. É a seção 9.1.")}

<figure>
  <img src="{fig('09_ponte_browniana.png')}">
  <figcaption><b>Figura 9.</b> As 25 trajetórias de desvio acumulado ao longo de 3.246
  concursos, padronizadas para que o acaso puro produza um passeio dentro da faixa de ±2.
  Destacadas as duas dezenas extremas: 20 (vermelho) e 16 (verde). Não há deriva
  sistemática — há passeio aleatório, com duas trajetórias que se afastam mais do que as
  outras e não voltam.</figcaption>
</figure>

<h3>5.7 VII — Teoria do Espelho (a simetria n ↔ 26−n)</h3>

<p>O volante 5×5 tem centro exato: a dezena 13. Toda outra dezena tem um par espelhado
(1↔25, 2↔24, … 12↔14). Se houvesse qualquer estrutura geométrica no sorteio — carregamento
simétrico do globo, ordem de inserção das bolas — a contagem de pares espelhados que saem
juntos seria o detector natural.</p>

{_ficha("Espelho", "minha",
  "a simetria n ↔ 26−n do volante deixa marca: dezenas espelhadas tendem a sair juntas, ou tendem a se evitar",
  "a contagem de pares espelhados por concurso bater com o nulo",
  f"média medida de pares espelhados por concurso: {num(s['media_medida'],4)}; nulo ({s['nulo_por']}): "
  f"{num(s['media_nula'],4)}. z = {num(s['z'],2,sinal=True)}.",
  "morta. A geometria do volante não deixa marca nenhuma — o que é esperado, já que o volante é um artefato de impressão do bilhete e o globo não sabe que ele existe.")}

<div class="destaque">
<p><b>Balanço do capítulo.</b> Sete teorias inéditas, sete mortes. Isso não é fracasso do
método: é o método funcionando. O valor delas para o projeto não está em terem dado
positivo — está em terem sido escritas com o critério de falseamento <b>antes</b> da
medida, e em duas delas terem exposto erros de nulo que estavam prontos para contaminar
qualquer análise futura do repositório.</p>
</div>
"""
