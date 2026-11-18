# Book Worm – backend

REST API for the Book Worm bookstore. **FastAPI** + **MongoDB** (async `pymongo`), JWT auth.

## Setup (Windows / PowerShell)

```powershell
cd backend
python -m venv .venv                # a .venv is already present in this repo
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env              # optional - the defaults work for local development
```

MongoDB must be reachable at `mongodb://localhost:27017` (change `BOOKWORM_MONGODB_URL` otherwise).
Local MongoDB or Docker both work, e.g. `docker run -d -p 27017:27017 mongo:8`.

## Run

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

* Interactive docs: <http://localhost:8000/docs>
* Health check: <http://localhost:8000/api/health>

On first start (empty database) the catalog is seeded from `app/seed_data/*.json`
together with the coupons, one sample review and the demo account
`demo@bookworm.com` / `Demo@123` (with an older order, address and 120 gift points).
Seeding is skipped for any collection that already has data. Set `BOOKWORM_SEED_ON_STARTUP=false` to disable it.

## Configuration (`BOOKWORM_*` environment variables or `.env`)

| Variable | Default |
| --- | --- |
| `BOOKWORM_MONGODB_URL` | `mongodb://localhost:27017` |
| `BOOKWORM_MONGODB_DB` | `bookworm` |
| `BOOKWORM_JWT_SECRET` | dev-only value – **set your own outside local development** |
| `BOOKWORM_JWT_EXPIRE_MINUTES` | `10080` (7 days) |
| `BOOKWORM_CORS_ORIGINS` | `["http://localhost:4200","http://localhost:4300"]` |
| `BOOKWORM_SEED_ON_STARTUP` | `true` |

## Endpoints

JSON is camelCase to match the Angular models. 🔒 = needs `Authorization: Bearer <token>`.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/auth/register` | Create account → `{accessToken, tokenType, user}` (409 if the e-mail exists) |
| POST | `/api/auth/login` | Log in → same payload (401 on bad credentials) |
| GET 🔒 | `/api/users/me` | Current user incl. gift points and saved address |
| PUT 🔒 | `/api/users/me/address` | Save the delivery address |
| GET | `/api/books` | List/search. Query: `q, category, language, format, publisher, author, min_price, max_price, sort (relevance｜popularity｜price_asc｜price_desc｜newest｜rating), skip, limit` |
| GET | `/api/books/{id}` | Book details |
| GET / POST | `/api/books/{id}/reviews` | List reviews / add a review (token optional – guests post as "Guest reader") |
| GET | `/api/writers`, `/api/writers/{slug}` | Writers |
| GET | `/api/coupons` | Available coupon codes |
| GET 🔒 | `/api/orders`, `/api/orders/{number}` | The caller's orders (newest first) |
| POST 🔒 | `/api/orders` | Place an order |
| POST 🔒 | `/api/orders/{number}/cancel` | Cancel within 48 h of placing |
| GET | `/api/health` | DB ping |

### Order rules (enforced server-side)

* The client sends only `{items:[{bookId, qty}], address, payment, couponCode?, usePoints?}`.
  Prices, discount, tax, coupon, gift points and delivery dates are **recomputed from the catalog** – client-sent totals are ignored.
* Quantity per book is capped at 10; duplicate lines are merged; the coupon must exist and meet its minimum order.
* Gift points: spent points are deducted atomically (never overspent); 5 % of the amount paid is earned, 7 % once earlier non-cancelled orders total ₹1,000.
* Cancelling is allowed once, within 48 hours, and reverses the points movement of that order.
* `payment.detail` is a masked reference (e.g. `•••• 4242`) – raw card data is never accepted or stored.
* Users only ever see their own orders (other users' order numbers return 404).

Cart and wishlist stay in the browser (`localStorage`) so guests can shop without an account.

## Tests

```powershell
.\.venv\Scripts\python -m pytest
```

Tests run against a throwaway database (`bookworm_test_<random>`) on the same MongoDB server and drop it afterwards.

## Layout

```
app/
  main.py        app factory, CORS, lifespan (client, indexes, seeding)
  config.py      settings          security.py  bcrypt + JWT
  schemas.py     pydantic models   pricing.py   port of the frontend pricing rules
  database.py    indexes, doc<->model helpers   deps.py  db / auth dependencies
  seed.py        initial data      seed_data/   books.json, writers.json
  routers/       auth, catalog (books/writers/coupons), reviews, orders
tests/
```
