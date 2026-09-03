# -*- coding: utf-8 -*-
"""Capítulos 8 a 10 e apêndices."""
import numpy as np
from relatorio_base import fig, milhar, num, pct



def _multi(cabecalhos, linhas, ncols, larguras=None):
    """Uma tabela só, com `ncols` grupos de colunas por linha.

    Multicoluna de CSS quebra tabelas longas de forma imprevisível — a segunda
    coluna estoura a largura e o conteúdo some na margem. Empilhar os grupos
    dentro de UMA tabela resolve: a quebra de página passa a ser de linha, que
    é o que o navegador sabe fazer direito.
    """
    n = len(linhas)
    alt = -(-n // ncols)
    th = "".join(cabecalhos * ncols)
    cg = ""
    if larguras:
        cg = "<colgroup>" + "".join(f'<col style="width:{w}%">'
                                    for w in list(larguras) * ncols) + "</colgroup>"
    corpo = []
    for i in range(alt):
        cel = []
        for c in range(ncols):
            j = i + c * alt
            cel.append(linhas[j] if j < n else '<td colspan="%d"></td>' % len(cabecalhos))
        corpo.append("<tr>" + "".join(cel) + "</tr>")
    return f'<table class="compacta">{cg}<tr>{th}</tr>{"".join(corpo)}</table>'


def erros(D):
    m = D["inovacoes"]["VI_mare"]
    return f"""
<div class="quebra"></div>
<h2>9 · Cinco erros de método encontrados — quatro deles meus</h2>

<p>Este capítulo é, na minha avaliação, a parte mais aproveitável do relatório para o
projeto. Ele não descreve o que a Lotofácil faz: descreve <b>armadilhas de medição</b> que
estavam prontas para produzir descobertas falsas, quatro delas encontradas porque eu
mesmo caí nelas durante este estudo e tive de voltar atrás.</p>

<h3>9.1 O χ² de contingência deflacionado pelo fator (1−p)</h3>

<p>Este é o erro mais grave e o mais fácil de cometer, e ele afeta qualquer análise que
cruze dezenas com épocas, com dias da semana, com máquinas ou com qualquer outra
categoria.</p>

<p>O χ² de contingência divide o desvio ao quadrado pelo valor esperado E, porque assume
variância igual a E — a hipótese de Poisson. Mas a contagem de uma dezena ao longo de
<i>n</i> concursos <b>não</b> é Poisson: é Binomial(<i>n</i>, 0,6), cuja variância é
<b>E · (1 − p) = 0,4 · E</b>. Dividir por E em vez de por 0,4·E deflaciona o χ² por um
fator de 2,5.</p>

<div class="morto">
<span class="rot">o erro, medido</span>
<p>Na minha Teoria da Maré (dezena × 8 épocas, 168 graus de liberdade), o χ² bruto deu
<b>{num(m['chi2_bruto_errado'],1)}</b> contra 168 esperados — o que parecia uma anomalia
enorme <i>no sentido oposto</i>: as frequências seriam <b>uniformes demais</b>, sinal
clássico de dado fabricado ou arredondado. Convertido em z, dava <b>−4,93</b>.</p>
<p>Verificação: rodei o mesmo cálculo em 60 históricos gerados por acaso puro. Eles deram
χ² médio de <b>70,1</b> com df = 168 — razão de {num(0.417,3)}, praticamente o
(1 − p) = 0,4 previsto. Ou seja: o "achado" era a fórmula, não o dado.</p>
<p>Corrigido, o χ² da maré vira <b>{num(m['chi2'],1)}</b> com 168 graus e z =
{num(m['chi2_z'],2,sinal=True)}. Não há deriva por época.</p>
</div>

<p><b>Por que isto importa além deste estudo.</b> Qualquer análise que aplique o χ² de
contingência padrão a contagens de dezenas de loteria vai encontrar tabelas
sistematicamente "uniformes demais" e pode concluir que o sorteio é bom demais para ser
verdade. O fator de correção é (1 − p), e ele muda com a modalidade:
0,40 na Lotofácil (p = 0,60), 0,90 na Mega-Sena (p = 0,10), 0,9375 na Quina.
<b>Na Lotofácil o erro é grande; nas outras, quase invisível</b> — o que torna a
Lotofácil o lugar onde a armadilha aparece e pode ser aprendida.</p>

<h3>9.2 O nulo com p = 0,6 quando a dezena tem p ≠ 0,6</h3>

<p>Já descrito na seção 6.2, mas o princípio geral merece enunciado próprio: <b>ao testar
dependência, o nulo tem de absorver todos os fatos marginais que não são objeto do
teste</b>. Testar autocorrelação contra p = 0,600 quando a dezena tem frequência empírica
0,629 não testa memória — testa a frequência, doze vezes seguidas.</p>

<p>O sintoma diagnóstico é barato e vale como regra: <b>se vários lags de uma mesma série
aparecem juntos no topo da lista, não são vários sinais — é um fato marginal contaminando
vários testes</b>. Memória real em lag 11 sem memória em lag 10 não tem mecanismo físico.</p>

<h3>9.3 Teorias diferentes que são a mesma aposta</h3>

<p>Duas descobertas de álgebra, não de dados, e as duas inflam artificialmente a contagem
de hipóteses testadas:</p>

<table>
<tr><th>Teoria A</th><th>Teoria B</th><th>Relação</th><th class="n">verificado em</th></tr>
<tr><td>“as 15 menos atrasadas”</td><td>“repetir o concurso anterior”</td>
<td>são <b>a mesma aposta</b>: atraso 1 significa exatamente “saiu no concurso anterior”</td>
<td class="n">3.245 de 3.245 concursos</td></tr>
<tr><td>“as 15 mais frias”</td><td>“maior déficit acumulado”</td>
<td>déficit = 0,6·t − frequência; subtrair uma constante não muda a ordem, logo o ranking é <b>idêntico</b></td>
<td class="n">identidade algébrica</td></tr>
</table>

<p>Isso importa por dois motivos. Primeiro, um sistema que trata "menos atrasadas" e
"repetir o anterior" como duas hipóteses independentes está contando duas quando há uma —
e, se as duas "concordarem", vai ler isso como consenso entre métodos, quando é a mesma
conta duas vezes. Segundo, "déficit acumulado" costuma ser apresentado como teoria
sofisticada, ligada à lei dos grandes números, e é apenas "as mais frias" com outro nome.</p>

<h3>9.4 A aproximação normal onde o esperado é 0,001</h3>

<p>Na Teoria do Núcleo, a janela de 20 concursos tem esperança de
<b>25 · 0,6²⁰ = 0,001</b> dezena. O z normal calculado ali deu <b>+2,94</b>, e não significa
absolutamente nada: com esperado abaixo de 5, a distribuição é Poisson e a aproximação
normal é ficção. O código agora marca essas linhas em vez de reportar o z.</p>

<p>A regra prática, que o estudo passou a aplicar em toda parte: <b>categoria com esperado
abaixo de 5 é agrupada ou marcada, nunca reportada como z</b>. É a origem de boa parte dos
"padrões raríssimos" que circulam — eventos que aconteceram três vezes onde se esperava
uma, e cuja razão de 3 vezes não é notícia nenhuma.</p>

<h3>9.5 O critério de aceitação do v8 aceita 58% do ruído</h3>

<p>O sistema “Super Cérebro Loterias v8.0” do projeto usa este critério para promover uma
hipótese ao consenso: a média de acertos precisa <b>superar o acaso na validação e no
teste posterior</b>. O critério é bem-intencionado — exige duas etapas cronológicas
independentes — e é <b>insuficiente</b>, por uma razão puramente aritmética.</p>

<p>Sob a hipótese nula, uma média tem cerca de 50% de chance de ficar acima do acaso em
cada etapa. Duas etapas independentes: 0,5 × 0,5 = <b>0,25</b>. Uma em quatro hipóteses
inúteis passa.</p>

<table>
<tr><th>Modalidade</th><th class="n">candidatas</th><th class="n">P(≥1 aceita por puro acaso)</th><th class="n">aceitas de fato</th></tr>
<tr><td>Mega-Sena</td><td class="n">3</td><td class="n">57,8%</td><td class="n">1</td></tr>
<tr><td>Quina</td><td class="n">3</td><td class="n">57,8%</td><td class="n">0</td></tr>
<tr><td>Lotofácil</td><td class="n">3</td><td class="n">57,8%</td><td class="n">0</td></tr>
<tr><td>Dia de Sorte</td><td class="n">2</td><td class="n">43,8%</td><td class="n">1</td></tr>
<tr><td><b>Total</b></td><td class="n"><b>11</b></td><td class="n"><b>2,75 esperadas por acaso</b></td><td class="n"><b>2</b></td></tr>
</table>

<div class="destaque">
<p>O v8 aceitou <b>2</b> hipóteses. O acaso puro, com o mesmo critério e as mesmas 11
candidatas, produziria <b>2,75</b>. O resultado do v8 é, portanto, <b>exatamente o que se
espera quando nenhuma das hipóteses tem valor</b> — e a hipótese aceita para a Mega-Sena
teve z de 1,47 na validação e 1,70 no teste, valores muito abaixo do
{num(D['protocolo']['controle_negativo']['max_z_p50'],2)} que uma busca deste tipo fabrica
na história falsa <i>mediana</i>.</p>
</div>

<p><b>Correção sugerida, concreta e barata.</b> Substituir “superou o acaso nas duas
etapas” por: <i>(a)</i> exigir um z mínimo calibrado pelo <b>controle negativo do próprio
sistema</b> — gerar N históricos falsos, rodar o mesmo ciclo de proposta e validação, e
usar o percentil 95 do maior z como limiar; <i>(b)</i> registrar quantas hipóteses foram
propostas, incluindo as descartadas antes do cálculo, porque o limiar depende disso; e
<i>(c)</i> exigir que o sinal do efeito seja o mesmo nas duas etapas, e não apenas positivo
nas duas — o que já elimina metade dos falsos positivos de graça. O módulo
<span class="mono">lab/protocolo.py</span> deste estudo faz exatamente isso e pode ser
reaproveitado sem alteração.</p>
"""


def capacidade_real(D):
    f = D["fechamento"]; pm = D["premios"]
    faixas = [15, 14, 13, 12, 11]
    lp = "".join(
        f'<tr><td class="c"><b>{k}</b></td>' +
        "".join(f'<td class="n">1 em {milhar(round(1/pm[str(k)][str(fa)]))}</td>'
                if pm[str(k)][str(fa)] > 0 else '<td class="n">—</td>' for fa in faixas) +
        f'</tr>' for k in range(15, 21))
    lf = "".join(
        f'<tr><td class="c">{k.split("_")[0]}</td><td class="c">{k.split("_")[1]}</td>'
        f'<td class="c">{k.split("_")[2]}</td><td class="n"><b>{v["n_apostas"]}</b></td>'
        f'<td class="n">{milhar(v["custo_de_cobrir_tudo"])}</td>'
        f'<td class="n">{milhar(v["casos"])}</td>'
        f'<td class="c">{"PROVADO" if v["provado"] else "não"}</td></tr>'
        for k, v in f.items())
    return f"""
<div class="quebra"></div>
<h2>10 · Onde há capacidade real: o fechamento</h2>

<p>Depois de oito capítulos derrubando teorias, é honesto — e necessário — mostrar onde
existe capacidade demonstrável neste terreno. Ela existe, é verificável <b>antes</b> do
sorteio, e não depende de prever coisa nenhuma.</p>

<p>A pergunta do fechamento não é "quais dezenas vão sair". É: <b>dado que eu já escolhi um
conjunto de dezenas, como distribuo as apostas para converter acerto parcial em prêmio com
certeza?</b> E "certeza" aqui é literal: ou toda combinação possível está coberta, ou a
garantia não existe.</p>

<h3>10.1 As garantias, provadas por verificação exaustiva</h3>

<p>Cada linha abaixo foi construída pelo módulo <span class="mono">NUCLEO/fechamento.py</span>
do projeto e depois <b>conferida caso a caso</b> — todos os casos, não uma amostra.</p>

<table>
<tr><th class="c">dezenas fixadas</th><th class="c">se saírem</th><th class="c">garante</th>
<th class="n">apostas</th><th class="n">cobrir tudo custaria</th><th class="n">casos conferidos</th><th class="c">status</th></tr>
{lf}
</table>

<div class="achado">
<span class="rot">a garantia mais bonita, demonstrável de cabeça</span>
<p><b>Vinte dezenas fixas, quatro apostas, 11 acertos garantidos se as 15 saírem entre as
20.</b> A prova cabe em três linhas: divida as 20 dezenas em quatro grupos de 5; cada
aposta é "as 20 menos um grupo". Se 15 das 20 forem sorteadas, 5 ficam de fora, e cada uma
dessas 5 cai em exatamente um grupo — logo <b>algum</b> grupo contém ao menos uma delas.
A aposta que exclui esse grupo perde no máximo 4 das sorteadas, e acerta ao menos 11.
Verificado nos 15.504 casos possíveis, sem exceção.</p>
</div>

<p>Repare no que isso é e no que não é. O fechamento <b>não aumenta</b> a chance das suas
dezenas saírem — essa continua sendo a mesma de qualquer outro conjunto do mesmo tamanho.
Ele reorganiza as apostas para que, quando saírem, o prêmio venha, e o ganho é de
<b>eficiência sobre o dinheiro apostado</b>, não de previsão. É a diferença entre 4 apostas
e 15.504, com a mesma garantia.</p>

<h3>10.2 As probabilidades exatas por tamanho de aposta</h3>

<table>
<tr><th class="c">dezenas na aposta</th><th class="n">15 acertos</th><th class="n">14</th>
<th class="n">13</th><th class="n">12</th><th class="n">11</th></tr>
{lp}
</table>

<p>Esta tabela é a referência contra a qual toda teoria deste relatório foi medida, e ela
não depende de nenhum dado histórico: é combinatória pura. É também o lugar onde se vê,
sem retórica, por que o achado do capítulo 7 não muda nada — <b>0,18 acerto por jogo</b> não
desloca perceptivelmente nenhuma das entradas acima.</p>
"""


def reproducao(D):
    pr = D["protocolo"]["protocolo"]
    return f"""
<div class="quebra"></div>
<h2>11 · Como reproduzir e como continuar</h2>

<h3>11.1 O que roda, e em que ordem</h3>

<table>
<tr><th>Arquivo</th><th>O que faz</th><th class="n">saída</th></tr>
<tr><td class="mono">lab/base.py</td><td>carrega e confere os dados; distribuições exatas; gerador de histórias falsas</td><td class="n">—</td></tr>
<tr><td class="mono">lab/teorias.py</td><td>as estatísticas estruturais e os nulos exatos</td><td class="n">—</td></tr>
<tr><td class="mono">lab/bateria.py</td><td>os {D['protocolo']['protocolo']['n_testes_na_bateria']} testes; a mesma função serve ao real e ao falso</td><td class="n">—</td></tr>
<tr><td class="mono">lab/protocolo.py</td><td>corte cronológico + controle negativo</td><td class="n">resultados/protocolo.json</td></tr>
<tr><td class="mono">lab/assertividade.py</td><td>enumera as 3.268.760 combinações; mede o catálogo de regras</td><td class="n">resultados/assertividade.json</td></tr>
<tr><td class="mono">lab/inovacoes.py</td><td>as sete teorias inéditas</td><td class="n">resultados/inovacoes.json</td></tr>
<tr><td class="mono">lab/persistencia.py</td><td>o achado do capítulo 7, com 4.000 histórias falsas</td><td class="n">resultados/persistencia.json</td></tr>
<tr><td class="mono">lab/outras_loterias.py</td><td>o teste confirmatório do capítulo 8, nas oito modalidades</td><td class="n">resultados/outras_loterias.json</td></tr>
<tr><td class="mono">lab/figuras.py</td><td>as dez figuras</td><td class="n">figuras/*.png</td></tr>
<tr><td class="mono">lab/relatorio.py</td><td>este documento</td><td class="n">RELATORIO.pdf</td></tr>
</table>

<p>Sementes fixas em toda parte: <span class="mono">{pr['semente']}</span> no protocolo e na
persistência. Rodando de novo, os números deste relatório saem iguais até a última casa.
O controle negativo do protocolo levou {num(pr['segundos_controle_negativo'],0)} segundos
para {milhar(pr['n_historias_falsas'])} histórias.</p>

<h3>11.2 O que eu faria a seguir, em ordem de valor</h3>

<ol>
<li><b>Atualizar a base e rodar o pré-registro da seção 7.5.</b> A base termina no concurso
3.246 (novembro de 2024). Há quase dois anos de concursos novos disponíveis, e eles são
dados que nenhuma hipótese deste relatório viu. É a coisa mais valiosa a fazer, e a mais
barata: um <span class="mono">git pull</span> na fonte e uma rodada de
<span class="mono">persistencia.py</span>.</li>
<li><b>Obter, junto à Caixa, o registro de qual globo e qual conjunto de bolas foi usado em
cada concurso.</b> Depois do capítulo 8, esta virou a coisa mais valiosa que falta. Com ela,
a hipótese do capítulo 7 deixa de ser "há um desvio" e passa a ser testável como "há um
desvio associado a este equipamento" — que é a diferença entre curiosidade estatística e
achado físico. Sem ela, nenhuma quantidade de concursos novos resolve o mecanismo.</li>
<li><b>Trocar o critério de aceitação do v8</b> pelo do capítulo 9.5. É a mudança de maior
impacto no software existente, e o código para isso já está escrito em
<span class="mono">lab/protocolo.py</span>.</li>
<li><b>Auditar retroativamente o repositório com o fator (1−p).</b> Qualquer χ² de
contingência sobre contagens de dezenas que exista no projeto está deflacionado. Na
Lotofácil o erro é de 2,5×.</li>
<li><b>Investir no fechamento.</b> É a única linha do projeto com capacidade real,
demonstrável e verificável antes do sorteio. O módulo atual usa um método guloso e não
promete otimalidade; a literatura de <i>covering designs</i> tem construções melhores para
vários dos casos da tabela 10.1.</li>
</ol>

<h3>11.3 Uma nota sobre o que este relatório não conseguiu fazer</h3>

<p>Três limitações que ficam registradas por honestidade:</p>
<ul>
<li>A base termina em novembro de 2024 porque a rotina automática da fonte parou ali, e a
API oficial da Caixa está bloqueada pela política de rede deste ambiente. Todos os números
valem para 1–3.246.</li>
<li>Não foi possível cruzar os resultados com <b>qual globo e qual conjunto de bolas</b>
foi usado em cada concurso. Essa informação existe nos registros da Caixa e transformaria a
hipótese do capítulo 7 de "há um desvio" em "há um desvio associado a este equipamento" —
que é a diferença entre uma curiosidade estatística e um achado físico.</li>
<li>O χ² de uniformidade tem p de família de
{num(D['protocolo']['veredicto']['dep.uniformidade_25']['p_familia'],3)}, acima de 0,05.
Chamá-lo de achado estabelecido seria exatamente o erro que o capítulo 2 existe para
evitar. Ele é sugestivo e replicante — nada além disso, até que a seção 7.5 seja
executada.</li>
</ul>
"""


def apendices(D):
    a = D["inovacoes"]["IV_atrito"]
    zs = np.array(a["z_todas"])
    iu = np.triu_indices(25, 1)
    ordem = np.argsort(-np.abs(zs))
    lp = _multi(['<th class="c">dupla</th>', '<th class="n">z</th>'],
        [f'<td class="c">{iu[0][i]+1:02d}–{iu[1][i]+1:02d}</td>'
         f'<td class="n {"pos" if zs[i]>2 else ("neg" if zs[i]<-2 else "")}">{num(zs[i],2,sinal=True)}</td>'
         for i in ordem], 4, larguras=(14.5, 10.5))
    d = D["assertividade"]["distribuicoes_exatas"]
    def tab_dist(chave, titulo):
        ex = np.array(d[chave]["exato"]); me = np.array(d[chave]["medido"])
        v = np.arange(len(ex)); m = ex > 1e-6
        cel = [f'<td class="c">{int(k)}</td><td class="n">{pct(ex[k],4)}</td>'
               f'<td class="n">{pct(me[k],4)}</td>'
               f'<td class="n">{num((me[k]-ex[k])*100,4,sinal=True)}</td>' for k in v[m]]
        cab = ['<th class="c">valor</th>', '<th class="n">exato</th>',
               '<th class="n">medido</th>', '<th class="n">dif. p.p.</th>']
        ncols = 3 if len(cel) > 40 else (2 if len(cel) > 12 else 1)
        larg = {1: (16, 28, 28, 28), 2: (8, 14, 14, 14), 3: (5.4, 9.4, 9.4, 9.1)}[ncols]
        return f'<h3>{titulo}</h3>' + _multi(cab, cel, ncols, larguras=larg)
    import outras_loterias as OL
    tabs = {}
    for chave, nome, N, k, prim, usar, por in OL.MODALIDADES:
        if chave not in ("megasena", "quina"):
            continue
        M = OL.carregar(chave, N, k, prim, usar, por)
        pp = k / N; T = len(M)
        z = OL.z_freq(M, pp); tot = M.sum(axis=0)
        cel = [f'<td class="c"><b>{i+1:02d}</b></td><td class="n">{milhar(tot[i])}</td>'
               f'<td class="n">{pct(tot[i]/T,2)}</td>'
               f'<td class="n {"pos" if z[i]>2 else ("neg" if z[i]<-2 else "")}">{num(z[i],2,sinal=True)}</td>'
               for i in np.argsort(-z)]
        cab = ['<th class="c">dez.</th>', '<th class="n">saídas</th>',
               '<th class="n">%</th>', '<th class="n">z</th>']
        tabs[chave] = (_multi(cab, cel, 3, larguras=(6, 9.4, 9, 9)), T, pp)
    tab_mega, tmega, pm_ = tabs["megasena"]
    tab_quina, tquina, pq_ = tabs["quina"]
    pmega, pquina = pct(pm_, 2), pct(pq_, 2)
    tmega, tquina = milhar(tmega), milhar(tquina)

    pv = D["protocolo"]["veredicto"]
    ordv = sorted(pv.items(), key=lambda kv: -abs(kv[1]["z"]))
    lt = _multi(['<th>teste</th>', '<th class="n">z</th>',
                 '<th class="n">p iso</th>', '<th class="n">p fam</th>'],
        [f'<td class="mono">{k}</td><td class="n">{num(v["z"],2,sinal=True)}</td>'
         f'<td class="n">{num(v["p_isolado"],3)}</td><td class="n">{num(v["p_familia"],3)}</td>'
         for k, v in ordv], 2, larguras=(26, 7.5, 8, 8.5))
    return f"""
<div class="quebra"></div>
<h2>Apêndice A — as 300 duplas de dezenas</h2>
<p>Coocorrência de cada par de dezenas em 3.246 concursos, padronizada. Sob uniformidade,
esperam-se cerca de 14 duplas além de |z| = 2; foram encontradas
{a['duplas_acima_de_2sigma']}. A seção 5.4 mostra que esse excesso é a frequência marginal
das dezenas 20 e 16 contaminando as 24 duplas de cada uma, e não um efeito de par.</p>
{lp}

<div class="quebra"></div>
<h2>Apêndice B — distribuições exatas completas</h2>
<p>Obtidas percorrendo as 3.268.760 combinações. A coluna “exato” não tem barra de erro:
é contagem, não estimativa.</p>
{tab_dist('pares','B.1 · Quantidade de dezenas pares')}
{tab_dist('primos','B.2 · Quantidade de primos')}
{tab_dist('moldura','B.3 · Dezenas na moldura do volante')}
{tab_dist('consecutivos','B.4 · Pares de dezenas vizinhas')}
{tab_dist('fibonacci','B.5 · Dezenas de Fibonacci')}
{tab_dist('altas','B.6 · Dezenas maiores que 13')}
{tab_dist('seq_max','B.7 · Maior sequência corrida')}
<div class="quebra"></div>
{tab_dist('soma','B.8 · Soma das 15 dezenas (distribuição completa)')}

<div class="quebra"></div>
<h2>Apêndice C — Mega-Sena e Quina, dezena a dezena</h2>
<p>As duas modalidades que confirmaram a direção do achado no capítulo 8, com a frequência
de cada dezena e o desvio padronizado. A linha de base é {pmega} para a Mega-Sena
(6 de 60, em {tmega} concursos) e {pquina} para a Quina (5 de 80, em {tquina}).
Sob uniformidade perfeita, os z se distribuiriam como uma normal padrão.</p>
<h3>C.1 · Mega-Sena — 60 dezenas</h3>{tab_mega}
<h3>C.2 · Quina — 80 dezenas</h3>{tab_quina}

<div class="quebra"></div>
<h2>Apêndice D — o registro completo dos {len(pv)} testes</h2>
<p>Cada teste da bateria, com seu z no dado real, o p-valor isolado e o p-valor de família
obtido das {milhar(D['protocolo']['protocolo']['n_historias_falsas'])} histórias de acaso
puro. Ordenado por |z| decrescente. Esta tabela é o registro completo da busca — inclusive
dos testes que não deram em nada, que são a maioria e são o que dá validade aos poucos que
deram.</p>
{lt}
"""
