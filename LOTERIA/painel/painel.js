/* ═══════════════════════════════════════════════════════════════════════
   LOTERIA — o comportamento da tela.

   DUAS REGRAS QUE EU SEGUI AQUI
   ─────────────────────────────
   1. Nada de tela parada. Toda tarefa demorada mostra o que está fazendo,
      passo a passo. Uma tela parada por três minutos é indistinguível de uma
      tela quebrada, e quem fechasse a janela teria feito bem.

   2. Nada de texto de máquina. O motor devolve linhas como "[Formular] ▸ …"
      porque nasceu para terminal; aqui elas viram frase de gente. Se o número
      é ruim, a frase diz que é ruim -- o que não pode é sair críptico.
   ═══════════════════════════════════════════════════════════════════════ */
"use strict";

const estado = { jogo: null, detalhe: null, secao: "comecar", escolhidas: new Set(),
                 ultimoFechamento: null };

const $  = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function el(tag, props = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined) e.setAttribute(k, v);
  }
  for (const f of filhos.flat()) {
    if (f === null || f === undefined || f === false) continue;
    e.append(f.nodeType ? f : document.createTextNode(String(f)));
  }
  return e;
}

const num = (n, casas = 0) =>
  Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas,
                                      maximumFractionDigits: casas });

async function pedir(rota, corpo) {
  const op = corpo
    ? { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(corpo) }
    : {};
  const r = await fetch(rota, op);
  if (!r.ok) throw new Error(`o programa respondeu ${r.status}`);
  return r.json();
}

/* Acompanha uma tarefa demorada, contando o que ela vai fazendo. */
async function acompanhar(idTarefa, ondeMostrar, titulo) {
  const lista = el("ol");
  const caixa = el("div", { class: "progresso" },
                   el("p", { class: "girando" }, titulo), lista);
  ondeMostrar.replaceChildren(caixa);
  let vistas = 0;
  for (;;) {
    await new Promise((r) => setTimeout(r, 400));
    const t = await pedir(`/api/tarefa?id=${idTarefa}`);
    (t.linhas || []).slice(vistas).forEach((l) => lista.append(el("li", {}, l)));
    vistas = (t.linhas || []).length;
    if (t.estado === "pronto") { ondeMostrar.replaceChildren(); return t.resultado; }
    if (t.estado === "erro") {
      ondeMostrar.replaceChildren(
        el("div", { class: "aviso aviso-ruim" },
           el("p", {}, "Deu problema aqui: " + t.erro),
           el("p", {}, "Isso é defeito meu. Me mostre esta mensagem.")));
      return null;
    }
  }
}

function selo(tipo, texto) {
  const simbolo = { bom: "✓", ruim: "✗", espera: "•", neutro: "•" }[tipo];
  return el("span", { class: `selo selo-${tipo}` }, simbolo + " " + texto);
}

/* ── as abas das loterias ────────────────────────────────────────────── */
async function montarAbas() {
  const d = await pedir("/api/jogos");
  const abas = $("#abas");
  abas.replaceChildren();
  d.jogos.forEach((j, i) => {
    const b = el("button", {
      class: "aba", role: "tab", id: `aba-${j.chave}`,
      "aria-selected": i === 0 ? "true" : "false",
      tabindex: i === 0 ? "0" : "-1",
      onclick: () => trocarJogo(j.chave),
      onkeydown: (ev) => navegarAbas(ev, d.jogos, i),
    }, j.nome);
    abas.append(b);
  });
  $("#fonte-url").value = d.fonte.url || "";
  $("#fonte-url-n").value = d.fonte.url_concurso || "";
  await trocarJogo(d.jogos[0].chave);
}

/* setas navegam entre abas -- é o que um leitor de tela espera delas */
function navegarAbas(ev, jogos, i) {
  const mapa = { ArrowRight: 1, ArrowLeft: -1, Home: "inicio", End: "fim" };
  if (!(ev.key in mapa)) return;
  ev.preventDefault();
  let alvo;
  if (mapa[ev.key] === "inicio") alvo = 0;
  else if (mapa[ev.key] === "fim") alvo = jogos.length - 1;
  else alvo = (i + mapa[ev.key] + jogos.length) % jogos.length;
  const b = document.getElementById(`aba-${jogos[alvo].chave}`);
  b.focus();
  trocarJogo(jogos[alvo].chave);
}

