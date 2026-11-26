# Sistema de Gestão Semafórica Adaptativa (GSA)

Backend que recebe a contagem de veículos por via de um cruzamento, aplica regras de negócio
configuráveis e calcula automaticamente o tempo de sinal verde de cada semáforo, guardando o
histórico de leituras, ciclos e falhas. Um painel web mostra o cruzamento ao vivo.

A decisão **não usa inteligência artificial**: a detecção e a contagem de veículos ficam a cargo de
um sistema externo de visão computacional (YOLO), que envia os números para a API. O backend
distribui o verde entre os estágios do cruzamento pela regra proporcional do documento de
requisitos ou pela regra de Webster, respeitando os tempos mínimo e máximo de cada semáforo, e
cai para um plano fixo de segurança quando faltam leituras.

> **Situação:** versão `1.2.0`. As 8 fases do cronograma estão concluídas, com os 18 requisitos
> funcionais e os 10 não funcionais atendidos (rastreabilidade no relatório final). As versões
> 1.1 e 1.2 acrescentaram recursos para o pitch: estágios, regra de Webster, modo de segurança,
> simulação comparativa, painel ao vivo, contador YOLO e deploy.
>
> - Relatório final: [`docs/relatorio/Relatorio_Final_GSA.pdf`](docs/relatorio/Relatorio_Final_GSA.pdf)
> - Relatório parcial (01/10/2026): [`docs/relatorio/parcial/`](docs/relatorio/parcial/)
> - Roteiro do pitch: [`docs/pitch/ROTEIRO.md`](docs/pitch/ROTEIRO.md)
> - Requisitos e escopo: [`docs/requisitos/`](docs/requisitos/)

Disciplina: **Back-end Frameworks** · Orientador: **Wilson Cosmos**

![Painel ao vivo durante a demonstração: modo adaptativo, falha de câmera com modo de segurança e volta ao adaptativo](docs/demo/demo_painel.gif)

## Equipe

| Integrante | Matrícula | Função |
|---|---|---|
| Délcio Farias Dias Neto | 04183547 | Líder técnico — arquitetura e motor de cálculo |
| João Pedro Bezerra dos Santos Ranieri | 04184381 | Banco de dados — modelagem, ORM e migrações |
| Erick Eduardo Campos Matias | 04186589 | API — endpoints de cadastro e de leituras |
| Nelson Paulo Santiago Barroso | 04180548 | Qualidade e documentação — testes, Swagger e relatórios |

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Framework web | FastAPI (servidor ASGI Uvicorn) |
| ORM e migrações | SQLAlchemy 2 + Alembic |
| Validação e configuração | Pydantic v2 + pydantic-settings |
| Banco de dados | SQLite (desenvolvimento) · PostgreSQL 16 (produção) |
| Segurança | JWT (PyJWT), OAuth2 password flow, senhas com PBKDF2-SHA256, chave de API |
| Tempo real | Server-Sent Events (`GET /eventos`) |
| Painel web | HTML, CSS e JavaScript sem dependências, servido pela própria API |
| Documentação | Swagger UI / OpenAPI (gerados pelo FastAPI) |
| Testes e qualidade | pytest · Ruff · GitHub Actions |
| Implantação | Docker · docker compose · Render (blueprint `render.yaml`) |
| Diagramas | Graphviz |
| Detecção de veículos | YOLO (Ultralytics) + ByteTrack — contador de exemplo em `deteccao/`, fora da API |

## Como executar

