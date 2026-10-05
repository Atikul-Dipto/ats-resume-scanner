import { useEffect, useRef, useState } from "react";
import { scoreDocument } from "../api/client.js";

const DEBOUNCE_MS = 700;

// Re-scores the document shortly after the user stops typing. Each new edit
// aborts the in-flight request, so a slow response can never overwrite a
// newer score, and the server sees at most one request per pause.
export default function useLiveScore(document, jobDescription) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);
  const controllerRef = useRef(null);

  useEffect(() => {
    if (!document) return undefined;
    setPending(true);
    const timer = setTimeout(() => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      scoreDocument(document, jobDescription, controller.signal)
        .then((data) => {
          setResult(data);
          setError(null);
        })
        .catch((err) => {
          if (err.name !== "AbortError") setError(err.message);
        })
        .finally(() => {
          if (controllerRef.current === controller) setPending(false);
        });
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [document, jobDescription]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  return { result, error, pending };
}
