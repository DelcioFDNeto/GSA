/* Classes de veículos e o modelo de seguimento (Intelligent Driver Model, Treiber et al.).

   O IDM dá aceleração e frenagem progressivas e mantém distância de segurança:
   a = a_max · [1 − (v / v0)^4 − (s_desejado / s)²],
   com s_desejado = s0 + v·T + v·Δv / (2·√(a_max·b)).
   O semáforo fechado entra como um obstáculo parado na linha de retenção. */

export const TIPOS = {
  carro: {
    nome: "carro",
    classe: "car",
    comprimento: 4.5,
    largura: 1.8,
    v0: 13.9, // 50 km/h
    // a, s0 e T calibrados para a fila descarregar a ~1.800 veíc/h por faixa com a mistura de
    // veículos padrão: o mesmo fluxo de saturação que o GSA usa na regra de Webster
    a: 2.3,
    b: 2.5,
    s0: 1.8,
    T: 1.1,
    bAmarelo: 3.6,
    peso: 0.78,
  },
  moto: {
    nome: "moto",
    classe: "motorcycle",
    comprimento: 2.1,
    largura: 0.8,
    v0: 15.3,
    a: 2.8,
    b: 3.0,
    s0: 1.6,
    T: 0.9,
    bAmarelo: 4.0,
    peso: 0.12,
  },
  onibus: {
    nome: "ônibus",
    classe: "bus",
    comprimento: 12.0,
    largura: 2.55,
    v0: 12.5,
    a: 1.1,
    b: 1.8,
    s0: 2.5,
    T: 1.5,
    bAmarelo: 2.8,
    peso: 0.04,
  },
  caminhao: {
    nome: "caminhão",
    classe: "truck",
    comprimento: 9.0,
    largura: 2.5,
    v0: 12.0,
    a: 1.0,
    b: 1.7,
    s0: 2.5,
    T: 1.6,
    bAmarelo: 2.6,
    peso: 0.06,
  },
};
export const ORDEM_TIPOS = ["carro", "moto", "onibus", "caminhao"];
export const PESOS_TIPOS = ORDEM_TIPOS.map((t) => TIPOS[t].peso);

export const LIMITE_PARADO = 0.5; // m/s: abaixo disso o veículo acumula tempo de espera
export const LIMITE_FILA = 2.0; // m/s: abaixo disso, antes da retenção, está na fila
export const FRENAGEM_MAXIMA = 9.0; // m/s², frenagem de emergência
export const FRENAGEM_VERMELHO = 6.0; // quem tinha seguido no amarelo ainda para se couber isso
export const DISTANCIA_LINHA = 1.0; // folga entre o para-choque e a linha de retenção

/** Aceleração do IDM para o espaço livre `gap` até o líder (ou obstáculo) com velocidade
    `vLider`. `gap = Infinity` é a via livre. */
export function aceleracaoIdm(v, gap, vLider, p, s0 = p.s0) {
  const livre = 1 - (v / p.v0) ** 4;
  if (gap === Infinity) return p.a * livre;
  const sEstrela = s0 + Math.max(0, v * p.T + (v * (v - vLider)) / (2 * Math.sqrt(p.a * p.b)));
  const espaco = Math.max(gap, 0.05);
  return p.a * (livre - (sEstrela / espaco) ** 2);
}

/** Frenagem necessária para parar antes de `distancia` metros, andando a `v`. */
export function frenagemNecessaria(v, distancia) {
  if (v <= 0) return 0;
  return (v * v) / (2 * Math.max(distancia, 0.1));
}

/** Atualização balística (Treiber & Kanagaraj): posição e velocidade após `dt`. */
export function integrar(s, v, a, dt) {
  const vNovo = v + a * dt;
  if (vNovo < 0) {
    return { s: s + (a < 0 ? -(v * v) / (2 * a) : 0), v: 0 };
  }
  return { s: s + v * dt + 0.5 * a * dt * dt, v: vNovo };
}

export const PALETAS = {
  carro: [
    ["#f1f1ee", 24],
    ["#b9bec4", 20],
    ["#1f2226", 15],
    ["#6c727a", 14],
    ["#a3271f", 8],
    ["#28467a", 8],
    ["#2f4b3d", 3],
    ["#c8b48a", 3],
    ["#d8d2c4", 2],
    ["#e2b33c", 2],
    ["#5b2f6e", 1],
  ],
  moto: [
    ["#c8382b", 1],
    ["#1f2226", 1],
    ["#2a5fa8", 1],
    ["#f1f1ee", 1],
    ["#e09a1a", 1],
  ],
  onibus: [
    ["#e9e7e1", 2],
    ["#f2b705", 1],
    ["#2a6fc9", 1],
    ["#1e8f4a", 1],
    ["#c8382b", 1],
  ],
  caminhao: [
    ["#c8382b", 1],
    ["#2a5fa8", 1],
    ["#f1f1ee", 1],
    ["#1e7a45", 1],
    ["#e09a1a", 1],
  ],
};
