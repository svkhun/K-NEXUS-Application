"""Origin-frozen planning with injected deterministic mocks only; never inference."""
from dataclasses import asdict, dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
import struct
from typing import Callable
from .boundary import check, day, decode, digest, money, thb, timestamp
from .bills import next_month
from .ingestion import Prepared, prepare


@dataclass(frozen=True)
class Aggregate:
    window_start: str
    window_end: str
    numerator_satang: int
    complete_known_days: int
    expected_calendar_days: int
    mean_satang: int | None
    excluded: tuple[tuple[str, tuple[str, ...]], ...]
    mapping_ids: tuple[str, ...]
    coverage_ids: tuple[str, ...]
    input_sha256: str
    provenance_id: str

    def wire(self):
        result = asdict(self)
        result['excluded'] = [{'date': d, 'reasons': list(r)} for d, r in self.excluded]
        result['mapping_ids'] = list(self.mapping_ids)
        result['coverage_ids'] = list(self.coverage_ids)
        return result


@dataclass(frozen=True)
class Selection:
    amount_satang: int | None
    method: str
    reason: str
    source_id: str | None
    selection_reason: str


@dataclass(frozen=True)
class TracePredictor:
    """Out-of-wire hand-authored fixture trace. This is not model output."""
    values: tuple[str, ...]

    def __call__(self, index, target, tensor):
        check(index < len(self.values), 'MOCK_TRACE_LENGTH')
        return self.values[index]


MockPredictor = Callable[[int, str, tuple[float, ...]], str | float | Decimal]


def aggregate(state: Prepared) -> Aggregate:
    q = decode(state.request_bytes)
    check(q['request_kind'] == 'FULL_FORECAST', 'FULL_FORECAST_REQUIRED')
    values = [v for _, v in state.history if v is not None]
    numerator, count = sum(values), len(values)
    mean = int((Decimal(numerator) / count).quantize(Decimal(1), rounding=ROUND_HALF_UP)) if count >= 7 else None
    reasons = dict(state.day_reasons)
    return Aggregate(state.history[0][0], state.history[-1][0], numerator, count, 28, mean,
                     tuple((d, reasons.get(d, ('UNKNOWN_TARGET',))) for d, v in state.history if v is None),
                     state.mapping_ids, state.coverage_ids, digest(q), q['aggregate_provenance']['id'])


def feature_row(target, history, bills):
    payday = target.replace(day=28)
    if payday < target:
        payday = next_month(target).replace(day=28)
    flag = any(b['original_satang'] > b['paid_satang'] and
               target <= day(b['due_date']) <= target + timedelta(days=6) for b in bills)
    return [(payday - target).days, int(flag), int(target.weekday() >= 5)] + [
        thb(history.get((target - timedelta(days=lag)).isoformat())) for lag in (1, 3, 7)]


def planning_next_payday(target):
    """Strictly after target; distinct from ML's zero on payday."""
    candidate = target.replace(day=28)
    return candidate if candidate > target else next_month(target).replace(day=28)


def float32_row(row):
    check(len(row) == 6, 'TENSOR_SHAPE')
    check(all(type(v) in (int, float) and math.isfinite(v) for v in row[:3]), 'NONFINITE_TENSOR_COLUMN')
    check(row[0] >= 0 and row[1] in (0, 1) and row[2] in (0, 1), 'INVALID_CALENDAR_FEATURE')
    result = []
    for i, value in enumerate(row):
        if value is None:
            check(i >= 3, 'NONFINITE_TENSOR_COLUMN')
            result.append(float('nan'))
            continue
        check(type(value) in (int, float) and math.isfinite(value), 'NONFINITE_TENSOR_COLUMN')
        check(i < 3 or value >= 0, 'INVALID_LAG_FEATURE')
        try:
            cast = struct.unpack('<f', struct.pack('<f', value))[0]
        except (OverflowError, struct.error) as exc:
            from .boundary import Rejected
            raise Rejected('FLOAT32_OVERFLOW') from exc
        check(math.isfinite(cast), 'FLOAT32_OVERFLOW')
        result.append(cast)
    return tuple(result)


def model_eligibility(q, row):
    if all(v is None for v in row[3:]):
        return 'ALL_LAGS_UNKNOWN'
    cohort = 'PARTIAL_LAGS' if any(v is None for v in row[3:]) else 'ALL_KNOWN'
    evidence = q['model_eligibility']
    if (evidence['status'] == 'VALIDATED_FUTURE_PACKAGE' and
            q['horizon'] in evidence['validated_horizons'] and cohort in evidence['validated_cohorts']):
        return 'MODEL_ELIGIBLE'
    return 'MODEL_NOT_ELIGIBLE'


