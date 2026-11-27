/* Comunicação com a ponte do GSA (sem rede): lotes, aplicação do plano, erros e contingência. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { ConexaoSimulador, ErroConexao, PonteGSA } from "../../simulador/web/js/conexao.js";
import { Mundo } from "../../simulador/web/js/mundo.js";
import { configuracaoB, plano } from "./_comum.mjs";

/** Servidor falso: registra as chamadas e responde com o que o teste mandar. */
function servidorFalso() {
  const falso = {
    sessoes: 0,
    envios: [],
    resposta: null,
    erro: null,
    async criarSessao(cruzamentoId, zonas, confianca, tempoInicial) {
      falso.sessoes++;
      falso.ultimasZonas = zonas;
      return { sessaoId: `s${falso.sessoes}`, janelaSegundos: 90, tempoInicial };
    },
    async enviarQuadros(sessaoId, quadros, viasSemEnvio) {
      falso.envios.push({ sessaoId, quadros, viasSemEnvio });
      if (falso.erro) throw falso.erro;
      return falso.resposta || { janela: { inicio: 0, duracao: 90, parcial: {} }, envios: [], ultimoPlano: null };
    },
    encerrarSessao() {},
  };
  return falso;
}

function preparar() {
  let agora = 0;
  const servidor = servidorFalso();
  const mundo = new Mundo({ configuracao: configuracaoB(), semente: 4 });
  const ponte = new PonteGSA({ conexao: servidor, cruzamentoId: 2, relogio: () => agora });
  return { servidor, mundo, ponte, avancarRelogio: (ms) => (agora += ms) };
}

test("abre a câmera com as zonas e envia os quadros em lotes, sem repetir os já enviados", async () => {
  const { servidor, mundo, ponte, avancarRelogio } = preparar();
  await ponte.abrir(mundo);
  assert.equal(ponte.status, "ativa");
  assert.equal(servidor.ultimasZonas.length, 4);
  assert.ok(servidor.ultimasZonas.every((z) => z.viaId && z.poligono.length === 4));
  mundo.simular(5); // 10 quadros
  avancarRelogio(600);
  await ponte.sincronizar(mundo);
  assert.equal(servidor.envios.length, 1);
  assert.equal(servidor.envios[0].quadros.length, 10);
  assert.equal(mundo.quadrosPendentes.length, 0);
  assert.equal(await ponte.sincronizar(mundo), null, "nada pendente, nada enviado");
});

test("aplica o plano do GSA uma vez por sequência e registra o último lote", async () => {
  const { servidor, mundo, ponte, avancarRelogio } = preparar();
  await ponte.abrir(mundo);
  const lote = { cruzamentoId: 2, leituras: [{ viaId: 3, quantidadeVeiculos: 42 }] };
  const planoGsa = { ...plano(40, 20), sequencia: 1, regra: "webster", duracaoGsa: 70, tempos: {} };
  servidor.resposta = {
    janela: { inicio: 90, duracao: 90, parcial: { 3: 2 } },
    envios: [{ lote, cicloGerado: { id: 7 }, plano: planoGsa, latenciaMs: 12, erro: null }],
    ultimoPlano: planoGsa,
  };
  mundo.simular(5);
  avancarRelogio(600);
  await ponte.sincronizar(mundo);
  assert.equal(mundo.b.controlador.pendente, planoGsa, "plano agendado para o fim do ciclo");
  assert.deepEqual(ponte.ultimoLote, lote);
  assert.equal(ponte.janelasEnviadas, 1);
  assert.equal(ponte.latenciaMs, 12);
  mundo.b.controlador.pendente = null;
  mundo.simular(5);
  avancarRelogio(600);
  await ponte.sincronizar(mundo);
  assert.equal(mundo.b.controlador.pendente, null, "a mesma sequência não é reaplicada");
});

test("falha de rede: guarda os quadros e tenta de novo com espera crescente", async () => {
  const { servidor, mundo, ponte, avancarRelogio } = preparar();
  await ponte.abrir(mundo);
  servidor.erro = new ErroConexao("sem conexão", 0);
  mundo.simular(5);
  avancarRelogio(600);
  await ponte.sincronizar(mundo);
  assert.equal(ponte.status, "erro");
  assert.equal(mundo.quadrosPendentes.length, 10, "nada se perde");
  avancarRelogio(300);
  assert.equal(await ponte.sincronizar(mundo), null, "espera antes de tentar de novo");
  servidor.erro = null;
  avancarRelogio(2000);
  await ponte.sincronizar(mundo);
  assert.equal(ponte.status, "ativa");
  assert.equal(mundo.quadrosPendentes.length, 0);
});

test("outra aba assumiu a câmera (409) e sessão expirada (404)", async () => {
  const { servidor, mundo, ponte, avancarRelogio } = preparar();
  await ponte.abrir(mundo);
  servidor.erro = new ErroConexao("sessão expirou", 404);
  mundo.simular(5);
  avancarRelogio(600);
  await ponte.sincronizar(mundo);
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(servidor.sessoes, 2, "abriu outra sessão");
  servidor.erro = new ErroConexao("outra aba", 409);
  mundo.simular(5);
  avancarRelogio(5000);
  await ponte.sincronizar(mundo);
  assert.equal(ponte.status, "substituida");
  const envios = servidor.envios.length;
  avancarRelogio(5000);
  await ponte.sincronizar(mundo);
  assert.equal(servidor.envios.length, envios, "não envia mais nada");
});

test("sem plano do GSA por duas janelas e um ciclo, volta ao plano fixo local", async () => {
  const { mundo, ponte } = preparar();
  await ponte.abrir(mundo);
  ponte.ultimoPlanoEm = 0; // houve um plano do GSA em t = 0
  mundo.simular(200);
  assert.equal(ponte.verificarContingenciaLocal(mundo), false, "ainda dentro do prazo");
  mundo.simular(200);
  assert.equal(ponte.verificarContingenciaLocal(mundo), true);
  assert.equal(mundo.b.controlador.pendente.origem, "contingencia_local");
  assert.equal(mundo.b.controlador.pendente.modoOperacao, "contingencia");
});

test("o cliente HTTP traduz erros da API em ErroConexao com status e mensagem", async () => {
  const conexao = new ConexaoSimulador({
    buscar: async () => ({ ok: false, status: 409, json: async () => ({ mensagem: "Outra aba" }) }),
  });
  await assert.rejects(conexao.estado(), (erro) => erro instanceof ErroConexao && erro.status === 409 && erro.message === "Outra aba");
  const semRede = new ConexaoSimulador({ buscar: async () => { throw new TypeError("falhou"); } });
  await assert.rejects(semRede.estado(), (erro) => erro.status === 0 && /sem conexão/.test(erro.message));
});
