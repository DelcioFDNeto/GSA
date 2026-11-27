/* Simulação microscópica de um cruzamento: cada veículo é uma entidade com posição, velocidade,
   classe, faixa e tempo de espera, e decide a cada passo como acelerar.

   Regras de cada passo (dt fixo, em tempo simulado):
   - chegadas entram na fila de entrada da via e nascem fora do quadro, na faixa com mais espaço;
   - aceleração pelo IDM em relação ao veículo da frente (distância de segurança, sem sobreposição);
   - semáforo vermelho = obstáculo parado na linha de retenção; no amarelo, para quem consegue
     frear com conforto e segue quem já não conseguiria parar antes da linha;
   - com verde, só entra no cruzamento se nenhum veículo do movimento conflitante ainda estiver
     dentro dele e se houver espaço depois dele (não bloquear o cruzamento);
   - parado, o motorista leva um tempo de reação para arrancar: a fila sai em onda, gradualmente;
   - quem passa da área simulada é removido. */

import { VERDE, AMARELO, VERMELHO, ControladorSemaforico } from "./controlador.js";
import { pontoDaFaixa } from "./geometria.js";
import {
  DISTANCIA_LINHA,
  FRENAGEM_MAXIMA,
  FRENAGEM_VERMELHO,
  LIMITE_FILA,
  LIMITE_PARADO,
  TIPOS,
  aceleracaoIdm,
  frenagemNecessaria,
  integrar,
} from "./veiculos.js";

const AMOSTRA_ESTATISTICA = 1; // s simulados entre amostras de fila
const AMOSTRA_SERIE = 5; // s simulados entre pontos da série temporal
const MAX_SERIE = 720; // uma hora de série
const ESPACO_MINIMO_ENTRADA = 2.5; // m livres atrás do último veículo para nascer outro
const VIA_LIVRE = 60; // m: acima disso a faixa é considerada vazia na escolha de faixa
const ALCANCE_COMPROMISSO = 8; // m antes da linha: quem já vai entrar ocupa o cruzamento
const ALCANCE_BLOQUEIO = 40; // m antes da linha: onde a regra de não bloquear vale

function novaEstatisticaVia() {
  return {
    chegadas: 0,
    servidos: 0,
    esperaServidos: 0,
    esperaMaxima: 0,
    filaSoma: 0,
    filaMaxima: 0,
    amostras: 0,
  };
}

export class SimulacaoCruzamento {
  constructor({ geometria, plano, eixos = null, limites = null, rotulo = "B" }) {
    this.geo = geometria;
    this.rotulo = rotulo;
    this.faixas = geometria.faixas.map((f) => ({ ...f, veiculos: [] }));
    this.viaIds = geometria.vias.map((v) => v.id);
    this.faixasDaVia = new Map(this.viaIds.map((id) => [id, []]));
    for (const f of this.faixas) this.faixasDaVia.get(f.viaId).push(f);
    this.esperando = new Map(this.viaIds.map((id) => [id, []]));
    this.controlador = new ControladorSemaforico({ plano, eixos, limites });
    this.estados = new Map(this.viaIds.map((id) => [id, this.controlador.estadoDaVia(id)]));
    this.t = 0;
    this.passos = 0;
    this.correcoes = 0; // vezes que a trava anti-sobreposição agiu (o IDM deve manter em 0)
    this.saidos = 0;
    this.estat = {
      porVia: new Map(this.viaIds.map((id) => [id, novaEstatisticaVia()])),
      chegadas: 0,
      servidos: 0,
      esperaServidos: 0,
      esperaMaxima: 0,
      filaSoma: 0,
      filaMaxima: 0,
      amostras: 0,
      serie: [],
    };
    this.proximaAmostra = AMOSTRA_ESTATISTICA;
    this.proximaSerie = 0;
  }

  /** Avança `dt` segundos simulados com as chegadas do intervalo. */
  passo(dt, eventos = []) {
    this.passos++;
    this.t = this.passos * dt;
    const ctrl = this.controlador;
    ctrl.avancar(dt);
    for (const id of this.viaIds) {
      const novo = ctrl.estadoDaVia(id);
      if (novo === VERDE && this.estados.get(id) !== VERDE) this.liberarDecisoes(id);
      this.estados.set(id, novo);
    }
    for (const ev of eventos) {
      const fila = this.esperando.get(ev.viaId);
      if (!fila) continue;
      fila.push({ evento: ev, espera: Math.max(0, this.t - ev.t) });
      this.estat.chegadas++;
      this.estat.porVia.get(ev.viaId).chegadas++;
    }
    this.lancar();
    const ocupacao = this.ocupacaoDaCaixa();
    for (const faixa of this.faixas) this.calcularAceleracoes(faixa, ocupacao);
    for (const faixa of this.faixas) this.mover(faixa, dt);
    for (const fila of this.esperando.values()) for (const item of fila) item.espera += dt;
    ctrl.verificarConflitos();
    if (this.t + 1e-9 >= this.proximaAmostra) {
      this.amostrar();
      this.proximaAmostra += AMOSTRA_ESTATISTICA;
    }
  }

