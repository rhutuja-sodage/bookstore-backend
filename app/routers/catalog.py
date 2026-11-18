import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.asynchronous.database import AsyncDatabase

from app.database import from_doc
from app.deps import get_db
from app.schemas import Book, Coupon, Writer

router = APIRouter(prefix="/api", tags=["catalog"])

SORTS: dict[str, list[tuple[str, int]]] = {
    "popularity": [("sold", -1)],
    "price_asc": [("price", 1)],
    "price_desc": [("price", -1)],
    "newest": [("published", -1)],
    "rating": [("rating", -1)],
}


@router.get("/books", response_model=list[Book])
async def list_books(
    db: Annotated[AsyncDatabase, Depends(get_db)],
    q: Annotated[str | None, Query(description="Matches title, author, publisher, category and genres")] = None,
    category: str | None = None,
    language: str | None = None,
    format: str | None = None,
    publisher: str | None = None,
    author: str | None = None,
    min_price: Annotated[float | None, Query(ge=0)] = None,
    max_price: Annotated[float | None, Query(ge=0)] = None,
    sort: Literal["relevance", "popularity", "price_asc", "price_desc", "newest", "rating"] = "relevance",
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    query: dict[str, Any] = {}
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{f: rx} for f in ("title", "author", "publisher", "category", "genres")]
    for field, value in (("category", category), ("language", language), ("format", format), ("publisher", publisher), ("author", author)):
        if value:
            query[field] = value
    if min_price is not None or max_price is not None:
        query["price"] = {
            **({"$gte": min_price} if min_price is not None else {}),
            **({"$lte": max_price} if max_price is not None else {}),
        }
    cursor = db.books.find(query)
    if sort in SORTS:
        cursor = cursor.sort(SORTS[sort])
    docs = await cursor.skip(skip).limit(limit).to_list()
    return [from_doc(d) for d in docs]


@router.get("/books/{book_id}", response_model=Book)
async def get_book(book_id: str, db: Annotated[AsyncDatabase, Depends(get_db)]) -> dict[str, Any]:
    doc = await db.books.find_one({"_id": book_id})
    if doc is None:
        raise HTTPException(404, "Book not found.")
    return from_doc(doc)


@router.get("/writers", response_model=list[Writer])
async def list_writers(db: Annotated[AsyncDatabase, Depends(get_db)]) -> list[dict[str, Any]]:
    return await db.writers.find({}, {"_id": 0}).to_list()  # seed order (same as the catalog)


@router.get("/writers/{slug}", response_model=Writer)
async def get_writer(slug: str, db: Annotated[AsyncDatabase, Depends(get_db)]) -> dict[str, Any]:
    doc = await db.writers.find_one({"_id": slug}, {"_id": 0})
    if doc is None:
        raise HTTPException(404, "Writer not found.")
    return doc


@router.get("/coupons", response_model=list[Coupon], response_model_exclude_none=True)
async def list_coupons(db: Annotated[AsyncDatabase, Depends(get_db)]) -> list[dict[str, Any]]:
    return await db.coupons.find({}, {"_id": 0}).to_list()
