"""Calendar-aware demo liquidity rules shared by the horizon and sweep guard."""
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_DOWN
from zoneinfo import ZoneInfo
import copy
from src.baseline_policy import select_spending, satang, thb


def demo_now(state):
    # Financial presets must never move the calendar away from the real Thai date.
    now = datetime.now(ZoneInfo("Asia/Bangkok"))
    today = now.strftime("%Y-%m-%d")
    if state.get("spending_date", today) != today:
        state["daily_spent_today"] = 0.0
    state["spending_date"] = today
    return now


def next_payday(now):
    candidate = now.replace(day=28)
    if candidate.date() <= now.date():
        candidate = candidate.replace(year=now.year + (now.month == 12), month=now.month % 12 + 1)
    return candidate


def commitments(prof, now, state=None):
    """Materialize monthly instances, never move an unpaid due date.

    Opening assumption: this month's bills are unpaid, earlier months settled.
    This is a synthetic opening snapshot, not reconstructed historical debt.
    Reads may materialize instances but never debit money or mark bills paid.
    """
    state = state if state is not None else {}
    salary = float(prof["monthly_salary"])
    rows = [
        ("debt", str(prof.get("debt_type", "บิลผ่อนชำระ / บัตรเครดิต")), float(prof.get("fixed_debt", salary * .12)), 22),
        ("rent", str(prof.get("living_type", "ค่าเช่าห้อง/คอนโด")), float(prof.get("fixed_rent", salary * .25)), 26),
        ("utilities", "ค่าน้ำ-ไฟ-อินเทอร์เน็ต", float(prof.get("fixed_utilities", salary * .05)), 27),
    ]
    opening = state.setdefault("bill_opening_month", now.strftime("%Y-%m-01"))
    state.setdefault("bill_opening_assumption", "CURRENT_MONTH_UNPAID_PRIOR_MONTHS_SETTLED_SYNTHETIC")
    instances = state.setdefault("bill_instances", {})
    month = date.fromisoformat(opening)
    while month <= now.date().replace(day=1):
        for kind, name, amount, day in rows:
            due_date = month.replace(day=day).isoformat()
            bill_id = f"{kind}:{due_date}"
            instances.setdefault(bill_id, dict(id=bill_id, kind=kind, name=name,
                original_amount=round(amount, 2), paid_amount=0.0, due_date=due_date))
        month = month.replace(year=month.year + (month.month == 12), month=month.month % 12 + 1)
    result = []
    for bill in instances.values():
        # paid_commitments remains a compatibility mirror for pre-existing sessions.
        paid = min(bill["original_amount"], float(state.get("paid_commitments", {}).get(bill["id"], bill["paid_amount"])))
        bill["paid_amount"] = paid
        remaining = round(max(0, bill["original_amount"] - paid), 2)
        due_days = (date.fromisoformat(bill["due_date"]) - now.date()).days
        bill["status"] = "PAID" if remaining == 0 else "PARTIAL" if paid else "OVERDUE" if due_days < 0 else "OPEN"
        if remaining or bill["due_date"][:7] == now.strftime("%Y-%m"):
            result.append({**bill, "amount": remaining, "due_days": due_days, "overdue": remaining > 0 and due_days < 0})
    return sorted(result, key=lambda row: row["due_days"])


def reserve_settings(state, prof):
    """Session-owned planning preference; the seed is an explicit demo assumption."""
    suggested = max(500.0, float(prof.get("emergency_buffer", float(prof["monthly_salary"]) * .12)))
    return {"amount": round(float(state.get("reserve_amount", suggested)), 2),
            "suggested_amount": round(suggested, 2),
            "confirmed": state.get("reserve_confirmed", False),
            "minimum": 500, "maximum": 10_000_000,
            "source": "SYNTHETIC_PROFILE_SEED"}


def planning_commitments(prof, now, state):
    """Same session instances/schedule through payday, including next month.

    Materialize on a copy so a planning read cannot alter session bill state.
    """
    draft = copy.deepcopy(state)
    commitments(prof, now, draft)  # establish the actual opening month first
    commitments(prof, next_payday(now)-timedelta(days=1), draft)
    return commitments(prof, now, draft)


