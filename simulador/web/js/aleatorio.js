/* Números pseudoaleatórios reprodutíveis: a mesma semente gera a mesma sequência. */

/** Gerador mulberry32: rápido, 32 bits, suficiente para simulação. */
export function criarRng(semente) {
  let a = semente >>> 0 || 0x9e3779b9;
  return function rng() {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Semente derivada (FNV-1a): fluxos independentes, um por finalidade (ex.: chegadas da via 3). */
export function derivarSemente(semente, ...partes) {
  let h = 2166136261 >>> 0;
  const texto = [semente, ...partes].join(":");
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

/** Normal padrão (Box–Muller). */
export function normal(rng) {
  let u = 0;
  while (u === 0) u = rng();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * rng());
}

/** Quantidade de eventos de um processo de Poisson com a média dada (Knuth; normal se grande). */
export function poisson(rng, media) {
  if (!(media > 0)) return 0;
  if (media > 30) return Math.max(0, Math.round(media + Math.sqrt(media) * normal(rng)));
  const limite = Math.exp(-media);
  let k = 0;
  let p = rng();
  while (p > limite) {
    k++;
    p *= rng();
  }
  return k;
}

/** Índice sorteado com os pesos dados, usando o número uniforme `u` (0 ≤ u < 1). */
export function escolherPeso(pesos, u) {
  const total = pesos.reduce((soma, p) => soma + p, 0);
  let alvo = u * total;
  for (let i = 0; i < pesos.length; i++) {
    alvo -= pesos[i];
    if (alvo < 0) return i;
  }
  return pesos.length - 1;
}
