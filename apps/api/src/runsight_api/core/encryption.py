import base64
import hashlib
import platform
import uuid

from cryptography.fernet import Fernet


def _derive_key() -> bytes:
    raw = f"{platform.node()}-{uuid.getnode()}".encode()
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_key())


def encrypt(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
