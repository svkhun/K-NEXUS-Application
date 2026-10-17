const base = '/api/v2';
let sessionPromise;

function ensureSession() {
  if (!sessionPromise) {
    sessionPromise = fetch(`${base}/session`, { credentials: 'same-origin' })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? 'ไม่สามารถเริ่ม session ทดลองได้');
        return body.csrf_token;
      })
      .catch((error) => { sessionPromise = undefined; throw error; });
  }
  return sessionPromise;
}

async function request(path, options = {}) {
  const csrf = await ensureSession();
  const response = await fetch(`${base}${path}`, {
    ...options,
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...options.headers, 'X-CSRF-Token': csrf },
  });
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) {
    if (body.code === 'SESSION_EXPIRED') sessionPromise = undefined;
    const detail = body.detail ?? body.message;
    const error = new Error(typeof detail === 'string' ? detail : 'ไม่สามารถเชื่อมต่อกับระบบทดลองได้');
    error.code = body.code;
    throw error;
  }
  return body;
}

const post = (path, body) => request(path, {
  method: 'POST', body: JSON.stringify(body),
  headers: { 'X-Idempotency-Key': crypto.randomUUID() },
});

export const api = {
  profile: (id) => request(`/flowsense/profile/${id}`),
  horizon: (id) => request(`/flowsense/horizon-status/${id}`),
  forecast: (id) => request(`/flowsense/forecast-30d/${id}`),
  sweep: (id, amount) => post('/flowsense/micro-sweep', { account_id: id, custom_sweep_amount: amount }),
  withdraw: (id, amount) => post('/flowsense/vault/withdraw', { account_id: id, amount }),
  scenario: (id, scenario) => post('/flowsense/scenario', { account_id: id, scenario }),
  savingsPreference: (id, enabled) => post('/flowsense/savings-preference', { account_id: id, enabled }),
  insights: () => request('/demo/insights'),
  reset: (id) => post(`/flowsense/reset-state/${id}`),
  evaluate: (payload) => post('/trustgraph/evaluate-transfer', payload),
  verify: (payload) => post('/trustgraph/verify-micro-auth', payload),
  confirm: (payload) => post('/trustgraph/confirm-transfer', payload),
  transferPreference: (id, enabled) => post('/trustgraph/transfer-preference', { account_id: id, enabled }),
  pendingTransfer: (id) => request(`/trustgraph/pending-transfer/${id}`),
};
