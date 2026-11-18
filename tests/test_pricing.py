from app.pricing import find_coupon, gift_points_earned, net_amount, price_cart
from app.schemas import Book, Coupon

BOOK = Book.model_validate({
    "id": "art-of-focus", "title": "t", "author": "a", "publisher": "p", "description": "d", "category": "c", "genres": [],
    "language": "English", "format": "Paperback", "price": 399, "discountPercent": 10, "taxPercent": 12, "deliveryDays": 4,
    "rating": 4, "ratingCount": 1, "sold": 1, "published": "2025-01-01", "cover": {"bg": "", "fg": "", "accent": "", "motif": "sun"},
})
COUPONS = [
    Coupon(code="BOOKS10", description="", percent=10, max_discount=200, min_order=0),
    Coupon(code="READMORE15", description="", percent=15, max_discount=300, min_order=700),
]


def test_matches_frontend_pricing_example():
    # Same numbers as bookworm/src/app/core/core.spec.ts
    p = price_cart([(BOOK, 2)])
    assert (p.item_count, p.subtotal, p.product_discount, p.tax, p.shipping, p.total) == (2, 798, 79.8, 86.18, 0, 804.38)


def test_empty_cart_is_zero():
    assert price_cart([]).total == 0


def test_coupon_and_points_never_exceed_payable():
    coupon, _ = find_coupon(COUPONS, "books10", net_amount([(BOOK, 2)]))
    p = price_cart([(BOOK, 2)], coupon, points_to_use=100000)
    assert p.coupon_code == "BOOKS10"
    assert p.points_used == int(p.subtotal - p.product_discount + p.tax - p.coupon_discount)
    assert 0 <= p.total < 1


def test_coupon_errors():
    assert find_coupon(COUPONS, "NOPE", 1000)[1] == "Invalid coupon code."
    assert find_coupon(COUPONS, "READMORE15", 100)[0] is None
    assert find_coupon(COUPONS, " ", 100)[1] == "Enter a coupon code."


def test_gift_point_rates():
    assert gift_points_earned(1000, 0) == 50
    assert gift_points_earned(1000, 1500) == 70
