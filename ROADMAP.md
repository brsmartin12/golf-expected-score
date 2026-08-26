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
| Headline differentiator | **Current form** | Tier 3 is the destination; earlier tiers exist to feed it |
| Data entered per round | **Score only** — date, course, tee, total | No hole-by-hole, no fairways/GIR/putts. Low friction is a feature |
| Audience | **Me + golf friends** | `user_id` in the schema from day one; auth moves earlier than originally planned |
| Form factor | **Mobile first, desktop too** | Round entry happens on a phone; see below. Constrains layout and charts from Tier 1 on |
| Naming | **"Potential", never "expected"** | Potential is the 20th percentile of your differentials — a good round, not a typical one. `potential_score` / `to_potential` throughout, with `typical_score` / `to_typical` beside them for the median |
| Handicap index | **The app computes none, and labels nothing one** | Both figures are percentiles instead. See "Stop computing an index at all" below; this is why `handicap_snapshots` and `rounds.index_at_time` do not exist |
| Display convention | **Golf's to-par orientation, for every stroke number in the app** | A minus sign already means "under par" to a golfer, so negative is always the good direction and positive always the bad one — on the round card, the form table, the season table, and anything added later. `to_typical` and `to_potential` in the API carry that orientation. An analysis primitive may run the opposite way where higher-is-better averages more naturally, but is then never shown raw. If a new number cannot be expressed with negative-is-better, that is a signal it is the wrong number to put on a screen |

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
- **Connectivity is a design constraint, but be precise about which failure.**
  It is tempting to say "courses have no signal, so entry must work offline" and
  reach for a local draft. That reasoning does not survive contact: with no
  signal at all the app never loads, and a draft of a form you never reached
  saves nothing. Two different problems get conflated, and they have different
  fixes.

  **Loading the app offline** is a service-worker problem. Cache the bundle and
  the app opens with no network at all. That is the PWA item in Tier 5, and it
  is the only thing that addresses "no signal, full stop".

  **Not losing what was typed** is a separate problem that a cached app does not
  solve — caching the app does not preserve the form. Three cases make it real,
  and only one of them is about a golf course:

  1. *The backfill.* Thirty rounds entered at a desk in one sitting. An API
     hiccup at round 22 loses that entry and the user's place in the sequence.
     No signal problem involved at all, and this is the case most likely to make
     someone abandon the task half-finished.
  2. *The frontend and the API are different hosts.* The bundle is served from a
     CDN, the API from Railway or Render. They fail independently — a deploy, a
     cold start, a 502 — so the page loading says nothing about whether the API
     is reachable.
  3. *Signal that was there and then was not.* The realistic car-park failure is
     not "no network", it is a connection good enough to load the app and gone
     by the time the round is typed thirty seconds later.

  So: a local draft of the in-progress entry, cleared on a successful save and
  offered back on load, plus failing loudly with everything preserved rather
  than silently dropping a write. It is roughly ten lines and it is a hedge, not
  an offline story. The two stack — the service worker gets the app open, the
  draft keeps the typing — and neither substitutes for the other. Stale reads
  are tolerable; a lost write is not.
- **Sequencing.** The before-round card only gets interesting once rounds are
  stored — "typical here" and "your record here" need history — so it lands in
  Tier 2. Its *shape* is worth planning now, because it decides what the Tier 1
  queries have to support.

The API used to split along this seam with two calculator endpoints. Both went
with the handicap index: every number the app shows is now a quantile of a
golfer's own rounds, so the after-round moment is `POST /rounds`, which returns
the verdict in the same response. The before-round card has no endpoint yet — it
is the Tier 2 target card, and it reads the same quantiles against a tee the
golfer has not played yet.

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
  round, fetch history, read the form table — extends this module. The *pattern*
  is the durable part, not whichever functions happen to be in it. The two
  calculator calls it opened with are already gone.
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

What 30 rounds unlocks, honestly: typical and potential (which want 20 for a
full window), percentiles, and the distribution all work immediately. Current
form works with wide error bars at first. Course fit will mostly report *"need
more rounds here"* until a season accumulates — that is the shrinkage in Tier 4
behaving correctly, not a bug, but it is worth expecting.

**2. Each round is graded on the rounds played before it, and nothing else.**

If a past round is compared against *today's* typical, it silently rewrites
itself every time a new score is logged — and every trend in the app becomes
meaningless. (Data-science readers: this is point-in-time correctness, the same
discipline a feature store enforces.)

