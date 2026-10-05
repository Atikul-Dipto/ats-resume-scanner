import { useRef, useState } from "react";

export default function UploadForm({ onSubmit, loading }) {
  const [file, setFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef(null);

  function pickFile(selected) {
    if (!selected) return;
    const name = selected.name.toLowerCase();
    if (!name.endsWith(".pdf") && !name.endsWith(".docx")) {
      alert("Please upload a .pdf or .docx file.");
      return;
    }
    setFile(selected);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragActive(false);
    pickFile(e.dataTransfer.files?.[0]);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!file) return;
    onSubmit(file, jobDescription);
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <div
        className={`dropzone ${dragActive ? "active" : ""} ${file ? "has-file" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          hidden
          onChange={(e) => pickFile(e.target.files?.[0])}
        />
        {file ? (
          <p className="dropzone-file">✓ {file.name}</p>
        ) : (
          <>
            <p className="dropzone-title">Drop your resume here</p>
            <p className="dropzone-hint">or click to browse — .pdf or .docx, max 5MB</p>
          </>
        )}
      </div>

      <label className="jd-label" htmlFor="job-description">
        Target job description <span>(optional — improves keyword scoring)</span>
      </label>
      <textarea
        id="job-description"
        rows={6}
        placeholder="Paste the job description you're targeting..."
        value={jobDescription}
        onChange={(e) => setJobDescription(e.target.value)}
      />

      <button type="submit" disabled={!file || loading}>
        {loading ? "Analyzing..." : "Run ATS Scan"}
      </button>
    </form>
  );
}