  liberarDecisoes(viaId) {
    for (const f of this.faixasDaVia.get(viaId)) {
      for (const v of f.veiculos) if (!v.cruzou) v.decisao = null;
    }
  }

  /** Tira da fila de entrada os veículos que cabem; no máximo um por faixa a cada passo. */
  lancar() {
    for (const [viaId, fila] of this.esperando) {
      if (!fila.length) continue;
      const usadas = new Set();
      while (fila.length) {
        const item = fila[0];
        const tipo = TIPOS[item.evento.tipo];
        const livres = [];
        for (const f of this.faixasDaVia.get(viaId)) {
          if (usadas.has(f)) continue;
          const ultimo = f.veiculos[f.veiculos.length - 1];
          const espaco = ultimo ? ultimo.s - ultimo.L - tipo.comprimento : Infinity;
          if (espaco >= ESPACO_MINIMO_ENTRADA) livres.push({ f, espaco, ultimo });
        }
        if (!livres.length) break;
        // o motorista escolhe a faixa mais vazia; entre faixas vazias, sorteio da chegada
        const vazias = livres.filter((l) => l.espaco > VIA_LIVRE);
        const escolha =
          vazias.length > 1
            ? vazias[Math.min(vazias.length - 1, Math.floor(item.evento.desempate * vazias.length))]
            : livres.reduce((a, b) => (b.espaco > a.espaco ? b : a));
        fila.shift();
        usadas.add(escolha.f);
        this.criarVeiculo(item, escolha);
      }
    }
  }

  criarVeiculo(item, { f, espaco, ultimo }) {
    const ev = item.evento;
    const tipo = TIPOS[ev.tipo];
    const v0 = tipo.v0 * ev.fatorVelocidade;
    let v = v0;
    if (ultimo) v = Math.min(v0, ultimo.v + 3, Math.max(0, (espaco - tipo.s0) / tipo.T));
    f.veiculos.push({
      id: ev.id,
      tipo: ev.tipo,
      classe: tipo.classe,
      L: tipo.comprimento,
      W: tipo.largura,
      v0,
      p: { ...tipo, v0 },
      cor: ev.cor,
      corSecundaria: ev.corSecundaria,
      reacao: ev.reacao,
      viaId: ev.viaId,
      faixaId: f.id,
      s: tipo.comprimento,
      sAnterior: tipo.comprimento,
      v,
      acel: 0,
      tChegada: ev.t,
      tEntrada: this.t,
      espera: item.espera,
      decisao: null, // null | "parar" | "seguir" (diante do amarelo/vermelho)
      cruzou: false,
      tCruzou: null,
      prontoEm: null,
    });
  }

  /** Há veículo de cada eixo dentro do cruzamento (ou prestes a entrar, já comprometido)? */
  ocupacaoDaCaixa() {
    const ocupado = { ns: false, lo: false };
    for (const f of this.faixas) {
      if (ocupado[f.eixo]) continue;
      for (const v of f.veiculos) {
        if (v.s - v.L >= f.sSaida) continue; // já saiu do cruzamento
        if (v.s > f.sParada || (v.decisao === "seguir" && f.sParada - v.s < ALCANCE_COMPROMISSO)) {
          ocupado[f.eixo] = true;
        }
        break; // os demais estão mais atrás
      }
    }
    return ocupado;
  }

