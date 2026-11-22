# Step 4: Save-or-burn advisor + live win-probability bar

Read `.junie/guidelines.md`, `README.md`, `pipeline/build_scout.py`, `web/src/draft.js`, `web/src/scout.js`, `web/src/App.jsx` and `web/src/components/ScoutPanel.jsx` first.

## A. Python: `pipeline/build_model.py` (stdlib only)
Inputs: `cache/games.csv` (columns: series_id, game_id, game_number, patch, event, stage, date, format, blue_id, blue_name, red_id, red_name, winner_id, blue_picks, red_picks, blue_bans, red_bans, burned_before; picks/bans are `|`-separated champion names) and `cache/drafts.csv` (one row per draft action with seq, action pick/ban, team_id, side, champion, won_game; first pick = team with the lowest-seq pick).
Output: `web/public/data/model.json` with ONLY aggregates:
- `champions`: {name: {games, wins, strength}} where strength = log-odds of a Bayesian-shrunk win rate: (wins + 10*0.5)/(games + 10), logit.
- `teams`: {team_id: {name, games, rating}} where rating = Elo (K=24, start 1500) run over games in date order, final value.
- `coef`: logistic regression fitted by plain gradient descent (L2 1e-3, 2000 iters, lr 0.1) on per-game features computed from the blue team's perspective:
  1. `elo`: (blue_rating_before - red_rating_before)/400 (ratings BEFORE the game, so no leakage)
  2. `draft`: mean champion strength of blue picks minus red picks (use leave-one-game-out champion stats: subtract this game's own result before shrinking)
  3. `blue`: 1 (intercept = blue side advantage)
  4. `first_pick`: +1 if blue had first pick else -1
- `metrics`: {games, log_loss, accuracy, baseline_log_loss} from 5-fold cross validation grouped by series_id (fixed seed 7).
- `meta`: {generated (ISO 8601 UTC), patches, events count}.
Env vars like build_scout.py: FWR_CACHE_DIR, FWR_OUT_DIR. Add `tests/test_build_model.py` (unittest, synthetic games, check: strong champion gets positive strength, Elo moves winner up, coefficients finite, output has no per-game rows, CV runs).

## B. JS: `web/src/model.js` (pure) + `web/src/model.test.js`
- `winProbability(model, {blueTeamId, redTeamId, bluePicks, redPicks, blueFirstPick})` -> {p, parts:{elo, draft, side, firstPick}} probability that BLUE wins. Missing picks contribute 0 (draft partially filled is fine). Unknown team -> rating 1500. Unknown champion -> strength 0.
- `pickImpact(model, state, champion, team)` -> change in p for `team` if it picks `champion` now.

## C. JS: `web/src/advisor.js` (pure) + `web/src/advisor.test.js`
Save-or-burn advisor for the team on the clock in a Fearless series. For each available champion candidate (top 10 by our-team comfort + model strength) return {champion, verdict: "take-now" | "save" | "deny", score, reasons[]}:
- value_now = model pick impact + our comfort (our team's scout report pick rate for this champion).
- future_cost = our comfort weighted by games remaining in the series (Bo3/Bo5 aware, only if the series can still go that long) — burning a comfort pick now loses it for later games.
- deny_value = opponent's likely-pick score for this champion in remaining games (from scout.js `likelyPicks` / their report) — picking it burns it for them too.
- verdict: "deny" if deny_value dominates, "save" if future_cost > value_now and there are later games, else "take-now". Reasons are short plain-English strings, e.g. "Their #1 G3+ pick — burning it denies them", "Your comfort pick: 3 games left, consider saving".
- Last possible game of the series: nothing is saved (future_cost = 0).
Tests: deny case, save case, last-game case, burned/banned champions never suggested.

## D. UI
- `web/src/components/WinBar.jsx`: horizontal bar above the draft showing blue vs red win % with team names, updating live as picks are locked; tooltip/legend with the parts (team form, draft, side, first pick).
- `web/src/components/AdvisorPanel.jsx`: list for the team on the clock with verdict chips (Take now / Save / Deny) and reasons; clicking a row picks the champion (reuse existing select handler).
- Wire both into `App.jsx`; load `data/model.json` in `data.js` (app must still work if the file is missing: hide bar/panel).
- Styles in `web/src/styles.css`, consistent with existing look, mobile-friendly.

## E. Docs
README: add "Save-or-burn advisor & win probability (step 4)" section with method and CV metrics placeholder, mark roadmap item 4 done.

## Verify
Run `python3 pipeline/build_model.py`, `python3 -m unittest discover -s tests -v`, `cd web && npx vitest run`, `cd web && npx vite build`. All must pass. Do not commit; leave changes in the working tree.
