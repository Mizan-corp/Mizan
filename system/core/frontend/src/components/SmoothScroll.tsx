import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import type Lenis from "lenis";

interface SmoothScrollProps {
  children: React.ReactNode;
}

// Lenis and GSAP load once the page is idle, and only for a mouse or trackpad (touch screens
// scroll smoothly on their own): they never hold up the first paint or the first tap.
const loadScrollKit = () => Promise.all([import("lenis"), import("@/lib/gsap")]);
const whenIdle = (fn: () => void) =>
  typeof window.requestIdleCallback === "function" ? window.requestIdleCallback(fn, { timeout: 3000 }) : setTimeout(fn, 1500);

export function SmoothScroll({ children }: SmoothScrollProps) {
  const location = useLocation();
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    // Check if user prefers reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion || !window.matchMedia("(pointer: fine)").matches) {
      return;
    }

    let cancelled = false;
    let cleanup = () => {};
    whenIdle(() => void loadScrollKit().then(([{ default: LenisClass }, { gsap, ScrollTrigger }]) => {
      if (cancelled) return;
      const lenis = new LenisClass({
        duration: 1.1,
        easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 1.5,
      });

      lenisRef.current = lenis;

      // Sync Lenis scroll with GSAP ScrollTrigger
      lenis.on("scroll", () => {
        ScrollTrigger.update();
      });

      const tickerCallback = (time: number) => {
        lenis.raf(time * 1000);
      };

      gsap.ticker.add(tickerCallback);
      gsap.ticker.lagSmoothing(0);

      cleanup = () => {
        lenis.destroy();
        gsap.ticker.remove(tickerCallback);
        lenisRef.current = null;
      };
    }));

    return () => {
      cancelled = true;
      cleanup();
    };
  }, []);

  // Reset scroll and refresh ScrollTrigger on route change
  useEffect(() => {
    if (lenisRef.current) {
      lenisRef.current.scrollTo(0, { immediate: true });
    } else {
      window.scrollTo(0, 0);
    }

    // Give react components a moment to mount before recalculating triggers
    const timeout = setTimeout(() => {
      // Only once GSAP is there (desktop, after idle): a phone never downloads it for this.
      if (lenisRef.current) void import("@/lib/gsap").then(({ ScrollTrigger }) => ScrollTrigger.refresh());
    }, 150);

    return () => clearTimeout(timeout);
  }, [location.pathname]);

  return <>{children}</>;
}
