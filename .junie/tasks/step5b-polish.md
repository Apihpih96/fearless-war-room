# Step 5b: polish pass for demo + deploy

Read `.junie/guidelines.md` and follow its hard rules. Do not commit. Do not run `npm install`.

## 1. Guided demo mode (for the submission video)
- Add a "▶ Demo" button in the header. It starts a fresh Bo3 series "Cloud9 2027 (reported)" vs "LYON" and auto-plays an ILLUSTRATIVE scripted Fearless series (hard-code the action list in `web/src/demo.js`, NOT taken from any real game: invent a plausible 20-action draft for G1 and a partial G2 that shows burned champions). Step every ~1.6 s, with Pause/Resume, Next and Exit controls.
- Each step can carry a short caption shown in a banner (e.g. "G2: everything picked in G1 is burned for both teams", "Advisor: Deny Xin Zhao, LYON's top pick", "Win probability moves with each pick"). Label the banner "Illustrative demo draft".
- Pure logic (script validation: every action legal under Fearless rules via existing draft.js functions; step/advance state) in `demo.js` with vitest tests (the script must replay with no illegal action).

## 2. Phone layout (412 px)
- Long team names wrap badly. Add a `shortName` (e.g. "C9 2027", "C9 Kia", else name truncated to ~12 chars) in a pure helper with tests; use it in the step line, WinBar labels and column headers at narrow widths (keep the full name in a `title` attribute).
- The step line ("Step 1/20 · Ban 1 · … bans") and Undo should sit on one row; the First pick / side selects should not wrap awkwardly.
- No horizontal scroll at 360 px or 412 px.

## 3. Robustness
- Add a React ErrorBoundary around the board with a friendly "Something broke – New series" reset.
- Make sure these do not crash and behave correctly: Bo5 to game 5; Undo back across the start of a game; New series; choosing c9-2027 as the opponent; swapping side mid-series; a report or model.json failing to load (app still works, panels show a short "not available" note). Add tests for the pure parts.

## 4. Ship-ready
- `vite.config.js`: `base: "./"` so the build works on GitHub Pages under a sub-path. Data fetches must use relative URLs (`import.meta.env.BASE_URL` or "./data/...").
- `index.html`: title "Fearless War Room – Cloud9 draft prep", meta description, theme-color, Open Graph tags, a simple SVG favicon ("FWR").
- Add `.github/workflows/pages.yml`: on push to main, setup Node 22, `cd web && npm ci && npx vitest run && npx vite build`, upload `web/dist` with actions/upload-pages-artifact and deploy with actions/deploy-pages. Also a Python job running `python -m unittest discover -s tests`. (Tests must not need GRID data; skip any that do when STL data is absent.)
- README: "Live demo" placeholder line, a "How to run" section (no GRID data needed to run the web app since aggregates are committed), and roadmap 5b done.

## Verify and report
`python3 -m unittest discover -s tests -v`, `cd web && npx vitest run`, `cd web && npx vite build --outDir /tmp/wb/dist`, then `rm -rf web/dist`. Report counts and what changed.
