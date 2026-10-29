import React from 'react';
export default function SpendingBasis({ basis, asOf, start }) {
  if (!basis) return null;
  const label = basis.method === 'HISTORY_MEAN' ? `ค่าเฉลี่ยย้อนหลัง ${basis.complete_known_days}/28 วัน` : basis.method === 'SCENARIO' ? 'ประมาณการจากสมมติฐาน' : 'ข้อมูลไม่พอสำหรับประมาณการ';
  return <div className="small-note" data-spending-method={basis.method}>
    <strong>{basis.method === 'SCENARIO' ? 'สมมติฐานรายจ่าย' : label}</strong>
    {basis.daily_non_bill_thb != null && ` · ฿${basis.daily_non_bill_thb.toLocaleString('th-TH', { maximumFractionDigits: 2 })}/วัน ไม่รวมบิล`}
    {basis.method === 'SCENARIO' && <> · กำหนดไว้สำหรับเดโม ไม่ใช่รายจ่ายที่วัดจากรายการจริง</>}
    <details><summary>ที่มาของประมาณการ</summary>{basis.method} · {label}<br/>{basis.source ? `ที่มา ${basis.source} · ${basis.source_version}` : basis.reason}
    {asOf && <> · ณ {asOf}</>}{start && <> · เริ่มสมมติรายจ่าย {start} (วันนี้รวมยอดที่บันทึกแล้ว)</>}</details>
    {basis.provenance?.source?.includes('FIXTURE') && <> · ประวัติ fixture เขียนมือเพื่อทดสอบ UI ไม่ใช่ข้อมูลผู้ใช้</>}
  </div>;
}
