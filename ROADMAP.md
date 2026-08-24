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

---

## Tier 0 — The calculator (build order steps 1–3)

Unchanged from `CLAUDE.md`. Calculation core (done), FastAPI wrapper, minimal React
form. Everything below assumes this exists.

## Tier 1 — History

Nothing in Tiers 2–5 works without stored rounds. Two things here matter more than
they look:

**1. CSV import of the existing spreadsheet, in this tier — not "someday."**

Cold start is what kills an analytics app. With no import path, the app has zero
rounds and is useless for a full season before it can say anything interesting. With
one, there is real analysis on day one, against data that already exists. This is the
single highest-leverage item on the roadmap and it is easy to keep postponing.

**2. Snapshot the handicap index in effect at the time of each round.**

If historical strokes-vs-expected is computed against *today's* index, every past
round silently rewrites itself every time the index moves — and every trend in the
app becomes meaningless. The round record has to remember what was true when it was
played. (Data-science readers: this is point-in-time correctness, the same discipline
a feature store enforces. It is much cheaper to get right now than to retrofit.)

### Schema

```
users              id, email, display_name
courses            id, name, city, state
tees               id, course_id, name, par, course_rating, slope_rating, yardage
rounds             id, user_id, tee_id, played_on, gross_score,
                   index_at_time, pcc (default 0), is_nine_hole, notes
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

- Auth (Supabase Auth or Clerk), groups, invitations.
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
