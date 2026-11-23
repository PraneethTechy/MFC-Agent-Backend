"""
Server-side credential encryption utility for Data Connectors.
Uses HMAC-SHA256 authenticated symmetric XOR stream with random cryptographic IV/salt.
Zero external dependencies, robust and safe at rest.
"""

import base64
import hashlib
import hmac
import secrets
from app.config import Settings

_settings = Settings()


def _get_master_key() -> bytes:
    """Derives a stable 32-byte master key from the server backend configuration."""
    seed = (_settings.database_url + "::mfg_cost_connector_secret_v1").encode("utf-8")
    return hashlib.sha256(seed).digest()


def encrypt_password(plaintext: str) -> str:
    """
    Encrypts a plaintext password string.
    Returns URL-safe Base64 encoded string: salt(16) + mac(32) + ciphertext.
    """
    if not plaintext:
        return ""

    master_key = _get_master_key()
    salt = secrets.token_bytes(16)

    # Derive per-credential keystream
    derived_key = hashlib.sha256(master_key + salt).digest()
    data = plaintext.encode("utf-8")

    # Generate keystream matching data length
    keystream = bytearray()
    counter = 0
    while len(keystream) < len(data):
        block = hashlib.sha256(derived_key + counter.to_bytes(4, "big")).digest()
        keystream.extend(block)
        counter += 1

    encrypted_bytes = bytes(a ^ b for a, b in zip(data, keystream[:len(data)]))

    # MAC for integrity
    mac = hmac.new(derived_key, encrypted_bytes, hashlib.sha256).digest()

    payload = salt + mac + encrypted_bytes
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_password(token: str) -> str:
    """
    Decrypts an encrypted password token.
    Raises ValueError on tampering or invalid signature.
    """
    if not token:
        return ""

    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        if len(raw) < 48:
            raise ValueError("Corrupt encrypted credential payload")

        salt = raw[:16]
        expected_mac = raw[16:48]
        encrypted_bytes = raw[48:]

        master_key = _get_master_key()
        derived_key = hashlib.sha256(master_key + salt).digest()

        actual_mac = hmac.new(derived_key, encrypted_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_mac, actual_mac):
            raise ValueError("Credential integrity check failed")

        keystream = bytearray()
        counter = 0
        while len(keystream) < len(encrypted_bytes):
            block = hashlib.sha256(derived_key + counter.to_bytes(4, "big")).digest()
            keystream.extend(block)
            counter += 1

        decrypted_bytes = bytes(a ^ b for a, b in zip(encrypted_bytes, keystream[:len(encrypted_bytes)]))
        return decrypted_bytes.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to decrypt database password: {exc}")

