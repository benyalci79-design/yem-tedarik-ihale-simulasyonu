"""Altı tabloyu ve kısıtlarını oluşturur.

Revision ID: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import BIGINT, DATETIME

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _bigint() -> sa.types.TypeEngine:
    return sa.BigInteger().with_variant(BIGINT(unsigned=True), "mysql")


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("current_stock_kg", sa.Numeric(16, 6), nullable=False),
        sa.Column("consumption_kg_per_min", sa.Numeric(12, 3), nullable=False),
        sa.Column("critical_coverage_minutes", sa.Numeric(8, 2), nullable=False),
        sa.Column("target_coverage_minutes", sa.Numeric(8, 2), nullable=False),
        sa.Column("offer_window_seconds", sa.Integer(), nullable=False),
        sa.Column("next_eligible_at_seconds", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.UniqueConstraint("code", name="uq_products_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "npc_suppliers",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("code", name="uq_npc_suppliers_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "simulation_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_running", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("elapsed_seconds", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("last_tick_at", DATETIME(fsp=6), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "npc_rules",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("product_id", _bigint(), nullable=False),
        sa.Column("npc_supplier_id", _bigint(), nullable=False),
        sa.Column("is_invited", sa.Boolean(), nullable=False),
        sa.Column("response_probability", sa.Numeric(4, 3), nullable=False),
        sa.Column("min_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_delivery_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("max_delivery_minutes", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["npc_supplier_id"], ["npc_suppliers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("product_id", "npc_supplier_id", name="uq_npc_rule_product_supplier"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "tenders",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("product_id", _bigint(), nullable=False),
        sa.Column("quantity_ton", sa.Numeric(12, 3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("opened_at_seconds", sa.Numeric(16, 3), nullable=False),
        sa.Column("offer_closes_at_seconds", sa.Numeric(16, 3), nullable=False),
        sa.Column("evaluate_at_seconds", sa.Numeric(16, 3), nullable=False),
        sa.Column("awarded_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("delivery_due_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("delivered_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("winning_participation_id", _bigint(), nullable=True),
        sa.Column("evaluated_stock_kg", sa.Numeric(16, 6), nullable=True),
        sa.Column("evaluated_consumption_kg_per_min", sa.Numeric(12, 3), nullable=True),
        sa.Column("evaluated_coverage_minutes", sa.Numeric(16, 6), nullable=True),
        sa.Column("result_reason", sa.String(500), nullable=True),
        sa.Column("created_at", DATETIME(fsp=6), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_tenders_code"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_tenders_product_status", "tenders", ["product_id", "status"])
    op.create_index("ix_tenders_status_close", "tenders", ["status", "offer_closes_at_seconds"])
    op.create_table(
        "tender_participations",
        sa.Column("id", _bigint(), primary_key=True, autoincrement=True),
        sa.Column("tender_id", _bigint(), nullable=False),
        sa.Column("npc_supplier_id", _bigint(), nullable=False),
        sa.Column("response_probability", sa.Numeric(4, 3), nullable=False),
        sa.Column("min_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_delivery_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("max_delivery_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("will_respond", sa.Boolean(), nullable=False),
        sa.Column("response_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("has_offer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("delivery_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("submitted_at_seconds", sa.Numeric(16, 3), nullable=True),
        sa.Column("decision", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("decision_reason", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["npc_supplier_id"], ["npc_suppliers.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tender_id", "npc_supplier_id", name="uq_participation_tender_supplier"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_participations_tender_offer", "tender_participations", ["tender_id", "has_offer"])
    op.create_foreign_key(
        "fk_tenders_winning_participation",
        "tenders",
        "tender_participations",
        ["winning_participation_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenders_winning_participation", "tenders", type_="foreignkey")
    op.drop_index("ix_participations_tender_offer", table_name="tender_participations")
    op.drop_table("tender_participations")
    op.drop_index("ix_tenders_status_close", table_name="tenders")
    op.drop_index("ix_tenders_product_status", table_name="tenders")
    op.drop_table("tenders")
    op.drop_table("npc_rules")
    op.drop_table("simulation_state")
    op.drop_table("npc_suppliers")
    op.drop_table("products")
