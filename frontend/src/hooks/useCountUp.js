import { useEffect, useRef, useState } from "react";

// Animates from the previous value to `target` (ease-out), so live numbers
// visibly tick up when they change instead of jumping.
export default function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0);
  const from = useRef(0);

  useEffect(() => {
    if (target == null) return undefined;
    const start = performance.now();
    const origin = from.current;
    let raf;
    const tick = (now) => {
      const t = Math.min(Math.max((now - start) / duration, 0), 1);
      const eased = 1 - Math.pow(1 - t, 3);
      const next = origin + (target - origin) * eased;
      setValue(next);
      if (t < 1) raf = requestAnimationFrame(tick);
      else from.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return Math.round(value);
}
