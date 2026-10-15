import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, BadgeCheck,
  Bell, Check, ChevronDown, CircleAlert, CreditCard, Fingerprint,
  Home, LockKeyhole, RotateCcw, Send, ShieldAlert, ShieldCheck,
  Sparkles, Wallet, X, Search, ChevronRight, Target, Eye, EyeOff,
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
const navItems = [
  { id: 'home', label: 'หน้าหลัก', icon: Home },
  { id: 'plan', label: 'แผนใช้เงิน', icon: Target },
  { id: 'accounts', label: 'บัญชี', icon: CreditCard },
  { id: 'transfer', label: 'โอน / จ่าย', icon: Send },
  { id: 'savings', label: 'ออมเงิน', icon: Wallet },
];

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
  const [sweepAmount, setSweepAmount] = useState('200');
  const [recipient, setRecipient] = useState(recipientTemplates[0]);
  const [amount, setAmount] = useState('350');
  const [transferResult, setTransferResult] = useState(null);
  const [clearanceToken, setClearanceToken] = useState(null);
  const inFlight = useRef(false);
  const activeAccount = useRef(accountId);
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
    Promise.all([api.profile(accountId), api.horizon(accountId), api.forecast(accountId)])
      .then(([nextProfile, nextHorizon, nextForecast]) => {
        if (!active) return;
        setProfile(nextProfile); setHorizon(nextHorizon); setForecast(nextForecast);
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
    activeAccount.current = id;
    setAccountId(id); setTransferResult(null); setClearanceToken(null);
    setRecipient({ ...recipientTemplates[0], id: id === 'ACC_0101' ? 'ACC_0100' : 'ACC_0101' });
    setAmount('350'); setTelemetry({ device: false, first: false, duration: 90, ratio: 1.1, auth: 'pin' });
    setError(''); setNotice('');
  };
  const doSweep = () => run(async () => {
    const value = Number(sweepAmount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินออมที่มากกว่า 0 บาท');
    const result = await api.sweep(accountId, value);
    await refresh();
    setNotice(`ย้าย ฿${money(result.swept_amount)} เข้ากระเป๋าเงินออมแล้ว`);
  });
  const doAutoSweep = () => run(async () => {
    const result = await api.sweep(accountId);
    await refresh();
    setNotice(`FlowSense ย้าย ฿${money(result.swept_amount, 2)} เข้ากระเป๋าเงินออมแล้ว`);
  });
  const doRecall = (mode = 'all', value) => run(async () => {
    if (mode === 'partial' && (!Number.isFinite(value) || value <= 0)) throw new Error('กรุณาระบุจำนวนเงินที่ต้องการดึงคืน');
    const result = await api.recall(accountId, mode, value);
    await refresh();
    setNotice(`ดึงคืน ฿${money(result.recalled_amount, 2)} เข้าบัญชีหลักแล้ว`);
  });
  const doUndo = () => doRecall('undo');
  const onScenario = (scenario) => run(async () => { await api.scenario(accountId, scenario); await refresh(); setTransferResult(null); setClearanceToken(null); setNotice('เปลี่ยนสถานการณ์จำลองแล้ว ลองดูคำแนะนำและกราฟที่เปลี่ยนไป'); });
  const prepareHighValue = () => run(async () => { await api.scenario(accountId, 'high_value'); await refresh(); changeRecipient(recipients[0]); setAmount('50000'); setNotice('เตรียมยอดบัญชีสมมติ ฿60,000 สำหรับทดลองการตรวจรายการมูลค่าสูงแล้ว'); });
  const onAutoToggle = (enabled) => run(async () => { await api.autoSaving(accountId, enabled); await refresh(); setNotice(enabled ? 'เปิดตัวช่วยออมแล้ว ลองกดทดลองรอบออม' : 'ปิดตัวช่วยออมแล้ว'); });
  const onAutoCycle = () => run(async () => { const result = await api.autoCycle(accountId); await refresh(); setNotice(result.status === 'SKIPPED' ? result.message : `รอบออมสำเร็จ ฿${money(result.swept_amount, 2)}`); });
  const doReset = () => run(async () => {
    await api.reset(accountId);
    await refresh();
    setTransferResult(null); setClearanceToken(null);
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
  });
  const evaluate = () => run(async () => {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินที่จะโอน');
    if (value > Number(profile?.main_balance)) throw new Error('ยอดเงินในบัญชีหลักไม่เพียงพอ');
    setTransferResult(null); setClearanceToken(null);
    const result = await api.evaluate(transferPayload());
    setTransferResult(result);
    await refresh();
  });
  const verify = () => run(async () => {
    try { for (let seconds = 5; seconds > 0; seconds--) { setScanning(seconds); await new Promise((resolve) => setTimeout(resolve, 1000)); } } finally { setScanning(0); }
    const result = await api.verify({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount) });
    setClearanceToken(result.clearance_token);
    setNotice('จำลองการยืนยันตัวตนสำเร็จ กรุณาตัดสินใจว่าจะโอนต่อหรือยกเลิก');
  });
  const decide = (decision) => run(async () => {
    const result = await api.confirm({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount), decision, auth_token: decision === 'PROCEED' ? clearanceToken : undefined });
    setTransferResult(result); setClearanceToken(null);
    await refresh();
  });
  const changeRecipient = (item) => {
    setTelemetry({ device: false, first: item.tone !== 'green', duration: item.tone === 'green' ? 90 : 8, ratio: item.tone === 'green' ? 1.1 : 8, auth: 'pin' });
    setRecipient(item); setAmount(String(item.amount)); setTransferResult(null); setClearanceToken(null); setError(''); setNotice('');
  };
  const openTab = (id) => {
    setTab(id); setError(''); setNotice(''); setSearch(''); setShowAlerts(false); setSearchOpen(false);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };
  const searchItems = navItems.filter((item) => {
    const terms = { home: 'หน้าหลัก ภาพรวม ยอดเงิน', plan: 'แผนใช้เงิน งบ วันนี้ รายวัน วันละ ใช้ได้ ควรใช้ คาดการณ์รายจ่าย flowsense สภาพคล่อง', accounts: 'บัญชี สภาพคล่อง คาดการณ์ กราฟ ภาระ', transfer: 'โอน จ่าย trustgraph ความเสี่ยง', savings: 'flowsense การออมเงิน ออมเงิน เงินออม ดึงคืน' };
    return search.trim() && terms[item.id].includes(search.trim().toLowerCase());
  });
  const tryScenario = (index) => { changeRecipient(recipients[index]); openTab('transfer'); };
  const title = { home: `สวัสดี, คุณ${persona.name}`, plan: 'แผนใช้เงิน', accounts: 'บัญชีของฉัน', savings: 'ออมเงิน', transfer: 'โอนเงิน' }[tab];

  useEffect(() => {
    if (transferResult && window.innerWidth <= 640) {
      const frame = requestAnimationFrame(() => document.querySelector('.result-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return () => cancelAnimationFrame(frame);
    }
  }, [transferResult]);

  return (
    <div className={`app-shell page-${tab}`}>
      <aside className="sidebar">
        <div className="bank-brand" aria-label="K แอปต้นแบบ"><span className="k-mark">K</span><small>CONCEPT EXPERIENCE</small></div>
        <nav className="side-nav" aria-label="เมนูหลัก">
          {navItems.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'active' : ''} aria-label={label} title={label} aria-current={tab === id ? 'page' : undefined} onClick={() => openTab(id)}><Icon size={19} strokeWidth={1.6} /><span>{label}</span>{tab === id && <ChevronRight className="side-chevron" size={14} />}</button>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-feature"><strong>FlowSense × TrustGraph</strong><p>ข้อมูลสมมติสำหรับทดลองใช้งาน</p></div>
        <div className="sidebar-profile"><div className={`avatar ${persona.color}`}>{persona.initials}</div><div><strong>คุณ{persona.name}</strong><small>บัญชีทดลอง</small></div></div>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <div className="mobile-brand"><span className="mobile-bank-logo" aria-label="K แอปต้นแบบ">K</span></div>
          <div className="header-product">FlowSense <span>×</span> TrustGraph <span className="concept-badge">DEMO</span></div>
          <div className="topbar-right">
            <button className="icon-button mobile-search-toggle" aria-label="เปิดช่องค้นหา" aria-expanded={searchOpen} onClick={() => setSearchOpen(!searchOpen)}><Search size={18} /></button><div className={`service-search ${searchOpen ? 'search-open' : ''}`}><Search size={16} /><input aria-label="ค้นหาบริการหรือเมนู" placeholder="ค้นหาบริการหรือเมนู" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && searchItems.length) openTab(searchItems[0].id); if (event.key === 'Escape') setSearch(''); }} />
              {search.trim() && <div className="search-results">{searchItems.length ? searchItems.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => openTab(id)}><Icon size={16} />{label}<ChevronRight size={14} /></button>) : <p>ไม่พบบริการ ลองค้นหา “ออม” หรือ “โอน”</p>}</div>}
            </div>
            <button className="icon-button" aria-label={hidden ? "แสดงข้อมูลการเงิน" : "ซ่อนข้อมูลการเงิน"} aria-pressed={hidden} onClick={() => { setHidden(!hidden); setShowAlerts(false); }}>{hidden ? <EyeOff size={18} /> : <Eye size={18} />}</button><div className="notification-wrap"><button className={`icon-button ${showAlerts ? 'selected' : ''}`} aria-label="ดูการแจ้งเตือน" aria-expanded={showAlerts} onClick={() => setShowAlerts(!showAlerts)}><Bell size={18} />{horizon?.commitment_at_risk && <span className="notification-dot" />}</button>{showAlerts && !hidden && <div className="notification-panel"><strong>ผู้ช่วยแจ้งเตือนของคุณ</strong><p>{horizon?.nudge_message || 'กำลังเตรียมสถานะสภาพคล่อง'}</p><button className="text-link" onClick={() => openTab(horizon?.commitment_at_risk ? 'savings' : 'accounts')}>ดูรายละเอียด <ArrowRight size={14} /></button></div>}</div>
          </div>
        </header>
        <main className="main-content">
          <div className="page-intro"><div><h1>{title}</h1><p>{tab === 'home' ? 'ภาพรวมเงินของคุณวันนี้' : tab === 'plan' ? 'ลองตั้งงบ ให้เงินพอถึงวันเงินเดือน' : tab === 'accounts' ? 'ยอดเงิน ภาระ และแนวโน้มวันข้างหน้า' : tab === 'savings' ? 'ออมเมื่อพร้อม ดึงคืนได้เมื่อจำเป็น' : 'ดูความเสี่ยงก่อนตัดสินใจ'}</p></div><details className="demo-context"><summary>บัญชีทดลอง · {persona.name}<ChevronDown size={15} /></summary><div className="demo-context-panel"><label htmlFor="persona">ลองเปลี่ยนโปรไฟล์</label><select id="persona" value={accountId} disabled={busy} onChange={(event) => changePersona(event.target.value)}>{personas.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}</select><p>แอปต้นแบบอิสระ ใช้ข้อมูลสมมติ ไม่ใช่แอปทางการของ KBank</p><button className="text-link" disabled={busy || !profile} onClick={doReset}><RotateCcw size={15} /> รีเซ็ตบัญชีทดลอง</button></div></details></div>

          <div className="demo-disclaimer"><ShieldCheck size={14} /><span>แอปต้นแบบ · ข้อมูลสมมติ · ไม่มีการโอนเงินจริง</span></div>
          {error && !hidden && <div className="message error" role="alert"><CircleAlert size={18} /><span>{error}</span><button aria-label="ปิดข้อความ" onClick={() => setError('')}><X size={16} /></button></div>}
          {notice && !hidden && <div className="message success" role="status"><Check size={18} /><span>{notice}</span><button aria-label="ปิดข้อความ" onClick={() => setNotice('')}><X size={16} /></button></div>}

          {hidden ? <section className="surface privacy-cover"><EyeOff size={32} /><h2>ซ่อนข้อมูลการเงินแล้ว</h2><p>ยอดเงิน กราฟ และรายการต่าง ๆ จะกลับมาเมื่อคุณเลือกแสดงข้อมูล</p><button className="primary-button" onClick={() => setHidden(false)}>แสดงข้อมูลการเงิน <Eye size={17} /></button></section> : loading ? <div className="loading-card"><div className="spinner" /> กำลังโหลดข้อมูลจำลอง...</div> : profile && horizon ? <>
            {tab === 'home' && <Dashboard profile={profile} horizon={horizon} activities={(profile.events || []).slice(0, 5).map(describeEvent)} hidden={hidden} setHidden={setHidden} openTab={openTab} tryScenario={tryScenario} />}
            {tab === 'plan' && <DailyPlan key={`${accountId}-${horizon.scenario}`} {...{ horizon, forecast, busy, onScenario, openTab }} />}
            {tab === 'accounts' && <AccountsPage profile={profile} horizon={horizon} chart={<ForecastChart timeline={forecast?.timeline} horizon={horizon} onRefresh={() => run(() => refresh())} busy={busy} />} openTab={openTab} hidden={hidden} doReset={doReset} busy={busy} onScenario={onScenario} refresh={() => run(() => refresh())} />}

            {tab === 'savings' && <SavingsPage {...{ profile, horizon, busy, sweepAmount, setSweepAmount, doSweep, doAutoSweep, doRecall, doReset, doUndo, onAutoToggle, onAutoCycle, onScenario, openTab }} />}

            {tab === 'transfer' && <div className="feature-layout transfer-layout"><TransferForm profile={profile} persona={persona} recipients={recipients} recipient={recipient} amount={amount} setAmount={setAmount} changeRecipient={changeRecipient} clearResult={() => { setTransferResult(null); setClearanceToken(null); }} busy={busy} evaluate={evaluate} prepareHighValue={prepareHighValue} telemetry={telemetry} setTelemetry={(value) => { setTelemetry(value); setTransferResult(null); setClearanceToken(null); }} /><aside className="feature-aside"><TransferResult result={transferResult} {...{ amount, recipient, busy, clearanceToken, verify, decide, scanning }} clear={() => setTransferResult(null)} /><div className="surface aside-card trust-note"><span className="icon-box mint"><LockKeyhole size={21} /></span><h3>ดูเหตุผลก่อนตัดสินใจโอน</h3><p>รายการปกติผ่านได้ทันที ส่วนรายการที่น่าสงสัยแสดงเหตุผลให้เห็นก่อนตัดสินใจ</p></div></aside></div>}
          </> : null}
          <footer className="page-footer"><span>FlowSense × TrustGraph · Prototype experience</span><span>Inspired by everyday banking · ไม่ใช่ผลิตภัณฑ์ทางการของ KBank</span></footer>
        </main>
        <nav className="mobile-nav" aria-label="เมนูหลักบนมือถือ">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'active' : ''} aria-label={label} aria-current={tab === id ? 'page' : undefined} onClick={() => openTab(id)}><Icon size={21} strokeWidth={2} /><span>{label}</span></button>)}</nav>
      </div>
    </div>
  );
}

export default App;
