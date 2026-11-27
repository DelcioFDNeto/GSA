/* Interface do simulador: carrega a configuração do cruzamento pela API do GSA, cria o mundo,
   desenha a 60 quadros por segundo e liga os controles. A física fica em mundo.js e a
   comunicação com o GSA em conexao.js; aqui só há DOM. */

import { ConexaoSimulador, PonteGSA } from "./conexao.js";
import { AMARELO, VERDE, VERMELHO, duracaoDoPlano } from "./controlador.js";
import { COR_ZONA, Renderizador } from "./desenho.js";
import { SENTIDOS } from "./geometria.js";
import { FATOR_CONGESTIONAMENTO, Mundo, PRESETS_HORA } from "./mundo.js";

const $ = (id) => document.getElementById(id);
const SEMENTE_PADRAO = 2026;
const ATUALIZACAO_PAINEL_MS = 200;
const NOMES_REGRA = {
  proporcional: "Proporcional",
  proporcional_com_limites: "Proporcional",
  webster: "Webster",
  plano_fixo: "Plano fixo (modo de segurança)",
};
const ROTULO_FLUXO = { baixo: "baixo", moderado: "moderado", alto: "alto", critico: "crítico" };
const NOME_FASE = { [VERDE]: "verde", [AMARELO]: "amarelo", [VERMELHO]: "vermelho geral" };
// Linhas da tabela de vias (as colunas são as vias): [chave, rótulo, explicação, vem do GSA?]
const INDICADORES = [
  ["presentes", "Veículos", "Na aproximação, inclusive fora do quadro e aguardando para entrar", false],
  ["parados", "Parados", "Abaixo de 0,5 m/s", false],
  ["fila", "Fila", "Veículos abaixo de 2 m/s antes da retenção · metros até o último da fila", false],
  ["espera", "Espera média", "Tempo parado, em média, de quem já cruzou a retenção", false],
  ["demanda", "Demanda (GSA)", "Fração dos veículos do cruzamento no último cálculo do GSA", true],
  ["fluxo", "Fluxo (GSA)", "Classificação por veículos por faixa no último cálculo do GSA", true],
  ["verde", "Verde (GSA)", "Tempo de verde do último ciclo calculado pelo GSA", true],
];

const app = {
  conexao: new ConexaoSimulador(),
  info: null,
  config: null,
  cruzamentoId: null,
  mundo: null,
  ponte: null,
  renderB: null,
  renderA: null,
  opcoes: { caixas: true, zonas: false, comparar: false, base: "igual", modoZona: "aproximacao", zoom: 1.5 },
  semente: SEMENTE_PADRAO,
  presetHora: null,
  falhaDesde: null,
  ultimoQuadro: 0,
  ultimoPainel: 0,
  ultimoAria: 0,
  planoDesenhado: null,
  loteMostrado: null,
  cicloMostrado: null,
  velocidadeMedida: { real: 0, simulado: 0, valor: 0 },
  linhasVia: new Map(),
  linhasFluxo: new Map(),
};

/* ---------- formatação ---------- */

const numero = (valor, casas = 0) =>
  Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
const dois = (n) => String(Math.floor(n)).padStart(2, "0");
const horaDoDia = (h) => `${dois(h)}:${dois((h % 1) * 60)}`;
const duracao = (s) => `${dois(s / 3600)}:${dois((s % 3600) / 60)}:${dois(s % 60)}`;
const segundos = (s) => `${numero(s, s < 10 ? 1 : 0)} s`;

/** Só altera o DOM quando o texto muda (o cartão de semáforos é atualizado a cada quadro). */
function definir(no, texto) {
  if (no.textContent !== texto) no.textContent = texto;
}

function el(tag, atributos = {}, filhos = []) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "texto") no.textContent = valor;
    else if (chave === "classe") no.className = valor;
    else no.setAttribute(chave, valor);
  }
  for (const filho of [].concat(filhos)) if (filho != null) no.append(filho);
  return no;
}

function mostrarAviso(texto, tipo = "erro") {
  const aviso = $("aviso");
  aviso.hidden = !texto;
  aviso.className = `aviso${tipo === "info" ? " info" : ""}`;
  aviso.textContent = texto || "";
}

function indicadorConexao(estado, texto) {
  const no = $("conexao");
  no.dataset.estado = estado;
  no.textContent = texto;
}

/* ---------- carga ---------- */

