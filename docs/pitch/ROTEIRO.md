# Roteiro do pitch — GSA

O deck tem 13 slides. A divisão abaixo é uma sugestão para cerca de 10 minutos; ajuste ao tempo
definido pelo professor.

| Bloco | Slides | Quem apresenta | Tempo |
|---|---|---|---|
| Abertura e problema | 1 – 2 | Délcio | 1 min |
| Solução e regras de cálculo | 3 – 4 | Délcio | 1,5 min |
| Resultados da simulação | 5 – 6 | Nelson | 1,5 min |
| Modo de segurança | 7 | João Pedro | 1 min |
| Demonstração ao vivo | 8 | Erick (conduz) · Délcio (narra) | 3 min |
| YOLO, tecnologia e próximos passos | 9 – 11 | Nelson · João Pedro | 1,5 min |
| Equipe e encerramento | 12 – 13 | Todos | 0,5 min |

## Antes da apresentação

1. Ambiente com as dependências: `pip install -r requirements-dev.txt`.
2. Banco novo e dados de demonstração:
   ```bash
   alembic upgrade head
   python -m scripts.seed
   ```
3. Defina as variáveis no terminal que vai subir a API **e** no que vai rodar o roteiro:
   ```bash
   export GSA_CHAVE_API_DETECCAO=uma-chave-qualquer-para-a-demo
   export GSA_JWT_SEGREDO=um-segredo-qualquer-para-a-demo
   export GSA_DEMO_SENHA_ADMIN=admin123     # senha do admin@gsa.local no seed local
   ```
4. Suba a API: `uvicorn app.main:app` e abra <http://127.0.0.1:8000/painel/?cruzamento=2> no
   navegador, em tela cheia (F11). Confira o indicador **ao vivo** no topo.
5. Deixe aberto o vídeo de reserva [`../demo/demo_painel.mp4`](../demo/demo_painel.mp4).

Usando o deploy no Render: troque a URL do navegador e rode o roteiro com
`--base-url https://<serviço>.onrender.com`, usando a chave e a senha geradas pelo Render.
Abra a URL alguns minutos antes, porque um serviço gratuito pode estar hibernando.

## Durante a demonstração (slide 8)

```bash
python -m scripts.demo_pitch --cruzamento 2 --intervalo 1.5
```

O roteiro leva cerca de 2 a 3 minutos. O que mostrar no painel:

1. **Manhã (6h–9h):** os veículos sobem, a regra de Webster aumenta o ciclo e o verde da avenida.
   O novo plano entra no fim do ciclo em andamento (aparece "próximo ciclo: N s").
2. **Fora do pico:** o ciclo volta para perto do mínimo (40 s).
3. **Câmera parada (por volta das 14h45 simuladas):** em cerca de 30 s o selo muda para **Modo de segurança**, a regra
   vira **Plano fixo** (ciclo de 120 s) e a falha aparece na lista.
4. **Câmera de volta:** a falha é resolvida e o selo volta para **Adaptativo**.
5. **Pico da tarde (17h–19h):** ciclo maior de novo; a tabela mostra vias com fluxo alto/crítico.

Se algo falhar (rede, porta ocupada, navegador), passe para o vídeo de reserva sem tentar
consertar ao vivo.

## Perguntas prováveis

- **Foi testado em rua real?** Não. Os ganhos vêm de simulação com demanda sintética, com o mesmo
  motor da API e as mesmas chegadas para todas as estratégias. O próximo passo é um piloto com
  contagem em campo.
- **Por que não usar IA para decidir o tempo?** A IA (YOLO) só conta veículos. A decisão usa
  regras determinísticas e auditáveis (proporcional e Webster), como pede o documento de
  requisitos; cada ciclo fica registrado com a regra aplicada.
- **E se a câmera falhar?** O cruzamento entra no plano fixo de segurança, a falha é registrada e
  o adaptativo volta sozinho quando as leituras retornam.
- **Por que a regra de Webster ganha da proporcional?** Ela considera o número de faixas e a
  saturação, e calcula também a duração do ciclo; a proporcional só divide um ciclo fixo.
- **O YOLO funciona bem?** O pipeline funcionou de ponta a ponta com um vídeo de amostra filmado
  de cima, ângulo em que o modelo pequeno errou e o médio acertou. Falta validar com vídeo de um
  cruzamento real em ângulo oblíquo.
- **Escala para muitos cruzamentos?** A API é stateless e usa PostgreSQL; o canal de eventos do
  painel hoje roda em um processo e, com vários servidores, precisaria de um intermediário como
  o Redis.
- **Quanto custaria implantar?** Não temos essa estimativa; dependeria das câmeras, da rede e da
  integração com os controladores existentes.
