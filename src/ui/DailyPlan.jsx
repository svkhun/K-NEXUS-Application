import React, { useMemo, useState } from 'react';
import { ArrowRight, CalendarDays, ChevronDown, CircleAlert, Info, ShieldCheck, Target, TrendingUp } from 'lucide-react';
import { ScenarioPicker } from './SavingsPage';
import { simulateDailyBudget, spendingOutlook } from './dailyPlanModel.mjs';

const money = (value, digits = 0) => Number(value || 0).toLocaleString('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dateLabel = (date) => date ? new Date(`${date}T12:00:00+07:00`).toLocaleDateString('th-TH', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short' }) : '—';

// Home answers today's question. The plan page is a separate editing workspace.
export function DailySummary({ horizon, openTab }) {
  const reserveShort = horizon.budget_reserve_shortfall > 0;
  const used = Math.min(100, horizon.daily_safe_limit > 0 ? horizon.spent_today / horizon.daily_safe_limit * 100 : 100);
  return <section className={`today-budget ${reserveShort ? 'needs-attention' : ''}`} aria-label="งบใช้จ่ายวันนี้">
    <div className="today-budget-heading"><span><Target size={18} /> งบใช้จ่ายวันนี้</span><time dateTime={horizon.as_of_date}>{dateLabel(horizon.as_of_date)}</time></div>
    <div className="today-budget-amount"><div><h2>วันนี้ใช้เพิ่มได้อีก</h2><strong>฿{money(horizon.remaining_today, 2)}</strong></div><button className="round-link" onClick={() => openTab('plan')} aria-label="ไปตั้งงบรายวัน"><ArrowRight size={21} /></button></div>
    <div className="today-budget-stats"><span>ใช้แล้ว <b>฿{money(horizon.spent_today, 2)}</b></span><span>จากงบ <b>฿{money(horizon.daily_safe_limit, 2)}</b></span></div>
    <div className="daily-progress" role="progressbar" aria-label="สัดส่วนงบวันนี้ที่ใช้ไป" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(used)}><i style={{ width: `${used}%` }} /></div>
    <div className="today-budget-footer"><p>{reserveShort ? `บิลและเงินสำรองยังขาด ฿${money(horizon.budget_reserve_shortfall, 2)}` : horizon.remaining_today <= 0 ? 'ใช้ถึงงบวันนี้แล้ว ลองปรับแผนก่อนใช้เพิ่ม' : `เผื่อบิลและเงินสำรองแล้ว · อีก ${horizon.days_to_payday} วันถึงเงินเดือน`}</p><button className="text-link" onClick={() => openTab('plan')}>ลองตั้งงบ <ArrowRight size={15} /></button></div>
  </section>;
}

function SpendingOutlook({ horizon, forecast }) {
  const outlook = spendingOutlook(forecast?.timeline, horizon.payday_date);
  const difference = outlook.average === null ? 0 : Math.max(0, outlook.average - horizon.daily_safe_limit);
  return <section className="surface spending-outlook">
    <div className="section-heading"><span className="section-icon lilac"><TrendingUp size={19} /></span><h2>ถ้าใช้จ่ายแบบเดิม</h2></div>
    <div className="outlook-value"><span>รายจ่ายคาดการณ์เฉลี่ย</span><strong>{outlook.average === null ? '—' : `฿${money(outlook.average)}`}<small> / วัน</small></strong></div>
    <p>{outlook.average === null ? 'ไม่มีวันคาดการณ์ก่อนเงินเดือนรอบนี้' : `${outlook.days} วันข้างหน้า ก่อน ${dateLabel(horizon.payday_date)} · ไม่รวมบิล`}</p>
    {outlook.average !== null && <div className={`outlook-comparison ${difference > 0 ? 'adjust' : ''}`}>{difference > 0 ? <CircleAlert size={17} /> : <ShieldCheck size={17} />}<span>{difference > 0 ? `สูงกว่างบแนะนำ ฿${money(difference)} / วัน` : 'อยู่ในงบต่อวันที่คำนวณได้'}</span></div>}
    <p className="small-note">โมเดลคาดการณ์จากข้อมูลสมมติ ส่วนงบแนะนำคำนวณจากเงินที่มี บิล และเงินสำรอง</p>
  </section>;
}

