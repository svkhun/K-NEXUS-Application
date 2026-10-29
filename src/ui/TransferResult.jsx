import React, { useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, CircleAlert, Clock3, Download, Fingerprint, LockKeyhole, ShieldAlert, ShieldCheck, X } from 'lucide-react';
import { formatCooldown, remainingCooldown } from './transferCooldown.mjs';
import TransferPlanning from './TransferPlanning';
const money = (v) => (v == null ? '—' : Number(v).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
function saveReceipt(result, amount, recipient) {
  const content = `K-NEXUS · FlowSense × TrustGraph\nใบรายการทดลอง — ไม่มีการโอนเงินจริง\n${result.receipt_id || 'DEMO'}\n${result.executed_at || new Date().toISOString()}\nยอดโอน ${money(amount)} บาท\nไปยัง ${recipient.name} (${recipient.id})\n${result.message || 'ดำเนินการในบัญชีจำลองสำเร็จ'}\nไม่ใช่หลักฐานการชำระเงินจริงหรือผลิตภัณฑ์ทางการของ KBank`;
  const url = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url; a.download = 'K-NEXUS-demo-receipt.txt'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function TransferResult({ result, amount, recipient, busy, clearanceToken, verify, decide, clear, scanning, checkCooldown, evaluate, cancelInFooter = false }) {
  const [, tick] = useState(0);
  const anchor = useMemo(() => performance.now(), [result]);
  useEffect(() => {
    if (!['MICRO_AUTH_REQUIRED', 'TRANSFER_REVIEW'].includes(result?.status)) return;
    const timer = setInterval(() => tick((n) => n + 1), 1000);
    const sync = () => { if (document.visibilityState !== 'hidden') checkCooldown(); };
    const refresh = setInterval(sync, 30000);
    window.addEventListener('focus', sync);
    document.addEventListener('visibilitychange', sync);
    return () => { clearInterval(timer); clearInterval(refresh); window.removeEventListener('focus', sync); document.removeEventListener('visibilitychange', sync); };
  }, [result?.status, checkCooldown]);
  const elapsed = performance.now() - anchor;
  const seconds = remainingCooldown(result, elapsed);
  const waiting = seconds > 0;
  const serverTime = Number(result?.server_now) + elapsed / 1000;
  const tokenValid = clearanceToken && Number(result?.clearance_expires_at) > serverTime;
  const success = result && ['APPROVED', 'TRANSFER_EXECUTED'].includes(result.status);
  const blocked = result?.status === 'BLOCKED_MULE_INTERDICTION';
  const canceled = result?.status === 'TRANSFER_CANCELLED';
  const expired = result?.status === 'REVIEW_EXPIRED' || (result?.review_expires_at && serverTime >= result.review_expires_at);
  const unknown = result?.status === 'OUTCOME_UNKNOWN';
  const terminal = success || blocked || canceled || expired || unknown;
  const normalReview = result?.status === 'TRANSFER_REVIEW';
  const changed = result?.plan_changed;
  const Icon = success ? Check : blocked ? LockKeyhole : canceled || expired ? ShieldCheck : ShieldAlert;
  const steps = result?.cooldown_required ? ['ดูเหตุผล', 'พักตรวจสอบ', 'ยืนยันจำลอง', 'ตัดสินใจ'] : ['ดูเหตุผล', 'ยืนยันจำลอง', 'ตัดสินใจ'];
  const step = waiting ? 1 : tokenValid ? steps.length - 1 : steps.length - 2;
  return <div className={`surface result-card${normalReview ? ' normal-review' : ''}`}>
    <span className="section-kicker">TRUSTGRAPH · ผลการตรวจสอบ</span>
    {!result ? <div className="result-empty"><span><ShieldCheck size={29} /></span><h3>พร้อมตรวจสอบ</h3><p>เลือกสถานการณ์และกดทดลองโอน เพื่อดูว่าระบบช่วยคุณอย่างไร</p></div> : <div className="result-detail">
      {!normalReview && <span className={`result-symbol ${success || canceled || expired ? 'approved' : blocked ? 'blocked' : 'warning'}`}><Icon size={28} /></span>}
      <h3>{unknown ? 'ยังไม่ทราบผลรายการ' : success ? 'โอนเงินจำลองสำเร็จ' : blocked ? 'ระงับรายการนี้' : canceled ? 'ยกเลิกรายการแล้ว' : expired ? 'รายการตรวจสอบหมดอายุ' : changed ? 'แผนเงินเปลี่ยน กรุณาตรวจใหม่' : normalReview ? 'ดูแผนเงินก่อนยืนยันโอน' : result.risk_tier === 'HIGH_VALUE_DEMO_CHECK' ? 'ยืนยันรายการมูลค่าสูง' : result.cooldown_required ? 'พักก่อนโอน ตรวจให้มั่นใจ' : 'พบความเสี่ยงที่ควรรู้'}</h3>
      <p>{unknown ? 'อาจบันทึกการโอนจำลองแล้ว กรุณาใช้ปุ่มรับผลคำสั่งเดิมและตรวจยอด/ประวัติ ห้ามสร้างรายการซ้ำ' : success ? result.zero_delay_baseline ? 'รายการปกติผ่านทันที · ไม่มีขั้นตอนยืนยันเพิ่ม' : 'ดำเนินการตามการตัดสินใจของคุณแล้ว' : canceled ? 'ยังไม่ได้โอนเงิน ตรวจสอบผู้รับผ่านช่องทางที่คุณรู้จักก่อนทำรายการใหม่' : expired ? 'ยังไม่ได้โอนเงิน รายการใหม่ต้องตรวจความเสี่ยงอีกครั้ง' : result.primary_reason_th || result.direct_risk_reasoning}</p>
      {success ? <><div className="demo-slip"><span>ใบรายการทดลอง</span><strong>฿{money(amount)}</strong><p>{recipient.name}</p><small>{result.receipt_id}</small><b>ไม่มีการโอนเงินจริงหรือยืนยันว่าผู้รับได้รับเงิน</b></div><button className="secondary-button" onClick={() => saveReceipt(result, amount, recipient)}><Download size={17} /> บันทึกใบรายการทดลอง</button></> : !canceled && !expired && !unknown && <>
        {!normalReview && <div className="risk-explanation"><CircleAlert size={17} /><span>ยังไม่มีการหักเงินจากบัญชีของคุณ</span></div>}
        {!normalReview && <details className="risk-details" open={!result.cooldown_required}>
          <summary>ข้อมูลประกอบและ policy ที่ตรวจเพิ่ม</summary>
          <p className="small-note">รายการต่อไปนี้เป็นบริบทและกฎจำลอง ไม่ใช่ attribution หรือเหตุผลเชิงเหตุและผลจากโมเดล</p>
          <ul>{result.direct_risk_reasons_list?.map((reason, i) => <li key={i}>{reason}</li>)}</ul>
          {result.target_meta && <dl className="risk-meta" aria-label="ข้อมูลบัญชีผู้รับ อธิบายเพิ่มเติม">
            <div>
              <dt>อายุบัญชีผู้รับ</dt>
              <dd>{result.target_meta.account_age_days == null ? 'ไม่มีข้อมูล' : `${result.target_meta.account_age_days} วัน`}</dd>
              <dd className="risk-meta-description">นับตั้งแต่วันที่เปิดบัญชีผู้รับ</dd>
            </div>
            <div>
              <dt>รับเงินแล้วโอนต่อเร็วแค่ไหน</dt>
              <dd>{result.target_meta.velocity_sec == null ? 'ไม่มีข้อมูล' : `เฉลี่ย ${Math.floor(result.target_meta.velocity_sec).toLocaleString('th-TH')} วินาที`}</dd>
              <dd className="risk-meta-description">เวลาระหว่างเงินเข้าบัญชีผู้รับกับการโอนออกต่อ ไม่ใช่ระยะเวลาโอนของคุณ</dd>
            </div>
            <div>
              <dt>การยืนยันตัวตนเจ้าของบัญชี</dt>
              <dd>ไม่มีรายละเอียดให้ตรวจสอบ</dd>
              <dd className="risk-meta-description">หมายถึงการตรวจว่าเจ้าของบัญชีเป็นใคร ข้อมูลทดลองนี้ยังใช้ยืนยันตัวผู้รับไม่ได้</dd>
            </div>
          </dl>}
          <p className="small-note">ข้อมูลทั้งหมดเป็นข้อมูลสมมติ ใช้ประกอบการทดลองเท่านั้น สัญญาณเหล่านี้ไม่ได้ยืนยันว่าผู้รับปลอดภัยหรือเป็นมิจฉาชีพ</p>
        </details>}
      </>}
      {!terminal && <>
        <div className="risk-transfer-summary"><span>{recipient.name}</span><strong>฿{money(amount)}</strong><small>{recipient.id} · บัญชีสมมติ</small></div>
        {changed ? <div className="impact-changed" role="status"><p>ยอดเงิน บิล หรือวันคำนวณเปลี่ยนแล้ว ตัวเลขเดิมยังใช้ยืนยันไม่ได้ ยังไม่มีการหักเงินจากรายการนี้</p><button className="primary-button" disabled={busy} onClick={evaluate}>คำนวณและตรวจรายการใหม่</button></div> : <TransferPlanning result={result} />}
        {!normalReview && <ol className="auth-steps" aria-label="ขั้นตอนการตรวจเพิ่ม">{steps.map((label, i) => <li key={label} className={i < step ? 'done' : i === step ? 'current' : ''}><span aria-hidden="true">{i + 1}</span>{label}</li>)}</ol>}
        {result.cooldown_required && <section className={`transfer-cooldown ${waiting ? '' : 'ready'}`} aria-label="สถานะพักก่อนโอน">
          <div className="cooldown-heading"><Clock3 size={20} /><strong>{waiting ? 'ให้เวลาตัวเองตรวจสอบผู้รับ' : 'ครบเวลาพักแล้ว'}</strong></div>
          {waiting ? <><div className="cooldown-clock" role="timer" aria-label="เวลาพักที่เหลือ">{formatCooldown(seconds)}</div><p>ยืนยันได้หลัง {new Date(result.cooldown_ends_at * 1000).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok' })} น. เวลาไทย</p><p>ปิดหน้าต่างหรือรีเฟรชได้ เวลาของรายการเดิมจะนับต่อ · กดยกเลิกเพื่อจบรายการและเวลาพัก</p><small className="review-expiry">รายการทดลองหมดอายุ {new Date(result.review_expires_at * 1000).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok' })} น.</small></> : <p role="status">ยังต้องตรวจผู้รับและยืนยันเอง การครบเวลาไม่ได้แปลว่ารายการปลอดภัย และไม่มีการโอนอัตโนมัติ</p>}
          <button className="text-link" disabled={busy} onClick={checkCooldown}>อัปเดตเวลาจากเซิร์ฟเวอร์</button>
        </section>}
        {!result.cooldown_required && result.risk_tier === 'CRITICAL_ANOMALY' && <p className="small-note">รายการนี้ปิดเวลาพักเสริมไว้ การตรวจความเสี่ยงและยืนยันจำลองยังทำงาน</p>}
        {scanning > 0 && <div className="simulated-scan" role="status"><Fingerprint size={36} /><strong>กำลังจำลอง Micro-Auth · {scanning} วินาที</strong><div className="meter-track"><i style={{ width: `${(5-scanning) * 20}%` }} /></div></div>}
        {!changed && <div className="auth-actions">{normalReview ? <button className="primary-button" disabled={busy} onClick={() => decide('PROCEED')}><Check size={18} />ยืนยันโอนจำลอง ฿{money(amount)}</button> : !tokenValid ? <button className="primary-button" disabled={busy || waiting} onClick={verify}><Fingerprint size={18} />{waiting ? `รอพักก่อนโอน · ${formatCooldown(seconds)}` : 'จำลองยืนยันตัวตน 5 วินาที'}</button> : <button className="primary-button" disabled={busy || waiting} onClick={() => decide('PROCEED')}><Check size={18} /> ยืนยันโอนต่อ ฿{money(amount)}</button>}{!cancelInFooter && <button className="secondary-button" disabled={busy} onClick={() => decide('CANCEL')}><X size={17} /> ยกเลิกรายการ</button>}</div>}
        {!normalReview && <small className="auth-note">จำลองเท่านั้น ไม่เปิดกล้องหรือเก็บใบหน้า · หลังยืนยันจำลองแล้วมีเวลา 2 นาทีในการยืนยันโอน หากหมดเวลายืนยันใหม่ได้</small>}
      </>}
      {result.raw_model_score !== undefined && <p className="small-note">คะแนนโมเดล {Number(result.raw_model_score).toFixed(4)} · คะแนนหลัง policy {Number(result.policy_score).toFixed(4)} · {result.explanation_note}</p>}
      {result.missing_graph_context && <p className="message error">บัญชีนี้เป็นบัญชีที่เดโมรู้จัก แต่ไม่มี graph embedding ใช้เวกเตอร์ศูนย์ตาม contract การไม่มีข้อมูลไม่ได้รับรองว่าปลอดภัย</p>}
      {result.latency_ms !== undefined && <div className="inference-note">เวลาประเมินความเสี่ยงในต้นแบบ {result.latency_ms} ms · ไม่รวมแผนเงินและเครือข่าย</div>}
      {terminal && !unknown && <button className="text-link" onClick={clear}>ลองสถานการณ์อื่น <ArrowRight size={16} /></button>}
    </div>}
  </div>;
}
