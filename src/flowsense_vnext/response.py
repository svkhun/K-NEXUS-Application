"""Independent wire assertion path: audit claims without invoking any real model."""
from datetime import timedelta
from decimal import Decimal
from .boundary import canonical, check, decode, digest, money, shape, thb, timestamp
from .ingestion import prepare
from .projection import (Selection, aggregate, feature_row, features_only, model_eligibility,
                         select, settle_copy)


def validate_response(payload, response, *, mock_predictor=None, previous_issue=None, resolver=None):
    state = prepare(payload, resolver=resolver)
    q = decode(state.request_bytes)
    r = decode(response) if isinstance(response, (bytes, str)) else decode(canonical(response))
    # Select schema from REQUEST envelope, never infer authorization from response fields.
    from .boundary import _validator, finite_tree
    finite_tree(r)
    schema = ('forecast.' if q['request_kind'] == 'FULL_FORECAST' else '') + 'response.schema.json'
    check(not any(_validator(schema, q['contract_version']).iter_errors(r)), 'SCHEMA_INVALID')
    check(r['request_sha256'] == digest(q), 'ISSUED_SNAPSHOT_MISMATCH')
    if previous_issue is not None:
        same_origin = (r['account_id'], r['origin']) == (previous_issue['account_id'], previous_issue['origin'])
        same_id = r.get('forecast_id') == previous_issue.get('forecast_id')
        check(not (same_origin or same_id) or canonical(r) == canonical(previous_issue), 'ISSUED_SNAPSHOT_IMMUTABLE')
    if q['request_kind'] == 'FEATURE_ONLY':
        check(r == features_only(q, resolver=resolver), 'FEATURE_RESPONSE_MISMATCH')
        return
    check(r['horizon'] == q['horizon'] and len(r['points']) == q['horizon'], 'POINT_COUNT_MISMATCH')
    check(all(r[k] == q['origin'] for k in ('origin', 'issued_at', 'input_as_of')), 'ISSUANCE_TIME_MISMATCH')
    check(r['account_id'] == q['account_id'] and r['contract_version'] == q['contract_version'], 'RESPONSE_IDENTITY_MISMATCH')
    monetary = ('predicted_non_bill_thb', 'cumulative_non_bill_thb', 'bill_payment_thb',
                'salary_inflow_thb', 'projected_balance_thb')
    for point in r['points']:
        for key in monetary:
            value = point[key]
            check(value is None or Decimal(str(value)) * 100 == money(value), 'WIRE_MONEY_PRECISION')
    model_claim = any(p['method'] == 'MODEL' for p in r['points'])
    expected_package = q['model_eligibility']['package_version'] if model_claim else None
    check(r['model_package_version'] == expected_package and
          (not model_claim or expected_package not in (None, '2026.10.27.1')), 'METHOD_PACKAGE_MISMATCH')
    frozen = aggregate(state)
    check(r['aggregate'] == frozen.wire(), 'AGGREGATE_MISMATCH')
    history = dict(state.history)
    bills = decode(state.bills_bytes)
    balance, cumulative = q['opening_balance']['amount_satang'], 0
    for offset, point in enumerate(r['points']):
        target = timestamp(q['origin']).date() + timedelta(days=offset)
        row = feature_row(target, history, bills)
        check(point['date'] == target.isoformat(), 'POINT_DATE_MISMATCH')
        check(point['feature_row'] == row, 'FEATURE_ROW_MISMATCH')
        if point['method'] == 'MODEL':
            check(mock_predictor is None and point['predicted_non_bill_thb'] is not None, 'METHOD_PACKAGE_MISMATCH')
            check(model_eligibility(q, row) == 'MODEL_ELIGIBLE', 'METHOD_SOURCE_MISMATCH')
            # Already rounded numeric witness checks only the claim's semantics.
            selected = Selection(money(point['predicted_non_bill_thb']), 'MODEL', 'FINITE_MODEL_OUTPUT',
                                 expected_package, 'MODEL_ELIGIBLE')
        else:
            selected = select(q, frozen, row, offset, target, mock_predictor)
        check([point[k] for k in ('method', 'reason', 'selection_reason', 'source_id')] ==
              [selected.method, selected.reason, selected.selection_reason, selected.source_id], 'METHOD_SOURCE_MISMATCH')
        amount = selected.amount_satang
        check(point['predicted_non_bill_thb'] == thb(amount), 'PREDICTION_MISMATCH')
        cumulative = cumulative + amount if cumulative is not None and amount is not None else None
        check(point['cumulative_non_bill_thb'] == thb(cumulative), 'CUMULATIVE_OR_NULL_MISMATCH')
        payment = settle_copy(bills, target)
        salary = q['salary']['monthly_satang'] if target.day == 28 else 0
        check(point['bill_payment_thb'] == thb(payment) and point['salary_inflow_thb'] == thb(salary), 'PROJECTION_PAYMENT_MISMATCH')
        balance = balance - amount + salary - payment if balance is not None and amount is not None else None
        check(point['projected_balance_thb'] == thb(balance), 'BALANCE_OR_NULL_MISMATCH')
        history[target.isoformat()] = amount
    mode = 'MOCK_CONTRACT_EXAMPLE' if mock_predictor else 'ORIGIN_FROZEN'
    claim = 'UNAVAILABLE' if cumulative is None else 'NOT_ASSESSED'
    check(r['forecast_mode'] == mode and r['forecast_dependent_claim'] == claim, 'MODE_OR_CLAIM_MISMATCH')