Two earlier plans for this are worth recording, because both were wrong in the
same direction. The first was to store the index on every round; hand-backfilling
makes that impossible, since nobody remembers their index from a Saturday two
years ago. The second was to make that column nullable and derive it when absent.

Neither is needed. **`played_on` is sufficient on its own**: sort the rounds by
the date they were played, and each one's history is the rounds before it in that
list. `golf.scoring.trailing` does exactly that, and `api/routers/rounds.py`
grades the whole series in one pass. A backfilled round entered last but played
first correctly gets no history at all, and becomes history for everything after
it.

The lesson generalises: point-in-time correctness comes from recording *when*
something happened, not from remembering what the answer was at the time.

### Schema

```
users              id, email, display_name
courses            id, name, city, state
tees               id, course_id, name, par, course_rating, slope_rating, yardage
rounds             id, user_id, tee_id, played_on, gross_score,
                   pcc (default 0), is_nine_hole, notes, created_at
```

Four tables, not six. `handicap_snapshots` and `rounds.index_at_time` were both
built and then dropped — see "Stop computing an index at all" below. What is left
is the raw record of what was played, which is the only thing worth storing.

Notes on the shape:

- **`tees` must be its own table.** Slope and rating are properties of a *tee*, not a
  course — the blues and the whites at the same club have different numbers. The
  original sketch in `CLAUDE.md` had one flat `courses` table with a `tee` column;
  that is the classic mistake here, and it is painful to undo once there are rounds
  pointing at it.
- **Store raw inputs only.** Differentials, typical and potential are *derived* —
  compute them on read through `golf/`. Never persist a computed value as the
  source of truth, or a formula fix leaves the database disagreeing with the code.
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

## The app's figures will not match GHIN, and should not try

**Decision: compute our own number, name it as ours, and show the official one
beside it when it is known.** Do not chase agreement with GHIN.

### Why agreement is not reachable

The largest gap is **Adjusted Gross Score**. GHIN caps every hole at net double
bogey — par + 2 + strokes received on that hole — before computing a
differential. This app takes the gross score, because it deliberately does not
collect hole scores, and net double bogey cannot be applied without them.

Simulated over 20,000 rounds per player:

| Player      | Gross | Adjusted | Lost to the cap | Rounds affected |
| ----------- | ----- | -------- | --------------- | --------------- |
| 5 handicap  | 86.0  | 84.9     | 1.12            | 52%             |
| 10 handicap | 92.4  | 91.0     | 1.42            | 61%             |
| 18 handicap | 101.0 | 99.7     | 1.34            | 55%             |

A stroke of gross score is 113/slope of a differential, so on a slope-130 course
each stroke lost to the cap is about 0.87 of a differential point — and an index
averages eight of them, so the bias carries through roughly 1:1. **Our figure
runs about 1 to 1.5 strokes worse than GHIN on identical rounds**, systematically
and always in the same direction.

Smaller sources on top of that: rounds posted to one and not the other, PCC
(usually 0 but not always), the low-index safeguards and exceptional-score
reduction, and nine-hole combining.

### Why it matters far less than it looks

**GHIN does not use a longer period either.** The WHS index is the best 8 of the
**last 20** differentials — 2019's rounds are not in it. So the populations can
converge, and after a 30-round backfill they largely have. "Their GHIN was built
over years" is true of the account, not of the calculation.

**Every headline number in this app is an internal comparison, so a consistent
bias cancels:**

- *typical vs potential* — both computed from the same differentials
- *form delta* — recent against the player's own baseline; no index appears at all
- *course fit* — per-course against the same player's overall; biased on both sides
- *round percentile* — a rank within the player's own rounds

The bias corrupts exactly one thing: a number labelled "handicap" sitting next
to a different number in the GHIN app. That is a naming problem, not a maths
problem — the same lesson as renaming "expected" to "potential".

### What follows: stop computing an index at all

Naming the figure carefully is not enough on its own. If the app computes
best-8-of-20 and calls it something else, the first person to ask "so how is
this worked out?" gets an answer that is recognisably the handicap formula with
pieces missing — which reads as a half-finished implementation rather than a
deliberate different measure.

So the app does not compute an index. **Potential is a percentile of the
golfer's own Score Differentials**, exactly as typical is their median:

```
typical differential   = median (50th percentile) of the last 20
potential differential = 20th percentile of the last 20
score on this tee      = differential x (slope / 113) + course rating
```

