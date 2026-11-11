"""Mevsim ilerlemesini simülasyon durumuna ekler.

Revision ID: 0006_season_progress
Revises: 0005_budget
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_season_progress"
down_revision = "0005_budget"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_state",
        sa.Column("season_progress", sa.Numeric(6, 4), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE simulation_state SET season_progress = ROUND(MOD(elapsed_seconds / 3600, 1), 4)"
    )


def downgrade() -> None:
    op.drop_column("simulation_state", "season_progress")
