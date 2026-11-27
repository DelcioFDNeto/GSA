/* Controles da interface (a lógica fica em mundo.js, sem DOM): iniciar, pausar, velocidade,
   fluxo por via, horário de pico, congestionamento e zonas. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { MAX_PASSOS_POR_QUADRO, Mundo, PASSO } from "../../simulador/web/js/mundo.js";
import { configuracaoB, perfilConstante } from "./_comum.mjs";

const novo = (extra = {}) => new Mundo({ configuracao: { ...configuracaoB(), ...extra }, semente: 1 });

test("iniciar, pausar e alternar controlam o relógio simulado", () => {
  const mundo = novo();
  assert.equal(mundo.avancar(1), 0, "parado não anda");
  mundo.iniciar();
  mundo.avancar(1);
  assert.ok(Math.abs(mundo.t - 1) < PASSO);
  mundo.pausar();
  mundo.avancar(1);
  assert.ok(Math.abs(mundo.t - 1) < PASSO);
  assert.equal(mundo.alternar(), true);
});

test("velocidades 1×, 2×, 5× e 10× multiplicam o tempo simulado por segundo real", () => {
  for (const velocidade of [1, 2, 5, 10]) {
    const mundo = novo();
    mundo.iniciar();
    assert.ok(mundo.definirVelocidade(velocidade));
    for (let i = 0; i < 60; i++) mundo.avancar(1 / 60);
    assert.ok(Math.abs(mundo.t - velocidade) < 2 * PASSO, `${velocidade}×: ${mundo.t}`);
    assert.equal(mundo.limitado, false);
  }
  assert.equal(novo().definirVelocidade(3), false);
});

test("se o processador não acompanha, desacelera em vez de acumular atraso", () => {
  const mundo = novo();
  mundo.iniciar();
  mundo.definirVelocidade(10);
  const passos = mundo.avancar(1); // pediria 200 passos em um quadro só
  assert.equal(passos, MAX_PASSOS_POR_QUADRO);
  assert.equal(mundo.limitado, true);
});

test("fluxo por via: +/− em passos de 10 %, entre 0 e 300 %", () => {
  const mundo = novo();
  const base = mundo.taxaDaVia(3);
  assert.equal(mundo.ajustarFluxo(3, +0.1), 1.1);
  assert.ok(Math.abs(mundo.taxaDaVia(3) - base * 1.1) < 1e-6);
  assert.ok(Math.abs(mundo.gerador.taxa(3) - base * 1.1) < 1e-6, "o gerador de chegadas recebe a taxa nova");
  for (let i = 0; i < 40; i++) mundo.ajustarFluxo(3, +0.1);
  assert.equal(mundo.fator(3), 3);
  for (let i = 0; i < 40; i++) mundo.ajustarFluxo(3, -0.1);
  assert.equal(mundo.fator(3), 0);
  assert.equal(mundo.taxaDaVia(3), 0);
  assert.equal(mundo.fator(4), 1, "as outras vias não mudam");
});

test("horário de pico segue o perfil de demanda; o relógio do dia pode avançar com a simulação", () => {
  const perfil = perfilConstante({ 3: 0, 4: 0, 5: 0, 6: 0 });
  perfil.vias["3"] = Array.from({ length: 96 }, (_, i) => (i === 32 ? 2000 : 500)); // pico às 8h
  const mundo = novo({ perfilDemanda: perfil });
  mundo.definirHora(8);
  assert.equal(mundo.taxaDaVia(3), 2000);
  mundo.definirHora(12);
  assert.equal(mundo.taxaDaVia(3), 500);
  mundo.definirHora(7.75);
  mundo.definirRelogio(true);
  mundo.simular(15 * 60);
  assert.ok(Math.abs(mundo.horaAtual() - 8) < 1e-6);
  assert.equal(mundo.taxaDaVia(3), 2000);
});

test("congestionamento multiplica só a demanda da avenida escolhida", () => {
  const mundo = novo();
  const antes = [3, 4, 5, 6].map((v) => mundo.taxaDaVia(v));
  mundo.definirCongestionamento("ns");
  assert.ok(Math.abs(mundo.taxaDaVia(3) - antes[0] * 1.5) < 1e-6);
  assert.ok(Math.abs(mundo.taxaDaVia(4) - antes[1] * 1.5) < 1e-6);
  assert.equal(mundo.taxaDaVia(5), antes[2]);
  mundo.definirCongestionamento(null);
  assert.equal(mundo.taxaDaVia(3), antes[0]);
});

test("zonas no formato de exemplo_zonas.json e demanda média do dia para o plano ajustado", () => {
  const mundo = novo();
  const entrada = mundo.zonas("entrada");
  const aproximacao = mundo.zonas("aproximacao");
  assert.deepEqual(entrada.map((z) => z.viaId), [3, 4, 5, 6]);
  assert.ok(entrada.every((z) => z.nome && z.poligono.length === 4));
  assert.notDeepEqual(entrada[0].poligono, aproximacao[0].poligono);
  mundo.ajustarFluxo(5, -0.5);
  assert.deepEqual(mundo.taxasMediasDoDia(), { 3: 1950, 4: 1050, 5: 80, 6: 300 });
});
