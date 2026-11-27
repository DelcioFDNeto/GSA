/* Controlador semafórico: transições, troca segura de plano, monitor de conflitos e aplicação
   do ciclo calculado pelo GSA (inclusive o significado de tempoVermelho). */

import assert from "node:assert/strict";
import { test } from "node:test";

import { ControladorSemaforico, validarPlano } from "../../simulador/web/js/controlador.js";
import { PASSO, geometriaB, plano } from "./_comum.mjs";

const { eixos, limites } = geometriaB();
const novo = (p) => new ControladorSemaforico({ plano: p, eixos, limites });

/** Estados de cada via a cada passo, de 0 a `segundos`. */
function linhaDoTempo(ctrl, segundos, vias = [3, 4, 5, 6]) {
  const amostras = [];
  for (let i = 0; i < Math.round(segundos / PASSO); i++) {
    amostras.push(Object.fromEntries(vias.map((v) => [v, ctrl.estadoDaVia(v)])));
    ctrl.avancar(PASSO);
  }
  return amostras;
}

/** Trechos consecutivos [estado, duração em s] de uma via. */
function trechos(amostras, via) {
  const resultado = [];
  for (const a of amostras) {
    const ultimo = resultado.at(-1);
    if (ultimo && ultimo[0] === a[via]) ultimo[1] += PASSO;
    else resultado.push([a[via], PASSO]);
  }
  return resultado.map(([estado, d]) => [estado, Math.round(d * 100) / 100]);
}

test("cada estágio cumpre verde → amarelo → vermelho geral com as durações do plano", () => {
  const amostras = linhaDoTempo(novo(plano(20, 15)), 90);
  // ciclo de 45 s: estágio 1 = 20 + 3 + 2; estágio 2 = 15 + 3 + 2
  assert.deepEqual(trechos(amostras, 3).slice(0, 4), [["verde", 20], ["amarelo", 3], ["vermelho", 22], ["verde", 20]]);
  assert.deepEqual(trechos(amostras, 5).slice(0, 4), [["vermelho", 25], ["verde", 15], ["amarelo", 3], ["vermelho", 27]]);
  // vias do mesmo estágio abrem e fecham juntas
  assert.ok(amostras.every((a) => a[3] === a[4] && a[5] === a[6]));
  // entre os estágios, 2 s de vermelho geral (vermelho de segurança do semáforo)
  const geral = amostras.filter((a) => Object.values(a).every((e) => e === "vermelho")).length * PASSO;
  assert.ok(Math.abs(geral - 2 * 2 * 2) < PASSO * 2.5, `vermelho geral: ${geral} s em dois ciclos`);
});

test("plano novo fica pendente e só entra no fim do ciclo, com todas as vias fechadas", () => {
  const ctrl = novo(plano(20, 15));
  linhaDoTempo(ctrl, 10);
  const antigo = ctrl.plano;
  assert.ok(ctrl.agendar(plano(25, 15)).ok);
  assert.ok(ctrl.agendar(plano(30, 20)).ok, "um plano mais novo substitui o pendente");
  let troca = null;
  let estadoAntes = null;
  for (let i = 0; i < Math.round(40 / PASSO); i++) {
    const antes = Object.fromEntries([3, 4, 5, 6].map((v) => [v, ctrl.estadoDaVia(v)]));
    ctrl.avancar(PASSO);
    if (ctrl.plano !== antigo && troca === null) {
      troca = ctrl.t;
      estadoAntes = antes;
    }
  }
  assert.ok(Math.abs(troca - 45) < PASSO * 1.5, `troca no fim do ciclo de 45 s (foi em ${troca})`);
  assert.ok(Object.values(estadoAntes).every((e) => e === "vermelho"), "todas fechadas na troca");
  assert.deepEqual(ctrl.plano.estagios.map((e) => e.verde), [30, 20]);
  assert.equal(ctrl.pendente, null);
  assert.equal(ctrl.trocas, 1);
});

