/* Painel ao vivo do GSA: consome a API REST e o fluxo SSE em /eventos. Sem dependências. */
"use strict";

const JANELA_LEITURAS_MIN = 120;
const PONTOS_POR_VIA = 60; // o gráfico mostra as últimas leituras de cada via
const MAX_CICLOS_GRAFICO = 30;
const CORES_VIA = ["--serie-1", "--serie-2", "--serie-3", "--serie-4"];
const NOMES_REGRA = {
  proporcional: "Proporcional",
  proporcional_com_limites: "Proporcional",
  webster: "Webster",
  plano_fixo: "Plano fixo",
};
const ROTULO_FLUXO = {
  baixo: "baixo",
  moderado: "moderado",
  alto: "alto",
  critico: "crítico",
};

const estado = {
  cruzamentos: [],
  selecionado: null,
  situacao: null,
  ciclo: null, // último ciclo calculado
  plano: null, // ciclo em execução na animação: { ciclo, linha, inicio }
  proximo: null, // ciclo calculado que entra quando o atual terminar
  motivoContingencia: null,
  leituras: [],
  ciclos: [],
  falhas: [],
};

const $ = (id) => document.getElementById(id);

async function api(caminho) {
  const resposta = await fetch(caminho, { headers: { Accept: "application/json" } });
  if (!resposta.ok) throw new Error(`${caminho}: HTTP ${resposta.status}`);
  return resposta.json();
}

function el(tag, atributos = {}, filhos = []) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "texto") no.textContent = valor;
    else if (chave === "classe") no.className = valor;
    else no.setAttribute(chave, valor);
  }
  for (const filho of [].concat(filhos)) if (filho) no.append(filho);
  return no;
}

const svgNS = "http://www.w3.org/2000/svg";
function svg(tag, atributos = {}) {
  const no = document.createElementNS(svgNS, tag);
  for (const [chave, valor] of Object.entries(atributos)) no.setAttribute(chave, valor);
  return no;
}

const hora = (data) =>
  data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const horaCurta = (data) => data.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
const corVia = (indice) => `var(${CORES_VIA[indice % CORES_VIA.length]})`;
const numero = (valor, casas = 1) =>
  valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/* ---------- carga ---------- */

async function iniciar() {
  try {
    estado.cruzamentos = await api("/cruzamentos");
  } catch (erro) {
    $("nome-cruzamento").textContent = "Não foi possível carregar os cruzamentos.";
    return;
  }
  const doEndereco = Number(new URLSearchParams(location.search).get("cruzamento"));
  const inicial =
    estado.cruzamentos.find((c) => c.id === doEndereco) ||
    estado.cruzamentos.find((c) => c.status === "ativo") ||
    estado.cruzamentos[0];
  desenharAbas();
  if (inicial) await selecionar(inicial.id);
  else $("nome-cruzamento").textContent = "Nenhum cruzamento cadastrado. Rode scripts/seed.py.";
  conectarEventos();
  carregarSimulacao();
  requestAnimationFrame(animar);
  setInterval(() => estado.selecionado && atualizarSituacao(), 30000);
}

function desenharAbas() {
  const abas = $("abas");
  abas.replaceChildren(
    ...estado.cruzamentos.map((c) => {
      const botao = el("button", { type: "button", texto: c.nome, "data-id": c.id, role: "tab" });
      botao.addEventListener("click", () => selecionar(c.id));
      return botao;
    }),
  );
}

