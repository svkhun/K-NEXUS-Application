import test from 'node:test';
import assert from 'node:assert/strict';
import { positionTutorial } from '../src/ui/tutorialGeometry.mjs';

const target = (left, top, width, height) => ({left, top, right: left + width, bottom: top + height});
const inside = (result, width, height, panelHeight) => {
  assert.ok(result.card.left >= 12);
  assert.ok(result.card.left + result.card.width <= width - 12);
  assert.ok(result.card.top >= 12);
  assert.ok(result.card.top + Math.min(panelHeight, height - 24) <= height - 12);
};
test('phone cards fit at either edge and the arrow points back to the highlighted element', () => {
  for (const top of [12, 220, 500, 680]) {
    const result = positionTutorial(target(20, top, 280, 45), {width: 320, height: 740}, 280);
    inside(result, 320, 740, 280);
    assert.ok(result.to[0] >= result.target.left && result.to[0] <= result.target.right);
    assert.ok(Math.abs(result.to[1] - (result.side === 'below' ? result.target.bottom : result.target.top)) <= 3);
  }
});
test('desktop uses free space beside a target rather than covering it', () => {
  const right = positionTutorial(target(200, 300, 300, 100), {width: 1440, height: 1000}, 300);
  const left = positionTutorial(target(1050, 300, 300, 100), {width: 1440, height: 1000}, 300);
  assert.equal(right.side, 'right');
  assert.ok(right.card.left > right.target.right);
  assert.equal(left.side, 'left');
  assert.ok(left.card.left + left.card.width < left.target.left);
});
test('keyboard-sized viewport caps panel height and clips an offscreen target safely', () => {
  const result = positionTutorial(target(-20, -80, 400, 500), {width: 320, height: 400}, 600);
  inside(result, 320, 400, 600);
  assert.equal(result.card.maxHeight, 376);
  assert.ok(result.target.width >= 0 && result.target.height >= 0);
  assert.ok(result.target.right <= 308 && result.target.bottom <= 388);
});
