// Real HTTP integration: discard a successful server response, then retry through
// the same command journal used by the UI. No browser or persistent bank state.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { createCommandJournal } from '../src/ui/commandJournal.mjs';

const base=process.env.BASELINE_API_BASE || 'http://127.0.0.1:8000/api/v2';
const response=await fetch(base+'/session');
const session=await response.json();
const cookie=response.headers.get('set-cookie').split(';')[0];
async function request(path,body,key=randomUUID()) {
  const response=await fetch(base+path, {method:body===undefined?'GET':'POST',
    headers:{Cookie:cookie,'Content-Type':'application/json','X-CSRF-Token':session.csrf_token,'X-Idempotency-Key':key},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
  const result=await response.json();
  assert.equal(response.status,200,JSON.stringify(result));
  return result;
}
const source='ACC_0100',target='ACC_0101',amount=100;
const before=await request('/flowsense/profile/'+source);
const review=await request('/trustgraph/evaluate-transfer',{source_account_id:source,target_account_id:target,amount,
  is_first_time_transfer:0,session_duration_sec:90,ratio_to_daily_avg:1.1});
assert.equal(review.status,'TRANSFER_REVIEW');
const memory=new Map();
let lose=true,serverResult;
const keys=[];
const journal=createCommandJournal({
  storage:{getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)},
  uuid:randomUUID,session:async()=>({id:session.session_id,csrf:session.csrf_token}),
  async send(path,body,key) {
    keys.push(key);
    const result=await request(path,body,key);
    if(lose){lose=false;serverResult=result;throw new TypeError('Simulated lost response AFTER server debit');}
    return result;
  },
});
const result=await journal.post('/trustgraph/confirm-transfer',{source_account_id:source,target_account_id:target,amount,
  decision:'PROCEED',review_token:review.review_token});
assert.equal(result.receipt_id,serverResult.receipt_id);
assert.equal(keys.length,2);
assert.equal(keys[0],keys[1]);
assert.equal(journal.pending(),null);
const after=await request('/flowsense/profile/'+source);
assert.equal(after.main_balance,Math.round((before.main_balance-amount)*100)/100);
assert.equal(after.events.filter(e=>e.event_type==='TRANSFER_EXECUTED').length,1);
const report={passed:true,transport:'REAL_HTTP_LOCALHOST',lost_response:'discarded after receiving successful server mutation',
  attempts:keys.length,same_key:keys[0]===keys[1],debit_count:1,receipt_replayed:true,
  before:before.main_balance,after:after.main_balance};
await writeFile(process.env.BASELINE_RETRY_OUTPUT || new URL('../artifacts/acceptance-2026-10-27/retry-http.json',import.meta.url),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
