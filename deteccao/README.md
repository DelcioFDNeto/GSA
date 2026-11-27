# Sistema de detecção de exemplo (YOLO)

O GSA recebe contagens de veículos de um sistema de detecção **externo** (requisito RF04). Esta
pasta traz um exemplo funcional desse sistema, usado para demonstrar a integração ponta a ponta:

```
vídeo da câmera → YOLO (detecção) → ByteTrack (id de cada veículo) → contagem por zona/via
→ POST /cruzamentos/{id}/leituras (X-API-Key) → GSA calcula o ciclo → painel em /painel
```

A API não depende deste código: ele roda em outra máquina (ou na borda, junto da câmera) e só
conversa com o backend pela API REST, como qualquer outro sistema de detecção.

## Instalação

Em um ambiente separado do da API (o PyTorch é grande):

```bash
python -m venv .venv-yolo
. .venv-yolo/bin/activate
pip install -r requirements-yolo.txt
```

Os pesos do modelo (`yolo11n.pt`, `yolo11s.pt`, `yolo11m.pt`…) são baixados pelo Ultralytics na
primeira execução.

## Configuração das zonas

Cada via do cruzamento recebe um polígono no quadro do vídeo, com coordenadas **normalizadas**
(0 a 1, proporcionais à largura e à altura). Exemplo em [`exemplo_zonas.json`](exemplo_zonas.json):

```json
{
  "cruzamentoId": 1,
  "janelaSegundos": 10,
  "zonas": [
    {"viaId": 1, "nome": "Via A", "poligono": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]]},
    {"viaId": 2, "nome": "Via B", "poligono": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]]}
  ]
}
```

- `viaId` são os ids das vias cadastradas na API (`GET /cruzamentos/{id}/vias`).
- `janelaSegundos` é o intervalo entre envios. Para a regra de Webster, use o mesmo valor do
  parâmetro `intervaloContagem` (padrão 90 s).
- Conta-se cada veículo **uma vez por janela** (pelo id do rastreador), usando o ponto central
  da base da caixa, onde o veículo toca a pista.

## Uso

```bash
export GSA_CHAVE_API_DETECCAO=...   # a mesma chave configurada na API
python -m deteccao.contador_yolo \
  --video meu_cruzamento.mp4 \
  --config deteccao/exemplo_zonas.json \
  --modelo yolo11m.pt \
  --saida anotado.mp4
```

| Opção | Uso |
|---|---|
| `--video` | arquivo, índice da webcam (`0`) ou URL RTSP da câmera |
| `--sem-envio` | só conta e grava o vídeo anotado, sem chamar a API |
| `--tempo-real` | processa um arquivo no ritmo do vídeo (para demonstrar junto com o painel) |
| `--confianca` | confiança mínima das detecções (padrão 0,3) |

O vídeo anotado mostra as zonas, as caixas com o id de cada veículo, a contagem da janela atual
e o último ciclo devolvido pela API. Para abrir no navegador, converta para H.264:
`ffmpeg -i anotado.mp4 -c:v libx264 -pix_fmt yuv420p anotado_h264.mp4`.

## Câmera sintética do simulador

O simulador visual (`python -m simulador`, ver o README principal) usa este mesmo módulo: as
detecções vêm dos veículos simulados (caixa, classe COCO, id persistente e confiança, no formato
do YOLO + ByteTrack) e a ponte do simulador conta com `ponto_de_contato`, `ContadorJanela` e
`montar_lote`, exatamente como o `contador_yolo.py`.

A simulação em malha fechada mostrou um efeito do desenho das zonas que vale para câmeras reais:

- **zona cobrindo a aproximação inteira** (como em `exemplo_zonas.json`): quem espera mais de uma
  janela é contado de novo. A contagem superestima o fluxo de chegada que a regra de Webster
  espera, mas é o único sinal de fila acumulada que chega ao GSA — e foi a configuração com melhor
  desempenho nos horários de pico;
- **faixa estreita na entrada do quadro** ("laço virtual"): cada veículo conta uma vez, então a
  janela mede as chegadas com precisão — enquanto a fila cabe no quadro. Com fila além do campo de
  visão, a câmera só vê a descarga, e o GSA não percebe o acúmulo e subdimensiona o verde.

Em qualquer caso, a câmera precisa enxergar a fila normal de pico: no simulador ela cobre 72 m de
cada aproximação.

## Validação feita e limitações

- O pipeline foi validado com o vídeo de amostra `car-detection.mp4` do repositório
  [intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos)
  (licença CC BY 4.0): as contagens chegaram à API e os ciclos foram gerados. As duas zonas
  (metade esquerda e direita do quadro) são **ilustrativas** — o vídeo é de um estacionamento.
- Esse vídeo é filmado **de cima**. Modelos pré-treinados no COCO são treinados principalmente
  com fotos tiradas de lado, e em vista aérea o `yolo11n` chegou a classificar carros como
  "cell phone"; o `yolo11m` reconheceu os carros. Câmeras de trânsito costumam ficar em ângulo
  oblíquo, em que os modelos pré-treinados funcionam melhor.
- Para o pitch, o ideal é gravar um vídeo curto de um cruzamento real (de uma passarela ou
  prédio, em ângulo oblíquo) e desenhar as zonas de cada aproximação.
- Contagem por janela mede **quantos veículos passaram ou esperaram** na zona; não mede fila
  em metros nem velocidade. Oclusão (um veículo atrás do outro) reduz a contagem.