### Local (SQLite)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env                 # defina GSA_JWT_SEGREDO e GSA_CHAVE_API_DETECCAO
alembic upgrade head                 # cria as tabelas
python -m scripts.seed               # dados de demonstração (usuários, 2 cruzamentos, 6 h de leituras)
uvicorn app.main:app --reload
```

- Painel ao vivo: <http://127.0.0.1:8000/> (redireciona para `/painel/`)
- Swagger UI: <http://127.0.0.1:8000/docs> (botão **Authorize** para login ou chave de API)
- ReDoc: <http://127.0.0.1:8000/redoc>
- Saúde da API: <http://127.0.0.1:8000/health>

### Docker (API + PostgreSQL)

```bash
# no .env: GSA_JWT_SEGREDO=... e GSA_CHAVE_API_DETECCAO=...
docker compose up --build
docker compose exec api python -m scripts.criar_usuario --nome "Admin" --email admin@exemplo.com
```

O contêiner aplica as migrações pendentes ao iniciar (`scripts/iniciar.sh`) e escuta na porta
`$PORT` (padrão 8000). Com `GSA_SEED_AO_INICIAR=1`, popula a demonstração se o banco estiver vazio.
A integração contínua sobe esse mesmo `docker compose` e verifica o `/health` a cada push.

### Banco novo sem dados de demonstração

```bash
alembic upgrade head
python -m scripts.criar_usuario --nome "Maria" --email maria@exemplo.com --perfil administrador
```

## Demonstração para o pitch

Com a API rodando sobre o banco do `scripts.seed` e o painel aberto em
<http://127.0.0.1:8000/painel/?cruzamento=2>:

```bash
export GSA_CHAVE_API_DETECCAO=...   # a mesma chave da API
export GSA_DEMO_SENHA_ADMIN=...     # senha do admin@gsa.local (admin123 no seed local)
python -m scripts.demo_pitch --cruzamento 2 --intervalo 1.5
```

O roteiro envia um dia de tráfego acelerado (picos às 8h e às 18h, demanda do cenário alto) e,
no meio, para a "câmera" de uma via: o cruzamento entra no modo de segurança, a falha aparece no
painel e, quando a câmera volta, o controle adaptativo retorna. A tolerância sem leitura é
reduzida para 30 s durante o roteiro e restaurada no fim. Vídeo de reserva:
[`docs/demo/demo_painel.mp4`](docs/demo/demo_painel.mp4).

## Autenticação e perfis (RNF07)

| Quem | Como se autentica | Pode |
|---|---|---|
| Qualquer cliente | — | Consultas (`GET`), `/eventos`, painel e `/health` |
| Sistema de detecção | Cabeçalho `X-API-Key` (`GSA_CHAVE_API_DETECCAO`) | Enviar leituras |
| Operador | Token Bearer (`POST /auth/login`) | Enviar leituras, calcular ciclo manualmente, registrar/resolver falhas |
| Administrador | Token Bearer | Tudo o que o operador faz + cadastros, parâmetros, ativação e usuários |

Usuários criados pelo `scripts.seed`: `admin@gsa.local` e `operador@gsa.local`. Sem as variáveis
`GSA_SEED_SENHA_ADMIN` e `GSA_SEED_SENHA_OPERADOR`, as senhas são `admin123` e `operador123`
(**somente para demonstração local**; em ambiente público defina as variáveis).

```bash
curl -X POST http://127.0.0.1:8000/auth/login -d "username=admin@gsa.local&password=admin123"
```

## Exemplo de uso

Envio de leituras pelo sistema de detecção (RF04). Cada lote grava as leituras e gera um ciclo:

```bash
curl -X POST http://127.0.0.1:8000/cruzamentos/1/leituras \
  -H "X-API-Key: $GSA_CHAVE_API_DETECCAO" -H "Content-Type: application/json" \
  -d '{"cruzamentoId": 1, "leituras": [{"viaId": 1, "quantidadeVeiculos": 30}, {"viaId": 2, "quantidadeVeiculos": 10}]}'
