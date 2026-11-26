// Gera o Relatório Final (DOCX) a partir do conteúdo abaixo e das imagens em docs/img.
// Uso: cd docs/relatorio && npm install && npm run final
// PDF:  soffice --headless --convert-to pdf Relatorio_Final_GSA.docx


const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, Header, HeadingLevel, ImageRun, LevelFormat,
  PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun,
  VerticalAlign, WidthType,
} = require("docx");

const IMG = path.join(__dirname, "..", "img");
const SAIDA = path.join(__dirname, "Relatorio_Final_GSA.docx");

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
  if (v.startsWith("Atendido") || v.startsWith("Concluída") || v.startsWith("Em uso") || v.startsWith("Aprovado"))
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
    p([t("Relatório Final", { bold: true, color: COR.titulo, size: 60 })], { spacing: { after: 60 } }),
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
    p([t("Versão do sistema: ", { bold: true }), t("1.2.0 — 8 de 8 fases concluídas, com incrementos para o pitch")], {
      spacing: { after: 60 },
    }),
    p([t("Data: ", { bold: true }), t("24 de novembro de 2026")]),
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
    "Receber as contagens do sistema de detecção e gerar um ciclo semafórico a cada lote.",
    "Calcular a demanda, classificar o fluxo e distribuir o verde respeitando mínimo e máximo.",
    "Consultar a situação atual, o histórico de trânsito e o histórico de ciclos.",
    "Configurar parâmetros, registrar falhas e controlar o acesso por perfil.",
    "Manter o cruzamento funcionando com um plano fixo de segurança quando faltam leituras.",
    "Acompanhar o cruzamento ao vivo em um painel web atualizado em tempo real.",
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
          "Backend que recebe a contagem de veículos por via, aplica regras de negócio configuráveis e calcula automaticamente o tempo de verde recomendado, distribuído de forma proporcional à demanda ou pela regra de Webster, com um plano fixo de segurança quando faltam leituras. Não há IA na decisão: a contagem vem de um sistema externo de visão computacional (YOLO).",
        ),
        linha(
          "Público-alvo",
          "Administradores (cadastram cruzamentos, vias, semáforos, parâmetros e usuários), operadores de trânsito (acompanham leituras, ciclos e falhas) e o sistema de detecção de veículos (envia as contagens).",
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
      "A API separa rotas (controllers), regras de negócio (services), motor de cálculo e acesso ao banco (repositories), como mostra a Figura 1. Os fluxogramas a seguir trazem os três caminhos principais do sistema: o recebimento de leituras com geração do ciclo (Figura 2), o cálculo do ciclo pelo motor, com estágios, regra proporcional ou de Webster e modo de segurança (Figura 3) e a detecção de falhas por ausência de leitura (Figura 4).",
    ),
    ...figura("arquitetura.png", 5.6, "Figura 1 — Arquitetura em camadas da API"),
    ...figura("fluxo1_leituras.png", 6.6, "Figura 2 — Recebimento de leituras e geração automática do ciclo", true),
    ...figura("fluxo2_ciclo.png", 6.4, "Figura 3 — Cálculo do ciclo semafórico pelo motor", true),
    ...figura("fluxo3_falhas.png", 6.6, "Figura 4 — Detecção e resolução de falhas por ausência de leitura", true),
  ];
}

const CRONOGRAMA = [
  ["1. Estruturação do projeto", "Délcio", "03/09 – 09/09", "S1", "Concluída"],
  ["2. Modelagem do banco de dados", "João Pedro", "08/09 – 16/09", "S1–S2", "Concluída"],
  ["3. Cadastros (CRUD básico)", "Erick", "14/09 – 23/09", "S2–S3", "Concluída"],
  ["4. Recebimento de leituras", "Erick", "21/09 – 28/09", "S3–S4", "Concluída"],
  ["5. Motor de cálculo e testes unitários", "Délcio · Nelson", "22/09 – 30/09", "S3–S4", "Concluída"],
  ["Relatório parcial", "Nelson", "28/09 – 01/10", "S4–S5", "Concluída"],
  ["6. Geração de ciclos e histórico", "João Pedro", "05/10 – 16/10", "S5–S7", "Concluída"],
  ["7. Consultas e configurações", "Erick", "19/10 – 30/10", "S7–S9", "Concluída"],
  ["8. Documentação, segurança e testes", "Nelson · Délcio", "03/11 – 13/11", "S9–S11", "Concluída"],
  ["Revisão e relatório final", "Equipe", "16/11 – 24/11", "S11–S12", "Concluída"],
  ["Incrementos para o pitch (v1.1 e v1.2)", "Equipe", "24/11", "S12", "Concluída"],
];

