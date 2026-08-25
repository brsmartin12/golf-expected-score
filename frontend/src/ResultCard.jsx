/**
 * Displays a result. A component that takes data and renders it, holding no
 * state of its own.
 *
 * `props` are a component's arguments -- React calls this function with the
 * attributes written in the JSX, so `<ResultCard result={x} />` arrives here as
 * `{ result: x }`. Data flows down: the parent owns the state, the child only
 * displays what it's handed.
 */

/** Format a signed number so a good round reads as "+4.0", not "4". */
function withSign(value) {
  return value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}

export default function ResultCard({ result }) {
  // A round verdict has a score; a bare expectation doesn't. That difference is
  // what decides which of the two layouts to render.
  const isRound = result.score !== undefined;

  if (!isRound) {
    return (
      <section className="result">
        <p className="result__label">Expected score</p>
        <p className="result__headline">{result.expected_score.toFixed(1)}</p>
        <p className="result__note">
          This is what your index shoots when you play <em>well</em> — an index
          averages your best 8 of 20, so it measures potential, not your typical
          round.
        </p>
      </section>
    );
  }

  const beat = result.beat_expectation;

  return (
    <section className={`result ${beat ? "result--good" : "result--under"}`}>
      <p className="result__label">Strokes vs. expected</p>
      <p className="result__headline">{withSign(result.strokes_vs_expected)}</p>
      <p className="result__verdict">
        {beat
          ? "Better than your index predicted."
          : "Short of what your index predicted."}
      </p>

      <dl className="result__details">
        <div>
          <dt>You shot</dt>
          <dd>{result.score.toFixed(0)}</dd>
        </div>
        <div>
          <dt>Expected</dt>
          <dd>{result.expected_score.toFixed(1)}</dd>
        </div>
        <div>
          <dt>Differential</dt>
          <dd>{result.score_differential.toFixed(1)}</dd>
        </div>
      </dl>

      <p className="result__note">
        The differential is this round on a neutral scale — what makes an 88 on a
        brutal course comparable to an 88 on an easy one.
      </p>
    </section>
  );
}