```

Com ciclo de 90 s e semáforos de 3 s de amarelo e 2 s de vermelho de segurança, sobram 80 s de
verde: a via A (30 veículos, 75 %) recebe **60 s** e a via B (10 veículos, 25 %) recebe **20 s** —
o mesmo exemplo do documento de requisitos. A resposta traz o ciclo gravado em `cicloGerado`.

Acompanhar os eventos em tempo real:

```bash
curl -N http://127.0.0.1:8000/eventos               # todos os cruzamentos
curl -N "http://127.0.0.1:8000/eventos?cruzamentoId=1"
```

## Regra de cálculo

**Estágios.** Vias com o mesmo `estagio` recebem verde juntas (ex.: os dois sentidos de uma
avenida); vias sem estágio formam um estágio próprio. O entreverde de cada estágio é o maior
amarelo + vermelho de segurança entre as suas vias.

**Proporcional** (`regraTemporizacao = proporcional`, a do documento de requisitos):

1. **Duração do ciclo**: a do cruzamento (`duracaoCiclo`) ou, se vazia, o parâmetro global (RF16).
2. **Verde disponível** = duração do ciclo − soma dos entreverdes.
3. **Demanda** de cada via = veículos da última leitura ÷ total do cruzamento (RF06); a de um
   estágio é a da sua via mais carregada.
4. **Classificação do fluxo** por veículos por faixa: baixo ≤ 5 < moderado ≤ 15 < alto ≤ 25 < crítico
   (limites editáveis em `PUT /parametros`) (RF07).
5. **Distribuição proporcional** do verde disponível conforme a demanda (RF08/RF09).
6. Estágios abaixo do **verde mínimo** são travados no mínimo (RF10) e acima do **máximo** são
   travados no máximo (RF11); o tempo restante é redistribuído entre os demais.
7. Sem veículos, o verde é dividido igualmente; os segundos são arredondados sem perder tempo do ciclo.

**Webster** (`regraTemporizacao = webster`): a duração do ciclo também passa a depender da demanda.

- fluxo de cada via q = veículos × 3600 ÷ `intervaloContagem` (veíc/h);
- razão de fluxo y = q ÷ (`fluxoSaturacaoPorFaixa` × faixas); a do estágio é a maior entre as vias;
- ciclo C = (1,5·L + 5) ÷ (1 − Y), com Y = soma das razões e L = soma dos entreverdes, limitado
  entre `cicloMinimo` e `cicloMaximo` (com Y ≥ 0,9 usa o máximo);
- o verde (C − L) é dividido pelas razões de fluxo, com os mesmos limites mínimo e máximo.

**Modo de segurança.** Se alguma via ativa está sem leitura há mais de `tempoMaximoSemLeitura`,
o ciclo usa o **plano fixo** (verde igual entre os estágios, com a duração do ciclo do cruzamento),
`modoOperacao = contingencia` e o motivo em `motivoContingencia`. Quando as leituras voltam, o
cálculo adaptativo retorna sozinho.

As regras ficam em `app/motor/regras.py` atrás do protocolo `RegraTemporizacao`: uma nova regra
entra sem alterar rotas nem banco (RNF09).

## Simulação: tempo fixo × adaptativo

`python -m scripts.simulacao_comparativa --sementes 5` simula, segundo a segundo, um cruzamento de
avenida (2 faixas por sentido) × rua (1 faixa por sentido) das 6h às 22h, com picos às 8h e às 18h,
usando o mesmo motor de cálculo da API. Todas as estratégias recebem as mesmas chegadas.

| Estratégia | Espera média — moderada | Espera média — alta (+40 %) | p95 — alta |
|---|---|---|---|
| Tempo fixo — divisão igual (90 s) | 18,2 s | 64,7 s | 387 s |
| Tempo fixo — ajustado à média do dia | 12,2 s | 225,0 s | 1405 s |
| GSA — proporcional | 13,6 s | 28,4 s | 69 s |
| GSA — Webster | 11,2 s | 15,6 s | 46 s |

Demanda sintética e modelo de filas simplificado (premissas em `simulacao/modelo.py`): a tabela
compara estratégias sob as mesmas condições, **não** é medição em via real. Gráficos em
`docs/img/simulacao_*.png` e no painel.

## Detecção com YOLO

[`deteccao/`](deteccao/README.md) traz um sistema de detecção de exemplo, que roda fora da API:
YOLO detecta veículos, o ByteTrack dá um id a cada um, cada via é uma zona (polígono) no quadro e,
a cada janela de tempo, o total por via vai para `POST /cruzamentos/{id}/leituras` com `X-API-Key`.

```bash
pip install -r requirements-yolo.txt   # ambiente separado (PyTorch é grande)
python -m deteccao.contador_yolo --video meu_cruzamento.mp4 \
  --config deteccao/exemplo_zonas.json --modelo yolo11m.pt --saida anotado.mp4
