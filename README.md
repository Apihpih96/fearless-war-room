# Fearless War Room

A Fearless Draft prep tool for Cloud9's League of Legends coaches.
Built for the Cloud9 x JetBrains "Sky's The Limit" Hackathon 2026, Category 2.

## Setup

```
hackathon/
├── stl-hackathon-2026-grid-starter/   # official GRID data (never commit)
└── fearless-war-room/                 # this repo
```

```bash
git clone --filter=blob:none --sparse https://github.com/cloud9esports/stl-hackathon-2026-grid-starter.git
cd stl-hackathon-2026-grid-starter && git sparse-checkout set lol meta && cd ..
cd fearless-war-room
pip install -r requirements.txt
python pipeline/extract_drafts.py            # all LoL series
python pipeline/extract_drafts.py --team "Cloud9 Kia"   # quick test
python pipeline/build_scout.py               # step 2: scouting JSON for every team
python -m unittest discover tests            # tests (synthetic data, no GRID needed)
```

Outputs (gitignored, derived from licensed data):
- `cache/drafts.csv` one row per pick/ban, with game number, side, patch, result
- `cache/games.csv` one row per game, with both drafts and `burned_before` (Fearless locks)

Committed (aggregates only, allowed by the data license):
- `web/public/data/index.json` every team with games, win rate, headline insight, plus league-wide champion presence
- `web/public/data/teams/<team_id>.json` one scouting report per team (Cloud9 Kia, every LCS 2026 team, plus LCK/LEC/LTA teams)

## Opponent scout (step 2)

`pipeline/build_scout.py` turns the draft cache into a report per team, scoped to the team's latest season (2026 for LCS):

- **Champion table**: pick, ban, first-pick and first-ban rates, presence, win rate, bans aimed at the team, with sample sizes (`"7/10"`). Split by Fearless game number (G1, G2, G3+) and by side, plus pick rate vs the league.
- **Top lists**: picks, bans and first picks per game number and side.
- **Fearless shift**: the team's five G1 favorites; for each, what *the player who plays it* picks once it is burned or banned (role-correct via GRID rosters); share of G2/G3+ picks on champions never seen in a G1 vs the league average; pool size per game number; picks once 3+ favorites are gone.
- **Players**: each player's most-played champions and G3+ picks.
- **Insights**: 3 to 5 plain-English findings with evidence, chosen to answer *"What pick/ban tendencies repeat most?"* and *"How does the draft shift in Fearless G3/4/5?"*

First pick is read from draft order, not side: since 2026 Riot's First Selection lets a team take first pick or side, and 240 of the 2026 games in the data have red side picking first.

## Save-or-burn advisor & win probability (step 4)

`pipeline/build_model.py` builds a win-probability model from the draft cache and writes `web/public/data/model.json`:

- **Champion strength**: Bayesian-shrunk log-odds win rate — `(wins + 10×0.5) / (games + 10)` then logit. Strong champions get positive strength, weak ones negative.
- **Team Elo**: K=24, starting at 1500, updated in date order. Final rating per team.
- **Logistic regression**: fitted by plain gradient descent (L2 1e-3, 2000 iterations, lr 0.1) on four per-game features (blue perspective):
  1. `elo` — (blue rating − red rating) / 400 (ratings **before** the game, no leakage)
  2. `draft` — mean champion strength of blue picks minus red picks (leave-one-game-out)
  3. `blue` — intercept (blue-side advantage)
  4. `first_pick` — +1 if blue had first pick, −1 otherwise
- **Cross-validation**: 5-fold grouped by `series_id` (seed 7) → log loss 0.636 vs 0.693 baseline, accuracy 63.8%, 1,697 games.

The React app loads `model.json` (gracefully hides the bar/panel if missing) and shows:

- **WinBar** — horizontal bar above the draft with live blue vs red win %, updating as picks lock. Legend shows the four contributing parts (team form, draft, side, first pick).
- **AdvisorPanel** — save-or-burn recommendations for the team on the clock. Each champion gets a verdict chip (Take now / Save / Deny) with plain-English reasons. Clicking a row picks the champion.

Run: `python pipeline/build_model.py` after `build_scout.py`.

## Reported roster self-scout (step 5a)

`pipeline/build_roster.py` builds a scouting report for a mixed roster from each player's own games in the GRID data, on whatever team they played for. The default roster is Cloud9's 2027 reported lineup (reported 2026-11-23, not officially confirmed):

- **Frog** (top): No LoL player found in GRID data → flagged as `no_data`, top-lane pool unknown.
- **Blaber** (jungle): Games from Cloud9 Kia.
- **Loki** (mid): Games from Cloud9 Kia.
- **Yeon** (bot/ADC): Games from Team Liquid (multiple team name variants).
- **CoreJJ** (support): Games from Team Liquid (multiple team name variants).

Output: `web/public/data/teams/c9-2027.json` (aggregates only) + merged entry in `index.json`.

The web app shows a toggle "2027 reported | 2026 Kia" near the team select, a visible badge "reported 2027 roster, not official", and a compact "Roster pools" card listing each player's status and top champions. Win probability falls back to 2026 Cloud9 Kia Elo with a caveat note.

Run: `python pipeline/build_roster.py` after `build_scout.py`. Re-running is idempotent.

## Draft board (step 3)

React + Vite app in `web/`, reading the committed JSON.

```bash
cd web
npm install          # .npmrc sets legacy-peer-deps (works around an npm 10 peer bug)
npm run dev          # http://localhost:5173
npm test             # Fearless rules + scout suggestion tests (vitest)
npm run build        # static site in web/dist, deployable anywhere
```

- **Series**: Bo3 or Bo5, game tabs, score, winner per game. First selection defaults to the loser of the last game, and first pick and side are set separately (2026 First Selection).
- **Fearless rules**: every champion picked earlier in the series is burned for both teams (🔥), and bans reset each game. Locked champions can't be selected, and the burn count shows on every tab.
- **Draft**: the full 20-step tournament order with the active slot highlighted. Champion grid with search (Enter picks the first match), role filters and hide-locked. Undo. Saved in localStorage.
- **Live scout panel**: the opponent's likely picks and bans for *this* game number, minus everything locked. Their G1 favorites show as open, banned or burned, with the player's fallback picks. "Contested" champions sit high on both teams' lists, and the panel ends with the auto insights.
- Champion portraits come from Riot Data Dragon; it falls back to initials offline.

Before every push: `git ls-files | grep -Ei '\.(zst|jsonl|parquet|sqlite|duckdb)$|cache/'` should print nothing.

## Roadmap
1. Draft extractor (done)
2. Opponent scout stats by team and game number -> aggregate JSON (done)
3. Draft board with Fearless rules (React) (done)
4. Save-or-burn advisor + win-probability model (done)
5. Self-scout mode, polish, deploy
5a. Reported roster self-scout (done)

## JetBrains tools
PyCharm (pipeline), WebStorm (frontend), Junie (coding agent).
