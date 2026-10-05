import React, { useState } from "react";
import { api } from "../api.js";
import ConfidenceBadge from "../components/ConfidenceBadge.jsx";
import FeedbackButtons from "../components/FeedbackButtons.jsx";
import PipelineTrace from "../components/PipelineTrace.jsx";

const LANG_LABELS = { en: "English", ur: "Urdu", "ur-roman": "Roman Urdu" };

function dirFor(lang) {
  return lang === "ur" ? "rtl" : "ltr";
}

export default function Translate() {
  const [text, setText] = useState("");
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [showTrace, setShowTrace] = useState(true);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleTranslate(e) {
    e.preventDefault();
    if (!text.trim()) {
      setError("Please enter text to translate");
      return;
    }
    setError(null);
    setLoading(true);
    setResult(null);
    try {
      const res = await api.translate({
        text,
        source_lang: sourceLang,
        target_lang: targetLang || null,
      });
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="translate-page">
      <h1>Translate</h1>
      <form onSubmit={handleTranslate} className="translate-form">
        <textarea
          rows={5}
          placeholder="Type English, Urdu, or Roman Urdu text..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <div className="translate-controls">
          <label>
            Source language
            <select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
              <option value="auto">Auto-detect</option>
              <option value="en">English</option>
              <option value="ur">Urdu</option>
              <option value="ur-roman">Roman Urdu</option>
            </select>
          </label>
          <label>
            Target language (optional override)
            <select value={targetLang} onChange={(e) => setTargetLang(e.target.value)}>
              <option value="">Default</option>
              <option value="en">English</option>
              <option value="ur">Urdu</option>
            </select>
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Translating..." : "Translate"}
          </button>
        </div>
      </form>

      {error && <p className="form-error">{error}</p>}

      {result && (
        <div className="result-card">
          <div className="result-meta">
            <span className="lang-tag">
              {LANG_LABELS[result.source_lang] || result.source_lang} → {LANG_LABELS[result.target_lang] || result.target_lang}
            </span>
            <ConfidenceBadge confidence={result.confidence} isValidated={result.is_validated} />
          </div>

          <div className="result-output" dir={dirFor(result.target_lang)} lang={result.target_lang}>
            {result.validated_output}
          </div>

          {result.alternates && result.alternates.length > 0 && (
            <div className="alternates">
              <strong>Alternate renderings:</strong>
              <ul>
                {result.alternates.map((alt, i) => (
                  <li key={i} dir={dirFor(result.target_lang)}>
                    {alt}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <FeedbackButtons translationId={result.id} />

          <button className="btn-link" onClick={() => setShowDiff((v) => !v)}>
            {showDiff ? "Hide" : "Show"} what the validation layer changed
          </button>

          {showDiff && (
            <div className="diff-panel">
              <div className="diff-column">
                <h4>Raw base-model output</h4>
                <p dir={dirFor(result.target_lang)}>{result.raw_output}</p>
              </div>
              <div className="diff-column">
                <h4>Validated output</h4>
                <p dir={dirFor(result.target_lang)}>{result.validated_output}</p>
              </div>
              {result.diff.length > 0 ? (
                <div className="diff-ops">
                  <h4>Change set</h4>
                  <ul>
                    {result.diff.map((d, i) => (
                      <li key={i}>
                        <span className={`diff-op diff-op-${d.op}`}>{d.op}</span>{" "}
                        {d.raw && <del>{d.raw}</del>} {d.validated && <ins>{d.validated}</ins>}
                      </li>
                    ))}
                  </ul>
                  {result.correction_reason && result.correction_reason.length > 0 && (
                    <p className="correction-reasons">
                      Reasons: {result.correction_reason.join("; ")}
                    </p>
                  )}
                </div>
              ) : (
                <p className="no-diff">No corrections were needed — raw and validated output match.</p>
              )}
            </div>
          )}

          <div>
            <button className="btn-link" onClick={() => setShowTrace((v) => !v)}>
              {showTrace ? "Hide" : "Show"} pipeline trace
            </button>
          </div>

          {showTrace && <PipelineTrace trace={result.trace} totalMs={result.total_ms} />}
        </div>
      )}
    </div>
  );
}
