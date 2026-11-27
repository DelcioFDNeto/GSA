/* Dados comuns dos testes do simulador: o cruzamento B do scripts/seed.py, como a ponte do
   simulador o entrega ao navegador (GET /simulador/api/cruzamentos/{id}/configuracao). */

import { montarGeometria, eixosDasVias } from "../../simulador/web/js/geometria.js";

export const PASSO = 0.05;

const semaforo = (viaId) => ({
  id: viaId * 10,
  viaId,
  tempoMinimoVerde: 15,
  tempoMaximoVerde: 60,
  tempoAmarelo: 3,
  tempoVermelho: 2,
  status: "ativo",
});

export const VIAS_B = [
  { id: 3, nome: "Avenida Central — sentido norte", direcao: "norte", quantidadeFaixas: 3, estagio: 1 },
  { id: 4, nome: "Avenida Central — sentido sul", direcao: "sul", quantidadeFaixas: 3, estagio: 1 },
  { id: 5, nome: "Rua Lateral — sentido leste", direcao: "leste", quantidadeFaixas: 1, estagio: 2 },
  { id: 6, nome: "Rua Lateral — sentido oeste", direcao: "oeste", quantidadeFaixas: 1, estagio: 2 },
].map((v) => ({ ...v, semaforo: semaforo(v.id), ativa: true, eixo: v.direcao === "norte" || v.direcao === "sul" ? "ns" : "lo" }));

/** Plano no formato da ponte (estágios na ordem do motor; vermelho = de segurança). */
export function plano(verde1, verde2, extra = {}) {
  return {
    origem: "gsa",
    modoOperacao: "adaptativo",
    estagios: [
      { chave: "e1", rotulo: "Estágio 1", vias: [3, 4], verde: verde1, amarelo: 3, vermelho: 2 },
      { chave: "e2", rotulo: "Estágio 2", vias: [5, 6], verde: verde2, amarelo: 3, vermelho: 2 },
    ],
    ...extra,
  };
}

/** Perfil de demanda constante (veículos/hora por via), no formato do perfilDemanda. */
export function perfilConstante(taxas) {
  return {
    passoMinutos: 15,
    vias: Object.fromEntries(Object.entries(taxas).map(([id, taxa]) => [id, Array(96).fill(taxa)])),
  };
}

export function configuracaoB({ taxas = { 3: 1950, 4: 1050, 5: 160, 6: 300 }, planoFixo = plano(55, 55, { origem: "tempo_fixo", modoOperacao: "tempo_fixo" }) } = {}) {
  return {
    cruzamento: { id: 2, nome: "Cruzamento Demonstração B", regraTemporizacao: "webster", duracaoCiclo: 120 },
    parametros: { intervaloContagem: 90, tempoMaximoSemLeitura: 300 },
    janelaSegundos: 90,
    vias: VIAS_B,
    planoFixo,
    perfilDemanda: perfilConstante(taxas),
    classes: ["car", "motorcycle", "bus", "truck"],
    confiancaMinima: 0.3,
  };
}

export function geometriaB() {
  const geometria = montarGeometria(VIAS_B);
  return { geometria, eixos: eixosDasVias(geometria), limites: new Map(VIAS_B.map((v) => [v.id, v.semaforo])) };
}

let proximoId = 1;
/** Evento de chegada determinístico (os testes controlam exatamente quem chega). */
export function chegada(viaId, t, tipo = "carro", extra = {}) {
  return {
    id: proximoId++,
    viaId,
    t,
    tipo,
    cor: "#f1f1ee",
    corSecundaria: 0.5,
    fatorVelocidade: 1,
    reacao: 0.8,
    desempate: 0.5,
    ...extra,
  };
}

/** Ponto dentro de um polígono (mesmo algoritmo de deteccao/zonas.py: ray casting). */
export function dentro(poligono, x, y) {
  let resultado = false;
  for (let i = 0; i < poligono.length; i++) {
    const [x1, y1] = poligono[i];
    const [x2, y2] = poligono[(i + poligono.length - 1) % poligono.length];
    if (y1 > y !== y2 > y && x < ((x2 - x1) * (y - y1)) / (y2 - y1) + x1) resultado = !resultado;
  }
  return resultado;
}
