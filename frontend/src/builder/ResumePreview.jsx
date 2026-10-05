import { buildBlocks } from "./model.js";

// A close visual stand-in for the exported PDF. Same block order and text as
// the server's layout (see model.js#buildBlocks), so what's previewed is what
// gets scored and downloaded.
export default function ResumePreview({ document }) {
  const blocks = buildBlocks(document);
  if (blocks.length === 0) {
    return <div className="resume-paper resume-paper--empty">Your resume preview appears here as you type.</div>;
  }
  return (
    <article className={`resume-paper resume-paper--${document.template}`} aria-label="Resume preview">
      {blocks.map(([kind, text], i) => {
        switch (kind) {
          case "name":
            return <h1 key={i}>{text}</h1>;
          case "headline":
            return <p key={i} className="rp-headline">{text}</p>;
          case "contact":
            return <p key={i} className="rp-contact">{text}</p>;
          case "heading":
            return <h2 key={i}>{text}</h2>;
          case "entry_title":
            return <h3 key={i}>{text}</h3>;
          case "entry_meta":
            return <p key={i} className="rp-meta">{text}</p>;
          case "bullet":
            return <p key={i} className="rp-bullet">{text}</p>;
          default:
            return <p key={i}>{text}</p>;
        }
      })}
    </article>
  );
}
