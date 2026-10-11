"""Trusted SDK transport. Generated code only ever enters a disposable microVM."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import socket
import urllib.request
from contextlib import asynccontextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit, urlencode

PUBLIC_DEMO = re.compile(r"^/api/demo-shop/[A-Za-z0-9_-]{1,100}(?:/(?:shop\.css|shop\.js))?$")
PRIVATE_SUBNETS = ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8", "169.254.0.0/16", "172.16.0.0/12", "192.0.0.0/24", "192.0.2.0/24", "192.88.99.0/24", "192.168.0.0/16", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24", "224.0.0.0/4", "240.0.0.0/4"]
INSTALL_HOSTS = ["pypi.org", "files.pythonhosted.org", "cdn.playwright.dev", "playwright.download.prss.microsoft.com", "cdn.playwright.azureedge.net", "storage.googleapis.com", "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com", "cli.github.com"]
WORK = "/vercel/sandbox/work"
MAX_FILE = 50 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024


def origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Cloud target must be a public HTTPS URL without credentials")
    port = parts.port
    if port and port != (443 if parts.scheme == "https" else 80):
        raise ValueError("Cloud targets must use standard public HTTP(S) ports")
    return f"{parts.scheme}://{parts.hostname.lower()}"


class _NoDNSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        return None


def dns_urlopen(url: str, timeout: int):
    return urllib.request.build_opener(_NoDNSRedirect()).open(url, timeout=timeout)


def resolve_public_dns(host: str, endpoint: str) -> list[str]:
    """Resolve through one trusted HTTPS service, without opening target egress.

    Domain-scoped controller firewalls intentionally deny arbitrary DNS names.
    The resolver receives only the hostname, never URLs, credentials or secrets.
    """
    parts = urlsplit(endpoint)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.port not in (None, 443):
        raise ValueError("A fixed HTTPS DNS resolver endpoint is required")
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    addresses = []
    for record_type in (1, 28):
        query = urlencode({"name": host, "type": record_type})
        with dns_urlopen(endpoint + "?" + query, timeout=5) as response:
            body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Public DNS response exceeds its size limit")
        value = json.loads(body)
        questions = value.get("Question", [])
        if value.get("Status") != 0 or value.get("TC", False) or len(questions) != 1 or questions[0].get("name", "").rstrip(".").lower() != host.lower() or questions[0].get("type") != record_type:
            raise ValueError("Public target DNS could not be verified")
        answers = value.get("Answer", [])
        if len(answers) > 128:
            raise ValueError("Public DNS response exceeds its answer limit")
        addresses.extend(str(answer["data"]) for answer in answers if answer.get("type") in (1, 28))
    return addresses


def validate_public_target(url: str, allowed_origins: set[str], resolver=None) -> str:
    authority = origin(url)
    if authority not in allowed_origins:
        raise ValueError("Navigation origin is not approved")
    host = urlsplit(url).hostname
    try:
        addresses = resolver(host) if resolver else [entry[4][0] for entry in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]
        ips = [ipaddress.ip_address(ip) for ip in addresses]
        if not ips or any(not ip.is_global or ip.is_multicast or ip in ipaddress.ip_network("192.88.99.0/24") for ip in ips):
            raise ValueError("Cloud targets must resolve only to public addresses")
    except OSError as error:
        raise ValueError("Public target DNS could not be verified") from error
    return url


def execution_network_policy(target: str, controller_origin: str = "", dependencies: tuple[str, ...] = (), resolver=None) -> dict:
    target_origin = origin(target)
    allow = {}
    for value in (target_origin, *dependencies):
        value_origin = origin(value)
        validate_public_target(value, {value_origin}, resolver=resolver)
        host = urlsplit(value).hostname
        if controller_origin and value_origin == origin(controller_origin):
            if value_origin == target_origin and not PUBLIC_DEMO.fullmatch(urlsplit(target).path):
                raise ValueError("Only the public demo is accessible on the controller origin")
            allow[host] = [
                {"match": {"method": ["GET", "HEAD"], "path": {"regex": PUBLIC_DEMO.pattern}}, "transform": []},
                {"response": {"statusCode": 403}},
            ]
        else:
            allow[host] = []
    # The domain allowlist alone cannot protect against DNS rebinding. Deny
    # private/link-local/metadata IPs at the microVM network boundary as well.
    return {"allow": allow, "subnets": {"deny": PRIVATE_SUBNETS}}


def worker_create_options(image: str, budget_seconds: int) -> dict:
    return {"image": image, "persistent": False, "env": {}, "execution_time_limit": budget_seconds}


@asynccontextmanager
async def managed_worker(create, image: str, budget_seconds: int):
    box = await create(**worker_create_options(image, budget_seconds))
    try:
        yield box
    finally:
        # Run on errors/cancellation too; the provider deadline is the final
        # backstop if the controlling process/connection itself disappears.
        await asyncio.shield(box.destroy(delete_orphan_snapshots=True))


@dataclass
class WorkerResult:
    exit_code: int
    files: dict[str, bytes]


async def stream_worker_output(reader, callback, budget):
    """Bound allocation before reading a newline, and cap persisted events."""
    if reader is None:
        return
    pending = ""
    # The SDK's read(n) waits for exactly n characters. Reading one character
    # drains its buffered provider chunks without delaying short live actions.
    while chunk := await reader.read(1):
        budget["bytes"] += len(chunk.encode("utf-8"))
        if budget["bytes"] > 2 * 1024 * 1024:
            raise ValueError("Worker exceeds the aggregate output limit")
        pending += chunk
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            if len(line) > 65536:
                raise ValueError("Worker stream exceeds safe message size")
            budget["messages"] += 1
            if budget["messages"] > 2000:
                raise ValueError("Worker exceeds the aggregate output limit")
            callback(line.rstrip())
        if len(pending) > 65536:
            raise ValueError("Worker stream exceeds safe message size")
    if pending:
        budget["messages"] += 1
        if budget["messages"] > 2000:
            raise ValueError("Worker exceeds the aggregate output limit")
        callback(pending.rstrip())


def collector_command(code):
    # System Python/stdlib are root-owned. Isolated startup cannot import
    # worker-written sitecustomize, PYTHONPATH, or user packages. Keep the
    # privilege restriction on every post-script process, not just the script.
    return "/usr/bin/setpriv", ["--no-new-privs", "/usr/bin/python3", "-I", "-S", "-c", code]


def artifact_manifest_code(root=WORK):
    return f'''import os,json,stat
entries=[]
total=0
with os.scandir({root!r}) as files:
    for entry in files:
        if not entry.name.endswith(('.png','.jpg','.jpeg','.webm','.html')): continue
        metadata=entry.stat(follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode): continue
        total+=metadata.st_size
        if len(entries)>=100 or total>{MAX_TOTAL} or metadata.st_size>{MAX_FILE} or len(entry.name)>180:
            raise ValueError('Worker evidence exceeds the collection limit')
        entries.append({{'name':entry.name,'size':metadata.st_size}})
print(json.dumps(entries))
'''


async def read_artifact(reader, budget):
    data = bytearray()
    while chunk := await reader.read(65536):
        budget["bytes"] += len(chunk)
        if budget["bytes"] > MAX_TOTAL:
            raise ValueError("Worker artifact exceeds the aggregate collection limit")
        if len(data) + len(chunk) > MAX_FILE:
            raise ValueError("Worker artifact exceeds the size limit")
        data.extend(chunk)
    return bytes(data)


async def prepare_worker(box):
    # This provider currently rejects IPv6 CIDRs. Refuse a VM with routable
    # IPv6 rather than silently leave an egress bypass. Untrusted processes
    # run with no_new_privs, so cannot enable interfaces via sudo/setuid.
    await box.run_process("sysctl", ["-w", "net.ipv6.conf.all.disable_ipv6=1", "net.ipv6.conf.default.disable_ipv6=1"], sudo=True, capture_output=True, check=True, kill_after=5)
    ipv6 = await box.run_process("ip", ["-6", "route", "show"], capture_output=True, check=True, kill_after=5)
    if str(getattr(ipv6, "stdout", "") or "").strip():
        raise ValueError("Worker has routable IPv6; isolation cannot be verified")
    await box.run_process("python", ["-c", "from pathlib import Path; paths=[Path('/etc/apt/sources.list'), *Path('/etc/apt/sources.list.d').glob('*.sources'), *Path('/etc/apt/sources.list.d').glob('*.list')]; [(p.write_text(p.read_text().replace('http://','https://'))) for p in paths if p.is_file()]"], sudo=True, capture_output=True, check=True, kill_after=5)
    await box.run_process("python", ["-m", "pip", "install", "--disable-pip-version-check", "playwright==1.63.0"], capture_output=True, check=True, kill_after=75)
    # Playwright elevates only apt itself. SDK sudo switches to system Python
    # and /root, losing the installed package and the user's browser cache.
    await box.run_process("python", ["-m", "playwright", "install", "--with-deps", "chromium"], capture_output=True, check=True, kill_after=120)
    # Chromium uses its NSS user trust store, not SSL_CERT_FILE. Import only
    # the provider's mounted per-VM CA; never disable HTTPS verification.
    await box.run_process("apt-get", ["install", "-y", "libnss3-tools"], sudo=True, capture_output=True, check=True, kill_after=30)


async def trust_worker_proxy(box):
    trust_code = "from pathlib import Path; import subprocess; candidates=[Path('/usr/local/share/ca-certificates/vercel-proxy-ca.pem'),Path('/etc/pki/ca-trust/source/anchors/vercel-proxy-ca.pem')]; ca=next((p for p in candidates if p.is_file()),None); assert ca, 'Provider proxy CA missing'; db=Path.home()/'.pki/nssdb'; db.mkdir(parents=True,exist_ok=True); subprocess.run(['/usr/bin/certutil','-N','--empty-password','-d','sql:'+str(db)],check=True); subprocess.run(['/usr/bin/certutil','-A','-n','Vercel sandbox proxy','-t','C,,','-i',str(ca),'-d','sql:'+str(db)],check=True)"
    await box.run_process("python", ["-c", trust_code], capture_output=True, check=True, kill_after=5)


class SandboxTransport:
    def __init__(self, policy, image: str, dependencies: tuple[str, ...] = ()):
        self.policy, self.image, self.dependencies = policy, image, dependencies

    @staticmethod
    def _network(document):
        from vercel.sandbox import NetworkPolicy, NetworkPolicySubnets, NetworkPolicyRule, NetworkPolicyRequestMatcher, NetworkPolicyMatcher, NetworkPolicyResponse, NetworkPolicyTransform
        rules = {}
        for host, values in document["allow"].items():
            rules[host] = []
            for value in values:
                if "response" in value:
                    rules[host].append(NetworkPolicyRule(response=NetworkPolicyResponse(status_code=value["response"]["statusCode"])))
                else:
                    match = value["match"]
                    rules[host].append(NetworkPolicyRule(match=NetworkPolicyRequestMatcher(method=match["method"], path=NetworkPolicyMatcher.regex(match["path"]["regex"])), transform=[NetworkPolicyTransform(headers={"Host": host})]))
            if not values:
                rules[host] = [NetworkPolicyRule(transform=[NetworkPolicyTransform(headers={"Host": host})])]
        return NetworkPolicy.custom(allow=rules, subnets=NetworkPolicySubnets(deny=document["subnets"]["deny"]))

    async def execute(self, *, code, environment, target_url, timeout_seconds, on_stdout, on_stderr):
        from vercel import sandbox
        from vercel.api import session
        from vercel.sandbox import NetworkPolicy, SandboxCredentials, SandboxServiceOptions, SandboxResources
        from backend.cloud_jobs import remaining_job_seconds
        budget = remaining_job_seconds(min(600, 210 + timeout_seconds))
        if budget < 30:
            raise ValueError("Cloud job has insufficient remaining browser budget")
        timeout_seconds = min(timeout_seconds, budget)
        credentials = self.policy.sdk_credentials(minimum_lifetime=budget)
        endpoint = getattr(self.policy, "dns_resolver_url", "")
        resolver = (lambda host: resolve_public_dns(host, endpoint)) if endpoint else None
        document = await asyncio.to_thread(execution_network_policy, target_url, self.policy.origin, self.dependencies, resolver=resolver)
        network = self._network(document)

        async def resolve():
            return SandboxCredentials(**credentials)

        async def create(**kwargs):
            return await sandbox.create_sandbox(**kwargs, resources=SandboxResources(vcpus=1), network_policy=network)

        async with session(service_options=[SandboxServiceOptions(credentials_factory=resolve)]):
            async with managed_worker(create, self.image, budget) as box:
                # No target, script or credentials exists during installation.
                # No snapshot/fork of the secret-bearing controller is involved.
                await box.update_network_policy(NetworkPolicy.custom(allow={host: () for host in INSTALL_HOSTS}))
                await prepare_worker(box)
                await box.update_network_policy(network)
                await trust_worker_proxy(box)
                await box.fs.mkdir(WORK, recursive=True)
                await box.fs.write_text(f"{WORK}/test_script.py", code, mode=0o600)
                process = await box.create_process("/usr/bin/setpriv", ["--no-new-privs", "python", f"{WORK}/test_script.py"], cwd=WORK, env=environment, kill_after=timeout_seconds)

                output_budget = {"bytes": 0, "messages": 0}
                await asyncio.wait_for(asyncio.gather(stream_worker_output(process.stdout, on_stdout, output_budget), stream_worker_output(process.stderr, on_stderr, output_budget)), timeout_seconds + 10)
                exit_code = await process.wait()
                # This is trusted collection code, not an untrusted supplied manifest.
                command, args = collector_command(artifact_manifest_code())
                manifest = await box.run_process(command, args, cwd="/", capture_output=True, check=True, kill_after=5)
                entries = json.loads(manifest.stdout)
                if len(entries) > 100 or sum(entry["size"] for entry in entries) > MAX_TOTAL:
                    raise ValueError("Worker evidence exceeds the collection limit")
                files, artifact_budget = {}, {"bytes": 0}
                for entry in entries:
                    name = entry["name"]
                    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,180}", name) or entry["size"] > MAX_FILE:
                        raise ValueError("Invalid worker artifact name or size")
                    async with box.fs.open(f"{WORK}/{name}", "rb") as reader:
                        files[name] = await read_artifact(reader, artifact_budget)
                return WorkerResult(exit_code, files)
