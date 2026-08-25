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
play well — roughly your 20th–25th percentile round. The WHS itself notes that a
player's *average* differential runs about **3 strokes above** their index.

So the "expected score" this app computes today is subtly mislabelled. It is the
score you shoot on a good day, not the score you usually shoot.

That gap is where the whole product lives:

- **Show two expectations, not one.** *Potential* (index-based — what the USGA gives
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

---

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

Unchanged from `CLAUDE.md`. Calculation core (done), FastAPI wrapper, minimal React
form. Everything below assumes this exists.

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

If historical strokes-vs-expected is computed against *today's* index, every past
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
- **Store raw inputs only.** Differentials, course handicaps and expected scores are
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

- The naive version (mean strokes-vs-expected per course) is pure noise at n=3, and
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
- **Leaderboard ranked by strokes-vs-expected, not raw score.** A 22-handicap can beat
  a 6-handicap on it. This is the app's entire thesis applied to a friend group, and
  it is a better game than counting strokes.
- **Net match calculator.** Given players, a tee, and a format, compute course
  handicaps, allowances, and strokes given and received. `course_handicap` and
  `playing_handicap` in `handicap.py` already do this math — it needs a UI, not new
  formulas.

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
