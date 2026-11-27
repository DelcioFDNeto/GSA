/* Comunicação com o servidor do simulador (/simulador/api), sempre assíncrona: a animação nunca
   espera a rede. A chave do sistema de detecção não passa por aqui — fica no servidor.

   A PonteGSA envia os quadros da câmera sintética em lotes (no máximo um pedido em voo), faz o
   reenvio com espera crescente quando a rede falha, entrega ao controlador cada plano novo
   calculado pelo GSA e, se o GSA ficar sem responder por mais de duas janelas e um ciclo, volta
   ao plano fixo local — como um controlador real que perde a comunicação com a central. */

export const INTERVALO_ENVIO_MS = 500;
export const MAX_QUADROS_POR_ENVIO = 200; // o servidor aceita até 240
export const TEMPO_LIMITE_MS = 15000;

export class ErroConexao extends Error {
  constructor(mensagem, status = 0, corpo = null) {
    super(mensagem);
    this.status = status;
    this.corpo = corpo;
  }
}

export class ConexaoSimulador {
  constructor({ base = "/simulador/api", buscar = (...args) => fetch(...args) } = {}) {
    this.base = base;
    this.buscar = buscar;
  }

  async requisitar(caminho, { metodo = null, corpo = undefined, manter = false } = {}) {
    const controle = typeof AbortController !== "undefined" ? new AbortController() : null;
    const limite = controle ? setTimeout(() => controle.abort(), TEMPO_LIMITE_MS) : null;
    let resposta;
    try {
      resposta = await this.buscar(this.base + caminho, {
        method: metodo || (corpo === undefined ? "GET" : "POST"),
        headers:
          corpo === undefined
            ? { Accept: "application/json" }
            : { Accept: "application/json", "Content-Type": "application/json" },
        body: corpo === undefined ? undefined : JSON.stringify(corpo),
        signal: controle?.signal,
        keepalive: manter, // permite encerrar a sessão quando a aba fecha
      });
    } catch (erro) {
      throw new ErroConexao(`sem conexão com o servidor do simulador (${erro.message})`);
    } finally {
      if (limite) clearTimeout(limite);
    }
    if (resposta.status === 204) return null;
    let dados = null;
    try {
      dados = await resposta.json();
    } catch {
      dados = null;
    }
    if (!resposta.ok) {
      const mensagem = dados?.mensagem || dados?.detail || `HTTP ${resposta.status}`;
      throw new ErroConexao(mensagem, resposta.status, dados);
    }
    return dados;
  }

  estado() {
    return this.requisitar("/estado");
  }

  configuracao(cruzamentoId) {
    return this.requisitar(`/cruzamentos/${cruzamentoId}/configuracao`);
  }

  planoFixo(cruzamentoId, tipo, taxas) {
    return this.requisitar(`/cruzamentos/${cruzamentoId}/plano-fixo`, { corpo: { tipo, taxas } });
  }

  criarSessao(cruzamentoId, zonas, confiancaMinima, tempoInicial = 0) {
    return this.requisitar("/sessoes", {
      corpo: { cruzamentoId, zonas, confiancaMinima, tempoInicial },
    });
  }

  enviarQuadros(sessaoId, quadros, viasSemEnvio = []) {
    return this.requisitar(`/sessoes/${sessaoId}/quadros`, { corpo: { quadros, viasSemEnvio } });
  }

  encerrarSessao(sessaoId) {
    return this.requisitar(`/sessoes/${sessaoId}`, { metodo: "DELETE", manter: true }).catch(() => null);
  }
}

export class PonteGSA {
  constructor({ conexao, cruzamentoId, relogio = () => Date.now() }) {
    this.conexao = conexao;
    this.cruzamentoId = cruzamentoId;
    this.relogio = relogio;
    this.geracao = 0;
    this.viasSemEnvio = [];
    this.limpar();
  }

  limpar() {
    this.sessaoId = null;
    this.status = "parada"; // parada | conectando | ativa | erro | substituida
    this.mensagem = "";
    this.emVoo = false;
    this.ultimoEnvioReal = -Infinity;
    this.janela = { inicio: 0, duracao: null, parcial: {} };
    this.janelasEnviadas = 0;
    this.janelasComErro = 0;
    this.falhasSeguidas = 0;
    this.latenciaMs = null;
    this.ultimoLote = null;
    this.ultimoCiclo = null;
    this.ultimoEnvio = null;
    this.ultimoPlano = null;
    this.ultimaSequencia = 0;
    this.ultimoPlanoEm = null;
    this.contingenciaLocal = false;
    this.historico = [];
  }

  /** Abre a câmera do cruzamento (nova janela de contagem a partir de `mundo.t`). */
  async abrir(mundo) {
    this.geracao++;
    const geracao = this.geracao;
    this.limpar();
    this.status = "conectando";
    try {
      const sessao = await this.conexao.criarSessao(
        this.cruzamentoId,
        mundo.zonas(),
        mundo.config.confiancaMinima ?? 0.3,
        Math.round(mundo.t * 1000) / 1000,
      );
      if (geracao !== this.geracao) return;
      this.sessaoId = sessao.sessaoId;
      this.janela = { inicio: sessao.tempoInicial ?? mundo.t, duracao: sessao.janelaSegundos, parcial: {} };
      this.status = "ativa";
      // quadros anteriores à abertura não pertencem a esta câmera
      mundo.quadrosPendentes = mundo.quadrosPendentes.filter((q) => q.t > this.janela.inicio);
    } catch (erro) {
      if (geracao !== this.geracao) return;
      this.status = "erro";
      this.mensagem = erro.message;
    }
  }

