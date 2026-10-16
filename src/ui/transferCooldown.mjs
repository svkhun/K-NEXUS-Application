// Anchor display time to the server response and monotonic elapsed time.
export function remainingCooldown(review, elapsedMs = 0) {
  if (!review?.cooldown_required) return 0;
  const seconds = Number(review.cooldown_ends_at) - Number(review.server_now);
  if (!Number.isFinite(seconds)) return Infinity;
  return Math.max(0, Math.ceil(seconds - Math.max(0, elapsedMs) / 1000));
}

export function formatCooldown(seconds) {
  if (!Number.isFinite(seconds)) return '--:--';
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
}
