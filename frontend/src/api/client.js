const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseError(res) {
  try {
    const body = await res.json();
    return body.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function analyzeResume(file, jobDescription) {
  const form = new FormData();
  form.append("file", file);
  if (jobDescription?.trim()) {
    form.append("job_description", jobDescription.trim());
  }

  const res = await fetch(`${BASE_URL}/api/analyze`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function searchJobs(query, skills, location) {
  const form = new FormData();
  form.append("query", query);
  form.append("skills", skills.join(","));
  form.append("location", location || "");

  const res = await fetch(`${BASE_URL}/api/jobs/search`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