async function iniciar() {
  const parametros = new URLSearchParams(location.search);
  app.semente = Number(parametros.get("semente")) || SEMENTE_PADRAO;
  $("inp-semente").value = app.semente;
  try {
    app.info = await app.conexao.estado();
  } catch (erro) {
    indicadorConexao("erro", "servidor fora do ar");
    mostrarAviso(
      `O servidor do simulador não respondeu (${erro.message}). Inicie com "python -m simulador" ` +
        "e recarregue a página.",
    );
    return;
  }
  if (!app.info.gsaOnline) {
    indicadorConexao("erro", "GSA fora do ar");
    mostrarAviso(`O GSA não respondeu: ${app.info.erro || "sem detalhes"}`);
    return;
  }
  app.cruzamentoId = Number(parametros.get("cruzamento")) || app.info.cruzamentoPadrao;
  if (!app.cruzamentoId) {
    mostrarAviso(
      "Nenhum cruzamento ativo com vias norte, sul, leste ou oeste. Popule a demonstração " +
        "com python -m scripts.seed (ou use python -m simulador, que já faz isso).",
    );
    return;
  }
  try {
    app.config = await app.conexao.configuracao(app.cruzamentoId);
  } catch (erro) {
    mostrarAviso(`Não foi possível carregar o cruzamento ${app.cruzamentoId}: ${erro.message}`);
    return;
  }
  const avisos = [...(app.config.avisos || [])];
  if (!app.info.chaveConfigurada) {
    avisos.unshift("GSA_CHAVE_API_DETECCAO não está definida no servidor: o GSA vai recusar as leituras.");
  }
  if (avisos.length) mostrarAviso(avisos.join(" "), "info");

  const { cruzamento } = app.config;
  $("subtitulo").textContent = `${cruzamento.nome} · regra ${NOMES_REGRA[cruzamento.regraTemporizacao] || cruzamento.regraTemporizacao}`;
  $("link-painel").href = app.config.urlPainel || app.info.urlPainel;
  $("lote-cruzamento").textContent = cruzamento.id;
  $("janela-dur").textContent = app.config.janelaSegundos;
  document.title = `GSA — Simulador · ${cruzamento.nome}`;

  app.renderB = new Renderizador($("canvas-b"));
  app.renderA = new Renderizador($("canvas-a"));
  const observador = new ResizeObserver((entradas) => {
    for (const entrada of entradas) {
      const render = entrada.target.id === "canvas-a" ? app.renderA : app.renderB;
      render.ajustarTamanho(entrada.contentRect.width);
    }
  });
  observador.observe($("canvas-b"));
  observador.observe($("canvas-a"));
  app.renderB.ajustarTamanho($("canvas-b").clientWidth);

  app.ponte = new PonteGSA({ conexao: app.conexao, cruzamentoId: app.cruzamentoId });
  ligarControles();
  await criarMundo();
  $("btn-iniciar").disabled = false;
  $("btn-reiniciar").disabled = false;
  indicadorConexao("aviso", "pronto — clique em Iniciar");
  window.__simulador = app; // inspeção e testes de interface
  requestAnimationFrame(laco);
}

/** Cria (ou recria, no reinício) o mundo com a semente, a demanda e o modo atuais. */
async function criarMundo({ manterRodando = false } = {}) {
  const anterior = app.mundo;
  const rodando = manterRodando && anterior?.rodando;
  const planoA = app.opcoes.comparar ? await planoDoCruzamentoA() : null;
  app.mundo = new Mundo({
    configuracao: app.config,
    semente: app.semente,
    planoA,
    demanda: anterior?.demanda ?? null,
  });
  if (anterior) app.mundo.velocidade = anterior.velocidade;
  app.mundo.modoZona = app.opcoes.modoZona;
  app.renderB.definirGeometria(app.mundo.geometria, app.semente);
  app.renderA.definirGeometria(app.mundo.geometria, app.semente);
  app.renderB.definirZoom(app.opcoes.zoom);
  app.renderA.definirZoom(app.opcoes.zoom);
  app.planoDesenhado = null;
  app.ponte.encerrar();
  app.ponte.viasSemEnvio = $("sel-falha").value ? [Number($("sel-falha").value)] : [];
  $("telas").classList.toggle("comparando", app.mundo.comparando);
  $("lateral").classList.toggle("comparando", app.mundo.comparando);
  $("tela-a").hidden = !app.mundo.comparando;
  $("cartao-comparacao").hidden = !app.mundo.comparando;
  if (app.mundo.comparando) {
    $("legenda-a").textContent = `ciclo ${duracaoDoPlano(planoA)} s · ${planoA.estagios.map((e) => e.verde).join("/")} s`;
  }
  montarTabelaVias();
  montarFluxos();
  if (rodando) {
    app.mundo.iniciar();
    app.ponte.abrir(app.mundo);
  }
  atualizarBotaoIniciar();
  atualizarPainel();
}

async function planoDoCruzamentoA() {
  if (app.opcoes.base !== "ajustado" || !app.mundo) return app.config.planoFixo;
  const taxas = app.mundo.taxasMediasDoDia();
  try {
    return await app.conexao.planoFixo(app.cruzamentoId, "ajustado", taxas);
  } catch (erro) {
    mostrarAviso(`Plano ajustado indisponível (${erro.message}); usando o plano fixo do GSA.`, "info");
    return app.config.planoFixo;
  }
}

/* ---------- laço principal ---------- */

function laco(agora) {
  const dtReal = app.ultimoQuadro ? Math.min(0.25, (agora - app.ultimoQuadro) / 1000) : 0;
  app.ultimoQuadro = agora;
  const m = app.mundo;
  const antes = m.t;
  m.avancar(dtReal);
  medirVelocidade(dtReal, m.t - antes);
  if (app.ponte.sessaoId || app.ponte.status !== "parada") app.ponte.sincronizar(m);
  desenhar();
  atualizarMarcadorCiclo();
  atualizarSemaforos();
  if (agora - app.ultimoPainel >= ATUALIZACAO_PAINEL_MS) {
    app.ultimoPainel = agora;
    atualizarPainel();
  }
  requestAnimationFrame(laco);
}