That last line is the same arithmetic the old index-based `potential_score` used
— an index was only ever an average of differentials wearing a different name.
What changes is where the number comes from, and what it can be asked about.

The whole question becomes answerable in one sentence with no asterisk:
*typical is the median of your last 20 rounds, potential is your 20th
percentile.* There is no cap to be missing and no safeguard to be absent,
because nothing is attempting to be a handicap.

Numerically it stays close to what an index would have given — the 20th
percentile runs about 0.3 strokes above best-8-of-20 for a steady player and 0.9
for a very streaky one — so the figure a golfer sees does not lurch.

Three things follow:

1. **A Score Differential needs no index**, which is what makes this possible at
   all: `score_differential(score, course_rating, slope_rating, pcc)`. Two
   golfers of wildly different ability who shoot the same score from the same
   tee get the same differential. The dependency runs rounds -> differentials ->
   quantiles, and stops there.
2. **`handicap_snapshots` is dropped.** Nothing reads it, and a figure entered
   once and never updated is confidently wrong within weeks — worse than showing
   nothing. If a golfer with no history ever needs a starting point, that is one
   nullable column on `users`, added when something actually needs it.
3. **`rounds.index_at_time` is dropped** for the same reason: with potential
   derived from the surrounding rounds, it is a breadcrumb pointing at a
   calculation the app no longer performs.

### The one thing this does NOT fix

**The app's figures still cannot allocate strokes between players.** The
percentile framing removes the credibility problem; it does nothing about the
fairness one, because the bias comes from gross scores containing blow-ups, not
from the best-8 formula.

Simulated with two players of genuinely equal ability — same mean score, one
steady and one streaky:

| Player  | Our figure | GHIN-style |
| ------- | ---------- | ---------- |
| steady  | 15.8       | 15.2       |
| streaky | 18.4       | 15.4       |

GHIN rates them 0.24 strokes apart. We rate them 2.4 apart. In a match the
streaky player would collect **over two strokes they have not earned** — which is
precisely the abuse the net double bogey cap exists to prevent, reintroduced.

So the rule is about **use**, not naming: *the app's own figures never allocate
strokes between players.* Everything self-referential — typical, potential, form
delta, course fit, percentile — is fine, because the same bias sits on both
sides of the comparison. Anything giving one golfer strokes against another
needs either Adjusted Gross Scores entered by everyone, or an official index the
group agrees on. `course_handicap` and `playing_handicap` stay in `handicap.py`
for that day, unused by the core loop until then.

**Worth testing when it is built:** the season table's beat-rate compares players
and derives from each one's own potential. Whether the blow-up bias contaminates
it is not obvious either way.

Worth noting this is not a shortcoming peculiar to this app: every golf app that
is not the handicap authority computes an unofficial figure and has exactly this
gap. The difference available to us is being explicit about it rather than
showing a number and hoping nobody cross-checks.

## Tier 2 — Analytics that need only a score column

All of these are pure functions living beside `handicap.py` in `backend/golf/`, with
pytest tests written against known-correct values first. Same treatment as the
existing math: framework-free, no I/O, provable.

- **Typical and potential.** ✅ Built — `golf/scoring.py`. The two quantiles, the
  20-round window, the inverse that turns a differential back into a score on a
  tee, and `trailing`, which grades each round on the rounds played before it.
  This replaced what used to be first on this list, a full WHS index calculation:
  see "Stop computing an index at all" above for why that is not being built.
- **What-if projection.** *"Shoot 84 today and your typical goes 89.2 → 88.9."*
  The single most-Googled question in amateur golf, and the USGA app buries it.
  Cheaper against a percentile than against an index: append the hypothetical
  differential, re-run the quantile, and show the difference.
- **Round percentile.** *"Your 85 was your 12th-best differential of 47 — you shoot
  this or better 26% of the time."* Near-zero implementation cost, largest emotional
  payoff on the roadmap, and it closes the exact "was that actually good?" loop that
  motivated the project.