```

Validado com um vídeo de amostra (CC BY 4.0) filmado de cima: o pipeline funcionou de ponta a
ponta, mas nesse ângulo o modelo pequeno confundiu carros com outros objetos e o médio acertou.
Detalhes e limitações em [`deteccao/README.md`](deteccao/README.md);
vídeo anotado em [`docs/demo/yolo_validacao.mp4`](docs/demo/yolo_validacao.mp4).

## Endpoints (38 operações)

Acesso: **P** público · **D** sistema de detecção (`X-API-Key`) ou usuário logado ·
**O** operador ou administrador · **A** administrador.

| Método | Rota | Requisito | Acesso |
|---|---|---|---|
| POST | `/auth/login` | RNF07 | P |
| GET | `/auth/me` | RNF07 | logado |
| GET / POST | `/usuarios` | RNF07 | A |
| GET / POST | `/cruzamentos` (filtro `?status=`) | RF01 | P / A |
| GET / PUT / DELETE | `/cruzamentos/{id}` (DELETE = desativação lógica) | RF01/RF17 | P / A / A |
| POST | `/cruzamentos/{id}/ativar` · `/cruzamentos/{id}/desativar` | RF17 | A |
| GET / POST | `/cruzamentos/{id}/vias` | RF02 | P / A |
| GET / PUT | `/vias/{id}` | RF02 | P / A |
| GET / POST | `/vias/{id}/semaforo` | RF03 | P / A |
| GET | `/cruzamentos/{id}/semaforos` | RF03 | P |
| GET / PUT | `/semaforos/{id}` | RF03 | P / A |
| GET / POST | `/cruzamentos/{id}/leituras` (lote; gera ciclo) | RF04/RF05/RF12/RF15 | P / D |
| GET / POST | `/vias/{id}/leituras` | RF05/RF15 | P / D |
| POST | `/cruzamentos/{id}/calcular-ciclo` (`?simular=true` não grava) | RF06–RF12 | O |
| GET | `/cruzamentos/{id}/ciclos` · `/ciclos/{id}` | RF13 | P |
| GET | `/cruzamentos/{id}/situacao` | RF14 | P |
| GET | `/cruzamentos/{id}/historico` (`inicio`, `fim`) | RF15 | P |
| GET / PUT | `/parametros` | RF16 | P / A |
| GET | `/falhas` · `/cruzamentos/{id}/falhas` | RF18 | P |
| POST | `/cruzamentos/{id}/falhas` · `/falhas/{id}/resolver` · `/falhas/verificar` | RF18 | O |
| GET | `/eventos` (SSE; filtro `?cruzamentoId=`) | — | P |
| GET | `/health` | — | P |

Erros seguem um formato único (`status`, `erro`, `mensagem`, `detalhes`) com os códigos 200, 201,
400, 401, 403, 404 e 500. Dados inválidos retornam **400** (o 422 padrão do FastAPI foi substituído).

`GET /eventos` envia `event: ciclo`, `event: leituras` e `event: falha`, cada um com
`{"tipo", "em", "dados"}`. O canal funciona em um único processo; com vários workers seria preciso
um intermediário externo (ex.: Redis).

## Falhas (RF18)

- **Ausência de leitura:** a API verifica a cada `GSA_INTERVALO_VERIFICACAO_FALHAS` segundos se alguma
  via monitorada (cruzamento e semáforo ativos) está sem leitura há mais que `tempoMaximoSemLeitura`
  (parâmetro). A falha é encerrada sozinha quando chega uma nova leitura da via. Enquanto isso, os
  ciclos do cruzamento usam o modo de segurança.
- **Cálculo indisponível:** registrada quando um lote chega a um cruzamento sem semáforo ativo.
- **Manual:** registrada pelo operador (`POST /cruzamentos/{id}/falhas`).

## Testes, qualidade e desempenho

```bash
pytest                                   # 111 testes (motor, API, segurança, migrações, tempo real,
                                         # simulação e lógica do contador YOLO)
