const cents = (value) => Math.round(value * 100) / 100;

export function spendingOutlook(timeline = [], paydayDate) {
  const future = timeline.filter(p => p.is_future).sort((a, b) => a.date.localeCompare(b.date));
  const beforePayday = future.filter(p => p.date < paydayDate);
  return {
    tomorrow: future[0] || null,
    average: beforePayday.length && beforePayday.every(p => typeof p.predicted_spend === 'number' && Number.isFinite(p.predicted_spend)) ? cents(beforePayday.reduce((sum, p) => sum + p.predicted_spend, 0) / beforePayday.length) : null,
    days: beforePayday.length,
  };
}

// A user-set budget projection: constant daily spending, known bills, no salary
// or vault withdrawals before payday. This is separate from the model forecast.
export function simulateDailyBudget(horizon, amount) {
  if (amount == null || amount === '' || !Number.isFinite(Number(amount)) || Number(amount) < 0 || Number(amount) > 100000) return null;
  if (!['current_balance', 'spent_today', 'days_to_payday', 'emergency_buffer'].every(key => typeof horizon[key] === 'number' && Number.isFinite(horizon[key])) || horizon.days_to_payday < 1 || (horizon.recurring_commitments || []).some(row => typeof row.amount !== 'number' || !Number.isFinite(row.amount))) return null;
  const budget = cents(Number(amount));
  const days = Math.max(1, Number(horizon.days_to_payday));
  let balance = cents(Number(horizon.current_balance) - Math.max(0, budget - Number(horizon.spent_today)));
  const overdueAndToday = (horizon.recurring_commitments || []).filter(row => row.due_days <= 0).reduce((sum, row) => sum + Number(row.amount), 0);
  balance = cents(balance - overdueAndToday);
  let minimum = balance;
  let billAtRisk = overdueAndToday > 0 && balance < 0;
  for (let day = 1; day < days; day++) {
    const bills = (horizon.recurring_commitments || []).filter(row => row.due_days === day).reduce((sum, row) => sum + Number(row.amount), 0);
    balance = cents(balance - budget - bills);
    if (bills > 0 && balance < 0) billAtRisk = true;
    minimum = Math.min(minimum, balance);
  }
  const shortfall = cents(Math.max(0, Number(horizon.emergency_buffer) - minimum));
  return { budget, endBalance: balance, minimum, shortfall, billAtRisk, withinReserve: shortfall === 0 };
}
