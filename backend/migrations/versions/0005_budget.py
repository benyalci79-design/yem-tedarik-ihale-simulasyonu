"""Aylık satın alma bütçesi tablosunu oluşturur.

Revision ID: 0005_budget
Revises: 0004_loss_and_seasonality
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_budget"
down_revision = "0004_loss_and_seasonality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("monthly_limit_tl", sa.Numeric(16, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_budgets_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.execute(
        sa.text(
            "INSERT INTO budgets (id, code, name, monthly_limit_tl, is_active) "
            "VALUES (1, 'YEM-HAM', 'Yem Hammadde Bütçesi', 500000.00, 1)"
        )
    )


def downgrade() -> None:
    op.drop_table("budgets")
