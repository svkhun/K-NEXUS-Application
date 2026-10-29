"""Date-keyed non-bill history; unknown coverage is never fabricated as zero."""
from datetime import timedelta
import copy
import numpy as np
from src.flowsense_engine import commitments, next_payday
from src.model_package import CATEGORIES


def aggregate_non_bill(transactions, complete_dates=()):
    history = {day: 0.0 for day in complete_dates}
    for row in transactions:
        category = CATEGORIES.get(row['category'])
        if category is None:
            raise ValueError('Unknown transaction category')
        day = row['date']
        # A partial date is not asserted complete by the presence of a transaction.
        if day in history and category == 'non_bill' and row['direction'] == 'DR':
            history[day] += abs(float(row['amount']))
    return history


def flow_features(target, history, prof, state):
    payday = target.replace(day=28)
    days = 0 if target.day == 28 else (next_payday(target).date() - target.date()).days
    rows = commitments(prof, target + timedelta(days=6), copy.deepcopy(state))
    due = float(any(target.date().isoformat() <= b['due_date'] <= (target + timedelta(days=6)).date().isoformat()
                    and b['amount'] > 0 for b in rows))
    lags = [history.get((target - timedelta(days=n)).strftime('%Y-%m-%d'), np.nan) for n in (1, 3, 7)]
    return np.array([[days, due, float(target.weekday() >= 5), *lags]], dtype=np.float32)


def recursive_spending(now, history, prof, state, predict, days=30):
    values = dict(history)
    result = []
    for offset in range(1, days + 1):
        target = now + timedelta(days=offset)
        prediction = max(0.0, float(predict(flow_features(target, values, prof, state))))
        values[target.strftime('%Y-%m-%d')] = prediction
        result.append((target, prediction))
    return result
