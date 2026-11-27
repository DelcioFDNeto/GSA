/* Geometria do cruzamento visto de cima, montada a partir das vias cadastradas no GSA.

   Metros; origem no centro do cruzamento; x para leste e y para o SUL (o mesmo sentido da tela
   e das coordenadas de imagem do YOLO). `direcao` da via é o sentido de circulação ("Avenida
   Central — sentido norte" anda para o norte). Mão de direção à direita: na avenida norte–sul o
   sentido norte fica a leste do eixo e o sentido sul a oeste; na leste–oeste, o sentido leste
   fica ao sul do eixo e o oeste ao norte. Cada via ocupa `quantidadeFaixas` faixas de 3,5 m.

   Cada faixa é uma reta da entrada (fora do quadro da câmera) até a saída, e a posição de um
   veículo é a distância `s` do seu para-choque dianteiro até a origem da faixa. */

export const LARGURA_FAIXA = 3.5;
export const CALCADA = 3.2;
export const RAIO_GRAMADO = 2.5; // raio da esquina do gramado; o meio-fio fica com este + calçada
export const AFASTAMENTO_PEDESTRES = 0.8; // da borda do cruzamento até a faixa de pedestres
export const LARGURA_PEDESTRES = 4.0;
export const FOLGA_RETENCAO = 1.2; // entre a faixa de pedestres e a linha de retenção
export const ESPESSURA_RETENCAO = 0.5;
/** Da borda do cruzamento até a face de montante da linha de retenção. */
export const RECUO_RETENCAO =
  AFASTAMENTO_PEDESTRES + LARGURA_PEDESTRES + FOLGA_RETENCAO + ESPESSURA_RETENCAO;
// Metros de aproximação dentro do quadro da câmera. Precisa caber a fila normal de pico: se a
// fila passa da borda do quadro, a câmera deixa de ver as chegadas (subconta) e depois vê a
// fila acumulada de uma vez (sobreconta). O zoom do desenho é independente disto.
export const APROXIMACAO_VISIVEL = 72;
// Duas formas de desenhar a zona de cada via (a contagem é sempre a de deteccao/zonas.py):
// - aproximacao (padrão): da borda do quadro até a retenção, como as zonas do contador YOLO.
//   Conta quem passou OU esperou na janela; quem espera mais de uma janela conta de novo. Isso
//   superestima o fluxo de chegada, mas é o único sinal de fila acumulada que chega ao GSA;
// - entrada: faixa de 16 m na entrada do quadro ("laço virtual"). Cada veículo passa uma vez,
//   então a janela conta as chegadas — o q exato do Webster — enquanto a fila cabe no quadro;
//   com fila além do quadro, a câmera só vê a descarga e o GSA não percebe o acúmulo.
// Com 16 m e 2 quadros/s, até uma moto a 55 km/h é vista em pelo menos dois quadros.
export const RECUO_FAIXA_CONTAGEM = 3;
export const COMPRIMENTO_FAIXA_CONTAGEM = 16;
export const MODO_ZONA_PADRAO = "aproximacao";
export const ENTRADA_FORA_DO_QUADRO = 70; // os veículos nascem antes do quadro, já em movimento
export const SAIDA_FORA_DO_QUADRO = 25;

export const SENTIDOS = {
  norte: { eixo: "ns", dx: 0, dy: -1, seta: "↑", nome: "Norte" },
  sul: { eixo: "ns", dx: 0, dy: 1, seta: "↓", nome: "Sul" },
  leste: { eixo: "lo", dx: 1, dy: 0, seta: "→", nome: "Leste" },
  oeste: { eixo: "lo", dx: -1, dy: 0, seta: "←", nome: "Oeste" },
};
const ORDEM_SENTIDOS = ["norte", "sul", "leste", "oeste"];

/** Faixas de um eixo: duas mãos com canteiro (pintado ou ajardinado) ou mão única centrada. */
function montarEixo(faixasNegativo, faixasPositivo) {
  const w = LARGURA_FAIXA;
  if (faixasNegativo === 0 && faixasPositivo === 0) {
    return { existe: false, duasMaos: false, canteiro: 0, tipoCanteiro: null, min: 0, max: 0 };
  }
  if (faixasNegativo > 0 && faixasPositivo > 0) {
    const ajardinado = Math.max(faixasNegativo, faixasPositivo) >= 3;
    const canteiro = ajardinado ? 2.4 : 0.5;
    return {
      existe: true,
      duasMaos: true,
      canteiro,
      tipoCanteiro: ajardinado ? "ajardinado" : "pintado",
      min: -(canteiro / 2 + faixasNegativo * w),
      max: canteiro / 2 + faixasPositivo * w,
    };
  }
  const meia = ((faixasNegativo + faixasPositivo) * w) / 2;
  return { existe: true, duasMaos: false, canteiro: 0, tipoCanteiro: null, min: -meia, max: meia };
}

