const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "ats-auth-token";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export const tokenStore = {
  get: () => {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token) => {
    try {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable (private mode) — session just won't persist */
    }
  },
};

// AuthContext subscribes so an expired token signs the user out everywhere.
const unauthorizedListeners = new Set();
export function onUnauthorized(listener) {
  unauthorizedListeners.add(listener);
  return () => unauthorizedListeners.delete(listener);
}

async function errorMessage(res) {
  if (res.status === 429) {
    const wait = res.headers.get("Retry-After");
    return `Too many requests — try again${wait ? ` in ${wait}s` : " shortly"}.`;
  }
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    // FastAPI validation errors: [{loc, msg}, ...]
    if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      const first = body.detail[0];
      return `${first.loc?.slice(1).join(" → ") || "Input"}: ${first.msg}`;
    }
  } catch {
    /* not JSON */
  }
  return `Request failed (${res.status})`;
}

async function request(path, { method = "GET", json, form, signal, raw = false } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }

  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, { method, headers, body, signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("Can't reach the server. It may be waking up (free tier) — try again in ~30s.", 0);
  }

  if (res.status === 401 && token) {
    unauthorizedListeners.forEach((fn) => fn());
  }
  if (!res.ok) throw new ApiError(await errorMessage(res), res.status);
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

// --- scan ---
export function analyzeResume(file, jobDescription) {
  const form = new FormData();
  form.append("file", file);
  if (jobDescription?.trim()) form.append("job_description", jobDescription.trim());
  return request("/api/analyze", { method: "POST", form });
}

export function searchJobs(query, skills, location) {
  const form = new FormData();
  form.append("query", query);
  form.append("skills", skills.join(","));
  form.append("location", location || "");
  return request("/api/jobs/search", { method: "POST", form });
}

// --- builder (no account needed) ---
export function scoreDocument(document, jobDescription, signal) {
  return request("/api/builder/score", {
    method: "POST",
    json: { document, job_description: jobDescription || null },
    signal,
  });
}

export async function exportDocument(document, format, filename) {
  const res = await request(`/api/builder/export/${format}`, {
    method: "POST",
    json: { document, filename: filename || "" },
    raw: true,
  });
  return res.blob();
}

// --- auth ---
export const auth = {
  register: (email, password) => request("/api/auth/register", { method: "POST", json: { email, password } }),
  login: (email, password) => request("/api/auth/login", { method: "POST", json: { email, password } }),
  me: () => request("/api/auth/me"),
  deleteAccount: () => request("/api/auth/me", { method: "DELETE" }),
};

// --- saved resumes ---
export const resumes = {
  list: () => request("/api/resumes"),
  get: (id) => request(`/api/resumes/${id}`),
  create: (title, document, targetJobDescription) =>
    request("/api/resumes", {
      method: "POST",
      json: { title, document, target_job_description: targetJobDescription || null },
    }),
  update: (id, { title, document, targetJobDescription, version }) =>
    request(`/api/resumes/${id}`, {
      method: "PUT",
      json: { title, document, target_job_description: targetJobDescription || null, version },
    }),
  duplicate: (id) => request(`/api/resumes/${id}/duplicate`, { method: "POST" }),
  remove: (id) => request(`/api/resumes/${id}`, { method: "DELETE" }),
  scans: (id) => request(`/api/resumes/${id}/scans`),
};

// --- job board ---
const query = (params) => {
  const qs = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  });
  const s = qs.toString();
  return s ? `?${s}` : "";
};

export const jobs = {
  list: (params) => request(`/api/jobs${query(params)}`),
  get: (id) => request(`/api/jobs/${id}`),
  match: (document, filters, signal) =>
    request("/api/jobs/match", { method: "POST", json: { document, ...filters }, signal }),
};

export const adminJobs = {
  list: (params) => request(`/api/admin/jobs${query(params)}`),
  get: (id) => request(`/api/admin/jobs/${id}`),
  create: (job) => request("/api/admin/jobs", { method: "POST", json: job }),
  update: (id, job) => request(`/api/admin/jobs/${id}`, { method: "PUT", json: job }),
  setStatus: (id, status) => request(`/api/admin/jobs/${id}/status`, { method: "POST", json: { status } }),
  remove: (id) => request(`/api/admin/jobs/${id}`, { method: "DELETE" }),
  sync: () => request("/api/admin/jobs/sync", { method: "POST" }),
};

// Deployment facts (e.g. whether saved data survives a server restart). Cached for the page's lifetime.
let metaPromise = null;
export function serverMeta() {
  metaPromise ??= request("/api/meta").catch(() => {
    metaPromise = null;
    return null;
  });
  return metaPromise;
}
