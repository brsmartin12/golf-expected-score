/**
 * Adding a course, adding a tee to one already here, or filling in the ratings
 * a tee was entered without.
 *
 * Three modes on one form, because they collect overlapping fields. None of the
 * later two is a nicety; each closes a wall a real backfill actually hit. A
 * course is unique on name and location, so before "Add a tee" existed the
 * second set of tees you played at a course was unreachable. And before "Nine
 * ratings" existed, a tee entered with only its 18-hole figures could never
 * gain its nine-hole ones — the form insisted on the 18-hole fields again, so
 * the way through was to enter the course a second time, which is exactly what
 * happened.
 *
 * Slope and rating are typed here ONCE per tee and never again. That is the
 * whole point of the courses table: every round afterwards is a picker choice.
 *
 * The nine-hole ratings are optional in the first two modes and collapsed
 * behind a toggle, because most people will not have them to hand the first
 * time. They matter when they matter: without them a nine played from this tee
 * is logged but cannot be graded, and approximating them from the 18-hole
 * figures is worse than leaving the round out. The USGA prints all four at
 * ncrdb.usga.org as "Front (9)" and "Back (9)", each written "rating / slope".
 */
import { useState } from "react";

import { addTees, createCourse, updateTee } from "../api.js";

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
  // "new"    a course and its first tee
  // "tee"    another tee at a course already here
  // "nines"  the nine-hole ratings for a tee that was entered without them —
  //          the operation whose absence made a real backfill duplicate a course
  const [mode, setMode] = useState("new");
  const [courseId, setCourseId] = useState("");
  const [teeId, setTeeId] = useState("");

  const addingTee = mode === "tee";
  const fixingNines = mode === "nines";
  const chosenCourse = courses.find((c) => String(c.id) === String(courseId));
  // Only tees that still lack them: this mode exists to fill a gap, and
  // offering tees that are already complete just invites confusion.
  const teesMissingNines = (chosenCourse?.tees ?? []).filter(
    (t) => t.front_course_rating === null || t.back_course_rating === null,
  );

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
      const nines = {
        front_course_rating: optional(form.frontRating),
        front_slope_rating: optional(form.frontSlope),
        back_course_rating: optional(form.backRating),
        back_slope_rating: optional(form.backSlope),
      };
      // Send only what was filled in: PATCH treats an absent field as "keep".
      const given = Object.fromEntries(
        Object.entries(nines).filter(([, v]) => v !== null),
      );
      if (fixingNines && Object.keys(given).length === 0) {
        throw new Error("Fill in at least one nine's rating and slope.");
      }

      const course = fixingNines
        ? await updateTee(Number(courseId), Number(teeId), given)
        : addingTee
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
      const saved = fixingNines
        ? course.tees.find((t) => String(t.id) === String(teeId))
        : course.tees.find((t) => t.name === form.teeName) ?? course.tees[0];

      setForm(EMPTY);
      setShowNines(false);
      // The tee just fixed drops out of `teesMissingNines`, so a stale id would
      // leave the picker showing a value it no longer offers.
      setTeeId("");
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
              { value: "tee", label: "Add a tee" },
              { value: "nines", label: "Nine ratings" },
            ].map((option) => (
              <label key={option.value} className="choice__option">
                <input
                  type="radio"
                  name="mode"
                  value={option.value}
                  checked={mode === option.value}
                  onChange={(event) => {
                    setMode(event.target.value);
                    setTeeId("");
                    setError(null);
                  }}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {addingTee || fixingNines ? (
        <label className="field">
          <span className="field__label">Course</span>
          <select
            required
            value={courseId}
            onChange={(event) => {
              setCourseId(event.target.value);
              setTeeId("");
            }}
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

      {fixingNines ? (
        <label className="field">
          <span className="field__label">Tee</span>
          <select
            required
            value={teeId}
            onChange={(event) => setTeeId(event.target.value)}
            disabled={courseId === ""}
          >
            <option value="">
              {courseId === "" ? "Pick a course first…" : "Pick a tee…"}
            </option>
            {teesMissingNines.map((tee) => (
              <option key={tee.id} value={tee.id}>
                {tee.name}
              </option>
            ))}
          </select>
          {courseId !== "" && teesMissingNines.length === 0 && (
            <span className="field__hint">
              Every tee at this course already has its nine-hole ratings.
            </span>
          )}
        </label>
      ) : (
        <>
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
        </>
      )}

      {showNines || fixingNines ? (
        <>
          <div className="rule">
            <span className="rule__label">Nine-hole ratings</span>
          </div>
          <p className="field__hint">
            From the scorecard or ncrdb.usga.org, written &ldquo;rating /
            slope&rdquo;. Each nine is rated separately — the slopes often
            differ by several points, which is why both are asked for.
            {fixingNines
              ? " Fill in one nine or both; whichever you leave blank is left as it was."
              : " Leave blank and nines from this tee are logged but not graded."}
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
        disabled={
          isSaving ||
          (addingTee && courseId === "") ||
          (fixingNines && teeId === "")
        }
      >
        {isSaving
          ? "Saving…"
          : fixingNines
          ? "Save ratings"
          : addingTee
          ? "Add tee"
          : "Add course"}
      </button>
    </form>
  );
}
