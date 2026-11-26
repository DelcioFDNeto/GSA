// Gera o Relatório Parcial (DOCX), entregue em 01/10/2026. Versão congelada: usa as imagens e
// diagramas desta pasta, que mostram o projeto como estava naquela data.
// Uso: cd docs/relatorio && npm install && npm run parcial
// PDF:  soffice --headless --convert-to pdf parcial/Relatorio_Parcial_GSA.docx

const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat,
  PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun,
  VerticalAlign, WidthType,
} = require("docx");

const IMG = path.join(__dirname, "img");
const SAIDA = path.join(__dirname, "Relatorio_Parcial_GSA.docx");

// ---------- Identidade visual ----------
const COR = {
  titulo: "1F3A5F",
  acento: "2A78D6",
  texto: "1A1A1A",
  suave: "5F5E5A",
  borda: "C9CDD2",
  cabecalho: "1F3A5F",
  faixa: "F3F6FA",
  ok: "E3F4EA", okTexto: "1E6B3A",
  parcial: "FFF1D1", parcialTexto: "7A5300",
  previsto: "ECEEF1", previstoTexto: "44505C",
  codigo: "F4F5F7",
};
const FONTE = "Calibri";
const MONO = "Courier New";
const LARGURA = 9638; // A4 com margens de 2 cm, em DXA

// ---------- Auxiliares ----------
const t = (texto, opts = {}) => new TextRun({ text: texto, font: FONTE, ...opts });
const mono = (texto, opts = {}) => new TextRun({ text: texto, font: MONO, size: 18, ...opts });

function p(conteudo, opts = {}) {
  const children = typeof conteudo === "string" ? [t(conteudo)] : conteudo;
  return new Paragraph({ children, spacing: { after: 120, line: 276 }, ...opts });
}

function h1(texto, novaPagina = true) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: novaPagina,
    children: [t(texto)],
  });
}

function h2(texto) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(texto)] });
}

function bullet(conteudo, nivel = 0) {
  const children = typeof conteudo === "string" ? [t(conteudo)] : conteudo;
  return new Paragraph({
    numbering: { reference: "marcadores", level: nivel },
    children,
    spacing: { after: 80, line: 264 },
  });
}

function legenda(texto) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 240 },
    children: [t(texto, { italics: true, size: 18, color: COR.suave })],
  });
}

function figura(arquivo, larguraPol, textoLegenda, novaPagina = false) {
  const caminho = path.join(IMG, arquivo);
  const { largura, altura } = dimensoesPng(caminho);
  const w = Math.round(larguraPol * 96);
  const h = Math.round((w * altura) / largura);
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 120, after: 0 },
      keepNext: true,
      pageBreakBefore: novaPagina,
      children: [
        new ImageRun({
          type: "png",
          data: fs.readFileSync(caminho),
          transformation: { width: w, height: h },
          altText: { title: textoLegenda, description: textoLegenda, name: arquivo },
        }),
      ],
    }),
    legenda(textoLegenda),
  ];
}

function dimensoesPng(caminho) {
  const buf = fs.readFileSync(caminho);
  return { largura: buf.readUInt32BE(16), altura: buf.readUInt32BE(20) };
}

const bordaFina = { style: BorderStyle.SINGLE, size: 4, color: COR.borda };
const BORDAS = { top: bordaFina, bottom: bordaFina, left: bordaFina, right: bordaFina };

function celula(conteudo, largura, opts = {}) {
  const { fundo, negrito, cor, alinhamento, tamanho, monoespacado } = opts;
  const linhas = Array.isArray(conteudo) && conteudo[0] instanceof Paragraph ? conteudo : null;
  const children = linhas || [
    new Paragraph({
      alignment: alinhamento || AlignmentType.LEFT,
      spacing: { before: 0, after: 0, line: 252 },
      children: (Array.isArray(conteudo) ? conteudo : [conteudo]).map((c) =>
        typeof c === "string"
          ? (monoespacado ? mono : t)(c, { bold: negrito, color: cor, size: tamanho || 19 })
          : c,
      ),
    }),
  ];
  return new TableCell({
    width: { size: largura, type: WidthType.DXA },
    borders: BORDAS,
    shading: fundo ? { type: ShadingType.CLEAR, color: "auto", fill: fundo } : undefined,
    margins: { top: 50, bottom: 50, left: 110, right: 110 },
    verticalAlign: VerticalAlign.CENTER,
    children,
  });
}

