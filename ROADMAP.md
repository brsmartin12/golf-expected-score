# Roadmap

## Why this app exists

The USGA already ships a handicap calculator. A form with three inputs — index,
slope, rating — has no reason to exist a second time.

What the USGA does *not* give you is your history back. It gives you a number and
treats every round you post as an anonymous input to that number. It will not tell
you whether you are playing well *right now*, how consistent you are, or which
courses suit your game.

Those questions are only answerable once rounds accumulate. That is the product.

## The insight the whole roadmap rests on

A WHS Handicap Index is the average of your **best 8 of the last 20** score
differentials.

Read that again, because everything below follows from it: an index is a measure of
your **potential**, not your expectation. It describes the round you shoot when you
play well — roughly a top-quartile round, since 12 of the 20 differentials are
discarded before the index is calculated.

How far above it your *typical* round sits depends on your consistency: for a
roughly normal spread the mean of the best 8 of 20 lands around 0.8 standard
deviations below the overall mean, so a streaky player's gap is wider than a
steady player's. That gap cannot be derived from an index alone — it needs a
scoring record, which is exactly what Tier 1 onwards is for.

This is why the code calls that number **potential**, never "expected". It is the
score you shoot on a good day, not the score you usually shoot.

That gap is where the whole product lives:

- **Show two numbers, not one.** *Potential* (index-based — what the USGA gives
  you) and *typical* (your actual mean, learned from your own rounds). "You shot 85.
  Typical for you here is 86.1. Your potential is 83.0." That single screen is
  already something no calculator provides.
- **The official index reacts slowly by design.** Best-8-of-20 is a deliberately
  conservative, slow-moving, *governing* number — it has to be, since it decides
  competitive fairness. It is a trailing indicator. A **current-form estimate** is a
  leading one, and it is ours to build.
- **Consistency is invisible in the index.** Two 12-handicaps — one who shoots 82–88,
  one who shoots 76–96 — are completely different golfers with the same handicap. The
  spread is half of what defines a player and nobody surfaces it.

## Design decisions already made

| Decision | Choice | Consequence |
|---|---|---|
| Headline differentiator | **Current-form index** | Tier 3 is the destination; earlier tiers exist to feed it |
| Data entered per round | **Score only** — date, course, tee, total | No hole-by-hole, no fairways/GIR/putts. Low friction is a feature |
| Audience | **Me + golf friends** | `user_id` in the schema from day one; auth moves earlier than originally planned |
| Form factor | **Mobile first, desktop too** | Round entry happens on a phone; see below. Constrains layout and charts from Tier 1 on |
| Naming | **"Potential", never "expected"** | The number is the best-8-of-20 score, i.e. a good round, not a typical one. `potential_score` / `strokes_vs_potential` / `to_potential` throughout. \"Typical\" is reserved for the median figure that arrives with stored rounds |
| Display convention | **Golf's to-par orientation** | The gap to potential shows as `+5.0` over (worse) and `-4.0` under (better), because a minus sign already means "under par" to a golfer. `strokes_vs_potential` in the API is the opposite sign on purpose — it is the analysis primitive, where higher is better. Never show it raw |

---

## Two moments, not one app

The app is opened at two distinct times, and they want different things.

**Before the round — standing at the course.** What should I shoot here? Which
tee should I play? Have I played well here before? What number today would move
my index? Entirely read-only, and moderately time-pressured: this happens in the
car park or on the first tee, not at a desk.

**After the round — still in the car park.** Log it in fifteen seconds, and
immediately find out whether it was any good. A write plus instant feedback, and
the more time-pressured of the two. This is where the app gets abandoned if it is
slow, which is the whole reason for the score-only scope decision.

Why the pairing matters: post-round logging is a *chore*, and every golf app has
one. Before-round is a reason to open the app when you are actually looking
forward to something, and almost nothing does it well. The chore is what makes
the data exist; the before-round moment is what makes the app worth keeping on a
phone. Neither survives alone — so do not let the pre-round card get filed as a
nice-to-have next to the logging screen.

### What this implies

- **Two entry points, not one form.** The Tier 0 screen conflates them: a single
  form where a score is optional. That is the calculator framing, and it is one
  of the things Tier 0 says gets replaced. The two moments deserve two screens
  that happen to share maths.
