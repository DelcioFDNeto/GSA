"""Roteiro de demonstração ao vivo para o pitch: um dia de tráfego acelerado em poucos minutos.

Envia lotes de contagens para a API (como faria o sistema de detecção) seguindo o perfil de
demanda da simulação (picos às 8h e às 18h). Cada envio representa alguns minutos do dia, então o
painel em /painel mostra o ciclo crescendo no pico e encolhendo fora dele. No meio do roteiro, a
"câmera" de uma via para de enviar dados: o cruzamento entra no modo de segurança (plano fixo) e
uma falha aparece no painel; quando a câmera volta, o controle adaptativo é retomado.

Pré-requisitos: API rodando com o banco populado (scripts.seed) e as variáveis
GSA_CHAVE_API_DETECCAO (chave do sistema de detecção) e GSA_DEMO_SENHA_ADMIN (ou --senha-admin).

Uso: python -m scripts.demo_pitch --cruzamento 2 --intervalo 2
Os números enviados são sintéticos; o roteiro serve para demonstrar o funcionamento, não para
medir ganho (para isso, ver scripts/simulacao_comparativa.py).
"""

import argparse
import math
import os
import random
import time

import httpx

from simulacao.modelo import APROXIMACOES

TEMPO_SEM_LEITURA_DEMO = 30  # mínimo aceito pela API; o padrão (300 s) deixaria a demo lenta


def perfil_por_faixa(hora: float) -> list[float]:
    """Veículos/hora por faixa das aproximações da simulação, na ordem: norte, sul, leste, oeste."""
    return [a.demanda(hora) / a.faixas for a in APROXIMACOES]


def contagens(
    vias: list[dict], hora: float, janela_s: int, fator: float, rng: random.Random
) -> list[int]:
    """Converte o perfil em veículos contados na janela, escalado pelas faixas de cada via."""
    perfil = perfil_por_faixa(hora)
    valores = []
    for indice, via in enumerate(vias):
        taxa = perfil[indice % len(perfil)] * via["quantidadeFaixas"] * fator  # veíc./h
        media = taxa * janela_s / 3600
        valores.append(max(0, round(rng.gauss(media, math.sqrt(media) or 1))))
    return valores


def login(cliente: httpx.Client, email: str, senha: str) -> dict:
    resposta = cliente.post("/auth/login", data={"username": email, "password": senha})
    resposta.raise_for_status()
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def ajustar_parametros(cliente: httpx.Client, admin: dict, segundos: int) -> int:
    atuais = cliente.get("/parametros").json()
    anterior = atuais["tempoMaximoSemLeitura"]
    novos = {k: v for k, v in atuais.items() if k != "atualizadoEm"}
    novos["tempoMaximoSemLeitura"] = segundos
    cliente.put("/parametros", json=novos, headers=admin).raise_for_status()
    return anterior


def executar(args: argparse.Namespace) -> None:
    if not args.chave:
        raise SystemExit("Defina GSA_CHAVE_API_DETECCAO (ou use --chave).")
    if not args.senha_admin:
        raise SystemExit("Defina GSA_DEMO_SENHA_ADMIN (ou use --senha-admin).")
    rng = random.Random(args.semente)
    deteccao = {"X-API-Key": args.chave}

    with httpx.Client(base_url=args.base_url, timeout=10) as cliente:
        admin = login(cliente, args.email_admin, args.senha_admin)
        vias = cliente.get(f"/cruzamentos/{args.cruzamento}/vias").raise_for_status().json()
        if not vias:
            raise SystemExit(f"Cruzamento {args.cruzamento} não possui vias")
        via_falha = vias[-1]
        anterior = ajustar_parametros(cliente, admin, TEMPO_SEM_LEITURA_DEMO)
        print(f"Painel: {args.base_url}/painel/?cruzamento={args.cruzamento}")
        print(f"Tolerância sem leitura ajustada para {TEMPO_SEM_LEITURA_DEMO} s (era {anterior} s)")

        passos = int((args.hora_fim - args.hora_inicio) * 60 / args.minutos_por_envio)
        falha_inicio = int(passos * args.falha_em)
        envios_parada = math.ceil((TEMPO_SEM_LEITURA_DEMO + 15) / args.intervalo)
        hora, envio, verificou = args.hora_inicio, 0, False
        try:
            while hora <= args.hora_fim:
                camera_parada = falha_inicio <= envio < falha_inicio + envios_parada
                if envio == falha_inicio:
                    print(f"--- câmera de '{via_falha['nome']}' parou de enviar dados ---")
                if envio == falha_inicio + envios_parada:
                    print(f"--- câmera de '{via_falha['nome']}' voltou ---")
                valores = contagens(vias, hora, args.janela, args.fator, rng)
                leituras = [
                    {"viaId": via["id"], "quantidadeVeiculos": valor}
                    for via, valor in zip(vias, valores, strict=True)
                    if not (camera_parada and via["id"] == via_falha["id"])
                ]
                resposta = cliente.post(
                    f"/cruzamentos/{args.cruzamento}/leituras",
                    json={"cruzamentoId": args.cruzamento, "leituras": leituras},
                    headers=deteccao,
                )
                resposta.raise_for_status()
                ciclo = resposta.json()["cicloGerado"]
                if ciclo:
                    modo = "SEGURANÇA" if ciclo["modoOperacao"] == "contingencia" else "adaptativo"
                    verdes = " ".join(str(t["tempoVerde"]) for t in ciclo["tempos"])
                    print(
                        f"{int(hora):02d}h{int(hora % 1 * 60):02d}  {sum(valores):>4} veíc."
                        f"  ciclo {ciclo['duracaoTotal']:>3} s  verdes [{verdes}]  {modo}"
                    )
                    if ciclo["modoOperacao"] == "contingencia" and not verificou:
                        # registra a falha na hora, sem esperar a verificação periódica da API
                        cliente.post("/falhas/verificar", headers=admin).raise_for_status()
                        verificou = True
                # com a câmera parada o relógio do roteiro anda em tempo real, para a falha
                # durar o suficiente (tolerância de 30 s) sem pular horas do dia
                avanco = args.intervalo / 60 if camera_parada else args.minutos_por_envio
                hora += avanco / 60
                envio += 1
                time.sleep(args.intervalo)
        finally:
            if not args.manter_parametros:
                ajustar_parametros(cliente, admin, anterior)
                print(f"Tolerância sem leitura restaurada para {anterior} s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cruzamento", type=int, default=2)
    parser.add_argument("--intervalo", type=float, default=2.0, help="segundos reais entre envios")
    parser.add_argument("--minutos-por-envio", type=float, default=15, help="minutos do dia")
    parser.add_argument("--janela", type=int, default=90, help="segundos cobertos por contagem")
    parser.add_argument("--hora-inicio", type=float, default=6)
    parser.add_argument("--hora-fim", type=float, default=22)
    parser.add_argument(
        "--fator", type=float, default=1.4, help="multiplica a demanda (1.4 = cenário alto)"
    )
    parser.add_argument("--falha-em", type=float, default=0.55, help="fração do roteiro")
    parser.add_argument("--semente", type=int, default=7)
    parser.add_argument("--chave", default=os.environ.get("GSA_CHAVE_API_DETECCAO"))
    parser.add_argument("--email-admin", default="admin@gsa.local")
    parser.add_argument("--senha-admin", default=os.environ.get("GSA_DEMO_SENHA_ADMIN"))
    parser.add_argument("--manter-parametros", action="store_true")
    executar(parser.parse_args())


if __name__ == "__main__":
    main()
