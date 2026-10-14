"""Bounded, isolated browser sessions for a synthetic-data public demo."""

import asyncio
import copy
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from collections import OrderedDict, deque
from collections.abc import MutableMapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

PRODUCTION = os.environ.get("ENVIRONMENT") == "production"
COOKIE_NAME = "__Host-flowsense" if PRODUCTION else "flowsense_demo"
SESSION_TTL = 3600
MAX_SESSIONS = 200
MAX_BODY = 8192
SESSION_RATE = 120
DEMO_ACCOUNTS = frozenset({"ACC_0100", "ACC_0101", "ACC_0150"})
DEMO_RECIPIENTS = DEMO_ACCOUNTS | {"ACC_0000", "ACC_0001"}
SECRET = os.environ.get("DEMO_SESSION_SECRET", "")
if PRODUCTION and len(SECRET) < 32:
    raise RuntimeError("DEMO_SESSION_SECRET must contain at least 32 characters in production")
SECRET = SECRET or secrets.token_hex(32)

origin_config = os.environ.get("PUBLIC_ORIGIN") or os.environ.get("RENDER_EXTERNAL_URL")
if PRODUCTION and not origin_config:
    raise RuntimeError("Set PUBLIC_ORIGIN or RENDER_EXTERNAL_URL in production")
ALLOWED_ORIGINS = frozenset([origin_config.rstrip("/")] if origin_config else [
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:5173", "http://localhost:5173", "http://testserver",
])
for origin in ALLOWED_ORIGINS:
    parsed = urlsplit(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or '*' in parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise RuntimeError("Public origin must be an exact http(s) origin without a path")
if PRODUCTION and any(urlsplit(origin).scheme != "https" for origin in ALLOWED_ORIGINS):
    raise RuntimeError("The production public origin must use HTTPS")
ALLOWED_HOSTS = list({urlsplit(origin).hostname for origin in ALLOWED_ORIGINS}) + ["localhost", "127.0.0.1"]
SESSION_CONTEXT = ContextVar("demo_session")
SEED_ACCOUNTS = {}


@dataclass
class DemoSession:
    sid: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    csrf: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.time() + SESSION_TTL)
    accounts: dict = field(default_factory=lambda: copy.deepcopy(SEED_ACCOUNTS))
    pending: dict = field(default_factory=dict)
    replies: OrderedDict = field(default_factory=OrderedDict)
    requests: deque = field(default_factory=deque)
    request_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    account_lock: threading.RLock = field(default_factory=threading.RLock)


def current_session():
    return SESSION_CONTEXT.get()


class SessionMapping(MutableMapping):
    """Keep the original engine's dictionary API, scoped to the current visitor."""

    def __init__(self, attribute):
        self.attribute = attribute

    def _store(self):
        return getattr(current_session(), self.attribute)

    def __getitem__(self, key): return self._store()[key]
    def __setitem__(self, key, value): self._store()[key] = value
    def __delitem__(self, key): del self._store()[key]
    def __iter__(self): return iter(self._store())
    def __len__(self): return len(self._store())


class BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            if int(headers.get(b"content-length", b"0")) > MAX_BODY:
                return await JSONResponse({"detail": "Request body too large"}, 413)(scope, receive, send)
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, 400)(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > MAX_BODY:
                raise BodyTooLarge()
            return message

        await self.app(scope, limited_receive, send)


class DemoSessionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.sessions = OrderedDict()
        self.creations = OrderedDict()

    @staticmethod
    def deny(detail, status=403, **extra):
        return JSONResponse({"detail": detail, **extra}, status_code=status)

    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/v2/") or path == "/api/v2/health":
            return await call_next(request)
        origin = request.headers.get("origin")
        if (origin and origin not in ALLOWED_ORIGINS) or request.headers.get("sec-fetch-site") == "cross-site":
            return self.deny("Cross-site API access is not allowed")

        now = time.time()
        expired = [sid for sid, session in self.sessions.items() if session.expires <= now]
        for sid in expired:
            del self.sessions[sid]
        session = self.sessions.get(request.cookies.get(COOKIE_NAME))
        if path == "/api/v2/session" and request.method == "GET":
            if session is None:
                peer = request.client.host if request.client else "unknown"
                for key in list(self.creations):
                    if not self.creations[key] or self.creations[key][-1] < now - 60:
                        del self.creations[key]
                counts = self.creations.setdefault(peer, deque())
                while counts and counts[0] <= now - 60:
                    counts.popleft()
                if len(counts) >= 20:
                    return self.deny("สร้าง session บ่อยเกินไป กรุณารอสักครู่", 429)
                if len(self.sessions) >= MAX_SESSIONS or len(self.creations) > 1024:
                    return self.deny("พื้นที่ทดลองเต็มชั่วคราว กรุณาลองอีกครั้ง", 503)
                counts.append(now)
                session = DemoSession()
                self.sessions[session.sid] = session
            response = JSONResponse({"csrf_token": session.csrf, "expires_in_seconds": max(0, int(session.expires - now)), "mode": "synthetic_demo"})
            response.set_cookie(COOKIE_NAME, session.sid, max_age=max(0, int(session.expires - now)), httponly=True, secure=PRODUCTION, samesite="strict", path="/")
            return response
        if session is None:
            return self.deny("session ทดลองหมดอายุ กรุณาโหลดหน้าเว็บใหม่", 401, code="SESSION_EXPIRED")
        while session.requests and session.requests[0] < now - 60:
            session.requests.popleft()
        if len(session.requests) >= SESSION_RATE:
            response = self.deny("ส่งคำขอบ่อยเกินไป กรุณารอสักครู่", 429)
            response.headers["Retry-After"] = "60"
            return response
        session.requests.append(now)

        fingerprint = None
        request_key = None
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf):
                return self.deny("CSRF token ไม่ถูกต้อง กรุณาโหลดหน้าเว็บใหม่")
            if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
                return self.deny("Only application/json is supported", 415)
            request_key = request.headers.get("x-idempotency-key", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", request_key):
                return self.deny("A valid X-Idempotency-Key is required", 400)
            try:
                body = await request.body()
            except BodyTooLarge:
                return self.deny("Request body too large", 413)
            fingerprint = hashlib.sha256(request.method.encode() + path.encode() + body).hexdigest()

        async with session.request_lock:
            if request_key in session.replies:
                old_fingerprint, payload, status, content_type = session.replies[request_key]
                if old_fingerprint != fingerprint:
                    return self.deny("Idempotency key was already used for another request", 409)
                return Response(payload, status_code=status, media_type=content_type)
            token = SESSION_CONTEXT.set(session)
            try:
                response = await call_next(request)
                if request_key and 200 <= response.status_code < 300:
                    payload = b"".join([chunk async for chunk in response.body_iterator])
                    session.replies[request_key] = (fingerprint, payload, response.status_code, "application/json")
                    while len(session.replies) > 32:
                        session.replies.popitem(last=False)
                    response = Response(payload, status_code=response.status_code, headers=dict(response.headers))
                return response
            finally:
                SESSION_CONTEXT.reset(token)


class SecurityHeadersMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                security = {
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "referrer-policy": "no-referrer",
                    "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
                    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'",
                }
                if scope.get("path", "").startswith("/api/"):
                    security["cache-control"] = "no-store"
                if PRODUCTION:
                    security["strict-transport-security"] = "max-age=31536000"
                for name, value in security.items():
                    headers = [(k, v) for k, v in headers if k.lower() != name.encode()]
                    headers.append((name.encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, secure_send)
