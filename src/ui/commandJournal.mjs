const storageKey = 'k-nexus-pending-command-v1';
const message = 'ยังไม่ทราบผลคำสั่ง อาจบันทึกสำเร็จแล้ว กรุณาลองรับผลเดิมและตรวจยอด/ประวัติ ห้ามสร้างรายการซ้ำ';

export function isDefinitiveRejection(status, recorded) {
  // An admission rejection (e.g. rate limit or stale CSRF) says nothing about
  // an earlier attempt whose response was lost. Only a recorded command result
  // below 500 can conclude this intent without further reconciliation.
  return status >= 400 && status < 500 && recorded === 'recorded';
}

export function createCommandJournal({ storage, uuid, send, session }) {
  let pending = JSON.parse(storage.getItem(storageKey) || 'null');
  let posting = false;
  const save = (value) => {
    if (value) storage.setItem(storageKey, JSON.stringify(value));
    else storage.removeItem(storageKey);
    pending = value;
  };
  const unknown = (cause) => Object.assign(new Error(message), { code: 'OUTCOME_UNKNOWN', cause });
  async function execute() {
    const current = await session();
    if (current.id !== pending.sessionId) {
      throw Object.assign(new Error('session เดิมหมดอายุ ผลคำสั่งเดิมยังยืนยันไม่ได้ จะไม่ส่งซ้ำใน session ใหม่ กรุณาเก็บข้อมูลรายการเพื่อตรวจสอบ'), { code: 'PENDING_SESSION_EXPIRED' });
    }
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const result = await send(pending.path, pending.body, pending.key, current.csrf);
        save(null);
        return result;
      } catch (error) {
        if (error.definitive) { save(null); throw error; }
        if (attempt === 1) throw unknown(error);
      }
    }
  }
  return {
    pending: () => pending,
    retry: () => pending ? execute() : Promise.resolve(null),
    async post(path, body) {
      if (pending || posting) throw unknown();
      posting = true;
      try {
        const current = await session();
        // Persist before sending; storage failure prevents transmission.
        save({ path, body, key: uuid(), sessionId: current.id, createdAt: new Date().toISOString() });
        return await execute();
      } finally { posting = false; }
    },
  };
}
