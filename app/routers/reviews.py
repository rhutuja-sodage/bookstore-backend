import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.database import from_doc
from app.deps import get_db, get_optional_user
from app.schemas import Review, ReviewIn

router = APIRouter(prefix="/api/books/{book_id}/reviews", tags=["reviews"])


async def _require_book(db: AsyncDatabase, book_id: str) -> None:
    if await db.books.count_documents({"_id": book_id}, limit=1) == 0:
        raise HTTPException(404, "Book not found.")


@router.get("", response_model=list[Review])
async def list_reviews(book_id: str, db: Annotated[AsyncDatabase, Depends(get_db)]) -> list[dict[str, Any]]:
    await _require_book(db, book_id)
    docs = await db.reviews.find({"bookId": book_id}).sort("date", -1).to_list()
    return [from_doc(d) for d in docs]


@router.post("", response_model=Review, status_code=201)
async def add_review(
    book_id: str,
    body: ReviewIn,
    db: Annotated[AsyncDatabase, Depends(get_db)],
    user: Annotated[dict[str, Any] | None, Depends(get_optional_user)],
) -> dict[str, Any]:
    """Guests may review too; they are shown as "Guest reader"."""
    await _require_book(db, book_id)
    doc = {
        "_id": f"rev_{uuid.uuid4().hex[:16]}",
        "bookId": book_id,
        "author": user["name"] if user else "Guest reader",
        "rating": body.rating,
        "text": body.text,
        "date": datetime.now(UTC),
    }
    await db.reviews.insert_one(doc)
    return from_doc(doc)