async function selecionar(id) {
  estado.selecionado = id;
  estado.motivoContingencia = null;
  for (const botao of $("abas").children) {
    botao.setAttribute("aria-selected", String(Number(botao.dataset.id) === id));
  }
  const url = new URL(location.href);
  url.searchParams.set("cruzamento", id);
  history.replaceState(null, "", url);

  const inicio = new Date(Date.now() - JANELA_LEITURAS_MIN * 60000).toISOString();
  const [situacao, ciclos, leituras, falhas] = await Promise.all([
    api(`/cruzamentos/${id}/situacao`),
    api(`/cruzamentos/${id}/ciclos?limite=${MAX_CICLOS_GRAFICO}`),
    api(`/cruzamentos/${id}/leituras?limite=1000&inicio=${encodeURIComponent(inicio)}`),
    api(`/cruzamentos/${id}/falhas?status=aberta`),
  ]);
  if (estado.selecionado !== id) return;
  estado.situacao = situacao;
  estado.ciclos = ciclos.slice().reverse();
  estado.ciclo = ciclos[0] || null;
  estado.leituras = leituras.slice().reverse();
  estado.falhas = falhas;
  estado.plano = null;
  estado.proximo = null;
  if (estado.ciclo) {
    // retoma a animação na posição em que o ciclo estaria agora
    const linha = linhaDoTempo(estado.ciclo, situacao);
    const duracaoMs = linha.duracao * 1000;
    const decorrido = Date.now() - new Date(estado.ciclo.dataHoraInicio).getTime();
    aplicarPlano(estado.ciclo, Date.now() - (((decorrido % duracaoMs) + duracaoMs) % duracaoMs));
  }
  desenharTudo();
}

/* Como em um controlador real, um plano novo só entra no fim do ciclo em andamento. */
function aplicarPlano(ciclo, inicio) {
  estado.plano = { ciclo, linha: linhaDoTempo(ciclo, estado.situacao), inicio };
  desenharSemaforos();
  desenharBarraCiclo();
}

async function atualizarSituacao() {
  const id = estado.selecionado;
  const situacao = await api(`/cruzamentos/${id}/situacao`).catch(() => null);
  if (situacao && estado.selecionado === id) {
    estado.situacao = situacao;
    desenharIndicadores();
    desenharVias();
  }
}

function desenharTudo() {
  desenharIndicadores();
  desenharVias();
  desenharSemaforos();
  desenharBarraCiclo();
  desenharGraficoLeituras();
  desenharGraficoCiclos();
  desenharFalhas();
}

/* ---------- tempo real ---------- */

function conectarEventos() {
  const conexao = $("conexao");
  const fonte = new EventSource("/eventos");
  fonte.onopen = () => {
    conexao.dataset.estado = "conectado";
    conexao.textContent = "ao vivo";
  };
  fonte.onerror = () => {
    conexao.dataset.estado = "erro";
    conexao.textContent = "reconectando…";
  };
  fonte.addEventListener("ciclo", (evento) => {
    const { dados } = JSON.parse(evento.data);
    if (dados.cruzamentoId !== estado.selecionado) return;
    estado.ciclo = dados;
    estado.motivoContingencia = dados.motivoContingencia || null;
    estado.ciclos.push(dados);
    estado.ciclos = estado.ciclos.slice(-MAX_CICLOS_GRAFICO);
    if (estado.plano) estado.proximo = dados;
    else aplicarPlano(dados, Date.now());
    desenharGraficoCiclos();
    atualizarSituacao();
  });
  fonte.addEventListener("leituras", (evento) => {
    const { dados } = JSON.parse(evento.data);
    if (dados.cruzamentoId !== estado.selecionado) return;
    estado.leituras.push(...dados.leituras);
    const limite = Date.now() - JANELA_LEITURAS_MIN * 60000;
    estado.leituras = estado.leituras.filter((l) => new Date(l.dataHora).getTime() >= limite);
    desenharGraficoLeituras();
  });
  fonte.addEventListener("falha", (evento) => {
    const { dados } = JSON.parse(evento.data);
    if (dados.cruzamentoId !== estado.selecionado) return;
    estado.falhas = estado.falhas.filter((f) => f.id !== dados.id);
    if (dados.status === "aberta") estado.falhas.unshift(dados);
    desenharFalhas();
    atualizarSituacao();
  });
}

/* ---------- indicadores e vias ---------- */

