import React, { useState } from "react";
import { api } from "../api.js";

export default function FeedbackButtons({ translationId }) {
  const [rating, setRating] = useState(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  async function send(newRating, withComment = null) {
    setRating(newRating);
    try {
      await api.submitFeedback(translationId, newRating, withComment);
      setSubmitted(true);
    } catch (err) {
      console.error(err);
    }
  }

  function handleThumbsDown() {
    setShowComment(true);
    send("down");
  }

  return (
    <div className="feedback-row">
      <button
        className={`btn-icon ${rating === "up" ? "active" : ""}`}
        onClick={() => send("up")}
        aria-label="Good translation"
      >
        👍
      </button>
      <button
        className={`btn-icon ${rating === "down" ? "active" : ""}`}
        onClick={handleThumbsDown}
        aria-label="Bad translation"
      >
        👎
      </button>
      {submitted && !showComment && <span className="feedback-thanks">Thanks for the feedback!</span>}
      {showComment && (
        <span className="feedback-comment">
          <input
            type="text"
            placeholder="What was wrong? (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            onBlur={() => comment && send("down", comment)}
          />
        </span>
      )}
    </div>
  );
}
