from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase


async def ensure_indexes(db: AsyncDatabase) -> None:
    await db.orders.create_index("number", unique=True)
    await db.orders.create_index([("userEmail", ASCENDING), ("placedAt", DESCENDING)])
    await db.reviews.create_index([("bookId", ASCENDING), ("date", DESCENDING)])
    await db.books.create_index("author")
    await db.books.create_index("category")


def to_doc(model: Any, id_field: str = "id") -> dict[str, Any]:
    """Pydantic model -> Mongo document (camelCase keys, id stored as _id)."""
    doc = model.model_dump(by_alias=True)
    doc["_id"] = doc.pop(id_field)
    return doc


def from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Mongo document -> dict a pydantic model can validate (_id exposed as id)."""
    out = dict(doc)
    out["id"] = out.pop("_id")
    return out
