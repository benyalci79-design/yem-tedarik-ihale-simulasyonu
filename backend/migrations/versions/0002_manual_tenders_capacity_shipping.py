"""Manuel ihale, depo kapasitesi, nakliye ve stok maliyeti tabloları.

Revision ID: 0002_manual_tenders_capacity_shipping
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT, DATETIME

revision = "0002_manual_capacity_shipping"
# Not: Alembic'in varsayılan alembic_version.version_num sütunu 32 karakterdir;
# bu yüzden revision kimliği dosya adından kısadır.
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

# Faz 1'deki backfill değerleri: depo kapasitesi (kg) ve TL/kg ortalama maliyet.
PRODUCT_BACKFILL = {
    "MISR": ("5000.000", "8.750000"),
    "ARPA": ("4000.000", "7.750000"),
    "SOYA": ("6000.000", "13.000000"),
}


def _bigint() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(BIGINT(unsigned=True), "mysql")


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("capacity_kg", sa.Numeric(16, 3), nullable=False, server_default="10000.000"),
    )
    op.add_column(
        "products",
        sa.Column("avg_cost_per_kg", sa.Numeric(14, 6), nullable=False, server_default="0"),
    )
    op.add_column(
        "simulation_state",
        sa.Column("speed_multiplier", sa.Numeric(4, 2), nullable=False, server_default="1.00"),
    )
    op.add_column(
        "npc_rules",
        sa.Column("freight_included", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "npc_rules",
        sa.Column("min_available_kg", sa.Numeric(16, 3), nullable=False, server_default="1000"),
    )
    op.add_column(
        "npc_rules",
        sa.Column("max_available_kg", sa.Numeric(16, 3), nullable=False, server_default="3000"),
    )
    op.add_column(
        "tender_participations",
        sa.Column("freight_included", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "tender_participations",
        sa.Column("min_available_kg", sa.Numeric(16, 3), nullable=False, server_default="1000"),
    )
    op.add_column(
        "tender_participations",
        sa.Column("max_available_kg", sa.Numeric(16, 3), nullable=False, server_default="3000"),
    )
    op.add_column(
        "tender_participations",
        sa.Column("offered_quantity_kg", sa.Numeric(16, 3), nullable=True),
    )
    op.add_column(
        "tender_participations",
        sa.Column("accepted_quantity_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
    )

    # Veri kaybı yok: mevcut ürünler koda göre gerçekçi kapasite/maliyet değerleri alır.
    for code, (capacity, avg_cost) in PRODUCT_BACKFILL.items():
        op.execute(
            sa.text(
                "UPDATE products SET capacity_kg = :capacity, avg_cost_per_kg = :avg_cost WHERE code = :code"
            ).bindparams(capacity=capacity, avg_cost=avg_cost, code=code)
        )

    op.create_table(
        "carriers",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_per_ton", sa.Numeric(12, 2), nullable=False),
        sa.Column("transit_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code", name="uq_carriers_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "tender_awards",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("tender_id", _bigint(), nullable=False),
        sa.Column("participation_id", _bigint(), nullable=False),
        sa.Column("quantity_kg", sa.Numeric(16, 3), nullable=False),
        sa.Column("unit_price_per_ton", sa.Numeric(12, 2), nullable=False),
        sa.Column("freight_included", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("carrier_id", _bigint(), nullable=True),
        sa.Column("carrier_price_per_ton", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("accepted_at_seconds", sa.Numeric(16, 3), nullable=False),
        sa.Column("carrier_assigned_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("delivery_due_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("delivered_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("landed_cost_tl", sa.Numeric(16, 2), nullable=True),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["participation_id"], ["tender_participations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["carrier_id"], ["carriers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("participation_id", name="uq_award_participation"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_awards_tender_status", "tender_awards", ["tender_id", "status"])
    op.create_index("ix_awards_status_due", "tender_awards", ["status", "delivery_due_at_seconds"])
    op.create_table(
        "stock_snapshots",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("elapsed_seconds", sa.Numeric(16, 3), nullable=False),
        sa.Column("product_id", _bigint(), nullable=False),
        sa.Column("stock_kg", sa.Numeric(16, 6), nullable=False),
        sa.Column("avg_cost_per_kg", sa.Numeric(14, 6), nullable=False),
        sa.Column("value_tl", sa.Numeric(18, 4), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_snapshots_elapsed", "stock_snapshots", ["elapsed_seconds"])
    op.create_index("ix_snapshots_product_elapsed", "stock_snapshots", ["product_id", "elapsed_seconds"])


def downgrade() -> None:
    op.drop_index("ix_snapshots_product_elapsed", table_name="stock_snapshots")
    op.drop_index("ix_snapshots_elapsed", table_name="stock_snapshots")
    op.drop_table("stock_snapshots")
    op.drop_index("ix_awards_status_due", table_name="tender_awards")
    op.drop_index("ix_awards_tender_status", table_name="tender_awards")
    op.drop_table("tender_awards")
    op.drop_table("carriers")
    op.drop_column("tender_participations", "accepted_quantity_kg")
    op.drop_column("tender_participations", "offered_quantity_kg")
    op.drop_column("tender_participations", "max_available_kg")
    op.drop_column("tender_participations", "min_available_kg")
    op.drop_column("tender_participations", "freight_included")
    op.drop_column("npc_rules", "max_available_kg")
    op.drop_column("npc_rules", "min_available_kg")
    op.drop_column("npc_rules", "freight_included")
    op.drop_column("simulation_state", "speed_multiplier")
    op.drop_column("products", "avg_cost_per_kg")
    op.drop_column("products", "capacity_kg")
