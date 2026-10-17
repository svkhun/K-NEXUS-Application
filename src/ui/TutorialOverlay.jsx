import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react';
import { positionTutorial } from './tutorialGeometry.mjs';

const storageKey = 'kplus-feature-tour-v1';
export function tutorialWasSeen() { try { return Boolean(localStorage.getItem(storageKey)); } catch { return false; } }
export function rememberTutorial(status) { try { localStorage.setItem(storageKey, status); } catch { /* The tour remains usable when storage is unavailable. */ } }

export const tutorialSteps = [
  { page: 'home', selector: '[data-tour="hero"]', clickSelector: '[data-tour="hero-plan"]', title: 'เริ่มดูแลเงินจากตรงนี้', body: 'เริ่มจากปุ่ม “ดูวิธีให้เงินพอใช้” เพื่อดูเงินที่แบ่งใช้ได้ถึงวันเงินเดือน กดปุ่มนั้นหรือกดถัดไปได้เลย', advanceOnClick: true, interactive: true },
  { page: 'plan', selector: '.budget-presets', title: 'ลองเลือกงบสักยอด', body: 'กด ฿300, ฿500 หรือ ฿1,000 เพื่อทดลองใช้จ่ายต่อวัน แล้วไปดูว่าเงินก่อนเงินเดือนจะเหลือเท่าไร', advanceOnClick: true, interactive: true },
  { page: 'plan', selector: '.budget-result', title: 'อ่านผลของงบที่เลือก', body: 'ยอดนี้คำนวณจากงบในช่องด้านบน พร้อมบอกว่ายังรักษาเงินสำรองได้หรือไม่ เปลี่ยนงบเพื่อเปรียบเทียบได้ โดยไม่มีการหักเงิน' },
  { page: 'plan', selector: '.reserve-edit-row', title: 'เงินสำรอง คุณเลือกเองได้', body: 'ปรับยอดเผื่อฉุกเฉิน แล้วกดดูผลก่อนใช้ยอดนี้ เพื่อเทียบงบก่อน–หลัง เงินยังอยู่ในบัญชีหลักและไม่ถูกล็อก ต้องกดยืนยันแยกต่างหากจึงบันทึกยอดใหม่', interactive: true },
  { page: 'transfer', selector: '#transfer-submit', title: 'เห็นผลก่อนเงินออก', body: 'เตรียมรายการสมมติให้แล้ว ปุ่มนี้ตรวจผู้รับพร้อมคำนวณผลต่อแผนเงิน กดลองดูผลตรวจตัวอย่างได้ ขั้นนี้ยังไม่หักเงินและไม่ยืนยันโอน', interactive: true },
  { page: 'transfer', selector: '.transfer-review-dialog .impact-comparison', fallback: '.review-dialog-header', title: 'เปรียบเทียบก่อน–หลังโอน', body: 'ดูว่างบใช้ชีวิตต่อวันเปลี่ยนเท่าไร แล้วอ่านเหตุผลที่ควรตรวจผู้รับในหน้าต่างนี้ คุณยกเลิกได้ และไม่ต้องรอครบเวลาพักเพื่อเรียนรู้ตัวอย่างนี้' },
  { page: 'savings', selector: '.withdrawal-balance', title: 'ใช้เงินออมเมื่อจำเป็น', body: 'คุณเลือกถอนบางส่วนหรือทั้งหมดกลับเข้าบัญชีหลักได้ ต้องกรอกจำนวนและยืนยันเอง การถอนย้ายเงินเดิมกลับมาใช้ ไม่ได้เพิ่มยอดเงินรวม' },
  { page: 'savings', selector: '.savings-consent', title: 'ออมเฉพาะตอนที่พร้อม', body: 'ระบบกันบิล ค่าใช้ชีวิต และเงินสำรองก่อนแนะนำยอดออม คุณเลือกเปิดใช้งานและยืนยันออมเอง จบการแนะนำแล้วกลับไปลองเมนูต่าง ๆ ได้เลย' },
];

