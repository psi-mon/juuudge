import os
import hashlib
import hmac
import getpass
import platform
from typing import Optional

def _get_machine_seed() -> bytes:
    """Generate a reproducible machine/user seed for key derivation."""
    user = getpass.getuser()
    node = platform.node()
    return f"{user}@{node}:juuudge:secret:salt".encode("utf-8")

def _derive_keystream(key: bytes, length: int) -> bytes:
    """Derive a keystream of specified length using HMAC-SHA256 in counter mode."""
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        block = hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(keystream[:length])

def is_valid_secret_text(text: str) -> bool:
    """Check if text contains valid printable characters without dangerous control bytes."""
    if not text:
        return False
    for ch in text:
        code = ord(ch)
        if code < 32 and ch not in ("\t", "\n", "\r"):
            return False
        if code == 127:  # DEL
            return False
    return True

def mask_secret(secret: str) -> str:
    """Format a secret into a safe masked fingerprint for display."""
    if not secret or not secret.strip():
        return "<not set>"
    secret = secret.strip()
    
    if secret.startswith("sk-ant-"):
        if len(secret) > 10:
            return f"sk-ant-…{secret[-4:]}"
        return "sk-ant-…"
    
    if len(secret) <= 8:
        return f"…{secret[-2:]}" if len(secret) >= 2 else "…"
    
    return f"{secret[:3]}…{secret[-4:]}"

def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string using a machine-derived key so it's not stored in plaintext."""
    if not plaintext:
        return ""
    
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", _get_machine_seed(), salt, 50_000, dklen=32)
    plain_bytes = plaintext.encode("utf-8")
    keystream = _derive_keystream(key, len(plain_bytes))
    
    ciphertext = bytes(b ^ k for b, k in zip(plain_bytes, keystream))
    return f"enc_v1:{salt.hex()}:{ciphertext.hex()}"

def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret string encrypted with encrypt_secret.
    
    Returns decrypted plaintext if valid, or "" if decryption fails, is corrupted, or produces non-printable/control bytes.
    If the string is plaintext (not enc_v1:), returns it if it is valid printable text, otherwise "".
    """
    if not ciphertext:
        return ""
    if not ciphertext.startswith("enc_v1:"):
        return ciphertext if is_valid_secret_text(ciphertext) else ""
    
    parts = ciphertext.split(":")
    if len(parts) != 3:
        return ""
    
    try:
        salt = bytes.fromhex(parts[1])
        cipher_bytes = bytes.fromhex(parts[2])
        key = hashlib.pbkdf2_hmac("sha256", _get_machine_seed(), salt, 50_000, dklen=32)
        keystream = _derive_keystream(key, len(cipher_bytes))
        plain_bytes = bytes(b ^ k for b, k in zip(cipher_bytes, keystream))
        decoded = plain_bytes.decode("utf-8")
        if not is_valid_secret_text(decoded):
            return ""
        return decoded
    except Exception:
        return ""
