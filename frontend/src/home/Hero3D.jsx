import { useEffect, useRef, useState } from "react";

function webglAvailable() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

// three.js is imported only here, on demand, so the rest of the app never
// downloads it. Without WebGL, a static illustrated fallback shows instead.
export default function Hero3D({ score = 92, onCardClick }) {
  const mountRef = useRef(null);
  const clickRef = useRef(onCardClick);
  const [mode, setMode] = useState("loading"); // loading | ready | fallback

  useEffect(() => {
    clickRef.current = onCardClick;
  }, [onCardClick]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    if (!webglAvailable()) {
      setMode("fallback");
      return undefined;
    }
    let dispose = () => {};
    let cancelled = false;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    Promise.all([import("three"), import("./heroScene.js")])
      .then(([THREE, { buildHeroScene }]) => {
        if (cancelled) return;
        dispose = buildHeroScene(THREE, mount, {
          score,
          reducedMotion,
          onCardClick: () => clickRef.current?.(),
        });
        setMode("ready");
      })
      .catch(() => !cancelled && setMode("fallback"));
    return () => {
      cancelled = true;
      dispose();
    };
  }, [score]);

  return (
    <div className={`hero3d hero3d--${mode}`} ref={mountRef} aria-hidden="true">
      {mode !== "ready" && (
        <div className="hero3d__fallback">
          <div className="hero3d__fallback-card">
            <span className="hero3d__avatar">P</span>
            <span className="hero3d__lines" />
          </div>
          <div className="hero3d__fallback-score">{score}</div>
        </div>
      )}
    </div>
  );
}