function medirVelocidade(dtReal, dtSimulado) {
  const medida = app.velocidadeMedida;
  medida.real += dtReal;
  medida.simulado += dtSimulado;
  if (medida.real >= 1) {
    medida.valor = medida.simulado / medida.real;
    medida.real = 0;
    medida.simulado = 0;
  }
}

function desenhar() {
  const m = app.mundo;
  const ponte = app.ponte;
  const plano = m.b.controlador.plano;
  const falha = m.b.controlador.falha;
  const janela = ponte.janela;
  const decorrido = janela.duracao ? Math.max(0, m.t - janela.inicio) : null;
  app.renderB.desenhar(m.b, {
    alpha: m.alpha,
    caixas: app.opcoes.caixas ? m.cameraB.caixasParaDesenho(m.b, m.alpha, m.t) : null,
    zonas: app.opcoes.zonas,
    modoZona: app.mundo.modoZona,
    parcial: janela.parcial,
    viasSemEnvio: ponte.viasSemEnvio,
    hud: {
      superiorEsquerdo: `CAM 01 · YOLO11 + ByteTrack (sintético) · ${m.cameraB.ultimoQuadro?.deteccoes.length ?? 0} detecções`,
      superiorDireito:
        `${relogioHud(m)}` +
        (decorrido != null ? ` · janela ${numero(Math.min(decorrido, janela.duracao), 1)}/${janela.duracao} s` : ""),
      inferior: `GSA: ciclo ${duracaoDoPlano(plano)} s | verdes ${plano.estagios.map((e) => e.verde).join("/")} s | ${rotuloModo(plano).texto}`,
      corInferior: plano.modoOperacao === "contingencia" ? "#ffd166" : "#e8eaed",
      alerta: falha ? "FALHA DO CONTROLADOR — todas as vias fechadas" : null,
    },
  });
  if (m.a) {
    const planoA = m.a.controlador.plano;
    app.renderA.desenhar(m.a, {
      alpha: m.alpha,
      hud: {
        superiorEsquerdo: "Controlador de tempo fixo — sem câmera e sem GSA",
        superiorDireito: relogioHud(m),
        inferior: `Tempo fixo: ciclo ${duracaoDoPlano(planoA)} s | verdes ${planoA.estagios.map((e) => e.verde).join("/")} s`,
      },
    });
  }
}

/** Tempo simulado e velocidade medida, mostrados no canto do quadro. */
function relogioHud(m) {
  if (!m.rodando) return `${duracao(m.t)} · pausado`;
  const medida = app.velocidadeMedida.valor || m.velocidade;
  return `${duracao(m.t)} · ${numero(medida, medida < 9.95 ? 1 : 0)}×${m.limitado ? " (limitado pelo processador)" : ""}`;
}

/* ---------- semáforos ---------- */

function rotuloModo(plano) {
  if (plano.origem === "contingencia_local") return { texto: "contingência local", classe: "contingencia" };
  if (plano.origem === "gsa") {
    return plano.modoOperacao === "contingencia"
      ? { texto: "modo de segurança (GSA)", classe: "contingencia" }
      : { texto: "adaptativo (GSA)", classe: "adaptativo" };
  }
  if (plano.origem === "tempo_fixo_ajustado") return { texto: "tempo fixo ajustado", classe: "fixo" };
  return { texto: "plano fixo inicial", classe: "fixo" };
}

function nomeDaVia(id) {
  const via = app.mundo.geometria.vias.find((v) => v.id === id);
  return via ? `${via.nomeCurto} ${via.seta}` : `via ${id}`;
}

function desenharBarraCiclo(plano) {
  const barra = $("ciclo-barra");
  const marcador = $("ciclo-marcador");
  barra.replaceChildren(marcador);
  for (const e of plano.estagios) {
    for (const [classe, tempo] of [
      ["verde", e.verde],
      ["amarelo", e.amarelo],
      ["vermelho", e.vermelho],
    ]) {
      if (tempo > 0) {
        barra.append(el("span", { classe: `seg ${classe}`, style: `flex:${tempo} 0 0`, title: `${e.rotulo}: ${classe} ${tempo} s` }));
      }
    }
  }
  $("ciclo-legenda").replaceChildren(
    ...plano.estagios.map((e) =>
      el("span", { texto: `${e.rotulo}: verde ${e.verde} s + ${e.amarelo} s amarelo + ${e.vermelho} s vermelho geral` }),
    ),
  );
  app.planoDesenhado = plano;
}

function atualizarMarcadorCiclo() {
  const ctrl = app.mundo.b.controlador;
  if (ctrl.plano !== app.planoDesenhado) desenharBarraCiclo(ctrl.plano);
  const total = ctrl.duracaoDoCiclo();
  const decorrido = ctrl.decorridoNoCiclo();
  $("ciclo-marcador").style.left = `calc(${(100 * decorrido) / total}% - 1px)`;
  definir($("ciclo-tempo"), `${Math.floor(decorrido)} / ${total} s`);
}

