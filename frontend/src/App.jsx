/**
 * The app shell: whatever the current route renders, plus the navigation.
 *
 * How routing works here
 * ----------------------
 * A single-page app has no server round trip when you move between screens, so
 * something has to map the URL to a component. React Router does that: main.jsx
 * declares the routes, and `<Outlet />` below is the hole the matched route's
 * component is rendered into. The shell — header, nav — stays put while only
 * the middle changes.
 *
 * Real URLs matter even here. /rounds is linkable, survives a refresh, and the
 * phone's back button does what it should.
 */
import { Outlet } from "react-router-dom";

import BottomNav from "./components/BottomNav.jsx";

export default function App() {
  return (
    <div className="shell">
      <main className="shell__body">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  );
}
