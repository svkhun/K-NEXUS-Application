"""Calendar-aware demo liquidity rules shared by the horizon and sweep guard."""
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from zoneinfo import ZoneInfo


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
    salary = float(prof["monthly_salary"])
    rows = [
        ("debt", str(prof.get("debt_type", "บิลผ่อนชำระ / บัตรเครดิต")), float(prof.get("fixed_debt", salary * .12)), 22),
        ("rent", str(prof.get("living_type", "ค่าเช่าห้อง/คอนโด")), float(prof.get("fixed_rent", salary * .25)), 26),
        ("utilities", "ค่าน้ำ-ไฟ-อินเทอร์เน็ต", float(prof.get("fixed_utilities", salary * .05)), 27),
    ]
    result = []
    for kind, name, amount, day in rows:
        due = now.replace(day=day)
        if due.date() < now.date():
            due = due.replace(year=now.year + (now.month == 12), month=now.month % 12 + 1)
        due_date = due.strftime("%Y-%m-%d")
        bill_id = f"{kind}:{due_date}"
        paid = float((state or {}).get("paid_commitments", {}).get(bill_id, 0))
        result.append(dict(id=bill_id, kind=kind, name=name, original_amount=round(amount, 2),
                           paid_amount=round(paid, 2), amount=round(max(0, amount-paid), 2),
                           due_date=due_date, due_days=(due.date()-now.date()).days))
    return sorted(result, key=lambda row: row["due_days"])


def get_savings_capacity(state, prof, now=None):
    """Port the source project's opt-in savings estimate; amounts are demo THB."""
    now = now or demo_now(state)
    payday = next_payday(now)
    days = max(1, (payday.date() - now.date()).days)
    salary = float(prof["monthly_salary"])
    fixed = sum(row["amount"] for row in commitments(prof, now, state))
    buffer = max(500.0, float(prof.get("emergency_buffer", salary * .12)))
    daily = max(0.0, float(prof.get("avg_daily_spend", 600)), float(state["daily_spent_today"]))
    living = round(daily * days, 2)
    end = round(float(state["main_balance"]) - living - fixed, 2)
    safe = max(0.0, round(end - buffer, 2))
    return dict(days_to_payday=days, payday_date=payday.strftime("%Y-%m-%d"),
                projected_daily_spend=daily, projected_living_cost=living,
                fixed_commitments=round(fixed, 2), emergency_buffer=round(buffer, 2),
                projected_end_balance=end, formula_safe_to_save=safe, safe_to_save=safe,
                forecast_reserve_adjustment=0.0, max_sweep_amount=min(500.0, safe))


def horizon(prof, state, projection=None):
    now = demo_now(state)
    payday = next_payday(now)
    days = (payday.date() - now.date()).days
    salary = float(prof["monthly_salary"])
    balance = float(state["main_balance"])
    spent = float(state["daily_spent_today"])
    burn = spent * .5 + float(prof.get("avg_daily_spend", 600)) * .5
    rows = commitments(prof, now, state)
    upcoming = [row for row in rows if row["due_days"] < days]
    deductions = 0
    for row in rows:
        # Alert only on a debit before the next salary, not a normal balance dip.
        if row["due_days"] < days:
            deductions += row["amount"]
            estimate = balance - burn * row["due_days"] - deductions
            row["projected_after_payment"] = round(estimate if row["due_days"] == 0 else (projection or {}).get(row["due_date"], estimate), 2)
            row["is_at_risk"] = row["amount"] > 0 and row["projected_after_payment"] < 0
        else:
            row["projected_after_payment"] = None
            row["is_at_risk"] = False
    fixed = sum(row["amount"] for row in upcoming)
    projected = round((projection or {}).get((payday-timedelta(days=1)).strftime("%Y-%m-%d"), balance - burn * days - fixed), 2)
    risk = any(row["is_at_risk"] for row in rows)
    normal = (balance < salary * .5 or state.get("scenario") == "normal_dip") and not risk
    savings = get_savings_capacity(state, prof, now)
    buffer = savings["emergency_buffer"]
    before_salary = [value for date, value in (projection or {}).items() if now.strftime("%Y-%m-%d") <= date < payday.strftime("%Y-%m-%d")]
    # Retain the web app's forecast guard in addition to the source's conservative
    # living-cost formula. Neither repeated sweeps nor a low model forecast may
    # consume the reserved bills, living costs or emergency buffer.
    surplus = max(0, round(min([savings["safe_to_save"], projected - buffer, balance - 500] + [value-buffer for value in before_salary]), 2))
    savings["safe_to_save"] = surplus
    savings["forecast_reserve_adjustment"] = round(savings["formula_safe_to_save"] - surplus, 2)
    savings["max_sweep_amount"] = min(500.0, surplus)
    suggested = round(min(500, balance * float(prof.get("recommended_sweep_pct", .08)) * .15, surplus), 2)
    state_name = "COMMITMENT_AT_RISK" if risk else "NORMAL_DIP_SAFE" if normal else "HEALTHY_HORIZON"
    nudge = "มีภาระใกล้ถึงกำหนดที่เงินอาจไม่พอ ลองถอนเงินออมตามจำนวนที่ต้องใช้หรือปรับแผนใช้จ่าย" if risk else "ยอดเงินลดตามรอบการใช้จ่าย ภาระก่อนเงินเดือนยังมีเงินรองรับ จึงไม่แจ้งเตือน" if normal else "มีเงินรองรับภาระก่อนเงินเดือน ออมได้เฉพาะส่วนที่เหลือหลังกันเงินใช้จ่ายและเงินสำรอง"
    health = round(max(0, min(100, (balance-fixed) / max(1, balance) * 100)), 1)
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
        "HEALTHY_HORIZON": "สภาพคล่องดี",
    }
    return {
        "days_to_payday": days,
        "payday_date": payday.strftime("%Y-%m-%d"),
        "as_of_date": now.strftime("%Y-%m-%d"),
        "scenario": state.get("scenario", "default"),
        "current_balance": round(balance, 2),
        "horizon_health_pct": health,
        "burn_rate_pct": round(100-health, 1),
        "horizon_state": state_name,
        "horizon_badge_th": badges[state_name],
        "alert_suppressed": not risk,
        "commitment_at_risk": risk,
        "total_recurring_commitments": round(fixed, 2),
        "recurring_commitments": rows,
        "projected_month_end_liquidity": max(0, projected),
        "raw_projected_end_balance": projected,
        "deficit_amount": round(max([0] + [-row["projected_after_payment"] for row in upcoming if row["is_at_risk"]]), 2),
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
        "projected_daily_burn": round(burn, 2),
        "nudge_message": nudge,
        "breakdown": {
            "rent": float(prof.get("fixed_rent", salary*.25)),
            "debt_emi": float(prof.get("fixed_debt", salary*.12)),
            "utilities": float(prof.get("fixed_utilities", salary*.05)),
            "emergency_buffer": buffer,
            "total_fixed_obligations": round(fixed, 2),
        },
    }
