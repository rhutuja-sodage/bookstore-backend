from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.db


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncDatabase = Depends(get_db),
) -> dict[str, Any] | None:
    """No Authorization header -> None. A bad / expired token is still rejected."""
    if credentials is None:
        return None
    email = decode_access_token(credentials.credentials)
    user = await db.users.find_one({"_id": email}) if email else None
    if user is None:
        raise _unauthorized("Invalid or expired token.")
    return user


async def get_current_user(user: dict[str, Any] | None = Depends(get_optional_user)) -> dict[str, Any]:
    if user is None:
        raise _unauthorized("Not authenticated.")
    return user
