import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { exportDocument } from "../api/client.js";
import { buildBlocks } from "./model.js";
import { FONT_CSS, PAPER_MM, ruleColor, resolveStyle } from "./templates.js";
import "./resume-paper.css";

// A physical-units stand-in for the exported PDF: same blocks, fonts, sizes
// and gaps (see resume-paper.css), flowed onto real pages the way the PDF
// breaks them. "Exact PDF" swaps in the server's actual file.

const PX_PER_MM = 96 / 25.4;
const PX_PER_PT = 96 / 72;
const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const PREFS_KEY = "ats-preview-prefs-v1";

function loadPrefs() {
  try {
    return JSON.parse(window.localStorage.getItem(PREFS_KEY)) || {};
  } catch {
    return {};
  }
}

function savePrefs(prefs) {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* preferences are a convenience only */
  }
}

export function paperVars(style) {
  const [w, h] = PAPER_MM[style.paper];
  return {
    "--rp-page-w": `${w}mm`,
    "--rp-page-h": `${h}mm`,
    "--rp-margin": `${style.margin}mm`,
    "--rp-font": FONT_CSS[style.font],
    "--rp-fs": style.font_size,
    "--rp-ns": style.name_size,
    "--rp-lh": style.line_height,
    "--rp-accent": style.accent,
    "--rp-rule": ruleColor(style),
    "--rp-header-align": style.header_align,
  };
}

function SmallCaps({ text }) {
  return text.split(" ").map((word, i) => (
    <Fragment key={i}>
      {i > 0 && <span className="rp-sc"> </span>}
      {word.slice(0, 1)}
      {word.length > 1 && <span className="rp-sc">{word.slice(1)}</span>}
    </Fragment>
  ));
}

function BlockContent({ block, previous, style }) {
  switch (block.kind) {
    case "name":
      return <h1 className="rp-name">{block.text}</h1>;
    case "headline":
      return <p className="rp-headline">{block.text}</p>;
    case "contact":
      return <p className="rp-contact">{block.text}</p>;
    case "heading": {
      const align = style.heading_align === "center" ? " rp-heading--center" : "";
      return (
        <h2 className={`rp-heading rp-heading--${style.heading_style}${align}`}>
          {style.heading_case === "smallcaps" ? <SmallCaps text={block.text} /> : block.text}
        </h2>
      );
    }
    case "entry_title":
      return (
        <div className={`rp-entry${previous && previous.kind !== "heading" ? " rp-entry-gap" : ""}`}>
          <h3 className="rp-entry__title">{block.text}</h3>
          {block.aside && <span className="rp-entry__aside">{block.aside}</span>}
        </div>
      );
    case "entry_meta":
      return <p className="rp-meta">{block.text}</p>;
    case "bullet":
      return <p className="rp-bullet">{block.text}</p>;
    case "skill":
      return (
        <p className="rp-skill">
          <span className="rp-skill-label">{block.label}:</span>
          {block.text.slice(block.label.length + 1)}
        </p>
      );
    default:
      return <p className="rp-line">{block.text}</p>;
  }
}

// Flows measured blocks onto pages like export_pdf.py: a heading never ends a
// page (it moves down with the block after it) and loses its top gap when it
// starts one.
function paginate(heights, blocks, style) {
  const [, pageH] = PAPER_MM[style.paper];
  const available = (pageH - 2 * style.margin) * PX_PER_MM;
  const headingGap = style.font_size * style.line_height * 0.75 * PX_PER_PT;
  const pages = [[]];
  let used = 0;
  blocks.forEach((block, i) => {
    const isHeading = block.kind === "heading";
    const need = heights[i] + (isHeading ? heights[i + 1] || 0 : 0);
    if (used > 0 && used + need > available + 0.5) {
      pages.push([]);
      used = 0;
    }
    pages.at(-1).push(i);
    used += heights[i] - (used === 0 && isHeading ? headingGap : 0);
  });
  return pages;
}

