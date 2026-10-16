"""Exercise the public HTTP boundary and cross-visitor isolation with real models."""

import secrets
import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app_v2 import app
from src import demo_security as security

BASE = "/api/v2"
SOURCE = "ACC_0100"


class SecurityTests(unittest.TestCase):
    def setUp(self):
        app.middleware_stack = None
        self.client = TestClient(app)
        self.client.__enter__()
        self.csrf = self.client.get(f"{BASE}/session").json()["csrf_token"]

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def post(self, path, body, key=None, client=None, csrf=None):
        return (client or self.client).post(f"{BASE}{path}", json=body, headers={
            "X-CSRF-Token": csrf or self.csrf,
            "X-Idempotency-Key": key or secrets.token_hex(16),
        })

    def balance(self, client=None):
        return (client or self.client).get(f"{BASE}/flowsense/profile/{SOURCE}").json()["main_balance"]

    def transfer(self, target="ACC_0001", amount=1200):
        return {"source_account_id": SOURCE, "target_account_id": target, "amount": amount,
                "session_duration_sec": 8 if target == "ACC_0001" else 90,
                "ratio_to_daily_avg": 8 if target == "ACC_0001" else 1.1,
                "is_first_time_transfer": 1 if target == "ACC_0001" else 0}

    def clearance(self):
        # These cases isolate signed-token invariants; cooldown has its own suite.
        self.post("/trustgraph/transfer-preference", {"account_id": SOURCE, "enabled": False})
        body = self.transfer()
        self.assertEqual(self.post("/trustgraph/evaluate-transfer", body).json()["status"], "MICRO_AUTH_REQUIRED")
        token_body = {key: body[key] for key in ("source_account_id", "target_account_id", "amount")}
        result = self.post("/trustgraph/verify-micro-auth", token_body)
        self.assertEqual(result.json()["verification_mode"], "SIMULATED")
        return token_body, result.json()["clearance_token"]

    def test_health_headers_and_private_api(self):
        health = self.client.get(f"{BASE}/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.headers["x-frame-options"], "DENY")
        self.assertIn("script-src 'self'", health.headers["content-security-policy"])
        self.assertEqual(health.headers["cache-control"], "no-store")
        self.assertIn("camera=()", health.headers["permissions-policy"])
        with TestClient(app) as anonymous:
            self.assertEqual(anonymous.get(f"{BASE}/flowsense/profile/{SOURCE}").status_code, 401)
        for route in ("/docs", "/openapi.json", f"{BASE}/secops/live-stream", f"{BASE}/wealthpilot/profile/{SOURCE}"):
            self.assertEqual(self.client.get(route).status_code, 404)
        self.assertEqual(self.client.get(f"{BASE}/flowsense/profile/ACC_0099").status_code, 404)
        self.assertEqual(self.client.get(f"{BASE}/health", headers={"Host": "evil.example"}).status_code, 400)

    def test_cookie_flags(self):
        cookie = self.client.get(f"{BASE}/session").headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        with patch.object(security, "PRODUCTION", True), patch.object(security, "COOKIE_NAME", "__Host-flowsense"):
            response = self.client.get(f"{BASE}/session")
            self.assertIn("secure", response.headers["set-cookie"].lower())
            self.assertIn("__Host-flowsense", response.headers["set-cookie"])
            self.assertIn("strict-transport-security", response.headers)

    def test_production_configuration_fails_closed(self):
        environment = {**os.environ, "ENVIRONMENT": "production", "PUBLIC_ORIGIN": "https://demo.example"}
        environment.pop("DEMO_SESSION_SECRET", None)
        result = subprocess.run([sys.executable, "-c", "import src.demo_security"], env=environment, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        environment["DEMO_SESSION_SECRET"] = "test-only-runtime-secret-with-32-characters"
        environment["PUBLIC_ORIGIN"] = "http://demo.example"
        result = subprocess.run([sys.executable, "-c", "import src.demo_security"], env=environment, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        environment["PUBLIC_ORIGIN"] = "https://demo.example"
        result = subprocess.run([sys.executable, "-c", "import src.demo_security"], env=environment, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_csrf_origin_and_media_type(self):
        body = {"account_id": SOURCE, "custom_sweep_amount": 200}
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", json=body).status_code, 403)
        headers = {"X-CSRF-Token": self.csrf, "X-Idempotency-Key": secrets.token_hex(16)}
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", json=body, headers={**headers, "Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.client.get(f"{BASE}/session", headers={"Sec-Fetch-Site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", content='{}', headers={**headers, "Content-Type": "text/plain"}).status_code, 415)

    def test_body_limit_and_input_validation(self):
        headers = {"X-CSRF-Token": self.csrf, "X-Idempotency-Key": secrets.token_hex(16), "Content-Type": "application/json"}
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", content=b'x' * 9000, headers=headers).status_code, 413)
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", content=iter([b'x' * 9000]), headers=headers).status_code, 413)
        for value in (-1, 0, 0.001, 100001):
            self.assertEqual(self.post("/flowsense/micro-sweep", {"account_id": SOURCE, "custom_sweep_amount": value}).status_code, 422)
        self.assertEqual(self.post("/flowsense/micro-sweep", {"account_id": "ACC_0099", "custom_sweep_amount": 200}).status_code, 422)
        self.assertEqual(self.post("/trustgraph/evaluate-transfer", self.transfer(SOURCE)).status_code, 422)
        self.assertEqual(self.post("/trustgraph/verify-micro-auth", {**self.transfer(), "liveness_score": 1}).status_code, 422)
        raw = '{"account_id":"ACC_0100","custom_sweep_amount":NaN}'
        self.assertEqual(self.client.post(f"{BASE}/flowsense/micro-sweep", content=raw, headers=headers).status_code, 422)

    def test_visitors_have_separate_balances(self):
        self.post("/flowsense/scenario", {"account_id": SOURCE, "scenario": "healthy"})
        self.post("/flowsense/savings-preference", {"account_id": SOURCE, "enabled": True})
        before = self.balance()
        with TestClient(app) as other:
            other_csrf = other.get(f"{BASE}/session").json()["csrf_token"]
            self.post("/flowsense/scenario", {"account_id": SOURCE, "scenario": "healthy"}, client=other, csrf=other_csrf)
            self.assertEqual(self.post("/flowsense/micro-sweep", {"account_id": SOURCE, "custom_sweep_amount": 200}).status_code, 200)
            self.assertEqual(self.balance(), before - 200)
            self.assertEqual(self.balance(other), before)
        self.assertEqual(self.post("/flowsense/vault/withdraw", {"account_id": SOURCE, "amount": 200}).status_code, 200)
        self.assertEqual(self.balance(), before)
        self.assertEqual(len(self.client.get(f"{BASE}/flowsense/forecast-30d/{SOURCE}").json()["timeline"]), 38)

    def test_idempotency_prevents_duplicate_debit_and_payload_reuse(self):
        before = self.balance()
        key = secrets.token_hex(16)
        body = self.transfer("ACC_0101", 350)
        first = self.post("/trustgraph/evaluate-transfer", body, key)
        self.assertEqual(first.json()["status"], "APPROVED")
        self.assertEqual(self.post("/trustgraph/evaluate-transfer", body, key).json(), first.json())
        self.assertEqual(self.balance(), before - 350)
        self.assertEqual(self.post("/trustgraph/evaluate-transfer", {**body, "amount": 500}, key).status_code, 409)

    def test_concurrent_duplicate_request_runs_once(self):
        self.post("/flowsense/scenario", {"account_id": SOURCE, "scenario": "healthy"})
        self.post("/flowsense/savings-preference", {"account_id": SOURCE, "enabled": True})
        before = self.balance()
        key = secrets.token_hex(16)
        body = {"account_id": SOURCE, "custom_sweep_amount": 200}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.post("/flowsense/micro-sweep", body, key), range(2)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(self.balance(), before - 200)

    def test_step_up_requires_evaluation_and_token(self):
        body = {key: self.transfer()[key] for key in ("source_account_id", "target_account_id", "amount")}
        self.assertEqual(self.post("/trustgraph/verify-micro-auth", body).status_code, 400)
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**body, "decision": "PROCEED"}).status_code, 401)
        payload, token = self.clearance()
        before = self.balance()
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "anything"}).status_code, 422)
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token + 'x'}).status_code, 401)
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "amount": 1201, "decision": "PROCEED", "auth_token": token}).status_code, 401)
        done = self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token})
        self.assertEqual(done.json()["status"], "TRANSFER_EXECUTED")
        self.assertEqual(self.balance(), before - 1200)
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token}).status_code, 401)

    def test_clearance_cannot_cross_sessions_or_survive_new_evaluation(self):
        payload, token = self.clearance()
        with TestClient(app) as other:
            csrf = other.get(f"{BASE}/session").json()["csrf_token"]
            self.post("/trustgraph/evaluate-transfer", self.transfer(), client=other, csrf=csrf)
            response = self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token}, client=other, csrf=csrf)
            self.assertEqual(response.status_code, 401)
        self.post("/trustgraph/evaluate-transfer", self.transfer())
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token}).status_code, 401)

    def test_cancel_and_reset_invalidate_clearance(self):
        payload, token = self.clearance()
        before = self.balance()
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "CANCEL"}).json()["status"], "TRANSFER_CANCELLED")
        self.assertEqual(self.balance(), before)
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token}).status_code, 401)
        payload, token = self.clearance()
        self.post(f"/flowsense/reset-state/{SOURCE}", {})
        self.assertEqual(self.post("/trustgraph/confirm-transfer", {**payload, "decision": "PROCEED", "auth_token": token}).status_code, 401)

    def test_blocked_account_cannot_use_high_value_gate(self):
        middleware = app.middleware_stack
        while not isinstance(middleware, security.DemoSessionMiddleware):
            middleware = middleware.app
        session = middleware.sessions[self.client.cookies.get(security.COOKIE_NAME)]
        session.accounts[SOURCE]["main_balance"] = 100000
        body = self.transfer("ACC_0000", 50000)
        result = self.post("/trustgraph/evaluate-transfer", body)
        self.assertEqual(result.json()["status"], "BLOCKED_MULE_INTERDICTION")
        verify_body = {key: body[key] for key in ("source_account_id", "target_account_id", "amount")}
        self.assertEqual(self.post("/trustgraph/verify-micro-auth", verify_body).status_code, 400)
        self.assertEqual(self.balance(), 100000)

    def test_rate_limit_and_session_expiry(self):
        with patch.object(security, "SESSION_RATE", 3):
            for _ in range(3):
                self.assertEqual(self.client.get(f"{BASE}/flowsense/profile/{SOURCE}").status_code, 200)
            self.assertEqual(self.client.get(f"{BASE}/flowsense/profile/{SOURCE}").status_code, 429)
        middleware = app.middleware_stack
        while not isinstance(middleware, security.DemoSessionMiddleware):
            middleware = middleware.app
        middleware.sessions[self.client.cookies.get(security.COOKIE_NAME)].expires = 0
        self.assertEqual(self.client.get(f"{BASE}/flowsense/profile/{SOURCE}").json()["code"], "SESSION_EXPIRED")


if __name__ == "__main__":
    unittest.main()