- **Typical vs. potential.** Both numbers, side by side with the actual score. The
  headline screen of the whole app, and **typical is the one that leads**.

  Potential is beaten in only about one round in five — it is the best-8-of-20
  score by construction. So a card headlined on the gap to potential delivers
  bad news roughly four times out of five, however well the round was played.
  Typical is a coin flip for everyone, always, and it answers the question
  actually being asked in the car park: *was that a good round for me?*

  So: headline the gap to typical, carry the gap to potential beside it as
  context. That also gives the card four states rather than two — beat both,
  beat typical only, beat neither, and the rare beat-potential-but-not-typical —
  which is more interesting than a single verdict and is precisely what a
  calculator with no history cannot show.

  Note where this leaves the vocabulary. "Expected" was renamed to "potential"
  because the word was wrong *for the index-based number*, which describes good
  rounds rather than usual ones. The word itself was never wrong: **typical is
  the expected score**, the middle of what you actually shoot. Use "typical" in
  the UI, since it is concrete and cannot be misread — but the app's original
  question turns out to have a correct answer after all, which is worth
  remembering when the product name is finally chosen.

  Two states to design, both drawn: with history, and before typical has settled,
  where the card shows potential alone plus a countdown rather than inventing a
  median from four rounds.

  **How the two are computed.** One calculation, two settings:

  ```
  typical_differential   = median (50th percentile) of the last 20
  potential_differential = 20th percentile of the last 20
  score on this tee      = differential × (slope/113) + course_rating + pcc
  ```

  Three decisions in "the median of the last 20 Score Differentials", each with
  a reason:

  - **Median, not mean.** Golf scores are right-skewed — a lost ball or a triple
    has no mirror image on the good side. Simulated over 15,000 records with a
    realistic blow-up rate, a player beats their median exactly 50.0% of the
    time at every spread, and their mean 53–57%. The 50/50 property is the whole
    reason typical is fit to headline the card; the mean quietly flatters. The
    median is also stable where the mean is not: one disaster round moved a
    20-round mean from 15.88 to 16.88 and left the median at 15.24 untouched. A
    baseline should not lurch because of one bad Saturday.
  - **The last 20, the same window the index uses.** Potential and typical then
    come from the *same rounds* and are directly comparable. An all-time typical
    against a 20-round potential compares two different populations and the gap
    between them means nothing.
  - **Eight rounds minimum.** The median varies by about ±1.4 strokes at eight
    rounds and ±1.0 at twenty. Below eight, show the countdown rather than a
    number.

  Expect the gap to land near **0.85σ** — roughly 2.2 strokes for a steady
  player, 4.2 for a streaky one, which is itself worth surfacing later as a
  consistency reading.

  **Do not implement this twice.** Typical and the Tier 3 current-form estimate
  are the same machinery at different settings — typical is unweighted over the
  last 20, current form is recency-weighted over the same differentials. One
  function with a weighting parameter, not two that drift apart.
- **Cross-course translation.** *"Your 85 at Pine Hills is an 81 at Riverside."* The
  differential already normalizes across courses; this just re-expresses it in the
  units golfers actually think in.
- **Pre-round target card.** For today's course and tee: your typical score, your
  potential score, the score that would move your typical down, and your best
  round here. A reason to open the app *before* playing, not only after.

## Tier 3 — Current form (the headline)

Model the differential series instead of ranking it.

- **Estimate a running centre and spread** over your differentials with an
  exponentially weighted estimator, or a small state-space / Kalman formulation.
  Recent rounds dominate, so a hot streak shows up immediately instead of waiting for
  20 rounds to turn over.
- **Show it against the flat figure**, in strokes on the tee in front of you, so
  the two sit next to each other: *"You usually shoot 88 here. Right now you're
  playing like an 85."* Both sides are the same kind of number — a quantile of
  the same differentials, one weighted and one not — which is what makes the
  comparison legible rather than a comparison of two different measures.
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

- The naive version (mean strokes to potential per course) is pure noise at n=3, and
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
- **Leaderboard ranked on current form, normalised to each player's own game.**
  Not "who is the best golfer" — the handicap already answers that, and boringly.
  The question worth asking a friend group is **who is playing better than their
  own normal, right now**. A 22-handicap can top it. Paired with a **season
  table** answering the standings question — who has outgrown their handicap
  this year. See "The form table" and "The season table" below for both metrics,
  and "What the leaderboard has to get right" for the three things that make
  either of them harder than it looks.
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

### The form table

The metric is a **change**, not a level. For each player:

```
form_delta = weighted mean(recent differentials) - mean(baseline differentials)
```

**Negative means playing better than their own normal**, in strokes, because
negative is the good direction everywhere in this app — see the display
convention in the decisions table. A golfer reading `-2.4` sees two and a half
strokes to the good without being taught anything.

Rank ascending: most negative at the top.

