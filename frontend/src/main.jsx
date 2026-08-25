/**
 * The entry point: the bridge from the browser's DOM to React, and the route table.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import App from "./App.jsx";
import Group from "./routes/Group.jsx";
import LogRound from "./routes/LogRound.jsx";
import Rounds from "./routes/Rounds.jsx";
import "./styles/tokens.css";
import "./index.css";

// StrictMode is a development-only wrapper. It deliberately double-invokes
// component bodies to surface accidental side effects -- so if a console.log
// appears twice in dev, that is this, not a bug.
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* The parent route renders App, which draws the shell and an Outlet.
            The children render into that Outlet. `index` is the one shown at
            the parent's own path, "/". */}
        <Route path="/" element={<App />}>
          <Route index element={<LogRound />} />
          <Route path="rounds" element={<Rounds />} />
          <Route path="group" element={<Group />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
