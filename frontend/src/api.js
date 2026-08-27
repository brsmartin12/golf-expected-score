/**
 * The one place that knows how to talk to the backend.
 *
 * Keeping fetch calls out of the components means a component never deals with
 * status codes or JSON shapes -- it asks for a result and either gets one or
 * gets an Error. Same instinct as keeping `golf/` free of FastAPI: the UI layer
 * and the transport layer shouldn't be tangled together.
 */

// import.meta.env is Vite's build-time environment. The value is substituted
// into the bundle when the app is built, so this is NOT read at runtime -- a
// production build has the deployed URL baked in. Falls back to the local
// backend so `npm run dev` works with no .env file at all.
const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

/**
 * Turn a failed response into a sentence a human can act on.
 *
 * FastAPI returns two different shapes under `detail`: a plain string (from our
 * own ValueError handler in api/main.py) or an array of per-field validation
 * errors from Pydantic, like:
 *   [{ loc: ["body", "slope_rating"], msg: "Input should be <= 155", ... }]
 * Without this, the UI would show "[object Object]" for every 422.
 */
function describeError(status, problem) {
  const detail = problem?.detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    return detail
      .map((err) => {
        // loc is a path like ["body", "slope_rating"]; the last element is the
        // field name, which is the only part worth showing a user.
        const field = err.loc?.[err.loc.length - 1] ?? "input";
        return `${field}: ${err.msg}`;
      })
      .join("; ");
  }

  return `Request failed (HTTP ${status}).`;
}

async function getJson(path) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`);
  } catch {
    throw new Error(
      `Could not reach the API at ${API_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(describeError(response.status, problem));
  }

  return response.json();
}

async function postJson(path, body) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    // fetch only rejects when the request never completed -- server down, DNS
    // failure, or the browser blocking a cross-origin response. A 422 or a 500
    // is a *successful* round trip as far as fetch is concerned, which is the
    // single most surprising thing about this API coming from Python.
    throw new Error(
      `Could not reach the API at ${API_URL}. Is the backend running?`,
    );
  }

  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(describeError(response.status, problem));
  }

  return response.json();
}

/** Every round this golfer has logged, most recently played first. */
export function fetchRounds() {
  return getJson("/rounds");
}

/** Every course with its tees — what the picker renders. */
export function fetchCourses() {
  return getJson("/courses");
}

/**
 * One tee, in the shape the API expects.
 *
 * Shared by createCourse and addTees on purpose: the nine-hole ratings were
 * silently dropped once already by a hand-written field list that fell out of
 * step, and two copies of this would be two chances to repeat it.
 */
function teePayload(tee) {
  return {
    name: tee.name,
    par: tee.par,
    course_rating: tee.courseRating,
    slope_rating: tee.slopeRating,
    // Omitted when blank rather than sent as null, so the backend's
    // paired-or-absent check sees a clean absence.
    ...(tee.frontCourseRating === null ? {} : {
      front_course_rating: tee.frontCourseRating,
      front_slope_rating: tee.frontSlopeRating,
    }),
    ...(tee.backCourseRating === null ? {} : {
      back_course_rating: tee.backCourseRating,
      back_slope_rating: tee.backSlopeRating,
    }),
  };
}

/** Add a course and its tees together. A course with no tees is useless. */
export function createCourse({ name, city, state, tee }) {
  return postJson("/courses", {
    name,
    city: city || null,
    state: state || null,
    tees: [teePayload(tee)],
  });
}

/**
 * Add tees to a course that already exists.
 *
 * Separate from createCourse because a course is unique on name and location:
 * re-posting it to attach another tee is a 409, not an update. Returns the whole
 * course, so a caller replaces its copy rather than merging.
 */
export function addTees(courseId, tees) {
  return postJson(`/courses/${courseId}/tees`, tees.map(teePayload));
}

/**
 * Log a round. The response carries the verdict, so this is one request rather
 * than a save followed by a fetch — see the note on POST /rounds in the backend.
 */
export function createRound({ teeId, playedOn, grossScore, nine }) {
  return postJson("/rounds", {
    tee_id: teeId,
    played_on: playedOn,
    gross_score: grossScore,
    // null means all eighteen holes; "front" or "back" names the nine played.
    nine: nine || null,
  });
}
