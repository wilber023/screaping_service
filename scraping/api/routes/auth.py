from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from scraping.auth.api_key import verify_api_key
from scraping.auth.jwt_auth import create_access_token

router = APIRouter()


@router.post("/token", summary="Obtener JWT con API Key")
def get_token(
    user_type: str = Query(
        "agricultor_experimentado",
        enum=["aprendiz", "agricultor_experimentado", "admin"],
        description="Tipo de usuario",
    ),
    _: str = Depends(verify_api_key),
):
    token = create_access_token(user_id="frontend-user", user_type=user_type)
    return {"access_token": token, "token_type": "bearer", "user_type": user_type}