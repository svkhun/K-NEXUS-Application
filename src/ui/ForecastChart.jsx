import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { ArrowDownRight, CalendarClock, CalendarDays, ChevronLeft, ChevronRight, Clock3, Coins, Info, RefreshCw, ShieldCheck } from 'lucide-react';
import { buildForecastView, buildMoneyScale, cashOut, paydayCountdown } from './forecastModel.mjs';

const money = (value, digits = 0) => Number(value || 0).toLocaleString('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dateLabel = (date, options = {}) => date ? new Date(`${date}T12:00:00+07:00`).toLocaleDateString('th-TH', { timeZone: 'Asia/Bangkok', day: 'numeric', month: 'short', ...options }) : '—';
const axisLabel = (value) => `${value < 0 ? '−' : ''}฿${money(Math.abs(value))}`;
const pad = (value) => String(value).padStart(2, '0');

export default function ForecastChart({ timeline = [], horizon, onRefresh, busy = false }) {
  const id = useId().replace(/:/g, '');
  const [range, setRange] = useState(30);
  const [selectedDate, setSelectedDate] = useState(null);
  const [showHistory, setShowHistory] = useState(true);
  const [showExpenses, setShowExpenses] = useState(true);
  const [now, setNow] = useState(() => new Date());
  const scrollRef = useRef(null);
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer); }, []);
  const view = useMemo(() => buildForecastView(timeline, range, showHistory), [timeline, range, showHistory]);
  const { points, today, payday, minimum, todayIndex } = view;
  useEffect(() => {
    const revealSelectedDay = () => {
      const element = scrollRef.current;
      if (!element || points.length < 2) return;
      const found = points.findIndex((point) => point.date === selectedDate);
      const index = found < 0 ? todayIndex : found;
      const position = (66 + index * 824 / (points.length-1)) / 960 * element.firstElementChild.clientWidth;
      if (position < element.scrollLeft+30 || position > element.scrollLeft+element.clientWidth-30) {
        element.scrollTo({ left: Math.max(0, position-element.clientWidth/2), behavior: 'auto' });
      }
    };
    revealSelectedDay();
    window.addEventListener('resize', revealSelectedDay);
    return () => window.removeEventListener('resize', revealSelectedDay);
  }, [points, selectedDate, todayIndex]);
  if (!today || points.length < 2) return <div className="chart-loading">กำลังเตรียมเส้นทางการเงิน…</div>;
  const foundIndex = points.findIndex((point) => point.date === selectedDate);
  const selectedIndex = foundIndex < 0 ? todayIndex : foundIndex;
  const selected = points[selectedIndex];
  const plot = { left: 66, right: 890, top: 39, bottom: 262 };
  const { axis: balanceAxis, y, baseline } = buildMoneyScale(points, plot.top, plot.bottom);
  const gap = (plot.right - plot.left) / Math.max(1, points.length - 1);
  const x = (index) => plot.left + index * gap;
  const coordinates = (subset) => subset.map((point) => `${x(points.indexOf(point))},${y(point.projected_balance)}`).join(' ');
  const historical = points.filter((point) => point.is_past || point.is_today);
  const projected = points.filter((point) => !point.is_past);
  const line = coordinates(points);
  const paydayIndex = points.findIndex((point) => point.date === payday?.date);
  const minimumIndex = points.findIndex((point) => point.date === minimum?.date);
  let paydayLabelX = Math.min(plot.right-50, Math.max(plot.left+50, x(paydayIndex)));
  if (paydayIndex >= 0 && Math.abs(paydayLabelX-x(todayIndex)) < 86) {
    paydayLabelX = x(todayIndex)+90 <= plot.right-50 ? x(todayIndex)+90 : x(todayIndex)-90;
  }
  const tickIndexes = [...new Set([0, Math.round(points.length * .2), todayIndex, Math.round(points.length * .55), Math.round(points.length * .78), points.length - 1])].filter((index) => index >= 0 && index < points.length).sort((a, b) => a-b).filter((index, order, indexes) => order === 0 || index-indexes[order-1] >= 3);
  const countdown = paydayCountdown(payday?.date || horizon?.payday_date, now);
  const timeLabel = now.toLocaleTimeString('th-TH', { timeZone: 'Asia/Bangkok', hour12: false });
  const selectFromPointer = (event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = (event.clientX - bounds.left) / bounds.width * 960;
    const index = Math.max(0, Math.min(points.length - 1, Math.round((position - plot.left) / gap)));
    setSelectedDate(points[index].date);
  };

  return <div className="money-timeline">
    <div className="timeline-controls">
      <div className="timeline-legend" aria-label="คำอธิบายกราฟ">
        <span><i className="legend-history" /> ย้อนหลังจำลอง 7 วัน</span><span><i className="legend-today" /> วันนี้</span><span><i className="legend-future" /> คาดการณ์</span><span><i className="legend-expense" /> รายจ่ายรวม</span>
      </div>
      <div className="timeline-ranges" role="group" aria-label="ช่วงคาดการณ์ล่วงหน้า">{[7, 14, 30].map((days) => <button key={days} aria-pressed={range === days} onClick={() => { setRange(days); setSelectedDate(null); }}>{days} วัน</button>)}</div>
    </div>
    <div className="timeline-clock-strip">
      <div className="timeline-clock"><span className="clock-emblem"><Clock3 size={17} /></span><div><small>เวลาไทย · {dateLabel(today.date, { weekday: 'short' })}</small><time dateTime={now.toISOString()}>{timeLabel}<span> ICT</span></time></div></div>
      <div className="payday-countdown"><CalendarClock size={18} /><div><small>ถึงวันเงินเดือนเข้าจำลอง</small><span>{countdown ? <><b>{countdown.days}</b> วัน <b>{pad(countdown.hours)}</b> ชม. <b>{pad(countdown.minutes)}</b> นาที <b>{pad(countdown.seconds)}</b> วิ</> : 'กำลังคำนวณ'}</span></div></div>
      {onRefresh && <button className="timeline-refresh" aria-label="อัปเดตข้อมูลคาดการณ์" disabled={busy} onClick={onRefresh}><RefreshCw size={15} /><span>อัปเดตข้อมูล</span></button>}
    </div>
    <div className="timeline-axis-head"><span>จำนวนเงิน (บาท) <b>สเกลเดียวกัน</b></span><div className="timeline-display-toggles"><button aria-pressed={showHistory} onClick={() => { setShowHistory(!showHistory); setSelectedDate(null); }}>ย้อนหลัง</button><button aria-pressed={showExpenses} onClick={() => setShowExpenses(!showExpenses)}>แท่งรายจ่าย</button></div></div>
    <div className="timeline-scroll" ref={scrollRef} tabIndex="0" aria-label="พื้นที่กราฟ เลื่อนแนวนอนบนมือถือเพื่อดูทุกวัน">
      <svg className="cashflow-svg" viewBox="0 0 960 306" role="img" aria-label={`เส้นยอดเงินย้อนหลังจำลองและคาดการณ์ ${range} วัน แท่งแสดงรายจ่าย เลือกวันที่แถบเลื่อนด้านล่าง`} onClick={selectFromPointer} onPointerMove={(event) => { if (event.pointerType === 'mouse') selectFromPointer(event); }}>
        <defs><linearGradient id={`${id}area`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#93d8ba" stopOpacity=".38" /><stop offset="1" stopColor="#bdebd5" stopOpacity=".03" /></linearGradient><linearGradient id={`${id}expense`} x1="0" x2="0" y1="0" y2="1"><stop stopColor="#e8b080" /><stop offset="1" stopColor="#f8d8b8" /></linearGradient></defs>
        {todayIndex > 0 && <rect x={plot.left} y={plot.top} width={x(todayIndex)-plot.left} height={plot.bottom-plot.top} fill="#eaf1fb" opacity=".5" rx="8" />}
        <rect x={x(todayIndex)} y={plot.top} width={plot.right-x(todayIndex)} height={plot.bottom-plot.top} fill="#eef8f1" opacity=".55" rx="8" />
        {balanceAxis.ticks.map((tick) => <g key={tick}><line x1={plot.left} x2={plot.right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? '#aebfb5' : '#e2eae3'} strokeDasharray={tick === 0 ? '4 4' : undefined} /><text x="52" y={y(tick)+4} textAnchor="end" className="balance-axis-label">{axisLabel(tick)}</text></g>)}
        {tickIndexes.map((index) => <line key={index} x1={x(index)} x2={x(index)} y1={plot.top} y2={plot.bottom} stroke="#e4ebe6" strokeDasharray="3 6" />)}
        <polygon points={`${plot.left},${y(0)} ${line} ${plot.right},${y(0)}`} fill={`url(#${id}area)`} />
        {showExpenses && points.map((point, index) => <rect key={point.date} x={x(index)-Math.min(7, gap*.31)} y={y(cashOut(point))} width={Math.min(14, gap*.62)} height={Math.max(0, baseline-y(cashOut(point)))} rx="3" fill={point.is_past ? '#adcbe3' : `url(#${id}expense)`} stroke={point.commitment_payment > 0 ? '#cb975e' : 'none'} strokeWidth="1" opacity={point.date === selected.date ? 1 : .75} />)}
        <polyline points={coordinates(historical)} fill="none" stroke="#7aadd1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <polyline points={coordinates(projected)} fill="none" stroke="#238c69" strokeWidth="3.2" strokeDasharray="5 6" strokeLinecap="round" strokeLinejoin="round" />
        <line x1={x(todayIndex)} x2={x(todayIndex)} y1={plot.top-4} y2={plot.bottom} stroke="#7aadd1" strokeDasharray="3 5" />
        <rect x={x(todayIndex)-24} y="8" width="48" height="21" rx="10.5" fill="#deebf7" /><text x={x(todayIndex)} y="22" textAnchor="middle" className="today-flag">วันนี้</text>
        <circle cx={x(todayIndex)} cy={y(today.projected_balance)} r="7" fill="#4b9fb8" stroke="#fff" strokeWidth="3" />
        {paydayIndex >= 0 && <g><line x1={x(paydayIndex)} x2={x(paydayIndex)} y1={plot.top} y2={plot.bottom} stroke="#d6b572" strokeDasharray="3 5" /><circle cx={x(paydayIndex)} cy={y(payday.projected_balance)} r="7" fill="#e9bd69" stroke="#fff" strokeWidth="3" /><rect x={paydayLabelX-50} y="8" width="100" height="21" rx="10.5" fill="#f9edcc" /><text x={paydayLabelX} y="22" textAnchor="middle" className="payday-flag">เงินเดือน {dateLabel(payday.date)}</text></g>}
        {minimumIndex >= 0 && minimumIndex !== todayIndex && <circle cx={x(minimumIndex)} cy={y(minimum.projected_balance)} r="4.5" fill="#fff" stroke="#bd8f62" strokeWidth="2.5" />}
        <line x1={x(selectedIndex)} x2={x(selectedIndex)} y1={plot.top} y2={plot.bottom} stroke="#396c57" opacity=".4" strokeDasharray="2 4" /><circle cx={x(selectedIndex)} cy={y(selected.projected_balance)} r="5.5" fill={selected.is_today ? '#4b9fb8' : '#2a7254'} stroke="#fff" strokeWidth="2.5" />
        {tickIndexes.map((index) => <text key={index} x={x(index)} y="289" textAnchor="middle" className={points[index].is_today ? 'date-tick current' : 'date-tick'}>{dateLabel(points[index].date)}</text>)}
      </svg>
    </div>
    <p className="chart-touch-hint">เลื่อนกราฟในแนวนอน แล้วแตะวันที่ต้องการ หรือใช้แถบเลือกวันด้านล่าง</p>
    <div className="timeline-scrubber"><button aria-label="ดูวันก่อนหน้า" disabled={selectedIndex === 0} onClick={() => setSelectedDate(points[selectedIndex-1].date)}><ChevronLeft size={17} /></button><input type="range" min="0" max={points.length-1} value={selectedIndex} style={{ '--slider-progress': `${selectedIndex / (points.length-1) * 100}%` }} aria-label="เลือกวันคาดการณ์" aria-valuetext={`${dateLabel(selected.date)} ยอดคงเหลือ ${money(selected.projected_balance)} บาท`} onChange={(event) => setSelectedDate(points[Number(event.target.value)].date)} /><button aria-label="ดูวันถัดไป" disabled={selectedIndex === points.length-1} onClick={() => setSelectedDate(points[selectedIndex+1].date)}><ChevronRight size={17} /></button></div>
    <div className={`timeline-selected ${selected.is_past ? 'is-history' : ''}`} aria-live="polite">
      <div className="selected-day"><span className="selected-day-icon"><CalendarDays size={20} /></span><div><small>{selected.is_today ? 'จุดปัจจุบัน' : selected.is_past ? 'ย้อนหลังจำลอง' : 'คาดการณ์ล่วงหน้า'}</small><strong>{dateLabel(selected.date, { weekday: 'short' })}</strong></div></div>
      <div><span>ยอดคงเหลือ</span><strong className={selected.projected_balance < 0 ? 'amount-warning' : ''}>฿{money(selected.projected_balance, 2)}</strong></div><div><span>ใช้จ่ายประจำวัน</span><b>฿{money(selected.is_past ? selected.actual_spend : selected.predicted_spend)}</b></div><div><span>ภาระที่จ่าย</span><b>฿{money(selected.commitment_payment)}</b></div><div><span>เงินเข้า</span><b className="inflow-value">{selected.salary_inflow > 0 ? '+' : ''}฿{money(selected.salary_inflow)}</b></div>
    </div>
    <div className="timeline-insights">
      <article className="timeline-insight low-point"><span className="insight-emblem"><ArrowDownRight size={19} /></span><div><small>ยอดต่ำสุดก่อนเงินเดือนเข้า</small><strong className={minimum?.projected_balance < 0 ? 'amount-warning' : ''}>฿{money(minimum?.projected_balance, 2)}</strong><span>{dateLabel(minimum?.date)} · {minimum?.projected_balance >= 0 ? 'ยอดคาดการณ์ยังไม่ติดลบ' : 'ควรเตรียมสภาพคล่องเพิ่ม'}</span></div></article>
      <article className="timeline-insight salary-point"><span className="insight-emblem"><Coins size={19} /></span><div><small>รอบเงินเดือนถัดไป</small><strong>{dateLabel(payday?.date || horizon?.payday_date)}</strong><span>{payday ? `เงินเข้าจำลอง +฿${money(payday.salary_inflow)}` : 'อยู่นอกช่วงคาดการณ์'}{payday && paydayIndex < 0 && ' · นอกช่วงกราฟที่เลือก'}</span></div></article>
      <article className={`timeline-insight runway-point ${horizon?.commitment_at_risk ? 'needs-plan' : ''}`}><span className="insight-emblem"><ShieldCheck size={19} /></span><div><small>{horizon?.commitment_at_risk ? 'ภาระใกล้ถึงกำหนดอาจไม่พอ' : 'ใช้ได้ต่อวันโดยประมาณ'}</small><strong>{horizon?.commitment_at_risk ? `ขาด ฿${money(horizon.deficit_amount)}` : `฿${money(horizon?.daily_safe_limit)}`}</strong><span>บัญชีหลักวันนี้ ฿{money(today.projected_balance, 2)} · {horizon?.alert_suppressed ? 'แจ้งเตือนเฉพาะภาระเสี่ยง' : 'ลองดึงเงินออมคืน'}</span></div></article>
    </div>
    <div className="timeline-footnote"><Info size={14} /><p>เส้นยอดคงเหลือและแท่งรายจ่ายใช้สเกลเงินบาทเดียวกันทางซ้าย · แท่งรวมรายจ่ายประจำวันและภาระที่จ่าย · ข้อมูลการเงินจำลอง นาฬิกาแสดงเวลาไทย</p></div>
  </div>;
}
