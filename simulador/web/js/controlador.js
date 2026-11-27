/* Controlador semafórico simulado: executa o plano calculado pelo GSA, sem decidir tempos.

   Cada estágio cumpre verde → amarelo → vermelho de segurança (todas as vias no vermelho) e
   passa ao seguinte. Um plano novo fica pendente e só entra no fim do ciclo em andamento, depois
   do vermelho de segurança do último estágio, quando todas as vias estão fechadas — a transição
   segura de um controlador real. Antes de aceitar um plano, o monitor de conflitos confere que
   nenhum estágio abre movimentos que se cruzam e que os tempos respeitam os semáforos
   cadastrados (verde mínimo/máximo, amarelo e vermelho de segurança); durante a execução, se
   duas vias conflitantes estivessem abertas ao mesmo tempo, o controlador fecharia todas. */

import { conflitam } from "./geometria.js";

export const VERDE = "verde";
export const AMARELO = "amarelo";
export const VERMELHO = "vermelho";

const TOLERANCIA = 1e-9;

/** Confere se o plano pode ser executado com segurança. `eixos`: Map via -> eixo;
    `limites`: Map via -> semáforo cadastrado ({tempoMinimoVerde, ...}). */
export function validarPlano(plano, { eixos = null, limites = null } = {}) {
  const erros = [];
  if (!plano || !Array.isArray(plano.estagios) || plano.estagios.length === 0) {
    return { ok: false, erros: ["plano sem estágios"] };
  }
  const vistas = new Set();
  for (const e of plano.estagios) {
    const rotulo = e.rotulo || e.chave;
    if (!(e.verde > 0)) erros.push(`${rotulo}: verde deve ser positivo`);
    if (!(e.amarelo > 0)) erros.push(`${rotulo}: amarelo deve ser positivo`);
    if (!(e.vermelho >= 0)) erros.push(`${rotulo}: vermelho de segurança inválido`);
    if (!Array.isArray(e.vias) || e.vias.length === 0) erros.push(`${rotulo}: sem vias`);
    for (const via of e.vias || []) {
      if (vistas.has(via)) erros.push(`via ${via} aparece em mais de um estágio`);
      vistas.add(via);
    }
    if (eixos) {
      const doEstagio = (e.vias || []).map((v) => eixos.get(v)).filter(Boolean);
      for (let i = 0; i < doEstagio.length; i++) {
        for (let j = i + 1; j < doEstagio.length; j++) {
          if (conflitam(doEstagio[i], doEstagio[j])) {
            erros.push(`${rotulo}: abre ao mesmo tempo movimentos que se cruzam`);
            i = j = doEstagio.length;
          }
        }
      }
    }
    if (limites) {
      const semaforos = (e.vias || []).map((v) => limites.get(v)).filter(Boolean);
      if (semaforos.length) {
        // mesmas regras do motor (app/motor/estagios.py)
        const minimo = Math.max(...semaforos.map((s) => s.tempoMinimoVerde));
        const maximo = Math.max(minimo, Math.min(...semaforos.map((s) => s.tempoMaximoVerde)));
        const amarelo = Math.max(...semaforos.map((s) => s.tempoAmarelo));
        const vermelho = Math.max(...semaforos.map((s) => s.tempoVermelho));
        if (e.verde < minimo || e.verde > maximo) {
          erros.push(`${rotulo}: verde de ${e.verde} s fora do intervalo ${minimo}–${maximo} s`);
        }
        if (e.amarelo < amarelo) erros.push(`${rotulo}: amarelo menor que ${amarelo} s`);
        if (e.vermelho < vermelho) {
          erros.push(`${rotulo}: vermelho de segurança menor que ${vermelho} s`);
        }
      }
    }
  }
  return { ok: erros.length === 0, erros };
}

export function duracaoDoPlano(plano) {
  return plano.estagios.reduce((t, e) => t + e.verde + e.amarelo + e.vermelho, 0);
}

export class ControladorSemaforico {
  constructor({ plano, eixos = null, limites = null }) {
    this.eixos = eixos;
    this.limites = limites;
    const validacao = validarPlano(plano, { eixos, limites });
    if (!validacao.ok) throw new Error(`Plano inicial inválido: ${validacao.erros.join("; ")}`);
    this.plano = plano;
    this.pendente = null;
    this.indice = 0;
    this.fase = VERDE;
    this.tFase = 0;
    this.t = 0;
    this.inicioCiclo = 0;
    this.ciclos = 0;
    this.trocas = 0;
    this.rejeitados = [];
    this.falha = null;
  }

