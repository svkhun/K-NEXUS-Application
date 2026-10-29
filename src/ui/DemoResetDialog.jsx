import React, { useEffect, useRef } from 'react';
import { scenarioLabel } from './ScenarioPicker';
export default function DemoResetDialog({ intent, persona, busy, blocked, error, onCancel, onConfirm }) {
  const ref = useRef(null);
  useEffect(() => {
    const previous = document.activeElement;
    ref.current.showModal();
    return () => { ref.current?.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog ref={ref} className="demo-reset-dialog" aria-labelledby="demo-reset-title" onCancel={event => { event.preventDefault(); if (!busy) onCancel(); }}>
    <h2 id="demo-reset-title">{intent === 'default' ? 'กลับค่าเริ่มต้น' : `เลือกสถานการณ์: ${scenarioLabel(intent)}`} · {persona}</h2>
    <p>เริ่มยอดบัญชีหลัก เงินออม บิล และประวัติทดลองของ {persona} ใหม่ ปิดการแยกเงินออมและคืนค่าป้องกันการโอน รายการตรวจสอบและสิทธิ์ยืนยันเดิมจะใช้ไม่ได้</p>
    <p>{intent === 'default' ? 'คืนเงินสำรองตามค่าเริ่มต้นของโปรไฟล์ ซึ่งเตรียมเงินจำลองไว้ให้ลองออมและโอนจำนวนเล็กน้อย' : 'คงเงินสำรองที่คุณตั้งไว้ แล้วคำนวณแผนใหม่ตามสถานการณ์ที่เลือก'} · ไม่เปลี่ยนบัญชีอื่น</p>
    {blocked && <p role="alert">จัดการรายการที่รอหรือรับผลคำสั่งเดิมก่อนเริ่มใหม่</p>}
    {error && <p role="alert">{error}</p>}
    <div className="demo-actions"><button autoFocus className="secondary-button" disabled={busy} onClick={onCancel}>ทดลองต่อโดยไม่เปลี่ยนข้อมูล</button><button className="primary-button" disabled={busy || blocked} onClick={onConfirm}>ยืนยันเริ่มข้อมูลใหม่</button></div>
  </dialog>;
}
