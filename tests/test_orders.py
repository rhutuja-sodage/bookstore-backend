import re
from datetime import UTC, datetime, timedelta

from pymongo import MongoClient

from app.config import get_settings


def points(client, headers):
    return client.get("/api/users/me", headers=headers).json()["giftPoints"]


def test_place_order_prices_come_from_the_server(client, new_user, order_body):
    r = client.post("/api/orders", json=order_body(), headers=new_user["headers"])
    assert r.status_code == 201, r.text
    o = r.json()
    assert re.fullmatch(r"BW-\d{8}-[A-Z2-9]{6}", o["number"]) and o["status"] == "Placed"
    assert o["userEmail"] == new_user["email"]
    assert (o["pricing"]["subtotal"], o["pricing"]["tax"], o["pricing"]["total"]) == (798, 86.18, 804.38)
    assert o["lines"][0]["price"] == 399 and o["lines"][0]["title"] == "The Art of Focus"
    assert o["pointsEarned"] == 40  # 5% of 804.38
    assert points(client, new_user["headers"]) == 40
    assert client.get(f"/api/orders/{o['number']}", headers=new_user["headers"]).json()["id"] == o["id"]
    assert [x["number"] for x in client.get("/api/orders", headers=new_user["headers"]).json()] == [o["number"]]


def test_client_cannot_inject_prices(client, new_user, order_body):
    body = order_body()
    body["pricing"] = {"total": 1}
    body["items"][0]["price"] = 1
    r = client.post("/api/orders", json=body, headers=new_user["headers"])
    assert r.json()["pricing"]["total"] == 804.38


def test_order_validation(client, new_user, order_body):
    h = new_user["headers"]
    assert client.post("/api/orders", json=order_body(), headers=None).status_code == 401
    assert client.post("/api/orders", json={**order_body(), "items": []}, headers=h).status_code == 422
    assert client.post("/api/orders", json=order_body((("art-of-focus", 11),)), headers=h).status_code == 422
    assert client.post("/api/orders", json=order_body((("art-of-focus", 0),)), headers=h).status_code == 422
    r = client.post("/api/orders", json=order_body((("no-such-book", 1),)), headers=h)
    assert r.status_code == 422 and "no-such-book" in r.json()["detail"]
    bad_addr = {**order_body(), "address": {**order_body()["address"], "pin": "1"}}
    assert client.post("/api/orders", json=bad_addr, headers=h).status_code == 422
    bad_pay = {**order_body(), "payment": {"mode": "Bitcoin", "detail": "x"}}
    assert client.post("/api/orders", json=bad_pay, headers=h).status_code == 422
    assert client.get("/api/orders", headers=h).json() == []  # nothing was stored


def test_coupon_applied_server_side(client, new_user, order_body):
    h = new_user["headers"]
    ok = client.post("/api/orders", json=order_body(couponCode="books10"), headers=h).json()
    assert ok["pricing"]["couponCode"] == "BOOKS10" and ok["pricing"]["couponDiscount"] == 71.82
    bad = client.post("/api/orders", json=order_body(couponCode="NOPE"), headers=h)
    assert bad.status_code == 422 and bad.json()["detail"] == "Invalid coupon code."
    low = client.post("/api/orders", json=order_body((("art-of-focus", 1),), couponCode="READMORE15"), headers=h)
    assert low.status_code == 422 and "minimum order" in low.json()["detail"]


def test_duplicate_lines_are_merged_and_capped(client, new_user, order_body):
    r = client.post("/api/orders", json=order_body((("art-of-focus", 8), ("art-of-focus", 8))), headers=new_user["headers"])
    assert [(l["bookId"], l["qty"]) for l in r.json()["lines"]] == [("art-of-focus", 10)]


def test_gift_points_are_spent_and_cannot_be_overspent(client, new_user, order_body):
    h = new_user["headers"]
    first = client.post("/api/orders", json=order_body(), headers=h).json()  # earns 40
    second = client.post("/api/orders", json=order_body(usePoints=True), headers=h).json()
    assert second["pricing"]["pointsUsed"] == 40
    assert second["pricing"]["total"] == 764.38
    assert second["pointsEarned"] == 38  # 5% of 764.38 -> 38 (loyalty bonus not yet reached)
    assert points(client, h) == 40 - 40 + 38
    assert first["number"] != second["number"]


def test_users_cannot_see_each_others_orders(client, new_user, demo_headers, order_body):
    o = client.post("/api/orders", json=order_body(), headers=new_user["headers"]).json()
    assert client.get(f"/api/orders/{o['number']}", headers=demo_headers).status_code == 404
    assert client.post(f"/api/orders/{o['number']}/cancel", headers=demo_headers).status_code == 404
    assert o["number"] not in [x["number"] for x in client.get("/api/orders", headers=demo_headers).json()]


def test_cancel_reverses_points(client, new_user, order_body):
    h = new_user["headers"]
    client.post("/api/orders", json=order_body(), headers=h)  # +40
    o = client.post("/api/orders", json=order_body(usePoints=True), headers=h).json()  # -40 +38
    assert points(client, h) == 38
    r = client.post(f"/api/orders/{o['number']}/cancel", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "Cancelled" and r.json()["cancelledAt"]
    assert points(client, h) == 38 + 40 - 38  # used points returned, earned points taken back
    again = client.post(f"/api/orders/{o['number']}/cancel", headers=h)
    assert again.status_code == 409 and points(client, h) == 40  # no double refund


def test_cancel_window_is_48_hours(client, new_user, order_body):
    h = new_user["headers"]
    o = client.post("/api/orders", json=order_body(), headers=h).json()
    db = MongoClient(get_settings().mongodb_url)[get_settings().mongodb_db]
    db.orders.update_one({"number": o["number"]}, {"$set": {"placedAt": datetime.now(UTC) - timedelta(hours=50)}})
    r = client.post(f"/api/orders/{o['number']}/cancel", headers=h)
    assert r.status_code == 409 and "48 hours" in r.json()["detail"]
    assert client.post("/api/orders/BW-NOPE/cancel", headers=h).status_code == 404


def test_loyalty_rate_uses_previous_non_cancelled_orders(client, new_user, order_body):
    h = new_user["headers"]
    big = client.post("/api/orders", json=order_body((("ultimate-guide-wealth", 1),)), headers=h).json()
    assert big["pricing"]["total"] >= 1000
    nxt = client.post("/api/orders", json=order_body(), headers=h).json()
    assert nxt["pointsEarned"] == int(nxt["pricing"]["total"] * 0.07)
    client.post(f"/api/orders/{big['number']}/cancel", headers=h)
    after = client.post("/api/orders", json=order_body(), headers=h).json()
    assert after["pointsEarned"] == int(after["pricing"]["total"] * 0.05)
