"""estagios, webster e modo de seguranca

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24 14:12:30.233915
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Linhas já existentes recebem o comportamento anterior: modo adaptativo, regra proporcional
    # e os valores padrão de Webster
    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "modo_operacao",
                sa.Enum(
                    "adaptativo", "contingencia", name="modooperacao", native_enum=False, length=20
                ),
                nullable=False,
                server_default="adaptativo",
            )
        )
        batch_op.add_column(sa.Column("grau_saturacao", sa.Float(), nullable=True))

    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "regra_temporizacao",
                sa.Enum(
                    "proporcional",
                    "webster",
                    name="regratemporizacao",
                    native_enum=False,
                    length=20,
                ),
                nullable=False,
                server_default="proporcional",
            )
        )

    with op.batch_alter_table("parametros_algoritmo", schema=None) as batch_op:
        for coluna, padrao in (
            ("fluxo_saturacao_por_faixa", "1800"),
            ("intervalo_contagem", "90"),
            ("ciclo_minimo", "40"),
            ("ciclo_maximo", "150"),
        ):
            batch_op.add_column(
                sa.Column(coluna, sa.Integer(), nullable=False, server_default=padrao)
            )

    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.add_column(sa.Column("estagio", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vias", schema=None) as batch_op:
        batch_op.drop_column("estagio")

    with op.batch_alter_table("parametros_algoritmo", schema=None) as batch_op:
        batch_op.drop_column("ciclo_maximo")
        batch_op.drop_column("ciclo_minimo")
        batch_op.drop_column("intervalo_contagem")
        batch_op.drop_column("fluxo_saturacao_por_faixa")

    with op.batch_alter_table("cruzamentos", schema=None) as batch_op:
        batch_op.drop_column("regra_temporizacao")

    with op.batch_alter_table("ciclos_semaforicos", schema=None) as batch_op:
        batch_op.drop_column("grau_saturacao")
        batch_op.drop_column("modo_operacao")
