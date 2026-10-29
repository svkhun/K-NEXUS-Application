"""Hand-authored acceptance fixture, never installed by Application runtime.

These complete-day declarations exercise plumbing, not observed bank history,
synthetic research data, persona enrichment, or a USER/ACC mapping.
"""
from datetime import timedelta
from src.baseline_policy import digest


def history_fixture(account, now, n=7, amount=10000):
    origin = now.replace(hour=0, minute=0, second=0, microsecond=0)
    records = [dict(date=(origin.date()-timedelta(days=d)).isoformat(),
                    amount_satang=0 if d == 1 else amount, complete=True, reasons=[])
               for d in range(1, n+1)]
    return dict(account_id=account, origin=origin.isoformat(), version='acceptance-fixture.v1',
                source='HAND_AUTHORED_ACCEPTANCE_FIXTURE_NOT_LEDGER',
                source_sha256=digest(records), records=records)
