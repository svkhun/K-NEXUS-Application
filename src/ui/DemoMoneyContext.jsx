import React from 'react';
import { budgetExplanation } from './demoContext.mjs';
const money = n => n == null ? 'ยังไม่พร้อมแสดง' : `฿${n.toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export default function DemoMoneyContext({ horizon, profile }) {
  const explanation = budgetExplanation(horizon);
  const unknownSaving = horizon.savings_capacity == null;
  if (!explanation && !unknownSaving && horizon.savings_capacity !== 0) return null;
  return <aside className="demo-money-context" aria-label="ความหมายของยอดเงิน"><strong>ยอดบัญชีหลัก {money(profile.main_balance)} · เงินออม {money(profile.vault_balance)}</strong>
    {explanation && <p>{explanation}</p>}
    {horizon.savings_capacity === 0 && <p>ความสามารถออมเพิ่ม ฿0 · หลังเผื่อค่าใช้ชีวิต {money(horizon.savings_estimate?.projected_living_cost)} บิล {money(horizon.savings_estimate?.fixed_commitments)} และเงินสำรอง {money(horizon.savings_estimate?.emergency_buffer)} แล้ว ยังไม่มีส่วนเกินพร้อมออม</p>}
    {unknownSaving && <p>ยังประมาณการความสามารถออมไม่ได้ · {horizon.savings_estimate?.reason || horizon.spending_basis?.reason || 'ข้อมูลประมาณการไม่ครบ'}</p>}
  </aside>;
}
