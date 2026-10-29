"""Product adapter for live intraday baseline v1; no model or legacy mean fallback.

The sealed midnight consumer/IssueRegistry remains separate. Only complete,
account-native closed days, or independently prepared contract history, can be
attached by an internal ingestion adapter. Browser transactions never seal a day.
"""
import copy
import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

VERSION = 'history28-min7-scenario-abstain.v1'
ADAPTER = 'live-intraday-next-day.v1'
TZ = ZoneInfo('Asia/Bangkok')
SOURCE = 'config/baseline-personas.v1.json'


def satang(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError('NONFINITE_MONEY')
    return int((number * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def thb(value):
    return None if value is None else value / 100


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def seed_assumptions(account_id, now, config):
    item = config['personas'][account_id]
    return dict(account_id=account_id, baseline_mode='BASELINE',
        spending_scenario=dict(version=config['version'], source=SOURCE,
            source_sha256=digest(config), unit='satang/day', daily_satang=item['daily_non_bill_satang'],
            effective_from=now.date().isoformat(), effective_to='2099-12-31',
            known_at=now.isoformat(), provenance_kind='EXPLICIT_SYNTHETIC_ASSUMPTION'),
        seeded_posted_today=dict(amount_satang=item['seeded_posted_today_satang'],
            source=SOURCE, version=config['version'], date=now.date().isoformat(),
            provenance_kind='SYNTHETIC_SESSION_OPENING_ALREADY_INCLUDED_IN_BALANCE'),
        daily_spent_today=thb(item['seeded_posted_today_satang']))


def attach_prepared_history(state, prepared):
    """Bridge validated sealed ingestion only; never import its historical balance.

    prepared must originate from flowsense_vnext.prepare(..., resolver=...).
    It retains its exact origin/account; select_spending rejects stale origins.
    """
    from src.flowsense_vnext.ingestion import Prepared
    if not isinstance(prepared, Prepared):
        raise ValueError('PREPARED_HISTORY_REQUIRED')
    q = json.loads(prepared.request_bytes)
    if q['account_id'] != state.get('account_id'):
        raise ValueError('HISTORY_ACCOUNT_MISMATCH')
    state['non_bill_history'] = dict(account_id=q['account_id'], origin=q['origin'],
        version=q['contract_version'], source='VALIDATED_CONTRACT_INGESTION',
        source_sha256=hashlib.sha256(prepared.request_bytes).hexdigest(),
        records=[dict(date=d, amount_satang=v, complete=v is not None,
                      reasons=list(dict(prepared.day_reasons).get(d, ()))) for d, v in prepared.history])


def select_spending(state, now):
    """Pure selection frozen on 28 closed Bangkok dates; zero counts in N."""
    now = now.astimezone(TZ) if now.tzinfo else now.replace(tzinfo=TZ)
    origin = now.replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [(origin.date()-timedelta(days=n)).isoformat() for n in range(28, 0, -1)]
    history = state.get('non_bill_history')
    rows, invalid = {}, 'NO_VALIDATED_CURRENT_HISTORY'
    if history:
        try:
            valid = (history['account_id'] == state['account_id'] and
                     datetime.fromisoformat(history['origin']) == origin and
                     bool(history['source']) and bool(history['version']) and bool(history['source_sha256']))
            records = history['records']
            if valid and len({r['date'] for r in records}) == len(records):
                rows = {r['date']: r for r in records if r['date'] in dates}
                invalid = 'INSUFFICIENT_COMPLETE_DAYS'
            else:
                invalid = 'HISTORY_ACCOUNT_OR_ORIGIN_INVALID'
        except (KeyError, ValueError, TypeError):
            invalid = 'HISTORY_INVALID'
    known, excluded = [], []
    for day in dates:
        row = rows.get(day, {})
        amount = row.get('amount_satang')
        if row.get('complete') is True and not row.get('reasons') and type(amount) is int and amount >= 0:
            known.append(amount)
        else:
            excluded.append(dict(date=day, reasons=row.get('reasons') or [invalid]))
    count, numerator = len(known), sum(known)
    selected = None
    method, reason, source, version = 'ABSTAIN', 'INSUFFICIENT_HISTORY_NO_SCENARIO', None, None
    scenario = state.get('spending_scenario')
    if state.get('baseline_mode', 'BASELINE') != 'BASELINE':
        reason = 'BASELINE_DISABLED'
    elif count >= 7:
        selected = int((Decimal(numerator)/count).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        method, reason, source, version = 'HISTORY_MEAN', 'MIN7_COMPLETE_28D', history['source'], history['version']
    elif scenario:
        try:
            known_at = datetime.fromisoformat(scenario['known_at'])
            # The assumption covers the live as-of date and all 30 future days.
            if (type(scenario['daily_satang']) is int and scenario['daily_satang'] >= 0 and
                scenario['unit'] == 'satang/day' and scenario['source'] and scenario['version'] and
                scenario['provenance_kind'] == 'EXPLICIT_SYNTHETIC_ASSUMPTION' and known_at.tzinfo and
                known_at <= now and scenario['effective_from'] <= now.date().isoformat() and
                scenario['effective_to'] >= (now.date()+timedelta(days=30)).isoformat()):
                selected = scenario['daily_satang']
                method, reason, source, version = 'SCENARIO', 'EXPLICIT_SCENARIO', scenario['source'], scenario['version']
            else:
                reason = 'INVALID_OR_INAPPLICABLE_SCENARIO'
        except (KeyError, ValueError, TypeError):
            reason = 'INVALID_SCENARIO'
    result = dict(policy_version=VERSION, adapter_version=ADAPTER, method=method, reason=reason,
        daily_satang=selected, daily_non_bill_thb=thb(selected), unit='THB/day', source=source,
        source_version=version, complete_known_days=count, expected_calendar_days=28,
        numerator_satang=numerator, window_start=dates[0], window_end=dates[-1], excluded=excluded,
        history_origin=origin.isoformat(), history_reason=invalid,
        scenario=copy.deepcopy(scenario) if method == 'SCENARIO' else None,
        provenance=copy.deepcopy({k: history[k] for k in ('source', 'source_sha256', 'version', 'origin')}) if rows else None)
    result['selection_id'] = digest(result)
    return result
