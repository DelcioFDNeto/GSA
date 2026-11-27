/* Ausência de colisões e de verdes conflitantes sob demanda pesada e planos mudando. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { criarRng } from "../../simulador/web/js/aleatorio.js";
import { Mundo } from "../../simulador/web/js/mundo.js";
import { PASSO, configuracaoB, plano } from "./_comum.mjs";

function caixaOcupadaPorEixos(sim) {
  const { caixa } = sim.geo;
  const eixos = new Set();
  for (const { v, f } of sim.veiculos()) {
    const r = sim.retangulo(f, v);
    if (r.x1 > caixa.x0 && r.x0 < caixa.x1 && r.y1 > caixa.y0 && r.y0 < caixa.y1) eixos.add(f.eixo);
  }
  return eixos;
}

test("uma hora de pico pesado com planos mudando: nenhuma colisão, nenhum verde conflitante", () => {
  const configuracao = configuracaoB({ taxas: { 3: 2400, 4: 1500, 5: 420, 6: 480 } });
  const mundo = new Mundo({ configuracao, semente: 99, planoA: plano(55, 55) });
  const sorteio = criarRng(5);
  let maiorFila = 0;
  for (let i = 0; i < 3600 / PASSO; i++) {
    if (i % Math.round(90 / PASSO) === 0) {
      // um plano novo a cada janela, como o GSA faria (dentro dos limites de 15–60 s)
      const resultado = mundo.aplicarPlanoGsa(plano(15 + Math.floor(sorteio() * 46), 15 + Math.floor(sorteio() * 46)));
      assert.ok(resultado.ok);
    }
    mundo.passo();
    for (const sim of [mundo.a, mundo.b]) {
      const abertas = new Set(sim.controlador.viasAbertas().map((v) => mundo.eixos.get(v)));
      assert.ok(abertas.size <= 1, `t=${mundo.t}: movimentos conflitantes abertos juntos`);
      assert.deepEqual(sim.sobreposicoes(), [], `t=${mundo.t.toFixed(2)}: veículos sobrepostos`);
      assert.ok(caixaOcupadaPorEixos(sim).size <= 1, `t=${mundo.t.toFixed(2)}: os dois eixos dentro do cruzamento`);
    }
    maiorFila = Math.max(maiorFila, mundo.b.medirVia(3).fila);
  }
  assert.equal(mundo.a.correcoes + mundo.b.correcoes, 0, "o IDM manteve a distância sem a trava de segurança");
  assert.equal(mundo.b.controlador.falha, null);
  assert.equal(mundo.a.controlador.falha, null);
  assert.ok(mundo.b.estat.servidos > 4000, `${mundo.b.estat.servidos} veículos atendidos`);
  assert.ok(maiorFila > 20, "o cenário formou filas de verdade");
});
