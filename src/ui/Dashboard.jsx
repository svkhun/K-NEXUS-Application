import React from 'react';
import InsightsLab from './InsightsLab';
import { AccountGarden } from './FinanceDecor';
import { ScenarioPicker } from './SavingsPage';
import { DailySummary } from './DailyPlan';
import {
  ArrowDownLeft, ArrowRight,
  Bell, ChevronRight, Clock3, CreditCard, Eye, EyeOff,
  Home, RotateCcw, Send, ShieldAlert, ShieldCheck,
  Sparkles, Target, TrendingUp, Wallet,
} from 'lucide-react';

const money = (value, digits = 0) => new Intl.NumberFormat('th-TH', {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
}).format(Number(value ?? 0));

export function AccountTiles({ profile, openTab, hidden = false }) {
  const value = (amount) => hidden ? '••••••' : `฿ ${money(amount, 2)}`;
  return (
    <div className="account-tiles">
      <button className="account-tile main-account" onClick={() => openTab('accounts')}>
        <div className="account-tile-top"><span className="account-emblem"><Wallet size={16} /></span><div><strong>บัญชีออมทรัพย์</strong><small>{profile.masked_account_id} · บัญชีหลัก</small></div><ChevronRight size={16} /></div>
        <AccountGarden /><b>{value(profile.main_balance)}</b><span className="account-caption">พร้อมใช้สำหรับทุกวัน</span>
      </button>
      <button className="account-tile savings-account" onClick={() => openTab('savings')}>
        <div className="account-tile-top"><span className="account-emblem"><Sparkles size={16} /></span><div><strong>กระเป๋าเงินออม</strong><small>FlowSense · Flexible Savings</small></div><ChevronRight size={16} /></div>
        <AccountGarden /><b>{value(profile.vault_balance)}</b><span className="account-caption">ออมได้ ดึงคืนได้เมื่อจำเป็น</span>
      </button>
      <div className="account-tile protection-account">
        <div className="account-tile-top"><span className="account-emblem"><ShieldCheck size={16} /></span><div><strong>ตรวจความเสี่ยงก่อนโอน</strong><small>TrustGraph · สถานการณ์จำลอง</small></div><span className="protection-dot" /></div>
        <AccountGarden /><b>ดูความเสี่ยงของผู้รับ</b><button className="protection-link" onClick={() => openTab('transfer')}>ตรวจสอบก่อนโอน <ArrowRight size={14} /></button>
      </div>
    </div>
  );
}