function desenharIndicadores() {
  const s = estado.situacao;
  if (!s) return;
  $("nome-cruzamento").textContent = `${s.nome} · ${s.vias.length} vias · status ${s.status}`;
  const contingencia = s.modoOperacao === "contingencia";
  const selo = $("modo");
  selo.className = `selo ${contingencia ? "contingencia" : "adaptativo"}`;
  selo.textContent = contingencia ? "Modo de segurança" : "Adaptativo";
  const motivo = $("motivo");
  motivo.hidden = !contingencia;
  motivo.textContent = contingencia
    ? estado.motivoContingencia ||
      "Leituras ausentes ou desatualizadas: o cruzamento opera com o plano fixo de segurança."
    : "";

  $("kpi-veiculos").textContent = s.totalVeiculos;
  $("kpi-falhas").textContent = s.falhasAbertas;
  const ciclo = estado.ciclo;
  $("kpi-ciclo").textContent = ciclo ? `${ciclo.duracaoTotal} s` : "—";
  $("kpi-regra").textContent = ciclo
    ? NOMES_REGRA[ciclo.regraAplicada] || ciclo.regraAplicada
    : NOMES_REGRA[s.regraTemporizacao] || s.regraTemporizacao;
  $("kpi-saturacao").textContent =
    ciclo && ciclo.grauSaturacao != null ? numero(ciclo.grauSaturacao, 2) : "—";
  $("kpi-atualizado").textContent = ciclo ? hora(new Date(ciclo.dataHoraInicio)) : "—";
}

function desenharVias() {
  const s = estado.situacao;
  if (!s) return;
  // a barra mostra a fatia do ciclo que é verde para a via
  const referencia = Math.max(
    1,
    estado.ciclo?.duracaoTotal || 0,
    ...s.vias.map((v) => v.tempoVerdeRecomendado || 0),
  );
  $("vias").replaceChildren(
    ...s.vias.map((via, indice) => {
      const fluxo = via.leituraDesatualizada
        ? el("span", { classe: "badge sem-leitura", texto: "sem leitura recente" })
        : via.classificacaoFluxo
          ? el("span", {
              classe: `badge ${via.classificacaoFluxo}`,
              texto: ROTULO_FLUXO[via.classificacaoFluxo] || via.classificacaoFluxo,
            })
          : el("span", { classe: "badge sem-leitura", texto: "—" });
      const verde = via.tempoVerdeRecomendado;
      const barra = el("div", { classe: "verde-barra" }, [
        el("div", { classe: "trilho" }, [
          el("div", {
            classe: "preenchido",
            style: `width:${verde ? (100 * verde) / referencia : 0}%`,
          }),
        ]),
        el("span", { classe: "num", texto: verde != null ? `${verde} s` : "—" }),
      ]);
      return el("tr", {}, [
        el("td", {}, [
          el("span", { classe: "marca-via", style: `background:${corVia(indice)}` }),
          via.nome,
        ]),
        el("td", { texto: via.estagio ?? "—" }),
        el("td", { classe: "dir num", texto: via.quantidadeFaixas }),
        el("td", {
          classe: "dir num",
          texto: via.ultimaLeitura ? via.ultimaLeitura.quantidadeVeiculos : "—",
        }),
        el("td", {}, [fluxo]),
        el("td", {}, [barra]),
      ]);
    }),
  );
}

/* ---------- semáforos animados ---------- */

/* Reconstrói a sequência de estágios do ciclo: vias do mesmo estágio abrem juntas; vias sem
   estágio formam um estágio próprio (mesma regra do motor). O vermelho de segurança entre
   estágios é dividido igualmente para a visualização. */
