import React, { useState } from 'react';
import { Clock3 } from 'lucide-react';
import { ProtectionIcon } from './NexusIcons';

export default function TransferProtectionSettings({ profile, busy, onChange, hasPending = false }) {
  const [confirmOff, setConfirmOff] = useState(false);
  const enabled = profile.transfer_cooldown_enabled;
  return <section className={`transfer-protection-settings ${enabled ? 'is-enabled' : 'is-disabled'}`} aria-labelledby="cooldown-settings-title">
    <div className="protection-settings-main"><span className="protection-settings-icon"><Clock3 size={23} /></span><div className="protection-settings-copy"><span className="section-kicker">ตั้งค่าการโอนเงิน</span><h2 id="cooldown-settings-title">พักก่อนโอนรายการเสี่ยง</h2><p>{enabled ? 'เปิดอยู่ · ให้เวลาตรวจสอบผู้รับ 15 นาที' : 'ปิดอยู่ · รายการเสี่ยงใหม่ไม่ต้องพัก 15 นาที'}</p></div><div className="protection-setting-toggle"><span>{enabled ? 'เปิด · 15 นาที' : 'ปิดเวลาพัก'}</span><button id="transfer-cooldown-toggle" className="saving-switch" role="switch" aria-label="พักก่อนโอนรายการเสี่ยง 15 นาที" aria-checked={enabled} disabled={busy} onClick={() => enabled ? setConfirmOff(true) : onChange(true)}><i /></button></div></div>
    <div className="protection-settings-caption"><ProtectionIcon size={16} /><span>รายการปกติไม่ต้องรอ · ยังตรวจความเสี่ยงและป้องกันโอนไปบัญชีที่ถูกระงับ</span></div>
    {hasPending && <p className="pending-policy-note">มีรายการเดิมที่กำลังตรวจสอบอยู่ หากต้องการใช้ค่าใหม่ ให้ยกเลิกรายการเดิมแล้วเริ่มใหม่</p>}
    {confirmOff && enabled && <div className="disable-cooldown-confirm" role="group" aria-label="ยืนยันปิดเวลาพักเสริม"><strong>ปิดเวลาพักสำหรับรายการใหม่?</strong><p>รายการใหม่จะไม่มีช่วงพัก 15 นาที แต่ยังต้องตรวจความเสี่ยงและยืนยันจำลอง รายการที่เปิดอยู่ยังใช้ค่าเดิมจนกว่าจะยกเลิก</p><div><button className="secondary-button" disabled={busy} onClick={() => { setConfirmOff(false); onChange(false); }}>ยืนยันปิดเวลาพักเสริม</button><button className="text-link" disabled={busy} onClick={() => setConfirmOff(false)}>เปิดไว้เหมือนเดิม</button></div></div>}
  </section>;
}
