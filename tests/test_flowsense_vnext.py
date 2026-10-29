"""Consumer regressions beyond sealed fixtures. Never imports production startup."""
import ast
import copy
from dataclasses import FrozenInstanceError
from datetime import date
from itertools import permutations
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from src.flowsense_vnext.boundary import (PIN, Rejected, canonical, decode, digest, normalize, shape)
from src.flowsense_vnext.ingestion import prepare
from src.flowsense_vnext.files import ROLES, FULL_ROLES, read_data_bundle
from src.flowsense_vnext.issuance import IssueRegistry
from src.flowsense_vnext.projection import (TracePredictor, aggregate, features_only, float32_row,
                                          forecast, planning_next_payday)
from src.flowsense_vnext.response import validate_response

ROOT = Path(__file__).resolve().parents[1]
CASES = {c['id']: c for c in decode((PIN / 'fixtures.json').read_bytes())['cases']}


def request(name='N7-mean'):
    return copy.deepcopy(CASES[name]['request'])


class ConsumerTests(unittest.TestCase):
    def rejected(self, reason, fn, *args, **kwargs):
        with self.assertRaises(Rejected) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.reason, reason)

    def test_nested_duplicate_json_keys_rejected(self):
        self.rejected('DUPLICATE_JSON_KEY', decode, b'{"opening":{"x":1,"x":2}}')

    def test_all_nonfinite_wire_forms_rejected(self):
        for raw in ('NaN', 'Infinity', '-Infinity', '1e999'):
            self.rejected('NONFINITE_WIRE', decode, '{"value":' + raw + '}')
        self.rejected('NONFINITE_WIRE', prepare, {'x': float('nan')})

    def test_invalid_json_is_stable(self):
        self.rejected('INVALID_JSON', decode, b'{')

    def test_schema_rejects_boolean_revision_and_unknown_fields(self):
        q = request()
        q['transactions'][0]['revision'] = True
        self.rejected('SCHEMA_INVALID', prepare, q)
        q = request()
        q['session'] = {'main_balance': 1}
        self.rejected('SCHEMA_INVALID', prepare, q)

    def test_money_normalization_preserves_cents_and_never_rounds_ledger(self):
        self.assertEqual(normalize('-300'), ('-300.00', -30000))
        self.assertEqual(normalize('-0.01'), ('-0.01', -1))
        for raw in ('-1.005', '-1.000', '+1', ' 1', '1e2', '01', 'NaN'):
            self.rejected('INVALID_RAW_PRECISION', normalize, raw)
        self.rejected('ZERO_AMOUNT', normalize, '-0.00')

    def test_input_and_session_immutable_and_frozen_state_has_no_aliases(self):
        q, session = request(), {'main_balance': 123, 'bills': [], 'daily_spent_today': 99}
        before = copy.deepcopy((q, session))
        state = prepare(q)
        forecast(q)
        self.assertEqual((q, session), before)
        q['transactions'][0]['raw_amount_thb'] = '-999'
        self.assertEqual(dict(state.history)['2026-10-26'], 30000)
        with self.assertRaises(FrozenInstanceError):
            state.request_bytes = b'{}'

    def test_future_actual_and_correction_poison_cannot_change_origin_points(self):
        base = forecast(request())
        for name in ('future-actual-poison', 'correction-known-after-origin'):
            result = forecast(request(name))
            self.assertEqual(result['points'], base['points'])
            self.assertEqual(result['aggregate']['numerator_satang'], 30000)

    def test_revision_order_independent_and_all_duplicate_orderings_rejected(self):
        q = request('source-correction-latest')
        expected = prepare(q).history
        for rows in permutations(q['transactions']):
            q['transactions'] = list(rows)
            self.assertEqual(prepare(q).history, expected)
        # Put repeated revision around another revision; audit losers too.
        q = request('source-correction-latest')
        rows = [q['transactions'][0], q['transactions'][1], copy.deepcopy(q['transactions'][0])]
        for ordering in permutations(rows):
            q['transactions'] = list(ordering)
            self.rejected('TRANSACTION_DUPLICATE_REVISION', prepare, q)

    def test_coverage_duplicate_loser_revision_is_not_hidden(self):
        q = request('latest-coverage-revision')
        q['coverage'].append(copy.deepcopy(q['coverage'][-2]))
        self.rejected('COVERAGE_DUPLICATE_REVISION', prepare, q)

    def test_mapping_rejection_precedes_mock_and_fallback(self):
        q = request('N6-scenario')
        q['mappings'] = []
        def forbidden(*args):
            self.fail('mock must not execute before mapping validation')
        self.rejected('UNKNOWN_MAPPING', forecast, q, mock_predictor=forbidden)

    def test_sparse_overlap_and_adjacent_mapping_intervals(self):
        self.rejected('OVERLAPPING_MAPPING', prepare, request('mapping-sparse-overlap'))
        self.assertEqual(dict(prepare(request('mapping-adjacent-intervals')).history)['2026-10-26'], 30000)

    def test_illustration_history_and_modulo_mapping_cannot_enter(self):
        q = request()
        q['history_source'] = 'SYNTHETIC_PROFILE_ILLUSTRATION'
        self.rejected('SCHEMA_INVALID', prepare, q)
        self.rejected('FIXTURE_MAPPING', prepare, request('fixture-mapping-rejected'))

    def test_midnight_and_day_end_equality(self):
        q = request('boundary-equality')
        self.assertEqual(dict(prepare(q).history)['2026-10-26'], 30000)
        for origin in ('2026-10-27T00:00:01+07:00', '2026-10-27T00:00:00Z'):
            q['origin'] = origin
            self.rejected('SCHEMA_INVALID', prepare, q)

    def test_all_sources_required_even_zero_row_source(self):
        q = request()
        q['source_registry']['sources'].append('empty-export')
        state = prepare(q)
        self.assertIsNone(dict(state.history)['2026-10-26'])
        self.assertIn('MISSING_COVERAGE_SOURCE', dict(state.day_reasons)['2026-10-26'])

    def test_known_empty_zero_and_unknown_are_distinct(self):
        state = prepare(request('coverage-partial'))
        self.assertIsNone(dict(state.history)['2026-10-26'])
        self.assertEqual(dict(state.history)['2026-10-25'], 0)
        mean = aggregate(state)
        self.assertEqual(mean.complete_known_days, 6)
        self.assertIsNone(mean.mean_satang)

    def test_cross_source_and_cross_day_charge_order_independent(self):
        q = request('cross-day-charge-dedup')
        expected = prepare(q).diagnostic()
        q['transactions'].reverse()
        self.assertEqual(prepare(q).diagnostic(), expected)
        self.assertIsNone(expected['history']['2026-10-25'])
        self.assertIsNone(expected['history']['2026-10-26'])

    def test_any_selected_dr_overlap_includes_invalid_raw_row(self):
        # C01.T1 ANY selected DR overlap, even if one also fails normalization.
        q = request('cross-day-charge-dedup')
        q['transactions'][0]['raw_amount_thb'] = '-1.005'
        result = prepare(q).diagnostic()
        for target in ('2026-10-25', '2026-10-26'):
            self.assertIsNone(result['history'][target])
            self.assertIn('DUPLICATE_ECONOMIC_CHARGE', result['day_reasons'][target])

    def test_correction_replaces_charge_representation_not_summed(self):
        q = request('source-correction-latest')
        result = prepare(q)
        self.assertEqual(dict(result.history)['2026-10-26'], 28000)

    def test_refund_is_distinct_credit_and_does_not_net_gross(self):
        q = request('linked-refund')
        self.assertEqual(dict(prepare(q).history)['2026-10-26'], 30000)
        q['transactions'].reverse()
        self.assertEqual(dict(prepare(q).history)['2026-10-26'], 30000)

    def test_exhaustive_declared_interval_and_h30_plus35(self):
        q = request('horizon-30')
        result = forecast(q)
        self.assertEqual(result['points'][-1]['date'], '2026-11-25')
        q['bill_calendar']['materialized_through'] = '2026-11-30'
        self.rejected('SHORT_BILL_LOOKAHEAD', prepare, q)
        q['bill_calendar']['materialized_through'] = '2026-12-27'
        self.rejected('MISSING_BILL_ID', prepare, q)

    def test_copied_prior_overdue_and_current_are_paid_once_with_negative_raw_balance(self):
        q = request('old-overdue-plus-current-deficit')
        before = copy.deepcopy(q)
        result = forecast(q)
        self.assertEqual(result['points'][0]['bill_payment_thb'], 1700)
        self.assertEqual(result['points'][0]['projected_balance_thb'], -742.86)
        self.assertEqual(result['points'][1]['bill_payment_thb'], 0)
        self.assertEqual(q, before)

    def test_prepayment_feature_then_salary_bill_and_next_day_state(self):
        points = forecast(request())['points']
        self.assertEqual(points[0]['feature_row'][:3], [1, 1, 0])
        self.assertEqual(points[1]['feature_row'][:3], [0, 0, 0])
        self.assertEqual(points[1]['salary_inflow_thb'], 20000)
        self.assertEqual(points[1]['projected_balance_thb'], 43414.28)
        self.assertEqual(planning_next_payday(date(2026, 10, 28)), date(2026, 11, 28))

    def test_year_leap_and_nonleap_h30_calendar(self):
        for name, end in (('calendar-h30-2026-12-27', '2027-01-25'),
                          ('calendar-h30-2027-02-01', '2027-03-02'),
                          ('calendar-h30-2028-02-01', '2028-03-01')):
            self.assertEqual(forecast(request(name))['points'][-1]['date'], end)

    def test_aggregate_is_origin_frozen_including_n28_zero(self):
        q = request('N28-complete-zero')
        result = forecast(q)
        self.assertEqual(result['aggregate']['complete_known_days'], 28)
        self.assertEqual(result['aggregate']['mean_satang'], 0)
        self.assertEqual(result['aggregate']['numerator_satang'], 0)
        q = request('horizon-30')
        self.assertEqual(forecast(q)['aggregate']['complete_known_days'], 7)

    def test_min7_mean_precedes_scenario_and_preserves_exact_numerator(self):
        q = request('N6-scenario')
        q['coverage'] = request()['coverage']
        result = forecast(q)
        self.assertEqual(result['aggregate']['numerator_satang'], 30000)
        self.assertEqual(result['aggregate']['complete_known_days'], 7)
        self.assertEqual(result['points'][0]['method'], 'HISTORY_MEAN')

    def test_partial_eligibility_does_not_authorize_mock(self):
        q = request('partial-lags-not-eligible')
        def forbidden(*args):
            self.fail('ineligible mock called')
        result = forecast(q, mock_predictor=forbidden)
        self.assertEqual(result['points'][0]['selection_reason'], 'MODEL_NOT_ELIGIBLE')
        self.assertEqual(result['points'][0]['method'], 'SCENARIO')

    def test_all_missing_lags_prevent_mock_even_with_eligibility_claim(self):
        q = request('all-lags-unknown-abstain')
        q['model_eligibility'] = request('half-up-recursive-feedback')['model_eligibility']
        def forbidden(*args):
            self.fail('all missing lags must not invoke mock')
        self.assertEqual(forecast(q, mock_predictor=forbidden)['points'][0]['method'], 'ABSTAIN')

    def test_float32_actual_boundary_and_nan_only_in_lags(self):
        row = float32_row([0, 1, 0, 1.01, None, 0])
        self.assertAlmostEqual(row[3], 1.0099999904632568)
        self.assertTrue(math.isnan(row[4]))
        self.rejected('NONFINITE_TENSOR_COLUMN', float32_row, [None, 1, 0, 1, 2, 3])
        self.rejected('NONFINITE_TENSOR_COLUMN', float32_row, [0, 1, 0, float('nan'), 2, 3])
        self.rejected('FLOAT32_OVERFLOW', float32_row, [0, 1, 0, 1e100, None, 0])

    def test_mock_receives_only_frozen_rounded_calendar_features(self):
        seen = []
        def predictor(index, target, tensor):
            self.assertIsInstance(tensor, tuple)
            seen.append((target, tensor))
            return '1.005'
        result = forecast(request('half-up-recursive-feedback'), mock_predictor=predictor)
        self.assertEqual(seen[0][0], '2026-10-27')
        self.assertEqual(result['points'][1]['feature_row'][3], 1.01)
        self.assertEqual(result['points'][-1]['cumulative_non_bill_thb'], 7.07)
        self.assertEqual(result['points'][0]['method'], 'MOCK')
        self.assertIsNone(result['model_package_version'])

    def test_nonfinite_mock_fallback_and_first_abstention_propagation(self):
        case = CASES['first-abstention-middle']
        q = request('first-abstention-middle')
        result = forecast(q, mock_predictor=TracePredictor(tuple(case['mock_predictions'])))
        self.assertEqual(result['points'][1]['selection_reason'], 'NONFINITE_MOCK_PREDICTION')
        self.assertEqual(result['points'][2]['predicted_non_bill_thb'], 2)
        self.assertTrue(all(p['cumulative_non_bill_thb'] is None and p['projected_balance_thb'] is None
                            for p in result['points'][1:]))
        self.assertEqual(result['forecast_dependent_claim'], 'UNAVAILABLE')

    def test_feature_only_rejects_forecast_extras(self):
        q = request('feature-only-envelope')
        self.assertIsNone(features_only(q)['prediction_thb'])
        q['opening_balance'] = request()['opening_balance']
        self.rejected('SCHEMA_INVALID', prepare, q)

    def test_issued_registry_persists_rejects_new_id_same_origin_and_late_correction(self):
        q = request()
        response = forecast(q)
        with tempfile.TemporaryDirectory(dir=PIN.parent) as folder:
            self.assertEqual(Path(folder).resolve().parent, PIN.parent.resolve())
            path = Path(folder) / 'issued.sqlite'
            store = IssueRegistry(path)
            original = store.issue(q, response)
            self.assertEqual(IssueRegistry(path).read(q['account_id'], q['origin']), original)
            self.assertEqual(store.issue(q, response), original)
            changed = forecast(q, forecast_id='invented-new-id')
            self.rejected('ISSUED_SNAPSHOT_IMMUTABLE', store.issue, q, changed)
            q['transactions'][0]['raw_amount_thb'] = '-299'
            q['transactions'][0]['signed_amount_thb'] = '-299.00'
            self.rejected('ISSUED_SNAPSHOT_IMMUTABLE', store.issue, q, forecast(q))
            self.assertEqual(IssueRegistry(path).read(original.account_id, original.origin), original)

    def test_previous_issue_cannot_be_replaced(self):
        q = request()
        old = forecast(q)
        self.rejected('ISSUED_SNAPSHOT_IMMUTABLE', validate_response, q,
                      forecast(q, forecast_id='new'), previous_issue=old)

    def test_hash_verified_data_bundle_reads_actual_sidecar_files(self):
        bundle = PIN.parent / 'examples/valid-data-bundle'
        state = read_data_bundle(bundle)
        self.assertEqual(dict(state.history)['2026-10-26'], 30000)
        self.assertEqual(forecast(state.request_bytes)['points'][6]['projected_balance_thb'], 43199.98)

    def test_data_file_tampering_and_field_collision_rejected(self):
        import hashlib
        import shutil
        with tempfile.TemporaryDirectory(dir=PIN.parent) as folder:
            root = Path(folder).resolve()
            self.assertEqual(root.parent, PIN.parent.resolve())
            source = PIN.parent / 'examples/valid-data-bundle'
            for path in source.iterdir():
                shutil.copyfile(path, root / path.name)
            (root / 'ledger.json').write_text('[]', encoding='utf-8')
            self.rejected('DATA_BUNDLE_HASH_MISMATCH', read_data_bundle, root)
            shutil.copyfile(source / 'ledger.json', root / 'ledger.json')
            core = decode((root / 'request-core.json').read_bytes())
            core['transactions'] = []
            raw = canonical(core)
            (root / 'request-core.json').write_bytes(raw)
            manifest = decode((root / 'bundle-manifest.json').read_bytes())
            manifest['files']['request-core.json'] = hashlib.sha256(raw).hexdigest()
            (root / 'bundle-manifest.json').write_bytes(canonical(manifest))
            self.rejected('DATA_BUNDLE_FIELD_COLLISION', read_data_bundle, root)

    def test_file_manifest_cannot_select_a_parent_or_unlisted_ledger(self):
        with tempfile.TemporaryDirectory(dir=PIN.parent) as folder:
            root = Path(folder).resolve()
            self.assertEqual(root.parent, PIN.parent.resolve())
            manifest = {'contract_version': '2.0.0-proposed.2', 'request_kind': 'FULL_FORECAST',
                        'files': {'../ledger.json': 'a' * 64}}
            (root / 'bundle-manifest.json').write_bytes(canonical(manifest))
            self.rejected('DATA_BUNDLE_FILES', read_data_bundle, root)

    def test_response_unknown_balance_never_zero_and_money_not_silently_rounded(self):
        q = request('N6-no-scenario')
        response = forecast(q)
        response['points'][0]['projected_balance_thb'] = 0
        self.rejected('BALANCE_OR_NULL_MISMATCH', validate_response, q, response)
        q = request()
        response = forecast(q)
        response['points'][0]['predicted_non_bill_thb'] = 1.005
        self.rejected('WIRE_MONEY_PRECISION', validate_response, q, response)

    def test_no_model_or_producer_imports_no_runtime_wiring_and_startup_guard(self):
        self.assertFalse(any(n in sys.modules for n in ('onnxruntime', 'torch', 'lightgbm', 'src.app_v2',
                                                        'src.model_package', 'semantic_validator')))
        for path in (ROOT / 'src').rglob('*.py'):
            if 'flowsense_vnext' not in path.parts and path.name != 'baseline_policy.py':
                self.assertNotIn('flowsense_vnext', path.read_text(encoding='utf-8-sig'), str(path))
        tree = ast.parse((ROOT / 'src/app_v2.py').read_text(encoding='utf-8-sig'))
        guard = next(n for n in tree.body if isinstance(n, ast.If) and
                     "SERVING_CONFIG.get('flowsense_enabled')" in ast.unparse(n.test))
        loads = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Name) and n.func.id == 'load_package']
        self.assertTrue(all(line > guard.lineno for line in loads))
        with self.assertRaisesRegex(RuntimeError, 'calendar revalidation'):
            exec(compile(ast.Module(body=[guard], type_ignores=[]), 'guard-only', 'exec'),
                 {'SERVING_CONFIG': {'flowsense_enabled': True}})
        self.assertFalse(json.loads((ROOT / 'models/serving.json').read_text())['flowsense_enabled'])


if __name__ == '__main__':
    unittest.main()
