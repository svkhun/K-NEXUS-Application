import React from 'react';
import { ArrowRight, CircleAlert } from 'lucide-react';

const money = (value) => Number(value ?? 0).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function TransferPlanning({ result }) {
  const impact = result.liquidity_impact;
  if (!impact) return null;
  const sequence = result.transfer_sequence;
  const guidance = result.verification_guidance;
  const showGuidance = result.risk_tier === 'CRITICAL_ANOMALY' || result.transfer_purpose !== 'general';
  return <div className="transfer-planning">
    <section className={`transfer-impact ${impact.reserve_at_risk ? 'reserve-shortfall' : ''}`} aria-labelledby="transfer-impact-title">
      <span className="section-kicker">FLOWSENSE · ผลต่อแผนเงินของคุณ</span>
      <h4 id="transfer-impact-title">ถ้าโอนรายการนี้ เงินใช้ชีวิตจะเหลือเท่าไร</h4>
      <p>งบเฉลี่ยที่เหลือต่อวัน ใน {impact.days_to_payday} วันก่อนเงินเดือนออก</p>
      <div className="impact-comparison"><div><span>ก่อนโอน</span><strong>฿{money(impact.before.average_per_day)}</strong></div><ArrowRight size={20} aria-hidden="true" /><div><span>หลังโอน</span><strong>฿{money(impact.after.average_per_day)}</strong></div></div>
      <dl className="impact-breakdown"><div><dt>เงินบัญชีหลังโอน</dt><dd>฿{money(impact.after.balance)}</dd></div><div><dt>บิลที่ยังต้องกันไว้</dt><dd>฿{money(impact.after.bills_remaining)}</dd></div><div><dt>เงินสำรองที่ตั้งไว้</dt><dd>฿{money(impact.emergency_buffer)}</dd></div></dl>
      {impact.reserve_at_risk && <p className="impact-shortfall"><CircleAlert size={18} />เงินหลังโอนต่ำกว่าบิลและเงินสำรองรวม ฿{money(impact.after.reserve_shortfall)} คุณยังเลือกยกเลิกหรือกลับไปปรับแผนได้</p>}
      {impact.matched_bill && <p className="impact-bill-note">คุณระบุว่ารายการนี้จ่าย “{impact.matched_bill.name}” ฿{money(result.amount ?? (impact.before.balance-impact.after.balance))} จึงลดภาระบิลยอดเดียวกันและไม่หักงบซ้ำ การเลือกบิลไม่ได้ยืนยันตัวผู้รับหรือเปลี่ยนผลตรวจความเสี่ยง</p>}
      <details className="impact-method"><summary>ที่มาของงบและข้อสมมติ</summary><p>(เงินบัญชี − บิลที่ยังรอจ่ายก่อนเงินเดือน − เงินสำรอง) ÷ จำนวนวันที่เหลือ โดยปัดลงเป็นสตางค์ หากเงินไม่พอจะแสดงงบ 0 และแจ้งส่วนที่ขาด</p><p>เป็นสูตรจัดสรรจากข้อมูลสมมติ ไม่ใช่ความน่าจะเป็นหรือผลทำนายจาก AI สมมติว่าเงินเดือนเข้าวันที่ 28 และข้อมูลบิลครบ ไม่รวมเงินออมที่ยังไม่ได้ถอน งบเฉลี่ยนี้ต่างจาก “วันนี้ใช้เพิ่มได้อีก” ซึ่งหักยอดใช้วันนี้แล้ว</p></details>
    </section>
    {sequence?.count_today > 0 && <section className="transfer-sequence" aria-label="ยอดโอนสะสมให้ผู้รับนี้วันนี้"><strong>วันนี้คุณโอนให้ผู้รับนี้แล้ว {sequence.count_today} ครั้ง รวม ฿{money(sequence.sent_today)}</strong><p>ถ้ายืนยันครั้งนี้ ยอดรวมจะเป็น ฿{money(sequence.total_if_confirmed)}</p><small>นับเฉพาะรายการสำเร็จของโปรไฟล์นี้ใน session ทดลอง ไม่ใช่หลักฐานว่าผู้รับเป็นมิจฉาชีพ</small></section>}
    {showGuidance && guidance && <section className="transfer-guidance" aria-label="วิธีตรวจสอบก่อนตัดสินใจ"><h4>{guidance.title}</h4><ol>{guidance.steps.map((step) => <li key={step}>{step}</li>)}</ol><small>{guidance.note}</small></section>}
  </div>;
}
