from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from app.deps import get_current_user, get_db
from app.schemas import Address, LoginIn, RegisterIn, TokenOut, User
from app.security import create_access_token, hash_password_async, verify_password_async

router = APIRouter(prefix="/api", tags=["auth"])


def to_user(doc: dict[str, Any]) -> User:
    return User(name=doc["name"], email=doc["_id"], gift_points=doc["giftPoints"], address=doc.get("address"))


def _token(doc: dict[str, Any]) -> TokenOut:
    return TokenOut(access_token=create_access_token(doc["_id"]), user=to_user(doc))


@router.post("/auth/register", response_model=TokenOut, status_code=201)
async def register(body: RegisterIn, db: Annotated[AsyncDatabase, Depends(get_db)]) -> TokenOut:
    doc = {
        "_id": body.email.lower(),
        "name": body.name,
        "passwordHash": await hash_password_async(body.password),
        "giftPoints": 0,
        "address": None,
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "An account with this email already exists.") from None
    return _token(doc)


@router.post("/auth/login", response_model=TokenOut)
async def login(body: LoginIn, db: Annotated[AsyncDatabase, Depends(get_db)]) -> TokenOut:
    doc = await db.users.find_one({"_id": body.email.lower()})
    if doc is None or not await verify_password_async(body.password, doc["passwordHash"]):
        raise HTTPException(401, "Incorrect email or password.")
    return _token(doc)


@router.get("/users/me", response_model=User)
async def me(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> User:
    return to_user(user)


@router.put("/users/me/address", response_model=User)
async def save_address(
    address: Address,
    user: Annotated[dict[str, Any], Depends(get_current_user)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> User:
    doc = {**user, "address": address.model_dump(by_alias=True)}
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"address": doc["address"]}})
    return to_user(doc)