Form has only this one orientation. Where an analysis primitive is defined the
other way round for averaging, the API exposes a display-oriented field beside it
(`to_typical`, `to_potential`); form exists only to be shown, so it is defined in
the display convention once and never flipped.

Three layers of normalisation fall out of that definition, which together are
what "normalised to their handicap" actually means:

1. **Course difficulty** — differentials already handle it. That is what a
   differential is for.
2. **Ability level** — the comparison is against the player's *own* baseline, so
   a 22-handicap and a 6-handicap are both being measured against themselves. No
   handicap arithmetic is needed to make them comparable.
3. **Volatility** — a 20-handicap's scores swing further than a 6's, so two
   strokes of improvement do not mean the same thing for both. Dividing the
   delta by that player's own differential standard deviation gives a
   standardised version, and since spread scales with handicap, this is the
   layer that does the actual handicap normalising.

Rank on the **stroke-denominated delta** because it is the one a golfer can read
without explanation ("Sam is playing 2.1 strokes better than his normal"), and
carry the standardised version alongside as the tie-break and as the "how
surprising is this" figure. The standardised version carries the same sign, so
negative stays good there too.

**It also happens to solve the sandbagging problem, for free.** Read the formula
again: no handicap appears in it — which is unsurprising, since the app computes
none. Both terms are the player's own
differentials, so inflating an index buys nothing — the baseline inflates with
it. The only way to game a form table is to play badly for months to depress
your own baseline, which costs real rounds and is a poor trade for a pint. This
supersedes the earlier suggestion of ranking on the best-8 figure to resist
manipulation; a form table does not need that defence.

**The windows must not overlap.** If the baseline includes the recent rounds,
the recent rounds pull the baseline toward themselves and the delta is
attenuated — real form changes look smaller than they are. Baseline is the
trailing rounds *before* the recent window.

**How much of a change is actually detectable.** This is the uncomfortable part,
and it should shape the design rather than be discovered later. With a typical
amateur differential spread of about 3.5 strokes:

| Recent | Baseline | Std. error | 95% confident at |
| ------ | -------- | ---------- | ---------------- |
| 5      | 20       | 1.75       | 3.4 strokes      |
| 8      | 20       | 1.46       | 2.9 strokes      |
| 10     | 30       | 1.28       | 2.5 strokes      |

So a two-stroke improvement over five rounds is **not** distinguishable from
noise. An honest form table would therefore report "no clear change" for almost
everybody, almost every week — which is correct, and unusable as a game.

The resolution: **rank on the point estimate so there is always an order, and
mark which gaps are real.** The table stays fun and always has a leader; the
players who are genuinely in form are visually distinct from the ones who are
merely at the top this week. Never state a form change as fact when the interval
covers zero.

**Two separate jobs, easily conflated.** Shrinkage (`n / (n + k)`) makes the
*ranking* fair when someone has few rounds; the confidence marker makes the app
*honest* about whether a gap is real. Neither substitutes for the other — a
shrunk delta can still be noise, and a significant delta still deserves shrinking
if it rests on six rounds. Both are specified under "What the leaderboard has to
get right".

**Sequencing.** Everything above is a pure function over lists of differentials,
so it belongs in `backend/golf/` with tests, alongside the Tier 3 current-form
work — the two share the same recency-weighted machinery. Only the grouping and
the screen wait for Tier 5.

### The season table — and why the obvious level metric is a trap

Two boards answering two different questions is worth having. The form table is
"who is hot"; the season table is the standings.

**What "level" was originally going to mean:** the average gap to potential over
a season.

**That version does not measure what it claims.** Potential sits at a fixed
percentile of a player's own differentials, so the gap between their average
round and their potential is essentially a fixed multiple of *their own spread*.
Simulated over 20,000 seasons per case:

| Player's spread (σ) | Mean gap to potential | % of rounds beating potential |
| ------------------- | --------------------- | ----------------------------- |
| 2.0                 | 1.85                  | 18.7%                         |
| 3.0                 | 2.78                  | 18.6%                         |
| 3.5                 | 3.24                  | 18.6%                         |
| 5.0                 | 4.64                  | 18.7%                         |
| 7.0                 | 6.53                  | 18.4%                         |

(Simulated against the best-8-of-20 figure the app used at the time. A 20th
percentile sits a few tenths away from that, so the multiple shifts slightly and
the *invariance* — the point of the table — does not.)

