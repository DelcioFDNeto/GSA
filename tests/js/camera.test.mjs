/* Câmera sintética: detecções no formato YOLO + ByteTrack derivadas dos veículos da simulação. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { Mundo } from "../../simulador/web/js/mundo.js";
import { configuracaoB, dentro, plano } from "./_comum.mjs";

const CLASSES = new Set(["car", "motorcycle", "bus", "truck"]);

function mundoRodando(segundos = 150) {
  const mundo = new Mundo({ configuracao: configuracaoB(), semente: 31 });
  mundo.aplicarPlanoGsa(plano(40, 20));
  mundo.simular(segundos);
  return mundo;
}

test("caixas normalizadas, classes COCO, confiança acima do limiar e um id por veículo", () => {
  const mundo = mundoRodando();
  const quadro = mundo.cameraB.capturar(mundo.b, mundo.t);
  assert.ok(quadro.deteccoes.length > 15);
  const ids = new Set();
  for (const d of quadro.deteccoes) {
    const [id, classe, x1, y1, x2, y2, confianca] = d;
    assert.equal(d.length, 7);
    assert.ok(Number.isInteger(id) && id > 0);
    assert.ok(CLASSES.has(classe), classe);
    assert.ok([x1, y1, x2, y2].every((c) => c >= 0 && c <= 1));
    assert.ok(x1 < x2 && y1 < y2);
    assert.ok(confianca >= 0.3 && confianca <= 0.99);
    assert.ok(!ids.has(id), "ids distintos no mesmo quadro");
    ids.add(id);
  }
});

test("o id de rastreamento é persistente: o mesmo veículo mantém o id entre quadros", () => {
  const mundo = mundoRodando();
  mundo.cameraB.capturar(mundo.b, mundo.t);
  const antes = new Map([...mundo.cameraB.trilhas].map(([veiculo, trilha]) => [veiculo, trilha.id]));
  mundo.simular(3);
  mundo.cameraB.capturar(mundo.b, mundo.t);
  let comparados = 0;
  for (const [veiculo, trilha] of mundo.cameraB.trilhas) {
    if (antes.has(veiculo)) {
      assert.equal(trilha.id, antes.get(veiculo));
      comparados++;
    }
  }
  assert.ok(comparados > 10);
  const todos = [...mundo.cameraB.trilhas.values()].map((t) => t.id);
  assert.equal(new Set(todos).size, todos.length, "veículos diferentes, ids diferentes");
});

test("só detecta o que está no quadro e o ponto de contato cai na zona da via do veículo", () => {
  const mundo = mundoRodando();
  const quadro = mundo.cameraB.capturar(mundo.b, mundo.t);
  const porTrilha = new Map([...mundo.cameraB.trilhas].map(([veiculo, trilha]) => [trilha.id, veiculo]));
  const veiculos = new Map([...mundo.b.veiculos()].map(({ v, f }) => [v.id, { v, f }]));
  let naZona = 0;
  let conferidos = 0;
  for (const [id, , x1, , x2, y2] of quadro.deteccoes) {
    const { v, f } = veiculos.get(porTrilha.get(id));
    assert.ok(v.s > f.sQuadroInicio - v.L, "veículo fora do quadro não é detectado");
    const via = mundo.geometria.vias.find((x) => x.id === v.viaId);
    if (v.cruzou) continue;
    // ponto de contato: centro da base da caixa, como em deteccao/zonas.py
    const ponto = [(x1 + x2) / 2, y2];
    conferidos++;
    if (dentro(via.zonas.aproximacao.normalizada, ...ponto)) naZona++;
    for (const outra of mundo.geometria.vias.filter((x) => x.id !== via.id)) {
      assert.equal(dentro(outra.zonas.aproximacao.normalizada, ...ponto), false, "nunca na zona de outra via");
    }
  }
  assert.ok(conferidos > 10 && naZona / conferidos > 0.95, `${naZona}/${conferidos} na zona certa`);
});
