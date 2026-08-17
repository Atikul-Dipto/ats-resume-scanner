import { useEffect, useState } from "react";

const STEPS = [
  "PARSING DOCUMENT STRUCTURE",
  "CHECKING ATS FORMATTING RULES",
  "SCANNING SECTION HEADERS",
  "EXTRACTING SKILLS & KEYWORDS",
  "CROSS-REFERENCING JOB DESCRIPTION",
  "COMPILING COMPATIBILITY SCORE",
];

export default function LoadingScan() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStepIndex((i) => (i + 1 < STEPS.length ? i + 1 : i));
    }, 1400);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="loading-scan">
      <div className="loading-scan__radar">
        <span className="loading-scan__ring" />
        <span className="loading-scan__ring loading-scan__ring--delay" />
        <span className="loading-scan__core" />
      </div>
      <p className="loading-scan__title">ANALYZING RESUME</p>
      <ul className="loading-scan__log">
        {STEPS.map((step, i) => (
          <li
            key={step}
            className={
              i < stepIndex ? "is-done" : i === stepIndex ? "is-active" : "is-pending"
            }
          >
            <span className="loading-scan__marker">{i < stepIndex ? "✓" : "›"}</span>
            {step}
          </li>
        ))}
      </ul>
    </div>
  );
}
