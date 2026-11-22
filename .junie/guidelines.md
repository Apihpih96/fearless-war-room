# Fearless War Room – guidelines for Junie

Project: Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026, Category 2 (League of Legends draft scouting for Fearless Draft).

## Layout
- `pipeline/` – Python 3 stdlib-only scripts. `extract_drafts.py` (GRID feeds -> `cache/*.csv`), `build_scout.py` (cache -> aggregate JSON in `web/public/data/`).
- `tests/` – Python `unittest` tests on synthetic data. Run: `python3 -m unittest discover -s tests -v`.
- `web/` – Vite 7 + React 19 app. Pure logic lives in `web/src/*.js` with vitest tests (`web/src/*.test.js`). Run: `cd web && npx vitest run`. Do NOT run `npm install` (node_modules is pre-provisioned).

## Hard rules
- LICENSE: GRID data is licensed. Never commit or copy anything from `cache/` or the starter repo. Only aggregates (counts, rates, fitted coefficients) may be written to `web/public/data/`. No per-game rows.
- Python: stdlib only (no numpy/pandas/sklearn).
- Fearless rules: every champion picked in an earlier game of the series is unavailable to BOTH teams; bans reset each game.
- 2026 "First Selection": first pick is independent of side; read first pick from draft order, never assume blue = first pick.
- Keep logic pure and tested; UI components stay thin.
- Use absolute ISO 8601 dates in docs.
