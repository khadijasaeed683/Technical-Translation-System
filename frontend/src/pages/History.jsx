import React, { useEffect, useState } from "react";
import { api } from "../api.js";
import PipelineTrace from "../components/PipelineTrace.jsx";

export default function History() {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [sourceLang, setSourceLang] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // traces[id] = { loading, trace, error } while that item's steps are open
  const [traces, setTraces] = useState({});

  async function load() {
    setLoading(true);
    try {
      const data = await api.getHistory({ keyword, source_lang: sourceLang });
      setItems(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleDelete(id) {
    await api.deleteHistoryItem(id);
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  function handleCopy(text) {
    navigator.clipboard.writeText(text);
  }

  async function handleToggleSteps(id) {
    if (traces[id]) {
      setTraces((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }
    setTraces((prev) => ({ ...prev, [id]: { loading: true } }));
    try {
      const data = await api.getTrace(id);
      setTraces((prev) => ({ ...prev, [id]: { loading: false, trace: data.trace } }));
    } catch (err) {
      setTraces((prev) => ({ ...prev, [id]: { loading: false, error: err.message } }));
    }
  }

  return (
    <div className="history-page">
      <h1>Translation history</h1>
      <form
        className="history-filters"
        onSubmit={(e) => {
          e.preventDefault();
          load();
        }}
      >
        <input
          type="text"
          placeholder="Search keyword..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
          <option value="">Any source language</option>
          <option value="en">English</option>
          <option value="ur">Urdu</option>
          <option value="ur-roman">Roman Urdu</option>
        </select>
        <button type="submit">Filter</button>
      </form>

      {error && <p className="form-error">{error}</p>}
      {loading && <p>Loading...</p>}

      <ul className="history-list">
        {items.map((item) => {
          const t = traces[item.id];
          return (
            <li key={item.id} className="history-item">
              <div className="history-item-text">
                <p className="history-source">{item.source_text}</p>
                <p className="history-output" dir={item.target_lang === "ur" ? "rtl" : "ltr"}>
                  {item.validated_output}
                </p>
              </div>
              <div className="history-item-meta">
                <span>{new Date(item.timestamp).toLocaleString()}</span>
                {!item.is_validated && <span className="badge badge-warning">Unvalidated</span>}
                <button className="btn-link" onClick={() => handleToggleSteps(item.id)}>
                  {t ? "Hide steps" : "View steps"}
                </button>
                <button className="btn-link" onClick={() => handleCopy(item.validated_output)}>
                  Copy
                </button>
                <button className="btn-link btn-danger" onClick={() => handleDelete(item.id)}>
                  Delete
                </button>
              </div>

              {t && (
                <div className="history-trace">
                  {t.loading && <p className="trace-muted">Loading steps...</p>}
                  {t.error && <p className="form-error">{t.error}</p>}
                  {!t.loading && !t.error && <PipelineTrace trace={t.trace} />}
                </div>
              )}
            </li>
          );
        })}
        {!loading && items.length === 0 && <p>No translations yet.</p>}
      </ul>
    </div>
  );
}