async function trocarJogo(chave) {
  estado.jogo = chave;
  estado.escolhidas.clear();
  estado.ultimoFechamento = null;
  $$(".aba").forEach((b) => {
    const meu = b.id === `aba-${chave}`;
    b.setAttribute("aria-selected", meu ? "true" : "false");
    b.tabIndex = meu ? 0 : -1;
  });
  estado.detalhe = await pedir(`/api/jogo?jogo=${chave}`);
  desenharTudo();
}

function irPara(secao) {
  estado.secao = secao;
  $$(".secao").forEach((s) =>
    s.classList.toggle("escondido", s.dataset.secao !== secao));
  $$(".menu-item").forEach((b) =>
    b.setAttribute("aria-current", b.dataset.secao === secao ? "page" : "false"));
  $("#conteudo").focus();
}

/* ── 1. começar ──────────────────────────────────────────────────────── */
function desenharComecar() {
  const j = estado.detalhe;
  $("#t-comecar").textContent = j.nome;

  const estadoRegras = j.conferido
    ? el("div", { class: "aviso aviso-bom" },
         el("p", {}, "As regras desta loteria já foram conferidas contra os "
                   + "resultados reais que estão no seu computador."))
    : el("div", { class: "aviso" },
         el("p", { html: "<strong>As regras desta loteria ainda não foram "
                        + "conferidas.</strong> Eu as escrevi de memória e não "
                        + "consegui checar na fonte de onde escrevi o programa." }),
         el("p", {}, "Vá em “Resultados” e busque os concursos: o programa "
                   + "confere sozinho e avisa se eu errei alguma coisa."));

  $("#comecar-estado").replaceChildren(estadoRegras);

  const p = j.custo[0];
  $("#comecar-resumo").replaceChildren(
    el("p", { html:
      `São <strong>${j.universo} dezenas</strong> e saem `
      + `<strong>${j.sorteadas}</strong>. A aposta vai de ${j.minimo} a `
      + `${j.maximo} dezenas. ${j.nota ? j.nota.charAt(0).toUpperCase() + j.nota.slice(1) + "." : ""}` }),
    el("p", { html:
      `Com a aposta mínima, a chance de levar o prêmio maior é de `
      + `<strong>1 em ${num(p.uma_em)}</strong>. Em média, uma aposta dessas `
      + `acerta <strong>${num(j.acertos_medios, 2)}</strong> dezenas — é contra `
      + `esse número que toda teoria tem de ser comparada, nunca contra zero.` }));

  const t = el("table");
  t.append(el("caption", {}, "Cada linha é um tamanho de aposta"));
  t.append(el("thead", {}, el("tr", {},
    el("th", { scope: "col" }, "Aposta"),
    el("th", { scope: "col" }, "Custa (em apostas mínimas)"),
    el("th", { scope: "col" }, "Chance do prêmio maior"),
    el("th", { scope: "col" }, "Chance por real"),
    el("th", { scope: "col" }, "Chance de ganhar algo"))));
  const corpo = el("tbody");
  j.custo.forEach((l) => corpo.append(el("tr", {},
    el("th", { scope: "row" }, `${l.k} dezenas`),
    el("td", { class: "num" }, num(l.custo)),
    el("td", { class: "num" }, "1 em " + num(l.uma_em)),
    el("td", { class: "num" }, l.razao_igual ? "a mesma" : "DIFERENTE"),
    el("td", { class: "num" }, num(l.algum_premio * 100, 3) + "%"))));
  t.append(corpo);
  // tabindex="0" + rotulo: sem isso, quem navega so de teclado nao consegue
  // rolar esta tabela de lado. Foi a unica violacao que o axe apontou.
  const caixaTabela = $("#tabela-custo");
  caixaTabela.setAttribute("tabindex", "0");
  caixaTabela.setAttribute("role", "region");
  caixaTabela.setAttribute("aria-label", "Tabela de custo por tamanho de aposta");
  caixaTabela.replaceChildren(t);
  $("#nota-custo").textContent =
    "A chance de ganhar ALGO cai conforme a aposta cresce. Não é contradição: "
    + "a aposta grande ganha várias vezes de uma vez quando ganha, e concentra "
    + "o dinheiro em torno de um punhado fixo de dezenas.";
}