function atualizarSemaforos() {
  const ctrl = app.mundo.b.controlador;
  const plano = ctrl.plano;
  const modo = ctrl.falha ? { texto: "falha — tudo vermelho", classe: "erro" } : rotuloModo(plano);
  const selo = $("modo");
  if (selo.className !== `selo ${modo.classe}`) selo.className = `selo ${modo.classe}`;
  definir(selo, modo.texto);
  const estagio = ctrl.estagio;
  const luz = ctrl.fase === VERMELHO || ctrl.falha ? "vermelho" : ctrl.fase;
  if ($("fase-cabeca").dataset.luz !== luz) $("fase-cabeca").dataset.luz = luz;
  definir($("fase-estagio"), ctrl.fase === VERMELHO ? "Vermelho geral" : estagio.rotulo);
  definir(
    $("fase-vias"),
    ctrl.fase === VERMELHO
      ? `segurança depois do ${estagio.rotulo.toLowerCase()}`
      : estagio.vias.map(nomeDaVia).join(" · "),
  );
  definir($("fase-restante"), `${Math.ceil(ctrl.restanteDaFase())} s`);
  definir($("fase-nome"), `${NOME_FASE[ctrl.fase]} · restante`);
  definir(
    $("ciclo-origem"),
    plano.origem === "gsa" ? `Ciclo do GSA${plano.cicloId ? ` nº ${plano.cicloId}` : ""} em execução` : "Plano em execução",
  );
  const pendente = $("plano-pendente");
  pendente.hidden = !ctrl.pendente;
  if (ctrl.pendente) {
    const falta = Math.max(0, ctrl.duracaoDoCiclo() - ctrl.decorridoNoCiclo());
    const p = ctrl.pendente;
    definir(
      pendente,
      `Próximo plano (${rotuloModo(p).texto}, ciclo ${duracaoDoPlano(p)} s, verdes ${p.estagios.map((e) => e.verde).join("/")} s) ` +
        `entra no fim deste ciclo, em ${Math.ceil(falta)} s.`,
    );
  }
  const motivo = $("motivo");
  const texto = plano.modoOperacao === "contingencia" ? plano.motivoContingencia : null;
  motivo.hidden = !texto;
  definir(motivo, texto || "");
}

/** Verificações de segurança (mais caras: na frequência do painel). */
function atualizarSeguranca() {
  const ctrl = app.mundo.b.controlador;
  const problemas = app.mundo.b.sobreposicoes().length + (app.mundo.a ? app.mundo.a.sobreposicoes().length : 0);
  const recusados = ctrl.rejeitados.length;
  definir(
    $("seguranca"),
    `Monitor de conflitos: ${ctrl.falha ? ctrl.falha.mensagem : "nenhum movimento conflitante aberto"} · ` +
      `sobreposições de veículos: ${problemas} · planos recusados: ${recusados}` +
      (recusados ? ` (${ctrl.rejeitados.at(-1).erros[0]})` : ""),
  );
}

/* ---------- vias ---------- */

function montarTabelaVias() {
  app.linhasVia.clear();
  const vias = app.mundo.geometria.vias;
  const cabecalho = [el("th", { scope: "col", texto: "Indicador" })];
  vias.forEach((via, i) => {
    const luz = el("span", { classe: "luz-via", "data-luz": "vermelho", title: "sinal da via agora" });
    cabecalho.push(
      el("th", { scope: "col", classe: "dir", title: via.nome }, [
        el("span", { classe: "cab-via" }, [
          el("span", { classe: "marca-via", style: `background:${COR_ZONA[i % COR_ZONA.length]}` }),
          el("span", { classe: "seta", texto: via.seta }),
          luz,
        ]),
        el("span", { classe: "cab-sub", texto: SENTIDOS[via.sentido].nome.toLowerCase() }),
      ]),
    );
    app.linhasVia.set(via.id, { luz, celulas: {} });
  });
  $("cabecalho-vias").replaceChildren(...cabecalho);
  $("vias").replaceChildren(
    ...INDICADORES.map(([chave, rotulo, dica, doGsa]) => {
      const linha = el("tr", { classe: doGsa ? "gsa" : "" }, [el("th", { scope: "row", title: dica, texto: rotulo })]);
      for (const via of vias) {
        const celula = el("td", { classe: "dir num" });
        app.linhasVia.get(via.id).celulas[chave] = celula;
        linha.append(celula);
      }
      return linha;
    }),
  );
  const ruas = new Map();
  for (const via of vias) {
    const rua = ruas.get(via.nomeCurto) || { setas: [], faixas: [], estagios: new Set() };
    rua.setas.push(via.seta);
    rua.faixas.push(via.quantidadeFaixas);
    rua.estagios.add(via.estagio ?? "próprio");
    ruas.set(via.nomeCurto, rua);
  }
  $("legenda-vias").textContent = [...ruas]
    .map(([nome, r]) => {
      const faixas = [...new Set(r.faixas)].join("/");
      return `${r.setas.join(" ")} ${nome}: ${faixas} faixa${faixas === "1" ? "" : "s"} por sentido, estágio ${[...r.estagios].join("/")}`;
    })
    .join(" · ");
}

