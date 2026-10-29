"""Consumer implementation of H1-H5: bounded classification evidence only.

Opening enumeration is performed by bills.py before entering this module. Its
return value is a separate lookup; it must never replace the projection bills.
No producer semantic code or candidate helper is imported here.
"""
from collections import defaultdict
from datetime import timedelta
import hashlib
from .boundary import (_validator, check, day, digest, lineage, select_revisions, timestamp)
from .bills import DUE_DAYS

VERSION = '2.0.0-proposed.4'
SOURCE_KINDS = ('verified_source', 'synthetic_generator_explicit')


def latest(rows, keys, stable, origin, label):
    identities = {}
    for row in rows:
        if timestamp(row['available_at']) > origin:
            continue
        key = tuple(row[k] for k in keys)
        value = tuple(row[k] for k in stable)
        check(key not in identities or identities[key] == value, label + '_IDENTITY_CHANGED')
        identities[key] = value
    return select_revisions(rows, keys, origin, label)


def document(provenance, q, origin, resolver):
    lineage(provenance, origin, SOURCE_KINDS)
    check(resolver is not None, 'HISTORY_SOURCE_REQUIRED')
    raw = resolver(provenance['source'])
    check(hashlib.sha256(raw).hexdigest() == provenance['sha256'], 'HISTORY_ARTIFACT_HASH')
    doc = resolver.document(provenance['source'])
    check(isinstance(doc, dict) and isinstance(doc.get('account'), dict) and
          all(doc['account'].get(k) == q[k] for k in ('account_id', 'user_id')), 'HISTORY_SOURCE_ACCOUNT')
    return doc


def source_row(item, collection, q, origin, resolver):
    doc = document(item['provenance'], q, origin, resolver)
    source = item['provenance']['source']
    if source not in resolver._source_schema_checked:
        check(not any(_validator('source-facts.schema.json', VERSION).iter_errors(doc)), 'HISTORY_SOURCE_ROW')
        resolver._source_schema_checked.add(source)
    ref = item['source_row']
    matches = [row for row in doc[collection] if row['row_id'] == ref['row_id']]
    check(ref['collection'] == collection and len(matches) == 1 and digest(matches[0]) == ref['sha256'], 'HISTORY_SOURCE_ROW')
    row = matches[0]
    check(timestamp(row['observed_at']) <= timestamp(row['available_at']) <= origin, 'HISTORY_SOURCE_ROW')
    keys = ('account_id', 'id') if collection == 'bill_facts' else ('account_id', 'source', 'id')
    stable = ('user_id', 'kind', 'due_date', 'source') if collection == 'bill_facts' else ('user_id', 'event_time', 'bill_instance_id')
    cache_key = (source, collection, origin)
    if cache_key not in resolver._selections:
        resolver._selections[cache_key] = latest(doc[collection], keys, stable, origin,
            'SOURCE_HISTORY_BILL' if collection == 'bill_facts' else 'SOURCE_HISTORY_RECEIPT')
    selected = resolver._selections[cache_key]
    reason = 'HISTORY_BILL_SOURCE_MISMATCH' if collection == 'bill_facts' else 'HISTORY_RECEIPT_SOURCE_MISMATCH'
    check(any(row == chosen for chosen in selected), reason)
    fields = ('id', 'account_id', 'user_id', 'revision', 'source', 'kind', 'due_date', 'original_satang') if collection == 'bill_facts' else tuple(k for k in row if k != 'row_id')
    check(all(row[k] == item.get(k) for k in fields), reason)
    if collection == 'bill_facts':
        derivation = row['derivation']
        if derivation['kind'] == 'KNOWN_EFFECTIVE_SCHEDULE':
            schedules = [s for s in doc['schedules'] if timestamp(s['known_at']) <= origin and
                         timestamp(s['available_at']) <= origin and s['effective_from'] <= row['due_date']]
            schedules = select_revisions(schedules, ('schedule_id',), origin, 'SOURCE_SCHEDULE')
            check(len(schedules) == 1, 'HISTORY_NO_KNOWN_SCHEDULE')
            s = schedules[0]
            check(s['schedule_id'] == derivation.get('schedule_id') and s['revision'] == derivation.get('revision') and
                  s['monthly_amounts_satang'][row['kind']] == row['original_satang'], 'HISTORY_BILL_SOURCE_MISMATCH')
        else:
            check(derivation['kind'] in ('EXPLICIT_PREEXISTING_OBLIGATION', 'EXPLICIT_BILL_OBSERVATION') and
                  bool(derivation.get('declaration_id')), 'HISTORY_BILL_SOURCE_MISMATCH')
    return row


