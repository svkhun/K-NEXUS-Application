import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, BadgeCheck,
  Bell, Check, ChevronDown, CircleAlert, CreditCard, Fingerprint,
  Home, LockKeyhole, RotateCcw, Send, ShieldAlert, ShieldCheck,
  Sparkles, Wallet, X, Search, ChevronRight,
} from 'lucide-react';
import { api } from './api';
import Dashboard, { AccountsPage } from './Dashboard';
import TransferForm from './TransferForm';

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
  { id: 'accounts', label: 'บัญชี', icon: CreditCard },
  { id: 'transfer', label: 'โอน / จ่าย', icon: Send },
  { id: 'savings', label: 'FlowSense', icon: Wallet },
];

function ForecastChart({ timeline = [] }) {
  const points = timeline.filter((point) => !point.is_past);
  if (points.length < 2) return <div className="chart-loading">กำลังเตรียมกราฟ...</div>;
  const values = points.map((point) => Number(point.projected_balance));
  const low = Math.min(0, ...values) - 1200;
  const high = Math.max(...values) + 1000;
  const x = (index) => 18 + index * (564 / (points.length - 1));
  const y = (value) => 150 - ((value - low) / Math.max(1, high - low)) * 120;
  const line = points.map((point, index) => `${x(index)},${y(point.projected_balance)}`).join(' ');
  const area = `18,160 ${line} 582,160`;
  const zeroY = y(0);
  return (
    <div className="forecast-chart" role="img" aria-label="กราฟคาดการณ์ยอดเงินคงเหลือใน 22 วันข้างหน้า">
      <svg viewBox="0 0 600 175" preserveAspectRatio="none">
        <defs><linearGradient id="chartFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#15a575" stopOpacity=".25" /><stop offset="1" stopColor="#15a575" stopOpacity="0" /></linearGradient></defs>
        <line x1="18" x2="582" y1={zeroY} y2={zeroY} stroke="#d6e2db" strokeDasharray="5 5" />
        <polygon points={area} fill="url(#chartFill)" />
        <polyline points={line} fill="none" stroke="#0b9e6b" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="18" cy={y(points[0].projected_balance)} r="5.5" fill="#0b9e6b" stroke="white" strokeWidth="3" />
      </svg>
      <div className="chart-labels"><span>วันนี้</span><span>อีก 7 วัน</span><span>อีก 14 วัน</span><span>อีก 22 วัน</span></div>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState('home');
  const [hidden, setHidden] = useState(false);
  const [search, setSearch] = useState('');
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
  const [activities, setActivities] = useState([]);
  const [sweepAmount, setSweepAmount] = useState('200');
  const [recipient, setRecipient] = useState(recipientTemplates[0]);
  const [amount, setAmount] = useState('350');
  const [transferResult, setTransferResult] = useState(null);
  const [clearanceToken, setClearanceToken] = useState(null);
  const inFlight = useRef(false);
  const persona = useMemo(() => personas.find((item) => item.id === accountId) ?? personas[0], [accountId]);

  const refresh = useCallback(async (id = accountId) => {
    const [nextProfile, nextHorizon, nextForecast] = await Promise.all([api.profile(id), api.horizon(id), api.forecast(id)]);
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

  const addActivity = (title, description, icon = Activity) => {
    setActivities((current) => [{ title, description, icon, time: new Date().toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }) }, ...current].slice(0, 5));
  };
  const run = async (action) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(err.message); }
    finally { inFlight.current = false; setBusy(false); }
  };
  const changePersona = (id) => {
    setAccountId(id); setTransferResult(null); setClearanceToken(null);
    setRecipient({ ...recipientTemplates[0], id: id === 'ACC_0101' ? 'ACC_0100' : 'ACC_0101' });
    setAmount('350');
    setActivities([]); setError(''); setNotice('');
  };
  const doSweep = () => run(async () => {
    const value = Number(sweepAmount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินออมที่มากกว่า 0 บาท');
    const result = await api.sweep(accountId, value);
    await refresh();
    setNotice(`ย้าย ฿${money(result.swept_amount)} เข้ากระเป๋าเงินออมแล้ว`);
    addActivity('ออมเงินสำเร็จ', `+฿${money(result.swept_amount)} เข้ากระเป๋าเงินออม`, ArrowDownLeft);
  });
  const doAutoSweep = () => run(async () => {
    const result = await api.sweep(accountId);
    await refresh();
    setNotice(`FlowSense ย้าย ฿${money(result.swept_amount, 2)} เข้ากระเป๋าเงินออมแล้ว`);
    addActivity('ออมตามคำแนะนำ FlowSense', `+฿${money(result.swept_amount, 2)} เข้ากระเป๋าเงินออม`, ArrowDownLeft);
  });
  const doRecall = () => run(async () => {
    const result = await api.recall(accountId);
    await refresh();
    setNotice(`ดึงคืน ฿${money(result.recalled_amount, 2)} เข้าบัญชีหลักแล้ว`);
    addActivity('ดึงเงินออมคืน', `฿${money(result.recalled_amount, 2)} กลับเข้าบัญชีหลัก`, RotateCcw);
  });
  const doReset = () => run(async () => {
    await api.reset(accountId);
    await refresh();
    setActivities([]); setTransferResult(null); setClearanceToken(null);
    setNotice('รีเซ็ตข้อมูลของบัญชีจำลองแล้ว');
  });
  const transferPayload = () => ({
    source_account_id: accountId,
    target_account_id: recipient.id,
    amount: Number(amount),
    is_first_time_transfer: recipient.tone === 'green' ? 0 : 1,
    device_switch_last_24h: 0,
    session_duration_sec: recipient.tone === 'green' ? 90 : 8,
    ratio_to_daily_avg: recipient.tone === 'green' ? 1.1 : 8,
    auth_factor_used: 'pin',
    scenario_mode: recipient.id === 'ACC_0000' ? 'blocked' : 'auto',
  });
  const evaluate = () => run(async () => {
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) throw new Error('กรุณาระบุจำนวนเงินที่จะโอน');
    if (value > Number(profile?.main_balance)) throw new Error('ยอดเงินในบัญชีหลักไม่เพียงพอ');
    setTransferResult(null); setClearanceToken(null);
    const result = await api.evaluate(transferPayload());
    setTransferResult(result);
    if (result.status === 'APPROVED') {
      await refresh();
      addActivity('โอนเงินสำเร็จ', `฿${money(value)} ไปยัง ${recipient.name}`, ArrowUpRight);
    }
  });
  const verify = () => run(async () => {
    const result = await api.verify({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount) });
    setClearanceToken(result.clearance_token);
    setNotice('จำลองการยืนยันตัวตนสำเร็จ กรุณาตัดสินใจว่าจะโอนต่อหรือยกเลิก');
  });
  const decide = (decision) => run(async () => {
    const result = await api.confirm({ source_account_id: accountId, target_account_id: recipient.id, amount: Number(amount), decision, auth_token: decision === 'PROCEED' ? clearanceToken : undefined });
    setTransferResult(result); setClearanceToken(null);
    await refresh();
    if (decision === 'PROCEED') addActivity('โอนเงินหลังตรวจสอบ', `฿${money(amount)} ไปยัง ${recipient.name}`, ArrowUpRight);
    else addActivity('ยกเลิกรายการโอน', 'เงินยังอยู่ในบัญชีหลัก', ShieldCheck);
  });
  const changeRecipient = (item) => {
    setRecipient(item); setAmount(String(item.amount)); setTransferResult(null); setClearanceToken(null); setError(''); setNotice('');
  };
  const openTab = (id) => {
    setTab(id); setError(''); setNotice(''); setSearch(''); setShowAlerts(false);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };
  const searchItems = navItems.filter((item) => {
    const terms = { home: 'หน้าหลัก ภาพรวม ยอดเงิน', accounts: 'บัญชี สภาพคล่อง คาดการณ์ กราฟ ภาระ', transfer: 'โอน จ่าย trustgraph ความเสี่ยง', savings: 'flowsense เงินออม ดึงคืน' };
    return search.trim() && terms[item.id].includes(search.trim().toLowerCase());
  });
  const tryScenario = (index) => { changeRecipient(recipients[index]); openTab('transfer'); };
  const title = { home: `สวัสดี, คุณ${persona.name}`, accounts: 'บัญชีของฉัน', savings: 'FlowSense · เงินออม', transfer: 'โอนเงิน' }[tab];

  useEffect(() => {
    if (transferResult && window.innerWidth <= 640) {
      const frame = requestAnimationFrame(() => document.querySelector('.result-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
      return () => cancelAnimationFrame(frame);
    }
  }, [transferResult]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="bank-brand" aria-label="K Plus Concept"><span>K<span>+</span></span><small>CONCEPT EXPERIENCE</small></div>
        <nav className="side-nav" aria-label="เมนูหลัก">
          {navItems.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'active' : ''} aria-current={tab === id ? 'page' : undefined} onClick={() => openTab(id)}><Icon size={19} strokeWidth={1.6} /><span>{label}</span>{tab === id && <ChevronRight className="side-chevron" size={14} />}</button>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="sidebar-feature"><ShieldCheck size={19} /><strong>FlowSense × TrustGraph</strong><p>ผู้ช่วยการเงินและความปลอดภัย<br />ที่คุณลองใช้ได้ด้วยตัวเอง</p></div>
        <div className="sidebar-profile"><div className={`avatar ${persona.color}`}>{persona.initials}</div><div><strong>คุณ{persona.name}</strong><small>บัญชีทดลอง</small></div></div>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <div className="mobile-brand"><span className="mobile-bank-logo">K<span>+</span></span></div>
          <div className="header-product">FlowSense <span>×</span> TrustGraph <span className="concept-badge">DEMO</span></div>
          <div className="topbar-right">
            <div className="service-search"><Search size={16} /><input aria-label="ค้นหาบริการหรือเมนู" placeholder="ค้นหาบริการหรือเมนู" value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && searchItems.length) openTab(searchItems[0].id); if (event.key === 'Escape') setSearch(''); }} />
              {search.trim() && <div className="search-results">{searchItems.length ? searchItems.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => openTab(id)}><Icon size={16} />{label}<ChevronRight size={14} /></button>) : <p>ไม่พบบริการ ลองค้นหา “ออม” หรือ “โอน”</p>}</div>}
            </div>
            <div className="notification-wrap"><button className={`icon-button ${showAlerts ? 'selected' : ''}`} aria-label="ดูการแจ้งเตือน" aria-expanded={showAlerts} onClick={() => setShowAlerts(!showAlerts)}><Bell size={18} />{horizon?.commitment_at_risk && <span className="notification-dot" />}</button>{showAlerts && <div className="notification-panel"><strong>ผู้ช่วยแจ้งเตือนของคุณ</strong><p>{horizon?.commitment_at_risk ? `เงินอาจขาดประมาณ ฿${money(horizon.deficit_amount)} ก่อนเงินเดือนเข้า ลองจัดการเงินออมเพื่อดูผลลัพธ์` : 'ยังไม่มีภาระที่ต้องแจ้งเตือนในตอนนี้ ดูแนวโน้มเงินและวันถึงรอบเงินเดือนในหน้าบัญชีได้เลย'}</p><button className="text-link" onClick={() => openTab(horizon?.commitment_at_risk ? 'savings' : 'accounts')}>ดูรายละเอียด <ArrowRight size={14} /></button></div>}</div>
            <button className="icon-button" aria-label="รีเซ็ตบัญชีทดลอง" title="รีเซ็ตบัญชีทดลอง" disabled={busy || !profile} onClick={doReset}><RotateCcw size={17} /></button>
          </div>
        </header>
        <main className="main-content">
          <div className="page-intro"><div><h1>{title}</h1><p>{tab === 'home' ? 'ดูแลเงินของคุณให้พร้อมสำหรับทุกวัน' : tab === 'accounts' ? 'เห็นยอดเงิน ภาระที่ต้องจ่าย และแนวโน้มวันข้างหน้า' : tab === 'savings' ? 'ออมเมื่อพร้อม และดึงกลับได้ทันทีเมื่อจำเป็น' : 'TrustGraph ช่วยดูความเสี่ยงก่อนคุณตัดสินใจ'}</p></div><div className="profile-picker"><label htmlFor="persona">ลองเปลี่ยนโปรไฟล์</label><div className="select-wrap"><select id="persona" value={accountId} disabled={busy} onChange={(event) => changePersona(event.target.value)}>{personas.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}</select><ChevronDown size={15} /></div></div></div>

          <div className="demo-disclaimer"><ShieldCheck size={14} /><span>พื้นที่ทดลองใช้ฟังก์ชันใหม่ · ข้อมูลสมมติ ไม่มีการโอนเงินจริง</span></div>
          {error && <div className="message error" role="alert"><CircleAlert size={18} /><span>{error}</span><button aria-label="ปิดข้อความ" onClick={() => setError('')}><X size={16} /></button></div>}
          {notice && <div className="message success" role="status"><Check size={18} /><span>{notice}</span><button aria-label="ปิดข้อความ" onClick={() => setNotice('')}><X size={16} /></button></div>}

          {loading ? <div className="loading-card"><div className="spinner" /> กำลังโหลดข้อมูลจำลอง...</div> : profile && horizon ? <>
            {tab === 'home' && <Dashboard profile={profile} horizon={horizon} activities={activities} chart={<ForecastChart timeline={forecast?.timeline} />} hidden={hidden} setHidden={setHidden} busy={busy} doRecall={doRecall} openTab={openTab} tryScenario={tryScenario} />}
            {tab === 'accounts' && <AccountsPage profile={profile} horizon={horizon} chart={<ForecastChart timeline={forecast?.timeline} />} openTab={openTab} hidden={hidden} doReset={doReset} busy={busy} />}

            {tab === 'savings' && <div className="feature-layout"><section className="surface feature-primary"><div className="section-kicker">FLOWSENSE · FLEXIBLE SAVINGS</div><div className="feature-header"><div><h2>ออมได้ โดยไม่ต้องล็อกเงิน</h2><p>ย้ายเงินส่วนที่พร้อมออมไปกระเป๋าเงินออม และเรียกกลับบัญชีหลักได้เมื่อต้องใช้</p></div><span className="feature-illustration"><Wallet size={42} /></span></div><div className="account-pair"><div><span>บัญชีหลัก</span><strong>฿{money(profile.main_balance, 2)}</strong></div><div className="pair-arrow"><ArrowRight size={19} /></div><div><span>กระเป๋าเงินออม</span><strong>฿{money(profile.vault_balance, 2)}</strong></div></div><div className="auto-save-recommendation"><span className="auto-save-icon"><Sparkles size={18} /></span><div><span>คำแนะนำจาก FlowSense</span><strong>ออมครั้งนี้ ฿{money(Math.min(profile.main_balance * profile.persona.recommended_sweep_pct * 0.15, 500), 2)}</strong><small>คำนวณจากยอดเงินและโปรไฟล์ของคุณ</small></div><button disabled={busy} onClick={doAutoSweep}>ลองออมให้ฉัน <ArrowRight size={14} /></button></div><div className="divider" /><label className="field-label" htmlFor="sweep-amount">จำนวนเงินที่อยากออม</label><div className="amount-input"><span>฿</span><input id="sweep-amount" type="number" min="1" step="1" value={sweepAmount} onChange={(event) => setSweepAmount(event.target.value)} /><span>THB</span></div><div className="amount-presets">{[100, 200, 500].map((value) => <button key={value} className={Number(sweepAmount) === value ? 'selected' : ''} onClick={() => setSweepAmount(String(value))}>฿{money(value)}</button>)}</div><button className="primary-button" disabled={busy} onClick={doSweep}><ArrowDownLeft size={18} /> {busy ? 'กำลังดำเนินการ...' : 'ย้ายเข้าเงินออม'}</button><button className="secondary-button" disabled={busy || profile.vault_balance <= 0} onClick={doRecall}><RotateCcw size={17} /> ดึงเงินออมคืนทันที</button></section><aside className="feature-aside"><div className="surface aside-card"><span className="icon-box mint"><Sparkles size={22} /></span><h3>ช่วยออมแบบพอดี</h3><p>FlowSense ดูยอดคงเหลือและภาระที่ต้องจ่าย ก่อนแนะนำการออม</p><div className="aside-metric"><span>ใช้ได้ต่อวันโดยประมาณ</span><strong>฿{money(horizon.daily_safe_limit)}</strong></div></div><div className="surface aside-card"><span className="icon-box pale"><RotateCcw size={22} /></span><h3>ดึงคืนได้เมื่อจำเป็น</h3><p>ในแอปทดลองนี้ กดครั้งเดียวเพื่อย้ายยอดในกระเป๋าเงินออมกลับบัญชีหลัก</p><div className="aside-metric"><span>ยอดที่ย้ายออมในรอบนี้</span><strong>฿{money(profile.total_swept)}</strong></div></div><button className="reset-button" onClick={doReset} disabled={busy}><RotateCcw size={15} /> รีเซ็ตบัญชีทดลอง</button></aside></div>}

            {tab === 'transfer' && <div className="feature-layout transfer-layout"><TransferForm profile={profile} persona={persona} recipients={recipients} recipient={recipient} amount={amount} setAmount={setAmount} changeRecipient={changeRecipient} clearResult={() => { setTransferResult(null); setClearanceToken(null); }} busy={busy} evaluate={evaluate} /><aside className="feature-aside"><div className="surface result-card"><span className="section-kicker">TRUSTGRAPH · ผลการตรวจสอบ</span>{!transferResult ? <div className="result-empty"><span><ShieldCheck size={29} /></span><h3>พร้อมตรวจสอบ</h3><p>เลือกสถานการณ์และกดปุ่มทดลองโอน เพื่อดู TrustGraph ทำงาน</p></div> : transferResult.status === 'APPROVED' || transferResult.status === 'TRANSFER_EXECUTED' ? <div className="result-detail"><span className="result-symbol approved"><Check size={29} /></span><h3>โอนเงินสำเร็จ</h3><p>รายการนี้ผ่านการตรวจสอบและดำเนินการแล้ว</p><div className="result-meta"><span>ยอดโอน</span><strong>฿{money(amount)}</strong></div><div className="result-meta"><span>ไปยัง</span><strong>{recipient.name}</strong></div><button className="text-link" onClick={() => setTransferResult(null)}>ลองสถานการณ์อื่น <ArrowRight size={16} /></button></div> : transferResult.status === 'BLOCKED_MULE_INTERDICTION' ? <div className="result-detail"><span className="result-symbol blocked"><LockKeyhole size={26} /></span><h3>ระงับรายการนี้</h3><p>{transferResult.primary_reason_th || transferResult.direct_risk_reasoning}</p><div className="risk-explanation"><ShieldAlert size={17} /><span>ไม่มีการหักเงินจากบัญชีของคุณ</span></div><button className="text-link" onClick={() => setTransferResult(null)}>ลองสถานการณ์อื่น <ArrowRight size={16} /></button></div> : transferResult.status === 'TRANSFER_CANCELLED' ? <div className="result-detail"><span className="result-symbol approved"><ShieldCheck size={27} /></span><h3>ยกเลิกรายการแล้ว</h3><p>เงินยังคงอยู่ในบัญชีหลักของคุณ</p><button className="text-link" onClick={() => setTransferResult(null)}>ลองสถานการณ์อื่น <ArrowRight size={16} /></button></div> : <div className="result-detail"><span className="result-symbol warning"><ShieldAlert size={27} /></span><h3>{transferResult.bot_mandated ? 'ต้องยืนยันตัวตนเพิ่ม' : 'พบความเสี่ยงที่ควรรู้'}</h3><p>{transferResult.primary_reason_th || transferResult.direct_risk_reasoning}</p><div className="risk-explanation"><CircleAlert size={17} /><span>รายการยังไม่ถูกโอน คุณเป็นผู้ตัดสินใจ</span></div><div className="auth-actions">{!clearanceToken ? <button className="primary-button" disabled={busy} onClick={verify}><Fingerprint size={18} /> จำลองการยืนยันตัวตน</button> : <button className="primary-button" disabled={busy} onClick={() => decide('PROCEED')}><Check size={18} /> ยืนยันโอนต่อ</button>}<button className="secondary-button" disabled={busy} onClick={() => decide('CANCEL')}><X size={17} /> ยกเลิกรายการ</button></div><small className="auth-note">ขั้นตอนยืนยันตัวตนเป็นการจำลอง ไม่มีการเปิดกล้องหรือสแกนใบหน้าจริง</small></div>}</div><div className="surface aside-card trust-note"><span className="icon-box mint"><LockKeyhole size={21} /></span><h3>ปลอดภัยตั้งแต่ก่อนโอน</h3><p>รายการปกติผ่านได้ทันที ส่วนรายการที่น่าสงสัยแสดงเหตุผลให้เห็นก่อนตัดสินใจ</p></div></aside></div>}
          </> : null}
          <footer className="page-footer"><span>FlowSense × TrustGraph · Prototype experience</span><span>Inspired by everyday banking · ไม่ใช่ผลิตภัณฑ์ทางการของ KBank</span></footer>
        </main>
        <nav className="mobile-nav" aria-label="เมนูหลักบนมือถือ">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => openTab(id)}><Icon size={21} strokeWidth={2} /><span>{label}</span></button>)}</nav>
      </div>
    </div>
  );
}

export default App;
