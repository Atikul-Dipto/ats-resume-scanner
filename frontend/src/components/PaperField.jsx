import { useMemo } from "react";

// Kinds cycle so documents dominate, with a folder or a mark every few items.
const KINDS = ["doc", "doc", "folder", "doc", "check", "doc", "doc", "folder", "target", "doc"];

function buildParticles(count) {
  return Array.from({ length: count }, (_, i) => {
    const kind = KINDS[i % KINDS.length];
    const layer = i % 3; // 0 = far, 2 = near
    const glyph = kind === "check" || kind === "target";
    return {
      id: i,
      kind,
      // Alternate sides; --p is how far into the side margin (0 = page edge).
      side: i % 2 ? "right" : "left",
      p: ((i * 7) % 10) / 12,
      size: glyph ? 16 + layer * 4 : 24 + layer * 10 + (i % 4) * 3,
      duration: `${30 - layer * 6 + (i % 5) * 2}s`,
      delay: `${(i * -2.3) % 30}s`,
      drift: `${((i % 7) - 3) * 22}px`,
      spin: `${((i % 9) - 4) * 9}deg`,
      opacity: 0.4 + layer * 0.18,
    };
  });
}

/** Floating resumes and folders behind the scanner, with a scan beam sweeping down. */
export default function PaperField() {
  const particles = useMemo(() => buildParticles(26), []);

  return (
    <div className="paper-field" aria-hidden="true">
      <div className="paper-field__beam" />
      {particles.map((p) => (
        <span
          key={p.id}
          className={`paper paper--${p.kind} paper--${p.side}`}
          style={{
            "--p": p.p,
            "--size": `${p.size}px`,
            "--duration": p.duration,
            "--delay": p.delay,
            "--drift": p.drift,
            "--spin": p.spin,
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
