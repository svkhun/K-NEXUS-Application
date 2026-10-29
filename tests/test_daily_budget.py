"""Daily allowance must count a posted expense exactly once and protect reserves."""
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo
from src.flowsense_engine import horizon, demo_now


class DailyBudgetTests(unittest.TestCase):
    def calculate(self, balance, spent, day=25):
        profile = dict(monthly_salary=10000, fixed_debt=0, fixed_rent=1000,
                       fixed_utilities=0, emergency_buffer=1000, avg_daily_spend=100)
        state = dict(main_balance=balance, daily_spent_today=spent)
        with patch('src.flowsense_engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, day, tzinfo=ZoneInfo('Asia/Bangkok'))
            return horizon(profile, state)

    def test_posted_spending_reduces_remaining_once(self):
        before = self.calculate(5000, 0)
        after = self.calculate(4800, 200)
        self.assertEqual(before['daily_safe_limit'], 1000)
        self.assertEqual(after['daily_safe_limit'], 1000)
        self.assertEqual(after['remaining_today'], 800)
        self.assertEqual(before['remaining_today'] - after['remaining_today'], 200)

    def test_spent_over_allowance_and_insufficient_reserves_never_offer_more(self):
        self.assertEqual(self.calculate(3800, 1200)['remaining_today'], 0)
        short = self.calculate(1500, 0)
        self.assertEqual(short['remaining_today'], 0)
        self.assertEqual(short['budget_reserve_shortfall'], 500)

    def test_allowance_rounds_down_and_leaves_bills_and_buffer(self):
        result = self.calculate(5000.01, 0)
        self.assertLessEqual(result['daily_safe_limit'] * result['days_to_payday'], 3000.01)
        self.assertLessEqual(result['remaining_today'], result['spendable_balance'])

    def test_last_day_before_payday_has_one_budget_day(self):
        result = self.calculate(1500, 200, day=27)
        self.assertEqual(result['days_to_payday'], 1)
        # Opening current-month rent remains unpaid after its due date.
        self.assertEqual(result['daily_safe_limit'], 0)
        self.assertEqual(result['remaining_today'], 0)
        self.assertEqual(result['budget_reserve_shortfall'], 500)

    def test_displayed_budget_and_spending_reconcile_to_the_cent(self):
        result = self.calculate(5000, 306.7155)
        self.assertEqual(result['remaining_today'], round(result['daily_safe_limit'] - result['spent_today'], 2))

    def test_new_thai_day_resets_daily_spend_without_changing_balances(self):
        state = dict(main_balance=4800, daily_spent_today=200, spending_date='2026-10-25')
        with patch('src.flowsense_engine.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 26, tzinfo=ZoneInfo('Asia/Bangkok'))
            demo_now(state)
        self.assertEqual(state['daily_spent_today'], 0)
        self.assertEqual(state['main_balance'], 4800)
        self.assertEqual(state['spending_date'], '2026-10-26')