GSA_TESTE_DATABASE_URL=postgresql+psycopg://usuario:senha@localhost/banco_vazio pytest
ruff check . && ruff format --check .
python -m scripts.benchmark --lotes 500  # RNF10
```

A integração contínua (`.github/workflows/ci.yml`) roda lint e testes em SQLite (Python 3.11 e
3.12), migrações e testes em PostgreSQL 16, e sobe a imagem com `docker compose`.

Benchmark medido em 24/11/2026 na versão 1.0, no ambiente de desenvolvimento (contêiner Linux,
4 vCPUs), 500 lotes de 4 leituras, cada lote gravando leituras e um ciclo:

| Operação | SQLite p50 / p95 | PostgreSQL 16 p50 / p95 |
|---|---|---|
| `POST /cruzamentos/{id}/leituras` + geração do ciclo | 14,3 / 22,2 ms | 20,2 / 27,4 ms |
| `GET /cruzamentos/{id}/situacao` | 7,4 / 9,7 ms | 10,8 / 14,2 ms |

## Deploy com URL pública (Render)

O arquivo [`render.yaml`](render.yaml) descreve a API (imagem Docker) e um banco PostgreSQL:

1. No Render, **New → Blueprint** e escolha este repositório.
2. O Render gera `GSA_JWT_SEGREDO`, `GSA_CHAVE_API_DETECCAO` e as senhas dos usuários de
   demonstração (`GSA_SEED_SENHA_ADMIN`, `GSA_SEED_SENHA_OPERADOR`); o banco é populado no
   primeiro início (`GSA_SEED_AO_INICIAR=1`).
3. Depois do deploy, o painel fica em `https://<serviço>.onrender.com/painel/`. Para a
   demonstração, rode o roteiro do seu computador apontando para a URL pública:
   `python -m scripts.demo_pitch --base-url https://<serviço>.onrender.com --cruzamento 2`.

Confira no site do Render as condições atuais dos planos gratuitos (hibernação do serviço e
validade do banco gratuito, por exemplo) antes de depender deles no dia da apresentação.

## Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `GSA_DATABASE_URL` | `sqlite:///./gsa.db` | Conexão com o banco (`postgres://` e `postgresql://` são aceitas) |
| `GSA_JWT_SEGREDO` | aleatório a cada início | Assinatura dos tokens (defina em produção) |
| `GSA_JWT_EXPIRACAO_MINUTOS` | `60` | Validade do token |
| `GSA_CHAVE_API_DETECCAO` | — | Chave do sistema de detecção (`X-API-Key`) |
| `GSA_INTERVALO_VERIFICACAO_FALHAS` | `60` | Segundos entre verificações (0 desativa) |
| `GSA_DURACAO_CICLO_PADRAO`, `GSA_LIMITE_FLUXO_*`, `GSA_VERDE_*_PADRAO`, `GSA_TEMPO_MAXIMO_SEM_LEITURA` | ver `.env.example` | Valores iniciais dos parâmetros; depois valem os de `PUT /parametros` |
| `GSA_FLUXO_SATURACAO_POR_FAIXA`, `GSA_INTERVALO_CONTAGEM`, `GSA_CICLO_MINIMO`, `GSA_CICLO_MAXIMO` | `1800`, `90`, `40`, `150` | Valores iniciais da regra de Webster |
| `PORT` | `8000` | Porta do contêiner |
| `GSA_SEED_AO_INICIAR` | `0` | `1` popula a demonstração ao iniciar o contêiner |
| `GSA_SEED_SENHA_ADMIN`, `GSA_SEED_SENHA_OPERADOR` | `admin123`, `operador123` | Senhas dos usuários do seed |

## APIs utilizadas

| API | Tipo | Função no projeto | Situação |
|---|---|---|---|
| API REST própria (FastAPI) | Interna | Cadastros, leituras, ciclos, consultas, parâmetros, falhas e autenticação | Em uso |
| Eventos em tempo real (SSE, `/eventos`) | Interna | Atualiza o painel quando chegam ciclos, leituras e falhas | Em uso |
| Swagger UI / OpenAPI (`/docs`, `/openapi.json`) | Interna | Documentação interativa da API | Em uso |
| Sistema de detecção de veículos (YOLO) | Externa (envia dados) | Envia a contagem por via para `POST /cruzamentos/{id}/leituras` com `X-API-Key` | Contador de exemplo em `deteccao/`, validado com vídeo de amostra; simulado por script nas demonstrações |

## Estrutura

