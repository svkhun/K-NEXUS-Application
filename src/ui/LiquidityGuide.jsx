import React from 'react';
import { ArrowRight } from 'lucide-react';
import { PlanIcon, SavingsIcon, WithdrawIcon } from './NexusIcons';
const money = (value) => (value == null ? '—' : Number(value).toLocaleString('th-TH', { maximumFractionDigits: 2 }));

export default function LiquidityGuide({ profile, horizon, openTab, onWithdraw }) {
  const futureDays = Math.max(0, horizon.days_to_payday - 1);
  const exampleWithdrawal = Math.min(1000, profile.vault_balance);
  return <section className="liquidity-guide" aria-labelledby="liquidity-guide-title">
    <div className="liquidity-guide-intro"><span>ทำให้เงินพร้อมใช้ถึงวันเงินเดือน</span><h2 id="liquidity-guide-title">เห็นเงินที่ใช้ได้ แล้วเลือกวิธีให้เงินพอ</h2><p>เริ่มจากแยกบิลและเงินเผื่อฉุกเฉินออกจากยอดบัญชี แล้วเลือกปรับรายจ่ายหรือดึงเงินออมที่มีมาใช้</p></div>
    <div className="liquidity-allocation" aria-label="เงินบัญชีหลักแบ่งใช้อย่างไร"><div><span>บัญชีหลักตอนนี้</span><strong>฿{money(profile.main_balance)}</strong></div><div className="allocation-bills"><span>− บิลก่อนเงินเดือน</span><strong>฿{money(horizon.total_recurring_commitments)}</strong></div><div className="allocation-reserve"><span>− เงินสำรองในแผน</span><strong>฿{money(horizon.emergency_buffer)}</strong></div><div className="allocation-available"><span>เหลือแบ่งใช้ {horizon.days_to_payday} วัน</span><strong>฿{money(horizon.spendable_balance)}</strong></div></div>
    {horizon.budget_reserve_shortfall > 0 && <p className="liquidity-shortfall">บิลและเงินสำรองยังขาด ฿{money(horizon.budget_reserve_shortfall)} จึงยังไม่มีเงินส่วนที่แบ่งใช้ได้</p>}
    <div className="liquidity-actions">
      <button className="liquidity-action spend-action" onClick={() => { document.getElementById('daily-budget')?.focus(); }}><span className="action-colour"><PlanIcon size={23}/></span><span><strong>ลองลดรายจ่าย</strong><b>{futureDays ? `ลดวันละ ฿50 → เหลือเพิ่ม ฿${money(futureDays * 50)}` : 'ลองตั้งงบสำหรับวันนี้'}</b><small>{futureDays ? `ตัวอย่าง ${futureDays} วันตั้งแต่พรุ่งนี้ถึงก่อนเงินเดือน หากลดรายจ่ายได้จริง` : 'ดูผลในช่องงบรายวันด้านล่าง'}</small><em>ลองตั้งงบด้านล่าง <ArrowRight size={14}/></em></span></button>
      <button className="liquidity-action withdraw-action" disabled={exampleWithdrawal <= 0} onClick={onWithdraw}><span className="action-colour"><WithdrawIcon size={23}/></span><span><strong>ใช้เงินออมเมื่อจำเป็น</strong><b>{exampleWithdrawal > 0 ? `ถอน ฿${money(exampleWithdrawal)} → บัญชีหลัก +฿${money(exampleWithdrawal)}` : 'ยังไม่มีเงินออมให้ถอน'}</b><small>ตัวอย่างย้ายเงินเดิมกลับมาใช้ เงินรวมไม่เพิ่ม คุณเลือกจำนวนและยืนยันเอง</small><em>เลือกจำนวนที่จะถอน <ArrowRight size={14}/></em></span></button>
      <button className="liquidity-action save-action" onClick={() => openTab('savings')}><span className="action-colour"><SavingsIcon size={23}/></span><span><strong>ออมเฉพาะส่วนที่เหลือ</strong><b>{horizon.savings_capacity == null ? 'ข้อมูลไม่พอสำหรับประมาณการออม' : horizon.savings_capacity > 0 ? `ส่วนที่พร้อมออม ฿${money(horizon.savings_capacity)}` : 'รอบนี้ยังไม่แนะนำให้ออมเพิ่ม'}</b><small>กันบิล ค่าใช้ชีวิต และเงินสำรองก่อน ช่วยไม่ให้แยกเงินที่ต้องใช้ไปออม</small><em>ดูแผนการออม <ArrowRight size={14}/></em></span></button>
    </div>
  </section>;
}
