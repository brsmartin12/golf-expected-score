/**
 * The Log tab.
 *
 * Still the Tier 0 calculator, restyled onto the new tokens so the app keeps
 * working while the shell lands. The real round-entry screen — course picker,
 * quick-add, the typical-led verdict card — replaces this in the next piece;
 * see Tier 1 in ROADMAP.md.
 */
import { useState } from "react";

import ResultCard from "../ResultCard.jsx";
import { fetchPotentialScore, fetchRoundVerdict } from "../api.js";

const EMPTY_FORM = {
  handicapIndex: "",
  slopeRating: "",
  courseRating: "",
  score: "",
};

export default function LogRound() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setResult(null);
    setIsLoading(true);

    const inputs = {
      handicapIndex: Number(form.handicapIndex),
      slopeRating: Number(form.slopeRating),
      courseRating: Number(form.courseRating),
    };

    try {
      const played = form.score.trim() !== "";
      const data = played
        ? await fetchRoundVerdict({ ...inputs, score: Number(form.score) })
        : await fetchPotentialScore(inputs);
      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <>
      <header className="page__header">
        <h1 className="page__title">Log a round</h1>
        <p className="page__sub">
          Temporary: typed slope and rating until courses are pickable.
        </p>
      </header>

      <form className="card form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field__label">Handicap Index</span>
          <input
            name="handicapIndex"
            type="number"
            step="0.1"
            min="-10"
            max="54"
            inputMode="decimal"
            required
            placeholder="10.0"
            value={form.handicapIndex}
            onChange={handleChange}
          />
        </label>

        <label className="field">
          <span className="field__label">Slope Rating</span>
          <input
            name="slopeRating"
            type="number"
            step="1"
            min="55"
            max="155"
            inputMode="numeric"
            required
            placeholder="130"
            value={form.slopeRating}
            onChange={handleChange}
          />
          <span className="field__hint">55&ndash;155. 113 is an average course.</span>
        </label>

        <label className="field">
          <span className="field__label">Course Rating</span>
          <input
            name="courseRating"
            type="number"
            step="0.1"
            min="0.1"
            inputMode="decimal"
            required
            placeholder="71.5"
            value={form.courseRating}
            onChange={handleChange}
          />
        </label>

        <label className="field">
          <span className="field__label">
            Your score <span className="field__optional">optional</span>
          </span>
          <input
            name="score"
            type="number"
            step="1"
            min="1"
            inputMode="numeric"
            placeholder="88"
            value={form.score}
            onChange={handleChange}
          />
        </label>

        <button className="button" type="submit" disabled={isLoading}>
          {isLoading ? "Calculating\u2026" : "Calculate"}
        </button>
      </form>

      {error && (
        <p className="notice notice--bad" role="alert">
          {error}
        </p>
      )}

      {result && <ResultCard result={result} />}
    </>
  );
}