- **One "me, at this tee, today" call.** Both moments want the same bundle: the
  tee's slope, rating and par; the current index; potential and typical here;
  and the record at this course. Serving that in a single request keeps both
  screens fast and stops the frontend orchestrating three round trips. Worth
  knowing before the models land, since it shapes what they need to make cheap.
- **Connectivity is a design constraint, not an afterthought.** Both moments
  happen at a golf course, and plenty of courses have poor signal or none. A
  post-round entry that fails in the car park does not merely annoy — it loses
  the round, and the fifteen-second promise with it. Before Tier 1 ships, decide
  whether entry queues locally and syncs later, or at minimum fails loudly with
  everything still in the form and nothing silently dropped. Stale reads are
  tolerable; a lost write is not.
- **Sequencing.** The before-round card only gets interesting once rounds are
  stored — "typical here" and "your record here" need history — so it lands in
  Tier 2. Its *shape* is worth planning now, because it decides what the Tier 1
  queries have to support.

Today `POST /potential-score` answers the before-round question and `POST /round`
answers the after-round one, so the API already splits along this seam. It is the
UI and the data layer that still need to.

## Mobile is the primary form factor

This is not polish, and it is not only about small screens looking tidy.

The score-only decision exists because **a round must stay a 15-second entry**.
A 15-second entry happens in the parking lot straight after the round — on a
phone. If logging a round means sitting down at a laptop later that evening,
the friction that score-only entry was designed to eliminate comes straight back
in through the other door, and the round simply never gets logged. Mobile is what
makes the core scope decision actually work.

Desktop still matters, but for a different job: reading trends, comparing
courses, importing the spreadsheet. Entry is a phone activity; analysis is a
lean-back activity. The app needs both, and they are not the same screen.

What this means concretely:

- **Design at 375px first**, then let the layout widen. Going the other way —
  building a desktop screen and shrinking it — is how dense dashboards end up
  unusable on the device they are most needed on.
- **Inputs at a 16px minimum font size.** iOS Safari zooms the whole page when
  focusing anything smaller, and it does not zoom back out cleanly.
- **`inputMode="decimal"` on numeric fields**, so phones raise a number pad
  instead of a full keyboard. Score entry is all digits.
- **Touch targets at least 44px tall.** Comfortably bigger than a mouse needs.
- **Tier 2–4 charts must be legible at 375px.** This is the real constraint of
  this decision. Trend lines with error bars and per-course distributions are
  easy to make dense; they have to survive a narrow screen or they will be
  built twice.
- **Later, and cheap: a PWA manifest** so the app can be added to the home
  screen and open without browser chrome. Worth doing around Tier 5, once it is
  something you would use every week.

The step 3 frontend already has the viewport meta tag, a single-column layout,
relative units and a max-width, so it is most of the way there. The known gaps
are `inputMode` on the numeric fields and an actual pass at 375px.

## Tier 0 — The calculator (build order steps 1–3)

Calculation core, FastAPI wrapper, minimal React form. Everything below assumes
this exists.

**The screen this produces is scaffolding, not the product.** It is a handicap
calculator — precisely the thing the top of this document says has no reason to
exist a second time. Right now the app is strictly *worse* than the USGA's,
because theirs also stores your rounds. That is expected at this tier, and it is
not a sign the plan is wrong.

So: do not invest in polishing this screen. It exists to prove the
browser → HTTP → Python → rendered pixels round trip works, and to be the
smallest possible surface on which to learn React.

**What survives from Tier 0:**

- `frontend/src/api.js` as the transport boundary. Every later call — post a
  round, fetch history, get the form index — extends this module. The *pattern*
  is the durable part, not the two functions currently in it.
- The `VITE_API_URL` wiring, used verbatim when the frontend is deployed.
- The CORS allowlist and the production build pipeline.
- **The to-par display convention** (see the decisions table above). Every later
  screen inherits it.
- The `ResultCard` framing — the gap to potential as the headline, with the
  expectation as supporting context. That presentation *is* the product thesis.
- Working familiarity with React, which is the real deliverable of a learning
  project.

**What gets replaced:**

- **The form.** Once `courses` and `tees` exist you pick a course from a list
  instead of retyping slope and rating every round. Manual entry of a tee demotes
  to an edge case for a course not yet added.
- **The single-screen layout.** It becomes round entry, history, trends and
  course fit — separate views with navigation between them.

## Tier 1 — History