function tabela(colunas, linhas, opts = {}) {
  const larguras = colunas.map((c) => c.largura);
  const cab = new TableRow({
    tableHeader: true,
    children: colunas.map((c) =>
      celula(c.titulo, c.largura, { fundo: COR.cabecalho, negrito: true, cor: "FFFFFF" }),
    ),
  });
  const corpo = linhas.map(
    (linha, i) =>
      new TableRow({
        cantSplit: true,
        children: linha.map((valor, j) => {
          const fmt = (opts.formatar && opts.formatar(valor, j, linha)) || {};
          const zebra = opts.zebra && i % 2 === 1 ? COR.faixa : undefined;
          return celula(valor, larguras[j], { fundo: zebra, ...fmt });
        }),
      }),
  );
  return new Table({
    width: { size: LARGURA, type: WidthType.DXA },
    columnWidths: larguras,
    rows: [cab, ...corpo],
  });
}

function situacao(valor) {
  const v = String(valor);
  if (v.startsWith("Atendido") || v.startsWith("Concluída") || v.startsWith("Em uso"))
    return { fundo: COR.ok, cor: COR.okTexto, negrito: true };
  if (v.startsWith("Parcial") || v.startsWith("Simulada"))
    return { fundo: COR.parcial, cor: COR.parcialTexto, negrito: true };
  if (v.startsWith("Previst") || v.startsWith("Fase"))
    return { fundo: COR.previsto, cor: COR.previstoTexto, negrito: true };
  return null;
}

function espaco(pts = 120) {
  return new Paragraph({ spacing: { before: 0, after: pts }, children: [] });
}

function blocoCodigo(linhas) {
  return linhas.map(
    (linha, i) =>
      new Paragraph({
        shading: { type: ShadingType.CLEAR, color: "auto", fill: COR.codigo },
        spacing: { before: i === 0 ? 60 : 0, after: i === linhas.length - 1 ? 160 : 0, line: 240 },
        indent: { left: 200, right: 200 },
        children: [mono(linha.replace(/ /g, " "))],
      }),
  );
}

// ---------- Conteúdo ----------
const EQUIPE = [
  ["Délcio Farias Dias Neto", "04183547", "Líder técnico — arquitetura e motor de cálculo"],
  ["João Pedro Bezerra dos Santos Ranieri", "04184381", "Banco de dados — modelagem, ORM e migrações"],
  ["Erick Eduardo Campos Matias", "04186589", "API — endpoints de cadastro e de leituras"],
  ["Nelson Paulo Santiago Barroso", "04180548", "Qualidade e documentação — testes, Swagger e relatórios"],
];

