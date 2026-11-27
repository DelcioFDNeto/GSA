/* Formação de filas no vermelho, retomada gradual no verde e decisão no amarelo. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { SimulacaoCruzamento } from "../../simulador/web/js/cruzamento.js";
import { PASSO, chegada, geometriaB, plano } from "./_comum.mjs";

/** Roda até `ate` segundos; `chegadas(t, i)` devolve os eventos de cada passo. Guarda todos os
    veículos que já apareceram (os que saem da área são removidos das faixas). */
function rodar(planoInicial, ate, chegadas = () => [], sim = null, vistos = new Map()) {
  sim = sim || new SimulacaoCruzamento({ ...geometriaB(), plano: planoInicial });
  for (let i = 0; sim.t < ate - 1e-9; i++) {
    sim.passo(PASSO, chegadas(sim.t, i));
    for (const f of sim.faixas) for (const v of f.veiculos) vistos.set(v.id, v);
  }
  return { sim, vistos: [...vistos.values()], mapa: vistos };
}

const daVia = (lista, viaId) => lista.filter((v) => v.viaId === viaId).sort((a, b) => a.id - b.id);

// via 5 (rua, sentido leste) fica no vermelho enquanto o estágio 1 (avenida) está aberto:
// com plano(60, 15), de 0 a 65 s; uma chegada a cada 1,5 s até completar 8
const oitoNoVermelho = (t, i) => (i % 30 === 0 && i < 8 * 30 ? [chegada(5, t)] : []);

test("no vermelho os veículos param antes da retenção, em fila, sem encostar", () => {
  const { sim } = rodar(plano(60, 15), 50, oitoNoVermelho);
  const faixa = sim.faixas.find((f) => f.viaId === 5);
  const fila = faixa.veiculos;
  assert.equal(sim.estados.get(5), "vermelho");
  assert.equal(fila.length, 8);
  assert.deepEqual(fila.map((v) => v.id), [...fila.map((v) => v.id)].sort((a, b) => a - b), "ordem de chegada");
  assert.ok(fila.every((v) => v.v < 0.1 && !v.cruzou && v.s < faixa.sParada), "todos parados antes da linha");
  assert.ok(faixa.sParada - fila[0].s < 2.5, "o primeiro para junto da linha de retenção");
  for (let i = 1; i < fila.length; i++) {
    const espaco = fila[i - 1].s - fila[i - 1].L - fila[i].s;
    assert.ok(espaco > 1.2 && espaco < 4, `distância de segurança entre ${i - 1} e ${i}: ${espaco.toFixed(2)} m`);
  }
  const medida = sim.medirVia(5);
  assert.equal(medida.fila, 8);
  assert.equal(medida.parados, 8);
  assert.ok(medida.filaMetros > 8 * 4.5, "o tamanho da fila em metros cobre os oito carros");
  assert.ok(fila.every((v) => v.espera > 0), "quem está parado acumula tempo de espera");
});

test("quando abre, a fila sai em onda: cada um arranca depois do da frente", () => {
  const { sim, mapa } = rodar(plano(60, 15), 50, oitoNoVermelho);
  const fila = sim.faixas.find((f) => f.viaId === 5).veiculos.slice();
  const partida = new Map();
  while (sim.t < 82) {
    rodar(null, sim.t + PASSO, () => [], sim, mapa);
    for (const v of fila) if (!partida.has(v.id) && v.v > 0.3) partida.set(v.id, sim.t);
  }
  const inicioVerde = 60 + 3 + 2;
  const tempos = fila.map((v) => partida.get(v.id));
  assert.ok(tempos.every((t) => t !== undefined), "todos arrancaram");
  assert.ok(tempos[0] >= inicioVerde + 0.4, "o primeiro reage ao verde, não arranca no mesmo instante");
  for (let i = 1; i < tempos.length; i++) {
    assert.ok(tempos[i] - tempos[i - 1] >= 0.4, `veículo ${i} arranca depois do anterior`);
  }
  const cruzaram = fila.filter((v) => v.cruzou);
  assert.ok(cruzaram.length >= 6, `${cruzaram.length} cruzaram no verde de 15 s + amarelo`);
  assert.ok(cruzaram.every((v) => v.tCruzou >= inicioVerde));
});

test("fila longa descarrega perto do fluxo de saturação do GSA (~1.800 veículos/h por faixa)", () => {
  // avenida aberta por 40 s primeiro: a rua acumula 18 carros, depois tem 60 s de verde
  const chegadas = (t, i) => (i % 30 === 0 && i < 18 * 30 ? [chegada(5, t)] : []);
  const { vistos } = rodar(plano(40, 60), 120, chegadas);
  const travessias = daVia(vistos, 5).filter((v) => v.cruzou).map((v) => v.tCruzou).sort((a, b) => a - b);
  assert.equal(travessias.length, 18);
  const intervalos = travessias.slice(1).map((t, i) => t - travessias[i]).slice(4, 14);
  const media = intervalos.reduce((a, b) => a + b, 0) / intervalos.length;
  assert.ok(media > 1.7 && media < 2.3, `intervalo de saturação ${media.toFixed(2)} s (${(3600 / media).toFixed(0)} veíc/h)`);
});

test("no amarelo, para quem consegue frear; quem está perto segue — e ninguém cruza no vermelho", () => {
  // avenida (via 3): verde 0–15 s, amarelo 15–18 s; carros chegando a cada 2 s até 10 s
  const decisoes = new Map();
  const chegadas = (t, i) => (i % 40 === 0 && t < 11 ? [chegada(3, t)] : []);
  const sim = new SimulacaoCruzamento({ ...geometriaB(), plano: plano(15, 15) });
  const vistos = new Map();
  while (sim.t < 37) {
    rodar(null, sim.t + PASSO, (t) => chegadas(t, Math.round(t / PASSO)), sim, vistos);
    for (const v of vistos.values()) if (v.decisao) decisoes.set(v.id, v.decisao);
  }
  const todos = daVia([...vistos.values()], 3);
  assert.equal(todos.length, 6);
  const fimDoAmarelo = 15 + 3;
  const seguiram = todos.filter((v) => decisoes.get(v.id) === "seguir");
  const pararam = todos.filter((v) => !v.cruzou);
  assert.ok(seguiram.length >= 1 && pararam.length >= 1, "há quem siga e quem pare");
  for (const v of todos.filter((x) => x.cruzou && x.tCruzou > 15)) {
    assert.equal(decisoes.get(v.id), "seguir", `veículo ${v.id} só cruzou no amarelo porque já não conseguia parar`);
    assert.ok(v.tCruzou <= fimDoAmarelo, "quem seguiu passou da linha ainda no amarelo");
  }
  assert.ok(pararam.every((v) => v.v < 0.1 && decisoes.get(v.id) === "parar"), "os demais esperam parados");
});
