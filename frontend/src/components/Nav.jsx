/**
 * The app's navigation: three tabs, at the bottom on a phone and along the top
 * on a desktop.
 *
 * Bottom on a phone because both of the app's moments happen there, often
 * one-handed — the bottom of the screen is where a thumb reaches. On a desktop
 * there is no thumb and no reach problem, and a full-width bar pinned to the
 * bottom of a 24-inch screen is the single thing that made the app look like an
 * enormous phone. The move is done in CSS with `order`, not with two
 * components: same markup, same tab state, one media query.
 *
 * `NavLink` is React Router's link that knows whether it is the current route.
 * It hands `isActive` to a className function, which is how the current tab
 * lights up without any state of our own.
 */
import { NavLink } from "react-router-dom";

const TABS = [
  {
    to: "/",
    label: "Log",
    // Icons are inline SVG rather than an icon font or emoji: they scale, they
    // recolour with currentColor, and they add no network request.
    icon: <path d="M12 5v14M5 12h14" />,
  },
  {
    to: "/rounds",
    label: "Rounds",
    icon: <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />,
  },
  {
    to: "/group",
    label: "Group",
    icon: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c0-3 2.7-5 6-5s6 2 6 5" />
        <path d="M16 6a3 3 0 010 6M18 20c0-2.4-.9-4.2-2.3-5.4" />
      </>
    ),
  },
];

export default function Nav() {
  return (
    <nav className="nav">
      {TABS.map(({ to, label, icon }) => (
        <NavLink
          key={to}
          to={to}
          // `end` stops "/" matching every route — without it the Log tab would
          // stay lit on every screen, since every path starts with "/".
          end={to === "/"}
          className={({ isActive }) => `nav__tab${isActive ? " nav__tab--on" : ""}`}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            aria-hidden="true"
          >
            {icon}
          </svg>
          <span className="nav__label">{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