/* ── 2. resultados ───────────────────────────────────────────────────── */
async function desenharResultados() {
  const h = await pedir(`/api/historico?jogo=${estado.jogo}`);
  const alvo = $("#res-estado");
  if (!h.tem) {
    alvo.replaceChildren(el("div", { class: "aviso" },
      el("p", { html: "<strong>Ainda não há resultados no seu computador para "
                    + "esta loteria.</strong>" }),
      el("p", {}, "Sem eles, o programa não mede nada e as inteligências que "
                + "dependem de histórico ficam caladas. Clique no botão abaixo.")));
    $("#btn-medir").disabled = true;
    return;
  }
  $("#btn-medir").disabled = false;
  const linhas = [
    el("p", { html: `<strong>${num(h.n)} concursos</strong> guardados no seu `
                  + `computador.` }),
  ];
  if (h.primeiro && h.ultimo) {
    linhas.push(el("p", { html:
      `Do concurso ${h.primeiro.concurso} ao ${h.ultimo.concurso}. `
      + `O último saiu em ${h.ultimo.data || "data não informada"}: `
      + (h.ultimo.dezenas || []).map((d) => `<strong>${d}</strong>`).join(" · ") }));
  }
  linhas.push(el("p", {}, h.tem_ganhadores
    ? "Vieram também os ganhadores por faixa — dá para medir a partilha do prêmio."
    : "Não vieram os ganhadores por faixa, então a partilha do prêmio fica sem medida."));
  alvo.replaceChildren(
    el("div", { class: h.conferido ? "aviso aviso-bom" : "aviso aviso-ruim" },
       ...linhas,
       el("p", {}, h.conferido
         ? "As regras que eu escrevi batem com estes resultados."
         : "ATENÇÃO: as regras que eu escrevi NÃO batem com estes resultados: "
           + (h.problemas || []).join("; "))));
}

async function puxar() {
  $("#btn-puxar").disabled = true;
  $("#res-saida").replaceChildren();
  try {
    const { tarefa } = await pedir("/api/puxar", { jogo: estado.jogo });
    const r = await acompanhar(tarefa, $("#res-progresso"),
                               "Buscando os concursos na fonte…");
    if (!r) return;
    if (!r.ok) {
      $("#res-saida").replaceChildren(el("div", { class: "aviso aviso-ruim" },
        el("p", { html: "<strong>Não consegui buscar.</strong>" }),
        el("p", {}, r.erro || ""),
        r.novos ? el("p", {}, `Mas ${r.novos} concursos novos ficaram salvos. `
                            + `Clicar de novo continua daí.`) : null));
    } else {
      $("#res-saida").replaceChildren(el("div", { class: "aviso aviso-bom" },
        el("p", { html: `<strong>Pronto: ${num(r.total)} concursos no seu `
                      + `computador</strong> (${num(r.novos)} novos agora).` })));
    }
    await desenharResultados();
  } finally { $("#btn-puxar").disabled = false; }
}

