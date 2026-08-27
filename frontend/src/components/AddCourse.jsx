/**
 * Adding a course, or adding a tee to a course already here.
 *
 * Two modes on one form, because they collect almost the same fields. The
 * second one is not a nicety: a course is unique on name and location, so
 * before this existed the second set of tees you ever played at a course was
 * unreachable — you would meet that partway through a backfill, at the first
 * round from different tees, with no way past it.
 *
 * Slope and rating are typed here ONCE per tee and never again. That is the
 * whole point of the courses table: every round afterwards is a picker choice.
 *
 * The nine-hole ratings are optional and collapsed behind a toggle, because
 * most people will not have them to hand the first time. They matter when they
 * matter: without them a nine played from this tee is logged but cannot be
 * graded, and approximating them from the 18-hole figures is worse than leaving
 * the round out. The USGA prints all four at ncrdb.usga.org as "Front (9)" and
 * "Back (9)", each written "rating / slope".
 */
import { useState } from "react";

import { addTees, createCourse } from "../api.js";

const EMPTY = {
  name: "", city: "", state: "", teeName: "", par: "72",
  courseRating: "", slopeRating: "",
  frontRating: "", frontSlope: "", backRating: "", backSlope: "",
};

/** "" -> null, so an untouched optional field is omitted rather than sent as 0. */
function optional(value) {
  return value.trim() === "" ? null : Number(value);
}

export default function AddCourse({ courses = [], onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showNines, setShowNines] = useState(false);
  // "new" adds a course and its first tee; "tee" adds a tee to one already here.
  const [mode, setMode] = useState("new");
  const [courseId, setCourseId] = useState("");

  const addingTee = mode === "tee";

  function change(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setIsSaving(true);

    const tee = {
      name: form.teeName,
      par: Number(form.par),
      courseRating: Number(form.courseRating),
      slopeRating: Number(form.slopeRating),
      frontCourseRating: optional(form.frontRating),
      frontSlopeRating: optional(form.frontSlope),
      backCourseRating: optional(form.backRating),
      backSlopeRating: optional(form.backSlope),
    };

    try {
      const course = addingTee
        ? await addTees(Number(courseId), [tee])
        : await createCourse({
            name: form.name,
            city: form.city,
            state: form.state,
            tee,
          });

      // Hand back the tee that was just created, so entry continues on it.
      // Matched by name rather than by position: adding a tee returns the whole
      // course, and its tees come back in whatever order the database gives.
      const saved = course.tees.find((t) => t.name === form.teeName)
        ?? course.tees[0];

      setForm(EMPTY);
      setShowNines(false);
      onSaved(course, saved?.id);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
      {courses.length > 0 && (
        <fieldset className="choice">
          <legend className="field__label">Adding</legend>
          <div className="choice__options">
            {[
              { value: "new", label: "New course" },
              { value: "tee", label: "Tee to a course" },
            ].map((option) => (
              <label key={option.value} className="choice__option">
                <input
                  type="radio"
                  name="mode"
                  value={option.value}
                  checked={mode === option.value}
                  onChange={(event) => {
                    setMode(event.target.value);
                    setError(null);
                  }}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {addingTee ? (
        <label className="field">
          <span className="field__label">Course</span>
          <select
            required
            value={courseId}
            onChange={(event) => setCourseId(event.target.value)}
          >
            <option value="">Pick a course&hellip;</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
                {course.tees.length > 0 &&
                  ` — has ${course.tees.map((t) => t.name).join(", ")}`}
              </option>
            ))}
          </select>
        </label>
      ) : (
        <>
          <label className="field">
            <span className="field__label">Course name</span>
            <input name="name" required maxLength={120} placeholder="Pine Hills"
                   value={form.name} onChange={change} />
          </label>

          <div className="field-row">
            <label className="field">
              <span className="field__label">City</span>
              <input name="city" maxLength={80} placeholder="Austin" value={form.city} onChange={change} />
            </label>
            <label className="field field--narrow">
              <span className="field__label">State</span>
              <input name="state" maxLength={40} placeholder="TX" value={form.state} onChange={change} />
            </label>
          </div>
        </>
      )}

      <label className="field">
        <span className="field__label">Tee</span>
        <input name="teeName" required maxLength={40} placeholder="Blue"
               value={form.teeName} onChange={change} />
      </label>

      <div className="field-row">
        <label className="field field--narrow">
          <span className="field__label">Par</span>
          <input name="par" type="number" inputMode="numeric" required min="1" max="100"
                 value={form.par} onChange={change} />
        </label>
        <label className="field">
          <span className="field__label">Rating</span>
          <input name="courseRating" type="number" inputMode="decimal" step="0.1" required
                 min="0.1" placeholder="71.5" value={form.courseRating} onChange={change} />
        </label>
        <label className="field field--narrow">
          <span className="field__label">Slope</span>
          <input name="slopeRating" type="number" inputMode="numeric" required min="55" max="155"
                 placeholder="130" value={form.slopeRating} onChange={change} />
        </label>
      </div>

      {showNines ? (
        <>
          <div className="rule">
            <span className="rule__label">Nine-hole ratings</span>
          </div>
          <p className="field__hint">
            From the scorecard or ncrdb.usga.org, written &ldquo;rating /
            slope&rdquo;. Each nine is rated separately — the slopes often
            differ by several points, which is why both are asked for. Leave
            blank and nines from this tee are logged but not graded.
          </p>

          <div className="field-row">
            <label className="field">
              <span className="field__label">Front rating</span>
              <input name="frontRating" type="number" inputMode="decimal" step="0.1"
                     min="0.1" placeholder="35.8" value={form.frontRating} onChange={change} />
            </label>
            <label className="field field--narrow">
              <span className="field__label">Front slope</span>
              <input name="frontSlope" type="number" inputMode="numeric" min="55" max="155"
                     placeholder="130" value={form.frontSlope} onChange={change} />
            </label>
          </div>

          <div className="field-row">
            <label className="field">
              <span className="field__label">Back rating</span>
              <input name="backRating" type="number" inputMode="decimal" step="0.1"
                     min="0.1" placeholder="36.1" value={form.backRating} onChange={change} />
            </label>
            <label className="field field--narrow">
              <span className="field__label">Back slope</span>
              <input name="backSlope" type="number" inputMode="numeric" min="55" max="155"
                     placeholder="128" value={form.backSlope} onChange={change} />
            </label>
          </div>
        </>
      ) : (
        <button className="link-button" type="button" onClick={() => setShowNines(true)}>
          Add nine-hole ratings (optional)
        </button>
      )}

      {error && <p className="notice notice--bad" role="alert">{error}</p>}

      <button
        className="button"
        type="submit"
        disabled={isSaving || (addingTee && courseId === "")}
      >
        {isSaving ? "Adding…" : addingTee ? "Add tee" : "Add course"}
      </button>
    </form>
  );
}
