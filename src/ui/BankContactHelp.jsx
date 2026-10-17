import React from 'react';
import { ExternalLink, Phone, ShieldCheck } from 'lucide-react';

// Official KBank contact details checked on 17 October 2026.
const CONTACT_URL = 'https://www.kasikornbank.com/th/contact/pages/k-contact-center.aspx';

export default function BankContactHelp({ pending, headingRef, hidden }) {
  return <section className="bank-contact-help" id="bank-contact-help" aria-labelledby="bank-contact-heading" hidden={hidden}>
    <span className="bank-contact-kicker"><ShieldCheck size={18} /> สอบถามก่อนตัดสินใจโอน</span>
    <h3 id="bank-contact-heading" ref={headingRef} tabIndex={-1}>ติดต่อธนาคารเพื่อตรวจสอบ</h3>
    <p>หากยังไม่มั่นใจผู้รับ ให้สอบถามเจ้าหน้าที่ผ่านช่องทางทางการ หรือยกเลิกรายการแล้วตรวจสอบผู้รับเพิ่มเติม</p>
    <p className="bank-contact-demo">เว็บนี้เป็นต้นแบบ ไม่ได้เชื่อมต่อเจ้าหน้าที่หรือส่งข้อมูลรายการให้ธนาคาร ไม่จำเป็นต้องโทรจริงเพื่อทดลองใช้งาน</p>
    <div className="bank-contact-channel">
      <span>ธนาคารกสิกรไทย · K-Contact Center</span>
      <strong>02-888-8888</strong>
      <p>ให้บริการตลอด 24 ชั่วโมง<br />สอบถามเรื่องภัยจากมิจฉาชีพ กด 00 ตามเมนูเสียง</p>
      <a className="primary-button" href="tel:028888888" aria-describedby="bank-call-note"><Phone size={18} /> โทร 02-888-8888</a>
      <small id="bank-call-note">เปิดแอปโทรศัพท์เพื่อโทรจริง อาจมีค่าบริการตามเครือข่าย</small>
    </div>
    <a className="bank-contact-source" href={CONTACT_URL} target="_blank" rel="noopener noreferrer" aria-label="ตรวจสอบช่องทางบนเว็บไซต์ธนาคาร (เปิดแท็บใหม่)">ตรวจสอบช่องทางบนเว็บไซต์ธนาคาร <ExternalLink size={15} /></a>
    <div className="bank-contact-before-call">
      <h4>ก่อนคุยกับเจ้าหน้าที่</h4>
      <ul><li>แจ้งว่าพบคำเตือนก่อนโอน พร้อมชื่อผู้รับและยอดเงินที่คุณกำลังตรวจสอบ</li><li>ติดต่อผู้รับผ่านช่องทางที่คุณรู้จักอยู่แล้ว หากยังไม่มั่นใจให้ยกเลิกรายการ</li></ul>
    </div>
    {pending && <p className="bank-contact-pending">ยังไม่มีการหักเงิน · การเปิดช่องทางติดต่อไม่ยกเลิกรายการ และเวลาพักเดิมยังนับต่อ การติดต่อธนาคารไม่ทำให้รายการได้รับการอนุมัติอัตโนมัติ</p>}
  </section>;
}
