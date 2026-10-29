"""Consumer-owned account boundary, ledger normalization and closed-day coverage."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from .bills import opening_bills
from .boundary import (TZ, Rejected, canonical, check, day, decode, lineage,
                       normalize, select_revisions, shape, timestamp)

SPEND = {'food_daily', 'transport', 'entertainment', 'fee', 'external_transfer', 'unplanned_transfer'}
BILL_CATEGORY = {'debt_emi': 'debt', 'rent': 'rent', 'utilities': 'utilities'}
CREDITS = {'refund', 'reversal'}
SOURCE_KINDS = ('verified_source', 'synthetic_generator_explicit')


@dataclass(frozen=True)
class Prepared:
    """No mutable caller-owned dictionaries escape into frozen state."""
    request_bytes: bytes
    history: tuple[tuple[str, int | None], ...]
    day_reasons: tuple[tuple[str, tuple[str, ...]], ...]
    bills_bytes: bytes
    mapping_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]

    def diagnostic(self):
        return {'history': dict(self.history), 'day_reasons': {d: list(r) for d, r in self.day_reasons}}


class MappingIndex:
    def __init__(self, q, origin):
        self.account, self.user = q['account_id'], q['user_id']
        self.rows = [m for m in q['mappings'] if timestamp(m['available_at']) <= origin]
        for i, row in enumerate(self.rows):
            check(row['effective_to'] is None or row['effective_to'] > row['effective_from'], 'INVALID_MAPPING_INTERVAL')
            check(row['provenance_kind'] != 'legacy_modulo_fixture', 'FIXTURE_MAPPING')
            for other in self.rows[:i]:
                overlap = max(row['effective_from'], other['effective_from']) < min(
                    row['effective_to'] or '9999-12-31', other['effective_to'] or '9999-12-31')
                check(not (overlap and (row['account_id'] == other['account_id'] or row['user_id'] == other['user_id'])),
                      'OVERLAPPING_MAPPING')
        self.at(origin.date().isoformat(), self.account, self.user)

    def at(self, target, account, user=None):
        candidates = [m for m in self.rows if m['account_id'] == account and
                      (user is None or m['user_id'] == user) and m['effective_from'] <= target and
                      (m['effective_to'] is None or target < m['effective_to'])]
        check(len(candidates) == 1, 'UNKNOWN_MAPPING')
        check(account == self.account and candidates[0]['user_id'] == self.user, 'ACCOUNT_IDENTITY_MISMATCH')
        return candidates[0]['mapping_id']


def _transaction_value(row, selected, bills, origin, *, missing_reason='INVALID_BILL_LINK'):
    event, posting, available = (timestamp(row[k]) for k in ('event_time', 'posting_time', 'available_at'))
    check(event <= posting <= available, 'INVALID_TRANSACTION_TIME_ORDER')
    fixed, amount = normalize(row['raw_amount_thb'])
    check(fixed == row['signed_amount_thb'], 'NORMALIZED_AMOUNT_MISMATCH')
    check((amount < 0) == (row['direction'] == 'DR'), 'SIGN_DIRECTION_CONFLICT')
    category = row['category']
    check(category in SPEND | BILL_CATEGORY.keys() | CREDITS | {'salary', 'internal_wallet'}, 'UNKNOWN_CATEGORY')
    if category in SPEND | BILL_CATEGORY.keys():
        check(row['direction'] == 'DR', 'CATEGORY_DIRECTION_CONFLICT')
    if category in CREDITS | {'salary'}:
        check(row['direction'] == 'CR', 'CATEGORY_DIRECTION_CONFLICT')
    if category in CREDITS:
        check(not row['represented_charge_ids'] and 'original_ref' in row, 'INVALID_CREDIT_IDENTITY')
        ref = row['original_ref']
        original = selected.get((ref['source'], ref['transaction_id']))
        check(original is not None and original['direction'] == 'DR' and
              timestamp(original['event_time']) <= event and
              (ref['source'], ref['transaction_id']) != (row['source'], row['transaction_id']), 'INVALID_ORIGINAL_REFERENCE')
    else:
        check('original_ref' not in row and bool(row['represented_charge_ids']), 'INVALID_CHARGE_IDENTITY')
    check(len(row['represented_charge_ids']) == len(set(row['represented_charge_ids'])), 'DUPLICATE_ECONOMIC_CHARGE')
    if category == 'internal_wallet':
        check('same_owner_provenance' in row, 'UNKNOWN_OWNERSHIP')
        lineage(row['same_owner_provenance'], origin, SOURCE_KINDS)
    linked = 'bill_instance_id' in row
    if linked or category in BILL_CATEGORY:
        check(category in BILL_CATEGORY.keys() | {'external_transfer', 'unplanned_transfer'}, 'INVALID_BILL_LINK')
        check(linked and 'bill_payment_event_id' in row and row['direction'] == 'DR', 'INVALID_BILL_LINK')
        bill = bills.get(row['bill_instance_id'])
        check(bill is not None, missing_reason)
        check(category not in BILL_CATEGORY or BILL_CATEGORY[category] == bill['kind'], 'INVALID_BILL_LINK')
        matches = [e for e in bill['payment_events'] if e['source'] == row['source'] and e['id'] == row['bill_payment_event_id']]
        check(len(matches) == 1 and matches[0]['amount_satang'] == -amount and matches[0]['event_time'] == row['event_time'],
              'INVALID_BILL_LINK')
    else:
        check('bill_payment_event_id' not in row, 'INVALID_BILL_LINK')
    return -amount if category in SPEND and not linked else 0


def _full_envelope(q, origin):
    check(q['opening_snapshot']['as_of'] == q['origin'], 'BILLS_NOT_MIDNIGHT_SNAPSHOT')
    balance = q['opening_balance']
    check(balance['as_of'] == q['origin'] and balance['snapshot_id'] == q['opening_snapshot']['snapshot_id'],
          'BALANCE_NOT_MIDNIGHT_SNAPSHOT')
    lineage(balance['provenance'], origin)
    check(balance['provenance']['as_of'] == q['origin'], 'BALANCE_NOT_MIDNIGHT_SNAPSHOT')
    salary = q['salary']
    check(timestamp(salary['known_at']) <= timestamp(salary['available_at']) <= origin, 'SALARY_AFTER_ORIGIN')
    lineage(salary['provenance'], origin)
    lineage(q['aggregate_provenance'], origin, SOURCE_KINDS)
    eligible = q['model_eligibility']
    lineage(eligible['evidence'], origin)
    if eligible['status'] == 'UNVALIDATED':
        check(eligible['package_version'] is None and not eligible['validated_horizons'] and not eligible['validated_cohorts'],
              'INVALID_MODEL_ELIGIBILITY')
    else:
        check(eligible['package_version'] not in (None, '2026.10.27.1') and eligible['validated_horizons'] and eligible['validated_cohorts'],
              'INCOMPATIBLE_MODEL_PACKAGE')
    scenario = q['scenario']
    if scenario is not None:
        lineage(scenario['provenance'], origin, ('explicit_scenario',))
        check(day(scenario['effective_from']) <= origin.date() and
              day(scenario['effective_to']) >= origin.date() + timedelta(days=q['horizon'] - 1), 'SCENARIO_NOT_APPLICABLE')


def prepare(payload, *, resolver=None):
    """Accept strict wire bytes/text, or an already parsed in-process object.

    Parsed objects cannot prove absence of duplicate JSON keys; use bytes at ingress.
    Day values and recursive state are integer satang until feature serialization.
    """
    q = decode(payload) if isinstance(payload, (str, bytes)) else decode(canonical(payload))
    shape(q)
    origin = timestamp(q['origin'])
    mapping = MappingIndex(q, origin)  # account rejection always precedes fallback
    registry = q['source_registry']
    check(timestamp(registry['available_at']) <= origin, 'SOURCE_REGISTRY_AFTER_ORIGIN')
    lineage(registry['provenance'], origin, SOURCE_KINDS)
    sources = registry['sources']
    check(len(sources) == len(set(sources)), 'DUPLICATE_SOURCE_REGISTRY')
    bills = opening_bills(q, origin)
    stable = {}
    for row in q['transactions']:
        if timestamp(row['available_at']) > origin:
            continue
        check(row['source'] in sources, 'UNREGISTERED_SOURCE')
        mapping.at(timestamp(row['event_time']).date().isoformat(), row['account_id'], row['user_id'])
        key = (row['account_id'], row['source'], row['transaction_id'])
        fields = (row['user_id'], row['event_time'])
        check(key not in stable or stable[key] == fields, 'TRANSACTION_IDENTITY_CHANGED')
        stable[key] = fields
    selected = select_revisions(q['transactions'], ('account_id', 'source', 'transaction_id'), origin, 'TRANSACTION')
    selected = [r for r in selected if timestamp(r['event_time']) < origin]
    for row in q['coverage']:
        if timestamp(row['available_at']) <= origin:
            mapping.at(row['date'], row['account_id'])
    coverage = select_revisions(q['coverage'], ('account_id', 'date'), origin, 'COVERAGE')
    amounts, reasons = {}, defaultdict(set)
    for cover in coverage:
        target = cover['date']
        amounts[target] = 0
        if cover['status'] != 'complete':
            reasons[target].add('COVERAGE_' + cover['status'].upper())
        else:
            end = datetime.combine(day(target) + timedelta(days=1), time(), TZ)
            if cover['sealed_at'] is None or not end <= timestamp(cover['sealed_at']) <= timestamp(cover['available_at']) <= origin:
                reasons[target].add('INVALID_COVERAGE_SEAL')
        if sorted(cover['covered_sources']) != sorted(sources):
            reasons[target].add('MISSING_COVERAGE_SOURCE')
    # Audit charge representation before normalization: C01.T1 says ANY selected DR overlap.
    charges = defaultdict(list)
    for row in selected:
        if row['direction'] == 'DR':
            for charge in row['represented_charge_ids']:
                charges[(row['account_id'], charge)].append(timestamp(row['event_time']).date().isoformat())
    for dates in charges.values():
        if len(dates) > 1:
            for target in dates:
                reasons[target].add('DUPLICATE_ECONOMIC_CHARGE')
    identities = {(r['source'], r['transaction_id']): r for r in selected}
    bill_index = {b['id']: b for b in bills}
    amended = q['contract_version'] == '2.0.0-proposed.4'
    if amended:
        from .historical import classification
        bill_index, conflicts = classification(q, bills, selected, origin, resolver)
        for target in conflicts:
            reasons[target].add('DUPLICATE_LEDGER_PAYMENT_EVENT')
    for row in selected:
        target = timestamp(row['event_time']).date().isoformat()
        if target not in amounts:
            amounts[target] = 0
            reasons[target].add('COVERAGE_ABSENT')
        try:
            amounts[target] += _transaction_value(row, identities, bill_index, origin,
                missing_reason='HISTORICAL_BILL_REFERENCE_MISSING' if amended else 'INVALID_BILL_LINK')
        except Rejected as exc:
            reasons[target].add(exc.reason)
    closed = [(origin.date() - timedelta(days=n)).isoformat() for n in range(28, 0, -1)]
    for target in closed:
        if target not in amounts:
            reasons[target].add('COVERAGE_ABSENT')
    history = tuple((d, None if reasons[d] else amounts[d]) for d in closed)
    if q['request_kind'] == 'FULL_FORECAST':
        _full_envelope(q, origin)
    return Prepared(canonical(q), history, tuple((d, tuple(sorted(r))) for d, r in sorted(reasons.items()) if r),
                    canonical(bills), tuple(sorted({mapping.at(d, q['account_id']) for d in closed if d in amounts})),
                    tuple(sorted(f"{c['account_id']}:{c['date']}:{c['revision']}" for c in coverage if c['date'] in closed)))
