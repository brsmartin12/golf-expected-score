// Vite is the build tool: it serves the app in development (fast, with hot
// reloading) and bundles it for production with `npm run build`.
//
// The React plugin teaches it two things: how to compile JSX -- the HTML-ish
// syntax in .jsx files, which is not valid JavaScript and must be transformed
// into function calls -- and how to hot-reload a component without throwing
// away the state of the rest of the page.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned so it always matches an origin allowed by the API's CORS config
    // (see DEV_ORIGINS in backend/api/main.py). Vite silently moves to the next
    // free port if 5173 is taken, which would otherwise cause the browser to
    // start blocking responses with no obvious cause.
    port: 5173,
    strictPort: true,
  },
});