function secaoCronograma() {
  return [
    h1("3. Cronograma"),
    p(
      "Início em 03/09/2026 (semana S1). Todas as fases previstas no escopo foram concluídas; cada uma teve um responsável principal, com apoio dos demais integrantes. Depois do relatório final, a equipe acrescentou recursos para o pitch (seção 6).",
    ),
    ...figura("cronograma.png", 6.0, "Figura 5 — Cronograma do projeto (datas de 2026)"),
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
  ];
}

function secaoApis() {
  const ENDPOINTS = [
    ["POST", "/auth/login", "RNF07", "Público"],
    ["GET", "/auth/me", "RNF07", "Usuário logado"],
    ["GET · POST", "/usuarios", "RNF07", "Administrador"],
    ["GET · POST", "/cruzamentos", "RF01", "Público · Admin."],
    ["GET · PUT · DELETE", "/cruzamentos/{id}", "RF01 · RF17", "Público · Admin."],
    ["POST", "/cruzamentos/{id}/ativar · /desativar", "RF17", "Administrador"],
    ["GET · POST", "/cruzamentos/{id}/vias", "RF02", "Público · Admin."],
    ["GET · PUT", "/vias/{id}", "RF02", "Público · Admin."],
    ["GET · POST", "/vias/{id}/semaforo", "RF03", "Público · Admin."],
    ["GET", "/cruzamentos/{id}/semaforos", "RF03", "Público"],
    ["GET · PUT", "/semaforos/{id}", "RF03", "Público · Admin."],
    ["GET · POST", "/cruzamentos/{id}/leituras", "RF04 · RF05 · RF12 · RF15", "Público · Detecção"],
    ["GET · POST", "/vias/{id}/leituras", "RF05 · RF15", "Público · Detecção"],
    ["POST", "/cruzamentos/{id}/calcular-ciclo", "RF06–RF12", "Operador"],
    ["GET", "/cruzamentos/{id}/ciclos · /ciclos/{id}", "RF13", "Público"],
    ["GET", "/cruzamentos/{id}/situacao", "RF14", "Público"],
    ["GET", "/cruzamentos/{id}/historico", "RF15", "Público"],
    ["GET · PUT", "/parametros", "RF16", "Público · Admin."],
    ["GET", "/falhas · /cruzamentos/{id}/falhas", "RF18", "Público"],
    ["POST", "/cruzamentos/{id}/falhas · /falhas/{id}/resolver · /falhas/verificar", "RF18", "Operador"],
    ["GET", "/eventos (Server-Sent Events)", "—", "Público"],
    ["GET", "/health", "—", "Público"],
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
        ["API REST própria (FastAPI)", "Interna", "Cadastros, leituras, ciclos, consultas, parâmetros, falhas e autenticação (38 operações)", "Em uso"],
        ["Eventos em tempo real (GET /eventos)", "Interna", "Server-Sent Events com novos ciclos, leituras e falhas, consumidos pelo painel web", "Em uso"],
        ["Swagger UI / OpenAPI (/docs, /openapi.json)", "Interna (gerada)", "Documentação interativa, com login e chave de API pelo botão Authorize", "Em uso"],
        ["Sistema de detecção de veículos (YOLO)", "Externa — envia dados", "Envia a contagem de veículos por via para a API", "Parcial — contador de exemplo validado com vídeo de amostra"],
      ],
      { formatar: (v, j) => (j === 3 ? situacao(v) : null) },
    ),
    espaco(160),
    h2("API externa — sistema de detecção"),
    bullet([t("Endpoint base: ", { bold: true }), mono("http://<servidor>:8000"), t(" — rota "), mono("POST /cruzamentos/{id}/leituras"), t(" (o detector é cliente da nossa API).")]),
    bullet([t("Autenticação: ", { bold: true }), t("cabeçalho "), mono("X-API-Key"), t(" com a chave definida em GSA_CHAVE_API_DETECCAO; sem chave válida a resposta é 401.")]),
    bullet([t("Formato: ", { bold: true }), t("JSON. Resposta 201 com as leituras gravadas e o ciclo gerado; erros 400/401/404 no formato padrão da API.")]),
    bullet([t("Simulação: ", { bold: true }), mono("scripts/simulador_deteccao.py"), t(" envia contagens aleatórias e "), mono("scripts/demo_pitch.py"), t(" envia um dia de tráfego acelerado, com falha de câmera simulada.")]),
    bullet([t("Contador YOLO: ", { bold: true }), mono("deteccao/contador_yolo.py"), t(" detecta e rastreia veículos em vídeo, conta por zona de cada via e envia os lotes com a chave de API (Figura 13).")]),
    p([t("Payload enviado (RF04):", { bold: true, size: 20 })], { spacing: { before: 120, after: 40 } }),
    ...blocoCodigo([
      '{ "cruzamentoId": 1,',
      '  "leituras": [ { "viaId": 1, "quantidadeVeiculos": 28 },',
      '                { "viaId": 2, "quantidadeVeiculos": 9 } ] }',
    ]),
    h2("Endpoints da API interna"),
    tabela(
      [
        { titulo: "Método", largura: 1700 },
        { titulo: "Rota", largura: 4138 },
        { titulo: "Requisito", largura: 1900 },
        { titulo: "Acesso", largura: 1900 },
      ],
      ENDPOINTS,
      { zebra: true, formatar: (v, j) => (j === 1 ? { monoespacado: true, tamanho: 17 } : null) },
    ),
    p([
      t("Consultas são públicas; cadastros, parâmetros e usuários exigem o perfil administrador; cálculo manual e falhas aceitam operador. Erros seguem um formato único (", { size: 19, color: COR.suave }),
      mono("status, erro, mensagem, detalhes", { color: COR.suave }),
      t(") com os códigos 200, 201, 400, 401, 403, 404 e 500; dados inválidos retornam 400 em vez do 422 padrão do FastAPI (RNF06).", { size: 19, color: COR.suave }),
    ], { spacing: { before: 120 } }),
  ];
}

