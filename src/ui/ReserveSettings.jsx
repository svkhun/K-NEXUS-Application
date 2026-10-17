import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, ShieldCheck, SlidersHorizontal } from 'lucide-react';

const money = (value) => Number(value || 0).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ReserveSettings({ horizon, busy, onReservePreview, onReserveSave }) {
  const settings = horizon.reserve_settings;
  const [amount, setAmount] = useState(String(settings.amount));
  const [preview, setPreview] = useState(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);
  useEffect(() => { setAmount(String(settings.amount)); }, [settings.amount, settings.confirmed]);
  useEffect(() => { request.current += 1; setPreview(null); setChecking(false); }, [horizon]);
  useEffect(() => () => { request.current += 1; }, []);
  const changeAmount = (value) => { request.current += 1; setAmount(value); setPreview(null); setChecking(false); setError(''); };
  const valid = amount.trim() !== '' && Number.isFinite(Number(amount)) && Number(amount) >= settings.minimum && Number(amount) <= settings.maximum && Math.abs(Number(amount) * 100 - Math.round(Number(amount) * 100)) < 1e-7;
  const check = async (event) => {
    event.preventDefault();
    if (!valid || busy || checking) return;
    const id = ++request.current;
    setChecking(true); setError(''); setPreview(null);
    try { const result = await onReservePreview(Number(amount)); if (id === request.current) setPreview(result); }
    catch (err) { if (id === request.current) setError(err.message); }
    finally { if (id === request.current) setChecking(false); }
  };
  return <section className="surface reserve-settings" aria-labelledby="reserve-settings-title">
    <div className="reserve-settings-heading"><span className="reserve-symbol"><ShieldCheck size={25}/></span><div><span className="section-kicker">คุณเลือกเงินเผื่อฉุกเฉินได้</span><h2 id="reserve-settings-title">อยากเหลือเงินสำรองไว้เท่าไร?</h2></div></div>
    <p>เผื่อไว้สำหรับเรื่องไม่คาดคิด เงินยังอยู่ในบัญชีหลักและใช้ได้ตามปกติ ระบบเพียงเว้นยอดนี้ออกจากงบใช้จ่ายและคำแนะนำออม</p>
    <div className={`reserve-status ${settings.confirmed ? 'confirmed' : ''}`}><strong>{settings.confirmed ? 'คุณยืนยันยอดในแผนแล้ว' : 'ยังไม่ได้ตั้งเอง · ใช้ยอดเริ่มต้นชั่วคราว'}</strong><span>฿{money(settings.amount)}</span></div>
    <details className="reserve-source"><summary>ยอดเริ่มต้นมาจากไหน?</summary><p>฿{money(settings.suggested_amount)} เป็นค่าจากโปรไฟล์สมมติของบัญชีทดลอง ไม่ได้คำนวณจากสถานการณ์จริงของคุณหรือทำนายโดย AI คุณยืนยันยอดนี้หรือปรับให้เหมาะกับตัวเองได้ ต้นแบบกำหนดขั้นต่ำ ฿500 เป็นกติกาทดลอง ไม่ใช่เกณฑ์เงินฉุกเฉินที่เหมาะกับทุกคน</p></details>
    <form onSubmit={check}>
      <label className="field-label" htmlFor="reserve-amount">เงินสำรองที่ต้องการคงไว้ในแผน</label>
      <div className="reserve-edit-row"><div className="amount-input"><span>฿</span><input id="reserve-amount" type="number" inputMode="decimal" min={settings.minimum} max={settings.maximum} step="0.01" required value={amount} disabled={busy} onChange={(event) => changeAmount(event.target.value)} aria-describedby="reserve-help"/></div><button className="secondary-button" type="submit" disabled={busy || checking || !valid}><SlidersHorizontal size={16}/>{checking ? 'กำลังคำนวณ…' : 'ดูผลก่อนใช้ยอดนี้'}</button></div>
      <p id="reserve-help" className="small-note">ตั้งได้ ฿500–10,000,000 · ทศนิยมไม่เกิน 2 ตำแหน่ง</p>
      {Number(amount) !== settings.suggested_amount && <button className="text-link" type="button" disabled={busy} onClick={() => changeAmount(String(settings.suggested_amount))}>ใช้ยอดเริ่มต้น ฿{money(settings.suggested_amount)}</button>}
    </form>
    {error && <p role="alert" className="reserve-error">{error}</p>}
    {preview && <div className="reserve-preview" aria-live="polite"><h3>ถ้าใช้เงินสำรอง ฿{money(preview.amount)}</h3><div className="reserve-preview-labels"><span>ผลต่อแผนเงิน</span><span>ตอนนี้</span><span>หลังปรับ</span></div>{[['remaining_today', 'วันนี้ใช้เพิ่มได้อีก'], ['savings_capacity', 'เงินส่วนที่พร้อมออม']].map(([key, label]) => <div className="reserve-preview-row" key={key}><span>{label}</span><b>฿{money(preview.before[key])}</b><strong>฿{money(preview.after[key])}</strong></div>)}
      <p>{preview.amount < preview.before.emergency_buffer ? 'งบใช้จ่ายอาจเพิ่มขึ้น เพราะคุณเลือกเหลือเงินเผื่อฉุกเฉินน้อยลง ไม่ใช่มีเงินเพิ่มในบัญชี' : preview.amount === preview.before.emergency_buffer ? 'ใช้ยอดเดิมในแผน กดยืนยันเพื่อระบุว่านี่เป็นยอดที่คุณเลือกเอง โดยยอดบัญชีไม่เปลี่ยน' : 'กันสำรองมากขึ้นอาจทำให้งบใช้จ่ายและส่วนที่พร้อมออมลดลง ยอดบัญชียังเท่าเดิม'}</p>
      {preview.after.budget_reserve_shortfall > 0 && <p className="reserve-error">เงินในบัญชีต่ำกว่าบิลและเงินสำรองรวม ฿{money(preview.after.budget_reserve_shortfall)} งบใช้เพิ่มจะแสดงเป็น 0</p>}
      <button className="primary-button" disabled={busy || checking} onClick={() => onReserveSave(preview.amount)}>ยืนยันใช้เงินสำรอง ฿{money(preview.amount)} <ArrowRight size={16}/></button><small>เปลี่ยนแผนเท่านั้น ไม่มีการย้ายหรือล็อกเงิน · จำไว้เฉพาะบัญชีใน session ทดลองนี้</small>
    </div>}
  </section>;
}
