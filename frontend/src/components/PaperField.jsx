import { useMemo } from "react";

const GLYPHS = ["check", "target"];

function buildParticles(count) {
  return Array.from({ length: count }, (_, i) => {
    const isGlyph = i % 5 === 0;
    const layer = i % 3;
    const duration = 16 + layer * 6 + (i % 7);
    return {
      id: i,
      kind: isGlyph ? GLYPHS[(i / 5) % GLYPHS.length] : "doc",
      left: `${(i * 17 + 7) % 100}%`,
      size: isGlyph ? 14 + (i % 4) * 2 : 22 + (i % 5) * 6,
      duration: `${duration}s`,
      delay: `${(i % 11) * -1.7}s`,
      drift: `${((i % 5) - 2) * 26}px`,
      rotate: `${(i % 7) * 9 - 27}deg`,
      opacity: 0.16 + layer * 0.08,
    };
  });
}

export default function PaperField() {
  const particles = useMemo(() => buildParticles(30), []);

  return (
    <div className="paper-field" aria-hidden="true">
      {particles.map((p) => (
        <span
          key={p.id}
          className={`paper-particle paper-particle--${p.kind}`}
          style={{
            "--left": p.left,
            "--size": `${p.size}px`,
            "--duration": p.duration,
            "--delay": p.delay,
            "--drift": p.drift,
            "--rotate": p.rotate,
            "--opacity": p.opacity,
          }}
        >
          {p.kind === "check" && "✓"}
          {p.kind === "target" && "◎"}
        </span>
      ))}
    </div>
  );
}
