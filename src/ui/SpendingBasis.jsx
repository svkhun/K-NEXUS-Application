import React from 'react';
export default function SpendingBasis({ basis, asOf, start }) {
  if (!basis) return null;
  const label = basis.method === 'HISTORY_MEAN' ? `ค่าเฉลี่ยย้อนหลัง ${basis.complete_known_days}/28 วัน` : basis.method === 'SCENARIO' ? 'ประมาณการจากสมมติฐาน' : 'ข้อมูลไม่พอสำหรับประมาณการ';
  return <p className="small-note" data-spending-method={basis.method}>
    <strong>{basis.method} · {label}</strong>
    {basis.daily_non_bill_thb != null && ` · ฿${basis.daily_non_bill_thb.toLocaleString('th-TH', { maximumFractionDigits: 2 })}/วัน ไม่รวมบิล`}
    <br/>{basis.source ? `ที่มา ${basis.source} · ${basis.source_version}` : basis.reason}
    {asOf && <> · ณ {asOf}</>}{start && <> · เริ่มสมมติรายจ่าย {start} (วันนี้รวมยอดที่บันทึกแล้ว)</>}
    {basis.method === 'SCENARIO' && <> · กำหนดไว้สำหรับเดโม ไม่ใช่ค่าเฉลี่ยที่วัดจากรายการจริง</>}
    {basis.provenance?.source?.includes('FIXTURE') && <> · ประวัติ fixture เขียนมือเพื่อทดสอบ UI ไม่ใช่ข้อมูลผู้ใช้</>}
  </p>;
}