/** Ponto da faixa a `s` metros da origem. */
export function pontoDaFaixa(faixa, s) {
  return { x: faixa.origem.x + faixa.dx * s, y: faixa.origem.y + faixa.dy * s };
}

/** Ponto a `s` metros da origem e deslocado lateralmente para a coordenada `lateral`. */
function pontoLateral(faixa, s, lateral) {
  const p = pontoDaFaixa(faixa, s);
  return faixa.eixo === "ns" ? { x: lateral, y: p.y } : { x: p.x, y: lateral };
}

/** Retângulo (x, y, largura, altura) entre `s0` e `s1` ao longo da faixa e duas laterais. */
function retangulo(faixa, s0, s1, lateral0, lateral1) {
  const a = pontoLateral(faixa, s0, lateral0);
  const b = pontoLateral(faixa, s1, lateral1);
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    largura: Math.abs(a.x - b.x),
    altura: Math.abs(a.y - b.y),
  };
}

export function montarGeometria(vias) {
  const avisos = [];
  const porSentido = { norte: [], sul: [], leste: [], oeste: [] };
  for (const via of [...vias].sort((a, b) => a.id - b.id)) {
    if (!SENTIDOS[via.direcao]) {
      avisos.push(`${via.nome}: direção '${via.direcao}' não é desenhada (sem leitura).`);
      continue;
    }
    porSentido[via.direcao].push(via);
  }
  const faixasDe = (sentido) => porSentido[sentido].reduce((t, v) => t + v.quantidadeFaixas, 0);
  // eixo norte–sul: lado negativo (x < 0) = sentido sul; eixo leste–oeste: lado y < 0 = oeste
  const ns = montarEixo(faixasDe("sul"), faixasDe("norte"));
  const lo = montarEixo(faixasDe("oeste"), faixasDe("leste"));
  const extensao = Math.max(Math.abs(ns.min), ns.max, Math.abs(lo.min), lo.max);
  const meio = Math.ceil((extensao + RECUO_RETENCAO + APROXIMACAO_VISIVEL) * 2) / 2;
  const caixa = { x0: ns.min, x1: ns.max, y0: lo.min, y1: lo.max };
  const comprimento = 2 * meio + ENTRADA_FORA_DO_QUADRO + SAIDA_FORA_DO_QUADRO;

  const faixas = [];
  const viasGeo = [];
  for (const sentido of ORDEM_SENTIDOS) {
    const info = SENTIDOS[sentido];
    const eixo = info.eixo === "ns" ? ns : lo;
    const outro = info.eixo === "ns" ? lo : ns;
    // componente lateral do vetor "esquerda do motorista" (dy, −dx)
    const sinalEsquerda = info.eixo === "ns" ? info.dy : -info.dx;
    // borda do cruzamento encontrada primeiro (coordenada de deslocamento p = dx·x + dy·y)
    const [a, b] = info.eixo === "ns" ? [info.dy * lo.min, info.dy * lo.max] : [info.dx * ns.min, info.dx * ns.max];
    const sEntrada = Math.min(a, b) + meio + ENTRADA_FORA_DO_QUADRO;
    const sSaida = Math.max(a, b) + meio + ENTRADA_FORA_DO_QUADRO;
    let k = 0;
    let ordemNoSentido = 0;
    for (const via of porSentido[sentido]) {
      const daVia = [];
      for (let j = 0; j < via.quantidadeFaixas; j++, k++) {
        const lateral = eixo.duasMaos
          ? -sinalEsquerda * (eixo.canteiro / 2 + (k + 0.5) * LARGURA_FAIXA)
          : sinalEsquerda * (eixo.max - (k + 0.5) * LARGURA_FAIXA);
        const origem =
          info.eixo === "ns"
            ? { x: lateral, y: -info.dy * (meio + ENTRADA_FORA_DO_QUADRO) }
            : { x: -info.dx * (meio + ENTRADA_FORA_DO_QUADRO), y: lateral };
        const faixa = {
          id: `${via.id}:${j}`,
          viaId: via.id,
          sentido,
          eixo: info.eixo,
          indice: j,
          lateral,
          origem,
          dx: info.dx,
          dy: info.dy,
          angulo: Math.atan2(info.dy, info.dx),
          comprimento,
          sEntrada,
          sSaida,
          sParada: sEntrada - RECUO_RETENCAO,
          sQuadroInicio: ENTRADA_FORA_DO_QUADRO,
          sQuadroFim: ENTRADA_FORA_DO_QUADRO + 2 * meio,
        };
        faixas.push(faixa);
        daVia.push(faixa);
      }
      const laterais = daVia.map((f) => f.lateral);
      const lateralMin = Math.min(...laterais) - LARGURA_FAIXA / 2;
      const lateralMax = Math.max(...laterais) + LARGURA_FAIXA / 2;
      const ref = daVia[0];
      const retencao = retangulo(ref, ref.sParada, ref.sParada + ESPESSURA_RETENCAO, lateralMin, lateralMax);
      // zonas de contagem sobre as faixas da via, em metros e normalizadas (0 a 1) no quadro
      const normalizar = ([x, y]) => [
        Math.min(1, Math.max(0, (x + meio) / (2 * meio))),
        Math.min(1, Math.max(0, (y + meio) / (2 * meio))),
      ];
      const zona = (s0, s1) => {
        const z = retangulo(ref, s0, s1, lateralMin, lateralMax);
        const mundo = [
          [z.x, z.y],
          [z.x + z.largura, z.y],
          [z.x + z.largura, z.y + z.altura],
          [z.x, z.y + z.altura],
        ];
        return { mundo, normalizada: mundo.map(normalizar) };
      };
      const inicioFaixa = ref.sQuadroInicio + RECUO_FAIXA_CONTAGEM;
      const zonas = {
        entrada: zona(inicioFaixa, inicioFaixa + COMPRIMENTO_FAIXA_CONTAGEM),
        aproximacao: zona(ref.sQuadroInicio, ref.sParada + ESPESSURA_RETENCAO),
      };
      // grupo focal na calçada à direita do motorista, alinhado à linha de retenção
      const sinalDireita = -sinalEsquerda;
      const borda = sinalDireita > 0 ? eixo.max : eixo.min;
      const semaforo = pontoLateral(
        ref,
        ref.sParada + ESPESSURA_RETENCAO / 2 - ordemNoSentido * 3.2,
        borda + sinalDireita * CALCADA * 0.48,
      );
      viasGeo.push({
        id: via.id,
        nome: via.nome,
        nomeCurto: nomeCurto(via.nome, sentido),
        sentido,
        eixo: info.eixo,
        seta: info.seta,
        quantidadeFaixas: via.quantidadeFaixas,
        estagio: via.estagio ?? null,
        faixas: daVia.map((f) => f.id),
        lateralMin,
        lateralMax,
        retencao,
        zonas,
        semaforo: { ...semaforo, angulo: ref.angulo },
        cruza: outro.existe,
      });
      ordemNoSentido++;
    }
  }
  return { meio, tamanho: 2 * meio, ns, lo, caixa, faixas, vias: viasGeo, avisos };
}

