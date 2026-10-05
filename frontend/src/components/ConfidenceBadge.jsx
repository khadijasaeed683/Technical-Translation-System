import React from "react";

export default function ConfidenceBadge({ confidence, isValidated }) {
  if (!isValidated) {
    return <span className="badge badge-warning">Unvalidated (fallback)</span>;
  }
  if (confidence === null || confidence === undefined) {
    return null;
  }
  const pct = Math.round(confidence * 100);
  const level = pct >= 80 ? "high" : pct >= 50 ? "medium" : "low";
  return <span className={`badge badge-confidence-${level}`}>Confidence: {pct}%</span>;
}
