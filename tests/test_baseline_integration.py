"""Baseline acceptance: meaningful arithmetic, state, HTTP and model gating."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import secrets
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.baseline_policy import select_spending, seed_assumptions, satang, attach_prepared_history
from src.flowsense_engine import horizon, commitments
from src.liquidity_forecast import forecast
from src.transfer_planning import plan_fingerprint, apply_planned_debit
from scripts.baseline_fixture import history_fixture

TZ = ZoneInfo('Asia/Bangkok')
NOW = datetime(2026, 10, 27, 13, tzinfo=TZ)
PROFILE = dict(monthly_salary=20000, fixed_debt=1000, fixed_rent=3000,
               fixed_utilities=500, emergency_buffer=1000, avg_daily_spend=99999)
CONFIG = json.loads(Path('config/baseline-personas.v1.json').read_text())


def state(now=NOW):
    return dict(main_balance=20000, vault_balance=1000,
                **seed_assumptions('ACC_0100', now, CONFIG))


class SelectorTests(unittest.TestCase):
    def test_n6_n7_n28_zero_missing_exact_half_up_and_priority(self):
        for n in (6, 7, 28):
            account = state()
            account['non_bill_history'] = history_fixture('ACC_0100', NOW, n, 101)
            result = select_spending(account, NOW)
            self.assertEqual(result['complete_known_days'], n)
            self.assertEqual(result['numerator_satang'], 101*(n-1))
            self.assertEqual(result['method'], 'HISTORY_MEAN' if n >= 7 else 'SCENARIO')
            self.assertEqual(len(result['excluded']), 28-n)
            if n >= 7:
                self.assertEqual(result['daily_satang'], 87 if n == 7 else 97)
        account['non_bill_history'] = history_fixture('ACC_0100', NOW, 28, 0)
        self.assertEqual(select_spending(account, NOW)['daily_satang'], 0)
        self.assertEqual(satang('1.005'), 101)

    def test_partial_invalid_duplicate_foreign_stale_history_never_zero(self):
        account = state()
        history = history_fixture('ACC_0100', NOW, 7)
        account['non_bill_history'] = history
        history['records'][0].update(complete=False, amount_satang=None, reasons=['PARTIAL'])
        self.assertEqual(select_spending(account, NOW)['method'], 'SCENARIO')
        history['records'][0].update(complete=True, amount_satang=0)
        self.assertEqual(select_spending(account, NOW)['complete_known_days'], 6)
        for key, value in [('account_id', 'FOREIGN'), ('origin', (NOW-timedelta(days=1)).replace(hour=0).isoformat())]:
            bad = copy.deepcopy(history); bad[key] = value; account['non_bill_history'] = bad
            self.assertEqual(select_spending(account, NOW)['complete_known_days'], 0)
        account['spending_scenario'] = None
        self.assertIsNone(select_spending(account, NOW)['daily_satang'])
        self.assertEqual(select_spending(account, NOW)['method'], 'ABSTAIN')

    def test_scenario_invalid_time_units_negative_and_disabled_abstain(self):
        for key, value in [('unit', 'THB/transaction'), ('known_at', '2099-01-01T00:00:00+07:00'),
                           ('daily_satang', -1), ('daily_satang', 1.5), ('effective_to', '2026-10-28')]:
            account = state(); account['spending_scenario'][key] = value
            self.assertEqual(select_spending(account, NOW)['method'], 'ABSTAIN')
        account = state(); account['baseline_mode'] = 'OFF'
        self.assertEqual(select_spending(account, NOW)['reason'], 'BASELINE_DISABLED')

    def test_copied_projection_calendar_and_posted_spend_once(self):
        for date in (NOW, datetime(2026, 12, 31, 13, tzinfo=TZ), datetime(2028, 2, 29, 13, tzinfo=TZ)):
            account = state(date); before = copy.deepcopy(account)
            path = forecast(PROFILE, account, now=date)
            self.assertEqual(account, before)
            self.assertEqual(path['timeline'][0]['projected_balance'], 20000)
            self.assertEqual(len(path['timeline']), 31)
            self.assertEqual(path['projection_start'], (date+timedelta(days=1)).date().isoformat())
            for old, point in zip(path['timeline'], path['timeline'][1:]):
                self.assertEqual(satang(point['projected_balance']), satang(old['projected_balance'])-35000-satang(point['commitment_payment'])+satang(point['salary_inflow']))
        tomorrow = forecast(PROFILE, state(), now=NOW)['timeline'][1]
        self.assertEqual(tomorrow['salary_inflow'], 20000)
        self.assertEqual(tomorrow['commitment_payment'], 4500)

    def test_early_partial_overdue_full_only_remaining_on_projection_copy(self):
        account = state(); rows = commitments(PROFILE, NOW, account)
        debt = next(r for r in rows if r['kind'] == 'debt')
        apply_planned_debit(account, 300, debt)
        rent = next(r for r in rows if r['kind'] == 'rent')
        apply_planned_debit(account, 3000, rent)
        before = copy.deepcopy(account)
        path = forecast(PROFILE, account, now=NOW)
        self.assertEqual(path['timeline'][1]['commitment_payment'], 1200)
        self.assertEqual(account, before)
        self.assertEqual(path['current_balance'], 16700)

    def test_next_month_bills_match_plan_savings_transfer_and_graph(self):
        from src.transfer_planning import transfer_impact
        now = datetime(2026,10,29,13,tzinfo=TZ)
        account = state(now)
        before = copy.deepcopy(account)
        with patch('src.flowsense_engine.datetime') as clock:
            clock.now.return_value = now
            plan = horizon(PROFILE,account)
            impact = transfer_impact(account,PROFILE,100)
        path = forecast(PROFILE,account,now=now)
        bills = sum(p['commitment_payment'] for p in path['timeline'] if p['date'] < path['payday_date'])
        self.assertEqual(bills,9000) # current overdue + next-month obligations
        self.assertEqual(plan['total_recurring_commitments'], bills)
        self.assertEqual(plan['savings_estimate']['fixed_commitments'], bills)
        self.assertEqual(impact['before']['bills_remaining'], bills)
        self.assertEqual(account,before)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        from src import app_v2 as backend, demo_security as security
        from fastapi.testclient import TestClient
        self.backend, self.security = backend, security
        self.clock = patch('src.flowsense_engine.datetime'); self.clock.start().now.return_value = NOW
        self.client = TestClient(backend.app); self.client.__enter__()
        session = self.client.get('/api/v2/session').json(); self.csrf = session['csrf_token']
        layer = backend.app.middleware_stack
        while not isinstance(layer, security.DemoSessionMiddleware): layer = layer.app
        self.session = layer.sessions[session['session_id']]
        self.account = self.session.accounts['ACC_0100']

    def tearDown(self):
        self.client.__exit__(None, None, None); self.clock.stop()

    def get(self, route):
        response = self.client.get('/api/v2/flowsense/'+route+'/ACC_0100')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def post(self, route, body, key=None):
        return self.client.post('/api/v2/'+route, json=body, headers={'X-CSRF-Token':self.csrf, 'X-Idempotency-Key':key or secrets.token_hex(16)})

    def test_all_personas_and_consumers_share_selection(self):
        for account in ('ACC_0100','ACC_0101','ACC_0150'):
            values = [self.client.get('/api/v2/flowsense/'+route+'/'+account).json() for route in ('profile','forecast-30d','horizon-status')]
            self.assertEqual(len({v['spending_basis']['selection_id'] for v in values}),1)
            self.assertEqual(values[0]['spending_basis']['method'],'SCENARIO')
            self.assertEqual(values[2]['savings_estimate']['spending_basis'], values[0]['spending_basis'])
        self.assertEqual(set(self.backend.PACKAGE_SESSIONS), {'trustgraph'})
        self.assertFalse(self.backend.SERVING_CONFIG['flowsense_enabled'])

    def test_history_and_abstain_through_api_and_savings_rejection(self):
        self.account['non_bill_history'] = history_fixture('ACC_0100', NOW, 7)
        path = self.get('forecast-30d'); plan = self.get('horizon-status')
        self.assertEqual(path['spending_basis']['method'],'HISTORY_MEAN')
        self.assertEqual(path['spending_basis'],plan['spending_basis'])
        self.account.pop('non_bill_history'); self.account['spending_scenario']=None
        path = self.get('forecast-30d'); plan = self.get('horizon-status')
        self.assertEqual(plan['horizon_state'],'UNAVAILABLE')
        self.assertIsNone(plan['savings_capacity']); self.assertIsNone(plan['commitment_at_risk'])
        self.assertIsNone(path['min_projected_balance'])
        self.assertTrue(all(p['projected_balance'] is None and p['predicted_spend'] is None for p in path['timeline'][1:]))
        self.assertIsInstance(plan['remaining_today'],float)
        self.account['savings_enabled']=True
        before=copy.deepcopy(self.account)
        response=self.post('flowsense/micro-sweep',dict(account_id='ACC_0100',custom_sweep_amount=100))
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.account,before)

    def test_assumption_and_history_revision_stale_review_without_debit(self):
        transfer=dict(source_account_id='ACC_0100',target_account_id='ACC_0101',amount=100,
                      session_duration_sec=90,ratio_to_daily_avg=1.1)
        for kind in ('scenario','history'):
            review=self.post('trustgraph/evaluate-transfer',transfer).json()
            self.assertEqual(review['status'],'TRANSFER_REVIEW')
            self.assertEqual(review['liquidity_impact']['spending_basis'],self.get('profile')['spending_basis'])
            if kind=='scenario':self.account['spending_scenario']['daily_satang']+=1
            else:self.account['non_bill_history']=history_fixture('ACC_0100',NOW)
            before=self.account['main_balance']
            result=self.post('trustgraph/confirm-transfer',dict(source_account_id='ACC_0100',target_account_id='ACC_0101',amount=100,decision='PROCEED',review_token=review['review_token']))
            self.assertEqual(result.status_code,409,result.text)
            self.assertEqual(before,self.account['main_balance'])

    def test_no_model_inference_and_read_immutability(self):
        with patch.object(self.backend.rt,'InferenceSession',side_effect=AssertionError('No new sessions')):
            before=copy.deepcopy(self.account)
            self.get('forecast-30d'); self.get('horizon-status')
            self.assertEqual(self.account,before)


class PreparedBridgeTests(unittest.TestCase):
    def test_sealed_proposed4_history_classification_and_stale_origin(self):
        from src.flowsense_vnext.boundary import decode
        from src.flowsense_vnext.ingestion import prepare
        from src.flowsense_vnext.sources import ArtifactResolver
        pin=Path('docs/contracts/flowsense-vnext-data-review/proposed.4-v2.1.1/pinned')
        cases=decode((pin/'historical-fixtures.json').read_bytes())['cases']
        q=next(c['request'] for c in cases if c['id']=='original-nonbill-32197-not-zero')
        resolver=ArtifactResolver(pin,decode((pin/'fixture-source-manifest.json').read_bytes())['files'],('fixtures/source/',))
        prepared=prepare(q,resolver=resolver)
        native=dict(account_id=q['account_id'],main_balance=20000,daily_spent_today=0)
        attach_prepared_history(native,prepared)
        then=datetime.fromisoformat(q['origin'])+timedelta(hours=13)
        basis=select_spending(native,then)
        self.assertEqual(basis['method'],'HISTORY_MEAN')
        self.assertEqual(basis['daily_satang'],27752)
        self.assertEqual(basis['complete_known_days'],28)
        path=forecast(PROFILE,native,now=then)
        self.assertEqual(path['timeline'][1]['commitment_payment'],4500)
        self.assertNotIn('bill_instances',native) # history never becomes outstanding bills
        self.assertEqual(select_spending(native,NOW)['method'],'ABSTAIN')
        with self.assertRaisesRegex(ValueError,'HISTORY_ACCOUNT_MISMATCH'):
            attach_prepared_history(dict(account_id='ACC_0100'),prepared)
