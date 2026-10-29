import React, { useId } from 'react';
import { ArrowRight, ChevronDown, FlaskConical } from 'lucide-react';
import './scenarios.css';

const scenarios = [
  { id: 'healthy', label: 'มีเงินพร้อมออม', shortLabel: 'พร้อมออม', detail: 'ดูยอดพร้อมออม หลังกันบิลและเงินสำรอง' },
  { id: 'normal_dip', label: 'เงินลด แต่ยังพอใช้', shortLabel: 'เงินลดลง', detail: 'ดูงบต่อวัน เมื่อยอดเงินในบัญชีลดลง' },
  { id: 'commitment_risk', label: 'เงินอาจไม่พอจ่ายบิล', shortLabel: 'เสี่ยงจ่ายบิล', detail: 'ดูคำเตือนและทางเลือก เมื่อเงินอาจขาด' },
];
const guidance = {
  home: 'เลือกแล้วดูงบวันนี้และคำแนะนำที่เปลี่ยนไป',
  plan: 'เลือกแล้วลองตั้งงบ ให้เงินพอถึงวันเงินเดือน',
  accounts: 'เลือกแล้วเปรียบเทียบกราฟเงินและบิลที่ต้องจ่าย',
  transactions: 'เลือกแล้วดูยอดบัญชี ก่อนลองออมหรือโอน',
  savings: 'เลือกแล้วดูยอดพร้อมออมและคำแนะนำในหน้านี้',
};
export const scenarioLabel = (id) => scenarios.find((item) => item.id === id)?.label || (id === 'high_value' ? 'รายการมูลค่าสูง' : id === 'default' ? 'ค่าเริ่มต้นของโปรไฟล์' : 'ยังไม่ทราบสถานการณ์');

export default function ScenarioPicker({ horizon, busy, onScenario, page, pending, onResume, doReset, persona }) {
  const titleId = useId();
  return <section className="scenario-context" aria-label="สถานการณ์ทดลองที่ใช้อยู่">
    <div className="scenario-active" role="status"><strong>สถานการณ์ทดลอง: {scenarioLabel(horizon.scenario)}{horizon.scenario === 'default' && ` · ${persona}`}</strong><p>ยอดและแผนด้านล่างเปลี่ยนตามสถานการณ์นี้ · เงินจำลอง</p><button type="button" className="text-link" disabled={busy || pending} onClick={doReset}>กลับค่าเริ่มต้น</button></div>
    <details className="scenario-explorer" aria-labelledby={titleId} aria-busy={busy}>
    <summary className="scenario-drawer-toggle">
      <FlaskConical size={16} aria-hidden="true"/>
      <span id={titleId}>เปลี่ยนสถานการณ์</span>
      <span className="scenario-current">{scenarioLabel(horizon.scenario)}</span>
      <ChevronDown className="scenario-drawer-chevron" size={15} aria-hidden="true"/>
    </summary>
    <div className="scenario-drawer-body">
    <p className="scenario-guidance">{guidance[page]}</p>
    <div className="scenario-choices" role="group" aria-label="เลือกสถานการณ์ทดลอง">
      {scenarios.map(({ id, label, shortLabel }) => <button key={id} type="button" aria-label={label} aria-pressed={horizon.scenario === id} disabled={busy || pending || horizon.scenario === id} onClick={() => onScenario(id)}>
        <span className="scenario-label-full" aria-hidden="true">{label}</span><span className="scenario-label-short" aria-hidden="true">{shortLabel}</span>
      </button>)}
    </div>
    <details className="scenario-info"><summary>เปลี่ยนแล้วเริ่มข้อมูลทดลองใหม่ <ChevronDown size={14}/></summary><div><p>{guidance[page]}</p><ul>{scenarios.map(({ id, label, detail }) => <li key={id}><strong>{label}</strong> · {detail}</li>)}</ul><p>เริ่มยอดเงินและการตั้งค่าทดลองใหม่ โดยคงเงินสำรองที่คุณตั้งไว้ · ไม่มีการย้ายเงินจริง</p></div></details>
    {pending && <div className="scenario-pending"><p>จัดการรายการโอนที่รออยู่ก่อนเปลี่ยนสถานการณ์</p><button type="button" className="text-link" disabled={busy} onClick={onResume}>กลับไปดูรายการ <ArrowRight size={15}/></button></div>}
    </div>
  </details></section>;
}
