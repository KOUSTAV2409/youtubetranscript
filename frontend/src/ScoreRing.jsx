import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "./hooks/usePrefersReducedMotion.js";

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/**
 * Circular worth meter — fills with a critically damped spring (no overshoot).
 * Reduced motion: settle immediately (opacity only).
 */
export default function ScoreRing({ score, verdict }) {
  const reduced = usePrefersReducedMotion();
  const clamped = Math.min(100, Math.max(0, Number(score) || 0));
  const targetOffset = CIRCUMFERENCE - (clamped / 100) * CIRCUMFERENCE;
  const [offset, setOffset] = useState(reduced ? targetOffset : CIRCUMFERENCE);
  const [settled, setSettled] = useState(reduced);

  useEffect(() => {
    if (reduced) {
      setOffset(targetOffset);
      setSettled(true);
      return undefined;
    }

    setSettled(false);
    setOffset(CIRCUMFERENCE);

    // Start from presentation value after paint — spring to target
    let frame = 0;
    let raf = 0;
    const start = performance.now();
    const from = CIRCUMFERENCE;
    const to = targetOffset;
    const response = 0.55; // Apple-ish settle window (seconds)

    // Critically damped exponential ease toward target (no bounce)
    const tick = (now) => {
      const t = Math.min(1, (now - start) / (response * 1000));
      // 1 - e^(-k t) style settle; smoothstep for compositor-friendly path
      const eased = 1 - Math.pow(1 - t, 3);
      setOffset(from + (to - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        setOffset(to);
        setSettled(true);
      }
    };

    frame = requestAnimationFrame(() => {
      raf = requestAnimationFrame(tick);
    });

    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(raf);
    };
  }, [clamped, targetOffset, reduced]);

  return (
    <div
      className={`score-ring verdict-${verdict} ${settled ? "is-settled" : ""}`}
      aria-label={`Worth score ${clamped} out of 100`}
    >
      <svg className="score-svg" viewBox="0 0 100 100" aria-hidden="true">
        <circle className="score-track" cx="50" cy="50" r={RADIUS} />
        <circle
          className="score-progress"
          cx="50"
          cy="50"
          r={RADIUS}
          style={{
            strokeDasharray: CIRCUMFERENCE,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      <div className="score-center">
        <span className="score-num">{clamped}</span>
        <span className="score-den">worth / 100</span>
      </div>
    </div>
  );
}