const focusable = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], summary';
export default function TutorialOverlay({ stepIndex, busy, error, onNext, onBack, onSkip, nextLabel }) {
  const step = tutorialSteps[stepIndex];
  const host = stepIndex === 5 ? document.querySelector('.transfer-review-dialog') || document.body : document.body;
  const layer = useRef(null);
  const panel = useRef(null);
  const target = useRef(null);
  const [layout, setLayout] = useState(null);
  const [missing, setMissing] = useState(false);
  const callbacks = useRef({ onNext, onSkip, busy });
  callbacks.current = { onNext, onSkip, busy };

  // Native modal dialogs occupy the browser top layer. Keep this coach mark
  // inside that dialog and use a manual popover to escape its scrolling clip.
  useLayoutEffect(() => {
    const element = layer.current;
    element.showPopover?.();
    return () => { if (element.matches(':popover-open')) element.hidePopover(); };
  }, [host]);

  useLayoutEffect(() => {
    let frame, observer, active = true, scrolled = false;
    setMissing(false); setLayout(null);
    const measure = () => {
      frame = undefined;
      if (!active) return;
      const element = document.querySelector(step.selector) || (step.fallback && document.querySelector(step.fallback));
      if (!element || !element.getBoundingClientRect().width) { target.current = null; return; }
      target.current = element;
      if (!scrolled) { element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }); scrolled = true; }
      const box = element.getBoundingClientRect();
      const next = positionTutorial(box, { width: document.documentElement.clientWidth, height: window.innerHeight }, panel.current?.getBoundingClientRect().height || 240);
      setLayout((current) => JSON.stringify(current) === JSON.stringify(next) ? current : next);
      setMissing(false);
      if (observer) { observer.disconnect(); observer = null; }
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(measure); };
    const resize = new ResizeObserver(schedule);
    if (panel.current) resize.observe(panel.current);
    observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    window.addEventListener('scroll', schedule, true);
    window.addEventListener('resize', schedule);
    window.visualViewport?.addEventListener('resize', schedule);
    const timer = setTimeout(() => { if (!target.current) setMissing(true); }, 2000);
    panel.current?.focus({ preventScroll: true });
    measure();
    return () => { active = false; cancelAnimationFrame(frame); clearTimeout(timer); observer?.disconnect(); resize.disconnect(); window.removeEventListener('scroll', schedule, true); window.removeEventListener('resize', schedule); window.visualViewport?.removeEventListener('resize', schedule); };
  }, [step, host]);
  useEffect(() => { if (layout) panel.current?.focus({ preventScroll: true }); }, [stepIndex, Boolean(layout)]);

  useEffect(() => {
    const onClick = (event) => {
      if (step.advanceOnClick && target.current?.contains(event.target) && (!step.clickSelector || event.target.closest(step.clickSelector))) callbacks.current.onNext();
    };
    const onKey = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); if (!callbacks.current.busy) callbacks.current.onSkip(); return; }
      if (event.key !== 'Tab') return;
      const controls = [...(step.interactive && target.current?.matches(focusable) ? [target.current] : []), ...(step.interactive ? target.current?.querySelectorAll(focusable) || [] : []), ...(panel.current?.querySelectorAll(focusable) || [])].filter((element) => element.getBoundingClientRect().width > 0);
      event.preventDefault();
      if (!controls.length) return;
      const current = controls.indexOf(document.activeElement);
      controls[(current + (event.shiftKey ? -1 : 1) + controls.length) % controls.length].focus({ preventScroll: true });
    };
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onKey, true);
    return () => { document.removeEventListener('click', onClick); document.removeEventListener('keydown', onKey, true); };
  }, [step]);
  useEffect(() => () => { requestAnimationFrame(() => {
    const restore = document.querySelector('.transfer-review-dialog[open] button:not(:disabled)') || document.querySelector('[data-tutorial-launch]') || (target.current?.matches(focusable) ? target.current : target.current?.querySelector(focusable)) || document.querySelector('main button');
    restore?.focus({ preventScroll: true });
  }); }, []);

  const rect = layout?.target;
  const cardStyle = layout?.card || { left: 12, top: 12, width: document.documentElement.clientWidth - 24, maxHeight: window.innerHeight - 24 };
  return createPortal(<div ref={layer} popover="manual" className="tutorial-layer">
    {rect ? <>
      <div className="tutorial-shade" style={{ left: 0, top: 0, width: '100%', height: rect.top }}/>
      <div className="tutorial-shade" style={{ left: 0, top: rect.bottom, width: '100%', bottom: 0 }}/>
      <div className="tutorial-shade" style={{ left: 0, top: rect.top, width: rect.left, height: rect.height }}/>
      <div className="tutorial-shade" style={{ left: rect.right, top: rect.top, right: 0, height: rect.height }}/>
      <div className="tutorial-spotlight" style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}/>
      {!step.interactive && <div className="tutorial-target-next" aria-hidden="true" onClick={onNext} style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}/>}
      <svg className="tutorial-arrow" aria-hidden="true"><defs><marker id="tutorial-arrow-tip" markerWidth="7" markerHeight="7" refX="5.5" refY="3.5" orient="auto"><path d="M0 0L6 3.5L0 7" fill="none" stroke="#fff3cc" strokeWidth="1.5"/></marker></defs><path d={`M${layout.from.join(' ')} L${layout.to.join(' ')}`} stroke="#fff3cc" strokeWidth="3" fill="none" markerEnd="url(#tutorial-arrow-tip)"/></svg>
    </> : <div className="tutorial-shade tutorial-shade-full"/>}
    <section ref={panel} className="tutorial-popover" role="dialog" aria-modal="false" aria-labelledby="tutorial-title" aria-describedby="tutorial-body" tabIndex={-1} style={{ ...cardStyle, visibility: layout || missing ? 'visible' : 'hidden' }}>
      <div className="tutorial-topline"><span>แนะนำวิธีใช้ · {stepIndex + 1}/{tutorialSteps.length}</span><button aria-label="ข้าม tutorial" disabled={busy} onClick={onSkip}><X size={19}/></button></div>
      <h2 id="tutorial-title">{step.title}</h2>
      <p id="tutorial-body">{step.body}</p>
      {missing && <p className="tutorial-error" role="alert">ยังไม่พบจุดที่จะแนะนำ ลองย้อนกลับ หรือข้ามเพื่อใช้งานเองได้</p>}
      {error && <p className="tutorial-error" role="alert">{error}</p>}
      <div className="tutorial-progress" aria-label={`ขั้นที่ ${stepIndex + 1} จาก ${tutorialSteps.length}`}>{tutorialSteps.map((_, index) => <i key={index} className={index <= stepIndex ? 'visited' : ''}/>)}</div>
      <div className="tutorial-buttons"><button className="tutorial-back" disabled={stepIndex === 0 || busy} onClick={onBack}><ArrowLeft size={15}/>ย้อนกลับ</button><button className="tutorial-next" disabled={busy || (missing && stepIndex === 4)} onClick={onNext}>{busy ? 'กำลังตรวจ…' : nextLabel || (stepIndex === tutorialSteps.length - 1 ? 'จบการแนะนำ' : 'ถัดไป')}{stepIndex === tutorialSteps.length - 1 ? <Check size={17}/> : <ArrowRight size={17}/>}</button></div>
      <button className="tutorial-skip" disabled={busy} onClick={onSkip}>ข้ามไปลองเอง</button>
    </section>
  </div>, host);
}