async function medir() {
  $("#btn-medir").disabled = true;
  $("#res-saida").replaceChildren();
  try {
    const { tarefa } = await pedir("/api/medir", { jogo: estado.jogo });
    const r = await acompanhar(tarefa, $("#res-progresso"),
                               "Medindo as crenças nos seus resultados…");
    if (!r) return;
    if (r.erro) {
      $("#res-saida").replaceChildren(
        el("div", { class: "aviso aviso-ruim" }, el("p", {}, r.erro)));
      return;
    }
    const caixa = el("div", {});
    caixa.append(el("h3", {}, `O que os seus ${num(r.n)} concursos disseram`));
    Object.values(r.medicao.resultados).forEach((v) => {
      const item = (r.itens || []).find((i) => i.id === v.id) || {};
      const tipo = { confirmado: "bom", derrubado: "ruim", sem_base: "espera" }[v.veredito];
      const rotulo = { confirmado: "confirmado", derrubado: "derrubado",
                       sem_base: "sem base para dizer" }[v.veredito];
      caixa.append(el("div", { class: "ia" },
        el("div", { class: "ia-topo" },
           el("h3", { class: "ia-nome" }, `${v.id} — ${item.titulo || ""}`),
           selo(tipo, rotulo)),
        ...(v.porque || []).map((p) => el("p", { class: "ia-motivo" }, p))));
    });
    $("#res-saida").replaceChildren(caixa);
    if (estado.secao === "base") desenharBase();
  } finally { $("#btn-medir").disabled = false; }
}

/* ── 3. formular ─────────────────────────────────────────────────────── */
function desenharFormular() {
  const j = estado.detalhe;
  $("#form-quantas").min = j.minimo;
  $("#form-quantas").max = j.maximo;
  if (!$("#form-quantas").value) $("#form-quantas").value = j.minimo;
  $("#form-quantas-dica").textContent = `de ${j.minimo} a ${j.maximo}`;
}

async function formular() {
  $("#btn-formular").disabled = true;
  try {
    const c = await pedir("/api/formular", {
      jogo: estado.jogo,
      quantas: Number($("#form-quantas").value) || 0,
      semente: Number($("#form-semente").value) || 0,
    });
    if (!c.ok) {
      $("#form-saida").replaceChildren(
        el("div", { class: "aviso aviso-ruim" }, el("p", {}, c.nota)));
      return;
    }
    const caixa = el("div", {});
    caixa.append(el("p", { html:
      `Semente <strong>${c.semente}</strong> — anote se quiser repetir estes `
      + `mesmos jogos depois.` }));
    if (!c.tem_historico) {
      caixa.append(el("div", { class: "aviso" }, el("p", {},
        "Sem resultados no computador, duas das quatro ficam caladas. "
        + "Busque os resultados na seção 2 para ouvi-las.")));
    }
    c.jogos.forEach((g) => {
      if (g.calada) {
        caixa.append(el("div", { class: "ia ia-calada" },
          el("div", { class: "ia-topo" },
             el("h3", { class: "ia-nome" }, g.rotulo),
             selo("neutro", "calada")),
          el("p", { class: "ia-motivo" }, g.motivo)));
        return;
      }
      const bolas = el("div", { class: "ia-bolas" },
        ...g.dezenas.map((d) => el("span", { class: "bola" },
                                   String(d).padStart(2, "0"))));
      caixa.append(el("div", { class: "ia" },
        el("div", { class: "ia-topo" }, el("h3", { class: "ia-nome" }, g.rotulo)),
        bolas,
        el("p", { class: "ia-motivo" }, g.motivo),
        ...(g.avisos || []).map((a) =>
          el("div", { class: "aviso" }, el("p", {}, a))),
        el("ul", { class: "ia-citacoes" },
           ...(g.citacoes || []).map((t) => el("li", {}, t))),
        el("div", { class: "linha-botoes", style: "margin-top:.9rem" },
           el("button", { class: "botao botao-2",
             onclick: () => usarNoFechamento(g.dezenas) },
             "Usar estas dezenas no fechamento"))));
    });
    $("#form-saida").replaceChildren(caixa);
  } finally { $("#btn-formular").disabled = false; }
}

function usarNoFechamento(dezenas) {
  estado.escolhidas = new Set(dezenas);
  irPara("fechamento");
  desenharGrade();
}

