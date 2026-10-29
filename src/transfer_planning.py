"""Explainable transfer planning on synthetic state; no fraud probability claims."""
import copy
import hashlib
import json
from decimal import Decimal, ROUND_DOWN

from src.flowsense_engine import commitments, planning_commitments, demo_now, next_payday, reserve_settings
from src.baseline_policy import select_spending


def cents(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def plan_fingerprint(state, prof):
    state = copy.deepcopy(state)
    now = demo_now(state)
    values = {"date": now.strftime("%Y-%m-%d"), "balance": state["main_balance"],
              "spent": state["daily_spent_today"], "bills": planning_commitments(prof, now, state),
              "reserve": reserve_settings(state, prof)["amount"],
              "profile": {key: prof.get(key) for key in ("monthly_salary", "fixed_rent", "fixed_debt",
                          "fixed_utilities", "emergency_buffer")},
              "spending_basis": select_spending(state, now),
              "history_input": state.get('non_bill_history'),
              "scenario_input": state.get('spending_scenario'),
              "vault_balance": state.get('vault_balance')}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def bill_for_transfer(state, prof, bill_id, amount):
    if not bill_id:
        return None
    now = demo_now(state)
    days = (next_payday(now).date()-now.date()).days
    bill = next((row for row in planning_commitments(prof, now, state)
                 if row["id"] == bill_id and row["due_days"] < days and row["amount"] > 0), None)
    if not bill or amount > bill["amount"]:
        raise ValueError("บิลนี้ไม่อยู่ในแผนก่อนเงินเดือน จ่ายครบแล้ว หรือยอดโอนเกินยอดบิลคงเหลือ กรุณาตรวจรายการใหม่")
    return bill


def apply_planned_debit(state, amount, bill=None):
    state["main_balance"] = cents(Decimal(str(state["main_balance"]))-Decimal(str(amount)))
    if bill:
        paid = state.setdefault("paid_commitments", {})
        paid[bill["id"]] = cents(Decimal(str(paid.get(bill["id"], bill["paid_amount"])))+Decimal(str(amount)))
        state.setdefault('bill_instances', {}).setdefault(bill['id'],
            {key: bill[key] for key in ('id', 'kind', 'name', 'due_date', 'original_amount', 'paid_amount')})['paid_amount'] = paid[bill['id']]
    else:
        state["daily_spent_today"] = cents(Decimal(str(round(state.get("daily_spent_today", 0), 2)))+Decimal(str(amount)))


def transfer_impact(state, prof, amount, bill_id=None):
    state = copy.deepcopy(state)
    now = demo_now(state)
    days = max(1, (next_payday(now).date()-now.date()).days)
    bill = bill_for_transfer(state, prof, bill_id, amount)
    buffer = reserve_settings(state, prof)["amount"]

    def summary(account):
        rows = [row for row in planning_commitments(prof, now, account) if row["due_days"] < days]
        fixed = cents(sum(Decimal(str(row["amount"])) for row in rows))
        available = Decimal(str(account["main_balance"]))-Decimal(str(fixed))-Decimal(str(buffer))
        return {"balance": round(account["main_balance"], 2), "bills_remaining": fixed,
                "available_after_reserves": cents(available),
                "average_per_day": cents(max(Decimal(0), available)/days),
                "reserve_shortfall": cents(max(Decimal(0), -available))}

    after = copy.deepcopy(state)
    apply_planned_debit(after, amount, bill)
    before_summary, after_summary = summary(state), summary(after)
    from src.liquidity_forecast import forecast
    for account, result in ((state, before_summary), (after, after_summary)):
        path = forecast(prof, account, now=now)
        result['forecast_minimum'] = path['min_projected_balance']
        result['forecast_snapshot_id'] = path['snapshot_id']
    return {"data_mode": "synthetic_demo", "method": "BILLS_AND_BUFFER_ALLOCATION",
            "spending_basis": select_spending(state, now),
            "days_to_payday": days, "payday_date": next_payday(now).strftime("%Y-%m-%d"),
            "emergency_buffer": buffer, "before": before_summary, "after": after_summary,
            "matched_bill": bill, "reserve_at_risk": after_summary["reserve_shortfall"] > 0,
            "daily_reduction": cents(max(Decimal(0), Decimal(str(before_summary["average_per_day"]))-Decimal(str(after_summary["average_per_day"]))))}


def verification_guidance(purpose):
    choices = {
        "job": ("ตรวจงานก่อนจ่ายเงิน", ["ตรวจบริษัทและตำแหน่งงานผ่านเว็บไซต์หรือเบอร์ที่คุณหาเอง", "หากถูกขอให้จ่ายก่อนเริ่มงานหรือโอนเพิ่มเพื่อถอนรายได้ ให้หยุดตรวจสอบก่อน"]),
        "unlock": ("ตรวจเหตุผลที่ถูกขอให้โอนเพิ่ม", ["หยุดโอนเพิ่มเพื่อปลดล็อกเงินหรือถอนผลตอบแทน", "ตรวจสอบกับธนาคารผ่านช่องทางทางการ และเก็บหลักฐานการสนทนา"]),
        "changed_account": ("ยืนยันบัญชีใหม่กับผู้รับเดิม", ["โทรหาผู้รับผ่านเบอร์เดิมที่เคยใช้ ไม่ใช้เบอร์จากข้อความขอเปลี่ยนบัญชี", "ยืนยันชื่อผู้รับ เลขบัญชี และเหตุผลที่เปลี่ยนบัญชีก่อนตัดสินใจ"]),
        "general": ("ตรวจผู้รับผ่านช่องทางที่คุณรู้จัก", ["หยุดคุยกับผู้ที่เร่งให้โอน แล้วติดต่อผู้รับผ่านช่องทางอื่นที่รู้จักอยู่แล้ว", "ตรวจชื่อบัญชี ยอดเงิน และเหตุผลการโอน หากยังไม่มั่นใจให้ยกเลิกหรือสอบถามธนาคาร"]),
    }
    title, steps = choices[purpose]
    return {"title": title, "steps": steps,
            "note": "การทำตามคำแนะนำหรือครบเวลาพักไม่ได้รับรองว่าผู้รับปลอดภัย"}
