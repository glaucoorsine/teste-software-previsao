# -*- coding: utf-8 -*-
"""Capa, sumário executivo, o material e o método."""
from relatorio_base import fig, milhar, num, pct


def capa(D):
    return """
<div class="capa">
  <div class="topo">
    <div class="selo">Estudo interno · Projeto Teste-Software-Previsão · Não é sistema de aposta</div>
    <h1>A Lotofácil<br>sob controle negativo</h1>
    <div class="sub">Vinte e um anos de sorteios, 689 testes, 1.000 histórias falsas
      e o único achado que sobrou.<br><br>
      Enumeração completa das 3.268.760 combinações · Sete teorias inéditas ·
      Auditoria de método</div>
  </div>
  <div class="rodape">
    <b>Base:</b> 3.246 concursos (1 a 3.246), setembro de 2003 a novembro de 2024 —
    íntegros, sem falhas, conferidos contra fonte independente.<br>
    <b>Autoria:</b> análise conduzida por Claude (Anthropic) a pedido de
    Glauco Orsine Travaglia, como acréscimo à linha científica do projeto.<br>
    <b>Reprodução:</b> todo o código, as sementes e os dados intermediários estão em
    <span class="mono">LOTERIA/ESTUDO/</span> no repositório.<br>
    <b>Data:</b> 3 de setembro de 2026.
  </div>
</div>"""


def aviso():
    return """
<div class="aviso">
<b>O que este documento é, e o que ele não é.</b><br><br>
Este é um relatório de <b>auditoria estatística</b>. Ele não indica dezenas, não propõe
combinações, não descreve nenhum método de escolha para uso real e não sugere apostar.
A conclusão central, medida e demonstrada nas páginas seguintes, é que <b>a Lotofácil se
comporta como um sorteio uniforme e sem memória</b>, e que nenhuma das teorias examinadas
— nem as populares, nem as sete que foram inventadas para este estudo — produz capacidade
de previsão.<br><br>
O único desvio que sobreviveu ao exame é pequeno demais para mudar qualquer aposta:
vale <b>0,18 acerto por jogo</b>, quando a menor faixa de prêmio exige 11 acertos e a média
do acaso já é 9. Ele é relatado por ser <b>cientificamente interessante</b>, e o documento
diz explicitamente, na seção 7.5, qual resultado futuro o derrubaria.
</div>"""


