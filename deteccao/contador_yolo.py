"""Conta veículos por via em um vídeo (arquivo, webcam ou RTSP) com YOLO e envia à API do GSA.

Cada via tem uma zona (polígono) no quadro. O YOLO detecta carros, motos, ônibus e caminhões, o
rastreador (ByteTrack) dá um id a cada veículo e, ao fim de cada janela de tempo, o total de
veículos distintos vistos em cada zona é enviado em lote para POST /cruzamentos/{id}/leituras
com a chave do sistema de detecção (X-API-Key). A resposta traz o ciclo calculado, mostrado no
vídeo anotado.

Instalação (separada da API):  pip install -r requirements-yolo.txt
Uso:
  python -m deteccao.contador_yolo --video meu_cruzamento.mp4 --config deteccao/exemplo_zonas.json \
      --saida anotado.mp4
  --sem-envio   só conta e anota, sem chamar a API
  --tempo-real  processa um arquivo no ritmo do vídeo (útil para demonstrar junto com o painel)
"""

import argparse
import os
import time
from pathlib import Path

import cv2
import httpx
import numpy as np
from ultralytics import YOLO

from deteccao.zonas import ContadorJanela, carregar_configuracao, montar_lote, ponto_de_contato

CORES = [(214, 120, 42), (52, 104, 235), (122, 175, 27), (0, 161, 237)]  # BGR


def desenhar_zonas(quadro, zonas, contagens, largura, altura) -> None:
    camada = quadro.copy()
    for indice, zona in enumerate(zonas):
        cor = CORES[indice % len(CORES)]
        pontos = np.array([(x * largura, y * altura) for x, y in zona.poligono], np.int32)
        cv2.fillPoly(camada, [pontos], cor)
        cv2.polylines(quadro, [pontos], True, cor, 2)
    cv2.addWeighted(camada, 0.18, quadro, 0.82, 0, quadro)
    for indice, zona in enumerate(zonas):
        texto = f"{zona.nome}: {contagens.get(zona.via_id, 0)} veic."
        rotulo(quadro, texto, (12, 28 + 26 * indice), CORES[indice % len(CORES)])


def rotulo(quadro, texto, origem, cor, escala=0.55) -> None:
    (w, h), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, escala, 1)
    x, y = origem
    cv2.rectangle(quadro, (x - 4, y - h - 6), (x + w + 4, y + base), (20, 20, 20), -1)
    cv2.putText(quadro, texto, (x, y - 2), cv2.FONT_HERSHEY_SIMPLEX, escala, cor, 1, cv2.LINE_AA)


def enviar(cliente: httpx.Client | None, cruzamento_id: int, contagens, chave) -> str:
    lote = montar_lote(cruzamento_id, contagens)
    if cliente is None:
        return f"(sem envio) {lote['leituras']}"
    resposta = cliente.post(
        f"/cruzamentos/{cruzamento_id}/leituras", json=lote, headers={"X-API-Key": chave}
    )
    if resposta.status_code != 201:
        return f"API respondeu {resposta.status_code}: {resposta.text[:120]}"
    ciclo = resposta.json()["cicloGerado"]
    if ciclo is None:
        return "leituras gravadas; ciclo não gerado"
    verdes = "/".join(str(t["tempoVerde"]) for t in ciclo["tempos"])
    return f"ciclo {ciclo['duracaoTotal']} s | verdes {verdes} s | {ciclo['modoOperacao']}"


