import test from 'node:test';
import assert from 'node:assert/strict';
import { budgetExplanation, returnNotice } from '../src/ui/demoContext.mjs';
import { createCommandJournal } from '../src/ui/commandJournal.mjs';

const plan = {remaining_today:0, current_balance:6000, total_recurring_commitments:4000, emergency_buffer:3000, spent_today:120, daily_safe_limit:0};
test('zero budget is distinct from main money and reasons follow actual inputs', () => {
  assert.match(budgetExplanation(plan), /บิลและเงินสำรอง/);
  assert.match(budgetExplanation({...plan,total_recurring_commitments:0,emergency_buffer:6000}), /สำหรับเงินสำรอง/);
  assert.match(budgetExplanation({...plan,current_balance:0}), /ยอดบัญชีหลัก/);
  assert.match(budgetExplanation({...plan,total_recurring_commitments:0,emergency_buffer:0}), /ใช้ถึงงบ/);
  assert.equal(budgetExplanation({...plan,remaining_today:50}), null);
});
test('missing/null/error inputs cannot become a zero or a confident reserve explanation', () => {
  for (const remaining_today of [undefined,null,NaN]) assert.match(budgetExplanation({...plan,remaining_today}), /ยังไม่พร้อม/);
  assert.match(budgetExplanation({...plan,current_balance:null}), /ข้อมูลประกอบไม่ครบ/);
  assert.equal(returnNotice('NEW',true),'EXPIRED');
  assert.equal(returnNotice('RESUMED',true),'RESUMED');
  assert.equal(returnNotice('NEW',false),'NEW');
});
test('unknown command across reload prevents destructive scenario and reset commands', async () => {
  const store = new Map();
  const options = { storage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},uuid:()=> 'unknown-intent',session:async()=>({id:'original',csrf:'test'}),send:async()=>{throw new Error('response lost');} };
  const original = createCommandJournal(options);
  await assert.rejects(original.post('/trustgraph/confirm-transfer',{amount:1}),{code:'OUTCOME_UNKNOWN'});
  const saved = original.pending();
  const resumed = createCommandJournal(options);
  for (const path of ['/flowsense/scenario','/flowsense/reset-state/ACC_0100']) await assert.rejects(resumed.post(path,{}),{code:'OUTCOME_UNKNOWN'});
  assert.deepEqual(resumed.pending(),saved);
});
