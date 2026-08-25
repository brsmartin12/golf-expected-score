/**
 * The Group tab.
 *
 * Deliberately empty for now. Groups arrive with authentication at step 10 —
 * there is no second golfer to compare against until then, and the form table
 * needs stored rounds before it can say anything. See Tier 5 in ROADMAP.md.
 */
export default function Group() {
  return (
    <>
      <header className="page__header">
        <h1 className="page__title">Group</h1>
      </header>

      <div className="card empty">
        <svg
          width="30"
          height="30"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          aria-hidden="true"
        >
          <circle cx="9" cy="8" r="3" />
          <path d="M3 20c0-3 2.7-5 6-5s6 2 6 5" />
          <path d="M16 6a3 3 0 010 6M18 20c0-2.4-.9-4.2-2.3-5.4" />
        </svg>
        <p className="empty__title">Not built yet</p>
        <p className="empty__body">
          The form and season tables need sign-in, and a few friends with rounds
          of their own. They come last on purpose.
        </p>
      </div>
    </>
  );
}
