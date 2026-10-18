import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, BadgeCheck,
  Bell, Check, ChevronDown, CircleAlert, CreditCard, Fingerprint,
  Home, LockKeyhole, RotateCcw, Send, ShieldAlert, ShieldCheck,
  Sparkles, Wallet, X, Search, ChevronRight, Target, Eye, EyeOff, UserRound, BarChart3,
} from 'lucide-react';
import { api } from './api';
import Dashboard, { AccountsPage } from './Dashboard';
import TransferForm from './TransferForm';
import ForecastChart from './ForecastChart';
import SavingsPage from './SavingsPage';
import TransferResult from './TransferResult';
import { describeEvent } from './InsightsLab';
import { bangkokDate } from './forecastModel.mjs';
import DailyPlan from './DailyPlan';
import TransferProtectionSettings from './TransferProtectionSettings';
import TransferReviewDialog from './TransferReviewDialog';
import { BankWordmark, TransactionsHub, ProfilePage, FinancialTabs } from './KBankSurfaces';
import TutorialOverlay, { tutorialSteps, tutorialWasSeen, rememberTutorial } from './TutorialOverlay';

const personas = [
  { id: 'ACC_0100', name: 'เมย์', role: 'วัยเริ่มทำงาน', initials: 'ม', color: 'mint' },
  { id: 'ACC_0101', name: 'นนท์', role: 'ค่าใช้จ่ายหลายทาง', initials: 'น', color: 'peach' },
  { id: 'ACC_0150', name: 'แพรว', role: 'เน้นสร้างเงินสำรอง', initials: 'พ', color: 'lilac' },
];
const recipientTemplates = [
  { id: 'ACC_0101', name: 'บัญชีที่คุ้นเคย', meta: 'ทดลองโอนรายการปกติ', icon: BadgeCheck, tone: 'green', amount: 350 },
  { id: 'ACC_0001', name: 'บัญชีที่ควรตรวจเพิ่ม', meta: 'ทดลองเห็นคำเตือนความเสี่ยง', icon: ShieldAlert, tone: 'orange', amount: 1200 },
  { id: 'ACC_0000', name: 'บัญชีที่ถูกระงับ', meta: 'ทดลองกรณีหยุดรายการ', icon: LockKeyhole, tone: 'red', amount: 1200 },
];
const money = (value, digits = 0) => new Intl.NumberFormat('th-TH', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value ?? 0));
const isPendingTransfer = (result) => ['MICRO_AUTH_REQUIRED', 'TRANSFER_REVIEW', 'REVIEW_CHANGED'].includes(result?.status);
const navItems = [
  { id: 'home', label: 'หน้าหลัก', icon: Home },
  { id: 'plan', label: 'การเงิน', icon: BarChart3 },
  { id: 'transactions', label: 'ธุรกรรม', icon: CreditCard },
  { id: 'savings', label: 'ออมเงิน', icon: Wallet },
  { id: 'profile', label: 'โปรไฟล์', icon: UserRound },
];
const serviceItems = [...navItems, { id: 'accounts', label: 'บัญชีและแนวโน้มเงิน', icon: CreditCard }, { id: 'transfer', label: 'โอน / จ่าย', icon: Send }];

