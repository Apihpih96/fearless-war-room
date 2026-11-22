# Step 4 review fix 2 (from reviewer's screenshot of C9 Kia vs LYON, G2, LYON banning)

1. WinBar layout (`web/src/components/WinBar.jsx` + styles): it currently shows "Cloud9 Kia [bar] LYON 50.8% 49.2% form … draft … side … 1st pick …" so it is unclear whose % is whose and the bar does not use the full width. Make it: `Cloud9 Kia 50.8%` on the left in the blue-side colour of THAT team, the bar filling the remaining width (left segment = left team's probability), `49.2% LYON` on the right. Put the parts legend on a second small line underneath, labelled from the left team's perspective, e.g. "Cloud9 Kia: team form −11.7 pts · draft +0.0 · side +14.1 · first pick +0.8". The left team must always be the user's team (the first team select), whatever side it plays, and the bar must follow the side swap correctly (winProbability returns P(blue wins)).
2. Advisor perspective (`AdvisorPanel.jsx`, `advisor.js` usage in `App.jsx`): always advise the user's team (first team select), never the opponent. Title: "Advisor · Cloud9 Kia" (team name).
   - When it is the user's team's PICK turn: current save/take/deny list.
   - When it is the user's team's BAN turn: show "Ban suggestions": opponent's likely picks for this game (scout `likelyPicks` on the opponent report, availability-aware), each with reason, clicking bans it.
   - When it is the opponent's turn: show the list for the user's next pick with a subtitle "Your next pick" and rows not clickable.
   Reasons must name the team correctly: deny reasons use the OPPONENT's scout report (their player → champion), comfort reasons use the user's report.
3. Add/adjust vitest tests for any changed pure logic (e.g. perspective helper). Run `cd web && npx vitest run` and `npx vite build`; both must pass. Do not commit.
