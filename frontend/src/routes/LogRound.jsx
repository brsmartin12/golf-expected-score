/**
 * The Log tab: the after-round moment.
 *
 * One screen, one job — get a round in and say whether it was any good. The
 * layout follows the quick-add flow: pick the course once, then score, save,
 * score, save. Everything that stays the same between rounds stays on screen.
 *
 * All of the behaviour lives in useRoundEntry; this file is the presentation.
 * That split is what makes a visual redesign cheap — see the note in the hook.
 */
import { useEffect, useState } from "react";

import AddCourse from "../components/AddCourse.jsx";
import VerdictCard from "../components/VerdictCard.jsx";
import { fetchCourses } from "../api.js";
import { useRoundEntry } from "../hooks/useRoundEntry.js";

export default function LogRound() {
  const [courses, setCourses] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [isAdding, setIsAdding] = useState(false);

  const { form, setField, isReady, isSaving, error, verdict, dismissVerdict, saved, save } =
    useRoundEntry();

  useEffect(() => {
    let cancelled = false;
    fetchCourses()
      .then((data) => !cancelled && setCourses(data))
      .catch((e) => !cancelled && setLoadError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  function handleCourseAdded(course) {
    setCourses((previous) => [...(previous ?? []), course].sort((a, b) =>
      a.name.localeCompare(b.name)));
    setIsAdding(false);
    // Select the tee that was just created, so entry can continue immediately.
    if (course.tees.length > 0) setField("teeId", String(course.tees[0].id));
  }

  // One flat list of tees: a tee is what a round is actually played from, and
  // flattening keeps the picker to a single control rather than two dependent
  // ones, which is a lot less fiddly with a thumb.
  const tees = (courses ?? []).flatMap((course) =>
    course.tees.map((tee) => ({
      id: tee.id,
      label: `${course.name} · ${tee.name}`,
    })),
  );

  const hasCourses = courses !== null && tees.length > 0;

  return (
    <>
      <header className="page__header">
        <h1 className="page__title">Log a round</h1>
        <p className="page__sub">
          {saved.length > 0
            ? `${saved.length} added this session`
            : "Course and date stay put between saves."}
        </p>
      </header>

      {loadError && <p className="notice notice--bad" role="alert">{loadError}</p>}

      {courses === null && !loadError && <p className="notice">Loading courses…</p>}

      {courses !== null && tees.length === 0 && !isAdding && (
        <div className="card empty">
          <p className="empty__title">No courses yet</p>
          <p className="empty__body">
            Add one with its slope and rating. You type those once — every round
            after this is picking it from a list.
          </p>
          <button className="button" type="button" onClick={() => setIsAdding(true)}>
            Add a course
          </button>
        </div>
      )}

      {isAdding && <AddCourse onAdded={handleCourseAdded} />}

      {/* Above the form on purpose. Saved below it, the verdict landed off the
          bottom of a phone screen — the app's headline moment, out of sight.
          Here the first thing after a save is the answer.

          No auto-scroll to go with it: during a long backfill that would fight
          the person typing, and the session list below already ticks each save.
          The big card is for the weekly round, the list is for the backfill. */}
      {verdict && <VerdictCard round={verdict} onDismiss={dismissVerdict} />}

      {hasCourses && !isAdding && (
        <form
          className="card form"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <label className="field">
            <span className="field__label">Course and tee</span>
            <select
              className="select"
              value={form.teeId}
              onChange={(event) => setField("teeId", event.target.value)}
              required
            >
              <option value="" disabled>
                Pick a course…
              </option>
              {tees.map((tee) => (
                <option key={tee.id} value={tee.id}>
                  {tee.label}
                </option>
              ))}
            </select>
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field__label">Date played</span>
              <input
                type="date"
                value={form.playedOn}
                onChange={(event) => setField("playedOn", event.target.value)}
                required
              />
            </label>

            <label className="field field--score">
              <span className="field__label">Score</span>
              <input
                type="number"
                inputMode="numeric"
                min="1"
                max="200"
                required
                placeholder="88"
                value={form.grossScore}
                onChange={(event) => setField("grossScore", event.target.value)}
              />
            </label>
          </div>

          <label className="field">
            <span className="field__label">
              Handicap index <span className="field__optional">optional</span>
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              min="-10"
              max="54"
              placeholder="10.0"
              value={form.handicapIndex}
              onChange={(event) => setField("handicapIndex", event.target.value)}
            />
            <span className="field__hint">
              Your index on the day, cleared after each save. Leave it blank
              for old rounds — it can be worked out from the rounds around it
              later.
            </span>
          </label>

          {error && <p className="notice notice--bad" role="alert">{error}</p>}

          <button className="button" type="submit" disabled={!isReady || isSaving}>
            {isSaving ? "Saving…" : saved.length > 0 ? "Save & add another" : "Save round"}
          </button>

          <button
            className="link-button"
            type="button"
            onClick={() => setIsAdding(true)}
          >
            Add a different course
          </button>
        </form>
      )}

      {saved.length > 0 && (
        <>
          <div className="rule">
            <span className="rule__label">Added this session</span>
          </div>
          <ul className="session">
            {saved.map((round) => (
              <li key={round.id} className="session__row">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M4 12.5l5 5L20 6.5" />
                </svg>
                <span className="session__what">
                  {round.played_on} · {round.course_name} {round.tee_name}
                </span>
                <span className="session__score">{round.gross_score}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
