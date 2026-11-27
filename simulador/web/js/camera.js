/* Câmera sintética: produz, a partir dos veículos da simulação, o que o YOLO + ByteTrack
   entregariam em cada quadro processado — caixa (normalizada, eixo y para baixo), classe COCO,
   id de rastreamento persistente e confiança. Não roda modelo nenhum: a contagem enviada ao GSA
   sai exatamente dos veículos que estão na tela.

   Para parecer uma detecção real: as caixas têm um pequeno ruído que varia devagar, a confiança
   cai para veículos cortados pela borda do quadro, motos às vezes não são detectadas em um quadro
   e ônibus/caminhões às vezes são confundidos. O id de rastreamento nasce na primeira detecção e
   acompanha o veículo até ele sair, como o ByteTrack. */

import { criarRng, derivarSemente, normal } from "./aleatorio.js";

export const INTERVALO_CAMERA = 0.5; // s simulados entre quadros processados (2 quadros/s)
const VISIBILIDADE_MINIMA = 0.35;
const CONFIANCA_BASE = { car: 0.9, motorcycle: 0.74, bus: 0.92, truck: 0.84 };
const PERDA_POR_QUADRO = { car: 0.02, motorcycle: 0.07, bus: 0.01, truck: 0.02 };
const CONFUSAO = { bus: ["truck", 0.04], truck: ["bus", 0.03], car: ["truck", 0.006] };
const RUIDO_RELATIVO = 0.035;
const arredondar = (valor, casas) => Math.round(valor * 10 ** casas) / 10 ** casas;

function caixaDoVeiculo(f, v, s) {
  const c = s - v.L / 2;
  const x = f.origem.x + f.dx * c;
  const y = f.origem.y + f.dy * c;
  const [mx, my] = f.eixo === "ns" ? [v.W / 2, v.L / 2] : [v.L / 2, v.W / 2];
  return { x0: x - mx, y0: y - my, x1: x + mx, y1: y + my };
}

function fracaoVisivel(c, meio) {
  const largura = Math.max(0, Math.min(c.x1, meio) - Math.max(c.x0, -meio));
  const altura = Math.max(0, Math.min(c.y1, meio) - Math.max(c.y0, -meio));
  return (largura * altura) / ((c.x1 - c.x0) * (c.y1 - c.y0));
}

export class CameraSintetica {
  constructor({ geometria, semente, confiancaMinima = 0.3, classes = null }) {
    this.meio = geometria.meio;
    this.rng = criarRng(derivarSemente(semente, "camera"));
    this.confiancaMinima = confiancaMinima;
    this.classes = classes ? new Set(classes) : null;
    this.trilhas = new Map(); // id do veículo -> trilha do rastreador
    this.proximoId = 1;
    this.ultimoQuadro = null;
  }

  /** Processa um quadro no instante simulado `t`: [id, classe, x1, y1, x2, y2, confiança]. */
  capturar(sim, t) {
    const meio = this.meio;
    const lado = 2 * meio;
    const deteccoes = [];
    const vivos = new Set();
    for (const f of sim.faixas) {
      for (const v of f.veiculos) {
        vivos.add(v.id);
        const caixa = caixaDoVeiculo(f, v, v.s);
        const visivel = fracaoVisivel(caixa, meio);
        if (visivel < VISIBILIDADE_MINIMA) continue;
        if (this.rng() < PERDA_POR_QUADRO[v.classe]) continue; // não detectado neste quadro
        let classe = v.classe;
        const [outra, chance] = CONFUSAO[v.classe] || [null, 0];
        if (outra && this.rng() < chance) classe = outra;
        const confianca = Math.min(
          0.99,
          Math.max(0.05, CONFIANCA_BASE[v.classe] + 0.04 * normal(this.rng) - (1 - visivel) * 0.35),
        );
        if (confianca < this.confiancaMinima) continue;
        if (this.classes && !this.classes.has(classe)) continue;
        let trilha = this.trilhas.get(v.id);
        if (!trilha) {
          trilha = { id: this.proximoId++, ruido: [0, 0, 0, 0] };
          this.trilhas.set(v.id, trilha);
        }
        const dimensoes = [caixa.x1 - caixa.x0, caixa.y1 - caixa.y0];
        for (let k = 0; k < 4; k++) {
          trilha.ruido[k] =
            0.65 * trilha.ruido[k] + 0.35 * normal(this.rng) * RUIDO_RELATIVO * dimensoes[k % 2];
        }
        trilha.classe = classe;
        trilha.confianca = confianca;
        trilha.vistoEm = t;
        const x1 = Math.max(-meio, caixa.x0 + trilha.ruido[0]);
        const y1 = Math.max(-meio, caixa.y0 + trilha.ruido[1]);
        const x2 = Math.min(meio, caixa.x1 + trilha.ruido[2]);
        const y2 = Math.min(meio, caixa.y1 + trilha.ruido[3]);
        deteccoes.push([
          trilha.id,
          classe,
          arredondar((x1 + meio) / lado, 4),
          arredondar((y1 + meio) / lado, 4),
          arredondar((x2 + meio) / lado, 4),
          arredondar((y2 + meio) / lado, 4),
          arredondar(confianca, 3),
        ]);
      }
    }
    for (const id of this.trilhas.keys()) if (!vivos.has(id)) this.trilhas.delete(id);
    this.ultimoQuadro = { t: arredondar(t, 3), deteccoes };
    return this.ultimoQuadro;
  }

  /** Caixas para desenhar agora (posição interpolada), com a última classe e confiança. */
  caixasParaDesenho(sim, alpha, t) {
    const caixas = [];
    for (const f of sim.faixas) {
      for (const v of f.veiculos) {
        const trilha = this.trilhas.get(v.id);
        if (!trilha || t - trilha.vistoEm > 2 * INTERVALO_CAMERA) continue;
        const s = v.sAnterior + (v.s - v.sAnterior) * alpha;
        const c = caixaDoVeiculo(f, v, s);
        caixas.push({
          x0: Math.max(-this.meio, c.x0 + trilha.ruido[0]),
          y0: Math.max(-this.meio, c.y0 + trilha.ruido[1]),
          x1: Math.min(this.meio, c.x1 + trilha.ruido[2]),
          y1: Math.min(this.meio, c.y1 + trilha.ruido[3]),
          id: trilha.id,
          classe: trilha.classe,
          confianca: trilha.confianca,
          viaId: v.viaId,
        });
      }
    }
    return caixas;
  }
}