function capa() {
  return [
    espaco(600),
    p([t("BACK-END FRAMEWORKS", { bold: true, color: COR.acento, size: 22, characterSpacing: 40 })]),
    p([t("Relatório Parcial", { bold: true, color: COR.titulo, size: 60 })], { spacing: { after: 60 } }),
    p([t("Sistema de Gestão Semafórica Adaptativa", { color: COR.titulo, size: 36 })], {
      spacing: { after: 120 },
    }),
    p([
      t("Cálculo automático da temporização de semáforos com base no volume real de tráfego", {
        italics: true,
        color: COR.suave,
        size: 24,
      }),
    ], { spacing: { after: 600 } }),
    p([t("Equipe", { bold: true, color: COR.titulo, size: 24 })], { spacing: { after: 100 } }),
    tabela(
      [
        { titulo: "Integrante", largura: 3700 },
        { titulo: "Matrícula", largura: 1300 },
        { titulo: "Função no projeto", largura: 4638 },
      ],
      EQUIPE,
      { zebra: true },
    ),
    espaco(240),
    p([t("Orientador: ", { bold: true }), t("Wilson Cosmos")], { spacing: { after: 60 } }),
    p([t("Repositório: ", { bold: true }), t("github.com/DelcioFDNeto/GSA")], { spacing: { after: 60 } }),
    p([t("Versão do sistema: ", { bold: true }), t("0.5.0 — fases 1 a 5 de 8 concluídas")], {
      spacing: { after: 60 },
    }),
    p([t("Data: ", { bold: true }), t("1º de outubro de 2026")]),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

function secaoEscopo() {
  const L1 = 2350;
  const L2 = LARGURA - L1;
  const linha = (rotulo, conteudo) =>
    new TableRow({
      cantSplit: true,
      children: [
        celula(rotulo, L1, { fundo: COR.faixa, negrito: true, cor: COR.titulo }),
        celula(conteudo, L2),
      ],
    });
  const funcoes = [
    "Cadastrar cruzamentos, vias e semáforos, com tempos mínimo e máximo de verde.",
    "Receber e armazenar a quantidade de veículos detectada em cada via.",
    "Calcular a demanda e classificar o fluxo em baixo, moderado, alto ou crítico.",
    "Calcular o tempo de verde proporcional à demanda, respeitando mínimo e máximo.",
    "Gerar ciclos semafóricos e consultar situação e histórico pela API REST.",
  ].map((f) => bullet(f));
  return [
    h1("1. Escopo", false),
    new Table({
      width: { size: LARGURA, type: WidthType.DXA },
      columnWidths: [L1, L2],
      rows: [
        linha(
          "Problema",
          "Semáforos de tempo fixo não acompanham a variação do trânsito: vias movimentadas recebem o mesmo verde que vias vazias, o que gera congestionamento de um lado e tempo ocioso do outro.",
        ),
        linha(
          "Objetivo",
          "Backend que recebe a contagem de veículos por via, aplica regras de negócio configuráveis e calcula automaticamente o tempo de verde recomendado, distribuído de forma proporcional à demanda. Não há IA na decisão: a contagem vem de um sistema externo de visão computacional (ex.: YOLO).",
        ),
        linha(
          "Público-alvo",
          "Administradores (cadastram cruzamentos, vias, semáforos e parâmetros), operadores de trânsito (acompanham leituras e decisões) e o sistema de detecção de veículos (envia as contagens).",
        ),
        new TableRow({
          cantSplit: true,
          children: [
            celula("Funcionalidades-chave", L1, { fundo: COR.faixa, negrito: true, cor: COR.titulo }),
            new TableCell({
              width: { size: L2, type: WidthType.DXA },
              borders: BORDAS,
              margins: { top: 70, bottom: 30, left: 110, right: 110 },
              children: funcoes,
            }),
          ],
        }),
      ],
    }),
    espaco(),
  ];
}

function secaoFluxograma() {
  return [
    h1("2. Fluxograma"),
    p(
      "A API tem dois caminhos principais: o recebimento das leituras enviadas pelo sistema de detecção e o cálculo dos tempos do ciclo. Em ambos a requisição passa pela rota (controller), pelas validações e pelo service antes de chegar ao banco de dados; o motor de cálculo é um módulo separado, sem dependência da API nem do banco.",
    ),
    ...figura("fluxo1_leituras.png", 5.9, "Figura 1 — Fluxo de recebimento de leituras (RF04/RF05)"),
    ...figura("fluxo2_calculo.png", 6.3, "Figura 2 — Fluxo de cálculo do ciclo semafórico (RF06–RF11)", true),
  ];
}

const CRONOGRAMA = [
  ["1. Estruturação do projeto", "Délcio", "03/09 – 09/09", "S1", "Concluída"],
  ["2. Modelagem do banco de dados", "João Pedro", "08/09 – 16/09", "S1–S2", "Concluída"],
  ["3. Cadastros (CRUD básico)", "Erick", "14/09 – 23/09", "S2–S3", "Concluída"],
  ["4. Recebimento de leituras", "Erick", "21/09 – 28/09", "S3–S4", "Concluída"],
  ["5. Motor de cálculo e testes unitários", "Délcio · Nelson", "22/09 – 30/09", "S3–S4", "Concluída"],
  ["Relatório parcial", "Nelson", "28/09 – 01/10", "S4–S5", "Concluída"],
  ["6. Geração de ciclos e histórico", "João Pedro", "05/10 – 16/10", "S5–S7", "Prevista"],
  ["7. Consultas e configurações", "Erick", "19/10 – 30/10", "S7–S9", "Prevista"],
  ["8. Documentação, segurança e testes", "Nelson · Délcio", "03/11 – 13/11", "S9–S11", "Prevista"],
  ["Revisão e relatório final", "Equipe", "16/11 – 19/11", "S11–S12", "Prevista"],
];

function secaoCronograma() {
  return [
    h1("3. Cronograma"),
    p(
      "Início em 03/09/2026 (semana S1). As fases seguem a ordem do escopo; cada uma tem um responsável principal, com apoio dos demais integrantes.",
    ),
    ...figura("cronograma.png", 6.0, "Figura 3 — Cronograma do projeto (datas de 2026)"),
    tabela(
      [
        { titulo: "Fase", largura: 3300 },
        { titulo: "Responsável", largura: 1700 },
        { titulo: "Período (2026)", largura: 1650 },
        { titulo: "Semanas", largura: 1388 },
        { titulo: "Situação", largura: 1600 },
      ],
      CRONOGRAMA,
      { formatar: (v, j) => (j === 4 ? situacao(v) : null) },
    ),
    h2("Próximas etapas"),
    bullet([
      t("Fase 6 — ", { bold: true }),
      t("gravar os ciclos calculados e seu histórico (RF12/RF13), gerando o ciclo após cada lote de leituras."),
    ]),
    bullet([
      t("Fase 7 — ", { bold: true }),
      t("situação atual (RF14), histórico por cruzamento (RF15), parâmetros pela API (RF16) e registro de falhas (RF18)."),
    ]),
    bullet([
      t("Fase 8 — ", { bold: true }),
      t("autenticação administrativa (RNF07), testes de integração, medição de desempenho (RNF10) e revisão do Swagger."),
    ]),
  ];
}

function secaoApis() {
  const ENDPOINTS = [
    ["POST · GET", "/cruzamentos", "RF01", "Implementado"],
    ["GET · PUT · DELETE", "/cruzamentos/{id}", "RF01 · RF17", "Implementado"],
    ["POST · GET", "/cruzamentos/{id}/vias", "RF02", "Implementado"],
    ["GET · PUT", "/vias/{id}", "RF02", "Implementado"],
    ["POST · GET", "/vias/{id}/semaforo", "RF03", "Implementado"],
    ["GET", "/cruzamentos/{id}/semaforos", "RF03", "Implementado"],
    ["GET · PUT", "/semaforos/{id}", "RF03", "Implementado"],
    ["POST", "/cruzamentos/{id}/leituras", "RF04 · RF05", "Implementado"],
    ["POST · GET", "/vias/{id}/leituras", "RF05 · RF15", "Implementado"],
    ["POST", "/cruzamentos/{id}/calcular-ciclo", "RF06–RF11", "Implementado"],
    ["GET", "/health", "—", "Implementado"],
    ["GET", "/cruzamentos/{id}/ciclos · /ciclos/{id}", "RF12 · RF13", "Fase 6"],
    ["GET", "/cruzamentos/{id}/situacao", "RF14", "Fase 7"],
  ];
  return [
    h1("4. APIs"),
    tabela(
      [
        { titulo: "API", largura: 2500 },
        { titulo: "Tipo", largura: 1500 },
        { titulo: "Função no projeto", largura: 3638 },
        { titulo: "Status", largura: 2000 },
      ],
      [
        ["API REST própria (FastAPI)", "Interna", "Cadastros, recebimento de leituras e cálculo dos tempos de verde", "Em uso"],
        ["Swagger UI / OpenAPI (/docs, /openapi.json)", "Interna (gerada)", "Documentação interativa e teste manual dos endpoints", "Em uso"],
        ["Sistema de detecção de veículos (YOLO)", "Externa — envia dados", "Envia a contagem de veículos por via para a API", "Simulada por script; integração real futura"],
      ],
      { formatar: (v, j) => (j === 3 ? situacao(v) : null) },
    ),
    espaco(160),
    h2("API externa — sistema de detecção"),
    bullet([t("Endpoint base: ", { bold: true }), mono("http://<servidor>:8000"), t(" — rota "), mono("POST /cruzamentos/{id}/leituras"), t(" (o detector é cliente da nossa API).")]),
    bullet([t("Autenticação: ", { bold: true }), t("nenhuma nesta fase; chave de API ou token previstos na fase 8 (RNF07).")]),
    bullet([t("Formato: ", { bold: true }), t("JSON. Resposta 201 com as leituras gravadas; erros 400/404 no formato padrão da API.")]),
    bullet([t("Simulação: ", { bold: true }), mono("scripts/simulador_deteccao.py"), t(" envia contagens aleatórias e exibe o ciclo calculado.")]),
    p([t("Payload enviado (RF04):", { bold: true, size: 20 })], { spacing: { before: 120, after: 40 } }),
    ...blocoCodigo([
      '{ "cruzamentoId": 1,',
      '  "leituras": [ { "viaId": 1, "quantidadeVeiculos": 28 },',
      '                { "viaId": 2, "quantidadeVeiculos": 9 } ] }',
    ]),
    h2("Endpoints da API interna"),
    tabela(
      [
        { titulo: "Método", largura: 1800 },
        { titulo: "Rota", largura: 4038 },
        { titulo: "Requisito", largura: 1500 },
        { titulo: "Situação", largura: 2300 },
      ],
      ENDPOINTS,
      {
        formatar: (v, j) =>
          j === 1 ? { monoespacado: true, tamanho: 17 } : j === 3 ? situacao(v.replace("Implementado", "Atendido")) : null,
      },
    ),
    p([
      t("Erros seguem um formato único (", { size: 19, color: COR.suave }),
      mono("status, erro, mensagem, detalhes", { color: COR.suave }),
      t(") com os códigos 200, 201, 400, 404 e 500; dados inválidos retornam 400 em vez do 422 padrão do FastAPI (RNF06).", { size: 19, color: COR.suave }),
    ], { spacing: { before: 120 } }),
  ];
}

function secaoFrameworks() {
  return [
    h1("5. Frameworks"),
    p("Stack definida no escopo (Python, FastAPI, SQLAlchemy, SQLite/PostgreSQL, Pydantic, Swagger, Git), complementada por ferramentas marcadas como “adicionado”."),
    tabela(
      [
        { titulo: "Papel", largura: 1900 },
        { titulo: "Framework", largura: 2300 },
        { titulo: "Por que foi escolhido", largura: 5438 },
      ],
      [
        ["Framework web", "FastAPI", "Gera a documentação OpenAPI/Swagger automaticamente (RNF05) e integra a validação do Pydantic às rotas."],
        ["Servidor", "Uvicorn (adicionado)", "Servidor ASGI recomendado para executar o FastAPI, leve e simples de iniciar."],
        ["ORM", "SQLAlchemy 2", "Mapeia as entidades para tabelas e permite trocar SQLite por PostgreSQL só mudando a URL do banco."],
        ["Migrações", "Alembic (adicionado)", "Versiona o esquema do banco; a mesma migração foi aplicada em SQLite e PostgreSQL 16."],
        ["Validação e configuração", "Pydantic v2 + pydantic-settings", "Rejeita dados inválidos antes da regra de negócio (RNF04) e lê os parâmetros do motor do arquivo .env."],
        ["Banco de dados", "SQLite / PostgreSQL", "SQLite dispensa instalação no desenvolvimento; PostgreSQL é o alvo de produção."],
        ["Testes", "pytest (adicionado)", "Executa os testes do motor de cálculo; será a base dos testes de integração na fase 8."],
        ["Qualidade de código", "Ruff (adicionado)", "Lint e formatação automáticos, mantendo o código padronizado entre os quatro integrantes."],
        ["Cliente HTTP", "httpx (adicionado)", "Usado pelo simulador do sistema de detecção para enviar leituras à API."],
        ["Diagramas", "Graphviz (adicionado)", "Fluxogramas versionados como texto (.dot) junto com o código."],
        ["Versionamento", "Git + GitHub", "Histórico de commits e colaboração da equipe no repositório."],
      ],
      { zebra: true, formatar: (v, j) => (j === 1 ? { negrito: true } : null) },
    ),
    espaco(),
  ];
}

function secaoEtapas() {
  const etapa = (verbo, resto, evidencia) =>
    bullet([
      t(verbo, { bold: true }),
      t(resto),
      t(" Evidência: ", { color: COR.suave }),
      mono(evidencia, { color: COR.suave }),
    ]);
  return [
    h1("6. Etapas cumpridas"),
    etapa("Estruturado", " o projeto em camadas (rotas → services → repositories), com o motor de cálculo em um módulo puro, separado da API e do banco (RNF08).", "app/api, app/services, app/repositories, app/motor"),
    etapa("Modeladas", " 6 tabelas (cruzamentos, vias, semaforos, leituras_trafego, ciclos_semaforicos, tempos_semaforicos) com SQLAlchemy e criada a migração inicial com Alembic, testada em SQLite e PostgreSQL 16.", "alembic/versions/0001_modelagem_inicial_do_banco.py"),
    etapa("Implementados", " 14 endpoints de cadastro e consulta de cruzamentos, vias e semáforos, com validação de dados e erros 400/404 padronizados; a exclusão de cruzamento é lógica (RF17).", "app/api/routes/"),
    etapa("Implementado", " o recebimento de leituras em lote, no payload do RF04, e por via, com validação “tudo ou nada” e registro de data e horário (3 endpoints).", "app/services/leitura_service.py"),
    etapa("Implementado", " o motor de cálculo — demanda, classificação em 4 faixas e distribuição proporcional com mínimo, máximo e redistribuição — exposto em POST /cruzamentos/{id}/calcular-ciclo. Reproduz o exemplo do documento de requisitos: 30 e 10 veículos resultam em 60 s e 20 s (Figura 5).", "app/motor/regras.py"),
    etapa("Escritos", " 22 casos de teste unitário do motor de cálculo com pytest, todos passando.", "tests/test_motor_calculo.py"),
    etapa("Criados", " o script de dados de demonstração (2 cruzamentos, 6 vias) e o simulador do sistema de detecção, que envia leituras pela API.", "scripts/seed.py, scripts/simulador_deteccao.py"),
    etapa("Documentada", " a API no Swagger/OpenAPI, com 19 operações, títulos em português e o 422 do FastAPI trocado por 400 (Figura 4).", "http://127.0.0.1:8000/docs"),
    h2("Situação dos requisitos"),
    tabela(
      [
        { titulo: "Tipo", largura: 2638 },
        { titulo: "Atendidos", largura: 2333 },
        { titulo: "Parciais", largura: 2333 },
        { titulo: "Previstos", largura: 2334 },
      ],
      [
        ["Funcionais (18)", "12", "3", "3"],
        ["Não funcionais (10)", "8", "1", "1"],
      ],
      {
        formatar: (v, j) =>
          j === 1 ? { ...situacao("Atendido"), alinhamento: AlignmentType.CENTER }
          : j === 2 ? { ...situacao("Parcial"), alinhamento: AlignmentType.CENTER }
          : j === 3 ? { ...situacao("Previsto"), alinhamento: AlignmentType.CENTER }
          : { negrito: true },
      },
    ),
    p([t("O detalhamento por requisito está no Anexo A; os prints da API em funcionamento estão no Anexo B.", { color: COR.suave, size: 19 })], { spacing: { before: 120 } }),
  ];
}

const RASTREABILIDADE = [
  ["RF01", "Cadastro de cruzamentos", "Atendido", "/cruzamentos"],
  ["RF02", "Cadastro de vias", "Atendido", "/cruzamentos/{id}/vias, /vias/{id}"],
  ["RF03", "Cadastro de semáforos", "Atendido", "/vias/{id}/semaforo, /semaforos/{id}"],
  ["RF04", "Endpoint de recebimento de leituras", "Atendido", "POST /cruzamentos/{id}/leituras"],
  ["RF05", "Registro de cada leitura", "Atendido", "tabela leituras_trafego"],
  ["RF06", "Cálculo da demanda", "Atendido", "app/motor/demanda.py"],
  ["RF07", "Classificação do fluxo", "Atendido", "app/motor/classificacao.py (.env)"],
  ["RF08", "Tempo de verde recomendado", "Atendido", "app/motor/regras.py"],
  ["RF09", "Distribuição proporcional", "Atendido", "app/motor/regras.py"],
  ["RF10", "Garantia de verde mínimo", "Atendido", "app/motor/regras.py"],
  ["RF11", "Limite de verde máximo", "Atendido", "app/motor/regras.py"],
  ["RF12", "Geração de novo ciclo", "Parcial", "cálculo sob demanda; gravação na fase 6"],
  ["RF13", "Histórico de ciclos", "Previsto", "tabelas modeladas; fase 6"],
  ["RF14", "Situação atual do cruzamento", "Previsto", "fase 7"],
  ["RF15", "Histórico de trânsito", "Parcial", "GET /vias/{id}/leituras; por cruzamento na fase 7"],
  ["RF16", "Configuração dos parâmetros", "Parcial", "variáveis no .env; via API na fase 7"],
  ["RF17", "Ativação e desativação", "Atendido", "DELETE lógico e PUT com status"],
  ["RF18", "Registro de falhas", "Previsto", "fase 7"],
  ["RNF01", "API REST", "Atendido", "app/api/routes"],
  ["RNF02", "Persistência em banco", "Atendido", "SQLAlchemy + Alembic"],
  ["RNF03", "Comunicação em JSON", "Atendido", "schemas Pydantic (camelCase)"],
  ["RNF04", "Validação de dados", "Atendido", "Pydantic + services"],
  ["RNF05", "Documentação Swagger/OpenAPI", "Atendido", "/docs; revisão na fase 8"],
  ["RNF06", "Códigos HTTP adequados", "Atendido", "app/main.py (handlers)"],
  ["RNF07", "Autenticação administrativa", "Previsto", "fase 8"],
  ["RNF08", "Modularidade", "Atendido", "camadas + app/motor"],
  ["RNF09", "Manutenibilidade das regras", "Atendido", "protocolo RegraTemporizacao"],
  ["RNF10", "Desempenho", "Parcial", "índice via/data; medição na fase 8"],
];

function anexos() {
  return [
    h1("Anexo A — Rastreabilidade dos requisitos"),
    tabela(
      [
        { titulo: "Código", largura: 1000 },
        { titulo: "Requisito", largura: 3238 },
        { titulo: "Situação", largura: 1300 },
        { titulo: "Onde / observação", largura: 4100 },
      ],
      RASTREABILIDADE,
      {
        formatar: (v, j) =>
          j === 0 ? { negrito: true } : j === 2 ? situacao(v) : j === 3 ? { tamanho: 17, cor: COR.suave } : null,
      },
    ),
    h1("Anexo B — Evidências"),
    ...figura("swagger_endpoints.png", 5.0, "Figura 4 — Swagger UI com as 19 operações implementadas (http://127.0.0.1:8000/docs)"),
    ...figura("swagger_calcular_ciclo.png", 6.4, "Figura 5 — Execução de POST /cruzamentos/1/calcular-ciclo pelo Swagger: 30 e 10 veículos resultam em 60 s e 20 s de verde", true),
  ];
}

// ---------- Documento ----------
const cabecalho = new Header({
  children: [
    new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [t("Relatório Parcial · Sistema de Gestão Semafórica Adaptativa", { size: 16, color: COR.suave })],
    }),
  ],
});

