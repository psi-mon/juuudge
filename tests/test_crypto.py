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

def test_decrypt_corrupted_or_invalid_utf8_returns_empty():
    # Corrupted hex payload that decrypts to invalid UTF-8 / non-printable garbage
    corrupted_blob = "enc_v1:00112233445566778899aabbccddeeff:0102030405060708"
    assert decrypt_secret(corrupted_blob) == ""
    assert decrypt_secret("enc_v1:invalid_hex:bad") == ""
    assert decrypt_secret("enc_v1:only_two_parts") == ""

def test_mask_secret():
    from juuudge.crypto import mask_secret

    assert mask_secret("") == "<not set>"
    assert mask_secret("   ") == "<not set>"
    assert mask_secret("sk-ant-test-super-secret-key-999") == "sk-ant-…-999"
    assert mask_secret("custom-secret-value-1234") == "cus…1234"
    assert mask_secret("abc") == "…bc"
