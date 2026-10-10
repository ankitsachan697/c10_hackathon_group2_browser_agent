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


def test_local_vault_creates_private_persistent_key_without_environment_setup(tmp_path):
    database_path = tmp_path / "journeys.db"
    first = CredentialVault.for_database(database_path)
    ciphertext = first.encrypt("account", "private-password")

    key_path = tmp_path / "journeys.credentials.key"
    assert key_path.exists()
    assert key_path.stat().st_mode & 0o077 == 0
    assert CredentialVault.for_database(database_path).decrypt(ciphertext) == ("account", "private-password")


def test_local_vault_refuses_to_replace_missing_key_for_existing_credentials(tmp_path):
    from backend.database import Database
    from backend.repositories import JourneyRepository, ProjectRepository

    database_path = tmp_path / "journeys.db"
    database = Database(database_path)
    database.initialize()
    project = ProjectRepository(database).create({"name": "Example"})
    journey = JourneyRepository(database).create({"project_id": project["id"], "name": "Login", "target_url": "https://example.test"})
    JourneyRepository(database).set_credentials(journey["id"], CredentialVault(VALID_KEY).encrypt("account", "private-password"))

    with pytest.raises(CredentialVaultError, match="existing credentials"):
        CredentialVault.for_database(database_path)


def test_explicit_key_remains_compatible_with_existing_ciphertext(tmp_path):
    database_path = tmp_path / "journeys.db"
    ciphertext = CredentialVault(VALID_KEY).encrypt("account", "private-password")

    assert CredentialVault.for_database(database_path, VALID_KEY).decrypt(ciphertext) == ("account", "private-password")
    key_path = tmp_path / "journeys.credentials.key"
    assert key_path.exists()
    assert key_path.stat().st_mode & 0o077 == 0
    assert CredentialVault.for_database(database_path).decrypt(ciphertext) == ("account", "private-password")


def test_explicit_key_cannot_silently_replace_a_different_stored_key(tmp_path):
    database_path = tmp_path / "journeys.db"
    CredentialVault.for_database(database_path)

    with pytest.raises(CredentialVaultError, match="differs"):
        CredentialVault.for_database(database_path, VALID_KEY)
