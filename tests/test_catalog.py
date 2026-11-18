def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_books_seeded(client):
    books = client.get("/api/books").json()
    assert len(books) == 31
    assert {"id", "title", "discountPercent", "taxPercent", "deliveryDays", "cover"} <= books[0].keys()


def test_search_matches_title_author_publisher_genre(client):
    ids = lambda **p: [b["id"] for b in client.get("/api/books", params=p).json()]  # noqa: E731
    assert "joy-of-minimalism" in ids(q="minimalism")
    assert len(ids(q="arjun")) == 1
    assert ids(q="nightfall") and ids(q="thriller")
    assert ids(q="(") == []  # regex characters are escaped, not interpreted


def test_filters_are_anded(client):
    r = client.get("/api/books", params={
        "category": "Fantasy", "language": "English", "format": "Paperback", "min_price": 400, "max_price": 599,
    }).json()
    assert [b["id"] for b in r] == ["dragon-crown"]


def test_sorting(client):
    asc = [b["price"] for b in client.get("/api/books", params={"sort": "price_asc"}).json()]
    desc = [b["price"] for b in client.get("/api/books", params={"sort": "price_desc"}).json()]
    assert asc == sorted(asc) and desc == sorted(desc, reverse=True)
    newest = [b["published"] for b in client.get("/api/books", params={"sort": "newest"}).json()]
    assert newest == sorted(newest, reverse=True)


def test_pagination_and_validation(client):
    assert len(client.get("/api/books", params={"limit": 5}).json()) == 5
    assert client.get("/api/books", params={"sort": "bogus"}).status_code == 422
    assert client.get("/api/books", params={"limit": 0}).status_code == 422


def test_get_book(client):
    assert client.get("/api/books/art-of-focus").json()["author"] == "Arjun Patel"
    assert client.get("/api/books/nope").status_code == 404


def test_writers_and_coupons(client):
    writers = client.get("/api/writers").json()
    assert len(writers) == 30
    assert client.get("/api/writers/daniel-reed").json()["name"] == "Daniel Reed"
    assert client.get("/api/writers/nobody").status_code == 404
    coupons = {c["code"]: c for c in client.get("/api/coupons").json()}
    assert set(coupons) == {"BOOKS10", "WELCOME100", "READMORE15"}
    assert "flat" not in coupons["BOOKS10"] and coupons["BOOKS10"]["maxDiscount"] == 200  # unset fields are omitted
    assert writers[0]["name"] == "Daniel Reed"


def test_reviews(client, new_user):
    seeded = client.get("/api/books/joy-of-minimalism/reviews").json()
    assert seeded[-1]["author"] == "John Smith"

    assert client.get("/api/books/nope/reviews").status_code == 404
    assert client.post("/api/books/art-of-focus/reviews", json={"rating": 6, "text": "too high"}).status_code == 422
    assert client.post("/api/books/art-of-focus/reviews", json={"rating": 5, "text": "abc"}).status_code == 422

    guest = client.post("/api/books/art-of-focus/reviews", json={"rating": 4, "text": "  Nice read  "})
    assert guest.status_code == 201 and guest.json()["author"] == "Guest reader" and guest.json()["text"] == "Nice read"

    named = client.post(
        "/api/books/art-of-focus/reviews", json={"rating": 5, "text": "Loved it"}, headers=new_user["headers"]
    )
    assert named.json()["author"] == "Test User"
    assert client.get("/api/books/art-of-focus/reviews").json()[0]["id"] == named.json()["id"]  # newest first

    bad = client.post("/api/books/art-of-focus/reviews", json={"rating": 5, "text": "Loved it"}, headers={"Authorization": "Bearer junk"})
    assert bad.status_code == 401