The average gap tracks σ almost exactly, at ≈ 0.93σ across the range. So **a
season table ranked on the average gap to potential is a consistency ranking
wearing a disguise** — the steadiest player wins, whether or not anyone is
playing above their normal. Calling that a "level" board mislabels it.

**Use the rate instead.** The right-hand column is flat: about 18.6% at every
spread. Rate of rounds that beat your potential is spread-neutral, so it
measures what it says it does, and it is more legible than an average anyway:

> Sam beat his handicap in 7 of 24 rounds — 29%, best in the group.

The ~19% baseline is a natural par line for the board: at 19% you are playing
exactly to your index, and above it you are outperforming it.

**What it actually detects.** A Handicap Index trails, by construction. A golfer
improving steadily beats it more often than 19% because the index has not caught
up. So the season table reads as *"whose handicap does not fit them this year"*.

**The index is a moving target, and it chases you.** Play well and it drops,
which raises the bar — so beating it gets harder exactly when you are playing
best. This is not a flaw to design around; it is the single most important fact
about the season table, and it has three consequences.

*It self-corrects, so nobody can lead forever.* Simulating a player who gains
four strokes over their first ten rounds and then holds that new level:

| Phase                | Rate of beating potential |
| -------------------- | ------------------------- |
| Rounds 1–20          | 33.9%                     |
| Rounds 21–40         | 19.9% — back to baseline  |

They are still four strokes better than they started. The index simply caught up.
That reset is a *feature*: it makes the season table a season-long competition
that starts fresh, rather than a permanent ranking the fastest improver owns
forever. It also quietly closes the sandbagging hole, since posting real scores
drags an inflated index back down.

*It forces the window to be the whole season, never a rolling one.* A rolling
beat-rate decays to 19% the moment a player plateaus, so it measures improvement
*velocity* — which is the form table's job. Cumulative over the season it is
robust to when the improvement happened. Same four-stroke gain, varying only in
timing:

| Improvement spread over | Season beat-rate | Index drop |
| ----------------------- | ---------------- | ---------- |
| First 10 rounds         | 27.0%            | 4.02       |
| First 20 rounds         | 26.9%            | 3.97       |
| First 30 rounds         | 26.5%            | 3.65       |
| All 40 rounds           | 25.2%            | 2.97       |
| Not improving           | 18.5%            | 0.02       |

*It means the index drop under-reports anyone still improving.* The last column
shows why: a golfer improving right up to the final round measures 2.97 of a
real 4.0, because the index has not finished catching up. The beat-rate column
barely moves, because those rounds were banked as beats when they happened.

**So: rank on the season beat-rate, and print the index change in the row.** The
rate is the fair ranking — spread-neutral and timing-robust. The index change is
the sentence a golfer actually wants ("you dropped 3.2 this season"), with the
honest caveat that it lags if they are still improving.

**How the two boards differ.** They correlate, and pretending otherwise would be
dishonest — but the time scale and the reference point differ:

- **Form** — about 5–10 rounds, measured against the player's own recent
  baseline. "Who is playing well right now."
- **Season** — the whole season, measured against the player's index. "Who has
  outgrown their handicap."

Someone improving all year appears on both. Someone who had one hot month
appears only on form. Someone steady and accurately handicapped appears on
neither, which is correct.

**Sandbagging applies here but not to form.** The season table measures rounds
against a player's own potential, so padding that potential is worth something.
The defence is the percentile itself: a 20th-percentile figure barely moves when
the bad four-fifths of the distribution gets worse. Rank on potential and never
on the current-form estimate, and it holds up for a friend group.

**Count or rate?** Rate is fairer — it does not reward whoever played most.
Count is more fun to say. Rank on the rate, print the count and the change in
potential in the row, and shrink the rate toward the ~19% par line for anyone with few
rounds rather than gating them out — see "What the leaderboard has to get
right".

**Consistency is a stat, not a third board.** Given that the average gap to
potential is ≈ 0.93σ — a fixed multiple of the player's own spread — a
consistency board and an average-based level board would be the same board
twice. Show σ on the player's own page with the
Tier 3 work, not as a competing ranking.

**Sequencing: ship form first.** It is the differentiated one, it needs no index,
and it is the reason to open the app. The season table is a straightforward
addition afterwards and should not delay it.

### What the boards feel like to use

