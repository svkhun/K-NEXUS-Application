import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Settings2, X } from 'lucide-react';

export default function TransferReviewDialog({ children, busy, pending, error, onClose, onSettings, onCancelTransfer }) {
  const dialog = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    element.showModal();
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected && !previousFocus.disabled && previousFocus !== document.body) previousFocus.focus({ preventScroll: true });
      else document.getElementById('transfer-submit')?.focus({ preventScroll: true });
    };
  }, []);
  useEffect(() => {
    const element = dialog.current;
    if (!busy && element?.open && !element.contains(document.activeElement)) {
      element.querySelector('button:not([disabled])')?.focus({ preventScroll: true });
    }
  }, [busy]);
  const keepFocus = (event) => {
    if (event.key !== 'Tab') return;
    const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],summary,[tabindex]:not([tabindex="-1"])')].filter((node) => node.getClientRects().length > 0);
    if (!controls.length) { event.preventDefault(); return; }
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return createPortal(<dialog ref={dialog} className="transfer-review-dialog" aria-labelledby="transfer-review-title" onKeyDown={keepFocus} onCancel={(event) => { event.preventDefault(); if (!busy) close.current(); }}>
    <header className="review-dialog-header"><div><span>TRUSTGRAPH · รายการทดลอง</span><h2 id="transfer-review-title">ตรวจสอบรายการโอน</h2></div><button className="icon-button" aria-label="ปิดหน้าต่างตรวจสอบ" disabled={busy} onClick={onClose}><X size={21} /></button></header>
    <div className="review-dialog-toolbar"><span>{pending ? 'ปิดหน้าต่างได้ โดยยังไม่ยกเลิกรายการ' : 'ผลการตรวจสอบรายการของคุณ'}</span><button className="text-link" disabled={busy} onClick={onSettings}><Settings2 size={17} /> ตั้งค่าเวลาพัก</button></div>
    {error && <div className="message error" role="alert">{error}</div>}
    <div className="review-dialog-body">{children}</div>
    <footer className="review-dialog-footer">{pending && <button className="secondary-button" disabled={busy} onClick={onCancelTransfer}><X size={17} /> ยกเลิกรายการ</button>}<button className={pending ? 'text-link' : 'primary-button'} disabled={busy} onClick={onClose}>กลับหน้าโอนเงิน</button></footer>
  </dialog>, document.body);
}
