// Save-or-burn advisor for the team on the clock in a Fearless series.
// Pure functions — no React dependencies.
//
// For each available champion candidate (top 10 by our-team comfort + model
// strength), returns a recommendation with verdict and reasons.

import { pickImpact } from "./model.js";
import { likelyPicks } from "./scout.js";

/**
 * Compute save-or-burn recommendations.
 *
 * @param {object} params
 * @param {object} params.model - model.json contents (may be null)
 * @param {object} params.usReport - our team's scout report
 * @param {object} params.oppReport - opponent's scout report
 * @param {string} params.bucket - "G1" | "G2" | "G3+"
 * @param {Set<string>} params.blocked - champions already picked or banned this game
 * @param {Set<string>} params.burned - champions burned by Fearless
 * @param {string} params.ourTeamId - our team's ID
 * @param {string} params.oppTeamId - opponent's team ID
 * @param {string[]} params.bluePicks - current blue picks
 * @param {string[]} params.redPicks - current red picks
 * @param {boolean} params.blueFirstPick - whether blue had first pick
 * @param {"blue"|"red"} params.ourSide - our side this game
 * @param {number} params.gamesLeft - number of games that can still be played (including this one)
 * @param {number} params.seriesGameIndex - 0-based index of current game in series
 * @returns {{champion, verdict, score, reasons}[]}
 */
export function advise(params) {
  const {
    model, usReport, oppReport, bucket, blocked, burned,
    ourTeamId, oppTeamId, bluePicks, redPicks, blueFirstPick,
    ourSide, gamesLeft, seriesGameIndex,
  } = params;

  // Champions that are truly unavailable (blocked this game + burned)
  const unavailable = new Set([...blocked, ...burned]);

  // Candidate champions: top by our comfort + model strength
  const candidates = candidateChampions(usReport, model, unavailable, 10);

  // Opponent's likely picks for scoring deny value
  const oppLikely = oppReport
    ? likelyPicks(oppReport, bucket, unavailable, 10)
    : [];
  const oppLikelyMap = new Map(oppLikely.map((p) => [p.champion, p.score]));

  // Our comfort map (pick rate from scout report)
  const ourComfort = new Map();
  if (usReport) {
    for (const c of usReport.champions || []) {
      const b = c.by_bucket?.[bucket]?.picks;
      if (b?.rate) {
        ourComfort.set(c.champion, b.rate);
      } else if (c.picks?.rate) {
        ourComfort.set(c.champion, c.picks.rate);
      }
    }
  }

  const results = [];
  for (const champ of candidates) {
    if (unavailable.has(champ)) continue;

    // Model pick impact
    let impact = 0;
    if (model) {
      const state = {
        blueTeamId: ourSide === "blue" ? ourTeamId : oppTeamId,
        redTeamId: ourSide === "red" ? ourTeamId : oppTeamId,
        bluePicks: [...bluePicks],
        redPicks: [...redPicks],
        blueFirstPick,
      };
      impact = pickImpact(model, state, champ, ourSide);
    }

    // Our comfort with this champion
    const comfort = ourComfort.get(champ) || 0;

    // value_now = model impact + our comfort
    const valueNow = impact + comfort;

    // future_cost = our comfort * (gamesLeft - 1) — burning now loses it for later games
    // If this is the last possible game, future_cost = 0
    const futureGames = Math.max(0, gamesLeft - 1);
    const futureCost = comfort * futureGames;

    // deny_value = opponent's likely-pick score for this champion
    const denyValue = oppLikelyMap.get(champ) || 0;

    // Verdict logic
    let verdict;
    const reasons = [];

    if (denyValue > valueNow && denyValue > 0.1) {
      verdict = "deny";
      reasons.push(`Their top pick (${oppLikely.find(p => p.champion === champ)?.reason || "high value"}) — burning it denies them`);
      if (comfort > 0.1) {
        reasons.push(`Also your comfort pick`);
      }
    } else if (futureCost > valueNow && futureGames > 0) {
      verdict = "save";
      reasons.push(`Your comfort pick: ${futureGames} game${futureGames > 1 ? "s" : ""} left, consider saving`);
      if (comfort > 0.2) {
        reasons.push(`High comfort (${(comfort * 100).toFixed(0)}% pick rate this game number)`);
      }
    } else {
      verdict = "take-now";
      if (impact > 0.01) {
        reasons.push(`Model favors: +${(impact * 100).toFixed(1)}% win probability`);
      }
      if (comfort > 0.1) {
        reasons.push(`Your comfort pick (${(comfort * 100).toFixed(0)}% pick rate)`);
      }
      if (denyValue > 0.1) {
        reasons.push(`Also denies them`);
      }
      if (reasons.length === 0) {
        reasons.push("Best available option");
      }
    }

    // Last game: no saving
    if (futureGames === 0 && verdict === "save") {
      verdict = "take-now";
      reasons.push("Last possible game — take it now");
    }

    const score = valueNow - futureCost + denyValue * 0.5;

    results.push({ champion: champ, verdict, score, reasons });
  }

  return results.sort((a, b) => b.score - a.score);
}

/**
 * Get top candidate champions by our comfort + model strength.
 */
function candidateChampions(usReport, model, unavailable, n) {
  const scores = new Map();

  // From scout report: our pick rates
  if (usReport) {
    for (const c of usReport.champions || []) {
      if (unavailable.has(c.champion)) continue;
      const comfort = c.picks?.rate || 0;
      scores.set(c.champion, (scores.get(c.champion) || 0) + comfort);
    }
  }

  // From model: champion strength
  if (model) {
    for (const [champ, info] of Object.entries(model.champions || {})) {
      if (unavailable.has(champ)) continue;
      const strength = Math.max(0, info.strength || 0);
      scores.set(champ, (scores.get(champ) || 0) + strength * 0.3);
    }
  }

  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([champ]) => champ);
}
