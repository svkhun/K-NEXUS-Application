"""Live baseline projection, distinct from sealed midnight issuance."""
import copy
from datetime import timedelta
from src.flowsense_engine import demo_now, next_payday, commitments
from src.baseline_policy import select_spending, satang, thb, digest, ADAPTER


def forecast(prof, state, *, now=None):
    projected = copy.deepcopy(state)
    now = now or demo_now(projected)
    basis = select_spending(projected, now)
    daily = basis['daily_satang']
    balance = satang(projected['main_balance'])
    spent = satang(projected['daily_spent_today'])
    payday = next_payday(now)
    today = dict(date=now.date().isoformat(), day_name=now.strftime('%a'),
        is_weekend=now.weekday() >= 5, days_to_payday=(payday.date()-now.date()).days,
        predicted_spend=None, actual_spend=thb(spent), posted_today_spend=thb(spent),
        salary_inflow=0, commitment_payment=0, projected_balance=thb(balance),
        status='CURRENT_SNAPSHOT', is_past=False, is_today=True, is_future=False,
        method='POSTED_SESSION_SNAPSHOT', source='SYNTHETIC_SESSION_STATE')
    commitments(prof, now, projected)
    future = []
    for offset in range(1, 31):
        day = now + timedelta(days=offset)
        rows = commitments(prof, day, projected)
        due = [b for b in rows if b['due_days'] <= 0 and b['amount'] > 0]
        payment = sum(satang(b['amount']) for b in due)
        for bill in due:
            projected.setdefault('paid_commitments', {})[bill['id']] = bill['original_amount']
        inflow = satang(prof['monthly_salary']) if day.day == 28 else 0
        balance = balance - daily - payment + inflow if balance is not None and daily is not None else None
        future.append(dict(date=day.date().isoformat(), day_name=day.strftime('%a'),
            is_weekend=day.weekday() >= 5, days_to_payday=(next_payday(day).date()-day.date()).days,
            predicted_spend=thb(daily), actual_spend=None, salary_inflow=thb(inflow),
            commitment_payment=thb(payment), projected_balance=thb(balance),
            status='FUTURE' if daily is not None else 'UNAVAILABLE',
            is_past=False, is_today=False, is_future=True, method=basis['method'],
            source=basis['source'], reason=basis['reason'], selection_id=basis['selection_id']))
    minimum = min(p['projected_balance'] for p in [today]+future) if daily is not None else None
    snapshot = dict(adapter=ADAPTER, basis=basis['selection_id'], date=now.date().isoformat(),
        balance=state['main_balance'], spent=projected['daily_spent_today'],
        bills=state.get('bill_instances', {}), paid=state.get('paid_commitments', {}), salary=prof['monthly_salary'])
    return dict(forecast_days=30, history_days=0, data_mode='synthetic_demo',
        forecast_mode='LIVE_INTRADAY_BASELINE', baseline_mode=state.get('baseline_mode', 'BASELINE'),
        adapter_version=ADAPTER, spending_basis=basis, snapshot_id=digest(snapshot),
        model_architecture='EXPLAINABLE_BASELINE', model_enabled=False,
        model_package_version=None, model_gate='NO_QUALIFYING_FLOWSENSE_PACKAGE',
        forecast_limitation='Baseline ไม่ใช่ validated AI forecast; ยังไม่ประเมินความแม่นยำ 30 วัน',
        history_provenance=dict(source=basis['source'], account_mapping='NO_LEGACY_USER_MAPPING'),
        origin_kind='LIVE_CURRENT_BALANCE_NOT_MIDNIGHT_OPENING', input_as_of=now.isoformat(),
        projection_start=future[0]['date'], assumed_spending_today_remaining=0,
        origin_assumption='Current balance includes posted debits; future daily burn starts tomorrow. No additional assumed debit today; manual daily budget is separate.',
        posted_today_provenance=copy.deepcopy(state.get('seeded_posted_today')),
        bill_projection_assumption='Remaining overdue/due bills paid on first future day/due date on a copy. Salary28 is synthetic; no actual settlement or salary credit.',
        today_index=0, current_datetime=now.isoformat(),
        days_to_payday=(payday.date()-now.date()).days, payday_date=payday.date().isoformat(),
        current_balance=today['projected_balance'], min_projected_balance=minimum,
        liquidity_health='UNAVAILABLE' if minimum is None else 'BASELINE_NONNEGATIVE' if minimum >= 0 else 'RISK_OF_DEFICIT',
        projection_summary='สถานการณ์จากยอดปัจจุบัน ใช้สมมติฐานตั้งแต่วันพรุ่งนี้ แยกบิลออกจากรายจ่ายประจำวัน',
        timeline=[today]+future)