function linhaDoTempo(ciclo, situacao) {
  if (!ciclo || !ciclo.tempos.length) return null;
  const estagioDaVia = new Map((situacao?.vias || []).map((v) => [v.viaId, v.estagio]));
  const grupos = new Map();
  for (const tempo of ciclo.tempos) {
    const estagio = estagioDaVia.get(tempo.viaId);
    const chave = estagio != null ? `e${estagio}` : `v${tempo.viaId}`;
    if (!grupos.has(chave)) {
      grupos.set(chave, {
        chave,
        rotulo: estagio != null ? `Estágio ${estagio}` : tempo.nomeVia,
        verde: tempo.tempoVerde,
        amarelo: tempo.tempoAmarelo,
        vias: [],
      });
    }
    grupos.get(chave).vias.push(tempo.viaId);
  }
  const estagios = [...grupos.values()];
  const usados = estagios.reduce((soma, e) => soma + e.verde + e.amarelo, 0);
  const vermelhoTotal = Math.max(0, ciclo.duracaoTotal - usados);
  let inicio = 0;
  estagios.forEach((e, i) => {
    const base = Math.floor(vermelhoTotal / estagios.length);
    e.vermelho = base + (i < vermelhoTotal - base * estagios.length ? 1 : 0);
    e.inicio = inicio;
    inicio += e.verde + e.amarelo + e.vermelho;
  });
  return { estagios, duracao: inicio };
}

function faseAtual(linha, segundo) {
  for (const e of linha.estagios) {
    const t = segundo - e.inicio;
    if (t < 0 || t >= e.verde + e.amarelo + e.vermelho) continue;
    if (t < e.verde) return { estagio: e, luz: "verde", resta: e.verde - t };
    if (t < e.verde + e.amarelo) return { estagio: e, luz: "amarelo", resta: e.verde + e.amarelo - t };
    return { estagio: e, luz: "vermelho-geral", resta: e.verde + e.amarelo + e.vermelho - t };
  }
  return null;
}

function desenharSemaforos() {
  const s = estado.situacao;
  const ciclo = estado.plano?.ciclo;
  const caixa = $("semaforos");
  if (!s || !ciclo) {
    caixa.replaceChildren(el("p", { classe: "sub", texto: "Aguardando o primeiro ciclo…" }));
    return;
  }
  const tempoDaVia = new Map(ciclo.tempos.map((t) => [t.viaId, t]));
  caixa.replaceChildren(
    ...s.vias.map((via) => {
      const tempo = tempoDaVia.get(via.viaId);
      return el("div", { classe: "semaforo", "data-via": via.viaId }, [
        el("div", { classe: "cabeca", "data-luz": "vermelho" }, [el("i"), el("i"), el("i")]),
        el("div", { classe: "semaforo-info" }, [
          el("strong", { texto: via.nome }),
          el("span", { classe: "contagem num", texto: "" }),
          el("span", {
            texto: tempo
              ? `verde ${tempo.tempoVerde} s · ${tempo.quantidadeVeiculos} veíc.`
              : "fora do cálculo",
          }),
        ]),
      ]);
    }),
  );
}

function desenharBarraCiclo() {
  const linha = estado.plano?.linha;
  const barra = $("ciclo-barra");
  const marcador = $("ciclo-marcador");
  barra.replaceChildren(marcador);
  const legenda = $("ciclo-legenda");
  if (!linha) {
    legenda.replaceChildren();
    $("ciclo-tempo").textContent = "";
    return;
  }
  for (const e of linha.estagios) {
    for (const [classe, duracao] of [
      ["verde", e.verde],
      ["amarelo", e.amarelo],
      ["vermelho", e.vermelho],
    ]) {
      if (duracao > 0) {
        barra.append(
          el("span", {
            classe: `seg ${classe}`,
            style: `flex:${duracao} 0 0`,
            title: `${e.rotulo}: ${classe} ${duracao} s`,
          }),
        );
      }
    }
  }
  legenda.replaceChildren(
    ...linha.estagios.map((e) => el("span", { texto: `${e.rotulo}: verde ${e.verde} s` })),
  );
}

