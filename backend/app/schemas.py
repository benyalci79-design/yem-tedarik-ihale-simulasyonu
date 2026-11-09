from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _max_places(value: Decimal, places: int) -> Decimal:
    if abs(value.as_tuple().exponent) > places:
        raise ValueError(f"En fazla {places} ondalık basamak kullanılabilir.")
    return value


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_stock_kg: Decimal | None = Field(default=None, ge=0)
    consumption_kg_per_min: Decimal | None = Field(default=None, gt=0)
    critical_coverage_minutes: Decimal | None = Field(default=None, gt=0)
    target_coverage_minutes: Decimal | None = Field(default=None, gt=0)
    offer_window_seconds: int | None = Field(default=None, ge=10, le=600)

    @field_validator("current_stock_kg", "consumption_kg_per_min")
    @classmethod
    def validate_three_places(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _max_places(value, 3)

    @field_validator("critical_coverage_minutes", "target_coverage_minutes")
    @classmethod
    def validate_two_places(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _max_places(value, 2)

    @model_validator(mode="after")
    def validate_target_if_both_present(self):
        if (
            self.target_coverage_minutes is not None
            and self.critical_coverage_minutes is not None
            and self.target_coverage_minutes <= self.critical_coverage_minutes
        ):
            raise ValueError("Hedef kapsama kritik kapsama değerinden büyük olmalıdır.")
        return self


class NpcRulePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_invited: bool | None = None
    response_probability: Decimal | None = Field(default=None, ge=0, le=1)
    min_price: Decimal | None = Field(default=None, gt=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    min_delivery_minutes: int | None = Field(default=None, ge=1, le=60)
    max_delivery_minutes: int | None = Field(default=None, ge=1, le=60)

    @field_validator("response_probability")
    @classmethod
    def validate_probability_places(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _max_places(value, 3)

    @field_validator("min_price", "max_price")
    @classmethod
    def validate_price_places(cls, value: Decimal | None) -> Decimal | None:
        return None if value is None else _max_places(value, 2)

    @model_validator(mode="after")
    def validate_ranges_if_both_present(self):
        if self.min_price is not None and self.max_price is not None and self.max_price < self.min_price:
            raise ValueError("Maksimum fiyat minimum fiyattan küçük olamaz.")
        if (
            self.min_delivery_minutes is not None
            and self.max_delivery_minutes is not None
            and self.max_delivery_minutes < self.min_delivery_minutes
        ):
            raise ValueError("Maksimum teslim süresi minimum teslim süresinden küçük olamaz.")
        return self
