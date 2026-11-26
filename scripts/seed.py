"""Popula o banco com dados fictícios de demonstração.

Cria dois usuários, dois cruzamentos e 6 horas de leituras (um lote a cada 15 minutos), o que
gera também o histórico de ciclos. O último lote do cruzamento A repete o exemplo do documento
de requisitos (30 e 10 veículos → 60 s e 20 s de verde). O cruzamento B agrupa as vias em dois
estágios (sentidos opostos abrem juntos) e usa a regra de Webster.

Uso: python -m scripts.seed   (após `alembic upgrade head`)
"""

import os
import random
from datetime import timedelta

from app.db.session import SessionLocal
from app.db.types import agora_utc
from app.models import Direcao, PerfilUsuario, RegraTemporizacao
from app.schemas.cruzamento import CruzamentoCreate
from app.schemas.leitura import LeituraItem, LeituraLoteCreate
from app.schemas.semaforo import SemaforoCreate
from app.schemas.usuario import UsuarioCreate
from app.schemas.via import ViaCreate
from app.services.cruzamento_service import CruzamentoService
from app.services.leitura_service import LeituraService
from app.services.usuario_service import UsuarioService
from app.services.via_service import SemaforoService, ViaService

# Senhas padrão apenas para demonstração local. Em ambiente público (deploy), defina
# GSA_SEED_SENHA_ADMIN e GSA_SEED_SENHA_OPERADOR para não usar as senhas conhecidas.
USUARIOS = [
    (
        "Administrador (demonstração)",
        "admin@gsa.local",
        os.environ.get("GSA_SEED_SENHA_ADMIN") or "admin123",
        PerfilUsuario.ADMINISTRADOR,
    ),
    (
        "Operador (demonstração)",
        "operador@gsa.local",
        os.environ.get("GSA_SEED_SENHA_OPERADOR") or "operador123",
        PerfilUsuario.OPERADOR,
    ),
]

# Mesmo exemplo do documento de requisitos: verde mínimo 20 s e máximo 70 s, ciclo padrão (90 s)
TEMPOS_DUAS_VIAS = SemaforoCreate(
    tempo_minimo_verde=20, tempo_maximo_verde=70, tempo_amarelo=3, tempo_vermelho=2
)
# Quatro aproximações em dois estágios; 120 s é o ciclo do plano fixo de segurança, já que
# com Webster a duração do ciclo varia com a demanda
TEMPOS_QUATRO_VIAS = SemaforoCreate(
    tempo_minimo_verde=15, tempo_maximo_verde=60, tempo_amarelo=3, tempo_vermelho=2
)

# (nome, latitude, longitude, duração do ciclo, regra, tempos,
#  [(via, direção, faixas, estágio, último lote)])
CRUZAMENTOS = [
    (
        "Cruzamento Demonstração A — exemplo do documento de requisitos",
        -15.7939,
        -47.8828,
        None,
        RegraTemporizacao.PROPORCIONAL,
        TEMPOS_DUAS_VIAS,
        [
            ("Via A — Avenida Principal", Direcao.NORTE, 2, None, 30),
            ("Via B — Rua Secundária", Direcao.LESTE, 1, None, 10),
        ],
    ),
    (
        "Cruzamento Demonstração B — quatro aproximações em dois estágios",
        -15.8000,
        -47.8900,
        120,
        RegraTemporizacao.WEBSTER,
        TEMPOS_QUATRO_VIAS,
        [
            ("Avenida Central — sentido norte", Direcao.NORTE, 3, 1, 42),
            ("Avenida Central — sentido sul", Direcao.SUL, 3, 1, 35),
            ("Rua Lateral — sentido leste", Direcao.LESTE, 1, 2, 6),
            ("Rua Lateral — sentido oeste", Direcao.OESTE, 1, 2, 0),
        ],
    ),
]

HORAS_DE_HISTORICO = 6
INTERVALO = timedelta(minutes=15)


def popular() -> None:
    sorteio = random.Random(2026)  # dados fictícios, mas iguais a cada execução
    with SessionLocal() as db:
        cruzamentos = CruzamentoService(db)
        if cruzamentos.listar():
            print("Banco já possui cruzamentos; nada a fazer.")
            return

        usuarios = UsuarioService(db)
        for nome, email, senha, perfil in USUARIOS:
            usuarios.criar(UsuarioCreate(nome=nome, email=email, senha=senha, perfil=perfil))
            definida = os.environ.get("GSA_SEED_SENHA_" + email.split("@")[0].upper())
            exibida = "senha definida por variável de ambiente" if definida else senha
            print(f"Usuário {email} / {exibida} ({perfil.value})")

        agora = agora_utc()
        lotes = int(timedelta(hours=HORAS_DE_HISTORICO) / INTERVALO)
        for nome, latitude, longitude, duracao, regra, tempos, vias in CRUZAMENTOS:
            cruzamento = cruzamentos.criar(
                CruzamentoCreate(
                    nome=nome,
                    latitude=latitude,
                    longitude=longitude,
                    duracao_ciclo=duracao,
                    regra_temporizacao=regra,
                )
            )
            ids = []
            for nome_via, direcao, faixas, estagio, _ in vias:
                via = ViaService(db).criar(
                    cruzamento.id,
                    ViaCreate(
                        nome=nome_via, direcao=direcao, quantidade_faixas=faixas, estagio=estagio
                    ),
                )
                SemaforoService(db).criar(via.id, tempos)
                ids.append((via.id, faixas))

            leituras = LeituraService(db)
            for n in range(lotes, 0, -1):
                volumes = [sorteio.randint(0, 12 * faixas) for _, faixas in ids]
                _enviar(leituras, cruzamento.id, ids, volumes, agora - n * INTERVALO)
            _enviar(leituras, cruzamento.id, ids, [v[-1] for v in vias], agora)
            print(
                f"Cruzamento {cruzamento.id}: {nome} "
                f"({len(vias)} vias, regra {regra.value}, {lotes + 1} lotes)"
            )


def _enviar(servico, cruzamento_id, ids, volumes, momento) -> None:
    dados = LeituraLoteCreate(
        cruzamento_id=cruzamento_id,
        leituras=[
            LeituraItem(via_id=via_id, quantidade_veiculos=volume)
            for (via_id, _), volume in zip(ids, volumes, strict=True)
        ],
    )
    servico.registrar_lote(cruzamento_id, dados, momento=momento)


if __name__ == "__main__":
    popular()
