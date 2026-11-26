import { useEffect } from "react";

let painted = false;

/**
 * An entrance animation's starting state, except on the first page the visitor opens: that page
 * comes pre-rendered (ADR-016) and must show its content at once, as the server drew it (no
 * invisible hero waiting for JavaScript, no hydration mismatch). Pages opened afterwards animate.
 */
export function useEntrance<T>(initial: T): T | false {
  const value = painted ? initial : false;
  useEffect(() => {
    painted = true;
  }, []);
  return value;
}