```
app/
├── api/routes/      # controllers (rotas FastAPI), incluindo /eventos (SSE)
├── api/deps.py      # sessão do banco, autenticação e perfis
├── services/        # regras de negócio e validações
├── repositories/    # acesso ao banco (SQLAlchemy)
├── motor/           # motor de cálculo — estágios e regras, sem FastAPI nem banco
├── models/          # entidades do banco
├── schemas/         # contratos JSON (Pydantic)
├── core/            # configuração, exceções, segurança e canal de eventos
├── db/              # engine, sessão e tipos
└── painel/          # painel web ao vivo (HTML, CSS e JS)
alembic/             # migrações do banco (0001 a 0003)
simulacao/           # modelo de filas da simulação comparativa
deteccao/            # contador de veículos com YOLO (sistema de detecção de exemplo)
scripts/             # seed, demonstração do pitch, simulação, simulador de detecção, benchmark
tests/               # testes automatizados (pytest)
docs/                # relatórios, requisitos, diagramas, imagens, vídeos e roteiro do pitch
```

## Cronograma

| Fase | Responsável | Período (2026) | Situação |
|---|---|---|---|
| 1. Estruturação do projeto | Délcio | 03/09 – 09/09 | Concluída |
| 2. Modelagem do banco de dados | João Pedro | 08/09 – 16/09 | Concluída |
| 3. Cadastros (CRUD básico) | Erick | 14/09 – 23/09 | Concluída |
| 4. Recebimento de leituras | Erick | 21/09 – 28/09 | Concluída |
| 5. Motor de cálculo e testes unitários | Délcio · Nelson | 22/09 – 30/09 | Concluída |
| Relatório parcial | Nelson | 28/09 – 01/10 | Concluída |
| 6. Geração de ciclos e histórico | João Pedro | 05/10 – 16/10 | Concluída |
| 7. Consultas e configurações | Erick | 19/10 – 30/10 | Concluída |
| 8. Documentação, segurança e testes | Nelson · Délcio | 03/11 – 13/11 | Concluída |
| Revisão e relatório final | Equipe | 16/11 – 24/11 | Concluída |
| Incrementos para o pitch (v1.1 e v1.2) | Equipe | 24/11 | Concluída |

## Documentação

| Arquivo | Como regenerar |
|---|---|
| `docs/relatorio/Relatorio_Final_GSA.docx` / `.pdf` | `cd docs/relatorio && npm install && npm run final`, depois `soffice --headless --convert-to pdf Relatorio_Final_GSA.docx` |
| `docs/relatorio/parcial/` | Relatório parcial entregue em 01/10/2026, com as imagens e diagramas da época (`npm run parcial`) |
| `docs/img/fluxo*.png`, `arquitetura.png` | `dot -Tpng -Gdpi=200 docs/diagramas/<arquivo>.dot -o docs/img/<arquivo>.png` (Graphviz) |
| `docs/img/cronograma.png` | `python docs/diagramas/cronograma.py` e `rsvg-convert -z 2.5 docs/diagramas/cronograma.svg -o docs/img/cronograma.png` |
| `docs/img/simulacao_*`, `app/painel/simulacao.json` | `python -m scripts.simulacao_comparativa --sementes 5` |
| `docs/img/swagger_*.png`, `painel_*.png` | Capturas com a API rodando sobre o banco do `scripts.seed` |
| `docs/demo/demo_painel.mp4` / `.gif` | Gravação do painel (Playwright) durante `scripts.demo_pitch` |
| `docs/demo/yolo_validacao.mp4` | Saída de `deteccao.contador_yolo` no vídeo de amostra |
| `docs/pitch/ROTEIRO.md` | Roteiro da apresentação e checklist da demonstração |

## Limitações e evolução futura

- A detecção foi validada com vídeo de amostra; falta um vídeo de cruzamento real em ângulo oblíquo.
- Integração com controladores físicos de semáforo (o GSA calcula e publica o plano; não o envia
  a um controlador).
- Coordenação entre cruzamentos vizinhos (onda verde).
- Os ganhos vêm de simulação com demanda sintética; um piloto com contagem em campo é o passo
  seguinte para medir o efeito real.
- O canal de eventos funciona em um processo; para vários workers, usar um intermediário (Redis).