function atualizarVias(resumo) {
  const tempos = app.ponte.ultimoPlano?.tempos || {};
  for (const via of resumo.porVia) {
    const linha = app.linhasVia.get(via.id);
    if (!linha) continue;
    const c = linha.celulas;
    const gsa = tempos[String(via.id)];
    const luz = app.mundo.b.estados.get(via.id);
    if (linha.luz.dataset.luz !== luz) linha.luz.dataset.luz = luz;
    definir(c.presentes, String(via.presentes));
    c.presentes.title = `${via.visiveis} no quadro da câmera · ${via.aguardandoEntrada} aguardando para entrar`;
    definir(c.parados, String(via.parados));
    definir(c.fila, via.fila ? `${via.fila} · ${numero(via.filaMetros)}m` : "0");
    definir(c.espera, via.servidos ? segundos(via.esperaMedia) : "—");
    definir(c.demanda, gsa ? `${numero(gsa.demanda, 1)}%` : "—");
    const fluxo = gsa ? gsa.classificacao : "";
    if (c.fluxo.dataset.valor !== fluxo) {
      c.fluxo.dataset.valor = fluxo;
      c.fluxo.replaceChildren(
        gsa ? el("span", { classe: `badge ${fluxo}`, texto: ROTULO_FLUXO[fluxo] || fluxo }) : "—",
      );
    }
    definir(c.verde, gsa ? `${gsa.verde} s` : "—");
  }
  definir($("tot-servidos"), numero(resumo.servidos));
  definir($("tot-vazao"), resumo.t > 30 ? `${numero(resumo.vazao)} veíc/h` : "—");
  definir($("tot-espera"), resumo.servidos ? segundos(resumo.esperaMedia) : "—");
  definir($("tot-fila"), `${numero(resumo.filaMedia, 1)} · ${resumo.filaMaxima}`);
}

/* ---------- demanda e cenários ---------- */

function montarFluxos() {
  app.linhasFluxo.clear();
  const itens = app.mundo.geometria.vias.map((via) => {
    const valor = el("span", { classe: "valor num" });
    const menos = el("button", { type: "button", "aria-label": `Reduzir o fluxo de ${via.nome}`, texto: "−" });
    const mais = el("button", { type: "button", "aria-label": `Aumentar o fluxo de ${via.nome}`, texto: "+" });
    menos.addEventListener("click", () => ajustarFluxo(via.id, -0.1));
    mais.addEventListener("click", () => ajustarFluxo(via.id, +0.1));
    app.linhasFluxo.set(via.id, valor);
    return el("li", {}, [el("span", { classe: "nome", title: via.nome, texto: `${via.nomeCurto} ${via.seta}` }), menos, valor, mais]);
  });
  $("fluxos").replaceChildren(...itens);

  const congestionamento = $("sel-congestionamento");
  const atual = congestionamento.value;
  congestionamento.replaceChildren(el("option", { value: "", texto: "nenhum" }));
  for (const eixo of ["ns", "lo"]) {
    const vias = app.mundo.geometria.vias.filter((v) => v.eixo === eixo);
    if (!vias.length) continue;
    const nomes = [...new Set(vias.map((v) => v.nomeCurto))];
    const nome = nomes.length === 1 ? nomes[0] : eixo === "ns" ? "Eixo norte–sul" : "Eixo leste–oeste";
    congestionamento.append(el("option", { value: eixo, texto: `${nome} (demanda ×${numero(FATOR_CONGESTIONAMENTO, 1)})` }));
  }
  congestionamento.value = app.mundo.demanda.congestionamento?.eixo || atual || "";

  const falha = $("sel-falha");
  const falhaAtual = falha.value;
  falha.replaceChildren(el("option", { value: "", texto: "nenhuma" }));
  for (const via of app.mundo.geometria.vias) falha.append(el("option", { value: via.id, texto: `${via.nomeCurto} ${via.seta}` }));
  falha.value = falhaAtual;
}

function ajustarFluxo(viaId, delta) {
  app.mundo.ajustarFluxo(viaId, delta);
  atualizarDemanda();
}

function atualizarDemanda() {
  const m = app.mundo;
  let total = 0;
  for (const via of m.geometria.vias) {
    const taxa = m.taxaDaVia(via.id);
    total += taxa;
    const valor = app.linhasFluxo.get(via.id);
    if (valor) {
      valor.replaceChildren(`${numero(taxa)} veíc/h `, el("small", { texto: `(${numero(m.fator(via.id) * 100)}%)` }));
    }
  }
  $("hora-demanda").textContent = `${horaDoDia(m.horaAtual())} · ${numero(total)} veíc/h no total`;
  for (const botao of $("presets-hora").children) {
    botao.setAttribute("aria-pressed", String(botao.dataset.preset === app.presetHora && !m.demanda.relogio));
  }
  const nota = $("nota-falha");
  nota.hidden = !app.ponte.viasSemEnvio.length;
  if (app.ponte.viasSemEnvio.length) {
    const desde = app.falhaDesde ? Math.round((performance.now() - app.falhaDesde) / 1000) : 0;
    const limite = app.config.parametros.tempoMaximoSemLeitura;
    nota.textContent =
      `Leituras de ${nomeDaVia(app.ponte.viasSemEnvio[0])} fora do lote há ${desde} s (relógio real). ` +
      `O GSA entra no modo de segurança quando a via passar ${limite} s sem leitura (tempoMaximoSemLeitura).`;
  }
}

