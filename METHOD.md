# How the numbers are worked out

The short answer, and the reason the app is built this way at all:

> **Typical** is the median of your last 20 Score Differentials. **Potential**
> is your 20th percentile. Both are then expressed as a score on the tee you
> played.

That is the whole calculation. There is no handicap in it, nothing is
discarded, and no step is missing. This file is the long version, for when the
short one prompts a follow-up question.

`ROADMAP.md` is the *why* — what the product is for. This is the *how*.

---

## 1. A round becomes a Score Differential

```
Score Differential = (113 / Slope Rating) x (Gross Score - Course Rating - PCC)
```

| Term | What it is |
|---|---|
| **Gross Score** | The number on your card. Not adjusted — see §5. |
| **Course Rating** | What a scratch golfer is expected to shoot from that tee. |
| **Slope Rating** | How much harder the course plays for a bogey golfer than a scratch one. 55–155, and 113 is average — that is the 113 in the formula. |
| **PCC** | Playing Conditions Calculation, a course-wide adjustment for the day. Almost always 0. |

The differential is what makes rounds comparable. An 88 is a different round
depending on where it was shot:

```
88 at 74.5 / 145  ->  10.5     a strong round
88 at 69.0 / 113  ->  19.0     a poor one
```

**No handicap enters this.** A differential is a function of the score, the
rating, the slope and the PCC alone. Two golfers of wildly different ability who
shoot the same score from the same tee produce the same differential. That is
what makes everything below possible without an index.

Code: `backend/golf/handicap.py::score_differential`

## 2. Differentials become typical and potential

Take your last 20 differentials and read two quantiles off them:

```
typical   = the 50th percentile (the median)
potential = the 20th percentile
```

**Why the median and not the mean.** Golf scores are right-skewed — a lost ball
has no mirror image on the good side — so the mean is dragged up by disasters
and you beat it only 53–57% of the time. You beat your median exactly half the
time, by construction. That 50/50 property is the whole reason typical is fit to
headline a round card. The median is also stable where the mean is not: in
simulation one disaster round moved a 20-round mean from 15.88 to 16.88 and left
the median at 15.24 untouched.

**Why 20 rounds.** The same window the WHS uses, so the two are drawn from the
same population if anyone compares them.

**Why 8 rounds minimum.** A median moves about ±1.4 strokes at eight rounds and
±1.0 at twenty. Below eight the app shows a countdown instead of a number.

Code: `backend/golf/scoring.py::typical_differential`, `potential_differential`

## 3. Back into strokes on your tee

A differential is course-neutral, which is what made it comparable — and not
something anyone thinks in. So it is converted back:

```
score = differential x (Slope / 113) + Course Rating + PCC
```

which is §1 solved for the score. One typical differential of 13.7 renders as:

```
Blue, all 18  (71.9 / 129)   ->  87.5
Blue, front 9 (35.8 / 130)   ->  43.7
```

Same number, different units. This is also what makes cross-course translation
free: *"your 85 at Pine Hills is an 81 at Riverside"* is §1 followed by §3.

Code: `backend/golf/scoring.py::score_from_differential`

## 4. Nine-hole rounds

A nine is rated against **that nine's own published Course Rating and Slope**,
which the USGA lists per tee as "Front (9)" and "Back (9)". Halving the 18-hole
rating is accurate to about 0.13 strokes, but the two nines' slopes genuinely
differ — one real card reads 111 overall, 116 front, 105 back — so the published
figures are stored and never approximated.

That produces a nine-hole differential, which is then put onto the 18-hole scale:

```
contributed = typical + (2 x nine_differential - typical) / sqrt(2)
```

**Why not just double it.** Doubling doubles the noise along with the signal,
giving sqrt(2) times too much spread. The WHS's own method — fill the holes not
played with your expected score — has the opposite problem, since an imputed
mean adds no variance at all. Typical is a median and survives either; potential
is a percentile, and a percentile moves with the spread of its population. The
multiplier that reproduces a real eighteen's spread is the geometric mean of the
two, which is sqrt(2).

A nine then counts as one round like any other, and is graded against a typical
*nine*. `ROADMAP.md` carries the simulations.

