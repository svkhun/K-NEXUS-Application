import React, { useEffect, useRef, useState } from 'react';
import { ArrowDownLeft, ArrowLeftRight, ArrowRight, BarChart3, ChevronLeft, ChevronRight, CircleUserRound, CreditCard, EyeOff, Landmark, PiggyBank, Settings2, ShieldCheck, Target, Wallet } from 'lucide-react';

const money = (value) => Number(value ?? 0).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function BankWordmark() {
  return <span className="bank-wordmark" role="img" aria-label="K NEXUS"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M9 8v32M12 25 29 8M12 25l17 15" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="square"/><path d="m28 19 10-9v28L28 28" fill="none" stroke="#8bd885" strokeWidth="4" strokeLinejoin="round"/></svg><span>NEXUS</span></span>;
}

export function FinancialTabs({ active, openTab }) {
  return <nav className="financial-tabs" aria-label="ส่วนการเงินของฉัน">{[['plan', 'แผนใช้เงิน'], ['accounts', 'แนวโน้มเงิน'], ['savings', 'เงินออม']].map(([id, label]) => <button key={id} aria-current={active === id ? 'page' : undefined} onClick={() => openTab(id)}>{label}</button>)}</nav>;
}

export function BankCardArt() {
  return <svg className="bank-card-art" viewBox="0 0 420 220" preserveAspectRatio="none" aria-hidden="true"><path fill="#5fc6c5" d="M0 0h420v220H0z"/><path fill="#259b9a" d="m0 0 170 0 155 220H0z"/><path fill="#9bddda" d="m170 0 250 0-90 220H315z"/><path fill="#ce6c69" d="m170 0 75 0 58 82-44 55z"/><path fill="#c7efea" opacity=".35" d="m0 220 125-143 100 143z"/></svg>;
}

export function MoneyJourneyArt() {
  return <svg className="money-journey-art" viewBox="0 0 190 155" aria-hidden="true"><circle cx="108" cy="80" r="67" fill="#d1ebe0"/><path d="m26 113 44-40 37 16 53-60" fill="none" stroke="#4eb9b4" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round"/><path d="m139 30 24-4-3 25" fill="none" stroke="#4eb9b4" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round"/><rect x="18" y="86" width="80" height="52" rx="8" fill="#185854" transform="rotate(-12 58 112)"/><rect x="27" y="98" width="25" height="7" rx="3" fill="#96e6da" transform="rotate(-12 40 100)"/><circle cx="135" cy="108" r="28" fill="#e8ca67" stroke="#fff5ce" strokeWidth="4"/><text x="135" y="119" textAnchor="middle" fontSize="34" fontFamily="sans-serif" fill="#72602b">฿</text><path d="M111 43v14m-7-7h14M42 34v10m-5-5h10" stroke="#7ea57b" strokeWidth="3" strokeLinecap="round"/></svg>;
}

export function QuickActions({ openTab, onPayBill, onWithdraw, onTransferSettings, expanded = false }) {
  const actions = [
    ['โอนเงิน', ArrowLeftRight, () => openTab('transfer')],
    ['จ่ายบิล', CreditCard, onPayBill],
    ['ออมเงิน', PiggyBank, () => openTab('savings')],
    [expanded ? 'ถอนเงินออม' : 'การเงินของฉัน', expanded ? ArrowDownLeft : BarChart3, expanded ? onWithdraw : () => openTab('accounts')],
    ...(expanded ? [['บัญชีของฉัน', Wallet, () => openTab('accounts')], ['แผนใช้เงิน', Target, () => openTab('plan')], ['แนวโน้มเงิน', BarChart3, () => openTab('accounts')], ['ตั้งค่าการโอน', Settings2, onTransferSettings]] : []),
  ];
  const tones = { 'โอนเงิน': 'mint', 'จ่ายบิล': 'coral', 'ออมเงิน': 'lime', 'ถอนเงินออม': 'gold', 'การเงินของฉัน': 'blue', 'บัญชีของฉัน': 'mint', 'แผนใช้เงิน': 'gold', 'แนวโน้มเงิน': 'blue', 'ตั้งค่าการโอน': 'coral' };
  return <div className="kplus-quick-actions" aria-label="ธุรกรรมด่วน">{actions.map(([label, Icon, action]) => <button key={label} data-tone={tones[label]} onClick={action}><span><Icon size={25} strokeWidth={1.6}/></span><strong>{label}</strong></button>)}</div>;
}

