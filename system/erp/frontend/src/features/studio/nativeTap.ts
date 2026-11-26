// Touch gestures on the editor canvas: a touch that travels beyond the tap
// slop is a scroll (or cancelled) gesture, never an edit selection. Selection
// is confirmed only when the touch ends where it began, so scrolling the page
// on a phone no longer opens the element under the finger for editing.
export const TAP_SLOP_PX = 10;

export type TapGesture = {
  pointerId: number;
  x: number;
  y: number;
  nodeId: string;
  repeated: boolean;
  moved: boolean;
};

export const beginTapGesture = (
  pointerId: number,
  x: number,
  y: number,
  nodeId: string,
  repeated: boolean,
): TapGesture => ({ pointerId, x, y, nodeId, repeated, moved: false });

// Returns the same gesture untouched for a different pointer (multi-touch:
// a second finger must not cancel or hijack the tracked one).
export const trackTapMove = (
  tap: TapGesture,
  pointerId: number,
  x: number,
  y: number,
): TapGesture => {
  if (tap.pointerId !== pointerId || tap.moved) return tap;
  return Math.hypot(x - tap.x, y - tap.y) > TAP_SLOP_PX ? { ...tap, moved: true } : tap;
};

// True only when the same pointer ends the gesture without passing the slop:
// a real tap. Scrolled or drifted touches do not select.
export const isTapRelease = (tap: TapGesture, pointerId: number): boolean =>
  tap.pointerId === pointerId && !tap.moved;