function avancarPlano() {
  const plano = estado.plano;
  const duracaoMs = plano.linha.duracao * 1000;
  const agora = Date.now();
  if (agora - plano.inicio < duracaoMs) return;
  const fim = plano.inicio + duracaoMs;
  if (estado.proximo) {
    const novo = estado.proximo;
    estado.proximo = null;
    aplicarPlano(novo, fim);
  } else {
    plano.inicio = fim;
  }
  const atual = estado.plano;
  const novaDuracao = atual.linha.duracao * 1000;
  if (agora - atual.inicio >= novaDuracao) {
    atual.inicio = agora - ((agora - atual.inicio) % novaDuracao); // aba ficou em segundo plano
  }
}

function animar() {
  $("relogio").textContent = hora(new Date());
  if (estado.plano?.linha?.duracao > 0) {
    avancarPlano();
    const linha = estado.plano.linha;
    const segundo = (Date.now() - estado.plano.inicio) / 1000;
    $("ciclo-marcador").style.left = `calc(${(100 * segundo) / linha.duracao}% - 1px)`;
    const proximo = estado.proximo;
    $("ciclo-tempo").textContent =
      `${Math.floor(segundo)} / ${linha.duracao} s` +
      (proximo ? ` · próximo ciclo: ${proximo.duracaoTotal} s` : "");
    const fase = faseAtual(linha, segundo);
    for (const no of document.querySelectorAll(".semaforo")) {
      const viaId = Number(no.dataset.via);
      const cabeca = no.querySelector(".cabeca");
      const contagem = no.querySelector(".contagem");
      const ativo = fase && fase.estagio.vias.includes(viaId);
      let luz = "vermelho";
      let resta = null;
      if (ativo && fase.luz !== "vermelho-geral") {
        luz = fase.luz;
        resta = fase.resta;
      } else {
        resta = segundosAteVerde(linha, segundo, viaId);
      }
      cabeca.dataset.luz = luz;
      contagem.textContent = resta != null ? `${Math.ceil(resta)} s` : "";
    }
  }
  requestAnimationFrame(animar);
}

function segundosAteVerde(linha, segundo, viaId) {
  const estagio = linha.estagios.find((e) => e.vias.includes(viaId));
  if (!estagio) return null;
  const espera = estagio.inicio - segundo;
  return espera > 0 ? espera : espera + linha.duracao;
}

/* ---------- gráficos ---------- */

function eixoTempo(grupo, x, inicio, fim, altura, margem) {
  const passo = escolherPasso(fim - inicio);
  const formatar = fim - inicio <= 15 * 60000 ? hora : horaCurta;
  const primeiro = Math.ceil(inicio / passo) * passo;
  for (let t = primeiro; t <= fim; t += passo) {
    grupo.append(
      svg("line", { x1: x(t), x2: x(t), y1: margem.topo, y2: altura - margem.base, stroke: "var(--grade)" }),
    );
    const rotulo = svg("text", { x: x(t), y: altura - margem.base + 16, "text-anchor": "middle" });
    rotulo.textContent = formatar(new Date(t));
    grupo.append(rotulo);
  }
}

function escolherPasso(intervaloMs) {
  const segundos = intervaloMs / 1000;
  const passos = [10, 15, 30, 60, 120, 300, 600, 900, 1200, 1800, 3600, 7200];
  const passo = passos.find((p) => segundos / p <= 5) || 7200;
  return passo * 1000;
}

function eixoY(grupo, y, maximo, largura, margem) {
  const passo = Math.max(1, Math.ceil(maximo / 4 / 5) * 5);
  for (let v = 0; v <= maximo; v += passo) {
    grupo.append(
      svg("line", { x1: margem.esq, x2: largura - margem.dir, y1: y(v), y2: y(v), stroke: "var(--grade)" }),
    );
    const rotulo = svg("text", { x: margem.esq - 6, y: y(v) + 4, "text-anchor": "end" });
    rotulo.textContent = v;
    grupo.append(rotulo);
  }
}

