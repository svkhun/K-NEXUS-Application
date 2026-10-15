import React from 'react';
import InsightsLab from './InsightsLab';
import { AccountGarden, SavingsBloom } from './FinanceDecor';
import { ScenarioPicker } from './SavingsPage';
import {
  Activity, ArrowDownLeft, ArrowRight, BadgeCheck,
  Bell, ChevronRight, Clock3, CreditCard, Eye, EyeOff,
  Home, LockKeyhole, RotateCcw, Send, ShieldAlert, ShieldCheck,
  Sparkles, TrendingUp, Wallet,
} from 'lucide-react';

const money = (value, digits = 0) => new Intl.NumberFormat('th-TH', {
  minimumFractionDigits: digits, maximumFractionDigits: digits,
}).format(Number(value ?? 0));

function PhonePreview({ dailyLimit }) {
  return (
    <div className="phone-scene" aria-hidden="true">
      <div className="scene-orbit orbit-one" /><div className="scene-orbit orbit-two" />
      <span className="scene-leaf leaf-one" /><span className="scene-leaf leaf-two" /><span className="scene-leaf leaf-three" />
      <div className="concept-phone">
        <div className="phone-speaker" />
        <div className="phone-brand">K<small>เงินออม</small></div>
        <div className="phone-greeting">เงินที่ใช้ได้วันนี้</div>
        <strong className="phone-amount">฿{money(dailyLimit)}</strong>
        <div className="phone-status"><span /> พร้อมสำหรับทุกวัน</div>
        <div className="phone-chart"><svg viewBox="0 0 140 50"><path d="M0 43 L17 38 L35 40 L53 27 L70 31 L87 17 L106 20 L125 8 L140 12" fill="none" stroke="#099c72" strokeWidth="3" strokeLinecap="round" /></svg></div>
        <div className="phone-vault"><Wallet size={14} /><span>กระเป๋าเงินออม</span><ArrowRight size={12} /></div>
        <div className="phone-bottom"><Home size={13} /><Send size={13} /><Wallet size={13} /></div>
      </div>
      <div className="floating-insight"><span><ShieldCheck size={17} /></span><div><strong>TrustGraph</strong><small>ตรวจความเสี่ยงก่อนโอน</small></div></div>
      <span className="scene-spark">✦</span>
    </div>
  );
}

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
        <div className="account-tile-top"><span className="account-emblem"><ShieldCheck size={16} /></span><div><strong>TrustGraph</strong><small>ผู้ช่วยตรวจความเสี่ยงก่อนโอน</small></div><span className="protection-dot" /></div>
        <AccountGarden /><b>พร้อมดูแลทุกการโอน</b><button className="protection-link" onClick={() => openTab('transfer')}>ทดลองใช้งาน <ArrowRight size={14} /></button>
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
      <div className="surface-heading"><div><h2>รายการทดลองล่าสุด</h2><p className="heading-description">ติดตามสิ่งที่คุณเพิ่งลองใช้งาน</p></div><Clock3 size={18} color="#90a19d" /></div>
      {activities.length ? <div className="activity-list">{activities.map(({ title, description, icon: Icon, time }, index) => (
        <div key={index} className="activity-row"><span className="activity-icon"><Icon size={17} /></span><div><strong>{title}</strong><small>{description}</small></div><time>{time}</time></div>
      ))}</div> : <div className="activity-starter"><p>เริ่มทดลอง แล้วรายการของคุณจะแสดงที่นี่</p><button onClick={() => openTab('savings')}><span className="starter-icon mint"><Wallet size={18} /></span><span><strong>เริ่มออมตามจังหวะของคุณ</strong><small>ลองออม ดึงคืน และดูสภาพคล่อง</small></span><ArrowRight size={16} /></button><button onClick={() => openTab('transfer')}><span className="starter-icon lilac"><ShieldCheck size={18} /></span><span><strong>ลองโอนอย่างเข้าใจความเสี่ยง</strong><small>เห็นเหตุผลก่อนตัดสินใจ</small></span><ArrowRight size={16} /></button></div>}
    </section>
  );
}

export function ForecastPanel({ horizon, chart }) {
  return (
    <section className="surface forecast-card">
      <div className="surface-heading timeline-heading"><div className="timeline-heading-copy"><span className="timeline-title-icon"><TrendingUp size={23} /></span><div><span className="section-kicker">YOUR MONEY TIMELINE</span><h2>เห็นเส้นทางเงิน ก่อนถึงวันข้างหน้า</h2><p className="heading-description">ย้อนหลัง 7 วัน เชื่อมวันนี้ สู่แผนการเงินอีก 30 วัน</p></div></div><span className={`runway-badge ${horizon.commitment_at_risk ? 'is-risk' : ''}`}><ShieldCheck size={15} />{horizon.commitment_at_risk ? 'ควรเตรียมสภาพคล่อง' : 'ภาระก่อนเงินเดือนมีเงินรองรับ'}</span></div>
      {chart}
    </section>
  );
}

