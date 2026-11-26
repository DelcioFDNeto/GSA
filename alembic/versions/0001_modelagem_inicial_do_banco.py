"""modelagem inicial do banco

Revision ID: 0001
Revises:
Create Date: 2026-10-01 22:46:18.515246
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cruzamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ativo", "inativo", name="statuscruzamento", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("criado_em", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cruzamentos_status"), ["status"], unique=False)

    op.create_table(
        "ciclos_semaforicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cruzamento_id", sa.Integer(), nullable=False),
        sa.Column("data_hora_inicio", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("duracao_total", sa.Integer(), nullable=False),
        sa.Column("regra_aplicada", sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(
            ["cruzamento_id"],
            ["cruzamentos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ciclos_semaforicos_cruzamento_id"), ["cruzamento_id"], unique=False
        )

    op.create_table(
        "vias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column(
            "direcao",
            sa.Enum(
                "norte",
                "sul",
                "leste",
                "oeste",
                "nordeste",
                "noroeste",
                "sudeste",
                "sudoeste",
                name="direcao",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("quantidade_faixas", sa.Integer(), nullable=False),
        sa.Column("cruzamento_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantidade_faixas >= 1", name="ck_via_faixas_positivas"),
        sa.ForeignKeyConstraint(
            ["cruzamento_id"],
            ["cruzamentos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_vias_cruzamento_id"), ["cruzamento_id"], unique=False)

    op.create_table(
        "leituras_trafego",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("via_id", sa.Integer(), nullable=False),
        sa.Column("quantidade_veiculos", sa.Integer(), nullable=False),
        sa.Column("data_hora", app.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantidade_veiculos >= 0", name="ck_leitura_quantidade"),
        sa.ForeignKeyConstraint(
            ["via_id"],
            ["vias.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("leituras_trafego", schema=None) as batch_op:
        batch_op.create_index("ix_leituras_via_data_hora", ["via_id", "data_hora"], unique=False)

    op.create_table(
        "semaforos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("via_id", sa.Integer(), nullable=False),
        sa.Column("tempo_minimo_verde", sa.Integer(), nullable=False),
        sa.Column("tempo_maximo_verde", sa.Integer(), nullable=False),
        sa.Column("tempo_amarelo", sa.Integer(), nullable=False),
        sa.Column("tempo_vermelho", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ativo",
                "inativo",
                "manutencao",
                name="statussemaforo",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.CheckConstraint("tempo_amarelo > 0", name="ck_semaforo_amarelo"),
        sa.CheckConstraint(
            "tempo_maximo_verde >= tempo_minimo_verde", name="ck_semaforo_verde_maximo"
        ),
        sa.CheckConstraint("tempo_minimo_verde > 0", name="ck_semaforo_verde_minimo"),
        sa.CheckConstraint("tempo_vermelho >= 0", name="ck_semaforo_vermelho"),
        sa.ForeignKeyConstraint(
            ["via_id"],
            ["vias.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("via_id"),
    )
    op.create_table(
        "tempos_semaforicos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ciclo_id", sa.Integer(), nullable=False),
        sa.Column("semaforo_id", sa.Integer(), nullable=False),
        sa.Column("quantidade_veiculos", sa.Integer(), nullable=False),
        sa.Column("classificacao_fluxo", sa.String(length=20), nullable=False),
        sa.Column("tempo_verde", sa.Integer(), nullable=False),
        sa.Column("tempo_amarelo", sa.Integer(), nullable=False),
        sa.Column("tempo_vermelho", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ciclo_id"],
            ["ciclos_semaforicos.id"],
        ),
        sa.ForeignKeyConstraint(
            ["semaforo_id"],
            ["semaforos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tempos_semaforicos", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tempos_semaforicos_ciclo_id"), ["ciclo_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("tempos_semaforicos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tempos_semaforicos_ciclo_id"))

    op.drop_table("tempos_semaforicos")
    op.drop_table("semaforos")
    with op.batch_alter_table("leituras_trafego", schema=None) as batch_op:
        batch_op.drop_index("ix_leituras_via_data_hora")

    op.drop_table("leituras_trafego")
    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_vias_cruzamento_id"))

    op.drop_table("vias")
    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ciclos_semaforicos_cruzamento_id"))

    op.drop_table("ciclos_semaforicos")
    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cruzamentos_status"))

    op.drop_table("cruzamentos")
