import base64

import pytest

from backend.credential_vault import CredentialVault, CredentialVaultError


VALID_KEY = base64.urlsafe_b64encode(b"k" * 32).decode()


def test_credentials_round_trip_without_plaintext():
    vault = CredentialVault(VALID_KEY)

    ciphertext = vault.encrypt("student", "Password123")

    assert vault.decrypt(ciphertext) == ("student", "Password123")
    assert "student" not in ciphertext
    assert "Password123" not in ciphertext


def test_encrypting_same_credentials_produces_randomized_ciphertext():
    vault = CredentialVault(VALID_KEY)

    assert vault.encrypt("student", "Password123") != vault.encrypt("student", "Password123")


@pytest.mark.parametrize("key", [None, "", "not-a-fernet-key"])
def test_missing_or_invalid_key_fails_safely(key):
    with pytest.raises(CredentialVaultError):
        CredentialVault(key)


def test_tampered_ciphertext_fails_without_returning_partial_values():
    vault = CredentialVault(VALID_KEY)
    ciphertext = vault.encrypt("student", "Password123")

    with pytest.raises(CredentialVaultError, match="decrypt"):
        vault.decrypt(ciphertext[:-2] + "xx")
