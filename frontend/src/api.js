const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  async signup(email, password) {
    const res = await fetch(`${API_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    return handle(res);
  },

  async login(email, password) {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    return handle(res);
  },

  async translate({ text, source_lang = "auto", target_lang = null }) {
    const res = await fetch(`${API_URL}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ text, source_lang, target_lang }),
    });
    return handle(res);
  },

  async getHistory(params = {}) {
    const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v));
    const res = await fetch(`${API_URL}/history?${query}`, { headers: authHeaders() });
    return handle(res);
  },

  async getTrace(id) {
    const res = await fetch(`${API_URL}/history/${id}/trace`, { headers: authHeaders() });
    return handle(res);
  },

  async deleteHistoryItem(id) {
    const res = await fetch(`${API_URL}/history/${id}`, { method: "DELETE", headers: authHeaders() });
    return handle(res);
  },

  async submitFeedback(translation_id, rating, comment = null) {
    const res = await fetch(`${API_URL}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ translation_id, rating, comment }),
    });
    return handle(res);
  },

  async getGlossary() {
    const res = await fetch(`${API_URL}/glossary`, { headers: authHeaders() });
    return handle(res);
  },

  async createGlossaryTerm(term) {
    const res = await fetch(`${API_URL}/glossary`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(term),
    });
    return handle(res);
  },

  async deleteGlossaryTerm(id) {
    const res = await fetch(`${API_URL}/glossary/${id}`, { method: "DELETE", headers: authHeaders() });
    return handle(res);
  },

  async getAdminAnalytics() {
    const res = await fetch(`${API_URL}/admin/analytics`, { headers: authHeaders() });
    return handle(res);
  },

  async runEvaluation(sample_size = null) {
    const res = await fetch(`${API_URL}/evaluation/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ sample_size }),
    });
    return handle(res);
  },

  async getEvaluationResults() {
    const res = await fetch(`${API_URL}/evaluation/results`, { headers: authHeaders() });
    return handle(res);
  },
};
