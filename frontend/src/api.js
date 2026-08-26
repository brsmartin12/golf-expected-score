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

/** The score this Handicap Index posts on this tee when it plays well. */
export function fetchPotentialScore({ handicapIndex, slopeRating, courseRating }) {
  return postJson("/potential-score", {
    handicap_index: handicapIndex,
    slope_rating: slopeRating,
    course_rating: courseRating,
  });
}

/** Grade a round that was actually played against that potential. */
export function fetchRoundVerdict({
  score,
  handicapIndex,
  slopeRating,
  courseRating,
}) {
  return postJson("/round", {
    score,
    handicap_index: handicapIndex,
    slope_rating: slopeRating,
    course_rating: courseRating,
  });
}

/** Every round this golfer has logged, most recently played first. */
export function fetchRounds() {
  return getJson("/rounds");
}

/** Every course with its tees — what the picker renders. */
export function fetchCourses() {
  return getJson("/courses");
}

/** Add a course and its tees together. A course with no tees is useless. */
export function createCourse({ name, city, state, tee }) {
  return postJson("/courses", {
    name,
    city: city || null,
    state: state || null,
    tees: [
      {
        name: tee.name,
        par: tee.par,
        course_rating: tee.courseRating,
        slope_rating: tee.slopeRating,
      },
    ],
  });
}

/**
 * Log a round. The response carries the verdict, so this is one request rather
 * than a save followed by a fetch — see the note on POST /rounds in the backend.
 */
export function createRound({ teeId, playedOn, grossScore, handicapIndex }) {
  return postJson("/rounds", {
    tee_id: teeId,
    played_on: playedOn,
    gross_score: grossScore,
    // Omitted rather than null-ed when unknown, which is the backfill case:
    // the index is derivable from the surrounding rounds later.
    ...(handicapIndex === null ? {} : { index_at_time: handicapIndex }),
  });
}