/* ── 4. fechamento ───────────────────────────────────────────────────── */
function desenharGrade() {
  const j = estado.detalhe;
  const g = $("#grade");
  g.replaceChildren(...j.dezenas.map((d) =>
    el("button", { class: "dezena", type: "button",
      "aria-pressed": estado.escolhidas.has(d) ? "true" : "false",
      onclick: (ev) => {
        if (estado.escolhidas.has(d)) estado.escolhidas.delete(d);
        else estado.escolhidas.add(d);
        ev.currentTarget.setAttribute("aria-pressed",
          estado.escolhidas.has(d) ? "true" : "false");
        atualizarConta();
      } }, String(d).padStart(2, "0"))));
  const k = $("#fech-k");
  k.min = j.minimo; k.max = j.maximo;
  if (!k.value) k.value = j.minimo;
  if (!$("#fech-se").value) $("#fech-se").value = Math.max(1, j.sorteadas - 1);
  if (!$("#fech-gar").value) $("#fech-gar").value = j.faixas[j.faixas.length - 1];
  atualizarConta();
}

function atualizarConta() {
  const n = estado.escolhidas.size;
  $("#grade-conta").innerHTML = `<strong>${n}</strong> dezena${n === 1 ? "" : "s"} escolhida${n === 1 ? "" : "s"}`;
  const se = Number($("#fech-se").value) || 0;
  const gar = Number($("#fech-gar").value) || 0;
  const k = Number($("#fech-k").value) || 0;
  $("#fech-frase").innerHTML =
    `<p>Você está pedindo: <strong>“das minhas ${n} dezenas, se ${se} saírem, `
    + `quero que alguma aposta de ${k} tenha ${gar} acertos — garantido”</strong>.</p>`;
  $("#btn-fechar").disabled = n < k || k < 1;
}

async function fechar() {
  const dez = Array.from(estado.escolhidas).sort((a, b) => a - b);
  $("#btn-fechar").disabled = true;
  $("#fech-saida").replaceChildren();
  try {
    const { tarefa } = await pedir("/api/fechamento", {
      jogo: estado.jogo, dezenas: dez,
      k: Number($("#fech-k").value), se: Number($("#fech-se").value),
      garantir: Number($("#fech-gar").value),
    });
    const r = await acompanhar(tarefa, $("#fech-progresso"),
                               "Montando as apostas e provando a garantia…");
    if (!r) return;
    const f = r.fechamento, prova = r.prova;
    if (!f.ok) {
      $("#fech-saida").replaceChildren(el("div", { class: "aviso aviso-ruim" },
        el("p", { html: "<strong>Não deu para fechar.</strong>" }),
        el("p", {}, f.nota)));
      return;
    }
    if (!prova || !prova.provado) {
      $("#fech-saida").replaceChildren(el("div", { class: "aviso aviso-ruim" },
        el("p", { html: "<strong>A prova reprovou — não use isto como garantia.</strong>" }),
        el("p", {}, (prova && prova.nota) || "")));
      return;
    }
    estado.ultimoFechamento = { apostas: f.apostas, dezenas: dez,
                                se: f.acertos_previstos, garantir: f.garantir };
    const caixa = el("div", {});
    caixa.append(el("div", { class: "aviso aviso-bom" },
      el("p", { html: `<strong>${f.n_apostas} apostas, e a garantia está `
                    + `provada.</strong>` }),
      el("p", {}, `A prova percorreu todos os ${num(prova.casos_testados)} `
                + `casos possíveis, um por um. Em nenhum deles a garantia falha.`),
      el("p", {}, `Apostar todas as combinações destas ${dez.length} dezenas `
                + `custaria ${num(f.custo_de_cobrir_tudo)} apostas. `
                + `Estas são ${f.n_apostas} — uma economia de `
                + `${num(f.economia)} apostas, com a mesma garantia.`)));
    caixa.append(el("div", { class: "aviso" },
      el("p", {}, "Lembre do que a garantia é e do que ela não é: ela vale SE "
                + `${f.acertos_previstos} das suas dezenas saírem. Que elas `
                + "saiam é sorteio, e sobre isso este programa não promete nada.")));
    const lista = el("div", { class: "apostas" });
    f.apostas.forEach((a, i) => lista.append(el("div", { class: "aposta" },
      el("span", { class: "aposta-num" }, `${i + 1}.`),
      ...a.map((d) => el("span", { class: "bola" }, String(d).padStart(2, "0"))))));
    caixa.append(el("h3", {}, "As apostas"), lista);
    caixa.append(el("div", { class: "linha-botoes" },
      el("button", { class: "botao botao-2", onclick: salvarApostas },
         "Salvar no computador"),
      el("button", { class: "botao botao-2", onclick: () => {
          $("#conf-apostas").value =
            f.apostas.map((a) => a.join(" ")).join("\n");
          irPara("conferir");
        } }, "Levar para conferir")));
    caixa.append(el("p", { id: "fech-salvo", "aria-live": "polite" }));
    $("#fech-saida").replaceChildren(caixa);
  } finally { atualizarConta(); }
}

