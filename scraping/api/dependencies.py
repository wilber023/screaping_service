from __future__ import annotations
from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from scraping.auth.jwt_auth import get_current_user, require_admin, require_full_access
from scraping.schemas.auth import TokenPayload
from scraping.storage.database import get_db

# Re-export for route convenience
__all__ = ["get_db", "get_current_user", "require_admin", "require_full_access"]
