"""Reserve preference changes planning, never money, and stays inside a session."""
import secrets
import unittest
from fastapi.testclient import TestClient
from src.app_v2 import app

BASE = '/api/v2/flowsense'
ACCOUNT = 'ACC_0100'


class ReservePreferenceTests(unittest.TestCase):
    def setUp(self):
        # Keep this suite's session creation separate from rate-limit boundary tests.
        self.client = TestClient(app, client=('127.0.0.2', 50000))
        self.client.__enter__()
        self.csrf = self.client.get('/api/v2/session').json()['csrf_token']

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def post(self, path, amount=3000, key=None):
        return self.client.post(BASE+path, json={'account_id': ACCOUNT, 'amount': amount}, headers={
            'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def horizon(self):
        return self.client.get(BASE+'/horizon-status/'+ACCOUNT).json()

    def profile(self):
        return self.client.get(BASE+'/profile/'+ACCOUNT).json()

    def test_preview_is_read_only_and_matches_saved_plan_without_moving_money(self):
        before, account = self.horizon(), self.profile()
        self.assertFalse(before['reserve_settings']['confirmed'])
        preview = self.post('/reserve-preview', 1200.25)
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(self.horizon()['reserve_settings'], before['reserve_settings'])
        result = self.post('/reserve-preference', 1200.25)
        self.assertTrue(result.json()['confirmed'])
        after = self.horizon()
        for key, value in preview.json()['after'].items():
            self.assertEqual(after[key], value, key)
        current = self.profile()
        self.assertEqual((current['main_balance'], current['vault_balance']), (account['main_balance'], account['vault_balance']))
        self.assertGreaterEqual(after['daily_safe_limit'], before['daily_safe_limit'])
        self.assertEqual(current['savings_capacity']['emergency_buffer'], 1200.25)

    def test_validation_csrf_and_large_reserve_shortfall(self):
        for amount in (499.99, 0, -1, 10.001, 500.001, 10_000_000.01, 'NaN', 'Infinity'):
            self.assertEqual(self.post('/reserve-preference', amount).status_code, 422, amount)
        forbidden = self.client.post(BASE+'/reserve-preference', json={'account_id': ACCOUNT, 'amount': 1000})
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(self.post('/reserve-preference', 1_000_000).status_code, 200)
        current = self.horizon()
        self.assertEqual(current['remaining_today'], 0)
        self.assertEqual(current['savings_capacity'], 0)
        self.assertGreater(current['budget_reserve_shortfall'], 0)

    def test_preference_isolated_and_replay_does_not_reapply_old_setting(self):
        key = secrets.token_hex(16)
        self.post('/reserve-preference', 1000, key)
        self.post('/reserve-preference', 2000)
        self.assertEqual(self.post('/reserve-preference', 1000, key).status_code, 200)
        self.assertEqual(self.horizon()['emergency_buffer'], 2000)
        self.assertFalse(self.client.get(BASE+'/horizon-status/ACC_0101').json()['reserve_settings']['confirmed'])
        with TestClient(app, client=('127.0.0.3', 50000)) as other:
            other.get('/api/v2/session')
            self.assertFalse(other.get(BASE+'/horizon-status/'+ACCOUNT).json()['reserve_settings']['confirmed'])

    def test_scenario_preserves_preference_and_explicit_reset_restores_seed(self):
        self.post('/reserve-preference', 700.50)
        headers = {'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': secrets.token_hex(16)}
        result = self.client.post(BASE+'/scenario', json={'account_id': ACCOUNT, 'scenario': 'healthy'}, headers=headers)
        self.assertEqual(result.json()['emergency_buffer'], 700.50)
        self.assertTrue(result.json()['reserve_settings']['confirmed'])
        headers['X-Idempotency-Key'] = secrets.token_hex(16)
        self.client.post(BASE+'/reset-state/'+ACCOUNT, json={}, headers=headers)
        settings = self.horizon()['reserve_settings']
        self.assertFalse(settings['confirmed'])
        self.assertEqual(settings['amount'], settings['suggested_amount'])

    def test_sweep_rechecks_new_reserve_before_debit(self):
        headers = {'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': secrets.token_hex(16)}
        self.client.post(BASE+'/scenario', json={'account_id': ACCOUNT, 'scenario': 'healthy'}, headers=headers)
        headers['X-Idempotency-Key'] = secrets.token_hex(16)
        self.client.post(BASE+'/savings-preference', json={'account_id': ACCOUNT, 'enabled': True}, headers=headers)
        before = self.profile()
        self.post('/reserve-preference', 1_000_000)
        headers['X-Idempotency-Key'] = secrets.token_hex(16)
        response = self.client.post(BASE+'/micro-sweep', json={'account_id': ACCOUNT, 'custom_sweep_amount': 100}, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.profile()['main_balance'], before['main_balance'])
