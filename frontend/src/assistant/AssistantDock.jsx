import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { assistant } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { safeHref } from "../jobs/format.js";
import { useAssistant } from "./AssistantContext.jsx";
import { StaleEdit, applyEdit, revertEdit } from "./edits.js";
import Markdown from "./Markdown.jsx";
import { addLocalMemory, loadLocalMemories, saveLocalMemories } from "./memory.js";

const CHAT_KEY = "prottoy-assistant-chat";
const HISTORY_LIMIT = 20;
const MARK = `${import.meta.env.BASE_URL}brand/prottoy-mark.png`;

const SUGGESTIONS = {
  builder: ["Write my professional summary", "Fix my weakest bullet points", "What's hurting my ATS score?", "Recommend jobs for me"],
  scan: ["Explain my score in plain words", "Rewrite my weakest bullets", "Recommend jobs for me"],
  jobsWithResume: ["Which jobs fit me best?", "Which skills am I missing most?"],
  jobs: ["Find remote software jobs", "Find civil engineering jobs in Bangladesh", "What jobs suit a fresh EEE graduate?"],
  job: ["Am I a good fit for this job?", "Write a cover letter for this job", "Summarize this job for me"],
  market: ["Which skills should I learn next?", "Who is hiring data analysts right now?", "What do these trends mean for my career?"],
  admin: ["Write a job description for a Data Analyst", "Write a JD for a Civil Site Engineer and save it as a draft"],
  other: ["Recommend jobs for a data analyst", "How do I make my resume ATS-friendly?", "Write a job description"],
};

const CONTEXT_LABEL = {
  builder: "Reading your resume in the builder",
  scan: "Reading your scanned resume",
  jobs: "Browsing the job board",
  job: "Looking at this job",
  market: "Reading Work Signal",
  admin: "Admin · job postings",
};

function suggestionsFor(info) {
  if (info.page === "jobs") return info.hasDocument ? SUGGESTIONS.jobsWithResume : SUGGESTIONS.jobs;
  return SUGGESTIONS[info.page] || SUGGESTIONS.other;
}

function loadChat() {
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(CHAT_KEY));
    return Array.isArray(saved) ? saved.map((m) => ({ ...m, streaming: false })) : [];
  } catch {
    return [];
  }
}

function saveChat(messages) {
  try {
    window.sessionStorage.setItem(CHAT_KEY, JSON.stringify(messages.slice(-40)));
  } catch {
    /* storage unavailable */
  }
}

const textOf = (message) =>
  message.role === "user" ? message.text : message.parts.filter((p) => p.type === "text").map((p) => p.text).join("").trim();

let idSeq = 0;
const nextId = () => `m${Date.now().toString(36)}${idSeq++}`;

// ---------- Parts ----------

function StatusLine({ part }) {
  return (
    <div className={`ai-status ${part.done ? "is-done" : ""}`}>
      <span className="ai-status__icon" aria-hidden="true">{part.done ? "✓" : ""}</span>
      {part.label}
      {!part.done && "…"}
    </div>
  );
}

