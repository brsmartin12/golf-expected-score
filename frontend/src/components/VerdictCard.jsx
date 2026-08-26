/**
 * The verdict shown straight after a round is saved. The app's headline screen.
 *
 * Right now it can only compare against POTENTIAL, because `typical` is a Tier 2
 * figure that needs stored history to compute. That is the "early days" state
 * from the design canvas, and it is drawn honestly: a countdown rather than an
 * invented median.
 *
 * Once typical exists it becomes the leading number, with potential beside it —
 * potential is beaten in only about one round in five, so headlining it means
 * bad news four times out of five. See Tier 2 in ROADMAP.md.
 */

/** Golf's to-par orientation: over is positive and worse, under negative and better. */
function toPar(value) {
  if (value > 0) return { text: `+${value.toFixed(1)}`, tone: "over" };
  if (value < 0) return { text: value.toFixed(1), tone: "under" };
  return { text: "E", tone: "level" };
}

const VERDICT = {
  over: "Short of the round your index says you can play.",
  under: "Better than the round your index says you can play.",
  level: "Exactly the round your index says you can play.",
};

export default function VerdictCard({ round, onDismiss }) {
  const hasIndex = round.to_potential !== null && round.to_potential !== undefined;
  const gap = hasIndex ? toPar(round.to_potential) : null;

  return (
    <section className={`verdict${gap ? ` verdict--${gap.tone}` : ""}`}>
      <button className="verdict__close" type="button" onClick={onDismiss} aria-label="Dismiss">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>

      <p className="verdict__shot">
        You shot <strong>{round.gross_score}</strong> at {round.course_name}
      </p>

      {gap ? (
        <>
          <p className="verdict__headline">{gap.text}</p>
          <p className="verdict__label">vs. your potential</p>
          <p className="verdict__says">{VERDICT[gap.tone]}</p>
        </>
      ) : (
        <>
          <p className="verdict__headline verdict__headline--quiet">
            {round.score_differential.toFixed(1)}
          </p>
          <p className="verdict__label">differential</p>
          <p className="verdict__says">
            Saved without an index, so there is nothing to compare it against yet.
          </p>
        </>
      )}

      <dl className="verdict__stats">
        <div>
          <dt>Differential</dt>
          <dd>{round.score_differential.toFixed(1)}</dd>
        </div>
        <div>
          <dt>Potential</dt>
          <dd>{round.potential_score === null ? "—" : round.potential_score.toFixed(1)}</dd>
        </div>
        <div className="verdict__pending">
          <dt>Typical</dt>
          <dd>
            <span className="verdict__soon">needs history</span>
          </dd>
        </div>
      </dl>
    </section>
  );
}
