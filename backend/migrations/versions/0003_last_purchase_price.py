"""Ürünün son alım birim fiyatını saklar.

Stok sıfıra düşse bile kullanıcı "en son kaçtan aldım" bilgisini görsün diye
ayrı bir alan tutulur; ağırlıklı ortalama maliyetten farklıdır (o, stoktaki
malın ortalamasıdır).

Revision ID: 0003_last_purchase_price
Revises: 0002_manual_capacity_shipping
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_last_purchase_price"
down_revision = "0002_manual_capacity_shipping"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("last_purchase_unit_price", sa.Numeric(14, 6), nullable=False, server_default="0"),
    )
    op.execute("UPDATE products SET last_purchase_unit_price = avg_cost_per_kg")


def downgrade() -> None:
    op.drop_column("products", "last_purchase_unit_price")