def sumario():
    L = [
      ("0", "Sumário executivo: o que deu, em números", True),
      ("1", "O material", True),
      ("1.1", "Procedência, integridade e o concurso 2425", False),
      ("1.2", "Conferência cruzada contra fonte independente", False),
      ("2", "O método", True),
      ("2.1", "Por que o corte é cronológico", False),
      ("2.2", "O controle negativo — a ideia central do estudo", False),
      ("2.3", "Os dois p-valores: isolado e de família", False),
      ("2.4", "A régua exata da Lotofácil", False),
      ("3", "O acaso exato: enumerando as 3.268.760 combinações", True),
      ("3.1", "Dois teoremas que caem só de contar", False),
      ("3.2", "As distribuições exatas, medidas contra o real", False),
      ("4", "Assertividade: onde ela existe e por que não é vantagem", True),
      ("4.1", "O teorema do ganho igual a um", False),
      ("4.2", "Dezenove regras, medidas uma a uma", False),
      ("4.3", "Cinturões: por que multiplicar as probabilidades erra", False),
      ("4.4", "O que “boa taxa de assertividade” significa de verdade", False),
      ("5", "As sete teorias inéditas", True),
      ("5.1", "I — Teoria do Complemento (as dez ausentes)", False),
      ("5.2", "II — Teoria do Eco Posicional (a ordem do globo)", False),
      ("5.3", "III — Teoria da Inércia de Repetição", False),
      ("5.4", "IV — Teoria do Atrito de Pares (a rede das 300 duplas)", False),
      ("5.5", "V — Teoria do Núcleo Persistente", False),
      ("5.6", "VI — Teoria da Maré (deriva em 21 anos)", False),
      ("5.7", "VII — Teoria do Espelho (a simetria n ↔ 26−n)", False),
      ("6", "A bateria completa contra o acaso puro", True),
      ("6.1", "O resultado que reorganiza tudo: |z| = 4,83 é normal", False),
      ("6.2", "Os três sobreviventes, e a autópsia deles", False),
      ("6.3", "As dezesseis teorias de ranking contra a linha de 9,0", False),
      ("7", "O único achado: as 25 dezenas não são iguais", True),
      ("7.1", "χ² = 56,38 e a replicação fora da amostra", False),
      ("7.2", "O tamanho do efeito: 0,18 acerto", False),
      ("7.3", "A hipótese da tinta", False),
      ("7.4", "O veredicto honesto", False),
      ("7.5", "Pré-registro: o que derruba isto nos próximos concursos", False),

      ("7.6", "As 25 dezenas, número a número", False),
      ("8", "As outras oito loterias: o teste que decide", True),
      ("8.1", "As oito modalidades, lado a lado", False),
      ("8.2", "O que apareceu: três acusam, cinco não têm poder", False),
      ("8.3", "O teste confirmatório, sem a Lotofácil", False),
      ("8.4", "Por que as cinco que deram nada não derrubam o achado", False),
      ("8.5", "O que isto muda no veredicto do capítulo 7", False),
      ("9", "Cinco erros de método encontrados — quatro deles meus", True),
      ("9.1", "O χ² de contingência deflacionado pelo fator (1−p)", False),
      ("9.2", "O nulo com p = 0,6 quando a dezena tem p ≠ 0,6", False),
      ("9.3", "Teorias diferentes que são a mesma aposta", False),
      ("9.4", "A aproximação normal onde o esperado é 0,001", False),
      ("9.5", "O critério de aceitação do v8 aceita 58% do ruído", False),
      ("10", "Onde há capacidade real: o fechamento", True),
      ("11", "Como reproduzir e como continuar", True),
      ("A", "Apêndice A — as 300 duplas de dezenas", True),
      ("B", "Apêndice B — distribuições exatas completas", True),
      ("C", "Apêndice C — Mega-Sena e Quina, dezena a dezena", True),
      ("D", "Apêndice D — o registro completo dos 689 testes", True),
    ]
    linhas = "".join(
        f'<div class="lin {"" if p else "p2"}"><span>{"<b>" if p else ""}{n} · {t}'
        f'{"</b>" if p else ""}</span></div>' for n, t, p in L)
    return f'<h1>Sumário</h1><div class="sumario">{linhas}</div>'


