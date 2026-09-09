import pytest
from juuudge.crypto import encrypt_secret, decrypt_secret

def test_encrypt_decrypt_roundtrip():
    secret = "sk-ant-api03-abcdef1234567890-test-key"
    encrypted = encrypt_secret(secret)
    
    # Must not be plaintext
    assert encrypted != secret
    assert secret not in encrypted
    assert encrypted.startswith("enc_v1:")

    # Decrypt must match original
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret

def test_encrypt_empty_or_plain():
    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""
    # Decrypting plaintext not matching prefix returns plaintext safely
    assert decrypt_secret("plain_key") == "plain_key"
