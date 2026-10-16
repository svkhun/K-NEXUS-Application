"""Source-project savings semantics exercised through the hardened HTTP boundary."""
import secrets
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from src.app_v2 import app
from src.flowsense_engine import get_savings_capacity, horizon

BASE = '/api/v2/flowsense'
ACCOUNT = 'ACC_0100'


class SavingsFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()
        self.csrf = self.client.get('/api/v2/session').json()['csrf_token']

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def post(self, path, body=None, key=None):
        return self.client.post(BASE + path, json={'account_id': ACCOUNT, **(body or {})}, headers={
            'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def profile(self):
        return self.client.get(BASE + '/profile/' + ACCOUNT).json()

    def prepare(self):
        self.post('/scenario', {'scenario': 'healthy'})
        self.assertEqual(self.post('/savings-preference', {'enabled': True}).status_code, 200)

    def test_opt_in_does_not_move_money_and_disabled_sweep_never_debits(self):
        self.post('/scenario', {'scenario': 'healthy'})
        before = self.profile()
        self.assertFalse(before['savings_enabled'])
        self.assertEqual(self.post('/micro-sweep', {'custom_sweep_amount': 100}).status_code, 400)
        self.post('/savings-preference', {'enabled': True})
        self.assertEqual(before['main_balance'], self.profile()['main_balance'])
        self.assertEqual(before['vault_balance'], self.profile()['vault_balance'])
        self.assertEqual(self.post('/micro-sweep', {'custom_sweep_amount': 100}).status_code, 200)
        self.post('/savings-preference', {'enabled': False})
        saved = self.profile()
        self.assertEqual(self.post('/micro-sweep').status_code, 400)
        self.assertEqual(self.profile()['main_balance'], saved['main_balance'])
        self.assertEqual(self.post('/vault/withdraw', {'amount': 100}).status_code, 200)

    def test_every_sweep_obeys_500_limit_and_recalculates_available_reserves(self):
        self.prepare()
        original = self.profile()
        self.assertEqual(self.post('/micro-sweep', {'custom_sweep_amount': 500.01}).status_code, 400)
        for _ in range(20):
            capacity = self.profile()['savings_capacity']
            if capacity['max_sweep_amount'] == 0:
                break
            response = self.post('/micro-sweep', {'custom_sweep_amount': capacity['max_sweep_amount']})
            self.assertEqual(response.status_code, 200, response.text)
            current = self.profile()
            self.assertAlmostEqual(current['main_balance'] + current['vault_balance'], original['main_balance'] + original['vault_balance'])
            self.assertGreaterEqual(current['main_balance'], capacity['projected_living_cost'] + capacity['fixed_commitments'] + capacity['emergency_buffer'] - .01)
        self.assertEqual(self.profile()['savings_capacity']['max_sweep_amount'], 0)
        before = self.profile()
        self.assertEqual(self.post('/micro-sweep').status_code, 400)
        self.assertEqual(before['main_balance'], self.profile()['main_balance'])

    def test_explicit_withdrawal_amount_and_currency_precision_are_required(self):
        before = self.profile()
        for body in ({}, {'amount': 0}, {'amount': -1}, {'amount': .001}, {'amount': 10, 'mode': 'undo'}):
            for route in ('/vault/withdraw', '/recall'):
                self.assertEqual(self.post(route, body).status_code, 422)
        self.assertEqual(self.post('/vault/withdraw', {'amount': before['vault_balance'] + .01}).status_code, 400)
        self.assertEqual(self.profile()['main_balance'], before['main_balance'])
        self.prepare()
        self.assertEqual(self.post('/micro-sweep', {'custom_sweep_amount': .001}).status_code, 422)

    def test_withdrawal_replay_is_once_and_partial_then_full_preserve_funds(self):
        before = self.profile()
        key = secrets.token_hex(16)
        response = self.post('/vault/withdraw', {'amount': 50.25}, key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post('/vault/withdraw', {'amount': 50.25}, key).json(), response.json())
        self.assertEqual(self.post('/vault/withdraw', {'amount': 50.26}, key).status_code, 409)
        self.assertEqual(self.profile()['main_balance'], round(before['main_balance'] + 50.25, 2))
        self.assertEqual(self.post('/vault/withdraw', {'amount': self.profile()['vault_balance']}).status_code, 200)
        final = self.profile()
        self.assertEqual(final['vault_balance'], 0)
        self.assertAlmostEqual(final['main_balance'], before['main_balance'] + before['vault_balance'])
        self.assertEqual(self.post('/vault/withdraw', {'amount': .01}).status_code, 400)

    def test_preference_is_private_scoped_and_reset_disables_savings(self):
        before = self.profile()
        self.assertEqual(self.client.post(BASE + '/savings-preference', json={'account_id': ACCOUNT, 'enabled': True}).status_code, 403)
        self.prepare()
        self.assertFalse(self.client.get(BASE + '/profile/ACC_0101').json()['savings_enabled'])
        with TestClient(app) as other:
            other.get('/api/v2/session')
            self.assertFalse(other.get(BASE + '/profile/' + ACCOUNT).json()['savings_enabled'])
        response = self.client.post(BASE + '/reset-state/' + ACCOUNT, json={}, headers={'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': secrets.token_hex(16)})
        self.assertEqual(response.status_code, 200)
        reset = self.profile()
        self.assertFalse(reset['savings_enabled'])
        self.assertEqual(reset['main_balance'], before['main_balance'])

    def test_retired_automation_routes_cannot_move_funds(self):
        before = self.profile()
        for route in ('/auto-saving', '/auto-cycle'):
            self.assertEqual(self.post(route).status_code, 404)
        self.assertEqual(self.profile()['main_balance'], before['main_balance'])


class SavingsCapacityTests(unittest.TestCase):
    profile = dict(monthly_salary=24000, fixed_rent=4000, fixed_debt=1000,
                   fixed_utilities=500, emergency_buffer=3000, avg_daily_spend=200)

    def test_source_formula_reserves_living_bills_and_minimum_buffer(self):
        state = dict(main_balance=20000, daily_spent_today=300)
        estimate = get_savings_capacity(state, self.profile, datetime(2026, 10, 16))
        self.assertEqual(estimate['days_to_payday'], 12)
        self.assertEqual(estimate['projected_living_cost'], 3600)
        self.assertEqual(estimate['safe_to_save'], 7900)
        self.assertEqual(estimate['max_sweep_amount'], 500)
        self.assertEqual(get_savings_capacity(state, {**self.profile, 'emergency_buffer': 0}, datetime(2026, 10, 16))['emergency_buffer'], 500)

    def test_payday_rollover_and_forecast_guard_cannot_inflate_capacity(self):
        state = dict(main_balance=20000, daily_spent_today=200)
        self.assertEqual(get_savings_capacity(state, self.profile, datetime(2026, 12, 28))['payday_date'], '2027-01-28')
        self.assertEqual(get_savings_capacity(state, self.profile, datetime(2028, 2, 29))['days_to_payday'], 28)
        with patch('src.flowsense_engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 16, tzinfo=ZoneInfo('Asia/Bangkok'))
            guarded = horizon(self.profile, state, {'2026-10-21': 3050})
        self.assertEqual(guarded['savings_capacity'], 50)
        self.assertEqual(guarded['max_sweep_amount'], 50)
        self.assertGreater(guarded['savings_estimate']['forecast_reserve_adjustment'], 0)
