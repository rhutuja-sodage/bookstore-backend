"""Loads the catalog and demo data into an empty database. Safe to run repeatedly."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pymongo.asynchronous.database import AsyncDatabase

from app.database import to_doc
from app.pricing import price_cart
from app.schemas import Address, Book, Coupon, Order, OrderLine, PaymentInfo, Review, Writer
from app.security import hash_password_async

SEED_DIR = Path(__file__).parent / "seed_data"

DEMO_EMAIL = "demo@bookworm.com"
DEMO_PASSWORD = "Demo@123"
DEMO_ADDRESS = Address(
    first_name="Demo", last_name="Reader", line1="12, Lotus Apartments, MG Road", email=DEMO_EMAIL,
    city="Pune", pin="411001", country_code="+91", phone="9876543210", state="Maharashtra", country="India",
)

COUPONS = [
    Coupon(code="BOOKS10", description="10% off (max ₹200)", percent=10, max_discount=200, min_order=0),
    Coupon(code="WELCOME100", description="₹100 off on orders above ₹300", flat=100, min_order=300),
    Coupon(code="READMORE15", description="15% off (max ₹300) on orders above ₹700", percent=15, max_discount=300, min_order=700),
]

SEED_REVIEWS = [
    Review(
        id="seed-r1", book_id="joy-of-minimalism", author="John Smith", rating=5, date=datetime(2026, 6, 28, tzinfo=UTC),
        text="The accordion component delivers large amounts of content in a small space through progressive disclosure. "
        "The user gets key details about the underlying content and can choose to expand that content within the constraints of the accordion.",
    ),
]


def _load(name: str) -> list[dict]:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))


async def _seed_collection(db: AsyncDatabase, name: str, docs: list[dict]) -> None:
    if docs and await db[name].count_documents({}, limit=1) == 0:
        await db[name].insert_many(docs)


async def _seed_demo_user(db: AsyncDatabase) -> None:
    if await db.users.find_one({"_id": DEMO_EMAIL}):
        return
    await db.users.insert_one({
        "_id": DEMO_EMAIL,
        "name": "Demo Reader",
        "passwordHash": await hash_password_async(DEMO_PASSWORD),
        "giftPoints": 120,
        "address": DEMO_ADDRESS.model_dump(by_alias=True),
    })
    # An older order so "Buy Again" and recommendations have data for the demo account.
    book_doc = await db.books.find_one({"_id": "art-of-focus"})
    if not book_doc:
        return
    book = Book.model_validate({**book_doc, "id": book_doc["_id"]})
    placed = datetime.now(UTC) - timedelta(days=20)
    delivered = placed + timedelta(days=5)
    order = Order(
        id="seed-1",
        number=f"BW-{placed:%Y%m%d}-SEED01",
        user_email=DEMO_EMAIL,
        placed_at=placed,
        delivery_date=delivered,
        lines=[OrderLine(
            book_id=book.id, title=book.title, author=book.author, description=book.description, format=book.format,
            genres=book.genres, price=book.price, qty=1, delivery_date=delivered,
        )],
        address=DEMO_ADDRESS,
        payment=PaymentInfo(mode="UPI", detail="demo@upi"),
        pricing=price_cart([(book, 1)]),
        points_earned=0,
        status="Placed",
    )
    await db.orders.insert_one(to_doc(order))


async def seed(db: AsyncDatabase) -> None:
    await _seed_collection(db, "books", [to_doc(Book.model_validate(b)) for b in _load("books.json")])
    await _seed_collection(db, "writers", [{**Writer.model_validate(w).model_dump(by_alias=True), "_id": w["slug"]} for w in _load("writers.json")])
    await _seed_collection(db, "coupons", [{**c.model_dump(by_alias=True), "_id": c.code} for c in COUPONS])
    await _seed_collection(db, "reviews", [to_doc(r) for r in SEED_REVIEWS])
    await _seed_demo_user(db)
