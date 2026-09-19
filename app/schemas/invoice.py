from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class CurrencyEnum(StrEnum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"
    CHF = "CHF"


class PartyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Company or individual name")
    tax_id: str | None = Field(default=None, description="Tax identification number (e.g. VAT, EIN)")
    address: str | None = Field(default=None, description="Physical or mailing address")
    email: str | None = Field(default=None, description="Contact email address")


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    description: str = Field(..., min_length=1, description="Description of the item or service")
    quantity: float = Field(..., gt=0, description="Quantity of items (must be greater than zero)")
    unit_price: float = Field(..., ge=0, description="Price per single unit (non-negative)")
    total: float = Field(..., ge=0, description="Total amount for this line item")

    @field_validator("total")
    @classmethod
    def validate_line_item_total(cls, total: float, info: ValidationInfo) -> float:
        values = info.data
        if "quantity" in values and "unit_price" in values:
            expected = round(values["quantity"] * values["unit_price"], 2)
            actual = round(total, 2)
            if abs(expected - actual) > 0.05:
                raise ValueError(
                    f"Line item total ({actual:.2f}) does not match quantity ({values['quantity']}) * "
                    f"unit_price ({values['unit_price']:.2f}) = {expected:.2f}"
                )
        return round(total, 2)


class Invoice(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(..., min_length=1, description="Unique invoice identifier")
    supplier: PartyInfo = Field(..., description="Vendor or supplier details")
    customer: PartyInfo = Field(..., description="Client or customer details")
    invoice_date: date = Field(..., description="Date invoice was issued (YYYY-MM-DD)")
    due_date: date | None = Field(default=None, description="Payment due date (YYYY-MM-DD)")
    currency: CurrencyEnum = Field(..., description="Three-letter currency code (e.g., USD, EUR, GBP)")
    line_items: list[LineItem] = Field(..., min_length=1, description="List of invoiced items")
    subtotal: float = Field(..., ge=0, description="Subtotal before tax")
    tax: float = Field(..., ge=0, description="Tax amount")
    total: float = Field(..., ge=0, description="Grand total")

    @model_validator(mode="after")
    def validate_invoice_totals_and_dates(self) -> "Invoice":
        # Check subtotal against sum of line items
        items_sum = round(sum(item.total for item in self.line_items), 2)
        reported_subtotal = round(self.subtotal, 2)
        if abs(items_sum - reported_subtotal) > 0.05:
            raise ValueError(f"Subtotal ({reported_subtotal:.2f}) does not match sum of line items ({items_sum:.2f})")

        # Check total against subtotal + tax
        expected_total = round(self.subtotal + self.tax, 2)
        reported_total = round(self.total, 2)
        if abs(expected_total - reported_total) > 0.05:
            raise ValueError(
                f"Total ({reported_total:.2f}) does not match subtotal ({reported_subtotal:.2f}) + "
                f"tax ({round(self.tax, 2):.2f}) = {expected_total:.2f}"
            )

        # Check due_date >= invoice_date
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError(f"Due date ({self.due_date}) cannot be earlier than invoice date ({self.invoice_date})")

        return self
