from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from pydantic.alias_generators import to_camel

BookFormat = Literal["Paperback", "Hardcover", "E-book", "Audiobook"]
PaymentMode = Literal["Credit card", "Debit card", "UPI", "Wallet", "Cash on delivery"]
OrderStatus = Literal["Placed", "Cancelled"]

# Stripped, non-empty text. Mirrors the "no blank" checks in the checkout form.
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[A-Za-z][A-Za-z .'-]*$")]


class CamelModel(BaseModel):
    """JSON uses camelCase (matches the Angular models); Python uses snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- Catalog -----------------------------------------------------------------------------------
class CoverStyle(CamelModel):
    bg: str
    fg: str
    accent: str
    motif: str


class Book(CamelModel):
    id: str
    title: str
    author: str
    publisher: str
    description: str
    category: str
    genres: list[str]
    language: str
    format: BookFormat
    price: float = Field(ge=0)
    discount_percent: float = Field(ge=0, le=100)
    tax_percent: float = Field(ge=0, le=100)
    delivery_days: int = Field(ge=0)
    rating: float = Field(ge=0, le=5)
    rating_count: int = Field(ge=0)
    sold: int = Field(ge=0)
    published: str
    cover: CoverStyle


class Writer(CamelModel):
    name: str
    slug: str
    bio: str
    location: str


class Coupon(CamelModel):
    code: str
    description: str
    percent: float | None = None
    flat: float | None = None
    max_discount: float | None = None
    min_order: float = 0


class Review(CamelModel):
    id: str
    book_id: str
    author: str
    rating: int = Field(ge=1, le=5)
    text: str
    date: datetime


class ReviewIn(CamelModel):
    rating: int = Field(ge=1, le=5)
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=100)]


# ---- Users -------------------------------------------------------------------------------------
class Address(CamelModel):
    first_name: Name
    last_name: Name
    line1: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
    email: EmailStr
    city: Name
    pin: Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{5}$")]
    country_code: Annotated[str, StringConstraints(pattern=r"^\+[0-9]{1,4}$")] = "+91"
    phone: Annotated[str, StringConstraints(pattern=r"^[6-9][0-9]{9}$")]
    state: Text
    country: Text


class User(CamelModel):
    name: str
    email: EmailStr
    gift_points: int
    address: Address | None = None


class RegisterIn(CamelModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    email: EmailStr
    password: Annotated[str, StringConstraints(min_length=6, max_length=72)]


class LoginIn(CamelModel):
    email: EmailStr
    password: Annotated[str, StringConstraints(max_length=72)]


class TokenOut(CamelModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: User


# ---- Orders ------------------------------------------------------------------------------------
class PriceBreakdown(CamelModel):
    item_count: int
    subtotal: float
    product_discount: float
    product_discount_percent: float
    tax: float
    shipping: float
    coupon_code: str | None
    coupon_discount: float
    points_used: int
    total: float


class PaymentInfo(CamelModel):
    mode: PaymentMode
    # Masked, human readable detail e.g. "â€¢â€¢â€¢â€¢ 4242". Raw card data must never be sent.
    detail: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class OrderLine(CamelModel):
    book_id: str
    title: str
    author: str
    description: str
    format: BookFormat
    genres: list[str]
    price: float
    qty: int
    delivery_date: datetime


class Order(CamelModel):
    id: str
    number: str
    user_email: str
    placed_at: datetime
    delivery_date: datetime
    lines: list[OrderLine]
    address: Address
    payment: PaymentInfo
    pricing: PriceBreakdown
    points_earned: int
    status: OrderStatus
    cancelled_at: datetime | None = None


class CartLineIn(CamelModel):
    book_id: str
    qty: int = Field(ge=1, le=10)


class OrderIn(CamelModel):
    items: list[CartLineIn] = Field(min_length=1, max_length=50)
    address: Address
    payment: PaymentInfo
    coupon_code: str | None = None
    use_points: bool = False
