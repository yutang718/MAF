"""Encryption of connector credentials at rest."""
import json

from cryptography.fernet import Fernet, InvalidToken

from govern.config import get_settings


class MasterKeyError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().MASTER_KEY
    if not key:
        raise MasterKeyError("GOVERN_MASTER_KEY is not set; connector credentials cannot be stored or read")
    try:
        return Fernet(key.encode())
    except ValueError as e:
        raise MasterKeyError("GOVERN_MASTER_KEY is not a valid Fernet key") from e


def encrypt_secrets(secrets: dict[str, str]) -> str:
    if not secrets:
        return ""
    return _fernet().encrypt(json.dumps(secrets).encode()).decode()


def decrypt_secrets(token: str) -> dict[str, str]:
    if not token:
        return {}
    try:
        return json.loads(_fernet().decrypt(token.encode()))
    except InvalidToken as e:
        raise MasterKeyError("connector credentials can't be decrypted; GOVERN_MASTER_KEY changed?") from e
