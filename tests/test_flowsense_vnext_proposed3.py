"""Targeted revision dispatch, real sidecar bytes and C01 overlap invariants."""
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.flowsense_vnext.boundary import REVISIONS, Rejected, _validator, canonical, decode, shape
from src.flowsense_vnext.files import read_data_bundle
from src.flowsense_vnext.ingestion import prepare
from src.flowsense_vnext.projection import features_only, forecast
from src.flowsense_vnext.response import validate_response

ROOT = Path(__file__).resolve().parents[1]
VERSION = '2.0.0-proposed.3'
OUT = ROOT / 'docs/contracts/flowsense-vnext-review/proposed.3'
CASES = decode((OUT / 'pinned/targeted-fixtures.json').read_bytes())['cases']


def request():
    return decode((OUT / 'examples/valid-wire.json').read_bytes())


class Proposed3Tests(unittest.TestCase):
    def rejected(self, reason, call, *args, **kwargs):
        with self.assertRaises(Rejected) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.reason, reason)

    def temporary(self):
        temp = tempfile.TemporaryDirectory(dir=OUT)
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def bundle(self):
        return Path(shutil.copytree(OUT / 'examples/valid-data-bundle', self.temporary() / 'bundle'))

    def rewrite(self, folder, name, value):
        raw = canonical(value)
        (folder / name).write_bytes(raw)
        manifest = decode((folder / 'bundle-manifest.json').read_bytes())
        manifest['files'][name] = hashlib.sha256(raw).hexdigest()
        (folder / 'bundle-manifest.json').write_bytes(canonical(manifest))

    def test_both_revisions_emit_and_validate_own_versions(self):
        # This historical regression owns the two pre-amendment envelopes.
        # proposed.4 requires source capabilities and has its own dedicated tests.
        for version in ('2.0.0-proposed.2', '2.0.0-proposed.3'):
            info = REVISIONS[version]
            q = decode((info['pin'] / 'forecast-request-example.json').read_bytes())
            response = forecast(q)
            self.assertEqual(response['contract_version'], version)
            validate_response(q, response)
            # A response from the other accepted revision still cannot cross routes.
            response['contract_version'] = next(v for v in REVISIONS if v != version)
            self.rejected('SCHEMA_INVALID', validate_response, q, response)

    def test_feature_only_schema_and_output_follow_proposed3(self):
        cases = decode((OUT / 'pinned/fixtures.json').read_bytes())['cases']
        q = next(c['request'] for c in cases if c['id'] == 'feature-only-envelope')
        response = features_only(q)
        self.assertEqual(response['contract_version'], VERSION)
        shape(response, response=True)
        validate_response(q, response)

    def test_arbitrary_or_malformed_versions_fail_without_fallback(self):
        for version in ('2.0.0-proposed.1', '2.0.0-proposed.4', '2.0.0', None, [], {}):
            q = request()
            q['contract_version'] = version
            self.rejected('SCHEMA_INVALID', prepare, q)

    def test_schemas_are_read_from_verified_revision_hash_mapping(self):
        folder = self.temporary()
        for name in ('revision-manifest.json', 'contract.json', 'forecast.request.schema.json'):
            shutil.copyfile(OUT / 'pinned' / name, folder / name)
        (folder / 'forecast.request.schema.json').write_bytes(b'{}\n')
        info = {**REVISIONS[VERSION], 'pin': folder}
        _validator.cache_clear()
        self.addCleanup(_validator.cache_clear)
        with patch.dict(REVISIONS, {VERSION: info}):
            self.rejected('PIN_HASH_MISMATCH', prepare, request())

    def test_valid_sidecars_equal_wire_and_use_same_prepare_path(self):
        folder = OUT / 'examples/valid-data-bundle'
        manifest = decode((folder / 'bundle-manifest.json').read_bytes())
        for name, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), expected)
        state = read_data_bundle(folder, expected_version=VERSION)
        self.assertEqual(state, prepare((OUT / 'examples/valid-wire.json').read_bytes()))
        result = forecast(state.request_bytes)
        validate_response(state.request_bytes, result)
        self.assertEqual(result['points'][6]['projected_balance_thb'], 43199.98)

    def test_actual_invalid_sidecar_examples_reject(self):
        for name, reason in [('invalid-hash-data-bundle', 'DATA_BUNDLE_HASH_MISMATCH'),
                             ('invalid-version-data-bundle', 'DATA_BUNDLE_MANIFEST'),
                             ('invalid-manifest-core-data-bundle', 'DATA_BUNDLE_MANIFEST')]:
            self.rejected(reason, read_data_bundle, OUT / 'examples' / name, expected_version=VERSION)

    def test_valid_old_bundle_is_not_a_proposed3_fallback(self):
        old = REVISIONS['2.0.0-proposed.2']['pin'].parent / 'examples/valid-data-bundle'
        self.rejected('DATA_BUNDLE_VERSION_MISMATCH', read_data_bundle, old, expected_version=VERSION)
        self.assertEqual(decode(read_data_bundle(old).request_bytes)['contract_version'], '2.0.0-proposed.2')

    def test_supported_manifest_core_version_mismatch_in_both_directions(self):
        folder = self.bundle()
        core = decode((folder / 'request-core.json').read_bytes())
        core['contract_version'] = '2.0.0-proposed.2'
        self.rewrite(folder, 'request-core.json', core)
        self.rejected('DATA_BUNDLE_MANIFEST', read_data_bundle, folder)
        core['contract_version'] = VERSION
        self.rewrite(folder, 'request-core.json', core)
        manifest = decode((folder / 'bundle-manifest.json').read_bytes())
        manifest['contract_version'] = '2.0.0-proposed.2'
        (folder / 'bundle-manifest.json').write_bytes(canonical(manifest))
        self.rejected('DATA_BUNDLE_MANIFEST', read_data_bundle, folder)

    def test_manifest_kind_mismatch_and_missing_sidecar_reject(self):
        folder = self.bundle()
        core = decode((folder / 'request-core.json').read_bytes())
        core['request_kind'] = 'FEATURE_ONLY'
        self.rewrite(folder, 'request-core.json', core)
        self.rejected('DATA_BUNDLE_MANIFEST', read_data_bundle, folder)
        manifest = decode((folder / 'bundle-manifest.json').read_bytes())
        del manifest['files']['ledger.json']
        (folder / 'bundle-manifest.json').write_bytes(canonical(manifest))
        self.rejected('DATA_BUNDLE_FILES', read_data_bundle, folder)

    def test_original_conflict_retains_exact_ledger_and_expected_reasons(self):
        original = decode((OUT.parent / 'proposed.2/conflict-C01-request.json').read_bytes())
        original['contract_version'] = VERSION
        case = next(c for c in CASES if c['id'] == 'consumer-C01-invalid-row-charge-overlap')
        self.assertEqual(original, case['request'])
        result = prepare(original).diagnostic()
        self.assertEqual({d: result['history'][d] for d in case['expected']['history']}, case['expected']['history'])
        for target, reasons in case['expected']['day_reasons'].items():
            self.assertEqual(result['day_reasons'][target], reasons)
        self.assertIn('INVALID_RAW_PRECISION', result['day_reasons']['2026-10-26'])

    def test_all_targeted_orderings_and_inputs_are_immutable(self):
        for case in CASES:
            q = copy.deepcopy(case['request'])
            before = canonical(q)
            if case['expected_rejection']:
                self.rejected(case['expected_rejection'], prepare, q)
                q['transactions'].reverse()
                self.rejected(case['expected_rejection'], prepare, q)
            else:
                state = prepare(q)
                response = forecast(q)
                validate_response(q, response)
                self.assertEqual(canonical(q), before, case['id'])
                q['transactions'].reverse()
                self.assertEqual(prepare(q).diagnostic(), state.diagnostic(), case['id'])
                reversed_response = forecast(q)
                self.assertEqual(reversed_response['points'], response['points'], case['id'])
            q['transactions'].reverse()
            # Reverse rejection branch once more; positive branch is now original.
            self.assertEqual(canonical(q), before, case['id'])

    def test_new_data_example_is_unvalidated_and_no_forbidden_imports(self):
        eligible = request()['model_eligibility']
        self.assertEqual((eligible['status'], eligible['package_version'], eligible['validated_horizons'], eligible['validated_cohorts']),
                         ('UNVALIDATED', None, [], []))
        self.assertFalse(any(n in sys.modules for n in ('onnxruntime', 'lightgbm', 'torch', 'semantic_validator',
                                                       'src.app_v2', 'src.model_package')))


if __name__ == '__main__':
    unittest.main()