**They belong to a third context, not the two moments.** Before-round and
after-round both happen at the course, on a phone, in a hurry. A leaderboard is
checked on the sofa, or opened because someone posted a round and the group chat
lit up. It is not time-pressured, it is not at the course, and it is the one
screen that will be **screenshotted into a group chat**. That last point is a
real design constraint: the layout has to survive being cropped and pasted, and
it has to explain itself to someone reading it cold.

**The form table.** Volatile on purpose — it should move week to week, and being
top of it is a streak, not a verdict.

```
FORM — last 8 rounds vs your own normal              this week

1  Sam      -2.4  ●  playing better than normal        8 rounds
2  Bri      -0.9  ○  within his normal range           6 rounds
3  Chris    -0.4  ◌  early days, 5 rounds so far       5 rounds
4  Dave     +1.6  ○  within his normal range          11 rounds

● a real change   ○ too small to call yet   ◌ provisional
Nobody here is a better golfer than anyone else. This is who is
playing above their own usual standard right now.
```

**The season table.** Slow, cumulative, resets at the start of a season. This is
the standings.

```
SEASON 2026 — rounds that beat your own handicap

1  Dave     31%   11 of 35     index  14.2 -> 11.4   -2.8
2  Sam      24%    6 of 25     index   9.1 ->  8.4   -0.7
3  Bri      17%    4 of 24     index  12.0 -> 12.1   +0.1

par is 19% — that is how often anyone beats their own handicap
```

**Six things the screen itself has to say**, not just this document:

1. **Neither board ranks who is the best golfer.** The handicap already does
   that and everyone knows it. Both are handicap-neutral by construction, so a
   22 can top either — and the *first* thing anyone will ask is why the
   22-handicap is winning. Answer it on the screen, in the screenshot.
2. **The two boards move at different speeds, and that is the point.** Form is
   supposed to churn. The season table is supposed to barely move. If they ever
   agree completely, one of them is redundant.
3. **"Within normal range" is the honest common case.** Most gaps are too small
   to call — the maths in the form table above says so plainly. The ranking
   still orders everybody so there is always a leader; the marker is what
   separates a real run of form from a good fortnight.
4. **The season table resets.** Say when, on the screen. Otherwise everyone
   assumes it is all-time and the January standings look broken.
5. **Last place is not an insult.** Bottom of the form table means playing below
   your own usual standard this month, which happens to everyone. Word it that
   way. "Worst" never appears.
6. **Negative is good, on every board.** `-2.4` on the form table and `-2.8` on
   the season table both mean strokes to the good, exactly as a scorecard reads.
   No board anywhere in the app may invert this, however natural "bigger number
   wins" feels for a leaderboard.

**Failure modes worth designing against:**

- *A new member feels shut out.* They should not be — five rounds is the floor
  and shrinkage does the protecting. Below five, frame the gap as a short
  countdown rather than a locked door: they will join mid-season and this is
  their first impression of the whole feature.
- *Somebody tops the form table on a few lucky rounds.* Prevented by the
  shrinkage, not by the minimum — the simulation above shows raw ranking is
  genuinely unfair at five rounds and shrunk ranking is not. Ship the shrinkage
  with the first version; it is not a refinement to add later.
- *Everything reads "within normal range" and the board feels pointless.* The
  ranking is what carries it; the marker is secondary information. Never hide
  the order behind the significance test.

**Expect small groups.** Four friends, not forty. A board of two is a
comparison, not a league, and should probably be laid out as one. Design for
two to six people and let it degrade gracefully upward, rather than the reverse.

**Notifications are the obvious engagement hook and the obvious way to become
annoying.** "Sam just took the form lead" is genuinely fun once a week and
intolerable daily. If it ships at all, it ships opt-in and rate-limited, and not
before the boards themselves have been used for a season.

### Still undecided

The design above is settled. These parameters are not, and are recorded here so
that a future session picks them deliberately rather than inventing them halfway
through an implementation.

- **Window sizes and recency weighting.** "Recent" is written as 5–10 rounds and
  "baseline" as 20–30 throughout, without a decision, and the exponential decay
  has no half-life attached. Pick these against the real backfilled history
  rather than in the abstract — 30 rounds is enough to see what the estimator
  does with them.
- **The shrinkage constant `k`.** Provisionally 10, which simulation shows makes
  a five-round newcomer exactly as likely to top the board as they deserve. It
  controls how fast a player earns the right to move; worth re-checking against
  the real backfilled history, but the fairness result is not delicate.