export default function Dashboard({ profile, horizon, activities, chart, hidden, setHidden, busy, doRecall, openTab, tryScenario }) {
  const total = Number(profile.main_balance) + Number(profile.vault_balance);
  return (
    <div className="bank-dashboard">
      <div className="welcome-grid">
        <section className="surface total-balance">
          <div className="total-balance-top"><div><span>ยอดเงินรวมทุกบัญชี</span><div className="total-amount">{hidden ? '••••••••' : `฿ ${money(total, 2)}`}<button className="icon-button balance-eye" aria-label={hidden ? 'แสดงยอดเงิน' : 'ซ่อนยอดเงิน'} onClick={() => setHidden(!hidden)}>{hidden ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></div><button className="text-link" onClick={() => openTab('accounts')}>ดูรายละเอียด <ChevronRight size={14} /></button></div>
          <div className="bank-quick-actions">
            <button onClick={() => openTab('transfer')}><span className="bank-action-icon action-primary"><Send size={21} /></span><strong>โอนเงิน</strong></button>
            <button onClick={() => openTab('savings')}><span className="bank-action-icon"><ArrowDownLeft size={21} /></span><strong>ออมเงิน</strong></button>
            <button onClick={() => doRecall('all')} disabled={busy || profile.vault_balance <= 0}><span className="bank-action-icon"><RotateCcw size={21} /></span><strong>ดึงเงินคืน</strong></button>
            <button onClick={() => openTab('accounts')}><span className="bank-action-icon"><TrendingUp size={21} /></span><strong>ดูเงินข้างหน้า</strong></button>
          </div>
        </section>
        <section className="flowsense-banner">
          <div className="banner-copy"><span className="banner-label"><Sparkles size={13} /> การออมเงิน</span><h2>เงินวันนี้<br />พร้อมสำหรับวันข้างหน้า</h2><p>รู้ว่าใช้ได้เท่าไร ออมได้เท่าไหน<br />ให้ผู้ช่วยการเงินดูแลไปกับคุณ</p><button onClick={() => openTab('savings')}>เริ่มออมเงิน <ArrowRight size={15} /></button></div>
          <PhonePreview dailyLimit={horizon.daily_safe_limit} />
        </section>
      </div>

      <div className="section-title-row"><h2>บัญชีของฉัน</h2><button className="text-link" onClick={() => openTab('accounts')}>ดูทั้งหมด <ChevronRight size={14} /></button></div>
      <AccountTiles profile={profile} openTab={openTab} hidden={hidden} />

      <div className="dashboard-timeline"><ForecastPanel horizon={horizon} chart={chart} /></div>

      <div className="section-title-row assistant-title"><div><h2>ผู้ช่วยการเงินสำหรับคุณ</h2><p>สองฟังก์ชันใหม่ที่อยากให้คุณลอง</p></div><span className="new-feature-tag">NEW EXPERIENCE</span></div>
      <div className="assistant-grid">
        <section className="surface flowsense-assistant">
          <div className="assistant-heading"><span className="assistant-icon"><Activity size={22} /></span><div><span>ผู้ช่วยการออมเงิน</span><h3>ใช้จ่ายได้แค่ไหน สบายใจได้เท่าไร</h3></div><span className={`status-pill ${horizon.commitment_at_risk ? 'risk' : 'safe'}`}><span />{horizon.horizon_badge_th}</span></div>
          <div className="flowsense-amount-row"><div><span>ใช้ได้ต่อวันโดยประมาณ</span><strong>฿ {money(horizon.daily_safe_limit)}</strong></div><div className="payday-note"><Clock3 size={14} /><span>อีก {horizon.days_to_payday} วัน<br />ถึงรอบเงินเดือน</span></div></div>
          <div className="health-meter"><div><span>ระดับสภาพคล่อง</span><strong>{money(horizon.horizon_health_pct)}%</strong></div><div className="meter-track"><i style={{ width: `${horizon.horizon_health_pct}%` }} /></div></div>
          <p className="assistant-description">{horizon.nudge_message}</p>
          <div className="assistant-actions"><button className="primary-button" onClick={() => openTab('savings')}><Wallet size={16} /> ทดลองออมและดึงคืน</button><button className="text-link" onClick={() => openTab('accounts')}>ดูแนวโน้ม <ArrowRight size={14} /></button></div>
        </section>
        <section className="surface trustgraph-assistant">
          <div className="assistant-heading"><span className="assistant-icon shield-icon"><ShieldCheck size={23} /></span><div><span>TrustGraph</span><h3>รู้ความเสี่ยง ก่อนเงินออกจากบัญชี</h3></div></div>
          <p className="trustgraph-description">ลองโอนใน 3 สถานการณ์ แล้วดูว่าระบบช่วยคุณตัดสินใจอย่างไร</p>
          <div className="scenario-shortcuts"><button onClick={() => tryScenario(0)}><span className="scenario-icon green"><BadgeCheck size={18} /></span><span><strong>รายการปกติ</strong><small>ผ่านได้โดยไม่มีขั้นตอนเพิ่ม</small></span><ChevronRight size={15} /></button><button onClick={() => tryScenario(1)}><span className="scenario-icon orange"><ShieldAlert size={18} /></span><span><strong>มีสัญญาณเสี่ยง</strong><small>เห็นเหตุผลก่อนตัดสินใจ</small></span><ChevronRight size={15} /></button><button onClick={() => tryScenario(2)}><span className="scenario-icon red"><LockKeyhole size={18} /></span><span><strong>บัญชีที่ถูกระงับ</strong><small>หยุดรายการเพื่อดูแลเงินคุณ</small></span><ChevronRight size={15} /></button></div>
        </section>
      </div>

      <div className="dashboard-bottom-grid"><ActivityList activities={activities} openTab={openTab} /><section className="surface journey-card"><div className="journey-copy"><span className="section-kicker">SMALL STEPS, BETTER FLOW</span><h2>ออมทีละนิด<br />พร้อมใช้ในทุกจังหวะ</h2><p>ลองให้ FlowSense ช่วยกันเงิน แล้วดูว่าเงินวันนี้ดูแลวันข้างหน้าได้อย่างไร</p><button className="primary-button" onClick={() => openTab('savings')}>เริ่มแผนเงินของคุณ <ArrowRight size={16} /></button></div><SavingsBloom /></section></div>
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
