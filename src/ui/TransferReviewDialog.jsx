import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, Phone, Settings2, X } from 'lucide-react';
import BankContactHelp from './BankContactHelp';

export default function TransferReviewDialog({ children, busy, pending, canContactBank, error, onClose, onSettings, onCancelTransfer }) {
  const dialog = useRef(null);
  const body = useRef(null);
  const contactHeading = useRef(null);
  const contactButton = useRef(null);
  const reviewScroll = useRef(0);
  const [showContact, setShowContact] = useState(false);
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
  useEffect(() => {
    if (!canContactBank) setShowContact(false);
  }, [canContactBank]);
  useEffect(() => {
    if (showContact) {
      body.current.scrollTop = 0;
      contactHeading.current?.focus({ preventScroll: true });
    }
  }, [showContact]);
  const toggleContact = () => {
    if (!showContact) reviewScroll.current = body.current.scrollTop;
    else requestAnimationFrame(() => {
      if (!body.current) return;
      body.current.scrollTop = reviewScroll.current;
      contactButton.current?.focus({ preventScroll: true });
    });
    setShowContact((current) => !current);
  };
  const keepFocus = (event) => {
    if (event.defaultPrevented || event.key !== 'Tab') return;
    const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],summary,[tabindex]:not([tabindex="-1"])')].filter((node) => node.getClientRects().length > 0 && !node.closest('[hidden]'));
    if (!controls.length) { event.preventDefault(); return; }
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };
  return createPortal(<dialog ref={dialog} className="transfer-review-dialog" aria-labelledby="transfer-review-title" onKeyDown={keepFocus} onCancel={(event) => { event.preventDefault(); if (!busy) close.current(); }}>
    <header className="review-dialog-header"><div><span>FlowSense × TrustGraph · รายการทดลอง</span><h2 id="transfer-review-title">ตรวจสอบข้อมูลก่อนโอน</h2></div><button className="icon-button" aria-label="ปิดหน้าต่างตรวจสอบ" disabled={busy} onClick={onClose}><X size={21} /></button></header>
    <div className="review-dialog-toolbar"><span>{pending ? 'ยังไม่หักเงิน · ปิดหน้าต่างได้โดยยังไม่ยกเลิก' : 'ผลการตรวจสอบรายการของคุณ'}</span><button className="text-link" disabled={busy} onClick={onSettings}><Settings2 size={17} /> ตั้งค่าเวลาพัก</button></div>
    {error && <div className="message error" role="alert">{error}</div>}
    <div className="review-dialog-body" ref={body}>
      {canContactBank && <BankContactHelp pending={pending} headingRef={contactHeading} hidden={!showContact} />}
      <div hidden={showContact && canContactBank}>{children}</div>
    </div>
    <footer className={`review-dialog-footer${canContactBank ? ' with-bank-help' : ''}`}>
      {canContactBank ? <div className="review-dialog-choices">
        {pending && <button className="secondary-button" disabled={busy} onClick={onCancelTransfer}><X size={17} /> ยกเลิกรายการ</button>}
        <button ref={contactButton} className={showContact ? 'secondary-button' : 'primary-button'} disabled={busy} aria-expanded={showContact} aria-controls="bank-contact-help" onClick={toggleContact}>{showContact ? <ArrowLeft size={17} /> : <Phone size={17} />}{showContact ? 'กลับไปดูคำเตือน' : 'ติดต่อธนาคาร'}</button>
      </div> : pending && <button className="secondary-button" disabled={busy} onClick={onCancelTransfer}><X size={17} /> ยกเลิกรายการ</button>}
      <button className={pending || canContactBank ? 'text-link' : 'primary-button'} disabled={busy} onClick={onClose}>กลับหน้าโอนเงิน</button>
    </footer>
  </dialog>, document.body);
}
