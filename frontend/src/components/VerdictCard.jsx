/**
 * The verdict shown straight after a round is saved. The app's headline screen.
 *
 * TYPICAL leads, not potential. Potential is a 20th percentile — it is beaten in
 * about one round in five — so headlining it means opening with bad news four
 * times out of five. Typical is a median, beaten half the time by construction,
 * which makes "you shot two better than usual" a sentence worth reading. See
 * Tier 2 in ROADMAP.md.
 *
 * Both figures are quantiles of this golfer's own differentials, so neither
 * exists until there is history behind the round. Until then the card shows the
 * differential and a countdown rather than an invented benchmark.
 *
 * For a nine, every number here is already on the nine's own scale — the API
 * halves the benchmark and runs it through that nine's rating and slope. So the
 * card needs no special arithmetic, only a label saying which nine it was.
 */

/** Golf's to-par orientation: over is positive and worse, under negative and better. */
function toPar(value) {
  if (value > 0) return { text: `+${value.toFixed(1)}`, tone: "over" };
  if (value < 0) return { text: value.toFixed(1), tone: "under" };
  return { text: "E", tone: "level" };
}

const VERDICT = {
  over: "Tougher day than usual for you here.",
  under: "Better than you usually play this course.",
  level: "Right on what you usually shoot here.",
};

function plural(n, word) {
  return `${n} more ${word}${n === 1 ? "" : "s"}`;
}

const HOLES = { front: "the front nine", back: "the back nine" };

export default function VerdictCard({ round, onDismiss }) {
  const graded = round.to_typical !== null && round.to_typical !== undefined;
  const gap = graded ? toPar(round.to_typical) : null;

  return (
    <section className={`verdict${gap ? ` verdict--${gap.tone}` : ""}`}>
      <button className="verdict__close" type="button" onClick={onDismiss} aria-label="Dismiss">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>

      <p className="verdict__shot">
        You shot <strong>{round.gross_score}</strong>
        {round.nine ? ` on ${HOLES[round.nine]} at ` : " at "}
        {round.course_name}
      </p>

      {gap ? (
        <>
          <p className="verdict__headline">{gap.text}</p>
          <p className="verdict__label">vs. your typical</p>
          <p className="verdict__says">{VERDICT[gap.tone]}</p>
        </>
      ) : round.score_differential === null ? (
        <>
          <p className="verdict__headline verdict__headline--quiet">&mdash;</p>
          <p className="verdict__label">not rated</p>
          <p className="verdict__says">
            This tee has no rating for {HOLES[round.nine]}, so there is nothing
            to measure the round against. Add it to the course and this round
            starts counting.
          </p>
        </>
      ) : (
        <>
          <p className="verdict__headline verdict__headline--quiet">
            {round.score_differential.toFixed(1)}
          </p>
          <p className="verdict__label">differential</p>
          <p className="verdict__says">
            {plural(round.rounds_until_benchmarks, "full round")} and this gets
            a verdict.
          </p>
        </>
      )}

      <dl className="verdict__stats">
        <div>
          <dt>Differential</dt>
          <dd>
            {round.score_differential === null
              ? "—"
              : round.score_differential.toFixed(1)}
          </dd>
        </div>
        <div className={round.typical_score === null ? "verdict__pending" : undefined}>
          <dt>Typical</dt>
          <dd>
            {round.typical_score === null ? (
              <span className="verdict__soon">needs history</span>
            ) : (
              round.typical_score.toFixed(1)
            )}
          </dd>
        </div>
        <div className={round.potential_score === null ? "verdict__pending" : undefined}>
          <dt>Potential</dt>
          <dd>
            {round.potential_score === null ? (
              <span className="verdict__soon">needs history</span>
            ) : (
              round.potential_score.toFixed(1)
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
