/**
 * Displays a result. A component that takes data and renders it, holding no
 * state of its own.
 *
 * `props` are a component's arguments -- React calls this function with the
 * attributes written in the JSX, so `<ResultCard result={x} />` arrives here as
 * `{ result: x }`. Data flows down: the parent owns the state, the child only
 * displays what it's handed.
 */

/**
 * Format the gap the way a scorecard does: "+5.0" for over, "-4.0" for under.
 *
 * This reads off `to_potential`, not `strokes_vs_potential`. The two are exact
 * negatives of each other and it matters which one reaches a golfer: a minus
 * sign already means "under par" on every leaderboard they have ever read, so
 * showing -5.0 for a round five strokes WORSE than their potential inverts the
 * one convention they are fluent in. Over is positive here, and positive is bad.
 */
function toParStyle(value) {
  if (value > 0) return `+${value.toFixed(1)}`;
  if (value < 0) return value.toFixed(1); // toFixed already carries the minus
  return "E"; // level, as a card would print it
}

export default function ResultCard({ result }) {
  // A round verdict has a score; a bare expectation doesn't. That difference is
  // what decides which of the two layouts to render.
  const isRound = result.score !== undefined;

  if (!isRound) {
    return (
      <section className="result">
        <p className="result__label">Your potential here</p>
        <p className="result__headline">{result.potential_score.toFixed(1)}</p>
        <p className="result__note">
          This is the score you post when you play <em>well</em>, not your
          typical round — an index averages your best 8 of 20, so 12 of your
          last 20 rounds are thrown away before it is calculated.
        </p>
      </section>
    );
  }

  // Three states, not two: exactly level is its own case, and calling it
  // "over potential" because it failed a `> 0` test would be a small lie.
  const gap = result.to_potential;
  const tone = gap < 0 ? "under" : gap > 0 ? "over" : "level";

  const verdict = {
    under: `Under your potential ${result.potential_score.toFixed(1)} — better than the round your index says you can play.`,
    over: `Over your potential ${result.potential_score.toFixed(1)} — short of the round your index says you can play.`,
    level: `Exactly your potential ${result.potential_score.toFixed(1)} — you played to your handicap.`,
  }[tone];

  return (
    <section className={`result result--${tone}`}>
      <p className="result__label">Vs. your potential</p>
      <p className="result__headline">{toParStyle(gap)}</p>
      <p className="result__verdict">{verdict}</p>

      <dl className="result__details">
        <div>
          <dt>You shot</dt>
          <dd>{result.score.toFixed(0)}</dd>
        </div>
        <div>
          <dt>Potential</dt>
          <dd>{result.potential_score.toFixed(1)}</dd>
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
