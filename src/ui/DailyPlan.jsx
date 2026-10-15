import React, { useMemo, useState } from 'react';
import { ArrowRight, CalendarDays, Check, CircleAlert, Coins, Info, ShieldCheck, SlidersHorizontal, Sparkles, Target, TrendingUp, Wallet } from 'lucide-react';
import { ScenarioPicker } from './SavingsPage';
import { simulateDailyBudget, spendingOutlook } from './dailyPlanModel.mjs';

const money = (value, digits = 0) => Number(value || 0).toLocaleString('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dateLabel = (date) => date ? new Date(`${date}T12:00:00+07:00`).toLocaleDateString('th-TH', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short' }) : '—';

export function DailySummary({ horizon, forecast, openTab, expanded = false }) {
  const outlook = spendingOutlook(forecast?.timeline, horizon.payday_date);
  const difference = outlook.average === null ? 0 : Math.max(0, outlook.average - horizon.daily_safe_limit);
  const used = Math.min(100, horizon.daily_safe_limit > 0 ? horizon.spent_today / horizon.daily_safe_limit * 100 : 100);
  const reserveShort = horizon.budget_reserve_shortfall > 0;
  return <section className="daily-overview" aria-label="แผนใช้เงินวันนี้">
    <div className={`daily-hero ${reserveShort ? 'needs-attention' : ''}`}>
      <div className="daily-hero-top"><span className="daily-eyebrow"><Target size={17} /> แผนใช้เงินวันนี้ <span>· {dateLabel(horizon.as_of_date)}</span></span><span className="daily-chip">FlowSense</span></div>
      <h2>วันนี้ใช้เพิ่มได้อีก</h2>
      <div className="daily-hero-number"><span>฿</span><strong>{money(horizon.remaining_today, 2)}</strong></div>
      <p className="daily-purpose">{reserveShort ? `ควรเติมเงินสำหรับบิลและเงินสำรองอีก ฿${money(horizon.budget_reserve_shortfall, 2)}` : horizon.remaining_today <= 0 ? 'ใช้ถึงงบวันนี้แล้ว ลองปรับแผนก่อนใช้จ่ายเพิ่ม' : 'งบที่ช่วยให้มีเงินพร้อมใช้ จนถึงรอบเงินเดือน'}</p>
      <div className="daily-budget-stats"><div><span>งบวันนี้ / ต่อวัน</span><strong>฿{money(horizon.daily_safe_limit, 2)}</strong></div><div><span>ใช้ไปแล้ววันนี้</span><strong>฿{money(horizon.spent_today, 2)}</strong></div><div><span>ถึงเงินเดือนเข้า</span><strong>{horizon.days_to_payday} <small>วัน</small></strong></div></div>
      <div className="daily-progress" role="progressbar" aria-label="สัดส่วนงบวันนี้ที่ใช้ไป" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(used)}><i style={{width:`${used}%`}} /></div>
      <div className="daily-hero-bottom"><span><ShieldCheck size={16} /> คำนวณหลังเผื่อบิลและเงินสำรอง</span><button onClick={() => openTab(expanded ? 'accounts' : 'plan')}>{expanded ? 'ดูกราฟ 30 วัน' : 'ดูแผนและลองตั้งงบ'}<ArrowRight size={16} /></button></div>
    </div>
    <aside className="daily-outlook">
      <span className="daily-outlook-icon"><TrendingUp size={21} /></span><span className="daily-eyebrow">ถ้าใช้จ่ายแบบเดิม</span>
      <h3>คาดว่าจะใช้เฉลี่ย</h3><strong className="daily-outlook-number">{outlook.average === null ? '—' : `฿${money(outlook.average)}`}<small> / วัน</small></strong>
      <p>{outlook.average === null ? 'ไม่มีวันคาดการณ์ก่อนเงินเดือนรอบนี้' : `รายจ่ายประจำวัน ${outlook.days} วันข้างหน้า ก่อน ${dateLabel(horizon.payday_date)} ไม่รวมบิล`}</p>
      <div className={`daily-comparison ${difference > 0 ? 'adjust' : ''}`}>{difference > 0 ? <CircleAlert size={18} /> : <Check size={18} />}<span>{outlook.average === null ? 'ใช้งบวันนี้ประกอบการวางแผน' : difference > 0 ? <>สูงกว่างบประมาณ <b>฿{money(difference)} / วัน</b><small>ลองลดรายจ่าย แล้วดูเงินที่เหลือ</small></> : <>อยู่ในงบต่อวันที่คำนวณได้<small>ติดตามอีกครั้งเมื่อมีรายการใหม่</small></>}</span></div>
      <span className="daily-model-note">คาดการณ์จากโมเดลและข้อมูลสมมติ · ไม่ใช่ยอดรับรอง</span>
    </aside>
  </section>;
}