def get_savings_capacity(state, prof, now=None):
    """Reserve future burn from the shared live basis; unknown stays unavailable."""
    local = copy.deepcopy(state)
    now = now or demo_now(local)
    basis = select_spending(local, now)
    days = max(1, (next_payday(now).date()-now.date()).days)
    fixed = thb(sum(satang(r['amount']) for r in planning_commitments(prof, now, local) if r['due_days'] < days))
    buffer = reserve_settings(local, prof)['amount']
    daily = basis['daily_non_bill_thb']
    # Current balance already contains posted-today debits. The product adapter
    # assumes zero additional spending today, then daily burn tomorrow onwards.
    living = thb(basis['daily_satang'] * (days-1)) if daily is not None else None
    end = thb(satang(local['main_balance'])-satang(living)-satang(fixed)) if living is not None else None
    safe = max(0.0, round(end-buffer, 2)) if end is not None else None
    return dict(days_to_payday=days, payday_date=next_payday(now).date().isoformat(),
        spending_basis=basis, availability='UNAVAILABLE' if daily is None else 'AVAILABLE',
        reason=basis['reason'], future_burn_days=days-1, projected_daily_spend=daily,
        projected_living_cost=living, fixed_commitments=fixed, emergency_buffer=buffer,
        projected_end_balance=end, formula_safe_to_save=safe, safe_to_save=safe,
        forecast_reserve_adjustment=0.0 if safe is not None else None,
        max_sweep_amount=min(500.0, safe) if safe is not None else None)


