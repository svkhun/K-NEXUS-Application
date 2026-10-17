import React from 'react';
import { ArrowRight, Check, ShieldCheck, SlidersHorizontal, Target, X } from 'lucide-react';

export const trials = [
  { id: 'budget', title: 'ลองเปลี่ยนงบรายวัน', result: 'เห็นว่าใช้วันละเท่าไร แล้วเงินพอถึงเงินเดือนหรือไม่', icon: Target },
  { id: 'transfer', title: 'ลองตรวจผู้รับก่อนโอน', result: 'เห็นคำเตือนผู้รับ และเงินใช้ชีวิตที่เหลือหลังโอน', icon: ShieldCheck },
  { id: 'reserve', title: 'ลองปรับเงินสำรอง', result: 'เทียบงบก่อน–หลัง โดยยังไม่ต้องบันทึกยอดใหม่', icon: SlidersHorizontal },
];

export function TrialStart({ completed, onStart, busy }) {
  return <section className="trial-start" aria-labelledby="trial-start-title">
    <div className="trial-start-heading"><span>เริ่มตรงนี้ · เลือกเรื่องที่อยากลอง</span><span aria-label={`ลองแล้ว ${completed.length} จาก 3 เรื่อง`}>{completed.length}/3</span></div>
    <h2 id="trial-start-title">เลือก 1 เรื่อง<br/>แล้วลองทำตามได้เลย</h2>
    <div className="trial-choices">{trials.map(({id, title, result, icon: Icon}, index) => <button key={id} className={index === 0 ? 'suggested' : ''} disabled={busy} onClick={() => onStart(id)}><span className={`trial-choice-icon trial-${id}`}>{completed.includes(id) ? <Check size={21}/> : <Icon size={21}/>}</span><span><strong>{title}</strong><small>{result}</small></span><span className="trial-choice-action">{completed.includes(id) ? 'ลองอีก' : index === 0 ? 'เริ่มเลย' : 'ลองดู'}<ArrowRight size={16}/></span></button>)}</div>
    <p>{completed.length === 3 ? 'ลองครบแล้ว คุณกลับมาเลือกทดลองซ้ำ หรือใช้เมนูด้านล่างต่อได้' : 'มีตัวอย่างให้กด พร้อมบอกจุดที่ควรดู · ใช้ข้อมูลสมมติ ไม่มีเงินจริง'}</p>
  </section>;
}

export default function TrialGuide({ id, guide, children, onAction, actionLabel, busy }) {
  if (!guide) return null;
  const title = trials.find((item) => item.id === id).title;
  return <section className={`trial-guide ${guide.done ? 'trial-observed' : ''}`} id={`trial-guide-${id}`} tabIndex={-1} aria-label={`วิธีทดลอง: ${title}`}>
    <div className="trial-guide-top"><strong>{guide.done ? <Check size={17}/> : <span className="trial-step-dot"/>}{guide.done ? 'เห็นผลทดลองแล้ว' : 'ลองตามนี้ได้เลย'} · {title}</strong><button aria-label="ปิดคำแนะนำการทดลอง" onClick={guide.onExit}><X size={17}/></button></div>
    <div className="trial-guide-copy">{children}</div>
    <div className="trial-guide-actions">{!guide.done && <button className="trial-action" disabled={busy} onClick={onAction}>{actionLabel}<ArrowRight size={16}/></button>}{guide.done && <button className="trial-action" disabled={busy} onClick={guide.onNext}>{guide.nextLabel}<ArrowRight size={16}/></button>}<button className="trial-skip" onClick={guide.onExit}>ลองเองต่อ</button></div>
  </section>;
}
