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

def test_master_key_file_creation_and_permissions(tmp_path, monkeypatch):
    import stat
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    secret = "sk-ant-test-key-file"
    encrypted = encrypt_secret(secret)
    assert encrypted.startswith("enc_v1:")

    key_file = tmp_path / "master.key"
    assert key_file.exists()
    assert len(key_file.read_bytes()) == 32
    # Check permissions 0600 (owner read/write only)
    mode = stat.S_IMODE(key_file.stat().st_mode)
    assert mode == 0o600

def test_encryption_survives_platform_node_change(tmp_path, monkeypatch):
    import platform
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.setattr(platform, "node", lambda: "original-machine-host.local")

    secret = "sk-ant-test-key-survives-node-change"
    encrypted = encrypt_secret(secret)

    # Change hostname (simulating DHCP, VPN, macOS Bonjour change across restarts)
    monkeypatch.setattr(platform, "node", lambda: "different-machine-host-after-reboot.local")

    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret
