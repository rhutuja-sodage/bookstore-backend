"""Server-side pricing. Mirrors bookworm/src/app/core/pricing.ts so quotes and orders agree."""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas import Book, Coupon, PriceBreakdown

SHIPPING_CHARGE = 0.0  # delivery is free
LOYALTY_THRESHOLD = 1000.0
HOURS_48 = 48


def round_money(value: float) -> float:
    return float(Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def net_amount(items: list[tuple[Book, int]]) -> float:
    return round_money(sum(b.price * q * (1 - b.discount_percent / 100) for b, q in items))


def find_coupon(coupons: list[Coupon], code: str, net: float) -> tuple[Coupon | None, str | None]:
    normalized = code.strip().upper()
    if not normalized:
        return None, "Enter a coupon code."
    coupon = next((c for c in coupons if c.code == normalized), None)
    if coupon is None:
        return None, "Invalid coupon code."
    if net < coupon.min_order:
        return None, f"Coupon needs a minimum order of ₹{coupon.min_order:g}."
    return coupon, None


def coupon_value(coupon: Coupon, net: float) -> float:
    value = coupon.flat if coupon.flat is not None else net * (coupon.percent or 0) / 100
    if coupon.max_discount is not None:
        value = min(value, coupon.max_discount)
    return round_money(min(value, net))


def price_cart(items: list[tuple[Book, int]], coupon: Coupon | None = None, points_to_use: int = 0) -> PriceBreakdown:
    """Per item: discount = price x qty x discount%; tax = (price x qty - discount) x tax%."""
    item_count = 0
    subtotal = product_discount = tax = 0.0
    for book, qty in items:
        gross = book.price * qty
        discount = gross * book.discount_percent / 100
        item_count += qty
        subtotal += gross
        product_discount += discount
        tax += (gross - discount) * book.tax_percent / 100

    subtotal, product_discount, tax = round_money(subtotal), round_money(product_discount), round_money(tax)
    net = subtotal - product_discount
    shipping = SHIPPING_CHARGE if items else 0.0
    coupon_discount = coupon_value(coupon, net) if coupon and net >= coupon.min_order else 0.0

    before_points = round_money(net + tax + shipping - coupon_discount)
    points_used = max(0, min(int(points_to_use), int(before_points)))

    return PriceBreakdown(
        item_count=item_count,
        subtotal=subtotal,
        product_discount=product_discount,
        product_discount_percent=round_money(product_discount / subtotal * 100) if subtotal else 0.0,
        tax=tax,
        shipping=shipping,
        coupon_code=coupon.code if coupon and coupon_discount > 0 else None,
        coupon_discount=coupon_discount,
        points_used=points_used,
        total=round_money(before_points - points_used),
    )


def gift_points_earned(order_total: float, previous_orders_total: float) -> int:
    """5% of the amount paid, 7% once earlier non-cancelled orders add up to ₹1,000."""
    rate = 0.07 if previous_orders_total >= LOYALTY_THRESHOLD else 0.05
    return int(order_total * rate)
