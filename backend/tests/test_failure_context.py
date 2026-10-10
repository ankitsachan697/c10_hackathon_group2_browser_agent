from backend.failure_context import FailureLimits, build_failure_packet, classify_failure


def test_failure_packet_is_bounded_redacted_and_reference_only():
    result = {
        "stderr": "prefix password='super-secret' " + "trace " * 100,
        "dom_snapshot": "<html>super-secret" + "x" * 500 + "</html>",
        "failed_action": "click Submit",
        "locator_evidence": ["button#old", "button:has-text('Submit')"],
        "screenshots": ["failure.png"],
        "video": "session.webm",
    }

    packet = build_failure_packet(result, FailureLimits(traceback_chars=80, dom_chars=100), ["super-secret"])

    assert len(packet.traceback) <= 80
    assert len(packet.dom_excerpt) <= 100
    assert "super-secret" not in packet.traceback + packet.dom_excerpt
    assert packet.artifact_references == ("failure.png",)
    assert "session.webm" not in packet.artifact_references


def test_failure_packet_redacts_payment_details_without_registered_secret():
    result = {
        "stderr": "card 4111 1111 1111 1111 cvv=123",
        "dom_snapshot": "<input value='4111-1111-1111-1111'>",
        "script_snapshot": "print('4111111111111111')",
    }
    packet = build_failure_packet(result)
    rendered = str(packet)
    assert "4111" not in rendered
    assert "123" not in rendered


def test_selector_and_timeout_failures_are_eligible():
    assert classify_failure({"stderr": "Timeout waiting for locator('#submit')"}).eligible is True
    assert classify_failure({"stderr": "strict mode violation: element not found"}).eligible is True


def test_auth_infrastructure_and_assertion_failures_are_not_eligible():
    for message, category in (
        ("401 Unauthorized invalid credentials", "AUTHENTICATION"),
        ("browser executable doesn't exist", "INFRASTRUCTURE"),
        ("AssertionError expected heading", "ASSERTION"),
    ):
        decision = classify_failure({"stderr": message})
        assert decision.eligible is False
        assert decision.category == category
