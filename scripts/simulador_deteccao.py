"""Simula o sistema externo de detecção (ex.: YOLO) enviando contagens de veículos para a API.

A integração real com câmeras é evolução futura; este script exercita o fluxo de recebimento de
leituras e a geração automática de ciclos. A autenticação usa a chave do sistema de detecção
(GSA_CHAVE_API_DETECCAO ou --chave) ou, sem chave, o login de um usuário (--email/--senha).

Uso: python -m scripts.simulador_deteccao --cruzamento 1 --iteracoes 5 --intervalo 2
"""

import argparse
import os
import random
import time

import httpx


def autenticar(cliente: httpx.Client, chave: str | None, email: str, senha: str) -> dict:
    if chave:
        return {"X-API-Key": chave}
    resposta = cliente.post("/auth/login", data={"username": email, "password": senha})
    resposta.raise_for_status()
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def simular(args: argparse.Namespace) -> None:
    with httpx.Client(base_url=args.base_url, timeout=10) as cliente:
        cabecalhos = autenticar(cliente, args.chave, args.email, args.senha)
        resposta = cliente.get(f"/cruzamentos/{args.cruzamento}/vias")
        resposta.raise_for_status()
        vias = resposta.json()
        if not vias:
            raise SystemExit(f"Cruzamento {args.cruzamento} não possui vias cadastradas")

        for n in range(1, args.iteracoes + 1):
            payload = {
                "cruzamentoId": args.cruzamento,
                "leituras": [
                    {
                        "viaId": via["id"],
                        "quantidadeVeiculos": random.randint(0, 20 * via["quantidadeFaixas"]),
                    }
                    for via in vias
                ],
            }
            resposta = cliente.post(
                f"/cruzamentos/{args.cruzamento}/leituras", json=payload, headers=cabecalhos
            )
            resposta.raise_for_status()
            dados = resposta.json()
            ciclo = dados["cicloGerado"]
            if ciclo is None:
                print(f"\n[{n}/{args.iteracoes}] leituras gravadas; {dados['avisos']}")
            else:
                print(f"\n[{n}/{args.iteracoes}] ciclo {ciclo['id']} de {ciclo['duracaoTotal']} s")
                for tempo in ciclo["tempos"]:
                    print(
                        f"  via {tempo['viaId']:>3}: {tempo['quantidadeVeiculos']:>3} veículos "
                        f"({tempo['classificacaoFluxo']:<8}) -> verde {tempo['tempoVerde']:>3} s "
                        f"[{tempo['ajusteAplicado']}]"
                    )
            if n < args.iteracoes:
                time.sleep(args.intervalo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cruzamento", type=int, default=1)
    parser.add_argument("--iteracoes", type=int, default=5)
    parser.add_argument("--intervalo", type=float, default=2.0, help="segundos entre envios")
    parser.add_argument("--chave", default=os.environ.get("GSA_CHAVE_API_DETECCAO"))
    parser.add_argument("--email", default="operador@gsa.local")
    parser.add_argument("--senha", default="operador123")
    simular(parser.parse_args())


if __name__ == "__main__":
    main()