Nothing in Tiers 2–5 works without stored rounds. Two things here matter more than
they look:

**1. Backfill the round history in this tier — not "someday."**

Cold start is what kills an analytics app. With no history the app has zero rounds
and is useless for a full season before it can say anything interesting. With a
backfill there is real analysis on day one.

The history lives in **18Birdies**, which has no CSV or spreadsheet export — so
there is no import to write. It is roughly **30 rounds**, entered by hand in one
sitting of ten or fifteen minutes. That makes the backfill a *data-entry UX*
problem rather than a parsing problem, and it is why quick-add entry (below) is
part of this tier rather than a nicety.

The existing spreadsheet is **not** round history — it is a calculator over a
handful of local courses. It is still worth importing, as seed data for `courses`
and `tees`, because that is what turns round entry into picking a course from a
list instead of retyping slope and rating every time.

What 30 rounds unlocks, honestly: the full WHS index (which needs 20), percentiles,
the distribution, and typical-vs-potential all work immediately. The current-form
index works with wide error bars at first. Course fit will mostly report *"need
more rounds here"* until a season accumulates — that is the shrinkage in Tier 4
behaving correctly, not a bug, but it is worth expecting.

**2. Handicap index at the time of each round: store it when known, derive it
when not.**

If historical strokes-vs-potential is computed against *today's* index, every past
round silently rewrites itself every time the index moves — and every trend in the
app becomes meaningless. (Data-science readers: this is point-in-time correctness,
the same discipline a feature store enforces.)

The original plan was to store the index on every round. Hand-backfilling makes
that impossible in practice: nobody remembers what their index was on a Saturday
two years ago. Fortunately it does not have to be remembered. Once the raw rounds
are in with their dates, **the index at any date is derivable** — it is the best 8
of the trailing 20 differentials, which is exactly what the Tier 2 index
calculation computes.

So `index_at_time` is **nullable**: populated when it is genuinely known (going
forward, or from an official record), derived from the surrounding rounds when it
is not. The point-in-time discipline is preserved; the data-entry burden that would
have blocked the backfill is not.

### Schema

```
users              id, email, display_name
courses            id, name, city, state
tees               id, course_id, name, par, course_rating, slope_rating, yardage
rounds             id, user_id, tee_id, played_on, gross_score,
                   index_at_time (nullable), pcc (default 0), is_nine_hole, notes
handicap_snapshots id, user_id, effective_on, index_value
```

Notes on the shape:

- **`tees` must be its own table.** Slope and rating are properties of a *tee*, not a
  course — the blues and the whites at the same club have different numbers. The
  original sketch in `CLAUDE.md` had one flat `courses` table with a `tee` column;
  that is the classic mistake here, and it is painful to undo once there are rounds
  pointing at it.
- **Store raw inputs only.** Differentials, course handicaps and potential scores are
  *derived* — compute them on read through `golf/handicap.py`. Never persist a
  computed value as the source of truth, or a formula fix leaves the database
  disagreeing with the code.
- **`user_id` from the start**, before auth ships. Adding a column is easy; adding a
  tenancy boundary to a table full of data is not.
- **Quick-add entry is part of this tier.** After saving, the form keeps the
  course, tee and date and clears only the score, so consecutive rounds at the
  same course take a few keystrokes. Entries appear in a running list so a typo
  is visible before the sitting ends. This is one button and a smarter reset on
  the form that already has to exist — not a separate screen.
- **Honest caveat to document:** score-only entry means Adjusted Gross Score is just
  the gross score. True AGS caps each hole at net double bogey, which needs hole-level
  data we have deliberately chosen not to collect. Fine for personal tracking — worth
  stating plainly rather than pretending the number is official.

## Tier 2 — Analytics that need only a score column

All of these are pure functions living beside `handicap.py` in `backend/golf/`, with
pytest tests written against known-correct values first. Same treatment as the
existing math: framework-free, no I/O, provable.

- **Full WHS index calculation.** Best 8 of the last 20, plus the low-index safeguard,
  the exceptional-score reduction, and the reduced-table rules for players with fewer
  than 20 rounds. Fiddly, entirely deterministic, and a perfect fit for the
  test-first approach the project already uses.
- **Index projection / what-if.** *"Shoot 84 today and your index goes 12.4 → 12.1."*
  This is the single most-Googled question in amateur golf and the USGA app buries it.
  It falls straight out of the index calculation above.
