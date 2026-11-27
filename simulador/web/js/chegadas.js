/* Chegadas de veículos: processo de Poisson por via, com taxa variável (veículos/hora).

   Cada via tem um fluxo aleatório próprio, derivado da semente, então mudar a demanda de uma via
   não altera as chegadas das outras. No modo comparativo, o MESMO gerador alimenta os dois
   cruzamentos: os eventos (instante, via, classe, cor, velocidade desejada…) são idênticos. */

import { criarRng, derivarSemente, escolherPeso, poisson } from "./aleatorio.js";
import { ORDEM_TIPOS, PALETAS, PESOS_TIPOS } from "./veiculos.js";

export class GeradorChegadas {
  constructor({ viaIds, semente }) {
    this.semente = semente;
    this.vias = [...viaIds].sort((a, b) => a - b).map((id) => ({
      id,
      taxa: 0,
      rng: criarRng(derivarSemente(semente, "chegadas", id)),
    }));
    this.proximoId = 1;
    this.total = 0;
  }

  definirTaxa(viaId, veiculosPorHora) {
    const via = this.vias.find((v) => v.id === viaId);
    if (via) via.taxa = Math.max(0, veiculosPorHora);
  }

  taxa(viaId) {
    return this.vias.find((v) => v.id === viaId)?.taxa ?? 0;
  }

  /** Eventos de chegada do intervalo (t − dt, t]. */
  gerar(t, dt) {
    const eventos = [];
    for (const via of this.vias) {
      const quantidade = poisson(via.rng, (via.taxa / 3600) * dt);
      for (let i = 0; i < quantidade; i++) {
        const rng = via.rng;
        const tipo = ORDEM_TIPOS[escolherPeso(PESOS_TIPOS, rng())];
        const paleta = PALETAS[tipo];
        eventos.push({
          id: this.proximoId++,
          viaId: via.id,
          t: t - dt * rng(), // instante dentro do passo
          tipo,
          cor: paleta[escolherPeso(paleta.map(([, p]) => p), rng())][0],
          corSecundaria: rng(),
          fatorVelocidade: 0.88 + 0.24 * rng(), // motoristas diferentes, velocidades diferentes
          reacao: 0.45 + 0.55 * rng(), // tempo de reação na partida, em segundos
          desempate: rng(),
        });
      }
    }
    this.total += eventos.length;
    return eventos;
  }
}