export function Commitments({ horizon }) {
  return (
    <section className="surface commitments">
      <div className="surface-heading"><div><h2>ภาระที่ต้องจ่าย</h2><p className="heading-description">เตรียมเงินให้พร้อมก่อนถึงกำหนด</p></div><span className="subtle-total">ก่อนเงินเดือน ฿{money(horizon.total_recurring_commitments)}</span></div>
      <div className="commitment-list">
        {horizon.recurring_commitments?.filter((item) => item.amount > 0).map((item, index) => (
          <div key={`${item.name}-${index}`} className={`commitment-row ${item.is_at_risk ? 'at-risk' : ''}`}>
            <span className={`commitment-icon icon-${index}`}>{index === 0 ? <Home size={18} /> : index === 1 ? <CreditCard size={18} /> : <Bell size={18} />}</span>
            <div><strong>{item.name}</strong><small>อีก {item.due_days} วัน · {item.is_at_risk ? 'เงินอาจไม่พอ' : 'ตามกำหนด'}</small></div><b>฿{money(item.amount)}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function ActivityList({ activities, openTab }) {
  return (
    <section className="surface activity-card">
      <div className="surface-heading"><div><h2>รายการล่าสุด</h2><p className="heading-description">รายการออมและโอนในบัญชีทดลองนี้</p></div><Clock3 size={18} /></div>
      {activities.length ? <div className="activity-list">{activities.map(({ title, description, icon: Icon, time }, index) => (
        <div key={index} className="activity-row"><span className="activity-icon"><Icon size={17} /></span><div><strong>{title}</strong><small>{description}</small></div><time>{time}</time></div>
      ))}</div> : <div className="activity-starter"><p>ยังไม่มีรายการ เมื่อทดลองออมหรือโอนเงิน รายการจะแสดงที่นี่</p><button onClick={() => openTab('savings')}><span className="starter-icon mint"><Wallet size={18} /></span><span><strong>ลองออมเงิน</strong><small>เลือกจำนวนเงิน และดึงคืนได้เมื่อจำเป็น</small></span><ArrowRight size={16} /></button><button onClick={() => openTab('transfer')}><span className="starter-icon lilac"><ShieldCheck size={18} /></span><span><strong>ลองโอนเงิน</strong><small>เลือกผู้รับเพื่อดูผลตรวจความเสี่ยง</small></span><ArrowRight size={16} /></button></div>}
    </section>
  );
}

export function ForecastPanel({ horizon, chart }) {
  return (
    <section className="surface forecast-card">
      <div className="surface-heading timeline-heading"><div className="timeline-heading-copy"><div><h2>แนวโน้มเงินเข้า–ออก</h2><p className="heading-description">ย้อนหลังจำลอง 7 วัน และคาดการณ์ล่วงหน้าสูงสุด 30 วัน</p></div></div><span className={`runway-badge ${horizon.commitment_at_risk ? 'is-risk' : ''}`}><ShieldCheck size={15} />{horizon.commitment_at_risk ? 'ควรเตรียมสภาพคล่อง' : 'ภาระก่อนเงินเดือนมีเงินรองรับ'}</span></div>
      {chart}
    </section>
  );
}

export default function Dashboard({ profile, horizon, activities, hidden, setHidden, openTab, tryScenario }) {
  const total = Number(profile.main_balance) + Number(profile.vault_balance);
  return (
    <div className="bank-dashboard">
      <section className="home-wallet surface" aria-label="ภาพรวมบัญชี">
          <div className="total-balance-top"><div><span>เงินรวมของคุณ</span><div className="total-amount">{hidden ? '••••••••' : `฿${money(total, 2)}`}<button className="icon-button balance-eye" aria-label={hidden ? 'แสดงยอดเงิน' : 'ซ่อนยอดเงิน'} onClick={() => setHidden(!hidden)}>{hidden ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></div><button className="text-link" onClick={() => openTab('accounts')}>ดูบัญชี <ChevronRight size={14} /></button></div>
          <div className="home-pockets"><button onClick={() => openTab('accounts')}><span>บัญชีหลัก</span><strong>฿{money(profile.main_balance, 2)}</strong></button><button onClick={() => openTab('savings')}><span>เงินออม</span><strong>฿{money(profile.vault_balance, 2)}</strong></button></div>
          <div className="bank-quick-actions">
            <button onClick={() => openTab('transfer')}><span className="bank-action-icon action-primary"><Send size={21} /></span><strong>โอนเงิน</strong></button>
            <button onClick={() => openTab('savings')}><span className="bank-action-icon"><ArrowDownLeft size={21} /></span><strong>ออมเงิน</strong></button>
            <button onClick={() => openTab('savings')}><span className="bank-action-icon"><RotateCcw size={21} /></span><strong>ดึงเงินคืน</strong></button>
            <button onClick={() => openTab('plan')}><span className="bank-action-icon"><Target size={21} /></span><strong>แผนใช้เงิน</strong></button>
          </div>
      </section>
      <DailySummary {...{ horizon, openTab }} />
      <section className="home-services" aria-label="ตัวช่วยดูแลเงิน">
        <button className="home-service trend-service" onClick={() => openTab('accounts')}><span className="section-icon sky"><TrendingUp size={21} /></span><div><h2>แนวโน้มเงินเข้า–ออก</h2><p>ดูกราฟเงินเหลือและบิล<br />ล่วงหน้าสูงสุด 30 วัน</p></div><ChevronRight size={17} /></button>
        <button className="home-service saving-service" onClick={() => openTab('savings')}><span className="section-icon mint"><Wallet size={21} /></span><div><h2>เงินส่วนที่พร้อมออม</h2><strong>฿{money(horizon.recommended_sweep_amount, 2)}</strong><p>{horizon.recommended_sweep_amount > 0 ? 'ยอดแนะนำสำหรับรอบนี้' : 'รอบนี้พักการออมเพิ่มไว้ก่อน'}</p></div><ChevronRight size={17} /></button>
        <button className="home-service trust-service" onClick={() => tryScenario(1)}><span className="section-icon lilac"><ShieldCheck size={21} /></span><div><h2>ตรวจความเสี่ยงก่อนโอน</h2><p>ลองดูคำเตือนและเหตุผล<br />ก่อนตัดสินใจทำรายการ</p></div><ChevronRight size={17} /></button>
      </section>
      <div className="dashboard-activity"><ActivityList activities={activities} openTab={openTab} /></div>
    </div>
  );
}

export function AccountsPage({ profile, horizon, chart, openTab, hidden, doReset, busy, onScenario, refresh }) {
  return (
    <div className="accounts-page"><ScenarioPicker {...{ horizon, busy, onScenario }} />
      <AccountTiles profile={profile} openTab={openTab} hidden={hidden} />
      <div className="account-timeline"><ForecastPanel horizon={horizon} chart={chart} /></div><div className="account-planning-grid"><Commitments horizon={horizon} /><section className="surface reserve-overview"><span className="icon-box lilac"><Wallet size={23} /></span><span className="section-kicker">YOUR FINANCIAL CUSHION</span><h2>กันเงินให้พร้อม แล้วค่อยออม</h2><p>FlowSense แยกเงินสำรองและภาระก่อนแนะนำยอดออม เพื่อให้ยังมีเงินพร้อมใช้</p><div className="reserve-amounts"><div><span>เงินสำรองที่กันไว้</span><strong>฿{money(horizon.emergency_buffer)}</strong></div><div><span>เงินส่วนที่พร้อมออม</span><strong>฿{money(horizon.savings_capacity)}</strong></div></div><button className="text-link" onClick={() => openTab('savings')}>จัดการเงินออม <ArrowRight size={15} /></button></section></div>
      {horizon.commitment_at_risk && <div className="liquidity-warning"><ShieldAlert size={21} /><div><strong>เตรียมสภาพคล่องก่อนถึงรอบเงินเดือน</strong><p>คาดว่าเงินอาจขาดประมาณ ฿{money(horizon.deficit_amount)} ลองดึงเงินออมคืนแล้วดูการคาดการณ์ที่เปลี่ยนไป</p></div><button onClick={() => openTab('savings')}>จัดการเงินออม <ArrowRight size={15} /></button></div>}
      <InsightsLab {...{ profile, busy, refresh }} /><div className="account-tools"><span><ShieldCheck size={15} /> ข้อมูลของโปรไฟล์ทดลองนี้</span><button className="reset-button" onClick={doReset} disabled={busy}><RotateCcw size={15} /> รีเซ็ตบัญชีทดลอง</button></div>
    </div>
  );
}
