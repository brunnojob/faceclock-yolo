import os

import numpy as np

os.environ.setdefault("FACECLOCK_API_KEY", "test-api-key")
os.environ.setdefault("FACECLOCK_MASTER_KEY", "test-master-key")

from app.security import decrypt_embedding, encrypt_embedding, event_digest


def test_embedding_round_trip() -> None:
    source = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    ciphertext, nonce = encrypt_embedding(source, "employee-1")
    restored = decrypt_embedding(ciphertext, nonce, "employee-1")
    assert np.allclose(source, restored)
    assert ciphertext != source.tobytes()


def test_event_digest_is_deterministic() -> None:
    assert event_digest("event") == event_digest("event")
    assert event_digest("event") != event_digest("other")

