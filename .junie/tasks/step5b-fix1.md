# Step 5b review fix 1: app crashes on first load

Read `.junie/guidelines.md`. Do not commit. Do not run `npm install`.

Reviewer loaded the production build in headless Chromium with an empty localStorage: the page is blank, console error `Cannot read properties of null (reading 'games')`. Cause: in `web/src/App.jsx` the loading guard became `if (!index) return …` but `effectiveSeries` is still null on the first render (series is created by an effect). Restore the guard so nothing reads `effectiveSeries` before it exists (e.g. `if (!index || !effectiveSeries) return <div className="splash">Loading war room…</div>;`). Also make sure the ▶ Demo button is a real `<button>` with accessible name "Demo" (aria-label) so it can be found by role.

Add a regression test so this class of bug is caught: a vitest that server-renders `<App />` (react-dom/server `renderToString`) with `localStorage` absent/empty and fetch stubbed to return the committed `web/public/data/index.json`, a team report, and model.json, and asserts it does not throw (initial render shows the loading splash). If App's effects make this hard, extract the pure "what should render" decision into a small helper and test that, plus keep a plain renderToString smoke test of the first render.

Verify: `cd web && npx vitest run`, `cd web && npx vite build --outDir /tmp/wb/dist`, then `rm -rf web/dist`, and `python3 -m unittest discover -s tests`. Report.
