import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Admin() {
  const [analytics, setAnalytics] = useState(null);
  const [evalResults, setEvalResults] = useState([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  async function loadAll() {
    try {
      const [a, e] = await Promise.all([api.getAdminAnalytics(), api.getEvaluationResults()]);
      setAnalytics(a);
      setEvalResults(e);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function handleRunEvaluation() {
    setRunning(true);
    setError(null);
    try {
      await api.runEvaluation();
      await loadAll();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="admin-page">
      <h1>Admin dashboard</h1>
      {error && <p className="form-error">{error}</p>}

      {analytics && (
        <section className="admin-section">
          <h2>Feedback & correction trends</h2>
          <div className="stat-grid">
            <Stat label="Total translations" value={analytics.total_translations} />
            <Stat label="Feedback received" value={analytics.total_feedback} />
            <Stat label="👍 Thumbs up" value={analytics.thumbs_up} />
            <Stat label="👎 Thumbs down" value={analytics.thumbs_down} />
            <Stat label="Thumbs-up rate" value={`${(analytics.thumbs_up_rate * 100).toFixed(1)}%`} />
            <Stat label="Correction rate" value={`${(analytics.correction_rate * 100).toFixed(1)}%`} />
            <Stat
              label="Unvalidated fallback rate"
              value={`${(analytics.unvalidated_fallback_rate * 100).toFixed(1)}%`}
            />
          </div>
          {analytics.top_correction_reasons.length > 0 && (
            <>
              <h3>Top correction reasons</h3>
              <ul>
                {analytics.top_correction_reasons.map((r) => (
                  <li key={r.reason}>
                    {r.reason}: {r.count}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <section className="admin-section">
        <h2>Evaluation (Google Translate vs raw base model vs our system)</h2>
        <p className="subtle">
          Runs the Section 7.1 comparison against the seed evaluation dataset. This calls the
          Gemini API and Google Translate for every sentence, so it can take a minute.
        </p>
        <button onClick={handleRunEvaluation} disabled={running}>
          {running ? "Running evaluation..." : "Run new evaluation"}
        </button>

        {evalResults.length > 0 && (
          <div className="eval-results">
            <h3>Latest run ({evalResults[0].dataset_size} sentence pairs)</h3>
            <table className="glossary-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Google Translate</th>
                  <th>Raw base model</th>
                  <th>Our system</th>
                </tr>
              </thead>
              <tbody>
                {evalResults[0].metrics.map((row) => (
                  <tr key={row.metric}>
                    <td>{row.metric}</td>
                    <td>{row.google_translate}</td>
                    <td>{row.raw_base_model}</td>
                    <td>
                      <strong>{row.our_system}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
