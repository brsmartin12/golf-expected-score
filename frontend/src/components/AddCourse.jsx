/**
 * Adding a course and one tee, so the app is usable on an empty database.
 *
 * Deliberately minimal: name plus a single tee. More tees at the same course
 * are added the same way for now, and the real answer is seeding courses from
 * the existing spreadsheet — see step 5 in CLAUDE.md.
 *
 * Slope and rating are typed here ONCE per tee and never again. That is the
 * whole point of the courses table: every round afterwards is a picker choice.
 */
import { useState } from "react";

import { createCourse } from "../api.js";

const EMPTY = { name: "", city: "", state: "", teeName: "", par: "72", courseRating: "", slopeRating: "" };

export default function AddCourse({ onAdded }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  function change(event) {
    const { name, value } = event.target;
    setForm((previous) => ({ ...previous, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setIsSaving(true);
    try {
      const course = await createCourse({
        name: form.name,
        city: form.city,
        state: form.state,
        tee: {
          name: form.teeName,
          par: Number(form.par),
          courseRating: Number(form.courseRating),
          slopeRating: Number(form.slopeRating),
        },
      });
      setForm(EMPTY);
      onAdded(course);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="card form" onSubmit={submit}>
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

      {error && <p className="notice notice--bad" role="alert">{error}</p>}

      <button className="button" type="submit" disabled={isSaving}>
        {isSaving ? "Adding…" : "Add course"}
      </button>
    </form>
  );
}