async function salvarApostas() {
  const f = estado.ultimoFechamento;
  if (!f) return;
  const r = await pedir("/api/salvar_apostas", {
    jogo: estado.jogo, apostas: f.apostas,
    meta: { se: f.se, garantir: f.garantir, dezenas: f.dezenas },
  });
  $("#fech-salvo").textContent = "Salvo em " + r.arquivo
    + " — a promessa da garantia foi salva junto, para poder ser auditada depois.";
}

/* ── 5. conferir ─────────────────────────────────────────────────────── */
function lerNumeros(txt) {
  return (txt || "").split(/[^\d]+/).filter(Boolean).map(Number);
}

async function conferir() {
  const j = estado.detalhe;
  const sorteio = lerNumeros($("#conf-sorteio").value);
  const apostas = ($("#conf-apostas").value || "").split("\n")
    .map(lerNumeros).filter((a) => a.length);
  if (!apostas.length) {
    $("#conf-saida").replaceChildren(el("div", { class: "aviso" },
      el("p", {}, "Escreva ao menos uma aposta.")));
    return;
  }
  const f = estado.ultimoFechamento;
  const meta = f && JSON.stringify(f.apostas.map((a) => a.slice().sort((x, y) => x - y)))
      === JSON.stringify(apostas.map((a) => a.slice().sort((x, y) => x - y)))
    ? { se: f.se, garantir: f.garantir, dezenas: f.dezenas } : null;

  const r = await pedir("/api/conferir",
                        { jogo: estado.jogo, apostas, sorteio, meta });
  const c = r.conferencia;
  if (!c.ok) {
    $("#conf-saida").replaceChildren(el("div", { class: "aviso aviso-ruim" },
      el("p", { html: "<strong>Não dá para conferir assim.</strong>" }),
      el("p", {}, c.nota)));
    return;
  }
  const alvo = new Set(c.sorteio);
  const caixa = el("div", {});
  caixa.append(el("h3", {}, "Sorteio"),
    el("div", { class: "ia-bolas" },
       ...c.sorteio.map((d) => el("span", { class: "bola bola-sorteada" },
                                  String(d).padStart(2, "0")))));
  const lista = el("div", { class: "apostas" });
  c.resultados.forEach((res, i) => lista.append(el("div", { class: "aposta" },
    el("span", { class: "aposta-num" }, `${i + 1}.`),
    ...res.aposta.map((d) => el("span",
      { class: "bola" + (alvo.has(d) ? " bola-acerto" : "") },
      String(d).padStart(2, "0"))),
    el("span", { style: "margin-left:auto;font-weight:700" },
       `${res.acertos} acerto${res.acertos === 1 ? "" : "s"}`),
    res.paga ? selo("bom", "paga") : selo("neutro", "não paga"))));
  caixa.append(el("h3", {}, "Suas apostas"), lista);

  const faixas = Object.entries(c.por_faixa || {});
  caixa.append(el("div", { class: faixas.length ? "aviso aviso-bom" : "aviso" },
    el("p", {}, faixas.length
      ? `${c.premiadas} aposta(s) premiada(s): `
        + faixas.map(([f2, q]) => `${q}× de ${f2} acertos`).join(", ")
      : `Nenhuma aposta premiada. A melhor fez ${c.melhor} acertos.`)));

  if (r.auditoria) {
    const a = r.auditoria;
    const classe = a.honrada === false ? "aviso aviso-ruim"
                 : a.honrada ? "aviso aviso-bom" : "aviso";
    caixa.append(el("div", { class: classe },
      el("p", { html: "<strong>Auditoria da garantia</strong>" }),
      el("p", {}, a.nota)));
  }
  $("#conf-saida").replaceChildren(caixa);
}

