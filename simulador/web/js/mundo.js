/* Mundo simulado: relógio, velocidade, demanda e os cruzamentos (B adaptativo e, no modo
   comparativo, A de tempo fixo), alimentados pelo MESMO gerador de chegadas.

   O tempo avança em passos fixos de tempo simulado; acelerar (2×, 5×, 10×) só executa mais
   passos por segundo real. Física, chegadas, semáforos e janelas de contagem usam todos esse
   mesmo relógio, então a contagem de uma janela de 90 s simulados representa 90 s em qualquer
   velocidade. Este módulo não usa o DOM: os controles da interface chamam os métodos daqui. */

import { derivarSemente } from "./aleatorio.js";
import { CameraSintetica, INTERVALO_CAMERA } from "./camera.js";
import { GeradorChegadas } from "./chegadas.js";
import { SimulacaoCruzamento } from "./cruzamento.js";
import { MODO_ZONA_PADRAO, eixosDasVias, montarGeometria } from "./geometria.js";

export const PASSO = 0.05; // s simulados por passo
export const VELOCIDADES = [1, 2, 5, 10];
export const MAX_PASSOS_POR_QUADRO = 50;
export const FATOR_CONGESTIONAMENTO = 1.5;
export const FATOR_MAXIMO = 3;
export const MAX_QUADROS_PENDENTES = 1200;
export const PRESETS_HORA = [
  { id: "madrugada", rotulo: "Madrugada", hora: 3 },
  { id: "manha", rotulo: "Pico da manhã", hora: 8 },
  { id: "meio-dia", rotulo: "Meio-dia", hora: 12.5 },
  { id: "tarde", rotulo: "Pico da tarde", hora: 18 },
  { id: "noite", rotulo: "Noite", hora: 21 },
];

export const HORARIO_MEDIA = [6, 22]; // período da média do dia (como a simulação comparativa)

export function demandaPadrao(viaIds) {
  return {
    horaInicial: 7,
    relogio: false,
    fatores: new Map(viaIds.map((id) => [id, 1])),
    congestionamento: null, // { eixo: "ns" | "lo", fator }
  };
}

export class Mundo {
  constructor({ configuracao, semente = 2026, planoA = null, demanda = null }) {
    this.config = configuracao;
    this.semente = semente;
    const ativas = configuracao.vias.filter((v) => v.ativa !== false);
    this.geometria = montarGeometria(ativas);
    this.eixos = eixosDasVias(this.geometria);
    this.limites = new Map(ativas.filter((v) => v.semaforo).map((v) => [v.id, v.semaforo]));
    const viaIds = this.geometria.vias.map((v) => v.id);
    this.demanda = demanda || demandaPadrao(viaIds);
    for (const id of viaIds) if (!this.demanda.fatores.has(id)) this.demanda.fatores.set(id, 1);
    this.perfil = configuracao.perfilDemanda;
    this.gerador = new GeradorChegadas({ viaIds, semente });
    const comum = { geometria: this.geometria, eixos: this.eixos, limites: this.limites };
    this.b = new SimulacaoCruzamento({ ...comum, plano: configuracao.planoFixo, rotulo: "B" });
    this.a = planoA ? new SimulacaoCruzamento({ ...comum, plano: planoA, rotulo: "A" }) : null;
    const camera = (rotulo) =>
      new CameraSintetica({
        geometria: this.geometria,
        semente: derivarSemente(semente, rotulo),
        confiancaMinima: configuracao.confiancaMinima ?? 0.3,
        classes: configuracao.classes,
      });
    // só o cruzamento B tem câmera: é ela que alimenta o GSA (o A roda o plano fixo sozinho)
    this.cameraB = camera("B");
    this.passos = 0;
    this.t = 0;
    this.acumulador = 0;
    this.alpha = 0;
    this.rodando = false;
    this.velocidade = 1;
    this.limitado = false;
    this.proximoQuadro = INTERVALO_CAMERA;
    this.proximaTaxa = 0;
    this.quadrosPendentes = [];
    this.quadrosDescartados = 0;
    this.modoZona = MODO_ZONA_PADRAO;
    this.atualizarTaxas();
  }

  get comparando() {
    return this.a !== null;
  }

  /* ---------- relógio ---------- */

  passo() {
    this.passos++;
    this.t = this.passos * PASSO;
    if (this.t + 1e-9 >= this.proximaTaxa) {
      this.atualizarTaxas();
      this.proximaTaxa += 1;
    }
    const eventos = this.gerador.gerar(this.t, PASSO);
    this.b.passo(PASSO, eventos);
    if (this.a) this.a.passo(PASSO, eventos);
    if (this.t + 1e-9 >= this.proximoQuadro) {
      this.quadrosPendentes.push(this.cameraB.capturar(this.b, this.t));
      if (this.quadrosPendentes.length > MAX_QUADROS_PENDENTES) {
        const excesso = this.quadrosPendentes.length - MAX_QUADROS_PENDENTES;
        this.quadrosPendentes.splice(0, excesso);
        this.quadrosDescartados += excesso;
      }
      this.proximoQuadro += INTERVALO_CAMERA;
    }
  }

