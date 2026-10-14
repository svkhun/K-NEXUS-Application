import React, { useId, useState } from 'react';
const money = (v) => Number(v || 0).toLocaleString('th-TH', { maximumFractionDigits: 0 });
const dateLabel = (date) => new Date(`${date}T12:00:00`).toLocaleDateString('th-TH', { day: 'numeric', month: 'short' });
export default function ForecastChart({ timeline = [] }) {
  const gradient = useId().replace(/:/g, '');
  const [range, setRange] = useState(30);
  const [index, setIndex] = useState(0);
  const points = timeline.filter((p) => !p.is_past).slice(0, range + 1);
  if (points.length < 2) return <div className="chart-loading">กำลังเตรียมกราฟ…</div>;
  const selected = Math.min(index, points.length - 1);
  const point = points[selected];
  const values = points.map((p) => Number(p.projected_balance));
  const low = Math.min(0, ...values) - 1200, high = Math.max(...values) + 1000;
  const x = (i) => 18 + i * (564 / (points.length - 1));
  const y = (v) => 150 - ((v - low) / Math.max(1, high - low)) * 120;
  const line = points.map((p, i) => `${x(i)},${y(p.projected_balance)}`).join(' ');
  return <div className="forecast-explorer"><div className="chart-toolbar"><span>เลือกช่วงที่อยากดู</span><div>{[7, 14, 30].map((d) => <button key={d} aria-pressed={range === d} onClick={() => { setRange(d); setIndex(0); }}>{d} วัน</button>)}</div></div><div className="forecast-chart" role="img" aria-label={`กราฟเงินคงเหลือ ${range} วัน ใช้แถบเลื่อนด้านล่างเพื่ออ่านแต่ละวัน`}><svg viewBox="0 0 600 175" preserveAspectRatio="none"><defs><linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#15a575" stopOpacity=".23" /><stop offset="1" stopColor="#15a575" stopOpacity="0" /></linearGradient></defs><line x1="18" x2="582" y1={y(0)} y2={y(0)} stroke="#bdcdc4" strokeDasharray="5 5" /><polygon points={`18,160 ${line} 582,160`} fill={`url(#${gradient})`} /><polyline points={line} fill="none" stroke="#099c72" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" /><line x1={x(selected)} x2={x(selected)} y1="15" y2="160" stroke="#0c8e70" strokeDasharray="3 4" opacity=".4" /><circle cx={x(selected)} cy={y(point.projected_balance)} r="5" fill="#099c72" stroke="white" strokeWidth="3" /></svg><div className="chart-labels"><span>วันนี้</span><span>{dateLabel(points[Math.floor(points.length / 2)].date)}</span><span>{dateLabel(points.at(-1).date)}</span></div></div><input className="day-slider" type="range" min="0" max={points.length - 1} value={selected} aria-label="เลือกวันคาดการณ์" aria-valuetext={`${dateLabel(point.date)} ยอดคงเหลือ ${money(point.projected_balance)} บาท`} onChange={(e) => setIndex(Number(e.target.value))} /><div className="forecast-day-detail" aria-live="polite"><div><span>{point.is_today ? 'วันนี้' : dateLabel(point.date)}</span><strong className={point.projected_balance < 0 ? 'amount-warning' : ''}>฿{money(point.projected_balance)}</strong></div><div><span>{point.is_today ? 'ใช้ไปวันนี้' : 'คาดว่าใช้จ่าย'}</span><b>฿{money(point.predicted_spend)}</b></div><div><span>{point.salary_inflow > 0 ? 'เงินเดือนเข้า' : 'ภาระที่จ่าย'}</span><b>{point.salary_inflow > 0 ? '+' : ''}฿{money(point.salary_inflow || point.commitment_payment)}</b></div></div><details className="history-details"><summary>ดูข้อมูลจำลองย้อนหลัง 7 วัน</summary><div className="history-list">{timeline.filter((p) => p.is_past).map((p) => <div key={p.date}><span>{dateLabel(p.date)}</span><span>ใช้จ่าย ฿{money(p.actual_spend)}</span><strong>คงเหลือ ฿{money(p.projected_balance)}</strong></div>)}</div></details></div>;
}
