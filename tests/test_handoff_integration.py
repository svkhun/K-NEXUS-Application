"""Fixed-clock acceptance tests for persisted bills and the serving boundary."""
import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import secrets
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fastapi.testclient import TestClient
from src import app_v2 as backend, demo_security as security
from src.flowsense_engine import commitments, horizon
from src.transfer_planning import apply_planned_debit, transfer_impact
from src.spending_contract import aggregate_non_bill, flow_features, recursive_spending
from src.model_package import load_package, load_legacy
from src.liquidity_forecast import forecast
from src.baseline_policy import seed_assumptions

TZ = ZoneInfo('Asia/Bangkok')
PROFILE = dict(monthly_salary=20000, fixed_debt=1000, fixed_rent=3000,
               fixed_utilities=500, avg_daily_spend=100, emergency_buffer=1000)


class CalendarContractTests(unittest.TestCase):
    def test_due_before_on_after_and_new_month_partial_full_without_duplicate_debit(self):
        state = dict(main_balance=20000, daily_spent_today=0)
        for day in (21, 22, 23):
            rows = commitments(PROFILE, datetime(2026, 10, day, tzinfo=TZ), state)
            bill = next(b for b in rows if b['kind'] == 'debt')
            self.assertEqual(bill['id'], 'debt:2026-10-22')
            self.assertEqual(bill['amount'], 1000)
            self.assertEqual(bill['due_days'], 22-day)
        apply_planned_debit(state, 300, bill)
        for day in (23, 24, 31):
            rows = commitments(PROFILE, datetime(2026, 10, day, tzinfo=TZ), state)
            self.assertEqual(next(b['amount'] for b in rows if b['kind'] == 'debt'), 700)
            self.assertEqual(state['main_balance'], 19700)
        rows = commitments(PROFILE, datetime(2026, 11, 22, tzinfo=TZ), state)
        debts = [b for b in rows if b['kind'] == 'debt']
        self.assertEqual({b['id']: b['amount'] for b in debts}, {'debt:2026-10-22': 700, 'debt:2026-11-22': 1000})
        apply_planned_debit(state, 700, debts[0])
        rows = commitments(PROFILE, datetime(2026, 11, 23, tzinfo=TZ), state)
        self.assertFalse(any(b['id'] == 'debt:2026-10-22' for b in rows))
        self.assertEqual(state['bill_instances']['debt:2026-10-22']['paid_amount'], 1000)
        self.assertEqual(state['main_balance'], 19000)
        self.assertFalse(any('2026-09' in b for b in state['bill_instances']))

    def test_all_planners_share_overdue_reserve_and_projection_never_settles(self):
        state = dict(main_balance=20000, daily_spent_today=0)
        config = json.loads((Path(backend.BASE_DIR)/'config/baseline-personas.v1.json').read_text())
        state.update(seed_assumptions('ACC_0100', datetime(2026,10,26,tzinfo=TZ), config))
        state['spending_scenario']['daily_satang'] = 10000
        with patch('src.flowsense_engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 26, tzinfo=TZ)
            horizon(PROFILE, state)
            clock.now.return_value += timedelta(days=1)
            plan = horizon(PROFILE, state)
            expected = 4500
            self.assertEqual(plan['total_recurring_commitments'], expected)
            self.assertEqual(plan['savings_estimate']['fixed_commitments'], expected)
            impact = transfer_impact(state, PROFILE, 250, 'rent:2026-10-26')
            self.assertEqual(impact['before']['bills_remaining'], expected)
            self.assertEqual(impact['after']['bills_remaining'], expected-250)
            snapshot = copy.deepcopy(state)
            path = forecast(PROFILE, state)
            self.assertEqual(state, snapshot)
            tomorrow = next(p for p in path['timeline'] if p['is_future'])
            self.assertEqual(tomorrow['commitment_payment'], expected)
            # Payday salary and non-bill debit are separate from the bill debit.
            self.assertEqual(tomorrow['salary_inflow'], PROFILE['monthly_salary'])
            self.assertEqual(tomorrow['predicted_spend'], 100)
            self.assertEqual(tomorrow['projected_balance'], 20000-100-expected+20000)
            self.assertEqual(forecast(PROFILE, state), path)

    def test_calendar_lags_use_real_days_and_distinguish_missing_zero_and_bills(self):
        now = datetime(2026, 10, 28, tzinfo=TZ)
        history = aggregate_non_bill([
            dict(date='2026-10-27', category='rent', direction='DR', amount=-3000),
            dict(date='2026-10-25', category='food_daily', direction='DR', amount=-120),
            dict(date='2026-10-25', category='transport', direction='DR', amount=-30),
            dict(date='2026-10-25', category='salary', direction='CR', amount=20000),
        ], complete_dates=['2026-10-27', '2026-10-25'])
        features = flow_features(now, history, PROFILE, {})
        self.assertEqual(features.dtype, np.float32)
        self.assertEqual(features.shape, (1, 6))
        self.assertEqual(features[0, 0], 0)  # model payday semantics
        self.assertEqual(features[0, 3], 0)  # observed, bill-only day
        self.assertEqual(features[0, 4], 150)
        self.assertTrue(np.isnan(features[0, 5]))
        self.assertEqual(horizon(PROFILE, dict(main_balance=20000, daily_spent_today=0))['daily_budget_method'],
                         'BALANCE_PLUS_TODAY_SPEND_MINUS_BILLS_AND_BUFFER_DIVIDED_BY_DAYS')

    def test_recursive_lags_include_only_predictions_on_exact_calendar_dates(self):
        now = datetime(2026, 12, 27, tzinfo=TZ)
        history = {'2026-12-27': 7, '2026-12-25': 5, '2026-12-21': 1}
        seen = []
        def predict(features):
            seen.append(features.copy())
            return len(seen)*10
        result = recursive_spending(now, history, PROFILE, {}, predict, days=8)
        np.testing.assert_allclose(seen[0][0, 3:], [7, 5, 1])
        self.assertEqual(seen[3][0, 3], 30)
        self.assertEqual(seen[3][0, 4], 10)
        self.assertTrue(np.isnan(seen[3][0, 5]))
        self.assertEqual(seen[7][0, 5], 10)
        self.assertEqual(result[0][0].day, 28)
        self.assertEqual(seen[0][0, 0], 0)
        self.assertNotIn('2026-12-28', history)


class PackageIntegrityTests(unittest.TestCase):
    def test_legacy_rollback_loads_only_its_original_pair(self):
        root = Path(backend.BASE_DIR)/'models/legacy'
        session, embeddings = load_legacy(root, backend.SERVING_CONFIG['legacy_hashes'])
        features = np.zeros((1,24),dtype=np.float32)
        features[0,8:] = embeddings['ACC_0101']
        outputs = session.run(None,{session.get_inputs()[0].name:features})
        self.assertTrue(0 <= outputs[1][0][1] <= 1)
        with self.assertRaises(ValueError):
            load_legacy(root, {**backend.SERVING_CONFIG['legacy_hashes'], 'trustgraph_embeddings.csv':'0'*64})

    def test_approved_package_contract_and_reference_shapes(self):
        manifest, sessions, embeddings = load_package(backend.PACKAGE_DIR, backend.SERVING_CONFIG['manifest_sha256'])
        self.assertEqual(len(manifest['hashes']), 13)
        self.assertTrue(all(v.shape == (16,) and v.dtype == np.float32 for v in embeddings.values()))
        for name, size, output in [('flowsense', 6, 'variable'), ('trustgraph', 24, 'probabilities')]:
            fixture = np.load(backend.PACKAGE_DIR / f'{name}_parity_inputs.npy')
            self.assertEqual(fixture.dtype, np.float32)
            self.assertEqual(fixture.shape[1], size)
            predictions = sessions[name].run([output], {'float_input': fixture})[0]
            self.assertEqual(predictions.shape, (len(fixture), 1 if name == 'flowsense' else 2))
            self.assertTrue(np.isfinite(predictions).all())

    def test_corrupted_hash_mixed_embedding_and_changed_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)/'package'
            shutil.copytree(backend.PACKAGE_DIR, directory)
            for name in ('trustgraph.onnx', 'flowsense.onnx', 'trustgraph_embeddings.csv', 'manifest.json'):
                path = directory/name
                original = path.read_bytes()
                if name == 'trustgraph_embeddings.csv':
                    path.write_bytes((Path(backend.BASE_DIR)/'models/legacy/trustgraph_embeddings.csv').read_bytes())
                else:
                    path.write_bytes(original+b'corruption')
                with self.assertRaises(ValueError):
                    load_package(directory, backend.SERVING_CONFIG['manifest_sha256'])
                path.write_bytes(original)


