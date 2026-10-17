import React, { useState } from 'react';
import { ArrowDownLeft, ArrowRight, ChevronDown, CircleAlert, RotateCcw, Sparkles, Wallet } from 'lucide-react';
import ReserveSettings from './ReserveSettings';
const money = (v, digits = 2) => Number(v || 0).toLocaleString('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function ScenarioPicker({ horizon, busy, onScenario }) {
  const scenarios = [['healthy', 'มีเงินพร้อมออม'], ['normal_dip', 'เงินลดปกติ'], ['commitment_risk', 'ภาระเสี่ยงไม่พอ']];
  const selected = scenarios.find(([id]) => horizon.scenario === id)?.[1] || 'ค่าตั้งต้นของบัญชี';
  return <details className="surface scenario-lab"><summary><span>เปลี่ยนสถานการณ์ทดลอง<small>กำลังใช้: {selected}</small></span><ChevronDown size={18} /></summary><div className="scenario-content"><p>เปรียบเทียบผลเมื่อยอดเงินเปลี่ยน ทุกสถานการณ์ใช้วันที่ปัจจุบันตามเวลาไทย</p><div className="scenario-pills">{scenarios.map(([id, label]) => <button key={id} aria-pressed={horizon.scenario === id} disabled={busy} onClick={() => onScenario(id)}>{label}</button>)}</div></div></details>;
}

