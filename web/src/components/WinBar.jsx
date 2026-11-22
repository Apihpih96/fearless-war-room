import { useMemo } from "react";
import { winProbability } from "../model.js";
import { picksOf } from "../draft.js";

/**
 * Horizontal win-probability bar.
 * Layout: `LeftTeam Pct%` [bar fills remaining width] `Pct% RightTeam`
 * Second line: parts legend from the left team's perspective.
 * The left team is always the user's team (first team select), whatever side it plays.
 * winProbability returns P(blue wins), so we map to the user's team correctly.
 */
export default function WinBar({ model, series, game, name }) {
  if (!model) return null;

  const blueWho = game.usSide === "blue" ? "us" : "opp";
  const redWho = blueWho === "us" ? "opp" : "us";

  // Resolve team IDs
  const blueId = blueWho === "us" ? series.us : series.opp;
  const redId = redWho === "us" ? series.us : series.opp;

  const bluePicks = picksOf(game, blueWho);
  const redPicks = picksOf(game, redWho);
  const blueFirstPick = game.firstPick === blueWho;

  const { p, parts } = useMemo(
    () => winProbability(model, { blueTeamId: blueId, redTeamId: redId, bluePicks, redPicks, blueFirstPick }),
    [model, blueId, redId, bluePicks, redPicks, blueFirstPick],
  );

  // p = P(blue wins). We always show the user's team on the left.
  const usOnBlue = game.usSide === "blue";
  const usPct = usOnBlue ? p : 1 - p;
  const oppPct = 1 - usPct;

  const usPctStr = (usPct * 100).toFixed(1);
  const oppPctStr = (oppPct * 100).toFixed(1);

  const usName = name("us");
  const oppName = name("opp");

  // Parts in "points" (percentage-point contribution to win probability for the user's team)
  // When us is blue, parts are as-is; when us is red, we negate them.
  const sign = usOnBlue ? 1 : -1;
  const pts = {
    elo: (parts.elo * 100 * sign).toFixed(1),
    draft: (parts.draft * 100 * sign).toFixed(1),
    side: (parts.side * 100 * sign).toFixed(1),
    firstPick: (parts.firstPick * 100 * sign).toFixed(1),
  };
  const fmt = (v) => (Number(v) >= 0 ? `+${v}` : `${v}`);

  return (
    <div className="win-bar">
      <div className="win-bar-main">
        <span className={`win-bar-team win-bar-team--left ${game.usSide}`}>
          {usName} {usPctStr}%
        </span>
        <div className="win-bar-track">
          <div className="win-bar-fill" style={{ width: `${usPctStr}%`, background: `var(--${game.usSide})` }} />
        </div>
        <span className={`win-bar-team win-bar-team--right ${game.usSide === "blue" ? "red" : "blue"}`}>
          {oppPctStr}% {oppName}
        </span>
      </div>
      <div className="win-bar-legend">
        <span>{usName}: team form {fmt(pts.elo)} pts</span>
        <span>·</span>
        <span>draft {fmt(pts.draft)}</span>
        <span>·</span>
        <span>side {fmt(pts.side)}</span>
        <span>·</span>
        <span>first pick {fmt(pts.firstPick)}</span>
      </div>
    </div>
  );
}
