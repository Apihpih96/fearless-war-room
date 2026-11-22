# How Junie built step 4 (AI-workflow log)

Junie CLI 26.11.2 ran headless (`junie --model=junie-lite --task "$(cat .junie/tasks/<task>.md)"`), signed in with the team's JetBrains account on the free Junie Lite tier. A reviewer (Hark) wrote the task specs, then checked every result with tests and browser screenshots before accepting it. Task specs are in `.junie/tasks/`, and Junie's own run output is in `.junie/runs/`. Project rules Junie follows are in `.junie/guidelines.md`.

| Date (MYT, UTC+08:00) | Task | What Junie did | Review outcome |
|---|---|---|---|
| 2026-11-23 | `step4.md` | Wrote `pipeline/build_model.py` (Elo, shrunk champion strength, logistic regression, grouped 5-fold CV), `model.js`, `advisor.js`, `WinBar`, `AdvisorPanel`, 6 Python and 20 vitest tests, README section | Tests passed, but a screenshot showed the bar and advisor never rendered |
| 2026-11-23 | `step4-fix1.md` | Found and fixed the `loadModel()` cache bug (`null !== undefined`), added fetch-stub tests, fixed footer | Bar and advisor rendered; layout and advisor perspective needed work |
| 2026-11-23 | `step4-fix2.md` | Rebuilt WinBar (user's team always left, parts legend), advisor always for the user's team, with pick, ban and "next pick" modes, plus perspective tests | Accepted: 37 vitest + 13 Python tests passing, build clean |

Lesson: green unit tests didn't catch a wiring bug. A rendered-UI check in the review loop did, so every Junie task now ends with a screenshot review.
