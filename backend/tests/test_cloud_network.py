import socket

import pytest

from backend.sandbox_transport import validate_public_target, execution_network_policy, SandboxTransport


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://10.0.0.5/", "file:///etc/passwd", "https://user:pass@example.com/", "https://example.com:8000/"])
def test_private_ip_dns_redirect_and_metadata_are_blocked(url):
    with pytest.raises(ValueError):
        validate_public_target(url, {"https://example.com"})


def test_dns_rebinding_private_answer_is_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("10.1.0.1", 443))])
    with pytest.raises(ValueError, match="public"):
        validate_public_target("https://example.com/", {"https://example.com"})


def test_redirect_to_unapproved_origin_is_rejected():
    with pytest.raises(ValueError, match="approved"):
        validate_public_target("https://other.example/", {"https://example.com"})


def test_controller_origin_only_exposes_demo_get_paths():
    policy = execution_network_policy("https://controller.example/api/demo-shop/demo_fixture", "https://controller.example")
    rules = policy["allow"]["controller.example"]
    assert rules[0]["match"]["method"] == ["GET", "HEAD"]
    assert "demo-shop" in rules[0]["match"]["path"]["regex"]
    assert rules[-1]["response"]["statusCode"] == 403
    assert "127.0.0.0/8" in policy["subnets"]["deny"]
    with pytest.raises(ValueError):
        execution_network_policy("https://controller.example/api/projects", "https://controller.example")


def test_controller_policy_constructs_real_sdk_rules_and_pins_host():
    policy = SandboxTransport._network(execution_network_policy("https://controller.example/api/demo-shop/demo_fixture", "https://controller.example"))
    rule = policy.allow["controller.example"][0]
    assert rule.transform[0].headers["Host"] == "controller.example"


def test_cloud_rejects_plain_http_before_worker_creation():
    with pytest.raises(ValueError, match="HTTPS"):
        execution_network_policy("http://example.com/")