def select_fallback(q, frozen: Aggregate, selection_reason: str) -> Selection:
    if frozen.mean_satang is not None:
        return Selection(frozen.mean_satang, 'HISTORY_MEAN', 'MIN7_COMPLETE_28D', frozen.provenance_id, selection_reason)
    if q['scenario'] is not None:
        scenario = q['scenario']
        return Selection(scenario['daily_satang'], 'SCENARIO', 'EXPLICIT_SCENARIO', scenario['provenance']['id'], selection_reason)
    return Selection(None, 'ABSTAIN', 'INSUFFICIENT_HISTORY_NO_SCENARIO', None, selection_reason)


def select(q, frozen, row, index, target, mock_predictor=None):
    eligibility = model_eligibility(q, row)
    if eligibility != 'MODEL_ELIGIBLE':
        return select_fallback(q, frozen, eligibility)
    if mock_predictor is None:
        return select_fallback(q, frozen, 'MODEL_NOT_EXECUTED')
    raw = Decimal(str(mock_predictor(index, target.isoformat(), float32_row(row))))
    if not raw.is_finite():
        return select_fallback(q, frozen, 'NONFINITE_MOCK_PREDICTION')
    return Selection(money(max(Decimal(0), raw)), 'MOCK', 'HAND_AUTHORED_NOT_MODEL_OUTPUT', 'mock-trace', eligibility)


def settle_copy(bills, target):
    payment = 0
    for bill in bills:
        if day(bill['due_date']) <= target:
            payment += bill['original_satang'] - bill['paid_satang']
            bill['paid_satang'] = bill['original_satang']
    return payment


def features_only(payload, *, resolver=None):
    state = prepare(payload, resolver=resolver)
    q = decode(state.request_bytes)
    check(q['request_kind'] == 'FEATURE_ONLY', 'FEATURE_ONLY_REQUIRED')
    target = timestamp(q['origin']).date()
    row = feature_row(target, dict(state.history), decode(state.bills_bytes))
    return {'contract_version': q['contract_version'], 'account_id': q['account_id'], 'origin': q['origin'],
            'request_sha256': digest(q), 'model_package_version': None, 'mode': 'FEATURE_ONLY_NO_MODEL',
            'target_date': target.isoformat(), 'feature_row': row,
            'missing_lag_days': [n for n, v in zip((1, 3, 7), row[3:]) if v is None], 'prediction_thb': None}


def forecast(payload, *, mock_predictor: MockPredictor | None = None, forecast_id=None, resolver=None):
    state = prepare(payload, resolver=resolver)
    q = decode(state.request_bytes)
    check(q['request_kind'] == 'FULL_FORECAST', 'FULL_FORECAST_REQUIRED')
    if isinstance(mock_predictor, TracePredictor):
        check(len(mock_predictor.values) == q['horizon'], 'MOCK_TRACE_LENGTH')
    frozen = aggregate(state)
    history = dict(state.history)
    bills = decode(state.bills_bytes)
    balance = q['opening_balance']['amount_satang']
    cumulative = 0
    points = []
    for offset in range(q['horizon']):
        target = timestamp(q['origin']).date() + timedelta(days=offset)
        row = feature_row(target, history, bills)  # pre-payment feature
        selected = select(q, frozen, row, offset, target, mock_predictor)
        amount = selected.amount_satang
        payment = settle_copy(bills, target)
        salary = q['salary']['monthly_satang'] if target.day == 28 else 0
        cumulative = cumulative + amount if cumulative is not None and amount is not None else None
        balance = balance - amount + salary - payment if balance is not None and amount is not None else None
        history[target.isoformat()] = amount  # already rounded to cents, including fallback
        points.append({'date': target.isoformat(), 'feature_row': row, 'predicted_non_bill_thb': thb(amount),
                       'cumulative_non_bill_thb': thb(cumulative), 'bill_payment_thb': thb(payment),
                       'salary_inflow_thb': thb(salary), 'projected_balance_thb': thb(balance),
                       'method': selected.method, 'reason': selected.reason,
                       'selection_reason': selected.selection_reason, 'source_id': selected.source_id})
    return {'contract_version': q['contract_version'], 'account_id': q['account_id'], 'origin': q['origin'],
            'request_sha256': digest(q), 'forecast_id': forecast_id or 'consumer-issue:' + digest(q),
            'issued_at': q['origin'], 'input_as_of': q['origin'], 'model_package_version': None,
            'horizon': q['horizon'], 'forecast_mode': 'MOCK_CONTRACT_EXAMPLE' if mock_predictor else 'ORIGIN_FROZEN',
            'aggregate': frozen.wire(), 'points': points,
            'forecast_dependent_claim': 'UNAVAILABLE' if cumulative is None else 'NOT_ASSESSED'}
