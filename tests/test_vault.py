"""Tests for Memory Vault encryption (v0.9.5)."""

from __future__ import annotations

import os

import pytest

from src.vault import (
    decrypt,
    decrypt_dict,
    encrypt,
    encrypt_dict,
    init_vault,
    is_vault_enabled,
    vault_status,
)


@pytest.fixture(autouse=True)
def _reset_vault():
    """Reset vault state before each test."""
    import src.vault
    src.vault._vault_key = None
    yield
    src.vault._vault_key = None
    os.environ.pop("TESSERA_VAULT_KEY", None)


class TestVaultInit:
    def test_disabled_by_default(self):
        assert not is_vault_enabled()
        assert not init_vault()

    def test_enabled_with_key(self):
        os.environ["TESSERA_VAULT_KEY"] = "my-secret-passphrase"
        assert init_vault()
        assert is_vault_enabled()

    def test_disabled_with_empty_key(self):
        os.environ["TESSERA_VAULT_KEY"] = ""
        assert not init_vault()


class TestEncryptDecrypt:
    def _enable_vault(self):
        os.environ["TESSERA_VAULT_KEY"] = "test-key-12345"
        init_vault()

    def test_roundtrip(self):
        self._enable_vault()
        original = "Use PostgreSQL for production"
        encrypted = encrypt(original)
        assert encrypted != original
        assert encrypted.startswith("vault:")
        decrypted = decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_korean(self):
        self._enable_vault()
        original = "한국어 텍스트 암호화 테스트"
        encrypted = encrypt(original)
        decrypted = decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_long_text(self):
        self._enable_vault()
        original = "x" * 1000
        encrypted = encrypt(original)
        decrypted = decrypt(encrypted)
        assert decrypted == original

    def test_roundtrip_empty(self):
        self._enable_vault()
        encrypted = encrypt("")
        decrypted = decrypt(encrypted)
        assert decrypted == ""

    def test_different_keys_different_output(self):
        os.environ["TESSERA_VAULT_KEY"] = "key-a"
        init_vault()
        enc_a = encrypt("hello")

        import src.vault
        src.vault._vault_key = None
        os.environ["TESSERA_VAULT_KEY"] = "key-b"
        init_vault()
        enc_b = encrypt("hello")

        # Different keys produce different ciphertext
        assert enc_a != enc_b

    def test_passthrough_when_disabled(self):
        text = "plaintext data"
        assert encrypt(text) == text
        assert decrypt(text) == text

    def test_decrypt_non_vault_string(self):
        self._enable_vault()
        assert decrypt("plain text") == "plain text"

    def test_decrypt_without_key_returns_ciphertext(self):
        # Encrypt with key
        self._enable_vault()
        encrypted = encrypt("secret")

        # Remove key
        import src.vault
        src.vault._vault_key = None

        # Should return encrypted string since can't decrypt
        assert decrypt(encrypted) == encrypted


class TestEncryptDecryptDict:
    def _enable_vault(self):
        os.environ["TESSERA_VAULT_KEY"] = "dict-test-key"
        init_vault()

    def test_encrypt_dict(self):
        self._enable_vault()
        d = {"content": "secret data", "category": "fact"}
        result = encrypt_dict(d)
        assert result["content"].startswith("vault:")
        assert result["category"] == "fact"  # Not encrypted

    def test_decrypt_dict(self):
        self._enable_vault()
        d = {"content": "secret data", "category": "fact"}
        encrypted = encrypt_dict(d)
        decrypted = decrypt_dict(encrypted)
        assert decrypted["content"] == "secret data"
        assert decrypted["category"] == "fact"

    def test_custom_fields(self):
        self._enable_vault()
        d = {"content": "a", "notes": "b", "tags": ["x"]}
        result = encrypt_dict(d, fields=["content", "notes"])
        assert result["content"].startswith("vault:")
        assert result["notes"].startswith("vault:")
        assert result["tags"] == ["x"]

    def test_passthrough_when_disabled(self):
        d = {"content": "plain"}
        assert encrypt_dict(d) == d


class TestVaultStatus:
    def test_disabled(self):
        status = vault_status()
        assert not status["enabled"]
        assert status["algorithm"] is None

    def test_enabled(self):
        os.environ["TESSERA_VAULT_KEY"] = "status-test"
        init_vault()
        status = vault_status()
        assert status["enabled"]
        assert status["algorithm"] == "AES-256-CBC"
        assert status["key_source"] == "TESSERA_VAULT_KEY"


class TestEdgeCases:
    def _enable_vault(self):
        os.environ["TESSERA_VAULT_KEY"] = "edge-case-key"
        init_vault()

    def test_special_characters(self):
        self._enable_vault()
        original = "Hello! @#$%^&*() 🎉 \n\ttabs"
        assert decrypt(encrypt(original)) == original

    def test_unicode_emoji(self):
        self._enable_vault()
        original = "🔐🗝️🔑"
        assert decrypt(encrypt(original)) == original

    def test_exactly_16_bytes(self):
        self._enable_vault()
        original = "a" * 16
        assert decrypt(encrypt(original)) == original

    def test_exactly_32_bytes(self):
        self._enable_vault()
        original = "b" * 32
        assert decrypt(encrypt(original)) == original
