import { useMemo } from "react";
import { advise } from "../advisor.js";
import { likelyPicks } from "../scout.js";
import { picksOf, sideOf, burnedBefore, nextStep, teamAt, ORDER } from "../draft.js";
import Portrait from "./Portrait.jsx";

/**
 * Advisor panel — always advises the user's team (first team select).
 *
 * - User's PICK turn: save/take/deny recommendations (clickable).
 * - User's BAN turn: ban suggestions (opponent's likely picks, clickable to ban).
 * - Opponent's turn: preview of user's next pick recommendations (not clickable).
 */
export default function AdvisorPanel({ model, series, game, usReport, oppReport, bucket, blocked, burned, onPick, turn, name }) {
  if (!model || !usReport || !oppReport) return null;

  const step = nextStep(game);
  if (step === -1 || !turn) return null;

  const usName = name("us");
  const pickingWho = turn.who;
  const isUsTurn = pickingWho === "us";
  const isBanTurn = turn.type === "ban";

  // Current picks from each side's perspective
  const blueWho = game.usSide === "blue" ? "us" : "opp";
  const redWho = blueWho === "us" ? "opp" : "us";
  const bluePicks = picksOf(game, blueWho);
  const redPicks = picksOf(game, redWho);
  const blueFirstPick = game.firstPick === blueWho;

  // Games left
  const winsNeeded = Math.ceil(series.format / 2);
  const sc = series.games.reduce((acc, g) => (g.winner ? { ...acc, [g.winner]: acc[g.winner] + 1 } : acc), { us: 0, opp: 0 });
  const maxRemaining = Math.max(0, winsNeeded - Math.max(sc.us, sc.opp));
  const gamesLeft = Math.max(1, maxRemaining);

  const usSide = sideOf(game, "us");

  // Always compute pick advice for the user's team
  const pickRecommendations = useMemo(
    () =>
      advise({
        model,
        usReport,
        oppReport,
        bucket,
        blocked,
        burned,
        ourTeamId: series.us,
        oppTeamId: series.opp,
        bluePicks,
        redPicks,
        blueFirstPick,
        ourSide: usSide,
        gamesLeft,
        seriesGameIndex: series.current,
      }),
    [model, usReport, oppReport, bucket, blocked, burned,
     series.us, series.opp, bluePicks, redPicks, blueFirstPick, usSide, gamesLeft, series.current],
  );

  // Ban suggestions: opponent's likely picks for this game
  const banSuggestions = useMemo(
    () => likelyPicks(oppReport, bucket, blocked, 6),
    [oppReport, bucket, blocked],
  );

  const verdictLabel = {
    "take-now": "Take now",
    save: "Save",
    deny: "Deny",
  };

  const verdictClass = {
    "take-now": "verdict-take",
    save: "verdict-save",
    deny: "verdict-deny",
  };

  // Determine mode
  let mode, subtitle, items, clickable;
  if (isUsTurn && isBanTurn) {
    // User's ban turn: show ban suggestions
    mode = "ban";
    subtitle = "Ban suggestions";
    items = banSuggestions;
    clickable = true;
  } else if (isUsTurn) {
    // User's pick turn: show pick recommendations
    mode = "pick";
    subtitle = "Your pick";
    items = pickRecommendations;
    clickable = true;
  } else {
    // Opponent's turn: show user's next pick preview
    mode = "preview";
    subtitle = "Your next pick";
    items = pickRecommendations;
    clickable = false;
  }

  return (
    <section className="advisor">
      <header>
        <h2>Advisor · {usName}</h2>
        <p>{subtitle}</p>
      </header>
      <ul className="advisor-list">
        {items.slice(0, 8).map((item, idx) => {
          const key = item.champion || idx;
          if (mode === "ban") {
            // Ban suggestion item: { champion, score, reason, record }
            return (
              <li key={key} className="advisor-row">
                <button
                  onClick={() => onPick(item.champion)}
                  disabled={!clickable}
                  title={item.reason || ""}
                >
                  <Portrait name={item.champion} small />
                  <div className="advisor-info">
                    <span className="advisor-champ"><b>{item.champion}</b></span>
                    <span className="verdict-chip verdict-deny">Ban</span>
                  </div>
                  <div className="advisor-reasons">
                    {item.reason && <span className="advisor-reason">{item.reason}</span>}
                  </div>
                </button>
              </li>
            );
          }
          // Pick recommendation item: { champion, verdict, score, reasons }
          return (
            <li key={key} className="advisor-row">
              <button
                onClick={() => clickable && onPick(item.champion)}
                disabled={!clickable}
                title={item.reasons?.join(" · ") || ""}
              >
                <Portrait name={item.champion} small />
                <div className="advisor-info">
                  <span className="advisor-champ"><b>{item.champion}</b></span>
                  <span className={`verdict-chip ${verdictClass[item.verdict]}`}>{verdictLabel[item.verdict]}</span>
                </div>
                <div className="advisor-reasons">
                  {item.reasons?.slice(0, 2).map((r, i) => (
                    <span key={i} className="advisor-reason">{r}</span>
                  ))}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