/* ---------- integração e comparação ---------- */

function atualizarIntegracao() {
  const ponte = app.ponte;
  const m = app.mundo;
  const plano = ponte.ultimoPlano;
  $("kpi-regra").textContent = plano ? NOMES_REGRA[plano.regra] || plano.regra : `${NOMES_REGRA[app.config.cruzamento.regraTemporizacao] || app.config.cruzamento.regraTemporizacao} (configurada)`;
  $("kpi-ciclo").textContent = plano ? `${plano.duracaoGsa} s` : "—";
  $("kpi-saturacao").textContent = plano?.grauSaturacao != null ? numero(plano.grauSaturacao, 2) : "—";
  $("kpi-janelas").textContent = ponte.janelasComErro ? `${ponte.janelasEnviadas} (+${ponte.janelasComErro} com erro)` : `${ponte.janelasEnviadas}`;
  const janela = ponte.janela;
  if (janela.duracao) {
    const decorrido = Math.min(janela.duracao, Math.max(0, m.t - janela.inicio));
    $("janela-tempo").textContent = `${numero(decorrido, 1)} / ${janela.duracao} s`;
    $("janela-barra").style.width = `${(100 * decorrido) / janela.duracao}%`;
  } else {
    $("janela-tempo").textContent = "câmera parada";
    $("janela-barra").style.width = "0";
  }
  const modoApi = app.info.modoApi === "remoto" ? `GSA remoto (${app.info.apiUrl})` : "GSA local, mesmo processo, pela rota REST";
  const latencia = ponte.latenciaMs != null ? ` · último envio ${numero(ponte.latenciaMs, 0)} ms` : "";
  $("api-detalhe").textContent = `${modoApi}${latencia}${ponte.mensagem ? ` · ${ponte.mensagem}` : ""}`;

  const status = $("status-api");
  const mapa = {
    parada: ["aguardando início", "neutro", "aviso", "pronto — clique em Iniciar"],
    conectando: ["conectando", "neutro", "aviso", "conectando…"],
    ativa: ["online", "ok", "conectado", "GSA conectado"],
    erro: ["erro", "erro", "erro", "erro na comunicação"],
    substituida: ["outra aba", "aviso", "aviso", "outra aba assumiu a câmera"],
  };
  const [texto, classe, estado, topo] = mapa[ponte.status] || mapa.parada;
  status.className = `selo ${classe}`;
  status.textContent = texto;
  indicadorConexao(estado, ponte.status === "ativa" && ponte.contingenciaLocal ? "GSA sem resposta" : topo);

  if (ponte.ultimoLote !== app.loteMostrado) {
    app.loteMostrado = ponte.ultimoLote;
    $("json-lote").textContent = JSON.stringify(ponte.ultimoLote, null, 2);
  }
  if (ponte.ultimoCiclo !== app.cicloMostrado) {
    app.cicloMostrado = ponte.ultimoCiclo;
    $("json-ciclo").textContent = JSON.stringify(ponte.ultimoCiclo, null, 2);
  }
}

function variacao(a, b, menorMelhor) {
  if (!a) return { texto: "—", classe: "" };
  const v = (b - a) / a;
  const melhor = menorMelhor ? v < 0 : v > 0;
  const sinal = v > 0 ? "+" : "−";
  return { texto: `${sinal}${numero(Math.abs(v) * 100)}%`, classe: Math.abs(v) < 0.005 ? "" : melhor ? "melhor" : "pior" };
}

function atualizarComparacao(ra, rb) {
  const linhas = [
    ["Tempo médio de espera", segundos(ra.esperaMedia), segundos(rb.esperaMedia), variacao(ra.esperaMedia, rb.esperaMedia, true)],
    ["Espera acumulada", `${numero(ra.esperaAcumulada / 60)} min`, `${numero(rb.esperaAcumulada / 60)} min`, variacao(ra.esperaAcumulada, rb.esperaAcumulada, true)],
    ["Fila média (veíc. por via)", numero(ra.filaMedia, 1), numero(rb.filaMedia, 1), variacao(ra.filaMedia, rb.filaMedia, true)],
    ["Fila máxima (veíc.)", ra.filaMaxima, rb.filaMaxima, variacao(ra.filaMaxima, rb.filaMaxima, true)],
    ["Veículos atendidos", numero(ra.servidos), numero(rb.servidos), variacao(ra.servidos, rb.servidos, false)],
    ["Vazão (veíc/h)", numero(ra.vazao), numero(rb.vazao), variacao(ra.vazao, rb.vazao, false)],
    ["Na aproximação agora", ra.noSistema, rb.noSistema, variacao(ra.noSistema, rb.noSistema, true)],
  ];
  $("comparacao").replaceChildren(
    ...linhas.map(([nome, a, b, v]) =>
      el("tr", {}, [el("td", { texto: nome }), el("td", { classe: "dir num", texto: a }), el("td", { classe: "dir num", texto: b }), el("td", { classe: `dir num ${v.classe}`, texto: v.texto })]),
    ),
  );
  const destaque = $("destaque-comparacao");
  if (ra.servidos < 20 || rb.servidos < 20) {
    destaque.textContent = "Coletando dados — os números ficam estáveis depois de alguns ciclos.";
  } else {
    const reducao = 1 - rb.esperaMedia / ra.esperaMedia;
    const forte = el("strong", { classe: reducao < 0 ? "pior" : "", texto: `${reducao >= 0 ? "−" : "+"}${numero(Math.abs(reducao) * 100)}%` });
    destaque.replaceChildren(forte, `no tempo médio de espera com o GSA (${segundos(ra.esperaMedia)} → ${segundos(rb.esperaMedia)}), após ${duracao(rb.t)} simulados`);
  }
  desenharGrafico(app.mundo.a.estat.serie, app.mundo.b.estat.serie);
}

