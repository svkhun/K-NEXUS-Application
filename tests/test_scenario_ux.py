"""Session lifecycle and destructive-demo boundaries, using the actual HTTP stack."""
import copy
from datetime import datetime
import secrets
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from src import app_v2 as backend, demo_security as security

BASE = '/api/v2/'
ACCOUNTS = ('ACC_0100', 'ACC_0101', 'ACC_0150')


class ScenarioUXTests(unittest.TestCase):
    def setUp(self):
        backend.app.middleware_stack = None
        self.client = TestClient(backend.app)
        self.client.__enter__()
        self.opening = self.client.get(BASE+'session').json()
        self.csrf = self.opening['csrf_token']
        self.layer = backend.app.middleware_stack
        while not isinstance(self.layer, security.DemoSessionMiddleware):
            self.layer = self.layer.app
        self.session = self.layer.sessions[self.opening['session_id']]

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def get(self, kind, account=ACCOUNTS[0]):
        result = self.client.get(BASE+'flowsense/'+kind+'/'+account)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def post(self, path, body=None, key=None):
        return self.client.post(BASE+path, json=body or {}, headers={
            'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def test_fresh_personas_calendar_initialization_and_explicit_reset(self):
        self.assertEqual(self.opening['lifecycle'], 'NEW')
        for account in ACCOUNTS:
            opening_plan = self.get('horizon-status', account)
            self.assertEqual(opening_plan['scenario'], 'default')
            self.assertGreater(opening_plan['remaining_today'], 1)
            self.assertGreater(opening_plan['max_sweep_amount'], 1)
        for instant in ('2026-10-27', '2026-10-28', '2026-10-31', '2026-11-01', '2028-02-29'):
            now = datetime.fromisoformat(instant+'T23:59:00').replace(tzinfo=ZoneInfo('Asia/Bangkok'))
            with patch('src.flowsense_engine.datetime') as clock:
                clock.now.return_value = now
                for account in ACCOUNTS:
                    with self.subTest(date=instant, account=account):
                        self.assertEqual(self.post('flowsense/reset-state/'+account).status_code, 200)
                        plan = self.get('horizon-status', account)
                        self.assertEqual(plan['scenario'], 'default')
                        self.assertEqual(plan['demo_initialization_version'], 'demo-opening.2026-10-30.1')
                        self.assertGreater(plan['remaining_today'], 1)
                        self.assertGreater(plan['max_sweep_amount'], 1)
                        self.assertEqual(plan['spending_basis']['method'], 'SCENARIO')
                        before = copy.deepcopy(self.session.accounts[account])
                        self.get('profile', account); self.get('forecast-30d', account)
                        self.assertEqual(self.session.accounts[account], before)

    def test_resume_and_get_refresh_preserve_scenario_money_bills_and_events(self):
        account = ACCOUNTS[0]
        self.assertEqual(self.post('flowsense/scenario', dict(account_id=account, scenario='commitment_risk')).status_code, 200)
        before = copy.deepcopy(self.session.accounts)
        resumed = self.client.get(BASE+'session').json()
        self.assertEqual(resumed['lifecycle'], 'RESUMED')
        self.assertEqual(resumed['session_id'], self.opening['session_id'])
        for other in ACCOUNTS:
            self.get('profile', other); self.get('forecast-30d', other)
        plan = self.get('horizon-status')
        self.assertEqual(plan['scenario'], 'commitment_risk')
        self.assertEqual(plan['remaining_today'], 0)
        self.assertGreater(plan['current_balance'], 0)
        self.assertGreater(plan['budget_reserve_shortfall'], 0)
        self.assertEqual(self.session.accounts, before)

    def test_reset_is_persona_scoped_and_retains_command_tombstones_and_receipts(self):
        account = ACCOUNTS[0]
        self.post('flowsense/reserve-preference', dict(account_id=account, amount=2500))
        self.post('flowsense/scenario', dict(account_id=account, scenario='healthy'))
        self.assertEqual(self.get('horizon-status')['emergency_buffer'], 2500)
        others = {a:copy.deepcopy(self.session.accounts[a]) for a in ACCOUNTS[1:]}
        keys = dict(self.session.commands)
        replies = copy.deepcopy(self.session.replies)
        self.assertEqual(self.post('flowsense/reset-state/'+account).status_code, 200)
        for a, state in others.items(): self.assertEqual(self.session.accounts[a], state)
        for key, value in keys.items():
            self.assertEqual(self.session.commands[key], value)
            self.assertEqual(self.session.replies[key], replies[key])
        self.assertNotIn('reserve_amount', self.session.accounts[account])
        with TestClient(backend.app) as visitor:
            session_id = visitor.get(BASE+'session').json()['session_id']
            other = copy.deepcopy(self.layer.sessions[session_id].accounts)
            self.post('flowsense/scenario', dict(account_id=account, scenario='commitment_risk'))
            self.assertEqual(self.layer.sessions[session_id].accounts, other)

    def test_unknown_server_command_blocks_reset_and_scenario_without_erasure(self):
        for status in (None, 500):
            self.session.commands['ambiguous-command-key'] = ('fingerprint', status)
            before = copy.deepcopy(self.session.accounts)
            for path, body in [('flowsense/reset-state/'+ACCOUNTS[0], {}),
                               ('flowsense/scenario', dict(account_id=ACCOUNTS[0], scenario='healthy'))]:
                result = self.post(path, body)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(result.json()['code'], 'OUTCOME_UNKNOWN')
                self.assertEqual(self.session.accounts, before)
                self.assertEqual(self.session.commands['ambiguous-command-key'], ('fingerprint', status))

    def test_reset_cannot_turn_old_transfer_retry_into_a_second_debit(self):
        payload = dict(source_account_id=ACCOUNTS[0], target_account_id=ACCOUNTS[1], amount=1,
                       session_duration_sec=90, ratio_to_daily_avg=1.1)
        review = self.post('trustgraph/evaluate-transfer', payload).json()
        self.assertEqual(review['status'], 'TRANSFER_REVIEW')
        payload = {k:payload[k] for k in ('source_account_id', 'target_account_id', 'amount')}
        payload.update(decision='PROCEED', review_token=review['review_token'])
        key = secrets.token_hex(16)
        first = self.post('trustgraph/confirm-transfer', payload, key)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['status'], 'TRANSFER_EXECUTED')
        self.post('flowsense/reset-state/'+ACCOUNTS[0])
        balance = self.get('profile')['main_balance']
        self.assertEqual(self.post('trustgraph/confirm-transfer', payload, key).json(), first.json())
        self.assertEqual(self.get('profile')['main_balance'], balance)
        self.assertNotEqual(self.post('trustgraph/confirm-transfer', payload).status_code, 200)

    def test_expiry_creates_new_session_and_does_not_claim_resume(self):
        self.session.expires = 0
        fresh = self.client.get(BASE+'session').json()
        self.assertEqual(fresh['lifecycle'], 'NEW')
        self.assertTrue(fresh['previous_session_expired'])
        self.assertNotEqual(fresh['session_id'], self.opening['session_id'])