  encerrar() {
    this.geracao++;
    if (this.sessaoId) this.conexao.encerrarSessao(this.sessaoId);
    this.limpar();
  }

  /** Chamado a cada quadro da animação: envia quando for a hora, sem bloquear. */
  sincronizar(mundo) {
    this.verificarContingenciaLocal(mundo);
    if (this.emVoo || !this.sessaoId || this.status === "substituida") return null;
    const pendentes = mundo.quadrosPendentes;
    if (!pendentes.length) return null;
    const agora = this.relogio();
    const fimJanela = this.janela.inicio + (this.janela.duracao ?? Infinity);
    const virouJanela = pendentes[pendentes.length - 1].t >= fimJanela;
    const espera = this.falhasSeguidas
      ? Math.min(10000, 500 * 2 ** this.falhasSeguidas)
      : INTERVALO_ENVIO_MS;
    if (agora - this.ultimoEnvioReal < espera && !(virouJanela && !this.falhasSeguidas)) {
      return null;
    }
    return this.enviar(mundo);
  }

  async enviar(mundo) {
    const geracao = this.geracao;
    const quantidade = Math.min(mundo.quadrosPendentes.length, MAX_QUADROS_POR_ENVIO);
    const quadros = mundo.quadrosPendentes.slice(0, quantidade);
    const ultimoT = quadros[quadros.length - 1].t;
    this.emVoo = true;
    this.ultimoEnvioReal = this.relogio();
    try {
      const resposta = await this.conexao.enviarQuadros(this.sessaoId, quadros, this.viasSemEnvio);
      if (geracao !== this.geracao) return null;
      // remove só o que foi enviado (novos quadros entraram no fim enquanto isso)
      const restantes = mundo.quadrosPendentes.filter((q) => q.t > ultimoT);
      mundo.quadrosPendentes = restantes;
      this.falhasSeguidas = 0;
      this.status = "ativa";
      this.processarResposta(mundo, resposta);
      return resposta;
    } catch (erro) {
      if (geracao !== this.geracao) return null;
      this.falhasSeguidas++;
      this.mensagem = erro.message;
      if (erro.status === 409) {
        this.status = "substituida";
      } else if (erro.status === 404) {
        this.status = "erro"; // a sessão expirou: abre outra a partir de agora
        this.emVoo = false;
        this.abrir(mundo);
      } else if (erro.status === 400) {
        this.status = "erro";
        mundo.quadrosPendentes = mundo.quadrosPendentes.filter((q) => q.t > ultimoT);
      } else {
        this.status = "erro";
      }
      return null;
    } finally {
      if (geracao === this.geracao) this.emVoo = false;
    }
  }

  processarResposta(mundo, resposta) {
    if (resposta.janela) this.janela = resposta.janela;
    for (const envio of resposta.envios || []) {
      this.ultimoEnvio = envio;
      this.historico.unshift(envio);
      if (this.historico.length > 20) this.historico.pop();
      if (envio.lote) this.ultimoLote = envio.lote;
      if (envio.latenciaMs != null) this.latenciaMs = envio.latenciaMs;
      if (envio.cicloGerado) this.ultimoCiclo = envio.cicloGerado;
      if (envio.erro) {
        this.janelasComErro++;
        this.mensagem = envio.erro;
      } else {
        this.janelasEnviadas++;
        this.mensagem = "";
      }
    }
    const plano = resposta.ultimoPlano;
    if (plano && plano.sequencia > this.ultimaSequencia) {
      this.ultimaSequencia = plano.sequencia;
      const resultado = mundo.aplicarPlanoGsa(plano);
      this.ultimoPlano = plano;
      this.ultimoPlanoEm = mundo.t;
      this.contingenciaLocal = false;
      if (!resultado.ok) {
        this.mensagem = `Plano recusado pelo monitor de conflitos: ${resultado.erros.join("; ")}`;
      }
    }
  }

  /** Sem plano do GSA por duas janelas e um ciclo: volta ao plano fixo local. */
  verificarContingenciaLocal(mundo) {
    if (this.contingenciaLocal || this.ultimoPlanoEm === null) return false;
    const janela = this.janela.duracao || 90;
    const limite = 2 * janela + mundo.b.controlador.duracaoDoCiclo();
    if (mundo.t - this.ultimoPlanoEm <= limite) return false;
    mundo.aplicarPlanoGsa({
      ...mundo.config.planoFixo,
      origem: "contingencia_local",
      modoOperacao: "contingencia",
      motivoContingencia:
        "Sem resposta do GSA por mais de duas janelas de contagem: o controlador voltou ao plano fixo local.",
    });
    this.contingenciaLocal = true;
    return true;
  }
}
