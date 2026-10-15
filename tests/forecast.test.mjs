import test from 'node:test';
import assert from 'node:assert/strict';
import { bangkokDate, buildForecastView, cashOut, niceAxis, paydayCountdown } from '../src/ui/forecastModel.mjs';

const timeline = [
  { date: '2026-10-24', is_past: true, projected_balance: -100 },
  { date: '2026-10-25', is_today: true, projected_balance: 5000 },
  { date: '2026-10-26', is_future: true, projected_balance: 300, predicted_spend: 200, commitment_payment: 4500 },
  { date: '2026-10-27', is_future: true, projected_balance: 250, predicted_spend: 50 },
  { date: '2026-10-28', is_future: true, projected_balance: 24000, salary_inflow: 24000 },
  { date: '2026-10-29', is_future: true, projected_balance: -2000 },
];

test('minimum before payday excludes history, payday inflow and the next cycle', () => {
  const view = buildForecastView(timeline);
  assert.equal(view.minimum.date, '2026-10-27');
  assert.equal(view.minimum.projected_balance, 250);
  assert.equal(view.payday.date, '2026-10-28');
});

test('changing the visible range retains payday insights beyond that range', () => {
  const view = buildForecastView([...timeline].reverse(), 1, false);
  assert.deepEqual(view.points.map((point) => point.date), ['2026-10-25', '2026-10-26']);
  assert.equal(view.todayIndex, 0);
  assert.equal(view.payday.date, '2026-10-28');
  assert.equal(view.minimum.projected_balance, 250);
  assert.equal(buildForecastView([]).minimum, null);
});

test('expense bars include fixed debits and choose historical simulated spend correctly', () => {
  assert.equal(cashOut(timeline[2]), 4700);
  assert.equal(cashOut({ is_past: true, actual_spend: 50, predicted_spend: 100, commitment_payment: 20 }), 70);
  assert.equal(cashOut({ salary_inflow: 24000 }), 0);
});

test('axes include zero and do not clip deficits or produce an empty range', () => {
  for (const [minimum, maximum] of [[-3500, 24000], [0, 0], [-5000, -100]]) {
    const axis = niceAxis(minimum, maximum);
    assert.ok(axis.min <= minimum);
    assert.ok(axis.max >= maximum);
    assert.ok(axis.max > axis.min);
    assert.ok(axis.ticks.includes(0));
  }
});

test('countdown uses the actual instant and Bangkok payday midnight, clamping expired dates', () => {
  const now = new Date('2026-10-15T02:00:00Z');
  assert.deepEqual(paydayCountdown('2026-10-28', now), { days: 12, hours: 15, minutes: 0, seconds: 0 });
  assert.deepEqual(paydayCountdown('2026-10-16', new Date('2026-10-15T16:59:59Z')), { days: 0, hours: 0, minutes: 0, seconds: 1 });
  assert.deepEqual(paydayCountdown('2026-10-14', now), { days: 0, hours: 0, minutes: 0, seconds: 0 });
  assert.equal(paydayCountdown(null, now), null);
});

test('calendar rollover follows Bangkok midnight rather than the browser timezone', () => {
  assert.equal(bangkokDate(new Date('2026-10-15T16:59:59Z')), '2026-10-15');
  assert.equal(bangkokDate(new Date('2026-10-15T17:00:00Z')), '2026-10-16');
  assert.equal(bangkokDate(new Date('2026-12-31T17:00:00Z')), '2027-01-01');
});
