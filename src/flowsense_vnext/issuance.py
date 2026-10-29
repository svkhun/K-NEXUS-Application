"""Opt-in local durable issue registry, never opened during application startup.

Canonical bytes are immutable by (account, origin) AND forecast ID, including after
process restart. This does not prove the wall-clock time of actual issuance.
"""
from dataclasses import dataclass
from contextlib import closing
import sqlite3
from .boundary import canonical, check, decode
from .response import validate_response


@dataclass(frozen=True)
class IssuedRecord:
    account_id: str
    origin: str
    forecast_id: str
    request_sha256: str
    opening_snapshot_id: str
    balance_snapshot_id: str
    response_bytes: bytes


class IssueRegistry:
    def __init__(self, path):
        self.path = str(path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS issues (account TEXT, origin TEXT, forecast_id TEXT UNIQUE, '
                       'request_sha256 TEXT, opening_id TEXT, balance_id TEXT, body BLOB, PRIMARY KEY(account, origin))')

    def read(self, account, origin):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT * FROM issues WHERE account=? AND origin=?', (account, origin)).fetchone()
        return IssuedRecord(*row) if row else None

    def issue(self, request, response, *, mock_predictor=None, resolver=None):
        q = decode(request) if isinstance(request, (str, bytes)) else decode(canonical(request))
        r = decode(response) if isinstance(response, (str, bytes)) else decode(canonical(response))
        validate_response(q, r, mock_predictor=mock_predictor, resolver=resolver)
        check(q['request_kind'] == 'FULL_FORECAST', 'FULL_FORECAST_REQUIRED')
        body = canonical(r)
        record = IssuedRecord(q['account_id'], q['origin'], r['forecast_id'], r['request_sha256'],
                              q['opening_snapshot']['snapshot_id'], q['opening_balance']['snapshot_id'], body)
        with closing(sqlite3.connect(self.path, isolation_level='IMMEDIATE')) as db, db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM issues WHERE (account=? AND origin=?) OR forecast_id=?',
                                  (record.account_id, record.origin, record.forecast_id)).fetchall()
            check(all(row == tuple(record.__dict__.values()) for row in existing), 'ISSUED_SNAPSHOT_IMMUTABLE')
            if not existing:
                db.execute('INSERT INTO issues VALUES (?,?,?,?,?,?,?)', tuple(record.__dict__.values()))
        return record
