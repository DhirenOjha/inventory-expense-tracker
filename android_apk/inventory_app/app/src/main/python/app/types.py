from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.storage import ValidationError


@dataclass(frozen=True)
class Quantity:
    raw: str

    @property
    def value(self) -> Decimal:
        if self.raw is None:
            raise ValidationError("quantity is required")
        try:
            quantity = Decimal(str(self.raw).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError("quantity must be a number") from exc
        if quantity <= 0:
            raise ValidationError("quantity must be > 0")
        return quantity


@dataclass(frozen=True)
class Money:
    raw: str

    @property
    def value(self) -> Decimal:
        if self.raw is None:
            raise ValidationError("amount is required")
        try:
            amount = Decimal(str(self.raw).strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError("amount must be a number") from exc
        if amount < 0:
            raise ValidationError("amount must be >= 0")
        return amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