function secaoFrameworks() {
  return [
    espaco(240),
    h1("5. Frameworks", false),
    p("Stack definida no escopo (Python, FastAPI, SQLAlchemy, SQLite/PostgreSQL, Pydantic, Swagger, Git), complementada por ferramentas marcadas como “adicionado”."),
    tabela(
      [
        { titulo: "Papel", largura: 1900 },
        { titulo: "Framework", largura: 2300 },
        { titulo: "Por que foi escolhido", largura: 5438 },
      ],
      [
        ["Framework web", "FastAPI", "Gera a documentação OpenAPI/Swagger automaticamente (RNF05) e integra a validação do Pydantic e a injeção de dependências usada na autenticação."],
        ["Servidor", "Uvicorn (adicionado)", "Servidor ASGI recomendado para executar o FastAPI, leve e simples de iniciar."],
        ["ORM", "SQLAlchemy 2", "Mapeia as entidades para tabelas e permite trocar SQLite por PostgreSQL só mudando a URL do banco."],
        ["Migrações", "Alembic (adicionado)", "Versiona o esquema; as migrações 0001 a 0003 foram aplicadas em SQLite e PostgreSQL 16, inclusive sobre dados existentes."],
        ["Validação e configuração", "Pydantic v2 + pydantic-settings", "Rejeita dados inválidos antes da regra de negócio (RNF04) e lê a configuração de variáveis de ambiente."],
        ["Banco de dados", "SQLite / PostgreSQL", "SQLite dispensa instalação no desenvolvimento; PostgreSQL é o banco do docker compose e da integração contínua."],
        ["Segurança", "PyJWT + python-multipart (adicionado)", "Tokens JWT assinados e formulário de login OAuth2, que habilita o botão Authorize do Swagger (RNF07)."],
        ["Testes", "pytest + httpx2 (adicionado)", "111 testes: unitários do motor e de integração da API pelo TestClient, em SQLite e PostgreSQL."],
        ["Qualidade de código", "Ruff (adicionado)", "Lint e formatação automáticos, verificados também na integração contínua."],
        ["Implantação", "Docker + docker compose + Render (adicionado)", "Imagem da API e PostgreSQL sobem com um comando; as migrações rodam ao iniciar o contêiner. O blueprint do Render publica a mesma imagem com URL pública."],
        ["Tempo real", "Server-Sent Events (adicionado)", "Atualiza o painel sem recarregar a página, com o StreamingResponse do próprio FastAPI, sem nova dependência."],
        ["Painel web", "HTML, CSS e JavaScript (adicionado)", "Página estática servida pela própria API, sem framework de front-end, que funciona sem internet na apresentação."],
        ["Detecção (exemplo)", "Ultralytics YOLO + ByteTrack + OpenCV (adicionado)", "Contagem de veículos por zona em vídeo; roda fora da API, em ambiente separado (requirements-yolo.txt)."],
        ["Integração contínua", "GitHub Actions (adicionado)", "A cada push: lint, testes em Python 3.11/3.12, testes em PostgreSQL e teste da imagem Docker."],
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
    h2("Fases 1 a 5 (entregues no relatório parcial)"),
    etapa("Estruturado", " o projeto em camadas e modeladas as 6 tabelas iniciais com SQLAlchemy e Alembic.", "app/, alembic/versions/0001_modelagem_inicial_do_banco.py"),
    etapa("Implementados", " os cadastros de cruzamentos, vias e semáforos e o recebimento de leituras no payload do RF04.", "app/api/routes/"),
    etapa("Implementado", " o motor de cálculo (demanda, classificação, distribuição proporcional com mínimo e máximo), que reproduz o exemplo do documento de requisitos: 30 e 10 veículos resultam em 60 s e 20 s.", "app/motor/"),
    h2("Fases 6 a 8"),
    etapa("Implementada", " a geração automática de ciclos: cada lote de leituras grava um ciclo com o tempo de cada semáforo; o operador também pode calcular manualmente ou apenas simular (RF12/RF13).", "app/services/ciclo_service.py, Figura 8"),
    etapa("Criada", " a migração 0002 (parâmetros, falhas, usuários e novas colunas de ciclo), testada sobre dados já existentes em SQLite e PostgreSQL 16.", "alembic/versions/0002_ciclos_parametros_falhas_e_usuarios.py"),
    etapa("Implementadas", " as consultas de situação atual (RF14) e de histórico de trânsito resumido por via, além das leituras do cruzamento com filtros (RF15).", "app/services/consulta_service.py, Figura 9"),
    etapa("Implementados", " os parâmetros editáveis pela API (RF16), a duração de ciclo própria por cruzamento e os tempos de verde padrão para novos semáforos.", "app/services/parametro_service.py"),
    etapa("Implementado", " o registro de falhas (RF18): verificação periódica de ausência de leitura, falha de cálculo indisponível e registro e resolução manual; a falha se encerra quando chega nova leitura.", "app/services/falha_service.py"),
    etapa("Implementada", " a autenticação (RNF07): login OAuth2 com JWT, perfis administrador e operador, chave de API do sistema de detecção e senhas com PBKDF2-SHA256.", "app/api/deps.py, app/core/seguranca.py"),
    etapa("Escritos", " 111 testes automatizados (na versão 1.2) — 32 do motor, 44 de integração da API, 17 da lógica do contador YOLO, 7 de tempo real, 4 de configuração, 3 da simulação, 2 de segurança e 2 de migração —, todos aprovados em SQLite e PostgreSQL 16.", "tests/"),
    etapa("Configurada", " a integração contínua com 4 jobs (lint e testes em Python 3.11 e 3.12, migrações e testes em PostgreSQL 16, imagem Docker com docker compose), todos aprovados na execução de 24/11/2026.", ".github/workflows/ci.yml"),
    tabela(
      [
        { titulo: "Job do GitHub Actions", largura: 7138 },
        { titulo: "Resultado", largura: 2500 },
      ],
      [
        ["Lint e testes (SQLite, Python 3.11)", "Aprovado"],
        ["Lint e testes (SQLite, Python 3.12)", "Aprovado"],
        ["Migrações e testes (PostgreSQL 16)", "Aprovado"],
        ["Imagem Docker e docker compose (health check)", "Aprovado"],
      ],
      { formatar: (v, j) => (j === 1 ? situacao(v) : null) },
    ),
    etapa("Medido", " o desempenho (RNF10) com 500 lotes de 4 leituras, cada um gravando leituras e um ciclo, no ambiente de desenvolvimento (contêiner Linux com 4 vCPUs); resultados na tabela abaixo.", "scripts/benchmark.py"),
    tabela(
      [
        { titulo: "Operação", largura: 3838 },
        { titulo: "SQLite p50", largura: 1450 },
        { titulo: "SQLite p95", largura: 1450 },
        { titulo: "PostgreSQL p50", largura: 1450 },
        { titulo: "PostgreSQL p95", largura: 1450 },
      ],
      [
        ["Envio de lote + geração do ciclo", "14,3 ms", "22,2 ms", "20,2 ms", "27,4 ms"],
        ["Consulta da situação atual", "7,4 ms", "9,7 ms", "10,8 ms", "14,2 ms"],
      ],
      { formatar: (v, j) => (j > 0 ? { alinhamento: AlignmentType.CENTER } : null) },
    ),
    h2("Incrementos para o pitch (versões 1.1 e 1.2)"),
    etapa("Implementados", " os estágios (vias compatíveis abrem juntas), a regra de Webster (ciclo C = (1,5·L + 5) ÷ (1 − Y), entre 40 e 150 s) e o modo de segurança: sem leitura recente, o ciclo usa o plano fixo e a falha é registrada.", "app/motor/estagios.py, app/motor/regras.py, migração 0003"),
    etapa("Simulada", " a operação de um cruzamento de avenida × rua das 6h às 22h, segundo a segundo, comparando o tempo fixo com as regras do GSA sob as mesmas chegadas de veículos (tabela abaixo e Figura 10). A demanda é sintética: os números comparam estratégias, não são medição em campo.", "scripts/simulacao_comparativa.py, simulacao/"),
    tabela(
      [
        { titulo: "Estratégia (5 sementes, 06h–22h)", largura: 3838 },
        { titulo: "Espera média — moderada", largura: 1950 },
        { titulo: "Espera média — alta (+40%)", largura: 1950 },
        { titulo: "p95 — alta", largura: 1900 },
      ],
      [
        ["Tempo fixo — divisão igual (90 s)", "18,2 s", "64,7 s", "387 s"],
        ["Tempo fixo — ajustado à média do dia", "12,2 s", "225,0 s", "1405 s"],
        ["GSA — proporcional", "13,6 s", "28,4 s", "69 s"],
        ["GSA — Webster", "11,2 s", "15,6 s", "46 s"],
      ],
      { formatar: (v, j) => (j > 0 ? { alinhamento: AlignmentType.CENTER } : null) },
    ),
    etapa("Criado", " o painel web ao vivo, servido pela API em /painel e atualizado por Server-Sent Events (GET /eventos): semáforos animados por estágio, indicadores, vias, gráficos, falhas abertas e a comparação da simulação (Figuras 11 e 12).", "app/painel/, app/core/eventos.py"),
    etapa("Criado", " o roteiro de demonstração, que envia um dia de tráfego acelerado e simula a falha de uma câmera, mostrando a entrada no modo de segurança e a volta ao controle adaptativo; gravado em vídeo como reserva.", "scripts/demo_pitch.py, docs/demo/"),
    etapa("Implementado", " um sistema de detecção de exemplo com YOLO e ByteTrack, que conta veículos por zona de cada via e envia os lotes com X-API-Key. Foi validado com um vídeo de amostra filmado de cima, ângulo em que o modelo médio reconheceu os carros e o pequeno não (Figura 13).", "deteccao/"),
    etapa("Preparado", " o deploy com URL pública no Render: blueprint com a API e um banco PostgreSQL, segredos gerados pela plataforma e senhas de demonstração definidas por variável de ambiente.", "render.yaml, scripts/iniciar.sh"),
    h2("Situação dos requisitos"),
    tabela(
      [
        { titulo: "Tipo", largura: 3638 },
        { titulo: "Atendidos", largura: 2000 },
        { titulo: "Parciais", largura: 2000 },
        { titulo: "Pendentes", largura: 2000 },
      ],
      [
        ["Funcionais (18)", "18", "0", "0"],
        ["Não funcionais (10)", "10", "0", "0"],
      ],
      {
        formatar: (v, j) =>
          j === 1 ? { ...situacao("Atendido"), alinhamento: AlignmentType.CENTER }
          : j > 1 ? { alinhamento: AlignmentType.CENTER }
          : { negrito: true },
      },
    ),
    p([t("O detalhamento por requisito está no Anexo A; os prints da API em funcionamento estão no Anexo B.", { color: COR.suave, size: 19 })], { spacing: { before: 120 } }),
  ];
}

function secaoConclusao() {
  return [
    h1("7. Conclusão e evolução futura"),
    p("O backend cumpre o escopo do MVP: recebe as contagens do sistema de detecção, calcula e grava um novo ciclo a cada lote, mantém o histórico de leituras e ciclos, registra falhas e expõe tudo por uma API REST documentada e protegida por perfis. A regra de temporização ficou isolada no motor de cálculo, o que permitiu acrescentar a regra de Webster e o plano fixo de segurança sem alterar rotas nem banco. Os incrementos para o pitch (painel ao vivo, simulação comparativa, contador YOLO e deploy) mostram o sistema funcionando de ponta a ponta."),
    p("Ficam como evolução, fora do escopo desta versão:"),
    bullet("Validar a detecção com vídeo de um cruzamento real, em ângulo oblíquo, e medir o efeito em campo com um piloto (os ganhos atuais vêm de simulação)."),
    bullet("Integração com controladores físicos de semáforo; hoje o GSA calcula e publica o plano, mas não o envia a um controlador."),
    bullet("Coordenação entre cruzamentos vizinhos (onda verde)."),
    bullet("Intermediário de mensagens (ex.: Redis) para o canal de eventos funcionar com vários processos, além de monitoramento."),
  ];
}

const RASTREABILIDADE = [
  ["RF01", "Cadastro de cruzamentos", "Atendido", "/cruzamentos · test_api_cadastros"],
  ["RF02", "Cadastro de vias", "Atendido", "/cruzamentos/{id}/vias, /vias/{id} · test_api_cadastros"],
  ["RF03", "Cadastro de semáforos", "Atendido", "/vias/{id}/semaforo, /semaforos/{id} · test_api_cadastros"],
  ["RF04", "Endpoint de recebimento de leituras", "Atendido", "POST /cruzamentos/{id}/leituras · test_api_leituras_ciclos"],
  ["RF05", "Registro de cada leitura", "Atendido", "tabela leituras_trafego · test_api_leituras_ciclos"],
  ["RF06", "Cálculo da demanda", "Atendido", "app/motor/demanda.py · test_motor_calculo"],
  ["RF07", "Classificação do fluxo", "Atendido", "app/motor/classificacao.py · test_motor_calculo"],
  ["RF08", "Tempo de verde recomendado", "Atendido", "app/motor/regras.py · test_motor_calculo"],
  ["RF09", "Distribuição proporcional", "Atendido", "app/motor/regras.py · test_motor_calculo"],
  ["RF10", "Garantia de verde mínimo", "Atendido", "app/motor/regras.py · test_motor_calculo"],
  ["RF11", "Limite de verde máximo", "Atendido", "app/motor/regras.py · test_motor_calculo"],
  ["RF12", "Geração de novo ciclo", "Atendido", "ciclo a cada lote e calcular-ciclo · test_api_leituras_ciclos"],
  ["RF13", "Histórico de ciclos", "Atendido", "/cruzamentos/{id}/ciclos, /ciclos/{id} · test_api_leituras_ciclos"],
  ["RF14", "Situação atual do cruzamento", "Atendido", "/cruzamentos/{id}/situacao · test_api_consultas"],
  ["RF15", "Histórico de trânsito", "Atendido", "/historico e /leituras do cruzamento e da via · test_api_consultas"],
  ["RF16", "Configuração dos parâmetros", "Atendido", "GET/PUT /parametros · test_api_consultas"],
  ["RF17", "Ativação e desativação", "Atendido", "/ativar, /desativar, DELETE lógico · test_api_cadastros"],
  ["RF18", "Registro de falhas", "Atendido", "/falhas, verificação periódica, modo de segurança · test_api_falhas, test_api_modos_regras"],
  ["RNF01", "API REST", "Atendido", "app/api/routes (38 operações)"],
  ["RNF02", "Persistência em banco", "Atendido", "SQLAlchemy + Alembic · test_migracoes"],
  ["RNF03", "Comunicação em JSON", "Atendido", "schemas Pydantic (camelCase)"],
  ["RNF04", "Validação de dados", "Atendido", "Pydantic + services · testes de 400"],
  ["RNF05", "Documentação Swagger/OpenAPI", "Atendido", "/docs com Authorize (Figuras 6 e 7)"],
  ["RNF06", "Códigos HTTP adequados", "Atendido", "app/main.py (handlers) · test_api_*"],
  ["RNF07", "Autenticação administrativa", "Atendido", "JWT, perfis e X-API-Key · test_api_autenticacao"],
  ["RNF08", "Modularidade", "Atendido", "camadas + app/motor (Figura 1)"],
  ["RNF09", "Manutenibilidade das regras", "Atendido", "protocolo RegraTemporizacao (proporcional, Webster, plano fixo)"],
  ["RNF10", "Desempenho", "Atendido", "scripts/benchmark.py (seção 6)"],
];

function anexos() {
  return [
    h1("Anexo A — Rastreabilidade dos requisitos"),
    tabela(
      [
        { titulo: "Código", largura: 1000 },
        { titulo: "Requisito", largura: 3038 },
        { titulo: "Situação", largura: 1300 },
        { titulo: "Implementação · teste", largura: 4300 },
      ],
      RASTREABILIDADE,
      {
        formatar: (v, j) =>
          j === 0 ? { negrito: true } : j === 2 ? situacao(v) : j === 3 ? { tamanho: 17, cor: COR.suave } : null,
      },
    ),
    h1("Anexo B — Evidências"),
    ...figura("swagger_endpoints_1.png", 4.8, "Figura 6 — Swagger UI (parte 1): autenticação, cadastros e leituras; o cadeado indica rota protegida"),
    ...figura("swagger_endpoints_2.png", 6.0, "Figura 7 — Swagger UI (parte 2): ciclos, consultas, parâmetros, falhas e sistema", true),
    ...figura("swagger_leituras.png", 6.3, "Figura 8 — Envio do lote do exemplo do documento (30 e 10 veículos) com X-API-Key: ciclo gravado com 60 s e 20 s de verde", true),
    ...figura("swagger_situacao.png", 6.3, "Figura 9 — Situação atual do cruzamento de quatro vias (RF14)", true),
    ...figura("simulacao_resumo.png", 6.6, "Figura 10 — Simulação: espera média por veículo em cada estratégia, com demanda moderada e alta (demanda sintética)", true),
    ...figura("painel_pico.png", 6.6, "Figura 11 — Painel ao vivo no pico da tarde do roteiro de demonstração: ciclo de 71 s pela regra de Webster", true),
    ...figura("painel_contingencia.png", 5.2, "Figura 12 — Painel em modo de segurança: câmera de uma via parada, plano fixo de 120 s e falha registrada", true),
    ...figura("yolo_quadro.png", 6.0, "Figura 13 — Contador YOLO no vídeo de amostra (intel-iot-devkit/sample-videos, CC BY 4.0): dois carros detectados na zona da Via A", true),
  ];
}

// ---------- Documento ----------
const cabecalho = new Header({
  children: [
    new Paragraph({
      alignment: AlignmentType.RIGHT,
      children: [t("Relatório Final · Sistema de Gestão Semafórica Adaptativa", { size: 16, color: COR.suave })],
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
  title: "Relatório Final — Sistema de Gestão Semafórica Adaptativa",
  description: "Relatório final da disciplina Back-end Frameworks",
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
        ...secaoConclusao(),
        ...anexos(),
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SAIDA, buf);
  console.log(`Gerado ${SAIDA}`);
});