class HandoffHTTPTests(unittest.TestCase):
    def setUp(self):
        self.clock = patch('src.flowsense_engine.datetime')
        self.datetime = self.clock.start()
        self.datetime.now.return_value = datetime(2026, 10, 21, tzinfo=TZ)
        self.client = TestClient(backend.app)
        self.client.__enter__()
        self.csrf = self.client.get('/api/v2/session').json()['csrf_token']
        layer = backend.app.middleware_stack
        while not isinstance(layer, security.DemoSessionMiddleware):
            layer = layer.app
        self.session = layer.sessions[self.client.cookies[security.COOKIE_NAME]]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.clock.stop()

    def post(self, path, body, key=None):
        return self.client.post('/api/v2'+path, json=body, headers={
            'X-CSRF-Token': self.csrf, 'X-Idempotency-Key': key or secrets.token_hex(16)})

    def test_replay_after_40_commands_collision_and_full_capacity_are_fail_closed(self):
        state = self.session.accounts['ACC_0100']
        key = secrets.token_hex(16)
        body = dict(account_id='ACC_0100', amount=1)
        original = state['main_balance']
        first = self.post('/flowsense/vault/withdraw', body, key)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers['X-Idempotency-Result'], 'recorded')
        with patch.object(security, 'SESSION_RATE', 1):
            admission = self.post('/flowsense/vault/withdraw', body, key)
            self.assertEqual(admission.status_code, 429)
            self.assertNotIn('X-Idempotency-Result', admission.headers)
        self.assertEqual(self.post('/flowsense/vault/withdraw', body, key).json(), first.json())
        for i in range(40):
            self.assertEqual(self.post('/flowsense/savings-preference', dict(account_id='ACC_0100', enabled=bool(i%2))).status_code, 200)
        replay = self.post('/flowsense/vault/withdraw', body, key)
        self.assertEqual(replay.json()['code'], 'RESULT_EVICTED')
        self.assertEqual(state['main_balance'], original+1)
        self.assertEqual(self.post('/flowsense/vault/withdraw', {**body, 'amount': 2}, key).status_code, 409)
        with patch.object(security, 'MAX_COMMANDS', len(self.session.commands)):
            self.assertEqual(self.post('/flowsense/vault/withdraw', body).json()['code'], 'COMMAND_CAPACITY')
        self.assertLessEqual(len(self.session.replies), 32)
        self.assertLessEqual(self.session.reply_bytes, security.MAX_REPLY_BYTES)
        self.assertEqual(state['main_balance'], original+1)


    def test_exception_after_mutation_leaves_a_tombstone_and_session_expiry_never_replays(self):
        state = self.session.accounts['ACC_0100']
        body = dict(account_id='ACC_0100', amount=1)
        key = secrets.token_hex(16)
        before = state['main_balance']
        with patch.object(backend, 'audit_log', side_effect=RuntimeError('lost after mutation')):
            with self.assertRaises(RuntimeError):
                self.post('/flowsense/vault/withdraw', body, key)
        self.assertEqual(state['main_balance'], before+1)
        self.assertEqual(self.post('/flowsense/vault/withdraw', body, key).json()['code'], 'RESULT_EVICTED')
        self.assertEqual(state['main_balance'], before+1)
        self.session.expires = 0
        self.assertEqual(self.post('/flowsense/vault/withdraw', body, key).json()['code'], 'SESSION_EXPIRED')
        self.assertEqual(state['main_balance'], before+1)

    def test_missing_context_uses_exactly_16_zero_features_and_keeps_policy_separate(self):
        with patch.dict(backend.FEATURE_STORE_CACHE, {}, clear=True), patch.object(backend,'sentinel_sess',wraps=backend.sentinel_sess) as model:
            result = self.post('/trustgraph/evaluate-transfer',dict(source_account_id='ACC_0100',target_account_id='ACC_0001',amount=100)).json()
            vector = model.run.call_args[0][1]['float_input']
            self.assertEqual(vector.dtype,np.float32)
            self.assertEqual(vector.shape,(1,24))
            np.testing.assert_array_equal(vector[0,8:],np.zeros(16,dtype=np.float32))
            self.assertTrue(result['missing_graph_context'])
            self.assertGreaterEqual(result['policy_score'],result['raw_model_score'])
            self.assertEqual(result['synthetic_score_floor'],.45)

    def test_three_personas_main_paths_and_missing_context_are_distinct_from_unknown(self):
        for source, target in [('ACC_0100','ACC_0101'), ('ACC_0101','ACC_0150'), ('ACC_0150','ACC_0100')]:
            self.assertEqual(self.post('/flowsense/scenario', dict(account_id=source, scenario='healthy')).status_code, 200)
            self.assertEqual(self.post('/flowsense/savings-preference', dict(account_id=source, enabled=True)).status_code, 200)
            before = copy.deepcopy(self.session.accounts[source])
            self.assertEqual(self.post('/flowsense/micro-sweep', dict(account_id=source, custom_sweep_amount=100)).status_code, 200)
            self.assertEqual(self.post('/flowsense/vault/withdraw', dict(account_id=source, amount=100)).status_code, 200)
            self.assertEqual(before['main_balance'], self.session.accounts[source]['main_balance'])
            payload = dict(source_account_id=source, target_account_id=target, amount=100, is_first_time_transfer=0, session_duration_sec=90, ratio_to_daily_avg=1.1)
            with patch.dict(backend.FEATURE_STORE_CACHE, {}, clear=True):
                result = self.post('/trustgraph/evaluate-transfer', payload).json()
                self.assertTrue(result['missing_graph_context'])
                self.assertEqual(result['model_package_version'], '2026.10.27.1')
                self.assertIn('ไม่ใช่ attribution', result['explanation_note'])
                self.assertIn('raw_model_score', result)
            self.assertEqual(before['main_balance'], self.session.accounts[source]['main_balance'])
            proof = {k:payload[k] for k in ('source_account_id','target_account_id','amount')}
            self.assertEqual(self.post('/trustgraph/confirm-transfer', {**proof,'decision':'CANCEL'}).status_code, 200)
            self.assertEqual(before['main_balance'], self.session.accounts[source]['main_balance'])
            result = self.post('/trustgraph/evaluate-transfer', payload).json()
            self.assertEqual(result['status'], 'TRANSFER_REVIEW')
            confirmation = {**proof, 'decision':'PROCEED', 'review_token':result['review_token']}
            key = secrets.token_hex(16)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.post('/trustgraph/confirm-transfer',confirmation,key),range(2)))
            self.assertTrue(all(r.status_code == 200 for r in results))
            self.assertEqual(results[0].json()['receipt_id'], results[1].json()['receipt_id'])
            self.assertEqual(self.session.accounts[source]['main_balance'], before['main_balance']-100)
            self.assertIn('ไม่มีการโอนเงินจริง', results[0].json()['message'])
        snapshot = copy.deepcopy(self.session.accounts)
        self.assertEqual(self.post('/trustgraph/evaluate-transfer', {**payload, 'target_account_id':'ACC_UNKNOWN'}).status_code, 422)
        self.assertEqual(snapshot, self.session.accounts)

    def test_http_overdue_partial_full_and_views_stay_consistent(self):
        source='ACC_0100'
        profile_patch = patch.dict(backend.BEHAVIORAL_PROFILES_CACHE[source], PROFILE)
        profile_patch.start()
        self.addCleanup(profile_patch.stop)
        self.post('/flowsense/reset-state/'+source, {})
        self.session.accounts[source].update(main_balance=100000, daily_spent_today=0)
        def view():
            return self.client.get('/api/v2/flowsense/horizon-status/'+source).json()
        bill = next(b for b in view()['recurring_commitments'] if b['kind']=='debt')
        self.datetime.now.return_value = datetime(2026, 11, 23, tzinfo=TZ)
        before = view()
        self.assertEqual(len([b for b in before['recurring_commitments'] if b['kind']=='debt']),2)
        half = round(bill['amount']/2,2)
        for amount in (half, round(bill['amount']-half,2)):
            payload=dict(source_account_id=source,target_account_id='ACC_0101',amount=amount,
                matched_bill_id=bill['id'],is_first_time_transfer=0,session_duration_sec=90,ratio_to_daily_avg=1.1)
            review=self.post('/trustgraph/evaluate-transfer',payload).json()
            self.assertEqual(review['status'],'TRANSFER_REVIEW')
            self.assertEqual(review['liquidity_impact']['before']['bills_remaining'],view()['total_recurring_commitments'])
            result=self.post('/trustgraph/confirm-transfer',dict(source_account_id=source,target_account_id='ACC_0101',amount=amount,decision='PROCEED',review_token=review['review_token']))
            self.assertEqual(result.status_code,200,result.text)
        after=view()
        self.assertEqual(after['total_recurring_commitments'],round(before['total_recurring_commitments']-bill['amount'],2))
        self.assertFalse(any(b['id']==bill['id'] for b in after['recurring_commitments']))
