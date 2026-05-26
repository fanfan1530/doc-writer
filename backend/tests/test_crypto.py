"""API Key 加密模块测试。"""
import pytest
from app.core.crypto import encrypt_api_key, decrypt_api_key


class TestCrypto:
    def test_round_trip(self):
        key = "sk-abc123def456ghi789"
        enc = encrypt_api_key(key)
        assert enc != key
        assert encrypt_api_key(enc) == enc  # idempotent
        assert decrypt_api_key(enc) == key

    def test_empty_key(self):
        assert encrypt_api_key("") == ""
        assert decrypt_api_key("") == ""

    def test_plaintext_passthrough(self):
        assert decrypt_api_key("plain-text-key") == "plain-text-key"

    def test_different_keys_produce_different_ciphertext(self):
        e1 = encrypt_api_key("key-a")
        e2 = encrypt_api_key("key-b")
        assert e1 != e2

    def test_long_key(self):
        key = "sk-" + "x" * 500
        enc = encrypt_api_key(key)
        assert decrypt_api_key(enc) == key
