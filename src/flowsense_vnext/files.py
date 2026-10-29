"""Optional hash-verified synthetic-v2 sidecar reader; no implicit legacy mapping.

Packaging only: sidecar values become identically named request fields. prepare()
still owns ALL schema/semantic validation. Source authenticity is a Gate1 task.
"""
import hashlib
from pathlib import Path
from .boundary import REVISIONS, check, decode
from .ingestion import prepare

ROLES = {
    'request-core.json': None,
    'ledger.json': 'transactions',
    'mapping.json': 'mappings',
    'coverage.json': 'coverage',
    'source-registry.json': 'source_registry',
    'bill-calendar.json': 'bill_calendar',
    'bills.json': 'bills',
    'opening-snapshot.json': 'opening_snapshot',
}
FULL_ROLES = {'opening-balance.json': 'opening_balance', 'salary.json': 'salary',
              'aggregate-provenance.json': 'aggregate_provenance', 'scenario.json': 'scenario',
              'model-eligibility.json': 'model_eligibility'}


def read_data_bundle(directory, *, expected_version=None, resolver=None):
    root = Path(directory).resolve()
    manifest = decode((root / 'bundle-manifest.json').read_bytes())
    check(isinstance(manifest, dict) and set(manifest) == {'contract_version', 'request_kind', 'files'}, 'DATA_BUNDLE_MANIFEST')
    version = manifest['contract_version']
    check(isinstance(version, str) and version in REVISIONS and manifest['request_kind'] in ('FEATURE_ONLY', 'FULL_FORECAST'),
          'DATA_BUNDLE_MANIFEST')
    check(expected_version is None or version == expected_version,
          'DATA_BUNDLE_MANIFEST' if expected_version == '2.0.0-proposed.4' else 'DATA_BUNDLE_VERSION_MISMATCH')
    roles = {**ROLES, **(FULL_ROLES if manifest['request_kind'] == 'FULL_FORECAST' else {})}
    amended = version == '2.0.0-proposed.4'
    if amended:
        roles['historical-bill-references.json'] = 'historical_bill_references'
    hashes = manifest['files']
    check(isinstance(hashes, dict) and set(hashes) == set(roles), 'DATA_BUNDLE_MANIFEST' if amended else 'DATA_BUNDLE_FILES')
    values = {}
    for filename in roles:
        path = (root / filename).resolve()
        check(path.parent == root, 'DATA_BUNDLE_PATH')
        raw = path.read_bytes()
        check(hashlib.sha256(raw).hexdigest() == hashes[filename], 'DATA_BUNDLE_HASH_MISMATCH')
        values[filename] = decode(raw)
    q = values['request-core.json']
    check(isinstance(q, dict) and not set(q).intersection(v for v in roles.values() if v),
          'DATA_BUNDLE_MANIFEST' if amended else 'DATA_BUNDLE_FIELD_COLLISION')
    q = dict(q)
    q.update({field: values[name] for name, field in roles.items() if field})
    check(q.get('request_kind') == manifest['request_kind'] and q.get('contract_version') == version, 'DATA_BUNDLE_MANIFEST')
    return prepare(q, resolver=resolver)
