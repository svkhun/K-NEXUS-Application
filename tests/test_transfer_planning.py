"""HTTP invariants for review-before-debit, bill accounting, and stale plans."""
import secrets
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from src.app_v2 import app, BEHAVIORAL_PROFILES_CACHE
from src import demo_security as security

BASE = '/api/v2'
SOURCE = 'ACC_0100'


class TransferPlanningTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch('src.flowsense_engine.datetime')
        self.datetime = self.clock.start()
        self.datetime.now.return_value = datetime(2026, 10, 10, tzinfo=ZoneInfo('Asia/Bangkok'))
        self.profile_patch = patch.dict(BEHAVIORAL_PROFILES_CACHE[SOURCE], dict(
            monthly_salary=20000, fixed_rent=5500, fixed_utilities=1660,
            fixed_debt=0, emergency_buffer=1000, avg_daily_spend=100))
        self.profile_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.csrf = self.client.get(BASE+'/session').json()['csrf_token']
        middleware = app.middleware_stack
        while not isinstance(middleware, security.DemoSessionMiddleware):
            middleware = middleware.app
        self.state = middleware.sessions[self.client.cookies.get(security.COOKIE_NAME)].accounts[SOURCE]
        self.state.update(main_balance=15000, daily_spent_today=0, spending_date='2026-10-10')
        self.post('/trustgraph/transfer-preference', dict(account_id=SOURCE, enabled=False))

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.profile_patch.stop()
        self.clock.stop()

    def post(self, path, body, key=None, client=None, csrf=None):
        return (client or self.client).post(BASE+path, json=body, headers={
            'X-CSRF-Token': csrf or self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def profile(self):
        return self.client.get(BASE+'/flowsense/profile/'+SOURCE).json()

    def horizon(self):
        return self.client.get(BASE+'/flowsense/horizon-status/'+SOURCE).json()

    def payload(self, amount=4000, target='ACC_0101', **kwargs):
        return dict(source_account_id=SOURCE, target_account_id=target, amount=amount,
                    is_first_time_transfer=int(target == 'ACC_0001'), session_duration_sec=90,
                    ratio_to_daily_avg=1.1, **kwargs)

    def evaluate(self, payload):
        response = self.post('/trustgraph/evaluate-transfer', payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def confirmation(self, payload, review):
        proof = {key: payload[key] for key in ('source_account_id', 'target_account_id', 'amount')}
        if review['status'] == 'TRANSFER_REVIEW':
            return dict(**proof, decision='PROCEED', review_token=review['review_token'])
        auth = self.post('/trustgraph/verify-micro-auth', proof)
        self.assertEqual(auth.status_code, 200, auth.text)
        return dict(**proof, decision='PROCEED', auth_token=auth.json()['clearance_token'])

    def test_preview_is_read_only_and_shows_the_380_to_157_77_example(self):
        payload = self.payload()
        before = self.profile()
        review = self.evaluate(payload)
        self.assertEqual(review['status'], 'TRANSFER_REVIEW')
        impact = review['liquidity_impact']
        self.assertEqual(impact['before']['average_per_day'], 380)
        self.assertEqual(impact['after']['average_per_day'], 157.77)
        self.assertEqual(self.profile()['main_balance'], before['main_balance'])
        self.assertEqual(self.state['daily_spent_today'], 0)
        self.assertNotIn('paid_commitments', self.state)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', dict(source_account_id=SOURCE,
            target_account_id='ACC_0101', amount=4000, decision='PROCEED')).status_code, 401)

    def test_full_rent_payment_preserves_budget_and_removes_only_this_months_bill(self):
        before = self.horizon()
        payload = self.payload(5500, matched_bill_id='rent:2026-10-26')
        review = self.evaluate(payload)
        self.assertEqual(review['liquidity_impact']['after']['average_per_day'], 380)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', self.confirmation(payload, review)).status_code, 200)
        after = self.horizon()
        self.assertEqual(after['daily_safe_limit'], before['daily_safe_limit'])
        self.assertEqual(after['total_recurring_commitments'], 1660)
        self.assertEqual(self.state['daily_spent_today'], 0)
        self.assertEqual(self.profile()['savings_capacity']['fixed_commitments'], 1660)
        future = self.client.get(BASE+'/flowsense/forecast-30d/'+SOURCE).json()['timeline']
        rent = next(row for row in future if row['date'] == '2026-10-26')
        self.assertEqual(rent['commitment_payment'], 0)
        self.datetime.now.return_value = datetime(2026, 11, 10, tzinfo=ZoneInfo('Asia/Bangkok'))
        self.assertEqual(self.horizon()['total_recurring_commitments'], 7160)

    def test_partial_bill_and_repeat_payment_cannot_overpay_or_reuse_the_receipt(self):
        payload = self.payload(1000.25, matched_bill_id='rent:2026-10-26')
        review = self.evaluate(payload)
        proof = self.confirmation(payload, review)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.post('/trustgraph/confirm-transfer', proof), range(2)))
        self.assertEqual(sorted(row.status_code for row in responses), [200, 401])
        self.assertEqual(self.state['main_balance'], 13999.75)
        rent = next(row for row in self.horizon()['recurring_commitments'] if row['kind'] == 'rent')
        self.assertEqual(rent['amount'], 4499.75)
        self.assertEqual(self.post('/trustgraph/evaluate-transfer', self.payload(4500, matched_bill_id=rent['id'])).status_code, 422)

    def test_stale_balance_cannot_debit_and_rechecking_updates_the_impact(self):
        payload = self.payload()
        review = self.evaluate(payload)
        proof = self.confirmation(payload, review)
        self.assertEqual(self.post('/flowsense/vault/withdraw', dict(account_id=SOURCE, amount=50)).status_code, 200)
        before = self.state['main_balance']
        stale = self.post('/trustgraph/confirm-transfer', proof)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['code'], 'PLAN_CHANGED')
        self.assertEqual(self.state['main_balance'], before)
        updated = self.evaluate(payload)
        self.assertEqual(updated['liquidity_impact']['before']['balance'], before)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', self.confirmation(payload, updated)).status_code, 200)

    def test_new_calendar_day_requires_a_fresh_review(self):
        payload = self.payload()
        review = self.evaluate(payload)
        self.datetime.now.return_value = datetime(2026, 10, 11, tzinfo=ZoneInfo('Asia/Bangkok'))
        self.assertEqual(self.post('/trustgraph/confirm-transfer', self.confirmation(payload, review)).status_code, 409)
        pending = self.client.get(BASE+'/trustgraph/pending-transfer/'+SOURCE).json()['pending']
        self.assertTrue(pending['plan_changed'])
        self.assertEqual(self.state['main_balance'], 15000)

    def test_changed_reserve_invalidates_review_and_fresh_review_uses_it(self):
        payload = self.payload(350)
        review = self.evaluate(payload)
        proof = self.confirmation(payload, review)
        self.assertEqual(self.post('/flowsense/reserve-preference', dict(account_id=SOURCE, amount=2500)).status_code, 200)
        stale = self.post('/trustgraph/confirm-transfer', proof)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['code'], 'PLAN_CHANGED')
        self.assertEqual(self.state['main_balance'], 15000)
        fresh = self.evaluate(payload)
        self.assertEqual(fresh['liquidity_impact']['emergency_buffer'], 2500)
        self.assertLess(fresh['liquidity_impact']['after']['average_per_day'], review['liquidity_impact']['after']['average_per_day'])

    def test_matching_a_bill_or_changing_context_does_not_lower_recipient_risk(self):
        for purpose in ('general', 'job', 'unlock', 'changed_account'):
            review = self.evaluate(self.payload(1000, 'ACC_0001', matched_bill_id='rent:2026-10-26', transfer_purpose=purpose))
            self.assertEqual(review['risk_tier'], 'CRITICAL_ANOMALY')
            self.assertFalse(review.get('review_token'))
            self.assertEqual(len(review['verification_guidance']['steps']), 2)
        blocked = self.evaluate(self.payload(1000, 'ACC_0000', matched_bill_id='rent:2026-10-26'))
        self.assertEqual(blocked['status'], 'BLOCKED_MULE_INTERDICTION')
        self.assertEqual(self.state['main_balance'], 15000)

    def test_liquidity_is_independent_of_fraud_risk_and_keeps_the_reserve_deficit(self):
        self.state['main_balance'] = 8500
        review = self.evaluate(self.payload(1000))
        self.assertEqual(review['risk_tier'], 'LOW_RISK')
        self.assertTrue(review['liquidity_impact']['reserve_at_risk'])
        self.assertEqual(review['liquidity_impact']['after']['reserve_shortfall'], 660)
        self.assertEqual(review['liquidity_impact']['after']['available_after_reserves'], -660)

    def test_sequence_counts_only_successful_transfers_and_cancel_does_not_erase_it(self):
        for amount in (300, 900):
            payload = self.payload(amount)
            review = self.evaluate(payload)
            self.assertEqual(self.post('/trustgraph/confirm-transfer', self.confirmation(payload, review)).status_code, 200)
        payload = self.payload(2800)
        review = self.evaluate(payload)
        self.assertEqual(review['transfer_sequence'], dict(count_today=2, sent_today=1200, total_if_confirmed=4000))
        self.post('/trustgraph/confirm-transfer', dict(source_account_id=SOURCE, target_account_id='ACC_0101', amount=2800, decision='CANCEL'))
        self.assertEqual(self.evaluate(payload)['transfer_sequence']['count_today'], 2)
        self.datetime.now.return_value = datetime(2026, 10, 11, tzinfo=ZoneInfo('Asia/Bangkok'))
        self.assertEqual(self.evaluate(payload)['transfer_sequence']['count_today'], 0)

    def test_review_tokens_are_session_bound_and_cannot_authorize_risky_transfers(self):
        payload = self.payload(350)
        review = self.evaluate(payload)
        proof = self.confirmation(payload, review)
        with TestClient(app) as other:
            csrf = other.get(BASE+'/session').json()['csrf_token']
            self.post('/trustgraph/evaluate-transfer', payload, client=other, csrf=csrf)
            self.assertEqual(self.post('/trustgraph/confirm-transfer', proof, client=other, csrf=csrf).status_code, 401)
        risky = self.payload(350, 'ACC_0001')
        self.evaluate(risky)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', {**proof, 'target_account_id': 'ACC_0001'}).status_code, 401)

    def test_pending_normal_review_restores_and_cancel_is_read_only(self):
        payload = self.payload(350)
        self.evaluate(payload)
        pending = self.client.get(BASE+'/trustgraph/pending-transfer/'+SOURCE).json()['pending']
        self.assertEqual(pending['status'], 'TRANSFER_REVIEW')
        self.assertIn('review_token', pending)
        self.assertNotIn('nonce', pending)
        self.post('/trustgraph/confirm-transfer', dict(source_account_id=SOURCE, target_account_id='ACC_0101', amount=350, decision='CANCEL'))
        self.assertEqual(self.state['main_balance'], 15000)
        self.assertIsNone(self.client.get(BASE+'/trustgraph/pending-transfer/'+SOURCE).json()['pending'])

    def test_unknown_expired_and_already_paid_bills_are_rejected(self):
        for bill in ('rent:2026-09-26', 'rent:2026-11-26', 'other:2026-10-26'):
            self.assertEqual(self.post('/trustgraph/evaluate-transfer', self.payload(100, matched_bill_id=bill)).status_code, 422)
        self.state['paid_commitments'] = {'rent:2026-10-26': 5500}
        self.assertEqual(self.post('/trustgraph/evaluate-transfer', self.payload(100, matched_bill_id='rent:2026-10-26')).status_code, 422)

    def test_bill_due_today_is_still_reserved_and_paid_forecast_is_not_duplicated(self):
        self.datetime.now.return_value = datetime(2026, 10, 26, tzinfo=ZoneInfo('Asia/Bangkok'))
        self.assertEqual(self.horizon()['total_recurring_commitments'], 7160)
        payload = self.payload(5500, matched_bill_id='rent:2026-10-26')
        review = self.evaluate(payload)
        self.assertEqual(self.post('/trustgraph/confirm-transfer', self.confirmation(payload, review)).status_code, 200)
        forecast = self.client.get(BASE+'/flowsense/forecast-30d/'+SOURCE).json()
        tomorrow = next(row for row in forecast['timeline'] if row['date'] == '2026-10-27')
        self.assertEqual(tomorrow['commitment_payment'], 1660)
