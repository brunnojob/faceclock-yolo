import base64
import hashlib
import hmac
import os

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Header, HTTPException, status

from app.config import get_settings


def _key() -> bytes:
    raw = get_settings().master_key.encode()
    try:
        decoded = base64.urlsafe_b64decode(raw)
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    return hashlib.sha256(raw).digest()


def encrypt_embedding(embedding: np.ndarray, employee_id: str) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    value = embedding.astype(np.float32).tobytes()
    return AESGCM(_key()).encrypt(nonce, value, employee_id.encode()), nonce


def decrypt_embedding(ciphertext: bytes, nonce: bytes, employee_id: str) -> np.ndarray:
    value = AESGCM(_key()).decrypt(nonce, ciphertext, employee_id.encode())
    return np.frombuffer(value, dtype=np.float32)


def event_digest(payload: str) -> str:
    return hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()


def require_api_key(x_api_key: str = Header(default="")) -> None:
    expected = get_settings().api_key
    if not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

