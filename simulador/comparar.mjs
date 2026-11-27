/* Comparação tempo fixo × GSA sem desenho, o mais rápido possível, contra a API de verdade.

   Usa os mesmos módulos da página (mundo, câmera sintética, controlador e ponte com o GSA) e espera a
   resposta de cada lote, então meia hora simulada roda em poucos segundos. Os ciclos são os do motor
   do GSA, como na interface.

   Pré-requisito: o simulador no ar (python -m simulador).
   Uso: node simulador/comparar.mjs [--hora 8] [--minutos 30] [--semente 2026] [--base igual|ajustado]
                                    [--zona aproximacao|entrada] [--relogio] [--congestionamento ns|lo]
                                    [--cruzamento 2] [--api http://127.0.0.1:8000/simulador/api] */

import { ConexaoSimulador, PonteGSA } from "./web/js/conexao.js";
import { Mundo } from "./web/js/mundo.js";

function argumentos(lista) {
  const opcoes = {
    hora: 8,
    minutos: 30,
    semente: 2026,
    base: "igual",
    zona: "aproximacao",
    relogio: false,
    congestionamento: null,
    cruzamento: null,
    api: "http://127.0.0.1:8000/simulador/api",
  };
  for (let i = 0; i < lista.length; i++) {
    const nome = lista[i].replace(/^--/, "");
    if (nome === "relogio") opcoes.relogio = true;
    else if (nome in opcoes) opcoes[nome] = typeof opcoes[nome] === "number" ? Number(lista[++i]) : lista[++i];
    else throw new Error(`opção desconhecida: ${lista[i]}`);
  }
  return opcoes;
}

const opcoes = argumentos(process.argv.slice(2));
const conexao = new ConexaoSimulador({ base: opcoes.api });
const estado = await conexao.estado();
const cruzamentoId = Number(opcoes.cruzamento) || estado.cruzamentoPadrao;
const config = await conexao.configuracao(cruzamentoId);

const preparar = (planoA) => {
  const mundo = new Mundo({ configuracao: config, semente: opcoes.semente, planoA });
  mundo.modoZona = opcoes.zona;
  mundo.definirHora(opcoes.hora);
  if (opcoes.relogio) mundo.definirRelogio(true);
  if (opcoes.congestionamento) mundo.definirCongestionamento(opcoes.congestionamento);
  return mundo;
};
const planoA =
  opcoes.base === "ajustado"
    ? await conexao.planoFixo(cruzamentoId, "ajustado", preparar(null).taxasMediasDoDia())
    : config.planoFixo;
const mundo = preparar(planoA);
const ponte = new PonteGSA({ conexao, cruzamentoId });
await ponte.abrir(mundo);

let problemas = 0;
for (let i = 0; i < (opcoes.minutos * 60) / 0.05; i++) {
  mundo.passo();
  const quadros = mundo.quadrosPendentes;
  const fimJanela = ponte.janela.inicio + ponte.janela.duracao;
  if (quadros.length && (quadros.length >= 20 || quadros.at(-1).t >= fimJanela)) await ponte.enviar(mundo);
  if (i % 200 === 0) problemas += mundo.a.sobreposicoes().length + mundo.b.sobreposicoes().length;
}

const a = mundo.a.resumo();
const b = mundo.b.resumo();
const linha = (rotulo, r) =>
  `${rotulo}  espera média ${r.esperaMedia.toFixed(1).padStart(5)} s | acumulada ${(r.esperaAcumulada / 60).toFixed(0).padStart(5)} min | ` +
  `fila média ${r.filaMedia.toFixed(1).padStart(4)} | fila máx. ${String(r.filaMaxima).padStart(3)} | atendidos ${r.servidos} | vazão ${r.vazao.toFixed(0)} veíc/h`;
console.log(
  `${config.cruzamento.nome} · ${opcoes.minutos} min a partir das ${opcoes.hora}h${opcoes.relogio ? " (relógio avançando)" : ""} · ` +
    `semente ${opcoes.semente} · zona ${opcoes.zona}${opcoes.congestionamento ? ` · congestionamento ${opcoes.congestionamento}` : ""}`,
);
console.log(`A: tempo fixo ${opcoes.base} (verdes ${planoA.estagios.map((e) => e.verde).join("/")} s, ciclo ${planoA.duracao} s) · B: GSA`);
console.log(linha("A", a));
console.log(linha("B", b));
console.log(
  `Redução da espera média com o GSA: ${(100 * (1 - b.esperaMedia / a.esperaMedia)).toFixed(0)}% · ` +
    `chegadas iguais: ${a.chegadas === b.chegadas} (${a.chegadas}) · janelas enviadas: ${ponte.janelasEnviadas} ` +
    `(com erro: ${ponte.janelasComErro}) · sobreposições: ${problemas} · planos recusados: ${mundo.b.controlador.rejeitados.length}`,
);
ponte.encerrar();