export default function DailyPlan({ horizon, forecast, busy, onScenario, openTab }) {
  const [amount, setAmount] = useState(String(Math.floor(horizon.daily_safe_limit)));
  const plan = useMemo(() => simulateDailyBudget(horizon, amount), [horizon, amount]);
  const outlook = spendingOutlook(forecast?.timeline, horizon.payday_date);
  const ceiling = Math.min(100000, Math.max(1000, Math.ceil(Math.max(horizon.daily_safe_limit * 2, outlook.average || 0) / 100) * 100));
  const bills = horizon.recurring_commitments.filter(row => row.amount > 0 && row.due_days < horizon.days_to_payday);
  return <div className="daily-plan-page">
    <DailySummary {...{horizon, forecast, openTab}} expanded />
    <div className="daily-plan-grid">
      <section className="surface budget-simulator"><div className="plan-section-heading"><span className="plan-icon peach"><SlidersHorizontal size={22} /></span><div><span className="section-kicker">ลองก่อนใช้จริง</span><h2>ถ้าใช้วันละเท่านี้ เงินจะพอไหม?</h2></div></div>
        <p className="plan-description">ปรับงบตั้งแต่วันนี้ถึงวันก่อนเงินเดือน แล้วดูเงินที่เหลือหลังจ่ายบิล</p>
        <label className="field-label" htmlFor="daily-budget">งบรายจ่ายประจำวัน (บาท / วัน)</label><div className="budget-input-row"><div className="amount-input"><span>฿</span><input id="daily-budget" type="number" inputMode="decimal" min="0" max="100000" step="1" value={amount} onChange={e => setAmount(e.target.value)} /></div><button className="budget-reset" onClick={() => setAmount(String(Math.floor(horizon.daily_safe_limit)))}>ใช้งบแนะนำ</button></div>
        <input className="budget-slider" type="range" aria-label="ปรับงบรายจ่ายต่อวัน" min="0" max={ceiling} step="1" value={Math.min(ceiling, Math.max(0, Number(amount) || 0))} onChange={e => setAmount(e.target.value)} />
        <div className="budget-slider-labels"><span>฿0</span><span>฿{money(ceiling)} / วัน</span></div>
        <div className="budget-presets">{[...new Set([Math.floor(horizon.daily_safe_limit), 300, 500, 1000])].map(value => <button key={value} aria-pressed={Number(amount) === value} onClick={() => setAmount(String(value))}>฿{money(value)}</button>)}</div>
        {!plan ? <p className="budget-validation" role="alert">กรอกงบระหว่าง 0–100,000 บาท</p> : <div className={`budget-result ${plan.withinReserve ? 'on-track' : 'needs-plan'}`} aria-live="polite"><div className="budget-result-title">{plan.withinReserve ? <ShieldCheck size={21} /> : <CircleAlert size={21} />}<strong>{plan.withinReserve ? 'งบนี้ยังรักษาเงินสำรองได้' : plan.minimum < 0 ? 'งบนี้อาจทำให้เงินไม่พอ' : 'งบนี้ต้องใช้เงินสำรองบางส่วน'}</strong></div><div className="budget-result-values"><div><span>คาดว่าเหลือก่อนเงินเดือน</span><strong>฿{money(plan.endBalance, 2)}</strong></div><div><span>{plan.withinReserve ? 'เงินสำรองที่คงไว้' : 'ต่ำกว่าเงินสำรองที่ตั้งไว้'}</span><strong>฿{money(plan.withinReserve ? horizon.emergency_buffer : plan.shortfall, 2)}</strong></div></div><p>{plan.withinReserve ? 'สมมติว่าใช้ตามงบนี้ทุกวัน และจ่ายบิลตามรายการที่ทราบ' : plan.billAtRisk ? 'มีบิลที่เงินอาจไม่พอ ลองลดงบหรือเตรียมเงินเพิ่ม' : 'ลองลดงบรายวัน หรือดูเงินออมที่สามารถดึงคืนได้'}</p>{!plan.withinReserve && <button className="text-link" onClick={() => openTab('savings')}>ดูทางเลือกดึงเงินออมคืน <ArrowRight size={15} /></button>}</div>}
        <p className="plan-note"><Info size={15} /> นี่คือผลจำลองตามงบที่ตั้ง ยังไม่เปลี่ยนยอดบัญชี และไม่นับเงินเดือนหรือเงินออมเป็นเงินใช้ก่อนวันเข้า</p>
      </section>
      <section className="surface budget-breakdown"><div className="plan-section-heading"><span className="plan-icon mint"><Coins size={22} /></span><div><span className="section-kicker">ที่มาของคำแนะนำ</span><h2>งบต่อวันคิดจากอะไร?</h2></div></div>
        <dl className="budget-formula"><div><dt>เงินในบัญชีตอนนี้</dt><dd>฿{money(horizon.current_balance, 2)}</dd></div><div><dt>บวกรายจ่ายที่ใช้ไปวันนี้</dt><dd>+ ฿{money(horizon.spent_today, 2)}</dd></div><div><dt>กันบิลก่อนเงินเดือน</dt><dd>− ฿{money(horizon.total_recurring_commitments, 2)}</dd></div><div><dt>กันเงินสำรอง</dt><dd>− ฿{money(horizon.emergency_buffer, 2)}</dd></div><div><dt>แบ่งใช้ตั้งแต่วันนี้ถึงก่อนเงินเดือน</dt><dd>{horizon.days_to_payday} วัน</dd></div><div className="formula-total"><dt>งบวันนี้ / ต่อวัน</dt><dd>฿{money(horizon.daily_safe_limit, 2)}</dd></div></dl>
        <p className="plan-note">ยอดบัญชีหักรายจ่ายวันนี้แล้ว จึงบวกกลับเพื่อหางบทั้งวัน จากนั้นหักยอดที่ใช้แล้วครั้งเดียวเพื่อแสดง “วันนี้ใช้เพิ่มได้อีก”</p>
        <div className="budget-bills"><h3><CalendarDays size={17} /> บิลที่เผื่อไว้ก่อนเงินเดือน</h3>{bills.length ? bills.map(row => <div key={row.name}><span>{row.name}<small>{dateLabel(row.due_date)}</small></span><strong>฿{money(row.amount)}</strong></div>) : <p>ไม่มีบิลตามข้อมูลจำลองก่อนเงินเดือนรอบนี้</p>}</div>
      </section>
    </div>
    <ScenarioPicker {...{horizon, busy, onScenario}} />
    <div className="plan-next-step"><span className="plan-icon lilac"><Wallet size={22} /></span><div><h3>รู้เงินที่ต้องใช้ แล้วค่อยวางแผนออม</h3><p>ระบบจะแนะนำออมเฉพาะส่วนที่เหลือหลังเผื่อรายจ่ายและเงินสำรอง</p></div><button className="primary-button" onClick={() => openTab('savings')}>ดูยอดที่พร้อมออม <ArrowRight size={17} /></button></div>
  </div>;
}
