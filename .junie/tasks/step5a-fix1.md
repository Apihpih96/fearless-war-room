# Step 5a review fix 1

Read `.junie/guidelines.md`. Do not commit. Reviewer screenshot of the default view found these bugs:

1. **Wrong denominators in c9-2027.json.** Champion `picks.of` and `by_bucket.<G>.picks.of` use the union of all roster games (e.g. Vi "13/89 G1s", "18/231"). They must use THAT PLAYER's own game counts (Blaber: Vi 18/142 overall; G1 n of Blaber's G1 games). Fix in `pipeline/build_roster.py`; `top.picks` labels likewise. `sample` must expose `per_player` ({player: {games, by_bucket}}) — it is currently missing/None. Add tests asserting a champion's `of` equals its player's game count.
2. **Default opponent is Cloud9 Kia** (a mirror of our own 2026 team) when "Us" is c9-2027. The default opponent must exclude both "c9-2027" and "47351"; pick the first other LCS 2026 team. Also, when the user toggles 2027/2026, if the opponent equals the other C9 entry, keep the opponent unchanged but never auto-select a C9 entry. Add a vitest for the pure default-opponent helper (put it in `roster.js`).
3. **Roster pools card and roster flags are only rendered when c9-2027 is the opponent.** They must also render when c9-2027 is "Us" (the default!). Show a compact "Cloud9 2027 roster pools (reported, not official)" card in the scout section (or above the advisor) whenever either side is c9-2027: each role, player, status, games, top 3 champions with games; Frog row reads "No GRID data, top-lane pool unknown". Show the flag text there too.
4. Check the mobile layout at 412px width doesn't overflow with the new toggle and badge.

Verify: `python3 pipeline/build_roster.py`, `python3 -m unittest discover -s tests -v`, `cd web && npx vitest run`, `cd web && npx vite build --outDir /tmp/wb/dist`, then `rm -rf web/dist`. Report results and Vi's and Orianna's picks labels from the regenerated JSON.
