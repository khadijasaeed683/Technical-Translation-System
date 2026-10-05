import React, { useState } from "react";
import "./PipelineTrace.css";

const STATUS_LABEL = {
  ok: "Done",
  skipped: "Skipped",
  fallback: "Fallback",
  failed: "Failed",
};

// Renders one value from a step's `details` object. dir="auto" keeps Urdu text right-to-left.
function DetailValue({ value }) {
  if (value === null || value === undefined || value === "") {
    return <span className="trace-muted">none</span>;
  }
  if (typeof value === "boolean") {
    return <span>{value ? "yes" : "no"}</span>;
  }
  if (typeof value === "string" || typeof value === "number") {
    return (
      <span className="trace-text" dir="auto">
        {String(value)}
      </span>
    );
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="trace-muted">none</span>;
    if (value.every((v) => typeof v !== "object" || v === null)) {
      return (
        <ul className="trace-list">
          {value.map((v, i) => (
            <li key={i} className="trace-text" dir="auto">
              {String(v)}
            </li>
          ))}
        </ul>
      );
    }
  }
  return (
    <pre className="trace-json" dir="ltr">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export default function PipelineTrace({ trace, totalMs }) {
  const [open, setOpen] = useState({});

  if (!trace || trace.length === 0) {
    return (
      <p className="trace-muted">
        No pipeline trace was recorded for this translation (it was made before tracing was added).
      </p>
    );
  }

  const allOpen = trace.every((s) => open[s.step]);
  const total = totalMs ?? trace.reduce((sum, s) => sum + s.duration_ms, 0);

  function toggle(step) {
    setOpen((prev) => ({ ...prev, [step]: !prev[step] }));
  }

  function toggleAll() {
    const next = {};
    if (!allOpen) trace.forEach((s) => (next[s.step] = true));
    setOpen(next);
  }

  return (
    <div className="trace">
      <div className="trace-header">
        <h3>Pipeline trace</h3>
        <span className="trace-total">{total} ms total</span>
        <button className="btn-link" onClick={toggleAll}>
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>

      <ol className="trace-steps">
        {trace.map((s) => {
          const isOpen = !!open[s.step];
          const detailEntries = Object.entries(s.details || {});
          return (
            <li key={s.step} className={`trace-step trace-${s.status}`}>
              <span className="trace-num">{s.step}</span>

              <button className="trace-toggle" onClick={() => toggle(s.step)} aria-expanded={isOpen}>
                <span className="trace-name">{s.name}</span>
                <span className={`trace-status trace-status-${s.status}`}>
                  {STATUS_LABEL[s.status] || s.status}
                </span>
                <span className="trace-duration">{s.duration_ms} ms</span>
                <span className="trace-chevron">{isOpen ? "▾" : "▸"}</span>
              </button>

              <p className="trace-summary" dir="auto">
                {s.summary}
              </p>

              {isOpen && detailEntries.length > 0 && (
                <dl className="trace-details">
                  {detailEntries.map(([key, value]) => (
                    <React.Fragment key={key}>
                      <dt>{key.replace(/_/g, " ")}</dt>
                      <dd>
                        <DetailValue value={value} />
                      </dd>
                    </React.Fragment>
                  ))}
                </dl>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
