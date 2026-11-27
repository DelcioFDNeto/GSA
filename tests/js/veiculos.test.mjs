/* Movimentação dos veículos: aceleração progressiva, velocidade máxima e remoção na saída. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { SimulacaoCruzamento } from "../../simulador/web/js/cruzamento.js";
import { TIPOS, aceleracaoIdm, integrar } from "../../simulador/web/js/veiculos.js";
import { PASSO, chegada, geometriaB, plano } from "./_comum.mjs";

function cruzamento(planoInicial = plano(60, 15)) {
  return new SimulacaoCruzamento({ ...geometriaB(), plano: planoInicial });
}

test("IDM: acelera de forma progressiva até a velocidade desejada, sem passar dela", () => {
  const p = TIPOS.carro;
  let { s, v } = { s: 0, v: 0 };
  const velocidades = [];
  for (let i = 0; i < 600; i++) {
    const a = aceleracaoIdm(v, Infinity, 0, p);
    assert.ok(a <= p.a + 1e-9);
    ({ s, v } = integrar(s, v, a, PASSO));
    velocidades.push(v);
  }
  assert.ok(velocidades.every((x, i) => i === 0 || x >= velocidades[i - 1] - 1e-9), "nunca desacelera em via livre");
  assert.ok(v > 0.97 * p.v0 && v <= p.v0, `chega perto de ${p.v0} m/s`);
  assert.ok(velocidades[19] < 0.25 * p.v0, "não salta para a velocidade máxima");
});

test("integração balística nunca produz velocidade negativa nem anda para trás", () => {
  const { s, v } = integrar(10, 2, -9, 1);
  assert.equal(v, 0);
  assert.ok(s >= 10 && s <= 10 + 2 * 2 / (2 * 9) + 1e-9);
});

test("veículo com verde atravessa, mantém posição crescente e é removido ao sair", () => {
  const sim = cruzamento(plano(60, 15)); // estágio 1 (avenida) começa no verde
  sim.passo(PASSO, [chegada(3, 0)]);
  const veiculo = sim.faixas.flatMap((f) => f.veiculos)[0];
  assert.equal(veiculo.viaId, 3);
  assert.ok(veiculo.id > 0 && veiculo.classe === "car" && veiculo.v0 > 0 && veiculo.faixaId);
  let anterior = veiculo.s;
  let removido = false;
  for (let i = 0; i < 40 / PASSO; i++) {
    sim.passo(PASSO, []);
    const ainda = sim.faixas.flatMap((f) => f.veiculos).find((v) => v.id === veiculo.id);
    if (!ainda) {
      removido = true;
      break;
    }
    assert.ok(ainda.s >= anterior, "a posição só aumenta");
    assert.ok(ainda.v <= ainda.v0 + 1e-6, "respeita a velocidade máxima do motorista");
    anterior = ainda.s;
  }
  assert.ok(removido, "saiu da área simulada e foi removido");
  assert.equal(sim.estat.servidos, 1);
  assert.equal(sim.saidos, 1);
});

test("as quatro classes têm dimensões e velocidades distintas", () => {
  const classes = Object.values(TIPOS);
  assert.deepEqual(classes.map((t) => t.classe).sort(), ["bus", "car", "motorcycle", "truck"]);
  assert.ok(TIPOS.onibus.comprimento > TIPOS.caminhao.comprimento && TIPOS.caminhao.comprimento > TIPOS.carro.comprimento);
  assert.ok(TIPOS.moto.comprimento < TIPOS.carro.comprimento && TIPOS.moto.v0 > TIPOS.caminhao.v0);
});
