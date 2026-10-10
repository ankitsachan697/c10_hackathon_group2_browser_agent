from backend.redaction import SensitiveDataRedactor


def test_known_credentials_and_payment_values_are_redacted_from_text():
    redactor = SensitiveDataRedactor(["private-password"])
    text = 'password="private-password" card=4111 1111 1111 1111 cvv=123 order=1234567890123456'

    output = redactor.redact(text)

    assert "private-password" not in output
    assert "4111 1111 1111 1111" not in output
    assert "cvv=123" not in output
    assert "order=1234567890123456" in output


def test_unlabelled_known_secret_is_redacted_everywhere():
    redactor = SensitiveDataRedactor(["private-password"])

    assert "private-password" not in redactor.redact("value: private-password")
