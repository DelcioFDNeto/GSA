"""ciclos, parametros, falhas e usuarios

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24 03:13:06.007760
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_TEMPO_VIA = "fk_tempos_semaforicos_via_id_vias"


def upgrade() -> None:
    op.create_table(
        "parametros_algoritmo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("duracao_ciclo", sa.Integer(), nullable=False),
        sa.Column("limite_fluxo_baixo", sa.Float(), nullable=False),
        sa.Column("limite_fluxo_moderado", sa.Float(), nullable=False),
        sa.Column("limite_fluxo_alto", sa.Float(), nullable=False),
        sa.Column("verde_minimo_padrao", sa.Integer(), nullable=False),
        sa.Column("verde_maximo_padrao", sa.Integer(), nullable=False),
        sa.Column("tempo_maximo_sem_leitura", sa.Integer(), nullable=False),
        sa.Column("atualizado_em", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "perfil",
            sa.Enum(
                "administrador", "operador", name="perfilusuario", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "falhas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cruzamento_id", sa.Integer(), nullable=False),
        sa.Column("via_id", sa.Integer(), nullable=True),
        sa.Column(
            "tipo",
            sa.Enum(
                "sem_leitura",
                "calculo_indisponivel",
                "manual",
                name="tipofalha",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("aberta", "resolvida", name="statusfalha", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("descricao", sa.String(length=300), nullable=False),
        sa.Column("detectada_em", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("resolvida_em", app.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.Column("observacao_resolucao", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["cruzamento_id"], ["cruzamentos.id"]),
        sa.ForeignKeyConstraint(["via_id"], ["vias.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("falhas", schema=None) as batch_op:
        batch_op.create_index(
            "ix_falhas_cruzamento_status", ["cruzamento_id", "status"], unique=False
        )

    # Colunas novas em tabelas existentes recebem valor padrão para as linhas já gravadas
    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "origem",
                sa.Enum("automatico", "manual", name="origemciclo", native_enum=False, length=20),
                nullable=False,
                server_default="manual",
            )
        )
        batch_op.add_column(
            sa.Column("duracao_ciclo_configurada", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("verde_disponivel", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("total_veiculos", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.create_index(
            "ix_ciclos_cruzamento_data", ["cruzamento_id", "data_hora_inicio"], unique=False
        )

    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duracao_ciclo", sa.Integer(), nullable=True))

    with op.batch_alter_table("tempos_semaforicos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("via_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("demanda_percentual", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "ajuste_aplicado",
                sa.String(length=30),
                nullable=False,
                server_default="proporcional",
            )
        )
    # A via de cada tempo já gravado vem do semáforo correspondente
    op.execute(
        "UPDATE tempos_semaforicos SET via_id = (SELECT semaforos.via_id FROM semaforos "
        "WHERE semaforos.id = tempos_semaforicos.semaforo_id)"
    )
    with op.batch_alter_table("tempos_semaforicos", schema=None) as batch_op:
        batch_op.alter_column("via_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(FK_TEMPO_VIA, "vias", ["via_id"], ["id"])

    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "criada_em",
                app.db.types.UTCDateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.drop_column("criada_em")

    with op.batch_alter_table("tempos_semaforicos", schema=None) as batch_op:
        batch_op.drop_constraint(FK_TEMPO_VIA, type_="foreignkey")
        batch_op.drop_column("ajuste_aplicado")
        batch_op.drop_column("demanda_percentual")
        batch_op.drop_column("via_id")

    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.drop_column("duracao_ciclo")

    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.drop_index("ix_ciclos_cruzamento_data")
        batch_op.drop_column("total_veiculos")
        batch_op.drop_column("verde_disponivel")
        batch_op.drop_column("duracao_ciclo_configurada")
        batch_op.drop_column("origem")

    with op.batch_alter_table("falhas", schema=None) as batch_op:
        batch_op.drop_index("ix_falhas_cruzamento_status")

    op.drop_table("falhas")
    op.drop_table("usuarios")
    op.drop_table("parametros_algoritmo")