export function TransactionsHub({ profile, horizon, openTab, onPayBill, onWithdraw, onTransferSettings }) {
  const [accountIndex, setAccountIndex] = useState(0);
  const track = useRef(null);
  const selectedIndex = useRef(0);
  const selectAccount = (index) => {
    const next = Math.max(0, Math.min(1, index));
    track.current?.scrollTo({ left: next * track.current.clientWidth, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
  };
  useEffect(() => {
    const element = track.current;
    const observer = new ResizeObserver(() => element.scrollTo({ left: selectedIndex.current * element.clientWidth, behavior: 'instant' }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return <div className="transactions-hub">
    <div className="account-category-tabs" role="group" aria-label="เลือกบัญชี"><button aria-pressed={accountIndex === 0} aria-controls="transaction-accounts" onClick={() => selectAccount(0)}>บัญชีหลัก</button><button aria-pressed={accountIndex === 1} aria-controls="transaction-accounts" onClick={() => selectAccount(1)}>บัญชีเงินออม</button></div>
    <section className="account-carousel" aria-label="บัญชีของฉัน" aria-roledescription="แถบเลื่อนบัญชี">
      <div id="transaction-accounts" className="account-carousel-track" ref={track} tabIndex={0} aria-label="ปัดซ้ายหรือขวาเพื่อเปลี่ยนบัญชี หรือใช้ปุ่มลูกศรบนแป้นพิมพ์" onScroll={(event) => {
        const element = event.currentTarget;
        const next = Math.max(0, Math.min(1, Math.round(element.scrollLeft / element.clientWidth)));
        selectedIndex.current = next;
        setAccountIndex(next);
      }} onKeyDown={(event) => {
        if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          selectAccount(event.key === 'Home' ? 0 : event.key === 'End' ? 1 : accountIndex + (event.key === 'ArrowRight' ? 1 : -1));
        }
      }}>
        {[false, true].map((savings, index) => <div key={index} className="account-slide" role="group" aria-label={`${index + 1} จาก 2 · ${savings ? 'บัญชีเงินออม' : 'บัญชีหลัก'}`}><button className={`kplus-account-card ${savings ? 'vault-card' : ''}`} tabIndex={accountIndex === index ? 0 : -1} onClick={() => openTab(savings ? 'savings' : 'accounts')} aria-label={savings ? 'ดูบัญชีเงินออม' : 'ดูบัญชีหลัก'}><BankCardArt/><div className="kplus-account-name"><span>{savings ? 'บัญชีเงินออม' : 'ออมทรัพย์ · บัญชีหลัก'}<small>{savings ? 'เลือกออมเอง ถอนเมื่อจำเป็น' : profile.masked_account_id}</small></span><CreditCard size={22}/></div><div className="kplus-account-balance"><span>{savings ? 'ยอดเงินออม' : 'ยอดเงินที่ใช้ได้'}</span><strong>฿{money(savings ? profile.vault_balance : profile.main_balance)}</strong><span className="account-card-link">ดูรายการและจัดการบัญชี <ChevronRight size={17}/></span></div></button></div>)}
      </div>
      <div className="account-carousel-controls"><button className="icon-button" aria-label="บัญชีก่อนหน้า" disabled={accountIndex === 0} onClick={() => selectAccount(0)}><ChevronLeft size={19}/></button><div className="account-pager" role="group" aria-label="หน้าบัญชี">{['บัญชีหลัก', 'บัญชีเงินออม'].map((label, index) => <button key={label} aria-label={`แสดง${label}`} aria-pressed={accountIndex === index} onClick={() => selectAccount(index)}><i/></button>)}</div><button className="icon-button" aria-label="บัญชีถัดไป" disabled={accountIndex === 1} onClick={() => selectAccount(1)}><ChevronRight size={19}/></button></div>
      <p className="account-swipe-hint" aria-live="polite">{accountIndex === 0 ? 'บัญชีหลัก' : 'บัญชีเงินออม'} · {accountIndex + 1}/2 <span>ปัดซ้าย–ขวาเพื่อดูอีกบัญชี</span></p>
    </section>
    <QuickActions {...{openTab, onPayBill, onWithdraw, onTransferSettings}} expanded/>
    <button className="inline-discovery" onClick={() => openTab('plan')}><span className="discovery-icon"><Target size={25}/></span><span><small>การเงินของฉัน · FlowSense</small><strong>ดูเงินที่ใช้ได้จริง ถึงวันเงินเดือนออก</strong><em>วันนี้ใช้เพิ่มได้อีก ฿{money(horizon.remaining_today)}</em></span><ChevronRight size={20}/></button>
    <div className="bank-service-links"><button onClick={() => openTab('transfer')}><ShieldCheck size={22}/><span>ดูแลก่อนโอน<small>ตรวจผู้รับ พร้อมเห็นเงินที่เหลือ</small></span><ChevronRight size={18}/></button><button onClick={() => openTab('profile')}><CircleUserRound size={22}/><span>โปรไฟล์และการตั้งค่า<small>จัดการข้อมูลทดลองของคุณ</small></span><ChevronRight size={18}/></button></div>
  </div>;
}

export function ProfilePage({ persona, profile, openTab, onTransferSettings, doReset, busy, setHidden }) {
  return <div className="bank-profile">
    <div className="profile-identity"><span><CircleUserRound size={48} strokeWidth={1.3}/></span><div><h2>คุณ{persona.name}</h2><p>{persona.role} · โปรไฟล์จำลอง</p></div></div>
    <div className="profile-shortcuts"><button onClick={() => openTab('accounts')}><BarChart3 size={27}/><span>การเงินของฉัน</span></button><button onClick={() => openTab('plan')}><Target size={27}/><span>แผนใช้เงิน</span></button><button onClick={() => openTab('savings')}><PiggyBank size={27}/><span>เงินออม</span></button></div>
    <h3 className="bank-section-label">ดูแลเงินในแบบของคุณ</h3>
    <div className="bank-setting-list"><button onClick={onTransferSettings}><ShieldCheck size={22}/><span>ตรวจสอบก่อนโอน<small>{profile.transfer_cooldown_enabled ? 'เปิดพักรายการเสี่ยง 15 นาที' : 'ปิดเวลาพักเสริมไว้'}</small></span><ChevronRight size={18}/></button><button onClick={() => openTab('savings')}><Wallet size={22}/><span>การแยกเงินออม<small>{profile.savings_enabled ? 'เปิดอยู่ · เลือกออมเองทุกครั้ง' : 'ปิดอยู่ · เปิดได้เมื่อคุณพร้อม'}</small></span><ChevronRight size={18}/></button><button onClick={() => setHidden(true)}><EyeOff size={22}/><span>ซ่อนข้อมูลการเงิน<small>ซ่อนยอดเงิน กราฟ และรายการบนหน้าจอ</small></span><ChevronRight size={18}/></button><button onClick={() => openTab('accounts')}><Landmark size={22}/><span>บัญชีและภาระที่ต้องจ่าย<small>ดูบิล เงินสำรอง และแนวโน้มเงิน</small></span><ChevronRight size={18}/></button></div>
    <div className="profile-prototype-note"><strong>K-NEXUS · ต้นแบบฟีเจอร์สำหรับประสบการณ์ K+</strong><p>FlowSense × TrustGraph · ข้อมูลสมมติทั้งหมด<br/>ไม่ใช่บริการทางการของธนาคาร ไม่มีการโอนเงินจริง</p><button className="text-link" disabled={busy} onClick={doReset}>รีเซ็ตบัญชีทดลอง <ArrowRight size={15}/></button></div>
  </div>;
}
