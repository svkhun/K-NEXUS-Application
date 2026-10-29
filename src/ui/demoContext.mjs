const known = value => typeof value === 'number' && Number.isFinite(value);
export function budgetExplanation(horizon) {
  if (!known(horizon.remaining_today)) return 'ยังไม่พร้อมแสดงงบใช้เพิ่มวันนี้ กรุณาลองโหลดข้อมูลอีกครั้ง';
  if (horizon.remaining_today !== 0) return null;
  if (![horizon.current_balance, horizon.total_recurring_commitments, horizon.emergency_buffer, horizon.spent_today, horizon.daily_safe_limit].every(known)) return 'ยังอธิบายงบไม่ได้ เนื่องจากข้อมูลประกอบไม่ครบ กรุณาลองโหลดข้อมูลอีกครั้ง';
  if (horizon.current_balance <= 0) return 'ยอดบัญชีหลักปัจจุบันเป็นศูนย์หรือติดลบ ดูเงินออมและแผนเงินก่อนใช้เพิ่ม';
  if (horizon.total_recurring_commitments + horizon.emergency_buffer >= horizon.current_balance) return `เงินปัจจุบันต้องกันไว้สำหรับ${horizon.total_recurring_commitments > 0 ? 'บิล' : ''}${horizon.total_recurring_commitments > 0 && horizon.emergency_buffer > 0 ? 'และ' : ''}${horizon.emergency_buffer > 0 ? 'เงินสำรอง' : ''} ยอดนี้จึงเป็นงบใช้เพิ่มวันนี้`;
  if (horizon.spent_today >= horizon.daily_safe_limit) return 'ใช้ถึงงบที่แบ่งไว้สำหรับวันนี้แล้ว เงินส่วนที่เหลือยังอยู่ในบัญชีหลัก';
  return 'งบที่แบ่งใช้เพิ่มวันนี้ต่ำกว่า 1 สตางค์ ดูรายละเอียดแผนเงินก่อนใช้เพิ่ม';
}
export function returnNotice(lifecycle, hadSession) {
  return lifecycle === 'RESUMED' ? 'RESUMED' : hadSession ? 'EXPIRED' : 'NEW';
}