function desenharGraficoLeituras() {
  const s = estado.situacao;
  const alvo = $("grafico-leituras");
  if (!s) return;
  const largura = 560;
  const altura = 230;
  const margem = { esq: 34, dir: 10, topo: 8, base: 24 };
  const porVia = new Map(s.vias.map((v) => [v.viaId, []]));
  for (const l of estado.leituras) {
    if (porVia.has(l.viaId)) {
      porVia.get(l.viaId).push([new Date(l.dataHora).getTime(), l.quantidadeVeiculos]);
    }
  }
  for (const [viaId, pontos] of porVia) {
    pontos.sort((a, b) => a[0] - b[0]);
    porVia.set(viaId, pontos.slice(-PONTOS_POR_VIA));
  }
  const visiveis = [...porVia.values()].flat();
  const fim = Date.now();
  const inicio = Math.min(fim - 60000, ...visiveis.map(([t]) => t));
  const maximo = Math.max(10, ...visiveis.map(([, v]) => v));
  const teto = Math.ceil(maximo / 10) * 10;
  const x = (t) => margem.esq + ((t - inicio) / (fim - inicio)) * (largura - margem.esq - margem.dir);
  const y = (v) => altura - margem.base - (v / teto) * (altura - margem.topo - margem.base);
  const raiz = svg("svg", { viewBox: `0 0 ${largura} ${altura}` });
  const grade = svg("g");
  eixoY(grade, y, teto, largura, margem);
  eixoTempo(grade, x, inicio, fim, altura, margem);
  raiz.append(grade);
  let indice = 0;
  for (const [, pontos] of porVia) {
    const cor = corVia(indice++);
    if (!pontos.length) continue;
    const d = pontos.map(([t, v], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join("");
    raiz.append(svg("path", { d, fill: "none", style: `stroke:${cor}`, "stroke-width": 2, "stroke-linejoin": "round" }));
    const [tf, vf] = pontos[pontos.length - 1];
    raiz.append(svg("circle", { cx: x(tf), cy: y(vf), r: 3.5, style: `fill:${cor}` }));
  }
  if (!visiveis.length) {
    const aviso = svg("text", { x: largura / 2, y: altura / 2, "text-anchor": "middle" });
    aviso.textContent = "Sem leituras nas últimas 2 horas";
    raiz.append(aviso);
  }
  alvo.replaceChildren(raiz);
  $("legenda-leituras").replaceChildren(
    ...s.vias.map((v, i) => el("span", { texto: v.nome, style: `--cor:${corVia(i)}` })),
  );
}

function desenharGraficoCiclos() {
  const alvo = $("grafico-ciclos");
  const ciclos = estado.ciclos;
  const largura = 560;
  const altura = 230;
  const margem = { esq: 34, dir: 10, topo: 8, base: 24 };
  const raiz = svg("svg", { viewBox: `0 0 ${largura} ${altura}` });
  if (!ciclos.length) {
    const aviso = svg("text", { x: largura / 2, y: altura / 2, "text-anchor": "middle" });
    aviso.textContent = "Nenhum ciclo calculado ainda";
    raiz.append(aviso);
    alvo.replaceChildren(raiz);
    return;
  }
  const teto = Math.ceil(Math.max(60, ...ciclos.map((c) => c.duracaoTotal)) / 30) * 30;
  const y = (v) => altura - margem.base - (v / teto) * (altura - margem.topo - margem.base);
  const grade = svg("g");
  eixoY(grade, y, teto, largura, margem);
  raiz.append(grade);
  const util = largura - margem.esq - margem.dir;
  const passo = util / MAX_CICLOS_GRAFICO;
  const larguraBarra = Math.max(4, passo - 4);
  ciclos.forEach((c, i) => {
    const xi = margem.esq + i * passo + (passo - larguraBarra) / 2;
    const cor = c.modoOperacao === "contingencia" ? "var(--sinal-amarelo)" : "var(--serie-1)";
    const barra = svg("rect", {
      x: xi,
      y: y(c.duracaoTotal),
      width: larguraBarra,
      height: Math.max(0, y(0) - y(c.duracaoTotal)),
      rx: 2,
      style: `fill:${cor}`,
    });
    const titulo = svg("title");
    titulo.textContent = `${hora(new Date(c.dataHoraInicio))} · ${c.duracaoTotal} s · ${c.totalVeiculos} veículos · ${NOMES_REGRA[c.regraAplicada] || c.regraAplicada}`;
    barra.append(titulo);
    raiz.append(barra);
  });
  const t0 = new Date(ciclos[0].dataHoraInicio);
  const t1 = new Date(ciclos[ciclos.length - 1].dataHoraInicio);
  const formatar = t1 - t0 <= 15 * 60000 ? hora : horaCurta;
  const primeiro = svg("text", { x: margem.esq, y: altura - 6 });
  primeiro.textContent = formatar(t0);
  const ultimo = svg("text", {
    x: margem.esq + (ciclos.length - 1) * passo + passo / 2,
    y: altura - 6,
    "text-anchor": "middle",
  });
  ultimo.textContent = formatar(t1);
  raiz.append(primeiro);
  if (ciclos.length > 1) raiz.append(ultimo);
  alvo.replaceChildren(raiz);
}

/* ---------- falhas ---------- */

function desenharFalhas() {
  const lista = $("falhas");
  if (!estado.falhas.length) {
    lista.replaceChildren(el("li", { classe: "vazio", texto: "Nenhuma falha aberta." }));
    return;
  }
  lista.replaceChildren(
    ...estado.falhas.map((f) =>
      el("li", {}, [
        el("time", { texto: hora(new Date(f.detectadaEm)) }),
        el("span", { texto: f.descricao }),
      ]),
    ),
  );
}

/* ---------- simulação ---------- */

async function carregarSimulacao() {
  let dados;
  try {
    dados = await api("simulacao.json");
  } catch {
    $("simulacao").hidden = true;
    return;
  }
  const busca = (cenario, id) => dados.cenarios[cenario].find((e) => e.id === id);
  const reducao = (de, para) => Math.round((100 * (de - para)) / de);
  const altaFixo = busca("alta", "fixo_igual");
  const altaWebster = busca("alta", "adaptativo_webster");
  const modFixo = busca("moderada", "fixo_igual");
  const modWebster = busca("moderada", "adaptativo_webster");
  const destaques = [
    [
      `−${reducao(altaFixo.espera_media_s, altaWebster.espera_media_s)}%`,
      `espera média com demanda alta (${numero(altaFixo.espera_media_s)} s → ` +
        `${numero(altaWebster.espera_media_s)} s)`,
    ],
    [
      `−${reducao(modFixo.espera_media_s, modWebster.espera_media_s)}%`,
      `espera média com demanda moderada (${numero(modFixo.espera_media_s)} s → ` +
        `${numero(modWebster.espera_media_s)} s)`,
    ],
    [
      `${numero(altaFixo.espera_p95_s, 0)} s → ${numero(altaWebster.espera_p95_s, 0)} s`,
      "espera do 95º percentil com demanda alta",
    ],
  ];
  $("destaques").replaceChildren(
    ...destaques.map(([valor, texto]) =>
      el("div", { classe: "destaque" }, [el("strong", { texto: valor }), el("span", { texto })]),
    ),
  );
  $("nota-simulacao").textContent =
    `Comparação entre tempo fixo de ${dados.premissas.ciclo_tempo_fixo_s} s (divisão igual) e o ` +
    `GSA com a regra de Webster. Simulação com demanda sintética (${dados.periodo}, ` +
    `${dados.sementes} sementes), não medição em campo. Premissas em docs/ e no script ` +
    `scripts/simulacao_comparativa.py.`;
}

iniciar();
