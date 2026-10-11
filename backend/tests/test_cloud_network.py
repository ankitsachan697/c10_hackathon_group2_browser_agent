import socket

import pytest

from backend.sandbox_transport import validate_public_target, execution_network_policy, SandboxTransport


def test_fixed_https_resolver_handles_controller_dns_allowlist(monkeypatch):
    from backend.sandbox_transport import resolve_public_dns
    import json
    from urllib.parse import parse_qs, urlsplit
    def direct_dns(*args, **kwargs):
        raise socket.gaierror("Target DNS is denied on the trusted controller")
    monkeypatch.setattr(socket, "getaddrinfo", direct_dns)
    requests = []
    class Response:
        def __init__(self, url): self.url = url
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            assert limit == 65537
            record_type = int(parse_qs(urlsplit(self.url).query)["type"][0])
            return json.dumps({"Status": 0, "TC": False, "Question": [{"name": "example.com.", "type": record_type}], "Answer": [{"type": 1, "data": "93.184.216.34"}]}).encode()
    def open_request(url, timeout):
        requests.append(url)
        assert timeout == 5
        return Response(url)
    monkeypatch.setattr("backend.sandbox_transport.dns_urlopen", open_request)
    resolver = lambda host: resolve_public_dns(host, "https://dns.google/resolve")
    policy = execution_network_policy("https://example.com/login", resolver=resolver)
    assert "example.com" in policy["allow"]
    assert len(requests) == 2
    assert all(urlsplit(url).hostname == "dns.google" for url in requests)
    assert all(parse_qs(urlsplit(url).query)["name"] == ["example.com"] for url in requests)


@pytest.mark.parametrize("answer", [[], ["10.0.0.1"], ["169.254.169.254"], ["::1"], ["224.0.0.1"], ["192.88.99.2"], ["203.0.113.1"], ["93.184.216.34", "192.168.1.1"]])
def test_remote_resolver_still_rejects_missing_or_private_addresses(answer):
    with pytest.raises(ValueError, match="public"):
        execution_network_policy("https://example.com/", resolver=lambda host: answer)


@pytest.mark.parametrize("body", [b'x'*65537, b'{"Status":2}', b'{"Status":0,"TC":true}', b'{"Status":0,"Question":[{"name":"other.example.","type":1}]}'])
def test_dns_response_is_bounded_and_verified(monkeypatch, body):
    from backend.sandbox_transport import resolve_public_dns
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return body
    monkeypatch.setattr("backend.sandbox_transport.dns_urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError): resolve_public_dns("example.com", "https://dns.google/resolve")


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
