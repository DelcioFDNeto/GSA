/* Desenho do cruzamento em Canvas 2D, visto de cima.

   O cenário fixo (gramado, calçadas, asfalto, sinalização horizontal, árvores) é desenhado uma
   vez em uma tela fora da página e copiado a cada quadro; os veículos usam imagens
   pré-desenhadas por classe e cor. Assim cada quadro custa poucas operações e a animação fica
   em 60 quadros por segundo sem placa de vídeo dedicada. */

import { criarRng, derivarSemente } from "./aleatorio.js";
import { AMARELO, VERDE, VERMELHO } from "./controlador.js";
import {
  AFASTAMENTO_PEDESTRES,
  CALCADA,
  LARGURA_PEDESTRES,
  RAIO_GRAMADO,
  faixasDePedestres,
  pontoDaFaixa,
} from "./geometria.js";

const COR = {
  grama: "#477a3b",
  calcada: "#b7b3a8",
  juntaCalcada: "rgba(70, 66, 58, 0.18)",
  meioFio: "#8e8a80",
  asfalto: "#2c3035",
  branca: "#e9e8e3",
  amarela: "#e2b52a",
  carcaca: "#14171a",
  lampadaApagada: "#262b31",
};
export const COR_SINAL = { [VERDE]: "#2fd16b", [AMARELO]: "#ffc21a", [VERMELHO]: "#ff4b4b" };
// Paleta do Ultralytics para os ids COCO de car (2), motorcycle (3), bus (5) e truck (7)
export const COR_CLASSE = { car: "#ff701f", motorcycle: "#ffb21d", bus: "#48f90a", truck: "#3ddb86" };
export const COR_ZONA = ["#3987e5", "#eb6834", "#1baf7a", "#eda100", "#a372e8", "#e05a9a"];
const MEIO_FIO = 0.25;

function comAlfa(hex, alfa) {
  const n = Number.parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
}

function misturar(hex, alvo, fracao) {
  const n = Number.parseInt(hex.slice(1), 16);
  const canal = (c) => Math.round(c + (alvo - c) * fracao);
  const r = canal((n >> 16) & 255);
  const g = canal((n >> 8) & 255);
  const b = canal(n & 255);
  return `rgb(${r}, ${g}, ${b})`;
}
const clarear = (hex, f) => misturar(hex, 255, f);
const escurecer = (hex, f) => misturar(hex, 0, f);

function caminhoArredondado(ctx, x, y, w, h, r) {
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(x, y, w, h, r);
    return;
  }
  const raio = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + raio, y);
  ctx.arcTo(x + w, y, x + w, y + h, raio);
  ctx.arcTo(x + w, y + h, x, y + h, raio);
  ctx.arcTo(x, y + h, x, y, raio);
  ctx.arcTo(x, y, x + w, y, raio);
  ctx.closePath();
}

function trapezio(ctx, xA, meiaA, xB, meiaB) {
  ctx.beginPath();
  ctx.moveTo(xA, -meiaA);
  ctx.lineTo(xA, meiaA);
  ctx.lineTo(xB, meiaB);
  ctx.lineTo(xB, -meiaB);
  ctx.closePath();
  ctx.fill();
}

/** Arredonda o canto côncavo (cx, cy) de uma cruz; (sx, sy) aponta para dentro do quarteirão. */
function filete(ctx, cx, cy, sx, sy, raio) {
  ctx.beginPath();
  ctx.moveTo(cx + sx * raio, cy);
  ctx.arcTo(cx, cy, cx, cy + sy * raio, raio);
  ctx.lineTo(cx, cy);
  ctx.closePath();
  ctx.fill();
}

function brilhoLateral(ctx, L, W, r) {
  const g = ctx.createLinearGradient(0, -W / 2, 0, W / 2);
  g.addColorStop(0, "rgba(0, 0, 0, 0.32)");
  g.addColorStop(0.16, "rgba(255, 255, 255, 0.06)");
  g.addColorStop(0.5, "rgba(255, 255, 255, 0.16)");
  g.addColorStop(0.84, "rgba(255, 255, 255, 0.04)");
  g.addColorStop(1, "rgba(0, 0, 0, 0.34)");
  ctx.fillStyle = g;
  caminhoArredondado(ctx, -L / 2, -W / 2, L, W, r);
  ctx.fill();
}

function vidro(ctx, x0, x1) {
  const g = ctx.createLinearGradient(x0, 0, x1, 0);
  g.addColorStop(0, "#0d1218");
  g.addColorStop(1, "#33475a");
  return g;
}

/* ---------- veículos (metros, frente apontando para +x, centro na origem) ---------- */