const rodape = new Footer({
  children: [
    new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [
        t("Back-end Frameworks · página ", { size: 16, color: COR.suave }),
        new TextRun({ children: [PageNumber.CURRENT], font: FONTE, size: 16, color: COR.suave }),
        t(" de ", { size: 16, color: COR.suave }),
        new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONTE, size: 16, color: COR.suave }),
      ],
    }),
  ],
});

const doc = new Document({
  creator: "Equipe GSA",
  title: "Relatório Parcial — Sistema de Gestão Semafórica Adaptativa",
  description: "Relatório parcial da disciplina Back-end Frameworks",
  styles: {
    default: { document: { run: { font: FONTE, size: 21, color: COR.texto } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONTE, size: 34, bold: true, color: COR.titulo },
        paragraph: { spacing: { before: 120, after: 200 }, keepNext: true, outlineLevel: 0 },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: FONTE, size: 25, bold: true, color: COR.titulo },
        paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "marcadores",
        levels: [
          {
            level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 360, hanging: 240 } }, run: { color: COR.acento } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        titlePage: true,
        page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134, header: 567, footer: 567 } },
      },
      headers: { default: cabecalho, first: new Header({ children: [] }) },
      footers: { default: rodape, first: new Footer({ children: [] }) },
      children: [
        ...capa(),
        ...secaoEscopo(),
        ...secaoFluxograma(),
        ...secaoCronograma(),
        ...secaoApis(),
        ...secaoFrameworks(),
        ...secaoEtapas(),
        ...anexos(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SAIDA, buf);
  console.log(`Gerado ${SAIDA}`);
});
