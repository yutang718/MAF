from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings
from .logging import get_logger

logger = get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def sanitize_input(text: str) -> str:
    """
    Basic input sanitization to prevent XSS and other injection attacks.
    """
    # Remove potentially dangerous characters
    sanitized = text.replace("<", "&lt;").replace(">", "&gt;")
    sanitized = sanitized.replace("'", "&#x27;").replace('"', "&quot;")
    return sanitized 