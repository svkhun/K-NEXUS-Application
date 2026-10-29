import test from 'node:test';
import assert from 'node:assert/strict';
import { simulateDailyBudget, spendingOutlook } from '../src/ui/dailyPlanModel.mjs';

const horizon = { current_balance: 4800, spent_today: 200, days_to_payday: 3, emergency_buffer: 1000,
  recurring_commitments: [{ due_days: 1, amount: 1000 }, { due_days: 3, amount: 9000 }] };

test('budget plan counts posted spend once, pays bills, and excludes payday debits', () => {
  assert.deepEqual(simulateDailyBudget(horizon, 1000), { budget: 1000, endBalance: 1000, minimum: 1000, shortfall: 0, billAtRisk: false, withinReserve: true });
  assert.equal(simulateDailyBudget(horizon, 1500).endBalance, -500);
  assert.equal(simulateDailyBudget(horizon, 1500).shortfall, 1500);
  assert.equal(simulateDailyBudget(horizon, 3000).billAtRisk, true);
});

test('overspent today cannot be undone by lowering the simulated daily budget', () => {
  const plan = simulateDailyBudget({ ...horizon, spent_today: 1200, current_balance: 3800 }, 500);
  assert.equal(plan.endBalance, 1800);
  for (const invalid of [null, undefined, '', -1, 'bad', Infinity, 100001]) assert.equal(simulateDailyBudget(horizon, invalid), null);
});

test('unknown facts stop manual simulation and forecast-dependent spending averages', () => {
  assert.equal(simulateDailyBudget({...horizon,current_balance:null},100),null);
  assert.equal(simulateDailyBudget({...horizon,recurring_commitments:[{due_days:1,amount:null}]},100),null);
  assert.equal(spendingOutlook([{date:'2026-10-26',is_future:true,predicted_spend:100},{date:'2026-10-27',is_future:true,predicted_spend:null}],'2026-10-28').average,null);
  assert.equal(simulateDailyBudget(horizon,0).budget,0);
});

test('overdue and due-today bills remain reserved exactly once in the budget simulation', () => {
  const bills = [{ id:'old', due_days:-5, amount:700 }, {id:'today',due_days:0,amount:300}, {id:'new',due_days:1,amount:500}];
  const state={current_balance:5000,spent_today:0,days_to_payday:3,emergency_buffer:1000,recurring_commitments:bills};
  assert.equal(simulateDailyBudget(state,500).endBalance,2000);
  assert.equal(simulateDailyBudget(state,500).endBalance,2000);
  assert.equal(bills[0].amount,700);
});

test('predicted spending is drawn from model days, excluding payday and history', () => {
  const view = spendingOutlook([
    { date: '2026-10-25', is_today: true, predicted_spend: 999 },
    { date: '2026-10-28', is_future: true, predicted_spend: 900 },
    { date: '2026-10-27', is_future: true, predicted_spend: 300 },
    { date: '2026-10-26', is_future: true, predicted_spend: 100 },
  ], '2026-10-28');
  assert.equal(view.average, 200);
  assert.equal(view.tomorrow.date, '2026-10-26');
  assert.equal(view.days, 2);
  assert.equal(spendingOutlook([], '2026-10-28').average, null);
});
