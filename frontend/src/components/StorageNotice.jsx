import { useEffect, useState } from "react";
import { serverMeta } from "../api/client.js";

// Shown where accounts matter, when the server has no permanent database yet.
export default function StorageNotice() {
  const [meta, setMeta] = useState(null);
  useEffect(() => {
    serverMeta().then(setMeta);
  }, []);
  if (!meta || meta.persistent_storage) return null;
  return (
    <div className="notice">
      Heads-up: this demo server doesn&apos;t have a permanent database yet, so accounts, saved resumes and posted jobs
      reset when it restarts. Your builder draft stays safe in this browser, and exported PDFs/DOCX are yours to keep.
    </div>
  );
}