/** "Avenida Central — sentido norte" -> "Avenida Central"; sem o separador, o nome todo. */
export function nomeCurto(nome, sentido) {
  const base = String(nome).split(" — ")[0].trim();
  return base || SENTIDOS[sentido]?.nome || nome;
}

/** Faixa de pedestres de cada perna existente (retângulo e orientação das listras). */
export function faixasDePedestres(geo) {
  const { ns, lo, caixa } = geo;
  const resultado = [];
  const d0 = AFASTAMENTO_PEDESTRES;
  const d1 = AFASTAMENTO_PEDESTRES + LARGURA_PEDESTRES;
  if (ns.existe) {
    resultado.push({ x: caixa.x0, y: caixa.y0 - d1, largura: caixa.x1 - caixa.x0, altura: d1 - d0, listras: "verticais" });
    resultado.push({ x: caixa.x0, y: caixa.y1 + d0, largura: caixa.x1 - caixa.x0, altura: d1 - d0, listras: "verticais" });
  }
  if (lo.existe) {
    resultado.push({ x: caixa.x0 - d1, y: caixa.y0, largura: d1 - d0, altura: caixa.y1 - caixa.y0, listras: "horizontais" });
    resultado.push({ x: caixa.x1 + d0, y: caixa.y0, largura: d1 - d0, altura: caixa.y1 - caixa.y0, listras: "horizontais" });
  }
  return resultado;
}

/** Eixo de cada via: movimentos em linha reta de eixos diferentes se cruzam. */
export function eixosDasVias(geo) {
  return new Map(geo.vias.map((v) => [v.id, v.eixo]));
}

export function conflitam(eixoA, eixoB) {
  return eixoA !== eixoB;
}
