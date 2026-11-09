from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    DECIMAL,
    DATETIME,
    INTEGER,
    SMALLINT,
    VARCHAR,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    current_stock_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 6), nullable=False)
    consumption_kg_per_min: Mapped[Decimal] = mapped_column(DECIMAL(12, 3), nullable=False)
    critical_coverage_minutes: Mapped[Decimal] = mapped_column(DECIMAL(8, 2), nullable=False)
    target_coverage_minutes: Mapped[Decimal] = mapped_column(DECIMAL(8, 2), nullable=False)
    offer_window_seconds: Mapped[int] = mapped_column(INTEGER, nullable=False)
    next_eligible_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, default=0)

    npc_rules: Mapped[list["NpcRule"]] = relationship(back_populates="product", passive_deletes=True)
    tenders: Mapped[list["Tender"]] = relationship(back_populates="product", passive_deletes=True)


class NpcSupplier(Base):
    __tablename__ = "npc_suppliers"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)

    rules: Mapped[list["NpcRule"]] = relationship(back_populates="npc_supplier", passive_deletes=True)
    participations: Mapped[list["TenderParticipation"]] = relationship(
        back_populates="npc_supplier", passive_deletes=True
    )


class NpcRule(Base):
    __tablename__ = "npc_rules"
    __table_args__ = (UniqueConstraint("product_id", "npc_supplier_id", name="uq_npc_rule_product_supplier"),)

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    npc_supplier_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("npc_suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    is_invited: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=True)
    response_probability: Mapped[Decimal] = mapped_column(DECIMAL(4, 3), nullable=False)
    min_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    max_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    min_delivery_minutes: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    max_delivery_minutes: Mapped[int] = mapped_column(SMALLINT, nullable=False)

    product: Mapped[Product] = relationship(back_populates="npc_rules")
    npc_supplier: Mapped[NpcSupplier] = relationship(back_populates="rules")


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    is_running: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    elapsed_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, default=0)
    last_tick_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    last_error: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        Index("ix_tenders_product_status", "product_id", "status"),
        Index("ix_tenders_status_close", "status", "offer_closes_at_seconds"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(30), unique=True, nullable=False)
    product_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_ton: Mapped[Decimal] = mapped_column(DECIMAL(12, 3), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(16), nullable=False)
    opened_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    offer_closes_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    evaluate_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    awarded_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivery_due_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivered_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    winning_participation_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("tender_participations.id", ondelete="RESTRICT"), nullable=True
    )
    evaluated_stock_kg: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 6), nullable=True)
    evaluated_consumption_kg_per_min: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 3), nullable=True)
    evaluated_coverage_minutes: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 6), nullable=True)
    result_reason: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)

    product: Mapped[Product] = relationship(back_populates="tenders")
    participations: Mapped[list["TenderParticipation"]] = relationship(
        back_populates="tender", foreign_keys="TenderParticipation.tender_id", passive_deletes=True
    )


class TenderParticipation(Base):
    __tablename__ = "tender_participations"
    __table_args__ = (
        UniqueConstraint("tender_id", "npc_supplier_id", name="uq_participation_tender_supplier"),
        Index("ix_participations_tender_offer", "tender_id", "has_offer"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("tenders.id", ondelete="RESTRICT"), nullable=False
    )
    npc_supplier_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("npc_suppliers.id", ondelete="RESTRICT"), nullable=False
    )
    response_probability: Mapped[Decimal] = mapped_column(DECIMAL(4, 3), nullable=False)
    min_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    max_price: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    min_delivery_minutes: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    max_delivery_minutes: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    will_respond: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    response_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    has_offer: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    unit_price: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    delivery_minutes: Mapped[int | None] = mapped_column(SMALLINT, nullable=True)
    submitted_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    decision: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="PENDING")
    decision_reason: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)

    tender: Mapped[Tender] = relationship(back_populates="participations", foreign_keys=[tender_id])
    npc_supplier: Mapped[NpcSupplier] = relationship(back_populates="participations")
