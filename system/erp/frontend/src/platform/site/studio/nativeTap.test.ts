// @vitest-environment jsdom
import { it, expect } from 'vitest';
import { beginTapGesture, trackTapMove, isTapRelease, TAP_SLOP_PX } from './nativeTap';

it('a stationary touch stays a tap and selects on release', () => {
  let tap = beginTapGesture(7, 100, 200, 'node-1', false);
  tap = trackTapMove(tap, 7, 101, 199);
  expect(tap.moved).toBe(false);
  expect(isTapRelease(tap, 7)).toBe(true);
});

it('a touch that scrolls past the slop is not a tap and never selects', () => {
  let tap = beginTapGesture(7, 100, 200, 'node-1', false);
  tap = trackTapMove(tap, 7, 100, 200 - TAP_SLOP_PX - 1);
  expect(tap.moved).toBe(true);
  expect(isTapRelease(tap, 7)).toBe(false);
  // Once marked moved, coming back to the origin stays non-tap.
  tap = trackTapMove(tap, 7, 100, 200);
  expect(tap.moved).toBe(true);
  expect(isTapRelease(tap, 7)).toBe(false);
});

it('movement at exactly the slop boundary still counts as a tap', () => {
  let tap = beginTapGesture(3, 50, 50, 'node-2', true);
  tap = trackTapMove(tap, 3, 50 + TAP_SLOP_PX, 50);
  expect(tap.moved).toBe(false);
  expect(isTapRelease(tap, 3)).toBe(true);
});

it('a different pointer never cancels or completes the tracked gesture', () => {
  let tap = beginTapGesture(7, 100, 200, 'node-1', false);
  tap = trackTapMove(tap, 9, 500, 500);
  expect(tap.moved).toBe(false);
  expect(isTapRelease(tap, 9)).toBe(false);
  expect(isTapRelease(tap, 7)).toBe(true);
});

it('repeated-template taps keep their repeated flag through tracking', () => {
  let tap = beginTapGesture(1, 10, 10, 'node-9', true);
  tap = trackTapMove(tap, 1, 12, 11);
  expect(tap.repeated).toBe(true);
  expect(tap.nodeId).toBe('node-9');
  expect(isTapRelease(tap, 1)).toBe(true);
});
