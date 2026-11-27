/* Geometria montada a partir das vias do GSA: faixas, mão de direção, retenção e zonas. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { montarGeometria, pontoDaFaixa } from "../../simulador/web/js/geometria.js";
import { VIAS_B, dentro } from "./_comum.mjs";

test("cada via ganha as faixas cadastradas, com mão de direção à direita", () => {
  const geo = montarGeometria(VIAS_B);
  const porVia = (id) => geo.faixas.filter((f) => f.viaId === id);
  assert.equal(geo.faixas.length, 3 + 3 + 1 + 1);
  assert.ok(porVia(3).every((f) => f.lateral > 0 && f.dy === -1), "sentido norte a leste do eixo");
  assert.ok(porVia(4).every((f) => f.lateral < 0 && f.dy === 1), "sentido sul a oeste do eixo");
  assert.ok(porVia(5).every((f) => f.lateral > 0 && f.dx === 1), "sentido leste ao sul do eixo");
  assert.ok(porVia(6).every((f) => f.lateral < 0 && f.dx === -1), "sentido oeste ao norte do eixo");
  assert.equal(geo.ns.tipoCanteiro, "ajardinado"); // avenida de 3 faixas por sentido
  assert.equal(geo.lo.tipoCanteiro, "pintado");
});

test("a linha de retenção fica antes do cruzamento e as faixas atravessam a área toda", () => {
  const geo = montarGeometria(VIAS_B);
  for (const f of geo.faixas) {
    assert.ok(f.sParada < f.sEntrada && f.sEntrada < f.sSaida && f.sSaida < f.comprimento);
    assert.ok(f.sQuadroInicio < f.sParada, "a retenção está dentro do quadro da câmera");
    const naRetencao = pontoDaFaixa(f, f.sParada);
    assert.ok(Math.abs(naRetencao.x) <= geo.meio && Math.abs(naRetencao.y) <= geo.meio);
  }
});

test("zonas normalizadas: faixa de entrada e aproximação inteira, uma por via, sem sobreposição", () => {
  const geo = montarGeometria(VIAS_B);
  for (const modo of ["entrada", "aproximacao"]) {
    for (const via of geo.vias) {
      const poligono = via.zonas[modo].normalizada;
      assert.equal(poligono.length, 4);
      assert.ok(poligono.flat().every((c) => c >= 0 && c <= 1));
      // o centro de cada faixa da via, no meio da zona, está na zona da via e em nenhuma outra
      for (const f of geo.faixas.filter((x) => x.viaId === via.id)) {
        const [xs, ys] = [via.zonas[modo].mundo.map((p) => p[0]), via.zonas[modo].mundo.map((p) => p[1])];
        const meio = f.eixo === "ns" ? [f.lateral, (Math.min(...ys) + Math.max(...ys)) / 2] : [(Math.min(...xs) + Math.max(...xs)) / 2, f.lateral];
        const n = meio.map((c) => (c + geo.meio) / (2 * geo.meio));
        for (const outra of geo.vias) {
          assert.equal(dentro(outra.zonas[modo].normalizada, ...n), outra.id === via.id, `${modo}: via ${via.id} x zona ${outra.id}`);
        }
      }
    }
  }
});

test("a faixa de entrada fica longe da retenção e é longa o bastante para 2 quadros por segundo", () => {
  const geo = montarGeometria(VIAS_B);
  for (const via of geo.vias) {
    const f = geo.faixas.find((x) => x.viaId === via.id);
    const pontos = via.zonas.entrada.mundo;
    const ao_longo = f.eixo === "ns" ? pontos.map((p) => p[1]) : pontos.map((p) => p[0]);
    const comprimento = Math.max(...ao_longo) - Math.min(...ao_longo);
    assert.ok(comprimento >= 15.3 * 0.5 * 2, "uma moto a 55 km/h aparece em ao menos dois quadros");
    const retencao = f.eixo === "ns" ? pontoDaFaixa(f, f.sParada).y : pontoDaFaixa(f, f.sParada).x;
    const distancia = Math.min(...ao_longo.map((c) => Math.abs(c - retencao)));
    assert.ok(distancia > 40, `a fila normal cabe entre a retenção e a faixa (${distancia.toFixed(0)} m)`);
  }
});

test("mão única (cruzamento A do seed) fica centrada e direções não desenháveis geram aviso", () => {
  const geo = montarGeometria([
    { id: 1, nome: "Via A — Avenida Principal", direcao: "norte", quantidadeFaixas: 2, estagio: null },
    { id: 2, nome: "Via B — Rua Secundária", direcao: "leste", quantidadeFaixas: 1, estagio: null },
    { id: 9, nome: "Alça", direcao: "nordeste", quantidadeFaixas: 1, estagio: null },
  ]);
  assert.equal(geo.ns.duasMaos, false);
  assert.deepEqual(
    geo.faixas.filter((f) => f.viaId === 1).map((f) => f.lateral),
    [-1.75, 1.75],
  );
  assert.equal(geo.vias.length, 2);
  assert.match(geo.avisos[0], /nordeste/);
});
