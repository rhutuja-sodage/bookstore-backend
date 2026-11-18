import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.database import from_doc, to_doc
from app.deps import get_current_user, get_db
from app.pricing import HOURS_48, find_coupon, gift_points_earned, net_amount, price_cart
from app.schemas import Book, Coupon, Order, OrderIn, OrderLine

router = APIRouter(prefix="/api/orders", tags=["orders"])

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_order_number(now: datetime) -> str:
    """Unique, human friendly order number such as BW-20260712-4F9K2Q."""
    return f"BW-{now:%Y%m%d}-{''.join(secrets.choice(_ALPHABET) for _ in range(6))}"


async def _adjust_points(db: AsyncDatabase, email: str, delta: int, *, require: int = 0) -> bool:
    """Atomically adds delta to the gift points (never below 0). With `require`, fails if the balance is lower."""
    flt: dict[str, Any] = {"_id": email}
    if require:
        flt["giftPoints"] = {"$gte": require}
    result = await db.users.update_one(flt, [{"$set": {"giftPoints": {"$max": [0, {"$add": ["$giftPoints", delta]}]}}}])
    return result.matched_count == 1


@router.get("", response_model=list[Order])
async def list_orders(
    user: Annotated[dict[str, Any], Depends(get_current_user)], db: Annotated[AsyncDatabase, Depends(get_db)]
) -> list[dict[str, Any]]:
    docs = await db.orders.find({"userEmail": user["_id"]}).sort("placedAt", -1).to_list()
    return [from_doc(d) for d in docs]


@router.get("/{number}", response_model=Order)
async def get_order(
    number: str, user: Annotated[dict[str, Any], Depends(get_current_user)], db: Annotated[AsyncDatabase, Depends(get_db)]
) -> dict[str, Any]:
    doc = await db.orders.find_one({"number": number, "userEmail": user["_id"]})
    if doc is None:
        raise HTTPException(404, "Order not found.")
    return from_doc(doc)


@router.post("", response_model=Order, status_code=201)
async def place_order(
    body: OrderIn,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> dict[str, Any]:
    """Prices come from the catalog, never from the client."""
    qty_by_id: dict[str, int] = {}
    for line in body.items:
        qty_by_id[line.book_id] = min(10, qty_by_id.get(line.book_id, 0) + line.qty)
    docs = await db.books.find({"_id": {"$in": list(qty_by_id)}}).to_list()
    books = {d["_id"]: Book.model_validate(from_doc(d)) for d in docs}
    missing = sorted(set(qty_by_id) - set(books))
    if missing:
        raise HTTPException(422, f"Unknown book(s): {', '.join(missing)}.")
    items = [(books[i], q) for i, q in qty_by_id.items()]

    coupon: Coupon | None = None
    if body.coupon_code:
        coupons = [Coupon.model_validate(c) for c in await db.coupons.find({}, {"_id": 0}).to_list()]
        coupon, error = find_coupon(coupons, body.coupon_code, net_amount(items))
        if coupon is None:
            raise HTTPException(422, error)

    pricing = price_cart(items, coupon, user["giftPoints"] if body.use_points else 0)

    cursor = await db.orders.aggregate([
        {"$match": {"userEmail": user["_id"], "status": {"$ne": "Cancelled"}}},
        {"$group": {"_id": None, "total": {"$sum": "$pricing.total"}}},
    ])
    previous = await cursor.to_list()
    points_earned = gift_points_earned(pricing.total, previous[0]["total"] if previous else 0)

    placed = datetime.now(UTC)
    lines = [
        OrderLine(
            book_id=b.id, title=b.title, author=b.author, description=b.description, format=b.format, genres=b.genres,
            price=b.price, qty=q, delivery_date=placed + timedelta(days=b.delivery_days),
        )
        for b, q in items
    ]
    order = Order(
        id=f"ord_{secrets.token_hex(8)}",
        number=generate_order_number(placed),
        user_email=user["_id"],
        placed_at=placed,
        delivery_date=max(line.delivery_date for line in lines),
        lines=lines,
        address=body.address,
        payment=body.payment,
        pricing=pricing,
        points_earned=points_earned,
        status="Placed",
    )

    # Spend / earn gift points first (guarded against a concurrent overspend), then store the order.
    if not await _adjust_points(db, user["_id"], points_earned - pricing.points_used, require=pricing.points_used):
        raise HTTPException(409, "Not enough gift points.")
    for _ in range(5):
        try:
            await db.orders.insert_one(to_doc(order))
            return order.model_dump(by_alias=True)
        except DuplicateKeyError:
            order.number = generate_order_number(placed)
    await _adjust_points(db, user["_id"], pricing.points_used - points_earned)
    raise HTTPException(500, "Could not allocate an order number. Please try again.")


@router.post("/{number}/cancel", response_model=Order)
async def cancel_order(
    number: str,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> dict[str, Any]:
    doc = await db.orders.find_one({"number": number, "userEmail": user["_id"]})
    if doc is None:
        raise HTTPException(404, "Order not found.")
    if doc["status"] == "Cancelled":
        raise HTTPException(409, "Order is already cancelled.")
    placed_at = doc["placedAt"].replace(tzinfo=UTC)
    if datetime.now(UTC) - placed_at > timedelta(hours=HOURS_48):
        raise HTTPException(409, "Orders can only be cancelled within 48 hours of payment.")

    now = datetime.now(UTC)
    updated = await db.orders.find_one_and_update(
        {"_id": doc["_id"], "status": "Placed"},
        {"$set": {"status": "Cancelled", "cancelledAt": now}},
        return_document=True,
    )
    if updated is None:  # cancelled concurrently
        raise HTTPException(409, "Order is already cancelled.")
    # Reverse the gift-point movements of this order
    await _adjust_points(db, user["_id"], doc["pricing"]["pointsUsed"] - doc["pointsEarned"])
    return from_doc(updated)