  /** Avança `dtReal` segundos de relógio real na velocidade escolhida. */
  avancar(dtReal) {
    if (!this.rodando) return 0;
    this.acumulador += dtReal * this.velocidade;
    let passos = 0;
    while (this.acumulador >= PASSO - 1e-12 && passos < MAX_PASSOS_POR_QUADRO) {
      this.passo();
      this.acumulador -= PASSO;
      passos++;
    }
    // sem processador para acompanhar: desacelera em vez de acumular atraso
    this.limitado = this.acumulador >= PASSO;
    if (this.limitado) this.acumulador = 0;
    this.alpha = Math.max(0, Math.min(1, this.acumulador / PASSO));
    return passos;
  }

  /** Avança direto `segundos` simulados (testes e pré-aquecimento). */
  simular(segundos) {
    const passos = Math.round(segundos / PASSO);
    for (let i = 0; i < passos; i++) this.passo();
    this.alpha = 0;
  }

  /* ---------- controles ---------- */

  iniciar() {
    this.rodando = true;
  }

  pausar() {
    this.rodando = false;
  }

  alternar() {
    this.rodando = !this.rodando;
    return this.rodando;
  }

  definirVelocidade(velocidade) {
    if (!VELOCIDADES.includes(velocidade)) return false;
    this.velocidade = velocidade;
    return true;
  }

  horaAtual() {
    const h = this.demanda.horaInicial + (this.demanda.relogio ? this.t / 3600 : 0);
    return ((h % 24) + 24) % 24;
  }

  definirHora(hora) {
    this.demanda.horaInicial = hora - (this.demanda.relogio ? this.t / 3600 : 0);
    this.atualizarTaxas();
  }

  definirRelogio(avancando) {
    const agora = this.horaAtual();
    this.demanda.relogio = Boolean(avancando);
    this.definirHora(agora);
  }

  fator(viaId) {
    return this.demanda.fatores.get(viaId) ?? 1;
  }

  /** Muda a demanda de uma via em `delta` (ex.: +0,1 = +10 % da demanda base). */
  ajustarFluxo(viaId, delta) {
    const novo = Math.round(Math.min(FATOR_MAXIMO, Math.max(0, this.fator(viaId) + delta)) * 10) / 10;
    this.demanda.fatores.set(viaId, novo);
    this.atualizarTaxas();
    return novo;
  }

  /** Congestionamento em uma avenida (eixo "ns" ou "lo"); `null` desfaz. */
  definirCongestionamento(eixo, fator = FATOR_CONGESTIONAMENTO) {
    this.demanda.congestionamento = eixo ? { eixo, fator } : null;
    this.atualizarTaxas();
  }

  taxaBase(viaId, hora = this.horaAtual()) {
    const valores = this.perfil?.vias?.[String(viaId)];
    if (!valores?.length) return 0;
    const posicao = hora / (this.perfil.passoMinutos / 60);
    const i = Math.floor(posicao) % valores.length;
    const fracao = posicao - Math.floor(posicao);
    return valores[i] * (1 - fracao) + valores[(i + 1) % valores.length] * fracao;
  }

  /** Veículos/hora que chegam agora à via: perfil do dia × ajuste da via × congestionamento. */
  taxaDaVia(viaId) {
    let taxa = this.taxaBase(viaId) * this.fator(viaId);
    const c = this.demanda.congestionamento;
    if (c && this.eixos.get(viaId) === c.eixo) taxa *= c.fator;
    return taxa;
  }

  /** Demanda média do dia (6h–22h) de cada via, com os ajustes da via: base do plano fixo
      "ajustado", calculado uma vez, como um técnico programaria um semáforo convencional. */
  taxasMediasDoDia() {
    const [inicio, fim] = HORARIO_MEDIA;
    const horas = Array.from({ length: (fim - inicio) * 4 }, (_, i) => inicio + i / 4);
    return Object.fromEntries(
      this.geometria.vias.map((via) => {
        const media = horas.reduce((soma, h) => soma + this.taxaBase(via.id, h), 0) / horas.length;
        return [via.id, Math.round(media * this.fator(via.id))];
      }),
    );
  }

  atualizarTaxas() {
    for (const via of this.geometria.vias) this.gerador.definirTaxa(via.id, this.taxaDaVia(via.id));
  }

  /** Plano vindo do GSA para o cruzamento B: entra no fim do ciclo em andamento. */
  aplicarPlanoGsa(plano) {
    return this.b.controlador.agendar(plano);
  }

  /** Zonas de detecção no formato do deteccao/exemplo_zonas.json (modo: entrada | aproximacao). */
  zonas(modo = this.modoZona) {
    return this.geometria.vias.map((via) => ({
      viaId: via.id,
      nome: via.nome,
      poligono: via.zonas[modo].normalizada,
    }));
  }
}