function desenharGrafico(serieA, serieB) {
  const canvas = $("grafico-comparacao");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const largura = canvas.clientWidth;
  const altura = canvas.clientHeight;
  if (!largura) return;
  if (canvas.width !== Math.round(largura * dpr)) {
    canvas.width = Math.round(largura * dpr);
    canvas.height = Math.round(altura * dpr);
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, largura, altura);
  const pontos = [...serieA, ...serieB];
  const margem = { esq: 30, dir: 8, topo: 8, base: 18 };
  ctx.font = "10px system-ui, sans-serif";
  ctx.fillStyle = "#8a929b";
  if (pontos.length < 2) {
    ctx.fillText("A série aparece depois dos primeiros segundos simulados.", margem.esq, altura / 2);
    return;
  }
  const t0 = Math.min(...pontos.map((p) => p.t));
  const t1 = Math.max(...pontos.map((p) => p.t), t0 + 60);
  const teto = Math.max(10, ...pontos.map((p) => p.fila)) * 1.1;
  const x = (t) => margem.esq + ((t - t0) / (t1 - t0)) * (largura - margem.esq - margem.dir);
  const y = (v) => altura - margem.base - (v / teto) * (altura - margem.topo - margem.base);
  ctx.strokeStyle = "#262b31";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 3; i++) {
    const v = (teto / 3) * i;
    ctx.beginPath();
    ctx.moveTo(margem.esq, y(v));
    ctx.lineTo(largura - margem.dir, y(v));
    ctx.stroke();
    ctx.fillText(numero(v), 4, y(v) + 3);
  }
  ctx.fillText(duracao(t0), margem.esq, altura - 4);
  const fim = duracao(t1);
  ctx.fillText(fim, largura - margem.dir - ctx.measureText(fim).width, altura - 4);
  for (const [serie, cor] of [
    [serieA, "#c98500"],
    [serieB, "#3987e5"],
  ]) {
    if (serie.length < 2) continue;
    ctx.strokeStyle = cor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    serie.forEach((p, i) => (i ? ctx.lineTo(x(p.t), y(p.fila)) : ctx.moveTo(x(p.t), y(p.fila))));
    ctx.stroke();
  }
}

/* ---------- painel ---------- */

function atualizarPainel() {
  const m = app.mundo;
  if (!m) return;
  atualizarSeguranca();
  const rb = m.b.resumo();
  atualizarVias(rb);
  atualizarDemanda();
  atualizarIntegracao();
  if (m.a) atualizarComparacao(m.a.resumo(), rb);
  $("legenda-b").textContent = `${rb.noSistema} veíc. na aproximação · ${numero(rb.servidos)} atravessaram`;
  const agora = performance.now();
  if (agora - app.ultimoAria > 2000) {
    app.ultimoAria = agora;
    const ctrl = m.b.controlador;
    $("canvas-b").setAttribute(
      "aria-label",
      `Cruzamento B: ${ctrl.estagio.rotulo} em ${NOME_FASE[ctrl.fase]}, ${Math.ceil(ctrl.restanteDaFase())} s restantes; ` +
        `${rb.noSistema} veículos na aproximação; ${rb.porVia.reduce((t, v) => t + v.fila, 0)} em fila.`,
    );
  }
}

/* ---------- controles ---------- */

function atualizarBotaoIniciar() {
  const botao = $("btn-iniciar");
  const rodando = app.mundo?.rodando;
  botao.dataset.rodando = String(Boolean(rodando));
  botao.querySelector('[aria-hidden="true"]').textContent = rodando ? "⏸" : "▶";
  botao.querySelector(".rotulo").textContent = rodando ? "Pausar" : app.mundo?.t ? "Continuar" : "Iniciar";
}

function alternarExecucao() {
  const m = app.mundo;
  if (!m.rodando && !app.ponte.sessaoId && app.ponte.status !== "conectando") app.ponte.abrir(m);
  m.alternar();
  atualizarBotaoIniciar();
}

function definirVelocidade(velocidade) {
  if (!app.mundo.definirVelocidade(velocidade)) return;
  for (const botao of $("velocidades").children) {
    botao.setAttribute("aria-pressed", String(Number(botao.dataset.velocidade) === velocidade));
  }
}

