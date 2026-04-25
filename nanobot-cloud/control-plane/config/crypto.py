import base64
import json

from cryptography.fernet import Fernet

from settings import settings

# Pad/trim key to valid Fernet format at import time
_raw = settings.encryption_key.encode()
_key = base64.urlsafe_b64encode(_raw[:32].ljust(32, b"="))
_fernet = Fernet(_key)


def encrypt_env(env: dict) -> str:
    return _fernet.encrypt(json.dumps(env).encode()).decode()


def decrypt_env(token: str) -> dict:
    return json.loads(_fernet.decrypt(token.encode()))
