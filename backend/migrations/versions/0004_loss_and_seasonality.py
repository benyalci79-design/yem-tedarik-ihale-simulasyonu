"""Fire oranı ve mevsimsel fiyat dalgalanması alanlarını ekler.

Revision ID: 0004_loss_and_seasonality
Revises: 0003_last_purchase_price
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_loss_and_seasonality"
down_revision = "0003_last_purchase_price"
branch_labels = None
depends_on = None

DEFAULTS = {
    "MISR": ("1.00", "8.00"),
    "ARPA": ("0.50", "6.00"),
    "SOYA": ("1.50", "10.00"),
}


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("loss_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "products",
        sa.Column("season_amplitude", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "tender_participations",
        sa.Column("season_factor", sa.Numeric(6, 4), nullable=False, server_default="1.0000"),
    )
    op.add_column(
        "tender_awards",
        sa.Column("loss_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
    )
    for code, (loss, amplitude) in DEFAULTS.items():
        op.execute(
            sa.text(
                "UPDATE products SET loss_percent = :loss, season_amplitude = :amplitude WHERE code = :code"
            ).bindparams(loss=loss, amplitude=amplitude, code=code)
        )


def downgrade() -> None:
    op.drop_column("tender_awards", "loss_kg")
    op.drop_column("tender_participations", "season_factor")
    op.drop_column("products", "season_amplitude")
    op.drop_column("products", "loss_percent")
