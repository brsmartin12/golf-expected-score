/**
 * The entry point: the bridge from the browser's DOM to React's world.
 *
 * Everything below this file is React. Everything above it is a plain HTML page
 * with one empty <div id="root">.
 */
import React from "react";
import { createRoot } from "react-dom/client";

import App from "./App.jsx";
import "./index.css";

// StrictMode is a development-only wrapper. It deliberately double-invokes
// component bodies to surface accidental side effects -- so if you ever see a
// console.log appear twice in dev, that is this, not a bug.
createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
