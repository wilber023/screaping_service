from __future__ import annotations
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from scraping.auth.api_key import verify_api_key
from scraping.config import settings
from scraping.schemas.auth import TokenPayload, UserType


def create_access_token(user_id: str, user_type: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    payload = {
        "user_id": user_id,
        "user_type": user_type,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> TokenPayload:
    try:
        raw = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Token could not be validated"},
        )

    user_id = raw.get("user_id")
    user_type = raw.get("user_type")
    exp = raw.get("exp")

    if not user_id or not user_type or exp is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Token is missing required fields"},
        )

    try:
        validated_type = UserType(user_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": f"Unknown user_type: {user_type}"},
        )

    return TokenPayload(user_id=user_id, user_type=validated_type, exp=exp)


async def get_current_user(
    authorization: str = Header(...),
    _api_key_client: str = Depends(verify_api_key),
) -> TokenPayload:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_token", "message": "Authorization header must be 'Bearer <token>'"},
        )
    token = authorization.split(" ", 1)[1]
    return _decode_token(token)


async def require_admin(
    current_user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    if current_user.user_type != UserType.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "insufficient_permissions", "message": "Admin role required"},
        )
    return current_user


async def require_full_access(
    current_user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """Allows both agricultor_experimentado and admin; restricts aprendiz."""
    if current_user.user_type == UserType.aprendiz:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "insufficient_permissions", "message": "This endpoint requires agricultor_experimentado or admin role"},
        )
    return current_user
