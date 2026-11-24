"""Pydantic request models.

Validation here mirrors what the Milestone 2 procedures check, so bad input
is rejected with a clear message before it reaches the database: required
fields, 11-digit phone numbers, 16-digit card numbers, numbers, dates.
Passwords are never returned in any response.
"""

from datetime import date, time
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

PHONE_RE = r"^\d{11}$"
CARD_RE = r"^\d{16}$"


class RegisterBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=30)
    middle_name: Optional[str] = Field(None, max_length=30)
    last_name: str = Field(..., min_length=1, max_length=30)
    username: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=1, max_length=30)
    email: str = Field(..., max_length=100)
    phone: str = Field(..., pattern=PHONE_RE)
    dob: Optional[date] = None

    @field_validator("email")
    @classmethod
    def _email_looks_valid(cls, v):
        if "@" not in v or "." not in v.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return v


class RiderRegister(RegisterBase):
    vehicle_type: str = Field(..., min_length=1, max_length=30)
    plate_no: str = Field(..., min_length=1, max_length=15)
    license_no: str = Field(..., min_length=1, max_length=20)
    zone_id: int


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=1, max_length=30)


class CreateAdminBody(RegisterBase):
    role: Literal["Super Admin", "Zone Admin"]
    zone_id: Optional[int] = None

    @model_validator(mode="after")
    def _zone_rules(self):
        if self.role == "Zone Admin" and self.zone_id is None:
            raise ValueError("A Zone Admin needs a zone.")
        if self.role == "Super Admin" and self.zone_id is not None:
            raise ValueError("A Super Admin has no zone.")
        return self


class AssignZoneBody(BaseModel):
    zone_id: int


class SuspendBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


class IssueVoucherBody(BaseModel):
    customer_id: int
    promo_code: str = Field(..., min_length=1, max_length=30)
    is_percentage: bool
    amount: Decimal = Field(..., gt=0)
    expiry_date: date


class BlacklistBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)


class CreateZoneBody(BaseModel):
    zone_name: str = Field(..., min_length=1, max_length=50)
    delivery_fee: Decimal = Field(..., ge=0)


class UpdateZoneFeeBody(BaseModel):
    new_fee: Decimal = Field(..., ge=0)


class RegisterBusinessBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    link_website: Optional[str] = Field(None, max_length=255)
    zone_id: int
    opening_hour: time
    closing_hour: time
    expected_delivery_time: int = Field(..., gt=0)
    phone: Optional[str] = Field(None, pattern=PHONE_RE)
    business_type: Literal["Restaurant", "Pharmacy"]
    cuisine_type: Optional[str] = Field(None, max_length=50)
    food_category: Optional[str] = Field(None, max_length=50)
    pharmacy_type: Optional[str] = Field(None, max_length=50)

    @model_validator(mode="after")
    def _type_rules(self):
        if self.business_type == "Restaurant":
            if not self.cuisine_type or not self.food_category:
                raise ValueError("A restaurant needs a cuisine type and a food category.")
        else:
            if not self.pharmacy_type:
                raise ValueError("A pharmacy needs a pharmacy type.")
        return self


class UpdateBusinessBody(BaseModel):
    opening_hour: Optional[time] = None
    closing_hour: Optional[time] = None
    phone: Optional[str] = Field(None, pattern=PHONE_RE)
    link_website: Optional[str] = Field(None, max_length=255)


class ProductBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    category: str = Field(..., min_length=1, max_length=50)
    price: Decimal = Field(..., gt=0)
    is_available: bool = True


class ToggleProductBody(BaseModel):
    is_available: bool


class PromotionBody(BaseModel):
    discount_amount: Decimal = Field(..., ge=0)


class AvailabilityBody(BaseModel):
    is_available: bool


class AddressBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=150)
    zone_id: int


class UpdateAddressBody(BaseModel):
    description: Optional[str] = Field(None, max_length=150)
    zone_id: Optional[int] = None
    action: Literal["Update", "Delete", "Remove"]

    @model_validator(mode="after")
    def _update_rules(self):
        if self.action == "Update" and (not self.description or self.zone_id is None):
            raise ValueError("Updating an address needs a description and a zone.")
        return self


class CardBody(BaseModel):
    card_no: str = Field(..., pattern=CARD_RE)
    card_holder_name: str = Field(..., min_length=1, max_length=100)
    expiration_date: date


class AddToCartBody(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1)
    notes: Optional[str] = Field(None, max_length=255)


class CheckoutPreviewBody(BaseModel):
    voucher_id: Optional[int] = None


class CheckoutBody(BaseModel):
    voucher_id: Optional[int] = None
    payment_method: Literal["Cash", "Card", "Wallet"]
    card_id: Optional[int] = None

    @model_validator(mode="after")
    def _card_rules(self):
        if self.payment_method == "Card" and self.card_id is None:
            raise ValueError("Paying by card needs a card.")
        if self.payment_method != "Card" and self.card_id is not None:
            raise ValueError("A card is only used when paying by Card.")
        return self


class FavoriteBody(BaseModel):
    item_id: int
    item_type: Literal["Business", "Product"]


class FeedbackBody(BaseModel):
    headline: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    rating: int = Field(..., ge=1, le=5)


class RateRiderBody(BaseModel):
    rider_rating: int = Field(..., ge=1, le=5)


class ReorderBody(BaseModel):
    address_id: int