- **When a season starts.** Calendar year is the obvious default; a northern
  golf season running roughly April to October is arguably truer and makes the
  winter reset feel natural rather than arbitrary. Undecided.
- **Whether the season table's beat-rate is contaminated by the blow-up bias.**
  It compares players, and each player's potential carries a bias that scales
  with how often they blow up, so it may not cancel the way the self-referential
  measures do. Test it rather than assume. (`handicap_snapshots` no longer
  exists, so the older question of official-versus-computed is moot: every
  player's figure comes from the same calculation.)
- **Whether a season's beat-rate should use each round's point-in-time potential
  or one figure for the season.** Point-in-time is what `golf.scoring.trailing`
  already computes and is the honest default, but it means a player's early-season
  rounds are judged against a smaller sample than their late-season ones. Worth
  checking whether that skews a season ranking before shipping one.
- **Nine-hole rounds.** Stored, but the WHS rule for combining two nines into an
  18-hole differential is not implemented. Until it is they should be excluded
  from both boards, and the exclusion should be visible rather than silent.
- **Multiple group membership.** The schema allows it. Whether the form figure is
  global (the same number in every group) or scoped per group is a product
  question — global is simpler and probably right, since form is about a player
  and not about a group.
- **Tie-breaks.** The form table has one: the standardised delta. The season
  table has none, and percentages will tie often in a group of four.

### What the leaderboard has to get right

These are not schema problems, which is exactly why they need writing down —
they will not surface on their own when the tables get built.

**1. Thin history is handled by shrinking the number, not by excluding the
player.** The obvious defence — demand a long history before anyone is ranked —
is the wrong one. At one round a week, a fifteen-round gate is four months of
sitting out, and a member who joins in May would watch until September. Somebody
excluded from a leaderboard is not being protected from noise; they are being
given no reason to come back.

Shrink the delta toward zero by `n / (n + k)` instead, exactly as Tier 4 does for
course fit, and the fairness problem disappears on its own. Simulated with four
players where **nobody is actually improving**, so a fair board should put the
newcomer top a quarter of the time:

| Newcomer's rounds | Raw ranking | Shrunk (k=10) | Signal kept |
| ----------------- | ----------- | ------------- | ----------- |
| 5                 | 35.5%       | 25.1%         | 33%         |
| 7                 | 33.8%       | 25.7%         | 41%         |
| 10                | 31.6%       | 26.5%         | 50%         |
| 25                | 24.9%       | 24.9%         | 71%         |

Raw, a five-round newcomer tops the board 35.5% of the time on pure luck.
Shrunk, 25.1% — fair, at every sample size. **A five-round floor with shrinkage
is as trustworthy as a twenty-five-round floor without it**, and it lets people
play.

So: **the minimum is 5 rounds**, which is simply the fewest the metric can be
computed from — three in the recent window, two in the baseline. The recent
window adapts (`max(3, min(8, n // 3))`) so it exists at five rounds and settles
at eight once there is history to fill it. Nobody is ever left off the board for
having played too little; their number is just pulled toward the middle until
they have earned the right to move.

The season rate gets the same treatment, shrunk toward the ~19% par line rather
than toward zero:

| Raw          | Shown |
| ------------ | ----- |
| 2 of 5 = 40% | 26%   |
| 0 of 5 = 0%  | 12%   |
| 4 of 10 = 40%| 29%   |
| 8 of 25 = 32%| 28%   |

Note the second row. A newcomer with a rough first month shows 12%, not 0% — a
small sample should not humiliate anyone either. A member who tops the board on four
rounds discredits the whole thing in week one.

**2. Sandbagging, with a genuinely awkward twist.** Every handicap-based
competition invites inflating your handicap, and golf has a word for it. The
awkward part is which of our two numbers resists it:

  - **Potential**, at the 20th percentile, mostly ignores deliberately bad
    rounds: padding the top four-fifths of the distribution barely moves it.
    Resistant, much as an official index is, and for the same reason.
  - **Current form** — this app's headline feature — is recency-weighted. Bad
    rounds count fully and move it quickly. That responsiveness is the entire
    point for a solo golfer, and it is precisely what makes it easy to game in a
    competition.

  So the app's better statistic is its more manipulable one. **The form table
  above sidesteps this entirely** by never using an index: both of its terms are
  the player's own differentials. This point still stands for any *level*-based
  board — a season table ranked on strokes-vs-potential is exposed to it, and
  should rank on the best-8 figure if it is ever built.

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
