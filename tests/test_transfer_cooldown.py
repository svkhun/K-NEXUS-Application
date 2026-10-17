"""Exercise risk-only cooldown policy at the public HTTP boundary with server time."""
import secrets
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.app_v2 import app

BASE = '/api/v2'
SOURCE = 'ACC_0100'


class TransferCooldownTests(unittest.TestCase):
    def setUp(self):
        self.now = time.time()
        self.clock = patch('src.app_v2.time.time', return_value=self.now)
        self.mock_time = self.clock.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.csrf = self.client.get(BASE + '/session').json()['csrf_token']

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.clock.stop()

    def post(self, route, body, key=None):
        return self.client.post(BASE + route, json=body, headers={
            'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def profile(self):
        return self.client.get(BASE + '/flowsense/profile/' + SOURCE).json()

    def transfer(self, target='ACC_0001', amount=1200):
        return dict(source_account_id=SOURCE, target_account_id=target, amount=amount,
                    session_duration_sec=8 if target == 'ACC_0001' else 90,
                    ratio_to_daily_avg=8 if target == 'ACC_0001' else 1.1,
                    is_first_time_transfer=int(target == 'ACC_0001'))

    def proof(self, target='ACC_0001', amount=1200):
        return dict(source_account_id=SOURCE, target_account_id=target, amount=amount)

    def evaluate(self, target='ACC_0001', amount=1200):
        response = self.post('/trustgraph/evaluate-transfer', self.transfer(target, amount))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def preference(self, enabled):
        return self.post('/trustgraph/transfer-preference', dict(account_id=SOURCE, enabled=enabled))

    def pending(self):
        return self.client.get(BASE + '/trustgraph/pending-transfer/' + SOURCE).json()['pending']

    def test_default_wait_guards_verify_and_confirm_at_the_exact_deadline(self):
        before = self.profile()['main_balance']
        self.assertTrue(self.profile()['transfer_cooldown_enabled'])
        review = self.evaluate()
        self.assertEqual(review['cooldown_remaining_sec'], 900)
        self.assertEqual(self.profile()['main_balance'], before)
        self.assertEqual(self.post('/trustgraph/verify-micro-auth', self.proof()).status_code, 409)
        self.mock_time.return_value = review['cooldown_ends_at'] - .001
        self.assertEqual(self.post('/trustgraph/verify-micro-auth', self.proof()).status_code, 409)
        self.mock_time.return_value = review['cooldown_ends_at']
        verified = self.post('/trustgraph/verify-micro-auth', self.proof()).json()
        token = verified['clearance_token']
        self.assertEqual(verified['clearance_expires_at'], int(review['cooldown_ends_at']) + 120)
        # Even a correctly signed token cannot bypass an active server deadline.
        self.mock_time.return_value = review['cooldown_ends_at'] - 1
        body = dict(**self.proof(), decision='PROCEED', auth_token=token)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', body).status_code, 409)
        self.assertEqual(self.profile()['main_balance'], before)
        self.mock_time.return_value = review['cooldown_ends_at']
        key = secrets.token_hex(16)
        response = self.post('/trustgraph/confirm-transfer', body, key)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', body, key).json(), response.json())
        self.assertEqual(self.profile()['main_balance'], before - 1200)
        self.assertIsNone(self.pending())
        self.assertEqual(self.evaluate()['cooldown_remaining_sec'], 900)

    def test_expired_auth_can_be_renewed_after_wait_without_restarting_timer(self):
        review = self.evaluate()
        self.mock_time.return_value = review['cooldown_ends_at']
        token = self.post('/trustgraph/verify-micro-auth', self.proof()).json()['clearance_token']
        self.mock_time.return_value += 121
        body = dict(**self.proof(), decision='PROCEED', auth_token=token)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', body).status_code, 401)
        body['auth_token'] = self.post('/trustgraph/verify-micro-auth', self.proof()).json()['clearance_token']
        self.assertEqual(self.post('/trustgraph/confirm-transfer', body).status_code, 200)

    def test_optional_wait_does_not_disable_risk_auth_or_blocked_destinations(self):
        self.preference(False)
        self.assertFalse(self.evaluate()['cooldown_required'])
        self.assertEqual(self.post('/trustgraph/confirm-transfer', dict(**self.proof(), decision='PROCEED')).status_code, 401)
        self.assertEqual(self.post('/trustgraph/verify-micro-auth', self.proof()).status_code, 200)
        self.assertEqual(self.evaluate('ACC_0000')['status'], 'BLOCKED_MULE_INTERDICTION')
        self.assertEqual(self.post('/trustgraph/verify-micro-auth', self.proof('ACC_0000')).status_code, 400)
        self.assertEqual(self.evaluate('ACC_0101', 350)['status'], 'TRANSFER_REVIEW')

    def test_setting_change_does_not_rewrite_an_active_transaction(self):
        before = self.profile()['main_balance']
        first = self.evaluate()
        self.mock_time.return_value += 60
        self.preference(False)
        second = self.evaluate()
        self.assertEqual(second['cooldown_ends_at'], first['cooldown_ends_at'])
        self.assertEqual(second['cooldown_remaining_sec'], 840)
        self.assertEqual(self.profile()['main_balance'], before)

    def test_cancel_then_new_identical_transfer_uses_disabled_setting_without_old_timer(self):
        before = self.profile()['main_balance']
        self.evaluate()
        self.mock_time.return_value += 60
        self.preference(False)
        cancelled = self.post('/trustgraph/confirm-transfer', dict(**self.proof(), decision='CANCEL'))
        self.assertEqual(cancelled.status_code, 200)
        self.assertTrue(cancelled.json()['cooldown_cleared'])
        self.assertIsNone(self.pending())
        retry = self.evaluate()
        self.assertFalse(retry['cooldown_required'])
        self.assertEqual(retry['cooldown_remaining_sec'], 0)
        token = self.post('/trustgraph/verify-micro-auth', self.proof()).json()['clearance_token']
        executed = self.post('/trustgraph/confirm-transfer', dict(**self.proof(), decision='PROCEED', auth_token=token))
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(self.profile()['main_balance'], before - 1200)

    def test_cancel_then_new_enabled_transfer_starts_its_own_full_period(self):
        first = self.evaluate()
        self.mock_time.return_value += 125
        self.post('/trustgraph/confirm-transfer', dict(**self.proof(), decision='CANCEL'))
        retry = self.evaluate()
        self.assertEqual(retry['cooldown_remaining_sec'], 900)
        self.assertEqual(retry['cooldown_ends_at'], first['cooldown_ends_at'] + 125)

    def test_replacing_the_amount_creates_a_new_review_with_current_settings(self):
        before = self.profile()['main_balance']
        self.evaluate()
        self.mock_time.return_value += 60
        self.preference(False)
        changed = self.evaluate(amount=500)
        self.assertFalse(changed['cooldown_required'])
        self.assertEqual(self.pending()['amount'], 500)
        self.assertEqual(self.profile()['main_balance'], before)

    def test_reload_status_preserves_deadline_and_is_scoped_to_persona_and_session(self):
        review = self.evaluate()
        self.mock_time.return_value += 125
        pending = self.pending()
        self.assertEqual(pending['cooldown_ends_at'], review['cooldown_ends_at'])
        self.assertEqual(pending['cooldown_remaining_sec'], 775)
        self.assertEqual(pending['target_account_id'], 'ACC_0001')
        self.assertNotIn('nonce', pending)
        self.assertIsNone(self.client.get(BASE + '/trustgraph/pending-transfer/ACC_0101').json()['pending'])
        with TestClient(app) as other:
            other.get(BASE + '/session')
            self.assertIsNone(other.get(BASE + '/trustgraph/pending-transfer/' + SOURCE).json()['pending'])
        self.assertEqual(self.client.get(BASE + '/trustgraph/pending-transfer/ACC_9999').status_code, 404)
        self.mock_time.return_value = review['review_expires_at'] + 1
        self.assertIsNone(self.pending())
        self.assertEqual(self.post('/trustgraph/verify-micro-auth', self.proof()).status_code, 400)

    def test_high_value_alone_does_not_wait_but_risk_is_not_bypassed_by_large_amount(self):
        self.post('/flowsense/scenario', dict(account_id=SOURCE, scenario='high_value'))
        known = self.evaluate('ACC_0101', 50000)
        self.assertEqual(known['risk_tier'], 'HIGH_VALUE_DEMO_CHECK')
        self.assertFalse(known['cooldown_required'])
        risky = self.evaluate('ACC_0001', 50000)
        self.assertEqual(risky['risk_tier'], 'CRITICAL_ANOMALY')
        self.assertEqual(risky['cooldown_remaining_sec'], 900)
        self.assertEqual(self.evaluate('ACC_0000', 50000)['status'], 'BLOCKED_MULE_INTERDICTION')
        self.assertEqual(self.profile()['main_balance'], 60000)

    def test_setting_requires_csrf_is_private_and_does_not_move_money(self):
        before = self.profile()['main_balance']
        self.assertEqual(self.client.post(BASE + '/trustgraph/transfer-preference', json=dict(account_id=SOURCE, enabled=False)).status_code, 403)
        key = secrets.token_hex(16)
        body = dict(account_id=SOURCE, enabled=False)
        first = self.post('/trustgraph/transfer-preference', body, key)
        self.assertEqual(first.json(), self.post('/trustgraph/transfer-preference', body, key).json())
        self.assertFalse(self.profile()['transfer_cooldown_enabled'])
        self.assertTrue(self.client.get(BASE + '/flowsense/profile/ACC_0101').json()['transfer_cooldown_enabled'])
        self.assertEqual(self.profile()['main_balance'], before)
        self.post('/flowsense/reset-state/' + SOURCE, {})
        self.assertTrue(self.profile()['transfer_cooldown_enabled'])
