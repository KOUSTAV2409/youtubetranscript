import { usePrefersReducedMotion } from "./hooks/usePrefersReducedMotion.js";

/**
 * Critically damped enter (Apple default: no overshoot).
 * Reduced motion → opacity cross-fade only.
 */
export default function SpringIn({ children, className = "", delay = 0, as: Tag = "div", ...rest }) {
  const reduced = usePrefersReducedMotion();
  const motionClass = reduced ? "fade-in" : "spring-in";

  return (
    <Tag
      className={`${motionClass} ${className}`.trim()}
      style={{ "--enter-delay": `${delay}ms` }}
      {...rest}
    >
      {children}
    </Tag>
  );
}
