/**
 * All the logic behind the round-entry screen, deliberately separate from how it
 * looks.
 *
 * A custom hook is just a function whose name starts with `use` and which calls
 * other hooks. That naming is not decoration — it is how React knows to apply
 * the rules of hooks to it. What it buys here: the screen's behaviour lives in
 * one testable place, and a visual redesign rewrites the component that calls
 * this without touching any of it.
 *
 * Three behaviours worth naming:
 *
 *   Quick-add. After a save the course, tee and date stay and only the score
 *   clears, because consecutive backfilled rounds are usually at the same
 *   course and near each other in time. Thirty rounds becomes three keystrokes
 *   each instead of four fields each.
 *
 *   The draft. The in-progress entry is mirrored to localStorage so a failed
 *   save never loses what was typed. This is a hedge, not an offline story —
 *   see the connectivity note in ROADMAP.md for which failures it does and does
 *   not cover.
 *
 *   The session list. Rounds saved since the screen was opened, kept in memory
 *   so a long backfill shows its own progress and a typo is visible before the
 *   sitting ends.
 */
import { useCallback, useEffect, useState } from "react";

import { createRound } from "../api.js";

const DRAFT_KEY = "golf.roundEntry.draft";

export function todayIso() {
  // Local date, not UTC: toISOString() would roll over at 5pm in the US and
  // date a round to tomorrow.
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 10);
}

const EMPTY = { teeId: "", playedOn: todayIso(), grossScore: "", handicapIndex: "" };

function readDraft() {
  try {
    const stored = window.localStorage.getItem(DRAFT_KEY);
    return stored ? { ...EMPTY, ...JSON.parse(stored) } : EMPTY;
  } catch {
    // Private browsing, cleared storage, a corrupted value — none of which
    // should stop the screen loading.
    return EMPTY;
  }
}

export function useRoundEntry() {
  // The initialiser is passed as a function so it runs once, on mount, rather
  // than on every render.
  const [form, setForm] = useState(readDraft);
  const [saved, setSaved] = useState([]);
  const [verdict, setVerdict] = useState(null);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);

  // Mirror every keystroke to the draft. Cheap, and it means a crash or a
  // failed save leaves the typing intact.
  useEffect(() => {
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
    } catch {
      // Storage being unavailable is not worth breaking entry over.
    }
  }, [form]);

  const setField = useCallback((name, value) => {
    setForm((previous) => ({ ...previous, [name]: value }));
  }, []);

  const isReady =
    form.teeId !== "" && form.playedOn !== "" && form.grossScore.trim() !== "";

  const save = useCallback(async () => {
    setError(null);
    setIsSaving(true);

    try {
      const round = await createRound({
        teeId: Number(form.teeId),
        playedOn: form.playedOn,
        grossScore: Number(form.grossScore),
        handicapIndex:
          form.handicapIndex.trim() === "" ? null : Number(form.handicapIndex),
      });

      setVerdict(round);
      setSaved((previous) => [round, ...previous]);

      // Quick-add: keep the CONTEXT, clear what belongs to the round.
      //
      // Course, tee and date persist because consecutive entries share them.
      // The index deliberately does NOT, even though it is stable week to week:
      // left sticky, a backfill would stamp thirty rounds spanning three years
      // with whatever index was typed once at the start. That is silently wrong
      // history — the exact failure `index_at_time` was made nullable to avoid.
      // Retyping an index occasionally is a much smaller cost than fabricating
      // one for every round.
      setForm((previous) => ({ ...previous, grossScore: "", handicapIndex: "" }));
      return true;
    } catch (saveError) {
      // Deliberately does NOT clear the form. A failed save that also wipes
      // what was typed is the failure this whole mechanism exists to prevent.
      setError(saveError.message);
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [form]);

  const dismissVerdict = useCallback(() => setVerdict(null), []);

  return {
    form,
    setField,
    isReady,
    isSaving,
    error,
    verdict,
    dismissVerdict,
    saved,
    save,
  };
}
