import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';
const server = await createServer({ server:{middlewareMode:true,hmr:false}, appType:'custom' });
after(async()=>server.close());
const { default:MoneyContext } = await server.ssrLoadModule('/src/ui/DemoMoneyContext.jsx');
const { default:Picker } = await server.ssrLoadModule('/src/ui/ScenarioPicker.jsx');
const { default:Basis } = await server.ssrLoadModule('/src/ui/SpendingBasis.jsx');
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component,props));
test('rendered zero budget states the real main/vault balances and factual bill reason',()=>{
  const html = render(MoneyContext,{profile:{main_balance:6000,vault_balance:1000},horizon:{remaining_today:0,current_balance:6000,total_recurring_commitments:4000,emergency_buffer:3000,spent_today:120,daily_safe_limit:0,savings_capacity:0,savings_estimate:{projected_living_cost:100,fixed_commitments:4000,emergency_buffer:3000}}});
  assert.match(html,/ยอดบัญชีหลัก ฿6,000.00/); assert.match(html,/เงินออม ฿1,000.00/);
  assert.match(html,/บิลและเงินสำรอง/); assert.match(html,/ความสามารถออมเพิ่ม ฿0/);
});
test('rendered null amounts remain unavailable and never pretend to be zero',()=>{
  const html = render(MoneyContext,{profile:{main_balance:null,vault_balance:null},horizon:{remaining_today:null,savings_capacity:null,spending_basis:{reason:'BASELINE_DISABLED'}}});
  assert.doesNotMatch(html,/฿0/); assert.match(html,/ยังไม่พร้อม/); assert.match(html,/BASELINE_DISABLED/);
});
test('visible active scenario comes from server and pending disables destructive choices',()=>{
  const html = render(Picker,{horizon:{scenario:'commitment_risk'},persona:'เมย์',page:'home',pending:true});
  assert.match(html,/สถานการณ์ทดลอง: เงินอาจไม่พอจ่ายบิล/);
  assert.match(html,/<button[^>]+disabled=""[^>]*>กลับค่าเริ่มต้น/);
  assert.match(html,/กลับไปดูรายการ/);
});
test('spending assumptions use distinct language and retain technical method/source/version',()=>{
  const html = render(Basis,{basis:{method:'SCENARIO',daily_non_bill_thb:350,source:'config/baseline-personas.v1.json',source_version:'v1'}});
  assert.match(html,/สมมติฐานรายจ่าย/); assert.match(html,/350/); assert.match(html,/data-spending-method="SCENARIO"/);
  assert.match(html,/config\/baseline-personas.v1.json/); assert.match(html,/v1/);
});
test('actual App renders loading before data, without invented zero balances',async()=>{
  globalThis.window = {sessionStorage:{getItem:()=>null}};
  try {
    const { default:App } = await server.ssrLoadModule('/src/ui/App.jsx');
    const html = render(App,{});
    assert.match(html,/กำลังโหลดข้อมูลจำลอง/);
    assert.doesNotMatch(html,/฿0|฿ 0/);
  } finally { delete globalThis.window; }
});