function desenharCarro(ctx, L, W, cor) {
  const r = 0.46;
  ctx.fillStyle = cor;
  caminhoArredondado(ctx, -L / 2, -W / 2, L, W, r);
  ctx.fill();
  brilhoLateral(ctx, L, W, r);
  ctx.lineWidth = 0.05;
  ctx.strokeStyle = "rgba(0, 0, 0, 0.5)";
  caminhoArredondado(ctx, -L / 2, -W / 2, L, W, r);
  ctx.stroke();
  // vincos do capô
  ctx.strokeStyle = "rgba(0, 0, 0, 0.18)";
  ctx.lineWidth = 0.04;
  ctx.beginPath();
  ctx.moveTo(L * 0.47, -W * 0.22);
  ctx.lineTo(L * 0.27, -W * 0.27);
  ctx.moveTo(L * 0.47, W * 0.22);
  ctx.lineTo(L * 0.27, W * 0.27);
  ctx.stroke();
  // para-brisa, teto, vidro traseiro e janelas laterais
  ctx.fillStyle = vidro(ctx, L * 0.07, L * 0.26);
  trapezio(ctx, L * 0.26, W * 0.42, L * 0.07, W * 0.36);
  ctx.fillStyle = clarear(cor, 0.1);
  caminhoArredondado(ctx, -L * 0.22, -W * 0.355, L * 0.29, W * 0.71, 0.2);
  ctx.fill();
  ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
  caminhoArredondado(ctx, -L * 0.18, -W * 0.2, L * 0.2, W * 0.4, 0.15);
  ctx.fill();
  ctx.fillStyle = vidro(ctx, -L * 0.34, -L * 0.22);
  trapezio(ctx, -L * 0.22, W * 0.355, -L * 0.34, W * 0.31);
  ctx.fillStyle = "rgba(16, 22, 30, 0.85)";
  ctx.fillRect(-L * 0.22, -W * 0.435, L * 0.29, W * 0.065);
  ctx.fillRect(-L * 0.22, W * 0.37, L * 0.29, W * 0.065);
  // retrovisores
  ctx.fillStyle = escurecer(cor, 0.35);
  for (const lado of [-1, 1]) {
    ctx.beginPath();
    ctx.ellipse(L * 0.2, lado * (W / 2 + 0.07), 0.13, 0.08, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  // faróis e lanternas
  ctx.fillStyle = "#f6f0cf";
  for (const lado of [-1, 1]) {
    caminhoArredondado(ctx, L / 2 - 0.17, lado > 0 ? W * 0.18 : -W * 0.4, 0.12, W * 0.22, 0.04);
    ctx.fill();
  }
  ctx.fillStyle = "#7d1616";
  for (const lado of [-1, 1]) {
    caminhoArredondado(ctx, -L / 2 + 0.04, lado > 0 ? W * 0.2 : -W * 0.42, 0.1, W * 0.22, 0.03);
    ctx.fill();
  }
}

function desenharMoto(ctx, L, W, cor, extra) {
  ctx.fillStyle = "#121314";
  caminhoArredondado(ctx, -L / 2, -0.1, 0.62, 0.2, 0.08);
  ctx.fill();
  caminhoArredondado(ctx, L / 2 - 0.55, -0.08, 0.55, 0.16, 0.07);
  ctx.fill();
  ctx.fillStyle = cor;
  ctx.beginPath();
  ctx.ellipse(L * 0.08, 0, L * 0.28, 0.2, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#1c1d20";
  caminhoArredondado(ctx, -L * 0.3, -0.15, L * 0.32, 0.3, 0.12);
  ctx.fill();
  ctx.strokeStyle = "#3a3d42";
  ctx.lineWidth = 0.07;
  ctx.beginPath();
  ctx.moveTo(L * 0.24, -0.38);
  ctx.lineTo(L * 0.24, 0.38);
  ctx.stroke();
  // piloto: ombros, braços e capacete
  const jaqueta = ["#2b2f36", "#3c4b63", "#5a3328", "#2f4a3a"][Math.floor(extra * 4) % 4];
  ctx.fillStyle = jaqueta;
  ctx.beginPath();
  ctx.ellipse(-L * 0.06, 0, 0.2, 0.33, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = jaqueta;
  ctx.lineWidth = 0.12;
  ctx.beginPath();
  ctx.moveTo(-L * 0.02, -0.28);
  ctx.lineTo(L * 0.22, -0.34);
  ctx.moveTo(-L * 0.02, 0.28);
  ctx.lineTo(L * 0.22, 0.34);
  ctx.stroke();
  const capacete = ["#f1f1ee", "#c8382b", "#1f2226", "#e2b33c"][Math.floor(extra * 7) % 4];
  ctx.fillStyle = capacete;
  ctx.beginPath();
  ctx.arc(L * 0.02, 0, 0.16, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
  ctx.beginPath();
  ctx.arc(L * 0.05, -0.05, 0.06, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#fff6c8";
  ctx.beginPath();
  ctx.arc(L / 2 - 0.06, 0, 0.06, 0, Math.PI * 2);
  ctx.fill();
}

function desenharOnibus(ctx, L, W, cor) {
  const r = 0.35;
  ctx.fillStyle = cor;
  caminhoArredondado(ctx, -L / 2, -W / 2, L, W, r);
  ctx.fill();
  brilhoLateral(ctx, L, W, r);
  ctx.strokeStyle = "rgba(0, 0, 0, 0.5)";
  ctx.lineWidth = 0.05;
  caminhoArredondado(ctx, -L / 2, -W / 2, L, W, r);
  ctx.stroke();
  ctx.fillStyle = clarear(cor, 0.12);
  caminhoArredondado(ctx, -L / 2 + 0.3, -W / 2 + 0.24, L - 0.65, W - 0.48, 0.18);
  ctx.fill();
  // ar-condicionado e escotilhas no teto
  ctx.fillStyle = "#d3d7db";
  caminhoArredondado(ctx, -1.5, -W * 0.3, 3.0, W * 0.6, 0.15);
  ctx.fill();
  ctx.strokeStyle = "rgba(0, 0, 0, 0.18)";
  ctx.lineWidth = 0.04;
  ctx.beginPath();
  for (let x = -1.25; x <= 1.3; x += 0.32) {
    ctx.moveTo(x, -W * 0.24);
    ctx.lineTo(x, W * 0.24);
  }
  ctx.stroke();
  ctx.fillStyle = "#b8bdc2";
  for (const x of [-L * 0.33, L * 0.24]) {
    caminhoArredondado(ctx, x - 0.4, -0.4, 0.8, 0.8, 0.08);
    ctx.fill();
  }
  // vidros: para-brisa, traseiro e janelas laterais
  ctx.fillStyle = vidro(ctx, L / 2 - 0.45, L / 2);
  caminhoArredondado(ctx, L / 2 - 0.42, -W * 0.45, 0.34, W * 0.9, 0.12);
  ctx.fill();
  ctx.fillStyle = "#151a20";
  ctx.fillRect(-L / 2 + 0.06, -W * 0.38, 0.22, W * 0.76);
  ctx.fillStyle = "rgba(16, 22, 30, 0.8)";
  ctx.fillRect(-L * 0.44, -W / 2 + 0.02, L * 0.84, 0.12);
  ctx.fillRect(-L * 0.44, W / 2 - 0.14, L * 0.84, 0.12);
  ctx.fillStyle = "#16181b";
  for (const lado of [-1, 1]) ctx.fillRect(L / 2 - 0.5, lado * (W / 2 + 0.05) - 0.06, 0.18, 0.12);
}

function desenharCaminhao(ctx, L, W, cor, extra) {
  const carga = ["#e8e8e4", "#c9ccd0", "#a9b0b6", "#b59f74"][Math.floor(extra * 4) % 4];
  const cabine = 2.1;
  // baú com nervuras
  ctx.fillStyle = carga;
  caminhoArredondado(ctx, -L / 2, -W / 2, L - cabine - 0.25, W, 0.12);
  ctx.fill();
  brilhoLateral(ctx, L, W, 0.12);
  ctx.strokeStyle = "rgba(0, 0, 0, 0.14)";
  ctx.lineWidth = 0.05;
  ctx.beginPath();
  for (let x = -L / 2 + 0.55; x < L / 2 - cabine - 0.4; x += 0.6) {
    ctx.moveTo(x, -W / 2 + 0.08);
    ctx.lineTo(x, W / 2 - 0.08);
  }
  ctx.stroke();
  ctx.strokeStyle = "rgba(0, 0, 0, 0.45)";
  caminhoArredondado(ctx, -L / 2, -W / 2, L - cabine - 0.25, W, 0.12);
  ctx.stroke();
  // engate e cabine
  ctx.fillStyle = "#1b1c1e";
  ctx.fillRect(L / 2 - cabine - 0.3, -W * 0.3, 0.35, W * 0.6);
  ctx.fillStyle = cor;
  caminhoArredondado(ctx, L / 2 - cabine, -W / 2 + 0.05, cabine, W - 0.1, 0.32);
  ctx.fill();
  ctx.fillStyle = clarear(cor, 0.15);
  caminhoArredondado(ctx, L / 2 - cabine + 0.15, -W * 0.36, cabine * 0.55, W * 0.72, 0.2);
  ctx.fill();
  ctx.fillStyle = vidro(ctx, L / 2 - 0.55, L / 2);
  caminhoArredondado(ctx, L / 2 - 0.5, -W * 0.42, 0.36, W * 0.84, 0.1);
  ctx.fill();
  ctx.fillStyle = "#16181b";
  for (const lado of [-1, 1]) ctx.fillRect(L / 2 - 0.65, lado * (W / 2 + 0.03) - 0.07, 0.16, 0.14);
}

const DESENHOS = {
  carro: desenharCarro,
  moto: desenharMoto,
  onibus: desenharOnibus,
  caminhao: desenharCaminhao,
};

/* ---------- renderizador ---------- */

export class Renderizador {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.geo = null;
    this.semente = 1;
    this.fundo = null;
    this.sprites = new Map();
    this.luzFreio = null;
    this.dpr = 1;
    this.lado = 0;
    this.zoom = 1; // só do desenho: a câmera sintética sempre vê o quadro inteiro
  }

  /** Aproxima o desenho do centro do cruzamento (1 = quadro inteiro da câmera). */
  definirZoom(zoom) {
    if (zoom === this.zoom) return;
    this.zoom = zoom;
    this.fundo = null;
    this.sprites.clear();
    this.luzFreio = null;
  }

  /** Metade do lado da área desenhada, em metros. */
  get meioVisivel() {
    return this.geo.meio / this.zoom;
  }

  definirGeometria(geometria, semente) {
    this.geo = geometria;
    this.semente = semente;
    this.fundo = null;
    this.sprites.clear();
    this.luzFreio = null;
  }

  /** Ajusta a resolução ao tamanho exibido (chamado ao redimensionar). */
  ajustarTamanho(ladoCss, dpr = globalThis.devicePixelRatio || 1) {
    const razao = Math.min(Math.max(dpr, 1), 2);
    const lado = Math.max(160, Math.floor(ladoCss));
    if (lado === this.lado && razao === this.dpr) return;
    this.lado = lado;
    this.dpr = razao;
    this.canvas.width = Math.round(lado * razao);
    this.canvas.height = Math.round(lado * razao);
    this.fundo = null;
    this.sprites.clear();
    this.luzFreio = null;
  }

  get pixelsPorMetro() {
    return this.canvas.width / (2 * this.meioVisivel);
  }

  /** Coordenadas do mundo (m) para pixels do canvas. */
  paraTela(x, y) {
    const k = this.pixelsPorMetro;
    const m = this.meioVisivel;
    return [(x + m) * k, (y + m) * k];
  }

  emMetros(ctx) {
    const k = this.pixelsPorMetro;
    const m = this.meioVisivel;
    ctx.setTransform(k, 0, 0, k, m * k, m * k);
  }

  /* ---------- cenário fixo ---------- */

  cruz(ctx, expansao, raio, cor) {
    const { ns, lo, meio } = this.geo;
    const L = meio + 4;
    ctx.fillStyle = cor;
    if (ns.existe) ctx.fillRect(ns.min - expansao, -L, ns.max - ns.min + 2 * expansao, 2 * L);
    if (lo.existe) ctx.fillRect(-L, lo.min - expansao, 2 * L, lo.max - lo.min + 2 * expansao);
    if (ns.existe && lo.existe && raio > 0) {
      filete(ctx, ns.max + expansao, lo.min - expansao, 1, -1, raio);
      filete(ctx, ns.max + expansao, lo.max + expansao, 1, 1, raio);
      filete(ctx, ns.min - expansao, lo.max + expansao, -1, 1, raio);
      filete(ctx, ns.min - expansao, lo.min - expansao, -1, -1, raio);
    }
  }

  dentroDaCalcada(x, y, folga) {
    const { ns, lo } = this.geo;
    const naVertical = ns.existe && x > ns.min - CALCADA - folga && x < ns.max + CALCADA + folga;
    const naHorizontal = lo.existe && y > lo.min - CALCADA - folga && y < lo.max + CALCADA + folga;
    return naVertical || naHorizontal;
  }

  gerarFundo() {
    const geo = this.geo;
    const tela = document.createElement("canvas");
    tela.width = this.canvas.width;
    tela.height = this.canvas.height;
    const ctx = tela.getContext("2d");
    this.emMetros(ctx);
    const rng = criarRng(derivarSemente(this.semente, "cenario"));
    const L = geo.meio + 4;
    const px = 1 / this.pixelsPorMetro;

    // gramado com textura
    ctx.fillStyle = COR.grama;
    ctx.fillRect(-L, -L, 2 * L, 2 * L);
    for (let i = 0; i < 9000; i++) {
      const claro = rng() < 0.5;
      ctx.fillStyle = claro ? `rgba(120, 170, 90, ${0.05 + rng() * 0.08})` : `rgba(20, 50, 20, ${0.05 + rng() * 0.1})`;
      const r = 0.15 + rng() * 0.6;
      ctx.fillRect(-L + rng() * 2 * L, -L + rng() * 2 * L, r, r * (0.6 + rng()));
    }

    // calçada (com juntas), meio-fio e asfalto, com esquinas arredondadas concêntricas
    const raioMeioFio = RAIO_GRAMADO + CALCADA;
    this.cruz(ctx, CALCADA, RAIO_GRAMADO, COR.calcada);
    ctx.strokeStyle = COR.juntaCalcada;
    ctx.lineWidth = Math.max(0.04, px);
    ctx.beginPath();
    for (let t = -L; t < L; t += 1.6) {
      if (geo.ns.existe) {
        ctx.moveTo(geo.ns.min - CALCADA, t);
        ctx.lineTo(geo.ns.min, t);
        ctx.moveTo(geo.ns.max, t);
        ctx.lineTo(geo.ns.max + CALCADA, t);
      }
      if (geo.lo.existe) {
        ctx.moveTo(t, geo.lo.min - CALCADA);
        ctx.lineTo(t, geo.lo.min);
        ctx.moveTo(t, geo.lo.max);
        ctx.lineTo(t, geo.lo.max + CALCADA);
      }
    }
    ctx.stroke();
    this.cruz(ctx, MEIO_FIO, raioMeioFio - MEIO_FIO, COR.meioFio);
    this.cruz(ctx, 0, raioMeioFio, COR.asfalto);

    // textura do asfalto e marcas de pneu
    for (let i = 0; i < 7000; i++) {
      const x = -L + rng() * 2 * L;
      const y = -L + rng() * 2 * L;
      const naPista =
        (geo.ns.existe && x > geo.ns.min && x < geo.ns.max) ||
        (geo.lo.existe && y > geo.lo.min && y < geo.lo.max);
      if (!naPista) continue;
      ctx.fillStyle = rng() < 0.5 ? `rgba(255, 255, 255, ${0.025 + rng() * 0.04})` : `rgba(0, 0, 0, ${0.05 + rng() * 0.08})`;
      const r = 0.06 + rng() * 0.14;
      ctx.fillRect(x, y, r, r);
    }
    for (const f of geo.faixas) {
      for (const lado of [-0.82, 0.82]) {
        const lateral = f.lateral + lado;
        const r = this.retanguloNaFaixa(f, f.sQuadroInicio - 6, f.sQuadroFim + 6, lateral - 0.28, lateral + 0.28);
        ctx.fillStyle = "rgba(0, 0, 0, 0.07)";
        ctx.fillRect(r.x, r.y, r.largura, r.altura);
      }
      const mancha = this.retanguloNaFaixa(f, f.sParada - 22, f.sParada - 1, f.lateral - 0.55, f.lateral + 0.55);
      ctx.fillStyle = "rgba(0, 0, 0, 0.1)";
      ctx.fillRect(mancha.x, mancha.y, mancha.largura, mancha.altura);
    }

    this.desenharCanteiros(ctx, rng);
    this.desenharArvores(ctx, rng);
    this.desenharSinalizacao(ctx, px);
    this.fundo = tela;
  }

  retanguloNaFaixa(f, s0, s1, lateral0, lateral1) {
    const a = pontoDaFaixa(f, s0);
    const b = pontoDaFaixa(f, s1);
    if (f.eixo === "ns") {
      return { x: Math.min(lateral0, lateral1), y: Math.min(a.y, b.y), largura: Math.abs(lateral1 - lateral0), altura: Math.abs(a.y - b.y) };
    }
    return { x: Math.min(a.x, b.x), y: Math.min(lateral0, lateral1), largura: Math.abs(a.x - b.x), altura: Math.abs(lateral1 - lateral0) };
  }

  /** Pernas do cruzamento: trechos da avenida fora dele, depois das faixas de pedestres. */
  pernas(eixo) {
    const { caixa, meio } = this.geo;
    const recuo = AFASTAMENTO_PEDESTRES + LARGURA_PEDESTRES + 0.6;
    const fim = meio + 4;
    if (eixo === "ns") {
      return [
        { de: -fim, ate: caixa.y0 - recuo, ponta: "fim" },
        { de: caixa.y1 + recuo, ate: fim, ponta: "inicio" },
      ];
    }
    return [
      { de: -fim, ate: caixa.x0 - recuo, ponta: "fim" },
      { de: caixa.x1 + recuo, ate: fim, ponta: "inicio" },
    ];
  }

  desenharCanteiros(ctx, rng) {
    for (const nome of ["ns", "lo"]) {
      const eixo = this.geo[nome];
      if (eixo.tipoCanteiro !== "ajardinado") continue;
      const meia = eixo.canteiro / 2;
      for (const perna of this.pernas(nome)) {
        const comprimento = perna.ate - perna.de;
        const ret = nome === "ns" ? [-meia, perna.de, 2 * meia, comprimento] : [perna.de, -meia, comprimento, 2 * meia];
        ctx.fillStyle = "#a29e94";
        caminhoArredondado(ctx, ...ret, meia);
        ctx.fill();
        const interno = nome === "ns" ? [-meia + 0.25, perna.de + 0.25, 2 * meia - 0.5, comprimento - 0.5] : [perna.de + 0.25, -meia + 0.25, comprimento - 0.5, 2 * meia - 0.5];
        ctx.fillStyle = "#4f8a43";
        caminhoArredondado(ctx, ...interno, meia - 0.25);
        ctx.fill();
        for (let t = perna.de + 4; t < perna.ate - 3; t += 7 + rng() * 4) {
          const [x, y] = nome === "ns" ? [0, t] : [t, 0];
          ctx.fillStyle = "rgba(0, 0, 0, 0.22)";
          ctx.beginPath();
          ctx.arc(x + 0.25, y + 0.3, meia * 0.7, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = rng() < 0.5 ? "#3f7a37" : "#5b9a4a";
          ctx.beginPath();
          ctx.arc(x, y, meia * 0.65, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  }

  desenharArvores(ctx, rng) {
    const L = this.geo.meio + 3;
    const arvores = [];
    for (let tentativa = 0; tentativa < 900 && arvores.length < 70; tentativa++) {
      const r = 1.6 + rng() * 2.4;
      const x = -L + rng() * 2 * L;
      const y = -L + rng() * 2 * L;
      if (this.dentroDaCalcada(x, y, r + 0.8)) continue;
      if (arvores.some((a) => Math.hypot(a.x - x, a.y - y) < a.r + r + 0.6)) continue;
      arvores.push({ x, y, r });
    }
    for (const a of arvores) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.26)";
      ctx.beginPath();
      ctx.ellipse(a.x + a.r * 0.35, a.y + a.r * 0.42, a.r, a.r * 0.92, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const a of arvores) {
      const g = ctx.createRadialGradient(a.x - a.r * 0.35, a.y - a.r * 0.35, a.r * 0.1, a.x, a.y, a.r);
      const tom = rng();
      g.addColorStop(0, tom < 0.5 ? "#7cbc5c" : "#6aae58");
      g.addColorStop(0.65, tom < 0.5 ? "#3f7d36" : "#367436");
      g.addColorStop(1, "#244f22");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
      ctx.fill();
      for (let i = 0; i < 4; i++) {
        const ang = rng() * Math.PI * 2;
        ctx.fillStyle = `rgba(20, 60, 20, ${0.12 + rng() * 0.12})`;
        ctx.beginPath();
        ctx.arc(a.x + Math.cos(ang) * a.r * 0.45, a.y + Math.sin(ang) * a.r * 0.45, a.r * (0.3 + rng() * 0.2), 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }

  desenharSinalizacao(ctx, px) {
    const geo = this.geo;
    const largura = Math.max(0.13, px * 1.2);
    ctx.fillStyle = COR.branca;
    // divisórias entre faixas do mesmo sentido: tracejadas, contínuas perto da retenção
    for (const sentido of ["norte", "sul", "leste", "oeste"]) {
      const faixas = geo.faixas.filter((f) => f.sentido === sentido).sort((a, b) => a.lateral - b.lateral);
      for (let i = 1; i < faixas.length; i++) {
        const f = faixas[i];
        const lateral = (faixas[i - 1].lateral + f.lateral) / 2;
        const trecho = (s0, s1) => {
          const r = this.retanguloNaFaixa(f, s0, s1, lateral - largura / 2, lateral + largura / 2);
          ctx.fillRect(r.x, r.y, r.largura, r.altura);
        };
        for (let s = f.sQuadroInicio - 8; s < f.sParada - 18; s += 8) trecho(s, Math.min(s + 3, f.sParada - 18));
        trecho(f.sParada - 18, f.sParada);
        const inicioSaida = f.sSaida + AFASTAMENTO_PEDESTRES + LARGURA_PEDESTRES + 0.8;
        for (let s = inicioSaida; s < f.sQuadroFim + 8; s += 8) trecho(s, s + 3);
      }
    }
    // linha dupla amarela nas vias de mão dupla sem canteiro ajardinado
    ctx.fillStyle = COR.amarela;
    for (const nome of ["ns", "lo"]) {
      const eixo = geo[nome];
      if (eixo.tipoCanteiro !== "pintado") continue;
      for (const perna of this.pernas(nome)) {
        for (const lado of [-0.19, 0.07]) {
          if (nome === "ns") ctx.fillRect(lado, perna.de, 0.12, perna.ate - perna.de);
          else ctx.fillRect(perna.de, lado, perna.ate - perna.de, 0.12);
        }
      }
    }
    // faixas de pedestres (zebradas)
    ctx.fillStyle = COR.branca;
    for (const fp of faixasDePedestres(geo)) {
      if (fp.listras === "verticais") {
        for (let x = fp.x + 0.3; x < fp.x + fp.largura - 0.3; x += 1.0) ctx.fillRect(x, fp.y, 0.5, fp.altura);
      } else {
        for (let y = fp.y + 0.3; y < fp.y + fp.altura - 0.3; y += 1.0) ctx.fillRect(fp.x, y, fp.largura, 0.5);
      }
    }
    // linhas de retenção (base branca; a cor do sinal é pintada por cima a cada quadro)
    for (const via of geo.vias) {
      const r = via.retencao;
      ctx.fillRect(r.x, r.y, r.largura, r.altura);
    }
    // setas de "siga em frente" em cada faixa de aproximação
    for (const f of geo.faixas) {
      const p = pontoDaFaixa(f, f.sParada - 9);
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(f.angulo);
      ctx.beginPath();
      ctx.moveTo(-2.6, -0.13);
      ctx.lineTo(0.2, -0.13);
      ctx.lineTo(0.2, -0.5);
      ctx.lineTo(1.5, 0);
      ctx.lineTo(0.2, 0.5);
      ctx.lineTo(0.2, 0.13);
      ctx.lineTo(-2.6, 0.13);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
  }

  /* ---------- veículos ---------- */

  sprite(v) {
    const chave = `${v.tipo}|${v.cor}|${Math.floor(v.corSecundaria * 8)}`;
    let sprite = this.sprites.get(chave);
    if (sprite) return sprite;
    const k = this.pixelsPorMetro;
    const margem = 0.5;
    const tela = document.createElement("canvas");
    tela.width = Math.ceil((v.L + 2 * margem) * k);
    tela.height = Math.ceil((v.W + 2 * margem) * k);
    const ctx = tela.getContext("2d");
    ctx.setTransform(k, 0, 0, k, tela.width / 2, tela.height / 2);
    DESENHOS[v.tipo](ctx, v.L, v.W, v.cor, v.corSecundaria);
    sprite = { tela, cx: tela.width / 2, cy: tela.height / 2 };
    this.sprites.set(chave, sprite);
    return sprite;
  }

  spriteLuzFreio() {
    if (this.luzFreio) return this.luzFreio;
    const k = this.pixelsPorMetro;
    const tela = document.createElement("canvas");
    const tamanho = Math.max(4, Math.ceil(1.1 * k));
    tela.width = tela.height = tamanho;
    const ctx = tela.getContext("2d");
    const g = ctx.createRadialGradient(tamanho / 2, tamanho / 2, 0, tamanho / 2, tamanho / 2, tamanho / 2);
    g.addColorStop(0, "rgba(255, 70, 60, 0.95)");
    g.addColorStop(0.35, "rgba(255, 40, 30, 0.55)");
    g.addColorStop(1, "rgba(255, 0, 0, 0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, tamanho, tamanho);
    this.luzFreio = tela;
    return tela;
  }

  desenharVeiculos(ctx, sim, alpha) {
    const meio = this.meioVisivel;
    const k = this.pixelsPorMetro;
    const visiveis = [];
    for (const f of sim.faixas) {
      for (const v of f.veiculos) {
        const s = v.sAnterior + (v.s - v.sAnterior) * alpha;
        const c = s - v.L / 2;
        const x = f.origem.x + f.dx * c;
        const y = f.origem.y + f.dy * c;
        if (Math.abs(x) > meio + 8 || Math.abs(y) > meio + 8) continue;
        visiveis.push({ v, f, x, y });
      }
    }
    this.emMetros(ctx);
    ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
    for (const { v, f, x, y } of visiveis) {
      const [w, h] = f.eixo === "ns" ? [v.W, v.L] : [v.L, v.W];
      caminhoArredondado(ctx, x - w / 2 + 0.3, y - h / 2 + 0.4, w, h, 0.4);
      ctx.fill();
    }
    const luz = this.spriteLuzFreio();
    for (const { v, f, x, y } of visiveis) {
      const sprite = this.sprite(v);
      const px = (x + meio) * k;
      const py = (y + meio) * k;
      ctx.setTransform(f.dx, f.dy, -f.dy, f.dx, px, py);
      ctx.drawImage(sprite.tela, -sprite.cx, -sprite.cy);
      const freando = v.acel < -0.6 || (v.v < 0.3 && !v.cruzou);
      if (freando && v.tipo !== "moto") {
        const traseira = -(v.L / 2) * k;
        const lateral = v.W * 0.32 * k;
        const meiaLuz = luz.width / 2;
        ctx.drawImage(luz, traseira - meiaLuz, -lateral - meiaLuz);
        ctx.drawImage(luz, traseira - meiaLuz, lateral - meiaLuz);
      }
    }
  }

  /* ---------- sinais, zonas, caixas e textos ---------- */

  desenharRetencoes(ctx, sim) {
    this.emMetros(ctx);
    for (const via of this.geo.vias) {
      const cor = COR_SINAL[sim.estados.get(via.id)] || COR_SINAL[VERMELHO];
      const r = via.retencao;
      ctx.shadowColor = cor;
      ctx.shadowBlur = 10 * this.dpr;
      ctx.fillStyle = cor;
      ctx.fillRect(r.x, r.y, r.largura, r.altura);
    }
    ctx.shadowBlur = 0;
  }

  desenharSemaforos(ctx, sim, mostrarTempo) {
    const ctrl = sim.controlador;
    const k = this.pixelsPorMetro;
    for (const via of this.geo.vias) {
      const estado = sim.estados.get(via.id) || VERMELHO;
      const { x, y, angulo } = via.semaforo;
      this.emMetros(ctx);
      ctx.translate(x, y);
      ctx.rotate(angulo);
      ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
      caminhoArredondado(ctx, -2.05, -0.62, 4.4, 1.6, 0.55);
      ctx.fill();
      ctx.fillStyle = COR.carcaca;
      caminhoArredondado(ctx, -2.25, -0.82, 4.5, 1.64, 0.58);
      ctx.fill();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.18)";
      ctx.lineWidth = 0.06;
      ctx.stroke();
      // vermelho mais perto do cruzamento, verde mais atrás
      const lampadas = [
        [VERMELHO, 1.42],
        [AMARELO, 0],
        [VERDE, -1.42],
      ];
      for (const [cor, posicao] of lampadas) {
        const acesa = estado === cor;
        ctx.beginPath();
        ctx.arc(posicao, 0, 0.56, 0, Math.PI * 2);
        if (acesa) {
          ctx.shadowColor = COR_SINAL[cor];
          ctx.shadowBlur = 14 * this.dpr;
          ctx.fillStyle = COR_SINAL[cor];
        } else {
          ctx.shadowBlur = 0;
          ctx.fillStyle = COR.lampadaApagada;
        }
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      if (!mostrarTempo) continue;
      const restante = estado === VERMELHO ? ctrl.segundosAteVerde(via.id) : ctrl.restanteDaFase();
      if (restante == null) continue;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      // à direita do motorista, para fora da pista: (−sen, cos) do ângulo de deslocamento
      const [px, py] = this.paraTela(x, y);
      const fora = 2.6 * k;
      const dx = -Math.sin(angulo) * fora;
      const dy = Math.cos(angulo) * fora;
      this.rotulo(ctx, String(Math.ceil(restante)), px + dx, py + dy, COR_SINAL[estado], true);
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
  }

  rotulo(ctx, texto, x, y, cor, centralizado = false) {
    const d = this.dpr;
    ctx.font = `700 ${11 * d}px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`;
    const w = ctx.measureText(texto).width + 8 * d;
    const h = 16 * d;
    // sempre inteiro dentro do canvas
    const x0 = Math.min(Math.max(centralizado ? x - w / 2 : x, 2 * d), this.canvas.width - w - 2 * d);
    const y0 = Math.min(Math.max(centralizado ? y - h / 2 : y, 2 * d), this.canvas.height - h - 2 * d);
    ctx.fillStyle = "rgba(10, 12, 14, 0.78)";
    caminhoArredondado(ctx, x0, y0, w, h, 4 * d);
    ctx.fill();
    ctx.fillStyle = cor;
    ctx.textBaseline = "middle";
    ctx.fillText(texto, x0 + 4 * d, y0 + h / 2 + 0.5 * d);
  }

  desenharZonas(ctx, opcoes) {
    this.emMetros(ctx);
    const px = 1 / this.pixelsPorMetro;
    this.geo.vias.forEach((via, i) => {
      const falha = opcoes.viasSemEnvio?.includes(via.id);
      const cor = falha ? "#ff4b4b" : COR_ZONA[i % COR_ZONA.length];
      ctx.beginPath();
      via.zonas[opcoes.modo || "aproximacao"].mundo.forEach(([x, y], j) => (j ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
      ctx.closePath();
      ctx.fillStyle = comAlfa(cor, 0.17);
      ctx.fill();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2 * this.dpr * px;
      ctx.setLineDash([6 * this.dpr * px, 4 * this.dpr * px]);
      ctx.stroke();
      ctx.setLineDash([]);
    });
  }

  desenharRotulosZonas(ctx, opcoes) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const parcial = opcoes.parcial || {};
    this.geo.vias.forEach((via, i) => {
      const falha = opcoes.viasSemEnvio?.includes(via.id);
      const cor = falha ? "#ff8a80" : COR_ZONA[i % COR_ZONA.length];
      const poligono = via.zonas[opcoes.modo || "aproximacao"].mundo;
      const xs = poligono.map(([x]) => x);
      const ys = poligono.map(([, y]) => y);
      // rótulo na ponta da zona junto à borda do quadro
      const borda = { norte: [0.5, 1], sul: [0.5, 0], leste: [0, 0.5], oeste: [1, 0.5] }[via.sentido];
      const x = Math.min(...xs) + (Math.max(...xs) - Math.min(...xs)) * borda[0];
      const y = Math.min(...ys) + (Math.max(...ys) - Math.min(...ys)) * borda[1];
      const [px, py] = this.paraTela(x, y);
      const contagem = parcial[String(via.id)];
      const texto = `${via.nomeCurto} ${via.seta}: ${contagem ?? "—"} veíc.${falha ? " · SEM ENVIO" : ""}`;
      const d = this.dpr;
      // na borda do quadro; nas ruas transversais, para fora da pista
      const deslocamento = { norte: [0, -20 * d], sul: [0, 20 * d], leste: [0, 22 * d], oeste: [0, -22 * d] }[via.sentido];
      this.rotulo(ctx, texto, px + deslocamento[0], py + deslocamento[1], cor, true);
    });
  }

  /** Caixas no estilo do Ultralytics. Em filas densas, um rótulo que cobriria outro já
      desenhado é omitido (a caixa continua): os veículos seguem visíveis. */
  desenharCaixas(ctx, caixas) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const d = this.dpr;
    const pequeno = this.lado < 460;
    ctx.lineWidth = 1.5 * d;
    ctx.font = `600 ${(pequeno ? 8.5 : 9.5) * d}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
    ctx.textBaseline = "alphabetic";
    const ocupados = [];
    const h = (pequeno ? 10 : 12) * d;
    for (const c of caixas) {
      const [x0, y0] = this.paraTela(c.x0, c.y0);
      const [x1, y1] = this.paraTela(c.x1, c.y1);
      const cor = COR_CLASSE[c.classe] || "#ffffff";
      ctx.strokeStyle = cor;
      ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
      const texto = pequeno ? `${c.id} ${c.classe}` : `id:${c.id} ${c.classe} ${c.confianca.toFixed(2)}`;
      const w = ctx.measureText(texto).width + 5 * d;
      const ty = y0 - h >= 0 ? y0 - h : y0;
      const rotulo = { x0: x0 - 0.8 * d, y0: ty, x1: x0 - 0.8 * d + w, y1: ty + h };
      if (ocupados.some((o) => rotulo.x0 < o.x1 && o.x0 < rotulo.x1 && rotulo.y0 < o.y1 && o.y0 < rotulo.y1)) {
        continue;
      }
      ocupados.push(rotulo);
      ctx.fillStyle = cor;
      ctx.fillRect(rotulo.x0, rotulo.y0, w, h);
      ctx.fillStyle = "#101214";
      ctx.fillText(texto, x0 + 1.8 * d, ty + h - 2.6 * d);
    }
  }

  desenharHud(ctx, hud) {
    if (!hud) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const d = this.dpr;
    const margem = 10 * d;
    if (hud.superiorEsquerdo) this.rotulo(ctx, hud.superiorEsquerdo, margem, margem, "#e8eaed");
    if (hud.superiorDireito) {
      ctx.font = `700 ${11 * d}px system-ui, sans-serif`;
      const w = ctx.measureText(hud.superiorDireito).width + 8 * d;
      this.rotulo(ctx, hud.superiorDireito, this.canvas.width - margem - w, margem, "#e8eaed");
    }
    if (hud.inferior) this.rotulo(ctx, hud.inferior, margem, this.canvas.height - margem - 16 * d, hud.corInferior || "#e8eaed");
    if (hud.alerta) this.rotulo(ctx, hud.alerta, this.canvas.width / 2, this.canvas.height / 2, "#ff8a80", true);
  }

  /** Um quadro completo. `opcoes`: caixas, zonas, parcial, viasSemEnvio, tempos, hud. */
  desenhar(sim, { alpha = 0, caixas = null, zonas = false, modoZona = "aproximacao", parcial = null, viasSemEnvio = [], tempos = true, hud = null } = {}) {
    if (!this.geo || !this.canvas.width) return;
    if (!this.fundo) this.gerarFundo();
    const ctx = this.ctx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.drawImage(this.fundo, 0, 0);
    this.desenharRetencoes(ctx, sim);
    if (zonas) this.desenharZonas(ctx, { viasSemEnvio, modo: modoZona });
    this.desenharVeiculos(ctx, sim, alpha);
    this.desenharSemaforos(ctx, sim, tempos);
    if (caixas) this.desenharCaixas(ctx, caixas);
    if (zonas) this.desenharRotulosZonas(ctx, { parcial, viasSemEnvio, modo: modoZona });
    this.desenharHud(ctx, hud);
  }
}

