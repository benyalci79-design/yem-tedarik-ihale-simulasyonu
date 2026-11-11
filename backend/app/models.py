from datetime import datetime
from decimal import Decimal

from sqlalchemy import BOOLEAN, ForeignKey, Index, UniqueConstraint, true
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, DECIMAL, INTEGER, SMALLINT, VARCHAR
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
    # Depo sınırı ve stoktaki ürünün ağırlıklı ortalama birim maliyeti (TL/kg).
    capacity_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="10000.000")
    avg_cost_per_kg: Mapped[Decimal] = mapped_column(DECIMAL(14, 6), nullable=False, server_default="0")
    # Kullanılmıyor: otomatik ihale akışı kaldırıldı. Sütun geriye dönük uyumluluk için duruyor.
    next_eligible_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, default=0)

    npc_rules: Mapped[list["NpcRule"]] = relationship(back_populates="product", passive_deletes=True)
    tenders: Mapped[list["Tender"]] = relationship(back_populates="product", passive_deletes=True)
    snapshots: Mapped[list["StockSnapshot"]] = relationship(back_populates="product", passive_deletes=True)


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
    # True: fiyata nakliye dahil. False: nakliye ayrıca seçilir.
    freight_included: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default=true())
    min_available_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="1000")
    max_available_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="3000")

    product: Mapped[Product] = relationship(back_populates="npc_rules")
    npc_supplier: Mapped[NpcSupplier] = relationship(back_populates="rules")


class SimulationState(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    is_running: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    elapsed_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, default=0)
    last_tick_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    last_error: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)
    # Hız çarpanı (0.50 / 1.00 / 2.00 / 3.00); sadece gerçek zaman ölçeklenir.
    speed_multiplier: Mapped[Decimal] = mapped_column(DECIMAL(4, 2), nullable=False, server_default="1.00")


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
    # Kullanılmıyor (otomatik değerlendirme kaldırıldı); açılışta kapanışa eşitlenir.
    evaluate_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    awarded_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivery_due_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivered_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    # Kullanılmıyor: çoklu award modeline geçildi. Sütun geriye dönük uyumluluk için duruyor.
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
    awards: Mapped[list["TenderAward"]] = relationship(
        back_populates="tender", foreign_keys="TenderAward.tender_id", passive_deletes=True
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
    # Davet anındaki kural anlık görüntüsü (sonradan ayar değişse bile sabit kalır).
    freight_included: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default=true())
    min_available_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="1000")
    max_available_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="3000")
    will_respond: Mapped[bool] = mapped_column(BOOLEAN, nullable=False)
    response_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    has_offer: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, default=False)
    unit_price: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    delivery_minutes: Mapped[int | None] = mapped_column(SMALLINT, nullable=True)
    offered_quantity_kg: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    accepted_quantity_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False, server_default="0")
    submitted_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    decision: Mapped[str] = mapped_column(VARCHAR(16), nullable=False, default="PENDING")
    decision_reason: Mapped[str | None] = mapped_column(VARCHAR(500), nullable=True)

    tender: Mapped[Tender] = relationship(back_populates="participations", foreign_keys=[tender_id])
    npc_supplier: Mapped[NpcSupplier] = relationship(back_populates="participations")
    award: Mapped["TenderAward | None"] = relationship(
        back_populates="participation", uselist=False, foreign_keys="TenderAward.participation_id"
    )


class Carrier(Base):
    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(VARCHAR(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    price_per_ton: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    transit_minutes: Mapped[int] = mapped_column(SMALLINT, nullable=False)
    is_active: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default=true())

    awards: Mapped[list["TenderAward"]] = relationship(back_populates="carrier", passive_deletes=True)


class TenderAward(Base):
    __tablename__ = "tender_awards"
    __table_args__ = (
        UniqueConstraint("participation_id", name="uq_award_participation"),
        Index("ix_awards_tender_status", "tender_id", "status"),
        Index("ix_awards_status_due", "status", "delivery_due_at_seconds"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    tender_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("tenders.id", ondelete="RESTRICT"), nullable=False
    )
    participation_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("tender_participations.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    unit_price_per_ton: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False)
    freight_included: Mapped[bool] = mapped_column(BOOLEAN, nullable=False, server_default=true())
    carrier_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("carriers.id", ondelete="RESTRICT"), nullable=True
    )
    carrier_price_per_ton: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    accepted_at_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    carrier_assigned_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivery_due_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    delivered_at_seconds: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 3), nullable=True)
    landed_cost_tl: Mapped[Decimal | None] = mapped_column(DECIMAL(16, 2), nullable=True)

    tender: Mapped[Tender] = relationship(back_populates="awards", foreign_keys=[tender_id])
    participation: Mapped[TenderParticipation] = relationship(back_populates="award", foreign_keys=[participation_id])
    carrier: Mapped[Carrier | None] = relationship(back_populates="awards")


class StockSnapshot(Base):
    __tablename__ = "stock_snapshots"
    __table_args__ = (
        Index("ix_snapshots_elapsed", "elapsed_seconds"),
        Index("ix_snapshots_product_elapsed", "product_id", "elapsed_seconds"),
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    elapsed_seconds: Mapped[Decimal] = mapped_column(DECIMAL(16, 3), nullable=False)
    product_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    stock_kg: Mapped[Decimal] = mapped_column(DECIMAL(16, 6), nullable=False)
    avg_cost_per_kg: Mapped[Decimal] = mapped_column(DECIMAL(14, 6), nullable=False)
    value_tl: Mapped[Decimal] = mapped_column(DECIMAL(18, 4), nullable=False)

    product: Mapped[Product] = relationship(back_populates="snapshots")
