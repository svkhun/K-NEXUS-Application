"""Product invariants: preserve funds, reserve obligations, explain demo scenarios."""
import secrets
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from src.app_v2 import app
from src.flowsense_engine import next_payday

BASE = '/api/v2'


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()
        self.csrf = self.client.get(BASE + '/session').json()['csrf_token']

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def post(self, path, **body):
        return self.client.post(BASE + path, json=body, headers={'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': secrets.token_hex(16)})

    def profile(self, account='ACC_0100'):
        return self.client.get(BASE + '/flowsense/profile/' + account).json()

    def scenario(self, mode, account='ACC_0100'):
        response = self.post('/flowsense/scenario', account_id=account, scenario=mode)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_scenarios_alert_only_on_commitments(self):
        for account in ('ACC_0100', 'ACC_0101', 'ACC_0150'):
            normal = self.scenario('normal_dip', account)
            self.assertEqual(normal['horizon_state'], 'NORMAL_DIP_SAFE')
            self.assertTrue(normal['alert_suppressed'])
            risk = self.scenario('commitment_risk', account)
            self.assertTrue(risk['commitment_at_risk'])
            self.assertFalse(risk['alert_suppressed'])
            self.assertTrue(any(row['is_at_risk'] for row in risk['recurring_commitments']))
            self.assertEqual(risk['recommended_sweep_amount'], 0)
            self.assertGreater(self.scenario('healthy', account)['recommended_sweep_amount'], 0)

    def test_guard_reserves_living_cost_bills_buffer_and_forecast_minimum(self):
        self.scenario('commitment_risk')
        self.post('/flowsense/savings-preference', account_id='ACC_0100', enabled=True)
        before = self.profile()
        self.assertEqual(self.post('/flowsense/micro-sweep', account_id='ACC_0100', custom_sweep_amount=100).status_code, 400)
        self.assertEqual(before['main_balance'], self.profile()['main_balance'])
        horizon = self.scenario('healthy')
        self.post('/flowsense/savings-preference', account_id='ACC_0100', enabled=True)
        self.assertEqual(self.post('/flowsense/micro-sweep', account_id='ACC_0100', custom_sweep_amount=round(horizon['max_sweep_amount']+.01, 2)).status_code, 400)
        result = self.post('/flowsense/micro-sweep', account_id='ACC_0100').json()
        self.assertEqual(result['status'], 'SWEEP_SUCCESS')
        forecast = self.client.get(BASE + '/flowsense/forecast-30d/ACC_0100').json()
        minimum = min(point['projected_balance'] for point in forecast['timeline'] if not point['is_past'] and point['date'] < horizon['payday_date'])
        self.assertGreaterEqual(minimum, horizon['emergency_buffer'])

    def test_standard_partial_and_full_withdrawal_conserves_funds_without_opt_in(self):
        original = self.profile()
        partial = self.post('/flowsense/vault/withdraw', account_id='ACC_0100', amount=50)
        self.assertEqual(partial.json()['withdrawn_amount'], 50)
        before = self.profile()
        self.assertFalse(before['savings_enabled'])
        self.assertEqual(self.post('/flowsense/vault/withdraw', account_id='ACC_0100', amount=before['vault_balance']+.01).status_code, 400)
        self.assertEqual(self.post('/flowsense/vault/withdraw', account_id='ACC_0100', amount=before['vault_balance']).json()['withdrawn_amount'], before['vault_balance'])
        final = self.profile()
        self.assertEqual(final['vault_balance'], 0)
        self.assertAlmostEqual(final['main_balance'], original['main_balance']+original['vault_balance'], places=2)

    def test_thirty_future_days_calendar_and_paid_commitments(self):
        self.scenario('healthy')
        forecast = self.client.get(BASE + '/flowsense/forecast-30d/ACC_0100').json()
        future = [p for p in forecast['timeline'] if p['is_future']]
        self.assertEqual(len(future), 30)
        self.assertEqual(len([p for p in forecast['timeline'] if p['is_past']]), 7)
        self.assertEqual(len({p['date'] for p in forecast['timeline']}), 38)
        for previous, current in zip([forecast['timeline'][7]]+future, future):
            self.assertAlmostEqual(current['projected_balance'], previous['projected_balance']-current['predicted_spend']-current['commitment_payment']+current['salary_inflow'], delta=.02)
        for year, month, day, expected in ((2026,12,31,'2027-01-28'), (2028,2,29,'2028-03-28'), (2026,1,28,'2026-02-28')):
            self.assertEqual(next_payday(datetime(year,month,day,tzinfo=ZoneInfo('Asia/Bangkok'))).strftime('%Y-%m-%d'), expected)

    def test_all_scenarios_use_current_thai_date_and_matching_forecast(self):
        for instant, expected in (
            ('2026-10-15T05:53:00+00:00', '2026-10-15'),
            ('2026-10-15T17:00:00+00:00', '2026-10-16'),
            ('2026-12-31T17:00:00+00:00', '2027-01-01'),
            ('2028-02-28T17:00:00+00:00', '2028-02-29'),
        ):
            with patch('src.flowsense_engine.datetime') as clock:
                clock.now.side_effect = lambda zone: datetime.fromisoformat(instant).astimezone(zone)
                for scenario in ('default', 'healthy', 'normal_dip', 'commitment_risk', 'high_value'):
                    if scenario == 'default':
                        self.post('/flowsense/reset-state/ACC_0100')
                        horizon = self.client.get(BASE + '/flowsense/horizon-status/ACC_0100').json()
                    else:
                        horizon = self.scenario(scenario)
                    forecast = self.client.get(BASE + '/flowsense/forecast-30d/ACC_0100').json()
                    with self.subTest(instant=instant, scenario=scenario):
                        self.assertEqual(horizon['as_of_date'], expected)
                        self.assertEqual(forecast['current_datetime'][:10], expected)
                        self.assertEqual(next(p['date'] for p in forecast['timeline'] if p['is_today']), expected)
                        self.assertEqual(horizon['payday_date'], forecast['payday_date'])
                        self.assertEqual(horizon['days_to_payday'], forecast['days_to_payday'])

    def test_event_feed_scoped_and_graph_is_synthetic(self):
        self.scenario('healthy')
        self.post('/flowsense/savings-preference', account_id='ACC_0100', enabled=True)
        self.post('/flowsense/micro-sweep', account_id='ACC_0100', custom_sweep_amount=100)
        self.assertIn('MICRO_SWEEP_EXECUTED', [e['event_type'] for e in self.profile()['events']])
        with TestClient(app) as visitor:
            visitor.get(BASE+'/session')
            self.assertEqual(visitor.get(BASE+'/flowsense/profile/ACC_0100').json()['events'], [])
        self.assertEqual(self.profile('ACC_0101')['events'], [])
        balance = self.profile()['main_balance']
        self.post('/trustgraph/evaluate-transfer', source_account_id='ACC_0100', target_account_id='ACC_0000', amount=100)
        self.assertEqual(self.profile()['main_balance'], balance)
        self.assertEqual(self.profile()['events'][0]['event_type'], 'TRANSFER_BLOCKED')
        graph = self.client.get(BASE+'/demo/insights').json()
        self.assertEqual(graph['data_mode'], 'synthetic_sample')
        self.assertLessEqual(len(graph['edges']), 18)
        ids = {n['id'] for n in graph['nodes']}
        self.assertTrue(all(e['source'] in ids and e['target'] in ids for e in graph['edges']))

    def test_high_value_preset_checks_before_debit_and_returns_receipt(self):
        self.scenario('high_value')
        transfer = dict(source_account_id='ACC_0100', target_account_id='ACC_0101', amount=50000, is_first_time_transfer=0, session_duration_sec=90, ratio_to_daily_avg=1.1)
        result = self.post('/trustgraph/evaluate-transfer', **transfer).json()
        self.assertEqual(result['risk_tier'], 'HIGH_VALUE_DEMO_CHECK')
        self.assertEqual(self.profile()['main_balance'], 60000)
        proof = {key: transfer[key] for key in ('source_account_id', 'target_account_id', 'amount')}
        token = self.post('/trustgraph/verify-micro-auth', **proof).json()['clearance_token']
        executed = self.post('/trustgraph/confirm-transfer', **proof, decision='PROCEED', auth_token=token).json()
        self.assertTrue(executed['receipt_id'].startswith('DEMO-'))
        self.assertEqual(self.profile()['main_balance'], 10000)