  get estagio() {
    return this.plano.estagios[this.indice];
  }

  duracaoDaFase() {
    return this.estagio[this.fase];
  }

  duracaoDoCiclo() {
    return duracaoDoPlano(this.plano);
  }

  /** Agenda o plano para o fim do ciclo em andamento (substitui um pendente mais antigo). */
  agendar(plano) {
    const validacao = validarPlano(plano, { eixos: this.eixos, limites: this.limites });
    if (!validacao.ok) {
      this.rejeitados.push({ t: this.t, plano, erros: validacao.erros });
      if (this.rejeitados.length > 20) this.rejeitados.shift();
      return validacao;
    }
    this.pendente = plano;
    return validacao;
  }

  avancar(dt) {
    this.t += dt;
    if (this.falha) return;
    this.tFase += dt;
    let guarda = 0;
    while (this.tFase >= this.duracaoDaFase() - TOLERANCIA && guarda++ < 64) {
      this.tFase -= this.duracaoDaFase();
      this.proximaFase();
    }
  }

  proximaFase() {
    if (this.fase === VERDE) {
      this.fase = AMARELO;
      return;
    }
    if (this.fase === AMARELO) {
      this.fase = VERMELHO;
      return;
    }
    this.fase = VERDE;
    this.indice++;
    if (this.indice < this.plano.estagios.length) return;
    // fim do ciclo: todas as vias estão no vermelho de segurança — momento seguro da troca
    this.indice = 0;
    this.ciclos++;
    this.inicioCiclo = this.t - Math.max(this.tFase, 0);
    if (this.pendente) {
      this.plano = this.pendente;
      this.pendente = null;
      this.trocas++;
    }
  }

  estadoDaVia(viaId) {
    if (this.falha || this.fase === VERMELHO) return VERMELHO;
    return this.estagio.vias.includes(viaId) ? this.fase : VERMELHO;
  }

  viasAbertas() {
    if (this.falha || this.fase === VERMELHO) return [];
    return [...this.estagio.vias];
  }

  /** Monitor de conflitos: com duas vias conflitantes abertas, fecha tudo (falha segura). */
  verificarConflitos() {
    if (this.falha || !this.eixos) return this.falha;
    const abertas = this.viasAbertas();
    for (let i = 0; i < abertas.length; i++) {
      for (let j = i + 1; j < abertas.length; j++) {
        const a = this.eixos.get(abertas[i]);
        const b = this.eixos.get(abertas[j]);
        if (a && b && conflitam(a, b)) {
          this.falha = {
            t: this.t,
            vias: [abertas[i], abertas[j]],
            mensagem: `vias ${abertas[i]} e ${abertas[j]} abertas ao mesmo tempo`,
          };
          return this.falha;
        }
      }
    }
    return null;
  }

  restanteDaFase() {
    return Math.max(0, this.duracaoDaFase() - this.tFase);
  }

  decorridoNoCiclo() {
    let soma = 0;
    for (let i = 0; i < this.indice; i++) {
      const e = this.plano.estagios[i];
      soma += e.verde + e.amarelo + e.vermelho;
    }
    const e = this.estagio;
    if (this.fase === AMARELO) soma += e.verde;
    if (this.fase === VERMELHO) soma += e.verde + e.amarelo;
    return soma + Math.max(this.tFase, 0);
  }

  /** Segundos até a via voltar ao verde (0 se está verde; estimativa com o plano atual). */
  segundosAteVerde(viaId) {
    const k = this.plano.estagios.findIndex((e) => e.vias.includes(viaId));
    if (k < 0) return null;
    if (k === this.indice && this.fase === VERDE) return 0;
    let inicio = 0;
    for (let i = 0; i < k; i++) {
      const e = this.plano.estagios[i];
      inicio += e.verde + e.amarelo + e.vermelho;
    }
    let falta = inicio - this.decorridoNoCiclo();
    if (falta <= 0) falta += this.duracaoDoCiclo();
    return falta;
  }
}