function usePages(blocks, style) {
  const measureRef = useRef(null);
  const [pages, setPages] = useState(() => [blocks.map((_, i) => i)]);
  const layoutKey = JSON.stringify([blocks, style]);

  const measure = useCallback(() => {
    const root = measureRef.current;
    if (!root) return;
    const heights = [...root.querySelectorAll(":scope > .rp-page > .rp-block")].map((el) => el.offsetHeight);
    if (heights.length !== blocks.length) return;
    const next = paginate(heights, blocks, style);
    setPages((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- layoutKey captures blocks and style
  }, [layoutKey]);

  useLayoutEffect(measure, [measure]);

  // Web fonts change line breaks once they arrive; measure again then.
  useEffect(() => {
    if (!document.fonts) return undefined;
    let alive = true;
    document.fonts.ready.then(() => alive && measure());
    document.fonts.addEventListener?.("loadingdone", measure);
    return () => {
      alive = false;
      document.fonts.removeEventListener?.("loadingdone", measure);
    };
  }, [measure]);

  return { pages, measureRef };
}

export function ResumePages({ document: doc, guides = false }) {
  const style = useMemo(() => resolveStyle(doc), [doc]);
  const blocks = useMemo(() => buildBlocks(doc, style), [doc, style]);
  const { pages, measureRef } = usePages(blocks, style);

  const renderBlock = (i, pageTop) => (
    <div key={i} className={`rp-block${pageTop ? " is-page-top" : ""}`}>
      <BlockContent block={blocks[i]} previous={blocks[i - 1]} style={style} />
    </div>
  );

  return (
    <div className="rp-pages" style={paperVars(style)}>
      <div className="rp-measure" ref={measureRef} aria-hidden="true">
        <div className="rp-page">{blocks.map((_, i) => renderBlock(i, false))}</div>
      </div>
      {pages.map((indices, p) => (
        <article key={p} className="rp-page" aria-label={`Resume preview, page ${p + 1} of ${pages.length}`}>
          {indices.map((i, j) => renderBlock(i, j === 0 && p > 0))}
          {guides && <div className="rp-guides" aria-hidden="true" />}
          {pages.length > 1 && <span className="rp-page-label" aria-hidden="true">{p + 1} / {pages.length}</span>}
        </article>
      ))}
    </div>
  );
}

// A single, unpaginated first page, used for the template gallery thumbnails.
export function ResumeThumbnail({ document: doc, width }) {
  const style = resolveStyle(doc);
  const blocks = buildBlocks(doc, style);
  const [pageWmm, pageHmm] = PAPER_MM[style.paper];
  const scale = width / (pageWmm * PX_PER_MM);
  return (
    <div className="rp-thumb" style={{ width, height: pageHmm * PX_PER_MM * scale }} aria-hidden="true">
      <div style={{ ...paperVars(style), transform: `scale(${scale})`, transformOrigin: "0 0" }}>
        <div className="rp-page">
          {blocks.map((block, i) => (
            <div key={i} className="rp-block">
              <BlockContent block={block} previous={blocks[i - 1]} style={style} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Content-box size of an element, via a callback ref (the element can mount
// later, e.g. when leaving "Exact PDF"). Whole pixels only, so sub-pixel
// jitter from scaling can't feed back into another resize.
function useElementSize() {
  const [el, setEl] = useState(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    if (!el) return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const width = Math.round(entry.contentRect.width);
      const height = Math.round(entry.contentRect.height);
      setSize((prev) => (prev.width === width && prev.height === height ? prev : { width, height }));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [el]);
  return [setEl, size];
}

// The real server-rendered file. On demand rather than live: export is
// rate-limited, and the live view already tracks every keystroke.
function ExactPdf({ document: doc }) {
  const [state, setState] = useState({ url: null, snapshot: null, loading: false, error: null });
  const snapshot = JSON.stringify(doc);
  const urlRef = useRef(null);

  const render = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const blob = await exportDocument(doc, "pdf", "preview");
      const url = URL.createObjectURL(blob);
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = url;
      setState({ url, snapshot, loading: false, error: null });
    } catch (err) {
      setState((s) => ({ ...s, loading: false, error: err.message }));
    }
  }, [doc, snapshot]);

  useEffect(() => {
    render();
    return () => urlRef.current && URL.revokeObjectURL(urlRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- render once when opened; refreshes are on demand
  }, []);

  const stale = state.url && state.snapshot !== snapshot;
  let message = "This is the exact file you'll download.";
  if (state.loading) message = "Rendering the real PDF…";
  else if (state.error) message = `⚠ ${state.error}`;
  else if (stale) message = "You've edited since this render.";
  return (
    <div className="exact-pdf">
      <div className={`exact-pdf__bar${stale ? " is-stale" : ""}`}>
        <span role="status">{message}</span>
        <button type="button" className="btn-ghost btn-small" onClick={render} disabled={state.loading}>
          ↻ {stale ? "Update" : "Refresh"}
        </button>
      </div>
      {state.url && <iframe className="exact-pdf__frame" title="Exact PDF preview" src={`${state.url}#view=FitH`} />}
    </div>
  );
}

export default function ResumePreview({ document: doc, onExpand, expanded = false }) {
  const [prefs, setPrefs] = useState(() => ({ zoom: "fit", guides: false, ...loadPrefs() }));
  const [exact, setExact] = useState(false);
  const [outerRef, outer] = useElementSize();
  const [innerRef, inner] = useElementSize();
  const style = resolveStyle(doc);
  const empty = buildBlocks(doc, style).length === 0;

  const update = (patch) =>
    setPrefs((p) => {
      const next = { ...p, ...patch };
      savePrefs(next);
      return next;
    });

  const pageW = PAPER_MM[style.paper][0] * PX_PER_MM;
  const fitRaw = outer.width ? Math.min(outer.width / pageW, expanded ? 1.6 : 1.25) : 0.5;
  const fit = Math.max(0.25, Math.floor(fitRaw * 100) / 100);
  const scale = prefs.zoom === "fit" ? fit : prefs.zoom;
  const stepZoom = (dir) => {
    const next = dir > 0
      ? ZOOM_STEPS.find((z) => z > scale + 0.01)
      : [...ZOOM_STEPS].reverse().find((z) => z < scale - 0.01);
    if (next) update({ zoom: next });
  };

  return (
    <div className={`preview${expanded ? " preview--expanded" : ""}`}>
      <div className="preview-toolbar" role="toolbar" aria-label="Preview controls">
        <div className="seg-group">
          <button type="button" className={`seg${!exact ? " is-active" : ""}`} aria-pressed={!exact} onClick={() => setExact(false)}>
            Live
          </button>
          <button type="button" className={`seg${exact ? " is-active" : ""}`} aria-pressed={exact} onClick={() => setExact(true)}
            disabled={empty} title="Render the real PDF on the server">
            Exact PDF
          </button>
        </div>
        {!exact && (
          <>
            <div className="seg-group">
              <button type="button" className="seg" onClick={() => stepZoom(-1)} aria-label="Zoom out">−</button>
              <span className="preview-zoom" aria-live="polite">{Math.round(scale * 100)}%</span>
              <button type="button" className="seg" onClick={() => stepZoom(1)} aria-label="Zoom in">+</button>
              <button type="button" className={`seg${prefs.zoom === "fit" ? " is-active" : ""}`} onClick={() => update({ zoom: "fit" })}>
                Fit
              </button>
            </div>
            <label className="preview-toggle" title="Show the page margins and the centre line">
              <input type="checkbox" checked={prefs.guides} onChange={(e) => update({ guides: e.target.checked })} />
              Guides
            </label>
          </>
        )}
        <span className="preview-paper">{style.paper === "a4" ? "A4" : "US Letter"} · {style.margin} mm margins</span>
        {onExpand && (
          <button type="button" className="btn-ghost btn-small preview-expand" onClick={onExpand}>
            {expanded ? "✕ Close" : "⤢ Full screen"}
          </button>
        )}
      </div>

      {exact ? (
        <ExactPdf document={doc} />
      ) : empty ? (
        <div className="preview-empty">Your resume preview appears here as you type.</div>
      ) : (
        <div className="preview-stage" ref={outerRef}>
          <div className="preview-canvas" style={{ width: pageW * scale, height: inner.height * scale }}>
            <div ref={innerRef} style={{ width: pageW, transform: `scale(${scale})`, transformOrigin: "0 0" }}>
              <ResumePages document={doc} guides={prefs.guides} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
