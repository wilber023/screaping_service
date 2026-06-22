from __future__ import annotations
from pydantic import BaseModel
from enum import Enum


class UserType(str, Enum):
    aprendiz = "aprendiz"
    agricultor_experimentado = "agricultor_experimentado"
    admin = "admin"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_type: UserType


class TokenPayload(BaseModel):
    user_id: str
    user_type: UserType
    exp: int
