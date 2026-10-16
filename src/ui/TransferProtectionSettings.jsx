import React, { useState } from 'react';
import { ChevronDown, ShieldCheck } from 'lucide-react';

export default function TransferProtectionSettings({ profile, busy, onChange }) {
  const [confirmOff, setConfirmOff] = useState(false);
  const enabled = profile.transfer_cooldown_enabled;
  return <details className="transfer-protection-settings">
    <summary><ShieldCheck size={18} /><span>ตั้งค่าพักก่อนโอนรายการเสี่ยง<small>{enabled ? 'เปิด · 15 นาที' : 'ปิดเวลาพักเสริม'}</small></span><ChevronDown size={17} /></summary>
    <div className="protection-settings-body">
      <div className="auto-setting"><div><strong>พักก่อนโอนรายการเสี่ยง 15 นาที</strong><small>รายการปกติไม่ต้องรอ</small></div><button className="saving-switch" role="switch" aria-label="พักก่อนโอนรายการเสี่ยง 15 นาที" aria-checked={enabled} disabled={busy} onClick={() => enabled ? setConfirmOff(true) : onChange(true)}><i /></button></div>
      <p>ให้เวลาหยุดคิดและตรวจผู้รับผ่านช่องทางที่คุณเชื่อถือ ครบเวลาแล้วต้องยืนยันเอง เงินจะไม่โอนอัตโนมัติ</p>
      <p>การตั้งค่านี้ใช้กับรายการเสี่ยงใหม่ เวลาพักที่เริ่มแล้วจะยังคงเดิม การตรวจความเสี่ยง การยืนยันจำลอง และการระงับบัญชีต้องห้ามยังทำงานเมื่อปิดเวลาพัก</p>
      {confirmOff && enabled && <div className="disable-cooldown-confirm" role="group" aria-label="ยืนยันปิดเวลาพักเสริม"><strong>ปิดเวลาพักสำหรับรายการใหม่?</strong><p>คุณจะไม่มีช่วงพัก 15 นาทีเพื่อทบทวนรายการเสี่ยงใหม่</p><button className="secondary-button" disabled={busy} onClick={() => { setConfirmOff(false); onChange(false); }}>ยืนยันปิดเวลาพักเสริม</button><button className="text-link" disabled={busy} onClick={() => setConfirmOff(false)}>เปิดไว้เหมือนเดิม</button></div>}
    </div>
  </details>;
}