def sumario_executivo(D):
    pr, pe = D["protocolo"], D["persistencia"]
    cn = pr["controle_negativo"]
    v = pe["veredicto"]
    return f"""
<div class="quebra"></div>
<h2>0 · Sumário executivo: o que deu, em números</h2>

<p>Este estudo passou <b>689 testes estatísticos</b> sobre os 3.246 concursos da Lotofácil e,
em seguida, passou <b>os mesmos 689 testes</b> sobre 1.000 históricos que foram gerados aqui
por acaso uniforme puro — mundos onde, por construção, não existe padrão nenhum. A
comparação entre os dois é o que dá sentido a cada número deste relatório.</p>

<div class="destaque">
<p><b>O número mais importante do documento.</b> Nas 1.000 histórias comprovadamente
aleatórias, a bateria de 689 testes produziu um maior |z| de <b>{num(cn['max_z_p50'])}</b>
na mediana, <b>{num(cn['max_z_p95'])}</b> no percentil 95, e chegou a
<b>{num(cn['max_z_maximo'])}</b> no pior caso. Ou seja: procurar padrão em 689 lugares
diferentes <b>fabrica sozinho</b> um resultado de quase cinco desvios-padrão, uma em cada
vinte vezes, sem que exista padrão algum. Qualquer descoberta de loteria com z abaixo
de {num(cn['max_z_p95'],1)} que tenha vindo de uma busca deste tamanho é, muito
provavelmente, exatamente isto.</p>
</div>

<h3>O que morreu</h3>
<ul>
<li><b>Todas as teorias populares.</b> Quente, frio, atrasada, soma, paridade, moldura,
espelho, repetir o anterior — dezesseis estratégias medidas na janela de teste. Todas
entre 8,87 e 9,12 acertos por jogo, contra a linha exata de 9,00. Nenhuma fora do
intervalo de confiança de forma que o controle negativo não reproduza.</li>
<li><b>As sete teorias inéditas</b> criadas para este estudo — complemento, eco posicional,
inércia, atrito, núcleo, maré, espelho. Todas nulas. Duas delas <i>pareceram</i> positivas
até que o nulo correto fosse aplicado, e essa correção virou o capítulo 9.</li>
<li><b>A ideia de que uma regra estrutural com alta taxa de acerto seja vantagem.</b>
Demonstrado por enumeração das 3.268.760 combinações: para qualquer regra estrutural,
a taxa de acerto é <b>exatamente igual</b> à fração do espaço que a regra ocupa. Dezenove
regras medidas, nenhuma fora da reta (Figura 5).</li>
</ul>

<h3>O que sobrou</h3>
<p>Uma única coisa, e ela é pequena: <b>as 25 dezenas não saem com a mesma frequência</b>.
χ² = {num(v['chi2_total']['observado'])} com 24 graus de liberdade, contra
{num(v['chi2_total']['nulo_media'])} esperados — p isolado de
{num(v['chi2_total']['p_unilateral_maior'],4)}. E, o que importa muito mais do que o
p-valor: <b>o desvio se repete em janelas cronológicas que não se tocam</b>. A correlação
média entre os desvios de três períodos disjuntos é
{num(v['r_media']['observado'],3)} (p = {num(v['r_media']['p_unilateral_maior'],4)}),
quando o acaso dá {num(v['r_media']['nulo_media'],3)}.</p>

<p><b>O tamanho disso.</b> Apostar as quinze dezenas historicamente mais frequentes rende
{num(v['acertos_quentes_fora_da_amostra']['observado'],3)} acertos por jogo fora da amostra; as quinze
menos frequentes rendem {num(v['acertos_frios_fora_da_amostra']['observado'],3)}. A separação inteira
entre o melhor e o pior conjunto possível é de
<b>{num(v['separacao_quente_menos_frio']['observado'],3)} acerto</b>. A faixa de prêmio mais
baixa da Lotofácil começa em <b>11</b> acertos. O efeito é real o bastante para ser medido
e pequeno o bastante para não mudar absolutamente nada em uma aposta — e é precisamente
esse par que o torna útil como objeto de estudo.</p>

<figure>
  <img src="{fig('01_controle_negativo.png')}">
  <figcaption><b>Figura 1.</b> Duzentas das 1.000 histórias geradas por acaso uniforme.
  Cada barra conta em quantas delas a bateria de 689 testes produziu aquele maior |z|.
  A linha vermelha é o maior |z| obtido no dado real da Lotofácil — dentro, e não fora,
  do que o acaso puro fabrica.</figcaption>
</figure>

<h3>E uma coisa que eu não esperava</h3>
<p>Rodando a mesma medida nas <b>outras oito loterias da Caixa</b> — que é o teste que
separa "física" de "coincidência" —, Quina e Mega-Sena apontam na mesma direção da
Lotofácil. Excluindo inteiramente a Lotofácil, onde o achado nasceu, as sete restantes
combinadas dão p = 0,047 para a persistência e p = 0,030 para a uniformidade. É confirmação
independente: fraca, logo abaixo de 0,05, e feita sobre uma previsão registrada antes de
olhar. As cinco modalidades que não acusaram nada não contradizem: elas são de 2,6 a 13
vezes menos sensíveis que a Lotofácil, e não teriam como ver um efeito deste tamanho.
O capítulo 8 é inteiro sobre isso.</p>

<h3>O que este estudo acrescenta ao projeto, em uma frase</h3>
<p>Não é uma teoria que ganha: é uma <b>régua</b>. Toda hipótese futura sobre qualquer
loteria pode agora ser medida contra a distribuição do que a busca inventa sozinha, e
não contra o zero — que é a régua errada e a que produz quase toda descoberta falsa
desta área.</p>
"""