def opening_source(opening, doc, q, origin, resolver):
    """New profile proves frozen opening values from independent bill/receipt facts."""
    bill_rows = latest(doc.get('bill_source_observations', []), ('account_id', 'id'),
                       ('user_id', 'kind', 'due_date', 'source'), origin, 'SOURCE_HISTORY_BILL')
    receipt_rows = latest(doc.get('payment_receipts', []), ('account_id', 'source', 'id'),
                          ('user_id', 'event_time', 'bill_instance_id'), origin, 'SOURCE_HISTORY_RECEIPT')
    for bill in opening:
        found = [b for b in bill_rows if b['id'] == bill['id']]
        check(len(found) == 1, 'HISTORY_BILL_SOURCE_MISMATCH')
        source_row(found[0], 'bill_facts', q, origin, resolver)
        check(all(bill[k] == found[0][k] for k in ('id', 'kind', 'due_date', 'original_satang')), 'HISTORY_BILL_SOURCE_MISMATCH')
        facts = []
        for receipt in receipt_rows:
            if receipt['bill_instance_id'] == bill['id'] and timestamp(receipt['event_time']) < origin:
                source_row(receipt, 'receipt_facts', q, origin, resolver)
                facts.append({k: receipt[k] for k in ('id', 'source', 'amount_satang', 'event_time', 'available_at')})
        check(sorted(facts, key=lambda e: (e['source'], e['id'])) ==
              sorted(bill['payment_events'], key=lambda e: (e['source'], e['id'])), 'HISTORY_RECEIPT_SOURCE_MISMATCH')


def classification(q, opening, selected, origin, resolver):
    h = q['historical_bill_references']
    check(all(h[k] == q[k] for k in ('account_id', 'user_id')), 'HISTORY_ACCOUNT_MISMATCH')
    check(h['as_of'] == q['origin'] and timestamp(h['as_of']) <= timestamp(h['available_at']) <= origin and
          h['provenance']['as_of'] == h['as_of'], 'HISTORY_AS_OF_MISMATCH')
    doc = document(h['provenance'], q, origin, resolver)
    lower = origin.date() - timedelta(days=28)
    window = [r for r in selected if lower <= timestamp(r['event_time']).date() and timestamp(r['event_time']) < origin]
    needed = {r['bill_instance_id'] for r in window if r['direction'] == 'DR' and 'bill_instance_id' in r}
    for b in h['bills']:
        if timestamp(b['available_at']) <= origin:
            check(all(b[k] == q[k] for k in ('account_id', 'user_id')), 'HISTORY_ACCOUNT_MISMATCH')
    bills = latest(h['bills'], ('id',), ('kind', 'due_date', 'source'), origin, 'HISTORY_BILL')
    index = {b['id']: b for b in opening}
    events = {(e['source'], e['id']) for b in opening for e in b['payment_events']}
    for b in bills:
        check(b['id'] not in index, 'HISTORY_OPENING_ID_COLLISION')
        check(b['id'] in needed, 'UNREFERENCED_HISTORY_BILL')
        check(b['id'] == f"{b['kind']}:{b['due_date']}" and day(b['due_date']).day == DUE_DAYS[b['kind']], 'CONFLICTING_HISTORY_BILL_ID')
        check(day(b['due_date']) < origin.date().replace(day=1), 'HISTORY_NOT_PRIOR_MONTH')
        check(b['observed_at'] == q['origin'] and timestamp(b['observed_at']) <= timestamp(b['available_at']) <= origin, 'HISTORY_AFTER_ORIGIN')
        source_row(b, 'bill_facts', q, origin, resolver)
        check(b['provenance']['as_of'] == b['observed_at'], 'HISTORY_AS_OF_MISMATCH')
        receipts = latest(b['payment_events'], ('source', 'id'), ('event_time', 'account_id', 'bill_instance_id'), origin, 'HISTORY_RECEIPT')
        for e in receipts:
            check(e['account_id'] == q['account_id'] and e['user_id'] == q['user_id'] and e['bill_instance_id'] == b['id'], 'HISTORY_RECEIPT_IDENTITY')
            check(e['source'] in q['source_registry']['sources'], 'UNREGISTERED_HISTORY_RECEIPT_SOURCE')
            check(timestamp(e['event_time']) < origin and timestamp(e['event_time']) <= timestamp(e['available_at']) <= origin, 'HISTORY_RECEIPT_TIME')
            source_row(e, 'receipt_facts', q, origin, resolver)
            check(e['provenance']['as_of'] == e['available_at'], 'HISTORY_RECEIPT_AS_OF_MISMATCH')
            key = (e['source'], e['id'])
            check(key not in events, 'DUPLICATE_SOURCE_PAYMENT_EVENT')
            events.add(key)
        check(sum(e['amount_satang'] for e in receipts) == b['paid_satang'] == b['original_satang'], 'HISTORY_NOT_SETTLED')
        index[b['id']] = dict(b, payment_events=receipts)
    opening_source(opening, doc, q, origin, resolver)
    consumption = defaultdict(list)
    for r in window:
        if r['direction'] == 'DR' and 'bill_payment_event_id' in r:
            consumption[(r['source'], r['bill_payment_event_id'])].append(r['event_time'][:10])
    conflicts = {d for dates in consumption.values() if len(dates) > 1 for d in dates}
    return index, conflicts
