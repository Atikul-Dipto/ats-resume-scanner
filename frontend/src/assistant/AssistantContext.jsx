import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from "react";
import { assistant } from "../api/client.js";

// Pages tell the assistant what the user is looking at (their resume, a job,
// a target job description) and, in the builder, how to apply an edit.
// Two contexts: stable actions (pages register through these without
// re-rendering when the assistant's state changes) and that state.
const ActionsContext = createContext(null);
const StateContext = createContext(null);
const NO_PAGE = { page: "other" };

export function AssistantProvider({ children }) {
  const current = useRef(NO_PAGE);
  const [pageInfo, setPageInfo] = useState({ page: "other", hasDocument: false, editable: false });
  const [openRequest, setOpenRequest] = useState(null);
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    assistant.status().then((s) => setEnabled(Boolean(s?.enabled)));
  }, []);

  const register = useCallback((owner, ctx) => {
    current.current = { ...ctx, owner };
    const next = { page: ctx.page, hasDocument: Boolean(ctx.document), editable: Boolean(ctx.apply) };
    setPageInfo((prev) =>
      prev.page === next.page && prev.hasDocument === next.hasDocument && prev.editable === next.editable ? prev : next
    );
  }, []);

  const unregister = useCallback((owner) => {
    if (current.current.owner !== owner) return;
    current.current = NO_PAGE;
    setPageInfo({ page: "other", hasDocument: false, editable: false });
  }, []);

  // What travels with each chat message.
  const requestContext = useCallback(() => {
    const ctx = current.current;
    return {
      page: ctx.page,
      document: ctx.document || null,
      editable: Boolean(ctx.apply && ctx.document),
      job_description: ctx.jobDescription?.trim() || null,
      job_id: ctx.jobId || null,
    };
  }, []);

  // Applies fn(doc) => doc to the open builder document and returns the new
  // document (null if none is editable). Runs synchronously, so errors thrown
  // by fn reach the caller, and back-to-back edits build on each other.
  const applyToDocument = useCallback((fn) => {
    const { apply, document } = current.current;
    if (!apply || !document) return null;
    const next = fn(document);
    current.current = { ...current.current, document: next };
    apply(next);
    return next;
  }, []);

  const openAssistant = useCallback((prompt) => setOpenRequest({ prompt: prompt || null, at: Date.now() }), []);

  const actions = useMemo(
    () => ({ register, unregister, requestContext, applyToDocument, openAssistant }),
    [register, unregister, requestContext, applyToDocument, openAssistant]
  );
  const state = useMemo(() => ({ enabled, pageInfo, openRequest }), [enabled, pageInfo, openRequest]);
  return (
    <ActionsContext.Provider value={actions}>
      <StateContext.Provider value={state}>{children}</StateContext.Provider>
    </ActionsContext.Provider>
  );
}

export function useAssistant() {
  return { ...useContext(ActionsContext), ...useContext(StateContext) };
}

/** Registers what this page shows. Call on every render; it's cheap. */
export function useAssistantPage(ctx) {
  const actions = useContext(ActionsContext);
  const owner = useId();
  useEffect(() => {
    actions?.register(owner, ctx);
  });
  useEffect(() => () => actions?.unregister(owner), [actions, owner]);
}