def horizon(prof, state, projection=None):
    local = copy.deepcopy(state)
    now = demo_now(local)
    payday = next_payday(now)
    days = (payday.date()-now.date()).days
    salary = float(prof['monthly_salary'])
    balance = float(local['main_balance'])
    spent = float(local['daily_spent_today'])
    basis = select_spending(local, now)
    burn = basis['daily_non_bill_thb']
    if projection is None:
        from src.liquidity_forecast import forecast
        path = forecast(prof, local, now=now)
        projection = {p['date']: p['projected_balance'] for p in path['timeline']}
    commitments(prof, now, local)
    rows = planning_commitments(prof, now, local)
    upcoming = [row for row in rows if row['due_days'] < days]
    for row in rows:
        target = max(row['due_date'], (now+timedelta(days=1)).date().isoformat())
        value = projection.get(target)
        row['projected_after_payment'] = value if row['due_days'] < days and burn is not None else None
        row['is_at_risk'] = (row['amount'] > 0 and value < 0) if value is not None and row['due_days'] < days and burn is not None else None
    fixed = round(sum(row['amount'] for row in upcoming), 2)
    projected = projection.get((payday-timedelta(days=1)).date().isoformat()) if burn is not None else None
    risk = any(row['is_at_risk'] for row in rows) if burn is not None else None
    normal = (balance < salary*.5 or local.get('scenario') == 'normal_dip') and risk is False
    savings = get_savings_capacity(local, prof, now)
    buffer = savings['emergency_buffer']
    before_salary = [v for d, v in projection.items() if now.date().isoformat() <= d < payday.date().isoformat()]
    known = burn is not None and projected is not None and all(v is not None for v in before_salary)
    surplus = max(0, round(min([savings['safe_to_save'], projected-buffer, balance-500] + [v-buffer for v in before_salary]), 2)) if known else None
    savings['safe_to_save'] = surplus
    savings['forecast_reserve_adjustment'] = round(savings['formula_safe_to_save']-surplus, 2) if known else None
    savings['max_sweep_amount'] = min(500.0, surplus) if known else None
    savings['availability'] = 'AVAILABLE' if known else 'UNAVAILABLE'
    suggested = round(min(500, balance*float(prof.get('recommended_sweep_pct', .08))*.15, surplus), 2) if known else None
    state_name = 'UNAVAILABLE' if not known else 'COMMITMENT_AT_RISK' if risk else 'NORMAL_DIP_SAFE' if normal else 'HEALTHY_HORIZON'
    nudge = 'ข้อมูลไม่พอสำหรับประมาณการ; งบจากยอด บิล และเงินสำรองยังดูได้' if not known else 'มีภาระที่เงินอาจไม่พอ ลองปรับแผนใช้จ่าย' if risk else 'ผลตาม baseline และสมมติฐานที่แสดง ไม่ใช่การรับรองความปลอดภัย'
    health = round(max(0, min(100, (balance-fixed)/max(1, balance)*100)), 1) if known else None
    # Current balance already includes today's debits. Add them back only when
    # establishing today's total allowance, then deduct them once for what's left.
    def money(value):
        return Decimal(str(round(value, 2)))

    def cents(value):
        return float(max(Decimal(0), value).quantize(Decimal('0.01'), rounding=ROUND_DOWN))

    available = money(balance) - money(fixed) - money(buffer)
    daily_limit = cents((available + money(spent)) / days)
    spendable = cents(available)
    remaining_today = cents(min(available, money(daily_limit) - money(spent)))
    badges = {
        "COMMITMENT_AT_RISK": "ภาระใกล้ถึงกำหนดอาจไม่พอ",
        "NORMAL_DIP_SAFE": "เงินลดปกติ · ไม่แจ้งเตือน",
        "HEALTHY_HORIZON": "มีเงินรองรับตาม baseline",
        "UNAVAILABLE": "ข้อมูลไม่พอสำหรับประมาณการ",
    }
    return {
        "days_to_payday": days,
        "payday_date": payday.strftime("%Y-%m-%d"),
        "as_of_date": now.strftime("%Y-%m-%d"),
        "input_as_of": now.isoformat(),
        "scenario": local.get("scenario", "default"),
        "current_balance": round(balance, 2),
        "horizon_health_pct": health,
        "burn_rate_pct": round(100-health, 1) if health is not None else None,
        "horizon_state": state_name,
        "horizon_badge_th": badges[state_name],
        "alert_suppressed": not risk if known else None,
        "commitment_at_risk": risk,
        "total_recurring_commitments": round(fixed, 2),
        "recurring_commitments": rows,
        "bill_opening_assumption": local["bill_opening_assumption"],
        "projected_month_end_liquidity": projected,
        "raw_projected_end_balance": projected,
        "deficit_amount": round(max([0] + [-row["projected_after_payment"] for row in upcoming if row["is_at_risk"]]), 2) if known else None,
        "daily_safe_limit": daily_limit,
        "spent_today": round(spent, 2),
        "remaining_today": remaining_today,
        "spendable_balance": spendable,
        "budget_reserve_shortfall": round(max(0, fixed + buffer - balance), 2),
        "daily_budget_method": "BALANCE_PLUS_TODAY_SPEND_MINUS_BILLS_AND_BUFFER_DIVIDED_BY_DAYS",
        "savings_capacity": surplus,
        "savings_estimate": savings,
        "max_sweep_amount": savings["max_sweep_amount"],
        "recommended_sweep_amount": suggested,
        "emergency_buffer": buffer,
        "reserve_settings": reserve_settings(state, prof),
        "projected_daily_burn": burn,
        "spending_basis": basis,
        "forecast_availability": "AVAILABLE" if known else "UNAVAILABLE",
        "budget_basis": "DETERMINISTIC_BALANCE_BILLS_BUFFER_NOT_FORECAST",
        "projection_start": (now+timedelta(days=1)).date().isoformat(),
        "nudge_message": nudge,
        "breakdown": {
            "rent": float(prof.get("fixed_rent", salary*.25)),
            "debt_emi": float(prof.get("fixed_debt", salary*.12)),
            "utilities": float(prof.get("fixed_utilities", salary*.05)),
            "emergency_buffer": buffer,
            "total_fixed_obligations": round(fixed, 2),
        },
    }
