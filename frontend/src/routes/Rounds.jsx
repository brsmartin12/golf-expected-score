/**
 * The Rounds tab: everything logged so far, most recently played first.
 *
 * Wired to the real GET /rounds, so this is the first screen in the app that
 * reads from the database rather than computing from a form.
 *
 * How data loading works here
 * ---------------------------
 * `useEffect` runs after the component has rendered. That ordering is the point:
 * React draws the loading state first, the request goes out, and a second render
 * happens when it comes back. Fetching during render instead would block the
 * paint and, in StrictMode, fire twice.
 *
 * The three states — loading, failed, loaded — are all rendered explicitly.
 * Leaving out the failed state is how an app ends up showing an eternal spinner
 * when the backend is down.
 */
import { useEffect, useState } from "react";

import { deleteRound, fetchRounds } from "../api.js";

function formatPlayedOn(iso) {
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return {
    day: String(day).padStart(2, "0"),
    month: date.toLocaleString(undefined, { month: "short" }),
  };
}

/** To-par orientation: over is positive and worse, under is negative and better. */
function toPar(value) {
  if (value === null || value === undefined) return null;
  if (value > 0) return { text: `+${value.toFixed(1)}`, tone: "over" };
  if (value < 0) return { text: value.toFixed(1), tone: "under" };
  return { text: "E", tone: "level" };
}

export default function Rounds() {
  const [rounds, setRounds] = useState(null);
  const [error, setError] = useState(null);
  // Which row is asking "are you sure?". Inline rather than a modal: one row is
  // the whole question, and a dialog over a list loses which row it came from.
  const [confirming, setConfirming] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    fetchRounds()
      .then((data) => {
        // Guards against setting state after the component has gone, which
        // happens routinely when a tab is switched mid-request.
        if (!cancelled) setRounds(data);
      })
      .catch((requestError) => {
        if (!cancelled) setError(requestError.message);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function remove(id) {
    setBusy(true);
    setError(null);
    try {
      await deleteRound(id);
      // Refetch rather than splice. Every round after the deleted one was
      // graded against a population that just changed, so their verdicts move
      // too — the server recomputes them, and a local splice would leave stale
      // numbers on screen. See the note on deleteRound in api.js.
      setRounds(await fetchRounds());
      setConfirming(null);
    } catch (deleteError) {
      setError(deleteError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="page__header">
        <h1 className="page__title">Your rounds</h1>
        {rounds !== null && (
          <p className="page__sub">
            {rounds.length === 0
              ? "Nothing logged yet"
              : `${rounds.length} logged`}
          </p>
        )}
      </header>

      {error && (
        <p className="notice notice--bad" role="alert">
          {error}
        </p>
      )}

      {!error && rounds === null && <p className="notice">Loading&hellip;</p>}

      {rounds !== null && rounds.length === 0 && (
        <div className="card empty">
          <svg
            width="30"
            height="30"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            aria-hidden="true"
          >
            <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />
          </svg>
          <p className="empty__title">No rounds yet</p>
          <p className="empty__body">
            Log one and it shows up here. After eight, rounds start being
            graded against what you typically shoot; around twenty is where
            that number becomes worth trusting.
          </p>
        </div>
      )}

      {rounds !== null && rounds.length > 0 && (
        <ul className="rounds">
          {rounds.map((round) => {
            const { day, month } = formatPlayedOn(round.played_on);
            // Against TYPICAL, matching the verdict card. A round is judged
            // on what this golfer usually shoots, not on their best form.
            const gap = toPar(round.to_typical);

            if (confirming === round.id) {
              return (
                <li key={round.id} className="round round--confirming">
                  <p className="round__ask">
                    Delete the {round.gross_score} at {round.course_name}?
                  </p>
                  <div className="round__answer">
                    <button className="link-button" type="button" disabled={busy}
                            onClick={() => setConfirming(null)}>
                      Cancel
                    </button>
                    <button className="button button--danger" type="button"
                            disabled={busy} onClick={() => remove(round.id)}>
                      {busy ? "Deleting…" : "Delete"}
                    </button>
                  </div>
                </li>
              );
            }

            return (
              <li key={round.id} className="round">
                <div className="round__date">
                  <span className="round__day">{day}</span>
                  <span className="round__month">{month}</span>
                </div>

                <div className="round__what">
                  <span className="round__course">{round.course_name}</span>
                  <span className="round__meta">
                    {round.tee_name}
                    {round.nine && ` · ${round.nine} 9`}
                    {round.score_differential !== null &&
                      ` · ${round.score_differential.toFixed(1)} diff`}
                  </span>
                </div>

                <div className="round__numbers">
                  <span className="round__score">{round.gross_score}</span>
                  {gap ? (
                    <span className={`round__gap round__gap--${gap.tone}`}>
                      {gap.text}
                    </span>
                  ) : (
                    <span className="round__gap round__gap--none">
                      {round.score_differential === null
                        ? "not rated"
                        : "no history"}
                    </span>
                  )}
                </div>

                <button
                  className="round__remove"
                  type="button"
                  onClick={() => setConfirming(round.id)}
                  aria-label={`Delete the ${round.gross_score} at ${round.course_name}`}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                       stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                       aria-hidden="true">
                    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