- **Round percentile.** *"Your 85 was your 12th-best differential of 47 — you shoot
  this or better 26% of the time."* Near-zero implementation cost, largest emotional
  payoff on the roadmap, and it closes the exact "was that actually good?" loop that
  motivated the project.
- **Typical vs. potential.** Both numbers, side by side with the actual score. The
  headline screen of the whole app.
- **Cross-course translation.** *"Your 85 at Pine Hills is an 81 at Riverside."* The
  differential already normalizes across courses; this just re-expresses it in the
  units golfers actually think in.
- **Pre-round target card.** For today's course and tee: your typical score, your
  potential score, the score that would lower your index, and your best round here.
  A reason to open the app *before* playing, not only after.

## Tier 3 — Current-form index (the headline)

Model the differential series instead of ranking it.

- **Estimate running mean μ and spread σ** over your differentials with an
  exponentially weighted estimator, or a small state-space / Kalman formulation.
  Recent rounds dominate, so a hot streak shows up immediately instead of waiting for
  20 rounds to turn over.
- **Derive a form index** from μ and σ on the same scale as the official index, so the
  two can sit next to each other: *"Official 12.4. You're playing like a 10.8."*
- **Consistency (σ) as a first-class stat**, trended over time. See the two-12-
  handicaps point above — this is a real, legible difference between players that
  every other golf app throws away.
- **Trend with honest error bars.** *"Improving 1.8 strokes/year, significant"* versus
  *"flat — your last 6 rounds are within noise."* Golfers over-read three good rounds
  constantly. Refusing to claim a trend that isn't there is a feature, and it is the
  thing that makes the rest of the numbers trustworthy.

## Tier 4 — Course fit, done honestly

*"This course plays well with your game"* — with the statistics that make it true
rather than merely fun.

- The naive version (mean strokes-vs-potential per course) is pure noise at n=3, and
  will confidently tell you a course you played once on a good day is your best
  course. **Shrink each course's estimate toward zero** — empirical Bayes / James–
  Stein, `effect × n/(n+k)` — and carry a confidence interval alongside it.
- **Only label a course a good or bad fit when its interval excludes zero.**
- Otherwise say **"not enough data yet — 4 more rounds here."** Honest, and it hands
  the user a concrete reason to keep logging rounds.
- Apply the same treatment **per tee**, and optionally grouped by course length or
  rating band — which starts to answer *why* a course fits, not just *that* it does.

## Tier 5 — Social

This is where "me + golf friends" pulls auth forward from its original step 6.

- **Google sign-in**, groups, invitations.

  The OAuth flow itself is close to free — one library call
  (`signInWithOAuth({ provider: "google" })`). Nobody should hand-roll OAuth.
  The cost lives elsewhere, roughly in this order:

  1. **Threading `user_id` through every query.** The largest piece by far, and
     the one already pre-paid by putting `user_id` in the schema back at Tier 1
     rather than retrofitting it here.
  2. **Verifying the token on the FastAPI side.** A JWT signature check against
     the provider's public keys, wrapped in one FastAPI dependency that turns a
     request into a `user_id`. Around 30 lines. A new concept, but a small one.
  3. **Google Cloud Console setup.** The OAuth consent screen, authorised
     origins, redirect URIs. Genuinely fiddly, mostly clicking, and the error
     messages when it is wrong are unhelpful. Budget an hour of irritation.
  4. **Frontend session handling.** Storing the session, refreshing it, putting
     the app behind a login, logging out. Probably introduces a router.
  5. **Local development.** Signed-in has to work locally too, or there needs to
     be a deliberate bypass.

  Realistically **one to two focused sessions** once the schema exists — *if*
  Postgres is already on Supabase, since Auth then comes in the same box and
  shares the same user table. That is a real argument for choosing Supabase
  over Railway for the database back at Tier 1.

  **Sequencing: leave this at Tier 5, don't move it up.** Until then a single
  hardcoded dev `user_id` is enough. Auth adds a token to every request and a
  login wall to every local test, in exchange for nothing at all while you are
  the only user.

  One fork to decide here, not now: Supabase's Row Level Security enforces
  tenancy in the database instead of in application code, which is the safer
  pattern — but it expects requests to carry the user's JWT, which fits
  Supabase's own client libraries better than SQLAlchemy connecting with a
  service credential. With SQLAlchemy the practical answer is to enforce
  `user_id` in application code and route every query through one place that
  cannot forget.
