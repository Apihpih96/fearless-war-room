# How Junie built Fearless War Room (AI-workflow log)

Junie CLI 26.11.2 ran headless (`junie --model=junie-lite --task "$(cat .junie/tasks/<task>.md)"`), signed in with the team's JetBrains account on the free Junie Lite tier. A reviewer (Hark) wrote the task specs, then checked every result with tests and browser screenshots before accepting it. Task specs are in `.junie/tasks/`, and Junie's own run output is in `.junie/runs/`. Project rules Junie follows are in `.junie/guidelines.md`.

| Date (MYT, UTC+08:00) | Task | What Junie did | Review outcome |
|---|---|---|---|
| 2026-11-23 | `step4.md` | Wrote `pipeline/build_model.py` (Elo, shrunk champion strength, logistic regression, grouped 5-fold CV), `model.js`, `advisor.js`, `WinBar`, `AdvisorPanel`, 6 Python and 20 vitest tests, README section | Tests passed, but a screenshot showed the bar and advisor never rendered |
| 2026-11-23 | `step4-fix1.md` | Found and fixed the `loadModel()` cache bug (`null !== undefined`), added fetch-stub tests, fixed footer | Bar and advisor rendered; layout and advisor perspective needed work |
| 2026-11-23 | `step4-fix2.md` | Rebuilt WinBar (user's team always left, parts legend), advisor always for the user's team, with pick, ban and "next pick" modes, plus perspective tests | Accepted: 37 vitest + 13 Python tests passing, build clean |
| 2026-11-24 | `step5a-c9-2027.md` | Added `pipeline/build_roster.py` (per-player champion pools for the reported 2027 Cloud9 roster, built from each player's own games), `roster.js`, a roster toggle, a badge and a Roster pools card, 15 Python and 16 vitest tests, and README metrics | Tests passed, but the screenshot showed wrong denominators (union of games), a Cloud9 Kia mirror as the default opponent, and the pools card hidden when C9 2027 is "Us" |
| 2026-11-24 | `step5a-fix1.md` | Switched to per-player denominators, added a `defaultOpponent` helper, showed the pools card on either side, fixed the mobile layout | Accepted: 32 Python + 62 vitest tests passing, build clean |
| 2026-11-24 | `step5b-polish.md` | Demo mode (auto-played illustrative draft with banner and Pause/Next/Exit), phone layout, ErrorBoundary, display-name helpers, GitHub Pages CI workflow, README update | Tests passed, but the production build was blank on a fresh first load (`effectiveSeries` null) and the Demo button wasn't reachable by role |
| 2026-11-24 | `step5b-fix1.md` | Widened the loading guard, added `resolveRenderPhase` with 8 regression tests, and gave the Demo button an accessible name | Accepted: 87 vitest + 32 Python tests passing, first load renders |
| 2026-11-24 | `step5b-fix2.md` | Phone overflow: `min-width: 0` across the flex chains, header stacking at ≤600 px | Partly: `overflow-x: clip` hid the scrollbar, but `scripts/overflow_check.py` still found elements past the viewport edge |
| 2026-11-24 | reviewer edit | Root cause was the `.app` grid's implicit `auto` column sizing to the widest `<select>` option, plus `nowrap` on the game controls at ≤412 px. Fixed with `grid-template-columns: minmax(0, 1fr)` and wrapping controls | Accepted: no element past the edge at 360 or 412 px, Demo plays on a phone |

## Lessons

- Green unit tests didn't catch a wiring bug. A rendered-UI check in the review loop did, so every Junie task now ends with a screenshot review.
- A hidden scrollbar isn't a fixed layout. The overflow check now lists every element past the viewport edge instead of reading `scrollWidth`.
