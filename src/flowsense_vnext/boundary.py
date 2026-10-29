"""Strict wire and exact money primitives; no application or inference imports."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = '2.0.0-proposed.2'
TZ = timezone(timedelta(hours=7), 'Asia/Bangkok')
PIN = Path(__file__).resolve().parents[2] / 'docs/contracts/flowsense-vnext-review/proposed.2/pinned'
# Historical defaults remain proposed.2. Every ingress selects an explicit sealed
# revision; no prefix matching, latest-version alias, or cross-version fallback.
REVISIONS = {
    '2.0.0-proposed.2': {
        'pin': PIN,
        'raw_contract_sha256': '47854eb2d09df6d018c86aa3087e6c27ee6846f54e912f9bec8757627003953c',
        'bundle_sha256': '283e24f5f6f80ae925b8ed821b200cccb3822a63c80c488690230418354a7d46',
    },
    '2.0.0-proposed.3': {
        'pin': PIN.parents[1] / 'proposed.3/pinned',
        'raw_contract_sha256': 'a3e82787143abb92f333ecfdf051d23a87ed545b41fe806df452c44d386e625d',
        'bundle_sha256': '981045aa753f0eaf076e109636c97c4a979c2922319f7b7ef946e73753653e06',
    },
    '2.0.0-proposed.4': {
        'pin': PIN.parents[2] / 'flowsense-vnext-data-review/proposed.4-v2.1.1/pinned',
        'raw_contract_sha256': 'a3ebbe36a3225b9d8c9af5a6c644aecec39dd43503b07c34addea1c93e77e62f',
        'bundle_sha256': '79804e41736b0613f940fc3e4c034148bd15fd98518c4ab4d8c920c587c4679c',
    },
}
SCHEMA_NAMES = {'contract.schema.json', 'request.schema.json', 'response.schema.json',
                'forecast.request.schema.json', 'forecast.response.schema.json', 'source-facts.schema.json'}


class Rejected(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def check(ok, reason):
    if not ok:
        raise Rejected(reason)


def finite_tree(value):
    if isinstance(value, float):
        check(math.isfinite(value), 'NONFINITE_WIRE')
    elif isinstance(value, dict):
        for item in value.values():
            finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            finite_tree(item)


def decode(raw):
    """Call at the byte/text boundary, before a JSON parser can lose duplicate keys."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            check(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result

    def constant(_):
        raise Rejected('NONFINITE_WIRE')
    try:
        result = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, Rejected):
            raise
        raise Rejected('INVALID_JSON') from exc
    finite_tree(result)  # includes exponent overflow such as 1e999
    return result


def canonical(value):
    finite_tree(value)
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@lru_cache(maxsize=24)
def _validator(name, version=VERSION):
    # Standard JSON Schema implementation only; never imports the producer checker.
    from jsonschema import Draft202012Validator, FormatChecker
    check(isinstance(version, str) and version in REVISIONS and name in SCHEMA_NAMES, 'SCHEMA_INVALID')
    revision = REVISIONS[version]
    pin = revision['pin']
    manifest = decode((pin / 'revision-manifest.json').read_bytes())
    check(digest({k: manifest[k] for k in ('algorithm', 'files')}) == revision['bundle_sha256'] == manifest['bundle_sha256'],
          'PIN_HASH_MISMATCH')
    check(hashlib.sha256((pin / 'contract.json').read_bytes()).hexdigest() == revision['raw_contract_sha256'],
          'PIN_HASH_MISMATCH')
    raw = (pin / name).read_bytes()
    check(hashlib.sha256(raw).hexdigest() == manifest['files'][name], 'PIN_HASH_MISMATCH')
    schema = decode(raw)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def shape(value, response=False):
    finite_tree(value)
    check(isinstance(value, dict), 'SCHEMA_INVALID')
    check(isinstance(value.get('contract_version'), str) and value['contract_version'] in REVISIONS, 'SCHEMA_INVALID')
    full = value.get('request_kind') == 'FULL_FORECAST' if not response else 'points' in value
    name = ('forecast.' if full else '') + ('response' if response else 'request') + '.schema.json'
    check(not any(_validator(name, value.get('contract_version')).iter_errors(value)), 'SCHEMA_INVALID')


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise Rejected('SCHEMA_INVALID') from exc
    check(result.utcoffset() == timedelta(hours=7), 'INVALID_TIMEZONE')
    return result


def day(value):
    return date.fromisoformat(value)


def money(value):
    """HALF_UP is for predictions/mean only; never fixes a malformed ledger row."""
    number = Decimal(str(value))
    check(number.is_finite(), 'NONFINITE_WIRE')
    with localcontext() as ctx:
        ctx.prec = max(40, len(number.as_tuple().digits) + abs(number.adjusted()) + 8)
        return int((number * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def thb(satang):
    if satang is None:
        return None
    result = float(Decimal(satang) / 100)
    check(math.isfinite(result), 'NONFINITE_WIRE')
    # JSON numbers cannot represent arbitrarily large cents faithfully.
    check(Decimal(str(result)) * 100 == satang, 'WIRE_MONEY_RANGE')
    return result


def normalize(raw):
    check(isinstance(raw, str) and re.fullmatch(r'-?(0|[1-9][0-9]*)(\.[0-9]{1,2})?', raw),
          'INVALID_RAW_PRECISION')
    negative = raw.startswith('-')
    whole, _, fraction = raw.lstrip('-').partition('.')
    amount = int(whole) * 100 + int(fraction.ljust(2, '0'))
    check(amount != 0, 'ZERO_AMOUNT')
    return ('-' if negative else '') + whole + '.' + fraction.ljust(2, '0'), -amount if negative else amount


def lineage(p, origin, allowed=('verified_source', 'synthetic_generator_explicit', 'explicit_scenario')):
    check(p['kind'] in allowed, 'INVALID_PROVENANCE_KIND')
    check(timestamp(p['as_of']) <= timestamp(p['available_at']) <= origin, 'PROVENANCE_AFTER_ORIGIN')


def select_revisions(rows, identity_fields, origin, label):
    """Group all known revisions, audit immutable identities, then choose maximum."""
    groups = {}
    for row in rows:
        if timestamp(row['available_at']) > origin:
            continue
        key = tuple(row[name] for name in identity_fields)
        versions = groups.setdefault(key, {})
        revision = row['revision']
        if revision in versions:
            suffix = '_DUPLICATE_REVISION' if versions[revision] == row else '_CONFLICTING_REVISION'
            raise Rejected(label + suffix)
        versions[revision] = row
    return [versions[max(versions)] for _, versions in sorted(groups.items())]