def executar(args: argparse.Namespace) -> None:
    config = carregar_configuracao(args.config)
    modelo = YOLO(args.modelo)
    classes = [i for i, nome in modelo.names.items() if nome in config.classes]
    fonte = int(args.video) if args.video.isdigit() else args.video
    captura = cv2.VideoCapture(fonte)
    if not captura.isOpened():
        raise SystemExit(f"Não foi possível abrir o vídeo: {args.video}")
    arquivo = isinstance(fonte, str) and Path(fonte).exists()
    fps = captura.get(cv2.CAP_PROP_FPS) or 30
    largura = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    altura = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    gravador = None
    if args.saida:
        codec = cv2.VideoWriter_fourcc(*"mp4v")
        gravador = cv2.VideoWriter(args.saida, codec, fps, (largura, altura))

    if not args.sem_envio and not args.chave:
        raise SystemExit("Defina GSA_CHAVE_API_DETECCAO (ou --chave), ou use --sem-envio.")
    cliente = None if args.sem_envio else httpx.Client(base_url=args.base_url, timeout=10)
    contador = ContadorJanela(config.zonas)
    inicio_real = time.monotonic()
    inicio_janela = 0.0
    situacao = "aguardando a primeira janela"
    quadro_n = 0
    try:
        while True:
            ok, quadro = captura.read()
            if not ok:
                break
            agora = quadro_n / fps if arquivo else time.monotonic() - inicio_real
            resultado = modelo.track(
                quadro,
                persist=True,
                classes=classes,
                conf=args.confianca,
                tracker="bytetrack.yaml",
                verbose=False,
            )[0]
            caixas = resultado.boxes
            if caixas.id is not None:
                for (x1, y1, x2, y2), id_rastreio, classe in zip(
                    caixas.xyxy.tolist(),
                    caixas.id.int().tolist(),
                    caixas.cls.int().tolist(),
                    strict=True,
                ):
                    via = contador.registrar(
                        id_rastreio,
                        *ponto_de_contato(x1 / largura, y1 / altura, x2 / largura, y2 / altura),
                    )
                    cor = (90, 90, 90) if via is None else (255, 255, 255)
                    cv2.rectangle(quadro, (int(x1), int(y1)), (int(x2), int(y2)), cor, 2)
                    texto = f"#{id_rastreio} {modelo.names[classe]}"
                    # rótulo acima da caixa, ou dentro dela quando o veículo está no topo
                    y_rotulo = int(y1) if y1 > 22 else int(y1) + 22
                    rotulo(quadro, texto, (int(x1) + 4, y_rotulo), cor)

            if agora - inicio_janela >= config.janela_segundos:
                contagens = contador.fechar_janela()
                situacao = enviar(cliente, config.cruzamento_id, contagens, args.chave)
                print(f"[{agora:6.1f} s] {contagens} -> {situacao}")
                inicio_janela = agora

            desenhar_zonas(quadro, config.zonas, contador.parcial(), largura, altura)
            rotulo(quadro, f"GSA: {situacao}", (12, altura - 14), (255, 255, 255))
            rotulo(
                quadro,
                f"janela {agora - inicio_janela:4.1f}/{config.janela_segundos:.0f} s",
                (largura - 170, 28),
                (255, 255, 255),
            )
            if gravador:
                gravador.write(quadro)
            quadro_n += 1
            if arquivo and args.tempo_real:
                atraso = quadro_n / fps - (time.monotonic() - inicio_real)
                if atraso > 0:
                    time.sleep(atraso)
    finally:
        captura.release()
        if gravador:
            gravador.release()
        if cliente:
            cliente.close()
    print(f"{quadro_n} quadros processados")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--video", required=True, help="arquivo, índice da webcam ou URL RTSP")
    parser.add_argument("--config", required=True, help="JSON com cruzamento, janela e zonas")
    parser.add_argument("--modelo", default="yolo11n.pt", help="pesos do YOLO (baixados se faltar)")
    parser.add_argument("--confianca", type=float, default=0.3)
    parser.add_argument("--saida", help="grava o vídeo anotado neste arquivo .mp4")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--chave", default=os.environ.get("GSA_CHAVE_API_DETECCAO"))
    parser.add_argument("--sem-envio", action="store_true")
    parser.add_argument("--tempo-real", action="store_true")
    executar(parser.parse_args())


if __name__ == "__main__":
    main()
