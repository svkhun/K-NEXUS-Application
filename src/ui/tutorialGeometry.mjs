const clamp = (value, low, high) => Math.max(low, Math.min(value, Math.max(low, high)));

// All coordinates are viewport coordinates, matching fixed overlays and DOMRect.
export function positionTutorial(rect, viewport, panelHeight) {
  const margin = 12, gap = 22;
  const width = Math.min(350, viewport.width - margin * 2);
  const height = Math.min(panelHeight, viewport.height - margin * 2);
  const left = clamp(rect.left - 6, margin, viewport.width - margin);
  const top = clamp(rect.top - 6, margin, viewport.height - margin);
  const right = clamp(rect.right + 6, left, viewport.width - margin);
  const bottom = clamp(rect.bottom + 6, top, viewport.height - margin);
  const target = { left, top, right, bottom, width: right - left, height: bottom - top };
  let x, y, side;
  if (viewport.width >= 800 && viewport.width - right - gap - margin >= width) {
    side = 'right'; x = right + gap; y = clamp((top + bottom - height) / 2, margin, viewport.height - height - margin);
  } else if (viewport.width >= 800 && left - gap - margin >= width) {
    side = 'left'; x = left - gap - width; y = clamp((top + bottom - height) / 2, margin, viewport.height - height - margin);
  } else {
    x = clamp((left + right - width) / 2, margin, viewport.width - width - margin);
    const below = viewport.height - bottom - gap - margin;
    const above = top - gap - margin;
    side = below >= height || below >= above ? 'below' : 'above';
    y = clamp(side === 'below' ? bottom + gap : top - gap - height, margin, viewport.height - height - margin);
  }
  const from = side === 'right' ? [x - 5, y + height / 2] : side === 'left' ? [x + width + 5, y + height / 2] : [clamp((left + right) / 2, x + 20, x + width - 20), side === 'below' ? y - 5 : y + height + 5];
  const to = side === 'right' ? [right + 3, (top + bottom) / 2] : side === 'left' ? [left - 3, (top + bottom) / 2] : [(left + right) / 2, side === 'below' ? bottom + 3 : top - 3];
  return { target, card: { left: x, top: y, width, maxHeight: viewport.height - margin * 2 }, from, to, side };
}