export default function SavingsPage({ profile, horizon, busy, sweepAmount, setSweepAmount, doSweep, doRecommendedSweep, doWithdraw, doReset, onSavingsToggle, onScenario, openTab, onReservePreview, onReserveSave }) {
  const [withdrawAmount, setWithdrawAmount] = useState('200');
  const [withdrawAll, setWithdrawAll] = useState(false);
  const enabled = profile.savings_enabled;
  const estimate = horizon.savings_estimate;
  const max = estimate.max_sweep_amount;
  const canSave = enabled && max > 0 && !busy;
  const withdrawal = withdrawAll ? profile.vault_balance : Number(withdrawAmount);
  const validMoney = (v) => Number.isFinite(v) && v > 0 && Math.abs(v * 100 - Math.round(v * 100)) < 1e-7;
  const validSave = validMoney(Number(sweepAmount)) && Number(sweepAmount) <= max;
  const validWithdrawal = validMoney(withdrawal) && withdrawal <= profile.vault_balance;
  return <div className="savings-page">
    <div className="savings-budget-link"><Wallet size={23} /><div><strong>วันนี้ใช้เพิ่มได้อีก ฿{money(horizon.remaining_today)}</strong><p>ตรวจงบใช้จ่ายก่อนตัดสินใจออม</p></div><button onClick={() => openTab('plan')}>ดูแผนใช้เงิน <ArrowRight size={16} /></button></div>
    <p className="savings-purpose">เงินตึงให้เก็บไว้ใช้ก่อน · การแยกออมช่วยจัดเงินเป็นส่วน ไม่ได้เพิ่มยอดเงินรวม หากต้องใช้ คุณถอนกลับเข้าบัญชีหลักได้</p>
    <ScenarioPicker horizon={horizon} busy={busy} onScenario={onScenario} />
    <div className="feature-layout">
      <section className="surface feature-primary">
        <div className="section-kicker">การออมเงิน · FlowSense</div>
        <div className="feature-header"><div><h2>ออมเมื่อพร้อม ถอนเมื่อจำเป็น</h2><p>กันค่าใช้ชีวิต บิล และเงินสำรองก่อน คุณเลือกเองว่าจะออมเท่าไร</p></div><span className="feature-illustration"><Wallet size={38} /></span></div>
        <div className="account-pair"><div><span>บัญชีหลัก</span><strong>฿{money(profile.main_balance)}</strong></div><div className="pair-arrow"><ArrowRight size={19} /></div><div><span>บัญชีเงินออม</span><strong>฿{money(profile.vault_balance)}</strong></div></div>
        <div className="savings-consent"><div className="auto-setting"><div><strong>เปิดการแยกเงินออม</strong><small>{enabled ? 'เปิดใช้งานแล้ว · ออมเมื่อคุณกดยืนยัน' : 'ยังไม่เปิดใช้งาน · คุณเลือกเปิดได้เอง'}</small></div><button className="saving-switch" role="switch" aria-label="เปิดการแยกเงินออม" aria-checked={enabled} disabled={busy} onClick={() => onSavingsToggle(!enabled)}><i /></button></div><p>เปิดแล้วไม่มีการย้ายเงินอัตโนมัติ ปิดได้ทุกเมื่อ และยังถอนเงินออมที่มีอยู่ได้</p></div>
        <div className="auto-save-recommendation"><span className="auto-save-icon"><Sparkles size={18} /></span><div><span>คำแนะนำสำหรับครั้งนี้</span><strong>฿{money(horizon.recommended_sweep_amount)}</strong><small>ออมได้สูงสุดครั้งละ ฿{money(max)} · ไม่เกิน 500 บาท</small></div><button disabled={!canSave || horizon.recommended_sweep_amount <= 0} onClick={doRecommendedSweep}>ออมตามคำแนะนำ <ArrowRight size={14} /></button></div>
        {max <= 0 && <div className="reserve-note"><CircleAlert size={18} /><span>พักการออมไว้ก่อน เงินที่มีต้องกันไว้สำหรับค่าใช้ชีวิต บิล และเงินสำรอง</span></div>}
        <details className="savings-calculation"><summary>ออมได้เท่าไร คิดจากอะไร? <ChevronDown size={17} /></summary><p>ประมาณค่าใช้ชีวิตถึงเงินเดือนรอบถัดไปอีก {estimate.days_to_payday} วัน จากค่าที่สูงกว่าระหว่างค่าเฉลี่ยต่อวันกับยอดที่ใช้วันนี้ และกันบิลประจำตามโปรไฟล์ครบหนึ่งรอบ</p><dl>
          <div><dt>ยอดบัญชีหลัก</dt><dd>฿{money(profile.main_balance)}</dd></div>
          <div><dt>หัก ค่าใช้ชีวิตประมาณการ</dt><dd>− ฿{money(estimate.projected_living_cost)}</dd></div>
          <div><dt>หัก บิลประจำ</dt><dd>− ฿{money(estimate.fixed_commitments)}</dd></div>
          <div><dt>หัก เงินสำรอง</dt><dd>− ฿{money(estimate.emergency_buffer)}</dd></div>
          {estimate.forecast_reserve_adjustment > 0 && <div><dt>กันเพิ่มตามจุดต่ำของกราฟ</dt><dd>− ฿{money(estimate.forecast_reserve_adjustment)}</dd></div>}
          <div className="calculation-total"><dt>ส่วนที่เหลือพร้อมออม</dt><dd>฿{money(estimate.safe_to_save)}</dd></div>
        </dl><p>ยอดพร้อมออมต่ำสุดคือ 0 บาท ตรวจใหม่ทุกครั้งก่อนออม และจำกัดไม่เกิน 500 บาทต่อครั้ง ข้อมูลและยอดทั้งหมดเป็นการจำลอง</p></details>
        <form onSubmit={(e) => { e.preventDefault(); if (canSave && validSave) doSweep(); }}>
          <label className="field-label" htmlFor="sweep-amount">เลือกจำนวนเงินออมเอง</label><div className="amount-input"><span>฿</span><input id="sweep-amount" aria-describedby="savings-limit" inputMode="decimal" type="number" required min="0.01" max={max || 500} step="0.01" disabled={busy || !enabled || max <= 0} value={sweepAmount} onChange={(e) => setSweepAmount(e.target.value)} /><span>THB</span></div>
          <div className="amount-presets">{[100, 200, 500].map((v) => <button type="button" disabled={!canSave || v > max} key={v} className={Number(sweepAmount) === v ? 'selected' : ''} onClick={() => setSweepAmount(String(v))}>฿{money(v, 0)}</button>)}</div>
          <p id="savings-limit" className="small-note">{!enabled ? 'เปิดการแยกเงินออมด้านบนก่อนเริ่มออม' : max > 0 ? `ระบุได้ 0.01–${money(max)} บาท` : 'ยังไม่มีส่วนที่พร้อมออมในขณะนี้'}</p>
          <button className="primary-button" disabled={!canSave || !validSave}><ArrowDownLeft size={18} /> แยกเงินเข้าบัญชีออม</button>
        </form>
      </section>
      <aside className="feature-aside">
        <section className="surface aside-card recall-card"><span className="icon-box mint"><ArrowDownLeft size={22} /></span><h3>ถอนเงินออม</h3><p>เลือกถอนบางส่วนหรือทั้งหมดเข้าบัญชีหลักได้ แม้ปิดการแยกเงินออมอยู่</p><div className="withdrawal-balance"><span>ยอดที่ถอนได้</span><strong>฿{money(profile.vault_balance)}</strong></div>
          <form onSubmit={(e) => { e.preventDefault(); if (!busy && validWithdrawal) doWithdraw(withdrawal); }}>
            <label className="field-label" htmlFor="withdraw-amount">จำนวนเงินที่ต้องการถอน</label><div className="amount-input"><span>฿</span><input id="withdraw-amount" inputMode="decimal" type="number" required min="0.01" max={profile.vault_balance} step="0.01" disabled={busy || withdrawAll || profile.vault_balance <= 0} value={withdrawAll ? profile.vault_balance : withdrawAmount} onChange={(e) => setWithdrawAmount(e.target.value)} /></div>
            <label className="withdraw-all"><input type="checkbox" checked={withdrawAll} disabled={busy || profile.vault_balance <= 0} onChange={(e) => setWithdrawAll(e.target.checked)} /> ถอนทั้งหมด</label>
            {!withdrawAll && withdrawAmount !== '' && !validWithdrawal && <p className="withdrawal-hint">ระบุจำนวนมากกว่า 0 ไม่เกินยอดที่ถอนได้ และไม่เกินทศนิยม 2 ตำแหน่ง</p>}
            <button className="primary-button" disabled={busy || !validWithdrawal}>ถอนเงินออมเข้าบัญชีหลัก <ArrowRight size={16} /></button>
          </form><p className="small-note">เป็นการย้ายยอดจำลองระหว่างบัญชีของคุณ ไม่มีการโอนเงินจริงหรือคำนวณดอกเบี้ย</p>
        </section>
        <ReserveSettings {...{horizon, busy, onReservePreview, onReserveSave}}/>
        <button className="reset-button" disabled={busy} onClick={doReset}><RotateCcw size={15} /> กลับข้อมูลเริ่มต้น</button>
      </aside>
    </div>
  </div>;
}
