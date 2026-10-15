// Derive chart insights from the API timeline, never from illustrative values.
export function bangkokDate(now) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now);
}

export function buildForecastView(timeline = [], days = 30, includeHistory = true) {
  const ordered = [...timeline].sort((a, b) => a.date.localeCompare(b.date));
  const today = ordered.find((point) => point.is_today);
  const history = ordered.filter((point) => point.is_past);
  const future = ordered.filter((point) => point.is_future);
  const payday = future.find((point) => Number(point.salary_inflow) > 0);
  const beforePayday = [today, ...future.filter((point) => !payday || point.date < payday.date)].filter(Boolean);
  const minimum = beforePayday.reduce((lowest, point) => !lowest || Number(point.projected_balance) < Number(lowest.projected_balance) ? point : lowest, null);
  const points = [...(includeHistory ? history : []), ...(today ? [today] : []), ...future.slice(0, days)];
  return { points, today, history, payday, minimum, future, todayIndex: points.findIndex((point) => point.is_today) };
}

export function cashOut(point) {
  return Math.max(0, Number(point.is_past ? point.actual_spend : point.predicted_spend) || 0) + Math.max(0, Number(point.commitment_payment) || 0);
}

export function niceAxis(minimum, maximum, intervals = 4) {
  const raw = Math.max(1, maximum - minimum) / intervals;
  const power = 10 ** Math.floor(Math.log10(raw));
  const fraction = raw / power;
  const step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * power;
  const min = Math.floor(Math.min(0, minimum) / step) * step;
  const max = Math.max(step, Math.ceil(maximum / step) * step);
  const ticks = [];
  for (let value = min; value <= max + step / 100; value += step) ticks.push(value);
  return { min, max, ticks };
}

export function paydayCountdown(paydayDate, now) {
  if (!paydayDate) return null;
  const instant = now.getTime();
  const seconds = Math.max(0, Math.floor((new Date(`${paydayDate}T00:00:00+07:00`).getTime() - instant) / 1000));
  return { days: Math.floor(seconds / 86400), hours: Math.floor(seconds / 3600) % 24, minutes: Math.floor(seconds / 60) % 60, seconds: seconds % 60 };
}
