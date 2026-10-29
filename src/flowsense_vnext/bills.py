"""Frozen opening validation and independent calendar enumeration."""
from datetime import date, timedelta
from .boundary import check, day, lineage, select_revisions, timestamp

DUE_DAYS = {'debt': 22, 'rent': 26, 'utilities': 27}


def next_month(month):
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def expected_instances(first, through, amounts):
    result = {}
    month = first.replace(day=1)
    while month <= through:
        for kind, due in DUE_DAYS.items():
            target = month.replace(day=due)
            if amounts[kind] > 0 and target <= through:
                result[f'{kind}:{target}'] = (kind, target.isoformat(), amounts[kind])
        month = next_month(month)
    return result


def opening_bills(q, origin):
    opening = q['opening_snapshot']
    observed = timestamp(opening['as_of'])
    check(observed <= timestamp(opening['available_at']) <= origin, 'OPENING_AFTER_ORIGIN')
    lineage(opening['provenance'], origin)
    check(opening['provenance']['as_of'] == opening['as_of'], 'OPENING_PROVENANCE_MISMATCH')
    revisions = q['bill_calendar']['revisions']
    for schedule in revisions:
        check(timestamp(schedule['known_at']) <= timestamp(schedule['available_at']) <= origin, 'SCHEDULE_AFTER_ORIGIN')
    schedules = select_revisions(revisions, ('schedule_id',), origin, 'SCHEDULE')
    check(len(schedules) == 1, 'AMBIGUOUS_SCHEDULE')
    schedule = schedules[0]
    first = observed.date().replace(day=1)
    check(day(schedule['effective_from']) <= first, 'SCHEDULE_EFFECTIVE_AFTER_OPENING')
    through = day(q['bill_calendar']['materialized_through'])
    check(through >= origin.date() + timedelta(days=q['horizon'] + 5), 'SHORT_BILL_LOOKAHEAD')
    expected = expected_instances(first, through, schedule['monthly_amounts_satang'])
    bills = select_revisions(q['bills'], ('id',), origin, 'BILL')
    check(all(timestamp(b['available_at']) <= origin for b in q['bills']), 'BILL_AFTER_ORIGIN')
    supplied = {b['id'] for b in bills}
    prior = opening['prior_overdue_ids']
    check(len(prior) == len(set(prior)), 'DUPLICATE_PRIOR_OVERDUE_ID')
    check(not set(prior).intersection(expected), 'INVALID_PRIOR_OVERDUE')
    check(set(expected) <= supplied, 'MISSING_BILL_ID')
    check(supplied <= set(expected).union(prior), 'EXTRA_BILL_ID')
    check(set(prior) <= supplied, 'MISSING_PRIOR_OVERDUE')
    seen_events = set()
    for bill in bills:
        identifier = bill['id']
        check(identifier == f"{bill['kind']}:{bill['due_date']}" and
              day(bill['due_date']).day == DUE_DAYS[bill['kind']], 'CONFLICTING_BILL_ID')
        if identifier in expected:
            check((bill['kind'], bill['due_date'], bill['original_satang']) == expected[identifier], 'CONFLICTING_BILL_ID')
        else:
            check(day(bill['due_date']) < first and bill['paid_satang'] < bill['original_satang'], 'INVALID_PRIOR_OVERDUE')
        check(timestamp(bill['observed_at']) <= timestamp(bill['available_at']) <= origin, 'BILL_AFTER_ORIGIN')
        check(timestamp(bill['observed_at']) == observed, 'BILL_OPENING_OBSERVATION_MISMATCH')
        check(0 <= bill['paid_satang'] <= bill['original_satang'], 'INVALID_PAID_BOUNDS')
        total = 0
        for event in bill['payment_events']:
            key = (event['source'], event['id'])
            check(key not in seen_events, 'DUPLICATE_SOURCE_PAYMENT_EVENT')
            seen_events.add(key)
            check(timestamp(event['event_time']) <= timestamp(event['available_at']) <= observed, 'PAYMENT_AFTER_OBSERVATION')
            total += event['amount_satang']
        check(total == bill['paid_satang'], 'PAID_EVENT_SUM_MISMATCH')
        if opening['assumption'] == 'CURRENT_MONTH_UNPAID_PRIOR_MONTHS_SETTLED' and identifier not in prior:
            check(bill['paid_satang'] == 0, 'OPENING_ASSUMPTION_CONFLICT')
    return bills