/* ── 6. a base ───────────────────────────────────────────────────────── */
async function desenharBase() {
  const d = await pedir(`/api/base?jogo=${estado.jogo}`);
  const caixa = el("div", {});
  const grupos = {};
  d.itens.forEach((i) => (grupos[i.rotulo_origem] ||= []).push(i));
  for (const [rotulo, itens] of Object.entries(grupos)) {
    caixa.append(el("h2", { style: "margin-top:1.5rem" }, rotulo));
    itens.forEach((i) => {
      const tipo = i.veredito === "confirmado" ? "bom"
                 : i.veredito === "derrubado" ? "ruim"
                 : i.veredito === "sem_base" ? "espera" : "neutro";
      const rot = i.veredito === "confirmado" ? "confirmado nos seus dados"
                : i.veredito === "derrubado" ? "derrubado — não autoriza mais nada"
                : i.veredito === "sem_base" ? "sem base para dizer"
                : (i.medivel ? "ainda não medido" : "demonstrado");
      caixa.append(el("div", { class: "ia" },
        el("div", { class: "ia-topo" },
           el("h3", { class: "ia-nome" }, `${i.id} — ${i.titulo}`),
           selo(tipo, rot)),
        el("p", {}, i.afirma),
        el("p", { class: "ia-motivo", html:
          `<strong>O que derrubaria isto:</strong> ${i.derruba}` }),
        i.nota ? el("p", { class: "ia-motivo" }, i.nota) : null));
    });
  }
  $("#base-saida").replaceChildren(caixa);
}

/* ── amarração ───────────────────────────────────────────────────────── */
function desenharTudo() {
  desenharComecar();
  desenharFormular();
  desenharGrade();
  const j = estado.detalhe;
  $("#conf-dica-apostas").textContent =
    `Cada linha com ${j.minimo} a ${j.maximo} dezenas de ${j.primeiro} a `
    + `${j.primeiro + j.universo - 1}`;
  $("#conf-sorteio").placeholder =
    j.dezenas.slice(0, j.sorteadas).map((d) => String(d).padStart(2, "0")).join(" ");
  if (estado.secao === "resultados") desenharResultados();
  if (estado.secao === "base") desenharBase();
}

document.addEventListener("DOMContentLoaded", () => {
  $$(".menu-item").forEach((b) => b.addEventListener("click", () => {
    irPara(b.dataset.secao);
    if (b.dataset.secao === "resultados") desenharResultados();
    if (b.dataset.secao === "base") desenharBase();
  }));
  $("#btn-puxar").addEventListener("click", puxar);
  $("#btn-medir").addEventListener("click", medir);
  $("#btn-formular").addEventListener("click", formular);
  $("#btn-fechar").addEventListener("click", fechar);
  $("#btn-conferir").addEventListener("click", conferir);
  $("#btn-limpar").addEventListener("click", () => {
    estado.escolhidas.clear(); desenharGrade();
  });
  $("#btn-sortear").addEventListener("click", () => {
    const j = estado.detalhe;
    const todas = j.dezenas.slice();
    const quantas = Math.min(todas.length, Number($("#fech-k").value) + 4);
    estado.escolhidas.clear();
    while (estado.escolhidas.size < quantas) {
      estado.escolhidas.add(todas[Math.floor(Math.random() * todas.length)]);
    }
    desenharGrade();
  });
  ["#fech-k", "#fech-se", "#fech-gar"].forEach((s) =>
    $(s).addEventListener("input", atualizarConta));
  $("#btn-fonte").addEventListener("click", async () => {
    await pedir("/api/fonte", { url: $("#fonte-url").value,
                                url_concurso: $("#fonte-url-n").value });
    $("#fonte-estado").textContent = "Endereço guardado. Tente buscar os "
      + "resultados agora.";
  });
  montarAbas().catch((e) => {
    document.body.prepend(el("div", { class: "aviso aviso-ruim" },
      el("p", {}, "Não consegui falar com o programa: " + e.message)));
  });
});