export default function DailyPlan({ horizon, forecast, busy, onScenario, openTab }) {
  const recommended = Math.floor(horizon.daily_safe_limit);
  const [amount, setAmount] = useState(String(recommended));
  const plan = useMemo(() => simulateDailyBudget(horizon, amount), [horizon, amount]);
  const outlook = spendingOutlook(forecast?.timeline, horizon.payday_date);
  const ceiling = Math.min(100000, Math.max(1000, Math.ceil(Math.max(horizon.daily_safe_limit * 2, outlook.average || 0) / 100) * 100));
  const bills = horizon.recurring_commitments.filter(row => row.amount > 0 && row.due_days < horizon.days_to_payday);

  return <div className="daily-plan-page">
    <div className="plan-period"><CalendarDays size={17} /><span>วางแผนถึง {dateLabel(horizon.payday_date)} <b>· {horizon.days_to_payday} วัน</b></span><button className="text-link" onClick={() => openTab('accounts')}>ดูแนวโน้ม <ArrowRight size={15} /></button></div>
    <div className="daily-plan-grid">
      <section className="surface budget-simulator" aria-label="ทดลองตั้งงบรายวัน">
        <div className="simulator-heading"><span className="section-kicker">ลองปรับแผนของคุณ</span><h2>อยากใช้วันละเท่าไร?</h2><p>ลองเปลี่ยนจำนวนเงิน แล้วดูว่าจะพอถึงเงินเดือนหรือไม่</p></div>
        <label className="field-label" htmlFor="daily-budget">งบรายจ่ายประจำวัน</label>
        <div className="budget-input-row"><div className="amount-input"><span>฿</span><input id="daily-budget" type="number" inputMode="decimal" min="0" max="100000" step="1" value={amount} onChange={e => setAmount(e.target.value)} aria-describedby="budget-advice" /><span>/ วัน</span></div></div>
        <div className="budget-advice" id="budget-advice"><span>แนะนำไม่เกิน <b>฿{money(horizon.daily_safe_limit, 2)} / วัน</b></span><button className="text-link" onClick={() => setAmount(String(recommended))}>ใช้งบแนะนำ</button></div>
        <input className="budget-slider" type="range" aria-label="ปรับงบรายจ่ายต่อวัน" min="0" max={ceiling} step="1" value={Math.min(ceiling, Math.max(0, Number(amount) || 0))} onChange={e => setAmount(e.target.value)} />
        <div className="budget-slider-labels"><span>฿0</span><span>฿{money(ceiling)}</span></div>
        <div className="budget-presets">{[300, 500, 1000].map(value => <button key={value} aria-pressed={Number(amount) === value} onClick={() => setAmount(String(value))}>฿{money(value)}</button>)}</div>
        {!plan ? <p className="budget-validation" role="alert">กรอกงบระหว่าง 0–100,000 บาท</p> : <div className={`budget-result ${plan.withinReserve ? 'on-track' : 'needs-plan'}`} aria-live="polite">
          <div className="budget-result-title">{plan.withinReserve ? <ShieldCheck size={19} /> : <CircleAlert size={19} />}<strong>{plan.withinReserve ? 'งบนี้ยังรักษาเงินสำรองได้' : plan.minimum < 0 ? 'งบนี้อาจทำให้เงินไม่พอ' : 'งบนี้ต้องใช้เงินสำรองบางส่วน'}</strong></div>
          <div className="budget-result-main"><span>เงินเหลือก่อนเงินเดือน</span><strong>฿{money(plan.endBalance, 2)}</strong></div>
          <div className="budget-result-reserve"><span>{plan.withinReserve ? 'เงินสำรองที่คงไว้' : 'ต่ำกว่าเงินสำรองที่ตั้งไว้'}</span><b>฿{money(plan.withinReserve ? horizon.emergency_buffer : plan.shortfall, 2)}</b></div>
          {!plan.withinReserve && <><p>{plan.billAtRisk ? 'มีบิลที่เงินอาจไม่พอ ลองลดงบหรือเตรียมเงินเพิ่ม' : 'ลองลดงบรายวัน หรือดูเงินออมที่สามารถดึงคืนได้'}</p><button className="text-link" onClick={() => openTab('savings')}>ดูทางเลือกดึงเงินออมคืน <ArrowRight size={15} /></button></>}
        </div>}
        <p className="plan-note"><Info size={15} /><span>ผลจำลองตามงบที่ตั้ง ยังไม่เปลี่ยนยอดบัญชี โดยคิดรายจ่ายวันนี้ที่ใช้ไปแล้ว ฿{money(horizon.spent_today, 2)} รวมอยู่ด้วย</span></p>
      </section>

      <aside className="planning-evidence">
        <SpendingOutlook {...{ horizon, forecast }} />
        <details className="surface budget-breakdown">
          <summary><span>งบแนะนำคิดอย่างไร?<small>ดูบิลและเงินสำรองที่เผื่อไว้</small></span><ChevronDown size={18} /></summary>
          <div className="budget-breakdown-body">
            <dl className="budget-formula">
              <div><dt>เงินในบัญชีตอนนี้</dt><dd>฿{money(horizon.current_balance, 2)}</dd></div>
              <div><dt>บวกรายจ่ายที่ใช้ไปวันนี้</dt><dd>+ ฿{money(horizon.spent_today, 2)}</dd></div>
              <div><dt>กันบิลก่อนเงินเดือน</dt><dd>− ฿{money(horizon.total_recurring_commitments, 2)}</dd></div>
              <div><dt>กันเงินสำรอง</dt><dd>− ฿{money(horizon.emergency_buffer, 2)}</dd></div>
              <div><dt>จำนวนวันที่แบ่งใช้</dt><dd>{horizon.days_to_payday} วัน</dd></div>
              <div className="formula-total"><dt>งบต่อวัน</dt><dd>฿{money(horizon.daily_safe_limit, 2)}</dd></div>
            </dl>
            <p className="small-note">บวกรายจ่ายวันนี้กลับเพื่อหางบทั้งวัน แล้วหักยอดใช้แล้วครั้งเดียวเพื่อหายอดที่ยังใช้เพิ่มได้</p>
            <div className="budget-bills"><h3>บิลก่อนเงินเดือน</h3>{bills.length ? bills.map(row => <div key={row.name}><span>{row.name}<small>{dateLabel(row.due_date)}</small></span><strong>฿{money(row.amount)}</strong></div>) : <p>ไม่มีบิลตามข้อมูลจำลองในช่วงนี้</p>}</div>
          </div>
        </details>
        <p className="small-note plan-assumptions">สมมติว่าใช้งบเดียวกันทุกวันและจ่ายบิลตามกำหนด ไม่นับเงินเดือนหรือดึงเงินออมก่อนวันเงินเข้า</p>
      </aside>
    </div>
    <ScenarioPicker {...{ horizon, busy, onScenario }} />
  </div>;
}