test("monitor de conflitos recusa planos inseguros e mantém o plano em execução", () => {
  const ctrl = novo(plano(20, 15));
  const inseguros = {
    "movimentos que se cruzam": { estagios: [{ chave: "e1", vias: [3, 5], verde: 20, amarelo: 3, vermelho: 2 }] },
    "verde acima do máximo": plano(70, 15),
    "verde abaixo do mínimo": plano(10, 15),
    "amarelo menor que o do semáforo": { estagios: [{ chave: "e1", vias: [3, 4], verde: 20, amarelo: 2, vermelho: 2 }] },
    "vermelho de segurança menor": { estagios: [{ chave: "e1", vias: [3, 4], verde: 20, amarelo: 3, vermelho: 1 }] },
    "via em dois estágios": {
      estagios: [
        { chave: "e1", vias: [3, 4], verde: 20, amarelo: 3, vermelho: 2 },
        { chave: "e2", vias: [4, 5, 6], verde: 20, amarelo: 3, vermelho: 2 },
      ],
    },
  };
  for (const [motivo, p] of Object.entries(inseguros)) {
    const resultado = ctrl.agendar(p);
    assert.equal(resultado.ok, false, motivo);
    assert.ok(resultado.erros.length > 0, motivo);
  }
  assert.equal(ctrl.pendente, null);
  assert.equal(ctrl.rejeitados.length, Object.keys(inseguros).length);
  assert.match(validarPlano(inseguros["movimentos que se cruzam"], { eixos }).erros[0], /cruzam/);
});

test("falha segura: se vias conflitantes abrissem juntas, o controlador fecharia todas", () => {
  const ctrl = novo(plano(20, 15));
  ctrl.plano = { estagios: [{ chave: "x", rotulo: "x", vias: [3, 5], verde: 20, amarelo: 3, vermelho: 2 }] };
  assert.ok(ctrl.verificarConflitos());
  assert.deepEqual(ctrl.viasAbertas(), []);
  assert.ok([3, 4, 5, 6].every((v) => ctrl.estadoDaVia(v) === "vermelho"));
});

test("ciclo do GSA aplicado: verde, amarelo e vermelho TOTAL de cada via batem com o cicloGerado", () => {
  // Webster com ciclo de 87 s (como devolvido pela API): tempoVermelho é o total da via no ciclo,
  // e o vermelho de segurança (2 s) vem do semáforo cadastrado
  const cicloGerado = {
    duracaoTotal: 87,
    tempos: [
      { viaId: 3, tempoVerde: 53, tempoAmarelo: 3, tempoVermelho: 31 },
      { viaId: 4, tempoVerde: 53, tempoAmarelo: 3, tempoVermelho: 31 },
      { viaId: 5, tempoVerde: 24, tempoAmarelo: 3, tempoVermelho: 60 },
      { viaId: 6, tempoVerde: 24, tempoAmarelo: 3, tempoVermelho: 60 },
    ],
  };
  const ctrl = novo(plano(20, 15));
  ctrl.agendar(plano(53, 24));
  linhaDoTempo(ctrl, 45); // termina o ciclo do plano anterior
  const amostras = linhaDoTempo(ctrl, 87 * 2);
  for (const t of cicloGerado.tempos) {
    const soma = (estado) => (amostras.filter((a) => a[t.viaId] === estado).length * PASSO) / 2;
    assert.ok(Math.abs(soma("verde") - t.tempoVerde) < 0.11, `via ${t.viaId}: verde`);
    assert.ok(Math.abs(soma("amarelo") - t.tempoAmarelo) < 0.11, `via ${t.viaId}: amarelo`);
    assert.ok(Math.abs(soma("vermelho") - t.tempoVermelho) < 0.11, `via ${t.viaId}: vermelho total`);
  }
  assert.equal(ctrl.duracaoDoCiclo(), cicloGerado.duracaoTotal);
});