function definirZoom(zoom) {
  app.opcoes.zoom = zoom;
  app.renderB.definirZoom(zoom);
  app.renderA.definirZoom(zoom);
  for (const botao of $("zooms").children) {
    botao.setAttribute("aria-pressed", String(Number(botao.dataset.zoom) === zoom));
  }
}

/** Troca o polígono das zonas: a câmera recomeça a janela de contagem com as zonas novas. */
function definirModoZona(modo) {
  app.opcoes.modoZona = modo;
  app.mundo.modoZona = modo;
  if (app.opcoes.zonas && modo === "entrada" && app.opcoes.zoom !== 1) definirZoom(1);
  if (app.ponte.sessaoId || app.ponte.status === "conectando") app.ponte.abrir(app.mundo);
}

function alternarOpcao(nome, valor) {
  app.opcoes[nome] = valor ?? !app.opcoes[nome];
  const ids = { caixas: "opt-caixas", zonas: "opt-zonas" };
  if (ids[nome]) $(ids[nome]).checked = app.opcoes[nome];
  // a faixa de entrada fica na borda do quadro: mostra o quadro inteiro da câmera
  if (nome === "zonas" && app.opcoes.zonas && app.opcoes.modoZona === "entrada" && app.opcoes.zoom !== 1) {
    definirZoom(1);
  }
}

async function alternarComparacao(ativo) {
  app.opcoes.comparar = ativo;
  $("opt-comparar").checked = ativo;
  if (ativo) {
    // os dois cruzamentos começam juntos, do zero, para receber as mesmas chegadas
    await criarMundo({ manterRodando: true });
  } else {
    app.mundo.a = null;
    $("telas").classList.remove("comparando");
    $("lateral").classList.remove("comparando");
    $("tela-a").hidden = true;
    $("cartao-comparacao").hidden = true;
  }
}

function ligarControles() {
  $("btn-iniciar").addEventListener("click", alternarExecucao);
  $("btn-reiniciar").addEventListener("click", () => criarMundo({ manterRodando: true }));
  for (const botao of $("velocidades").children) {
    botao.addEventListener("click", () => definirVelocidade(Number(botao.dataset.velocidade)));
  }
  for (const botao of $("zooms").children) {
    botao.addEventListener("click", () => definirZoom(Number(botao.dataset.zoom)));
  }
  $("sel-zona").addEventListener("change", (e) => definirModoZona(e.target.value));
  $("opt-caixas").addEventListener("change", (e) => alternarOpcao("caixas", e.target.checked));
  $("opt-zonas").addEventListener("change", (e) => alternarOpcao("zonas", e.target.checked));
  $("opt-comparar").addEventListener("change", (e) => alternarComparacao(e.target.checked));
  $("sel-base").addEventListener("change", (e) => {
    app.opcoes.base = e.target.value;
    if (app.opcoes.comparar) criarMundo({ manterRodando: true });
  });
  $("presets-hora").replaceChildren(
    ...PRESETS_HORA.map((preset) => {
      const botao = el("button", { type: "button", "data-preset": preset.id, "aria-pressed": "false", texto: `${preset.rotulo} · ${horaDoDia(preset.hora)}` });
      botao.addEventListener("click", () => {
        app.presetHora = preset.id;
        app.mundo.definirHora(preset.hora);
        atualizarDemanda();
      });
      return botao;
    }),
  );
  $("opt-relogio").addEventListener("change", (e) => {
    app.mundo.definirRelogio(e.target.checked);
    atualizarDemanda();
  });
  $("sel-congestionamento").addEventListener("change", (e) => {
    app.mundo.definirCongestionamento(e.target.value || null);
    atualizarDemanda();
  });
  $("sel-falha").addEventListener("change", (e) => {
    app.ponte.viasSemEnvio = e.target.value ? [Number(e.target.value)] : [];
    app.falhaDesde = e.target.value ? performance.now() : null;
    atualizarDemanda();
  });
  const aplicarSemente = () => {
    const valor = Math.max(1, Math.min(999999, Math.round(Number($("inp-semente").value)) || SEMENTE_PADRAO));
    $("inp-semente").value = valor;
    app.semente = valor;
    const url = new URL(location.href);
    url.searchParams.set("semente", valor);
    history.replaceState(null, "", url);
    criarMundo({ manterRodando: true });
  };
  $("btn-semente").addEventListener("click", aplicarSemente);
  $("inp-semente").addEventListener("keydown", (e) => e.key === "Enter" && aplicarSemente());
  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
    const tecla = e.key.toLowerCase();
    const acoes = {
      " ": alternarExecucao,
      r: () => criarMundo({ manterRodando: true }),
      1: () => definirVelocidade(1),
      2: () => definirVelocidade(2),
      5: () => definirVelocidade(5),
      0: () => definirVelocidade(10),
      b: () => alternarOpcao("caixas"),
      z: () => alternarOpcao("zonas"),
      c: () => alternarComparacao(!app.opcoes.comparar),
    };
    if (!acoes[tecla] || !app.mundo) return;
    if (tecla === " " && e.target.closest("button")) return; // o botão em foco já trata o espaço
    e.preventDefault();
    acoes[tecla]();
  });
  window.addEventListener("pagehide", () => app.ponte?.encerrar());
}

iniciar();