**One rule this creates.** A scaled nine has an eighteen's *distribution*, which
is what a quantile needs. It does not carry an eighteen's *information* — twenty
nines are worth about 10.8 eighteens. So anything that takes a **mean** or puts
an **error bar** on a window must instead double the nine and weight it 0.5.
Skip that and confidence intervals come out up to 20% too narrow.

Code: `backend/golf/scoring.py::eighteen_from_nine`, `benchmarks`

## 5. What this app deliberately does not do

### It computes no Handicap Index, and labels nothing one

A WHS index is the average of your **best 8 of the last 20** differentials. We
could compute that. We don't, and the reason is the question this file exists to
answer: a figure worked out as best-8-of-20 is recognisably the handicap
formula, so the first person to ask how it works would find that formula with
pieces missing — no net double bogey cap, none of the WHS safeguards — and read
it as a half-finished handicap rather than a different measure chosen on purpose.

A percentile has no such problem. Nothing is absent from it.

The two are close in any case: a 20th percentile runs about 0.3 strokes above
best-8-of-20 for a steady player and 0.9 for a very streaky one.

### It uses Gross Score, not Adjusted Gross Score

The WHS caps every hole at net double bogey before computing a differential.
We use the score on the card, and you are never asked to adjust anything.

Partly that is circular to compute — net double bogey needs a Course Handicap,
which needs an index we do not have. Mostly it is that **we are answering a
different question**. AGS exists to keep one disaster hole from wrecking a
handicap that other people will give strokes against. Nobody asks what they
would have shot if their triple had been capped. Asked what you usually shoot,
the honest answer is the number on the card.

What it costs, over 4,000 simulated rounds per player:

| Player | typical | potential | the gap |
|---|---:|---:|---:|
| steady (rare blow-ups) | +0.00 | +0.00 | +0.00 |
| typical (some blow-ups) | **+1.80** | +0.00 | **+1.80** |
| streaky (often blows up) | **+2.60** | +0.90 | **+1.70** |

Potential is barely touched — a good round has few disasters to cap. Typical
carries all of it, so **the gap between the two runs about 1.7 strokes wider
here than a WHS-based figure would show.**

### It never allocates strokes between players

This follows directly from the row above. The blow-up inflation is
self-referential: your round and the typical it is measured against are both
uncapped, so `to_typical` reads true. It does **not** cancel between people —
two golfers a handicap system would rate 0.24 apart can come out 2.4 apart here,
because the bias scales with how often each of them blows up.

So these figures are for comparing you with yourself. Giving strokes in a match
needs Adjusted Gross Scores from everyone, or an official index the group agrees
on. `course_handicap` and `playing_handicap` remain in `handicap.py` for that
day; they take an official index typed in on the day, never one we derive.

## 6. Known biases, in one table

Everything above, with the numbers attached. All are measured by simulation, not
asserted; the runs are described in `ROADMAP.md`.

| Effect | Size | Direction | Who it hits |
|---|---|---|---|
| Small-sample bias in the 20th percentile | +0.17 strokes | potential reads slightly high | everyone, at 20 rounds |
| Gross instead of Adjusted Gross | +1.8 to +2.6 on typical | typical reads high, gap reads wide | anyone who blows up |
| Nine-hole scaling (sqrt(2)) | +0.18 on potential | same as the 20-round floor above | unchanged by nine share |
| Nine-hole scaling, if doubled instead | −0.23 | potential would read flatteringly low | not used |
| Nine-hole scaling, WHS mean-fill instead | +0.53 | potential would read low | not used |
| Nine bootstrap pivot from doubled nines | −0.09 | typical reads slightly low | golfers with few full rounds |

For comparison, the same treatment applied to GHIN's own nine-hole method puts
their index about **+0.5 strokes high** at a 50% nine share. Their error runs in
the safe direction for a handicap authority — too many strokes is not
sandbagging. Ours would land on potential, where the same bias understates the
number a golfer most wants right, which is why the methods diverge.

## 7. Where each piece lives

```
backend/golf/handicap.py    one round -> a Score Differential
backend/golf/scoring.py     many differentials -> typical, potential, nine-hole scaling
backend/api/routers/rounds.py   grades each round on the rounds played BEFORE it
```

Nothing derived is ever stored. Differentials, typical and potential are
computed on every read, so a formula fix cannot leave the database disagreeing
with the code — and so a round's verdict always reflects the rounds around it
rather than a value frozen at entry.