  calcularAceleracoes(faixa, ocupacao) {
    const estado = this.estados.get(faixa.viaId);
    const conflitoNaCaixa = ocupacao[faixa.eixo === "ns" ? "lo" : "ns"];
    const veiculos = faixa.veiculos;
    for (let i = 0; i < veiculos.length; i++) {
      const v = veiculos[i];
      const lider = i > 0 ? veiculos[i - 1] : null;
      const p = v.p;
      let a = lider
        ? aceleracaoIdm(v.v, lider.s - lider.L - v.s, lider.v, p)
        : aceleracaoIdm(v.v, Infinity, 0, p);
      if (!v.cruzou) {
        const distancia = faixa.sParada - v.s;
        if (this.deveParar(v, estado, distancia, lider, faixa, conflitoNaCaixa)) {
          a = Math.min(a, aceleracaoIdm(v.v, distancia, 0, p, DISTANCIA_LINHA));
        }
      }
      // tempo de reação na partida: parado, só arranca depois de `reacao` segundos
      if (v.v < 0.1) {
        if (a > 0.05) {
          if (v.prontoEm === null) v.prontoEm = this.t + v.reacao;
          if (this.t < v.prontoEm) a = 0;
        } else {
          v.prontoEm = null;
        }
      } else {
        v.prontoEm = null;
      }
      v.acel = Math.max(-FRENAGEM_MAXIMA, Math.min(a, p.a));
    }
  }

  deveParar(v, estado, distancia, lider, faixa, conflitoNaCaixa) {
    if (estado === VERMELHO) {
      // quem seguiu no amarelo mas ficou para trás (ex.: atrás de um ônibus) ainda para
      if (
        v.decisao === "seguir" &&
        frenagemNecessaria(v.v, distancia - DISTANCIA_LINHA) <= FRENAGEM_VERMELHO
      ) {
        v.decisao = "parar";
      }
      return v.decisao !== "seguir";
    }
    if (estado === AMARELO) {
      if (v.decisao === null) {
        v.decisao =
          frenagemNecessaria(v.v, distancia - 0.3) <= v.p.bAmarelo ? "parar" : "seguir";
      } else if (
        v.decisao === "seguir" &&
        frenagemNecessaria(v.v, distancia - DISTANCIA_LINHA) <= 0.8 * v.p.bAmarelo
      ) {
        v.decisao = "parar";
      }
      return v.decisao === "parar";
    }
    if (distancia > ALCANCE_BLOQUEIO) return false;
    if (conflitoNaCaixa) return true; // retardatário do outro estágio ainda cruzando
    // não bloquear o cruzamento: a fila depois dele precisa ter espaço para este veículo
    return Boolean(
      lider && lider.cruzou && lider.v < LIMITE_FILA && lider.s - lider.L < faixa.sSaida + v.L + 1.5,
    );
  }

  mover(faixa, dt) {
    const vs = faixa.veiculos;
    let lider = null;
    for (const v of vs) {
      v.sAnterior = v.s;
      const novo = integrar(v.s, v.v, v.acel, dt);
      v.s = novo.s;
      v.v = novo.v;
      if (lider) {
        const limite = lider.s - lider.L - 0.05;
        if (v.s > limite) {
          this.correcoes++;
          v.s = Math.max(v.sAnterior, limite);
          v.v = Math.min(v.v, lider.v);
        }
      }
      if (!v.cruzou) {
        if (v.v < LIMITE_PARADO) v.espera += dt;
        if (v.s > faixa.sParada) {
          v.cruzou = true;
          v.tCruzou = this.t;
          this.registrarTravessia(v);
        }
      }
      lider = v;
    }
    while (vs.length && vs[0].s - vs[0].L > faixa.comprimento) {
      vs.shift();
      this.saidos++;
    }
  }

  registrarTravessia(v) {
    const e = this.estat.porVia.get(v.viaId);
    e.servidos++;
    e.esperaServidos += v.espera;
    e.esperaMaxima = Math.max(e.esperaMaxima, v.espera);
    this.estat.servidos++;
    this.estat.esperaServidos += v.espera;
    this.estat.esperaMaxima = Math.max(this.estat.esperaMaxima, v.espera);
  }

  /** Situação atual de uma via: veículos na aproximação (inclusive aguardando entrada). */
  medirVia(viaId) {
    let presentes = 0;
    let parados = 0;
    let fila = 0;
    let filaMetros = 0;
    let esperaAtual = 0;
    let visiveis = 0;
    const faixas = this.faixasDaVia.get(viaId);
    for (const f of faixas) {
      for (const v of f.veiculos) {
        if (v.cruzou) continue;
        presentes++;
        if (v.s > f.sQuadroInicio) visiveis++;
        if (v.v < LIMITE_PARADO) parados++;
        if (v.v < LIMITE_FILA) {
          fila++;
          filaMetros = Math.max(filaMetros, f.sParada - (v.s - v.L));
        }
        esperaAtual += v.espera;
      }
    }
    const aguardando = this.esperando.get(viaId);
    if (aguardando.length) {
      filaMetros = Math.max(filaMetros, faixas[0].sParada) + (aguardando.length * 7) / faixas.length;
    }
    for (const item of aguardando) esperaAtual += item.espera;
    return {
      presentes: presentes + aguardando.length,
      visiveis,
      parados: parados + aguardando.length,
      fila: fila + aguardando.length,
      filaMetros,
      aguardandoEntrada: aguardando.length,
      esperaAtual,
    };
  }

