import test from 'node:test';
import assert from 'node:assert/strict';
import { createCommandJournal, isDefinitiveRejection } from '../src/ui/commandJournal.mjs';

function fixture(send) {
  const data = new Map();
  const storage = { getItem: k => data.get(k), setItem: (k,v) => data.set(k,v), removeItem: k => data.delete(k) };
  let sequence = 0;
  const options = { storage, uuid: () => `intent-${++sequence}`, send, session: async () => ({ id:'session-one',csrf:'csrf' }) };
  return { options, journal: createCommandJournal(options) };
}

test('server success then lost response retries same key and debits once; new intent uses a new key', async () => {
  let balance = 1000;
  const responses = new Map();
  const keys = [];
  let lose = true;
  const { journal } = fixture(async (path, body, key) => {
    keys.push(key);
    if (!responses.has(key)) {
      balance -= body.amount;
      responses.set(key,{balance});
    }
    if (lose) { lose = false; throw new TypeError('response lost after debit'); }
    return responses.get(key);
  });
  assert.deepEqual(await journal.post('/confirm',{amount:100}),{balance:900});
  assert.deepEqual(keys,['intent-1','intent-1']);
  assert.equal(journal.pending(),null);
  await journal.post('/confirm',{amount:100});
  assert.equal(balance,800);
  assert.equal(keys.at(-1),'intent-2');
});

test('unknown outcome retains exact command across reload, blocks new intents and reconciles', async () => {
  const { options,journal } = fixture(async () => {throw new Error('offline');});
  await assert.rejects(journal.post('/confirm',{amount:120,review_token:'bound'}),{code:'OUTCOME_UNKNOWN'});
  const pending = journal.pending();
  assert.deepEqual(pending.body,{amount:120,review_token:'bound'});
  await assert.rejects(journal.post('/withdraw',{amount:1}),{code:'OUTCOME_UNKNOWN'});
  let received;
  const reloaded=createCommandJournal({...options,send:async (...args)=>{received=args;return {status:'TRANSFER_EXECUTED'};}});
  assert.equal((await reloaded.retry()).status,'TRANSFER_EXECUTED');
  assert.deepEqual(received.slice(0,3),[pending.path,pending.body,pending.key]);
  assert.equal(reloaded.pending(),null);
});

test('expired session never replays an old command in a new session', async () => {
  const {options,journal}=fixture(async()=>{throw new Error('lost');});
  await assert.rejects(journal.post('/confirm',{amount:1}));
  let calls=0;
  const reloaded=createCommandJournal({...options,session:async()=>({id:'different',csrf:'new'}),send:async()=>{calls++;}});
  await assert.rejects(reloaded.retry(),{code:'PENDING_SESSION_EXPIRED'});
  assert.equal(calls,0);
  assert.ok(reloaded.pending());
});

test('definitive rejection clears intent; ambiguous eviction retains it', async () => {
  const {options,journal}=fixture(async()=>{throw Object.assign(new Error('rejected'),{definitive:true});});
  await assert.rejects(journal.post('/confirm',{}));
  assert.equal(journal.pending(),null);
  const other=createCommandJournal({...options,send:async()=>{throw Object.assign(new Error('evicted'),{code:'RESULT_EVICTED'});}});
  await assert.rejects(other.post('/confirm',{}),{code:'OUTCOME_UNKNOWN'});
  assert.ok(other.pending());
});

test('simultaneous UI calls cannot create two commands during session initialization', async () => {
  const {journal}=fixture(async()=>({ok:true}));
  const results=await Promise.allSettled([journal.post('/confirm',{}),journal.post('/confirm',{})]);
  assert.equal(results.filter(r=>r.status==='fulfilled').length,1);
});

test('rate-limit or CSRF admission rejection after a lost response cannot conclude the old command', async () => {
  for (const status of [401,403,409,429,503]) assert.equal(isDefinitiveRejection(status,null),false);
  assert.equal(isDefinitiveRejection(422,'recorded'),true);
  assert.equal(isDefinitiveRejection(500,'recorded'),false);
  let attempt=0;
  const {journal}=fixture(async()=>{
    attempt++;
    if(attempt===1) throw new Error('lost after server debit');
    throw Object.assign(new Error('rate limited before cache'),{definitive:isDefinitiveRejection(429,null)});
  });
  await assert.rejects(journal.post('/confirm',{amount:100}),{code:'OUTCOME_UNKNOWN'});
  assert.ok(journal.pending());
});
