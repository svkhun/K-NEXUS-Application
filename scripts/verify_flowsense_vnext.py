"""Run explicitly pinned proposed.2/.3 fixtures on APPLICATION modules.

Only adapter operations: canonical JSON serialization, mock list -> immutable trace,
and the supplied response set/remove operations. No validation/projection here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1]
OUT = APP / 'docs/contracts/flowsense-vnext-review/proposed.2'
PIN = OUT / 'pinned'
sys.path.insert(0, str(APP))


def dependency_path(path=None):
    if path:
        sys.path.append(str(path))


def at(value, path):
    for component in path.split('.'):
        value = value[int(component)] if isinstance(value, list) else value[component]
    return value


def mutate(response, operations):
    result = copy.deepcopy(response)
    for operation in operations:
        target = result
        for key in operation['path'][:-1]:
            target = target[key]
        key = operation['path'][-1]
        if operation['op'] == 'remove':
            del target[key]
        else:
            target[key] = operation['value']
    return result


def run(revision='2.0.0-proposed.2', output=None):
    from src.flowsense_vnext.boundary import REVISIONS, Rejected, _validator, canonical, decode, shape
    from src.flowsense_vnext.ingestion import prepare
    from src.flowsense_vnext.projection import TracePredictor, features_only, forecast
    from src.flowsense_vnext.response import validate_response
    pin = REVISIONS[revision]['pin']
    out = output or pin.parent
    cases = decode((pin / 'fixtures.json').read_bytes())['cases']
    assert len(cases) == 109
    rows = []
    for case in cases:
        before = canonical(case)
        q = case['request']
        mock = TracePredictor(tuple(case['mock_predictions'])) if 'mock_predictions' in case else None
        schema_valid, reason, comparisons, unknowns = True, None, {}, {}
        try:
            try:
                shape(q)
            except Rejected:
                schema_valid = False
                raise
            state = prepare(canonical(q))
            unknowns = state.diagnostic()['day_reasons']
            if 'response_literal' in case:
                response = copy.deepcopy(case['response_literal'])
            elif q['request_kind'] == 'FULL_FORECAST':
                response = forecast(canonical(q), mock_predictor=mock)
            else:
                response = features_only(canonical(q))
            response = mutate(response, case.get('response_mutations', []))
            schema = ('forecast.' if q['request_kind'] == 'FULL_FORECAST' else '') + 'response.schema.json'
            if any(_validator(schema, revision).iter_errors(response)):
                schema_valid = False
            validate_response(q, response, mock_predictor=mock)
            for path, expected in case['expected'].items():
                actual = at(state.diagnostic() if path.startswith(('history.', 'day_reasons.')) else response, path)
                comparisons[path] = {'expected': expected, 'actual': actual, 'equal': expected == actual}
        except Rejected as exc:
            reason = exc.reason
        except Exception as exc:
            reason = type(exc).__name__ + ': ' + str(exc)
        immutable = canonical(case) == before
        passed = (reason == case['reason'] and schema_valid == case['schema_valid'] and immutable and
                  all(c['equal'] for c in comparisons.values()) and
                  (reason is not None or len(comparisons) == len(case['expected'])))
        category = ('negative_reject' if case['reason'] else 'day_local_unknown' if
                    any(v is None for k, v in case['expected'].items() if k.startswith('history.')) else 'positive')
        rows.append({'fixture_id': case['id'], 'clause': case['clause'], 'expected_outcome': category,
                     'group': 'migrated_existing_109', 'expected': case['expected'],
                     'status': 'PASS' if passed else 'FAIL', 'expected_reason': case['reason'], 'actual_reason': reason,
                     'expected_schema_valid': case['schema_valid'], 'actual_schema_valid': schema_valid,
                     'assertions': comparisons, 'day_reasons': unknowns, 'input_immutable': immutable})
    mutations = []
    for mutation in decode((pin / 'adversarial-mutations.json').read_bytes())['mutations']:
        row = next(r for r in rows if r['fixture_id'] == mutation['fixture_id'])
        mutations.append({**mutation, 'status': row['status'], 'actual_reason': row['actual_reason']})
    if revision == '2.0.0-proposed.3':
        targeted = decode((pin / 'targeted-fixtures.json').read_bytes())
        assert len(targeted['cases']) == 38
        for case in targeted['cases']:
            q = case['request']
            frozen = canonical(case)
            schema_valid, rejection, actual, error = True, None, None, None
            try:
                try:
                    shape(q)
                except Rejected:
                    schema_valid = False
                    raise
                # Exercise mutable in-process ingress as well as strict wire bytes.
                state = prepare(q)
                assert state == prepare(canonical(q)), 'Ingress paths disagree'
                response = forecast(q)
                validate_response(q, response)
                diagnostic = state.diagnostic()
                dates = ('2026-10-25', '2026-10-26')
                actual = {'history': {d: diagnostic['history'][d] for d in dates},
                          'day_reasons': {d: diagnostic['day_reasons'].get(d, []) for d in dates},
                          **{k: response['aggregate'][k] for k in ('numerator_satang', 'complete_known_days', 'mean_satang')},
                          'method': response['points'][0]['method'],
                          'forecast_dependent_claim': response['forecast_dependent_claim']}
                assert state == prepare(q), 'Nondeterministic preparation'
            except Rejected as exc:
                rejection = exc.reason
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            immutable = canonical(case) == frozen
            passed = (not error and immutable and schema_valid == case['schema_valid'] and
                      rejection == case['expected_rejection'] and actual == case['expected'])
            category = ('negative_reject' if case['expected_rejection'] else
                        'day_local_unknown' if None in case['expected']['history'].values() else 'positive')
            rows.append({'fixture_id': case['id'], 'clause': case['clause'], 'group': 'targeted_38',
                         'expected_outcome': category, 'status': 'PASS' if passed else 'FAIL',
                         'expected': case['expected'], 'actual': actual,
                         'expected_reason': case['expected_rejection'], 'actual_reason': rejection,
                         'expected_schema_valid': case['schema_valid'], 'actual_schema_valid': schema_valid,
                         'input_immutable': immutable, 'error': error})
    assert len({row['fixture_id'] for row in rows}) == len(rows)
    source_files = [*sorted((APP / 'src/flowsense_vnext').glob('*.py')), Path(__file__),
                    APP / 'tests/test_flowsense_vnext.py', APP / 'tests/test_flowsense_vnext_proposed3.py']
    sources = {p.relative_to(APP).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files if p.exists()}
    source_set_sha = hashlib.sha256(canonical(sources)).hexdigest()
    fixture_requests = {c['id']: c['request'] for c in cases}
    if revision == '2.0.0-proposed.3':
        fixture_requests.update({c['id']: c['request'] for c in targeted['cases']})
    for row in rows:
        row['consumer_source_hash_set_sha256'] = source_set_sha
        row['consumer_source_hashes_ref'] = '#/consumer_source_sha256'
        row['request_sha256'] = hashlib.sha256(canonical(fixture_requests[row['fixture_id']])).hexdigest()
    report = {'contract_version': revision, 'layer': 'INDEPENDENT_APPLICATION_ISOLATED_CONFORMANCE',
              'source_verification': json.loads((out / 'source-verification.json').read_text()),
              'command': [sys.executable, '-B', *sys.argv], 'consumer_source_sha256': sources,
              'consumer_source_hash_set_sha256': source_set_sha,
              'fixture_raw_sha256': {name: hashlib.sha256((pin / name).read_bytes()).hexdigest()
                                     for name in ('fixtures.json', 'targeted-fixtures.json') if (pin / name).exists()},
              'schema_dependency': {'file': __import__('jsonschema').__file__,
                                    'version': __import__('importlib.metadata', fromlist=['version']).version('jsonschema')},
              'adapter': 'Canonical JSON serialization; mock list to TracePredictor; supplied response mutations only. No semantic adapter.',
              'summary': {key: sum(r['status'] == key for r in rows) for key in ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN')},
              'fixture_categories': {key: sum(r['expected_outcome'] == key for r in rows) for key in ('positive', 'negative_reject', 'day_local_unknown')},
              'groups': {group: {'summary': {key: sum(r['status'] == key for r in rows if r['group'] == group)
                                              for key in ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN')},
                                'outcomes': {key: sum(r['expected_outcome'] == key for r in rows if r['group'] == group)
                                             for key in ('positive', 'negative_reject', 'day_local_unknown')}}
                         for group in sorted({r['group'] for r in rows})},
              'literal_assertions': sum(len(r.get('assertions', {})) for r in rows), 'cases': rows,
              'adversarial_mutations': mutations, 'models_loaded': 0, 'model_accuracy': 'NOT_RUN',
              'http_browser_artifact_parity': 'NOT_RUN', 'producer_self_check': 'NOT_EXECUTED',
              'producer_mutation_tests': 'NOT_RUN_NOT_COUNTED_AS_CONSUMER_FORECASTS'}
    forbidden = ('onnxruntime', 'torch', 'lightgbm', 'src.app_v2', 'src.model_package', 'semantic_validator')
    report['forbidden_imports_present'] = [name for name in forbidden if name in sys.modules]
    assert not report['forbidden_imports_present']
    (out / 'conformance-results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('summary', 'fixture_categories', 'groups', 'literal_assertions')}, indent=2))
    for row in rows:
        if row['status'] != 'PASS':
            print(json.dumps(row, ensure_ascii=False))
    return int(any(r['status'] != 'PASS' for r in rows))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--schema-site-packages', type=Path,
                        help='Optional existing read-only jsonschema dependency directory; never imports producer semantics')
    parser.add_argument('--revision', choices=('2.0.0-proposed.2', '2.0.0-proposed.3'), default='2.0.0-proposed.2')
    parser.add_argument('--output-dir', type=Path, help='Optional separate evidence directory; never changes fixture expectations')
    args = parser.parse_args()
    dependency_path(args.schema_site_packages)
    raise SystemExit(run(args.revision, args.output_dir))
