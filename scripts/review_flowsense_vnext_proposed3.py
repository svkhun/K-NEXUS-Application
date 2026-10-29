"""Targeted consumer acquisition/preservation; stdlib only, no producer execution.

Never seals a producer file or replaces a preservation baseline.
"""
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

APP = Path(__file__).resolve().parents[1]
SHOWCASE = Path('D:/All Project/k-flowsense-trustgraph')
SOURCE = SHOWCASE / 'docs/contracts/flowsense-vnext/revisions/2.0.0-proposed.3'
OUT = APP / 'docs/contracts/flowsense-vnext-review/proposed.3'
OLD = OUT.parent / 'proposed.2/pinned'
VERSION = '2.0.0-proposed.3'
RAW = 'a3e82787143abb92f333ecfdf051d23a87ed545b41fe806df452c44d386e625d'
BUNDLE = '981045aa753f0eaf076e109636c97c4a979c2922319f7b7ef946e73753653e06'
SKIP = {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache'}


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def inventory(root):
    files, errors = {}, []
    for base, dirs, names in os.walk(root, onerror=lambda exc: errors.append(str(exc))):
        dirs[:] = [d for d in dirs if d not in SKIP and Path(base) / d != OUT]
        for name in names:
            path = Path(base) / name
            try:
                files[path.relative_to(root).as_posix()] = sha(path)
            except OSError as exc:
                errors.append(str(exc))
    return {'files': files, 'errors': errors, 'excluded_directory_names': sorted(SKIP),
            'excluded_review_directory': str(OUT) if root == APP else None}


def git_state():
    result = {}
    for name, args in [('head', ['rev-parse', 'HEAD']), ('status', ['status', '--porcelain=v1', '--untracked-files=all']),
                       ('staged_diff', ['diff', '--cached', '--binary'])]:
        proc = subprocess.run(['git', *args], cwd=APP, capture_output=True, timeout=30,
                              env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'})
        assert proc.returncode == 0, proc.stderr
        result[name] = {'sha256': hashlib.sha256(proc.stdout).hexdigest(),
                        'text': proc.stdout.decode('utf-8') if name != 'staged_diff' else None}
    return result


def verify_and_pin():
    manifest = load(SOURCE / 'revision-manifest.json')
    evidence = load(SOURCE / 'evidence-manifest.json')
    bad = []
    verified = {}
    for label, doc in [('source', manifest), ('evidence', evidence)]:
        assert doc['algorithm'] == 'sha256(raw file bytes)'
        for name, expected in doc['files'].items():
            path = (SOURCE / name).resolve()
            assert path.is_relative_to(SOURCE.resolve())
            actual = sha(path)
            verified[label + '/' + name] = {'expected': expected, 'actual': actual, 'status': 'PASS' if actual == expected else 'FAIL'}
            if actual != expected:
                bad.append(name)
    bundle = hashlib.sha256(canonical({k: manifest[k] for k in ('algorithm', 'files')})).hexdigest()
    evidence_bundle = hashlib.sha256(canonical({k: evidence[k] for k in ('algorithm', 'files')})).hexdigest()
    derived = {'revision-manifest.json', 'evidence-manifest.json', 'HASHES.md', 'TARGETED_APPLICATION_HANDOFF.md'}
    actual_sources = {p.name for p in SOURCE.iterdir() if p.is_file() and p.name not in derived}
    actual_evidence = {p.relative_to(SOURCE).as_posix() for p in (SOURCE / 'evidence').rglob('*') if p.is_file()}
    actual_evidence |= derived - {'evidence-manifest.json'}
    okay = (not bad and len(manifest['files']) == 26 and actual_sources == set(manifest['files']) and
            actual_evidence == set(evidence['files']) and sha(SOURCE / 'contract.json') == RAW and
            bundle == BUNDLE == manifest['bundle_sha256'] and evidence_bundle == evidence['evidence_bundle_sha256'])
    report = {'status': 'PASS' if okay else 'FAIL', 'source': str(SOURCE), 'raw_contract_sha256': sha(SOURCE / 'contract.json'),
              'bundle_sha256': bundle, 'canonical_contract_sha256': hashlib.sha256(canonical(load(SOURCE / 'contract.json'))).hexdigest(),
              'evidence_bundle_sha256': evidence_bundle, 'source_files_verified': len(manifest['files']),
              'evidence_files_verified': len(evidence['files']), 'source_coverage_exact': actual_sources == set(manifest['files']),
              'evidence_coverage_exact': actual_evidence == set(evidence['files']), 'mismatches': bad, 'files': verified,
              'algorithm': 'SHA256 raw bytes; bundle SHA256 UTF8 sorted compact JSON {algorithm,files}, ensure_ascii=False, allow_nan=False, final LF',
              'producer_tools_executed': False, 'resealed': False}
    write('source-verification.json', report)
    assert okay, 'STOP: producer hash/coverage mismatch. No pin/ACK; never reseal.'
    pin = OUT / 'pinned'
    pin.mkdir(exist_ok=True)
    for name in sorted(actual_sources | set(evidence['files']) | {'evidence-manifest.json'}):
        target = pin / name
        raw = (SOURCE / name).read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == raw, 'Never replace a different pin'
        else:
            target.write_bytes(raw)
    report['pinned_raw_files'] = {p.relative_to(pin).as_posix(): sha(p) for p in sorted(pin.rglob('*')) if p.is_file()}
    write('source-verification.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'raw_contract_sha256', 'bundle_sha256', 'source_files_verified', 'evidence_files_verified')}))


def acquire():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not (OUT / 'snapshot-before.json').exists(), 'Never replace baseline'
    before = {'application': inventory(APP), 'showcase': inventory(SHOWCASE), 'git': git_state(),
              'command': [sys.executable, '-B', *sys.argv]}
    assert not before['application']['errors'] and not before['showcase']['errors']
    write('snapshot-before.json', before)
    verify_and_pin()


def semantic_diff():
    pin = OUT / 'pinned'
    previous, current = load(OLD / 'fixtures.json'), load(pin / 'fixtures.json')
    migrated = copy.deepcopy(previous)
    migrated['contract_version'] = VERSION
    for case in migrated['cases']:
        case['request']['contract_version'] = VERSION
        if 'response_literal' in case:
            response = case['response_literal']
            response['contract_version'] = VERSION
            response['request_sha256'] = hashlib.sha256(canonical(case['request'])).hexdigest()
            response['aggregate']['input_sha256'] = response['request_sha256']
    assert len(current['cases']) == 109 and migrated == current, 'Unexpected fixture/expectation drift'
    schema_checks = {}
    for name in ('request.schema.json', 'response.schema.json', 'forecast.request.schema.json', 'forecast.response.schema.json'):
        left = load(OLD / name)
        # Mechanical version-string migration only for these schema bytes, not historical evidence.
        expected = json.loads(json.dumps(left).replace('2.0.0-proposed.2', VERSION))
        schema_checks[name] = expected == load(pin / name)
    assert all(schema_checks.values()), 'Unexpected wire schema redesign'
    diffs = []
    for name in ('semantic_validator.py', 'CONTRACT.md', 'contract.json', 'build_metadata.py', 'build_fixtures.py',
                 'build_schemas.py', 'check_contract.py', 'test_checker.py', 'forecast-request-example.json',
                 'forecast-response-example.json', 'adversarial-mutations.json'):
        diffs.extend(difflib.unified_diff((OLD / name).read_text(encoding='utf-8').splitlines(True),
                     (pin / name).read_text(encoding='utf-8').splitlines(True), fromfile='proposed.2/' + name, tofile='proposed.3/' + name))
    (OUT / 'semantic-diff.patch').write_text(''.join(diffs), encoding='utf-8')
    report = {'fixture_version_migration_only': True, 'original_cases': 109, 'expectations_reasons_ids_notes_unchanged': True,
              'wire_schema_version_only': schema_checks, 'diff': 'semantic-diff.patch', 'producer_execution': False}
    write('semantic-diff-results.json', report)
    print(json.dumps(report))


def examples():
    """Application-local invented conformance packaging, never a Gate1 dataset."""
    sys.path.insert(0, str(APP))
    from src.flowsense_vnext.files import ROLES, FULL_ROLES
    out = OUT / 'examples'
    out.mkdir(exist_ok=True)
    q = load(OUT / 'pinned/forecast-request-example.json')
    assert q['contract_version'] == VERSION
    assert q['model_eligibility']['status'] == 'UNVALIDATED'
    assert q['model_eligibility']['package_version'] is None
    assert not q['model_eligibility']['validated_horizons'] and not q['model_eligibility']['validated_cohorts']
    (out / 'valid-wire.json').write_bytes(canonical(q))
    invalid = copy.deepcopy(q)
    invalid['mappings'] = []
    (out / 'invalid-unknown-mapping.json').write_bytes(canonical(invalid))
    invalid = copy.deepcopy(q)
    invalid['transactions'][0]['raw_amount_thb'] = '-1.005'
    (out / 'unknown-day-invalid-precision.json').write_bytes(canonical(invalid))
    roles = {**ROLES, **FULL_ROLES}
    core = {k: v for k, v in q.items() if k not in roles.values()}
    values = {name: canonical(q[field] if field else core) for name, field in roles.items()}
    manifest = {'contract_version': VERSION, 'request_kind': q['request_kind'],
                'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in values.items()}}
    variants = {}
    for name in ('valid-data-bundle', 'invalid-hash-data-bundle', 'invalid-version-data-bundle', 'invalid-manifest-core-data-bundle'):
        folder = out / name
        folder.mkdir(exist_ok=True)
        payloads, m = dict(values), copy.deepcopy(manifest)
        if name == 'invalid-hash-data-bundle':
            payloads['ledger.json'] += b' '  # JSON still valid; raw bytes no longer match.
        elif name == 'invalid-version-data-bundle':
            m['contract_version'] = '2.0.0-proposed.999'
        elif name == 'invalid-manifest-core-data-bundle':
            wrong = copy.deepcopy(core)
            wrong['contract_version'] = '2.0.0-proposed.2'
            payloads['request-core.json'] = canonical(wrong)
            m['files']['request-core.json'] = hashlib.sha256(payloads['request-core.json']).hexdigest()
        for filename, raw in payloads.items():
            (folder / filename).write_bytes(raw)
        (folder / 'bundle-manifest.json').write_bytes(canonical(m))
        variants[name] = {'raw_sha256': {p.name: sha(p) for p in folder.iterdir() if p.is_file()},
                          'expected': 'PASS' if name == 'valid-data-bundle' else 'REJECTED'}
    write('example-manifest.json', {'scope': 'CONFORMANCE_ONLY_NOT_GATE1_OR_ACCURACY', 'bundles': variants})
    print('Created proposed.3 wire and sidecar fixtures with hashes from actual file bytes.')


def verify(schema_site_packages=None):
    """Bounded, allowlisted consumers only; every log is new proposed.3 evidence."""
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8',
                   'PYTHONPATH': os.pathsep.join([str(APP), *([str(schema_site_packages)] if schema_site_packages else [])])}
    python = [sys.executable, '-B']
    tasks = [
        ('consumer-conformance', python + ['scripts/verify_flowsense_vnext.py', '--revision', VERSION], None),
        ('isolated-regressions', python + ['-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_flowsense_vnext*.py', '-v'], None),
    ]
    for name, example, expected in [
        ('sidecar-valid', 'valid-data-bundle', None),
        ('sidecar-invalid-hash', 'invalid-hash-data-bundle', 'DATA_BUNDLE_HASH_MISMATCH'),
        ('sidecar-invalid-version', 'invalid-version-data-bundle', 'DATA_BUNDLE_MANIFEST'),
        ('sidecar-manifest-core-mismatch', 'invalid-manifest-core-data-bundle', 'DATA_BUNDLE_MANIFEST'),
        ('wire-valid', 'valid-wire.json', None),
        ('wire-mapping-rejection', 'invalid-unknown-mapping.json', 'UNKNOWN_MAPPING'),
        ('wire-day-local-unknown', 'unknown-day-invalid-precision.json', None),
    ]:
        tasks.append((name, python + ['scripts/validate_flowsense_vnext_bundle.py',
                      (OUT / 'examples' / example).relative_to(APP).as_posix(), '--contract-version', VERSION], expected))
    results = []
    for name, command, expected_reason in tasks:
        start = time.monotonic()
        try:
            proc = subprocess.run(command, cwd=APP, capture_output=True, timeout=45, env=environment)
            log, code = proc.stdout + proc.stderr, proc.returncode
            actual = json.loads(proc.stdout) if name.startswith(('sidecar-', 'wire-')) else None
            okay = (code == 0 if expected_reason is None else code == 1 and actual.get('reason') == expected_reason)
            status = 'PASS' if okay else 'FAIL'
        except subprocess.TimeoutExpired as exc:
            log, code, status, actual = (exc.stdout or b'') + (exc.stderr or b''), None, 'TIMEOUT', None
        except OSError as exc:
            log, code, status, actual = str(exc).encode(), None, 'BLOCKED', None
        (OUT / (name + '.log')).write_bytes(log)
        results.append({'name': name, 'command': command, 'cwd': str(APP), 'timeout_seconds': 45,
                        'elapsed_seconds': round(time.monotonic() - start, 3), 'exit_code': code,
                        'status': status, 'expected_rejection': expected_reason, 'actual': actual, 'log': name + '.log'})
    report = {'results': results, 'summary': {s: sum(r['status'] == s for r in results) for s in ('PASS', 'FAIL', 'TIMEOUT', 'BLOCKED')},
              'schema_site_packages_read_only': str(schema_site_packages) if schema_site_packages else None,
              'dependency_install_or_upgrade': False, 'models_loaded': 0, 'producer_tools_executed': False,
              'skipped': [{'name': 'training/ONNX/evaluation/export', 'reason': 'Explicit task restriction; no training discovery'}],
              'not_run': ['full backend startup', 'HTTP/TestClient', 'browser', 'frontend build (no UI/build changes)',
                          'model accuracy/parity', 'data generation/Gate1 certification', 'activation', 'commit/push/deploy'],
              'environment': {'python': sys.version, 'executable': sys.executable},
              'scope': 'New execution against proposed.3 consumer; historical tests use preserved proposed.2 fixtures. Expected invalid inputs with exit1 are correct rejections, not failed checks.'}
    write('verification.json', report)
    print(json.dumps(report['summary']))
    return int(any(r['status'] != 'PASS' for r in results))


def preservation():
    before = load(OUT / 'snapshot-before.json')
    after = {'application': inventory(APP), 'showcase': inventory(SHOWCASE), 'git': git_state()}
    write('snapshot-after.json', after)
    report = {}
    allowed = ('src/flowsense_vnext/', 'docs/contracts/flowsense-vnext-review/proposed.3/')
    allowed_files = {'scripts/review_flowsense_vnext_proposed3.py', 'scripts/verify_flowsense_vnext.py',
                     'scripts/validate_flowsense_vnext_bundle.py', 'tests/test_flowsense_vnext_proposed3.py'}
    for repo in ('application', 'showcase'):
        a, b = before[repo]['files'], after[repo]['files']
        changed = [p for p, h in a.items() if b.get(p) != h]
        added = sorted(set(b) - set(a))
        outside = [p for p in changed + added if repo == 'showcase' or not (p.startswith(allowed) or p in allowed_files)]
        report[repo] = {'baseline_files': len(a), 'changed_or_removed': changed, 'added': added,
                        'out_of_scope_changes': outside, 'read_errors': after[repo]['errors']}
    report['historical_proposed2_unchanged'] = all(after['application']['files'].get(p) == h for p, h in before['application']['files'].items()
                                                  if p.startswith('docs/contracts/flowsense-vnext-review/proposed.2/'))
    report['head_unchanged'] = before['git']['head'] == after['git']['head']
    report['staged_diff_unchanged'] = before['git']['staged_diff'] == after['git']['staged_diff']
    report['serving_config'] = load(APP / 'models/serving.json')
    report['runtime_config_models_data_unchanged'] = all(after['application']['files'].get(p) == h for p, h in before['application']['files'].items()
        if p.startswith(('src/', 'models/', 'data/', 'frontend/', 'public/')) and not p.startswith('src/flowsense_vnext/'))
    report['status'] = 'PASS' if (all(not report[r]['out_of_scope_changes'] and not report[r]['read_errors'] for r in ('application', 'showcase'))
        and report['historical_proposed2_unchanged'] and report['head_unchanged'] and report['staged_diff_unchanged']
        and report['runtime_config_models_data_unchanged'] and report['serving_config']['flowsense_enabled'] is False) else 'FAIL'
    report['scope'] = 'All accessible workspace files except listed dependency/cache/.git directories and this review output. Existing dirty work compared by raw bytes; no deployed-state claim.'
    write('preservation-results.json', report)
    print(json.dumps(report, indent=2))
    return int(report['status'] != 'PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('acquire', 'semantic-diff', 'examples', 'verify', 'preservation'))
    parser.add_argument('--schema-site-packages', type=Path)
    args = parser.parse_args()
    result = verify(args.schema_site_packages) if args.action == 'verify' else {
        'acquire': acquire, 'semantic-diff': semantic_diff, 'examples': examples, 'preservation': preservation}[args.action]()
    raise SystemExit(result or 0)
