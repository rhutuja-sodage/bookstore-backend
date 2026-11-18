def test_register_login_me(client):
    body = {"name": "Alice Smith", "email": "Alice.Smith@Example.com", "password": "secret1"}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["tokenType"] == "bearer" and data["user"]["email"] == "alice.smith@example.com"
    assert data["user"]["giftPoints"] == 0 and "password" not in str(data).lower().replace("tokentype", "")

    assert client.post("/api/auth/register", json=body).status_code == 409  # duplicate (case-insensitive)

    login = client.post("/api/auth/login", json={"email": "alice.smith@example.com", "password": "secret1"})
    assert login.status_code == 200
    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {login.json()['accessToken']}"})
    assert me.json()["name"] == "Alice Smith"


def test_login_failures_do_not_reveal_which_part_was_wrong(client):
    wrong_pw = client.post("/api/auth/login", json={"email": "demo@bookworm.com", "password": "nope"})
    no_user = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json() == {"detail": "Incorrect email or password."}


def test_register_validation(client):
    ok = {"name": "Bob Jones", "email": "bob@example.com", "password": "secret1"}
    assert client.post("/api/auth/register", json={**ok, "password": "12345"}).status_code == 422
    assert client.post("/api/auth/register", json={**ok, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/auth/register", json={**ok, "name": " "}).status_code == 422


def test_protected_routes_require_a_valid_token(client):
    assert client.get("/api/users/me").status_code == 401
    assert client.get("/api/orders").status_code == 401
    assert client.get("/api/users/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_demo_account_seeded(client, demo_headers):
    me = client.get("/api/users/me", headers=demo_headers).json()
    assert me["email"] == "demo@bookworm.com" and me["address"]["city"] == "Pune"
    orders = client.get("/api/orders", headers=demo_headers).json()
    assert any(o["lines"][0]["bookId"] == "art-of-focus" for o in orders)


def test_save_address(client, new_user):
    addr = {
        "firstName": "Test", "lastName": "User", "line1": "12 Main Street", "email": "t@example.com", "city": "Pune",
        "pin": "411001", "countryCode": "+91", "phone": "9876543210", "state": "Maharashtra", "country": "India",
    }
    r = client.put("/api/users/me/address", json=addr, headers=new_user["headers"])
    assert r.status_code == 200 and r.json()["address"]["pin"] == "411001"
    assert client.get("/api/users/me", headers=new_user["headers"]).json()["address"]["city"] == "Pune"

    for field, value in (("pin", "012345"), ("phone", "1234567890"), ("firstName", "R2D2"), ("line1", "abc"), ("email", "x")):
        r = client.put("/api/users/me/address", json={**addr, field: value}, headers=new_user["headers"])
        assert r.status_code == 422, field