- **Leaderboard ranked by strokes-vs-potential, not raw score.** A 22-handicap can beat
  a 6-handicap on it. This is the app's entire thesis applied to a friend group, and
  it is a better game than counting strokes. Three things make it harder than it
  looks — see "What the leaderboard has to get right" below.
- **Net match calculator.** Given players, a tee, and a format, compute course
  handicaps, allowances, and strokes given and received. `course_handicap` and
  `playing_handicap` in `handicap.py` already do this math — it needs a UI, not new
  formulas.

### Schema, and why none of it is needed yet

Groups are **purely additive**: two new tables, and not one column changes on an
existing one.

```
groups             id, name, created_by_user_id, created_at
group_memberships  group_id, user_id, role, joined_at   (primary key: group_id + user_id)
```

Optionally later, and also additive:

```
outings            id, group_id, tee_id, played_on      -- one round played together
rounds.outing_id   nullable FK, null for a solo round
```

That is the whole difference between this and the decisions Tier 1 had to get
right up front. `rounds.user_id` genuinely *was* expensive to retrofit — every
existing row would have needed an owner invented for it — which is why it went
in before authentication existed. Groups are not like that: a join table added
later starts empty and breaks nothing, so building it now would mean unused
tables whose shape is still hostage to decisions authentication has not made.

The scaffolding that mattered is therefore already done, and it is worth being
concrete about what that means:

- `rounds.user_id` exists and is enforced, so every round already has an owner.
- `users.email` is unique, which is the column an OAuth identity maps onto.
- `get_current_user` in `api/deps.py` is a single dependency every route already
  goes through, so multi-user is a change to one function, not to every query.
- A test already asserts one golfer cannot see another's rounds.

**So: do not build the group tables before authentication.** Build them in the
same piece of work, once there is more than one real user to put in them.

### What the leaderboard has to get right

These are not schema problems, which is exactly why they need writing down —
they will not surface on their own when the tables get built.

**1. A ranking is meaningless for a member with thin history.** Strokes-vs-
potential needs each member's index, and an index derived from four rounds is
noise. A new member will then either top or bottom the table for purely
statistical reasons, and the leaderboard loses credibility the first week
somebody joins. Same discipline as course fit in Tier 4: show a position only
once the data supports it, and say *"needs 6 more rounds"* until then.

**2. Sandbagging, with a genuinely awkward twist.** Every handicap-based
competition invites inflating your handicap, and golf has a word for it. The
awkward part is which of our two numbers resists it:

  - The **official WHS index** averages the *best 8 of 20*. Deliberately bad
    rounds are discarded, so it is quite resistant by construction.
  - The **current-form index** — this app's headline feature — is a
    recency-weighted mean. Bad rounds count fully and move it quickly. That
    responsiveness is the entire point for a solo golfer, and it is precisely
    what makes it easy to game in a competition.

  So the app's better statistic is its more manipulable one. For a friend group
  the stakes are a pint and the answer is probably "rank on the best-8 figure,
  show current form alongside it as information" — but that should be a decision
  taken deliberately, not a default that falls out of using the headline number
  everywhere.

**3. Privacy and leaderboard integrity pull against each other.** A per-round
"don't share this one" flag is trivial to add later. What is not trivial is that
a leaderboard where members can hide their bad rounds stops being a leaderboard
and becomes a ranking of who hid the most. Pick one and be explicit: either
rounds posted while in a group are visible to that group, or the leaderboard
openly reports how many rounds each member has withheld. Silently allowing
hidden rounds is the one option that is actually dishonest.

## Tier 6 — Stretch

- Automatic course and tee slope/rating lookup, so adding a course isn't manual data
  entry (originally build order step 7).
- **Real PCC.** The `pcc` parameter already exists in `score_differential` and sits
  unused at 0.0. Historical weather for the date and course could drive an informal
  conditions adjustment — *"you lose 3.4 strokes above 15 mph"* is a genuinely
  personal insight and the parameter is already threaded through the math.

## Explicitly out of scope

Hole-by-hole entry, strokes gained, shot tracking, GPS, fairways/GIR/putts.

This follows directly from the score-only decision. It is where most golf apps die:
the analysis gets richer, the data entry gets tedious, and the user stops logging
rounds — at which point every feature above stops working. A round must stay a
15-second entry.
