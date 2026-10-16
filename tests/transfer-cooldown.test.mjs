import test from 'node:test';
import assert from 'node:assert/strict';
import { remainingCooldown, formatCooldown } from '../src/ui/transferCooldown.mjs';

test('countdown uses server time and monotonic elapsed milliseconds', () => {
  const review = { cooldown_required: true, server_now: 100, cooldown_ends_at: 1000 };
  assert.equal(remainingCooldown(review), 900);
  assert.equal(remainingCooldown(review, 899999), 1);
  assert.equal(remainingCooldown(review, 900000), 0);
  assert.equal(remainingCooldown(review, 1000000), 0);
});

test('ordinary transfers and invalid server clocks do not falsely show ready', () => {
  assert.equal(remainingCooldown(null), 0);
  assert.equal(remainingCooldown({ cooldown_required: false }), 0);
  assert.equal(remainingCooldown({ cooldown_required: true }), Infinity);
});

test('timer labels retain minutes and seconds at boundaries', () => {
  assert.equal(formatCooldown(900), '15:00');
  assert.equal(formatCooldown(61), '01:01');
  assert.equal(formatCooldown(0), '00:00');
  assert.equal(formatCooldown(Infinity), '--:--');
});
