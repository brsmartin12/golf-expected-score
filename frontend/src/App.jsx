/**
 * The form, its state, and the call to the API.
 *
 * React state, briefly
 * --------------------
 * A React component is a function returning a description of the UI. React
 * calls it, compares the result to what's on screen, and patches the difference.
 *
 * The catch: a plain local variable can't survive that. React would re-run the
 * function and reset it. `useState` is the escape hatch -- it hands back the
 * current value plus a setter, and calling the setter tells React "this changed,
 * run me again." So:
 *
 *     const [score, setScore] = useState("");
 *
 * gives a value that persists across renders, and a way to update it that also
 * schedules a re-render. Never assign to it directly; React wouldn't notice.
 */
import { useState } from "react";

import ResultCard from "./ResultCard.jsx";
import { fetchExpectedScore, fetchRoundVerdict } from "./api.js";

// Form fields start as strings because <input> values are always strings, even
// with type="number". Empty string means "untouched", which is how the optional
// score field stays distinguishable from a deliberate 0.
const EMPTY_FORM = {
  handicapIndex: "",
  slopeRating: "",
  courseRating: "",
  score: "",
};

export default function App() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  // Tracks the in-flight request so the button can be disabled and relabelled.
  // Without it, an impatient double-click fires two requests.
  const [isLoading, setIsLoading] = useState(false);

  // One handler for every input, keyed by the field's `name` attribute. The
  // spread copies the existing fields and overrides one: React state must be
  // replaced, not mutated -- it detects change by identity, so editing the old
  // object in place would leave the screen stale.
  function handleChange(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function handleSubmit(event) {
    // A <form> submit reloads the page by default -- an inheritance from the
    // era when the server rendered the next page. In a single-page app that
    // would throw away all the state, so it has to be suppressed explicitly.
    event.preventDefault();

    setError(null);
    setResult(null);
    setIsLoading(true);

    // The inputs are strings; the API expects numbers. Convert at this
    // boundary so nothing downstream has to wonder which it's holding.
    const inputs = {
      handicapIndex: Number(form.handicapIndex),
      slopeRating: Number(form.slopeRating),
      courseRating: Number(form.courseRating),
    };

    try {
      // Score is optional, and which endpoint to call depends on it: with a
      // score there's a round to grade, without one there's only an expectation.
      const played = form.score.trim() !== "";
      const data = played
        ? await fetchRoundVerdict({ ...inputs, score: Number(form.score) })
        : await fetchExpectedScore(inputs);

      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      // `finally` so the button recovers whether the call succeeded or failed.
      setIsLoading(false);
    }
  }

  return (
    <main className="page">
      <header className="page__header">
        <h1>Golf Expected Score</h1>
        <p className="page__tagline">
          What should you shoot here — and was that round actually as bad as it
          felt?
        </p>
      </header>

      <form className="form" onSubmit={handleSubmit}>
        {/*
          These are "controlled inputs": React holds the value and the input
          displays it. Typing fires onChange, which updates state, which
          re-renders with the new value. The DOM never holds truth of its own.

          inputMode picks the on-screen keyboard a phone raises. type="number"
          alone is not enough -- iOS still offers a full keyboard for it. Score
          and slope are whole numbers ("numeric"); index and rating take a
          decimal point ("decimal").
        */}
        <label className="field">
          <span className="field__label">Handicap Index</span>
          <input
            name="handicapIndex"
            type="number"
            step="0.1"
            inputMode="decimal"
            min="-10"
            max="54"
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
            inputMode="numeric"
            min="55"
            max="155"
            required
            placeholder="130"
            value={form.slopeRating}
            onChange={handleChange}
          />
          <span className="field__hint">55–155. 113 is an average course.</span>
        </label>

        <label className="field">
          <span className="field__label">Course Rating</span>
          <input
            name="courseRating"
            type="number"
            step="0.1"
            inputMode="decimal"
            min="0.1"
            required
            placeholder="71.5"
            value={form.courseRating}
            onChange={handleChange}
          />
          <span className="field__hint">What a scratch golfer shoots here.</span>
        </label>

        <label className="field">
          <span className="field__label">
            Your score <span className="field__optional">optional</span>
          </span>
          <input
            name="score"
            type="number"
            step="1"
            inputMode="numeric"
            min="1"
            placeholder="88"
            value={form.score}
            onChange={handleChange}
          />
          <span className="field__hint">
            Add it to grade a round you played. Leave blank for the expectation
            alone.
          </span>
        </label>

        <button className="submit" type="submit" disabled={isLoading}>
          {isLoading ? "Calculating…" : "Calculate"}
        </button>
      </form>

      {/*
        Conditional rendering: `condition && <JSX/>` renders the element when
        the condition holds and nothing when it doesn't, because React ignores
        false. This is how a UI shows a result only once there is one.
      */}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {result && <ResultCard result={result} />}
    </main>
  );
}
