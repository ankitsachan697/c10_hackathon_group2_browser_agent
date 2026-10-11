"""Authenticate raw controller HTTP/WebSocket requests, not just the gateway."""
import hmac
import re

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

try:
    from .cloud_policy import CloudPolicy
except ImportError:
    from cloud_policy import CloudPolicy


PUBLIC_DEMO = re.compile(r"^/api/demo-shop/[A-Za-z0-9_-]{1,100}(?:/(?:shop\.css|shop\.js))?$")
DEVICE_HTTP = re.compile(r"^/api/companions/(?:exchange|heartbeat|[A-Za-z0-9_-]{1,100}/sessions)$")
DEVICE_WS = re.compile(r"^/api/companions/relay/[A-Za-z0-9_-]{1,100}/(?:companion|runner)$")
MEDIA_PATH = re.compile(r"^/api/media/[A-Za-z0-9_-]{1,100}$")
SAFE_EXECUTION_PATH = re.compile(r"^/api/(?:operations/generations|(?:journeys|runs)/[A-Za-z0-9_-]+/(?:run|rerun))$")
EXECUTION_PATH = re.compile(
    r"^/api/(?:operations/generations|discovery-and-generate|execute|execute-script|"
    r"diagnose-and-repair|visual-diff|autonomous-run|"
    r"(?:journeys|projects|runs|schedules|test-cases)(?:/[A-Za-z0-9_-]+)?/(?:run|rerun|generate|regenerate))$"
)


def authenticate_cloud_request(request: Request, policy: CloudPolicy) -> None:
    if not policy.enabled:
        return
    if request.method in {"GET", "HEAD"} and PUBLIC_DEMO.fullmatch(request.url.path):
        return
    supplied = request.headers.getlist("x-studio-control")
    if len(supplied) != 1 or not hmac.compare_digest(supplied[0], policy.control_secret):
        raise HTTPException(401, detail="Studio authorization is required")


class CloudAuthMiddleware:
    def __init__(self, app, policy: CloudPolicy, execution_ready=False):
        self.app, self.policy = app, policy
        self.execution_ready = execution_ready

    async def __call__(self, scope, receive, send):
        if not self.policy.enabled or scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        path, method = scope.get("path", ""), scope.get("method", "")
        if scope["type"] == "http" and method == "GET" and MEDIA_PATH.fullmatch(path):
            # This read-only handler authenticates its exact artifact capability.
            return await self.app(scope, receive, send)
        # These existing endpoints validate scoped pairing/device/relay credentials
        # themselves. They cannot grant general controller/API authorization.
        if scope["type"] == "websocket" and DEVICE_WS.fullmatch(path):
            return await self.app(scope, receive, send)
        if scope["type"] == "http" and DEVICE_HTTP.fullmatch(path):
            if (path.endswith("/sessions") and method == "GET") or (not path.endswith("/sessions") and method == "POST"):
                return await self.app(scope, receive, send)
        headers = [value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"x-studio-control"]
        permitted = len(headers) == 1 and hmac.compare_digest(headers[0], self.policy.control_secret)
        if scope["type"] == "http" and method in {"GET", "HEAD"} and PUBLIC_DEMO.fullmatch(path):
            permitted = True
        if not permitted:
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            return await JSONResponse({"error": {"code": "AUTH_REQUIRED", "message": "Studio authorization is required"}},
                                      status_code=401)(scope, receive, send)
        # Deployment-first release: the trusted controller may store/manage data,
        # but must never inspect arbitrary targets or execute generated code.
        # Remove this gate only alongside the isolated worker implementation.
        if (scope["type"] == "http" and method == "POST" and EXECUTION_PATH.fullmatch(path)
                and not (self.execution_ready and SAFE_EXECUTION_PATH.fullmatch(path))):
            return await JSONResponse({"error": {"code": "CLOUD_EXECUTION_PENDING", "message":
                "This execution route is not enabled on the cloud controller. Use New journey with Headless, or rerun a saved script."}},
                status_code=503)(scope, receive, send)
        await self.app(scope, receive, send)