function App() {
  const [tab, setTab] = useState('home');
  const [hidden, setHidden] = useState(false);
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [scanning, setScanning] = useState(0);
  const [telemetry, setTelemetry] = useState({ device: false, first: false, duration: 90, ratio: 1.1, auth: 'pin' });
  const [showAlerts, setShowAlerts] = useState(false);
  const [accountId, setAccountId] = useState(personas[0].id);
  const recipients = useMemo(() => recipientTemplates.map((item, index) => index === 0 ? { ...item, id: accountId === 'ACC_0101' ? 'ACC_0100' : 'ACC_0101' } : item), [accountId]);
  const [profile, setProfile] = useState(null);
  const [horizon, setHorizon] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [tutorialStep, setTutorialStep] = useState(null);
  const tutorialOffered = useRef(false);
  const [sweepAmount, setSweepAmount] = useState('200');
  const [recipient, setRecipient] = useState(recipientTemplates[0]);
  const [amount, setAmount] = useState('350');
  const [matchedBillId, setMatchedBillId] = useState('');
  const [transferPurpose, setTransferPurpose] = useState('general');
  const [transferResult, setTransferResult] = useState(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [focusSettings, setFocusSettings] = useState(false);
  const [clearanceToken, setClearanceToken] = useState(null);
  const inFlight = useRef(false);
  const activeAccount = useRef(accountId);
  useEffect(() => {
    if (!reviewOpen && focusSettings) {
      const control = document.getElementById('transfer-cooldown-toggle');
      control?.focus({ preventScroll: true });
      control?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setFocusSettings(false);
    }
  }, [reviewOpen, focusSettings]);
  const persona = useMemo(() => personas.find((item) => item.id === accountId) ?? personas[0], [accountId]);

  const refresh = useCallback(async (id = accountId) => {
    const [nextProfile, nextHorizon, nextForecast] = await Promise.all([api.profile(id), api.horizon(id), api.forecast(id)]);
    if (activeAccount.current !== id) return;
    setProfile(nextProfile);
    setHorizon(nextHorizon);
    setForecast(nextForecast);
  }, [accountId]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    Promise.all([api.profile(accountId), api.horizon(accountId), api.forecast(accountId), api.pendingTransfer(accountId)])
      .then(([nextProfile, nextHorizon, nextForecast, review]) => {
        if (!active) return;
        setProfile(nextProfile); setHorizon(nextHorizon); setForecast(nextForecast);
        if (review.pending) {
          const pending = review.pending;
          const target = recipientTemplates.find((item) => item.id === pending.target_account_id) || { ...recipientTemplates[0], id: pending.target_account_id };
          setRecipient(target); setAmount(String(pending.amount)); setClearanceToken(null); setTransferResult(pending);
          setMatchedBillId(pending.matched_bill_id || ''); setTransferPurpose(pending.transfer_purpose || 'general');
        }
      })
      .catch((err) => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accountId]);

  useEffect(() => {
    const refreshOnNewDay = async () => {
      if (loading || !horizon || inFlight.current || document.visibilityState === 'hidden' || horizon.as_of_date === bangkokDate(new Date())) return;
      inFlight.current = true;
      try { await refresh(); } catch (err) { setError(err.message); }
      finally { inFlight.current = false; }
    };
    const timer = setInterval(refreshOnNewDay, 30000);
    window.addEventListener('focus', refreshOnNewDay);
    document.addEventListener('visibilitychange', refreshOnNewDay);
    return () => {
      clearInterval(timer);
      window.removeEventListener('focus', refreshOnNewDay);
      document.removeEventListener('visibilitychange', refreshOnNewDay);
    };
  }, [horizon, loading, refresh]);

  const run = async (action) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(err.message); }
    finally { inFlight.current = false; setBusy(false); }
  };
  const changePersona = (id) => {
    setTutorialStep(null);
    activeAccount.current = id;
    setAccountId(id); setTransferResult(null); setClearanceToken(null); setReviewOpen(false);
    setRecipient({ ...recipientTemplates[0], id: id === 'ACC_0101' ? 'ACC_0100' : 'ACC_0101' });
    setAmount('350'); setTelemetry({ device: false, first: false, duration: 90, ratio: 1.1, auth: 'pin' });
    setMatchedBillId(''); setTransferPurpose('general');
    setError(''); setNotice('');
  };
  const doSweep = () => run(async () => {
    const value = Number(sweepAmount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินออมที่มากกว่า 0 บาท');
    if (Math.abs(value * 100 - Math.round(value * 100)) > 1e-7) throw new Error('ระบุจำนวนเงินไม่เกินทศนิยม 2 ตำแหน่ง');
    const result = await api.sweep(accountId, value);
    await refresh();
    setNotice(`แยกเงินออม ฿${money(result.swept_amount, 2)} แล้ว`);
  });
  const doRecommendedSweep = () => run(async () => {
    const result = await api.sweep(accountId);
    await refresh();
    setNotice(`แยกเงินออมตามคำแนะนำ ฿${money(result.swept_amount, 2)} แล้ว`);
  });
  const doWithdraw = (value) => run(async () => {
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินที่ต้องการถอน');
    if (Math.abs(value * 100 - Math.round(value * 100)) > 1e-7) throw new Error('ระบุจำนวนเงินไม่เกินทศนิยม 2 ตำแหน่ง');
    const result = await api.withdraw(accountId, value);
    await refresh();
    setNotice(`ถอนเงินออม ฿${money(result.withdrawn_amount, 2)} เข้าบัญชีหลักแล้ว`);
  });
  const onScenario = (scenario) => run(async () => { await api.scenario(accountId, scenario); setMatchedBillId(''); setTransferPurpose('general'); await refresh(); setTransferResult(null); setClearanceToken(null); setReviewOpen(false); setNotice('เปลี่ยนสถานการณ์จำลองแล้ว ลองดูคำแนะนำและกราฟที่เปลี่ยนไป'); });
  const prepareHighValue = () => run(async () => { await api.scenario(accountId, 'high_value'); await refresh(); changeRecipient(recipients[0]); setAmount('50000'); setNotice('เตรียมยอดบัญชีสมมติ ฿60,000 สำหรับทดลองการตรวจรายการมูลค่าสูงแล้ว'); });
  const onSavingsToggle = (enabled) => run(async () => { await api.savingsPreference(accountId, enabled); await refresh(); setNotice(enabled ? 'เปิดการแยกเงินออมแล้ว เลือกจำนวนแล้วกดออมเมื่อพร้อม' : 'ปิดการแยกเงินออมแล้ว ยังถอนเงินออมที่มีอยู่ได้ตามปกติ'); });
  const onReservePreview = (value) => api.reservePreview(accountId, value);
  const onReserveSave = (value) => run(async () => {
    await api.reservePreference(accountId, value);
    await refresh();
    setNotice(`ใช้เงินสำรอง ฿${money(value, 2)} ในแผนแล้ว งบใช้จ่ายและยอดพร้อมออมคำนวณใหม่ โดยยอดบัญชีไม่เปลี่ยน`);
  });
  const doReset = () => run(async () => {
    await api.reset(accountId); setMatchedBillId(''); setTransferPurpose('general');
    setTutorialStep(null);
    await refresh();
    setTransferResult(null); setClearanceToken(null); setReviewOpen(false);
    setNotice('รีเซ็ตข้อมูลของบัญชีจำลองแล้ว');
  });
  const transferPayload = () => ({
    source_account_id: accountId,
    target_account_id: recipient.id,
    amount: Number(amount),
    is_first_time_transfer: telemetry.first ? 1 : 0,
    device_switch_last_24h: telemetry.device ? 1 : 0,
    session_duration_sec: Number(telemetry.duration),
    ratio_to_daily_avg: Number(telemetry.ratio),
    auth_factor_used: telemetry.auth,
    scenario_mode: recipient.id === 'ACC_0000' ? 'blocked' : 'auto',
    matched_bill_id: matchedBillId || null,
    transfer_purpose: transferPurpose,
  });
  const evaluate = () => run(async () => {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินที่จะโอน');
    if (value > Number(profile?.main_balance)) throw new Error('ยอดเงินในบัญชีหลักไม่เพียงพอ');
    setTransferResult(null); setClearanceToken(null); setReviewOpen(false);
    const result = await api.evaluate(transferPayload());
    setTransferResult(result); setReviewOpen(true);
    await refresh();
  });
  const verify = () => run(async () => {
    try { for (let seconds = 5; seconds > 0; seconds--) { setScanning(seconds); await new Promise((resolve) => setTimeout(resolve, 1000)); } } finally { setScanning(0); }
    const result = await api.verify({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount) });
    setClearanceToken(result.clearance_token);
    setTransferResult((current) => ({ ...current, ...result.cooldown, clearance_expires_at: result.clearance_expires_at }));
    setNotice('จำลองการยืนยันตัวตนสำเร็จ กรุณาตัดสินใจว่าจะโอนต่อหรือยกเลิก');
  });
  const onTransferPreference = (enabled) => run(async () => {
    await api.transferPreference(accountId, enabled); await refresh();
    setNotice(enabled ? 'เปิดพักก่อนโอนรายการเสี่ยง 15 นาทีแล้ว' : isPendingTransfer(transferResult) ? 'ปิดสำหรับรายการใหม่แล้ว หากต้องการใช้ค่านี้ ให้ยกเลิกรายการเดิมแล้วเริ่มใหม่' : 'ปิดเวลาพักเสริมแล้ว รายการเสี่ยงใหม่ยังตรวจความเสี่ยงและยืนยันจำลองตามปกติ');
  });
  const checkCooldown = async () => {
    if (inFlight.current) return;
    try {
      const { pending } = await api.pendingTransfer(accountId);
      if (activeAccount.current !== accountId) return;
      setTransferResult((current) => {
        if (!isPendingTransfer(current)) return current;
        if (!pending || pending.target_account_id !== recipient.id || Number(pending.amount) !== Number(amount)) return { status: 'REVIEW_EXPIRED' };
        return { ...current, ...pending };
      });
    } catch (err) { setError(err.message); }
  };
  const decide = (decision) => run(async () => {
    let result;
    try {
      result = await api.confirm({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount), decision, auth_token: decision === 'PROCEED' ? clearanceToken : undefined, review_token: decision === 'PROCEED' ? transferResult?.review_token : undefined });
    } catch (err) {
      if (err.code === 'PLAN_CHANGED') { setClearanceToken(null); setTransferResult((current) => ({ ...current, plan_changed: true })); }
      throw err;
    }
    setTransferResult(result); setClearanceToken(null); setReviewOpen(true);
    if (result.status === 'TRANSFER_EXECUTED') setMatchedBillId('');
    await refresh();
    if (decision === 'CANCEL') setNotice('ยกเลิกรายการและเวลาพักเดิมแล้ว รายการใหม่จะใช้ค่าตั้งค่าปัจจุบัน');
  });
  const showTransferReview = () => { setTab('transfer'); setReviewOpen(true); checkCooldown(); };
  const editTransferSettings = () => { setReviewOpen(false); setFocusSettings(true); };
  const clearTransferResult = () => { setTransferResult(null); setClearanceToken(null); setReviewOpen(false); };
  const changeRecipient = (item) => {
    setTelemetry({ device: false, first: item.tone !== 'green', duration: item.tone === 'green' ? 90 : 8, ratio: item.tone === 'green' ? 1.1 : 8, auth: 'pin' });
    setRecipient(item); setAmount(String(item.amount)); setTransferResult(null); setClearanceToken(null); setReviewOpen(false); setError(''); setNotice('');
    setMatchedBillId(''); setTransferPurpose('general');
  };
  const openTab = (id) => {
    setTab(id); setError(''); setNotice(''); setSearch(''); setShowAlerts(false); setSearchOpen(false);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };
  const onPayBill = () => {
    const bill = horizon?.recurring_commitments?.find((row) => row.amount > 0 && row.due_days < horizon.days_to_payday);
    changeRecipient(recipients[0]);
    if (bill) { setMatchedBillId(bill.id); setAmount(String(bill.amount)); }
    openTab(bill ? 'transfer' : 'accounts');
  };
  const onWithdraw = () => { openTab('savings'); requestAnimationFrame(() => document.getElementById('withdraw-amount')?.focus()); };
  const onTransferSettings = () => { openTab('transfer'); setReviewOpen(false); setFocusSettings(true); };
  const searchItems = serviceItems.filter((item) => {
    const terms = { home: 'หน้าหลัก ภาพรวม ยอดเงิน', plan: 'แผนใช้เงิน การเงิน งบ วันนี้ รายวัน วันละ ใช้ได้ ควรใช้ คาดการณ์รายจ่าย flowsense สภาพคล่อง', accounts: 'บัญชี สภาพคล่อง คาดการณ์ กราฟ ภาระ', transfer: 'โอน จ่าย trustgraph ความเสี่ยง', savings: 'flowsense การออมเงิน ออมเงิน เงินออม ถอน ถอนเงิน ดึงคืน', transactions: 'ธุรกรรม บริการ', profile: 'โปรไฟล์ ตั้งค่า ซ่อน ข้อมูล' };
    return search.trim() && terms[item.id].includes(search.trim().toLowerCase());
  });
  const tryScenario = (index) => { changeRecipient(recipients[index]); openTab('transfer'); };
  const visitTutorialStep = (index) => {
    const step = tutorialSteps[index];
    setReviewOpen(index === 5);
    if (step.page === 'transfer' && index === 4 && !isPendingTransfer(transferResult)) {
      changeRecipient(recipients[1]);
      setAmount(String(Math.min(1200, Number(profile.main_balance))));
    }
    openTab(step.page);
    setTutorialStep(index);
  };
  const startTutorial = () => { tutorialOffered.current = true; visitTutorialStep(0); };
  const closeTutorial = (status) => {
    rememberTutorial(status); setTutorialStep(null);
    if (status === 'complete') { setReviewOpen(false); openTab('home'); setNotice('ดูวิธีใช้ครบแล้ว ลองตั้งงบ ดูผลก่อนโอน หรือเลือกจัดการเงินออมได้ด้วยตัวเอง'); }
  };
  const nextTutorial = () => {
    if (busy) return;
    if (tutorialStep === tutorialSteps.length - 1) { closeTutorial('complete'); return; }
    if (tutorialStep === 4) {
      if (isPendingTransfer(transferResult)) showTransferReview();
      else if (Number(profile.main_balance) > 0) evaluate();
      else visitTutorialStep(6);
      return;
    }
    visitTutorialStep(tutorialStep + 1);
  };
  useEffect(() => {
    if (loading || !profile || !horizon || tutorialOffered.current) return;
    tutorialOffered.current = true;
    if (!tutorialWasSeen()) { setTab('home'); setTutorialStep(0); }
  }, [loading, profile, horizon]);
  useEffect(() => {
    if (tutorialStep === 4 && reviewOpen && transferResult) setTutorialStep(5);
  }, [tutorialStep, reviewOpen, transferResult]);
  const navSection = ({ accounts: 'plan', transfer: 'transactions' })[tab] || tab;
  const title = { home: `สวัสดี, คุณ${persona.name}`, plan: 'แผนใช้เงินของฉัน', accounts: 'การเงินของฉัน', savings: 'ออมเงิน', transfer: 'โอนเงิน', transactions: 'ธุรกรรม', profile: 'โปรไฟล์' }[tab];
  const description = { home: 'ภาพรวมเงินของคุณวันนี้', plan: 'ลองตั้งงบ ให้เงินพอถึงวันเงินเดือน', accounts: 'ยอดเงิน ภาระ และแนวโน้มวันข้างหน้า', savings: 'ออมเมื่อพร้อม ถอนเงินได้ตามปกติ', transfer: 'เห็นผลต่อแผนเงินและตรวจผู้รับก่อนโอน', transactions: 'บัญชีและบริการที่ใช้บ่อย', profile: 'ดูแลการเงินและตั้งค่าในแบบของคุณ' }[tab];

  useEffect(() => {
    if (transferResult && window.innerWidth <= 640) {
      const frame = requestAnimationFrame(() => document.querySelector('.result-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return () => cancelAnimationFrame(frame);
    }
  }, [transferResult]);

  return (
    <div className={`app-shell kplus-experience page-${tab}`}>
      <aside className="sidebar">
        <div className="bank-brand"><BankWordmark/><small>ต้นแบบฟีเจอร์ · ข้อมูลสมมติ</small></div>
        <nav className="side-nav" aria-label="เมนูหลัก">
          {navItems.map(({ id, label, icon: Icon }) => <button key={id} className={navSection === id ? 'active' : ''} aria-label={label} title={label} aria-current={navSection === id ? 'page' : undefined} onClick={() => openTab(id)}><Icon size={19} strokeWidth={1.6} /><span>{label}</span>{navSection === id && <ChevronRight className="side-chevron" size={14} />}</button>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-feature"><strong>K-NEXUS</strong><p>FlowSense × TrustGraph · ข้อมูลสมมติ</p></div>
        <div className="sidebar-profile"><div className={`avatar ${persona.color}`}>{persona.initials}</div><div><strong>คุณ{persona.name}</strong><small>บัญชีทดลอง</small></div></div>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <button className="header-avatar" aria-label="เปิดโปรไฟล์ของฉัน" onClick={() => openTab('profile')}><UserRound size={23}/></button>
          <div className="mobile-brand"><BankWordmark/><small>ต้นแบบฟีเจอร์</small></div>
          <div className="header-product">K-NEXUS</div>
          <div className="topbar-right">
            <button className="icon-button mobile-search-toggle" aria-label="เปิดช่องค้นหา" aria-expanded={searchOpen} onClick={() => setSearchOpen(!searchOpen)}><Search size={18} /></button><div className={`service-search ${searchOpen ? 'search-open' : ''}`}><Search size={16} /><input aria-label="ค้นหาบริการหรือเมนู" placeholder="ค้นหาบริการหรือเมนู" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && searchItems.length) openTab(searchItems[0].id); if (event.key === 'Escape') setSearch(''); }} />
              {search.trim() && <div className="search-results">{searchItems.length ? searchItems.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => openTab(id)}><Icon size={16} />{label}<ChevronRight size={14} /></button>) : <p>ไม่พบบริการ ลองค้นหา “ออม” หรือ “โอน”</p>}</div>}
            </div>
            <button className="icon-button" aria-label={hidden ? "แสดงข้อมูลการเงิน" : "ซ่อนข้อมูลการเงิน"} aria-pressed={hidden} onClick={() => { setHidden(!hidden); setShowAlerts(false); }}>{hidden ? <EyeOff size={18} /> : <Eye size={18} />}</button><div className="notification-wrap"><button className={`icon-button ${showAlerts ? 'selected' : ''}`} aria-label="ดูการแจ้งเตือน" aria-expanded={showAlerts} onClick={() => setShowAlerts(!showAlerts)}><Bell size={18} />{horizon?.commitment_at_risk && <span className="notification-dot" />}</button>{showAlerts && !hidden && <div className="notification-panel"><strong>ผู้ช่วยแจ้งเตือนของคุณ</strong><p>{horizon?.nudge_message || 'กำลังเตรียมสถานะสภาพคล่อง'}</p><button className="text-link" onClick={() => openTab(horizon?.commitment_at_risk ? 'savings' : 'accounts')}>ดูรายละเอียด <ArrowRight size={14} /></button></div>}</div>
          </div>
        </header>
        <main className="main-content">
          <div className="page-intro"><div><h1>{title}</h1><p>{description}</p></div><details className="demo-context"><summary>บัญชีทดลอง · {persona.name}<ChevronDown size={15} /></summary><div className="demo-context-panel"><label htmlFor="persona">ลองเปลี่ยนโปรไฟล์</label><select id="persona" value={accountId} disabled={busy} onChange={(event) => changePersona(event.target.value)}>{personas.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}</select><p>แอปต้นแบบอิสระ ใช้ข้อมูลสมมติ ไม่ใช่แอปทางการของ KBank</p><button className="text-link" disabled={busy || !profile} onClick={doReset}><RotateCcw size={15} /> รีเซ็ตบัญชีทดลอง</button></div></details></div>

          <div className="demo-disclaimer"><ShieldCheck size={14} /><span>แอปต้นแบบ · ข้อมูลสมมติ · ไม่มีการโอนเงินจริง</span></div>
          {error && !hidden && <div className="message error" role="alert"><CircleAlert size={18} /><span>{error}</span><button aria-label="ปิดข้อความ" onClick={() => setError('')}><X size={16} /></button></div>}
          {notice && !hidden && <div className="message success" role="status"><Check size={18} /><span>{notice}</span><button aria-label="ปิดข้อความ" onClick={() => setNotice('')}><X size={16} /></button></div>}

          {hidden ? <section className="surface privacy-cover"><EyeOff size={32} /><h2>ซ่อนข้อมูลการเงินแล้ว</h2><p>ยอดเงิน กราฟ และรายการต่าง ๆ จะกลับมาเมื่อคุณเลือกแสดงข้อมูล</p><button className="primary-button" onClick={() => setHidden(false)}>แสดงข้อมูลการเงิน <Eye size={17} /></button></section> : loading ? <div className="loading-card"><div className="spinner" /> กำลังโหลดข้อมูลจำลอง...</div> : profile && horizon ? <>
            {tab !== 'transfer' && isPendingTransfer(transferResult) && <div className="pending-transfer-banner"><ShieldAlert size={19} /><span>มีรายการรอตรวจสอบก่อนโอน · ยังไม่ได้หักเงิน</span><button className="text-link" onClick={showTransferReview}>กลับไปดูรายการ <ArrowRight size={16} /></button></div>}
            {tab === 'home' && <Dashboard profile={profile} horizon={horizon} activities={(profile.events || []).slice(0, 5).map(describeEvent)} hidden={hidden} setHidden={setHidden} openTab={openTab} tryScenario={tryScenario} {...{onPayBill, onWithdraw, onTransferSettings, startTutorial, busy}} />}
            {tab === 'transactions' && <TransactionsHub {...{profile, horizon, openTab, onPayBill, onWithdraw, onTransferSettings}}/>}
            {tab === 'profile' && <ProfilePage {...{persona, profile, openTab, onTransferSettings, doReset, busy, setHidden}}/>}
            {['plan', 'accounts'].includes(tab) && <FinancialTabs active={tab} openTab={openTab}/>}
            {tab === 'plan' && <DailyPlan key={`${accountId}-${horizon.scenario}`} {...{ profile, horizon, forecast, busy, onScenario, openTab, onWithdraw, onReservePreview, onReserveSave }}/>}
            {tab === 'accounts' && <AccountsPage profile={profile} horizon={horizon} chart={<ForecastChart timeline={forecast?.timeline} horizon={horizon} onRefresh={() => run(() => refresh())} busy={busy} />} openTab={openTab} hidden={hidden} doReset={doReset} busy={busy} onScenario={onScenario} refresh={() => run(() => refresh())} />}

            {tab === 'savings' && <SavingsPage key={accountId} {...{ profile, horizon, busy, sweepAmount, setSweepAmount, doSweep, doRecommendedSweep, doWithdraw, doReset, onSavingsToggle, onScenario, openTab, onReservePreview, onReserveSave }}/>}

            {tab === 'transfer' && <TransferProtectionSettings key={accountId} profile={profile} busy={busy} hasPending={isPendingTransfer(transferResult)} onChange={onTransferPreference} />}
            {tab === 'transfer' && <>
              {isPendingTransfer(transferResult) && <div className="transfer-active-review"><div><strong>มีรายการที่กำลังตรวจสอบ</strong><p>฿{money(amount, 2)} · {recipient.name} · ยังไม่ได้หักเงิน</p></div><div><button id="transfer-review-open" className="primary-button" disabled={busy} onClick={showTransferReview}>ดูรายการที่รอ <ArrowRight size={16} /></button><button className="text-link" disabled={busy} onClick={() => decide('CANCEL')}>ยกเลิกรายการเดิม</button></div></div>}
              {transferResult && !isPendingTransfer(transferResult) && <button className="transfer-last-result text-link" onClick={() => setReviewOpen(true)}>ดูผลรายการล่าสุด <ArrowRight size={16} /></button>}
              <div className="transfer-workspace"><TransferForm profile={profile} persona={persona} recipients={recipients} recipient={recipient} amount={amount} setAmount={setAmount} changeRecipient={changeRecipient} clearResult={clearTransferResult} busy={busy} evaluate={evaluate} prepareHighValue={prepareHighValue} bills={(horizon.recurring_commitments || []).filter((bill) => bill.due_days < horizon.days_to_payday && bill.amount > 0)} matchedBillId={matchedBillId} setMatchedBillId={setMatchedBillId} transferPurpose={transferPurpose} setTransferPurpose={setTransferPurpose} telemetry={telemetry} setTelemetry={(value) => { setTelemetry(value); clearTransferResult(); }} /><div className="transfer-flow-note"><ShieldCheck size={19} /><p>ผลการตรวจสอบจะแสดงในหน้าต่าง Pop-up · เมื่อยกเลิก รายการและเวลาพักนั้นจะสิ้นสุด รายการใหม่ใช้ค่าตั้งค่าปัจจุบัน</p></div></div>
            </>}
            {reviewOpen && transferResult && <TransferReviewDialog busy={busy} pending={isPendingTransfer(transferResult)} canContactBank={transferResult.status === 'BLOCKED_MULE_INTERDICTION' || (transferResult.status === 'MICRO_AUTH_REQUIRED' && transferResult.risk_tier !== 'HIGH_VALUE_DEMO_CHECK')} error={error} onClose={() => setReviewOpen(false)} onSettings={editTransferSettings} onCancelTransfer={() => decide('CANCEL')}><TransferResult result={transferResult} {...{ amount, recipient, busy, clearanceToken, verify, decide, scanning, checkCooldown, evaluate }} cancelInFooter clear={clearTransferResult} /></TransferReviewDialog>}

          </> : null}
          <footer className="page-footer"><span>K-NEXUS · FlowSense × TrustGraph</span><span>Inspired by everyday banking · ไม่ใช่ผลิตภัณฑ์ทางการของ KBank</span></footer>
        </main>
        <nav className="mobile-nav" aria-label="เมนูหลักบนมือถือ">{navItems.map(({ id, label, icon: Icon }) => <button key={id} data-tab={id} className={navSection === id ? 'active' : ''} aria-label={label} aria-current={navSection === id ? 'page' : undefined} onClick={() => openTab(id)}><span className="nav-icon">{id === 'transactions' ? <b aria-hidden="true">฿</b> : <Icon size={21} strokeWidth={1.7}/>}</span><span>{label}</span></button>)}</nav>
      </div>
      {tutorialStep !== null && !hidden && !loading && <TutorialOverlay stepIndex={tutorialStep} busy={busy} error={tutorialStep === 4 ? error : ''} onNext={nextTutorial} onBack={() => visitTutorialStep(tutorialStep - 1)} onSkip={() => closeTutorial('skipped')} nextLabel={tutorialStep === 4 ? (Number(profile?.main_balance) > 0 || isPendingTransfer(transferResult) ? 'ดูผลตรวจตัวอย่าง' : 'ไปดูวิธีถอนเงินออม') : undefined}/> }
    </div>
  );
}

export default App;