  amostrar() {
    let filaTotal = 0;
    for (const id of this.viaIds) {
      const { fila } = this.medirVia(id);
      const e = this.estat.porVia.get(id);
      e.filaSoma += fila;
      e.filaMaxima = Math.max(e.filaMaxima, fila);
      e.amostras++;
      this.estat.filaSoma += fila;
      this.estat.filaMaxima = Math.max(this.estat.filaMaxima, fila);
      this.estat.amostras++;
      filaTotal += fila;
    }
    if (this.t + 1e-9 >= this.proximaSerie) {
      this.estat.serie.push({ t: this.t, fila: filaTotal, espera: this.esperaAcumulada() });
      if (this.estat.serie.length > MAX_SERIE) this.estat.serie.shift();
      this.proximaSerie += AMOSTRA_SERIE;
    }
  }

  /** Espera de todos os veículos que já chegaram: atendidos e ainda na aproximação. */
  esperaAcumulada() {
    let soma = this.estat.esperaServidos;
    for (const f of this.faixas) for (const v of f.veiculos) if (!v.cruzou) soma += v.espera;
    for (const fila of this.esperando.values()) for (const item of fila) soma += item.espera;
    return soma;
  }

  resumo() {
    const e = this.estat;
    const porVia = this.viaIds.map((id) => {
      const via = e.porVia.get(id);
      return {
        id,
        ...this.medirVia(id),
        servidos: via.servidos,
        chegadas: via.chegadas,
        esperaMedia: via.servidos ? via.esperaServidos / via.servidos : 0,
        esperaMaxima: via.esperaMaxima,
        filaMedia: via.amostras ? via.filaSoma / via.amostras : 0,
        filaMaxima: via.filaMaxima,
      };
    });
    return {
      t: this.t,
      chegadas: e.chegadas,
      servidos: e.servidos,
      esperaMedia: e.servidos ? e.esperaServidos / e.servidos : 0,
      esperaMaxima: e.esperaMaxima,
      esperaAcumulada: this.esperaAcumulada(),
      filaMedia: e.amostras ? e.filaSoma / e.amostras : 0,
      filaMaxima: e.filaMaxima,
      vazao: this.t > 0 ? (e.servidos / this.t) * 3600 : 0,
      noSistema: porVia.reduce((t, v) => t + v.presentes, 0),
      porVia,
    };
  }

  /** Retângulo ocupado pelo veículo (os sentidos são alinhados aos eixos). */
  retangulo(f, v, s = v.s) {
    const p = pontoDaFaixa(f, s - v.L / 2);
    const [mx, my] = f.eixo === "ns" ? [v.W / 2, v.L / 2] : [v.L / 2, v.W / 2];
    return { x0: p.x - mx, x1: p.x + mx, y0: p.y - my, y1: p.y + my };
  }

  *veiculos() {
    for (const f of this.faixas) for (const v of f.veiculos) yield { v, f };
  }

  /** Verificação de segurança: sobreposição na mesma faixa ou entre movimentos que se cruzam. */
  sobreposicoes() {
    const problemas = [];
    for (const f of this.faixas) {
      for (let i = 1; i < f.veiculos.length; i++) {
        const a = f.veiculos[i - 1];
        const b = f.veiculos[i];
        if (a.s - a.L - b.s < -1e-6) problemas.push({ tipo: "mesma faixa", a: a.id, b: b.id });
      }
    }
    const { caixa } = this.geo;
    const perto = [];
    for (const { v, f } of this.veiculos()) {
      const r = this.retangulo(f, v);
      if (r.x1 > caixa.x0 - 1 && r.x0 < caixa.x1 + 1 && r.y1 > caixa.y0 - 1 && r.y0 < caixa.y1 + 1) {
        perto.push({ id: v.id, eixo: f.eixo, r });
      }
    }
    for (let i = 0; i < perto.length; i++) {
      for (let j = i + 1; j < perto.length; j++) {
        const a = perto[i];
        const b = perto[j];
        if (a.eixo === b.eixo) continue;
        if (a.r.x0 < b.r.x1 && b.r.x0 < a.r.x1 && a.r.y0 < b.r.y1 && b.r.y0 < a.r.y1) {
          problemas.push({ tipo: "cruzamento", a: a.id, b: b.id });
        }
      }
    }
    return problemas;
  }
}
