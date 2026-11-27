/* Chegadas de Poisson reprodutíveis, com taxa por sentido, e as mesmas chegadas nos dois
   cruzamentos do modo comparativo. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { GeradorChegadas } from "../../simulador/web/js/chegadas.js";
import { Mundo } from "../../simulador/web/js/mundo.js";
import { PASSO, configuracaoB, plano } from "./_comum.mjs";

function gerar(semente, taxas, segundos) {
  const gerador = new GeradorChegadas({ viaIds: Object.keys(taxas).map(Number), semente });
  for (const [via, taxa] of Object.entries(taxas)) gerador.definirTaxa(Number(via), taxa);
  const eventos = [];
  for (let i = 1; i <= Math.round(segundos / PASSO); i++) eventos.push(...gerador.gerar(i * PASSO, PASSO));
  return eventos;
}

test("processo de Poisson: média na taxa pedida e intervalos com coeficiente de variação ~1", () => {
  const eventos = gerar(3, { 3: 1800, 5: 200 }, 7200);
  const via3 = eventos.filter((e) => e.viaId === 3);
  const via5 = eventos.filter((e) => e.viaId === 5);
  assert.ok(Math.abs(via3.length - 3600) < 200, `${via3.length} chegadas (esperado 3600 ± 3σ)`);
  assert.ok(Math.abs(via5.length - 400) < 65, `${via5.length} chegadas (esperado 400)`);
  const intervalos = via3.slice(1).map((e, i) => e.t - via3[i].t);
  const media = intervalos.reduce((a, b) => a + b, 0) / intervalos.length;
  const desvio = Math.sqrt(intervalos.reduce((a, b) => a + (b - media) ** 2, 0) / intervalos.length);
  assert.ok(Math.abs(desvio / media - 1) < 0.1, `coeficiente de variação ${(desvio / media).toFixed(2)}`);
});

test("mesma semente, mesmas chegadas; a taxa de uma via não altera as chegadas das outras", () => {
  const a = gerar(7, { 3: 900, 5: 300 }, 600);
  const b = gerar(7, { 3: 900, 5: 300 }, 600);
  assert.deepEqual(a, b);
  const c = gerar(7, { 3: 900, 5: 1200 }, 600);
  const tempos = (lista) => lista.filter((e) => e.viaId === 3).map((e) => [e.t, e.tipo, e.cor]);
  assert.deepEqual(tempos(a), tempos(c));
  assert.notDeepEqual(gerar(8, { 3: 900, 5: 300 }, 600), a);
});

test("classes sorteadas na proporção de uma via urbana", () => {
  const eventos = gerar(11, { 3: 3600 }, 3600);
  const fracao = (tipo) => eventos.filter((e) => e.tipo === tipo).length / eventos.length;
  assert.ok(Math.abs(fracao("carro") - 0.78) < 0.03);
  assert.ok(Math.abs(fracao("moto") - 0.12) < 0.02);
  assert.ok(fracao("onibus") > 0.02 && fracao("caminhao") > 0.04);
});

test("modo comparativo: A (tempo fixo) e B (GSA) recebem exatamente as mesmas chegadas", () => {
  const mundo = new Mundo({ configuracao: configuracaoB(), semente: 2026, planoA: plano(55, 55) });
  const original = mundo.gerador.gerar.bind(mundo.gerador);
  const geradas = [];
  mundo.gerador.gerar = (t, dt) => {
    const eventos = original(t, dt);
    geradas.push(...eventos);
    return eventos;
  };
  mundo.aplicarPlanoGsa(plano(30, 15)); // B passa a ter outro plano: as chegadas não mudam
  mundo.simular(900);
  assert.ok(geradas.length > 400);
  assert.equal(mundo.a.estat.chegadas, geradas.length);
  assert.equal(mundo.b.estat.chegadas, geradas.length);
  for (const via of [3, 4, 5, 6]) {
    assert.equal(mundo.a.estat.porVia.get(via).chegadas, mundo.b.estat.porVia.get(via).chegadas);
  }
  // cada veículo de A tem o gêmeo em B (mesmo id, classe e cor), mesmo andando de forma diferente
  const de = (sim) => new Map([...sim.veiculos()].map(({ v }) => [v.id, `${v.classe}:${v.cor}:${v.viaId}`]));
  const emB = de(mundo.b);
  for (const [id, descricao] of de(mundo.a)) {
    if (emB.has(id)) assert.equal(emB.get(id), descricao);
  }
});