function JobCards({ jobs, onNavigate }) {
  return (
    <div className="ai-jobs">
      {jobs.map((job) => {
        const apply = safeHref(job.apply_url);
        return (
          <div key={job.id} className="ai-job">
            <div className="ai-job__head">
              <div>
                <strong>{job.title}</strong>
                <span>{job.company}{job.location ? ` · ${job.location}` : ""}</span>
              </div>
              {job.match_score != null && (
                <span className={`ai-job__score tier-${job.match_score >= 70 ? "good" : job.match_score >= 40 ? "fair" : "poor"}`}>
                  {Math.round(job.match_score)}%
                </span>
              )}
            </div>
            {job.missing_skills?.length > 0 && (
              <p className="ai-job__gap">Missing: {job.missing_skills.slice(0, 4).join(", ")}</p>
            )}
            <div className="ai-job__actions">
              <Link to={`/jobs/${job.id}`} onClick={onNavigate}>Details</Link>
              {apply && (
                <a href={apply} target="_blank" rel="noopener noreferrer" className="ai-job__apply">Apply ↗</a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Proposal({ part, onEdit, canApply }) {
  const pending = part.edits.filter((e) => e.state === "pending");
  return (
    <div className="ai-proposal">
      {part.note && <p className="ai-proposal__note">{part.note}</p>}
      {part.edits.map((edit, i) => (
        <div key={i} className={`ai-edit is-${edit.state}`}>
          <div className="ai-edit__label">{edit.label}</div>
          {edit.before && <p className="ai-edit__before">{edit.before}</p>}
          <p className="ai-edit__after">{edit.kind === "add_skills" ? `+ ${edit.after}` : edit.after}</p>
          <div className="ai-edit__actions">
            {edit.state === "pending" && (
              <>
                <button type="button" className="ai-btn ai-btn--primary" disabled={!canApply} onClick={() => onEdit(i, "apply")}>Apply</button>
                <button type="button" className="ai-btn" onClick={() => onEdit(i, "skip")}>Dismiss</button>
              </>
            )}
            {edit.state === "applied" && (
              <>
                <span className="ai-edit__state">Applied ✓</span>
                <button type="button" className="ai-btn" disabled={!canApply} onClick={() => onEdit(i, "undo")}>Undo</button>
              </>
            )}
            {edit.state === "skipped" && <span className="ai-edit__state">Dismissed</span>}
            {edit.state === "stale" && <span className="ai-edit__state">That line changed since — ask again for a fresh suggestion.</span>}
          </div>
        </div>
      ))}
      {pending.length > 1 && canApply && (
        <button type="button" className="ai-btn ai-btn--primary ai-proposal__all" onClick={() => onEdit(null, "apply-all")}>
          Apply all {pending.length}
        </button>
      )}
      {!canApply && pending.length > 0 && <p className="ai-proposal__hint">Open the resume in the builder to apply these.</p>}
    </div>
  );
}

function AssistantMessage({ message, onEdit, canApply, onNavigate }) {
  return (
    <div className="ai-msg ai-msg--assistant">
      <img className="ai-msg__avatar" src={MARK} alt="" aria-hidden="true" />
      <div className="ai-msg__body">
        {message.parts.map((part, i) => {
          switch (part.type) {
            case "text":
              return <div key={i} className="ai-text"><Markdown text={part.text} /></div>;
            case "status":
              return <StatusLine key={i} part={part} />;
            case "jobs":
              return <JobCards key={i} jobs={part.jobs} onNavigate={onNavigate} />;
            case "proposal":
              return <Proposal key={i} part={part} canApply={canApply} onEdit={(edit, action) => onEdit(message.id, i, edit, action)} />;
            case "memory":
              return (
                <div key={i} className="ai-chip-note">
                  Remembered: “{part.fact}”{part.stored === "browser" ? " (in this browser)" : ""}
                </div>
              );
            case "job_draft":
              return (
                <div key={i} className="ai-chip-note">
                  Draft saved: <Link to="/admin/jobs" onClick={onNavigate}>{part.title} at {part.company}</Link> — review and publish it from Admin.
                </div>
              );
            case "error":
              return <div key={i} className="ai-error" role="alert">{part.message}</div>;
            default:
              return null;
          }
        })}
        {message.streaming && !message.parts.some((p) => p.type === "text" || (p.type === "status" && !p.done)) && (
          <div className="ai-typing" aria-label="Thinking"><span /><span /><span /></div>
        )}
      </div>
    </div>
  );
}

function MemoryView({ signedIn, onBack }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!signedIn) {
      setItems(loadLocalMemories().map((text) => ({ id: text, text })));
      return;
    }
    assistant.memories().then(setItems).catch((err) => setError(err.message));
  }, [signedIn]);

  async function forget(item) {
    if (signedIn) {
      try {
        await assistant.forget(item.id);
      } catch (err) {
        setError(err.message);
        return;
      }
    } else {
      saveLocalMemories(loadLocalMemories().filter((m) => m !== item.text));
    }
    setItems((list) => list.filter((m) => m.id !== item.id));
  }

  return (
    <div className="ai-memory">
      <button type="button" className="ai-btn ai-memory__back" onClick={onBack}>← Back to chat</button>
      <h3>What Prottoy remembers</h3>
      <p className="ai-memory__intro">
        The assistant saves goals and preferences you mention so it can tailor its help.{" "}
        {signedIn ? "They're stored with your account." : "You're signed out, so they're kept in this browser only."}
      </p>
      {error && <div className="ai-error">{error}</div>}
      {items === null && !error && <p className="ai-memory__empty">Loading…</p>}
      {items?.length === 0 && <p className="ai-memory__empty">Nothing yet. Tell the assistant about the roles you're after.</p>}
      <ul>
        {items?.map((item) => (
          <li key={item.id}>
            <span>{item.text}</span>
            <button type="button" className="ai-btn" onClick={() => forget(item)} aria-label={`Forget: ${item.text}`}>Forget</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------- Dock ----------

export default function AssistantDock() {
  const { status: authStatus, user } = useAuth();
  const { enabled, pageInfo, requestContext, applyToDocument, openRequest } = useAssistant();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState("chat");
  const [messages, setMessages] = useState(loadChat);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const stickToBottom = useRef(true);
  const signedIn = authStatus === "authenticated";

  useEffect(() => {
    if (!busy) saveChat(messages);
  }, [messages, busy]);

  useEffect(() => {
    if (open && view === "chat") inputRef.current?.focus();
  }, [open, view]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages, open]);

  const updateAssistant = useCallback((id, fn) => {
    setMessages((list) => list.map((m) => (m.id === id ? fn(m) : m)));
  }, []);

  const send = useCallback(async (raw) => {
    const text = raw.trim();
    if (!text || busy) return;
    setInput("");
    setView("chat");
    stickToBottom.current = true;

    const userMsg = { id: nextId(), role: "user", text };
    const reply = { id: nextId(), role: "assistant", parts: [], streaming: true };
    const history = [...messages, userMsg]
      .map((m) => ({ role: m.role, content: textOf(m) }))
      .filter((m) => m.content)
      .slice(-HISTORY_LIMIT);
    while (history.length && history[0].role !== "user") history.shift();
    setMessages((list) => [...list, userMsg, reply]);
    setBusy(true);

    const push = (part) => updateAssistant(reply.id, (m) => {
      const parts = m.parts.map((p) => (p.type === "status" ? { ...p, done: true } : p));
      return { ...m, parts: [...parts, part] };
    });
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await assistant.chat(
        { messages: history, context: requestContext(), memories: signedIn ? [] : loadLocalMemories() },
        {
          signal: controller.signal,
          onEvent: (name, data) => {
            if (name === "text") {
              updateAssistant(reply.id, (m) => {
                const parts = m.parts.map((p) => (p.type === "status" ? { ...p, done: true } : p));
                const last = parts.at(-1);
                if (last?.type === "text") parts[parts.length - 1] = { ...last, text: last.text + data.delta };
                else parts.push({ type: "text", text: data.delta.replace(/^\n+/, "") });
                return { ...m, parts };
              });
            } else if (name === "status") push({ type: "status", label: data.label, done: false });
            else if (name === "jobs") push({ type: "jobs", jobs: data.jobs });
            else if (name === "proposal") push({ type: "proposal", note: data.note, edits: data.edits.map((e) => ({ ...e, state: "pending" })) });
            else if (name === "memory") {
              if (data.stored === "browser") addLocalMemory(data.fact);
              push({ type: "memory", fact: data.fact, stored: data.stored });
            } else if (name === "job_draft") push({ type: "job_draft", ...data });
            else if (name === "error") push({ type: "error", message: data.message });
          },
        }
      );
    } catch (err) {
      if (err.name !== "AbortError") push({ type: "error", message: err.message || "Something went wrong." });
    } finally {
      abortRef.current = null;
      setBusy(false);
      updateAssistant(reply.id, (m) => ({
        ...m,
        streaming: false,
        parts: m.parts.map((p) => (p.type === "status" ? { ...p, done: true } : p)),
      }));
    }
  }, [busy, messages, requestContext, signedIn, updateAssistant]);

  // Other parts of the app can open the assistant, optionally with a question.
  useEffect(() => {
    if (!openRequest || !enabled) return;
    setOpen(true);
    if (openRequest.prompt) send(openRequest.prompt);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- act once per request
  }, [openRequest, enabled]);

  const onEdit = useCallback((messageId, partIndex, editIndex, action) => {
    const message = messages.find((m) => m.id === messageId);
    const part = message?.parts[partIndex];
    if (!part) return;
    const targets = action === "apply-all"
      ? part.edits.map((e, i) => (e.state === "pending" ? i : -1)).filter((i) => i >= 0)
      : [editIndex];

    const states = {};
    for (const i of targets) {
      const edit = part.edits[i];
      if (action === "skip") {
        states[i] = "skipped";
        continue;
      }
      try {
        const next = applyToDocument((doc) => (action === "undo" ? revertEdit(doc, edit) : applyEdit(doc, edit)));
        if (next === null) return;
        states[i] = action === "undo" ? "pending" : "applied";
      } catch (err) {
        if (!(err instanceof StaleEdit)) throw err;
        states[i] = "stale";
      }
    }
    updateAssistant(messageId, (m) => ({
      ...m,
      parts: m.parts.map((p, pi) => (pi !== partIndex ? p : {
        ...p,
        edits: p.edits.map((e, ei) => (ei in states ? { ...e, state: states[ei] } : e)),
      })),
    }));
  }, [messages, applyToDocument, updateAssistant]);

  function newChat() {
    abortRef.current?.abort();
    setMessages([]);
    setView("chat");
  }

  function onScroll() {
    const el = scrollRef.current;
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }

  if (!enabled) return null;

  const closeOnMobile = () => window.matchMedia("(max-width: 600px)").matches && setOpen(false);
  const contextLabel = CONTEXT_LABEL[pageInfo.page];

  return (
    <>
      {!open && (
        <button type="button" className="ai-launcher" onClick={() => setOpen(true)} aria-label="Open the Prottoy assistant">
          <span className="ai-launcher__spark" aria-hidden="true">✦</span>
          <span className="ai-launcher__text">Ask Prottoy</span>
        </button>
      )}

      {open && (
        <section className="ai-panel" role="dialog" aria-label="Prottoy assistant">
          <header className="ai-panel__head">
            <img src={MARK} alt="" className="ai-panel__mark" />
            <div className="ai-panel__title">
              <strong>Prottoy Assistant</strong>
              <span>{contextLabel || (user ? "Signed in · personalised" : "Your career copilot")}</span>
            </div>
            <button type="button" className="ai-icon" onClick={() => setView(view === "memory" ? "chat" : "memory")}
              aria-label="What the assistant remembers" title="Memory">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 6 0V7a3 3 0 0 0-3-3Z" />
                <path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-6 0" />
              </svg>
            </button>
            <button type="button" className="ai-icon" onClick={newChat} aria-label="New chat" title="New chat">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <button type="button" className="ai-icon" onClick={() => setOpen(false)} aria-label="Close assistant" title="Close">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </header>

          {view === "memory" ? (
            <MemoryView signedIn={signedIn} onBack={() => setView("chat")} />
          ) : (
            <>
              <div className="ai-panel__body" ref={scrollRef} onScroll={onScroll}>
                {messages.length === 0 ? (
                  <div className="ai-welcome">
                    <img src={MARK} alt="" className="ai-welcome__mark" />
                    <h3>Hi{user ? "" : " there"}! How can I help?</h3>
                    <p>
                      I can score and fix your resume, write summaries and cover letters, recommend jobs that fit you,
                      and draft job descriptions. I&apos;ll remember your goals as we go.
                    </p>
                  </div>
                ) : (
                  messages.map((m) =>
                    m.role === "user" ? (
                      <div key={m.id} className="ai-msg ai-msg--user"><p>{m.text}</p></div>
                    ) : (
                      <AssistantMessage key={m.id} message={m} onEdit={onEdit} canApply={pageInfo.editable}
                        onNavigate={closeOnMobile} />
                    )
                  )
                )}
              </div>

              {!busy && messages.length === 0 && (
                <div className="ai-suggestions">
                  {suggestionsFor(pageInfo).map((s) => (
                    <button key={s} type="button" className="ai-suggestion" onClick={() => send(s)}>{s}</button>
                  ))}
                </div>
              )}

              <form className="ai-composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={input}
                  maxLength={4000}
                  placeholder={pageInfo.editable ? "Ask me to improve any part of your resume…" : "Ask about your resume, jobs, or a JD…"}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                      e.preventDefault();
                      send(input);
                    }
                  }}
                  aria-label="Message the assistant"
                />
                {busy ? (
                  <button type="button" className="ai-send ai-send--stop" onClick={() => abortRef.current?.abort()} aria-label="Stop">■</button>
                ) : (
                  <button type="submit" className="ai-send" disabled={!input.trim()} aria-label="Send">↑</button>
                )}
              </form>
              <p className="ai-disclaimer">AI can make mistakes — review suggestions before you apply or send them.</p>
            </>
          )}
        </section>
      )}
    </>
  );
}
